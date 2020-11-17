# PyHSI

Python modules for controlling hyperspectral equipment

## Pylon

Pylon is the API for working with Basler cameras. Set-up requires:

1) Install Pylon from [Basler's website](https://www.baslerweb.com/en/sales-support/downloads/software-downloads/pylon-6-1-1-linux-x86-64-bit/). (Free, but requires submitting contact details. On Linux, it looks like .deb package doesn't work - use the .tar.gz instead.)
2) Install pypylon (the Python wrapper) from [the GitHub repo](https://github.com/basler/pypylon). (Use the latest wheel. It's probably a good idea to set up a dedicated virtualenv or conda env with Python 3 for this.)
3) Configure static IPv4 address for ethernet connection to 169.254.1.5, with netmask 255.255.0.0, and gateway 169.254.1.2.
4) Run `basler_cam.connection_test()`.

## Zolix

`zolix.py` contains code for operating the Zolix translation stage. This consists mainly of the `Scanner` class, which has methods such as `move_to()`. When first getting set up, run `Scanner.reset()`.
