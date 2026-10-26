# LayerCam v1: power budget and regulators

Computed by `sim/power_budget.py` from `src/circuit.py` / `src/parts.py` (dividers, inductors, capacitors read from the netlist) and the datasheet figures in the script. Figures marked *assumed* have no datasheet behind them; they are listed under *Assumptions* with the reason for each value.

## Loads per operating case

| case | 0.9 V | DDR 1.36 V | 1.8 V | 3.3 V | Wi-Fi 3.3 V | IR LEDs (VSYS) | VSYS current | VSYS power |
|---|---|---|---|---|---|---|---|---|
| day: streaming 3 MP 30 fps, Wi-Fi average, IR LEDs off | 0.60 A | 0.12 A | 0.038 A | 0.133 A | 0.12 A | 0 mA | **0.35 A** | 1.75 W |
| night: the same with the six IR LEDs on at 100 % | 0.60 A | 0.12 A | 0.038 A | 0.133 A | 0.12 A | 198 mA | **0.55 A** | 2.73 W |
| worst sustained: SoC at the measured maximum +15 % hot leakage, DDR max, Wi-Fi transmitting continuously, IR LEDs on at the high-current corner | 1.39 A | 0.30 A | 0.048 A | 0.217 A | 0.40 A | 221 mA | **1.08 A** | 5.48 W |
| peak (milliseconds): worst plus a 1 A Wi-Fi burst and an IR-cut pulse | 1.39 A | 0.30 A | 0.048 A | 0.380 A | 1.00 A | 221 mA | **1.64 A** | 8.24 W |

VSYS current at 5.0 V in, regulator losses from the buck model below (switch and inductor resistance hot, 4 ns edges); the LED strings straight from VSYS.

## The 5 V source

Prusa's own camera on this port is rated "5 VDC 1 A" (Prusa product page): the printer's mainboard feeds it over the USB-C cable. LayerCam presents 5.1 k Rd on both CC lines and reads nothing back, so it must live within whatever the port gives without negotiation.

| case | VSYS current | against 1 A |
|---|---|---|
| day | 0.35 A | within |
| night | 0.55 A | within |
| worst | 1.08 A | OVER by 8 % |
| peak | 1.64 A | OVER by 64 % |

## Each regulator

| rail | regulator | divider | Vout nom (corners) | allowed | load typ / worst | rating | L | ripple / peak (L -20 %, fsw min) | Isat | Irms rating | efficiency (worst) | C out effective |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| VDD_0V9 | TLV62569 U2 | 47k / 100k | 0.882 V (0.859-0.905) | 0.850-0.950 | 0.60 / 1.39 A (peak 1.39) | 2.0 A | FPA252012D-2R2MT0 2.2 uH | 0.33 / 1.56 A | 3.0 A | 2.4 A | 75 % | 60 uF |
| VCC_DDR | EA3036C U3 CH2 | 127k / 100k | 1.362 V (1.320-1.405) | 1.283-1.450 | 0.12 / 0.30 A (peak 0.30) | 1.0 A | FPA252012D-1R5MT0 1.5 uH | 0.83 / 0.71 A | 3.6 A | 2.9 A | 92 % | 31 uF |
| VCC_1V8 | EA3036C U3 CH3 | 200k / 100k | 1.800 V (1.741-1.861) | 1.620-1.980 | 0.04 / 0.05 A (peak 0.05) | 1.0 A | FPA252012D-1R5MT0 1.5 uH | 0.98 / 0.54 A | 3.6 A | 2.9 A | 89 % | 14 uF |
| VCC_3V3 | EA3036C U3 CH1 | 100k / 22k | 3.327 V (3.208-3.450) | 3.000-3.465 | 0.13 / 0.22 A (peak 0.38) | 1.0 A | FPA252012D-1R5MT0 1.5 uH | 0.97 / 0.87 A | 3.6 A | 2.9 A | 97 % | 29 uF |
| VWIFI | TLV62569 U4 | 100k / 22k | 3.327 V (3.208-3.450) | 3.200-4.800 | 0.12 / 0.40 A (peak 1.00) | 2.0 A | FPA252012D-2R2MT0 2.2 uH | 0.52 / 1.26 A | 3.0 A | 2.4 A | 96 % | 25 uF |

