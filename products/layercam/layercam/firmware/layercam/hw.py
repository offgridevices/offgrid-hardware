"""The board's small hardware: light sensor and BOOT pad (SARADC), IR-cut
H-bridge (two GPIOs), IR LEDs (PWM), status LED (gpio-leds).  Linux sysfs
only, so nothing to install.  The decisions (when is it dark, which LED
pattern, is the BOOT pad leaking) are pure functions, tested on the host;
the Sysfs class is the thin part that touches files.

There is no button (its plastic would sit above its rating in the printer):
Wi-Fi setup and reset, updates and recovery work without one (README.md).
"""
import glob, os, threading, time

from . import board


def _write(path, value):
    with open(path, 'w') as f:
        f.write(str(value))


def _read(path):
    with open(path) as f:
        return f.read().strip()


# ------------------------------------------------------------------ decisions
class DayNight:
    """Night when the light stays below dark_v for hold_s, day when it stays
    above light_v for hold_s; in between nothing changes (hysteresis), so the
    printer's own light flickering or a hand passing by does not flip the
    filter.  The TEMT6000 follows the eye's response and does not see the
    850 nm LEDs, so turning them on cannot turn them off again."""

    def __init__(self, dark_v=0.10, light_v=0.25, hold_s=5.0, start='day'):
        assert dark_v < light_v
        self.dark_v, self.light_v, self.hold = dark_v, light_v, hold_s
        self.state = start
        self.since = None          # when the reading first crossed towards the other state

    def feed(self, volts, now):
        want = None
        if self.state == 'day' and volts < self.dark_v:
            want = 'night'
        elif self.state == 'night' and volts > self.light_v:
            want = 'day'
        if want is None:
            self.since = None
            return self.state
        if self.since is None:
            self.since = now
        if now - self.since >= self.hold:
            self.state, self.since = want, None
        return self.state


def ir_plan(mode, light_state, printing):
    """-> (filter, leds): filter 'day' (IR-cut in) or 'night' (out); leds:
    whether night pictures may light the IR LEDs.  They are never on
    continuously: only for the moments around each picture (and live view),
    because lit continuously they and their resistors are the hottest
    thing in the housing (sim/thermal.md, night case)."""
    if mode == 'day' or mode == 'off':
        return 'day', False
    if mode == 'night':
        return 'night', True
    night = light_state == 'night'
    # the filter follows the light; in 'printing' mode the LEDs wait for a print.
    # The filter coil is pulsed only when this answer changes (Service.update_ir).
    return ('night' if night else 'day'), (night and (printing or mode == 'auto'))


# The BOOT pad (TP5) is the SoC's MaskROM strap: SARADC_IN0, 10k up to 1.8 V,
# 100R to the pad.  Bridged to ground while the camera powers up, the boot ROM
# waits for flashing over USB; Linux never sees that.  Once running, the
# pin should read 1.8 V.  Lower means something leaks to ground (flux,
# moisture, a crushed cap): the next power-up may then stop in MaskROM and
# the camera would look dead.  Read now and then and reported, nothing else.
BOOT_PAD_LOW_V = 1.2


def boot_pad_problem(volts):
    if volts is None or volts >= BOOT_PAD_LOW_V:
        return None
    return ('BOOT pad at %.2f V (should be 1.8 V): something leaks to ground there, and the camera may '
            'start in flashing mode at the next power-up; clean the pads (TP5, TP3)' % volts)


# status LED: one green LED, so meaning is in the rhythm.  (on ms, off ms) pairs, repeated.
# (Right after power-up, before the service runs, a few quick flashes are the
# power-cycle gesture counting: gesture.py.)
PATTERNS = {
    'updating': [(50, 50)],                          # flicker: installing an update, leave the power on
    'setup': [(1000, 1000)],                         # slow blink: setup access point is on
    'hot': [(1500, 300)],                            # long on, short off: hot, camera throttled or stopped
    'offline': [(100, 100)],                         # fast blink: joining Wi-Fi (or trying it again)
    'error': [(150, 150), (150, 150), (150, 1500)],  # three blinks: something needs attention (see the page)
    'recording': [(150, 150), (150, 1550)],          # double blink: a timelapse is recording
    'ok': [(1, 0)],                                  # steady: on the network, idle
}


def led_state(setup_ap, wifi_up, error, recording, thermal='normal', updating=False):
    """The one pattern to show, most urgent first (the order of PATTERNS)."""
    if updating:
        return 'updating'
    if setup_ap:
        return 'setup'
    if thermal != 'normal':
        return 'hot'
    if not wifi_up:
        return 'offline'
    if error:
        return 'error'
    if recording:
        return 'recording'
    return 'ok'


