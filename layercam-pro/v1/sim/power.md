# LayerCam Pro v1: power budget and regulators

Computed by `sim/power_budget.py` from `src/circuit.py` / `src/parts.py` (dividers, inductors, capacitors read from the netlist) and the datasheet figures in the script. Figures marked *assumed* have no datasheet behind them; they are listed under *Assumptions* with the reason for each value. LayerCam v1's budget (layercam/v1/sim/power.md) is the starting point: the RV1106 side is unchanged.

## Verdict

**PASS with WARNs.** In snapshot mode (the requirement) the camera averages 0.18 A by day and 0.21 A by night with the Wi-Fi's power save off (the C6 firmware built without tools/c6-power-save.sh) (0.15 / 0.18 A once it is on), 0.53 A during a night shot: all well inside the port's 1 A. Heat in the case in snapshot mode: 0.91 W by day, 1.03 W by night (power save off); 0.73 / 0.86 W with it on. Live view and the stress bound are reported only.

- **Wi-Fi power save off costs 169 mW** in snapshot mode (the C6 at 98 mA against 47 mA with it on): the C6 is then the second-largest heat source in the case after the RV1106.
- VDD_0V9: 51k / 100.0k = 0.906 V (0.882-0.930) in 0.850-0.950.
- VCC_DDR: 127k / 100.0k = 1.362 V (1.320-1.405) in 1.283-1.450.
- VCC_1V8: 200k / 100.0k = 1.800 V (1.741-1.861) in 1.700-1.900.
- VCC_3V3: 100k / 22.6k = 3.255 V (3.138-3.375) in 3.000-3.465.
- VWIFI: 100k / 22.6k = 3.255 V (3.138-3.375) in 3.000-3.600.
- Regulators carry their worst loads with room (0.9 V 1.39 of 2 A; EA3036C channels at most 0.31 of 1 A; Wi-Fi 0.50 A peak of 2 A); every inductor peak is under 80 % of its saturation current.
- IR LED strings with 47 R: 48 mA nominal, 21-55 mA over the supply and VF spread; 0.138 W per resistor at the high corner while lit (lit 20 % of the time in night snapshots; thermal.md checks its derating).
- Remaining WARNs: the stress bound against the 1 A port, the LED brightness spread (a constant-current sink would remove it), L1 / L5 saturating below the TLV62569's typical current limit, the VSYS capacitance at hot plug.
- Not verified: every snapshot-mode current (ASSUMED: measure idle, shot and upload currents on the first board, with power save off and on), the SC4336H's own currents, the Murata inductor Irms / DCR and DC-bias curves, the VSMY3850X01 grade's ratings.

## The Wi-Fi module (ESP32-C6-MINI-1U-H4)

Espressif's module datasheet v1.5 (3.3 V, 25 C) gives:

| state | current | source |
|---|---|---|
| TX 11b 20.5dBm (100 % duty) | 382 mA | table 6-4 |
| TX 11g 19dBm (100 % duty) | 316 mA | table 6-4 |
| TX HT20 MCS7 18dBm (100 % duty) | 295 mA | table 6-4 |
| TX HT40 MCS7 (100 % duty) | 280 mA | table 6-4 |
| TX HE MCS9 15.5dBm (100 % duty) | 251 mA | table 6-4 |
| RX / listen, HT20 or HE20 (CPU idle) | 78 mA | table 6-4 |
| modem-sleep, 160 MHz, CPU idle, peripheral clocks on | 28 mA | table 6-7 |
| light-sleep | 0.18 mA | table 6-8 |

**Power save is OFF** unless the C6's firmware is built with it on (`firmware/tools/c6-power-save.sh`, which the 65 C rating needs): esp-hosted gives Linux no way to turn it on, so the receiver listens all the time (88 mA: the RX figure plus an assumed 10 mA for esp-hosted's CPU and the SDIO link). In snapshot mode each 10 s carries one ~1 MB JPEG: 5 % TX airtime at 295 mA (HT20 MCS7, 18 dBm) and the radio on for 10 % of the time.

| C6 average | power save off (firmware built without the power-save step) | power save on (modem-sleep between DTIM beacons) |
|---|---|---|
| snapshot mode | **98 mA** (320 mW) | **47 mA** (151 mW) |
| live view (~4 Mbit/s up, 15 % TX) | 119 mA | the same (the radio is busy) |

Light-sleep (0.18 mA) would cut the floor further but stops the SDIO link, so it is not counted. LayerCam v1 assumed 50 mA for the AP6256 in power-save; the C6 with power save off draws about twice that.

