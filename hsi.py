"""Tools for viewing and working with hyperspectral images"""
import cv2
import numpy as np
from spectral.io import envi


def highlight_saturated(img, threshold=(0.01, 0.99)):
    """Highlight saturated pixels in a greyscale image"""
    img = np.repeat(img[:, :, np.newaxis], 3, axis=2)
    img[img < threshold[0]] = 0
    img[img > threshold[1]] = 1
    under = np.all(img == [0, 0, 0], axis=-1)
    over = np.all(img == [1, 1, 1], axis=-1)
    img[under] = [1, 0, 0]  # BGR
    img[over] = [0, 0, 1]
    return img


def image_play(img, highlight=False, title="Preview"):
    """Display video preview of image, exit with ESC"""
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


if __name__ == '__main__':
    img = envi.open('S_avermitilis.hdr', 'S_avermitilis.raw')
    image_play(img)
