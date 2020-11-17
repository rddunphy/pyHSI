"""Tools for viewing and working with hyperspectral images"""
import cv2
from spectral.io import envi


def image_play(img, title="Preview"):
    """Display video preview of image, exit with ESC"""
    try:
        n_bands = img.shape[2]
        for i in range(n_bands):
            band = img[:, :, i].squeeze()
            cv2.imshow(title, band)
            k = cv2.waitKey(10) & 0xFF
            if k == 27:
                raise KeyboardInterrupt("User pressed escape")
    finally:
        cv2.destroyAllWindows()


if __name__ == '__main__':
    img = envi.open('S_avermitilis.hdr', 'S_avermitilis.raw')
    image_play(img)