## The image sensor (SC4336H) and its 2.8 V LDO

SmartSens gives the SC4336H as "< 120 mW at 30 fps"; the SC4336 family draws AVDD 20.9 mA (2.8 V) and DOVDD 50.1 mA (1.8 V) at 2-lane 30 fps (149 mW; a third-party summary of the SC4336 datasheet). The model streams at the SC4336H's 120 mW split in the SC4336's ratio and uses the SC4336 figures for the stress bound.

| state | AVDD (2.8 V, TLV75528 from 3.3 V) | DOVDD (1.8 V, 1R from VCC_1V8) | sensor | LDO |
|---|---|---|---|---|
| streaming 30 fps (SC4336H) | 16.8 mA | 40.3 mA | 120 mW | 7.6 mW |
| SC4336 figures (stress bound) | 20.9 mA | 50.1 mA | 149 mW | 9.5 mW |
| software standby (ASSUMED) | 1.0 mA | 2.0 mA | 6 mW | 0.5 mW |

The LDO drops 0.45 V (3.3 V rail nominal 3.255 V; TLV755P dropout about 0.2 V at 500 mA, far less at 21 mA): it regulates at the 3.3 V rail's low corner too.

## Loads per operating case

| case | 0.9 V | DDR 1.36 V | 1.8 V | 3.3 V | Wi-Fi 3.25 V | IR LEDs (VSYS) | VSYS current | VSYS power |
|---|---|---|---|---|---|---|---|---|
| snapshot, day, Wi-Fi power save OFF (firmware built without the power-save step): one still every 10 s, idle between (REQUIREMENT CASE) | 0.24 A | 0.06 A | 0.041 A | 0.048 A | 0.098 A | 0 mA | **0.18 A** | 0.92 W |
| snapshot, night, Wi-Fi power save OFF: the same, IR LEDs on for 2 s of each 10 s (REQUIREMENT CASE) | 0.24 A | 0.06 A | 0.041 A | 0.048 A | 0.098 A | 29 mA | **0.21 A** | 1.06 W |
| snapshot, day, Wi-Fi power save ON (once fixed) | 0.24 A | 0.06 A | 0.041 A | 0.048 A | 0.047 A | 0 mA | **0.15 A** | 0.75 W |
| snapshot, night, Wi-Fi power save ON (once fixed) | 0.24 A | 0.06 A | 0.041 A | 0.048 A | 0.047 A | 29 mA | **0.18 A** | 0.89 W |
| snapshot, night, during a shot (seconds): streaming loads, Wi-Fi uploading, LEDs on | 0.60 A | 0.12 A | 0.078 A | 0.098 A | 0.192 A | 145 mA | **0.53 A** | 2.67 W |
| live view, day: streaming 2560 x 1440 at 30 fps, Wi-Fi average, IR LEDs off (reported only) | 0.60 A | 0.12 A | 0.078 A | 0.083 A | 0.119 A | 0 mA | **0.33 A** | 1.65 W |
| live view, night: the same with the six IR LEDs on at 100 % (reported only) | 0.60 A | 0.12 A | 0.078 A | 0.083 A | 0.119 A | 145 mA | **0.48 A** | 2.38 W |
| worst sustained (stress bound): SoC at the measured maximum +15 % hot leakage, DDR max, Wi-Fi transmitting continuously at 20.5 dBm, sensor at the SC4336 figures, IR LEDs on at the high-current corner | 1.39 A | 0.30 A | 0.098 A | 0.151 A | 0.392 A | 164 mA | **1.00 A** | 5.02 W |
| peak (milliseconds): worst plus the C6's 0.5 A supply peak and an IR-cut pulse | 1.39 A | 0.30 A | 0.098 A | 0.308 A | 0.500 A | 164 mA | **1.18 A** | 5.93 W |

VSYS current at 5.0 V in, regulator losses from the buck model below (switch and inductor resistance hot, 4 ns edges); the LED strings straight from VSYS. All of the input power is heat inside the case except the light the LEDs emit and the Wi-Fi's radiated power.

