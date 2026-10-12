"""The sampled world, as the MCU sees it once per control tick.

Everything is an integer in an explicit unit (mV, mA, ms, deci-degC), so each
field maps to one `int32_t` in the C struct `sb_inputs_t`.  The ADC/DMA layer
(see firmware/README.md) fills this struct; the decision logic never touches a
peripheral directly.

Also holds the two tiny helpers every module uses, written the way C does
arithmetic (truncating division, explicit clamps).
"""
from dataclasses import dataclass, field
from enum import IntEnum

# ---------------------------------------------------------------- helpers


def idiv(a, b):
    """C-style integer division (truncates toward zero, like `/` on int32)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


# ---------------------------------------------------------------- inputs

N_TAPS = 6                 # taps 2..7 of the 2S-6S JST-XH sockets (pin 1 is GND / B-)
ADC_VIN_MAX_MV = 66000     # VIN and VOUT-high dividers
ADC_VOUT_LOW_MAX_MV = 3300  # clamped low-range channel for the 3 V probe
ADC_TAP_MAX_MV = 36000


class Toggle(IntEnum):
    """ON-OFF-(ON) toggle: ON away from the user, BIND is the spring-return
    position toward the user.  Mechanically BIND and ON are on opposite sides
    of OFF, so ON -> BIND always passes through OFF (but a slow tick can miss it)."""
    OFF = 0
    ON = 1
    BIND = 2


@dataclass
class Inputs:
    t_ms: int = 0                      # monotonic time of this sample

    # power path (signed where the hardware can see a sign)
    vin_mv: int = 0                    # battery input, 0..66000 (a reversed battery reads 0: ADC clamp)
    vout_mv: int = 0                   # drone side, signed: the divider is offset-biased to read to -5 V
    vout_low_mv: int = 0               # clamped 0..3300 channel used by the 3 V probe
    current_ma: int = 0                # INA181A2 on the 1 mOhm low-side shunt in the drone's return,
                                       # raw (0..65 A): everything the drone draws, pre-charge included
    peak_trip: bool = False            # PEAK_OK went low (programmable LMV331 or the fixed ~65 A hard-short
                                       # LMV331, same latch): INP pulled low, latched until MCU_EN drops
    short_trip: bool = False           # TPS48000 FLT: its own short-circuit protection (~99 A) fired

    # balance lead: voltage of the XH sockets' pins 2..7 versus board GND, mV (index 0 = pin 2 = "tap 1").
    # Pin 1 (black wire) meets GND through 10 Ohm (R75) and the pack's B- meets GND through the
    # reverse-battery FET Q11, so under main current every tap reads high by I x (Q11 + lead):
    # cell voltages are only trusted at idle (see Machine.batt_idle).
    taps_mv: list = field(default_factory=lambda: [0] * N_TAPS)

    # temperatures, deci-degC
    ntc_fet_dc: int = 250
    ntc_rpre_dc: int = 250

    # human interface (already debounced by the 1 kHz GPIO scan)
    guard_closed: bool = True          # hall switch: magnet present
    toggle: Toggle = Toggle.OFF
    btn_minus: bool = False            # Limit rocker, level (pressed = True)
    btn_plus: bool = False
    usb_present: bool = False          # VBUS seen


# Aux supply: the diode-OR wakes the MCU from any of these.  Threshold is the
# buck's start-up voltage (LMR36503: 3.0 V in) plus the OR diode.
AUX_WAKE_MV = 3300


def aux_powered(vin_mv, vout_mv, bal_top_mv, bal_referenced, usb_present):
    """Would the board be awake?  `bal_referenced` is False when the balance
    plug's black wire is not on pin 1 and nothing else gives the board a
    ground (then the balance lead cannot power it: the safe failure)."""
    if usb_present:
        return True
    if vin_mv >= AUX_WAKE_MV or vout_mv >= AUX_WAKE_MV:
        return True
    return bal_referenced and bal_top_mv >= AUX_WAKE_MV
