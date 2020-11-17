import cv2
import numpy as np
from pypylon import genicam, pylon
from spectral.io import envi

from zolix import Scanner, auto_detect_port


def preview(exp=None, gain=None, binning=None, velocity=None, port=None):
    try:
        device = pylon.TlFactory.GetInstance().CreateFirstDevice()
        camera = pylon.InstantCamera(device)
        camera.Open()
        if exp:
            camera.ExposureTime = exp  # Exposure time in microseconds, as double
        if gain:
            camera.Gain = gain  # Gain in dB as double
        if binning:
            camera.BinningHorizontalMode = "BinningHorizontalMode_Sum"  # Not available for every model?
            camera.BinningVerticalMode = "BinningVerticalMode_Sum"
            camera.BinningHorizontal = binning
            camera.BinningVertical = binning
        camera.StartGrabbing()
        while True:
            grab = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
            if grab.GrabSucceeded():
                cv2.imshow(grab.Array)
            grab.Release()
    finally:
        camera.StopGrabbing()
        camera.Close()
        cv2.destroyAllWindows()


def preview_waterfall():
    # TODO: Waterfall preview for focus
    pass


def capture_save(file_name, start, stop, exp=None, gain=None, binning=None, velocity=None, port=None):
    # TODO: Look into https://docs.baslerweb.com/overlapping-image-acquisition
    # TODO: bits?
    if port:
        s = Scanner(port)
    else:
        s = Scanner(auto_detect_port())
    if not velocity:
        velocity = s.default_velocity
    if not file_name.endswith('.hdr'):
        file_name = file_name + '.hdr'
    frames = []
    try:
        device = pylon.TlFactory.GetInstance().CreateFirstDevice()
        camera = pylon.InstantCamera(device)
        camera.Open()
        if exp:
            camera.ExposureTime = exp  # Exposure time in microseconds, as double
        if gain:
            camera.Gain = gain  # Gain in dB as double
        if binning:
            camera.BinningHorizontalMode = "BinningHorizontalMode_Sum"  # Not available for every model?
            camera.BinningVerticalMode = "BinningVerticalMode_Sum"
            camera.BinningHorizontal = binning
            camera.BinningVertical = binning
        n_frames = 0
        s.move_to(start, block=True)
        s.move_to(stop, velocity=velocity)
        camera.StartGrabbing()
        while s.is_moving():
            grab = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
            if grab.GrabSucceeded():
                frames.append(grab.Array)
                n_frames += 1
            else:
                print("Error: ", grab.ErrorCode, grab.ErrorDescription)
            grab.Release()
    finally:
        camera.StopGrabbing()
        camera.Close()
    n_cols = frames[0].shape[0]
    n_bands = frames[0].shape[1]  # TODO: check these are the right way round

    # Process data and save as Envi file
    data = np.ndarray((n_frames, n_cols, n_bands), dtype=np.uint16)
    for i, frame in enumerate(frames):
        data[i, :, :] = frame
    md = {
        'reflectance scale factor': 4095,  # TODO: check
        'wavelength': [x + 1.0 for x in range(256)]  # TODO: check
    }
    envi.save_image(file_name, data, interleave='bil', ext='.raw', metadata=md)


def connection_test():
    try:
        device = pylon.TlFactory.GetInstance().CreateFirstDevice()
        camera = pylon.InstantCamera(device)
        camera.Open()
        print("Connected to device: ", camera.GetDeviceInfo().GetModelName())
        camera.Close()
    except genicam.GenericException as e:
        print("Could not connect to device.", e)
