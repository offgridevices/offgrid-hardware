# LayerCam v1: temperatures in a 65 C chamber

Computed by `sim/thermal.py`: the main board as a 2D plate on a 0.5 mm grid (outline from `src/geometry.py`, part places from `src/layout_main.py`, heat from `sim/power_budget.py`), inside Prusa's printed housing in a 65 C chamber with still air. The model and every assumed number are listed at the end; the board is the placed design (routing changes the copper coverage, see the sensitivity).

The requirement cases are **snapshot mode** (`snap_day`, `snap_night`): a still at most every 10 s, the sensor in standby, the CPU at its lowest DVFS point and Wi-Fi in power-save between shots (power_budget.py has the loads). The housing's time constant is many minutes, so a 10 s cycle is modelled by its average heat; the LED junctions and the string resistors are checked at their power while lit. Live view (`day`, `night`) and the stress bound are reported, not checked; live view gets a chamber limit and a firmware rule instead.

Every case below includes the **cnc heat path** from the RV1106's top (`mechanical/heat-plate/`, chosen in *Heat paths compared*). The side button has been removed from the design (test pads instead).

Board: 17.2 cm^2 a face; in-plane conductance 0.0584 W/K per square (copper coverage F 55 %, In1 90 %, In2 50 %, In3 85 %, In4 90 %, B 55 %). SoC exposed pad to the planes: 1.13 K/W through 25 filled vias.

## Verdict

**Snapshot mode at 65 C, with the cnc heat path: PASS (marginal)** (0 FAIL, 5 WARN). Every part stays inside its rating up to a **66 C** chamber: a margin of 0.7 K, inside the model's +-10 K uncertainty, so the first board must be measured in a 65 C oven before this is called a pass.

| at 65 C, cnc heat path | snap_day | snap_night | live day | live night |
|---|---|---|---|---|
| RV1106 junction | 86.4 C | 86.7 C | 108.7 C | 109.9 C |
| AP6256 (85 C) | 83.7 C | 84.0 C | 104.9 C | 106.3 C |
| SC3336 sensor (85 C) | 84.0 C | 84.2 C | 104.3 C | 105.6 C |
| USB-C (80 C) | 78.4 C | 78.7 C | 90.3 C | 91.7 C |
| crystals (85 C) | 82.8 C | 83.1 C | 102.1 C | 103.3 C |
| board max | 83.5 C | 83.8 C | 103.1 C | 104.3 C |
| LED ring (average) | 66.7 C | 75.2 C | 68.5 C | 109.9 C |
| IR LED junction while lit | 66.7 C | 81.1 C | 68.5 C | 115.8 C |
| heat in the housing | 0.79 W | 0.93 W | 1.77 W | 2.50 W |

Heat paths (snap_night at 65 C; chamber limit for snapshot mode):

- bare board: RV1106 95.1, AP6256 87.9, SC3336 88.0 C; snapshot in rating to **60.7 C** (first: crystals Y2 / Y3, oscillator Y4); live view to 31 C / 29 C.
- 1 heatsink 14x14x6: RV1106 92.6, AP6256 86.9, SC3336 87.0 C; snapshot in rating to **62.4 C** (first: crystals Y2 / Y3, oscillator Y4); live view to 35 C / 33 C.
- 2 CNC block: RV1106 86.7, AP6256 84.0, SC3336 84.2 C; snapshot in rating to **65.7 C** (first: SC3336 sensor (camera module)); live view to 42 C / 41 C.
- 3 bent sheet: RV1106 88.0, AP6256 84.6, SC3336 84.8 C; snapshot in rating to **65.1 C** (first: SC3336 sensor (camera module)); live view to 41 C / 39 C.

- Within 3 K of their rating in snapshot mode at 65 C: SC3336 sensor (camera module) 84.2 / 85 C; AP6256 module (U6) 84.0 / 85 C; USB-C receptacle (USB board) 78.7 / 80 C; crystals Y2 / Y3, oscillator Y4 83.1 / 85 C; 24 MHz crystal Y1 83.0 / 85 C; status LED LED1 82.8 / 85 C; camera FFC connector J2 (XF2M) 82.6 / 85 C; DRV8837 (U7) 82.4 / 85 C; W25N02KV flash (U5) 82.2 / 85 C; SH connectors J1 / J4 (JST) 82.1 / 85 C
- String resistor (47R) while lit at night: 0.141 W against 0.235 W derated at 75 C.
- Live view stays a firmware-gated mode: every part in rating to 42 C by day and 41 C by night with the cnc path. Governor: live view only while TSADC < 85 C; snapshot mode stretches to 30 s above 84 C; stop at 110 C; shutdown 125 C.
- AP6256 and SC3336 run above 75 C in snapshot mode (full RF and best image end there): WARN, they work.
- Model uncertainty about +-10 K (optimistic bracket 1 K lower on the SoC); the snapshot currents are ASSUMED. Measure on the first board and rerun.

## Snapshot, day (requirement)

Heat in the housing: **0.79 W** (U1 0.49, U6 0.18, camera module 0.04, U3 0.03, U2 0.02, U5 0.01, U4 0.01, L1 0.01).

| | value |
|---|---|
| housing wall | 70.6 C (5.6 K over the chamber) |
| air inside (mean of board and wall) | 76.4 C |
| main board mean / max | 82.2 / 83.5 C |
| board heat out: faces / edge to the pocket / into the camera module | 0.38 / 0.13 / 0.02 W |
| lid-slot air exchange | 0.05 W |
| LED ring (average) | 66.7 C (0.00 W average; 0.02 W out through the front wall) |
| RV1106 | 0.28 W; board under the pad 83.4 C, at the package edge 82.9 C; Tj 84.6 C (pad path) / 86.4 C (thetaJB 12.5 from the edge) |

