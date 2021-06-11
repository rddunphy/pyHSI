import serial
import unittest
from unittest.mock import call, MagicMock

from pyhsi.stages import TSA200


class TestTSA200(unittest.TestCase):
    def setUp(self):
        self.mock_port = MagicMock()
        self.mock_port.read_until = MagicMock(return_value=b'0' + serial.LF)
        self.stage = TSA200(velocity=20, max_velocity=40, port=self.mock_port)

    def test_is_moving(self):
        self.assertFalse(self.stage.is_moving())
        self.mock_port.write.assert_called_with(b'PR MV' + serial.CR)
        self.mock_port.read_until = MagicMock(return_value=b'1' + serial.LF)
        self.assertTrue(self.stage.is_moving())

    def test_set_velocity(self):
        self.stage.set_velocity(30)
        calls = [
            call.write(b'VM 382020' + serial.CR),
            call.read_until(serial.LF),
            call.write(b'VI 95505' + serial.CR),
            call.read_until(serial.LF)
        ]
        self.mock_port.assert_has_calls(calls, any_order=False)
        self.mock_port.write.assert_called_with(b'VI 95505' + serial.CR)
        self.assertEqual(self.stage._v, 30)

    def test_set_velocity_illegal(self):
        self.assertRaises(ValueError, self.stage.set_velocity, 45)
        self.assertRaises(ValueError, self.stage.set_velocity, -1)

    def test_move_to(self):
        self.stage.set_velocity(20)
        self.stage.move_to(100, velocity=30)
        calls = [
            call.write(b'VM 382020' + serial.CR),
            call.read_until(serial.LF),
            call.write(b'VI 95505' + serial.CR),
            call.read_until(serial.LF),
            call.write(b'MA 1273400' + serial.CR),
            call.read_until(serial.LF),
        ]
        self.mock_port.assert_has_calls(calls, any_order=False)
        self.assertEqual(self.stage._v, 20)

    def test_move_to_illegal(self):
        self.assertRaises(ValueError, self.stage.move_to, 200)
        self.assertRaises(ValueError, self.stage.move_to, -1)


if __name__ == "__main__":
    unittest.main()
