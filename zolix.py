"""Controller for Zolix TSA200-B and TSA200-BF linear translation stages.

The main component is the `TSA200` class, which represents a connection to the
translation stage. This can probably be used for other Zolix translation stages
by supplying the length argument, but has only been tested on TSA200 series.

Usage example:

    s = TSA200()
    s.move_to(100, velocity=10, block=True)
    s.reset()
"""

import serial
from serial.serialutil import SerialException
from serial.tools import list_ports
import time


class TSA200:
    """Represents an instance of the Zolix TSA200 linear stage."""

    def __init__(self, com_port=None, velocity=20, length=196,
                 max_velocity=40):
        """Connects to the stage and resets it.

        Kwargs:
            - com_port: The name of the COM port to connect to (e.g. `COM3` on
                Windows, `/dev/ttyUSB0` on Linux. If not specified, the port
                will be detected automatically. [Default None]
            - velocity: The default velocity in mm/s. [Default 20]
            - length: The traversable length of the stage in mm. [Default 196]
            - max_velocity: The maximum allowed velocity. [Default 40]
        """
        if not com_port:
            com_port = auto_detect_port()
        self.length = length
        self.max_velocity = max_velocity
        self.default_velocity = velocity
        self._v = velocity
        self._mm_to_steps = 12734
        self._write_terminator = serial.CR
        self._read_terminator = serial.LF
        try:
            self._serial = serial.Serial(com_port)
            if not self._serial.is_open:
                self._serial.open()
            self.reset()
        except SerialException as e:
            if e.errno == 13:
                raise IOError((f"Can't open port '{com_port}' - on Linux, "
                               "add user to dialup group (`sudo usermod -a "
                               "-G dialout USER_NAME`)")) from e
            raise

    def _write(self, cmd):
        # Write command terminated with CR
        self._serial.write(cmd + self._write_terminator)
        # Stage echos the input command back, which we don't care about
        self._serial.read_until(self._read_terminator)

    def _read(self):
        return self._serial.read_until(self._read_terminator).strip()

    def is_moving(self):
        """Returns True if the stage is currently moving, False otherwise."""
        self._write(b'PR MV')  # Print Moving - returns 1 if moving, else 0
        return bool(int(self._read()))

    def wait_while_moving(self):
        """Block execution until the stage is no longer moving."""
        while self.is_moving():
            continue

    def reset(self):
        """Reset stage to 0 mm.

        This should be done once when first connecting prior to running other
        move commands, in order to ensure that the target positions used are
        relative to the actual start of the stage. For this reason, it is
        called from `__init__()`. This function will block execution until the
        stage has reset."""
        self._write(b'ER=0')
        time.sleep(0.5)  # Not sure why this is required...
        self._write(b'RC=75')
        self.set_velocity(self._v)
        self._write(b'S4=1,1,1')
        self._write(b'HM 1')
        self.wait_while_moving()
        self._write(b'P=0')

    def set_velocity(self, velocity):
        """Set the velocity for subsequent calls to `move_to()`.

        Args:
            - velocity: Velocity in mm/s
        """
        if velocity < 0 or velocity > self.max_velocity:
            raise ValueError(("Velocity must be between 0 and "
                              f"{self.max_velocity} mm/s"))
        velocity_steps = round(velocity * self._mm_to_steps)
        self._write(b'VM %d' % velocity_steps)  # Velocity Maximum
        self._write(b'VI %d' % velocity_steps)  # Velocity Initial
        self._v = velocity

    def move_to(self, target, velocity=None, block=False):
        """Move the stage to the target position.

        Args:
            - target: Target position in mm
        Kwargs:
            - velocity: The velocity at which to move in mm/s. If None,
                defaults to the last set velocity. Velocity returns to its old
                value after execution - to change velocity for multiple move
                instructions, use `set_velocity()`. [Default: None]
            - block: If True, method will not return until after the move is
                completed. [Default: False]
        """
        old_v = self._v
        if velocity:
            self.set_velocity(velocity)
        if target < 0 or target > self.length:
            raise ValueError(f"Target must be between 0 and {self.length} mm")
        target_steps = round(target * self._mm_to_steps)
        self._write(b'MA %d' % target_steps)
        if self._v != old_v:
            self.set_velocity(old_v)
        if block:
            self.wait_while_moving()


def auto_detect_port(product="USB2Serial 1xRS422/485"):
    """Scan for active com ports that match the device.

    Kwargs:
        - product: Name of product against which to match the port. This is
            likely to be the serial adapter, rather than the stage itself.
            [Default: "USB2Serial 1xRS422/485"]
    """
    ports = list_ports.comports()
    for port in ports:
        if port.product == product:
            return port.device
    raise IOError("Could not find port with device '%s' connected." % product)


def test():
    """Run short test sequence to make sure that everything is working."""
    try:
        port = auto_detect_port()
        print("Found stage on port '%s'." % port)
    except IOError:
        print("Stage not connected.")
        exit(1)
    print("Setting up stage...")
    start = time.time()
    s = TSA200(com_port=port)
    end = time.time()
    print("Stage ready in %.2f seconds" % (end - start))
    time.sleep(0.5)
    print("Moving to 100 mm at velocity 10 mm/s...")
    start = time.time()
    s.move_to(100, velocity=10, block=True)
    end = time.time()
    print("Move completed in %.2f seconds." % (end - start))


if __name__ == "__main__":
    test()
