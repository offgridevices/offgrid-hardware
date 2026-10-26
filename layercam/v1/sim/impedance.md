# LayerCam v1: impedance of the coupled pairs

Computed by `sim/impedance.py` (field solver `sim/fieldsolve.py`). Widths and gaps from `src/board.py` DIFF; stackups from `src/pcb.py`; JLCPCB's published figures for JLC06161H-3313 (jlcpcb.com/impedance, read 26 Oct 2026).

## Stackup used

| | value | source |
|---|---|---|
| outer copper (F.Cu / B.Cu) | 0.035 mm (1 oz finished) | pcb.STACKUP6 = JLCPCB table |
| L1-L2 / L5-L6 prepreg | 3313 x1, 0.0994 mm, Dk 4.10 | pcb.STACKUP6 = JLCPCB table (Dk table: 3313 4.1) |
| inner copper | 0.0152 mm (0.5 oz) | JLCPCB |
| cores / middle prepreg | 0.55 mm Dk 4.6 / 2116 0.1088 mm Dk 4.16 | JLCPCB (not on the outer-layer path) |
| solder mask | 30.5 um on laminate, 15.2 um on copper, Dk 3.8 | JLCPCB calculator parameters |
| track etch | top narrower by 12.7 um each side (trapezoid) | assumed, typical |
| ground fill beside a pair (main) | 0.177 mm from the track (CLEAR 0.127 + 0.05) | src/pcb.py, src/stitch.py |
| USB board | 2 layers, core 1.13 mm (USB_T 1.2 - 0.07), Dk 4.5, 35 um copper, ground fill both sides at 0.18 mm | pcb.STACKUP2, geometry.USB_T, stitch.py |

## Field solver checked against exact results

| case | reference (ohm) | solver (ohm) | error |
|---|---|---|---|
| stripline b 0.4, w 0.2, t 0, er 4 (Cohn, exact) | 50.25 | 49.97 | -0.56 % |
| microstrip w/h 1, t 0, er 4.1 (Hammerstad-Jensen) | 73.31 | 72.55 | -1.04 % |
| microstrip w/h 2, t 0, er 4.1 (Hammerstad-Jensen) | 50.29 | 49.86 | -0.85 % |

## Main board, outer layers over In1 / In4, as designed

Closed forms first (no coplanar ground; the IPC-2141 single-line formula is known to read high for w/h near 1, Hammerstad-Jensen is within about 1 % for the bare line); then the field solver, bare and with the ground fill that stitch.py pours beside the pair. Zdiff = 2 Zodd, Zcm = Zeven / 2.

| pair | w / gap (mm) | IPC-2141 Z0 / Zdiff | H-J Z0 / Zdiff (no mask) | H-J + mask Z0 / Zdiff | solver Z0 (single) | solver Zdiff, no fill | solver Zdiff, fill at 0.177 | solver Zcm | target |
|---|---|---|---|---|---|---|---|---|---|
| MIPI | 0.100 / 0.150 | 60.9 / 108.0 | 65.2 / 115.7 | 62.2 / 110.3 | 61.7 | 106.0 | 104.9 | 34.9 | 100 +-10 % |
| USB | 0.120 / 0.150 | 56.1 / 99.5 | 60.2 / 106.9 | 57.6 / 102.2 | 57.3 | 98.8 | 97.8 | 32.2 | 90 +-10 % |

### Sensitivity (MIPI 0.10 / 0.15, field solver, no fill)

| change | Zdiff (ohm) |
|---|---|
| as above | 106.0 |
| no solder mask | 116.7 |
| rectangular track (no etch) | 101.0 |
| prepreg +10 % (0.109 mm) | 109.1 |
| prepreg -10 % (0.089 mm) | 102.3 |
| Dk 3.9 | 107.8 |
| Dk 4.3 | 104.3 |
| track -0.015 mm (over-etch) | 114.5 |
| track +0.015 mm | 98.4 |

## Widths and gaps that hit the targets (main board outer layers)

Field solver, solder mask on, ground fill at 0.177 mm beside the pair (the fill stitch.py pours; where the three MIPI lanes run side by side there is no fill between them, so the bare figure applies there). Rules: track >= 0.100 mm, gap >= 0.127 mm.

