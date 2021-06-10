"""Utility tools for viewing and working with hyperspectral images."""

import cv2
import matplotlib.pyplot as plt
import numpy as np


def get_wavelengths(n_bands, min_wl, max_wl):
    """Get list of wavelengths corresponding to bands of an image.

    Args:
        n_bands: number of bands
        min_wl: minimum wavelength captured by the first band
        max_wl: maximum wavelength captured by the last band
    """
    inc = (max_wl - min_wl) / n_bands
    min_wl += 0.5 * inc
    wl = [min_wl + (x * inc) for x in range(n_bands)]
    return [(round(10 * x)) / 10 for x in wl]


def nearest_band(wavelengths, target):
    """Get index of band nearest to a target wavelength."""
    idx = 0
    minimum = float('inf')
    for (i, wl) in enumerate(wavelengths):
        if abs(target - wl) < minimum:
            minimum = abs(target - wl)
            idx = i
    return idx


def get_rgb_bands(wavelengths):
    """Get nearest bands to actual red, green, and blue light.

    If any two bands are the same (i.e. the spectrum of the camera does not
    cover the full visible spectrum), returns three evenly spaced bands for
    pseudo-RGB colouring.
    """
    bands = (
        nearest_band(wavelengths, 630),
        nearest_band(wavelengths, 532),
        nearest_band(wavelengths, 465)
    )
    if bands[0] == bands[1] or bands[1] == bands[2]:
        inc = len(wavelengths) // 4
        bands = (3 * inc, 2 * inc, inc)
    return bands


def highlight_saturated(img, threshold_black=0, threshold_white=1):
    """Highlight saturated pixels in a greyscale image.

    Kwargs:
        threshold_black: upper threshold for black pixels
        threshold_white: lower threshold for white pixels
    """
    img = np.repeat(img[:, :, np.newaxis], 3, axis=2)
    if threshold_black > 0:
        img[img <= threshold_black] = 0
    if threshold_white < 1:
        img[img >= threshold_white] = 1
    under = np.all(img == [0, 0, 0], axis=-1)
    over = np.all(img == [1, 1, 1], axis=-1)
    img[under] = [1, 0, 0]  # Blue-Green-Red
    img[over] = [0, 0, 1]
    return img


def add_wavelength_labels(img, wl, rot=0):
    w0 = min(wl)
    w1 = max(wl)
    margin = 20
    step = 100
    vals = [v for v in range(0, round(w1), step) if v > w0]
    for v in vals:
        if rot == 1:
            pos = round(img.shape[0] * (1 - (v - w0) / (w1 - w0)))
        elif rot == 2:
            pos = round(img.shape[1] * (1 - (v - w0) / (w1 - w0)))
        elif rot == 3:
            pos = round(img.shape[0] * (v - w0) / (w1 - w0))
        elif rot == 0:
            pos = round(img.shape[1] * (v - w0) / (w1 - w0))
        if rot % 2:
            p1 = (10, pos)
            p2 = (30, pos)
            org = (40, pos + 10)
            text = f"{v} nm"
        else:
            p1 = (pos, 10)
            p2 = (pos, 30)
            org = (pos - 30, 60)
            text = str(v)
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 1
        colour = (0, 255, 0)
        thickness = 2
        img = cv2.line(img, p1, p2, colour, thickness)
        if v > w0 + margin and v < w1 - margin:
            img = cv2.putText(img, text, org, font, scale, colour, thickness)
    return img


def image_play(img, highlight=False, title="Preview"):
    """Display video preview of image, exit with ESC.

    Args:
        img: numpy array of image data

    Kwargs:
        highlight: highlight saturated pixels
        title: window title
    """
    try:
        n_bands = img.shape[2]
        for i in range(n_bands):
            band = img[:, :, i].squeeze()
            if highlight:
                band = highlight_saturated(band)
            cv2.imshow(title, band)
            k = cv2.waitKey(10) & 0xFF
            if k == 27:
                raise KeyboardInterrupt("User pressed escape")
    finally:
        cv2.destroyAllWindows()


def show_band(img, band):
    plt.imshow(img[:, :, band].squeeze(), cmap="Greys")
    plt.show()


def show_preview(img, wl):
    rgb = img[:, :, get_rgb_bands(wl)]
    plt.imshow(rgb)
    plt.show()
