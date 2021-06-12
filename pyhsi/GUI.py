from datetime import datetime
import os
import sys

import cv2
import numpy as np
import PySimpleGUI as sg
import serial
from serial.tools import list_ports
from spectral.io import envi
from spectral.io.spyfile import FileNotFoundError
import tkinter as tk

from . import __version__
from .cameras import BaslerCamera, MockCamera
from .stages import TSA200, MockStage
from .utils import get_rgb_bands, add_wavelength_labels

DEBUG = 0
INFO = 1
WARN = 2
ERROR = 3
LOG_COLOURS = {
    DEBUG: "grey",
    INFO: "black",
    WARN: "orange",
    ERROR: "red"
}
INIT_EVENT = "Init"
MENU_QUIT = "Quit"

CAMERA_TYPE_SEL = "CameraSelect"
CAMERA_TYPE_BASLER = "Basler VNIR"
CAMERA_TYPE_MOCK = "Mock camera"
CAMERA_MOCK_FILE = "CameraMockFileName"
CAMERA_MOCK_CONTROL_PANE = "CameraMockControlPanel"
CAMERA_REAL_CONTROL_PANE = "CameraRealControlPanel"
STAGE_TYPE_SEL = "StageSelect"
STAGE_TYPE_MOCK = "Mock stage"
STAGE_TYPE_TSA200 = "Zolix TSA200"
STAGE_PORT_SEL = "StagePortSelect"
PORT_RELOAD_BTN = "PortRefresh"
STAGE_PORT_PANE = "PortRefreshPanel"
EXP_INPUT = "ExposureInput"
EXP_FDB = "ExposureFeedback"
BINNING_SEL = "BinningInput"
GAIN_INPUT = "GainInput"
GAIN_DB_LBL = "GainDBLabel"
GAIN_FDB = "GainFeedback"
RANGE_START_INPUT = "RangeStartInput"
RANGE_END_INPUT = "RangeEndInput"
RANGE_FDB = "RangeFeedback"
ADD_RANGE_FIELDS_BTN = "AddRangeFields"
VELOCITY_INPUT = "VelocityInput"
VELOCITY_FDB = "VelocityFeedback"
OUTPUT_FORMAT_SEL = "OutputFormatSelect"
FORMAT_ENVI = "ENVI"
REVERSE_COLUMNS_CB = "FlipOutputCheckbox"
OUTPUT_FOLDER = "OutputFolder"
SAVE_FILE = "SaveFileName"
CAPTURE_IMAGE_BTN = "CaptureImage"
PREVIEW_BTN = "CameraPreview"
PREVIEW_CLEAR_BTN = "PreviewClearButton"
PREVIEW_WATERFALL_CB = "PreviewWaterfall"
PREVIEW_HIGHLIGHT_CB = "PreviewHighlight"
PREVIEW_INTERP_CB = "PreviewInterpolation"
PREVIEW_ROTLEFT_BTN = "PreviewRotationLeft"
PREVIEW_ROTRIGHT_BTN = "PreviewRotationRight"
PREVIEW_PSEUDOCOLOUR_CB = "PreviewPseudocolour"
PREVIEW_SINGLE_BAND_SLIDER = "PreviewSingleBandSlider"
PREVIEW_SINGLE_BAND_NM = "PreviewSingleBandNm"
PREVIEW_RED_BAND_SLIDER = "PreviewRedBandSlider"
PREVIEW_RED_BAND_NM = "PreviewRedBandNm"
PREVIEW_GREEN_BAND_SLIDER = "PreviewGreenBandSlider"
PREVIEW_GREEN_BAND_NM = "PreviewGreenBandNm"
PREVIEW_BLUE_BAND_SLIDER = "PreviewBlueBandSlider"
PREVIEW_BLUE_BAND_NM = "PreviewBlueBandNm"
PREVIEW_SINGLE_BAND_PANE = "PreviewSingleBandPanel"
PREVIEW_RGB_BAND_PANE = "PreviewRgbBandPanel"
CAPTURE_IMAGE_PROGRESS = "CaptureImageProgress"
CONSOLE_OUTPUT = "ConsoleOutput"
PREVIEW_CANVAS = "PreviewCanvas"