| w (mm) | gap (mm) | Zdiff bare | Zdiff with fill | Zodd | Zcm |
|---|---|---|---|---|---|
| 0.090 | 0.127 | 106.2 | 105.2 | 53.1 | 37.3 |
| 0.090 | 0.150 | 110.1 | 109.0 | 55.1 | 36.5 |
| 0.090 | 0.175 | 113.4 | 112.1 | 56.7 | 35.8 |
| 0.090 | 0.200 | 115.9 | 114.6 | 58.0 | 35.2 |
| 0.090 | 0.250 | 119.4 | 117.9 | 59.7 | 34.3 |
| 0.100 | 0.127 | 102.4 | 101.4 | 51.2 | 35.7 |
| 0.100 | 0.150 | 106.0 | 104.9 | 53.0 | 34.9 |
| 0.100 | 0.175 | 109.1 | 107.9 | 54.5 | 34.3 |
| 0.100 | 0.200 | 111.5 | 110.2 | 55.7 | 33.7 |
| 0.100 | 0.250 | 114.8 | 113.3 | 57.4 | 32.9 |
| 0.110 | 0.127 | 98.8 | 97.9 | 49.4 | 34.2 |
| 0.110 | 0.150 | 102.3 | 101.2 | 51.1 | 33.5 |
| 0.110 | 0.175 | 105.1 | 104.0 | 52.6 | 32.9 |
| 0.110 | 0.200 | 107.4 | 106.2 | 53.7 | 32.4 |
| 0.110 | 0.250 | 110.5 | 109.1 | 55.2 | 31.7 |
| 0.120 | 0.127 | 95.6 | 94.7 | 47.8 | 32.9 |
| 0.120 | 0.150 | 98.8 | 97.8 | 49.4 | 32.2 |
| 0.120 | 0.175 | 101.5 | 100.4 | 50.8 | 31.7 |
| 0.120 | 0.200 | 103.7 | 102.5 | 51.8 | 31.2 |
| 0.120 | 0.250 | 106.6 | 105.3 | 53.3 | 30.5 |
| 0.130 | 0.127 | 92.6 | 91.7 | 46.3 | 31.7 |
| 0.130 | 0.150 | 95.6 | 94.7 | 47.8 | 31.1 |
| 0.130 | 0.175 | 98.2 | 97.1 | 49.1 | 30.5 |
| 0.130 | 0.200 | 100.2 | 99.1 | 50.1 | 30.1 |
| 0.130 | 0.250 | 103.0 | 101.7 | 51.5 | 29.4 |
| 0.140 | 0.127 | 89.8 | 88.9 | 44.9 | 30.5 |
| 0.140 | 0.150 | 92.7 | 91.7 | 46.3 | 30.0 |
| 0.140 | 0.175 | 95.1 | 94.1 | 47.6 | 29.4 |
| 0.140 | 0.200 | 97.0 | 95.9 | 48.5 | 29.0 |
| 0.140 | 0.250 | 99.6 | 98.4 | 49.8 | 28.4 |
| 0.150 | 0.127 | 87.2 | 86.4 | 43.6 | 29.5 |
| 0.150 | 0.150 | 89.9 | 89.0 | 45.0 | 28.9 |
| 0.150 | 0.175 | 92.2 | 91.2 | 46.1 | 28.5 |
| 0.150 | 0.200 | 94.0 | 93.0 | 47.0 | 28.1 |
| 0.150 | 0.250 | 96.5 | 95.4 | 48.3 | 27.5 |