| case | heat in the case | the largest parts |
|---|---|---|
| snap_day | 0.91 W | U1 0.49, U6 0.32, U3 0.03, U8 0.02, U2 0.02 |
| snap_night | 1.03 W | U1 0.49, U6 0.32, U3 0.03, U8 0.02, R90 0.02 |
| snap_day_ps | 0.73 W | U1 0.49, U6 0.15, U3 0.03, U8 0.02, U2 0.02 |
| snap_night_ps | 0.86 W | U1 0.49, U6 0.15, U3 0.03, U8 0.02, R90 0.02 |
| snap_burst | 2.53 W | U1 0.97, U6 0.59, U8 0.12, R90 0.11, R91 0.11 |
| day | 1.64 W | U1 0.97, U6 0.38, U8 0.12, U2 0.06, L1 0.04 |
| night | 2.26 W | U1 0.97, U6 0.38, U8 0.12, R90 0.11, R91 0.11 |
| worst | 4.87 W | U1 2.06, U6 1.21, U2 0.23, L1 0.20, U8 0.15 |
| peak | 5.31 W | U1 2.06, U6 1.56, U2 0.23, L1 0.20, U8 0.15 |

## The 5 V source

Prusa's own camera on this port is rated "5 VDC 1 A" (Prusa product page): the printer's mainboard feeds it over the USB-C cable. The camera presents 5.1 k Rd on both CC lines and reads nothing back, so it must live within whatever the port gives without negotiation.

| case | VSYS current | against 1 A |
|---|---|---|
| snap_day | 0.18 A | within |
| snap_night | 0.21 A | within |
| snap_day_ps | 0.15 A | within |
| snap_night_ps | 0.18 A | within |
| snap_burst | 0.53 A | within |
| day | 0.33 A | within |
| night | 0.48 A | within |
| worst | 1.00 A | within |
| peak | 1.18 A | OVER by 18 % |

## Each regulator

| rail | regulator | divider | Vout nom (corners) | allowed | load in a shot / worst | rating | L | ripple / peak (L -20 %, fsw min) | Isat | Irms rating | efficiency (worst) | C out effective |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| VDD_0V9 | TLV62569 U2 | 51k / 100.0k | 0.906 V (0.882-0.930) | 0.850-0.950 | 0.60 / 1.39 A (peak 1.39) | 2.0 A | DFE252012F-2R2M=P2 2.2 uH | 0.33 / 1.56 A | 2.3 A | 2.0 A | 75 % | 42 uF |
| VCC_DDR | EA3036C U3 CH2 | 127k / 100.0k | 1.362 V (1.320-1.405) | 1.283-1.450 | 0.12 / 0.30 A (peak 0.30) | 1.0 A | DFE252012F-1R5M=P2 1.5 uH | 0.83 / 0.71 A | 2.7 A | 2.4 A | 92 % | 29 uF |
| VCC_1V8 | EA3036C U3 CH3 | 200k / 100.0k | 1.800 V (1.741-1.861) | 1.700-1.900 | 0.08 / 0.10 A (peak 0.10) | 1.0 A | DFE252012F-1R5M=P2 1.5 uH | 0.98 / 0.59 A | 2.7 A | 2.4 A | 93 % | 13 uF |
| VCC_3V3 | EA3036C U3 CH1 | 100k / 22.6k | 3.255 V (3.138-3.375) | 3.000-3.465 | 0.10 / 0.15 A (peak 0.31) | 1.0 A | DFE252012F-1R5M=P2 1.5 uH | 1.00 / 0.81 A | 2.7 A | 2.4 A | 96 % | 23 uF |
| VWIFI | TLV62569 U4 | 100k / 22.6k | 3.255 V (3.138-3.375) | 3.000-3.600 | 0.19 / 0.39 A (peak 0.50) | 2.0 A | DFE252012F-2R2M=P2 2.2 uH | 0.56 / 0.78 A | 2.3 A | 2.0 A | 96 % | 23 uF |

The ripple and peak column is at the corner that maximises them: 5.25 V in, inductance -20 %, the switching frequency at its datasheet minimum (EA3036C 1.0 MHz; TLV62569 has none, 1.2 MHz assumed), at the larger of the worst sustained and peak loads. *C out effective* sums every ceramic on the rail at its bias and at 85 C (-15 %, X6S / X7S near 100 C). The inductors are Murata DFE252012F: saturation current from parts.py; the Irms rating and DCR are typical values (ASSUMED).

### The two rails with little room

- **VDD_0V9**: 0.906 V nominal from 51k / 100k; lowest corner 0.882 V against the CPU's 0.85 V minimum, leaving 32 mV for ripple and load steps. A 0.5 A step (CPU or NPU waking) on 42 uF effective with an assumed 60 kHz loop crossover dips about 31 mV: the low corner then reaches 0.851 V.
- **VWIFI**: 3.255 V nominal (3.138-3.375) from 100k / 22.6k, inside the C6's 3.0-3.6 V with 225 mV under its 3.6 V absolute maximum at the high corner (LayerCam v1's 3.60 V would have sat on it). A transmit burst (88 mA listening to the 0.5 A supply peak) on 23 uF effective dips about 48 mV: the low corner reaches 3.091 V.

