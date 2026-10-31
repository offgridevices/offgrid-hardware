# LayerCam v1: impedance of the controlled tracks (PCBWay)

Computed by `sim/impedance.py` (field solver `sim/fieldsolve.py`) from what the boards are built with: stackups from `src/pcb.py` (STACKUP6, STACKUP2), pair rules from `src/board.py` (DIFF, RF_W), clearances from `src/pcb.py` and `src/stitch.py`.

## Stackup (src/pcb.py STACKUP6, PCBWay's regular 6-layer 1.6 mm build No. 1)

| layer | type | thickness (mm) | Dk |
|---|---|---|---|
| F.Cu | copper | 0.0350 | - |
| dielectric 1 | prepreg 2116 | 0.1195 | 4.45 |
| In1.Cu | copper | 0.0350 | - |
| dielectric 2 | core FR4 | 0.4300 | 4.60 |
| In2.Cu | copper | 0.0350 | - |
| dielectric 3 | prepreg 7628 | 0.1750 | 4.74 |
| In3.Cu | copper | 0.0350 | - |
| dielectric 4 | core FR4 | 0.4300 | 4.60 |
| In4.Cu | copper | 0.0350 | - |
| dielectric 5 | prepreg 2116 | 0.1195 | 4.45 |
| B.Cu | copper | 0.0350 | - |

Outer layers: F.Cu over 0.1195 mm (Dk 4.45) to In1, B.Cu over 0.1195 mm (Dk 4.45) to In4; copper 0.035 mm. Solder mask (PCBWay publishes none, ASSUMED): 15 um on copper, 30 um on laminate, Dk 3.8. Track etch: top 12.7 um narrower a side (ASSUMED). USB board: 2 layers, 1.20 mm board, core 1.13 mm, Dk 4.5, copper 0.035 mm (STACKUP2). Ground fill: 0.177 mm from other nets on the main board, 0.180 mm on the USB board (CLEAR + 0.05, stitch.py).

## Field solver checked against exact results

| case | reference (ohm) | solver (ohm) | error |
|---|---|---|---|
| stripline b 0.4, w 0.2, t 0, er 4 (Cohn, exact) | 50.25 | 49.97 | -0.56 % |
| microstrip w/h 1, t 0, er 4.1 (Hammerstad-Jensen) | 73.31 | 72.56 | -1.02 % |
| microstrip w/h 2, t 0, er 4.1 (Hammerstad-Jensen) | 50.29 | 49.87 | -0.82 % |

## Differential pairs

*Bare*: the pair alone over its plane; *fill*: with the ground fill 0.177 mm beside it (stitch.py; where MIPI lanes run side by side there is no fill between them, so the bare figure applies there). The etch columns move the track 0.015 mm narrower / wider at the same pitch, with the fill. Zdiff = 2 Zodd.

| pair | layer | w / gap (mm) | bare | fill | narrower / wider | no mask | target | |
|---|---|---|---|---|---|---|---|---|
| MIPI | F | 0.120 / 0.150 | 102.0 | 100.6 | 107.8 / 93.9 | 111.1 | 100 +-10 % | PASS |
| USB | F | 0.150 / 0.130 | 90.7 | 89.5 | 95.5 / 83.7 | 98.4 | 90 +-10 % | PASS |
| USB | B | 0.150 / 0.130 | 90.7 | 89.5 | 95.5 / 83.7 | 98.4 | 90 +-10 % | PASS |
| USB board | F (2-layer) | 0.250 / 0.130 | - | 92.1 | 97.0 / 87.1 | 99.9 | 90 +-10 % | PASS |

Closed forms for the bare pairs on F (no mask, no fill; IPC-2141 reads high for w/h near 1): MIPI IPC-2141 104.4, Hammerstad-Jensen 109.5 ohm; USB IPC-2141 91.3, Hammerstad-Jensen 96.1 ohm.

## Antenna feed (RF netclass, 50 ohm single-ended)

