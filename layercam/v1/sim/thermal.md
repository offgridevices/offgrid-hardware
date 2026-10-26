# LayerCam v1: temperatures in a 65 C chamber

Computed by `sim/thermal.py`: the main board as a 2D plate on a 0.5 mm grid (outline from `src/geometry.py`, part places from `src/layout_main.py`, heat from `sim/power_budget.py`), inside Prusa's printed housing in a 65 C chamber with still air. The model and every assumed number are listed at the end; the board is the placed design (routing changes the copper coverage, see the sensitivity).

The requirement cases are **snapshot mode** (`snap_day`, `snap_night`): a still at most every 10 s, the sensor in standby, the CPU at its lowest DVFS point and Wi-Fi in power-save between shots (power_budget.py has the loads). The housing's time constant is many minutes, so a 10 s cycle is modelled by its average heat; the LED junctions and the string resistors are checked at their power while lit. Live view (`day`, `night`) and the stress bound are reported, not checked; live view gets a chamber limit and a firmware rule instead.

Board: 17.2 cm^2 a face; in-plane conductance 0.0344 W/K per square (copper coverage F 55 %, In1 90 %, In2 50 %, In3 85 %, In4 90 %, B 55 %). SoC exposed pad to the planes: 0.85 K/W through 25 filled vias.

## Verdict

**Snapshot mode (the requirement) at 65 C: FAIL** (23 FAIL, 4 WARN in the checks below). Every part stays inside its rating in snapshot mode up to a **43 C** chamber (60 C leaving out the 70 C button).

| at 65 C | snap_day | snap_night | live day | live night |
|---|---|---|---|---|
| RV1106 junction | 96 C | 96 C | 127 C | 128 C |
| AP6256 | 87 C | 88 C | 112 C | 113 C |
| SC3336 sensor | 88 C | 88 C | 111 C | 112 C |
| button SW1 (70 C) | 89 C | 90 C | 114 C | 115 C |
| USB-C (80 C) | 81 C | 81 C | 95 C | 97 C |
| board max | 92 C | 92 C | 118 C | 120 C |
| LED ring (average) | 67 C | 75 C | 69 C | 110 C |
| IR LED junction while lit | 67 C | 81 C | 69 C | 116 C |
| heat in the housing | 0.79 W | 0.93 W | 1.77 W | 2.50 W |