| part | temperature (C) | limit (C) | margin (K) | limit from |
|---|---|---|---|---|
| SC3336 sensor (camera module) | 84.0 | 85 | +1.0 | operating max; best image to 60 C (SmartSens) |
| AP6256 module (U6) | 83.7 | 85 | +1.3 | operating max; full RF only to 75 C |
| USB-C receptacle (USB board) | 78.4 | 80 | +1.6 | -30..80 C (catalogue) |
| crystals Y2 / Y3, oscillator Y4 | 82.8 | 85 | +2.2 | -40..85 C |
| 24 MHz crystal Y1 | 82.7 | 85 | +2.3 | -40..85 C (YXC) |
| status LED LED1 | 82.5 | 85 | +2.5 | -40..85 C (KENTO) |
| camera FFC connector J2 (XF2M) | 82.3 | 85 | +2.7 | -30..85 C incl. rise (Omron) |
| DRV8837 (U7) | 82.1 | 85 | +2.9 | ambient -40..85 C (TI) |
| W25N02KV flash (U5) | 81.9 | 85 | +3.1 | -40..85 C (Winbond) |
| SH connectors J1 / J4 (JST) | 81.9 | 85 | +3.1 | -25..85 C incl. rise (JST) |
| U.FL J5 | 81.8 | 90 | +8.2 | -40..90 C (Hirose) |
| RV1106 surroundings (internal air) | 76.4 | 85 | +8.6 | ambient operating max (T3-2) |
| housing wall (PETG/ASA print) | 70.6 | 80 | +9.4 | PETG softens ~ 80 C (Tg); ASA/PC higher |
| X6S capacitors (4.7uF, 10uF, 22uF) under the SoC (B face) | 83.5 | 105 | +21.5 | X6S: -55..105 C (Murata) |
| X6S capacitors (4.7uF, 10uF, 22uF) at the bucks | 82.9 | 105 | +22.1 | X6S: -55..105 C (Murata) |
| PicoBlade J3 | 82.0 | 105 | +23.0 | -40..105 C (Molex) |
| IR LEDs (ring), case | 66.7 | 100 | +33.3 | operating -40..100 C (JNJ) |
| TEMT6000 light sensor (ring) | 66.7 | 100 | +33.3 | -40..100 C (Vishay) |
| RV1106 junction (U1) | 86.4 | 125 | +38.6 | Tj max (datasheet 4.1) |
| TLV62569 0.9 V (U2) junction | 83.6 | 125 | +41.4 | TJ max (SLVSDG1C 6.3) |
| X7S capacitors (1uF) under the SoC (B face) | 83.5 | 125 | +41.5 | X7S: -55..125 C (Murata) |
| inductor L1 (FPA252012D) | 83.0 | 125 | +42.0 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| X7S capacitors (1uF) at the bucks | 82.9 | 125 | +42.1 | X7S: -55..125 C (Murata) |
| EA3036C junction (U3) | 82.4 | 125 | +42.6 | TJ range (datasheet) |
| inductor L4 (FPA252012D) | 82.2 | 125 | +42.8 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| TLV62569 Wi-Fi (U4) junction | 82.1 | 125 | +42.9 | TJ max (SLVSDG1C 6.3) |
| inductor L3 (FPA252012D) | 82.1 | 125 | +42.9 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L2 (FPA252012D) | 81.9 | 125 | +43.1 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L5 (FPA252012D) | 81.7 | 125 | +43.3 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| IR LEDs (ring), junction | 66.7 | 115 | +48.3 | Tj max (JNJ) |

![snap_day](thermal_snap_day.png)

## Snapshot, night, IR LEDs lit 2 s of every 10 s (requirement)

Heat in the housing: **0.93 W** (U1 0.49, U6 0.18, ring resistors 0.08, ring LEDs 0.06, camera module 0.04, U3 0.03, U2 0.02, U5 0.01, U4 0.01, L1 0.01).

| | value |
|---|---|
| housing wall | 70.9 C (5.9 K over the chamber) |
| air inside (mean of board and wall) | 76.7 C |
| main board mean / max | 82.4 / 83.8 C |
| board heat out: faces / edge to the pocket / into the camera module | 0.38 / 0.13 / 0.02 W |
| lid-slot air exchange | 0.05 W |
| LED ring (average) | 75.2 C (0.14 W average; 0.12 W out through the front wall) |
| RV1106 | 0.28 W; board under the pad 83.6 C, at the package edge 83.1 C; Tj 84.8 C (pad path) / 86.7 C (thetaJB 12.5 from the edge) |

