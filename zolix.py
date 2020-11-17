import serial
from serial.serialutil import SerialException
from serial.tools import list_ports


class Scanner:
    def __init__(self, com_port, velocity=20, length=196, max_velocity=50):
        self.length = length
        self.max_velocity = max_velocity
        self.default_velocity = velocity
        self.mm_to_steps = 12734
        self.write_terminator = serial.CR
        self.read_terminator = serial.LF
        try:
            self.ser = serial.Serial(com_port)
            if not self.ser.is_open:
                self.ser.open()
            self.set_velocity(velocity)
            self.reset()
        except SerialException as e:
            if e.errno == 13:
                raise IOError((f"Can't open port '{com_port}' - on Linux, "
                               "add user to dialup group (`sudo usermod -a "
                               "-G dialout USER_NAME`)")) from e
            raise

    def _write(self, cmd):
        # Write command terminated with CR
        self.ser.write(cmd + self.write_terminator)
        # Scanner returns the same command again, which we don't care about
        self.ser.read_until(self.read_terminator)

    def _read(self):
        return self.ser.read_until(self.read_terminator).strip()

    def is_moving(self):
        self._write(b'PR MV')
        return int(self._read())

    def wait_while_moving(self):
        while self.is_moving():
            continue

    def reset(self):
        self._write(b'S4=1,1,1')
        self._write(b'HM 1')
        self.wait_while_moving()
        self._write(b'P=0')

    def set_velocity(self, velocity):
        if velocity < 0 or velocity > self.max_velocity:
            raise ValueError(("Velocity must be between 0 and "
                              f"{self.max_velocity} mm/s"))
        velocity_steps = round(velocity * self.mm_to_steps)
        self._write(b'VM {0}'.format(velocity_steps))
        self._v = velocity

    def move_to(self, target, velocity=None, block=False):
        if velocity:
            self.set_velocity(velocity)
        if target < 0 or target > self.length:
            raise ValueError(f"Target must be between 0 and {self.length} mm")
        target_steps = round(target * self.mm_to_steps)
        self._write(b'MA {0}'.format(target_steps))
        if self._v != self.default_velocity:
            self.set_velocity(self.default_velocity)
        if block:
            self.wait_while_moving()


def auto_detect_port():
    ports = list_ports.comports()
    if not ports:
        raise IOError("No com ports found")
    # TODO: Check each available port to see if it's the scanner
    return ports[0]


if __name__ == "__main__":
    s = Scanner('/dev/ttyUSB0')
    s.scan(0, 50, 10)
