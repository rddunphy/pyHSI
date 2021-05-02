"""Utility tools for viewing and working with hyperspectral images."""

import cv2
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
