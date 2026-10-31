# LayerCam v1: power budget and regulators

Computed by `sim/power_budget.py` from `src/circuit.py` / `src/parts.py` (dividers, inductors, capacitors read from the netlist) and the datasheet figures in the script. Figures marked *assumed* have no datasheet behind them; they are listed under *Assumptions* with the reason for each value.

## Verdict

**PASS with WARNs.** In snapshot mode (the requirement) the camera averages 0.16 A by day and 0.20 A by night, 0.68 A during a night shot, all well inside the port's 1 A. Live view and the stress bound are reported only.

- VDD_0V9: 51k / 100k = 0.906 V (0.882-0.930) in 0.850-0.950.
- VCC_DDR: 127k / 100k = 1.362 V (1.320-1.405) in 1.283-1.450.
- VCC_1V8: 200k / 100k = 1.800 V (1.741-1.861) in 1.620-1.980.
- VCC_3V3: 100k / 23k = 3.255 V (3.138-3.375) in 3.000-3.465.
- VWIFI: 100k / 20k = 3.600 V (3.470-3.734) in 3.200-4.800.
- Regulators carry their worst loads with room (0.9 V 1.39 of 2 A; EA3036C channels at most 0.38 of 1 A; Wi-Fi 1.0 A peak of 2 A); every inductor peak is under 80 % of its saturation current.
- IR LED strings with 47 R: 55 mA nominal, 15-61 mA over the supply and VF spread; 0.174 W per resistor at the high corner while lit (lit 20 % of the time in snapshot mode; thermal.md checks its derating).
- The 1 u / 4.7 u / 10 u / 22 u capacitors are now Murata X7S / X6S (125 / 105 C). DC-bias fractions for them are assumed (SimSurfing not reachable); the 0.9 V rail's 42 uF effective is still past TI's tested range for the TLV62569: check its load step on the bench.
- Remaining WARNs: the stress bound against the 1 A port, the LED brightness spread (a constant-current sink would remove it), L1 / L5 saturating at the TLV62569's typical current limit, 91 uF on VSYS at hot plug.
- Not verified: every snapshot-mode current (ASSUMED, see the CASES comment: measure idle, shot and upload currents on the first board), the FPA252012D datasheet, Murata DC-bias curves, the loops with this much output capacitance.

## Loads per operating case

| case | 0.9 V | DDR 1.36 V | 1.8 V | 3.3 V | Wi-Fi 3.3 V | IR LEDs (VSYS) | VSYS current | VSYS power |
|---|---|---|---|---|---|---|---|---|
| snapshot, day: one still every 10 s, idle between (REQUIREMENT CASE) | 0.24 A | 0.06 A | 0.033 A | 0.065 A | 0.05 A | 0 mA | **0.16 A** | 0.81 W |
| snapshot, night: the same, IR LEDs on for 2 s of each 10 s (REQUIREMENT CASE) | 0.24 A | 0.06 A | 0.033 A | 0.065 A | 0.05 A | 33 mA | **0.20 A** | 0.98 W |
| snapshot, night, during a shot (seconds): streaming loads, Wi-Fi transmitting, LEDs on | 0.60 A | 0.12 A | 0.038 A | 0.148 A | 0.32 A | 164 mA | **0.68 A** | 3.40 W |
| live view, day: streaming 3 MP 30 fps, Wi-Fi average, IR LEDs off (reported only) | 0.60 A | 0.12 A | 0.038 A | 0.133 A | 0.12 A | 0 mA | **0.36 A** | 1.79 W |
| live view, night: the same with the six IR LEDs on at 100 % (reported only) | 0.60 A | 0.12 A | 0.038 A | 0.133 A | 0.12 A | 164 mA | **0.52 A** | 2.60 W |
| worst sustained (stress bound): SoC at the measured maximum +15 % hot leakage, DDR max, Wi-Fi transmitting continuously, IR LEDs on at the high-current corner | 1.39 A | 0.30 A | 0.048 A | 0.217 A | 0.40 A | 183 mA | **1.07 A** | 5.41 W |
| peak (milliseconds): worst plus a 1 A Wi-Fi burst and an IR-cut pulse | 1.39 A | 0.30 A | 0.048 A | 0.380 A | 1.00 A | 183 mA | **1.66 A** | 8.33 W |

VSYS current at 5.0 V in, regulator losses from the buck model below (switch and inductor resistance hot, 4 ns edges); the LED strings straight from VSYS.

