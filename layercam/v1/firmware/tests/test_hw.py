"""Light sensor hysteresis, IR plan, button, status LED, and the sysfs writes
(against a fake /sys tree)."""
import os, tempfile, unittest
from unittest import mock

from layercam import board, hw


class DayNight(unittest.TestCase):
    def test_hysteresis_and_hold(self):
        d = hw.DayNight(dark_v=0.10, light_v=0.25, hold_s=5)
        self.assertEqual(d.feed(0.05, 0), 'day')        # dark, but not yet for 5 s
        self.assertEqual(d.feed(0.05, 4.9), 'day')
        self.assertEqual(d.feed(0.05, 5.0), 'night')
        self.assertEqual(d.feed(0.20, 6), 'night')       # between the thresholds: no change
        self.assertEqual(d.feed(0.20, 60), 'night')
        self.assertEqual(d.feed(0.30, 61), 'night')
        self.assertEqual(d.feed(0.30, 66), 'day')

    def test_flicker_does_not_switch(self):
        d = hw.DayNight(hold_s=5)
        t = 0
        for i in range(20):              # 2 s dark, 1 s light: the timer starts again each time
            for v in (0.05, 0.05, 0.4):
                self.assertEqual(d.feed(v, t), 'day')
                t += 1

    def test_ir_plan(self):
        self.assertEqual(hw.ir_plan('auto', 'night', False), ('night', True))
        self.assertEqual(hw.ir_plan('auto', 'day', True), ('day', False))
        self.assertEqual(hw.ir_plan('printing', 'night', False), ('night', False))
        self.assertEqual(hw.ir_plan('printing', 'night', True), ('night', True))
        self.assertEqual(hw.ir_plan('printing', 'day', True), ('day', False))
        self.assertEqual(hw.ir_plan('day', 'night', True), ('day', False))
        self.assertEqual(hw.ir_plan('night', 'day', False), ('night', True))
        self.assertEqual(hw.ir_plan('off', 'night', True), ('day', False))


class ButtonAndLed(unittest.TestCase):
    def test_short_long(self):
        b = hw.Button(long_s=5)
        self.assertIsNone(b.feed(True, 0))
        self.assertEqual(b.feed(False, 0.3), 'short')
        self.assertIsNone(b.feed(True, 10))
        self.assertIsNone(b.feed(True, 14.9))
        self.assertEqual(b.feed(True, 15.0), 'long')     # fires while held
        self.assertIsNone(b.feed(True, 20))
        self.assertIsNone(b.feed(False, 21))             # and not again on release

    def test_bounce_ignored(self):
        b = hw.Button()
        b.feed(True, 0)
        self.assertIsNone(b.feed(False, 0.01))

    def test_led_priority(self):
        self.assertEqual(hw.led_state(True, False, True, True), 'setup')
        self.assertEqual(hw.led_state(False, False, True, True), 'offline')
        self.assertEqual(hw.led_state(False, True, True, True), 'error')
        self.assertEqual(hw.led_state(False, True, False, True), 'recording')
        self.assertEqual(hw.led_state(False, True, False, False), 'ok')
        for p in hw.PATTERNS.values():
            self.assertTrue(all(on >= 0 and off >= 0 for on, off in p))


class Sysfs(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        adc = self.root + board.ADC_DEVICE
        os.makedirs(adc)
        self.w(adc + '/in_voltage_scale', '1.7578125')           # 1800 mV / 1024
        self.w(adc + '/in_voltage0_raw', '1023')
        self.w(adc + '/in_voltage1_raw', '57')
        os.makedirs(self.root + '/sys/class/gpio')
        for n in (board.IRCUT_A, board.IRCUT_B):
            os.makedirs(self.root + '/sys/class/gpio/gpio%d' % n)
        self.chip = self.root + '/sys/devices/platform/ff350030.pwm/pwm/pwmchip3'
        os.makedirs(self.chip + '/pwm0')
        os.makedirs(self.root + board.LED_STATUS)
        self.hw = hw.Sysfs(self.root)

    def w(self, p, v):
        with open(p, 'w') as f:
            f.write(v)

    def r(self, p):
        with open(self.root + p) as f:
            return f.read()

    def test_adc(self):
        self.assertFalse(self.hw.button_pressed())
        self.w(self.root + board.ADC_DEVICE + '/in_voltage0_raw', '10')
        self.assertTrue(self.hw.button_pressed())
        self.assertAlmostEqual(self.hw.light_volts(), 57 * 1.7578125 / 1000)

    def test_ircut_pulse_then_off(self):
        writes = []
        real = hw._write
        with mock.patch('layercam.hw._write', side_effect=lambda p, v: (writes.append((p, v)), real(p, v))), \
                mock.patch('layercam.hw.time.sleep'):
            self.hw.ircut('night')
        vals = [(os.path.basename(os.path.dirname(p)), v) for p, v in writes if p.endswith('/value')]
        a, b = 'gpio%d' % board.IRCUT_A, 'gpio%d' % board.IRCUT_B
        self.assertEqual(vals, [(a, 1), (b, 0), (a, 0), (b, 0)])

    def test_pwm_and_led(self):
        self.hw.ir_leds(50)
        base = '/sys/devices/platform/ff350030.pwm/pwm/pwmchip3/pwm0'
        self.assertEqual(self.r(base + '/period'), str(board.PWM_IR_PERIOD_NS))
        self.assertEqual(self.r(base + '/duty_cycle'), str(board.PWM_IR_PERIOD_NS // 2))
        self.assertEqual(self.r(base + '/enable'), '1')
        self.hw.ir_leds(0)
        self.assertEqual(self.r(base + '/enable'), '0')
        self.hw.set_led(True)
        self.assertEqual(self.r(board.LED_STATUS + '/brightness'), '1')

    def test_missing_hardware_is_quiet(self):
        h = hw.Sysfs(tempfile.mkdtemp())
        self.assertIsNone(h.light_volts())
        self.assertFalse(h.button_pressed())
        h.ir_leds(100)
        h.set_led(True)
        with mock.patch('layercam.hw.time.sleep'):
            h.ircut('day')


if __name__ == '__main__':
    unittest.main()