| part | temperature (C) | limit (C) | margin (K) | limit from |
|---|---|---|---|---|
| SC3336 sensor (camera module) | 84.2 | 85 | +0.8 | operating max; best image to 60 C (SmartSens) |
| AP6256 module (U6) | 84.0 | 85 | +1.0 | operating max; full RF only to 75 C |
| USB-C receptacle (USB board) | 78.7 | 80 | +1.3 | -30..80 C (catalogue) |
| crystals Y2 / Y3, oscillator Y4 | 83.1 | 85 | +1.9 | -40..85 C |
| 24 MHz crystal Y1 | 83.0 | 85 | +2.0 | -40..85 C (YXC) |
| status LED LED1 | 82.8 | 85 | +2.2 | -40..85 C (KENTO) |
| camera FFC connector J2 (XF2M) | 82.6 | 85 | +2.4 | -30..85 C incl. rise (Omron) |
| DRV8837 (U7) | 82.4 | 85 | +2.6 | ambient -40..85 C (TI) |
| W25N02KV flash (U5) | 82.2 | 85 | +2.8 | -40..85 C (Winbond) |
| SH connectors J1 / J4 (JST) | 82.1 | 85 | +2.9 | -25..85 C incl. rise (JST) |
| U.FL J5 | 82.0 | 90 | +8.0 | -40..90 C (Hirose) |
| RV1106 surroundings (internal air) | 76.7 | 85 | +8.3 | ambient operating max (T3-2) |
| housing wall (PETG/ASA print) | 70.9 | 80 | +9.1 | PETG softens ~ 80 C (Tg); ASA/PC higher |
| X6S capacitors (4.7uF, 10uF, 22uF) under the SoC (B face) | 83.8 | 105 | +21.2 | X6S: -55..105 C (Murata) |
| X6S capacitors (4.7uF, 10uF, 22uF) at the bucks | 83.2 | 105 | +21.8 | X6S: -55..105 C (Murata) |
| PicoBlade J3 | 82.3 | 105 | +22.7 | -40..105 C (Molex) |
| IR LEDs (ring), case | 77.2 | 100 | +22.8 | operating -40..100 C (JNJ) |
| TEMT6000 light sensor (ring) | 75.2 | 100 | +24.8 | -40..100 C (Vishay) |
| IR LEDs (ring), junction | 81.1 | 115 | +33.9 | Tj max (JNJ) |
| RV1106 junction (U1) | 86.7 | 125 | +38.3 | Tj max (datasheet 4.1) |
| TLV62569 0.9 V (U2) junction | 83.9 | 125 | +41.1 | TJ max (SLVSDG1C 6.3) |
| X7S capacitors (1uF) under the SoC (B face) | 83.8 | 125 | +41.2 | X7S: -55..125 C (Murata) |
| inductor L1 (FPA252012D) | 83.3 | 125 | +41.7 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| X7S capacitors (1uF) at the bucks | 83.2 | 125 | +41.8 | X7S: -55..125 C (Murata) |
| EA3036C junction (U3) | 82.7 | 125 | +42.3 | TJ range (datasheet) |
| inductor L4 (FPA252012D) | 82.4 | 125 | +42.6 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| TLV62569 Wi-Fi (U4) junction | 82.4 | 125 | +42.6 | TJ max (SLVSDG1C 6.3) |
| inductor L3 (FPA252012D) | 82.4 | 125 | +42.6 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L2 (FPA252012D) | 82.2 | 125 | +42.8 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L5 (FPA252012D) | 82.0 | 125 | +43.0 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| 47R string resistor (ring), power while lit | 0.141 W | 0.235 W at 75 C | +0.094 W | 0.25 W to 70 C, 0 at 155 C |

![snap_night](thermal_snap_night.png)

## Live view, day: streaming (reported, not required)

Heat in the housing: **1.77 W** (U1 0.97, U6 0.43, camera module 0.20, U2 0.06, L1 0.04, U3 0.03, U5 0.02, U4 0.01, cable, connectors 0.01).

| | value |
|---|---|
| housing wall | 75.8 C (10.8 K over the chamber) |
| air inside (mean of board and wall) | 88.3 C |
| main board mean / max | 100.7 / 103.1 C |
| board heat out: faces / edge to the pocket / into the camera module | 0.88 / 0.28 / -0.02 W |
| lid-slot air exchange | 0.15 W |
| LED ring (average) | 68.5 C (0.00 W average; 0.04 W out through the front wall) |
| RV1106 | 0.55 W; board under the pad 102.9 C, at the package edge 101.9 C; Tj 105.1 C (pad path) / 108.7 C (thetaJB 12.5 from the edge) |

| part | temperature (C) | limit (C) | margin (K) | limit from |
|---|---|---|---|---|
| AP6256 module (U6) | 104.9 | 85 | -19.9 | operating max; full RF only to 75 C |
| SC3336 sensor (camera module) | 104.3 | 85 | -19.3 | operating max; best image to 60 C (SmartSens) |
| crystals Y2 / Y3, oscillator Y4 | 102.1 | 85 | -17.1 | -40..85 C |
| 24 MHz crystal Y1 | 101.5 | 85 | -16.5 | -40..85 C (YXC) |
| camera FFC connector J2 (XF2M) | 101.4 | 85 | -16.4 | -30..85 C incl. rise (Omron) |
| status LED LED1 | 101.1 | 85 | -16.1 | -40..85 C (KENTO) |
| W25N02KV flash (U5) | 100.3 | 85 | -15.3 | -40..85 C (Winbond) |
| DRV8837 (U7) | 100.3 | 85 | -15.3 | ambient -40..85 C (TI) |
| SH connectors J1 / J4 (JST) | 100.1 | 85 | -15.1 | -25..85 C incl. rise (JST) |
| USB-C receptacle (USB board) | 90.3 | 80 | -10.3 | -30..80 C (catalogue) |
| U.FL J5 | 100.2 | 90 | -10.2 | -40..90 C (Hirose) |
| RV1106 surroundings (internal air) | 88.3 | 85 | -3.3 | ambient operating max (T3-2) |
| X6S capacitors (4.7uF, 10uF, 22uF) under the SoC (B face) | 103.1 | 105 | +1.9 | X6S: -55..105 C (Murata) |
| X6S capacitors (4.7uF, 10uF, 22uF) at the bucks | 102.2 | 105 | +2.8 | X6S: -55..105 C (Murata) |
| housing wall (PETG/ASA print) | 75.8 | 80 | +4.2 | PETG softens ~ 80 C (Tg); ASA/PC higher |
| PicoBlade J3 | 100.1 | 105 | +4.9 | -40..105 C (Molex) |
| RV1106 junction (U1) | 108.7 | 125 | +16.3 | Tj max (datasheet 4.1) |
| TLV62569 0.9 V (U2) junction | 104.5 | 125 | +20.5 | TJ max (SLVSDG1C 6.3) |
| inductor L1 (FPA252012D) | 104.0 | 125 | +21.0 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| X7S capacitors (1uF) under the SoC (B face) | 103.1 | 125 | +21.9 | X7S: -55..125 C (Murata) |
| X7S capacitors (1uF) at the bucks | 102.2 | 125 | +22.8 | X7S: -55..125 C (Murata) |
| TLV62569 Wi-Fi (U4) junction | 100.6 | 125 | +24.4 | TJ max (SLVSDG1C 6.3) |
| EA3036C junction (U3) | 100.6 | 125 | +24.4 | TJ range (datasheet) |
| inductor L4 (FPA252012D) | 100.3 | 125 | +24.7 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L3 (FPA252012D) | 100.2 | 125 | +24.8 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L2 (FPA252012D) | 100.0 | 125 | +25.0 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L5 (FPA252012D) | 99.9 | 125 | +25.1 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| IR LEDs (ring), case | 68.5 | 100 | +31.5 | operating -40..100 C (JNJ) |
| TEMT6000 light sensor (ring) | 68.5 | 100 | +31.5 | -40..100 C (Vishay) |
| IR LEDs (ring), junction | 68.5 | 115 | +46.5 | Tj max (JNJ) |

