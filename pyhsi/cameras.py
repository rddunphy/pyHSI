"""Controller for Basler camera.

Usage example:

    camera = BaslerCamera()
    camera.waterfall()
    camera.capture_save('file_name', 50, 150)
"""

from datetime import datetime
import os
import time
import timeit

import cv2
import numpy as np
from pypylon import pylon
from spectral.io import envi

from .stages import TSA200
from .utils import highlight_saturated, get_wavelengths, get_rgb_bands


class BaslerCamera:
    """Represents an instance of the Basler piA1600 camera."""

    def __init__(self, exp=4000, gain=100, binning=1, mode_12bit=True,
                 stage=None, device=None):
        """Get an instance of the Basler camera with the specified setup.

        Kwargs:
            exp: exposure time (in μs)
            gain: raw gain value (range 0-500)
            binning: vertical and horizontal pixel binning
            mode_12bit: use 12-bit mode (8-bit mode if False)
            stage: linear translation stage for capturing images (creates
                instance of TSA200 if not specified)
            device: instance of pylon camera (generated automatically by
                default)
        """
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
        self.stage = stage

    def set_exposure_time(self, exp):
        """Set exposure time in in μs"""
        self.exp = exp

    def set_mode_12bit(self, mode_12bit):
        """Use 12-bit mode (8-bit mode if False)"""
        self.mode_12bit = mode_12bit
        self.bits = 12 if mode_12bit else 8
        self.ref_scale_factor = 4095 if mode_12bit else 255

    def set_binning(self, binning):
        """Set vertical and horizontal pixel binning. 1, 2, or 4."""
        self.binning = binning
        self.n_bands = self.max_bands // binning
        self.n_samples = self.max_samples // binning
        self.wl = get_wavelengths(self.n_bands, self.min_wl, self.max_wl)

    def set_raw_gain(self, raw_gain):
        """Set raw gain value (range 0-500)"""
        self.raw_gain = raw_gain

    def set_actual_gain(self, gain):
        """Set gain in dB"""
        self.set_raw_gain(round(gain / self.raw_gain_factor))

    def get_actual_gain(self):
        """Get gain in dB"""
        return self.raw_gain_factor * self.raw_gain

    def set_hardware_values(self):
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

    def preview(self, highlight=True, flip=False, scale_to=None):
        """Show a live preview of frames from the camera.

        Useful for checking exposure.

        Kwargs:
            highlight: highlight saturated pixels in blue/red (default True)
            flip: flip order of columns in each frame
            scale_to: size to scale output to - (width, height)
        """
        self.set_hardware_values()
        try:
            cv_window_title = "BaslerCamera preview"
            cv2.namedWindow(cv_window_title)
            cv2.startWindowThread()
            self.device.StartGrabbing()
            while True:
                grab = self.device.RetrieveResult(
                    5000, pylon.TimeoutHandling_ThrowException)
                if grab.GrabSucceeded():
                    img = np.asarray(grab.Array) / self.ref_scale_factor
                    img = np.rot90(img, k=2)
                    if flip:
                        img = np.fliplr(img)
                    if highlight:
                        img = highlight_saturated(img)
                    if scale_to:
                        img = cv2.resize(img, scale_to)
                    cv2.imshow(cv_window_title, img)
                    k = cv2.waitKey(1) & 0xFF
                    if k == 27 or cv2.getWindowProperty(cv_window_title, cv2.WND_PROP_VISIBLE) < 1:
                        break
                grab.Release()
        finally:
            self.device.StopGrabbing()
            self.device.Close()
            cv2.destroyAllWindows()

    def waterfall(self, bands=None, length=500, flip=False, horizontal=False,
                  scale_to=None):
        """Show a live spatial preview of successive frames.

        Useful for checking focus. Output will be in greyscale if a single band
        is selected, or in RGB if three bands are selected. If bands are not
        specified, output will use result of `pyhsi.utils.get_rgb_bands()`.

        Kwargs:
            bands: which band(s) to use in the preview
            length: number of frames to show
            flip: flip order of columns in each frame
            horizontal: rotate so frames shift horizontally (right to left)
            scale_to: size to scale output to - (width, height)
        """
        self.set_hardware_values()
        if bands is None:
            bands = get_rgb_bands(self.wl)
        if len(bands) == 1:
            greyscale = True
            print(f"Using band {bands}")
        else:
            greyscale = False
            print(f"Using bands {bands}")
        preview_data = None
        try:
            cv_window_title = "BaslerCamera waterfall preview"
            cv2.namedWindow(cv_window_title)
            cv2.startWindowThread()
            self.device.StartGrabbing()
            while True:
                grab = self.device.RetrieveResult(
                    5000, pylon.TimeoutHandling_ThrowException)
                if grab.GrabSucceeded():
                    img = np.asarray(grab.Array) / self.ref_scale_factor
                    if preview_data is None:
                        if greyscale:
                            preview_data = np.ndarray((length, img.shape[1]))
                        else:
                            preview_data = np.ndarray((length, img.shape[1], 3))
                    preview_data[1:] = preview_data[:-1]
                    if greyscale:
                        new_frame = img[bands]
                    else:
                        new_frame = np.ndarray((img.shape[1], 3))
                        new_frame[:, 0] = img[bands[0]]
                        new_frame[:, 1] = img[bands[1]]
                        new_frame[:, 2] = img[bands[2]]
                    if not flip:
                        new_frame = np.flip(new_frame)
                    preview_data[0] = new_frame
                    if horizontal:
                        preview = np.rot90(preview_data)
                    else:
                        preview = preview_data
                    if scale_to:
                        preview = cv2.resize(preview, scale_to)
                    cv2.imshow(cv_window_title, preview)
                    k = cv2.waitKey(1) & 0xFF
                    if k == 27:
                        break
                grab.Release()
        finally:
            self.device.StopGrabbing()
            self.device.Close()
            cv2.destroyAllWindows()

    # def capture_save(self, file_name, start, stop, velocity=None, flip=False,
    #                  verbose=True, overwrite=False):
    #     # """Capture a full hypersepectral image.

        # File name may contain the following fields:
        #     {date} - acquisition date (YY-mm-dd)
        #     {time} - acquisition time (HH:MM:SS)
        #     {bin} - pixel binning
        #     {exp} - exposure time (in μs)
        #     {gain} - gain in dB
        #     {raw_gain} - raw gain value
        #     {mode} - '8-bit' or '12-bit'
        #     {start} - start position in mm
        #     {stop} - stop position in mm
        #     {travel} - distance travelled in mm
        #     {vel} - velocity in mm/s
        #     {frames} - number of frames captured
        #     {samples} - number of samples per frame
        #     {bands} - number of bands

        # Args:
        #     file_name: save location (without extension)
        #     start: start position of stage (in mm)
        #     stop: stop position of stage (in mm)
        #     overwrite: overwrite existing files without prompt

        # Kwargs:
        #     velocity: stage velocity (in mm/s)
        #     flip: flip order of columns in each frame
        #     verbose: print progress messages
        # """
        # acq_time = datetime.now()
        # if isinstance(stop, list):
        #     data = self.capture_complex(start, stop, velocity=velocity, flip=flip,
        #                         verbose=verbose)
        #     stop = stop[-1]
        # else:
        #     data = self.capture(start, stop, velocity=velocity, flip=flip,
        #                         verbose=verbose)
        # md = {
        #     'acquisition time': acq_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
        #     'description': "Image captured with Basler piA1600-35gm\n",
        #     'reflectance scale factor': self.ref_scale_factor,
        #     'wavelength': self.wl
        # }
        # while True:
        #     file_name = self._process_file_name(file_name, acq_time, start,
        #                                         stop, velocity, data.shape)
        #     try:
        #         envi.save_image(file_name, data, dtype='uint16',
        #                         interleave='bil', ext='.raw', metadata=md,
        #                         force=overwrite)
        #         break
        #     except envi.EnviException:
        #         new_name = input((f"File '{file_name}' exists. Enter new "
        #                           f"name or leave blank to overwrite: "))
        #         new_name = new_name.strip()
        #         if new_name:
        #             file_name = new_name
        #         else:
        #             overwrite = True
        # if verbose:
        #     print(f"Image saved as {file_name}.")
        # return data, md

    def capture_save(self, file_name, ranges, velocity=None, flip=False,
                     verbose=True, overwrite=False):
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
            start: start position of stage (in mm)
            stop: stop position of stage (in mm)
            overwrite: overwrite existing files without prompt

        Kwargs:
            velocity: stage velocity (in mm/s)
            flip: flip order of columns in each frame
            verbose: print progress messages
        """
        acq_time = datetime.now()
        if not isinstance(ranges[0], tuple) and not isinstance(ranges[0], list):
            ranges = [ranges]
        data = self.capture(ranges, velocity=velocity, flip=flip,
                            verbose=verbose)
        start = ranges[0][0]
        stop = ranges[-1][1]
        md = {
            'acquisition time': acq_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'description': "Image captured with Basler piA1600-35gm\n",
            'reflectance scale factor': self.ref_scale_factor,
            'wavelength': self.wl
        }
        while True:
            file_name = self._process_file_name(file_name, acq_time, start,
                                                stop, velocity, data.shape)
            try:
                envi.save_image(file_name, data, dtype='uint16',
                                interleave='bil', ext='.raw', metadata=md,
                                force=overwrite)
                break
            except envi.EnviException:
                new_name = input((f"File '{file_name}' exists. Enter new "
                                  f"name or leave blank to overwrite: "))
                new_name = new_name.strip()
                if new_name:
                    file_name = new_name
                else:
                    overwrite = True
        if verbose:
            print(f"Image saved as {file_name}.")
        return data, md

    def capture(self, ranges, velocity=None, flip=False, verbose=True):
        """Capture a full hypersepectral image.

        Args:
            start: start position of stage (in mm)
            stop: stop position of stage (in mm)

        Kwargs:
            velocity: stage velocity (in mm/s)
            flip: flip order of columns in each frame
            verbose: print progress messages
        """
        # TODO: Look into https://docs.baslerweb.com/overlapping-image-acquisition
        # TODO: 8-bit mode
        self.set_hardware_values()
        if not velocity:
            velocity = self.stage.default_velocity
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
                print(f"Imaging {d} mm at {velocity} mm/s (≈{t} s)")
                now = datetime.now().strftime("%H:%M:%S")
                print(f"Starting image capture at {now}...")
                print("Positioning stage...")
            for r in ranges:
                start = r[0]
                stop = r[1]
                self.stage.move_to(start, block=True)
                self.stage.move_to(stop, velocity=velocity)
                self.device.StartGrabbing()
                range_start_time = timeit.default_timer()
                while self.stage.is_moving():
                    grab = self.device.RetrieveResult(
                        5000, pylon.TimeoutHandling_ThrowException)
                    if grab.GrabSucceeded():
                        frames.append(grab.Array)
                        n_frames += 1
                    else:
                        print("Error: ", grab.ErrorCode, grab.ErrorDescription)
                    grab.Release()
                capture_time += timeit.default_timer() - range_start_time
                self.device.StopGrabbing()
        finally:
            total_time = timeit.default_timer() - total_start_time
            self.device.StopGrabbing()
            self.device.Close()
        if verbose:
            print(f"Total time {total_time:.2f} s")
            print((f"{n_frames} frames captured in {capture_time:.2f} s "
                   f"({n_frames/capture_time:.2f} fps)"))
        data = np.rot90(np.array(frames, dtype=np.uint16), axes=(1, 2))
        if flip:
            data = np.fliplr(data)
        return data

    def _process_file_name(self, fn, acq_time, start, stop, vel, shape):
        # TODO: This should really be separate
        fields = {
            "date": acq_time.strftime("%Y-%m-%d"),
            "time": acq_time.strftime("%H:%M:%S"),
            "exp": f"{self.exp}",
            "bin": f"{self.binning}",
            "gain": f"{self.get_actual_gain():.2f}",
            "raw_gain": f"{self.raw_gain}",
            "mode": "12-bit" if self.mode_12bit else "8-bit",
            "start": f"{start}",
            "stop": f"{stop}",
            "travel": f"{abs(start - stop)}",
            "vel": f"{vel}",
            "frames": f"{shape[0]}",
            "samples": f"{shape[1]}",
            "bands": f"{shape[2]}"
        }
        for field in fields:
            fn = fn.replace(f"{{{field}}}", fields[field])
        if not fn.endswith(".hdr"):
            fn = fn + ".hdr"
        if "{n}" in fn:
            n = 0
            while True:
                test_fn = fn.replace("{n}", str(n))
                if not os.path.exists(test_fn):
                    return test_fn
                n += 1
        return fn

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
            f"Reflectance scale factor: {self.ref_scale_factor}",
            f"Stage velocity: {self.stage._v} mm/s"
        ]
        return "\n".join(lines)


class MockCamera:
    def __init__(self, exp=4000, gain=100, binning=1, mode_12bit=True,
                 stage=None, device=None):
        self.stage = stage
        self.raw_gain_factor = 1
        self.exp = exp
        self.gain = gain
        self.binning = binning
        self.mode_12bit = mode_12bit
        self.wl = None
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
        img = envi.open(file_name)
        self.result_image = img.asarray()
        self.ref_scale_factor = img.scale_factor
        self.nbands = img.nbands
        self.wl = img.bands.centers
        self._current_frame = 0

    def capture_save(self, file_name, ranges, velocity=None, flip=False,
                     verbose=True, overwrite=False):
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
            start: start position of stage (in mm)
            stop: stop position of stage (in mm)
            overwrite: overwrite existing files without prompt

        Kwargs:
            velocity: stage velocity (in mm/s)
            flip: flip order of columns in each frame
            verbose: print progress messages
        """
        acq_time = datetime.now()
        if not isinstance(ranges[0], tuple) and not isinstance(ranges[0], list):
            ranges = [ranges]
        data = self.capture(ranges, velocity=velocity, flip=flip,
                            verbose=verbose)
        start = ranges[0][0]
        stop = ranges[-1][1]
        md = {
            'acquisition time': acq_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'description': "Image captured with Basler piA1600-35gm\n",
            'reflectance scale factor': self.ref_scale_factor,
            'wavelength': self.wl if self.wl else [x+1 for x in range(self.nbands)]
        }
        while True:
            file_name = self._process_file_name(file_name, acq_time, start,
                                                stop, velocity, data.shape)
            try:
                envi.save_image(file_name, data, dtype='uint16',
                                interleave='bil', ext='.raw', metadata=md,
                                force=overwrite)
                break
            except envi.EnviException:
                new_name = input((f"File '{file_name}' exists. Enter new "
                                  f"name or leave blank to overwrite: "))
                new_name = new_name.strip()
                if new_name:
                    file_name = new_name
                else:
                    overwrite = True
        if verbose:
            print(f"Image saved as {file_name}.")
        return data, md

    def capture(self, ranges, velocity=None, flip=False, verbose=True):
        """Simulate capturing a full hypersepectral image.

        Args:
            start: start position of stage (in mm)
            stop: stop position of stage (in mm)

        Kwargs:
            velocity: stage velocity (in mm/s)
            flip: flip order of columns in each frame
            verbose: print progress messages
        """
        if not isinstance(ranges[0], tuple):
            ranges = [ranges]
        for r in ranges:
            start = r[0]
            stop = r[1]
            self.stage.move_to(start, block=True)
            self.stage.move_to(stop, velocity=velocity, block=True)
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
        img = np.asarray(img * 255, dtype="uint8")
        # time.sleep(self.exp/1000000)
        return img

    def _process_file_name(self, fn, acq_time, start, stop, vel, shape):
        fields = {
            "date": acq_time.strftime("%Y-%m-%d"),
            "time": acq_time.strftime("%H:%M:%S"),
            "exp": f"{self.exp}",
            "bin": f"{self.binning}",
            "gain": f"{self.get_actual_gain():.2f}",
            "raw_gain": f"{self.raw_gain}",
            "mode": "12-bit" if self.mode_12bit else "8-bit",
            "start": f"{start}",
            "stop": f"{stop}",
            "travel": f"{abs(start - stop)}",
            "vel": f"{vel}",
            "frames": f"{shape[0]}",
            "samples": f"{shape[1]}",
            "bands": f"{shape[2]}"
        }
        for field in fields:
            fn = fn.replace(f"{{{field}}}", fields[field])
        if not fn.endswith(".hdr"):
            fn = fn + ".hdr"
        if "{n}" in fn:
            n = 0
            while True:
                test_fn = fn.replace("{n}", str(n))
                if not os.path.exists(test_fn):
                    return test_fn
                n += 1
        return fn
