#!/usr/bin/env python3
import unittest

from pyhsi.utils import get_wavelengths


class TestUtils(unittest.TestCase):
    def test_get_wavlengths(self):
        wl = get_wavelengths(4, 0, 8)
        self.assertEqual(wl, [1, 3, 5, 7])


if __name__ == "__main__":
    unittest.main()