The ripple and peak column is at the corner that maximises them: 5.25 V in, inductance -20 %, the switching frequency at its datasheet minimum (EA3036C 1.0 MHz; TLV62569 has none, 1.2 MHz assumed), at the larger of the worst sustained and peak loads. *C out effective* sums every ceramic on the rail at its bias and at 85 C (X5R -15 %).

### The two rails with little room

- **VDD_0V9**: 0.882 V nominal from 47k / 100k; lowest corner 0.859 V against the CPU's 0.85 V minimum, leaving 9 mV for ripple and load steps. A 0.5 A step (CPU or NPU waking) on 60 uF effective with an assumed 60 kHz loop crossover dips about 22 mV: the low corner then reaches 0.837 V.
  - with 49.9k on top: 0.899 V (0.876-0.924), 3 mV above 0.85 at the low corner less the step, 26 mV under the logic's 0.95 V at the high corner.
  - with 51.0k on top: 0.906 V (0.882-0.930), 10 mV above 0.85 at the low corner less the step, 20 mV under the logic's 0.95 V at the high corner.
- **VWIFI**: 3.327 V nominal (3.208-3.450); AMPAK guarantees full RF only from 3.2 V. A transmit burst (0.4 A to 1 A) on 25 uF effective dips about 63 mV: the low corner reaches 3.144 V.
  - with 20k in place of 22k at the bottom: 3.600 V (3.470-3.734), 206 mV of room above 3.2 V after the burst; VBAT may be anything to 4.8 V (it is a battery input), and VDDIO stays on the 3.3 V rail.

## Capacitors at their bias

| net | parts | nominal | effective at bias, 85 C | rating against the rail |
|---|---|---|---|---|
| VSYS | 1 x 100nF (16V X7R 0402), 8 x 10uF (10V X5R 0603), 1 x 1uF (25V X5R 0402) | 81.1 uF | 27.9 uF | 52 % of the lowest-rated part |
| VDD_0V9 | 6 x 100nF (16V X7R 0402), 3 x 10uF (10V X5R 0603), 3 x 1uF (25V X5R 0402), 2 x 22uF (6.3V X5R 0603) | 77.6 uF | 59.7 uF | 14 % of the lowest-rated part |
| VCC_DDR | 3 x 100nF (16V X7R 0402), 2 x 10uF (10V X5R 0603), 1 x 1uF (25V X5R 0402), 1 x 22uF (6.3V X5R 0603) | 43.3 uF | 30.5 uF | 22 % of the lowest-rated part |
| VCC_1V8 | 3 x 100nF (16V X7R 0402), 1 x 1uF (25V X5R 0402), 1 x 22uF (6.3V X5R 0603) | 23.3 uF | 14.2 uF | 29 % of the lowest-rated part |
| VCC_3V3 | 11 x 100nF (16V X7R 0402), 2 x 10uF (10V X5R 0603), 2 x 1uF (25V X5R 0402), 2 x 22uF (6.3V X5R 0603) | 67.1 uF | 29.3 uF | 53 % of the lowest-rated part |
| VWIFI | 1 x 100nF (16V X7R 0402), 3 x 22uF (6.3V X5R 0603) | 66.1 uF | 25.1 uF | 53 % of the lowest-rated part |

TI asks for 10-47 uF effective on the TLV62569 with 2.2 uH (its table 4: 2 x 22 uF the standard). The 0.9 V rail carries 60 uF effective, most of it the SoC's decoupling behind the plane: more than TI tested. With peak-current-mode control extra output capacitance lowers the crossover rather than destabilising it, but check it on the bench with a load step.

Hot plug: 91 uF nominal sits on VSYS (USB board 10 uF, main board 81 uF) with no inrush limit. USB 2.0 allows a device 10 uF at attach. The printer's port is the only source and the camera is normally plugged in with the printer off, so this is a WARN; a soft-start load switch on the main board would make it compliant.

## IR LED strings (ring board)

