# Ridge 3 rev 2: test plan for the first prototypes

For the engineer who builds and tests the first stacks.  Nothing below has
been done yet: every expected value is a simulation (`../STRESS.md`,
`RELIABILITY.md`, the tools in `../sim/`) or a datasheet limit, and the point
of these tests is to replace them with measurements.  The open decisions each
test settles are in [`STATUS.md`](STATUS.md); record results as described at
the end, then update `STATUS.md`.

The basic bring-up (first power, flashing, orientation, motor order) is in
the main README's [Bring-up](../README.md#bring-up) and is not repeated here.
Do it first on every stack.

## What to order for testing

- **Boards:** one FC panel (6 FCs) and two ESC panels (12 ESCs), all from
  the committed files.  One ESC panel exactly as committed (IDRIVE 75 kΩ,
  60 / 120 mA); on the other, change the IDRIVE line of the panel's BOM
  (`../esc/production/panel/ridge3-esc-panel-bom-jlcpcb.csv`, line 11:
  `75k, "R9_1,...,R45_6"`, and the same line of the PCBWay BOM beside it)
  from LCSC C295816 (RC0201FR-0775KL) to **C295780 (RC0201FR-0718KL, 18 kΩ,
  30 / 60 mA)** before ordering (`CHANGING.md`, C1).  Nothing else differs.
  Label the panels.
- **Per stack:** the heatsink, gap pad, stack lead, grommets and hardware
  listed in the README's [Also needed](../README.md#also-needed-not-on-the-boards).
- **Allocation:** of the 12 ESCs, 4 for function and switching (two of each
  IDRIVE), 4 for heat and flight (the IDRIVE you intend to ship, plus one
  of the other), 4 for destructive tests (locked rotor first).

## Equipment

| Item | For | Notes |
|---|---|---|
| Bench supply, 0-30 V, current limit, 5 A or more | bring-up, T3, T7 | a smoke stopper (fused or current-limited) on the first battery power-up |
| 6S LiPo packs, fresh and tired; one 6S LiHV | T5-T9, T11, T13 | the "tired" pack is the high-resistance case for throttle chops |
| Oscilloscope, 4 channels, 200 MHz or more | T5, T6, T11 | short ground spring on the probe, not the clip lead |
| Isolated or differential probe | T5 | for the high-side FET (VDRAIN to SHx) |
| DC current clamp, 100 A or more | T3, T5, T7 | on one motor phase wire |
| Logic analyser | T6 | on the DRV8320H's nFAULT (pin 17): it has no pad, solder a fine wire to the pin's fillet |
| K thermocouples (4) and a logger | T4, T7, T8 | Kapton tape on the hottest FET (phase C high side is beside the thermistor; measure the low sides too) |
| Thermal camera | T8, T9 | optional, finds the hot spot the thermocouple missed |
| Motor test stand with thrust and RPM, 3" props, the reference motor (BrotherHobby VY1507 3100KV) | T5, T8 | the simulations are fitted to this motor |
| A box or room at 50 °C, and a fan with an anemometer (2 and 5 m/s) | T8, T9 | the simulations' hot day |
| ST-Link V2 or Artery AT-Link | flashing, T2 | |
| LiPo-safe area, eye protection, a blast shield for T7 | all | |

## The tests

Each test: what it settles, how, what to record, and what passes.

### T1. Inspection

- X-ray (ask the assembler) of the ESC FETs, the DRV8320Hs and the MCUs:
  voids under the thermal pads.  Pass: no large voids under a FET's drain
  pad.
- Continuity of the stack lead (VBAT on pin 1, `3V3` on pin 4).
- The heatsink's bosses: height over the pad face within ±0.05 mm (it sets
  the gap pad's squeeze).

### T2. Firmware settings, read back

On every ESC, after the README's bring-up step 5: read the settings back in
the AM32 configurator.  Record: temperature limit 110 °C, current limit
20 A, stuck-rotor protection on, 3D off, car-type reversing off, PWM
24 kHz fixed (variable PWM off).  An MCU
flashed over SWD starts with an erased settings page, which AM32 reads as
car-reverse mode with both limits off; this test proves the procedure in
`../firmware/README.md` set them.  Pass: all four, every ESC.

### T3. Current sensing

