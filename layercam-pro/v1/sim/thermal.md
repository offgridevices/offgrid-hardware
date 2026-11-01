# LayerCam Pro v1: temperatures in a 70 C chamber

Computed by `sim/thermal.py`: the one board as a 2D plate on a 0.5 mm grid (outline from `src/pcb.py` / `src/geometry.py`, part places from src/layout_main.py FIXED (no routed board yet), heat from `sim/power_budget.py`), in the PC-CF case with Prusa's outside, its stock 20 x 20 x 15 mm heatsink under three lid slots, in a 70 C chamber with still air. The model and every assumed number are listed at the end; the copper coverage is ESTIMATED: LayerCam v1's routed main board's figures (the Pro is not routed yet).

The requirement cases are **snapshot mode** (one still at most every 10 s; a timelapse frame per layer is one of those shots, so timelapse mode is the same load): `snap_day`, `snap_night` with the Wi-Fi's power save **off**, as the camera is built today (esp-hosted gives Linux no way to turn it on), and `snap_day_ps`, `snap_night_ps` with it on, once that is fixed. A 10 s cycle is modelled by its average heat (the case's time constant is many minutes); the LED junctions and string resistors are checked at their power while lit. Live view and the stress bound are reported, not checked.

Board: 28.8 cm^2 a face; in-plane conductance 0.0640 W/K per square (copper coverage F 67 %, In1 89 %, In2 66 %, In3 84 %, In4 89 %, B 73 %). SoC exposed pad to the planes: 1.13 K/W through 25 filled vias; junction to heatsink 12.0 K/W (theta-JC top 8.4 + 3M 8810 tape 3.3 + base 0.3).

## Verdict

**Snapshot mode at 70 C: FAIL** (15 FAIL, 5 WARN). With the Wi-Fi's power save off (as built) every part stays inside its rating up to a **65.2 C** chamber by night and 67.4 C by day; with power save on, 68.5 C by night and 70.6 C by day. The part closest to its limit at 70 C is the **USB-C receptacle USB4105 (J1)**: 89.4 C against 85 C (-4.4 K).

| at 70 C | snapshot day, PS off | snapshot night, PS off | snapshot day, PS on | snapshot night, PS on | live view day | live view night |
|---|---|---|---|---|---|---|
| RV1106 junction (125 C) | 90.4 C | 92.2 C | 87.9 C | 89.7 C | 106.0 C | 114.1 C |
| image sensor (85 C; best image 60 C) | 86.8 C | 88.8 C | 83.8 C | 85.9 C | 99.7 C | 109.0 C |
| ESP32-C6 (105 C) | 89.3 C | 91.4 C | 84.8 C | 86.9 C | 100.9 C | 110.2 C |
| flash (85 C) | 87.3 C | 89.3 C | 84.3 C | 86.4 C | 99.2 C | 108.3 C |
| USB-C (85 C) | 87.4 C | 89.4 C | 84.0 C | 86.0 C | 97.8 C | 106.8 C |
| status LED (85 C) | 85.7 C | 87.8 C | 83.1 C | 85.2 C | 96.7 C | 106.2 C |
| air inside (85 C ambient parts) | 81.3 C | 82.6 C | 79.3 C | 80.7 C | 88.7 C | 95.0 C |
| IR LED junction while lit (100 C) | 87.3 C | 95.1 C | 84.3 C | 92.2 C | 99.3 C | 114.5 C |
| board max | 87.5 C | 89.5 C | 84.8 C | 86.8 C | 100.1 C | 109.1 C |
| heatsink | 86.1 C | 87.8 C | 83.7 C | 85.4 C | 97.6 C | 105.2 C |
| heat in the case | 0.91 W | 1.03 W | 0.73 W | 0.86 W | 1.64 W | 2.26 W |

Highest chamber temperature with every part inside its rating: snapshot day, PS off **67.4 C** (first: USB-C receptacle USB4105 (J1)); snapshot night, PS off **65.2 C** (first: USB-C receptacle USB4105 (J1)); snapshot day, PS on **70.6 C** (first: W25N02KV flash (U5)); snapshot night, PS on **68.5 C** (first: W25N02KV flash (U5)); live view day **53.6 C** (first: SC4336H image sensor (U8)); live view night **42.2 C** (first: SC4336H image sensor (U8)); stress bound **-9.4 C** (first: W25N02KV flash (U5)).

- **The board is nearly isothermal** (86.5-89.5 C in night snapshots): six copper layers spread the heat faster than the still air takes it off, so every part on it sits 16-20 K over the chamber and the four parts rated 85 C (USB-C, flash, image sensor, status LED) are within 1.6 K of each other. Their order is inside the model's uncertainty; what fails is the board as a whole: in snapshot mode it needs to run about 5 K cooler (power save off) or 2 K cooler (on) to pass at 70 C.
- **What moves it** (sensitivity table): Wi-Fi power save on +3.3 K of chamber; a 1 mm gap pad from the fin tops to the lid gives 66.4 C by night with power save off and 69.8 C with it on; chamber air moving at 0.5 m/s about 2 K; the copper slot between SoC and sensor under 0.5 K (the board spreads round it). No single in-case change modelled reaches 70 C by night.
- **Image sensor**: 88.8 C in night snapshots at 70 C (power save off), 85.9 C with it on; its 85 C is reached at a 65.8 C chamber, its best-image 60 C at 38.9 C (it is above 60 C in every case at 70 C: the chamber alone is 70 C).
- **Wi-Fi power save** off as built costs 2.9 K on the sensor and 2.5 K on the junction against power save on (snap_night), and 3.3 K of chamber rating.
- **The vent slots carry little**: 0.031 W of the heatsink's 0.23 W leaves through its three slots and 0.097 W through the lid over it; the rest goes into the case's inside air and the board. Without the heatsink the sensor would be 92.3 C; a gap pad from the fin tops to the lid would make it 87.5 C.
- Live view: every part in rating to 53.6 C by day and 42.2 C by night; it stays a firmware-gated mode (TSADC below 87 C; snapshot mode stretches to 30 s above 85 C).
- Model uncertainty about +-10 K (optimistic bracket: RV1106 91.7 C, sensor 88.2 C in snap_night); the placement is layout_main.py's, the copper coverage LayerCam v1's, the snapshot currents ASSUMED. Rerun on the routed board and measure the first board in a 70 C oven.

## Snapshot, day, Wi-Fi power save off (requirement, as built)

Heat in the case: **0.91 W** (U1 0.49, U6 0.32, U3 0.03, U8 0.02, U2 0.02, U5 0.01, U4 0.01, L1 0.01).

| | value |
|---|---|
| case wall | 76.6 C (6.6 K over the chamber) |
| air inside (mean of board and wall) | 81.3 C |
| board mean / max | 86.0 / 87.5 C |
| board heat out: faces / edge and bosses / into the heatsink's underside | 0.49 / 0.20 / 0.01 W |
| heatsink | 86.1 C; 0.21 W from the junction; out to the chamber through its slots 0.027 W (exchange flow 0.009 W), through the lid patch 0.087 W (patch 76.3 C) |
| other slots' air exchange | 0.011 W |
| RV1106 | 0.28 W into the board; board under the pad 87.4 C, at the package edge 86.9 C; Tj 88.6 C (pad path) / 90.4 C (theta-JB 12.5 from the edge) |

| part | temperature (C) | limit (C) | margin (K) | limit from |
|---|---|---|---|---|
| USB-C receptacle USB4105 (J1) | 87.4 | 85 | -2.4 | -40..85 C incl. rise (GCT) |
| W25N02KV flash (U5) | 87.3 | 85 | -2.3 | -40..85 C (Winbond) |
| SC4336H image sensor (U8) | 86.8 | 85 | -1.8 | -30..85 C operating; best image to 60 C (SmartSens) |
| status LED LED1 (KT-0603G) | 85.7 | 85 | -0.7 | -40..85 C (KENTO) |
| internal air (RV1106 / EA3036C ambient) | 81.3 | 85 | +3.7 | ambient operating max (RV1106 T3-2, EA3036C TA) |
| TEMT6000 light sensor (Q2) | 87.5 | 100 | +12.5 | -40..100 C (Vishay) |
| 3M 8810 tape on the RV1106 | 87.3 | 100 | +12.7 | long-term 100 C (3M; UNVERIFIED: data sheet not read here) |
| IR LEDs VSMY3850X01, junction while lit | 87.3 | 100 | +12.7 | Tj 100 C (Vishay VSMY3850 rev 1.5; the X01 grade's own data sheet not read) |
| ESP32-C6-MINI-1U-H4 (U6) | 89.3 | 105 | +15.7 | -40..105 C, the -H4 grade (Espressif) |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) under the SoC (B face) | 87.5 | 105 | +17.5 | X6S: -55..105 C |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the sensor | 86.7 | 105 | +18.3 | X6S: -55..105 C |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the bucks | 86.5 | 105 | +18.5 | X6S: -55..105 C |
| PicoBlade IR-cut lead socket (J3) | 85.1 | 105 | +19.9 | -40..105 C (Molex) |
| IR LEDs VSMY3850X01, ambient | 84.3 | 105 | +20.7 | -40..105 C, X01 grade (parts.py; the base part is rated 85 C) |
| case wall (PC carbon fibre) | 76.6 | 110 | +33.4 | softens near its HDT, ~110 C (PC; ESTIMATED) |
| RV1106 junction (U1) | 90.4 | 125 | +34.6 | Tj max (datasheet 4.1) |
| X7S capacitors (1uF) under the SoC (B face) | 87.5 | 125 | +37.5 | X7S: -55..125 C |
| crystals Y1 (24 MHz) / Y2 (32 kHz) | 87.2 | 125 | +37.8 | -40..125 C (ECS, Abracon) |
| TLV62569 0.9 V (U2) junction | 87.1 | 125 | +37.9 | TJ max (SLVSDG1C 6.3) |
| X7S capacitors (1uF) at the sensor | 86.7 | 125 | +38.3 | X7S: -55..125 C |
| TLV62569 Wi-Fi (U4) junction | 86.6 | 125 | +38.4 | TJ max (SLVSDG1C 6.3) |
| inductor L1 (DFE252012F) | 86.6 | 125 | +38.4 | -40..125 C incl. self-heating (Murata) |
| X7S capacitors (1uF) at the bucks | 86.5 | 125 | +38.5 | X7S: -55..125 C |
| inductor L5 (DFE252012F) | 86.4 | 125 | +38.6 | -40..125 C incl. self-heating (Murata) |
| EA3036C junction (U3) | 86.4 | 125 | +38.6 | TJ range (datasheet) |
| TLV75528 sensor LDO junction (U9) | 86.2 | 125 | +38.8 | TJ max (SBVS320D) |
| USBLC6 / SMF6.0CA (U10 / D1) | 85.9 | 125 | +39.1 | TJ to 125 / 150 C |
| inductor L4 (DFE252012F) | 85.9 | 125 | +39.1 | -40..125 C incl. self-heating (Murata) |
| inductor L3 (DFE252012F) | 85.7 | 125 | +39.3 | -40..125 C incl. self-heating (Murata) |
| DRV8210P IR-cut driver (U7) | 85.7 | 125 | +39.3 | TA -40..125 C (TI) |
| inductor L2 (DFE252012F) | 85.6 | 125 | +39.4 | -40..125 C incl. self-heating (Murata) |