## The 5 V source

Prusa's own camera on this port is rated "5 VDC 1 A" (Prusa product page): the printer's mainboard feeds it over the USB-C cable. LayerCam presents 5.1 k Rd on both CC lines and reads nothing back, so it must live within whatever the port gives without negotiation.

| case | VSYS current | against 1 A |
|---|---|---|
| snap_day | 0.16 A | within |
| snap_night | 0.20 A | within |
| snap_burst | 0.68 A | within |
| day | 0.36 A | within |
| night | 0.52 A | within |
| worst | 1.07 A | OVER by 7 % |
| peak | 1.66 A | OVER by 66 % |

## Each regulator

| rail | regulator | divider | Vout nom (corners) | allowed | load in a shot / worst | rating | L | ripple / peak (L -20 %, fsw min) | Isat | Irms rating | efficiency (worst) | C out effective |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| VDD_0V9 | TLV62569 U2 | 51k / 100k | 0.906 V (0.882-0.930) | 0.850-0.950 | 0.60 / 1.39 A (peak 1.39) | 2.0 A | DFE252012F-2R2M=P2 2.2 uH | 0.33 / 1.56 A | 3.0 A | 2.4 A | 75 % | 42 uF |
| VCC_DDR | EA3036C U3 CH2 | 127k / 100k | 1.362 V (1.320-1.405) | 1.283-1.450 | 0.12 / 0.30 A (peak 0.30) | 1.0 A | DFE252012F-1R5M=P2 1.5 uH | 0.83 / 0.71 A | 3.6 A | 2.9 A | 92 % | 29 uF |
| VCC_1V8 | EA3036C U3 CH3 | 200k / 100k | 1.800 V (1.741-1.861) | 1.620-1.980 | 0.04 / 0.05 A (peak 0.05) | 1.0 A | DFE252012F-1R5M=P2 1.5 uH | 0.98 / 0.54 A | 3.6 A | 2.9 A | 89 % | 13 uF |
| VCC_3V3 | EA3036C U3 CH1 | 100k / 23k | 3.255 V (3.138-3.375) | 3.000-3.465 | 0.15 / 0.22 A (peak 0.38) | 1.0 A | DFE252012F-1R5M=P2 1.5 uH | 0.99 / 0.87 A | 3.6 A | 2.9 A | 96 % | 30 uF |
| VWIFI | TLV62569 U4 | 100k / 20k | 3.600 V (3.470-3.734) | 3.200-4.800 | 0.32 / 0.40 A (peak 1.00) | 2.0 A | DFE252012F-2R2M=P2 2.2 uH | 0.47 / 1.23 A | 3.0 A | 2.4 A | 96 % | 20 uF |

The ripple and peak column is at the corner that maximises them: 5.25 V in, inductance -20 %, the switching frequency at its datasheet minimum (EA3036C 1.0 MHz; TLV62569 has none, 1.2 MHz assumed), at the larger of the worst sustained and peak loads. *C out effective* sums every ceramic on the rail at its bias and at 85 C (-15 %, X6S / X7S near 100 C).

### The two rails with little room

- **VDD_0V9**: 0.906 V nominal from 51k / 100k; lowest corner 0.882 V against the CPU's 0.85 V minimum, leaving 32 mV for ripple and load steps. A 0.5 A step (CPU or NPU waking) on 42 uF effective with an assumed 60 kHz loop crossover dips about 31 mV: the low corner then reaches 0.851 V.
  - with 49.9k on top: 0.899 V (0.876-0.924), -6 mV above 0.85 at the low corner less the step, 26 mV under the logic's 0.95 V at the high corner.
  - with 51.0k on top: 0.906 V (0.882-0.930), 1 mV above 0.85 at the low corner less the step, 20 mV under the logic's 0.95 V at the high corner.
- **VWIFI**: 3.600 V nominal (3.470-3.734); AMPAK guarantees full RF only from 3.2 V. A transmit burst (0.4 A to 1 A) on 20 uF effective dips about 78 mV: the low corner reaches 3.391 V.
  - with 20k in place of 22k at the bottom: 3.600 V (3.470-3.734), 191 mV of room above 3.2 V after the burst; VBAT may be anything to 4.8 V (it is a battery input), and VDDIO stays on the 3.3 V rail.

## Capacitors at their bias