![day](thermal_day.png)

## Live view, night: streaming with the IR LEDs on (reported, not required)

Heat in the housing: **2.50 W** (U1 0.97, U6 0.43, ring resistors 0.42, ring LEDs 0.30, camera module 0.20, U2 0.06, L1 0.04, U3 0.03, U5 0.02, cable, connectors 0.02, U4 0.01).

| | value |
|---|---|
| housing wall | 77.4 C (12.4 K over the chamber) |
| air inside (mean of board and wall) | 89.7 C |
| main board mean / max | 102.0 / 104.3 C |
| board heat out: faces / edge to the pocket / into the camera module | 0.88 / 0.28 / -0.02 W |
| lid-slot air exchange | 0.16 W |
| LED ring (average) | 109.9 C (0.72 W average; 0.53 W out through the front wall) |
| RV1106 | 0.54 W; board under the pad 104.1 C, at the package edge 103.1 C; Tj 106.3 C (pad path) / 109.9 C (thetaJB 12.5 from the edge) |

| part | temperature (C) | limit (C) | margin (K) | limit from |
|---|---|---|---|---|
| AP6256 module (U6) | 106.3 | 85 | -21.3 | operating max; full RF only to 75 C |
| SC3336 sensor (camera module) | 105.6 | 85 | -20.6 | operating max; best image to 60 C (SmartSens) |
| crystals Y2 / Y3, oscillator Y4 | 103.3 | 85 | -18.3 | -40..85 C |
| camera FFC connector J2 (XF2M) | 102.8 | 85 | -17.8 | -30..85 C incl. rise (Omron) |
| 24 MHz crystal Y1 | 102.7 | 85 | -17.7 | -40..85 C (YXC) |
| status LED LED1 | 102.4 | 85 | -17.4 | -40..85 C (KENTO) |
| W25N02KV flash (U5) | 101.7 | 85 | -16.7 | -40..85 C (Winbond) |
| DRV8837 (U7) | 101.6 | 85 | -16.6 | ambient -40..85 C (TI) |
| SH connectors J1 / J4 (JST) | 101.4 | 85 | -16.4 | -25..85 C incl. rise (JST) |
| IR LEDs (ring), case | 111.8 | 100 | -11.8 | operating -40..100 C (JNJ) |
| USB-C receptacle (USB board) | 91.7 | 80 | -11.7 | -30..80 C (catalogue) |
| U.FL J5 | 101.6 | 90 | -11.6 | -40..90 C (Hirose) |
| TEMT6000 light sensor (ring) | 109.9 | 100 | -9.9 | -40..100 C (Vishay) |
| RV1106 surroundings (internal air) | 89.7 | 85 | -4.7 | ambient operating max (T3-2) |
| IR LEDs (ring), junction | 115.8 | 115 | -0.8 | Tj max (JNJ) |
| X6S capacitors (4.7uF, 10uF, 22uF) under the SoC (B face) | 104.3 | 105 | +0.7 | X6S: -55..105 C (Murata) |
| X6S capacitors (4.7uF, 10uF, 22uF) at the bucks | 103.5 | 105 | +1.5 | X6S: -55..105 C (Murata) |
| housing wall (PETG/ASA print) | 77.4 | 80 | +2.6 | PETG softens ~ 80 C (Tg); ASA/PC higher |
| PicoBlade J3 | 101.4 | 105 | +3.6 | -40..105 C (Molex) |
| RV1106 junction (U1) | 109.9 | 125 | +15.1 | Tj max (datasheet 4.1) |
| TLV62569 0.9 V (U2) junction | 105.7 | 125 | +19.3 | TJ max (SLVSDG1C 6.3) |
| inductor L1 (FPA252012D) | 105.2 | 125 | +19.8 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| X7S capacitors (1uF) under the SoC (B face) | 104.3 | 125 | +20.7 | X7S: -55..125 C (Murata) |
| X7S capacitors (1uF) at the bucks | 103.5 | 125 | +21.5 | X7S: -55..125 C (Murata) |
| TLV62569 Wi-Fi (U4) junction | 102.0 | 125 | +23.0 | TJ max (SLVSDG1C 6.3) |
| EA3036C junction (U3) | 101.9 | 125 | +23.1 | TJ range (datasheet) |
| inductor L4 (FPA252012D) | 101.6 | 125 | +23.4 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L3 (FPA252012D) | 101.5 | 125 | +23.5 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L2 (FPA252012D) | 101.3 | 125 | +23.7 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L5 (FPA252012D) | 101.3 | 125 | +23.7 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| 47R string resistor (ring), power while lit | 0.141 W | 0.133 W at 110 C | -0.008 W | 0.25 W to 70 C, 0 at 155 C |