Image sensor: **86.8 C** against its 85 C rating (-1.8 K) and its best-image limit of 60 C (-26.8 K).

![snap_day](thermal_snap_day.png)

## Snapshot, night, IR LEDs lit 2 s of every 10 s, Wi-Fi power save off (requirement, as built)

Heat in the case: **1.03 W** (U1 0.49, U6 0.32, U3 0.03, U8 0.02, R45 0.02, R46 0.02, R47 0.02, U2 0.02, U5 0.01, D2 0.01, D3 0.01, D4 0.01, D5 0.01, D6 0.01, D7 0.01, U4 0.01, L1 0.01).

| | value |
|---|---|
| case wall | 77.3 C (7.3 K over the chamber) |
| air inside (mean of board and wall) | 82.6 C |
| board mean / max | 88.0 / 89.5 C |
| board heat out: faces / edge and bosses / into the heatsink's underside | 0.57 / 0.23 / 0.01 W |
| heatsink | 87.8 C; 0.23 W from the junction; out to the chamber through its slots 0.031 W (exchange flow 0.011 W), through the lid patch 0.097 W (patch 76.9 C) |
| other slots' air exchange | 0.014 W |
| RV1106 | 0.26 W into the board; board under the pad 89.4 C, at the package edge 89.0 C; Tj 90.5 C (pad path) / 92.2 C (theta-JB 12.5 from the edge) |

| part | temperature (C) | limit (C) | margin (K) | limit from |
|---|---|---|---|---|
| USB-C receptacle USB4105 (J1) | 89.4 | 85 | -4.4 | -40..85 C incl. rise (GCT) |
| W25N02KV flash (U5) | 89.3 | 85 | -4.3 | -40..85 C (Winbond) |
| SC4336H image sensor (U8) | 88.8 | 85 | -3.8 | -30..85 C operating; best image to 60 C (SmartSens) |
| status LED LED1 (KT-0603G) | 87.8 | 85 | -2.8 | -40..85 C (KENTO) |
| internal air (RV1106 / EA3036C ambient) | 82.6 | 85 | +2.4 | ambient operating max (RV1106 T3-2, EA3036C TA) |
| IR LEDs VSMY3850X01, junction while lit | 95.1 | 100 | +4.9 | Tj 100 C (Vishay VSMY3850 rev 1.5; the X01 grade's own data sheet not read) |
| TEMT6000 light sensor (Q2) | 89.5 | 100 | +10.5 | -40..100 C (Vishay) |
| 3M 8810 tape on the RV1106 | 89.1 | 100 | +10.9 | long-term 100 C (3M; UNVERIFIED: data sheet not read here) |
| ESP32-C6-MINI-1U-H4 (U6) | 91.4 | 105 | +13.6 | -40..105 C, the -H4 grade (Espressif) |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) under the SoC (B face) | 89.5 | 105 | +15.5 | X6S: -55..105 C |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the sensor | 88.7 | 105 | +16.3 | X6S: -55..105 C |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the bucks | 88.5 | 105 | +16.5 | X6S: -55..105 C |
| PicoBlade IR-cut lead socket (J3) | 87.2 | 105 | +17.8 | -40..105 C (Molex) |
| IR LEDs VSMY3850X01, ambient | 86.0 | 105 | +19.0 | -40..105 C, X01 grade (parts.py; the base part is rated 85 C) |
| case wall (PC carbon fibre) | 77.3 | 110 | +32.7 | softens near its HDT, ~110 C (PC; ESTIMATED) |
| RV1106 junction (U1) | 92.2 | 125 | +32.8 | Tj max (datasheet 4.1) |
| X7S capacitors (1uF) under the SoC (B face) | 89.5 | 125 | +35.5 | X7S: -55..125 C |
| crystals Y1 (24 MHz) / Y2 (32 kHz) | 89.3 | 125 | +35.7 | -40..125 C (ECS, Abracon) |
| TLV62569 0.9 V (U2) junction | 89.1 | 125 | +35.9 | TJ max (SLVSDG1C 6.3) |
| X7S capacitors (1uF) at the sensor | 88.7 | 125 | +36.3 | X7S: -55..125 C |
| TLV62569 Wi-Fi (U4) junction | 88.7 | 125 | +36.3 | TJ max (SLVSDG1C 6.3) |
| X7S capacitors (1uF) at the bucks | 88.5 | 125 | +36.5 | X7S: -55..125 C |
| inductor L1 (DFE252012F) | 88.5 | 125 | +36.5 | -40..125 C incl. self-heating (Murata) |
| inductor L5 (DFE252012F) | 88.5 | 125 | +36.5 | -40..125 C incl. self-heating (Murata) |
| EA3036C junction (U3) | 88.4 | 125 | +36.6 | TJ range (datasheet) |
| TLV75528 sensor LDO junction (U9) | 88.3 | 125 | +36.7 | TJ max (SBVS320D) |
| USBLC6 / SMF6.0CA (U10 / D1) | 87.9 | 125 | +37.1 | TJ to 125 / 150 C |
| inductor L4 (DFE252012F) | 87.9 | 125 | +37.1 | -40..125 C incl. self-heating (Murata) |
| DRV8210P IR-cut driver (U7) | 87.8 | 125 | +37.2 | TA -40..125 C (TI) |
| inductor L3 (DFE252012F) | 87.8 | 125 | +37.2 | -40..125 C incl. self-heating (Murata) |
| inductor L2 (DFE252012F) | 87.6 | 125 | +37.4 | -40..125 C incl. self-heating (Murata) |
| 47R string resistors, power while lit | 0.110 W | 0.193 W at 89 C | +0.083 W | 0.25 W to 70 C, 0 at 155 C |

Image sensor: **88.8 C** against its 85 C rating (-3.8 K) and its best-image limit of 60 C (-28.8 K).

![snap_night](thermal_snap_night.png)

## Snapshot, day, Wi-Fi power save on (requirement, once fixed)

Heat in the case: **0.73 W** (U1 0.49, U6 0.15, U3 0.03, U8 0.02, U2 0.02, U5 0.01, U4 0.01, L1 0.01).

| | value |
|---|---|
| case wall | 75.5 C (5.5 K over the chamber) |
| air inside (mean of board and wall) | 79.3 C |
| board mean / max | 83.1 / 84.8 C |
| board heat out: faces / edge and bosses / into the heatsink's underside | 0.39 / 0.16 / 0.00 W |
| heatsink | 83.7 C; 0.19 W from the junction; out to the chamber through its slots 0.022 W (exchange flow 0.007 W), through the lid patch 0.073 W (patch 75.3 C) |
| other slots' air exchange | 0.009 W |
| RV1106 | 0.30 W into the board; board under the pad 84.7 C, at the package edge 84.1 C; Tj 85.9 C (pad path) / 87.9 C (theta-JB 12.5 from the edge) |