Three strings of two 850 nm LEDs, each through 39 ohm from VSYS, switched by Q1 (AO3400A) on LED_K. JNJ-LTJI0106W90: VF 1.4 V typ / 2.1 V max at 100 mA, 100 mA continuous, Tj 115 C max.

| corner | VSYS at the ring | VF each | string current | resistor power | per LED |
|---|---|---|---|---|---|
| nominal (5.0 V, typical VF, LEDs warm) | 4.98 V | 1.20 V | 65.9 mA | 0.169 W | 79 mW |
| high (5.25 V, typical VF hot, R -1 %) | 5.25 V | 1.20 V | 73.7 mA | 0.210 W | 89 mW |
| low (4.75 V, maximum VF cold, R +1 %) | 4.69 V | 2.00 V | 17.5 mA | 0.012 W | 35 mW |

The string current spans 18-74 mA (4.2 : 1) over the supply and VF spread: two LEDs take 2.4-4 V of a 4.7-5.25 V supply, so the resistor sees a small, very variable remainder.

| resistor | current high / nominal / low corner | resistor power, high corner |
|---|---|---|
| 39 R | 74 / 66 / 18 mA | 0.210 W |
| 47 R | 61 / 55 / 15 mA | 0.174 W |
| 56 R | 51 / 46 / 12 mA | 0.146 W |

## IR-cut filter

DRV8837 from 3.3 V into the 20 ohm coil: 163 mA for 100-500 ms per switch (0.53 W in the coil, 7 mW in the bridge), twice a day. The coil warms to about 23 ohm at 65 C (copper +0.39 %/K): 142 mA. The 3.3 V buck has room for it (counted in the peak case).

## Cables

- USB cable (SH, 1 A per contact): VSYS and ground on two contacts each, 1.08 A worst: 0.54 A a contact.
- LED ring cable: 221 mA on two contacts each way.

## Assumptions (no datasheet number behind them)

- RV1106 typical streaming core current 0.60 A (half the Core1106 maximum); DDR3L 0.12 A typical, 0.30 A max; +15 % core leakage when hot. Measure these on the first board (USB power meter plus the rail shunts).
- AP6256 average 0.12 A while streaming, 0.40 A transmitting continuously (AMPAK gives only the 1 A peak).
- SC3336 module 0.06-0.08 A from 3.3 V (SmartSens publishes no figure in the flyer).
- Capacitor DC-bias fractions (Samsung curves, read approximately), switch resistance x1.35 hot, 4 ns edges, TLV62569 fsw +-20 %, loop crossover 60 kHz for the droop estimates.
- 850 nm LED: VF 0.1 V lower at 55 mA than at 100 mA, -1.5 mV/K, 25 % of its power leaves as light.

## Checks

