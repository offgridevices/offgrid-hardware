# Mesh Radio v1: power-path simulations

Electrical studies of the power path in `src/circuit.py` (blocks `inputs()`,
`charger()`, `system()`, `pa_power()`) against README requirements P1-P8,
X1-X7 and E4: hot plug and over-voltage on the three inputs, a reversed
cell, short circuits and the cell protector's trip timing, 3 W bursts from
a worn cell (with a cold start at -40 C and a hot USB-charging case at
85 C), charging from a 6 V panel, and a derating table.  Every study runs
at ambient -40, -20, 0, 25, 60 and 85 C.  (`rf/` and `thermal/` in this
folder are separate studies with their own results.)

```
sim/run_all.sh                         # everything, ~1.5-2 h on 4 cores (runs are cached in sim/out/)
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

Ambient corners -40 / -20 / 0 / 25 / 60 / 85 C.  Full per-case tables are in
each study's `results.txt`.

| study | -40 C | -20 C | 0 C | 25 C | 60 C | 85 C | driver |
|---|---|---|---|---|---|---|---|
| hotplug USB 5 V, 6 V panel, drone 5 V | PASS | PASS | PASS | PASS | PASS | PASS | |
| hotplug USB 5.5 V | MARGINAL | MARGINAL | MARGINAL | MARGINAL | MARGINAL | MARGINAL | OV cut-off 5.22-5.57 V brackets vSafe5V max (X3) |
| hotplug USB / drone 20 V fault, 5->20 V step | MARGINAL | MARGINAL | MARGINAL | MARGINAL | FAIL | FAIL | TVS2200 max VBR + tempco puts eFuse IN at 27.5-28.05 V vs 28 V abs max |
| hotplug 12 V panel (21 V Voc) | FAIL | PASS | PASS | PASS | PASS | PASS | cold Voc 26.1 V, TVS conducts ~0.2 A DC |
| hotplug RB060MM leak into USB_5V (USB out, 10.3 V on solar) | PASS | PASS | PASS | PASS | PASS (1.9 V) | FAIL (10 V) | nRF VBUS abs max 5.8 V |
| reverse cell, no USB | PASS | PASS | PASS | PASS | PASS | PASS | X1 |
| reverse cell + USB, protector on before plug (`_held`) | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | reverse FET turns on: ~33 A, BAT_P -4.4 V for ~440 us, 95 uC in substrate diodes |
| shorts 3V3, header 3V3, VPA | PASS | PASS | PASS | PASS | PASS | PASS | |
| shorts VSYS_SW | FAIL/MARG | FAIL | FAIL | FAIL | FAIL | FAIL | 15 A for 20 ms until OCD; LM66100 12 A, TPS22965 15-20 A, reverse FET 13 W |
| shorts PA_IN | PASS | PASS | MARGINAL | MARGINAL | MARGINAL | MARGINAL | mux limit 4.5 A for 20 ms until OCD |
| shorts BAT_P (all cells) | MARGINAL | MARGINAL | MARGINAL | MARGINAL | MARGINAL | MARGINAL | trips in ~0.25 ms because the BQ29700 loses its supply; restart is a bench item |
| burst 3 W, 4.2 V cell, 150 mOhm, drawn / fixed | FAIL / FAIL | FAIL / FAIL | FAIL / FAIL | PASS / PASS | PASS / PASS | PASS / PASS | 1 W max at -20 C, 2.5 W at 0 C; see max-power table |
| burst 1 W, 3.3 V cell, 150 mOhm, drawn / fixed | FAIL / FAIL | FAIL / FAIL | FAIL / PASS | PASS / PASS | PASS / PASS | PASS / PASS | as drawn BAT_P < PR1 2.98 V -> mux gap -> TPS63810 UVLO |
| burst cold start (worn cell, first 1 W / 3 W burst) | FAIL | | | | | | boots (3V3 = 3.3 V) but first burst resets the TPS63810 |
| burst hot (USB, charging disabled, 3 x 0.3 s at 1-2.5 W), drawn / fixed | | | | | | FAIL / PASS | LM66100 CE=GND charges the cell at up to 0.9 A outside charger control (P7) |
| solar 6 V panel, drawn | FAIL | FAIL | FAIL | PASS | FAIL | FAIL | LM66100 back-charge outside the 0-45 C window |
| solar 6 V panel, Schottky | PASS | PASS | PASS | PASS | PASS | PASS | |
| USB charge path, drawn / Schottky | FAIL / PASS | FAIL / PASS | FAIL / PASS | FAIL / PASS | FAIL / PASS | FAIL / PASS | |
| derating (E4 <= 70 %) | | | | | | | 69 rows: 25 FAIL, 2 MARGINAL (see derating/results.txt) |

Highest PA level that passes from the battery alone (burst/results.txt, 25 C;
drawn -> fixed): 4.2 V cell 3 / 3 / 2.5 W at 50 / 150 / 300 mOhm (both);
3.7 V 3 / 2 / 1.6 W -> 3 / 2.5 / 1.6 W; 3.3 V 1.6 / 1 W / none -> 2.5 / 1.6 / 1 W;
3.1 V none -> 1.6 W / none / none.  At -40 C only a fresh 4.2 V cell (2 W) and
fresh 3.7 V cell (1 W) pass, with or without the fix.

## Recommended circuit changes

These are proposals for the owner and the designer; `src/circuit.py` was
not changed by this work.

1. **Replace the LM66100 (BAT_P -> VSYS) with a Schottky**, RB060MM-30
   (ROHM; already on the BOM; DigiKey RB060MM-30CT-ND, LCSC C308720).  Fixes the
   uncontrolled cell charging (solar, USB, hot case: P7/X5) and the 12 A
   LM66100 stress in a VSYS_SW short.  Costs ~0.3 V headroom, which the PR1
   change below recovers.
2. **TPS2121 PR1 divider 562 k / 301 k -> 562 k / 374 k** (IN1 threshold
   2.98 -> 2.60 V), so a sagging cell no longer triggers the 100 us
   switchover gap that resets the TPS63810.  With no cell fitted the mux then
   selects the charger-held BAT_P and collapses: add a GPIO N-FET (any
   SOT-23 logic-level part, e.g. a 2N7002 from a non-Chinese maker) pulling PR1 low when
   no cell is detected, or use the TPS2121 fast-switchover (XCOMP/CP2) mode.
   `n_1W_fix_pr` passes.
3. **Replace the TPS22965 with a current-limited load switch**, e.g. TPS22950
   (TI; DigiKey 296-TPS22950YBHRCT-ND for YBH; SOT-23 part number and LCSC
   not confirmed), so a VSYS_SW short is limited in microseconds rather than
   waiting 20 ms for the protector OCD.
4. **Reverse-cell with USB**: larger reverse FET, CSD25404Q3 (TI, 6.5 mOhm
   max; DigiKey 296-47255-1-ND showed backorder; LCSC C2865523 unconfirmed),
   plus a Schottky clamp GND -> BAT_P, or move to a low-side N-FET reverse
   topology.  The simulated clamp alone shortens the event (38 us, 7 uC at
   25 C) but does not pass; bench-test whichever is chosen.
5. **Solar/drone front end**: a 60 V eFuse with reverse blocking, TPS26600
   (TI; DigiKey 296-47292-1-ND, stock figures conflicting; LCSC C544399,
   ~3,200 in stock), which allows a higher-voltage TVS and removes the 28 V
   abs-max FAIL at 60/85 C and the cold 12 V-panel FAIL.  Input capacitors
   to 50 V 1 uF X7R 0603 (e.g. Murata GRM188R71H105KA61D, not confirmed).
6. **EN/UVLO divider**: lower impedance (~100 k / 38.3 k) so zener leakage
   cannot raise USB UVLO above OV (with 2 uA leakage USB never turns on).
7. **OVLO**: ~10 nF filter to ride through plug-in ring.
8. **USB OR-ing leak**: the RB060MM from the solar side leaks up to 10 V
   onto USB_5V at 85 C; use a low-leakage ideal diode there (the removed
   LM66100 with CE = VOUT fits) or a bleed resistor on USB_5V.
9. **Firmware**: cap PA power from cell voltage and temperature using the
   max-power table; do not transmit above ~1 W below 0 C with a worn cell.
10. **Owner decision**: JST-PH is rated 2 A; passing 3 W bursts draw 3.4-3.6 A.

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

### Temperature

Every component sits at the ambient of the run (`powerlib.set_temp`):

| quantity | over temperature | source |
|---|---|---|
| cell R_int | x9 / x5 / x2 / x1 / x0.8 / x0.75 at -40 / -20 / 0 / 25 / 60 / 85 C | rise reported by Ji, Zhang & Wang, *Li-ion cell operation at low temperatures*, J. Electrochem. Soc. 160 (4) A636 (2013), doi 10.1149/2.047304jes (measured to -20 C), extrapolated below; hot side kept conservative |
| cell OCV | unchanged (the runs set the state of charge by OCV) | capacity loss in the cold (~50-70 % at -20 C) is a runtime question, not modelled |
| MOSFET / switch RDS(on) | +0.4 %/C from 25 C (reverse FET, protector FETs, LM66100, TPS2121, TPS22965, TPS62840, eFuse, BQ25185 FETs) | level-1 MOSFETs pinned at 25 C (`temp=25`) with KP / (1 + 0.004 dT) |
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
chosen, and run `sim/run_all.sh`.  The protector sense path (22 mOhm +
RSS(on)) is in `powerlib.PROT`; a long return between the sense resistor
and the BQ29700's V- pin adds to the OCD/SCD thresholds and should be
added there.

### hotplug (X3, abs-max pins)
Proves eFuse/charger/nRF pins stay inside abs max and that the OV cut-off acts,
for USB 5 / 5.5 / 20 V, a 5 -> 20 V step, 12 V and 6 V panels and drone 5 / 20 V,
at every corner.  Criteria: abs max = FAIL, > 95 % of abs max = MARGINAL.
Limits: ideal 50 ns-windowed source slew, cable as lumped RLC, TVS as a
diode with breakdown spread typ/min/max plus +6.5 mV/C.

### reverse (X1)
Cell reversed with and without USB, and with CELL_MINUS held near GND
before the plug (protector on; the worst case, set in reality by leakage).
Criteria: no IC pin beyond its abs max with > 1 mA, no substrate charge > 1 uC.
Limits: the result depends on leakage states the model cannot know; some
cases are n/a because the solver stopped before the plug.

### shorts (X2, X5)
Hard shorts on 3V3, header 3V3, VSYS_SW, VPA, PA_IN and BAT_P, with fresh,
mid and worn cells and with USB, and the BQ29700 OCD (3.3-4.9 A) / SCD
(15.6-25.6 A) thresholds over temperature.  Criteria: no part above its
pulsed rating before the protector or a current limit acts.  Limits:
protector release after a trip is not modelled (bench).

### burst (P2, X4)
0.2 s bursts at 1 / 1.6 / 2 / 2.5 / 3 W from cells at 4.2 / 3.7 / 3.3 / 3.1 V
and 50 / 150 / 300 mOhm (25 C value, scaled by temperature), drawn and
fixed; 1 s showcase bursts; USB-only; cold start; hot USB case.  Criteria:
3V3 >= 1.9 V, no protector trip, no TPS63810 UVLO, VPA >= 95 %.  Limits:
cell is OCV + resistance (no RC diffusion: real cells sag less in a 0.2 s
burst but more over 1 s at cold).

### solar (P5)
6 V 1 W panel through BQ25185 VINDPM into a 3.0 / 4.1 V cell at 100 / 20 %
sun, panel at ambient + 25 C x sun; USB rows.  Criteria: harvest > 50 % of
the panel's MPP inside the 0-45 C charge window, <= 1 mA into the cell
outside it.  Result at 25 C: 56 % (3.0 V) and 75 % (4.1 V) of MPP.

### derating (E4)
Collects every stress.json plus datasheet rows at 60 and 85 C; E4 limit
70 %.  FAILs include JST-PH (180 %), CSD25485F5 (112 % current, 134 % power),
LM66100, TPS22965, TPS259470A (101 % peak, 112 % cold panel), TPS63810
(89 % output current; 204 % dissipation at 85 C), QPA9510 (2.0-2.3 A vs
2.4 A), BQ25185 dissipation, C1u25 (84 %), RB060MM reversed panel (87 %),
L2u2 (78 %) and nRF VBUS at OV max (101 %).

## What this does not prove

- Behavioural models from datasheets, not vendor models (encrypted).
  Thresholds use datasheet min/typ/max; part-to-part spread beyond that is not covered.
- Cell: ohmic only (OCV + R_int, scaled with Ji, Zhang & Wang 2013); no
  diffusion RC, no state-of-charge drift during a burst.
- Leakage-dependent states (reversed-cell CELL_MINUS position, zener and
  Schottky leakage) use typical fits; the datasheet maximum is ~5x higher.
- BQ29700 recovery after an SCD/OCD/supply-loss trip; TPS2121 VCOMP
  interpretation; TPS63810 behaviour after UVLO (modelled as a reset).
- Unrouted board: TRACE_* parasitics in board.py are estimates.  Re-run with
  routed values as described above.
- Thermal: junction temperatures are static (ambient + P x theta-JA), with no
  transient heating.
- Part stock/LCSC numbers marked "not confirmed" were not checked live.