## Capacitors at their bias

| net | parts | nominal | effective at bias, 85 C | rating against the rail |
|---|---|---|---|---|
| VSYS | 2 x 100nF (16V X7R 0402), 9 x 10uF (10V X6S 0603), 1 x 1uF (10V X7S 0402) | 91.2 uF | 28.3 uF | 52 % of the lowest-rated part |
| VDD_0V9 | 6 x 100nF (16V X7R 0402), 3 x 10uF (10V X6S 0603), 3 x 1uF (10V X7S 0402), 1 x 22uF (6.3V X6S 0603) | 55.6 uF | 42.3 uF | 14 % of the lowest-rated part |
| VCC_DDR | 3 x 100nF (16V X7R 0402), 2 x 10uF (10V X6S 0603), 1 x 1uF (10V X7S 0402), 1 x 22uF (6.3V X6S 0603) | 43.3 uF | 29.5 uF | 22 % of the lowest-rated part |
| VCC_1V8 | 3 x 100nF (16V X7R 0402), 1 x 1uF (10V X7S 0402), 1 x 22uF (6.3V X6S 0603) | 23.3 uF | 13.2 uF | 29 % of the lowest-rated part |
| VCC_3V3 | 9 x 100nF (16V X7R 0402), 1 x 10uF (10V X6S 0603), 3 x 1uF (10V X7S 0402), 2 x 22uF (6.3V X6S 0603) | 57.9 uF | 22.3 uF | 53 % of the lowest-rated part |
| VWIFI | 1 x 100nF (16V X7R 0402), 3 x 22uF (6.3V X6S 0603) | 66.1 uF | 22.3 uF | 53 % of the lowest-rated part |
| CAM_AVDD | 2 x 100nF (16V X7R 0402), 2 x 1uF (10V X7S 0402) | 2.2 uF | 1.6 uF | 28 % of the lowest-rated part |
| CAM_DOVDD | 1 x 100nF (16V X7R 0402), 1 x 1uF (10V X7S 0402) | 1.1 uF | 0.8 uF | 18 % of the lowest-rated part |

TI asks for 10-47 uF effective on the TLV62569 with 2.2 uH (its table 4: 2 x 22 uF the standard). The 0.9 V rail carries 42 uF effective, most of it the SoC's decoupling behind the plane. With peak-current-mode control extra output capacitance lowers the crossover rather than destabilising it, but check it on the bench with a load step. The TLV75528 needs 1 uF in (and >= 0.47 uF effective out, at most 200 uF): 1.6 uF at its output net.

Hot plug: 91 uF nominal sits on VSYS with no inrush limit. USB 2.0 allows a device 10 uF at attach. The printer's port is the only source and the camera is normally plugged in with the printer off, so this is a WARN; a soft-start load switch would make it compliant.

## IR LED strings (on the board's front face)

Three strings of two 850 nm VSMY3850X01 LEDs, each through 47 ohm (1206) from VSYS, switched by Q1 (AO3400A) on LED_K, lit only while a night frame is taken. Vishay VSMY3850: VF 1.6 V typ / 2.0 V max at 100 mA, 100 mA continuous; the base part's datasheet (doc 83399 rev 1.5) rates Tj 100 C and ambient -40..85 C; parts.py gives the X01 grade -40..105 C (its datasheet was not read: confirm).

| corner | VSYS | VF each | string current | resistor power | per LED |
|---|---|---|---|---|---|
| nominal (5.0 V, typical VF, LEDs warm) | 4.98 V | 1.36 V | 48.4 mA | 0.110 W | 66 mW |
| high (5.25 V, typical VF hot, R -1 %) | 5.25 V | 1.36 V | 54.6 mA | 0.138 W | 74 mW |
| low (4.75 V, maximum VF cold, R +1 %) | 4.71 V | 1.85 V | 21.3 mA | 0.021 W | 39 mW |

The string current spans 21-55 mA (2.6 : 1) over the supply and VF spread: two LEDs take 2.6-3.7 V of a 4.7-5.25 V supply, so the resistor sees a small, very variable remainder.

