# SmokeBreak v1: tests and simulations

Every test and simulation for this revision, with its **v1** result. How
this record works across the repository: [`docs/versioning.md`](../../docs/versioning.md).
Before a v2, question each row first (still needed? still right? anything
missing? did hardware disagree?).

Worst case used throughout: a 14S LiHV pack (60.9 V), a drone with
2200–5000 µF and a 15 W video transmitter, 300 nH drone leads.

## Build gates (CI, every push)

`ci / smokebreak-v1` runs these on every push; a failure stops the build.

| Test | Why | How | v1 result |
|---|---|---|---|
| Silkscreen art rebuilt from source | The logo, flag and labels are what `src/` draws | `src/artwork.py` | pass, 32 items |
| KiCad DRC, zones refilled, every severity | The fab can make it | `src/fab.py` | 0 errors, 0 warnings, 0 unconnected |
| Nets equal the circuit | The copper is the schematic | `src/fab.py` | pass, 674 pads |
| BOM and CPL from the placed parts | Assembly gets what the board needs | `src/fab.py` | 97 BOM lines, 194 placements |
| Committed production files equal the build | Someone orders from them | `tools/check_outputs.py` | pass |
| Firmware model | Every firmware decision (probe, pre-charge, limits, balance, packs, over-voltage) | `pytest firmware/tests` | 328 passed |

## Checks run by hand (recorded here)

| Check | Why | How | v1 result | Run |
|---|---|---|---|---|
| Brand | The logo is the brand's own geometry | `tools/verify_brand.py` (Chromium renders the brand SVG) | pass against offgrid-brand v3.2.2: mark IoU 0.993, lockup IoU 0.963, 0 px off | 18 Oct 2026 |
| Placement | No part overlaps, nothing too tall under the screen | `tools/placement_check.py`, KiCad's courtyard check | 0 overlaps (the hole/switch bounding-box warnings are circles that clear); KiCad DRC finds no courtyard overlap | 19 Oct 2026 |
| Case fit | The case closes on the board, prints, and works | `enclosure/check.py` → `enclosure/print/fit_check.txt` | pass: 6 watertight STLs; no interference; XT60 / XT30 0.19 mm, USB-C 0.07 mm; display 0.2 mm all round; guard clears the lever by 1.0 mm; magnet 12.9 mT at the hall switch closed (2.7 × its maximum operate point); rocker presses both switches | 14 Oct 2026 |
| Cost | The owner's target | `tools/cost.py` | **$55.58** landed at 100 units with the display, against $20–22 (README *Requirements*) | 19 Oct 2026 |

## Simulations (run by hand, recorded here)

All in `sim/` (ngspice 47), run on the circuit in `src/circuit.py`.
Details, plots and open risks: [`sim/SIM.md`](sim/SIM.md). The circuit is
the same netlist the routed board carries (net check above); these are
circuit simulations, so the routing does not change them.

| Simulation | Why | v1 result | Run |
|---|---|---|---|
| 1 Pre-charge, main-switch close | The drone's capacitors charge within 1 s; the FETs close inside their safe area; resistor energy | pass: slowest 80 ms; main close within the derated SOA; worst attempt 10.6 J (5.3 J per resistor, the 12 J abort keeps each under 60 % of its pulse rating) | 19 Oct 2026 |
| 2 Hot plug, both polarities | Plugging a pack in must not overstress anything | pass: VIN 79.8 V (< 90 V); reversed: Q11 avalanches 28 A for < 1 µs | 19 Oct 2026 |
| 3 Short while on | A hard short at 1S–14S, worn pack, long leads | pass: no FET avalanche, SRC ≥ −65 V, Vgs < 19 V | 19 Oct 2026 |
| 4 Reversed pack on the input | Nothing conducts, the controller survives | pass: every path < 1 mA | 19 Oct 2026 |
| 5 Pack on the drone side | Static and plugging in, both polarities | pass: VOUT < 90 V, SRC ≥ −65 V | 19 Oct 2026 |
| 6 Packs on both sides | Nothing conducts while off | pass | 19 Oct 2026 |
| 7 3 V probe | It tells ten kinds of drone load apart | pass: all ten classified; capacitance within ±15 % | 19 Oct 2026 |
| 8 Internal resistance | The pack check's estimate | pass: worst +0.5 % | 19 Oct 2026 |
| 9 Peak current path | The comparator cuts within 5 µs | pass | 19 Oct 2026 |
| Thermal at 15 A in the closed case | The FETs stay cool enough | **not run** (README *Limits*: measure at bring-up) | — |

21 of 21 checks pass. The board is the *Q11 alternative network* rows of
`sim/SIM.md`; rows labelled *pre-review* are the circuit before the
simulation review, kept for comparison.

The runs use the board's parts:
- Q11's 4.7 MΩ gate;
- the SMBJ64CA at its highest-breakdown corner (78.6 V, 103 V clamp);
- the BSC070N10LS5's 50 A / 55 mJ avalanche rating.

One approximation remains: Q11 is modelled with the BSC040N10NS5's device
model (the same 100 V SuperSO8 class), because no BSC070N10LS5 model is in
`sim/lib/`. Re-run on 19 Oct 2026.

## On hardware (not yet run)

| Test | Why | How | v1 result |
|---|---|---|---|
| Bring-up | Powers, flashes, reverse supply harmless | README *Bring-up* | not built |
| Probe | Classifies open, 1 kΩ, 18 Ω, 0.3 Ω, 2200 µF | resistors and a capacitor bank on the drone side | not built |
| Pre-charge | Time and resistor temperature, repeated attempts | 2200 µF and 5000 µF banks at 6S and 14S | not built |
| Short cut-off | Under 5 µs, nothing damaged | a switched short with a scope on the shunt | not built |
| Heat | FET and case temperature at 15 A for 10 minutes, 25 A for 60 s | thermocouples, case closed | not built |
| Cell readings | ±10 mV per cell after calibration | against a meter, 2S–6S | not built |
| Guard sensor | Opens past 40°, never reads open when closed | by hand | not built |
| Case | Fits, closes flat, rocker feel, guard hinge | first print | not printed |

When these run, record the results here. Where they disagree with a
simulation, fix the model before the next revision trusts it.