ANT_FEED / ANT: one 0.18 mm track on B.Cu over In4 (board.RF_W), about 5.5 mm from the AP6256's antenna pin through the 0402 pi match to the U.FL, with the B ground fill 0.177 mm away on both sides. Reported as a plain microstrip and as the coplanar line with ground the fill makes (the one that is built).

| width (mm) | microstrip (no fill) | with the fill (CPWG) | narrower / wider | no mask | Hammerstad-Jensen (bare microstrip) | target |
|---|---|---|---|---|---|---|
| 0.180 | 50.8 | 48.8 | 51.0 / 46.7 | 51.7 | 52.9 | 50 +-10 % |

50.0 ohm with the fill is reached at **0.170 mm** (50.1 ohm; 52.2 ohm as a plain microstrip). The current 0.18 mm is inside +-10 %: no change needed.

At 5.5 GHz the 5.5 mm run is 0.18 wavelengths long, so its impedance matters (at 2.4 GHz 0.08).

The routed USB board's pair: D+ 24.3 mm, D- 18.4 mm of track (including the joins between the receptacle's two contact rows), about 138 ps: close to the lumped limit for USB 2.0's 500 ps edges; the 6-wire SH cable after it is uncontrolled anyway.

## Ordering

Order with PCBWay's impedance control: **100 ohm differential on L1 (F.Cu) for the MIPI class, 90 ohm differential on L1 / L6 (F.Cu, B.Cu) for USB, 50 ohm single-ended on L6 (B.Cu) for the antenna feed**, all referenced to the adjacent ground plane (In1 / In4), +-10 %. Give them the widths below and let them trim to their process; ask for their stackup report and the mask they use. The USB board (2-layer, 1.2 mm) needs no impedance control (its pair is short and the fill sets it). Via-in-pad under the RV1106 must be ordered as resin-filled and capped.

## Checks

- PASS src/pcb.py STACKUP6 matches PCBWay's published build No. 1
- PASS solver within 1.5 % of stripline b 0.4, w 0.2, t 0, er 4 (-0.56 %)
- PASS solver within 1.5 % of microstrip w/h 1, t 0, er 4.1 (-1.02 %)
- PASS solver within 1.5 % of microstrip w/h 2, t 0, er 4.1 (-0.82 %)
- PASS MIPI 0.120 / 0.150 on F: 93.9-107.8 ohm (bare, beside the fill, +-0.015 mm etch) inside 90-110
- PASS MIPI gap 0.150 mm at or above the main board's 0.127 mm clearance
- PASS USB 0.150 / 0.130 on F: 83.7-95.5 ohm (bare, beside the fill, +-0.015 mm etch) inside 81-99
- PASS USB gap 0.130 mm at or above the main board's 0.127 mm clearance
- PASS USB 0.150 / 0.130 on B: 83.7-95.5 ohm (bare, beside the fill, +-0.015 mm etch) inside 81-99
- PASS USB gap 0.130 mm at or above the main board's 0.127 mm clearance
- PASS USB board 0.250 / 0.130 on the USB board: 87.1-97.0 ohm (bare, beside the fill, +-0.015 mm etch) inside 81-99
- PASS USB board gap 0.130 mm at or above the usb board's 0.130 mm clearance
- PASS RF 0.180 mm on B with the fill: 48.8 ohm (46.7-51.0 across the etch) inside 45-55
- PASS RF 0.180 mm on B as a plain microstrip (where the fill is cut back): 50.8 ohm

## Verdict

- **MIPI 0.120 / 0.150 mm: PASS** (93.9-107.8 ohm)
- **USB 0.150 / 0.130 mm: PASS** (83.7-95.5 ohm)
- **USB board 0.250 / 0.130 mm: PASS** (87.1-97.0 ohm)
- **RF 0.180 mm on B: PASS** (48.8 ohm with the fill, 46.7-51.0 across the etch; 50.8 ohm as a plain microstrip)
- JLCPCB (the earlier fab, 0.0994 mm 3313 prepreg) is no longer modelled.

**no FAIL, 0 WARN**
