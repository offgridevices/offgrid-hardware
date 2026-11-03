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
    'IRCUT_A': 'GPIO1_A0',       # DRV8210P IN1
    'IRCUT_B': 'GPIO1_A1',       # DRV8210P IN2
    'WIFI_EN': 'GPIO1_A2',       # ESP32-C6 EN (mmc-pwrseq in the device tree)
    'WIFI_BOOT': 'GPIO0_A2',     # ESP32-C6 GPIO9 strap: low at EN rise = UART download (tools/layercam-c6-flash.py)
    'WIFI_HOST_WAKE': 'GPIO0_A3',  # ESP32-C6 IO4, esp-hosted's host wake (wired, unused)
    'LED_STATUS': 'GPIO1_C0',
    'CAM_RST': 'GPIO3_C5',       # SC4336H XSHUTDN (reset-gpios)
    'CAM_PWDN': 'GPIO3_C6',      # SC4336H PWDNB (pwdn-gpios)
    'IR_PWM': 'GPIO1_B0',        # PWM3_IR_M1
}

IRCUT_A = gpio_number(PINS['IRCUT_A'])
IRCUT_B = gpio_number(PINS['IRCUT_B'])
WIFI_EN = gpio_number(PINS['WIFI_EN'])
WIFI_BOOT = gpio_number(PINS['WIFI_BOOT'])

# the Wi-Fi module's UART0, for flashing it from Linux: UART1_M0 (serial1)
WIFI_UART = '/dev/ttyS1'

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

# sensor: SmartSens SC4336H, bare on the board, 2-lane MIPI, 24 MHz clock.
# 2560 x 1440 is the SC4336 family's mode (the SDK's sc4336.c; SmartSens'
# SC4336H flyer: 2560x1440 at 30 fps).  The driver is a port of sc4336.c
# (tools/sc4336h-port.py); its name and the IQ file follow from these.
SENSOR = 'sc4336h'
SENSOR_WIDTH, SENSOR_HEIGHT = 2560, 1440
SENSOR_I2C_BUS, SENSOR_I2C_ADDR = 4, 0x30
SENSOR_CHIP_ID_REG = 0x3107      # 16 bits, 0x3107/0x3108, as the whole SC3336/SC4336 family
# rockchip,camera-module-name / -lens-name in the device tree: rkaiq loads
# /etc/iqfiles/<sensor>_<module>_<lens>.json
SENSOR_MODULE, SENSOR_LENS = 'LayerCamPro', 'LCP-F16'
IQ_FILE = '%s_%s_%s.json' % (SENSOR, SENSOR_MODULE, SENSOR_LENS)