def adc_to_volts(raw, scale_mv):
    return raw * scale_mv / 1000.0


# ------------------------------------------------------------------ sysfs
class Sysfs:
    """Everything that touches the board.  Missing files (a PC, a test) make
    the methods do nothing rather than fail, so the service runs anywhere."""

    def __init__(self, root=''):
        self.root = root
        self.adc = root + board.ADC_DEVICE
        self.led = root + board.LED_STATUS
        self.pwm = None
        self._scale = None
        self.lock = threading.Lock()

    def present(self):
        return os.path.exists(self.adc)

    def volts(self, channel):
        try:
            if self._scale is None:
                self._scale = float(_read(self.adc + '/in_voltage_scale'))
            return adc_to_volts(int(_read('%s/in_voltage%d_raw' % (self.adc, channel))), self._scale)
        except (OSError, ValueError):
            return None

    def boot_pad_volts(self):
        return self.volts(board.ADC_BOOT_PAD)

    def light_volts(self):
        return self.volts(board.ADC_LIGHT)

    def set_led(self, on):
        try:
            _write(self.led + '/brightness', 1 if on else 0)
        except OSError:
            pass

    def _gpio(self, n, value):
        base = self.root + '/sys/class/gpio'
        g = '%s/gpio%d' % (base, n)
        if not os.path.exists(g):
            _write(base + '/export', n)
            _write(g + '/direction', 'out')
        _write(g + '/value', value)

    def ircut(self, state):
        """Pulse the filter's coil: IN1 high (red lead positive) opens it for
        night, IN2 high closes it for day; then both low, the bridge off
        (DRV8837 truth table)."""
        a, b = (1, 0) if state == 'night' else (0, 1)
        try:
            with self.lock:
                self._gpio(board.IRCUT_A, a)
                self._gpio(board.IRCUT_B, b)
                time.sleep(board.IRCUT_PULSE_S)
                self._gpio(board.IRCUT_A, 0)
                self._gpio(board.IRCUT_B, 0)
        except OSError:
            pass

    def ir_ramp(self, start, end, ramp_ms, step_ms=20):
        """Change the IR LED duty gradually, so all three LED strings
        (sim/power.md has their current) do not step the 5 V input at once."""
        steps = max(1, int(ramp_ms / step_ms))
        for i in range(1, steps + 1):
            self.ir_leds(start + (end - start) * i / steps)
            if i < steps:
                time.sleep(step_ms / 1000.0)

    def temperature(self, zone):
        """The SoC's temperature in C from a thermal zone (millidegrees), or None."""
        try:
            return int(_read(self.root + zone)) / 1000.0
        except (OSError, ValueError):
            return None

    def cpu_speed(self, fast):
        """Lowest operating point unless fast: scaling_max_freq, which works
        under any governor (Luckfox's kernel defaults to ondemand)."""
        base = self.root + '/sys/devices/system/cpu/cpu0/cpufreq'
        try:
            freqs = sorted(int(f) for f in _read(base + '/scaling_available_frequencies').split())
            _write(base + '/scaling_max_freq', freqs[-1] if fast else freqs[0])
        except (OSError, ValueError, IndexError):
            pass

    def ir_leds(self, duty_percent):
        try:
            if self.pwm is None:
                chips = glob.glob(self.root + board.PWM_IR_GLOB)
                if not chips:
                    return
                chip = chips[0]
                self.pwm = chip + '/pwm0'
                if not os.path.exists(self.pwm):
                    _write(chip + '/export', 0)
                _write(self.pwm + '/period', board.PWM_IR_PERIOD_NS)
                _write(self.pwm + '/polarity', 'normal')
            duty = int(board.PWM_IR_PERIOD_NS * max(0, min(100, duty_percent)) / 100)
            _write(self.pwm + '/duty_cycle', duty)
            _write(self.pwm + '/enable', 1 if duty else 0)
        except OSError:
            pass


class LedBlinker(threading.Thread):
    def __init__(self, hw):
        threading.Thread.__init__(self, name='led', daemon=True)
        self.hw, self.state, self.running = hw, 'offline', True

    def run(self):
        while self.running:
            pat = PATTERNS.get(self.state, PATTERNS['ok'])
            for on_ms, off_ms in pat:
                self.hw.set_led(on_ms > 0)
                time.sleep(max(on_ms, 50) / 1000.0 if off_ms else 0.5)
                if off_ms:
                    self.hw.set_led(False)
                    time.sleep(off_ms / 1000.0)