| resistor | current high / nominal / low corner | resistor power, high corner |
|---|---|---|
| 39 R | 66 / 58 / 26 mA | 0.167 W |
| 47 R | 55 / 48 / 21 mA | 0.138 W |
| 56 R | 46 / 41 / 18 mA | 0.116 W |

## IR-cut filter

DRV8210P from 3.3 V into the 20 ohm coil: 157 mA for 100-500 ms per switch (0.49 W in the coil, 26 mW in the bridge, HS + LS 1.05 ohm), twice a day. The coil warms to about 23.5 ohm at 85 C (copper +0.39 %/K): 134 mA. The 3.3 V buck has room for it (counted in the peak case).

## USB-C

- USB4105-GF-A: VBUS and ground on two contacts each (A4B9 / B4A9, A1B12 / B1A12), 1.00 A worst sustained: 0.50 A a contact; USB 2.0 type-C contacts carry 3 A by the USB-C specification.

## Assumptions (no datasheet number behind them)

- RV1106 typical streaming core current 0.60 A (half the Core1106 maximum); DDR3L 0.12 A typical, 0.30 A max; +15 % core leakage when hot; snapshot idle 0.18 A core, 0.05 A DDR. Measure these on the first board (USB power meter plus the rail shunts).
- ESP32-C6: 10 mA for esp-hosted's CPU and SDIO on top of Espressif's RX figure; 5 % TX airtime at HT20 MCS7 and 10 % radio-on per 10 s in snapshot mode; DTIM beacons 4 % awake with power save on; 15 % TX in live view. Espressif's figures are at 3.3 V and 25 C; at 3.25 V and 90 C the RF currents are similar, the sleep floors higher.
- SC4336H: streaming split of its 120 mW in the SC4336's AVDD / DOVDD ratio; standby 1 mA + 2 mA. The SC4336 currents are from a third-party summary of its datasheet (the SC4336H datasheet is under NDA).
- Inductor Irms ratings and DCR (Murata pages not reachable); capacitor DC-bias fractions; switch resistance x1.35 hot, 4 ns edges, TLV62569 fsw +-20 %, loop crossover 60 kHz for the droop estimates; USB-C contacts and board copper 0.04 ohm round trip.
- 850 nm LED: VF 0.15 V lower at 45 mA than at 100 mA, -1.45 mV/K (Vishay), 27 % of its power leaves as light.

## Checks

