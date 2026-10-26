# LayerCam v1: a heat path from the RV1106 to the lid

Prusa's printed case stays unchanged. Without help, the board in this sealed
plastic box keeps every part in rating in snapshot mode only up to a chamber
temperature of about 61 C (`sim/thermal.md`). Three ways to take the SoC's
heat towards the lid's vent window were designed and modelled:

| option | part | snapshot mode keeps every part in rating up to | snap_night at 65 C: RV1106 / AP6256 / SC3336 | live view (day / night) up to | board needs | assembly | rough cost (no quote) |
|---|---|---|---|---|---|---|---|
| none | - | 60.7 C | 95 / 88 / 88 C | 31 / 29 C | - | - | - |
| 1 | 14 x 14 x 6 mm aluminium heatsink on thermal tape | 62.4 C | 93 / 87 / 87 C | 35 / 33 C | nothing | stick it on | about $0.3 |
| 1b | 14 x 14 x 10 mm heatsink (LCSC C286230), the tallest 14 mm part that fits, at board (0, 15.9) | 63.3 C | 91 / 86 / 87 C | 36 / 34 C | overhangs the package 3.6 mm towards the module | stick it on | about $0.3 |
| 1c | best stock 14 x 14 (5 mm tall, board (0, 17.9)) + 5 mm TG-A6200 on the fin tops pressed into the shell | 62.5 C | 93 / 87 / 87 C | 35 / 33 C | nothing | fiddly | about $3 |
| 1d | 20 x 20 x 6 copper, **does not fit** (modelled as if it did) | 63.5 C | 91 / 86 / 86 C | 37 / 35 C | - | - | - |
| **2** | **CNC 6061 block, black anodised, two gap pads** | **65.7 C** | **87 / 84 / 84 C** | **42 / 41 C** | **nothing** | **drop it in before the lid** | **$4-8 at 100, $15-30 at 5** |
| 3 | bent 1.5 mm 5052 sheet, black anodised, two gap pads | 65.1 C | 88 / 85 / 85 C | 41 / 39 C | nothing | the same as 2 | $1.5-3 at 100, $8-15 at 5 |

Figures come from `sim/thermal.py` with PCBWay's 6-layer build, with
`plate.py` computing each path from its geometry (`heat_paths.json`). The
costs are estimates, not quotes.

**Recommendation: option 2, the CNC block.** It is the only one with any
margin, and that margin is small. At 0.7 K it sits well inside the model's
roughly 10 K uncertainty, so a first board must be measured in a 65 C oven.
Option 3 is the same idea at lower cost, about 0.6 K worse, and needs a bend
shop.

Option 1 does not reach 65 C. A heatsink inside a sealed box only moves heat
into the air around it.

### Why the gain is small

The plate's path to the chamber is limited by the 3.35 mm printed lid, about
49 K/W through the plastic plus 81 K/W from the lid's outside surface. The
six 20 x 2 mm slots add little, about 370 K/W. Only metal outside the case
would change that, and that means changing the case.

## The housing, measured

All positions below are in the lens frame of `src/geometry.py`. They were
measured from the case STLs (Printables 1343977, assembled as in
`docs/housing.md`) by casting rays upward on a 0.25 mm grid.
`HOUSING_DIR=<folder with asm_*.stl> python3 plate.py` re-measures the case
and checks every part against it.

- **Lid vent window:** six through-slots, each 20.0 x 2.0 mm, spanning
  X -10..+10, centred at Y -14.5, -10.5, -6.5, -2.5, +1.5 and +5.5 (4 mm
  pitch).
  - The lid is 3.35 mm thick there: Z 38.5 underside, Z 41.85 outside.
- **Pocket under the window:** the slots open from a pocket whose ceiling is
  at Z 38.5. It spans X +-11.0 for Y -18.5..+8.0 and narrows to X +-4.25 at
  Y -21.
  - Outside the pocket the ceiling drops to Z 32. Towards the round end it
    follows the shell down to Z 27-30.
  - The free height over the board's back face is 17.6 mm in the pocket.
