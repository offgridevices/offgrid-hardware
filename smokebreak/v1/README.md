# SmokeBreak v1 — the board

The circuit board inside the Arm (`../design/arm/`): a 1S–14S smoke stopper,
per-cell battery checker and miswiring tester with a colour screen, a guarded
metal toggle and a status-light ring.

| | |
|---|---|
| Board | 94 × 52 mm, 6 layers, 1.6 mm, black mask, white silk, ENIG |
| Assembly | every SMD part on the top (PCBWay, one side); connectors, toggle and the two pre-charge resistors hand-soldered from the bottom |
| Checks | KiCad 10 DRC: 0 errors, 0 warnings, 0 unconnected; netlist matches `src/circuit.py` pad for pad; power-path simulations (`sim/SIM.md`, ngspice 47, 22/22 pass); firmware logic model (`firmware/`, 236 tests) |

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
| `src/` | the board as code: `circuit.py` (netlist), `parts.py` (every part, MPN, LCSC), `place.py` (placement), `make.py` → `route_run.py` → `finish_run.py` / `repair_run.py` → `final.py` → `polish.py` (clean-up pass) → `fab.py` (`pipeline.sh` runs up to `final.py`) |
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
   separately: XT60PW-M, XT30PW-M, JST B3B/B4B/B5B/B6B/B7B-XH-A (top entry, one
   each), the toggle, 2 × Vishay AC05 3.9 Ω, and the drone leads: an XT60H
   female on 12 AWG and an XT30U female on 16 AWG silicone, 50–75 mm each.
3. The display (1.9" 170 × 320 ST7789, 30-pin 0.5 mm FPC) is bought separately
   and plugs into J7.

## Hand assembly (from the bottom; the bottom silkscreen says what goes where)

The battery end carries everything a pack plugs into: XT60 and XT30 male
through the end wall, and right behind them the balance well, five top-entry
sockets with pin 1 (the black wire) of every one on the same line at the
front. The drone end has no connector on the board: two short leads with
female plugs are soldered to pads.

1. Pre-charge resistors R_PRE, R_PRE2 (end to end along the back): lie them
   flat on the top, bend the leads, solder, trim to 1.5 mm.
2. Balance sockets J12 (2S), J11 (3S), J10 (4S), J9 (5S), J5 (6S), mouths up,
   pin 1 in the square pad at the front. The bottom silkscreen names
   each one, with an arrow at pin 1 (black wire). USB-C (back wall) is
   already on.
3. XT60 (J1) and XT30 (J2) male at the battery end, mating face past the
   edge: seat fully, solder with a big iron (the pads are on the power
   planes), trim to 1.5 mm.
4. Drone leads: strip 5 mm, tin, push through J3 (XT60 lead, 12 AWG) and J4
   (XT30 lead, 16 AWG) from the top, red to the square pad (+, marked on
   both sides), solder from the bottom; a 2.5 mm zip tie through each
   pair's slots is the strain relief. The minus pads face each other, by
   the shunt.
5. Toggle SW1 last, with the lever upright; check it sits 8.9 mm proud.
6. Four M3 × 6 screws with DIN 125 washers into the case bosses (2 to
   3 kgf·cm is plenty; the plated rings take the washers, nothing else is
   within 4.7 mm of a hole).

## Mechanical

- Board top face 11.5 mm under the top panel's underside: the XT connectors'
  axes sit at the body's mid-height. Under the screen (x 3–49, y 1–27)
  nothing is taller than 8.5 mm (XT60 8.2, the pre-charge resistors 7.5).
- The balance well: one recess in the face over x 12–48.6, y 29–52 (board),
  floored at the sockets' tops (7 mm); 2S–6S on the face's front lip, an
  arrow at each pin 1. Every plug's black wire lands at the front, 8–40 mm
  from its pack's power plug, so short-lead packs reach.
- Back wall: USB-C (J8). Drone end: the two leads through a grommeted slot.
- The toggle's shoulder seats on a 2.6 mm printed boss under the panel.
- The guard's magnet (6 × 3 mm N52) sits in the guard tip over the hall
  sensor U6 (board 73.2, 36.6).
- Mounting: 4 × M3, 5 mm in from each edge; plated 7.4 mm rings for DIN 125
  washers (7.0 mm), a 9.4 mm keep-out round each with no track or via on
  any layer, so a tight screw cannot crack anything.
- Underside art: the OffGrid lockup at the exact centre, SmokeBreak along
  the back on the same centre line, the US flag (Flag Code proportions) at
  the drone end's front corner; all four sit in via-free fields.

## Bring-up (first boards)

1. Bare board: no shorts VIN–GND, VOUT–DRONE_NEG, +5V–GND, +3V3–GND.
2. USB-C only: +5V ≈ 4.4 V, +3V3 = 3.3 V; flash over the SWD pogo pads (J6, underside) or USB DFU.
3. Bench supply 12 V, 100 mA limit, on the battery XT60 (guard closed): the
   screen wakes, nothing on the drone side.
4. Reverse the bench supply: nothing happens, nothing warms.
5. Probe tests with resistors on the drone side (open, 1 kΩ, 18 Ω, 0.3 Ω), then
   a capacitor bank (2200 µF) for pre-charge, then a real drone.
6. Measure, and set in firmware: the board's own capacitance on VOUT as the
   probe sees it (the model assumes 4.1 µF; about 9.5 µF is likely at 3 V),
   the INA181 offset, the cell-divider gains.

## Open items to confirm

- Vishay AC05 3.9 Ω pulse rating: the datasheet chart gives about 11 J per
  resistor for a single pulse; the 12 J abort puts 6 J on each (two in
  series, about 55 %). Confirm with Vishay for repeated attempts.
- The toggle: sample C&K 7107, E-Switch 100SP5T1B1M2QE and NKK M2000
  side by side; all fit the footprint.
- The 6-layer price from PCBWay (the cost tally uses an estimate).
- Battery range limits found in simulation: a 6S pack at 3.5 V/cell with a
  10 W video transmitter is refused (gap stays above 12 V); a reversed 14S pack
  on the drone side plus a pack on the input (two faults at once) exceeds the
  100 V parts.
