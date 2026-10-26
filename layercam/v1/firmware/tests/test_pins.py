"""The software's pins against the schematic.

src/circuit.py is the source of truth: main_soc() names each SoC pin's net
and, in its comment, the pin's function (GPIO1_A0, SARADC_IN1, PWM3_IR_M1,
I2C4_SCL_M2...).  This reads that file as text (it is not changed, and
needs nothing installed) and checks layercam/board.py and
dts/rv1106g-layercam-v1.dts against it.  A test at the end breaks a copy of
the device tree to prove the check can fail.
"""
import os, re, unittest

from layercam import board

HERE = os.path.dirname(os.path.abspath(__file__))
CIRCUIT = os.path.join(HERE, '..', '..', 'src', 'circuit.py')
DTS = os.path.join(HERE, '..', 'dts', 'rv1106g-layercam-v1.dts')


def soc_pins(text):
    """net -> the function named in its comment, from main_soc()'s pin map."""
    body = text[text.index('def main_soc'):text.index("add('U', 'RV1106G3'")]
    out = {}
    for pin, net, comment in re.findall(r"'(\d+)':\s*'([A-Z0-9_]+)',\s*#\s*([^\n]*)", body):
        out[net] = comment
    return out


def gpio_ref(gpio):
    """'GPIO1_A0' -> ('1', 'RK_PA0') as the device tree writes it."""
    bank, pin = gpio[4:].split('_')
    return bank, 'RK_P' + pin


def check(circuit_text, dts_text):
    problems = []
    pins = soc_pins(circuit_text)

    def comment_gpio(net):
        m = re.search(r'GPIO\d_[A-D]\d', pins.get(net, ''))
        return m.group(0) if m else None

    # board.py's GPIOs are the ones circuit.py names
    for net, gpio in board.PINS.items():
        if net == 'IR_PWM':
            if 'PWM3_IR_M1' not in pins.get(net, ''):
                problems.append('IR_PWM is not on PWM3_IR_M1 in circuit.py')
            continue
        if comment_gpio(net) != gpio:
            problems.append('%s: board.py %s, circuit.py %s' % (net, gpio, comment_gpio(net)))

    # the device tree uses them where it should
    def has(pattern, what):
        if not re.search(pattern, dts_text):
            problems.append('device tree: ' + what)

    def gref(net):
        b, p = gpio_ref(board.PINS[net])
        return r'<&gpio%s %s ' % (b, p)

    has(r'status_led: status \{[^}]*gpios = ' + re.escape(gref('LED_STATUS')), 'status LED not on LED_STATUS')
    has(r'reset-gpios = ' + re.escape(gref('WL_REG_ON')) + 'GPIO_ACTIVE_LOW', 'WL_REG_ON not the SDIO power sequence')
    has(r'WIFI,host_wake_irq = ' + re.escape(gref('WL_HOST_WAKE')), 'WL_HOST_WAKE not the Wi-Fi interrupt')
    has(r'pwdn-gpios = ' + re.escape(gref('CAM_RST')), 'CAM_RST not the sensor power-down')
    has(r'BT,reset_gpio = ' + re.escape(gref('BT_REG_ON')), 'BT_REG_ON')
    has(r'BT,wake_gpio = ' + re.escape(gref('BT_WAKE')), 'BT_WAKE')
    has(r'BT,wake_host_irq = ' + re.escape(gref('BT_HOST_WAKE')), 'BT_HOST_WAKE')
    for net in ('IRCUT_A', 'IRCUT_B'):
        b, p = gpio_ref(board.PINS[net])
        has(r'<%s %s RK_FUNC_GPIO &pcfg_pull_down>' % (b, p), '%s not held low as a GPIO' % net)
    has(r'&pwm3 \{[^}]*pinctrl-0 = <&pwm3m1_pins>', 'PWM3 not on its M1 pin')
    if 'MIPI_CLK0_OUT' in pins.get('CAM_MCLK_SOC', '') or 'GPIO3_C4' in pins.get('CAM_MCLK_SOC', ''):
        has(r'pinctrl-0 = <&mipi_refclk_out0>', 'sensor clock not on mipi_refclk_out0 (GPIO3_C4)')
    else:
        problems.append('CAM_MCLK_SOC is not on MIPI_CLK0_OUT/GPIO3_C4 in circuit.py')
    if 'I2C4_SCL_M2' not in pins.get('CAM_SCL', '') or 'I2C4_SDA_M2' not in pins.get('CAM_SDA', ''):
        problems.append('camera I2C is not I2C4_M2 in circuit.py')
    has(r'&i2c4 \{[^}]*pinctrl-0 = <&i2c4m2_xfer>', 'I2C4 not on its M2 pins')
    if 'UART1_TX_M0' not in pins.get('BT_TXD', '') or 'UART1_RTS_M0' not in pins.get('BT_RTS', ''):
        problems.append('Bluetooth UART is not UART1_M0 in circuit.py')

    # ADC channels
    if 'SARADC_IN%d' % board.ADC_LIGHT not in pins.get('ALS', ''):
        problems.append('light sensor: board.py channel %d, circuit.py %s' % (board.ADC_LIGHT, pins.get('ALS')))
    if 'SARADC_IN%d' % board.ADC_BUTTON not in pins.get('BOOT_KEY', ''):
        problems.append('button: board.py channel %d, circuit.py %s' % (board.ADC_BUTTON, pins.get('BOOT_KEY')))
    has(r'&saradc \{[^}]*status = "okay"', 'SARADC not enabled')
    has(r'&sdmmc \{[^}]*no-1-8-v;', 'SDIO not kept at 3.3 V')
    if '3.3 V' not in pins.get('SD_D1', '') and 'VCCIO4' not in circuit_text:
        problems.append('SDIO voltage not found in circuit.py')
    return problems


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
        self.assertEqual(check(self.circuit, self.dts), [])

    def test_check_can_fail(self):
        broken = self.dts.replace('<&gpio1 RK_PC0 GPIO_ACTIVE_HIGH>', '<&gpio1 RK_PC1 GPIO_ACTIVE_HIGH>')
        broken = broken.replace('pwm3m1_pins', 'pwm3m0_pins')
        self.assertEqual(len(check(self.circuit, broken)), 2)
        swapped = self.circuit.replace("'IRCUT_A',        # GPIO1_A0", "'IRCUT_A',        # GPIO1_A1")
        self.assertNotEqual(swapped, self.circuit)
        self.assertTrue(check(swapped, self.dts))


if __name__ == '__main__':
    unittest.main()