- **RV1106:** sits at Y -19.4 (board (0, 19.4)) and spans 12.3 x 12.3 mm.
  - Its top is at Z 21.70: the board's back face at Z 20.85 (PCBWay's 1.55
    mm finished board) plus the 0.85 mm package.
  - Its +Y half lies under the pocket. Over its -Y half the ceiling falls
    from 38.5 to about 29.

## Option 2: CNC block (recommended)

One piece of 6061-T6, machined, then black anodised. Anodising raises the
emissivity to about 0.85; the anodic layer is thin enough not to matter
under a gap pad.

- **Foot:** 12.0 x 12.0 x 2.0 mm, centred on the SoC at (0, -19.4). Its
  underside is at Z 22.75.
- **Column:** 12.0 mm (X +-6) by 6.45 mm (Y -20.0..-13.55), rising from
  Z 24.75 to Z 35.6.
- **Flange:** 2.5 mm thick, top at Z 38.1. It is the pocket outline less
  0.4 mm all round.
  - Outline points: (-5.8, -20.3), (5.8, -20.3), (7.7, -19.5), (10.6, -18.3),
    (10.6, 7.6), (-10.6, 7.6), (-10.6, -18.3), (-7.7, -19.5).
  - It covers all six slots.
- Overall height from foot underside to flange top: 15.35 mm. Mass: 7 g.
- Fit: 0.35 mm clear of the case everywhere (checked against the STLs), and
  9 mm above the camera module.
- **Gap pads:** t-Global **TG-A6200**, 6.2 W/mK, ultra-soft silicone, tacky
  on both sides.
  - Bottom: 1.5 mm, cut to 12 x 12 mm (e.g. TG-A6200-20-20-1.5, Digi-Key
    1168-TG-A6200-20-20-1.5-ND). It is squeezed to about 1.05 mm.
  - Top: 0.5 mm, cut to the flange outline, squeezed to about 0.4 mm.
  - Confirm the size codes and price with Digi-Key. Ask t-Global for the
    pressure-deflection curve and keep the compression at or under about
    30 %: at that compression the pad presses roughly 20-30 N on the QFN.
  - Thermal path: junction to block 12.2 K/W (theta-JC 8.4, pad 1.5, metal
    2.3); block to chamber 96 K/W through the lid and slots; block to the air
    inside 203 K/W.
- **Board:** no holes and no keepout beyond the SoC itself. The foot and
  column stay within the package outline. LED1 at board (8.8, 14.0) stays
  visible through slot 1, 1.9 mm from the column.
- **Holding:** nothing to screw. The pocket's walls locate the flange in X
  and Y. The lid presses the stack down through the two pads.
- **Tolerance:** the stack (lid underside to SoC top) is 16.8 mm nominal.
  - It varies by about +-0.5 mm: board +-0.16, print +-0.3, package +-0.05.
  - The two pads have about 0.45 mm of nominal compression. At the worst
    corner they barely touch or are squeezed to about 60 %.
  - Before the run, measure three printed cases and machine the column to
    suit. Or use a 2.0 mm bottom pad if the spread is wider.
- **Assembly order:**
  1. Main board into the case; camera module and cables as before.
  2. Put the bottom pad on the RV1106 and the top pad on the flange.
  3. Lower the block onto the SoC with the flange towards the lid window.
  4. Fit the lid. The pocket catches the flange. Tighten the lid screws
     evenly.

## Option 3: bent sheet

One piece of 1.5 mm 5052-H32, laser-cut, bent twice into a Z shape, then black
anodised.

- **Foot:** sits on the SoC, X +-6, Y -25.4..-13.2.
- **Web:** stands at Y -14.7..-13.2, X +-6, from Z 22.75 up to the flange.
- **Flange:** X +-10.6, Y -14.7..+7.6. It covers five slots fully and half
  of slot 1.
- **Flat pattern:** a 44.45 x 21.2 mm blank, 12 mm wide below the flange.
  - Lengths: foot 9.20, bend 3.30, web 9.35, bend 3.30, flange 19.30.
  - Bends: inside radius 1.5 mm, K 0.4, 1 x 1.5 mm relief notches at the
    flange corners.
