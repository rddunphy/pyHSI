import ctypes
from datetime import datetime
import json
from json.decoder import JSONDecodeError
import logging
import os
import string
import sys
import threading

import cv2
import numpy as np
import PySimpleGUI as sg
import serial
from serial.tools import list_ports
import spectral
from spectral.io import envi
import tkinter as tk

from . import __version__
from .cameras import BaslerCamera, MockCamera
from .stages import TSA200, MockStage
from .utils import get_rgb_bands, add_wavelength_labels


###############################################################################
# Event name definitions and menu items
###############################################################################

# Unique string keys for GUI elements - some also used as keys for
# configuration files

APP_VERSION = "Version"
PREVIEW_CANVAS = "PreviewCanvas"
PREVIEW_FRAME = "PreviewFrame"
CONSOLE_OUTPUT = "ConsoleOutput"

# Camera control panel
CAMERA_TYPE_SEL = "CameraModel"
CAMERA_TYPE_BASLER = "Basler VNIR"
CAMERA_TYPE_MOCK = "Mock camera"
CAMERA_MOCK_FILE = "MockCameraFilePath"
CAMERA_MOCK_FILE_BROWSE = "CameraMockFileBrowseButton"
CAMERA_MOCK_CONTROL_PANE = "CameraMockControlPanel"
CAMERA_REAL_CONTROL_PANE = "CameraRealControlPanel"
EXP_INPUT = "ExposureTimeMS"
EXP_FDB = "ExposureFeedback"
BINNING_SEL = "PixelBinning"
GAIN_INPUT = "RawGain"
GAIN_DB_LBL = "GainDBLabel"
GAIN_FDB = "GainFeedback"
REVERSE_COLUMNS_CB = "ReverseColumns"

# Stage control panel
STAGE_TYPE_SEL = "StageModel"
STAGE_TYPE_MOCK = "Mock stage"
STAGE_TYPE_TSA200 = "Zolix TSA200"
STAGE_PORT_SEL = "StagePortSelect"
PORT_RELOAD_BTN = "PortRefresh"
STAGE_PORT_PANE = "PortRefreshPane"
RANGE_START_INPUT = "RangeStart"
RANGE_END_INPUT = "RangeEnd"
RANGE_FDB = "RangeFeedback"
ADD_RANGE_FIELDS_BTN = "AddRangeFields"
VELOCITY_INPUT = "Velocity"
VELOCITY_FDB = "VelocityFeedback"

# Live preview control panel
PREVIEW_BTN = "CameraPreview"
PREVIEW_CLEAR_BTN = "PreviewClearButton"
PREVIEW_WATERFALL_CB = "PreviewWaterfall"
PREVIEW_HIGHLIGHT_CB = "PreviewHighlight"
PREVIEW_INTERP_CB = "PreviewInterpolation"
PREVIEW_ROTLEFT_BTN = "PreviewRotationLeft"
PREVIEW_ROTRIGHT_BTN = "PreviewRotationRight"
PREVIEW_PSEUDOCOLOUR_CB = "PreviewPseudocolour"
PREVIEW_SINGLE_BAND_SLIDER = "PreviewSingleBand"
PREVIEW_SINGLE_BAND_NM = "PreviewSingleBandNm"
PREVIEW_RED_BAND_SLIDER = "PreviewRedBand"
PREVIEW_RED_BAND_NM = "PreviewRedBandNm"
PREVIEW_GREEN_BAND_SLIDER = "PreviewGreenBand"
PREVIEW_GREEN_BAND_NM = "PreviewGreenBandNm"
PREVIEW_BLUE_BAND_SLIDER = "PreviewBlueBand"
PREVIEW_BLUE_BAND_NM = "PreviewBlueBandNm"
PREVIEW_SINGLE_BAND_PANE = "PreviewSingleBandPane"
PREVIEW_RGB_BAND_PANE = "PreviewRgbBandPane"

# Capture and save control panel
OUTPUT_FORMAT_SEL = "OutputFormat"
FORMAT_ENVI = "ENVI"
OUTPUT_FOLDER = "OutputFolder"
OUTPUT_FOLDER_BROWSE = "OutputFolderBrowseButton"
SAVE_FILE = "SaveFileName"
IMAGE_DESCRIPTION_INPUT = "ImageDescription"
CAPTURE_IMAGE_BTN = "CaptureImage"
STOP_CAPTURE_BTN = "StopImageCapture"
RESET_STAGE_BTN = "ResetStageButton"
MOVE_STAGE_BTN = "MoveStageButton"
CAPTURE_IMAGE_PROGRESS = "CaptureImageProgress"
CAPTURE_THREAD_DONE = "CaptureThreadDone"
CAPTURE_THREAD_PROGRESS = "CaputureThreadProgress"

# Menubar items
MENU_OPEN_FILE = "Open image in viewer... (Ctrl-O)"
MENU_SAVE_CONFIG = "Save configuration as... (Ctrl-S)"
MENU_LOAD_CONFIG = "Load configuration... (Ctrl-L)"
MENU_QUIT = "Quit (Ctrl-Q)"
MENU_HELP = "Help (F1)"
MENU_ABOUT = "About"

# Viewer window
VIEW_FRAME = "ViewFrame"
VIEW_CANVAS = "ViewCanvas"
PSEUDOCOLOUR_CB = "PseudocolourCheckbox"
SINGLE_BAND_SLIDER = "SingleBandSlider"
SINGLE_BAND_NM = "SingleBandNmLabel"
SINGLE_BAND_PANE = "SingleBandControlPane"
RED_BAND_SLIDER = "RedBandSlider"
RED_BAND_NM = "RedBandNmLabel"
GREEN_BAND_SLIDER = "GreenBandSlider"
GREEN_BAND_NM = "GreenBandNmLabel"
BLUE_BAND_SLIDER = "BlueBandSlider"
BLUE_BAND_NM = "BlueBandNmLabel"
RGB_BAND_PANE = "RGBBandControlPane"
INTERP_CB = "InterpolationCheckbox"
ROTLEFT_BTN = "RotateLeftButton"
ROTRIGHT_BTN = "RotateRightButton"


###############################################################################
# Icon names
###############################################################################

# Icon names correspond to filename with .png extension in ICON_DIR
ICON_DIR = os.path.abspath("icons")
ICON_APP = "pyhsi"
ICON_RELOAD = "reload"
ICON_OPEN = "open"
ICON_PLAY = "play"
ICON_PAUSE = "pause"
ICON_ROT_LEFT = "rotate-left"
ICON_ROT_RIGHT = "rotate-right"
ICON_DELETE = "delete"
ICON_CAMERA = "camera"
ICON_STOP = "stop"
ICON_RESET = "reset"
ICON_MOVE = "move"


###############################################################################
# Global configuration and logging settings
###############################################################################

# Input fields that are saved in config files
CONFIG_KEYS = (
    CAMERA_TYPE_SEL, CAMERA_MOCK_FILE, EXP_INPUT, BINNING_SEL, GAIN_INPUT,
    REVERSE_COLUMNS_CB, STAGE_TYPE_SEL, RANGE_START_INPUT, RANGE_END_INPUT,
    VELOCITY_INPUT, PREVIEW_WATERFALL_CB, PREVIEW_PSEUDOCOLOUR_CB,
    PREVIEW_SINGLE_BAND_SLIDER, PREVIEW_RED_BAND_SLIDER,
    PREVIEW_GREEN_BAND_SLIDER, PREVIEW_BLUE_BAND_SLIDER, PREVIEW_HIGHLIGHT_CB,
    PREVIEW_INTERP_CB, OUTPUT_FORMAT_SEL, OUTPUT_FOLDER, SAVE_FILE,
    IMAGE_DESCRIPTION_INPUT, APP_VERSION
)

# Config file versions that are compatible with this version of PyHSI
CONFIG_COMPAT_VERSIONS = ("0.2.0")
DEFAULT_CONFIG_PATH = os.path.abspath("default_config.phc")

LOG_COLOURS = {
    "DEBUG": "grey",
    "INFO": "black",
    "WARNING": "orange",
    "ERROR": "red",
    "CRITICAL": "red"
}
LOG_FILE_PATH = os.path.abspath("pyhsi.log")

# Allow ENVI header files with uppercase parameters
spectral.settings.envi_support_nonlowercase_params = True


###############################################################################
# Help and About dialog texts
###############################################################################

CREDITS = f"""PyHSI v{__version__}
© 2021 R. David Dunphy
Center for Signal & Image Processing
University of Strathclyde"""

