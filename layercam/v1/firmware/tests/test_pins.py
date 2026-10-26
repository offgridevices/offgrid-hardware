"""The software's pins against the schematic (firmware/pincheck.py, which the
board build runs too through src/check_firmware.py).  The last test breaks
copies of the device tree and the circuit to prove the check can fail."""
import os, unittest

import pincheck
from layercam import board

HERE = os.path.dirname(os.path.abspath(__file__))
CIRCUIT = os.path.join(HERE, '..', '..', 'src', 'circuit.py')
DTS = os.path.join(HERE, '..', 'dts', 'rv1106g-layercam-v1.dts')


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