- PASS night streaming draws 0.55 A, under 80 % of the port's 1 A
- WARN worst sustained 1.08 A against the port's 1 A rating
- WARN millisecond peak 1.64 A (the 10 uF caps on VSYS carry the edge; the port must not trip)
- PASS VDD_0V9 set to 0.882 V (0.859-0.905 with VREF +-2 % and 1 % resistors) inside 0.850-0.950 (RV1106 CPU_DVDD 0.85-1.05, DVDD/PMU 0.81-0.95 (datasheet Rev 2.2 T3-2))
- PASS VDD_0V9 worst load 1.39 A within 70 % of TLV62569's 2.0 A
- PASS VDD_0V9 inductor peak 1.56 A (L -20 %, fsw min, 5.25 V in) under 80 % of its 3.0 A saturation
- PASS VDD_0V9 inductor RMS 1.39 A under 70 % of its 2.4 A rating (it runs in a 65 C+ housing)
- WARN VDD_0V9 inductor saturates at 3.0 A, against the TLV62569's 3.0 A typical switch limit (no maximum given): in a short or hard overload the inductor saturates before the limit acts
- PASS VCC_DDR set to 1.362 V (1.320-1.405 with VREF +-2 % and 1 % resistors) inside 1.283-1.450 (DDR3L VDDQ 1.283-1.45 (RV1106 T3-2))
- PASS VCC_DDR worst load 0.30 A within 70 % of EA3036C's 1.0 A
- PASS VCC_DDR inductor peak 0.71 A (L -20 %, fsw min, 5.25 V in) under 80 % of its 3.6 A saturation
- PASS VCC_DDR inductor RMS 0.38 A under 70 % of its 2.9 A rating (it runs in a 65 C+ housing)
- PASS VCC_DDR peak 0.71 A under the EA3036C's 1.8 A minimum current limit
- PASS VCC_1V8 set to 1.800 V (1.741-1.861 with VREF +-2 % and 1 % resistors) inside 1.620-1.980 (1.8 V domains 1.62-1.98)
- PASS VCC_1V8 worst load 0.05 A within 70 % of EA3036C's 1.0 A
- PASS VCC_1V8 inductor peak 0.54 A (L -20 %, fsw min, 5.25 V in) under 80 % of its 3.6 A saturation
- PASS VCC_1V8 inductor RMS 0.29 A under 70 % of its 2.9 A rating (it runs in a 65 C+ housing)
- PASS VCC_1V8 peak 0.54 A under the EA3036C's 1.8 A minimum current limit
- PASS VCC_3V3 set to 3.327 V (3.208-3.450 with VREF +-2 % and 1 % resistors) inside 3.000-3.465 (VCCIO 3.0-3.465 (USB_AVDD to 3.6))
- PASS VCC_3V3 worst load 0.38 A within 70 % of EA3036C's 1.0 A
- PASS VCC_3V3 inductor peak 0.87 A (L -20 %, fsw min, 5.25 V in) under 80 % of its 3.6 A saturation
- PASS VCC_3V3 inductor RMS 0.47 A under 70 % of its 2.9 A rating (it runs in a 65 C+ housing)
- PASS VCC_3V3 peak 0.87 A under the EA3036C's 1.8 A minimum current limit
- PASS VWIFI set to 3.327 V (3.208-3.450 with VREF +-2 % and 1 % resistors) inside 3.200-4.800 (AP6256 VBAT 3.2-4.8 for full RF (datasheet note 1))
- PASS VWIFI worst load 1.00 A within 70 % of TLV62569's 2.0 A
- PASS VWIFI inductor peak 1.26 A (L -20 %, fsw min, 5.25 V in) under 80 % of its 3.0 A saturation
- PASS VWIFI inductor RMS 1.01 A under 70 % of its 2.4 A rating (it runs in a 65 C+ housing)
- WARN VWIFI inductor saturates at 3.0 A, against the TLV62569's 3.0 A typical switch limit (no maximum given): in a short or hard overload the inductor saturates before the limit acts
- PASS EA3036C total output 1.76 W at peak, under its 6 W limit
- WARN VDD_0V9 low corner minus a 0.5 A step droop (0.837 V) stays at or above the CPU's 0.85 V
- WARN VWIFI low corner minus a TX-burst droop (3.144 V) stays at or above 3.2 V
- PASS VSYS: every capacitor rated above the rail (worst 52 % of its rating)
- PASS VDD_0V9: every capacitor rated above the rail (worst 14 % of its rating)
- PASS VCC_DDR: every capacitor rated above the rail (worst 22 % of its rating)
- PASS VCC_1V8: every capacitor rated above the rail (worst 29 % of its rating)
- PASS VCC_3V3: every capacitor rated above the rail (worst 53 % of its rating)
- PASS VWIFI: every capacitor rated above the rail (worst 53 % of its rating)
- WARN VDD_0V9 output capacitance 60 uF effective inside TI's tested range for the TLV62569 (to about 53 uF)
- WARN VSYS capacitance at attach 91 uF against USB's 10 uF
- PASS LED current 74 mA at the high corner under the 100 mA rating
- WARN 39 R power 0.210 W at the high corner within half its 0.25 W (it derates above 70 C; thermal.py checks it at the ring's temperature)
- WARN IR brightness spread 4.2 : 1 between corners
- PASS IR-cut pulse 163 mA within the DRV8837's 1.8 A
- PASS SH contacts carry 0.54 A each (rated 1 A)

**no FAIL, 10 WARN**
