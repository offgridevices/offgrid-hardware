# Mesh Radio v1: power-path simulations

Electrical studies of the power path in `src/circuit.py` (blocks `inputs()`,
`charger()`, `system()`, `pa_power()`) against README requirements P1-P8,
X1-X7 and E4: hot plug and over-voltage on the three inputs, a reversed
cell, short circuits and the cell protector's trip timing, 3 W bursts from
a worn cell, charging from a 6 V panel, and a derating table.

```
sim/run_all.sh                         # everything, ~1-1.5 h on 4 cores (the burst grid is most of it)
tools/kd python3 sim/burst/run.py      # or one study, from mesh-radio/v1, in the pinned container
tools/kd sh sim/run_all.sh             # everything in the container
```

Needs ngspice (44 tested) and Python 3 with numpy and matplotlib; the
`ogkicad:10` image (`tools/kd`) has both.  Each study writes `results.txt`
(every number quoted here), `stress.json` (its worst cases, for the
derating table) and a PNG next to its `run.py`.  Netlists as run, ngspice
logs and decimated waveforms go to `sim/out/` (ignored by the repository's
`out/` rule).  `derating/` reads the other studies' `stress.json`, so it
runs last.

**The board is not routed.**  Every PCB resistance and inductance below is
an estimate (see *Parasitics*).  These studies are re-run on the routed
board with extracted values before the order; that is a change to a few
constants in `board.py`, not to the studies.

## Verdict

Requirement IDs refer to `../README.md`.  "As drawn" is `src/circuit.py`
today; "fixed" is with the recommended changes below.

{{VERDICT}}

## Recommended circuit changes

These are proposals for the owner and the designer; `src/circuit.py` was
not changed by this work.

{{CHANGES}}

## Models (what each part is, and where the numbers come from)

TI's PSpice models for these parts are encrypted and do not run in ngspice,
so every IC is a behavioural model built from its datasheet (the copies
used are TI's current revisions; Qorvo's QPA9510 data sheet of 23 Jun 2025).
Switching converters are averaged: no switching ripple, which none of these
checks needs.  Logic inside a model (comparators with hysteresis, deglitch
timers, fault latches) sits on small state nodes that move in about a
microsecond, so currents never jump discontinuously (`powerlib.py`).

