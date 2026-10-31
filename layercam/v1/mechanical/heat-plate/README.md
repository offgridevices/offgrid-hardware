# LayerCam v1: the heatsink on the RV1106

**The fitted part is a stock 14 x 14 x 10 mm aluminium heatsink on thermal tape.** It is centred at board
(0, 15.9) on the RV1106. With it the camera is rated for a chamber up to **63 C**: in snapshot mode every
part stays inside its rating up to 63.3 C (`sim/thermal.md`, model uncertainty about +-10 K: measure a built
camera in a 63 C oven). The original 65 C goal needs the optional CNC block (65.7 C) or bent sheet (65.1 C)
below. Prusa's printed case stays unchanged in every option.

## The fitted heatsink

**What to buy:** LCSC C286230 and a 14 x 14 mm piece of 3M 8810 tape (the README's order list). Any other part must meet all of these:

- 14 x 14 mm footprint, **10 mm tall at most** (the case leaves 0.3 mm over a 10 mm part here; taller does not
  fit; shorter fits further towards the SoC's centre and works slightly less well: 8 mm at board (0, 17.4)
  gives 63.0 C, 6 mm at (0, 18.4) 62.4 C).
- Aluminium, black anodised preferred (emissivity ~0.85; bare aluminium radiates far less).
- Pre-applied thermal tape (3M 8810 class, about 0.25 mm), or fit 0.25 mm thermal tape / pad yourself.
- Examples:
  - **LCSC C286230, XSD1690-058**: 14 x 14 x 10 mm, black oxide. Its drawing (Refinelink "LY12", read
    27 Oct 2026) confirms 14 x 14 x 10 with a 1.6 mm base and 5 x 5 cross-cut pin fins 1.5 mm wide, LY12
    (2A12) aluminium, black anodised. No tape: add 3M 8810 (or 8805) cut to 14 x 14.
  - Generic Raspberry Pi heatsink kits with a 14 x 14 x 10 (or shorter) black aluminium part and tape.
  - LCSC C5250881 (G11-03-02, listed "14*6 mm") and Electrokit 41037418 (XSD-14146) are 6 mm-tall
    alternatives.

**Where it goes** (board coordinates, mm; F, the board's back face, which faces the lid):

- Footprint: **x -7.0 .. +7.0, y 8.9 .. 22.9** (centre (0, 15.9)).
- The RV1106 package is x -6.15 .. +6.15, y 13.25 .. 25.55. The heatsink covers **9.65 mm of its 12.3 mm**
  (y 13.25 .. 22.9). It leaves the package's +y end (y 22.9 .. 25.55, 2.65 mm) uncovered and **overhangs the
  package's -y edge by 4.35 mm** (y 8.9 .. 13.25, towards the camera module and the lens window) and each
  side by 0.85 mm (x +-6.15 .. +-7.0).
- Why there: the case's rounded end comes down over the package's +y end (Z 29 at board y 25.5), and the camera
  module starts at board y 8.4 (the heatsink stops 0.5 mm short of it).
- Under the overhang the heatsink's underside is 1.10 mm above the board (0.85 mm package + 0.25 mm tape;
  1.05 mm with a 0.80 mm minimum package). **Parts under the overhang: 0.8 mm tall at most** (0402s; 0603
  capacitors up to 0.8 mm). LED1 at (8.8, 14.0) stays 1.0 mm clear of the heatsink's edge.

**How to fit it** (after reflow, before the board goes into the case; step 2 of the README's *How to build one*):

1. Clean the RV1106's top with isopropyl alcohol; let it dry.
2. Put the tape on the heatsink's base if it has none.
3. Place it square, centred at board (0, 15.9): its +y edge 2.65 mm short of the package's +y end, its sides
   0.85 mm past the package's.
4. Press firmly for 10 s. Let the tape cure (3M 8810: full bond after about 24 h at room temperature).

## All the options

| option | part | snapshot mode keeps every part in rating up to | snap_night at 63 C: RV1106 / AP6256 / SC3336 | live view (day / night) up to | board needs | assembly | rough cost (no quote) |
|---|---|---|---|---|---|---|---|
| none | - | 60.7 C | 93 / 86 / 86 C | 31 / 29 C | - | - | - |
| **fitted** | **14 x 14 x 10 heatsink on tape (LCSC C286230), board (0, 15.9)** | **63.3 C** | **89.5 / 84.6 / 84.7 C** | **36 / 34 C** | **keepout: parts <= 0.8 mm under x -7..7, y 8.9..22.9** | **clean, stick, press** | **about $0.3** |
| 14 x 14 x 6 | 14 x 14 x 6 heatsink on tape, board (0, 18.4) | 62.4 C | 90.7 / 85.1 / 85.2 C | 35 / 33 C | parts <= 0.8 mm under its overhang | the same | about $0.3 |
| pad into the shell | best stock 14 x 14 (5 mm, board (0, 17.9)) + 5 mm TG-A6200 on the fin tops | 62.5 C | 90.6 / 85.1 / 85.2 C | 35 / 33 C | the same | fiddly | about $3 |
| 20 x 20 x 6 copper | **does not fit** (modelled as if it did) | 63.5 C | 89.1 / 84.4 / 84.6 C | 37 / 35 C | - | - | - |
| optional upgrade | CNC 6061 block, black anodised, two gap pads | 65.7 C | 84.8 / 82.2 / 82.4 C | 42 / 41 C | nothing | drop it in before the lid | $4-8 at 100, $15-30 at 5 |
| optional upgrade | bent 1.5 mm 5052 sheet, black anodised, two gap pads | 65.1 C | 86.1 / 82.8 / 83.0 C | 41 / 39 C | nothing | the same | $1.5-3 at 100, $8-15 at 5 |

Figures from `sim/thermal.py` (PCBWay's 6-layer build), each path computed by `plate.py` from its geometry
(`heat_paths.json`). Costs are estimates, not quotes. For a 65 C chamber, fit the CNC block (meets it by 0.7 K)
or the sheet (0.1 K) instead of the heatsink; both reach the lid through its 3.35 mm plastic, about 49 K/W plus
81 K/W from the lid's outside, the only path out that the unchanged case offers.

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

## Optional upgrade for a 65 C chamber: CNC block

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

## Optional upgrade: bent sheet

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
- Mass: 2.9 g. Same pads, holding, tolerance and assembly as the CNC block.
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

## The 14 x 14 x 6 alternative

- **Size:** centred at board (0, 18.4), nearly over the whole package, a 14 x 14 mm heatsink can only be
  **6 mm** tall: the shell's curve over the package's +y end sets the limit (0.9 mm left).
  - It then overhangs the package by 1.85 mm on the +Y side, 1.25 mm above
    the board. Only 0402 / 0603 parts may sit there.
  - Taller parts must move towards the module: 8 mm at board (0, 17.4), 10 mm at (0, 15.9) (the fitted part).
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
- `heatsink_14x14x10.stl` (the fitted part, as its envelope), `heatsink_14x14x6.stl`, `cnc_block.stl`,
  `sheet_bracket.stl`: the parts in the lens frame.
- `drawing.png`: plan, section at X = 0, and the sheet's flat pattern.
- `heat_paths.json`: the thermal paths that `sim/thermal.py` reads.

STEP is not written: trimesh has no STEP writer, and nothing was installed to
add one. Give PCBWay's CNC and sheet-metal services the STL plus the
dimensions above, or redraw the two parts in a CAD tool from them.
