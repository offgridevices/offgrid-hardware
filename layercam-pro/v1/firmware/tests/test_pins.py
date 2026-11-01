"""The software's pins against the schematic (firmware/pincheck.py, which the
board build runs too through src/check_firmware.py).  The last test breaks
copies of the device tree and the circuit to prove the check can fail."""
import os, unittest

import pincheck
from layercam import board

HERE = os.path.dirname(os.path.abspath(__file__))
CIRCUIT = os.path.join(HERE, '..', '..', 'src', 'circuit.py')
DTS = os.path.join(HERE, '..', 'dts', pincheck.DTS)


def problems(circuit, dts):
    return [what for ok, what in pincheck.results(circuit, dts, board) if not ok]


class Pins(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(CIRCUIT) as f:
            cls.circuit = f.read()
        with open(DTS) as f:
            cls.dts = f.read()

    def test_gpio_numbers(self):
        self.assertEqual(board.gpio_number('GPIO1_A0'), 32)
        self.assertEqual(board.gpio_number('GPIO1_C0'), 48)
        self.assertEqual(board.gpio_number('GPIO3_C5'), 117)

    def test_against_circuit(self):
        res = pincheck.results(self.circuit, self.dts, board)
        self.assertGreaterEqual(len(res), 25)
        self.assertEqual(problems(self.circuit, self.dts), [])

    def test_check_can_fail(self):
        broken = self.dts.replace('<&gpio1 RK_PC0 GPIO_ACTIVE_HIGH>', '<&gpio1 RK_PC1 GPIO_ACTIVE_HIGH>')
        broken = broken.replace('pwm3m1_pins', 'pwm3m0_pins')
        self.assertEqual(len(problems(self.circuit, broken)), 2)
        swapped = self.circuit.replace("'IRCUT_A',        # GPIO1_A0", "'IRCUT_A',        # GPIO1_A1")
        self.assertNotEqual(swapped, self.circuit)
        self.assertTrue(problems(swapped, self.dts))
        # a button back on the BOOT pad, the evb's ADC keys back, the USB port made a host
        tp = "add('TP', 'TP', {'1': 'BOOT_SW'}, B, 'boot pad', ref='TP5')"
        self.assertIn(tp, self.circuit)
        button = self.circuit.replace(tp, "add('SW', 'TS24CA', {'1': 'BOOT_SW', '2': GND}, B, 'button', ref='SW1')")
        self.assertEqual(len(problems(button, self.dts)), 2)
        keys = self.dts.replace('/delete-node/ adc-keys;', '')
        host = self.dts.replace('dr_mode = "peripheral"', 'dr_mode = "host"')
        self.assertEqual(len(problems(self.circuit, keys)), 1)
        self.assertEqual(len(problems(self.circuit, host)), 1)

    def test_pro_wifi_and_sensor_checks_can_fail(self):
        """v1's 200 ms pwrseq, a bcmdhd node put back, the sensor's two
        control lines swapped, v1's sensor, the C6's EN moved in circuit.py."""
        def n(circuit, dts):
            return len(problems(circuit, dts))
        self.assertEqual(n(self.circuit, self.dts.replace('post-power-on-delay-ms = <1500>', 'post-power-on-delay-ms = <200>')), 1)
        self.assertEqual(n(self.circuit, self.dts.replace('espressif,full-chip-reset;', '')), 1)
        bcm = self.dts.replace('&cpu0 {', 'wlan { compatible = "wlan-platdata"; };\n&cpu0 {')
        self.assertEqual(n(self.circuit, bcm), 1)
        swapped = (self.dts.replace('reset-gpios = <&gpio3 RK_PC5', 'X1').replace('pwdn-gpios = <&gpio3 RK_PC6', 'X2')
                   .replace('X1', 'reset-gpios = <&gpio3 RK_PC6').replace('X2', 'pwdn-gpios = <&gpio3 RK_PC5'))
        self.assertNotEqual(swapped, self.dts)
        self.assertEqual(n(self.circuit, swapped), 2)
        old = self.dts.replace('"smartsens,sc4336h"', '"smartsens,sc3336"')
        self.assertEqual(n(self.circuit, old), 1)
        boot = self.dts.replace('<0 RK_PA2 RK_FUNC_GPIO &pcfg_pull_up>', '<0 RK_PA2 RK_FUNC_GPIO &pcfg_pull_none>')
        self.assertEqual(n(self.circuit, boot), 1)
        uart = self.dts.replace('pinctrl-0 = <&uart1m0_xfer>;', 'pinctrl-0 = <&uart1m0_xfer &uart1m0_ctsn>;')
        self.assertEqual(n(self.circuit, uart), 1)
        en = self.circuit.replace("'74': 'WIFI_EN',        # GPIO1_A2", "'74': 'WIFI_EN',        # GPIO1_A3")
        self.assertNotEqual(en, self.circuit)
        self.assertTrue(problems(en, self.dts))

    def test_sdk_settings(self):
        res = pincheck.sdk_results(os.path.join(HERE, '..'), board)
        self.assertGreaterEqual(len(res), 8)
        self.assertEqual([w for ok, w in res if not ok], [])
        self.assertEqual(board.IQ_FILE, 'sc4336h_LayerCamPro_LCP-F16.json')
        self.assertEqual((board.SENSOR_WIDTH, board.SENSOR_HEIGHT), (2560, 1440))

    def test_board_build_entry(self):
        """src/check_firmware.run, as src/verify.py calls it."""
        import importlib.util
        path = os.path.join(HERE, '..', '..', 'src', 'check_firmware.py')
        spec = importlib.util.spec_from_file_location('check_firmware', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        res = mod.run(os.path.join(HERE, '..'))
        self.assertTrue(res and all(ok for ok, _ in res), [w for ok, w in res if not ok])
        self.assertTrue(all(isinstance(ok, bool) and isinstance(w, str) for ok, w in res))


if __name__ == '__main__':
    unittest.main()
