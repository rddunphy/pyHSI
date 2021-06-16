"""Controller for Basler camera.

Usage example:

    camera = BaslerCamera()
    stage = TSA200()
    camera.capture_save('file_name', stage, (50, 150))
"""

from datetime import datetime
import logging
from time import sleep
import timeit

import numpy as np
from pypylon import pylon
from spectral.io import envi

from .utils import highlight_saturated, get_wavelengths


class BaslerCamera:
    """Represents an instance of the Basler piA1600 camera."""

    def __init__(self, exp=4000, gain=100, binning=1, mode_12bit=True, device=None):
        """Get an instance of the Basler camera with the specified setup.

        Kwargs:
            exp: exposure time (in μs)
            gain: raw gain value (range 0-500)
            binning: vertical and horizontal pixel binning
            mode_12bit: use 12-bit mode (8-bit mode if False)
            device: hardware device to use instead of Pylon instance
        """
        self.model_name = "Basler piA1600"
        self.device = device
        self.min_wl = 278.7
        self.max_wl = 1003.5
        self.raw_gain_factor = 0.0359
        self.max_bands = 1200
        self.max_samples = 1600
        self.set_exposure_time(exp)
        self.set_raw_gain(gain)
        self.set_binning(binning)
        self.set_mode_12bit(mode_12bit)
        self.dirty = True

    def set_exposure_time(self, exp):
        """Set exposure time in in μs"""
        self.exp = exp
        self.dirty = True

    def set_mode_12bit(self, mode_12bit):
        """Use 12-bit mode (8-bit mode if False)"""
        self.mode_12bit = mode_12bit
        self.bits = 12 if mode_12bit else 8
        self.ref_scale_factor = 4095 if mode_12bit else 255
        self.dirty = True

    def set_binning(self, binning):
        """Set vertical and horizontal pixel binning. 1, 2, or 4."""
        self.binning = binning
        self.n_bands = self.max_bands // binning
        self.n_samples = self.max_samples // binning
        self.wl = get_wavelengths(self.n_bands, self.min_wl, self.max_wl)
        self.dirty = True

    def set_raw_gain(self, raw_gain):
        """Set raw gain value (range 0-500)"""
        self.raw_gain = raw_gain
        self.dirty = True

    def set_actual_gain(self, gain):
        """Set gain in dB"""
        self.set_raw_gain(round(gain / self.raw_gain_factor))

    def get_actual_gain(self):
        """Get gain in dB"""
        return self.raw_gain_factor * self.raw_gain

    def set_hardware_values(self):
        if self.dirty:
            if self.device is None:
                device = pylon.TlFactory.GetInstance().CreateFirstDevice()
                self.device = pylon.InstantCamera(device)
            self.device.Open()
            self.device.BinningHorizontal.SetValue(self.binning)
            self.device.BinningVertical.SetValue(self.binning)
            self.device.GainRaw.SetValue(self.raw_gain)
            if self.mode_12bit:
                self.device.PixelFormat.SetValue('Mono16')
            else:
                self.device.PixelFormat.SetValue('Mono8')
            self.device.ExposureTimeAbs.SetValue(self.exp)
            self.device.Close()
            self.dirty = False

    def get_frame(self, flip=False, highlight=False):
        self.set_hardware_values()
        img = self.result_image[self._current_frame, :, :]
        img = img / self.ref_scale_factor
        self._current_frame = (self._current_frame + 1) % self.result_image.shape[0]
        if flip:
            img = np.flipud(img)
        if highlight:
            img = highlight_saturated(img)
        img = np.asarray(img * 255, dtype="uint8")
        return img

    def capture_save(self, file_name, stage, ranges, velocity=None, flip=False,
                     verbose=True, overwrite=False, description=""):
        """Capture a full hypersepectral image.

        File name may contain the following fields:
            {date} - acquisition date (YY-mm-dd)
            {time} - acquisition time (HH:MM:SS)
            {bin} - pixel binning
            {exp} - exposure time (in μs)
            {gain} - gain in dB
            {raw_gain} - raw gain value
            {mode} - '8-bit' or '12-bit'
            {start} - start position in mm
            {stop} - stop position in mm
            {travel} - distance travelled in mm
            {vel} - velocity in mm/s
            {frames} - number of frames captured
            {samples} - number of samples per frame
            {bands} - number of bands

        Args:
            file_name: save location (without extension)
            stage: linear translation stage
            ranges: list of ranges or single range to image, of the form
                    (start, stop)
            overwrite: overwrite existing files without prompt

        Kwargs:
            velocity: stage velocity (in mm/s)
            flip: flip order of columns in each frame
            verbose: log progress messages
        """
        acq_time = datetime.now()
        if not isinstance(ranges[0], tuple) and not isinstance(ranges[0], list):
            ranges = [ranges]
        data = self.capture(stage, ranges, velocity=velocity, flip=flip,
                            verbose=verbose)
        md = {
            'acquisition time': acq_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'reflectance scale factor': self.ref_scale_factor,
            'wavelength': self.wl
        }
        description = description.strip()
        if description != "":
            md['description'] = description
        envi.save_image(file_name, data, dtype='uint16',
                        interleave='bil', ext='.raw', metadata=md,
                        force=overwrite)
        if verbose:
            logging.info(f"Image saved as {file_name}.")
        return data, md

    def capture(self, stage, ranges, velocity=None, flip=False, verbose=True):
        """Capture a full hypersepectral image.

        Args:
            stage: linear translation stage
            ranges: list of ranges or single range to image, of the form
                    (start, stop)

        Kwargs:
            velocity: stage velocity (in mm/s)
            flip: flip order of columns in each frame
            verbose: log progress messages
        """
        # TODO: Look into https://docs.baslerweb.com/overlapping-image-acquisition
        # TODO: 8-bit mode
        self.set_hardware_values()
        if not velocity:
            velocity = stage.default_velocity
        frames = []
        if not isinstance(ranges[0], tuple):
            ranges = [ranges]
        try:
            n_frames = 0
            total_start_time = timeit.default_timer()
            capture_time = 0
            if verbose:
                d = 0
                for r in ranges:
                    d += abs(r[0] - r[1])
                t = round(d / velocity)
                logging.info(f"Imaging {d} mm at {velocity} mm/s (≈{t} s)")
                now = datetime.now().strftime("%H:%M:%S")
                logging.info(f"Starting image capture at {now}...")
                logging.info("Positioning stage...")
            for r in ranges:
                start = r[0]
                stop = r[1]
                stage.move_to(start, block=True)
                stage.move_to(stop, velocity=velocity)
                self.device.StartGrabbing()
                range_start_time = timeit.default_timer()
                while stage.is_moving():
                    grab = self.device.RetrieveResult(
                        5000, pylon.TimeoutHandling_ThrowException)
                    if grab.GrabSucceeded():
                        frames.append(grab.Array)
                        n_frames += 1
                    else:
                        logging.error(f"{grab.ErrorCode} - {grab.ErrorDescription}")
                    grab.Release()
                capture_time += timeit.default_timer() - range_start_time
                self.device.StopGrabbing()
        finally:
            total_time = timeit.default_timer() - total_start_time
            self.device.StopGrabbing()
            self.device.Close()
        if verbose:
            logging.info(f"Total time {total_time:.2f} s")
            logging.info((f"{n_frames} frames captured in {capture_time:.2f} s "
                   f"({n_frames/capture_time:.2f} fps)"))
        data = np.rot90(np.array(frames, dtype=np.uint16), axes=(1, 2))
        if flip:
            data = np.fliplr(data)
        return data

    def __str__(self):
        lines = [
            "Basler piA1600-gm camera",
            f"Sensor size: {self.max_samples}x{self.max_bands}",
            f"Spectral range: {self.min_wl}-{self.max_wl} nm",
            f"Mode: {'12-bit' if self.mode_12bit else '8-bit'}",
            f"Gain: {self.raw_gain} ({self.get_actual_gain():.2f} dB)",
            f"Exposure: {self.exp} μs",
            f"Binning: {self.binning}x{self.binning}",
            f"Samples: {self.n_samples}",
            f"Bands: {self.n_bands}",
            f"Reflectance scale factor: {self.ref_scale_factor}"
        ]
        return "\n".join(lines)


