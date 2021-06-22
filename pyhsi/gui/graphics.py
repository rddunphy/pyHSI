"""Stuff to do with processing images and loading icons"""

import os

import cv2
import PySimpleGUI as sg


# Icon names correspond to filename with .png extension in ICON_DIR
ICON_DIR = os.path.abspath("icons")


def get_application_icon_path():
    """Get the PyHSI icon for this OS (.ico for Windows, .png otherwise)"""
    icon_ext = ".ico" if sg.running_windows() else ".png"
    return os.path.join(ICON_DIR, "pyhsi" + icon_ext)


def get_icon_path(icon, hidpi=False):
    """Return full path for icon with given name"""
    size = 40 if hidpi else 25
    return os.path.join(ICON_DIR, f"{icon}{size}.png")


def get_icon_button(icon, hidpi=False, **kwargs):
    """Create a button with an icon as an image"""
    mc = ("white", "#405e92")
    path = get_icon_path(icon, hidpi=hidpi)
    return sg.Button("", image_filename=path, mouseover_colors=mc, **kwargs)


def set_button_icon(button, icon, hidpi=False, **kwargs):
    """Change image on button"""
    path = get_icon_path(icon, hidpi=hidpi)
    button.update(image_filename=path, **kwargs)


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