| part | temperature (C) | limit (C) | margin (K) | limit from |
|---|---|---|---|---|
| W25N02KV flash (U5) | 84.3 | 85 | +0.7 | -40..85 C (Winbond) |
| USB-C receptacle USB4105 (J1) | 84.0 | 85 | +1.0 | -40..85 C incl. rise (GCT) |
| SC4336H image sensor (U8) | 83.8 | 85 | +1.2 | -30..85 C operating; best image to 60 C (SmartSens) |
| status LED LED1 (KT-0603G) | 83.1 | 85 | +1.9 | -40..85 C (KENTO) |
| internal air (RV1106 / EA3036C ambient) | 79.3 | 85 | +5.7 | ambient operating max (RV1106 T3-2, EA3036C TA) |
| 3M 8810 tape on the RV1106 | 84.9 | 100 | +15.1 | long-term 100 C (3M; UNVERIFIED: data sheet not read here) |
| TEMT6000 light sensor (Q2) | 84.8 | 100 | +15.2 | -40..100 C (Vishay) |
| IR LEDs VSMY3850X01, junction while lit | 84.3 | 100 | +15.7 | Tj 100 C (Vishay VSMY3850 rev 1.5; the X01 grade's own data sheet not read) |
| ESP32-C6-MINI-1U-H4 (U6) | 84.8 | 105 | +20.2 | -40..105 C, the -H4 grade (Espressif) |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) under the SoC (B face) | 84.8 | 105 | +20.2 | X6S: -55..105 C |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the bucks | 83.9 | 105 | +21.1 | X6S: -55..105 C |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the sensor | 83.6 | 105 | +21.4 | X6S: -55..105 C |
| PicoBlade IR-cut lead socket (J3) | 82.5 | 105 | +22.5 | -40..105 C (Molex) |
| IR LEDs VSMY3850X01, ambient | 81.8 | 105 | +23.2 | -40..105 C, X01 grade (parts.py; the base part is rated 85 C) |
| case wall (PC carbon fibre) | 75.5 | 110 | +34.5 | softens near its HDT, ~110 C (PC; ESTIMATED) |
| RV1106 junction (U1) | 87.9 | 125 | +37.1 | Tj max (datasheet 4.1) |
| X7S capacitors (1uF) under the SoC (B face) | 84.8 | 125 | +40.2 | X7S: -55..125 C |
| TLV62569 0.9 V (U2) junction | 84.5 | 125 | +40.5 | TJ max (SLVSDG1C 6.3) |
| crystals Y1 (24 MHz) / Y2 (32 kHz) | 84.2 | 125 | +40.8 | -40..125 C (ECS, Abracon) |
| inductor L1 (DFE252012F) | 84.0 | 125 | +41.0 | -40..125 C incl. self-heating (Murata) |
| X7S capacitors (1uF) at the bucks | 83.9 | 125 | +41.1 | X7S: -55..125 C |
| EA3036C junction (U3) | 83.8 | 125 | +41.2 | TJ range (datasheet) |
| X7S capacitors (1uF) at the sensor | 83.6 | 125 | +41.4 | X7S: -55..125 C |
| inductor L4 (DFE252012F) | 83.3 | 125 | +41.7 | -40..125 C incl. self-heating (Murata) |
| TLV62569 Wi-Fi (U4) junction | 83.3 | 125 | +41.7 | TJ max (SLVSDG1C 6.3) |
| TLV75528 sensor LDO junction (U9) | 83.2 | 125 | +41.8 | TJ max (SBVS320D) |
| inductor L3 (DFE252012F) | 83.2 | 125 | +41.8 | -40..125 C incl. self-heating (Murata) |
| DRV8210P IR-cut driver (U7) | 83.1 | 125 | +41.9 | TA -40..125 C (TI) |
| inductor L5 (DFE252012F) | 83.1 | 125 | +41.9 | -40..125 C incl. self-heating (Murata) |
| inductor L2 (DFE252012F) | 83.0 | 125 | +42.0 | -40..125 C incl. self-heating (Murata) |
| USBLC6 / SMF6.0CA (U10 / D1) | 82.7 | 125 | +42.3 | TJ to 125 / 150 C |

Image sensor: **83.8 C** against its 85 C rating (+1.2 K) and its best-image limit of 60 C (-23.8 K).

![snap_day_ps](thermal_snap_day_ps.png)

## Snapshot, night, Wi-Fi power save on (requirement, once fixed)

Heat in the case: **0.86 W** (U1 0.49, U6 0.15, U3 0.03, U8 0.02, R45 0.02, R46 0.02, R47 0.02, U2 0.02, U5 0.01, D2 0.01, D3 0.01, D4 0.01, D5 0.01, D6 0.01, D7 0.01, U4 0.01, L1 0.01).

| | value |
|---|---|
| case wall | 76.3 C (6.3 K over the chamber) |
| air inside (mean of board and wall) | 80.7 C |
| board mean / max | 85.2 / 86.8 C |
| board heat out: faces / edge and bosses / into the heatsink's underside | 0.46 / 0.19 / 0.01 W |
| heatsink | 85.4 C; 0.20 W from the junction; out to the chamber through its slots 0.026 W (exchange flow 0.008 W), through the lid patch 0.083 W (patch 76.0 C) |
| other slots' air exchange | 0.011 W |
| RV1106 | 0.28 W into the board; board under the pad 86.7 C, at the package edge 86.2 C; Tj 87.9 C (pad path) / 89.7 C (theta-JB 12.5 from the edge) |

| part | temperature (C) | limit (C) | margin (K) | limit from |
|---|---|---|---|---|
| W25N02KV flash (U5) | 86.4 | 85 | -1.4 | -40..85 C (Winbond) |
| USB-C receptacle USB4105 (J1) | 86.0 | 85 | -1.0 | -40..85 C incl. rise (GCT) |
| SC4336H image sensor (U8) | 85.9 | 85 | -0.9 | -30..85 C operating; best image to 60 C (SmartSens) |
| status LED LED1 (KT-0603G) | 85.2 | 85 | -0.2 | -40..85 C (KENTO) |
| internal air (RV1106 / EA3036C ambient) | 80.7 | 85 | +4.3 | ambient operating max (RV1106 T3-2, EA3036C TA) |
| IR LEDs VSMY3850X01, junction while lit | 92.2 | 100 | +7.8 | Tj 100 C (Vishay VSMY3850 rev 1.5; the X01 grade's own data sheet not read) |
| TEMT6000 light sensor (Q2) | 86.8 | 100 | +13.2 | -40..100 C (Vishay) |
| 3M 8810 tape on the RV1106 | 86.7 | 100 | +13.3 | long-term 100 C (3M; UNVERIFIED: data sheet not read here) |
| ESP32-C6-MINI-1U-H4 (U6) | 86.9 | 105 | +18.1 | -40..105 C, the -H4 grade (Espressif) |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) under the SoC (B face) | 86.8 | 105 | +18.2 | X6S: -55..105 C |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the bucks | 85.9 | 105 | +19.1 | X6S: -55..105 C |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the sensor | 85.7 | 105 | +19.3 | X6S: -55..105 C |
| PicoBlade IR-cut lead socket (J3) | 84.7 | 105 | +20.3 | -40..105 C (Molex) |
| IR LEDs VSMY3850X01, ambient | 83.6 | 105 | +21.4 | -40..105 C, X01 grade (parts.py; the base part is rated 85 C) |
| case wall (PC carbon fibre) | 76.3 | 110 | +33.7 | softens near its HDT, ~110 C (PC; ESTIMATED) |
| RV1106 junction (U1) | 89.7 | 125 | +35.3 | Tj max (datasheet 4.1) |
| X7S capacitors (1uF) under the SoC (B face) | 86.8 | 125 | +38.2 | X7S: -55..125 C |
| TLV62569 0.9 V (U2) junction | 86.5 | 125 | +38.5 | TJ max (SLVSDG1C 6.3) |
| crystals Y1 (24 MHz) / Y2 (32 kHz) | 86.3 | 125 | +38.7 | -40..125 C (ECS, Abracon) |
| inductor L1 (DFE252012F) | 86.0 | 125 | +39.0 | -40..125 C incl. self-heating (Murata) |
| X7S capacitors (1uF) at the bucks | 85.9 | 125 | +39.1 | X7S: -55..125 C |
| EA3036C junction (U3) | 85.8 | 125 | +39.2 | TJ range (datasheet) |
| X7S capacitors (1uF) at the sensor | 85.7 | 125 | +39.3 | X7S: -55..125 C |
| TLV62569 Wi-Fi (U4) junction | 85.4 | 125 | +39.6 | TJ max (SLVSDG1C 6.3) |
| inductor L4 (DFE252012F) | 85.4 | 125 | +39.6 | -40..125 C incl. self-heating (Murata) |
| TLV75528 sensor LDO junction (U9) | 85.4 | 125 | +39.6 | TJ max (SBVS320D) |
| inductor L3 (DFE252012F) | 85.3 | 125 | +39.7 | -40..125 C incl. self-heating (Murata) |
| DRV8210P IR-cut driver (U7) | 85.2 | 125 | +39.8 | TA -40..125 C (TI) |
| inductor L5 (DFE252012F) | 85.2 | 125 | +39.8 | -40..125 C incl. self-heating (Murata) |
| inductor L2 (DFE252012F) | 85.1 | 125 | +39.9 | -40..125 C incl. self-heating (Murata) |
| USBLC6 / SMF6.0CA (U10 / D1) | 84.8 | 125 | +40.2 | TJ to 125 / 150 C |
| 47R string resistors, power while lit | 0.110 W | 0.202 W at 86 C | +0.092 W | 0.25 W to 70 C, 0 at 155 C |

Image sensor: **85.9 C** against its 85 C rating (-0.9 K) and its best-image limit of 60 C (-25.9 K).

![snap_night_ps](thermal_snap_night_ps.png)

## Live view, day: streaming (reported, not required)

Heat in the case: **1.64 W** (U1 0.97, U6 0.38, U8 0.12, U2 0.06, L1 0.04, U3 0.03, U5 0.02, U4 0.01, U9 0.01).