ICON_DIR = "icons"
ICON_APP = "pyhsi"
ICON_RELOAD = "reload"
ICON_OPEN = "open"
ICON_PLAY = "play"
ICON_PAUSE = "pause"
ICON_ROT_LEFT = "rotate-left"
ICON_ROT_RIGHT = "rotate-right"
ICON_DELETE = "delete"
ICON_CAMERA = "camera"


def get_band_slider(key):
    return sg.Slider(
        range=(1, 100),
        default_value=50,
        orientation="h",
        disable_number_display=True,
        key=key,
        enable_events=True
    )


def get_screen_size():
    root = tk.Tk()
    root.update_idletasks()
    root.attributes('-fullscreen', True)
    root.state('iconic')
    geometry = root.winfo_geometry()
    root.destroy()
    w, geometry = geometry.split('x')
    h = geometry.split('+')[0]
    return (int(w), int(h))


def get_icon_button(icon, key=None, button_type=None, file_types=None,
                    initial_folder=None, disabled=False, tooltip=None):
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
    if port.product:
        return f"{port.device}: {port.product}"
    return str(port.device)


class PyHSI:
    def __init__(self, debug=False):
        self.debug = debug
        self.default_folder = os.environ['HOME']
        sg.set_options(font=("latin modern sans", 14))
        self.xy_expand_elements = []
        self.x_expand_elements = []
        screen_size = get_screen_size()
        self.live_preview_active = False
        self.live_preview_rotation = 1
        self.waterfall_frame = None
        self.live_preview_frame = None
        self.view_canvas_size = (round(screen_size[0] * 0.6),
                                 round(screen_size[1] * 0.7))
        menubar = sg.Menu([["&File", [MENU_QUIT]]])
        content = [
            [
                sg.Column(self.capture_control_panel(), expand_y=True),
                sg.Column(self.preview_panel(), expand_y=True)
            ]
        ]
        console = sg.Multiline(size=(80, 5), key=CONSOLE_OUTPUT, disabled=True)
        self.x_expand_elements.append(console)
        self.camera = None
        self.camera_type = None
        self.stage = None
        self.stage_type = None
        self.viewer_file = None
        self.viewer_img = None
        icon_ext = ".ico" if sg.running_windows() else ".png"
        icon_path = os.path.join(ICON_DIR, ICON_APP + icon_ext)
        sg.set_global_icon(icon_path)
        self.window = sg.Window(
            title="PyHSI",
            layout=[[menubar], [content], [console]],
            enable_close_attempted_event=True,
            resizable=True,
            finalize=True
        )
        for e in self.xy_expand_elements:
            e.expand(expand_x=True, expand_y=True)
        for e in self.x_expand_elements:
            e.expand(expand_x=True, expand_y=False, expand_row=False)
        sg.cprint_set_output_destination(self.window, CONSOLE_OUTPUT)
        self.log(f"Screen size: {screen_size}", level=DEBUG)
        self.log(f"Canvas size: {self.view_canvas_size}", level=DEBUG)

    def log(self, message, level=INFO):
        if self.debug or level > DEBUG:
            ts = datetime.now().strftime("%H:%M:%S")
            ls = ["DEBUG", "INFO", "WARN", "ERROR"][level]
            entry = f"[{ts}] {ls}: {message}"
            if self.window[CONSOLE_OUTPUT].get().strip():
                cpentry = '\n' + entry
            else:
                cpentry = entry
            sg.cprint(cpentry, text_color=LOG_COLOURS[level], end='')
            if self.debug:
                print(entry)

    def capture_control_panel(self):
        label_size = (12, 1)
        label_pad = (5, 8)
        cameras = [CAMERA_TYPE_BASLER, CAMERA_TYPE_MOCK]
        stages = [STAGE_TYPE_TSA200, STAGE_TYPE_MOCK]
        self.ports = list_ports.comports()
        if len(self.ports) > 0:
            ports = [port_label(p) for p in self.ports]
        else:
            ports = ["No ports found"]
        camera_frame = sg.Frame("Camera", [
            [
                sg.Text("Model", size=label_size, pad=label_pad),
                sg.Combo(cameras, default_value=cameras[0], enable_events=True,
                         key=CAMERA_TYPE_SEL, readonly=True)
            ],
            [
                sg.pin(sg.Column([[
                    sg.Text("Source file", size=label_size, pad=label_pad),
                    sg.Input("", size=(20, 1), key=CAMERA_MOCK_FILE,
                             enable_events=True),
                    get_icon_button(ICON_OPEN, button_type=sg.BUTTON_TYPE_BROWSE_FILE,
                                    file_types=(("ENVI", "*.hdr"),), initial_folder=self.default_folder, tooltip="Browse")
                ]], key=CAMERA_MOCK_CONTROL_PANE, pad=(0, 0), visible=False))
            ],
            [
                sg.pin(sg.Column([
                    [
                        sg.Text("Exposure time", size=label_size, pad=label_pad),
                        sg.Input(default_text="20.0", size=(5, 1),
                                 key=EXP_INPUT, enable_events=True),
                        sg.Text("ms"),
                        sg.pin(sg.Text("0.1 to 1000.0", size=(20, 1), visible=False,
                                       key=EXP_FDB, text_color="dark red"))
                    ],
                    [
                        sg.Text("Binning", size=label_size, pad=label_pad),
                        sg.Combo(["1", "2", "4"], default_value="2", enable_events=True,
                                 key=BINNING_SEL, readonly=True)
                    ],
                    [
                        sg.Text("Gain", size=label_size, pad=label_pad),
                        sg.Input(default_text="100", size=(5, 1),
                                 key=GAIN_INPUT, enable_events=True),
                        sg.Text("(3.59 dB)", key=GAIN_DB_LBL, size=(10, 1)),
                        sg.pin(sg.Text("0 to 500", key=GAIN_FDB,
                                       visible=False, text_color="dark red"))
                    ]
                ], key=CAMERA_REAL_CONTROL_PANE, pad=(0, 0)))
            ],
            [
                sg.Checkbox("Reverse order of columns", default=False,
                            key=REVERSE_COLUMNS_CB)
            ]
        ])
        stage_frame = sg.Frame("Stage", [
            [
                sg.Text("Model", size=label_size, pad=label_pad),
                sg.Combo(stages, default_value=stages[0], readonly=True,
                         enable_events=True, key=STAGE_TYPE_SEL)
            ],
            [
                sg.pin(sg.Column([[
                    sg.Text("Port", size=label_size, pad=label_pad),
                    sg.Combo(ports, default_value=ports[0], disabled=(
                        len(self.ports) == 0), key=STAGE_PORT_SEL, readonly=True),
                    get_icon_button(ICON_RELOAD, key=PORT_RELOAD_BTN, tooltip="Reload port list")
                    # TODO: dynamically detect when port list changes?
                ]], key=STAGE_PORT_PANE, pad=(0, 0)))
            ],
            [
                sg.Text("Capture range", size=label_size, pad=label_pad),
                sg.Input(default_text="0", size=(5, 1),
                         key=RANGE_START_INPUT, enable_events=True),
                sg.Text("to"),
                sg.Input(default_text="100", size=(5, 1),
                         key=RANGE_END_INPUT, enable_events=True),
                sg.Text("mm"),
                sg.pin(sg.Text("0.0 to 196.0", key=RANGE_FDB,
                               visible=False, text_color="dark red"))
                # sg.Button("+", key=ADD_RANGE_FIELDS_BTN)
                # TODO: dynamically add range fields using
                # window.extend_layout()
            ],
            [
                sg.Text("Velocity", size=label_size, pad=label_pad),
                sg.Input(default_text="20", size=(5, 1),
                         key=VELOCITY_INPUT, enable_events=True),
                sg.Text("mm/s"),
                sg.pin(sg.Text("0.01 to 50.0", key=VELOCITY_FDB,
                               visible=False, text_color="dark red"))
            ]
        ])
        preview_frame = sg.Frame("Live preview", [
            [
                sg.Checkbox("Waterfall", size=(16, 1), key=PREVIEW_WATERFALL_CB, enable_events=True),
                sg.Checkbox("Pseudocolour", key=PREVIEW_PSEUDOCOLOUR_CB, enable_events=True, disabled=True)
            ],
            [
                sg.pin(sg.Column([[
                    sg.Text("Band", size=(6, 1), pad=label_pad),
                    get_band_slider(PREVIEW_SINGLE_BAND_SLIDER),
                    sg.Text("--", size=(15, 1), key=PREVIEW_SINGLE_BAND_NM)
                ]], key=PREVIEW_SINGLE_BAND_PANE, pad=(0, 0), visible=False))
            ],
            [
                sg.pin(sg.Column([
                    [
                        sg.Text("Red", size=(6, 1), pad=label_pad),
                        get_band_slider(PREVIEW_RED_BAND_SLIDER),
                        sg.Text("--", size=(15, 1), key=PREVIEW_RED_BAND_NM)
                    ],
                    [
                        sg.Text("Green", size=(6, 1), pad=label_pad),
                        get_band_slider(PREVIEW_GREEN_BAND_SLIDER),
                        sg.Text("--", size=(15, 1), key=PREVIEW_GREEN_BAND_NM)
                    ],
                    [
                        sg.Text("Blue", size=(6, 1), pad=label_pad),
                        get_band_slider(PREVIEW_BLUE_BAND_SLIDER),
                        sg.Text("--", size=(15, 1), key=PREVIEW_BLUE_BAND_NM)
                    ]
                ], key=PREVIEW_RGB_BAND_PANE, pad=(0, 0), visible=False))
            ],
            [
                sg.Checkbox("Highlight saturated", size=(16, 1), key=PREVIEW_HIGHLIGHT_CB),
                sg.Checkbox("Interpolation", key=PREVIEW_INTERP_CB, enable_events=True)
            ],
            [
                get_icon_button(ICON_PLAY, key=PREVIEW_BTN, tooltip="Toggle preview"),
                get_icon_button(ICON_ROT_LEFT, key=PREVIEW_ROTLEFT_BTN, tooltip="Rotate preview left"),
                get_icon_button(ICON_ROT_RIGHT, key=PREVIEW_ROTRIGHT_BTN, tooltip="Rotate preview right"),
                get_icon_button(ICON_DELETE, key=PREVIEW_CLEAR_BTN, tooltip="Clear preview", disabled=True)
            ]
        ])
        formats = [FORMAT_ENVI]
        file_names = ["{date}_{n}", "{date}_dark_ref"]
        output_frame = sg.Frame("Output", [
            [
                sg.Text("Format", size=label_size, pad=label_pad),
                sg.Combo(formats, default_value=formats[0], key=OUTPUT_FORMAT_SEL, readonly=True)
            ],
            [
                sg.Text("Folder", size=label_size, pad=label_pad),
                sg.Input(self.default_folder, size=(20, 1), key=OUTPUT_FOLDER, enable_events=True),
                get_icon_button(ICON_OPEN, button_type=sg.BUTTON_TYPE_BROWSE_FOLDER, initial_folder=self.default_folder, tooltip="Browse")
            ],
            [
                sg.Text("File name", size=label_size, pad=label_pad),
                sg.Combo(file_names, default_value=file_names[0], key=SAVE_FILE)
            ],
            [
                get_icon_button(ICON_CAMERA, key=CAPTURE_IMAGE_BTN, tooltip="Capture image and save"),
                sg.ProgressBar(1.0, size=(30, 50), visible=False, key=CAPTURE_IMAGE_PROGRESS)
            ]
        ])
        self.x_expand_elements.extend(
            (camera_frame, stage_frame, output_frame, preview_frame))
        return [[camera_frame], [stage_frame], [preview_frame], [output_frame]]

    def preview_panel(self):
        frame = sg.Frame("Preview", [[
            sg.Image(size=self.view_canvas_size, key=PREVIEW_CANVAS)
        ]])
        self.xy_expand_elements.append(frame)
        return [[frame]]

    def validate(self, field):
        value = self.window[field].get()
        if field == EXP_INPUT:
            self.parse_numeric(value, float, 0.1, 1000, EXP_FDB)
        elif field == GAIN_INPUT:
            self.parse_numeric(value, int, 0, 500, GAIN_FDB)
        elif field == VELOCITY_INPUT:
            self.parse_numeric(value, float, 0.01, 50, VELOCITY_FDB)
        elif field == RANGE_START_INPUT or field == RANGE_END_INPUT:
            self.parse_numeric(value, float, 0, 196, RANGE_FDB)

    def refresh_stage_ports(self):
        self.ports = list_ports.comports()
        self.log(f"Found {len(self.ports)} available serial ports.")
        ports = self.ports if len(self.ports) > 0 else ["No ports found"]
        self.window[STAGE_PORT_SEL].update(
            values=ports,
            value=ports[0],
            disabled=(len(self.ports) == 0))

    def update_gain_label(self, values):
        gain = self.parse_numeric(values[GAIN_INPUT], int, 0, 500, GAIN_FDB)
        if gain is None:
            return
        gain_db = gain * self.camera.raw_gain_factor
        self.window[GAIN_DB_LBL].update(value=f"({gain_db:.2f} dB)")

    def update_preview_slider_labels(self, values):
        s_b = round(values[PREVIEW_SINGLE_BAND_SLIDER])
        r_b = round(values[PREVIEW_RED_BAND_SLIDER])
        g_b = round(values[PREVIEW_GREEN_BAND_SLIDER])
        b_b = round(values[PREVIEW_BLUE_BAND_SLIDER])
        if self.camera.wl:
            s_nm = self.camera.wl[s_b - 1]
            r_nm = self.camera.wl[r_b - 1]
            g_nm = self.camera.wl[g_b - 1]
            b_nm = self.camera.wl[b_b - 1]
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
        if self.camera.wl:
            n = len(self.camera.wl)
            rgb = get_rgb_bands(self.camera.wl)
            r = rgb[0] - 1
            g = rgb[1] - 1
            b = rgb[2] - 1
        else:
            n = 100
            r = 75
            g = 50
            b = 25
        s = n // 2
        self.window[PREVIEW_SINGLE_BAND_SLIDER].update(
            range=(1, n), disabled=False)
        self.window[PREVIEW_SINGLE_BAND_SLIDER].update(value=s)
        values[PREVIEW_SINGLE_BAND_SLIDER] = s
        self.window[PREVIEW_RED_BAND_SLIDER].update(
            range=(1, n), disabled=False)
        self.window[PREVIEW_RED_BAND_SLIDER].update(value=r)
        values[PREVIEW_RED_BAND_SLIDER] = r
        self.window[PREVIEW_GREEN_BAND_SLIDER].update(
            range=(1, n), disabled=False)
        self.window[PREVIEW_GREEN_BAND_SLIDER].update(value=g)
        values[PREVIEW_GREEN_BAND_SLIDER] = g
        self.window[PREVIEW_BLUE_BAND_SLIDER].update(
            range=(1, n), disabled=False)
        self.window[PREVIEW_BLUE_BAND_SLIDER].update(value=b)
        values[PREVIEW_BLUE_BAND_SLIDER] = b
        self.update_preview_slider_labels(values)

    def set_camera_type(self, values):
        if values[CAMERA_TYPE_SEL] == CAMERA_TYPE_MOCK:
            self.window[CAMERA_MOCK_CONTROL_PANE].update(visible=True)
            self.window[CAMERA_REAL_CONTROL_PANE].update(visible=False)
        else:
            self.window[CAMERA_MOCK_CONTROL_PANE].update(visible=False)
            self.window[CAMERA_REAL_CONTROL_PANE].update(visible=True)
        self.setup_camera(values)
        self.update_gain_label(values)
        self.update_preview_slider_ranges(values)

    def handle_event(self, event, values):
        self.log(f"Handling {event} event", level=DEBUG)
        if event == INIT_EVENT:
            self.log(f"Starting PyHSI v{__version__}")
            self.set_camera_type(values)
        elif event in (EXP_INPUT, VELOCITY_INPUT,
                       RANGE_START_INPUT, RANGE_END_INPUT):
            self.validate(event)
        elif event == CAMERA_TYPE_SEL:
            self.set_camera_type(values)
        elif event == GAIN_INPUT:
            self.update_gain_label(values)
        elif event == BINNING_SEL:
            self.camera.set_binning(int(values[BINNING_SEL]))
            self.update_preview_slider_ranges(values)
        elif event == CAMERA_MOCK_FILE:
            file_name = values[CAMERA_MOCK_FILE]
            try:
                self.camera.set_result_image(file_name)
                self.update_preview_slider_ranges(values)
            except Exception:
                pass
        elif event == CAPTURE_IMAGE_BTN:
            self.capture_image(values)
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
        elif event == PREVIEW_WATERFALL_CB or event == PREVIEW_PSEUDOCOLOUR_CB:
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
        elif event == PREVIEW_INTERP_CB:
            if not self.live_preview_active:
                self.update_live_preview(values[PREVIEW_WATERFALL_CB], values[PREVIEW_INTERP_CB])
        elif event == PORT_RELOAD_BTN:
            self.refresh_stage_ports()
        elif event == STAGE_TYPE_SEL:
            if values[STAGE_TYPE_SEL] == STAGE_TYPE_MOCK:
                self.window[STAGE_PORT_PANE].update(visible=False)
            else:
                self.window[STAGE_PORT_PANE].update(visible=True)
        elif event in (MENU_QUIT, sg.WINDOW_CLOSE_ATTEMPTED_EVENT):
            self.exit()

    def exit(self):
        # TODO: Cleanup code / check there are no ongoing processes
        # We don't want to exit in the middle of capturing an image - in this
        # case probably display a prompt?
        if self.live_preview_active:
            confirm = sg.popup_ok_cancel("Are you sure you want to exit?", title="Confirm close")
            if confirm != "OK":
                return
            self.stop_live_preview()
        self.log("Exiting PyHSI", level=DEBUG)
        self.window.close()
        sys.exit()

    def run(self):
        _, values = self.window.read(timeout=0)
        event = INIT_EVENT
        while True:
            if event != '__TIMEOUT__':
                self.handle_event(event, values)
            elif self.live_preview_active:
                self.next_live_preview_frame(values)
            event, values = self.window.read(timeout=0)

    def setup_stage(self, values):
        try:
            stage_type = values[STAGE_TYPE_SEL]
            if not self.stage or stage_type != self.stage_type:
                if stage_type == STAGE_TYPE_TSA200:
                    pstr = values[STAGE_PORT_SEL]
                    port = None
                    for p in self.ports:
                        if pstr == port_label(p):
                            port = p
                    if port is None:
                        self.log(f"No serial port for stage '{stage_type}'",
                                 level=ERROR)
                        return False
                    self.stage = TSA200(port=serial.Serial(port.device))
                else:
                    self.stage = MockStage()
                self.stage_type = stage_type
        except Exception as e:
            self.log(f"Unable to connect to stage '{stage_type}': {e}",
                     level=ERROR)
            return False
        return True

    def setup_camera(self, values):
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

    def parse_numeric(self, input_, type_, min_, max_, fdb_key):
        try:
            val = type_(input_)
            if val < min_:
                raise ValueError(f"Minimum value {min_}")
            if val > max_:
                raise ValueError(f"Maximum value {max_}")
            self.window[fdb_key].update(visible=False)
            return val
        except ValueError:
            self.window[fdb_key].update(visible=True)
            return None

    def parse_values(self, values):
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
        self.log("Starting live preview", level=DEBUG)
        self.setup_camera(values)
        if self.camera_type == CAMERA_TYPE_MOCK:
            file_name = values[CAMERA_MOCK_FILE]
            try:
                self.camera.set_result_image(file_name)
            except FileNotFoundError:
                if not file_name.strip():
                    self.log("No source file for mock camera", level=ERROR)
                else:
                    self.log(f"No file named {file_name}", level=ERROR)
                return
            except envi.EnviDataFileNotFoundError:
                self.log(f"Unable to find data file for {file_name}", level=ERROR)
                return
        self.live_preview_active = True
        self.next_live_preview_frame(values)
        icon_path = os.path.join(ICON_DIR, ICON_PAUSE + ".png")
        self.window[PREVIEW_BTN].update(image_filename=icon_path)
        self.window[PREVIEW_CLEAR_BTN].update(disabled=False)

    def stop_live_preview(self):
        self.log("Stopping live preview", level=DEBUG)
        icon_path = os.path.join(ICON_DIR, ICON_PLAY + ".png")
        self.window[PREVIEW_BTN].update(image_filename=icon_path)
        if self.live_preview_frame is None:
            self.window[PREVIEW_CLEAR_BTN].update(disabled=True)
        self.live_preview_active = False

    def clear_preview(self):
        if self.live_preview_active:
            self.stop_live_preview()
        self.window[PREVIEW_CANVAS].update(data=None)
        self.waterfall_frame = None
        self.live_preview_frame = None
        self.window[PREVIEW_CLEAR_BTN].update(disabled=True)

    def next_live_preview_frame(self, values):
        # Pseudocolour takes precedence over highlight
        flip = values[REVERSE_COLUMNS_CB]
        hl = values[PREVIEW_HIGHLIGHT_CB]
        waterfall = values[PREVIEW_WATERFALL_CB]
        pc = values[PREVIEW_PSEUDOCOLOUR_CB]
        if waterfall and pc:
            hl = False
        try:
            frame = self.camera.get_frame(flip=flip, highlight=hl)
        except Exception as e:
            self.log(f"Unable to connect to camera: {e}", level=ERROR)
            self.stop_live_preview()
            return
        if self.waterfall_frame is None or self.waterfall_frame.shape[0] != frame.shape[0]:
            self.waterfall_frame = np.zeros((frame.shape[0], 500, 3))
        self.waterfall_frame[:, :-1] = self.waterfall_frame[:, 1:]
        if not hl and not pc:
            frame = np.repeat(frame[:, :, np.newaxis], 3, axis=2)
        if pc and (waterfall or not hl):
            bgr = (round(values[PREVIEW_BLUE_BAND_SLIDER]) - 1,
                   round(values[PREVIEW_GREEN_BAND_SLIDER]) - 1,
                   round(values[PREVIEW_RED_BAND_SLIDER]) - 1)
            self.waterfall_frame[:, -1] = frame[:, bgr]
        else:
            band = round(values[PREVIEW_SINGLE_BAND_SLIDER]) - 1
            self.waterfall_frame[:, -1] = frame[:, band]
        if len(frame.shape) == 2:
            self.live_preview_frame = np.repeat(frame[:, :, np.newaxis], 3, axis=2)
        else:
            self.live_preview_frame = frame
        self.update_live_preview(waterfall, values[PREVIEW_INTERP_CB])

    def update_live_preview(self, waterfall, interpolation):
        frame = self.waterfall_frame if waterfall else self.live_preview_frame
        if frame is None:
            self.clear_preview()
            return
        frame = np.rot90(frame, k=self.live_preview_rotation)
        max_w = self.view_canvas_size[0]
        max_h = self.view_canvas_size[1]
        if waterfall:
            new_w = max_w
            new_h = max_h
        else:
            old_h = frame.shape[0]
            old_w = frame.shape[1]
            new_w = round(min(max_w, old_w * max_h / old_h))
            new_h = round(min(max_h, old_h * max_w / old_w))
        if interpolation:
            interp = cv2.INTER_LINEAR
        else:
            interp = cv2.INTER_NEAREST
        frame = cv2.resize(frame, (new_w, new_h), interpolation=interp)
        if not waterfall and self.camera.wl:
            frame = add_wavelength_labels(frame, self.camera.wl, rot=self.live_preview_rotation)
        frame = cv2.imencode('.png', frame)[1].tobytes()
        self.window[PREVIEW_CANVAS].update(data=frame)

    def capture_image(self, values):
        # TODO: Concurrency
        # https://pysimplegui.readthedocs.io/en/latest/cookbook/#recipe-long-operations-multi-threading
        try:
            self.setup_camera(values)
            if not self.setup_stage(values):
                return
            vals = self.parse_values(values)
            self.window[CAPTURE_IMAGE_BTN].update(disabled=True)
            self.window[CAPTURE_IMAGE_PROGRESS].update(0, visible=True)
            [img, md] = self.camera.capture_save(vals['file_name'], self.stage, vals['ranges'],
                                                 vals['velocity'], flip=vals['flip'],
                                                 verbose=False)
            self.show_preview(img / 4095, md['wavelength'])  # TODO: Fix
        except Exception as e:
            self.log(f"Unable to capture image: {e}", level=ERROR)
        finally:
            self.window[CAPTURE_IMAGE_PROGRESS].update(0, visible=False)
            self.window[CAPTURE_IMAGE_BTN].update(disabled=False)
