import logging
import numpy as np


def find_white_frames(S, threshold=0.99):
    f = np.mean(S, axis=(1, 2))
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
    W = np.mean(W, axis=0)
    B = np.mean(B, axis=0)
    with np.errstate(invalid='ignore', divide='ignore'):
        div = (W - B)
        X = np.where(div > 0, np.divide(S - B, div), 0)
        X[X > 1] = 1
        X[X < 0] = 0
        if scale_factor is not None:
            X = X * scale_factor
            X = np.asarray(X, dtype=S.dtype)
        return X