| net | parts | nominal | effective at bias, 85 C | rating against the rail |
|---|---|---|---|---|
| VSYS | 1 x 100nF (16V X7R 0402), 8 x 10uF (10V X6S 0603), 1 x 1uF (10V X7S 0402) | 81.1 uF | 25.1 uF | 52 % of the lowest-rated part |
| VDD_0V9 | 6 x 100nF (16V X7R 0402), 3 x 10uF (10V X6S 0603), 3 x 1uF (10V X7S 0402), 1 x 22uF (6.3V X6S 0603) | 55.6 uF | 42.3 uF | 14 % of the lowest-rated part |
| VCC_DDR | 3 x 100nF (16V X7R 0402), 2 x 10uF (10V X6S 0603), 1 x 1uF (10V X7S 0402), 1 x 22uF (6.3V X6S 0603) | 43.3 uF | 29.5 uF | 22 % of the lowest-rated part |
| VCC_1V8 | 3 x 100nF (16V X7R 0402), 1 x 1uF (10V X7S 0402), 1 x 22uF (6.3V X6S 0603) | 23.3 uF | 13.2 uF | 29 % of the lowest-rated part |
| VCC_3V3 | 12 x 100nF (16V X7R 0402), 2 x 10uF (10V X6S 0603), 2 x 1uF (10V X7S 0402), 2 x 22uF (6.3V X6S 0603), 1 x 4.7uF (6.3V X6S 0402) | 71.9 uF | 29.7 uF | 53 % of the lowest-rated part |
| VWIFI | 1 x 100nF (16V X7R 0402), 3 x 22uF (6.3V X6S 0603) | 66.1 uF | 22.3 uF | 53 % of the lowest-rated part |

TI asks for 10-47 uF effective on the TLV62569 with 2.2 uH (its table 4: 2 x 22 uF the standard). The 0.9 V rail carries 42 uF effective, most of it the SoC's decoupling behind the plane: more than TI tested. With peak-current-mode control extra output capacitance lowers the crossover rather than destabilising it, but check it on the bench with a load step.

Hot plug: 91 uF nominal sits on VSYS (USB board 10 uF, main board 81 uF) with no inrush limit. USB 2.0 allows a device 10 uF at attach. The printer's port is the only source and the camera is normally plugged in with the printer off, so this is a WARN; a soft-start load switch on the main board would make it compliant.

## IR LED strings (ring board)

Three strings of two 850 nm LEDs, each through 47 ohm from VSYS, switched by Q1 (AO3400A) on LED_K. JNJ-LTJI0106W90: VF 1.4 V typ / 2.1 V max at 100 mA, 100 mA continuous, Tj 115 C max.

| corner | VSYS at the ring | VF each | string current | resistor power | per LED |
|---|---|---|---|---|---|
| nominal (5.0 V, typical VF, LEDs warm) | 4.98 V | 1.20 V | 54.7 mA | 0.141 W | 66 mW |
| high (5.25 V, typical VF hot, R -1 %) | 5.25 V | 1.20 V | 61.1 mA | 0.174 W | 74 mW |
| low (4.75 V, maximum VF cold, R +1 %) | 4.69 V | 2.00 V | 14.5 mA | 0.010 W | 29 mW |

The string current spans 15-61 mA (4.2 : 1) over the supply and VF spread: two LEDs take 2.4-4 V of a 4.7-5.25 V supply, so the resistor sees a small, very variable remainder.

| resistor | current high / nominal / low corner | resistor power, high corner |
|---|---|---|
| 39 R | 74 / 66 / 18 mA | 0.210 W |
| 47 R | 61 / 55 / 15 mA | 0.174 W |
| 56 R | 51 / 46 / 12 mA | 0.146 W |

## IR-cut filter

DRV8837 from 3.3 V into the 20 ohm coil: 163 mA for 100-500 ms per switch (0.53 W in the coil, 7 mW in the bridge), twice a day. The coil warms to about 23 ohm at 65 C (copper +0.39 %/K): 142 mA. The 3.3 V buck has room for it (counted in the peak case).

## Cables

- USB cable (SH, 1 A per contact): VSYS and ground on two contacts each, 1.07 A worst: 0.54 A a contact.
- LED ring cable: 183 mA on two contacts each way.

## Assumptions (no datasheet number behind them)