- **MIPI**: 0.120 / 0.150 mm (the smallest change from the board's rule that is within 4 % of target and stays inside +-10 % for a track 0.015 mm narrower or wider at the same pitch) gives 98.8 ohm bare, 97.8 ohm beside the fill; 106.0 / 92.3 ohm with the etch error.
- **USB**: 0.140 / 0.150 mm (the smallest change from the board's rule that is within 4 % of target and stays inside +-10 % for a track 0.015 mm narrower or wider at the same pitch) gives 92.7 ohm bare, 91.7 ohm beside the fill; 98.9 / 87.0 ohm with the etch error.

Ordering with JLCPCB's impedance control (they adjust the widths to their process) is the other half of the fix: state 100 ohm differential on L1/L6 for the MIPI class and 90 ohm for USB.

## USB board (2 layers, 1.13 mm core)

The pair runs on F with ground fill beside it (stitch.py, 0.18 mm away) and the B ground fill 1.13 mm below: a coplanar waveguide with ground, the side fill doing most of the work.

| w / gap (mm) | fill gap (mm) | Zdiff | Zcm | note |
|---|---|---|---|---|
| 0.20 / 0.15 | 0.18 | 101.9 | 55.1 | as designed |
| 0.20 / 0.15 | none | 111.6 | 84.9 | if the fill is cut back near the pair |
| 0.20 / 0.127 | 0.18 | 96.8 | 55.6 | |
| 0.20 / 0.150 | 0.18 | 101.9 | 55.1 | |
| 0.20 / 0.200 | 0.18 | 110.8 | 54.0 | |
| 0.25 / 0.127 | 0.18 | 91.4 | 52.7 | |
| 0.25 / 0.150 | 0.18 | 96.0 | 52.2 | |
| 0.25 / 0.200 | 0.18 | 104.3 | 51.3 | |
| 0.30 / 0.127 | 0.18 | 87.2 | 50.2 | |
| 0.30 / 0.150 | 0.18 | 91.5 | 49.8 | |
| 0.30 / 0.200 | 0.18 | 99.2 | 49.0 | |
| 0.35 / 0.127 | 0.18 | 83.8 | 48.1 | |
| 0.35 / 0.150 | 0.18 | 87.8 | 47.7 | |
| 0.35 / 0.200 | 0.18 | 95.0 | 47.0 | |

Closest to 90 ohm with the fill where stitch.py puts it: **0.25 / 0.127 mm, 91.4 ohm**.

The USB board's pair is 25 mm long (routed usb/layercam-usb.kicad_pcb: D+ 18.1 mm, D- 25.1 mm of track including the joins between the receptacle's two rows): 144 ps of flight time at 5.7 ps/mm, against USB 2.0 high speed's 500 ps minimum edge (10-90 %). That is past the lumped limit (a sixth of the edge, 83 ps), so the impedance does show: 101.9 ohm against 90 reflects 6 % of each edge, small next to the receiver's margin and to the SH cable after it (6 unshielded parallel wires at 1 mm pitch: roughly 100-150 ohm differential, not controlled), and the D+ / D- length difference (see above) is mostly the joins between the receptacle's two contact rows.

## Checks

- PASS solver within 1.5 % of stripline b 0.4, w 0.2, t 0, er 4 (-0.56 %)
- PASS solver within 1.5 % of microstrip w/h 1, t 0, er 4.1 (-1.04 %)
- PASS solver within 1.5 % of microstrip w/h 2, t 0, er 4.1 (-0.85 %)
- PASS main MIPI 0.10 / 0.15: Zdiff 106.0 (bare) / 104.9 (with fill) against 100 +-10 % (90-110)
- WARN main MIPI 0.10 / 0.15 with the track 0.015 mm narrower / wider (same pitch): 114.5 / 98.4 ohm against 90-110
- PASS main USB 0.12 / 0.15: Zdiff 98.8 (bare) / 97.8 (with fill) against 90 +-10 % (81-99)
- WARN main USB 0.12 / 0.15 with the track 0.015 mm narrower / wider (same pitch): 106.0 / 92.3 ohm against 81-99
- PASS recommended main MIPI 0.120 / 0.150: 98.8 / 97.8 ohm, 92.3-106.0 across +-0.015 mm etch, inside 90-110
- PASS recommended main USB 0.140 / 0.150: 92.7 / 91.7 ohm, 87.0-98.9 across +-0.015 mm etch, inside 81-99
- WARN USB board 0.20 / 0.15 with fill at 0.18: Zdiff 101.9 against 90 +-10 %

## Verdict

- **MIPI 0.10 / 0.15 mm: 106.0 ohm bare, 104.9 ohm beside the ground fill: inside 100 +-10 %, but high.** A 0.015 mm over-etch takes it to 114.5 ohm (outside). Recommended: **0.120 / 0.150 mm** (98.8 / 97.8 ohm; 92.3-106.0 across the etch). The receiver end is forgiving (RV1106 MIPI ZID 80-125 ohm; two lanes well under 1 Gbit/s for 2304 x 1296 at 30 fps RAW10), so the current rule would very likely work; the change costs nothing.
- **USB (main) 0.12 / 0.15 mm: 98.8 ohm bare, 97.8 beside the fill: at the top edge of 90 +-10 %** (106.0 with a 0.015 mm over-etch). Recommended: **0.140 / 0.150 mm** (92.7 / 91.7 ohm; 87.0-98.9 across the etch).
- **USB board 0.20 / 0.15 mm: 101.9 ohm.** A 2-layer 1.2 mm board cannot put a plane close under the pair; the side fill sets the impedance. 0.25 / 0.127 mm with the fill where it is gives 91.4 ohm. A 6 % reflection on a short run ahead of an uncontrolled cable: WARN, not FAIL.
- USB layer change on the main board (pairs.py: F to B and back): no ground via beside the signal vias (stitching keeps 1.2 mm off every via). Add one ground via within about 1 mm of each transition so the return current can move between In1 and In4.

**no FAIL, 3 WARN**
