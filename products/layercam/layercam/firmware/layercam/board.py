"""The board's pins as Linux sees them.

Every value here comes from src/circuit.py's main_soc() pin map (the comment
on each pin names its function) and is checked against it, and against the
device tree in dts/, by tests/test_pins.py.  Rockchip numbers a GPIO
bank * 32 + group * 8 + index, groups A-D = 0-3: GPIO1_A0 = 32.
"""


def gpio_number(name):
    """'GPIO1_A0' -> 32."""
    bank, pin = name[4:].split('_')
    return int(bank) * 32 + 'ABCD'.index(pin[0]) * 8 + int(pin[1:])


# nets of circuit.py and the SoC pin they are on
PINS = {
    'IRCUT_A': 'GPIO1_A0',       # DRV8837 IN1
    'IRCUT_B': 'GPIO1_A1',       # DRV8837 IN2
    'WL_REG_ON': 'GPIO1_A2',
    'BT_REG_ON': 'GPIO0_A1',
    'BT_WAKE': 'GPIO0_A2',
    'WL_HOST_WAKE': 'GPIO0_A3',
    'BT_HOST_WAKE': 'GPIO0_A4',
    'LED_STATUS': 'GPIO1_C0',
    'CAM_RST': 'GPIO3_C5',
    'IR_PWM': 'GPIO1_B0',        # PWM3_IR_M1
}

IRCUT_A = gpio_number(PINS['IRCUT_A'])
IRCUT_B = gpio_number(PINS['IRCUT_B'])

# SARADC channels (in_voltageN_raw)
ADC_BOOT_PAD = 0                 # SARADC_IN0: the BOOT pad (TP5), MaskROM strap; 10k up to 1.8 V. Read for diagnostics only
ADC_LIGHT = 1                    # SARADC_IN1, TEMT6000 across 22k: ~0.5 V at 50 lux
ADC_DEVICE = '/sys/bus/iio/devices/iio:device0'

# PWM3 (ff350030) on its M1 pin; the device tree names the controller, the
# pwmchip number depends on probe order, so it is found by address.
PWM_IR_GLOB = '/sys/devices/platform/ff350030.pwm/pwm/pwmchip*'
PWM_IR_PERIOD_NS = 1000000       # 1 kHz: the AO3400A's gate (100R, 100k) switches cleanly

# the status LED is a gpio-leds node in the device tree
LED_STATUS = '/sys/class/leds/status'

# the IR-cut coil: 3.3 V for 100-500 ms (Commonlands), then the bridge off
IRCUT_PULSE_S = 0.2

# sensor (Luckfox Pico Pro/Max's SC3336 module, same IQ file)
SENSOR_WIDTH, SENSOR_HEIGHT = 2304, 1296