Each channel against a known DC load (bench supply through one motor
winding, or an electronic load), 5, 10 and 20 A.  Record AM32's reading
against the clamp meter; trim `ibata_scale` if needed.  Pass: within 10 %.
AM32's current limit (20 A) acts on this reading.

### T4. Temperature sensing

At room temperature, then with a hot-air gun on one channel: the ESC
temperature Betaflight shows (`dshot_edt`) against a thermocouple on that
channel's hottest FET.  Pass: the four channels read the room within a few
degrees (an open thermistor reads about -60 °C and silently disables the
limit), and under heat the reported temperature tracks the FET.  Record the
offset: AM32's 110 °C limit acts on the reported value.

### T5. Switching edges: decides IDRIVE

The simulations say the high side's turn-off pulls the driver's SHx pin
below ground past its -7 V (for 200 ns) absolute maximum, more at a punch's
current ([`sim/results/punch/PUNCH.md`](../sim/results/punch/PUNCH.md), from
`sim/.venv/bin/python sim/punch.py`):

| IDRIVE | 30 A, 5 nH | 68 A (punch), 3 / 5 / 8 nH | FET peaks at 68 A, 8 nH |
|---|---|---|---|
| 60 / 120 mA (75 kΩ, as built) | -10.3 V | -11.0 / -15.5 / -21.6 V | 55.6 / 57.2 V |
| 30 / 60 mA (18 kΩ) | -6.2 V | -6.3 / -8.9 / -12.4 V | 39.5 / 32.4 V |

- Probe SHx to the driver's ground at the driver, with the shortest ground
  you can make; the high-side FET's drain to source with the isolated probe;
  the low side's drain to source.  Current clamp on the phase.
- On the test stand, props on: 10, 20 and 30 A steady, then full-throttle
  punches from hover (the simulation peaks at 64-68 A per motor, about 4 ms
  in).  Cold, then with the FETs at about 100 °C (run at high throttle
  first).  Both IDRIVE settings.
- Record: SHx's lowest value and how long it stays below -7 V; each FET's
  peak; the phase current at that moment.
- Pass: SHx no lower than -7 V, or below it for less than 200 ns; FET peaks
  under 48 V (80 % of their 60 V).  The 5 nH loop is an estimate: this test
  also tells which row of the table the real layout is.
- Then decide IDRIVE (`STATUS.md`, D2).  If neither setting passes, the next
  ESC revision needs a clamp or series resistor at the SHx pins, or an RC
  snubber: record the waveforms it would be designed from.

### T6. The overcurrent monitor in hard punches

The DRV8320H's VDS monitor (pin open: 0.6 V, a typical figure with no
limits) turns a channel off for 4 ms when it trips, and AM32 is not told.
With the board's copper in what it measures it trips at 118-143 A with a
hot FET, well above a punch.  Logic analyser on nFAULT of one driver during
T5's hot punches and T13's flights.  Pass: no trips in flying.  Any trip:
record the current and FET temperature.

### T7. Locked rotor: decides the stuck-rotor cut (destructive)

The simulations (`RELIABILITY.md`, a crash) say a rotor stopped dead at full
throttle takes the low-side FET past its 175 °C for 11 ms from a cool board
and for about 200 ms right after hard flying on a 50 °C day; AM32 cuts the
motor after about 248 ms.

- Use the destructive ESCs.  Clamp the motor's bell (or the prop) so it
  cannot turn.  Current clamp on a phase, thermocouple on the low-side FETs,
  scope on one SHx, logic analyser on nFAULT.
- Start at 3S and 25 % throttle; then 4S, then 6S, then higher throttle,
  stopping at the first sign of damage.  Last, from a board heated to about
  120 °C.
- Record: the current against time, when AM32 cuts (its back-EMF timeouts
  are 22.5 ms apart; the cut comes at the 11th), whether the driver trips,
  the FET's peak temperature, and whether the ESC works afterwards without
  unplugging the battery (whether a DRV8320H fault latches until power is
  removed is one of the things this test settles: `RELIABILITY.md`).
- Compare with [`sim/results/crash/CRASH.md`](../sim/results/crash/CRASH.md)
  (`sim/.venv/bin/python sim/crash.py`).  Then decide whether to change
  AM32's stuck-rotor cut to 3 timeouts (`STATUS.md`, D3), and if so repeat
  T7 and T13 with the changed firmware.

