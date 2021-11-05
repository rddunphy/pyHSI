import logging
import numpy as np


def moving_average(a, n=3):
    kernel = np.ones(n) / n
    return np.convolve(a, kernel, mode='same')


def find_white_frames(S, threshold=0.9):
    f = np.mean(S, axis=(1, 2))
    f = moving_average(f, n=5)
    imax = np.argmax(f)
    w = threshold * f[imax]
    i1 = imax
    while i1 > 0 and f[i1] > w:
        i1 -= 1
    i2 = imax
    while i2 < len(f) - 1 and f[i2] > w:
        i2 += 1
    logging.debug(f"Detected white frames from {i1} to {i2} (brightest frame is {imax})")
    return i1, i2


def one_point_calibration(S, W, B, scale_factor=None):
    dtype = S.dtype
    W = np.median(W, axis=0)
    B = np.median(B, axis=0)
    with np.errstate(invalid='ignore', divide='ignore'):
        W = W - B
        S = S - B
        S = np.where(W > 0, np.divide(S, W), 0)
        S[S > 1] = 1
        S[S < 0] = 0
        if scale_factor is not None:
            S = S * scale_factor
        return np.asarray(S, dtype=dtype)