| | value |
|---|---|
| case wall | 80.7 C (10.7 K over the chamber) |
| air inside (mean of board and wall) | 88.7 C |
| board mean / max | 96.8 / 100.1 C |
| board heat out: faces / edge and bosses / into the heatsink's underside | 0.90 / 0.34 / 0.01 W |
| heatsink | 97.6 C; 0.39 W from the junction; out to the chamber through its slots 0.056 W (exchange flow 0.024 W), through the lid patch 0.151 W (patch 80.3 C) |
| other slots' air exchange | 0.024 W |
| RV1106 | 0.57 W into the board; board under the pad 99.9 C, at the package edge 98.8 C; Tj 102.2 C (pad path) / 106.0 C (theta-JB 12.5 from the edge) |

| part | temperature (C) | limit (C) | margin (K) | limit from |
|---|---|---|---|---|
| SC4336H image sensor (U8) | 99.7 | 85 | -14.7 | -30..85 C operating; best image to 60 C (SmartSens) |
| W25N02KV flash (U5) | 99.2 | 85 | -14.2 | -40..85 C (Winbond) |
| USB-C receptacle USB4105 (J1) | 97.8 | 85 | -12.8 | -40..85 C incl. rise (GCT) |
| status LED LED1 (KT-0603G) | 96.7 | 85 | -11.7 | -40..85 C (KENTO) |
| internal air (RV1106 / EA3036C ambient) | 88.7 | 85 | -3.7 | ambient operating max (RV1106 T3-2, EA3036C TA) |
| 3M 8810 tape on the RV1106 | 100.1 | 100 | -0.1 | long-term 100 C (3M; UNVERIFIED: data sheet not read here) |
| TEMT6000 light sensor (Q2) | 100.1 | 100 | -0.1 | -40..100 C (Vishay) |
| IR LEDs VSMY3850X01, junction while lit | 99.3 | 100 | +0.7 | Tj 100 C (Vishay VSMY3850 rev 1.5; the X01 grade's own data sheet not read) |
| ESP32-C6-MINI-1U-H4 (U6) | 100.9 | 105 | +4.1 | -40..105 C, the -H4 grade (Espressif) |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) under the SoC (B face) | 100.1 | 105 | +4.9 | X6S: -55..105 C |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the bucks | 98.4 | 105 | +6.6 | X6S: -55..105 C |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the sensor | 98.1 | 105 | +6.9 | X6S: -55..105 C |
| PicoBlade IR-cut lead socket (J3) | 95.5 | 105 | +9.5 | -40..105 C (Molex) |
| IR LEDs VSMY3850X01, ambient | 94.0 | 105 | +11.0 | -40..105 C, X01 grade (parts.py; the base part is rated 85 C) |
| RV1106 junction (U1) | 106.0 | 125 | +19.0 | Tj max (datasheet 4.1) |
| TLV62569 0.9 V (U2) junction | 100.7 | 125 | +24.3 | TJ max (SLVSDG1C 6.3) |
| inductor L1 (DFE252012F) | 100.2 | 125 | +24.8 | -40..125 C incl. self-heating (Murata) |
| X7S capacitors (1uF) under the SoC (B face) | 100.1 | 125 | +24.9 | X7S: -55..125 C |
| crystals Y1 (24 MHz) / Y2 (32 kHz) | 99.0 | 125 | +26.0 | -40..125 C (ECS, Abracon) |
| X7S capacitors (1uF) at the bucks | 98.4 | 125 | +26.6 | X7S: -55..125 C |
| X7S capacitors (1uF) at the sensor | 98.1 | 125 | +26.9 | X7S: -55..125 C |
| EA3036C junction (U3) | 97.7 | 125 | +27.3 | TJ range (datasheet) |
| TLV75528 sensor LDO junction (U9) | 97.6 | 125 | +27.4 | TJ max (SBVS320D) |
| TLV62569 Wi-Fi (U4) junction | 97.2 | 125 | +27.8 | TJ max (SLVSDG1C 6.3) |
| inductor L4 (DFE252012F) | 97.1 | 125 | +27.9 | -40..125 C incl. self-heating (Murata) |
| inductor L5 (DFE252012F) | 96.9 | 125 | +28.1 | -40..125 C incl. self-heating (Murata) |
| inductor L3 (DFE252012F) | 96.8 | 125 | +28.2 | -40..125 C incl. self-heating (Murata) |
| DRV8210P IR-cut driver (U7) | 96.7 | 125 | +28.3 | TA -40..125 C (TI) |
| inductor L2 (DFE252012F) | 96.4 | 125 | +28.6 | -40..125 C incl. self-heating (Murata) |
| USBLC6 / SMF6.0CA (U10 / D1) | 96.1 | 125 | +28.9 | TJ to 125 / 150 C |
| case wall (PC carbon fibre) | 80.7 | 110 | +29.3 | softens near its HDT, ~110 C (PC; ESTIMATED) |

Image sensor: **99.7 C** against its 85 C rating (-14.7 K) and its best-image limit of 60 C (-39.7 K).

![day](thermal_day.png)

## Live view, night: streaming with the IR LEDs on (reported, not required)

Heat in the case: **2.26 W** (U1 0.97, U6 0.38, U8 0.12, R45 0.11, R46 0.11, R47 0.11, U2 0.06, D2 0.05, D3 0.05, D4 0.05, D5 0.05, D6 0.05, D7 0.05, L1 0.04, U3 0.03, U5 0.02, U4 0.01, J1 0.01, U9 0.01).

| | value |
|---|---|
| case wall | 84.0 C (14.0 K over the chamber) |
| air inside (mean of board and wall) | 95.0 C |
| board mean / max | 106.0 / 109.1 C |
| board heat out: faces / edge and bosses / into the heatsink's underside | 1.30 / 0.46 / 0.02 W |
| heatsink | 105.2 C; 0.47 W from the junction; out to the chamber through its slots 0.079 W (exchange flow 0.036 W), through the lid patch 0.200 W (patch 83.2 C) |
| other slots' air exchange | 0.038 W |
| RV1106 | 0.49 W into the board; board under the pad 108.9 C, at the package edge 108.0 C; Tj 110.9 C (pad path) / 114.1 C (theta-JB 12.5 from the edge) |

| part | temperature (C) | limit (C) | margin (K) | limit from |
|---|---|---|---|---|
| SC4336H image sensor (U8) | 109.0 | 85 | -24.0 | -30..85 C operating; best image to 60 C (SmartSens) |
| W25N02KV flash (U5) | 108.3 | 85 | -23.3 | -40..85 C (Winbond) |
| USB-C receptacle USB4105 (J1) | 106.8 | 85 | -21.8 | -40..85 C incl. rise (GCT) |
| status LED LED1 (KT-0603G) | 106.2 | 85 | -21.2 | -40..85 C (KENTO) |
| IR LEDs VSMY3850X01, junction while lit | 114.5 | 100 | -14.5 | Tj 100 C (Vishay VSMY3850 rev 1.5; the X01 grade's own data sheet not read) |
| internal air (RV1106 / EA3036C ambient) | 95.0 | 85 | -10.0 | ambient operating max (RV1106 T3-2, EA3036C TA) |
| TEMT6000 light sensor (Q2) | 109.1 | 100 | -9.1 | -40..100 C (Vishay) |
| 3M 8810 tape on the RV1106 | 107.9 | 100 | -7.9 | long-term 100 C (3M; UNVERIFIED: data sheet not read here) |
| ESP32-C6-MINI-1U-H4 (U6) | 110.2 | 105 | -5.2 | -40..105 C, the -H4 grade (Espressif) |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) under the SoC (B face) | 109.1 | 105 | -4.1 | X6S: -55..105 C |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the sensor | 107.4 | 105 | -2.4 | X6S: -55..105 C |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the bucks | 107.2 | 105 | -2.2 | X6S: -55..105 C |
| PicoBlade IR-cut lead socket (J3) | 105.1 | 105 | -0.1 | -40..105 C (Molex) |
| IR LEDs VSMY3850X01, ambient | 101.9 | 105 | +3.1 | -40..105 C, X01 grade (parts.py; the base part is rated 85 C) |
| RV1106 junction (U1) | 114.1 | 125 | +10.9 | Tj max (datasheet 4.1) |
| TLV62569 0.9 V (U2) junction | 109.5 | 125 | +15.5 | TJ max (SLVSDG1C 6.3) |
| X7S capacitors (1uF) under the SoC (B face) | 109.1 | 125 | +15.9 | X7S: -55..125 C |
| inductor L1 (DFE252012F) | 109.1 | 125 | +15.9 | -40..125 C incl. self-heating (Murata) |
| crystals Y1 (24 MHz) / Y2 (32 kHz) | 108.6 | 125 | +16.4 | -40..125 C (ECS, Abracon) |
| X7S capacitors (1uF) at the sensor | 107.4 | 125 | +17.6 | X7S: -55..125 C |
| X7S capacitors (1uF) at the bucks | 107.2 | 125 | +17.8 | X7S: -55..125 C |
| TLV75528 sensor LDO junction (U9) | 107.0 | 125 | +18.0 | TJ max (SBVS320D) |
| EA3036C junction (U3) | 106.8 | 125 | +18.2 | TJ range (datasheet) |
| TLV62569 Wi-Fi (U4) junction | 106.5 | 125 | +18.5 | TJ max (SLVSDG1C 6.3) |
| inductor L5 (DFE252012F) | 106.2 | 125 | +18.8 | -40..125 C incl. self-heating (Murata) |
| inductor L4 (DFE252012F) | 106.0 | 125 | +19.0 | -40..125 C incl. self-heating (Murata) |
| DRV8210P IR-cut driver (U7) | 106.0 | 125 | +19.0 | TA -40..125 C (TI) |
| inductor L3 (DFE252012F) | 105.9 | 125 | +19.1 | -40..125 C incl. self-heating (Murata) |
| inductor L2 (DFE252012F) | 105.6 | 125 | +19.4 | -40..125 C incl. self-heating (Murata) |
| USBLC6 / SMF6.0CA (U10 / D1) | 105.3 | 125 | +19.7 | TJ to 125 / 150 C |
| case wall (PC carbon fibre) | 84.0 | 110 | +26.0 | softens near its HDT, ~110 C (PC; ESTIMATED) |
| 47R string resistors, power while lit | 0.110 W | 0.136 W at 109 C | +0.026 W | 0.25 W to 70 C, 0 at 155 C |

