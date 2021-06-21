import ctypes
from datetime import datetime
import json
from json.decoder import JSONDecodeError
import logging
import os
import string
import subprocess
import sys
import threading

import cv2
import dateutil
import numpy as np
import PySimpleGUI as sg
import serial
from serial.tools import list_ports
import spectral
from spectral.io import envi
import tkinter as tk


def get_icon_button(icon, hidpi=False, **kwargs):
    """Create a button with an icon as an image"""
    mc = ("white", "#405e92")
    size = 40 if hidpi else 25
    path = os.path.join(ICON_DIR, f"{icon}{size}.png")
    return sg.Button("", image_filename=path, mouseover_colors=mc, **kwargs)


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
ICON_EXPAND = "expand"
ICON_FILE = "file"
ICON_BROWSER = "browser"
ICON_CALIBRATE = "calibrate"
ICON_CUBE = "cube"
ICON_CROP = "crop"