- String resistor (47R) while lit at night: 0.141 W against 0.234 W derated at the ring's 75 C.
- Live view (reported): every part but the button stays in rating up to a 29 C chamber by day and 27 C by night; the firmware rules above turn that into a TSADC threshold. The stress bound fits at no chamber temperature: the firmware must never allow it.
- FAIL in snapshot mode at 65 C (worst of day / night): side button SW1 (TS24CA) 90 C / 70 C; crystals Y2 / Y3, oscillator Y4 90 C / 85 C; 24 MHz crystal Y1 90 C / 85 C; status LED LED1 89 C / 85 C; SC3336 sensor (camera module) 88 C / 85 C; AP6256 module (U6) 88 C / 85 C; DRV8837 (U7) 88 C / 85 C; SH connectors J1 / J4 (JST) 87 C / 85 C; USB-C receptacle (USB board) 81 C / 80 C; camera FFC connector J2 (XF2M) 86 C / 85 C; W25N02KV flash (U5) 86 C / 85 C
- Fix that makes snapshot mode pass: an aluminium lid (or plate in the lid's vent window) on the SoC through a gap pad: snap_night then RV1106 82 C, board 78 C, every part but the button in rating to a 70 C chamber; plus a button rated >= 85 C and a USB-C receptacle rated >= 85 C. Without the lid, suspending the SoC between shots alone reaches 63 C.
- WARN: AP6256 and SC3336 above 75 C in snapshot mode (AP6256 full RF and the sensor's best image end there; both run, with more noise / less TX power).
- Firmware governor: live view only while TSADC < 94 C; snapshot mode stretches to 30 s above 88 C; stop at 110 C; shutdown 125 C.
- Model uncertainty about +-10 K (the optimistic bracket is 2 K lower on the SoC in snap_night). The snapshot currents are ASSUMED: measure idle, shot and upload current on the first board and rerun.

## Snapshot, day (requirement)

Heat in the housing: **0.79 W** (U1 0.49, U6 0.18, camera module 0.04, U3 0.03, U2 0.02, U5 0.01, U4 0.01, L1 0.01).

| | value |
|---|---|
| housing wall | 71.4 C (6.4 K over the chamber) |
| air inside (mean of board and wall) | 79.2 C |
| main board mean / max | 87.0 / 91.5 C |
| board heat out: faces / edge to the pocket / into the camera module | 0.52 / 0.17 / 0.05 W |
| lid-slot air exchange | 0.07 W |
| LED ring (average) | 67.0 C (0.00 W average; 0.02 W out through the front wall) |
| RV1106 | 0.49 W; board under the pad 91.2 C, at the package edge 89.6 C; Tj 93.0 C (pad path) / 95.7 C (thetaJB 12.5 from the edge) |

| part | temperature (C) | limit (C) | margin (K) | limit from |
|---|---|---|---|---|
| side button SW1 (TS24CA) | 89.3 | 70 | -19.3 | -20..70 C (catalogue) |
| crystals Y2 / Y3, oscillator Y4 | 89.5 | 85 | -4.5 | -40..85 C |
| 24 MHz crystal Y1 | 89.3 | 85 | -4.3 | -40..85 C (YXC) |
| status LED LED1 | 88.6 | 85 | -3.6 | -40..85 C (KENTO) |
| SC3336 sensor (camera module) | 87.6 | 85 | -2.6 | operating max; best image to 60 C (SmartSens) |
| AP6256 module (U6) | 87.4 | 85 | -2.4 | operating max; full RF only to 75 C |
| DRV8837 (U7) | 87.3 | 85 | -2.3 | ambient -40..85 C (TI) |
| SH connectors J1 / J4 (JST) | 86.5 | 85 | -1.5 | -25..85 C incl. rise (JST) |
| USB-C receptacle (USB board) | 81.2 | 80 | -1.2 | -30..80 C (catalogue) |
| camera FFC connector J2 (XF2M) | 85.9 | 85 | -0.9 | -30..85 C incl. rise (Omron) |
| W25N02KV flash (U5) | 85.4 | 85 | -0.4 | -40..85 C (Winbond) |
| U.FL J5 | 85.2 | 90 | +4.8 | -40..90 C (Hirose) |
| RV1106 surroundings (internal air) | 79.2 | 85 | +5.8 | ambient operating max (T3-2) |
| housing wall (PETG/ASA print) | 71.4 | 80 | +8.6 | PETG softens ~ 80 C (Tg); ASA/PC higher |
| X6S capacitors (4.7uF, 10uF, 22uF) under the SoC (B face) | 91.5 | 105 | +13.5 | X6S: -55..105 C (Murata) |
| X6S capacitors (4.7uF, 10uF, 22uF) at the bucks | 89.8 | 105 | +15.2 | X6S: -55..105 C (Murata) |
| PicoBlade J3 | 86.6 | 105 | +18.4 | -40..105 C (Molex) |
| RV1106 junction (U1) | 95.7 | 125 | +29.3 | Tj max (datasheet 4.1) |
| IR LEDs (ring), case | 67.0 | 100 | +33.0 | operating -40..100 C (JNJ) |
| TEMT6000 light sensor (ring) | 67.0 | 100 | +33.0 | -40..100 C (Vishay) |
| X7S capacitors (1uF) under the SoC (B face) | 91.5 | 125 | +33.5 | X7S: -55..125 C (Murata) |
| TLV62569 0.9 V (U2) junction | 90.3 | 125 | +34.7 | TJ max (SLVSDG1C 6.3) |
| X7S capacitors (1uF) at the bucks | 89.8 | 125 | +35.2 | X7S: -55..125 C (Murata) |
| inductor L1 (FPA252012D) | 89.4 | 125 | +35.6 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L4 (FPA252012D) | 87.1 | 125 | +37.9 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| EA3036C junction (U3) | 86.8 | 125 | +38.2 | TJ range (datasheet) |
| inductor L3 (FPA252012D) | 86.8 | 125 | +38.2 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L2 (FPA252012D) | 85.8 | 125 | +39.2 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| TLV62569 Wi-Fi (U4) junction | 85.5 | 125 | +39.5 | TJ max (SLVSDG1C 6.3) |
| inductor L5 (FPA252012D) | 85.1 | 125 | +39.9 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| IR LEDs (ring), junction | 67.0 | 115 | +48.0 | Tj max (JNJ) |

![snap_day](thermal_snap_day.png)

## Snapshot, night, IR LEDs lit 2 s of every 10 s (requirement)

Heat in the housing: **0.93 W** (U1 0.49, U6 0.18, ring resistors 0.08, ring LEDs 0.06, camera module 0.04, U3 0.03, U2 0.02, U5 0.01, U4 0.01, L1 0.01).

| | value |
|---|---|
| housing wall | 71.7 C (6.7 K over the chamber) |
| air inside (mean of board and wall) | 79.5 C |
| main board mean / max | 87.3 / 91.8 C |
| board heat out: faces / edge to the pocket / into the camera module | 0.53 / 0.17 / 0.05 W |
| lid-slot air exchange | 0.07 W |
| LED ring (average) | 75.4 C (0.14 W average; 0.12 W out through the front wall) |
| RV1106 | 0.49 W; board under the pad 91.5 C, at the package edge 89.9 C; Tj 93.3 C (pad path) / 96.0 C (thetaJB 12.5 from the edge) |

| part | temperature (C) | limit (C) | margin (K) | limit from |
|---|---|---|---|---|
| side button SW1 (TS24CA) | 89.6 | 70 | -19.6 | -20..70 C (catalogue) |
| crystals Y2 / Y3, oscillator Y4 | 89.8 | 85 | -4.8 | -40..85 C |
| 24 MHz crystal Y1 | 89.6 | 85 | -4.6 | -40..85 C (YXC) |
| status LED LED1 | 88.9 | 85 | -3.9 | -40..85 C (KENTO) |
| SC3336 sensor (camera module) | 87.9 | 85 | -2.9 | operating max; best image to 60 C (SmartSens) |
| AP6256 module (U6) | 87.7 | 85 | -2.7 | operating max; full RF only to 75 C |
| DRV8837 (U7) | 87.6 | 85 | -2.6 | ambient -40..85 C (TI) |
| SH connectors J1 / J4 (JST) | 86.8 | 85 | -1.8 | -25..85 C incl. rise (JST) |
| USB-C receptacle (USB board) | 81.5 | 80 | -1.5 | -30..80 C (catalogue) |
| camera FFC connector J2 (XF2M) | 86.2 | 85 | -1.2 | -30..85 C incl. rise (Omron) |
| W25N02KV flash (U5) | 85.7 | 85 | -0.7 | -40..85 C (Winbond) |
| U.FL J5 | 85.5 | 90 | +4.5 | -40..90 C (Hirose) |
| RV1106 surroundings (internal air) | 79.5 | 85 | +5.5 | ambient operating max (T3-2) |
| housing wall (PETG/ASA print) | 71.7 | 80 | +8.3 | PETG softens ~ 80 C (Tg); ASA/PC higher |
| X6S capacitors (4.7uF, 10uF, 22uF) under the SoC (B face) | 91.8 | 105 | +13.2 | X6S: -55..105 C (Murata) |
| X6S capacitors (4.7uF, 10uF, 22uF) at the bucks | 90.1 | 105 | +14.9 | X6S: -55..105 C (Murata) |
| PicoBlade J3 | 86.9 | 105 | +18.1 | -40..105 C (Molex) |
| IR LEDs (ring), case | 77.4 | 100 | +22.6 | operating -40..100 C (JNJ) |
| TEMT6000 light sensor (ring) | 75.4 | 100 | +24.6 | -40..100 C (Vishay) |
| RV1106 junction (U1) | 96.0 | 125 | +29.0 | Tj max (datasheet 4.1) |
| X7S capacitors (1uF) under the SoC (B face) | 91.8 | 125 | +33.2 | X7S: -55..125 C (Murata) |
| IR LEDs (ring), junction | 81.3 | 115 | +33.7 | Tj max (JNJ) |
| TLV62569 0.9 V (U2) junction | 90.6 | 125 | +34.4 | TJ max (SLVSDG1C 6.3) |
| X7S capacitors (1uF) at the bucks | 90.1 | 125 | +34.9 | X7S: -55..125 C (Murata) |
| inductor L1 (FPA252012D) | 89.7 | 125 | +35.3 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L4 (FPA252012D) | 87.4 | 125 | +37.6 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| EA3036C junction (U3) | 87.1 | 125 | +37.9 | TJ range (datasheet) |
| inductor L3 (FPA252012D) | 87.1 | 125 | +37.9 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L2 (FPA252012D) | 86.1 | 125 | +38.9 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| TLV62569 Wi-Fi (U4) junction | 85.8 | 125 | +39.2 | TJ max (SLVSDG1C 6.3) |
| inductor L5 (FPA252012D) | 85.4 | 125 | +39.6 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| 47R string resistor (ring), power while lit | 0.141 W | 0.234 W at 75 C | +0.093 W | 0.25 W to 70 C, 0 at 155 C |

![snap_night](thermal_snap_night.png)

## Live view, day: streaming (reported, not required)

Heat in the housing: **1.77 W** (U1 0.97, U6 0.43, camera module 0.20, U2 0.06, L1 0.04, U3 0.03, U5 0.02, U4 0.01, cable, connectors 0.01).

| | value |
|---|---|
| housing wall | 77.3 C (12.3 K over the chamber) |
| air inside (mean of board and wall) | 93.4 C |
| main board mean / max | 109.6 / 118.3 C |
| board heat out: faces / edge to the pocket / into the camera module | 1.18 / 0.36 / 0.02 W |
| lid-slot air exchange | 0.20 W |
| LED ring (average) | 69.0 C (0.00 W average; 0.05 W out through the front wall) |
| RV1106 | 0.97 W; board under the pad 117.6 C, at the package edge 114.6 C; Tj 121.3 C (pad path) / 126.7 C (thetaJB 12.5 from the edge) |

| part | temperature (C) | limit (C) | margin (K) | limit from |
|---|---|---|---|---|
| side button SW1 (TS24CA) | 113.8 | 70 | -43.8 | -20..70 C (catalogue) |
| crystals Y2 / Y3, oscillator Y4 | 114.8 | 85 | -29.8 | -40..85 C |
| 24 MHz crystal Y1 | 113.8 | 85 | -28.8 | -40..85 C (YXC) |
| status LED LED1 | 112.5 | 85 | -27.5 | -40..85 C (KENTO) |
| AP6256 module (U6) | 111.8 | 85 | -26.8 | operating max; full RF only to 75 C |
| SC3336 sensor (camera module) | 110.7 | 85 | -25.7 | operating max; best image to 60 C (SmartSens) |
| DRV8837 (U7) | 109.7 | 85 | -24.7 | ambient -40..85 C (TI) |
| SH connectors J1 / J4 (JST) | 108.8 | 85 | -23.8 | -25..85 C incl. rise (JST) |
| camera FFC connector J2 (XF2M) | 108.2 | 85 | -23.2 | -30..85 C incl. rise (Omron) |
| W25N02KV flash (U5) | 106.7 | 85 | -21.7 | -40..85 C (Winbond) |
| U.FL J5 | 106.4 | 90 | -16.4 | -40..90 C (Hirose) |
| USB-C receptacle (USB board) | 95.4 | 80 | -15.4 | -30..80 C (catalogue) |
| X6S capacitors (4.7uF, 10uF, 22uF) under the SoC (B face) | 118.3 | 105 | -13.3 | X6S: -55..105 C (Murata) |
| X6S capacitors (4.7uF, 10uF, 22uF) at the bucks | 115.3 | 105 | -10.3 | X6S: -55..105 C (Murata) |
| RV1106 surroundings (internal air) | 93.4 | 85 | -8.4 | ambient operating max (T3-2) |
| PicoBlade J3 | 108.4 | 105 | -3.4 | -40..105 C (Molex) |
| RV1106 junction (U1) | 126.7 | 125 | -1.7 | Tj max (datasheet 4.1) |
| housing wall (PETG/ASA print) | 77.3 | 80 | +2.7 | PETG softens ~ 80 C (Tg); ASA/PC higher |
| X7S capacitors (1uF) under the SoC (B face) | 118.3 | 125 | +6.7 | X7S: -55..125 C (Murata) |
| TLV62569 0.9 V (U2) junction | 117.3 | 125 | +7.7 | TJ max (SLVSDG1C 6.3) |
| inductor L1 (FPA252012D) | 116.0 | 125 | +9.0 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| X7S capacitors (1uF) at the bucks | 115.3 | 125 | +9.7 | X7S: -55..125 C (Murata) |
| inductor L4 (FPA252012D) | 109.3 | 125 | +15.7 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L3 (FPA252012D) | 108.6 | 125 | +16.4 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| EA3036C junction (U3) | 108.4 | 125 | +16.6 | TJ range (datasheet) |
| inductor L2 (FPA252012D) | 106.9 | 125 | +18.1 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| TLV62569 Wi-Fi (U4) junction | 106.7 | 125 | +18.3 | TJ max (SLVSDG1C 6.3) |
| inductor L5 (FPA252012D) | 105.9 | 125 | +19.1 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| IR LEDs (ring), case | 69.0 | 100 | +31.0 | operating -40..100 C (JNJ) |
| TEMT6000 light sensor (ring) | 69.0 | 100 | +31.0 | -40..100 C (Vishay) |
| IR LEDs (ring), junction | 69.0 | 115 | +46.0 | Tj max (JNJ) |

![day](thermal_day.png)

## Live view, night: streaming with the IR LEDs on (reported, not required)

Heat in the housing: **2.50 W** (U1 0.97, U6 0.43, ring resistors 0.42, ring LEDs 0.30, camera module 0.20, U2 0.06, L1 0.04, U3 0.03, U5 0.02, cable, connectors 0.02, U4 0.01).

| | value |
|---|---|
| housing wall | 78.8 C (13.8 K over the chamber) |
| air inside (mean of board and wall) | 94.9 C |
| main board mean / max | 111.0 / 119.7 C |
| board heat out: faces / edge to the pocket / into the camera module | 1.19 / 0.36 / 0.03 W |
| lid-slot air exchange | 0.21 W |
| LED ring (average) | 110.0 C (0.72 W average; 0.54 W out through the front wall) |
| RV1106 | 0.97 W; board under the pad 119.0 C, at the package edge 116.0 C; Tj 122.7 C (pad path) / 128.1 C (thetaJB 12.5 from the edge) |

| part | temperature (C) | limit (C) | margin (K) | limit from |
|---|---|---|---|---|
| side button SW1 (TS24CA) | 115.1 | 70 | -45.1 | -20..70 C (catalogue) |
| crystals Y2 / Y3, oscillator Y4 | 116.2 | 85 | -31.2 | -40..85 C |
| 24 MHz crystal Y1 | 115.1 | 85 | -30.1 | -40..85 C (YXC) |
| status LED LED1 | 113.8 | 85 | -28.8 | -40..85 C (KENTO) |
| AP6256 module (U6) | 113.2 | 85 | -28.2 | operating max; full RF only to 75 C |
| SC3336 sensor (camera module) | 112.1 | 85 | -27.1 | operating max; best image to 60 C (SmartSens) |
| DRV8837 (U7) | 111.1 | 85 | -26.1 | ambient -40..85 C (TI) |
| SH connectors J1 / J4 (JST) | 110.2 | 85 | -25.2 | -25..85 C incl. rise (JST) |
| camera FFC connector J2 (XF2M) | 109.6 | 85 | -24.6 | -30..85 C incl. rise (Omron) |
| W25N02KV flash (U5) | 108.1 | 85 | -23.1 | -40..85 C (Winbond) |
| U.FL J5 | 107.9 | 90 | -17.9 | -40..90 C (Hirose) |
| USB-C receptacle (USB board) | 96.9 | 80 | -16.9 | -30..80 C (catalogue) |
| X6S capacitors (4.7uF, 10uF, 22uF) under the SoC (B face) | 119.7 | 105 | -14.7 | X6S: -55..105 C (Murata) |
| IR LEDs (ring), case | 112.0 | 100 | -12.0 | operating -40..100 C (JNJ) |
| X6S capacitors (4.7uF, 10uF, 22uF) at the bucks | 116.7 | 105 | -11.7 | X6S: -55..105 C (Murata) |
| TEMT6000 light sensor (ring) | 110.0 | 100 | -10.0 | -40..100 C (Vishay) |
| RV1106 surroundings (internal air) | 94.9 | 85 | -9.9 | ambient operating max (T3-2) |
| PicoBlade J3 | 109.7 | 105 | -4.7 | -40..105 C (Molex) |
| RV1106 junction (U1) | 128.1 | 125 | -3.1 | Tj max (datasheet 4.1) |
| IR LEDs (ring), junction | 115.9 | 115 | -0.9 | Tj max (JNJ) |
| housing wall (PETG/ASA print) | 78.8 | 80 | +1.2 | PETG softens ~ 80 C (Tg); ASA/PC higher |
| X7S capacitors (1uF) under the SoC (B face) | 119.7 | 125 | +5.3 | X7S: -55..125 C (Murata) |
| TLV62569 0.9 V (U2) junction | 118.7 | 125 | +6.3 | TJ max (SLVSDG1C 6.3) |
| inductor L1 (FPA252012D) | 117.4 | 125 | +7.6 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| X7S capacitors (1uF) at the bucks | 116.7 | 125 | +8.3 | X7S: -55..125 C (Murata) |
| inductor L4 (FPA252012D) | 110.7 | 125 | +14.3 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L3 (FPA252012D) | 110.0 | 125 | +15.0 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| EA3036C junction (U3) | 109.8 | 125 | +15.2 | TJ range (datasheet) |
| inductor L2 (FPA252012D) | 108.3 | 125 | +16.7 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| TLV62569 Wi-Fi (U4) junction | 108.1 | 125 | +16.9 | TJ max (SLVSDG1C 6.3) |
| inductor L5 (FPA252012D) | 107.3 | 125 | +17.7 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| 47R string resistor (ring), power while lit | 0.141 W | 0.132 W at 110 C | -0.008 W | 0.25 W to 70 C, 0 at 155 C |

![night](thermal_night.png)

## Stress bound: SoC flat out, Wi-Fi transmitting, LEDs at the high corner (reported)

Heat in the housing: **5.35 W** (U1 2.06, U6 1.44, ring resistors 0.52, ring LEDs 0.33, camera module 0.27, U2 0.23, L1 0.19, U5 0.12, cable, connectors 0.07, U3 0.06, U4 0.04, L5 0.02, L3 0.01).

| | value |
|---|---|
| housing wall | 93.0 C (28.0 K over the chamber) |
| air inside (mean of board and wall) | 128.4 C |
| main board mean / max | 163.8 / 179.9 C |
| board heat out: faces / edge to the pocket / into the camera module | 3.16 / 0.79 / 0.25 W |
| lid-slot air exchange | 0.65 W |
| LED ring (average) | 120.4 C (0.85 W average; 0.66 W out through the front wall) |
| RV1106 | 2.06 W; board under the pad 178.2 C, at the package edge 172.0 C; Tj 186.2 C (pad path) / 197.8 C (thetaJB 12.5 from the edge) |

| part | temperature (C) | limit (C) | margin (K) | limit from |
|---|---|---|---|---|
| side button SW1 (TS24CA) | 169.3 | 70 | -99.3 | -20..70 C (catalogue) |
| AP6256 module (U6) | 178.0 | 85 | -93.0 | operating max; full RF only to 75 C |
| crystals Y2 / Y3, oscillator Y4 | 174.2 | 85 | -89.2 | -40..85 C |
| 24 MHz crystal Y1 | 169.3 | 85 | -84.3 | -40..85 C (YXC) |
| status LED LED1 | 166.5 | 85 | -81.5 | -40..85 C (KENTO) |
| camera FFC connector J2 (XF2M) | 166.4 | 85 | -81.4 | -30..85 C incl. rise (Omron) |
| W25N02KV flash (U5) | 161.7 | 85 | -76.7 | -40..85 C (Winbond) |
| SH connectors J1 / J4 (JST) | 161.0 | 85 | -76.0 | -25..85 C incl. rise (JST) |
| DRV8837 (U7) | 160.8 | 85 | -75.8 | ambient -40..85 C (TI) |
| X6S capacitors (4.7uF, 10uF, 22uF) under the SoC (B face) | 179.9 | 105 | -74.9 | X6S: -55..105 C (Murata) |
| RV1106 junction (U1) | 197.8 | 125 | -72.8 | Tj max (datasheet 4.1) |
| U.FL J5 | 160.6 | 90 | -70.6 | -40..90 C (Hirose) |
| X6S capacitors (4.7uF, 10uF, 22uF) at the bucks | 175.4 | 105 | -70.4 | X6S: -55..105 C (Murata) |
| SC3336 sensor (camera module) | 153.9 | 85 | -68.9 | operating max; best image to 60 C (SmartSens) |
| TLV62569 0.9 V (U2) junction | 184.7 | 125 | -59.7 | TJ max (SLVSDG1C 6.3) |
| inductor L1 (FPA252012D) | 184.5 | 125 | -59.5 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| X7S capacitors (1uF) under the SoC (B face) | 179.9 | 125 | -54.9 | X7S: -55..125 C (Murata) |
| PicoBlade J3 | 158.5 | 105 | -53.5 | -40..105 C (Molex) |
| X7S capacitors (1uF) at the bucks | 175.4 | 125 | -50.4 | X7S: -55..125 C (Murata) |
| USB-C receptacle (USB board) | 130.4 | 80 | -50.4 | -30..80 C (catalogue) |
| RV1106 surroundings (internal air) | 128.4 | 85 | -43.4 | ambient operating max (T3-2) |
| TLV62569 Wi-Fi (U4) junction | 160.9 | 125 | -35.9 | TJ max (SLVSDG1C 6.3) |
| inductor L4 (FPA252012D) | 159.9 | 125 | -34.9 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L3 (FPA252012D) | 159.1 | 125 | -34.1 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| EA3036C junction (U3) | 158.7 | 125 | -33.7 | TJ range (datasheet) |
| inductor L5 (FPA252012D) | 158.1 | 125 | -33.1 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| inductor L2 (FPA252012D) | 157.0 | 125 | -32.0 | typical for molded 2520 power inductors (UNVERIFIED: no datasheet read) |
| IR LEDs (ring), case | 122.6 | 100 | -22.6 | operating -40..100 C (JNJ) |
| TEMT6000 light sensor (ring) | 120.4 | 100 | -20.4 | -40..100 C (Vishay) |
| housing wall (PETG/ASA print) | 93.0 | 80 | -13.0 | PETG softens ~ 80 C (Tg); ASA/PC higher |
| IR LEDs (ring), junction | 127.0 | 115 | -12.0 | Tj max (JNJ) |
| 47R string resistor (ring), power while lit | 0.174 W | 0.102 W at 120 C | -0.072 W | 0.25 W to 70 C, 0 at 155 C |

![worst](thermal_worst.png)

## Sensitivity (snap_night, RV1106 Tj / board max / ring average)

| change | RV1106 Tj (C) | board max (C) | ring (C) |
|---|---|---|---|
| as above | 96.0 | 91.8 | 75.4 |
| no lid slots (vents taped or facing down) | 96.5 | 92.3 | 75.6 |
| ring not touching the front wall | 96.2 | 92.0 | 98.7 |
| copper coverage x0.7 (a more perforated routed board) | 96.9 | 93.4 | 75.4 |
| inside emissivity 0.6 (bare metal shields, lens holder) | 97.8 | 93.6 | 75.6 |
| optimistic bracket: emissivity 0.85, Nu 1.5, copper x1.2 | 93.6 | 89.1 | 75.2 |
| chamber air moving at 0.5 m/s past the housing | 94.2 | 89.9 | 73.4 |
| SoC idle 50 % higher than assumed | 107.0 | 100.7 | 75.9 |
| Wi-Fi average twice the assumed 0.05 A | 99.4 | 95.2 | 75.7 |

## Highest chamber temperature per case

Bisection on the same model: the chamber temperature at which the first part reaches its limit.

| case | every part inside its limit up to | the same without the 70 C button | RV1106 Tj 125 C at | RV1106 Tj 115 C (10 K margin) at |
|---|---|---|---|---|
| snap_day | 44 C (side button SW1 (TS24CA)) | 60 C (crystals Y2 / Y3, oscillator Y4) | 85 C or more | 85 C or more |
| snap_night | 43 C (side button SW1 (TS24CA)) | 60 C (crystals Y2 / Y3, oscillator Y4) | 85 C or more | 85 C or more |
| day | 11 C (side button SW1 (TS24CA)) | 29 C (crystals Y2 / Y3, oscillator Y4) | 63 C | 51 C |
| night | 9 C (side button SW1 (TS24CA)) | 27 C (crystals Y2 / Y3, oscillator Y4) | 61 C | 49 C |
| worst | never (side button SW1 (TS24CA)) | never (AP6256 module (U6)) | never (not even at -20 C) | never (not even at -20 C) |

## Firmware rules (thermal governor)

The RV1106's TSADC reads its own junction (+-3 C). In a steady state every part sits at a fixed offset from it for a given load, so a junction temperature can stand in for the hottest part. For each mode: the junction temperature at the chamber temperature where the first part (the 70 C button left out) reaches its rating. Live view may run while the TSADC is below that reading, less the sensor's 3 C error; above it the firmware falls back to snapshot mode.

| mode | chamber limit (first part, button left out) | RV1106 Tj there (steady state) | rule: allowed while TSADC below | at 65 C in snapshot mode the TSADC reads |
|---|---|---|---|---|
| snapshot, day | 60 C | 91 C | **88 C** | 96 C |
| snapshot, night | 60 C | 91 C | **88 C** | 96 C |
| live view, day | 29 C | 97 C | **94 C** | 96 C |
| live view, night | 27 C | 97 C | **94 C** | 96 C |

Rule set, in order (to be tuned on a board in an oven):

1. **Snapshot mode is the default**: CPU at its lowest OPP between shots, NPU off, sensor in standby, Wi-Fi power-save on 2.4 GHz.
2. **Live view** only while TSADC < 94 C; crossing it ends live view (back to snapshot mode, the user sees "live view paused: camera too warm"). In a 65 C chamber the snapshot-mode reading is already 96 C, so live view is refused there.
3. TSADC > 88 C in snapshot mode: stretch the interval to 30 s, cap Wi-Fi TX power, shorten the IR flash to 1 s (the reading at which the first 85 C part reaches its rating in snapshot mode).
4. TSADC > 110 C: stop capturing (keep Wi-Fi associated, report the fault).
5. TSADC > 120 C: power the sensor and Wi-Fi down; Linux critical trip (shutdown) at 125 C.

## What it would take (snapshot margin, live view at 65 C)

*Throttled*: SoC heat -40 %, Wi-Fi on 2.4 GHz at reduced TX power (0.08 A average). *LEDs 30 %*: IR_PWM at 30 % duty. *Al lid*: an aluminium lid or plate touching the SoC through a gap pad, 26 K/W from the SoC area to the chamber.

| change | heat (W) | at 65 C: RV1106 Tj / board max / AP6256 / sensor (C) | every part but the button inside its rating up to |
|---|---|---|---|
| snapshot night + Al lid | 0.93 | 82 / 78 / 79 / 79 | 70 C |
| snapshot night, SoC suspended between shots (idle core 0.05 A, ASSUMED) | 0.83 | 91 / 88 / 86 / 86 | 63 C |
| snapshot night, SoC suspended + Al lid | 0.83 | 79 / 77 / 79 / 78 | 71 C |
| live day, throttled | 1.22 | 107 / 102 / 98 / 101 | 47 C |
| live day, Al lid | 1.77 | 99 / 93 / 97 / 95 | 52 C |
| live day, throttled + Al lid | 1.22 | 88 / 85 / 87 / 89 | 60 C |
| live night, throttled + LEDs 30 % + Al lid | 1.44 | 88 / 85 / 87 / 90 | 60 C |

## Every part's rating against the chamber

From `src/parts.py` (descriptions, the JLCPCB catalogue's temperature field read 26 Oct 2026, the datasheets). Flagged against the snapshot-night case: a part rated below 85 C, over its rating, or within 10 K of it.

| part | rated | snap_night at 65 C (C) | live night at 65 C (C) | flag (snapshot) |
|---|---|---|---|---|
| RV1106G3 | Tj 125, ambient -20..85 | 96 | 128 |  |
| W25N02KVZEIR | -40..85 | 86 | 108 | OVER its rating |
| AP6256 | -30..85 (full RF -20..75) | 88 | 113 | OVER its rating |
| EA3036C | TA -40..85, TJ to 125 | 87 | 110 |  |
| TLV62569 | TJ -40..125 | 91 | 119 |  |
| DRV8837 | TA -40..85 | 88 | 111 | OVER its rating |
| AO3400A | TJ -55..150 | 87 | 111 |  |
| crystals / oscillator (24M, 37.4M, 32k) | -40..85 | 90 | 116 | OVER its rating |
| KT-0603G LED | -40..85 | 89 | 114 | OVER its rating |
| XF2M-2015-1A FFC | -30..85 | 86 | 110 | OVER its rating |
| JST SH BM06B / SM06B | -25..85 | 87 | 110 | OVER its rating |
| Molex 53261 PicoBlade | -40..105 | 87 | 110 |  |
| Hirose U.FL | -40..90 | 85 | 108 | under 10 K margin |
| TS24CA side button | -20..70 | 90 | 115 | RATED BELOW 85 C; OVER its rating |
| TYPE-C-31-M-12 USB-C | -30..80 | 81 | 97 | RATED BELOW 85 C; OVER its rating |
| USBLC6-2SC6, SMF5.0CA | TJ to 125 / 150 | 81 | 97 |  |
| JNJ 850 nm IR LED (junction while lit) | -40..100, Tj 115 | 81 | 116 |  |
| TEMT6000 | -40..100 | 75 | 110 |  |
| FPA252012D inductors | not in the catalogue (typ. -40..125) | 90 | 117 | UNKNOWN rating: ask the maker |
| BLM15PD121 bead | -55..125 | 87 | 111 |  |
| 0402 / 1206 thick-film resistors | -55..155 (power derates above 70) | 92 | 120 |  |
| C0G / X7R capacitors (12p, 18p, 1n, 10n, 100n) | -55..125 | 92 | 120 |  |
| X7S capacitors (1uF) | -55..125 | 92 | 120 |  |
| X6S capacitors (4.7uF, 10uF, 22uF) | -55..105 | 92 | 120 |  |
| SC3336 module (bought) | -30..85, best image to 60 | 88 | 112 | OVER its rating |
| CLA219 IR-cut holder (bought) | not published (plastic, NdFeB magnet) | 87 | 111 | UNKNOWN rating: ask the maker |
| Towin CCL127028MPR lens (bought) | not published | 79 | 95 | UNKNOWN rating: ask the maker |

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

- PASS snap_day: RV1106 junction (U1) 95.7 C against 125 C (Tj max (datasheet 4.1))
- PASS snap_day: RV1106 surroundings (internal air) 79.2 C against 85 C (ambient operating max (T3-2))
- PASS snap_day: TLV62569 0.9 V (U2) junction 90.3 C against 125 C (TJ max (SLVSDG1C 6.3))
- PASS snap_day: TLV62569 Wi-Fi (U4) junction 85.5 C against 125 C (TJ max (SLVSDG1C 6.3))
- PASS snap_day: EA3036C junction (U3) 86.8 C against 125 C (TJ range (datasheet))
- PASS snap_day: inductor L1 (FPA252012D) 89.4 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- PASS snap_day: inductor L2 (FPA252012D) 85.8 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- PASS snap_day: inductor L3 (FPA252012D) 86.8 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- PASS snap_day: inductor L4 (FPA252012D) 87.1 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- PASS snap_day: inductor L5 (FPA252012D) 85.1 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- FAIL snap_day: AP6256 module (U6) 87.4 C against 85 C (operating max; full RF only to 75 C)
- FAIL snap_day: SC3336 sensor (camera module) 87.6 C against 85 C (operating max; best image to 60 C (SmartSens))
- FAIL snap_day: W25N02KV flash (U5) 85.4 C against 85 C (-40..85 C (Winbond))
- FAIL snap_day: DRV8837 (U7) 87.3 C against 85 C (ambient -40..85 C (TI))
- PASS snap_day: X7S capacitors (1uF) under the SoC (B face) 91.5 C against 125 C (X7S: -55..125 C (Murata))
- PASS snap_day: X7S capacitors (1uF) at the bucks 89.8 C against 125 C (X7S: -55..125 C (Murata))
- PASS snap_day: X6S capacitors (4.7uF, 10uF, 22uF) under the SoC (B face) 91.5 C against 105 C (X6S: -55..105 C (Murata))
- PASS snap_day: X6S capacitors (4.7uF, 10uF, 22uF) at the bucks 89.8 C against 105 C (X6S: -55..105 C (Murata))
- FAIL snap_day: 24 MHz crystal Y1 89.3 C against 85 C (-40..85 C (YXC))
- FAIL snap_day: crystals Y2 / Y3, oscillator Y4 89.5 C against 85 C (-40..85 C)
- FAIL snap_day: status LED LED1 88.6 C against 85 C (-40..85 C (KENTO))
- FAIL snap_day: side button SW1 (TS24CA) 89.3 C against 70 C (-20..70 C (catalogue))
- FAIL snap_day: camera FFC connector J2 (XF2M) 85.9 C against 85 C (-30..85 C incl. rise (Omron))
- FAIL snap_day: SH connectors J1 / J4 (JST) 86.5 C against 85 C (-25..85 C incl. rise (JST))
- PASS snap_day: U.FL J5 85.2 C against 90 C (-40..90 C (Hirose))
- PASS snap_day: PicoBlade J3 86.6 C against 105 C (-40..105 C (Molex))
- FAIL snap_day: USB-C receptacle (USB board) 81.2 C against 80 C (-30..80 C (catalogue))
- PASS snap_day: IR LEDs (ring), junction 67.0 C against 115 C (Tj max (JNJ))
- PASS snap_day: IR LEDs (ring), case 67.0 C against 100 C (operating -40..100 C (JNJ))
- PASS snap_day: TEMT6000 light sensor (ring) 67.0 C against 100 C (-40..100 C (Vishay))
- PASS snap_day: housing wall (PETG/ASA print) 71.4 C against 80 C (PETG softens ~ 80 C (Tg); ASA/PC higher)
- PASS snap_day: RV1106 junction (U1) 95.7 C with 10 K margin (115 C)
- WARN snap_day: AP6256 module (U6) 87.4 C with 10 K margin (75 C)
- WARN snap_day: SC3336 sensor (camera module) 87.6 C with 10 K margin (75 C)
- PASS snap_night: RV1106 junction (U1) 96.0 C against 125 C (Tj max (datasheet 4.1))
- PASS snap_night: RV1106 surroundings (internal air) 79.5 C against 85 C (ambient operating max (T3-2))
- PASS snap_night: TLV62569 0.9 V (U2) junction 90.6 C against 125 C (TJ max (SLVSDG1C 6.3))
- PASS snap_night: TLV62569 Wi-Fi (U4) junction 85.8 C against 125 C (TJ max (SLVSDG1C 6.3))
- PASS snap_night: EA3036C junction (U3) 87.1 C against 125 C (TJ range (datasheet))
- PASS snap_night: inductor L1 (FPA252012D) 89.7 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- PASS snap_night: inductor L2 (FPA252012D) 86.1 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- PASS snap_night: inductor L3 (FPA252012D) 87.1 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- PASS snap_night: inductor L4 (FPA252012D) 87.4 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- PASS snap_night: inductor L5 (FPA252012D) 85.4 C against 125 C (typical for molded 2520 power inductors (UNVERIFIED: no datasheet read))
- FAIL snap_night: AP6256 module (U6) 87.7 C against 85 C (operating max; full RF only to 75 C)
- FAIL snap_night: SC3336 sensor (camera module) 87.9 C against 85 C (operating max; best image to 60 C (SmartSens))
- FAIL snap_night: W25N02KV flash (U5) 85.7 C against 85 C (-40..85 C (Winbond))
- FAIL snap_night: DRV8837 (U7) 87.6 C against 85 C (ambient -40..85 C (TI))
- PASS snap_night: X7S capacitors (1uF) under the SoC (B face) 91.8 C against 125 C (X7S: -55..125 C (Murata))
- PASS snap_night: X7S capacitors (1uF) at the bucks 90.1 C against 125 C (X7S: -55..125 C (Murata))
- PASS snap_night: X6S capacitors (4.7uF, 10uF, 22uF) under the SoC (B face) 91.8 C against 105 C (X6S: -55..105 C (Murata))
- PASS snap_night: X6S capacitors (4.7uF, 10uF, 22uF) at the bucks 90.1 C against 105 C (X6S: -55..105 C (Murata))
- FAIL snap_night: 24 MHz crystal Y1 89.6 C against 85 C (-40..85 C (YXC))
- FAIL snap_night: crystals Y2 / Y3, oscillator Y4 89.8 C against 85 C (-40..85 C)
- FAIL snap_night: status LED LED1 88.9 C against 85 C (-40..85 C (KENTO))
- FAIL snap_night: side button SW1 (TS24CA) 89.6 C against 70 C (-20..70 C (catalogue))
- FAIL snap_night: camera FFC connector J2 (XF2M) 86.2 C against 85 C (-30..85 C incl. rise (Omron))
- FAIL snap_night: SH connectors J1 / J4 (JST) 86.8 C against 85 C (-25..85 C incl. rise (JST))
- PASS snap_night: U.FL J5 85.5 C against 90 C (-40..90 C (Hirose))
- PASS snap_night: PicoBlade J3 86.9 C against 105 C (-40..105 C (Molex))
- FAIL snap_night: USB-C receptacle (USB board) 81.5 C against 80 C (-30..80 C (catalogue))
- PASS snap_night: IR LEDs (ring), junction 81.3 C against 115 C (Tj max (JNJ))
- PASS snap_night: IR LEDs (ring), case 77.4 C against 100 C (operating -40..100 C (JNJ))
- PASS snap_night: TEMT6000 light sensor (ring) 75.4 C against 100 C (-40..100 C (Vishay))
- PASS snap_night: housing wall (PETG/ASA print) 71.7 C against 80 C (PETG softens ~ 80 C (Tg); ASA/PC higher)
- PASS snap_night: string resistor 0.141 W while lit against 0.234 W derated at 75 C
- PASS snap_night: RV1106 junction (U1) 96.0 C with 10 K margin (115 C)
- WARN snap_night: AP6256 module (U6) 87.7 C with 10 K margin (75 C)
- WARN snap_night: SC3336 sensor (camera module) 87.9 C with 10 K margin (75 C)
- FAIL snapshot mode keeps every part inside its rating up to a 43 C chamber (requirement 65 C)

**23 FAIL, 4 WARN**