HELP_TEXT = f"""Help for PyHSI version {__version__}

PyHSI is an application for capturing hyperspectral images. Images are \
captured using the control panel on the left of the left side of the window, \
and previews of images are displayed in the view panel on the right. The \
console at the bottom of the window provides feedback on the application's \
operation.


=Controls=

Overview of the controls available in the control panel.

==Camera==

Controls related to camera hardware setup:

* Model: Select camera model. Currently only supports the Basler piA1600 \
VNIR camera. The mock camera allows the behaviour of a camera to be simulated \
using an existing source file for testing purposes.
* Exposure time: Sets the exposure time of the camera in ms.
* Binning: Sets the pixel binning of the camera in both axes.
* Gain: Sets the camera's raw gain value. Actual gain in dB is displayed to \
the right.
* Reverse order of columns: If checked, each frame will be mirrored \
horizontally. Useful if the orientation of the camera is changed.

==Stage==

Controls related to stage hardware setup:

* Model: Select stage model. Currently only supports Zolix TSA200 stage with \
Schneider motor controller. The mock stage allows the behaviour of the TSA200 \
to be simulated for testing purposes.
* Port: Serial port to use for translation stage. Should show up as name of \
serial adapter (USB2Serial 1xRS422/485) once the stage is connected and \
refresh button has been pressed.
* Capture range: Start and end positions of stage in mm to be imaged.
* Velocity: Stage imaging velocity in mm/s.

==Live preview==

Controls for live preview from camera:

* Waterfall: Display selected band(s) sequentially moving across the screen.
* Pseudocolour: Use three bands instead of one to create a pseudocolour image \
(only available for waterfall preview).
* Highlight saturated: Highlight light-saturated pixels in red and \
dark-saturated pixels in blue (not available for pseudocoloured images).
* Interpolation: Apply linear interpolation to scaled images.
* Control buttons: Start/stop live preview, rotate preview left or right, \
clear preview panel.

==Capture and save==

Controls related to capturing and saving images:

* Format: Select output format used to save images. Currently only supports \
ENVI standard.
* Folder: Root folder for saving images.
* File name: Template file name to use for saving images. Accepts Python \
f-string fields; see File name templates section below for details.
* Description: Description to include in image metadata. Accepts Python \
f-string fields; see File name templates section below for details.
* Control buttons: Capture and save image, reset stage to minimum, move stage \
to target position, cancel image capture (this should immediately stop the \
stage from moving).


=Config files=

Configurations can be saved as JSON files with the extension .phc. \
Configuration files can be saved and loaded using options in the File menu. \
The default configuration can be changed by saving a configuration to \
{DEFAULT_CONFIG_PATH}.


=File name templates=

The output file name and description text fields accept Python f-strings with \
the following fields:

* {{model}} - make and model of the camera
* {{date}} - today's date, formatted as yyyy-mm-dd
* {{time}} - time of image acquisition, formatted as HH:MM:SS
* {{exp}} - exposure time in ms
* {{bin}} - pixel binning
* {{gain}} - gain in dB
* {{raw_gain}} - raw gain value
* {{mode}} - 12-bit or 8-bit
* {{start}} - start of imaging range in mm
* {{stop}} - end of imaging range in mm
* {{travel}} - range of stage imaged in mm
* {{vel}} - stage velocity in mm/s
* {{version}} - PyHSI version
* {{n}} - image number

The {{n}} field represents an identifier that causes the file name to be \
unique, so that multiple images captured with the same template name will be \
numbered sequentially.

Fields can be adjusted using Python format specifiers, e.g. {{n:03}} will \
left-pad numbers with zeros to make them three digits long, and {{exp:.2f}} \
will round the exposure time to two decimal places. Literal braces can be \
inserted by doubling them {{{{like this}}}}.


=Log file=

The output from the console as well as further details of any errors \
encountered are saved to {LOG_FILE_PATH}. PyHSI can be started in debug mode \
with the --debug flag, which will result in additional details being logged.


=Capturing HSI data=

Suggested workflow for caputuring images with the Zolix TSA200 stage and \
Basler piA1600 VNIR camera:

* Connect Zolix translation stage to power outlet and USB port
* Connect Basler camera to power outlet and ethernet port
* Connect enclosure to power outlet and check that lights turn on when door \
is closed
* Adjust exposure and gain using live preview so that there are no saturated \
pixels when imaging a white calibration tile
* Adjust focus by inserting extension rings or adjusting height of the camera \
and/or sample using waterfall preview
* Capture dark reference image with the lens cap on
* Place calibration tile and sample tray on stage
* Place lid fully over the enclosure to block out ambient light
* Capture images of samples with door fully closed to turn on halogen lights
* If necessary, adjust velocity to ensure square pixels
"""


###############################################################################
# Auxiliary classes and functions
###############################################################################


class LoggingHandler(logging.StreamHandler):
    """Pipes logging events to the console output"""

    def __init__(self, window):
        logging.StreamHandler.__init__(self)
        self.window = window

    def emit(self, record):
        level = record.levelname
        line = f'[{record.asctime}] {level}: {record.message}'
        if self.window[CONSOLE_OUTPUT].get().strip():
            line = '\n' + line
        sg.cprint(line, text_color=LOG_COLOURS[level], end='')


class InterruptableThread(threading.Thread):
    """Daemon thread that can be killed by calling `interrupt()`"""

    def __init__(self, target=None, args=None):
        threading.Thread.__init__(self, target=target, args=args, daemon=True)

    def get_id(self):
        if hasattr(self, '_thread_id'):
            return self._thread_id
        for id, thread in threading._active.items():
            if thread is self:
                return id

    def interrupt(self):
        thread_id = self.get_id()
        logging.debug(f"Interrupting thread {thread_id}")
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_long(thread_id), ctypes.py_object(SystemExit))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_long(thread_id), 0)
            logging.error("Failed to interrupt capture thread")


def get_band_slider(key, range=(0, 99), default_value=49):
    """Create slider element for selecting hyperspectral band"""
    return sg.Slider(
        range=range,
        default_value=default_value,
        orientation="h",
        disable_number_display=True,
        key=key,
        enable_events=True
    )


def template_to_file_name(root_dir, template, namespace, ext, max_n=99999):
    """Generate a file name that matches the given template"""
    if not template.endswith(ext):
        template += ext
    uses_n = False
    for _, field, _, _ in string.Formatter().parse(template):
        if field == "n":
            uses_n = True
    for n in range(max_n + 1):
        namespace['n'] = n
        file_name = template.format(**namespace)
        path = os.path.join(root_dir, file_name)
        if not os.path.isfile(path):
            return path
        if not uses_n:
            raise IOError(f"File {path} already exists")
    raise IOError((f"All file names of the format {template} are in use "
                   f"(n<={max_n})"))


def get_icon_button(icon, key=None, button_type=None, file_types=None,
                    initial_folder=None, disabled=False, tooltip=None):
    """Create a button with an icon as an image"""
    mc = ("white", "#405e92")
    icon_path = os.path.join(ICON_DIR, icon + ".png")
    if button_type is not None:
        return sg.Button("", image_filename=icon_path, key=key,
                         disabled=disabled, button_type=button_type,
                         file_types=file_types, target=(sg.ThisRow, -1),
                         initial_folder=initial_folder, tooltip=tooltip,
                         mouseover_colors=mc)
    return sg.Button("", image_filename=icon_path, key=key, disabled=disabled,
                     tooltip=tooltip, mouseover_colors=mc)


def port_label(port):
    """Return string to identify serial port by"""
    if port.product:
        return f"{port.device}: {port.product}"
    return str(port.device)


def resize_img_to_area(img, size, preserve_aspect_ratio=True, interpolation=False):
    """Resize frame to fill available area in preview panel"""
    max_w = max(size[0] - 20, 20)
    max_h = max(size[1] - 20, 20)
    if preserve_aspect_ratio:
        old_h = img.shape[0]
        old_w = img.shape[1]
        new_w = round(min(max_w, old_w * max_h / old_h))
        new_h = round(min(max_h, old_h * max_w / old_w))
    else:
        new_w = max_w
        new_h = max_h
    if interpolation:
        interp = cv2.INTER_LINEAR
    else:
        interp = cv2.INTER_NEAREST
    return cv2.resize(img, (new_w, new_h), interpolation=interp)


###############################################################################
# Main application classes
###############################################################################