![night](thermal_night.png)

## Stress bound: SoC flat out, Wi-Fi transmitting, LEDs at the high corner (reported)

Heat in the housing: **5.35 W** (U1 2.06, U6 1.44, ring resistors 0.52, ring LEDs 0.33, camera module 0.27, U2 0.23, L1 0.19, U5 0.12, cable, connectors 0.07, U3 0.06, U4 0.04, L5 0.02, L3 0.01).

| | value |
|---|---|
| housing wall | 90.5 C (25.5 K over the chamber) |
| air inside (mean of board and wall) | 119.3 C |
| main board mean / max | 148.2 / 153.3 C |
| board heat out: faces / edge to the pocket / into the camera module | 2.44 / 0.66 / 0.16 W |
| lid-slot air exchange | 0.52 W |
| LED ring (average) | 120.0 C (0.85 W average; 0.65 W out through the front wall) |
| RV1106 | 1.12 W; board under the pad 150.9 C, at the package edge 148.9 C; Tj 155.5 C (pad path) / 163.0 C (thetaJB 12.5 from the edge) |

| part | temperature (C) | limit (C) | margin (K) | limit from |
|---|---|---|---|---|
| AP6256 module (U6) | 164.8 | 85 | -79.8 | operating max; full RF only to 75 C |
| camera FFC connector J2 (XF2M) | 153.3 | 85 | -68.3 | -30..85 C incl. rise (Omron) |
| W25N02KV flash (U5) | 151.1 | 85 | -66.1 | -40..85 C (Winbond) |
| crystals Y2 / Y3, oscillator Y4 | 151.0 | 85 | -66.0 | -40..85 C |
| 24 MHz crystal Y1 | 147.4 | 85 | -62.4 | -40..85 C (YXC) |
| SH connectors J1 / J4 (JST) | 147.1 | 85 | -62.1 | -25..85 C incl. rise (JST) |
| status LED LED1 | 146.8 | 85 | -61.8 | -40..85 C (KENTO) |
| DRV8837 (U7) | 145.1 | 85 | -60.1 | ambient -40..85 C (TI) |
| U.FL J5 | 149.4 | 90 | -59.4 | -40..90 C (Hirose) |
| SC3336 sensor (camera module) | 143.6 | 85 | -58.6 | operating max; best image to 60 C (SmartSens) |
| X6S capacitors (4.7uF, 10uF, 22uF) under the SoC (B face) | 151.5 | 105 | -46.5 | X6S: -55..105 C (Murata) |
| X6S capacitors (4.7uF, 10uF, 22uF) at the bucks | 151.3 | 105 | -46.3 | X6S: -55..105 C (Murata) |
| USB-C receptacle (USB board) | 121.3 | 80 | -41.3 | -30..80 C (catalogue) |
| PicoBlade J3 | 145.4 | 105 | -40.4 | -40..105 C (Molex) |
| RV1106 junction (U1) | 163.0 | 125 | -38.0 | Tj max (datasheet 4.1) |
| inductor L1 (FPA252012D) | 161.8 | 125 | -36.8 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| TLV62569 0.9 V (U2) junction | 160.5 | 125 | -35.5 | TJ max (SLVSDG1C 6.3) |
| RV1106 surroundings (internal air) | 119.3 | 85 | -34.3 | ambient operating max (T3-2) |
| X7S capacitors (1uF) under the SoC (B face) | 151.5 | 125 | -26.5 | X7S: -55..125 C (Murata) |
| X7S capacitors (1uF) at the bucks | 151.3 | 125 | -26.3 | X7S: -55..125 C (Murata) |
| TLV62569 Wi-Fi (U4) junction | 150.5 | 125 | -25.5 | TJ max (SLVSDG1C 6.3) |
| inductor L5 (FPA252012D) | 148.4 | 125 | -23.4 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| IR LEDs (ring), case | 122.2 | 100 | -22.2 | operating -40..100 C (JNJ) |
| EA3036C junction (U3) | 146.4 | 125 | -21.4 | TJ range (datasheet) |
| inductor L2 (FPA252012D) | 146.2 | 125 | -21.2 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L3 (FPA252012D) | 145.5 | 125 | -20.5 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| TEMT6000 light sensor (ring) | 120.0 | 100 | -20.0 | -40..100 C (Vishay) |
| inductor L4 (FPA252012D) | 145.0 | 125 | -20.0 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| IR LEDs (ring), junction | 126.6 | 115 | -11.6 | Tj max (JNJ) |
| housing wall (PETG/ASA print) | 90.5 | 80 | -10.5 | PETG softens ~ 80 C (Tg); ASA/PC higher |
| 47R string resistor (ring), power while lit | 0.174 W | 0.103 W at 120 C | -0.071 W | 0.25 W to 70 C, 0 at 155 C |

![worst](thermal_worst.png)

## Sensitivity (snap_night, RV1106 Tj / board max / ring average)

| change | RV1106 Tj (C) | board max (C) | ring (C) |
|---|---|---|---|
| as above | 86.7 | 83.8 | 75.2 |
| no lid slots (vents taped or facing down) | 86.9 | 84.1 | 75.3 |
| ring not touching the front wall | 86.9 | 84.0 | 98.4 |
| copper coverage x0.7 (a more perforated routed board) | 86.7 | 84.1 | 75.2 |
| inside emissivity 0.6 (bare metal shields, lens holder) | 87.5 | 84.7 | 75.3 |
| optimistic bracket: emissivity 0.85, Nu 1.5, copper x1.2 | 85.6 | 82.4 | 75.0 |
| chamber air moving at 0.5 m/s past the housing | 85.4 | 82.4 | 73.2 |
| SoC idle 50 % higher than assumed | 94.3 | 89.6 | 75.6 |
| Wi-Fi average twice the assumed 0.05 A | 89.4 | 88.1 | 75.5 |