Image sensor: **109.0 C** against its 85 C rating (-24.0 K) and its best-image limit of 60 C (-49.0 K).

![night](thermal_night.png)

## Stress bound: SoC flat out, Wi-Fi transmitting, LEDs at the high corner (reported)

Heat in the case: **4.87 W** (U1 2.06, U6 1.21, U2 0.23, L1 0.20, U8 0.15, R45 0.14, R46 0.14, R47 0.14, U5 0.11, U3 0.06, D2 0.05, D3 0.05, D4 0.05, D5 0.05, D6 0.05, D7 0.05, J1 0.04, U4 0.03, L5 0.02, U9 0.01, L3 0.01).

| | value |
|---|---|
| case wall | 96.9 C (26.9 K over the chamber) |
| air inside (mean of board and wall) | 117.7 C |
| board mean / max | 138.6 / 145.6 C |
| board heat out: faces / edge and bosses / into the heatsink's underside | 2.96 / 0.88 / 0.05 W |
| heatsink | 137.7 C; 0.98 W from the junction; out to the chamber through its slots 0.201 W (exchange flow 0.112 W), through the lid patch 0.410 W (patch 94.6 C) |
| other slots' air exchange | 0.099 W |
| RV1106 | 1.07 W into the board; board under the pad 145.1 C, at the package edge 143.2 C; Tj 149.5 C (pad path) / 156.6 C (theta-JB 12.5 from the edge) |

| part | temperature (C) | limit (C) | margin (K) | limit from |
|---|---|---|---|---|
| W25N02KV flash (U5) | 146.1 | 85 | -61.1 | -40..85 C (Winbond) |
| SC4336H image sensor (U8) | 142.8 | 85 | -57.8 | -30..85 C operating; best image to 60 C (SmartSens) |
| USB-C receptacle USB4105 (J1) | 140.4 | 85 | -55.4 | -40..85 C incl. rise (GCT) |
| status LED LED1 (KT-0603G) | 138.2 | 85 | -53.2 | -40..85 C (KENTO) |
| IR LEDs VSMY3850X01, junction while lit | 151.2 | 100 | -51.2 | Tj 100 C (Vishay VSMY3850 rev 1.5; the X01 grade's own data sheet not read) |
| ESP32-C6-MINI-1U-H4 (U6) | 151.3 | 105 | -46.3 | -40..105 C, the -H4 grade (Espressif) |
| TEMT6000 light sensor (Q2) | 145.5 | 100 | -45.5 | -40..100 C (Vishay) |
| 3M 8810 tape on the RV1106 | 143.3 | 100 | -43.3 | long-term 100 C (3M; UNVERIFIED: data sheet not read here) |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) under the SoC (B face) | 145.6 | 105 | -40.6 | X6S: -55..105 C |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the bucks | 142.9 | 105 | -37.9 | X6S: -55..105 C |
| X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the sensor | 141.5 | 105 | -36.5 | X6S: -55..105 C |
| internal air (RV1106 / EA3036C ambient) | 117.7 | 85 | -32.7 | ambient operating max (RV1106 T3-2, EA3036C TA) |
| RV1106 junction (U1) | 156.6 | 125 | -31.6 | Tj max (datasheet 4.1) |
| PicoBlade IR-cut lead socket (J3) | 135.5 | 105 | -30.5 | -40..105 C (Molex) |
| inductor L1 (DFE252012F) | 154.2 | 125 | -29.2 | -40..125 C incl. self-heating (Murata) |
| TLV62569 0.9 V (U2) junction | 152.2 | 125 | -27.2 | TJ max (SLVSDG1C 6.3) |
| IR LEDs VSMY3850X01, ambient | 131.2 | 105 | -26.2 | -40..105 C, X01 grade (parts.py; the base part is rated 85 C) |
| X7S capacitors (1uF) under the SoC (B face) | 145.6 | 125 | -20.6 | X7S: -55..125 C |
| crystals Y1 (24 MHz) / Y2 (32 kHz) | 144.5 | 125 | -19.5 | -40..125 C (ECS, Abracon) |
| X7S capacitors (1uF) at the bucks | 142.9 | 125 | -17.9 | X7S: -55..125 C |
| X7S capacitors (1uF) at the sensor | 141.5 | 125 | -16.5 | X7S: -55..125 C |
| TLV62569 Wi-Fi (U4) junction | 140.7 | 125 | -15.7 | TJ max (SLVSDG1C 6.3) |
| inductor L5 (DFE252012F) | 140.3 | 125 | -15.3 | -40..125 C incl. self-heating (Murata) |
| EA3036C junction (U3) | 140.1 | 125 | -15.1 | TJ range (datasheet) |
| TLV75528 sensor LDO junction (U9) | 139.8 | 125 | -14.8 | TJ max (SBVS320D) |
| inductor L4 (DFE252012F) | 139.0 | 125 | -14.0 | -40..125 C incl. self-heating (Murata) |
| inductor L3 (DFE252012F) | 138.4 | 125 | -13.4 | -40..125 C incl. self-heating (Murata) |
| DRV8210P IR-cut driver (U7) | 138.1 | 125 | -13.1 | TA -40..125 C (TI) |
| USBLC6 / SMF6.0CA (U10 / D1) | 137.7 | 125 | -12.7 | TJ to 125 / 150 C |
| inductor L2 (DFE252012F) | 137.2 | 125 | -12.2 | -40..125 C incl. self-heating (Murata) |
| case wall (PC carbon fibre) | 96.9 | 110 | +13.1 | softens near its HDT, ~110 C (PC; ESTIMATED) |
| 47R string resistors, power while lit | 0.138 W | 0.030 W at 145 C | -0.109 W | 0.25 W to 70 C, 0 at 155 C |

Image sensor: **142.8 C** against its 85 C rating (-57.8 K) and its best-image limit of 60 C (-82.8 K).

![worst](thermal_worst.png)

## Sensitivity (snap_night, power save off)

| change | RV1106 Tj (C) | image sensor (C) | C6 (C) | flash (C) | USB-C (C) | heatsink (C) | out by the slots / lid patch (W) |
|---|---|---|---|---|---|---|---|
| as above | 92.2 | 88.8 | 91.4 | 89.3 | 89.4 | 87.8 | 0.031 / 0.097 |
| Wi-Fi power save on (snap_night_ps) | 89.7 | 85.9 | 86.9 | 86.4 | 86.0 | 85.4 | 0.026 / 0.083 |
| no heatsink (bare chip) | 99.1 | 92.3 | 94.8 | 93.3 | 92.4 | - | 0.000 / 0.000 |
| the three slots over the heatsink taped over | 92.3 | 88.9 | 91.5 | 89.5 | 89.5 | 87.9 | 0.000 / 0.112 |
| camera looking straight down (slots level: no exchange flow) | 92.5 | 89.0 | 91.6 | 89.6 | 89.6 | 88.1 | 0.021 / 0.099 |
| camera looking level (slots one above the other) | 92.1 | 88.8 | 91.3 | 89.3 | 89.3 | 87.7 | 0.035 / 0.096 |
| a 1 mm 6 W/mK gap pad from the fin tops to the lid (option) | 90.0 | 87.5 | 90.1 | 87.9 | 88.2 | 85.3 | 0.026 / 0.154 |
| power save on and the gap pad | 87.8 | 84.8 | 85.7 | 85.1 | 85.0 | 83.2 | 0.021 / 0.131 |
| a slot through the copper between SoC and sensor (y 5.4, 22 mm long; option) | 92.3 | 88.4 | 91.4 | 89.4 | 89.3 | 87.9 | 0.032 / 0.097 |
| copper coverage x0.7 (a more perforated routed board) | 92.3 | 88.9 | 91.8 | 89.6 | 89.5 | 88.0 | 0.032 / 0.098 |
| case wall 0.20 W/mK (plain PC) | 92.6 | 89.2 | 91.7 | 89.7 | 89.7 | 88.2 | 0.032 / 0.080 |
| case wall 0.50 / 0.90 W/mK (high fibre loading) | 91.9 | 88.5 | 91.1 | 89.0 | 89.1 | 87.4 | 0.031 / 0.106 |
| inside emissivity 0.6 (bare metal holder, lens, shields) | 93.0 | 89.8 | 92.4 | 90.3 | 90.4 | 88.6 | 0.033 / 0.099 |
| optimistic bracket: emissivity 0.85, copper x1.2 | 91.7 | 88.2 | 90.6 | 88.6 | 88.8 | 87.2 | 0.030 / 0.095 |
| chamber air moving at 0.5 m/s past the case | 90.1 | 86.7 | 89.2 | 87.2 | 87.3 | 85.6 | 0.029 / 0.099 |
| SoC idle 50 % higher than assumed | 98.4 | 92.5 | 95.0 | 93.3 | 92.7 | 91.9 | 0.041 / 0.119 |
| C6 30 % above its datasheet figures (hot) | 93.5 | 90.4 | 93.9 | 90.9 | 91.2 | 89.0 | 0.034 / 0.104 |

