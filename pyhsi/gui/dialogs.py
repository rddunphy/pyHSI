"""Dialogs used by the main application"""

import logging
import os

import cv2
import numpy as np
import PySimpleGUI as sg
from spectral.io import envi

from .graphics import get_icon_button, resize_img_to_area
from ..preprocessing import find_white_frames, one_point_calibration


class CalibrationDialog:
    """Dialog for performing one-point calibration on an image"""

    def __init__(self, img, root, file_path):
        # Create scaled grayscale image for preview
        self.img = img
        preview = img.read_band(img.nbands // 2)
        preview = np.ascontiguousarray(preview * 255, dtype="uint8")
        preview = np.repeat(preview[:, :, np.newaxis], 3, axis=2)
        rs = root.window.size
        max_img_size = (round(rs[0] * 0.5), round(rs[1] * 0.5))
        self.preview = resize_img_to_area(preview, max_img_size)
        self.view_scale = self.preview.shape[0] / self.img.shape[0]
        self.root = root
        i1, i2 = find_white_frames(self.img.asarray())
        self.folder = os.path.dirname(file_path)
        files = os.listdir(self.folder)
        dark_ref_file = ""
        for f in files:
            if f.endswith(".hdr") and "dark_ref" in f:
                dark_ref_file = os.path.join(self.folder, f)
        output_file = os.path.splitext(file_path)[0] + "_calibrated.hdr"
        layout = [
            [
                sg.Column([
                    [
                        sg.Text("Calibration tile")
                    ],
                    [
                        sg.Slider(
                            range=(self.img.nrows - 1, 0),
                            default_value=i1,
                            key="Slider_i1",
                            orientation="v",
                            enable_events=True
                        ),
                        sg.Slider(
                            range=(self.img.nrows - 1, 0),
                            default_value=i2,
                            key="Slider_i2",
                            orientation="v",
                            enable_events=True
                        )
                    ]
                ]),
                sg.Column([[
                    sg.Image(key="Image", size=(self.preview.shape[0], self.preview.shape[1]))
                ]])
            ],
            [
                sg.Text("Dark reference", pad=(3, 0), size=(15, 1)),
                sg.Input(dark_ref_file, key="DarkRefPath", size=(35, 1)),
                get_icon_button(
                    "open",
                    button_type=sg.BUTTON_TYPE_BROWSE_FILE,
                    file_types=(("ENVI", "*.hdr"),),
                    initial_folder=self.folder,
                    tooltip="Browse...",
                    hidpi=root.hidpi
                )
            ],
            [
                sg.Text("Save as", pad=(3, 0), size=(15, 1)),
                sg.Input(output_file, key="SavePath", size=(35, 1)),
                get_icon_button(
                    "open",
                    button_type=sg.BUTTON_TYPE_SAVEAS_FILE,
                    file_types=(("ENVI", "*.hdr"),),
                    initial_folder=self.folder,
                    tooltip="Browse...",
                    hidpi=root.hidpi
                )
            ],
            [
                sg.Ok(), sg.Cancel()
            ]
        ]
        self.window = sg.Window(
            "One-point calibration",
            layout,
            modal=True,
            keep_on_top=True,
            finalize=True,
            alpha_channel=0
        )
        self.update_frames(i1, i2)
        self.window.refresh()
        rx, ry = root.window.current_location()
        rw, rh = root.window.size
        ww, wh = self.window.size
        self.window.move(rx + rw//2 - ww//2, ry + rh//2 - wh//2)
        self.window.set_alpha(1)

    def run(self):
        while True:
            e, v = self.window.read()
            if e == "Ok":
                self.calibrate(v)
                break
            elif e in ("Slider_i1", "Slider_i2"):
                self.update_frames(int(v["Slider_i1"]), int(v["Slider_i2"]))
            else:  # Cancel, window closed, etc.
                break
        self.window.close()

    def update_frames(self, i1, i2):
        """Update image to show the selected frames with red lines"""
        i1 = round(i1 * self.view_scale)
        i2 = round(i2 * self.view_scale)
        img = self.preview.copy()
        max_x = img.shape[1] - 1
        c = (0, 0, 255)  # Use red for overlay
        img = cv2.line(img, (0, i1), (max_x, i1), c)
        img = cv2.line(img, (0, i2), (max_x, i2), c)
        overlay = np.zeros(img.shape, np.uint8)
        overlay = cv2.rectangle(overlay, (0, i1), (max_x, i2), c, -1)
        img = cv2.addWeighted(overlay, 0.25, img, 0.75, 0)
        img = cv2.imencode('.png', img)[1].tobytes()
        self.window["Image"].update(data=img)

    def calibrate(self, v):
        """Perform one-point calibration"""
        i1 = int(v["Slider_i1"])
        i2 = int(v["Slider_i2"])
        S = self.img.asarray()
        W = S[i1:i2, :, :]
        if 'interleave' in self.img.metadata:
            interleave = self.img.metadata['interleave']
        else:
            interleave = 'bil'
        try:
            d_img = envi.open(v["DarkRefPath"])
            D = d_img.asarray()
            X = one_point_calibration(S, W, D, scale_factor=self.img.scale_factor)
            envi.save_image(v["SavePath"], X, dtype='uint16', ext='.raw', interleave=interleave,
                            metadata=self.img.metadata, force=True)
            self.root.open_file(file_path=v["SavePath"])
        except Exception as e:
            logging.error(f"Error calibrating image: {e}")


class CropDialog:
    """Dialog for cropping a region of an image and discarding unwanted bands"""

    def __init__(self, img, root, file_path):
        # Create scaled grayscale image for preview
        self.img = img
        preview = img.read_band(img.nbands // 2)
        preview = np.ascontiguousarray(preview * 255, dtype="uint8")
        preview = np.repeat(preview[:, :, np.newaxis], 3, axis=2)
        rs = root.window.size
        max_img_size = (round(rs[0] * 0.5), round(rs[1] * 0.5))
        self.preview = resize_img_to_area(preview, max_img_size)
        self.view_scale = self.preview.shape[0] / self.img.shape[0]
        self.root = root
        self.folder = os.path.dirname(file_path)
        output_file = os.path.splitext(file_path)[0] + "_cropped.hdr"
        logging.debug(self.img.shape)
        layout = [
            [
                sg.Column([
                    [
                        sg.Text("Crop to area")
                    ],
                    [sg.Slider(
                        range=(0, self.img.ncols - 1),
                        default_value=0,
                        key="Slider_x1",
                        orientation="h",
                        enable_events=True
                    )],
                    [sg.Slider(
                        range=(0, self.img.ncols - 1),
                        default_value=self.img.ncols - 1,
                        key="Slider_x2",
                        orientation="h",
                        enable_events=True
                    )],
                    [
                        sg.Slider(
                            range=(self.img.nrows - 1, 0),
                            default_value=0,
                            key="Slider_y1",
                            orientation="v",
                            enable_events=True
                        ),
                        sg.Slider(
                            range=(self.img.nrows - 1, 0),
                            default_value=self.img.nrows - 1,
                            key="Slider_y2",
                            orientation="v",
                            enable_events=True
                        )
                    ],
                    [
                        sg.Text("Keep bands between")
                    ],
                    [sg.Slider(
                        range=(0, self.img.nbands - 1),
                        default_value=0,
                        key="Slider_lambda1",
                        orientation="h"
                    )],
                    [sg.Slider(
                        range=(0, self.img.nbands - 1),
                        default_value=self.img.nbands - 1,
                        key="Slider_lambda2",
                        orientation="h"
                    )]
                ]),
                sg.Column([[
                    sg.Image(key="Image", size=(self.preview.shape[0], self.preview.shape[1]))
                ]])
            ],
            [
                sg.Text("Save as", pad=(3, 0), size=(15, 1)),
                sg.Input(output_file, key="SavePath", size=(35, 1)),
                get_icon_button(
                    "open",
                    button_type=sg.BUTTON_TYPE_SAVEAS_FILE,
                    file_types=(("ENVI", "*.hdr"),),
                    initial_folder=self.folder,
                    tooltip="Browse...",
                    hidpi=root.hidpi
                )
            ],
            [
                sg.Ok(), sg.Cancel()
            ]
        ]
        self.window = sg.Window(
            "Crop image",
            layout,
            modal=True,
            keep_on_top=True,
            finalize=True,
            alpha_channel=0
        )
        self.update_frames(0, self.img.ncols - 1, 0, self.img.nrows - 1)
        self.window.refresh()
        rx, ry = root.window.current_location()
        rw, rh = root.window.size
        ww, wh = self.window.size
        self.window.move(rx + rw//2 - ww//2, ry + rh//2 - wh//2)
        self.window.set_alpha(1)

    def run(self):
        while True:
            e, v = self.window.read()
            if e == "Ok":
                self.crop(v)
                break
            elif e in ("Slider_x1", "Slider_x2", "Slider_y1", "Slider_y2"):
                self.update_frames(int(v["Slider_x1"]), int(v["Slider_x2"]),
                                   int(v["Slider_y1"]), int(v["Slider_y2"]))
            else:  # Cancel, window closed, etc.
                break
        self.window.close()

    def update_frames(self, x1, x2, y1, y2):
        """Update image to show the selected frames with red lines"""
        x1 = round(x1 * self.view_scale)
        x2 = round(x2 * self.view_scale)
        y1 = round(y1 * self.view_scale)
        y2 = round(y2 * self.view_scale)
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        img = self.preview.copy()
        max_x = img.shape[1] - 1
        max_y = img.shape[0] - 1
        c = (0, 0, 255)  # Use red for overlay
        img = cv2.rectangle(img, (x1, y1), (x2, y2), c, 1)
        overlay = np.zeros(img.shape, np.uint8)
        overlay = cv2.rectangle(overlay, (0, 0), (max_x, y1), c, -1)
        overlay = cv2.rectangle(overlay, (0, 0), (x1, max_y), c, -1)
        overlay = cv2.rectangle(overlay, (0, y2), (max_x, max_y), c, -1)
        overlay = cv2.rectangle(overlay, (x2, 0), (max_x, max_y), c, -1)
        img = cv2.addWeighted(overlay, 0.25, img, 0.75, 0)
        img = cv2.imencode('.png', img)[1].tobytes()
        self.window["Image"].update(data=img)

    def crop(self, v):
        """Crop image and save"""
        logging.debug(v)
        x1 = int(v["Slider_x1"])
        x2 = int(v["Slider_x2"])
        y1 = int(v["Slider_y1"])
        y2 = int(v["Slider_y2"])
        lambda1 = int(v["Slider_lambda1"])
        lambda2 = int(v["Slider_lambda2"])
        bands = list(range(lambda1, lambda2 + 1))
        img = self.img.read_subregion((y1, y2 + 1), (x1, x2 + 1), bands)
        img *= self.img.scale_factor
        metadata = self.img.metadata
        if 'interleave' in metadata:
            interleave = self.img.metadata['interleave']
        else:
            interleave = 'bil'
        if 'wavelength' in metadata:
            metadata['wavelength'] = metadata['wavelength'][lambda1:lambda2+1]
        try:
            envi.save_image(v["SavePath"], img, dtype='uint16', ext='.raw', interleave=interleave,
                            metadata=metadata, force=True)
            self.root.open_file(file_path=v["SavePath"])
        except Exception as e:
            logging.error(f"Error cropping image: {e}")
