import unittest

import numpy as np

from pyhsi.utils import (get_wavelengths, nearest_band,
                         highlight_saturated, get_rgb_bands)


class TestUtils(unittest.TestCase):
    def test_get_wavlengths(self):
        wl = get_wavelengths(4, 0, 8)
        self.assertEqual(wl, [1, 3, 5, 7])

    def test_nearest_band_next(self):
        idx = nearest_band([1, 3, 5, 7], 4.5)
        self.assertEqual(idx, 2)

    def test_nearest_band_prev(self):
        idx = nearest_band([1, 3, 5, 7], 5.5)
        self.assertEqual(idx, 2)

    def test_highlight_saturated(self):
        img = np.array([[0.1, 0.3],
                        [0, 1],
                        [0.01, 0.99]])
        hl = highlight_saturated(img)
        target = np.array(
            [[[0.1, 0.1, 0.1], [0.3, 0.3, 0.3]],
             [[1, 0, 0], [0, 0, 1]],
             [[0.01, 0.01, 0.01], [0.99, 0.99, 0.99]]])
        np.testing.assert_array_equal(hl, target)

    def test_highlight_saturated_threshold(self):
        img = np.array([[0.1, 0.3],
                        [0, 1],
                        [0.01, 0.99]])
        hl = highlight_saturated(
            img, threshold_black=0.05, threshold_white=0.95)
        target = np.array(
            [[[0.1, 0.1, 0.1], [0.3, 0.3, 0.3]],
             [[1, 0, 0], [0, 0, 1]],
             [[1, 0, 0], [0, 0, 1]]])
        np.testing.assert_array_equal(hl, target)

    def test_get_rgb_bands(self):
        wl = [300, 350, 400, 450, 500, 550, 600, 650]
        bands = get_rgb_bands(wl)
        self.assertEqual(bands, (7, 5, 3))

    def test_get_rgb_bands_fallback(self):
        wl = [550, 600, 650, 700, 750, 800, 850, 900]
        bands = get_rgb_bands(wl)
        self.assertEqual(bands, (6, 4, 2))


if __name__ == "__main__":
    unittest.main()