class MockCamera:
    def __init__(self, exp=4000, gain=100, binning=1, mode_12bit=True):
        self.model_name = "PyHSI Mock Camera"
        self.raw_gain_factor = 1
        self.exp = exp
        self.gain = gain
        self.binning = binning
        self.mode_12bit = mode_12bit
        self.wl = None
        self._result_image_file_name = None
        self._current_frame = 0

    def set_exposure_time(self, exp):
        """Set exposure time in in μs"""
        self.exp = exp

    def set_mode_12bit(self, mode_12bit):
        """Use 12-bit mode (8-bit mode if False)"""
        self.mode_12bit = mode_12bit

    def set_binning(self, binning):
        """Set vertical and horizontal pixel binning. 1, 2, or 4."""
        self.binning = binning

    def set_raw_gain(self, raw_gain):
        """Set raw gain value (range 0-500)"""
        self.raw_gain = raw_gain

    def set_actual_gain(self, gain):
        """Set gain in dB"""
        self.set_raw_gain(round(gain / self.raw_gain_factor))

    def get_actual_gain(self):
        """Get gain in dB"""
        return self.raw_gain_factor * self.raw_gain

    def set_result_image(self, file_name):
        if self._result_image_file_name != file_name:
            logging.debug(f"Setting result image for mock camera to {file_name}")
            self._result_image_file_name = file_name
            img = envi.open(file_name)
            self.result_image = img.asarray()
            self.ref_scale_factor = img.scale_factor
            self.nbands = img.nbands
            self.wl = img.bands.centers
            if self.wl is None:
                logging.warning(f"No valid wavelength data for {file_name}")
                self.wl = list(range(self.nbands))
            self._current_frame = 0
        else:
            logging.debug("Result image hasn't changed")

    def capture_save(self, file_name, stage, ranges, velocity=None, flip=False,
                     verbose=True, overwrite=False, description="",
                     progress_callback=None):
        """Capture a full hypersepectral image.

        File name may contain the following fields:
            {date} - acquisition date (YY-mm-dd)
            {time} - acquisition time (HH:MM:SS)
            {bin} - pixel binning
            {exp} - exposure time (in μs)
            {gain} - gain in dB
            {raw_gain} - raw gain value
            {mode} - '8-bit' or '12-bit'
            {start} - start position in mm
            {stop} - stop position in mm
            {travel} - distance travelled in mm
            {vel} - velocity in mm/s
            {frames} - number of frames captured
            {samples} - number of samples per frame
            {bands} - number of bands

        Args:
            file_name: save location (without extension)
            stage: linear translation stage
            ranges: list of ranges or single range to image, of the form
                    (start, stop)
            overwrite: overwrite existing files without prompt

        Kwargs:
            velocity: stage velocity (in mm/s)
            flip: flip order of columns in each frame
            verbose: log progress messages
        """
        acq_time = datetime.now()
        if not isinstance(ranges[0], tuple) and not isinstance(ranges[0], list):
            ranges = [ranges]
        data = self.capture(stage, ranges, velocity=velocity, flip=flip,
                            verbose=verbose, progress_callback=progress_callback)
        md = {
            'acquisition time': acq_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'reflectance scale factor': self.ref_scale_factor,
            'wavelength': self.wl
        }
        description = description.strip()
        if description != "":
            md['description'] = description
        envi.save_image(file_name, data, dtype='uint16',
                        interleave='bil', ext='.raw', metadata=md,
                        force=overwrite)
        if verbose:
            logging.info(f"Image saved as {file_name}.")
        return data, md

    def capture(self, stage, ranges, velocity=None, flip=False, verbose=True,
                progress_callback=None):
        """Simulate capturing a full hypersepectral image.

        Args:
            stage: linear translation stage
            ranges: list of ranges or single range to image, of the form
                    (start, stop)

        Kwargs:
            velocity: stage velocity (in mm/s)
            flip: flip order of columns in each frame
            verbose: log progress messages
            progress_callback: callback function which will periodically called
                with progress in range 0.0 to 1.0
        """
        if not isinstance(ranges[0], tuple):
            ranges = [ranges]
        for r in ranges:
            start = r[0]
            stop = r[1]
            stage.move_to(start, block=True)
            stage.move_to(stop, velocity=velocity)
            while stage.is_moving():
                sleep(0.1)
                progress = (stage.get_position() - start) / (stop - start)
                progress_callback(progress)
        if flip:
            return np.fliplr(self.result_image)
        return self.result_image

    def get_frame(self, flip=False, highlight=False):
        img = self.result_image[self._current_frame, :, :]
        img = img / self.ref_scale_factor
        self._current_frame = (self._current_frame + 1) % self.result_image.shape[0]
        if flip:
            img = np.flipud(img)
        if highlight:
            img = highlight_saturated(img)
        return img
