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

    def wait_while_moving(self):
        while True:
            self._write(b'PR MV')
            try:
                mv = int(self._read())
                if mv == 0:
                    return
            except ValueError:
                # Response wasn't an integer
                pass

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

    def move_to(self, target):
        if target < 0 or target > self.length:
            raise ValueError(f"Target must be between 0 and {self.length} mm")
        target_steps = round(target * self.mm_to_steps)
        self._write(b'MA {0}'.format(target_steps))
        self.wait_while_moving(s)

    def scan(self, start, end, velocity=None):
        if not velocity:
            velocity = self.default_velocity
        self.set_velocity(self.default_velocity)
        self.move_to(start)
        self.set_velocity(velocity)
        self.move_to(end)
        self.set_velocity(self.default_velocity)
        self.move_to(start)


def auto_detect_port():
    ports = list_ports.comports()
    if not ports:
        raise IOError("No com ports found")
    # TODO: Check each available port to see if it's the scanner
    return ports[0]


if __name__ == "__main__":
    s = Scanner('/dev/ttyUSB0')
    s.scan(0, 50, 10)