class PyHSI:
    """Root window for capturing images"""

    def __init__(self, debug=False):
        self.debug = debug
        self.viewers = {}
        self.default_folder = os.environ['HOME']
        self.xy_expand_elements = []
        self.x_expand_elements = []
        self.live_preview_active = False
        self.live_preview_rotation = 1
        self.waterfall_frame = None
        self.live_preview_frame = None
        self.camera = None
        self.camera_type = None
        self.stage = None
        self.stage_type = None
        self.viewer_file = None
        self.viewer_img = None
        self.capture_thread = None

        # Global PySimpleGUI options
        icon_ext = ".ico" if sg.running_windows() else ".png"
        icon_path = os.path.join(ICON_DIR, ICON_APP + icon_ext)
        sg.set_global_icon(icon_path)
        sg.set_options(font=("latin modern sans", 12))

        # PySimpleGUI layout
        menubar = sg.Menu([
            ["&File", ["&" + MENU_OPEN_FILE, "&" + MENU_SAVE_CONFIG, "&" + MENU_LOAD_CONFIG, "&" + MENU_QUIT]],
            ["&Help", ["&" + MENU_HELP, "&" + MENU_ABOUT]]
        ])
        content = [
            [
                sg.Column(
                    self.capture_control_panel(),
                    expand_y=True,
                    expand_x=True
                ),
                sg.Column(
                    self.preview_panel(),
                    expand_y=True,
                    expand_x=True
                )
            ]
        ]
        console = sg.Multiline(
            size=(20, 4),
            key=CONSOLE_OUTPUT,
            disabled=True
        )
        self.x_expand_elements.append(console)
        self.window = sg.Window(
            title="PyHSI",
            layout=[[menubar], [content], [console]],
            enable_close_attempted_event=True,
            resizable=True,
            size=(99999, 99999),
            finalize=True
        )
        self.window[IMAGE_DESCRIPTION_INPUT].Widget.configure(undo=True)

        for e in self.xy_expand_elements:
            e.expand(expand_x=True, expand_y=True)
        for e in self.x_expand_elements:
            e.expand(expand_x=True, expand_y=False, expand_row=False)

        # Set up keyboard shortcuts
        self.window.bind("<Control-q>", MENU_QUIT)
        self.window.bind("<Control-l>", MENU_LOAD_CONFIG)
        self.window.bind("<Control-s>", MENU_SAVE_CONFIG)
        self.window.bind("<Control-o>", MENU_OPEN_FILE)
        self.window.bind("<F1>", MENU_HELP)

        # Set up logging
        sg.cprint_set_output_destination(self.window, CONSOLE_OUTPUT)
        logging.basicConfig(
            level=logging.DEBUG if debug else logging.INFO,
            format="[%(asctime)s] %(levelname)-8s (%(pathname)s:%(lineno)d) : %(message)s",
            filename=LOG_FILE_PATH,
            datefmt="%H:%M:%S",
            filemode='w'
        )
        handler = LoggingHandler(self.window)
        logging.getLogger('').addHandler(handler)
        logging.captureWarnings(True)
        logging.info(f"Starting PyHSI v{__version__}")
        logging.debug(f"Running in debug mode - full log at {LOG_FILE_PATH}")
        logging.debug(f"Window size: {self.window.size}")

        # Load default configuration
        if os.path.isfile(DEFAULT_CONFIG_PATH):
            self.load_config(config_file=DEFAULT_CONFIG_PATH)
        else:
            logging.debug(f"No default configuration file at {DEFAULT_CONFIG_PATH}")

    def run(self):
        """Main event loop - events handled in `handle_event`"""
        try:
            while True:
                timeout = 10 if self.live_preview_active else None
                window, event, values = sg.read_all_windows(timeout=timeout)
                if event == '__TIMEOUT__' and self.live_preview_active:
                    _, values = self.window.read(timeout=0)
                    self.next_live_preview_frame(values)
                elif window is self.window:
                    self.handle_event(event, values)
                else:
                    try:
                        viewer = self.viewers[window]
                        viewer.handle_event(event, values)
                    except KeyError:
                        logging.debug("Event in unknown window {window}")
        except KeyboardInterrupt:
            logging.error("Received KeyboardInterrupt")
            self.exit(force=True)
        except Exception as e:
            logging.exception(f"Fatal exception: {e}")
            self.exit(force=True)

    def exit(self, force=False):
        """Exit application"""
        if not force and (self.live_preview_active or
                          self.capture_thread is not None):
            msg = "Are you sure you want to exit PyHSI?"
            if not self.confirm_popup("Confirm exit", msg):
                return
        if self.live_preview_active:
            self.stop_live_preview()
        if self.capture_thread is not None:
            self.stop_capture()
        open_viewers = list(self.viewers.values())
        if open_viewers:
            logging.debug(f"Closing {len(open_viewers)} open viewer(s)...")
            for viewer in open_viewers:
                viewer.exit()
        logging.info("Exiting PyHSI")
        self.window.close()
        sys.exit()

    def handle_event(self, event, values):
        """Event triaging"""
        logging.debug(f"Handling {event} event")
        if event in (EXP_INPUT, VELOCITY_INPUT, RANGE_START_INPUT,
                     RANGE_END_INPUT):
            self.validate(event)
        elif event in (PREVIEW_WATERFALL_CB, PREVIEW_PSEUDOCOLOUR_CB,
                       CAMERA_TYPE_SEL, STAGE_TYPE_SEL, GAIN_INPUT):
            self.update_view(values)
        elif event == BINNING_SEL:
            self.camera.set_binning(int(values[BINNING_SEL]))
            self.update_preview_slider_ranges(values)
        elif event == CAMERA_MOCK_FILE:
            file_name = values[CAMERA_MOCK_FILE]
            try:
                self.camera.set_result_image(file_name)
                self.update_preview_slider_ranges(values)
            except Exception as e:
                # Invalid source file, but at this stage we don't care
                logging.debug(f"Suppressed exception: {e}")
        elif event == CAPTURE_IMAGE_BTN:
            self.capture_image(values)
        elif event == STOP_CAPTURE_BTN:
            self.stop_capture()
        elif event == RESET_STAGE_BTN:
            self.reset_stage(values)
        elif event == MOVE_STAGE_BTN:
            self.move_stage(values)
        elif event == CAPTURE_THREAD_DONE:
            self.window[CAPTURE_IMAGE_PROGRESS].update(0, visible=False)
            self.window[CAPTURE_IMAGE_BTN].update(disabled=False)
            self.window[STOP_CAPTURE_BTN].update(disabled=True)
            self.window[RESET_STAGE_BTN].update(disabled=False)
            self.window[MOVE_STAGE_BTN].update(disabled=False)
            self.window[PREVIEW_BTN].update(disabled=False)
            self.capture_thread = None
        elif event == CAPTURE_THREAD_PROGRESS:
            self.window[CAPTURE_IMAGE_PROGRESS].update(values[CAPTURE_THREAD_PROGRESS])
        elif event == PREVIEW_BTN:
            if self.live_preview_active:
                self.stop_live_preview()
            else:
                self.start_live_preview(values)
        elif event == PREVIEW_ROTLEFT_BTN:
            self.live_preview_rotation = (self.live_preview_rotation + 1) % 4
            if not self.live_preview_active:
                self.update_live_preview(values[PREVIEW_WATERFALL_CB], values[PREVIEW_INTERP_CB])
        elif event == PREVIEW_ROTRIGHT_BTN:
            self.live_preview_rotation = (self.live_preview_rotation - 1) % 4
            if not self.live_preview_active:
                self.update_live_preview(values[PREVIEW_WATERFALL_CB], values[PREVIEW_INTERP_CB])
        elif event in (PREVIEW_SINGLE_BAND_SLIDER, PREVIEW_RED_BAND_SLIDER,
                       PREVIEW_GREEN_BAND_SLIDER, PREVIEW_BLUE_BAND_SLIDER):
            self.update_preview_slider_labels(values)
        elif event == PREVIEW_CLEAR_BTN:
            self.clear_preview()
        elif event == PREVIEW_INTERP_CB:
            if not self.live_preview_active:
                self.update_live_preview(values[PREVIEW_WATERFALL_CB], values[PREVIEW_INTERP_CB])
        elif event == PORT_RELOAD_BTN:
            self.reload_stage_ports()
        elif event == OUTPUT_FOLDER:
            self.set_default_folder(values[OUTPUT_FOLDER], warn=False)
        elif event == MENU_OPEN_FILE:
            self.open_file()
        elif event == MENU_SAVE_CONFIG:
            self.save_config(values)
        elif event == MENU_LOAD_CONFIG:
            self.load_config()
        elif event == MENU_HELP:
            self.display_help()
        elif event == MENU_ABOUT:
            self.display_about()
        elif event in (MENU_QUIT, sg.WINDOW_CLOSE_ATTEMPTED_EVENT):
            self.exit()
        elif event is None:
            # With multiple windows, close attempt causes None event, see
            # https://github.com/PySimpleGUI/PySimpleGUI/issues/3771
            logging.debug("Treating None event as sg.WINDOW_CLOSE_ATTEMPTED_EVENT")
            self.exit()

    def validate(self, field):
        """Validate numeric inputs and display feedback messages"""
        value = self.window[field].get()
        if field == EXP_INPUT:
            self.parse_numeric(value, float, 0.1, 1000, EXP_FDB)
        elif field == GAIN_INPUT:
            self.parse_numeric(value, int, 0, 500, GAIN_FDB)
        elif field == VELOCITY_INPUT:
            self.parse_numeric(value, float, 0.01, 50, VELOCITY_FDB)
        elif field == RANGE_START_INPUT or field == RANGE_END_INPUT:
            self.parse_numeric(value, float, 0, 196, RANGE_FDB)

    def reload_stage_ports(self):
        """Update list of available serial ports"""
        self.ports = list_ports.comports()
        logging.info(f"Found {len(self.ports)} available serial port(s).")
        if len(self.ports) > 0:
            ports = [port_label(p) for p in self.ports]
        else:
            ports = ["No ports found"]
        self.window[STAGE_PORT_SEL].update(
            values=ports,
            value=ports[0],
            disabled=(len(self.ports) == 0),
            readonly=True
        )

    def update_gain_label(self, values):
        """Calculate actual gain in dB from raw gain value"""
        gain = self.parse_numeric(values[GAIN_INPUT], int, 0, 500, GAIN_FDB)
        if gain is None or self.camera is None:
            return
        gain_db = gain * self.camera.raw_gain_factor
        self.window[GAIN_DB_LBL].update(value=f"({gain_db:.2f} dB)")

    def update_preview_slider_labels(self, values):
        """Update labels to display wavelength for to selected band"""
        s_b = round(values[PREVIEW_SINGLE_BAND_SLIDER])
        r_b = round(values[PREVIEW_RED_BAND_SLIDER])
        g_b = round(values[PREVIEW_GREEN_BAND_SLIDER])
        b_b = round(values[PREVIEW_BLUE_BAND_SLIDER])
        if self.camera.wl:
            s_nm = self.camera.wl[s_b]
            r_nm = self.camera.wl[r_b]
            g_nm = self.camera.wl[g_b]
            b_nm = self.camera.wl[b_b]
            self.window[PREVIEW_SINGLE_BAND_NM].update(f"{s_b} ({s_nm:.1f} nm)")
            self.window[PREVIEW_RED_BAND_NM].update(f"{r_b} ({r_nm:.1f} nm)")
            self.window[PREVIEW_GREEN_BAND_NM].update(f"{g_b} ({g_nm:.1f} nm)")
            self.window[PREVIEW_BLUE_BAND_NM].update(f"{b_b} ({b_nm:.1f} nm)")
        else:
            self.window[PREVIEW_SINGLE_BAND_NM].update(f"{s_b}")
            self.window[PREVIEW_RED_BAND_NM].update(f"{r_b}")
            self.window[PREVIEW_GREEN_BAND_NM].update(f"{g_b}")
            self.window[PREVIEW_BLUE_BAND_NM].update(f"{b_b}")

    def update_preview_slider_ranges(self, values):
        """Set ranges for sliders based on bands of current camera"""
        if self.camera.wl:
            n = len(self.camera.wl)
            rgb = get_rgb_bands(self.camera.wl)
            r = rgb[0]
            g = rgb[1]
            b = rgb[2]
        else:
            n = 100
            r = 74
            g = 49
            b = 24
        s = (n - 1) // 2
        self.window[PREVIEW_SINGLE_BAND_SLIDER].update(
            range=(0, n - 1), disabled=False)
        self.window[PREVIEW_SINGLE_BAND_SLIDER].update(value=s)
        values[PREVIEW_SINGLE_BAND_SLIDER] = s
        self.window[PREVIEW_RED_BAND_SLIDER].update(
            range=(0, n - 1), disabled=False)
        self.window[PREVIEW_RED_BAND_SLIDER].update(value=r)
        values[PREVIEW_RED_BAND_SLIDER] = r
        self.window[PREVIEW_GREEN_BAND_SLIDER].update(
            range=(0, n - 1), disabled=False)
        self.window[PREVIEW_GREEN_BAND_SLIDER].update(value=g)
        values[PREVIEW_GREEN_BAND_SLIDER] = g
        self.window[PREVIEW_BLUE_BAND_SLIDER].update(
            range=(0, n - 1), disabled=False)
        self.window[PREVIEW_BLUE_BAND_SLIDER].update(value=b)
        values[PREVIEW_BLUE_BAND_SLIDER] = b
        self.update_preview_slider_labels(values)

    def update_view(self, values=None):
        """Hide/display various view elements based on inputs"""
        if values is None:
            _, values = self.window.read(timeout=0)
        if values[CAMERA_TYPE_SEL] == CAMERA_TYPE_MOCK:
            self.window[CAMERA_MOCK_CONTROL_PANE].update(visible=True)
            self.window[CAMERA_REAL_CONTROL_PANE].update(visible=False)
        else:
            self.window[CAMERA_MOCK_CONTROL_PANE].update(visible=False)
            self.window[CAMERA_REAL_CONTROL_PANE].update(visible=True)
        try:
            self.setup_camera(values)
        except ValueError as e:
            # Happens whenever no source file has been selected yet
            logging.debug(f"Suppressed ValueError: {e}")
        except Exception as e:
            logging.exception(e)
        self.update_gain_label(values)
        self.update_preview_slider_ranges(values)
        pc_disabled = not values[PREVIEW_WATERFALL_CB]
        hl_disabled = values[PREVIEW_WATERFALL_CB] and values[PREVIEW_PSEUDOCOLOUR_CB]
        self.window[PREVIEW_PSEUDOCOLOUR_CB].update(disabled=pc_disabled)
        self.window[PREVIEW_HIGHLIGHT_CB].update(disabled=hl_disabled)
        single_vis = not pc_disabled and not values[PREVIEW_PSEUDOCOLOUR_CB]
        rgb_vis = not pc_disabled and values[PREVIEW_PSEUDOCOLOUR_CB]
        self.window[PREVIEW_RGB_BAND_PANE].update(visible=rgb_vis)
        self.window[PREVIEW_SINGLE_BAND_PANE].update(visible=single_vis)
        if not self.live_preview_active:
            self.update_live_preview(values[PREVIEW_WATERFALL_CB], values[PREVIEW_INTERP_CB])
        if values[STAGE_TYPE_SEL] == STAGE_TYPE_MOCK:
            self.window[STAGE_PORT_PANE].update(visible=False)
        else:
            self.window[STAGE_PORT_PANE].update(visible=True)

    def set_default_folder(self, folder, warn=True):
        """Change folder used as initial folder for dialogs"""
        if os.path.isdir(folder):
            self.default_folder = folder
            self.window[CAMERA_MOCK_FILE_BROWSE].InitialFolder = folder
            self.window[OUTPUT_FOLDER_BROWSE].InitialFolder = folder
        elif warn:
            logging.warning(f"{folder} is not a valid directory")

    def load_config(self, config_file=None):
        """Load configuration from file"""
        if config_file is None:
            config_file = tk.filedialog.askopenfilename(
                filetypes=(("PyHSI config", "*.phc"),),
                initialdir=self.default_folder,
                parent=self.window.TKroot)
        if config_file == () or config_file == "":
            # User pressed cancel
            return
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                v = config[APP_VERSION]
                if v not in CONFIG_COMPAT_VERSIONS:
                    msg = (f"Configuration file version {v} incompatible ",
                           f"with PyHSI v{__version__} for {config_file}")
                    raise IOError(msg)
                for key in CONFIG_KEYS:
                    if key in config and key != APP_VERSION:
                        self.window[key].update(value=config[key])
                for key in config.keys():
                    if key not in CONFIG_KEYS:
                        logging.warning(f"Unknown key {key} in config file")
                logging.info(f"Loaded configuration from {config_file}")
                self.update_view()
                if OUTPUT_FOLDER in config:
                    self.set_default_folder(config[OUTPUT_FOLDER])
        except (IOError, JSONDecodeError) as e:
            logging.exception(f"Unable to read config file: {e}")

    def save_config(self, values):
        """Save current configuration to file"""
        config = {k: v for k, v in values.items() if k in CONFIG_KEYS}
        config[APP_VERSION] = __version__
        config_file = tk.filedialog.asksaveasfilename(
            filetypes=(("PyHSI config", "*.phc"),),
            defaultextension='.phc',
            initialdir=self.default_folder,
            parent=self.window.TKroot
        )
        if config_file == () or config_file == "":
            # User pressed cancel
            return
        try:
            with open(config_file, 'w') as f:
                f.write(json.dumps(config, indent=4) + "\n")
                logging.info(f"Saved current configuration to {config_file}")
        except IOError as e:
            logging.exception(f"Unable to write config file: {e}")

    def open_file(self):
        """Open an HSI image in a new Viewer window"""
        file_path = tk.filedialog.askopenfilename(
            filetypes=(("ENVI", "*.hdr"),),
            initialdir=self.default_folder,
            parent=self.window.TKroot)
        if file_path == () or file_path == "":
            # User pressed cancel
            return
        logging.info(f"Opening {file_path}")
        ws = self.window.size
        size = (round(ws[0] * 0.7), round(ws[1] * 0.7))
        viewer = Viewer(self, file_path, size)
        self.viewers[viewer.window] = viewer

    def setup_stage(self, values):
        """Connect to stage - returns True if successful, False otherwise"""
        try:
            stage_type = values[STAGE_TYPE_SEL]
            if self.stage is None or stage_type != self.stage_type:
                if stage_type == STAGE_TYPE_TSA200:
                    pstr = values[STAGE_PORT_SEL]
                    port = None
                    for p in self.ports:
                        if pstr == port_label(p):
                            port = p
                    if port is None:
                        logging.error(f"No serial port for stage '{stage_type}'")
                        return False
                    self.stage = TSA200(port=serial.Serial(port.device))
                else:
                    self.stage = MockStage()
                self.stage_type = stage_type
        except Exception as e:
            logging.exception(f"Unable to connect to stage '{stage_type}': {e}")
            return False
        return True

    def setup_camera(self, values):
        """Set camera values - raises exception if unable to connect"""
        camera_type = values[CAMERA_TYPE_SEL]
        if not self.camera or camera_type != self.camera_type:
            if camera_type == CAMERA_TYPE_BASLER:
                self.camera = BaslerCamera()
            else:
                self.camera = MockCamera()
            self.camera_type = camera_type
        vals = self.parse_values(values)
        self.camera.set_exposure_time(vals['exp'])
        self.camera.set_raw_gain(vals['gain'])
        self.camera.set_binning(vals['binning'])
        if self.camera_type == CAMERA_TYPE_MOCK:
            file_name = values[CAMERA_MOCK_FILE].strip()
            if file_name != "":
                self.camera.set_result_image(file_name)
            else:
                raise ValueError("No source image specified for mock camera")

    def parse_numeric(self, input_, type_, min_, max_, fdb_key):
        """Utility function to validate and parse a numeric value"""
        try:
            val = type_(input_)
            if val < min_:
                raise ValueError(f"Minimum value {min_}")
            if val > max_:
                raise ValueError(f"Maximum value {max_}")
            if fdb_key is not None:
                self.window[fdb_key].update(visible=False)
            return val
        except ValueError as e:
            logging.debug(f"ValueError for numeric input: {e}")
            # Display feedback text field
            if fdb_key is not None:
                self.window[fdb_key].update(visible=True)
            return None

    def parse_values(self, values):
        """Convert input form values to a usable format and return as dict"""
        exp_ms = self.parse_numeric(
            values[EXP_INPUT], float, 0.1, 1000, EXP_FDB)
        if exp_ms is not None:
            exp = round(exp_ms * 1000)
        else:
            exp = None
        gain = self.parse_numeric(
            values[GAIN_INPUT], int, 0, 500, GAIN_FDB)
        binning = int(values[BINNING_SEL])
        ranges = (float(values[RANGE_START_INPUT]),
                  float(values[RANGE_END_INPUT]))
        flip = values[REVERSE_COLUMNS_CB]
        file_name = os.path.join(
            values[OUTPUT_FOLDER], values[SAVE_FILE])
        velocity = self.parse_numeric(
            values[VELOCITY_INPUT], float, 0.1, 40, VELOCITY_FDB)
        values = {'exp': exp, 'gain': gain, 'binning': binning,
                  'ranges': ranges, 'flip': flip, 'file_name': file_name,
                  'velocity': velocity}
        if None in values.values():
            raise ValueError("Invalid input(s)")
        return values

    def start_live_preview(self, values):
        """Start preview from connected camera"""
        try:
            logging.debug("Starting live preview")
            self.setup_camera(values)
            self.live_preview_active = True
            self.next_live_preview_frame(values)
            icon_path = os.path.join(ICON_DIR, ICON_PAUSE + ".png")
            self.window[PREVIEW_BTN].update(image_filename=icon_path)
            self.window[PREVIEW_CLEAR_BTN].update(disabled=False)
            self.window[PREVIEW_ROTLEFT_BTN].update(disabled=False)
            self.window[PREVIEW_ROTRIGHT_BTN].update(disabled=False)
        except Exception as e:
            logging.exception(f"Unable to start preview: {e}")

    def stop_live_preview(self):
        """Stop displaying frames from camera"""
        logging.debug("Stopping live preview")
        icon_path = os.path.join(ICON_DIR, ICON_PLAY + ".png")
        self.window[PREVIEW_BTN].update(image_filename=icon_path)
        self.live_preview_active = False

    def clear_preview(self):
        """Reset live preview and remove whatever is currently displayed"""
        if self.live_preview_active:
            self.stop_live_preview()
        self.window[PREVIEW_CANVAS].update(data=None)
        self.waterfall_frame = None
        self.live_preview_frame = None
        self.window[PREVIEW_CLEAR_BTN].update(disabled=True)
        self.window[PREVIEW_ROTLEFT_BTN].update(disabled=True)
        self.window[PREVIEW_ROTRIGHT_BTN].update(disabled=True)

    def next_live_preview_frame(self, values):
        """Get next frame from camera, process, and display"""
        # Pseudocolour takes precedence over highlight
        flip = values[REVERSE_COLUMNS_CB]
        hl = values[PREVIEW_HIGHLIGHT_CB]
        waterfall = values[PREVIEW_WATERFALL_CB]
        pc = values[PREVIEW_PSEUDOCOLOUR_CB]
        if waterfall and pc:
            hl = False
        try:
            frame = self.camera.get_frame(flip=flip, highlight=hl)
            frame = np.asarray(frame * 255, dtype="uint8")
        except Exception as e:
            logging.exception(f"Unable to connect to camera: {e}")
            self.stop_live_preview()
            return
        if self.waterfall_frame is None or self.waterfall_frame.shape[0] != frame.shape[0]:
            self.waterfall_frame = np.zeros((frame.shape[0], 500, 3))
        self.waterfall_frame[:, :-1] = self.waterfall_frame[:, 1:]
        if not hl and not pc:
            frame = np.repeat(frame[:, :, np.newaxis], 3, axis=2)
        if pc and (waterfall or not hl):
            bgr = (round(values[PREVIEW_BLUE_BAND_SLIDER]),
                   round(values[PREVIEW_GREEN_BAND_SLIDER]),
                   round(values[PREVIEW_RED_BAND_SLIDER]))
            self.waterfall_frame[:, -1] = frame[:, bgr]
        else:
            band = round(values[PREVIEW_SINGLE_BAND_SLIDER])
            self.waterfall_frame[:, -1] = frame[:, band]
        if len(frame.shape) == 2:
            self.live_preview_frame = np.repeat(frame[:, :, np.newaxis], 3, axis=2)
        else:
            self.live_preview_frame = frame
        self.update_live_preview(waterfall, values[PREVIEW_INTERP_CB])

    def update_live_preview(self, waterfall, interpolation):
        """Update preview display to reflect new frame/changed settings"""
        frame = self.waterfall_frame if waterfall else self.live_preview_frame
        if frame is None:
            self.clear_preview()
            return
        frame = np.rot90(frame, k=self.live_preview_rotation)
        frame = resize_img_to_area(
            frame, self.window[PREVIEW_FRAME].get_size(),
            preserve_aspect_ratio=not waterfall, interpolation=interpolation)
        if not waterfall and self.camera.wl:
            frame = add_wavelength_labels(frame, self.camera.wl, rot=self.live_preview_rotation)
        frame = cv2.imencode('.png', frame)[1].tobytes()
        self.window[PREVIEW_CANVAS].update(data=frame)

    def show_captured_preview(self, img, wl):
        """Display a preview of the image that has just been captured"""
        band = img[:, :, len(wl)//2]
        band = np.asarray(band * 255, dtype="uint8")
        band = resize_img_to_area(band, self.window[PREVIEW_FRAME].get_size())
        band = cv2.imencode('.png', band)[1].tobytes()
        self.window[PREVIEW_CANVAS].update(data=band)

    def capture_image(self, values):
        """Start capturing image in new thread"""
        self.capture_thread = InterruptableThread(
            target=self.capture_image_thread, args=(values,))
        self.capture_thread.start()

    def move_stage(self, values):
        """Move stage to position specified in a popup"""
        e, v = self.popup("Move stage", [
            [
                sg.Text("Target position"),
                sg.Input(key="target", size=(6, 1)),
                sg.Text("mm")
            ],
            [sg.Ok(), sg.Cancel()]
        ])
        if e == "Ok":
            target = self.parse_numeric(v["target"], float, 0, 196, None)
            if target is None:
                logging.error("Invalid input - should be float between 0.0 and 196.0")
            else:
                self.capture_thread = InterruptableThread(
                    target=self.move_stage_thread, args=(values, target))
                self.capture_thread.start()

    def move_stage_thread(self, values, target):
        """Move stage to target specified in mm (uses capture_thread field)"""
        try:
            if not self.setup_stage(values):
                return
            logging.info(f"Moving stage to {target} mm")
            self.window[CAPTURE_IMAGE_BTN].update(disabled=True)
            self.window[STOP_CAPTURE_BTN].update(disabled=False)
            self.window[RESET_STAGE_BTN].update(disabled=True)
            self.window[MOVE_STAGE_BTN].update(disabled=True)
            self.stage.move_to(target, block=True)
        except Exception as e:
            logging.exception(f"Unable to move stage: {e}")
        finally:
            self.window.write_event_value(CAPTURE_THREAD_DONE, '')

    def reset_stage(self, values):
        """Start resetting stage in new thread"""
        self.capture_thread = InterruptableThread(
            target=self.reset_stage_thread, args=(values,))
        self.capture_thread.start()

    def reset_stage_thread(self, values):
        """Reset stage to minimum (uses capture_thread field)"""
        try:
            if not self.setup_stage(values):
                return
            logging.info("Resetting stage")
            self.window[CAPTURE_IMAGE_BTN].update(disabled=True)
            self.window[STOP_CAPTURE_BTN].update(disabled=False)
            self.window[RESET_STAGE_BTN].update(disabled=True)
            self.window[MOVE_STAGE_BTN].update(disabled=True)
            self.stage.reset()
        except Exception as e:
            logging.exception(f"Unable to reset stage: {e}")
        finally:
            self.window.write_event_value(CAPTURE_THREAD_DONE, '')

    def stop_capture(self):
        """Immediately stop stage and interrupt capture thread"""
        logging.debug("Aborting capture thread")
        self.stage.stop()
        self.window[CAPTURE_IMAGE_BTN].update(disabled=False)
        self.window[STOP_CAPTURE_BTN].update(disabled=True)
        self.window[RESET_STAGE_BTN].update(disabled=False)
        self.window[MOVE_STAGE_BTN].update(disabled=False)
        self.window[PREVIEW_BTN].update(disabled=False)
        self.window[CAPTURE_IMAGE_PROGRESS].update(0, visible=False)
        self.capture_thread.interrupt()
        self.capture_thread = None

    def capture_image_thread(self, values):
        """Capture and save an image"""
        try:
            self.setup_camera(values)
            if not self.setup_stage(values):
                return
            vals = self.parse_values(values)
            logging.info("Starting image capture")
            self.window[CAPTURE_IMAGE_BTN].update(disabled=True)
            self.window[STOP_CAPTURE_BTN].update(disabled=False)
            self.window[RESET_STAGE_BTN].update(disabled=True)
            self.window[MOVE_STAGE_BTN].update(disabled=True)
            self.window[PREVIEW_BTN].update(disabled=True)
            self.window[CAPTURE_IMAGE_PROGRESS].update(0, visible=True)
            acq_time = datetime.now()
            fields = {
                "model": self.camera.model_name,
                "date": acq_time.strftime("%Y-%m-%d"),
                "time": acq_time.strftime("%H:%M:%S"),
                "exp": self.camera.exp / 1000,
                "bin": self.camera.binning,
                "gain": self.camera.get_actual_gain(),
                "raw_gain": self.camera.raw_gain,
                "mode": "12-bit" if self.camera.mode_12bit else "8-bit",
                "start": vals['ranges'][0],
                "stop": vals['ranges'][1],
                "travel": abs(vals['ranges'][0] - vals['ranges'][1]),
                "vel": vals['velocity'],
                "version": __version__,
                "n": 0
            }
            try:
                file_name = template_to_file_name(
                    values[OUTPUT_FOLDER], values[SAVE_FILE], fields, '.hdr')
                description = values[IMAGE_DESCRIPTION_INPUT].format(**fields)
                description = description.strip()
            except KeyError as e:
                fs = ", ".join(fields.keys())
                msg = f"{{{e}}} is not a valid field name (choose from {fs})"
                raise ValueError(msg)
            logging.debug(f"Capturing image with file_name='{file_name}' and description='{description}'")
            [img, md] = self.camera.capture_save(
                file_name, self.stage, vals['ranges'], vals['velocity'],
                flip=vals['flip'], verbose=True, description=description,
                progress_callback=self.capture_image_progress_callback)
            self.show_captured_preview(img / self.camera.ref_scale_factor,
                                       md['wavelength'])
        except Exception as e:
            logging.exception(f"Unable to capture image: {e}")
        finally:
            self.window.write_event_value(CAPTURE_THREAD_DONE, '')

    def capture_image_progress_callback(self, progress):
        """Update image capture progress bar"""
        self.window.write_event_value(CAPTURE_THREAD_PROGRESS, progress)

    def display_help(self):
        """Display help message in popup"""
        self.popup(
            "Help",
            [[sg.Column(
                [[sg.Multiline(
                    default_text=HELP_TEXT,
                    disabled=True,
                    expand_x=True,
                    expand_y=True,
                    size=(80, 20))],
                 [sg.Ok()]],
                element_justification="center",
                expand_x=True,
                expand_y=True
            )]],
            resizable=True
        )

    def display_about(self):
        """Display about message in popup"""
        self.popup(
            "About",
            [[sg.Column(
                [[sg.Text(CREDITS, justification="center", pad=(20, 20))],
                 [sg.Ok()]],
                element_justification="center"
            )]]
        )

    def popup(self, title, layout, **kwargs):
        """Utility function to display a popup centered to the main window"""
        logging.debug(f"Opening '{title}' popup dialog")
        popup = sg.Window(
            title,
            layout,
            keep_on_top=True,
            modal=True,
            alpha_channel=0,
            finalize=True,
            **kwargs
        )
        wx, wy = self.window.current_location()
        ww, wh = self.window.size
        pw, ph = popup.size
        popup.move(wx + ww//2 - pw//2, wy + wh//2 - ph//2)
        popup.set_alpha(1)
        e, v = popup.read(close=True)
        logging.debug(f"Closing popup dialog with event {e}")
        return e, v

    def confirm_popup(self, title, text):
        """Utility function to display ok/cancel popup"""
        event, _ = self.popup(
            title,
            [[sg.Text(text)],
             [sg.Ok(), sg.Cancel()]]
        )
        return event == "Ok"

    def preview_panel(self):
        """Create layout for the preview panel"""
        frame = sg.Frame("", [[
            sg.Image(key=PREVIEW_CANVAS),
            sg.Image(size=(9999, 1))  # Hack to make frame expand correctly
        ]], key=PREVIEW_FRAME)
        self.xy_expand_elements.append(frame)
        return [[frame]]

    def capture_control_panel(self):
        """Create layout for the control panel"""

        label_size = (12, 1)
        label_pad = (3, 0)

        #######################################################################
        # Camera setup controls
        #######################################################################

        cameras = [CAMERA_TYPE_BASLER, CAMERA_TYPE_MOCK]

        camera_frame = sg.Frame("Camera", [
            [
                sg.Text(
                    "Model",
                    size=label_size,
                    pad=label_pad
                ),
                sg.Combo(
                    cameras,
                    default_value=cameras[0],
                    enable_events=True,
                    key=CAMERA_TYPE_SEL,
                    readonly=True
                )
            ],
            [
                sg.pin(sg.Column([[
                    sg.Text(
                        "Source file",
                        size=label_size,
                        pad=label_pad
                    ),
                    sg.Input(
                        "",
                        size=(20, 1),
                        key=CAMERA_MOCK_FILE,
                        enable_events=True
                    ),
                    get_icon_button(
                        ICON_OPEN,
                        button_type=sg.BUTTON_TYPE_BROWSE_FILE,
                        file_types=(("ENVI", "*.hdr"),),
                        initial_folder=self.default_folder,
                        tooltip="Browse...",
                        key=CAMERA_MOCK_FILE_BROWSE
                    )
                ]], key=CAMERA_MOCK_CONTROL_PANE, pad=(0, 0), visible=False))
            ],
            [
                sg.pin(sg.Column([
                    [
                        sg.Text(
                            "Exposure time",
                            size=label_size,
                            pad=label_pad
                        ),
                        sg.Input(
                            default_text="20.0",
                            size=(5, 1),
                            key=EXP_INPUT,
                            enable_events=True
                        ),
                        sg.Text("ms"),
                        sg.pin(sg.Text(
                            "0.1 to 1000.0",
                            size=(20, 1),
                            visible=False,
                            key=EXP_FDB,
                            text_color="dark red"
                        ))
                    ],
                    [
                        sg.Text(
                            "Binning",
                            size=label_size,
                            pad=label_pad
                        ),
                        sg.Combo(
                            ["1", "2", "4"],
                            default_value="1",
                            enable_events=True,
                            key=BINNING_SEL,
                            readonly=True
                        )
                    ],
                    [
                        sg.Text(
                            "Gain",
                            size=label_size,
                            pad=label_pad
                        ),
                        sg.Input(
                            default_text="100",
                            size=(5, 1),
                            key=GAIN_INPUT,
                            enable_events=True
                        ),
                        sg.Text(
                            "(3.59 dB)",
                            key=GAIN_DB_LBL,
                            size=(10, 1)
                        ),
                        sg.pin(sg.Text(
                            "0 to 500",
                            key=GAIN_FDB,
                            visible=False,
                            text_color="dark red"
                        ))
                    ]
                ], key=CAMERA_REAL_CONTROL_PANE, pad=(0, 0)))
            ],
            [
                sg.Checkbox(
                    "Reverse order of columns",
                    default=False,
                    key=REVERSE_COLUMNS_CB
                )
            ]
        ])

        #######################################################################
        # Stage setup controls
        #######################################################################

        stages = [STAGE_TYPE_TSA200, STAGE_TYPE_MOCK]
        self.ports = list_ports.comports()
        if len(self.ports) > 0:
            ports = [port_label(p) for p in self.ports]
        else:
            ports = ["No ports found"]

        stage_frame = sg.Frame("Stage", [
            [
                sg.Text(
                    "Model",
                    size=label_size,
                    pad=label_pad
                ),
                sg.Combo(
                    stages,
                    default_value=stages[0],
                    readonly=True,
                    enable_events=True,
                    key=STAGE_TYPE_SEL
                )
            ],
            [
                sg.pin(sg.Column([[
                    sg.Text(
                        "Port",
                        size=label_size,
                        pad=label_pad
                    ),
                    sg.Combo(
                        ports,
                        default_value=ports[0],
                        disabled=(len(self.ports) == 0),
                        key=STAGE_PORT_SEL,
                        size=(20, 1),
                        readonly=True
                    ),
                    get_icon_button(
                        ICON_RELOAD,
                        key=PORT_RELOAD_BTN,
                        tooltip="Reload port list"
                    )
                    # TODO: dynamically detect when port list changes?
                ]], key=STAGE_PORT_PANE, pad=(0, 0)))
            ],
            [
                sg.Text(
                    "Capture range",
                    size=label_size,
                    pad=label_pad
                ),
                sg.Input(
                    default_text="0",
                    size=(5, 1),
                    key=RANGE_START_INPUT,
                    enable_events=True
                ),
                sg.Text("to"),
                sg.Input(
                    default_text="100",
                    size=(5, 1),
                    key=RANGE_END_INPUT,
                    enable_events=True
                ),
                sg.Text("mm"),
                sg.pin(sg.Text(
                    "0.0 to 196.0",
                    key=RANGE_FDB,
                    visible=False,
                    text_color="dark red"
                ))
                # sg.Button("+", key=ADD_RANGE_FIELDS_BTN)
                # TODO: dynamically add range fields using
                # window.extend_layout()
            ],
            [
                sg.Text(
                    "Velocity",
                    size=label_size,
                    pad=label_pad
                ),
                sg.Input(
                    default_text="20",
                    size=(5, 1),
                    key=VELOCITY_INPUT,
                    enable_events=True
                ),
                sg.Text("mm/s"),
                sg.pin(sg.Text(
                    "0.01 to 50.0",
                    key=VELOCITY_FDB,
                    visible=False,
                    text_color="dark red"
                ))
            ]
        ])

        #######################################################################
        # Live preview controls
        #######################################################################

        preview_frame = sg.Frame("Live preview", [
            [
                sg.Checkbox(
                    "Waterfall",
                    size=(16, 1),
                    key=PREVIEW_WATERFALL_CB,
                    enable_events=True
                ),
                sg.Checkbox(
                    "Pseudocolour",
                    key=PREVIEW_PSEUDOCOLOUR_CB,
                    enable_events=True,
                    disabled=True
                )
            ],
            [
                sg.pin(sg.Column([[
                    sg.Text(
                        "Band",
                        size=(6, 1),
                        pad=label_pad
                    ),
                    get_band_slider(PREVIEW_SINGLE_BAND_SLIDER),
                    sg.Text(
                        "--",
                        size=(15, 1),
                        key=PREVIEW_SINGLE_BAND_NM
                    )
                ]], key=PREVIEW_SINGLE_BAND_PANE, pad=(0, 0), visible=False))
            ],
            [
                sg.pin(sg.Column([
                    [
                        sg.Text(
                            "Red",
                            size=(6, 1),
                            pad=label_pad
                        ),
                        get_band_slider(PREVIEW_RED_BAND_SLIDER),
                        sg.Text(
                            "--",
                            size=(15, 1),
                            key=PREVIEW_RED_BAND_NM
                        )
                    ],
                    [
                        sg.Text(
                            "Green",
                            size=(6, 1),
                            pad=label_pad
                        ),
                        get_band_slider(PREVIEW_GREEN_BAND_SLIDER),
                        sg.Text(
                            "--",
                            size=(15, 1),
                            key=PREVIEW_GREEN_BAND_NM
                        )
                    ],
                    [
                        sg.Text(
                            "Blue",
                            size=(6, 1),
                            pad=label_pad
                        ),
                        get_band_slider(PREVIEW_BLUE_BAND_SLIDER),
                        sg.Text(
                            "--",
                            size=(15, 1),
                            key=PREVIEW_BLUE_BAND_NM
                        )
                    ]
                ], key=PREVIEW_RGB_BAND_PANE, pad=(0, 0), visible=False))
            ],
            [
                sg.Checkbox(
                    "Highlight saturated",
                    size=(16, 1),
                    key=PREVIEW_HIGHLIGHT_CB
                ),
                sg.Checkbox(
                    "Interpolation",
                    key=PREVIEW_INTERP_CB,
                    enable_events=True
                )
            ],
            [
                get_icon_button(
                    ICON_PLAY,
                    key=PREVIEW_BTN,
                    tooltip="Toggle preview"
                ),
                get_icon_button(
                    ICON_ROT_LEFT,
                    key=PREVIEW_ROTLEFT_BTN,
                    tooltip="Rotate preview left",
                    disabled=True
                ),
                get_icon_button(
                    ICON_ROT_RIGHT,
                    key=PREVIEW_ROTRIGHT_BTN,
                    tooltip="Rotate preview right",
                    disabled=True
                ),
                get_icon_button(
                    ICON_DELETE,
                    key=PREVIEW_CLEAR_BTN,
                    tooltip="Clear preview",
                    disabled=True
                )
            ]
        ])

        #######################################################################
        # Output format controls
        #######################################################################

        formats = [FORMAT_ENVI]
        file_names = ["{date}_{n}", "{date}_dark_ref"]
        description_multiline = sg.Multiline(
            size=(30, 3),
            key=IMAGE_DESCRIPTION_INPUT
        )
        output_frame = sg.Frame("Capture and save", [
            [
                sg.Text(
                    "Format",
                    size=label_size,
                    pad=label_pad
                ),
                sg.Combo(
                    formats,
                    default_value=formats[0],
                    key=OUTPUT_FORMAT_SEL,
                    readonly=True
                )
            ],
            [
                sg.Text(
                    "Folder",
                    size=label_size,
                    pad=label_pad
                ),
                sg.Input(
                    self.default_folder,
                    size=(20, 1),
                    key=OUTPUT_FOLDER,
                    enable_events=True
                ),
                get_icon_button(
                    ICON_OPEN,
                    button_type=sg.BUTTON_TYPE_BROWSE_FOLDER,
                    initial_folder=self.default_folder,
                    tooltip="Browse...",
                    key=OUTPUT_FOLDER_BROWSE
                )
            ],
            [
                sg.Text(
                    "File name",
                    size=label_size,
                    pad=label_pad
                ),
                sg.Combo(
                    file_names,
                    default_value=file_names[0],
                    key=SAVE_FILE
                ),
                sg.Text(".hdr")
            ],
            [
                sg.Text(
                    "Description",
                    size=label_size,
                    pad=label_pad
                ),
                description_multiline
            ],
            [
                get_icon_button(
                    ICON_CAMERA,
                    key=CAPTURE_IMAGE_BTN,
                    tooltip="Capture image and save"
                ),
                get_icon_button(
                    ICON_RESET,
                    key=RESET_STAGE_BTN,
                    tooltip="Reset stage to minimum"
                ),
                get_icon_button(
                    ICON_MOVE,
                    key=MOVE_STAGE_BTN,
                    tooltip="Move stage to target position..."
                ),
                get_icon_button(
                    ICON_STOP,
                    key=STOP_CAPTURE_BTN,
                    tooltip="Stop image capture",
                    disabled=True
                ),
                sg.pin(sg.ProgressBar(
                    1.0,
                    size=(20, 15),
                    pad=(5, 0),
                    visible=False,
                    key=CAPTURE_IMAGE_PROGRESS
                ))
            ]
        ])

        # Elements that need to be expanded to fill horizontal space:
        self.x_expand_elements.extend(
            (camera_frame, stage_frame, output_frame, preview_frame,
             description_multiline)
        )
        return [[camera_frame], [stage_frame], [preview_frame], [output_frame]]


class Viewer():
    """Window for viewing existing HSI files"""

    def __init__(self, root_window, file_path, size):
        self.root_window = root_window
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        self.img = envi.open(file_path)
        self.xy_expand_elements = []
        self.x_expand_elements = []
        self.pseudocolour = True
        self.single_band = self.img.nbands // 2
        self.wl = self.img.bands.centers
        if self.wl:
            rgb = get_rgb_bands(self.wl)
        else:
            logging.warning(f"No valid wavelength data for {self.file_name}")
            inc = self.img.nbands // 4
            rgb = (3 * inc, 2 * inc, inc)
        self.red_band = rgb[0]
        self.green_band = rgb[1]
        self.blue_band = rgb[2]
        self.interpolation = False
        self.rotation = 0
        content = [
            [
                sg.Column(
                    self.viewer_control_panel(),
                    expand_y=True,
                    expand_x=True
                ),
                sg.Column(
                    self.view_panel(),
                    expand_y=True,
                    expand_x=True
                )
            ]
        ]
        self.window = sg.Window(
            title=f"PyHSI - {self.file_name}",
            layout=content,
            resizable=True,
            size=size,
            finalize=True
        )
        self.window.bind("<Control-q>", sg.WINDOW_CLOSE_ATTEMPTED_EVENT)
        self.window.bind("<Control-o>", MENU_OPEN_FILE)
        self.window.bind("<F1>", MENU_HELP)

        for e in self.xy_expand_elements:
            e.expand(expand_x=True, expand_y=True)
        for e in self.x_expand_elements:
            e.expand(expand_x=True, expand_y=False, expand_row=False)

        _, values = self.window.read(timeout=0)
        self.update_sliders(values)

    def handle_event(self, event, values):
        logging.debug(f"Handling {event} event in Viewer({self.file_name})")
        if event == MENU_OPEN_FILE:
            self.root_window.open_file()
        elif event == MENU_HELP:
            self.root_window.display_help()
        elif event == INTERP_CB:
            self.interpolation = values[INTERP_CB]
            self.update_view()
        elif event == PSEUDOCOLOUR_CB:
            self.set_pseudocolour(values[PSEUDOCOLOUR_CB])
        elif event in (SINGLE_BAND_SLIDER, RED_BAND_SLIDER, GREEN_BAND_SLIDER, BLUE_BAND_SLIDER):
            self.update_sliders(values)
        elif event == ROTLEFT_BTN:
            self.rotation = (self.rotation + 1) % 4
            self.update_view()
        elif event == ROTRIGHT_BTN:
            self.rotation = (self.rotation - 1) % 4
            self.update_view()
        elif event in (MENU_QUIT, sg.WINDOW_CLOSE_ATTEMPTED_EVENT, sg.WIN_CLOSED):
            self.exit()
        elif event is None:
            # With multiple windows, close attempt causes None event, see
            # https://github.com/PySimpleGUI/PySimpleGUI/issues/3771
            logging.debug("Treating None event as sg.WINDOW_CLOSE_ATTEMPTED_EVENT")
            self.exit()

    def exit(self):
        """Close the viewer window"""
        logging.debug(f"Closing viewer window ({self.file_name})")
        self.root_window.viewers.pop(self.window)
        self.window.close()

    def update_sliders(self, values):
        """Update band slider values"""
        self.single_band = round(values[SINGLE_BAND_SLIDER])
        self.red_band = round(values[RED_BAND_SLIDER])
        self.green_band = round(values[GREEN_BAND_SLIDER])
        self.blue_band = round(values[BLUE_BAND_SLIDER])
        if self.wl:
            s_nm = self.wl[self.single_band]
            r_nm = self.wl[self.red_band]
            g_nm = self.wl[self.green_band]
            b_nm = self.wl[self.blue_band]
            self.window[SINGLE_BAND_NM].update(f"{self.single_band} ({s_nm:.1f} nm)")
            self.window[RED_BAND_NM].update(f"{self.red_band} ({r_nm:.1f} nm)")
            self.window[GREEN_BAND_NM].update(f"{self.green_band} ({g_nm:.1f} nm)")
            self.window[BLUE_BAND_NM].update(f"{self.blue_band} ({b_nm:.1f} nm)")
        else:
            self.window[SINGLE_BAND_NM].update(f"{self.single_band}")
            self.window[RED_BAND_NM].update(f"{self.red_band}")
            self.window[GREEN_BAND_NM].update(f"{self.green_band}")
            self.window[BLUE_BAND_NM].update(f"{self.blue_band}")
        self.update_view()

    def set_pseudocolour(self, pc):
        """Turn pseudocolour on or off"""
        if pc != self.pseudocolour:
            self.pseudocolour = pc
            self.window[RGB_BAND_PANE].update(visible=pc)
            self.window[SINGLE_BAND_PANE].update(visible=not pc)
            self.update_view()

    def update_view(self):
        """Actually display the image"""
        if self.pseudocolour:
            bgr = (self.blue_band, self.green_band, self.red_band)
            img = self.img.read_bands(bgr)
        else:
            img = self.img.read_band(self.single_band)
        img = np.asarray(img * 255, dtype="uint8")
        img = np.rot90(img, k=self.rotation)
        img = resize_img_to_area(img, self.window[VIEW_FRAME].get_size(), interpolation=self.interpolation)
        img = cv2.imencode('.png', img)[1].tobytes()
        self.window[VIEW_CANVAS].update(data=img)

    def viewer_control_panel(self):
        """View controls"""
        label_pad = (3, 0)
        slider_range = (0, self.img.nbands - 1)
        control_frame = sg.Frame("View controls", [
            [
                sg.Checkbox(
                    "Pseudocolour",
                    key=PSEUDOCOLOUR_CB,
                    enable_events=True,
                    default=self.pseudocolour
                )
            ],
            [
                sg.pin(sg.Column([[
                    sg.Text(
                        "Band",
                        size=(6, 1),
                        pad=label_pad
                    ),
                    get_band_slider(SINGLE_BAND_SLIDER,
                                    range=slider_range,
                                    default_value=self.single_band),
                    sg.Text(
                        "--",
                        size=(15, 1),
                        key=SINGLE_BAND_NM
                    )
                ]], key=SINGLE_BAND_PANE, pad=(0, 0), visible=False))
            ],
            [
                sg.pin(sg.Column([
                    [
                        sg.Text(
                            "Red",
                            size=(6, 1),
                            pad=label_pad
                        ),
                        get_band_slider(RED_BAND_SLIDER,
                                        range=slider_range,
                                        default_value=self.red_band),
                        sg.Text(
                            "--",
                            size=(15, 1),
                            key=RED_BAND_NM
                        )
                    ],
                    [
                        sg.Text(
                            "Green",
                            size=(6, 1),
                            pad=label_pad
                        ),
                        get_band_slider(GREEN_BAND_SLIDER,
                                        range=slider_range,
                                        default_value=self.green_band),
                        sg.Text(
                            "--",
                            size=(15, 1),
                            key=GREEN_BAND_NM
                        )
                    ],
                    [
                        sg.Text(
                            "Blue",
                            size=(6, 1),
                            pad=label_pad
                        ),
                        get_band_slider(BLUE_BAND_SLIDER,
                                        range=slider_range,
                                        default_value=self.blue_band),
                        sg.Text(
                            "--",
                            size=(15, 1),
                            key=BLUE_BAND_NM
                        )
                    ]
                ], key=RGB_BAND_PANE, pad=(0, 0)))
            ],
            [
                sg.Checkbox(
                    "Interpolation",
                    key=INTERP_CB,
                    enable_events=True,
                    default=self.interpolation
                )
            ],
            [
                get_icon_button(
                    ICON_ROT_LEFT,
                    key=ROTLEFT_BTN,
                    tooltip="Rotate view left"
                ),
                get_icon_button(
                    ICON_ROT_RIGHT,
                    key=ROTRIGHT_BTN,
                    tooltip="Rotate view right"
                )
            ]
        ])
        return [[control_frame]]

    def view_panel(self):
        """Create layout for the view panel"""
        frame = sg.Frame("", [[
            sg.Image(key=VIEW_CANVAS),
            sg.Image(size=(9999, 1))  # Hack to make frame expand correctly
        ]], key=VIEW_FRAME)
        self.xy_expand_elements.append(frame)
        return [[frame]]