### T8. Heat on a hot day

The stack as it flies (heatsink, gap pad, FC above), in 50 °C air (or the
hottest you can make; note it), the fan at 5 m/s, then 2 m/s.
Thermocouples on the hottest FETs, the ESC's MCU and the FC's 9 V
regulator.

- Hold a fixed throttle until temperatures settle, stepping up.  The
  simulation: 52 % throttle held indefinitely before AM32's limit cuts at
  50 °C and 5 m/s (44 % at 2 m/s), with 27 % for hover.
- Then the simulated hard flight on the stand: repeating 20 s cycles of 2 s
  at full throttle, 4 s at 60 % and 14 s at 40 %, for 3 minutes.  The
  simulation: AM32 first cuts a motor at about 62 s and for 10 % of the
  flight (18 % with IDRIVE 30 / 60), the hottest FET at 128 °C.
- Pass: no part past its rating (FETs 150 °C design / 175 °C maximum,
  processors 125 °C junction), and AM32's limit acting before the FETs pass
  150 °C.  Record where the measurement differs from the simulation by more
  than 10 °C: the thermal model is then corrected (`../sim/thermal.py`,
  `../sim/data.py`).

### T9. On the ground with video on

FC and ESC stacked, HD air unit on the 9 V pads (or a 9 V / 1.5 A load and a
5 V / 1 A load), still air, at room temperature and at 35 °C.  The video
thermostat should switch the 9 V rail off near 96 °C and on near 76 °C.  The
simulation: video on 69 % of the time at 25 °C, 46 % at 35 °C.  Pass: the
thermostat acts and nothing passes its rating.  Also the README's bring-up
step 7.

### T10. Supplies

The FC's 5 V, 9 V and 3.3 V rails at no load and full load (2 A on 5 V,
2 A on 9 V, briefly), and the 9 V rail on a nearly empty 3S pack (about
9.9 V): it should stay in regulation down to about 9.5 V of battery.
Ripple on each with the probe's ground spring.

### T11. Battery transients

- Hot plug: plug a full 6S pack in, leads 10 cm and 30 cm, scope on the
  ESC's battery pads.  Simulation: 39.7 V peak with 300 nH of leads.
  Pass: under 48 V.
- Throttle chop: full throttle to zero on the stand, fresh and tired packs.
  Simulation: 28 V (fresh, 25 mΩ) to 35 V (tired, 100 mΩ) on the bus; the
  FC's TVS stays off.  Pass: under 48 V on the bus.

### T12. LiHV

T5 (punch only) and T11 on a full 6S LiHV pack (26.1 V).  The simulation:
the same verdicts as 6S LiPo, punch peaks 68-72 A.  Set Betaflight's
`vbat_max_cell_voltage` to 440 first: at the 430 in
`../firmware/betaflight/cli-setup.txt` a full 6S LiHV pack is counted as
7 cells (`STATUS.md`, D8).

### T13. Flight

Hover on a leash or in a net first, then: hover, punches, flips and rolls,
prop-wash descents, 10 or more packs, with Betaflight's blackbox logging
the ESC telemetry (temperature, current, RPM).  Look for desyncs and
motor cut-outs.  With a changed stuck-rotor cut (T7), fly hard specifically
to look for false cuts: punches from low throttle, hard prop wash.

### T14. Before volume

Not for the first prototypes; needed before selling:

- EMC pre-scan at a lab (FCC Part 15 B for the US; the marks of each market).
- Thermal cycling, vibration, crash shock (drops), humidity and water, on a
  few stacks, with and without a conformal coating if one is considered.
- 20 or more flight hours on several stacks.
- The production test for every unit (`STATUS.md`, before volume).

## Recording results

Write each test's results to `tests/YYYY-MM-DD-T<n>-<short-name>.md` in this
folder: who, which board serial and IDRIVE, the setup (with a photo), the
numbers in a table against the simulation's, scope screenshots (PNG,
compressed), and pass or fail.  Then tick the test in `STATUS.md` and record
any decision it settled there, with the date.  If a measurement disagrees
with a simulation, say so in `STATUS.md`: the simulation's inputs
(`../sim/data.py`) are then corrected from the measurement and the
simulations run again, so the next revision is designed on measured
numbers.