## Highest chamber temperature per case

Bisection on the same model: the chamber temperature at which the first part reaches its limit, and the image sensor's two limits.

| case | every part inside its limit up to (first part there) | image sensor 85 C at | image sensor 60 C (best image) at | RV1106 Tj 125 C at |
|---|---|---|---|---|
| snapshot day, PS off | 67.4 C (USB-C receptacle USB4105 (J1)) | 68.1 C | 41.3 C | 85 C or more |
| snapshot night, PS off | 65.2 C (USB-C receptacle USB4105 (J1)) | 65.8 C | 38.9 C | 85 C or more |
| snapshot day, PS on | 70.6 C (W25N02KV flash (U5)) | 71.2 C | 44.7 C | 85 C or more |
| snapshot night, PS on | 68.5 C (W25N02KV flash (U5)) | 69.0 C | 42.2 C | 85 C or more |
| live view day | 53.6 C (SC4336H image sensor (U8)) | 53.6 C | 25.6 C | 85 C or more |
| live view night | 42.2 C (SC4336H image sensor (U8)) | 42.2 C | 13.3 C | 82.2 C |
| stress bound | -9.4 C (W25N02KV flash (U5)) | -5.4 C | never (not even at -20 C) | 30.0 C |

## Firmware rules (thermal governor)

The RV1106's TSADC reads its own junction (+-3 C). In a steady state every part sits at a fixed offset from it for a given load, so the junction temperature at the chamber where the first part reaches its rating is a threshold for that mode, less the sensor's 3 C error.

| mode | chamber limit (first part) | RV1106 Tj there (steady state) | rule: allowed while TSADC below | at 70 C the TSADC reads |
|---|---|---|---|---|
| snapshot day, PS off | 67.4 C (USB-C receptacle USB4105 (J1)) | 88 C | **85 C** | 90 C |
| snapshot night, PS off | 65.2 C (USB-C receptacle USB4105 (J1)) | 88 C | **85 C** | 92 C |
| snapshot day, PS on | 70.6 C (W25N02KV flash (U5)) | 88 C | **85 C** | 88 C |
| snapshot night, PS on | 68.5 C (W25N02KV flash (U5)) | 88 C | **85 C** | 90 C |
| live view day | 53.6 C (SC4336H image sensor (U8)) | 91 C | **88 C** | 106 C |
| live view night | 42.2 C (SC4336H image sensor (U8)) | 90 C | **87 C** | 114 C |

1. **Snapshot mode is the default**: CPU at its lowest OPP between shots, NPU off, sensor in standby.
2. **Live view** only while TSADC < 87 C; above it, back to snapshot mode ("live view paused: camera too warm").
3. TSADC > 85 C in snapshot mode: stretch the interval to 30 s, cap Wi-Fi TX power, shorten the IR flash.
4. TSADC > 110 C: stop capturing (keep Wi-Fi associated, report the fault); > 120 C power the sensor and Wi-Fi down; Linux critical trip at 125 C.

## The heatsink and the slots

snap_night at 70 C. The junction sends 0.23 W of its 0.49 W into the heatsink (junction to heatsink 12.0 K/W, against 4.1 K/W into the board); the heatsink at 87.8 C passes it on:

| path from the heatsink | conductance (W/K) | heat (W) |
|---|---|---|
| sides and fins to the air inside the case (1200 mm^2 of envelope at 11 W/m^2K, 3120 mm^2 of fin faces at 3) | 0.0226 | 0.116 |
| top across the 0.7 mm gap and 1.6 mm of lid into the lid patch (10.7 cm^2 outside, 0.0129 W/K into the rest of the lid) | 0.0085 | 0.092 |
| up the three slots' still air (2.3 mm) to the chamber | 0.0008 | 0.014 |
| radiation out through the slots | 0.0004 | 0.007 |
| exchange flow, in at the lowest slot and out at the highest (5.7 mm higher at a 45 deg tilt) through the fin channels | 0.0006 | 0.011 |
| the board under its overhang | 0.0089 | -0.009 |

**The slots are not a way out for much heat.** Three 2 x 20 mm openings 2.3 mm deep give the fins 0.0018 W/K to the chamber in all: a 2 mm slot is too narrow for air to circulate in it (Rayleigh number about 5 on its width), so it conducts like still air, and the stack-driven exchange between slots a few millimetres apart, through 1.9 mm fin channels, moves 610.5 mm^3/s. For comparison the whole case gives the chamber 0.165 W/K. The heatsink still helps, because it spreads the junction's heat into the back cavity and the lid: without it the junction is 99.1 C and the sensor 92.3 C (sensitivity above).

## Every part's rating against the chamber

From `src/parts.py` and docs/parts-check-2026-10-31.md. Flagged against snap_night (power save off): a part rated below 85 C, over its rating, or within 10 K of it.

| part | rated | snap_night at 70 C (C) | live night at 70 C (C) | flag (snapshot) |
|---|---|---|---|---|
| RV1106G3 | Tj 125, ambient -20..85 | 92 | 114 |  |
| RV1106G3 / EA3036C ambient (the air inside) | -20..85 / -40..85 | 83 | 95 | under 10 K margin |
| SC4336H image sensor | -30..85, best image to 60 | 89 | 109 | OVER its rating |
| ESP32-C6-MINI-1U-H4 | -40..105 | 91 | 110 |  |
| W25N02KVZEIR | -40..85 | 89 | 108 | OVER its rating |
| USB4105-GF-A USB-C | -40..85 | 89 | 107 | OVER its rating |
| KT-0603G status LED | -40..85 | 88 | 106 | OVER its rating |
| TLV62569, EA3036C (junction) | TJ -40..125 | 89 | 109 |  |
| TLV75528 | TJ -40..125 | 88 | 107 |  |
| DRV8210P | TA -40..125 | 88 | 106 |  |
| AO3400A | TJ -55..150 | 88 | 106 |  |
| crystals ECS 24 MHz, Abracon 32 kHz | -40..125 | 89 | 109 |  |
| Molex 53261 PicoBlade | -40..105 | 87 | 105 |  |
| USBLC6-2SC6, SMF6.0CA | TJ to 125 / 150 | 88 | 105 |  |
| VSMY3850X01 IR LED (junction while lit) | Tj 100 (base part), -40..105 (X01) | 95 | 115 | under 10 K margin |
| TEMT6000 | -40..100 | 90 | 109 |  |
| DFE252012F inductors | -40..125 | 89 | 109 |  |
| BLM15PD121 bead | -55..125 | 88 | 106 |  |
| 0402 / 1206 thick-film resistors | -55..155 (power derates above 70) | 90 | 109 |  |
| C0G / X7R capacitors | -55..125 | 90 | 109 |  |
| X7S capacitors (1uF) | -55..125 | 90 | 109 |  |
| X6S capacitors (2.2uF .. 22uF) | -55..105 | 90 | 109 |  |
| 3M 8810 tape (bought) | 100 long term (UNVERIFIED) | 89 | 108 |  |
| CLA219 IR-cut holder (bought) | not published (plastic, NdFeB magnet) | 89 | 109 | UNKNOWN rating: ask the maker |
| Towin CCL127028MPR lens (bought) | not published | 83 | 97 | UNKNOWN rating: ask the maker |
| light rods (bought) | -40..125 (Bivar, its PC pipes in general) | 86 | 102 |  |
| PC-CF case | HDT ~110 (ESTIMATED) | 77 | 84 |  |

## Model and assumptions

