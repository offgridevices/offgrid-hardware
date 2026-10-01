# Ridge 3 mounting holes: where they are, and why they stay

The question: the holes sit 5.25 mm in from the edges of a 36 mm board,
each with a slot cut to its corner.  Could they move out toward the
corners to free room?  Four screws hold the board in every direction, and
the grommets hold it in the screws.

The answer: **the holes stay on the 25.5 mm pattern, slotted.  The room
comes from the copper kept away round them instead.**  Revision 2 does
that (`src/pcb.py`: `HOLE_COPPER_R`, `HOLE_INNER_CLEAR`, `HOLE_PART_R`,
`GROMMET_SILK_R`).

The owner's instincts were right on three counts:

- The board cannot work loose sideways.  With four slotted corners, any
  two screws lock it in its plane.  The rubber lets it move about
  0.3 mm per 1000 g.
- The fabs would allow holes further out: JLCPCB's and PCBWay's rules
  allow holes out to about a 31 mm pattern.
- Rev 1 kept far more copper away from the holes than it needed: about
  161 mm² of every copper layer.

## Why the holes do not move

**The frame decides where the holes go.**  The 21 current 3-3.6" frames
surveyed, from 15 makers, take these patterns:

| Pattern | Frames | Notes |
|---|---|---|
| 25.5 mm | 9 at the FC position, 3 more elsewhere on the frame | 5 of the 7 cinewhoops. The frames' holes are Φ2 / M2 |
| 26.5 mm | 3 | GEPRC CL30, BetaFPV X-Knight 35, Lumenier QAV-S Mini |
| 27, 28 or 29 mm | **0** | "A little further out" fits no frame |
| 30.5 mm | 4, all M3 | No cinewhoops. SpeedyBee calls it "not recommended" on the Bee35 |

**Further apart, the board bends more in a crash, under its parts.**
This comes from a plate finite-element model with a 1500 g, 0.5 ms
pulse. It was checked against closed-form plates (0.2-2 %) and
reproduced by a separate Ritz model. Strain at the parts:

- 27 mm: +17 to +26 %
- 30.5 mm: +59 to +85 %

The 25.5 mm spacing is already past the beam's stiffest spacing
(21.1 mm).

**The gyro gains nothing.**  At 30.5 mm, the frame's rocking reaches the
IMU about 1.1 dB worse. Grommet hardness moves that by 6-9 dB.

**The room freed is in the wrong place.**  Moving the holes out frees
edge strips beside the corners. At most 30 mm² per side reaches the
interior, and nothing changes within ±9.65 mm of the centre.

**Ridge 3 is not unusual.**  25.5 mm AIO boards of 36.5-39 mm put their
holes 5.5-6.75 mm from the edge: the SpeedyBee F405 AIO V2 and F745 AIO,
and the T-Motor F7 45A AIO.

## What changed instead

Rev 1 kept all copper on every layer 3.1 mm from each hole's centre.
That suits an M3 nut, not the M2 grommet the board is made for.

| Rule | Rev 1 | Rev 2 | What sets it |
|---|---|---|---|
| Copper, outer layers | 3.1 mm round the hole | **2.6 mm** | The M2 grommet's flange (4.4-4.5 mm), or an M2 washer (radius 2.5), + 0.1 |
| Copper, inner layers | 3.1 mm round the hole | **0.5 mm from the hole's and slot's walls** (the ESC's battery planes: 1.0 mm) | Nothing bears on the inner layers. The fab asks 0.2 mm. The ESC's VBAT planes keep 1 mm so a cracked wall cannot bring a metal screw to the pack's positive |
| Parts | 3.1 mm | 3.1 mm (unchanged) | The nut driver's socket, and crash strain about 20 % higher in the ring 2.25-2.75 mm from the hole |
| Silkscreen | 3.1 mm | 2.75 mm | The flange, compressed |

Per board, this frees about +246 mm² of plane copper on the FC and
+339 mm² on the ESC. On the ESC, the battery planes now reach the battery
pads: the ring round each pad goes from 51 % open copper to 72 %.

The holes keep their slots.  Here is how the slot compares with a closed
hole:

- The slot's softer support gives 13 % less crash strain in the interior.
- The slot also gives 0.6 dB less rocking transmission to the gyro.
- A closed hole would free only slivers of copper.
- A closed hole seats the whole flange (the slot leaves 77-79 %).

An open U-notch is worse than either, and is what BetaFPV gave up for
"real holes".

## Hardware

- **Grommets:** M3-to-M2 silicone grommets for a 3.0-3.5 mm board hole,
  with a flange of 4.4-4.5 mm. Examples are FlyingTech type B
  (4.4 x 6.6 mm), or the "M2 x 6.6 mm" grommets SpeedyBee ships with its
  F405 AIO. Not the ones made for 4 mm holes.
- **Screws and nuts:** M2 screws, and M2 nylon-insert or aluminium nuts.
- **No M3 hard mount.**  The frames' 25.5 mm holes are M2, and an M3 nut
  needs 3.1-3.2 mm of bare board round the hole. A hard mount, if wanted,
  is M2 or nylon.
- **Board gap: at least 6 mm** from the ESC's top to the FC's bottom.
  - The FC's two 3.0 mm inductors and its 1210 capacitor C7 sit over the
    ESC's motor and battery pads.
  - 3.0 mm part + 2.0 mm wire joint + 0.5 mm the grommets give in a
    1500 g crash leaves 0.5 mm.
  - Solder the battery lead into its pads from below and trim it flush
    on top.
  - The simulations assume 5 mm. A wider gap only cools the boards.

## Still to check on the bench

- Measure an assembled grommet's flange. At 5.0 mm or more, compressed,
  it would reach 2.6-3.0 mm. The copper is fine either way (rubber on
  solder mask). Parts already keep 3.1 mm.
- Pull-test a grommet in a slotted hole and a closed one.
- Fit the actual nut driver on a board.
- Fly two grommet hardnesses. The mount's rocking modes, 830-1000 Hz on
  nominal grommets, sit in the motor band.
- Confirm JLC's mouse-bite tab width. Its capabilities page says at least
  5 mm, while `panel.py` uses 3.4 mm. With 5 mm tabs, the slotted FC has
  no room for corner tabs.

The analysis (frame survey, area sweeps, plate FE, hand calculations, fab
rules, each cross-checked by a separate model) was run for this decision.
Its numbers are summarised here.
