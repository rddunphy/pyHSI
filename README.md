# PyHSI

Python modules for controlling hyperspectral imaging equipment


## Installation

* Download the repository
* Requires Python 3 and Pip
* Installing in a dedicated virtualenv or Conda environment is recommeded
* Run `pip install .` in the root directory
* May require installing Pylon from [Basler's website](https://www.baslerweb.com/en/sales-support/downloads/software-downloads/pylon-6-1-1-linux-x86-64-bit/). (Free, but requires submitting contact details. On Linux, it looks like the .deb package doesn't work - use the .tar.gz instead.)
* Configure static IPv4 address for ethernet connection to 169.254.1.5, with netmask 255.255.0.0, and gateway 169.254.1.2.


## Usage

### `pyhsi.cameras`

Currently contains a single class, `BaslerCamera`, representing the [Basler
piA1600-35gm](https://www.baslerweb.com/en/products/cameras/area-scan-cameras/pilot/pia1600-35gc/).

Usage example:

```python
from pyhsi.cameras import BaslerCamera

# Instantiate camera with 4x4 pixel binning and a raw gain value of 400
cam = BaslerCamera(gain=400, binning=4)

# Show live preview from camera - press Escape to exit
cam.preview()

# Show waterfall preview - press Escape to exit
cam.waterfall()

# Capture an image of translation stage from 0 to 120 mm at 10 mm/s, 
# and save the result to "sample_2000-01-01_12:00:00.hdr"
cam.capture_save("sample_{date}_{time}", 0, 120, velocity=10)
```


### `pyhsi.stages`

Module for linear translation stages. This module currently has two classes:

* `TSA200` for the Zolix TSA200-B and TSA200-BF linear translation stages
* `DummyStage` for simulating a stage when no physical connection is available


### `pyhsi.utils`

Utility tools for displaying and working with HSI files.

* `get_wavelength(n_bandx, min_wl, max_wl)` - returns list of equidistant
  wavelengths from the specified range
* `nearest_band(wavelengths, target)` - returns index of the wavelengths that
  is closest to target wavelength
* `highlight_saturated(img)` - takes a greyscale image and returns an RGB
  representation, with light-saturated pixels highlighted in red and
  dark-saturated pixels highlighted in blue
* `image_play(img)` - play video representation of hyperspectral image


## Capturing HSI data

Workflow for caputuring images with the Zolix TSA200 and Basler piA1600:

* Connect Zolix translation stage to power outlet and USB port
* Connect Basler camera to power outlet and ethernet port
* Connect enclosure to power outlet and check that lights turn on when door is
  closed
* Adjust exposure using `camera.preview()` so that there are no saturated
  pixels when imaging a white calibration tile
* Adjust focus by inserting extension rings or adjusting height of the camera
  and/or sample using `camera.waterfall()`
* Capture dark reference image using `camera.capture_save("dark_ref", 0,
  100)` with the lens cap on
* Place calibration tile on sample tray perpendicular to direction of travel of
  the translation stage
* Place lid fully over the enclosure to block out ambient light
* Capture images of samples with `camera.capture_save("sample_name", 0, 100,
  velocity=10)`, with door fully closed to turn on halogen lights
* If necessary, adjust velocity to ensure square pixels
