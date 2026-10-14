# SmokeBreak v1 (compact)

A handheld smoke stopper, LiPo checker and miswiring tester.
- **Powers itself:** from any 2S–14S pack, or from USB-C. A 1S pack needs USB, because the 5 V supply starts at 6 V.
- **Face:** a 2.25" bar screen, a guarded flip-up arm switch inside a status-light ring, and one Limit rocker.
- **Case:** 97 × 56 × 15 mm. Every mechanical number lives in `src/geometry.py`, and both the board and the case read it.

| | |
|---|---|
| Board | 91.6 × 50.6 mm, 6 layers, 1.6 mm thick, 1 oz copper on every layer, black mask, white silk, ENIG |
| Assembly | Every SMD part is on the top side (PCBWay, one side). The plugs, sockets and toggle are hand-soldered. |
| Case | Printed in 3 colours: top shell, floor, switch guard, rocker paddle, translucent light ring, white text inlays |
| Checks | See the *Verification* section at the end. |

## Files

| Path | What |
|---|---|
| `smokebreak.kicad_pcb` / `.kicad_pro` / `.kicad_dru` | The board (KiCad 10). |
| `fab/smokebreak-gerbers.zip` | Gerbers and drill files: upload these for the bare board. |
| `fab/smokebreak-bom-pcbway.csv` | Assembly BOM: manufacturer part numbers, LCSC numbers, SMD/THT, notes. |
| `fab/smokebreak-cpl.csv` | Pick-and-place file (top side, SMD parts only). |
| `fab/smokebreak-netlist.csv` | Every pad and its net, checked against `src/circuit.py`. |
| `fab/smokebreak.step` | The assembled board in 3D. |
| `enclosure/out/*.step`, `*.stl` | The case parts: `top`, `bottom` (floor), `guard`, `rocker`, `ring_inlay`, `text_inlay`. `assembly.step` holds everything in place. |
| `enclosure/out/fit_check.txt` | Case-to-board interference and clearance report. |
| `enclosure/enclosure.py`, `check.py` | The case as code (CadQuery 2.8), and its fit check. |
| `src/` | The board as code. The flow is: `geometry.py` → `circuit.py` → `parts.py` → `place.py` → `spread.py` (writes `place_legal.py`) → `make.py` → `route_run.py` → `finish_run.py` / `repair_run.py` → `final.py` → `fab.py`. |
| `sim/` | Power-path simulations (ngspice). |
| `firmware/` | Reference model of every firmware decision, with tests. |

## Ordering the board (PCBWay)

1. **PCB:** upload `fab/smokebreak-gerbers.zip` with these settings:
   - 6 layers, 91.6 × 50.6 mm, FR-4 TG150, 1.6 mm thick.
   - **1 oz outer and 1 oz inner copper.** The 25 A path uses the inner planes.
   - Min track/space 4/4 mil, min hole 0.2 mm.
   - **Black** solder mask, **white** silkscreen, **ENIG**, vias tented.
2. **Assembly:** turnkey, top side only. Upload `fab/smokebreak-bom-pcbway.csv` and `fab/smokebreak-cpl.csv`.
   - Two parts have no LCSC stock: the 40 A fuse **2822HC40-RTR** and the 3.9 Ω resistors **D2TO020C3R900FRE3**. PCBWay sources them by part number from Digi-Key or Mouser; their BOM lines say so.
   - The THT lines are shipped loose and not fitted: XT60PW-M, XT30PW-M, JST B3B/B4B/B5B/B6B/B7B-XH-A (one each), the C&K 7107 toggle, and the two drone leads.
   - The drone leads are an XT60H female on 12 AWG and an XT30U female on 16 AWG silicone wire, 50–75 mm each.
3. **Display:** EastRising ER-TFT2.25-1 (76 × 284, 8-pin 0.5 mm FPC), bought separately. Ask for the IPS version.

## Printing the case

Print with 0.4 mm nozzle, 0.2 mm layers, PETG or ASA (PLA softens in a hot car).

| Part | Orientation | Notes |
|---|---|---|
| `top` | Face down | Use supports only inside the balance well (its floor plate is a bridge 2.7 mm up). Print `text_inlay` (white) and `ring_inlay` (translucent) in the same job as extra colours. |
| `bottom` | Inside up | Flat. |
| `guard` | On its side | Accent colour. |
| `rocker` | Cap down | |

Hardware:
- 3 × M3 heat-set inserts (M3 × 5.7). They go into the top shell's bosses, 6.5 mm deep holes.
- 3 × M3 × 8 button-head screws.
- 4 × Bumpon feet, Ø10 mm.
- Ø2 × 20 mm steel dowel for the guard hinge.
- Ø2 × 12 mm steel dowel for the rocker pivot.
- Ø6 × 3 mm N52 disc magnet, glued into the guard tip.

## Hand assembly

1. **Balance sockets:** J12 (2S), J11 (3S), J10 (4S), J9 (5S) and J5 (6S), mouths up. Pin 1 (the square pad) goes at the front; the bottom silkscreen names each socket and arrows pin 1.
2. **Battery plugs:** XT60 (J1) and XT30 (J2) male at the battery end. Seat them fully and solder with a big iron, because the pads sit on power planes.
3. **Drone leads:** strip 5 mm and tin. Solder the XT60 lead to J3 and the XT30 lead to J4, red to + (marked on both sides).
4. **Toggle SW1 last,** lever upright.
5. **Lead length:** trim every lead to 1.0 mm or less under the board. The floor leaves 1.3 mm.
6. **Case assembly:**
   1. Press the inserts into the top shell.
   2. Load the guard pin along its groove, then fit the guard.
   3. Fit the rocker and its pin.
   4. Tape the display into its pocket, with the FPC folded under to J7.
   5. Drop in the board.
   6. Hook the floor's tongue into the battery-end groove and close the floor. Its end tab clamps the drone leads.
   7. Fit the 3 screws.

## Bring-up (first boards)

1. Bare board: check there are no shorts VIN–GND, VOUT–DRONE_NEG, +5V–GND or +3V3–GND.
2. USB-C only: +5V should read about 4.7 V and +3V3 should read 3.3 V. Flash over the SWD pogo pads (J6, underside) or USB DFU.
3. Bench supply 12 V with a 100 mA limit, into the battery XT60, guard closed. The screen wakes, and nothing appears on the drone side.
4. Reverse the bench supply: nothing happens and nothing gets warm.
5. Probe tests with resistors on the drone side (open, 1 kΩ, 18 Ω, 0.3 Ω). Then a 2200 µF capacitor bank for pre-charge. Then a real drone.

## Open items to confirm on the first build

- **Pre-charge resistors:** D2TO020 pulse energy. The datasheet curve gives about 10 J at 100 ms. The 12 J abort puts 6 J on each resistor. Bench-test repeated attempts.
- **Display:** confirm with EastRising that the panel is IPS and the controller is ST7789P3. Check the FPC contact side against J7 (FH12, bottom contact) and the fold.
- **Guard height:** the guard is 17.9 mm tall because of the C&K 7107's lever. A short-lever toggle would make it lower.
- **Guard sensor:** it reads "open" only past about 40° (12.9 mT closed, under 1.5 mT at 40°). Firmware treats a partly open guard as closed.
- **First print:** check the well plate bridge, the rocker feel (0.2 mm nub gap), and the press fits of both dowels.

## Verification

Filled in from the final run: see the bottom of this file.
