# LayerCam Pro v1: impedance of the controlled tracks (PCBWay)

Computed by `sim/impedance.py` (field solver `sim/fieldsolve.py`) from what the board is built with: the stackup from `src/pcb.py` (STACKUP6), pair rules from `src/board.py` (DIFF), clearances from `src/pcb.py` and `src/stitch.py`. LayerCam Pro is one 6-layer board with LayerCam v1's stackup; its controlled tracks are the image sensor's two MIPI data lanes and clock, which leave the sensor's balls on B.Cu over In4 and reach the RV1106 on F.Cu over In1 (src/pairs.py). LayerCam v1's 2-layer USB board and its 90 ohm pair are gone: USB (firmware flashing only) runs a few centimetres from the edge connector to the SoC as ordinary tracks. There is no antenna feed on the board: the ESP32-C6-MINI-1U carries its own antenna socket.

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

Outer layers: F.Cu over 0.1195 mm (Dk 4.45) to In1, B.Cu over 0.1195 mm (Dk 4.45) to In4 (both ground planes, layout_main.zones()); copper 0.035 mm. Solder mask (PCBWay publishes none, ASSUMED): 15 um on copper, 30 um on laminate, Dk 3.8. Track etch: top 12.7 um narrower a side (ASSUMED). Ground fill: 0.177 mm from other nets (CLEAR + 0.05, stitch.py).

## Field solver checked against exact results

| case | reference (ohm) | solver (ohm) | error |
|---|---|---|---|
| stripline b 0.4, w 0.2, t 0, er 4 (Cohn, exact) | 50.25 | 49.97 | -0.56 % |
| microstrip w/h 1, t 0, er 4.1 (Hammerstad-Jensen) | 73.31 | 72.56 | -1.02 % |
| microstrip w/h 2, t 0, er 4.1 (Hammerstad-Jensen) | 50.29 | 49.87 | -0.82 % |

## Differential pairs

*Bare*: the pair alone over its plane; *fill*: with the ground fill 0.177 mm beside it (stitch.py; where the lanes run side by side there is no fill between them, so the bare figure applies there). The etch columns move the track 0.015 mm narrower / wider at the same pitch, with the fill. Zdiff = 2 Zodd. B.Cu over In4 is the mirror of F.Cu over In1 (the same 2116 prepreg), so the two layers read the same.

| pair | layer | w / gap (mm) | bare | fill | narrower / wider | no mask | target | |
|---|---|---|---|---|---|---|---|---|
| MIPI | F over In1 | 0.120 / 0.150 | 102.0 | 100.6 | 107.8 / 93.9 | 111.1 | 100 +-10 % | PASS |
| MIPI | B over In4 | 0.120 / 0.150 | 102.0 | 100.6 | 107.8 / 93.9 | 111.1 | 100 +-10 % | PASS |

Closed forms for the bare MIPI pair (no mask, no fill; IPC-2141 reads high for w/h near 1): F IPC-2141 104.4, Hammerstad-Jensen 109.5 ohm; B IPC-2141 104.4, Hammerstad-Jensen 109.5 ohm.

## Ordering

Order with PCBWay's impedance control: **100 ohm differential on L1 (F.Cu, over In1) and L6 (B.Cu, over In4) for the MIPI class, 0.12 / 0.15 mm**, referenced to the adjacent ground plane, +-10 %. Let them trim to their process; ask for their stackup report and the mask they use. No other track needs impedance control. Via-in-pad under the RV1106 must be ordered as resin-filled and capped.

## Checks

- PASS src/pcb.py STACKUP6 matches PCBWay's published build No. 1
- PASS solver within 1.5 % of stripline b 0.4, w 0.2, t 0, er 4 (-0.56 %)
- PASS solver within 1.5 % of microstrip w/h 1, t 0, er 4.1 (-1.02 %)
- PASS solver within 1.5 % of microstrip w/h 2, t 0, er 4.1 (-0.82 %)
- PASS MIPI 0.120 / 0.150 on F over In1: 93.9-107.8 ohm (bare, beside the fill, +-0.015 mm etch) inside 90-110
- PASS MIPI gap 0.150 mm at or above the board's 0.127 mm clearance
- PASS MIPI 0.120 / 0.150 on B over In4: 93.9-107.8 ohm (bare, beside the fill, +-0.015 mm etch) inside 90-110
- PASS MIPI gap 0.150 mm at or above the board's 0.127 mm clearance

## Verdict

- **MIPI 0.120 / 0.150 mm on F over In1 and B over In4: PASS** (93.9-107.8 ohm)
- No antenna feed on the board (the ESP32-C6-MINI-1U's socket is on the module); LayerCam v1's USB board and its 90 ohm pair are gone.

**no FAIL, 0 WARN**
