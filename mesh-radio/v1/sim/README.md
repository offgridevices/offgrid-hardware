# Mesh Radio v1: power-path simulations

Electrical studies of the power path in `src/circuit.py` (blocks `inputs()`,
`charger()`, `system()`, `pa_power()`) against README requirements P1-P8,
X1-X7 and E4: hot plug and over-voltage on the three inputs, a reversed
cell, short circuits and the cell protector's trip timing, 3 W bursts from
a worn cell (with a cold start at -40 C and a hot USB-charging case at
85 C), charging from a 6 V panel, and a derating table.  Every study runs
at ambient -40, -20, 0, 25, 60 and 85 C.  The studies model the circuit as
changed on 19 Oct 2026 (below); the first round found the faults those
changes fix.  (`rf/` and `thermal/` in this
folder are separate studies with their own results.)

```
sim/run_all.sh                         # everything, ~40 min on 4 cores (runs are cached in sim/out/)
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

Requirement IDs refer to `../README.md`.  The circuit is `src/circuit.py`
as changed on 19 Oct (next section).  Ambient corners -40 / -20 / 0 / 25 /
60 / 85 C; every number is in the study's `results.txt`.

| study / case | -40 C | -20 C | 0 C | 25 C | 60 C | 85 C | note |
|---|---|---|---|---|---|---|---|
| hotplug: USB 5 V, 20 V fault, 5 -> 20 V step; 6 V and 12 V panels; drone 5 / 20 V; panel and drone reversed | PASS | PASS | PASS | PASS | PASS | PASS | eFuse IN 22.9 V max (28 V); MAX17608 IN 37.6 / -47 V (65 / -70 V); nRF VBUS 5.27 V max in the step |
| hotplug: USB 5.5 V source | MARG | MARG | MARG | MARG | MARG | MARG | by design: the USB OV cut-off (5.22-5.57 V) sits on vSafe5V max to keep VBUS under the nRF52840's 5.5 V |
| USB UVLO vs zener leakage (bound) | PASS | PASS | PASS | PASS | PASS | MARG | only at a 64 uA leakage bound; bench check |
| RB060MM leakage onto VBUS (USB out, 10.4 V on VIN_CHG) | PASS | PASS | PASS | PASS | PASS | PASS | 0.5 V typ, 2.6 V at 5x leakage, 85 C |
| reverse cell: no USB / USB / USB with the protector on | PASS | PASS | PASS | PASS | PASS | PASS | reverse FET stays off; no pin current |
| reverse cell into live pads (right-way cell pulled out under USB, then a reversed one) | FAIL* | FAIL* | FAIL* | FAIL | FAIL | FAIL | 21-24 A for ~0.2 ms, BAT_P below -0.3 V, check-FET VGS 9-11 V.  *At <= 0 C the solver started unlatched, so those runs did not test it |
| right-way cell, with and without USB | PASS | PASS | PASS | PASS | PASS | PASS | FET on ~3 ms after the plug |
| shorts: 3V3, header 3V3, VSYS, VPA, PA_IN (also with USB) | PASS | PASS | PASS | PASS | PASS | PASS | VSYS: TPS22950 holds the cell to 1.0 A |
| shorts: BAT_P (cell terminals) | MARG | MARG | MARG | MARG | MARG | MARG | protector trips in ~0.3 ms (29 A peak, 48 A IDM FET); restart on the cell alone: bench |
| burst 3 W, fresh cell 4.2 V / 50 mOhm | cap 2 W | PASS | PASS | PASS | PASS | PASS | |
| burst 3 W, mid cell 3.7 V / 150 mOhm | no TX | no TX | cap 2 W | PASS | PASS | PASS | |
| burst 1 W, worn cell 3.3 V / 300 mOhm | no TX | no TX | no TX | PASS | PASS | PASS | |
| cold start (switch on, first burst) | 1 W fresh cell only | | | | | | worn or 150 mOhm cells cannot burst at -40 C (R_int x9) |
| hot: USB in, charging off, 3 bursts 1 / 2.5 / 3 W | | | | | | PASS | <= 0.07 mA into the cell (P7) |
| USB only, no cell, 1 W (firmware sets PA_SRC_SYS) | | | | PASS | | | 1.6 W and up exceed the charger's 1.05 A input |
| USB in, cell too weak for 1 W: firmware sets PA_SRC_SYS | | | | PASS | | | without it the weak cell trips UVP |
| solar 6 V panel (charges inside 0-45 C, <= 1 mA outside) and USB charge path | PASS | PASS | PASS | PASS | PASS | PASS | harvest 56 / 76 % of MPP (3.0 / 4.1 V cell), 37 / 53 % at 20 % sun |
| derating (E4) | | | | | | | 81 rows: 1 FAIL (the live-pad case above), 11 MARGINAL (3 W: QPA9510 2.3 A vs 2.4 A, TPS63810, TPS2121 IN1 4.0 A; BQ25185 ILIM at 1.1 A; nRF VBUS at OV max 96 % of abs max) |

"cap" / "no TX": the firmware cap from `burst/results.txt` (highest level that passes for that cell
and temperature); a capped level browns the board out or trips the protector, nothing is damaged.
"MARG" = MARGINAL, with the reason in the note.

**Residual risk, the one FAIL:** with external power in, unplugging a right-way cell leaves the
reverse FET on (its polarity check then sees BAT_P on the pads, a state that holds itself), so a
reversed cell plugged in next sees live pads.  Firmware can clear it: when on external power and
VBAT_SENSE says no cell, drive CHG_CE_N high for ~1 s (BAT_P then decays below the check FET's
threshold in well under a second) and back low.  That needs the processor running; with the
board switched off and external power in, the window stays open.  A hardware cure needs a cell-
presence signal (a 3-pin battery plug); bench-test the sequence either way.

## Changes made on 19 Oct (src/circuit.py, src/parts.py)

From the first round of these studies; the owner kept 3 W (firmware caps
the PA level by temperature and cell voltage), charge current 300 mA.

| block | change | why (study) |
|---|---|---|
| inputs | Solar and drone: RB060MM + TVS2200 + TPS259470A replaced by SMF33CA (33 V bidirectional) + MAX17608 (60 V, -60 V reverse, reverse-current blocking; OV 9.93 V, 0.71 A continuous limit, internal 4 V UVLO); SOLAR_OK / DRONE_OK become 1.5 M / 100 k (1/16) input-voltage dividers to the ADC | a 12 V panel's cold Voc (26 V) made the TVS2200 conduct, and a 20 V fault put the eFuse IN at 28.0-28.2 V hot (28 V abs max) (hotplug); no series Schottky: no reversed-panel stress, more harvest |
| inputs | USB: 4.7 uF 50 V + 1 R (0805 pulse-proof) snubber, eFuse input cap 1 uF 50 V, EN divider 20 k / 7.68 k with a 5.6 V zener (was 1 M / 383 k, 4.7 V), 100 pF on OVLO, VBUS bleed 2.2 k (was 47 k), 22 R from USB_5V to the nRF52840 VBUS (new net NRF_VBUS, its 4.7 uF) | 20 V plug-in ring to 28.2 V; zener leakage could lift UVLO above OV; a 5 V plug-in ring tripped OVLO, which then held USB off (it releases only below 4.89 V); RB060MM leakage put 10 V on VBUS at 85 C; VBUS must ride out the eFuse's 1-2 us cut-off of a 5 -> 20 V step (hotplug) |
| charger | LM66100 replaced by TPS22950 (current-limited 1.0 A, on with the power switch) + RB060MM Schottky to VSYS; VIN_CHG cap 1 + 10 uF -> 1 uF | the LM66100 (CE = GND) charged the cell at ~0.9 A outside the charger's control (solar, burst hot case); 12 A in a VSYS short (shorts); the TPS22950's own reverse block acts only near 1 A, so SYS back-charged the cell (solar); 11 uF on VIN_CHG made a weak panel hiccup the MAX17608 at start-up (solar) |
| charger | reverse FET CSD25485F5 -> CSD25310Q2 (19.9 mOhm, 9.6 A), gate pulled up to BAT_P (1 M) and pulled down only by an SSM3K56ACT polarity check (gate = BATT_PLUS through 100 k / 100 nF; 1 M across the plug) | 3.6 A bursts on a 3.2 A part; a reversed cell with USB in turned the old FET on (33 A, reverse); without the gate filter, BAT_P rising at USB plug-in (coupled onto the empty pad by the FET's capacitance) or the cell leads' plug-in ring turned the check on and latched the FET on |
| charger | protector sense 22 mOhm -> 15 mOhm (Vishay WSLP1206) | OCD could trip at 3.3 A, inside a 3 W burst (shorts) |
| charger | ISET 604 R -> 1 k (300 mA); CHG_TS also to P0.31/AIN7 (coordinator) | owner decision |
| system | TPS22965 removed: the slide switch drives the TPS62840 EN; the buck runs from VSYS | a VSYS_SW short put 15 A through the TPS22965 for 20 ms; the TPS22950 now limits the cell's share of any VSYS short |
| pa_power | PR1 562 k / 301 k -> 562 k / 374 k (IN1 priority to 2.60 V); SSM3K56ACT from PR1 to GND driven by P0.02, renamed PA_VSEL -> PA_SRC_SYS (TPS63810 VSEL tied low) | a sagging cell switched the mux over and the 100 us gap reset the TPS63810 (burst); with no cell, firmware selects SYS |
| mcu (crossing nets only) | A12 PA_VSEL -> PA_SRC_SYS; VBUS pin (AD2) and its 4.7 uF moved from USB_5V to NRF_VBUS | follow the pa_power and inputs changes |
| pa_power | 2 x 47 uF VPA caps: Samsung 0805 X5R -> TDK C3216X7S0J476M160AC (1206 X7S) | more capacitance at 4 V / 85 C (thermal study) |

Firmware follow-ups: P0.02 is now PA_SRC_SYS (drive high to run the
amplifier from charger SYS when no cell is fitted, low otherwise - the
existing "held low" code is the safe default); SOLAR_OK / DRONE_OK are now
analog (input voltage / 16, SAADC); the PA cap table is
`burst/results.txt`.

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
| TPS259470A | EN/UVLO + OVLO comparators (1.20 / 1.09 V), UVP 2.53 / 2.42 V, OVLO response 1.2 us (+ the 100 pF pin filter), dV/dt ramp 2000/CdVdt[pF] V/ms (2 V/ms) at start-up, after which the output follows the input, ILIM 3334/RILM with 2 x ILIM during the ITIMER blanking (0.84 ms for 1 nF), RON 45 mOhm, forward only | abs max IN 28 V, EN/OVLO 6.5 V, IN slew 100 V/us up, 10 V/us down | turn-on delay tD,ON not modelled (conservative: the output starts earlier) |
| UDZV4.7B zener (before 19 Oct) | diode BV 4.65 V, soft knee | VZ 4.55-4.75 V @ 5 mA, IR <= 2 uA @ 1 V | leakage at 1.2 V varied 0-2 uA analytically |
| UDZV5.6B zener (USB EN clamp) | diode BV 5.73 V (the max, for the EN abs-max check), +2 mV/C | VZ 5.49-5.73 V @ 5 mA, ZZ 60 Ohm, IR <= 1 uA @ 2.5 V | tempco assumed; leakage at 1.2 V taken as <= 1 uA doubling every 10 C (analytic table) |
| USB snubber | 4.7 uF 50 V X7R 1206 (4.4 uF left at 5 V, 2.8 uF at 20 V) + 1 Ohm | | DC-bias values read roughly from typical curves |
| MAX17608 | behavioural: internal UVLO 4.02 / 3.5 V, OVLO 1.5 V x (1 + 1.5 M / 267 k) with 3.3 % hysteresis, tOFF_OVP 1 us, tDEB_OVP 20 us, power-up debounce tDEB 16 ms, ~1 ms turn-on ramp, continuous current limit 1.5 V / 2.1 k = 0.71 A, RON 260 mOhm typ (490 max), forward only | abs max IN -70..65 V, IN-OUT 65 V, IN DC 1.1 A; IN slew 100 V/us | the limit acts at once (tOCP_RES 100 us); thermal shutdown not modelled; UVLO falling has no min/max in the datasheet |
| SMF33CA | two diodes back to back | VBR 36.7-40.6 V at 1 mA, VC 53.3 V at 3.8 A, 200 W | +0.1 %/C assumed |
| TPS22950 | switch, RON 41 mOhm (3.3 V), current limit 1.18 x RILIM[k]^-1.072 = 1.02 A (0.75-1.25 A), reverse-current blocking at VOUT > VIN + 44 mV, release below + 16 mV, ~0.55 ms turn-on | 2.7 A continuous, 4.1 A pulsed abs max, 6 V abs max | the limit acts at once (5 us); thermal shutdown not modelled |
| CSD25310Q2 | level-1 P-MOSFET + body diode | VTO -0.85 V; 27 / 19.9 mOhm typ at -2.5 / -4.5 V (fitted at -3.5 V: KP 17.2 A/V2); VGS +-8 V; 9.6 A; 650 pF | level 1 pessimistic at -2.5 V, optimistic at -4.5 V |
| SSM3K56ACT (polarity check, PR1 pull-down) | level-1 N-MOSFET | VTO 0.7 V (0.4-1.0), ~0.3 Ohm | |
| RB060MM-30 | diode | VF 0.40 / 0.44 V @ 1 / 2 A, VR 30 V, Io 2 A | VF 0.30 V @ 0.1 A assumed |
| BQ25185 | averaged power path | SYS regulated 4.5 V (VBATREG 4.2 V <= 4.3 V); ILIM 1.05 A (0.995-1.1); RON_IN 330-470 mOhm (400 used); VINDPM = VBAT + 330 mV above 3.5 V else 3.6 V; sleep 152 / 82 mV; ISET 300 A.ohm / 1 k = 300 mA (604 R, 497 mA, before 19 Oct); precharge 20 % below VLOWV 3.0 V, trickle 7 mA below 1.8 V; DPPM at VBAT + 100 mV; supplement at VBAT - 40 mV; battery FET 115-140 mOhm (130 used); BUVLO 3.0 V for 60 us, +150 mV hysteresis; BATOCP 3.13 A, 250 ms hiccup | BATOCP response 10 us assumed; thermal regulation, timers, termination toggling, TS/MR button and ship mode not modelled |
| CSD25485F5 (before 19 Oct) | level-1 P-MOSFET + body diode + gate ESD | VTO -0.95 V, 35 mOhm at -4.5 V (KP 8 A/V2), VSD 0.75 V | gate ESD +-14 V, Ciss 400 pF assumed; level 1 underestimates RDS(on) at low VGS |
| BQ29700 | behavioural | OVP 4.275 V / 1.25 s; UVP 2.80 V / 144 ms (release +100 mV and BAT - V- > 1 V); OCD 100 mV / 20 ms; SCD 500 mV / 250 us; OCC -100 mV / 8 ms; tolerances +-15 mV, +-100 mV, +-20 %, +-50 %; supply valid above 1.5 V; abs max BAT 12 V, V- <= BAT + 0.3 V | 16 uA V- sink while OCD/SCD is latched, 300 k V- pull-up in over-discharge (datasheet 6.5); DOUT/COUT through 10 k into 2 nF of gate (FET turn-off ~20 us, not published) |
| SSM10N954L | two level-1 N-FETs, common drain, body diodes | RSS(on) 2.2 typ / 2.75 mOhm (both) | 1.375 mOhm each at VGS 3.7 V, VTO 0.8 V assumed |
| LM66100 (before 19 Oct) | switch + body diode | RON 79 mOhm (task value; 91-140 mOhm at 3.6 V over temperature); CE = GND: on whenever VIN > 0.25 V, both directions; CE = VOUT: on below VOUT = VIN - 150 mV, off above VIN + 35 mV (0-80 mV); 1.5 A continuous, 2.5 A <= 120 ms | |
| TPS2121 | two forward-only 59 mOhm channels, current limit 4.5 A | PR1 priority (VREF 1.06 / 1.04 V: 2.65 / 2.60 V on BAT_P with 562 k / 374 k; 3.04 / 2.98 V with 301 k before 19 Oct); with PR1 low the higher input wins, IN1 only if 280 mV above IN2 (VCOMP 0-600 mV); tSW 100 us with CP2 grounded, output open meanwhile (Fig 9-8/9-9); UV 2.65 / 2.55 V | soft start (CSS 10 nF) as a 0.4 A limit for 0.7 ms; fast-trip and thermal shutdown not modelled |
| TPS63810 | averaged, 92 % flat, regulated to its I2C setting | IOUT <= min(3.5 A, 4.7 A x 0.92 x VIN / VOUT) from the 5.2 A (boost) / 3.8 A (buck) switch-limit minimums; UVLO 2.1 / 1.9 V; registers reset (back to 3.3 V) after a UVLO | loop 20 A/V (~70 kHz with ~45 uF), soft start 3.3 V/ms assumed; real efficiency falls to ~85 % in deep boost |
| QPA9510 | supply current source | 1.0 A @ 2.7 V (30 dBm), 1.7-2.0 A @ 3.6 V (34 dBm, 2.0 used), 2.3 A @ 4.0 V (35 dBm), 208 mA quiescent with APC on, 58 uA standby; abs max 2400 mA | 32 / 33 dBm points interpolated (3.1 V / 1.3 A, 3.35 V / 1.55 A); current scales with VCC below its setting (saturated PA); RF ramps in 40 us |
| TPS22965 (before 19 Oct) | 18 mOhm resistor | no current limit; 6 A continuous, 8 A < 300 us | |
| TPS62840 | averaged buck, 90 %, 100 % mode | high side 0.43-0.6 Ohm + L2u2 DCR 0.14 Ohm; ILIMF 1.0-1.4 A (1.1 A average used); UVLO 1.8 / 1.6 V | |
| 3V3 load | current | 13 mA listening; 130 mA transmitting (SX1262 at its +20 dBm firmware cap, APC LDO 9 mA, nRF52840) | brown-out: nRF52840 POF / SX1262 1.7-1.8 V, criterion 1.9 V |
| cell | OCV behind a resistance | OCV 3.1-4.2 V, R_int 50 / 150 / 300 mOhm | purely resistive (no RC recovery): the droop after ~5 ms is the 1 s value, conservative |
| solar panel | single-diode equation | 6 V 1 W: 12 cells, Voc 7.2 V, Isc 0.185 A; 12 V: 36 cells, Voc 21 V, Isc 0.33 A; -2.2 mV/C per cell | n = 1.3, 10 mOhm per cell, 20 nF |

### Temperature

Every component sits at the ambient of the run (`powerlib.set_temp`):

| quantity | over temperature | source |
|---|---|---|
| cell R_int | x9 / x5 / x2 / x1 / x0.8 / x0.75 at -40 / -20 / 0 / 25 / 60 / 85 C | rise reported by Ji, Zhang & Wang, *Li-ion cell operation at low temperatures*, J. Electrochem. Soc. 160 (4) A636 (2013), doi 10.1149/2.047304jes (measured to -20 C), extrapolated below; hot side kept conservative |
| cell OCV | unchanged (the runs set the state of charge by OCV) | capacity loss in the cold (~50-70 % at -20 C) is a runtime question, not modelled |
| MOSFET / switch RDS(on) | +0.4 %/C from 25 C (reverse FET, protector FETs, TPS22950, TPS2121, TPS62840, eFuses, BQ25185 FETs) | level-1 MOSFETs pinned at 25 C (`temp=25`) with KP / (1 + 0.004 dT) |
| TPS63810 efficiency | 8 % loss at 25 C scaled with RDS(on): 90.1 % at 85 C, 94.1 % at -40 C | assumption |
| TVS2200 breakdown | +6.5 mV/C | datasheet VCLAMP 27.7 V (27 C) vs 28.35 V (125 C) |
| RB060MM | ngspice diode with EG 0.69 eV, XTI 2: VF about -1.2 mV/C, leakage x~100 from 25 to 85 C | typical Schottky values; datasheet curves not digitised |
| UDZV4.7B | VZ taken as flat (a 4.7 V zener's TC is near zero); leakage doubling every 10 C (analytic table) | the datasheet gives IR at 25 C only |
| eFuse / charger / protector / mux thresholds | the datasheet min/max already hold over -40..125 C, so the min/max analysis is the same at every corner | |
| ceramic capacitors | x0.85 at -40 and 85 C, x0.9 at -20 C, x0.95 at 0 and 60 C, on top of the bias derating | typical X5R/X7R |
| BQ25185 TREG | charge current cut so 68.3 C/W x P keeps the die at 100 C (static) | datasheet 6.3.7.6 |
| NTC / firmware charge window | charging allowed only 0-45 C (firmware /CE inside the NTC's 0-60 C): off at -40/-20/0/60/85 C | src/circuit.py charger() |

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
chosen, and run `sim/run_all.sh`.  The protector sense path (15 mOhm +
RSS(on)) is in `powerlib.PROT`; a long return between the sense resistor
and the BQ29700's V- pin adds to the OCD/SCD thresholds and should be
added there.

### hotplug (X3, abs-max pins)
Plugs each input in through its cable or lead (USB 5 / 5.5 / 20 V, a 5 -> 20 V
step while on, a 12 V and a 6 V panel, drone 5 / 20 V, a 12 V panel and a
drone supply plugged in backwards) and checks every pin against its absolute
maximum, the over-voltage cut-offs, and the slew limits.  Also: the USB UVLO
against the EN zener's leakage, and the USB OR-ing Schottky's leakage onto
the nRF52840's VBUS with USB out.  Limits: cable as a lumped RLC; TVS as
diodes with a breakdown spread; MAX17608 and TPS259470A behavioural (see
Models); the 5 -> 20 V step relies on the TPS259470A OVLO response (1.2 us
datasheet + the 100 pF filter), which is the part to check on the bench.

### reverse (X1)
A 4.2 V cell plugged in backwards, with and without USB, with CELL_MINUS
held near GND before the plug (protector on, the worst case for the old
circuit), with the pads live before the plug (`_live`, see Verdict), and a
right-way plug-in for reference (which must connect).  Criteria: no IC pin
beyond its abs max with > 1 mA, no substrate conduction, reverse FET and the
polarity-check FET within VGS / VDS / power.  USB comes up at 1 ms so the
solver starts from the state the board really reaches.

### shorts (X2, X5)
Hard shorts (10 mOhm + 5 nH) on 3V3, the header's 3V3, VSYS (the buck input
since the load switch went), VPA, PA_IN and BAT_P, with fresh, mid and worn
cells and with USB; and the BQ29700 OCD / SCD thresholds over temperature with
15 mOhm sense (OCD 4.6-7.0 A, SCD 21.5-36 A).  Criteria: no part above its
pulsed rating before the protector or a current limit acts; the board runs
again once the short goes.  BAT_P shorts trip the protector (its supply is
lost in ~0.3 ms) and whether it releases on the cell alone is a bench item
(release rule in `shorts/results.txt`), hence MARGINAL.

### burst (P2, X4)
0.2 s bursts at 1 / 1.6 / 2 / 2.5 / 3 W from cells at 4.2 / 3.7 / 3.3 / 3.1 V
and 50 / 150 / 300 mOhm (the 25 C value, scaled with temperature): the
highest level that passes is the firmware cap.  Also 1 s bursts, USB with a
cell, USB with no cell (firmware sets PA_SRC_SYS, and the case where it does
not), a cold start at -40 C and three bursts at 85 C on USB with charging
disabled.  Criteria: 3V3 >= 1.9 V, no protector trip, no TPS63810 UVLO, VPA
>= 95 %; hot case <= 1 mA into the cell between bursts.  Limits: the cell is
OCV + resistance (no diffusion RC: real cells sag less in a 0.2 s burst, more
over 1 s in the cold).

### solar (P5, P7)
A 6 V 1 W panel through the MAX17608 and the charger's VINDPM into a 3.0 /
4.1 V cell at 100 / 20 % sun (panel at ambient + 25 C x sun), and USB, at every
corner: inside the 0-45 C charge window the cell must charge, outside it <= 1
mA may reach the cell.  Harvest at 25 C: 56 / 76 % of the panel's maximum
power at full sun (3.0 / 4.1 V cell), 37 / 53 % at 20 % sun.

### derating (E4)
Collects every study's stress.json plus datasheet rows at 45 / 60 / 85 C.  E4
limit 70 %; faults are judged against absolute maxima; the rows the owner's
3 W decision sets (amplifier, buck-boost, mux, battery plug) are MARGINAL
with that reason.

## What this does not prove

- Behavioural models from datasheets, not vendor models (encrypted).
  Thresholds use datasheet min/typ/max; part-to-part spread beyond that is
  not covered.  The MAX17608 and TPS22950 thermal shutdowns are not modelled
  (a hard short on VSYS or VIN_CHG ends in their thermal cycling).
- The cell is ohmic only (OCV + R_int, scaled with Ji, Zhang & Wang 2013); no
  diffusion RC, no state-of-charge drift during a burst.
- Leakage-dependent results use typical fits (Schottky x5 and the zener bound
  shown separately); the reversed-cell results depend on where floating nodes
  sit before the plug, which leakage sets.
- Bench items: the BQ29700 release after a trip on the cell alone; the USB
  turn-on at 85 C (zener leakage bound); the eFuse's real OVLO response to a
  5 -> 20 V step (the model trusts the datasheet's 1.2 us); the MAX17608
  start-up with a weak panel (its UVLO falling threshold has no min/max).
- The board is not routed (moving to 6 layers): TRACE_* in board.py are
  estimates; re-run with extracted values (Parasitics above).
- Thermal: junction temperatures are static (ambient + P x RthJA); bursts are
  short, see `sim/thermal` (another study).
- Stock figures were read from DigiKey and LCSC/JLCPCB on 19 Oct 2026.