- Chamber 70 C, still air (no credit for the chamber fan); bed radiation 0.10 W on the front. The camera looks down about 45 deg below horizontal (ASSUMED; it sets how far apart in height the slots are).
- Case: Prusa's outside, outer hull 125.6 cm^2 (measured from the STLs); new inside with 2 mm walls, 91.8 cm^2 of inner wall, cavities 15.5 mm (back) and 12.3 mm (front) deep on average. PC carbon fibre at 0.30 W/mK through the wall and 0.45 along it: ESTIMATED from Stratasys' FDM PC (0.28 W/mK, ASTM E1952) and unfilled PC (0.20); no PC-CF filament data sheet found gives a value. The wall itself is not the bottleneck (sensitivity: 0.20-0.50). Emissivity 0.90 outside; natural convection 1.32 (dT/0.05 m)^0.25 plus linearised radiation.
- Inside: radiation board to wall with effective emissivity 0.75; still-air conduction across the cavities with Catton's enclosure correlation (Nu 1.19 / 1.00 back / front at snap_night); board edge to the wall across 0.5 mm of air; 0.0006 W/K at each M2 boss; the front face under the IR-cut holder's base at 50 % (the holder traps air). Board places: src/layout_main.py FIXED (no routed board yet).
- Copper coverage ESTIMATED: LayerCam v1's routed main board's figures (the Pro is not routed yet) (docs/lessons.md: simulate heat on the routed board; routing raised temperatures 15 K on Ridge 3). Rerun with `tools/kd python3 sim/thermal.py` once layercam-pro.kicad_pcb is routed.
- Heatsink: 20 x 20 x 15 mm aluminium, 2 mm base, 7 straight fins 1.2 mm thick (ASSUMED: a typical stock part; the listing is to be confirmed), black anodised (emissivity 0.85); envelope 11 W/m^2K and fin faces 3 W/m^2K to the inside (LayerCam v1's estimates); on 3M 8810 (0.25 mm, 0.6 W/mK) over the 12.3 mm package with 0.5 K/W of contacts; top 0.7 mm under a 1.6 mm lid. The exchange flow assumes the fins run across the slots (the favourable way); fins along the slots would block it, which the taped-slot row bounds.
- RV1106: die to exposed pad 3 K/W (ASSUMED) plus the computed via array; the datasheet theta-JB (12.5 K/W, JEDEC 2s2p) from the board at the package edge as the pessimistic reading; the higher is used.
- Above the board: TLV62569 psi-JB 40.6, TLV75528 64.8 K/W (TI); EA3036C 15, inductors 60, ESP32-C6 module 6, SC4336H die 15, IR LED junction 120 K/W: ASSUMED.
- Loads: sim/power.md (the RV1106's snapshot currents and the C6's duty cycles are ASSUMED; the C6's currents are Espressif's at 25 C). Model uncertainty about +-10 K. Measure the first board in a 70 C oven and rerun.

## Checks

- PASS snap_day: RV1106 junction (U1) 90.4 C against 125 C (Tj max (datasheet 4.1))
- PASS snap_day: internal air (RV1106 / EA3036C ambient) 81.3 C against 85 C (ambient operating max (RV1106 T3-2, EA3036C TA))
- PASS snap_day: 3M 8810 tape on the RV1106 87.3 C against 100 C (long-term 100 C (3M; UNVERIFIED: data sheet not read here))
- FAIL snap_day: SC4336H image sensor (U8) 86.8 C against 85 C (-30..85 C operating; best image to 60 C (SmartSens))
- PASS snap_day: ESP32-C6-MINI-1U-H4 (U6) 89.3 C against 105 C (-40..105 C, the -H4 grade (Espressif))
- FAIL snap_day: W25N02KV flash (U5) 87.3 C against 85 C (-40..85 C (Winbond))
- FAIL snap_day: USB-C receptacle USB4105 (J1) 87.4 C against 85 C (-40..85 C incl. rise (GCT))
- FAIL snap_day: status LED LED1 (KT-0603G) 85.7 C against 85 C (-40..85 C (KENTO))
- PASS snap_day: TLV62569 0.9 V (U2) junction 87.1 C against 125 C (TJ max (SLVSDG1C 6.3))
- PASS snap_day: TLV62569 Wi-Fi (U4) junction 86.6 C against 125 C (TJ max (SLVSDG1C 6.3))
- PASS snap_day: EA3036C junction (U3) 86.4 C against 125 C (TJ range (datasheet))
- PASS snap_day: TLV75528 sensor LDO junction (U9) 86.2 C against 125 C (TJ max (SBVS320D))
- PASS snap_day: inductor L1 (DFE252012F) 86.6 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_day: inductor L2 (DFE252012F) 85.6 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_day: inductor L3 (DFE252012F) 85.7 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_day: inductor L4 (DFE252012F) 85.9 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_day: inductor L5 (DFE252012F) 86.4 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_day: DRV8210P IR-cut driver (U7) 85.7 C against 125 C (TA -40..125 C (TI))
- PASS snap_day: X7S capacitors (1uF) under the SoC (B face) 87.5 C against 125 C (X7S: -55..125 C)
- PASS snap_day: X7S capacitors (1uF) at the bucks 86.5 C against 125 C (X7S: -55..125 C)
- PASS snap_day: X7S capacitors (1uF) at the sensor 86.7 C against 125 C (X7S: -55..125 C)
- PASS snap_day: X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) under the SoC (B face) 87.5 C against 105 C (X6S: -55..105 C)
- PASS snap_day: X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the bucks 86.5 C against 105 C (X6S: -55..105 C)
- PASS snap_day: X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the sensor 86.7 C against 105 C (X6S: -55..105 C)
- PASS snap_day: crystals Y1 (24 MHz) / Y2 (32 kHz) 87.2 C against 125 C (-40..125 C (ECS, Abracon))
- PASS snap_day: TEMT6000 light sensor (Q2) 87.5 C against 100 C (-40..100 C (Vishay))
- PASS snap_day: PicoBlade IR-cut lead socket (J3) 85.1 C against 105 C (-40..105 C (Molex))
- PASS snap_day: USBLC6 / SMF6.0CA (U10 / D1) 85.9 C against 125 C (TJ to 125 / 150 C)
- PASS snap_day: IR LEDs VSMY3850X01, junction while lit 87.3 C against 100 C (Tj 100 C (Vishay VSMY3850 rev 1.5; the X01 grade's own data sheet not read))
- PASS snap_day: IR LEDs VSMY3850X01, ambient 84.3 C against 105 C (-40..105 C, X01 grade (parts.py; the base part is rated 85 C))
- PASS snap_day: case wall (PC carbon fibre) 76.6 C against 110 C (softens near its HDT, ~110 C (PC; ESTIMATED))
- WARN snap_day: image sensor 86.8 C against its best-image 60 C
- PASS snap_day: RV1106 junction 90.4 C with 10 K margin (115 C)
- PASS snap_night: RV1106 junction (U1) 92.2 C against 125 C (Tj max (datasheet 4.1))
- PASS snap_night: internal air (RV1106 / EA3036C ambient) 82.6 C against 85 C (ambient operating max (RV1106 T3-2, EA3036C TA))
- PASS snap_night: 3M 8810 tape on the RV1106 89.1 C against 100 C (long-term 100 C (3M; UNVERIFIED: data sheet not read here))
- FAIL snap_night: SC4336H image sensor (U8) 88.8 C against 85 C (-30..85 C operating; best image to 60 C (SmartSens))
- PASS snap_night: ESP32-C6-MINI-1U-H4 (U6) 91.4 C against 105 C (-40..105 C, the -H4 grade (Espressif))
- FAIL snap_night: W25N02KV flash (U5) 89.3 C against 85 C (-40..85 C (Winbond))
- FAIL snap_night: USB-C receptacle USB4105 (J1) 89.4 C against 85 C (-40..85 C incl. rise (GCT))
- FAIL snap_night: status LED LED1 (KT-0603G) 87.8 C against 85 C (-40..85 C (KENTO))
- PASS snap_night: TLV62569 0.9 V (U2) junction 89.1 C against 125 C (TJ max (SLVSDG1C 6.3))
- PASS snap_night: TLV62569 Wi-Fi (U4) junction 88.7 C against 125 C (TJ max (SLVSDG1C 6.3))
- PASS snap_night: EA3036C junction (U3) 88.4 C against 125 C (TJ range (datasheet))
- PASS snap_night: TLV75528 sensor LDO junction (U9) 88.3 C against 125 C (TJ max (SBVS320D))
- PASS snap_night: inductor L1 (DFE252012F) 88.5 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_night: inductor L2 (DFE252012F) 87.6 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_night: inductor L3 (DFE252012F) 87.8 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_night: inductor L4 (DFE252012F) 87.9 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_night: inductor L5 (DFE252012F) 88.5 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_night: DRV8210P IR-cut driver (U7) 87.8 C against 125 C (TA -40..125 C (TI))
- PASS snap_night: X7S capacitors (1uF) under the SoC (B face) 89.5 C against 125 C (X7S: -55..125 C)
- PASS snap_night: X7S capacitors (1uF) at the bucks 88.5 C against 125 C (X7S: -55..125 C)
- PASS snap_night: X7S capacitors (1uF) at the sensor 88.7 C against 125 C (X7S: -55..125 C)
- PASS snap_night: X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) under the SoC (B face) 89.5 C against 105 C (X6S: -55..105 C)
- PASS snap_night: X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the bucks 88.5 C against 105 C (X6S: -55..105 C)
- PASS snap_night: X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the sensor 88.7 C against 105 C (X6S: -55..105 C)
- PASS snap_night: crystals Y1 (24 MHz) / Y2 (32 kHz) 89.3 C against 125 C (-40..125 C (ECS, Abracon))
- PASS snap_night: TEMT6000 light sensor (Q2) 89.5 C against 100 C (-40..100 C (Vishay))
- PASS snap_night: PicoBlade IR-cut lead socket (J3) 87.2 C against 105 C (-40..105 C (Molex))
- PASS snap_night: USBLC6 / SMF6.0CA (U10 / D1) 87.9 C against 125 C (TJ to 125 / 150 C)
- PASS snap_night: IR LEDs VSMY3850X01, junction while lit 95.1 C against 100 C (Tj 100 C (Vishay VSMY3850 rev 1.5; the X01 grade's own data sheet not read))
- PASS snap_night: IR LEDs VSMY3850X01, ambient 86.0 C against 105 C (-40..105 C, X01 grade (parts.py; the base part is rated 85 C))
- PASS snap_night: case wall (PC carbon fibre) 77.3 C against 110 C (softens near its HDT, ~110 C (PC; ESTIMATED))
- PASS snap_night: string resistor 0.110 W while lit against 0.193 W derated at 89 C
- WARN snap_night: image sensor 88.8 C against its best-image 60 C
- PASS snap_night: RV1106 junction 92.2 C with 10 K margin (115 C)
- PASS snap_day_ps: RV1106 junction (U1) 87.9 C against 125 C (Tj max (datasheet 4.1))
- PASS snap_day_ps: internal air (RV1106 / EA3036C ambient) 79.3 C against 85 C (ambient operating max (RV1106 T3-2, EA3036C TA))
- PASS snap_day_ps: 3M 8810 tape on the RV1106 84.9 C against 100 C (long-term 100 C (3M; UNVERIFIED: data sheet not read here))
- PASS snap_day_ps: SC4336H image sensor (U8) 83.8 C against 85 C (-30..85 C operating; best image to 60 C (SmartSens))
- PASS snap_day_ps: ESP32-C6-MINI-1U-H4 (U6) 84.8 C against 105 C (-40..105 C, the -H4 grade (Espressif))
- PASS snap_day_ps: W25N02KV flash (U5) 84.3 C against 85 C (-40..85 C (Winbond))
- PASS snap_day_ps: USB-C receptacle USB4105 (J1) 84.0 C against 85 C (-40..85 C incl. rise (GCT))
- PASS snap_day_ps: status LED LED1 (KT-0603G) 83.1 C against 85 C (-40..85 C (KENTO))
- PASS snap_day_ps: TLV62569 0.9 V (U2) junction 84.5 C against 125 C (TJ max (SLVSDG1C 6.3))
- PASS snap_day_ps: TLV62569 Wi-Fi (U4) junction 83.3 C against 125 C (TJ max (SLVSDG1C 6.3))
- PASS snap_day_ps: EA3036C junction (U3) 83.8 C against 125 C (TJ range (datasheet))
- PASS snap_day_ps: TLV75528 sensor LDO junction (U9) 83.2 C against 125 C (TJ max (SBVS320D))
- PASS snap_day_ps: inductor L1 (DFE252012F) 84.0 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_day_ps: inductor L2 (DFE252012F) 83.0 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_day_ps: inductor L3 (DFE252012F) 83.2 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_day_ps: inductor L4 (DFE252012F) 83.3 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_day_ps: inductor L5 (DFE252012F) 83.1 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_day_ps: DRV8210P IR-cut driver (U7) 83.1 C against 125 C (TA -40..125 C (TI))
- PASS snap_day_ps: X7S capacitors (1uF) under the SoC (B face) 84.8 C against 125 C (X7S: -55..125 C)
- PASS snap_day_ps: X7S capacitors (1uF) at the bucks 83.9 C against 125 C (X7S: -55..125 C)
- PASS snap_day_ps: X7S capacitors (1uF) at the sensor 83.6 C against 125 C (X7S: -55..125 C)
- PASS snap_day_ps: X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) under the SoC (B face) 84.8 C against 105 C (X6S: -55..105 C)
- PASS snap_day_ps: X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the bucks 83.9 C against 105 C (X6S: -55..105 C)
- PASS snap_day_ps: X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the sensor 83.6 C against 105 C (X6S: -55..105 C)
- PASS snap_day_ps: crystals Y1 (24 MHz) / Y2 (32 kHz) 84.2 C against 125 C (-40..125 C (ECS, Abracon))
- PASS snap_day_ps: TEMT6000 light sensor (Q2) 84.8 C against 100 C (-40..100 C (Vishay))
- PASS snap_day_ps: PicoBlade IR-cut lead socket (J3) 82.5 C against 105 C (-40..105 C (Molex))
- PASS snap_day_ps: USBLC6 / SMF6.0CA (U10 / D1) 82.7 C against 125 C (TJ to 125 / 150 C)
- PASS snap_day_ps: IR LEDs VSMY3850X01, junction while lit 84.3 C against 100 C (Tj 100 C (Vishay VSMY3850 rev 1.5; the X01 grade's own data sheet not read))
- PASS snap_day_ps: IR LEDs VSMY3850X01, ambient 81.8 C against 105 C (-40..105 C, X01 grade (parts.py; the base part is rated 85 C))
- PASS snap_day_ps: case wall (PC carbon fibre) 75.5 C against 110 C (softens near its HDT, ~110 C (PC; ESTIMATED))
- WARN snap_day_ps: image sensor 83.8 C against its best-image 60 C
- PASS snap_day_ps: RV1106 junction 87.9 C with 10 K margin (115 C)
- PASS snap_night_ps: RV1106 junction (U1) 89.7 C against 125 C (Tj max (datasheet 4.1))
- PASS snap_night_ps: internal air (RV1106 / EA3036C ambient) 80.7 C against 85 C (ambient operating max (RV1106 T3-2, EA3036C TA))
- PASS snap_night_ps: 3M 8810 tape on the RV1106 86.7 C against 100 C (long-term 100 C (3M; UNVERIFIED: data sheet not read here))
- FAIL snap_night_ps: SC4336H image sensor (U8) 85.9 C against 85 C (-30..85 C operating; best image to 60 C (SmartSens))
- PASS snap_night_ps: ESP32-C6-MINI-1U-H4 (U6) 86.9 C against 105 C (-40..105 C, the -H4 grade (Espressif))
- FAIL snap_night_ps: W25N02KV flash (U5) 86.4 C against 85 C (-40..85 C (Winbond))
- FAIL snap_night_ps: USB-C receptacle USB4105 (J1) 86.0 C against 85 C (-40..85 C incl. rise (GCT))
- FAIL snap_night_ps: status LED LED1 (KT-0603G) 85.2 C against 85 C (-40..85 C (KENTO))
- PASS snap_night_ps: TLV62569 0.9 V (U2) junction 86.5 C against 125 C (TJ max (SLVSDG1C 6.3))
- PASS snap_night_ps: TLV62569 Wi-Fi (U4) junction 85.4 C against 125 C (TJ max (SLVSDG1C 6.3))
- PASS snap_night_ps: EA3036C junction (U3) 85.8 C against 125 C (TJ range (datasheet))
- PASS snap_night_ps: TLV75528 sensor LDO junction (U9) 85.4 C against 125 C (TJ max (SBVS320D))
- PASS snap_night_ps: inductor L1 (DFE252012F) 86.0 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_night_ps: inductor L2 (DFE252012F) 85.1 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_night_ps: inductor L3 (DFE252012F) 85.3 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_night_ps: inductor L4 (DFE252012F) 85.4 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_night_ps: inductor L5 (DFE252012F) 85.2 C against 125 C (-40..125 C incl. self-heating (Murata))
- PASS snap_night_ps: DRV8210P IR-cut driver (U7) 85.2 C against 125 C (TA -40..125 C (TI))
- PASS snap_night_ps: X7S capacitors (1uF) under the SoC (B face) 86.8 C against 125 C (X7S: -55..125 C)
- PASS snap_night_ps: X7S capacitors (1uF) at the bucks 85.9 C against 125 C (X7S: -55..125 C)
- PASS snap_night_ps: X7S capacitors (1uF) at the sensor 85.7 C against 125 C (X7S: -55..125 C)
- PASS snap_night_ps: X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) under the SoC (B face) 86.8 C against 105 C (X6S: -55..105 C)
- PASS snap_night_ps: X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the bucks 85.9 C against 105 C (X6S: -55..105 C)
- PASS snap_night_ps: X6S capacitors (2.2uF, 4.7uF, 10uF, 22uF) at the sensor 85.7 C against 105 C (X6S: -55..105 C)
- PASS snap_night_ps: crystals Y1 (24 MHz) / Y2 (32 kHz) 86.3 C against 125 C (-40..125 C (ECS, Abracon))
- PASS snap_night_ps: TEMT6000 light sensor (Q2) 86.8 C against 100 C (-40..100 C (Vishay))
- PASS snap_night_ps: PicoBlade IR-cut lead socket (J3) 84.7 C against 105 C (-40..105 C (Molex))
- PASS snap_night_ps: USBLC6 / SMF6.0CA (U10 / D1) 84.8 C against 125 C (TJ to 125 / 150 C)
- PASS snap_night_ps: IR LEDs VSMY3850X01, junction while lit 92.2 C against 100 C (Tj 100 C (Vishay VSMY3850 rev 1.5; the X01 grade's own data sheet not read))
- PASS snap_night_ps: IR LEDs VSMY3850X01, ambient 83.6 C against 105 C (-40..105 C, X01 grade (parts.py; the base part is rated 85 C))
- PASS snap_night_ps: case wall (PC carbon fibre) 76.3 C against 110 C (softens near its HDT, ~110 C (PC; ESTIMATED))
- PASS snap_night_ps: string resistor 0.110 W while lit against 0.202 W derated at 86 C
- WARN snap_night_ps: image sensor 85.9 C against its best-image 60 C
- PASS snap_night_ps: RV1106 junction 89.7 C with 10 K margin (115 C)
- FAIL snap_day keeps every part inside its rating up to a 67.4 C chamber (requirement 70 C)
- FAIL snap_night keeps every part inside its rating up to a 65.2 C chamber (requirement 70 C)
- PASS snap_day_ps keeps every part inside its rating up to a 70.6 C chamber (requirement 70 C)
- FAIL snap_night_ps keeps every part inside its rating up to a 68.5 C chamber (requirement 70 C)
- WARN snapshot-mode margin -4.8 K at 70 C (power save off), against a model uncertainty of about +-10 K

**15 FAIL, 5 WARN**