- RV1106 typical streaming core current 0.60 A (half the Core1106 maximum); DDR3L 0.12 A typical, 0.30 A max; +15 % core leakage when hot. Measure these on the first board (USB power meter plus the rail shunts).
- AP6256 average 0.12 A while streaming, 0.40 A transmitting continuously (AMPAK gives only the 1 A peak).
- SC3336 module 0.06-0.08 A from 3.3 V (SmartSens publishes no figure in the flyer).
- Capacitor DC-bias fractions (Samsung curves, read approximately), switch resistance x1.35 hot, 4 ns edges, TLV62569 fsw +-20 %, loop crossover 60 kHz for the droop estimates.
- 850 nm LED: VF 0.1 V lower at 55 mA than at 100 mA, -1.5 mV/K, 25 % of its power leaves as light.

## Checks

- PASS snap_day draws 0.16 A on average, under half the port's 1 A
- PASS snap_night draws 0.20 A on average, under half the port's 1 A
- PASS a night snapshot (seconds) draws 0.68 A, under 80 % of the port's 1 A
- PASS live view at night draws 0.52 A, under 80 % of the port's 1 A
- WARN worst sustained (stress bound) 1.07 A against the port's 1 A rating
- WARN millisecond peak 1.66 A (the 10 uF caps on VSYS carry the edge; the port must not trip)
- PASS VDD_0V9 set to 0.906 V (0.882-0.930 with VREF +-2 % and 1 % resistors) inside 0.850-0.950 (RV1106 CPU_DVDD 0.85-1.05, DVDD/PMU 0.81-0.95 (datasheet Rev 2.2 T3-2))
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
- PASS VCC_3V3 set to 3.255 V (3.138-3.375 with VREF +-2 % and 1 % resistors) inside 3.000-3.465 (VCCIO 3.0-3.465 (USB_AVDD to 3.6))
- PASS VCC_3V3 worst load 0.38 A within 70 % of EA3036C's 1.0 A
- PASS VCC_3V3 inductor peak 0.87 A (L -20 %, fsw min, 5.25 V in) under 80 % of its 3.6 A saturation
- PASS VCC_3V3 inductor RMS 0.48 A under 70 % of its 2.9 A rating (it runs in a 65 C+ housing)
- PASS VCC_3V3 peak 0.87 A under the EA3036C's 1.8 A minimum current limit
- PASS VWIFI set to 3.600 V (3.470-3.734 with VREF +-2 % and 1 % resistors) inside 3.200-4.800 (AP6256 VBAT 3.2-4.8 for full RF (datasheet note 1))
- PASS VWIFI worst load 1.00 A within 70 % of TLV62569's 2.0 A
- PASS VWIFI inductor peak 1.23 A (L -20 %, fsw min, 5.25 V in) under 80 % of its 3.0 A saturation
- PASS VWIFI inductor RMS 1.01 A under 70 % of its 2.4 A rating (it runs in a 65 C+ housing)
- WARN VWIFI inductor saturates at 3.0 A, against the TLV62569's 3.0 A typical switch limit (no maximum given): in a short or hard overload the inductor saturates before the limit acts
- PASS EA3036C total output 1.76 W at peak, under its 6 W limit
- PASS VDD_0V9 low corner minus a 0.5 A step droop (0.851 V) stays at or above the CPU's 0.85 V
- PASS VWIFI low corner minus a TX-burst droop (3.391 V) stays at or above 3.2 V
- PASS VSYS: every capacitor rated above the rail (worst 52 % of its rating)
- PASS VDD_0V9: every capacitor rated above the rail (worst 14 % of its rating)
- PASS VCC_DDR: every capacitor rated above the rail (worst 22 % of its rating)
- PASS VCC_1V8: every capacitor rated above the rail (worst 29 % of its rating)
- PASS VCC_3V3: every capacitor rated above the rail (worst 53 % of its rating)
- PASS VWIFI: every capacitor rated above the rail (worst 53 % of its rating)
- PASS VDD_0V9 output capacitance 42 uF effective inside TI's tested range for the TLV62569 (to about 53 uF)
- WARN VSYS capacitance at attach 91 uF against USB's 10 uF
- PASS LED current 61 mA at the high corner under the 100 mA rating
- WARN 47 R power 0.174 W at the high corner within half its 0.25 W (it derates above 70 C; thermal.py checks it at the ring's temperature)
- WARN IR brightness spread 4.2 : 1 between corners
- PASS IR-cut pulse 163 mA within the DRV8837's 1.8 A
- PASS SH contacts carry 0.54 A each (rated 1 A)

**no FAIL, 7 WARN**
