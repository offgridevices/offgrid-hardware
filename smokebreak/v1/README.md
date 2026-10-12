# SmokeBreak v1 — the board

The circuit board inside the Arm (`../design/arm/`): a 1S–14S smoke stopper,
per-cell battery checker and miswiring tester with a colour screen, a guarded
metal toggle and a status-light ring.

| | |
|---|---|
| Board | 94 × 52 mm, 6 layers, 1.6 mm, black mask, white silk, ENIG |
| Assembly | every SMD part on the top (PCBWay, one side); connectors, toggle and the two pre-charge resistors hand-soldered from the bottom |
| Checks | KiCad 10 DRC: 0 errors, 0 warnings, 0 unconnected; netlist matches `src/circuit.py` pad for pad; power-path simulations (`sim/SIM.md`, ngspice 47, 22/22 pass); firmware logic model (`firmware/`, 239 tests) |

## Files

| Path | What |
|---|---|
| `smokebreak.kicad_pcb` / `.kicad_pro` / `.kicad_dru` | the board (KiCad 10) |
| `fab/smokebreak-gerbers.zip` | Gerbers + drill files: upload for the bare board |
| `fab/smokebreak-bom-pcbway.csv` | assembly BOM: manufacturer part numbers, LCSC numbers, SMD/THT, notes |
| `fab/smokebreak-cpl.csv` | pick and place (top, SMD only) |
| `fab/smokebreak-netlist.csv` | every pad and its net (checked against `src/circuit.py`) |
| `fab/smokebreak.step` | the assembled board in 3D, for the case (the toggle, the LEDs, the AC05s and U1 are mesh models KiCad leaves out of STEP: take their sizes from `lib/` until real STEP models replace them) |
| `images/board-*.png` | renders |
| `src/` | the board as code: `circuit.py` (netlist), `parts.py` (every part, MPN, LCSC), `place.py` (placement), `make.py` → `route_run.py` → `finish_run.py` / `repair_run.py` → `final.py` → `fab.py` (`pipeline.sh` runs the lot) |
| `sim/` | power-path simulations and the design values they set |
| `firmware/` | reference model of every firmware decision, with tests |
| `tools/cost.py` | landed-cost tally |

## Ordering at PCBWay

1. **PCB** → upload `fab/smokebreak-gerbers.zip`. Settings: 6 layers, 94 × 52 mm,
   FR-4 TG150, 1.6 mm, outer copper 1 oz, inner 0.5 oz (1 oz inner is better for
   the 25 A path if the price is close), min track/space 4/4 mil (the board
   uses 0.125 / 0.11 mm), min hole 0.2 mm, **black** solder mask, **white**
   silkscreen, **ENIG**. Vias tented.
2. **Assembly** → turnkey, top side only. Upload `fab/smokebreak-bom-pcbway.csv`
   and `fab/smokebreak-cpl.csv`. Lines marked THT ("supplied loose") are not
   fitted: ask PCBWay to ship them loose with the boards, or buy them
   separately: XT60PW-M, XT30PW-M, XT60PW-F, XT30PW-F, JST S9B-XH-A, the
   toggle, 2 × Vishay AC05 15 Ω.
3. The display (1.9" 170 × 320 ST7789, 30-pin 0.5 mm FPC) is bought separately
   and plugs into J7.

## Hand assembly (from the bottom; the bottom silkscreen says what goes where)

1. Pre-charge resistors R_PRE, R_PRE2: lie them flat on the top, bend the
   leads, solder, trim to 1.5 mm.
2. Balance header J5 (pin 1 = black wire, by the arrow), USB-C is already on.
3. XT60/XT30 male on the left (battery), female on the right (drone): seat
   fully, solder with a big iron (the pads are on the power planes), trim to
   1.5 mm (the case floor is 1.9 mm below the board).
4. Toggle SW1 last, with the lever upright; check it sits 8.9 mm proud.

## Mechanical

- Board top face 11.5 mm under the top panel's underside: the XT connectors'
  axes sit at the body's mid-height. Under the screen (x 2.5–48.5, y 5–31)
  nothing is taller than 8.1 mm.
- The toggle's shoulder seats on a 2.6 mm printed boss under the panel.
- The guard's magnet (6 × 3 mm N52) sits in the guard tip over the hall
  sensor U6.
- Mounting: 4 × M2.5 at 3.6 mm from each corner.

## Bring-up (first boards)

1. Bare board: no shorts VIN–GND, VOUT–DRONE_NEG, +5V–GND, +3V3–GND.
2. USB-C only: +5V ≈ 4.4 V, +3V3 = 3.3 V; flash over the Tag-Connect (J6).
3. Bench supply 12 V, 100 mA limit, on the battery XT60 (guard closed): the
   screen wakes, nothing on the drone side.
4. Reverse the bench supply: nothing happens, nothing warms.
5. Probe tests with resistors on the drone side (open, 1 kΩ, 18 Ω, 0.3 Ω), then
   a capacitor bank (2200 µF) for pre-charge, then a real drone.
6. Measure, and set in firmware: the board's own capacitance on VOUT as the
   probe sees it (the model assumes 4.1 µF; about 9.5 µF is likely at 3 V),
   the INA181 offset, the cell-divider gains.

## Open items to confirm

- Vishay AC05 15 Ω pulse rating for 6 J per resistor (12 J abort, two in
  parallel) from the vendor's pulse curve.
- The toggle: sample C&K 7107, E-Switch 100SP5T1B1M2QE and NKK M2000
  side by side; all fit the footprint.
- The 6-layer price from PCBWay (the cost tally uses an estimate).
- Battery range limits found in simulation: a 6S pack at 3.5 V/cell with a
  10 W video transmitter is refused (gap stays above 12 V); a reversed 14S pack
  on the drone side plus a pack on the input (two faults at once) exceeds the
  100 V parts.