- PASS sensor LDO headroom 0.34 V at the 3.3 V rail's low corner (TLV75528 needs about 0.05 V at 21 mA)
- PASS snap_day draws 0.18 A on average, under half the port's 1 A
- PASS snap_night draws 0.21 A on average, under half the port's 1 A
- PASS snap_day_ps draws 0.15 A on average, under half the port's 1 A
- PASS snap_night_ps draws 0.18 A on average, under half the port's 1 A
- PASS a night snapshot (seconds) draws 0.53 A, under 80 % of the port's 1 A
- PASS live view at night draws 0.48 A, under 80 % of the port's 1 A
- PASS worst sustained (stress bound) 1.00 A against the port's 1 A rating
- PASS millisecond peak 1.18 A (the 10 uF caps on VSYS carry the edge; the port must not trip)
- PASS VDD_0V9 set to 0.906 V (0.882-0.930 with VREF +-2 % and 1 % resistors) inside 0.850-0.950 (RV1106 CPU_DVDD 0.85-1.05, DVDD/PMU 0.81-0.95 (datasheet Rev 2.2 T3-2))
- PASS VDD_0V9 worst load 1.39 A within 70 % of TLV62569's 2.0 A
- PASS VDD_0V9 inductor peak 1.56 A (L -20 %, fsw min, 5.25 V in) under 80 % of its 2.3 A saturation
- PASS VDD_0V9 inductor RMS 1.39 A under 70 % of its 2.0 A rating (ASSUMED; it runs in a 70 C+ case)
- WARN VDD_0V9 inductor saturates at 2.3 A, against the TLV62569's 3.0 A typical switch limit (no maximum given): in a short or hard overload the inductor saturates before the limit acts
- PASS VCC_DDR set to 1.362 V (1.320-1.405 with VREF +-2 % and 1 % resistors) inside 1.283-1.450 (DDR3L VDDQ 1.283-1.45 (RV1106 T3-2))
- PASS VCC_DDR worst load 0.30 A within 70 % of EA3036C's 1.0 A
- PASS VCC_DDR inductor peak 0.71 A (L -20 %, fsw min, 5.25 V in) under 80 % of its 2.7 A saturation
- PASS VCC_DDR inductor RMS 0.38 A under 70 % of its 2.4 A rating (ASSUMED; it runs in a 70 C+ case)
- PASS VCC_DDR peak 0.71 A under the EA3036C's 1.8 A minimum current limit
- PASS VCC_1V8 set to 1.800 V (1.741-1.861 with VREF +-2 % and 1 % resistors) inside 1.700-1.900 (1.8 V domains 1.62-1.98; the sensor's DOVDD 1.8 +-0.1 V (SmartSens))
- PASS VCC_1V8 worst load 0.10 A within 70 % of EA3036C's 1.0 A
- PASS VCC_1V8 inductor peak 0.59 A (L -20 %, fsw min, 5.25 V in) under 80 % of its 2.7 A saturation
- PASS VCC_1V8 inductor RMS 0.30 A under 70 % of its 2.4 A rating (ASSUMED; it runs in a 70 C+ case)
- PASS VCC_1V8 peak 0.59 A under the EA3036C's 1.8 A minimum current limit
- PASS VCC_3V3 set to 3.255 V (3.138-3.375 with VREF +-2 % and 1 % resistors) inside 3.000-3.465 (VCCIO 3.0-3.465 (USB_AVDD to 3.6))
- PASS VCC_3V3 worst load 0.31 A within 70 % of EA3036C's 1.0 A
- PASS VCC_3V3 inductor peak 0.81 A (L -20 %, fsw min, 5.25 V in) under 80 % of its 2.7 A saturation
- PASS VCC_3V3 inductor RMS 0.42 A under 70 % of its 2.4 A rating (ASSUMED; it runs in a 70 C+ case)
- PASS VCC_3V3 peak 0.81 A under the EA3036C's 1.8 A minimum current limit
- PASS VWIFI set to 3.255 V (3.138-3.375 with VREF +-2 % and 1 % resistors) inside 3.000-3.600 (ESP32-C6-MINI-1U VDD33 3.0-3.6 V (datasheet v1.5 table 6-2; 3.6 V is also its absolute maximum, table 6-1))
- PASS VWIFI worst load 0.50 A within 70 % of TLV62569's 2.0 A
- PASS VWIFI inductor peak 0.78 A (L -20 %, fsw min, 5.25 V in) under 80 % of its 2.3 A saturation
- PASS VWIFI inductor RMS 0.53 A under 70 % of its 2.0 A rating (ASSUMED; it runs in a 70 C+ case)
- WARN VWIFI inductor saturates at 2.3 A, against the TLV62569's 3.0 A typical switch limit (no maximum given): in a short or hard overload the inductor saturates before the limit acts
- PASS EA3036C total output 1.59 W at peak, under its 6 W limit
- PASS VDD_0V9 low corner minus a 0.5 A step droop (0.851 V) stays at or above the CPU's 0.85 V
- PASS VWIFI low corner minus a TX-burst droop (3.091 V) stays at or above the C6's 3.0 V
- PASS VWIFI within 0.1 V of VCC_3V3 (the C6's I/O runs at its supply and meets the SoC's 3.3 V pins directly)
- PASS VSYS: every capacitor rated above the rail (worst 52 % of its rating)
- PASS VDD_0V9: every capacitor rated above the rail (worst 14 % of its rating)
- PASS VCC_DDR: every capacitor rated above the rail (worst 22 % of its rating)
- PASS VCC_1V8: every capacitor rated above the rail (worst 29 % of its rating)
- PASS VCC_3V3: every capacitor rated above the rail (worst 53 % of its rating)
- PASS VWIFI: every capacitor rated above the rail (worst 53 % of its rating)
- PASS CAM_AVDD: every capacitor rated above the rail (worst 28 % of its rating)
- PASS CAM_DOVDD: every capacitor rated above the rail (worst 18 % of its rating)
- PASS VDD_0V9 output capacitance 42 uF effective inside TI's tested range for the TLV62569 (to about 53 uF)
- PASS TLV75528 output 1.6 uF effective, at least the 0.47 uF TI asks for
- WARN VSYS capacitance at attach 91 uF against USB's 10 uF
- PASS LED current 55 mA at the high corner under the 100 mA rating
- WARN 47 R power 0.138 W at the high corner within half its 0.25 W (it derates above 70 C; thermal.py checks it at the board's temperature)
- WARN IR brightness spread 2.6 : 1 between corners
- PASS IR-cut pulse 157 mA well within the DRV8210P's current limit
- PASS USB-C contacts carry 0.50 A each

**no FAIL, 5 WARN**
