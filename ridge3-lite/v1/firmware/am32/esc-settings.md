# AM32 settings for the Ridge 3 Lite v1 with iFlight XING2 1404 3800KV, 4S, 3" props

Firmware: stock AM32 v2.21, target GEN_64K_G071 (no custom build; the board is wired to the stock target).  Set these in ESC-configurator
(https://esc-configurator.com, Chrome/Edge) connected through Betaflight passthrough;
"Read setup", change, "Write setup".  Do all four ESCs the same except direction.

| Setting (ESC-configurator) | Value | Why |
|---|---|---|
| Motor KV | 3800 | XING2 1404 3800KV.  Used for start-up and the low-RPM power limit |
| Motor poles | **12** | XING2 1404 is 9N12P (12 magnets).  Set Betaflight `motor_poles = 12` too, or the RPM filter is off by 14/12 |
| Bidirectional mode (3D) | off | normal quad; turtle mode uses DShot commands, not 3D |
| Motor direction | per motor | Betaflight default "props in": M1 rear-right and M4 front-left clockwise, M2 front-right and M3 rear-left counter-clockwise (seen from above).  Check in BF Motors tab with props off; flip with "Motor direction reversed" (or BF's motor-direction wizard) |
| Complementary PWM | on | synchronous rectification; required for sine start, cooler FETs |
| Variable PWM frequency | on (or off at 24 kHz) | either is fine for 1404 motors; leave the default |
| PWM frequency | 24 kHz (default) | up to 48 kHz smooths small motors at the cost of switching loss; start at 24 |
| Timing advance | ESC-configurator default, auto timing on | low-inductance 1404s are happy there; raise only if they desync at punch-out |
| Startup power | default (100) | 3" props start easily |
| Sine startup | off | not needed on a quad |
| Stuck rotor protection | on | cuts power if the rotor is blocked (crash in grass) |
| Brake on stop | off | |
| Low voltage cutoff | **off** | on a multirotor an ESC that cuts one motor crashes the quad.  Battery warnings come from Betaflight (ADC voltage, beeper/OSD); land at 3.5 V/cell under no load |
| Temperature limit | **100 C** | see "Temperature limit" below |
| Current limit | **26 A** (AM32 steps of 2 A) | see below |
| Beep volume | 5 (default) | |
| Extended DShot telemetry | enabled by Betaflight (`dshot_edt = ON`) | ESC temperature, voltage and current reported over the bidirectional DShot line |

Betaflight side: `motor_pwm_protocol = DSHOT600`, `dshot_bidir = ON` (AM32 detects inverted
DShot by itself; no ESC setting), `motor_poles = 12`, RPM filter on.

## Temperature limit: why 100 C

AM32 has no external thermistor on this target: it reads the STM32G071's internal temperature
sensor (ADC channel TEMPSENSOR, Mcu/g071/Src/ADC.c), i.e. the ESC MCU's own die.  Here that die
sits on the FET copper, so it tracks the board heat closely (with some lag), and it is itself the
part with the lowest rating: STM32G071GBU**6** is the -40..85 C ambient grade, junction maximum
**105 C**.  A limit above 105 would protect nothing, including the MCU running the motor.

What AM32 does at the limit (Src/main.c): as soon as the die reads above the limit it caps duty at
50 % and slides that cap linearly to zero over the next 20 C.  At 100 C the cut-back starts 5 C
under the MCU's rating, with the internal sensor's few degrees of error still inside the margin.
Values below 70 or above 140 disable the limit entirely.  On a 3" quad in normal flight the board
should stay far below this; if it ever triggers, the motor is overloaded (wrong props, stall).

## Current limit: why 26 A

This board measures each motor's current itself: 0.5 mOhm Kelvin shunt, INA186A3 (100 V/V) and a
1.5k/1k divider give 20 mV/A at PA5, exactly GEN_64K_G071's `MILLIVOLT_PER_AMP 20`, so AM32's
reading is calibrated with no offset (`CURRENT_OFFSET 0`, INA186 REF to ground).  The amplifier
runs from 3.3 V, so the reading saturates at about 65 A, well above any setting here.

AM32's limit is a PID on duty cycle (`limits.current x 2 A`, Src/main.c): above the limit it pulls
that motor's throttle back.  That is right for a stall or a desync and wrong in normal flight, where
it would steal authority from one motor.  So the limit sits above healthy peaks and below fault
currents:

* XING2 1404 3800KV: 11.8 A rated continuous, 0.28 Ohm winding.  On 4S with 3" props expect
  15-20 A bursts at full throttle.
* A stalled motor on a full pack: 16.8 V / 0.28 Ohm = 60 A, which burns the motor in seconds.
* The FETs (TPN2R304PL, 80 A) and shunt (0.5 mOhm, 2 W: 0.34 W at 26 A) are nowhere near their limits.

26 A clears the bursts with margin and halves the stall current.  If a blackbox log (EDT current)
shows the limit acting during clean flight with your props, raise it to 30 A; heavier props than 3"
are not what this motor is for.