- Mass: 2.9 g. Same pads, holding, tolerance and assembly as option 2.
- The 1.5 mm web costs about 7 K/W more than the block's column
  (junction to part 19.0 K/W); downstream it is the same lid path.

## Why a bigger off-the-shelf heatsink is no answer

- **20 x 20 mm does not fit at any height** (`plate.py`, `housing_ceiling.json`). Centred near the SoC, its -Y
  edge runs into the case's rounded end, where the ceiling is Z 21-24 at X +-10. Moved towards +Y to clear that,
  it lands on the camera module, which sits on the board's back face from Y -8.4 at Z 21.9-26. It would also sit
  on U2 (SOT-23-5, 1.45 mm) at board (-9.4, 25.2). Generic 20 x 20 x 6 copper heatsinks with tape
  (Amazon / AliExpress, many sellers) are the part the question had in mind; modelled as if they fitted they
  reach only 63.5 C.
- **Fins inside the sealed case only stir the same trapped air.** In snap_night the board reaches the inside of
  the case through 0.048 W/K, and the case reaches the chamber through 0.141 W/K. A 14 x 14 x 6 heatsink adds
  0.006 W/K from the junction to that same inside air (theta-JC 8.4 K/W plus its own 149 K/W to the air) and
  nothing to the case-to-chamber step. A 20 x 20 copper one would add 0.011 W/K.
- **A gap pad from a stock heatsink into the shell does not help either.** Over the SoC's -Y half the shell is
  the case's solid rounded end: 5-10 mm of plastic, sloping. The best any stock 14 x 14 can do with a 5 mm pad
  is about 14 mm^2 of contact on 7 mm of plastic, 0.0003 W/K. The block's flange reaches the 3.35 mm lid over
  about 2.2 cm^2 instead: 0.010 W/K straight to the chamber.

## Option 1: off-the-shelf heatsink

- **Size:** a 14 x 14 mm heatsink can only be **6 mm** tall at the SoC. The
  shell's curve over the SoC's -Y half sets the limit.
- **Position:** centre it at board (0, 18.4), 1 mm towards the module. That
  leaves 0.9 mm under the shell.
  - It then overhangs the package by 1.85 mm on the +Y side, 1.25 mm above
    the board. Only 0402 / 0603 parts may sit there.
  - An 8 mm part fits only centred at board (0, 17.2) or further. A 10 mm one
    does not fit.
- **Parts:**
  - LCSC C5250881 (G11-03-02, "14*6 mm", black: confirm it is 14 x 14 x 6).
  - Electrokit 41037418 (XSD-14146, 14 x 14 x 6 mm, 32 K/W in free air,
    tape not included).
  - Any Raspberry Pi kit 14 x 14 x 6 mm black heatsink with 3M 8810 tape.
- **Tape:** 3M 8810, 0.25 mm. About 3 K/W over the package.
- **Assembly:** peel and stick. It is the cheapest option, but it reaches
  only 62.4 C.

## Files

- `plate.py`: the parametric geometry, clearance checks and thermal paths, for the three parts and the stock
  heatsinks above.
- `measure.py` -> `housing_ceiling.json`: the case's ceiling and plastic thickness round the SoC, measured from
  the STLs; `plate.py` reads it.
  - Run it with `tools/kd python3 mechanical/heat-plate/plate.py` from
    layercam/v1. Set `HOUSING_DIR` to check against the case STLs.
- `cnc_block.stl`, `sheet_bracket.stl`, `heatsink_14x14x6.stl`: the parts in
  the lens frame.
- `drawing.png`: plan, section at X = 0, and the sheet's flat pattern.
- `heat_paths.json`: the thermal paths that `sim/thermal.py` reads.

STEP is not written: trimesh has no STEP writer, and nothing was installed to
add one. Give PCBWay's CNC and sheet-metal services the STL plus the
dimensions above, or redraw the two parts in a CAD tool from them.