## Highest chamber temperature per case

Bisection on the same model: the chamber temperature at which the first part reaches its limit.

| case | every part inside its limit up to (first part there) | RV1106 Tj 125 C at | RV1106 Tj 115 C (10 K margin) at |
|---|---|---|---|
| snap_day | 66.0 C (SC3336 sensor (camera module)) | 85 C or more | 85 C or more |
| snap_night | 65.7 C (SC3336 sensor (camera module)) | 85 C or more | 85 C or more |
| day | 42.2 C (AP6256 module (U6)) | 83 C | 72 C |
| night | 40.7 C (AP6256 module (U6)) | 82 C | 71 C |
| worst | never (AP6256 module (U6)) | 17 C | 4 C |

## Firmware rules (thermal governor)

The RV1106's TSADC reads its own junction (+-3 C). In a steady state every part sits at a fixed offset from it for a given load, so a junction temperature can stand in for the hottest part. For each mode: the junction temperature at the chamber temperature where the first part reaches its rating. Live view may run while the TSADC is below that reading, less the sensor's 3 C error; above it the firmware falls back to snapshot mode.

| mode | chamber limit (first part) | RV1106 Tj there (steady state) | rule: allowed while TSADC below | at 65 C in snapshot mode the TSADC reads |
|---|---|---|---|---|
| snapshot, day | 66 C | 87 C | **84 C** | 87 C |
| snapshot, night | 66 C | 87 C | **84 C** | 87 C |
| live view, day | 42 C | 88 C | **85 C** | 87 C |
| live view, night | 41 C | 88 C | **85 C** | 87 C |

Rule set, in order (to be tuned on a board in an oven):

1. **Snapshot mode is the default**: CPU at its lowest OPP between shots, NPU off, sensor in standby, Wi-Fi power-save on 2.4 GHz.
2. **Live view** only while TSADC < 85 C; crossing it ends live view (back to snapshot mode, the user sees "live view paused: camera too warm"). In a 65 C chamber the snapshot-mode reading is 87 C.
3. TSADC > 84 C in snapshot mode: stretch the interval to 30 s, cap Wi-Fi TX power, shorten the IR flash to 1 s (the reading at which the first 85 C part reaches its rating in snapshot mode).
4. TSADC > 110 C: stop capturing (keep Wi-Fi associated, report the fault).
5. TSADC > 120 C: power the sensor and Wi-Fi down; Linux critical trip (shutdown) at 125 C.

## Heat paths from the RV1106 compared

The three parts in `mechanical/heat-plate/` (plate.py computes each path from its geometry; README.md has the parts). The junction splits its heat between the board (exposed pad, 4.1 K/W) and the part on its top (theta-JC top 8.4 K/W + pad or tape + metal); the part passes it to the air inside and, for the two that reach the lid pocket, through the 3.35 mm lid and its slots to the chamber.

| heat path | junction to part (K/W) | part to chamber (K/W) | part to inside air (K/W) | snap_night at 65 C: RV1106 / AP6256 / SC3336 / board max (C) | heat leaving by the top / straight out (W) | snapshot keeps every part in rating up to | live view (day / night) every part in rating up to |
|---|---|---|---|---|---|---|---|
| none (bare board) | - | - | - | 95.1 / 87.9 / 88.0 / 90.1 | 0.00 / 0.00 | **60.7 C** (crystals Y2 / Y3, oscillator Y4) | 31 C / 29 C |
| 1: 14 x 14 x 6 heatsink on tape | 12.0 | - | 149 | 92.6 / 86.9 / 87.0 / 88.3 | 0.07 / 0.00 | **62.4 C** (crystals Y2 / Y3, oscillator Y4) | 35 C / 33 C |
| 2: CNC 6061 block, gap pads | 12.2 | 96 | 203 | 86.7 / 84.0 / 84.2 / 83.8 | 0.21 / 0.18 | **65.7 C** (SC3336 sensor (camera module)) | 42 C / 41 C |
| 3: bent 1.5 mm 5052 sheet, gap pads | 19.0 | 115 | 238 | 88.0 / 84.6 / 84.8 / 84.7 | 0.18 / 0.15 | **65.1 C** (SC3336 sensor (camera module)) | 41 C / 39 C |

## Every part's rating against the chamber

