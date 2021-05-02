"""Controller for Zolix TSA200-B and TSA200-BF linear translation stages.

The main component is the `TSA200` class, which represents a connection to the
translation stage. This can probably be used for other Zolix translation stages
by supplying the length argument, but has only been tested on TSA200 series.

Usage example:

    stage = TSA200()
    stage.move_to(100, velocity=10, block=True)
    stage.reset()
"""

import serial
from serial.serialutil import SerialException
from serial.tools import list_ports
import time
import timeit


class TSA200:
    """Represents an instance of the Zolix TSA200 linear stage."""

    def __init__(self, velocity=20, length=196, max_velocity=40,
                 com_port=None, device_name="USB2Serial 1xRS422/485"):
        """Connects to the stage and resets it.

        Kwargs:
            velocity: the default velocity in mm/s.
            length: the traversable length of the stage in mm. [Default 196]
            max_velocity: the maximum allowed velocity.
            com_port: the name of the COM port to connect to (e.g. `COM3` on
                Windows, `/dev/ttyUSB0` on Linux. If not specified, the port
                will be detected automatically.
            device_name: device name to look up if com_port is not specified.
                This is likely to be the serial adapter, rather than the stage
                itself.
        """
        if not com_port:
            com_port = self._auto_detect_port(device_name)
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

    def _auto_detect_port(self, product):
        """Scan for active com ports that match the device.

        Args:
            product: name of product against which to match the port.
        """
        ports = list_ports.comports()
        for port in ports:
            if port.product == product:
                self.com_port = port.device
                return
        raise IOError(f"No port with device '{product}' connected.")

    def _write(self, cmd):
        # Write command terminated with CR
        self._serial.write(cmd + self._write_terminator)
        # Stage echos the input command back, which we don't care about
        self._serial.read_until(self._read_terminator)

    def _read(self):
        return self._serial.read_until(self._read_terminator).strip()

    def get_position(self):
        # TODO
        pass

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
        stage has reset.
        """
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
            velocity: velocity at which to move the stage in mm/s
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
            target: Target position in mm

        Kwargs:
            velocity: the velocity at which to move in mm/s. If None,
                defaults to the last set velocity. Velocity returns to its old
                value after execution - to change velocity for multiple move
                instructions, use `set_velocity()`.
            block: if True, method will not return until after the move is
                completed.
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

    def move_to_timed(self, target, velocity=None):
        """Move the stage to the target position and print timing information.

        Args:
            target: target position in mm

        Kwargs:
            velocity: the velocity at which to move in mm/s. If None,
                defaults to the last set velocity. Velocity returns to its old
                value after execution - to change velocity for multiple move
                instructions, use `set_velocity()`.
        """
        if not velocity:
            velocity = self._v
        print(f"Moving to {target} mm at velocity {velocity} mm/s...")
        # TODO
        # d = abs(target - self.get_position())
        # print(f"Distance {d} mm, should take {d/velocity:.2f} s")
        start = timeit.default_timer()
        self.move_to(target, velocity=velocity, block=True)
        time_taken = timeit.default_timer() - start
        print(f"Move completed in {time_taken:.2f} seconds.")


class DummyStage:
    """Simulates the behaviour of a Zolix TSA200 linear translation stage."""

    def __init__(self, com_port=None, velocity=20, length=196,
                 max_velocity=40):
        self._v = velocity
        self.default_velocity = velocity
        self.length = length
        self.max_velocity = max_velocity
        self._moving_until = False
        self._pos = 0

    def get_position(self):
        # TODO
        pass

    def wait_while_moving(self):
        """Block execution until the stage is no longer moving."""
        while self.is_moving():
            continue

    def reset(self):
        """Reset stage to 0 mm."""
        time.sleep(0.5)
        self.move_to(0, block=True)

    def is_moving(self):
        """Returns True if the stage is currently moving, False otherwise."""
        if not self._moving_until:
            return False
        return timeit.default_timer() < self._moving_until

    def set_velocity(self, velocity):
        """Set the velocity for subsequent calls to `move_to()`.

        Args:
            velocity: velocity at which to move the stage in mm/s
        """
        if velocity < 0 or velocity > self.max_velocity:
            raise ValueError(("Velocity must be between 0 and "
                              f"{self.max_velocity} mm/s"))
        self._v = velocity

    def move_to(self, target, velocity=None, block=False):
        """Move the stage to the target position.

        Args:
            target: target position in mm

        Kwargs:
            velocity: the velocity at which to move in mm/s. If None,
                defaults to the last set velocity. Velocity returns to its old
                value after execution - to change velocity for multiple move
                instructions, use `set_velocity()`.
            block: if True, method will not return until after the move is
                completed.
        """
        if target < 0 or target > self.length:
            raise ValueError(f"Target must be between 0 and {self.length} mm")
        old_v = self._v
        if velocity:
            self.set_velocity(velocity)
        sleep_time = abs(self._pos - target) / self._v
        if (block):
            time.sleep(sleep_time)
        else:
            self._moving_until = timeit.default_timer() + sleep_time
        self._pos = target
        if self._v != old_v:
            self.set_velocity(old_v)