| part | model | key numbers (datasheet) | assumptions |
|---|---|---|---|
| TVS2200 | diode, sharp knee | VBR 24.6 / 25.9 / 27.6 V at 1 mA; clamp 27.7 V max at 24 A; 105 pF; 18 mA DC breakdown current abs max | max VBR for pin checks, min VBR for "does it conduct" |
| TPS259470A | EN/UVLO + OVLO comparators (1.20 / 1.09 V), UVP 2.53 / 2.42 V, OVLO response 1.2 us, dV/dt ramp 2000/CdVdt[pF] V/ms (2 V/ms), ILIM 3334/RILM with 2 x ILIM during the ITIMER blanking (0.84 ms for 1 nF), RON 45 mOhm, forward only | abs max IN 28 V, EN/OVLO 6.5 V, IN slew 100 V/us up, 10 V/us down | turn-on delay tD,ON not modelled (conservative: the output starts earlier) |
| UDZV4.7B zener | diode BV 4.65 V, soft knee | VZ 4.55-4.75 V @ 5 mA, IR <= 2 uA @ 1 V | leakage at 1.2 V varied 0-2 uA analytically |
| RB060MM-30 | diode | VF 0.40 / 0.44 V @ 1 / 2 A, VR 30 V, Io 2 A | VF 0.30 V @ 0.1 A assumed |
| BQ25185 | averaged power path | SYS regulated 4.5 V (VBATREG 4.2 V <= 4.3 V); ILIM 1.05 A (0.995-1.1); RON_IN 330-470 mOhm (400 used); VINDPM = VBAT + 330 mV above 3.5 V else 3.6 V; sleep 152 / 82 mV; ISET 300 A.ohm / 604 R = 497 mA; precharge 20 % below VLOWV 3.0 V, trickle 7 mA below 1.8 V; DPPM at VBAT + 100 mV; supplement at VBAT - 40 mV; battery FET 115-140 mOhm (130 used); BUVLO 3.0 V for 60 us, +150 mV hysteresis; BATOCP 3.13 A, 250 ms hiccup | BATOCP response 10 us assumed; thermal regulation, timers, termination toggling, TS/MR button and ship mode not modelled |
| CSD25485F5 | level-1 P-MOSFET + body diode + gate ESD | VTO -0.95 V, 35 mOhm at -4.5 V (KP 8 A/V2), VSD 0.75 V | gate ESD +-14 V, Ciss 400 pF assumed; level 1 underestimates RDS(on) at low VGS |
| BQ29700 | behavioural | OVP 4.275 V / 1.25 s; UVP 2.80 V / 144 ms (release +100 mV and BAT - V- > 1 V); OCD 100 mV / 20 ms; SCD 500 mV / 250 us; OCC -100 mV / 8 ms; tolerances +-15 mV, +-100 mV, +-20 %, +-50 %; supply valid above 1.5 V; abs max BAT 12 V, V- <= BAT + 0.3 V | 16 uA V- sink while OCD/SCD is latched, 300 k V- pull-up in over-discharge (datasheet 6.5); DOUT/COUT through 10 k into 2 nF of gate (FET turn-off ~20 us, not published) |
| SSM10N954L | two level-1 N-FETs, common drain, body diodes | RSS(on) 2.2 typ / 2.75 mOhm (both) | 1.375 mOhm each at VGS 3.7 V, VTO 0.8 V assumed |
| LM66100 | switch + body diode | RON 79 mOhm (task value; 91-140 mOhm at 3.6 V over temperature); CE = GND: on whenever VIN > 0.25 V, both directions; CE = VOUT: on below VOUT = VIN - 150 mV, off above VIN + 35 mV (0-80 mV); 1.5 A continuous, 2.5 A <= 120 ms | |
| TPS2121 | two forward-only 59 mOhm channels, current limit 4.5 A | PR1 priority (VREF 1.06 / 1.04 V: 3.04 / 2.98 V on BAT_P with 562 k / 301 k); with PR1 low the higher input wins, IN1 only if 280 mV above IN2 (VCOMP 0-600 mV); tSW 100 us with CP2 grounded, output open meanwhile (Fig 9-8/9-9); UV 2.65 / 2.55 V | soft start (CSS 10 nF) as a 0.4 A limit for 0.7 ms; fast-trip and thermal shutdown not modelled |
| TPS63810 | averaged, 92 % flat, regulated to its I2C setting | IOUT <= min(3.5 A, 4.7 A x 0.92 x VIN / VOUT) from the 5.2 A (boost) / 3.8 A (buck) switch-limit minimums; UVLO 2.1 / 1.9 V; registers reset (back to 3.3 V) after a UVLO | loop 20 A/V (~70 kHz with ~45 uF), soft start 3.3 V/ms assumed; real efficiency falls to ~85 % in deep boost |
| QPA9510 | supply current source | 1.0 A @ 2.7 V (30 dBm), 1.7-2.0 A @ 3.6 V (34 dBm, 2.0 used), 2.3 A @ 4.0 V (35 dBm), 208 mA quiescent with APC on, 58 uA standby; abs max 2400 mA | 32 / 33 dBm points interpolated (3.1 V / 1.3 A, 3.35 V / 1.55 A); current scales with VCC below its setting (saturated PA); RF ramps in 40 us |
| TPS22965 | 18 mOhm resistor | no current limit; 6 A continuous, 8 A < 300 us | |
| TPS62840 | averaged buck, 90 %, 100 % mode | high side 0.43-0.6 Ohm + L2u2 DCR 0.14 Ohm; ILIMF 1.0-1.4 A (1.1 A average used); UVLO 1.8 / 1.6 V | |
| 3V3 load | current | 13 mA listening; 130 mA transmitting (SX1262 at its +20 dBm firmware cap, APC LDO 9 mA, nRF52840) | brown-out: nRF52840 POF / SX1262 1.7-1.8 V, criterion 1.9 V |
| cell | OCV behind a resistance | OCV 3.1-4.2 V, R_int 50 / 150 / 300 mOhm | purely resistive (no RC recovery): the droop after ~5 ms is the 1 s value, conservative |
| solar panel | single-diode equation | 6 V 1 W: 12 cells, Voc 7.2 V, Isc 0.185 A; 12 V: 36 cells, Voc 21 V, Isc 0.33 A; -2.2 mV/C per cell | n = 1.3, 10 mOhm per cell, 20 nF |

Capacitors are their values left at the working DC bias (derated from the
makers' bias curves, typical X5R/X7R): C47u 6.3 V 0805 at 4 V 19 uF;
C22u16 0805 at 4.5 V 14 uF; C10u25 0805 at 4-5 V 7-8 uF; C1u25 0603 0.6-0.9 uF;
C10u 0603 10 V at 4.5 V 5 uF; C4u7 0603 10 V 2.4-2.8 uF; 5 mOhm ESR each.

### Parasitics (estimates until the board is routed)

| where | value | basis |
|---|---|---|
| USB cable, 1 m | 0.2 Ohm, 1 uH | both conductors |
| solar lead, 1 m | 0.1 Ohm, 1 uH | |
| drone cable, 30 cm JST-GH | 0.05 Ohm, 0.3 uH | |
| battery leads + JST-PH | 2 x (20 mOhm, 0.1 uH) | ~10 mOhm contact + ~7 cm of 26 AWG each |
| JST pads -> reverse FET -> BAT_P | 6 mOhm, 6 nH | `TRACE_BAT` |
| BAT_P -> TPS2121 IN1 | 5 mOhm, 5 nH | `TRACE_MUX1` |
| TPS2121 OUT -> TPS63810 | 3 mOhm, 3 nH | `TRACE_PAIN` |
| TPS63810 -> QPA9510 | 5 mOhm, 5 nH | `TRACE_VPA` |
| USB-C -> TVS / eFuse | 5 mOhm, 5 nH | `TRACE_USB` |

Each R includes its ground return (1 oz copper, 0.5 mOhm/square, ~1 nH/mm
of loop).  **To re-run on the routed board:** extract the loop resistance
and inductance of these five paths from the layout (KiCad's net lengths and
widths, or a field solver), put them into `TRACE_*` at the top of
`board.py`, update `CABLE_USB` / `LEAD_PANEL` if the accessories are
chosen, and run `sim/run_all.sh`.  The protector sense path (22 mOhm +
RSS(on)) is in `powerlib.PROT`; a long return between the sense resistor
and the BQ29700's V- pin adds to the OCD/SCD thresholds and should be
added there.

{{STUDIES}}

## What this does not prove

{{UNVERIFIED}}