From `src/parts.py` (descriptions, the JLCPCB catalogue's temperature field read 26 Oct 2026, the datasheets). Flagged against the snapshot-night case: a part rated below 85 C, over its rating, or within 10 K of it.

| part | rated | snap_night at 65 C (C) | live night at 65 C (C) | flag (snapshot) |
|---|---|---|---|---|
| RV1106G3 | Tj 125, ambient -20..85 | 87 | 110 |  |
| W25N02KVZEIR | -40..85 | 82 | 102 | under 10 K margin |
| AP6256 | -30..85 (full RF -20..75) | 84 | 106 | under 10 K margin |
| EA3036C | TA -40..85, TJ to 125 | 83 | 102 |  |
| TLV62569 | TJ -40..125 | 84 | 106 |  |
| DRV8837 | TA -40..85 | 82 | 102 | under 10 K margin |
| AO3400A | TJ -55..150 | 82 | 102 |  |
| crystals / oscillator (24M, 37.4M, 32k) | -40..85 | 83 | 103 | under 10 K margin |
| KT-0603G LED | -40..85 | 83 | 102 | under 10 K margin |
| XF2M-2015-1A FFC | -30..85 | 83 | 103 | under 10 K margin |
| JST SH BM06B / SM06B | -25..85 | 82 | 101 | under 10 K margin |
| Molex 53261 PicoBlade | -40..105 | 82 | 101 |  |
| Hirose U.FL | -40..90 | 82 | 102 | under 10 K margin |
| TYPE-C-31-M-12 USB-C | -30..80 | 79 | 92 | RATED BELOW 85 C; under 10 K margin |
| USBLC6-2SC6, SMF5.0CA | TJ to 125 / 150 | 79 | 92 |  |
| JNJ 850 nm IR LED (junction while lit) | -40..100, Tj 115 | 81 | 116 |  |
| TEMT6000 | -40..100 | 75 | 110 |  |
| FPA252012D inductors | not in the catalogue (typ. -40..125) | 83 | 105 | UNKNOWN rating: ask the maker |
| BLM15PD121 bead | -55..125 | 82 | 102 |  |
| 0402 / 1206 thick-film resistors | -55..155 (power derates above 70) | 84 | 104 |  |
| C0G / X7R capacitors (12p, 18p, 1n, 10n, 100n) | -55..125 | 84 | 104 |  |
| X7S capacitors (1uF) | -55..125 | 84 | 104 |  |
| X6S capacitors (4.7uF, 10uF, 22uF) | -55..105 | 84 | 104 |  |
| SC3336 module (bought) | -30..85, best image to 60 | 84 | 106 | under 10 K margin |
| CLA219 IR-cut holder (bought) | not published (plastic, NdFeB magnet) | 82 | 102 | UNKNOWN rating: ask the maker |
| Towin CCL127028MPR lens (bought) | not published | 77 | 90 | UNKNOWN rating: ask the maker |

## Model and assumptions

- Chamber 65 C, still air (no credit for the chamber fan); bed radiation 0.10 W on the front.
- Housing: outer hull 125.6 cm^2, 2 mm walls at 0.20 W/mK, emissivity 0.90; natural convection 1.32 (dT/0.05 m)^0.25 plus linearised radiation outside. Lid slots: 240 mm^2 split in two halves 11 mm apart, Cd 0.6.
- Inside: radiation board to wall with effective emissivity 0.75; still-air conduction across 8.5 / 9.8 mm gaps (F / B) with Nu 1.1; board edge to the pocket across 0.6 mm of air.
- Copper coverage per layer as listed above (ASSUMED until the board is routed; rerun on the routed board, docs/lessons.md: routing raised temperatures 15 K on Ridge 3).
- RV1106: die to exposed pad 3 K/W (ASSUMED) plus the computed via array; the datasheet thetaJB (12.5 K/W, JEDEC 2s2p) from the board at the package edge as the pessimistic reading; the higher is used.
- TLV62569 psiJB 40.6 K/W (TI). EA3036C 15 K/W, inductors 60 K/W, AP6256 8 K/W above the board, LED junction 120 K/W above the ring: ASSUMED.
- Camera module: one node coupled to the board across its 1 mm shim gap and to the lid from its back face; the sensor die 3 K above it.
- LED ring: front face pressed on the printed wall (contact 150 W/m^2K), heat through 2 mm of plastic to the outside; back face to the inside. No copper pours on the ring.
- Snapshot mode: the 10 s cycle averaged (housing and board time constants of minutes); the SoC's own rise during a 1.5 s shot (about 0.4 W x 4 K/W) is under 2 K and not added.

## Checks

- PASS snap_day: RV1106 junction (U1) 86.4 C against 125 C (Tj max (datasheet 4.1))
- PASS snap_day: RV1106 surroundings (internal air) 76.4 C against 85 C (ambient operating max (T3-2))
- PASS snap_day: TLV62569 0.9 V (U2) junction 83.6 C against 125 C (TJ max (SLVSDG1C 6.3))
- PASS snap_day: TLV62569 Wi-Fi (U4) junction 82.1 C against 125 C (TJ max (SLVSDG1C 6.3))
- PASS snap_day: EA3036C junction (U3) 82.4 C against 125 C (TJ range (datasheet))
- PASS snap_day: inductor L1 (FPA252012D) 83.0 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- PASS snap_day: inductor L2 (FPA252012D) 81.9 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- PASS snap_day: inductor L3 (FPA252012D) 82.1 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- PASS snap_day: inductor L4 (FPA252012D) 82.2 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- PASS snap_day: inductor L5 (FPA252012D) 81.7 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- PASS snap_day: AP6256 module (U6) 83.7 C against 85 C (operating max; full RF only to 75 C)
- PASS snap_day: SC3336 sensor (camera module) 84.0 C against 85 C (operating max; best image to 60 C (SmartSens))
- PASS snap_day: W25N02KV flash (U5) 81.9 C against 85 C (-40..85 C (Winbond))
- PASS snap_day: DRV8837 (U7) 82.1 C against 85 C (ambient -40..85 C (TI))
- PASS snap_day: X7S capacitors (1uF) under the SoC (B face) 83.5 C against 125 C (X7S: -55..125 C (Murata))
- PASS snap_day: X7S capacitors (1uF) at the bucks 82.9 C against 125 C (X7S: -55..125 C (Murata))
- PASS snap_day: X6S capacitors (4.7uF, 10uF, 22uF) under the SoC (B face) 83.5 C against 105 C (X6S: -55..105 C (Murata))
- PASS snap_day: X6S capacitors (4.7uF, 10uF, 22uF) at the bucks 82.9 C against 105 C (X6S: -55..105 C (Murata))
- PASS snap_day: 24 MHz crystal Y1 82.7 C against 85 C (-40..85 C (YXC))
- PASS snap_day: crystals Y2 / Y3, oscillator Y4 82.8 C against 85 C (-40..85 C)
- PASS snap_day: status LED LED1 82.5 C against 85 C (-40..85 C (KENTO))
- PASS snap_day: camera FFC connector J2 (XF2M) 82.3 C against 85 C (-30..85 C incl. rise (Omron))
- PASS snap_day: SH connectors J1 / J4 (JST) 81.9 C against 85 C (-25..85 C incl. rise (JST))
- PASS snap_day: U.FL J5 81.8 C against 90 C (-40..90 C (Hirose))
- PASS snap_day: PicoBlade J3 82.0 C against 105 C (-40..105 C (Molex))
- PASS snap_day: USB-C receptacle (USB board) 78.4 C against 80 C (-30..80 C (catalogue))
- PASS snap_day: IR LEDs (ring), junction 66.7 C against 115 C (Tj max (JNJ))
- PASS snap_day: IR LEDs (ring), case 66.7 C against 100 C (operating -40..100 C (JNJ))
- PASS snap_day: TEMT6000 light sensor (ring) 66.7 C against 100 C (-40..100 C (Vishay))
- PASS snap_day: housing wall (PETG/ASA print) 70.6 C against 80 C (PETG softens ~ 80 C (Tg); ASA/PC higher)
- PASS snap_day: RV1106 junction (U1) 86.4 C with 10 K margin (115 C)
- WARN snap_day: AP6256 module (U6) 83.7 C with 10 K margin (75 C)
- WARN snap_day: SC3336 sensor (camera module) 84.0 C with 10 K margin (75 C)
- PASS snap_night: RV1106 junction (U1) 86.7 C against 125 C (Tj max (datasheet 4.1))
- PASS snap_night: RV1106 surroundings (internal air) 76.7 C against 85 C (ambient operating max (T3-2))
- PASS snap_night: TLV62569 0.9 V (U2) junction 83.9 C against 125 C (TJ max (SLVSDG1C 6.3))
- PASS snap_night: TLV62569 Wi-Fi (U4) junction 82.4 C against 125 C (TJ max (SLVSDG1C 6.3))
- PASS snap_night: EA3036C junction (U3) 82.7 C against 125 C (TJ range (datasheet))
- PASS snap_night: inductor L1 (FPA252012D) 83.3 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- PASS snap_night: inductor L2 (FPA252012D) 82.2 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- PASS snap_night: inductor L3 (FPA252012D) 82.4 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- PASS snap_night: inductor L4 (FPA252012D) 82.4 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- PASS snap_night: inductor L5 (FPA252012D) 82.0 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- PASS snap_night: AP6256 module (U6) 84.0 C against 85 C (operating max; full RF only to 75 C)
- PASS snap_night: SC3336 sensor (camera module) 84.2 C against 85 C (operating max; best image to 60 C (SmartSens))
- PASS snap_night: W25N02KV flash (U5) 82.2 C against 85 C (-40..85 C (Winbond))
- PASS snap_night: DRV8837 (U7) 82.4 C against 85 C (ambient -40..85 C (TI))
- PASS snap_night: X7S capacitors (1uF) under the SoC (B face) 83.8 C against 125 C (X7S: -55..125 C (Murata))
- PASS snap_night: X7S capacitors (1uF) at the bucks 83.2 C against 125 C (X7S: -55..125 C (Murata))
- PASS snap_night: X6S capacitors (4.7uF, 10uF, 22uF) under the SoC (B face) 83.8 C against 105 C (X6S: -55..105 C (Murata))
- PASS snap_night: X6S capacitors (4.7uF, 10uF, 22uF) at the bucks 83.2 C against 105 C (X6S: -55..105 C (Murata))
- PASS snap_night: 24 MHz crystal Y1 83.0 C against 85 C (-40..85 C (YXC))
- PASS snap_night: crystals Y2 / Y3, oscillator Y4 83.1 C against 85 C (-40..85 C)
- PASS snap_night: status LED LED1 82.8 C against 85 C (-40..85 C (KENTO))
- PASS snap_night: camera FFC connector J2 (XF2M) 82.6 C against 85 C (-30..85 C incl. rise (Omron))
- PASS snap_night: SH connectors J1 / J4 (JST) 82.1 C against 85 C (-25..85 C incl. rise (JST))
- PASS snap_night: U.FL J5 82.0 C against 90 C (-40..90 C (Hirose))
- PASS snap_night: PicoBlade J3 82.3 C against 105 C (-40..105 C (Molex))
- PASS snap_night: USB-C receptacle (USB board) 78.7 C against 80 C (-30..80 C (catalogue))
- PASS snap_night: IR LEDs (ring), junction 81.1 C against 115 C (Tj max (JNJ))
- PASS snap_night: IR LEDs (ring), case 77.2 C against 100 C (operating -40..100 C (JNJ))
- PASS snap_night: TEMT6000 light sensor (ring) 75.2 C against 100 C (-40..100 C (Vishay))
- PASS snap_night: housing wall (PETG/ASA print) 70.9 C against 80 C (PETG softens ~ 80 C (Tg); ASA/PC higher)
- PASS snap_night: string resistor 0.141 W while lit against 0.235 W derated at 75 C
- PASS snap_night: RV1106 junction (U1) 86.7 C with 10 K margin (115 C)
- WARN snap_night: AP6256 module (U6) 84.0 C with 10 K margin (75 C)
- WARN snap_night: SC3336 sensor (camera module) 84.2 C with 10 K margin (75 C)
- PASS snapshot mode (heat path: cnc) keeps every part inside its rating up to a 66 C chamber (requirement 65 C)
- WARN snapshot-mode margin 0.7 K at 65 C, against a model uncertainty of about +-10 K

**no FAIL, 5 WARN**
