# Print Hub v1: power chain

Computed by `sim/power_budget.py` from the part values and datasheet figures in it.

## 5 V rail (SY8368A buck)

| | value |
|---|---|
| output, nominal | 5.160 V |
| output, tolerance corners | 4.994 .. 5.331 V |
| at the highest corner, above the switch's 5.25 V minimum clamp | 0.08 V: 0.12 W more in the switch at 1.5 A |
| 9 V in, 5 A, nominal L: ripple current / peak | 1.25 A / 5.63 A |
| 9 V in, 5 A, L -20 %: ripple current / peak | 1.56 A / 5.78 A |
| 9 V in: output ripple (buck caps only) / input ripple | 4.6 mV / 102 mV |
| 12 V in, 5 A, nominal L: ripple current / peak | 1.67 A / 5.84 A |
| 12 V in, 5 A, L -20 %: ripple current / peak | 2.09 A / 6.04 A |
| 12 V in: output ripple (buck caps only) / input ripple | 6.2 mV / 102 mV |
| 9 V, 5 A: buck loss / inductor loss | 0.75 W / 0.38 W |
| 9 V, 5 A: efficiency (the firmware budgets 90 %) | 95.8 % |
| 9 V, 5 A: buck junction at 45 C air | 68 C (rated 125 C) |

## Each port

| | at 1.0 A | at 1.5 A | at the switch's limit (2.2 A max) |
|---|---|---|---|
| voltage at the USB-A, worst case (low rail, hot switch) | 4.87 V | 4.81 V | 4.73 V |
| switch dissipation, hot | 0.09 W | 0.20 W | 0.44 W |
| switch junction at 45 C air (with the clamp's 0.12 W) | | | 82 C (thermal shutdown 135-155 C) |
| shunt dissipation at the limit | | | 0.10 W (rated 1 W) |

A dead short on a port: the switch holds it to 2.20 A at most and cycles on its thermal shutdown, and its FAULT line (8 ms deglitch) makes the firmware switch the port off. The rail sees at most 2.2 A from that port, inside the buck's 5 A with the others running (see `sim/port_events.py` for the first microseconds).

## Current measurement

| | value |
|---|---|
| scale | 1.00 V per A |
| reading at the switch's highest limit | 2.22 V (ADC range 3.1 V; amplifier supply 3.3 V) |
| amplifier offset as current | 7.5 mA max |
| error at 0.5 A / 1.5 A | +-22 mA / +-52 mA |
| software limit, per port | 1.5 A at most: the USB-A receptacle's rating (1.5 A per contact) |

## Logic supply

| | value |
|---|---|
| from the print server's USB alone, worst case | 4.30 V into the LDO, needs 3.55 V |
| from the 5 V rail | 4.54 V into the LDO |
| WS2812B LED supply (3.3-5.3 V) | 4.30 .. 5.03 V |

## Charger budget (what the firmware allows, firmware/src/board.cpp)

| charger | contract | ports may draw |
|---|---|---|
| 20 W | 9 V 2.00 A | 2.7 A |
| 20 W, full 9 V offer | 9 V 2.22 A | 3.0 A |
| 30 W | 9 V 3.00 A | 4.1 A |
| 45 W and up | 9 V 3.00 A | 4.1 A |
| 5 V only (no USB-PD) | 5 V 3.00 A | nothing: ports stay off |

Typical load (fan 0.45 A, light 0.6 A, two filters charging 0.8 A each, spare 1 A): 3.65 A. A 30 W charger covers it; a 20 W one covers everything but the spare while both filters charge.

## Checks

- PASS rail above the switch's minimum output clamp by at most 0.08 V: 0.12 W more in the switch (harmless)
- PASS inductor peak 5.63 A under 80 % of saturation at 9 V, nominal L
- PASS valley current limit (8 A) above the 5 A load at 9 V, nominal L
- PASS inductor peak 5.78 A under 80 % of saturation at 9 V, L -20 %
- PASS valley current limit (8 A) above the 5 A load at 9 V, L -20 %
- PASS output ripple 4.6 mV under 25 mV at 9 V in
- PASS inductor peak 5.84 A under 80 % of saturation at 12 V, nominal L
- PASS valley current limit (8 A) above the 5 A load at 12 V, nominal L
- PASS inductor peak 6.04 A under 80 % of saturation at 12 V, L -20 %
- PASS valley current limit (8 A) above the 5 A load at 12 V, L -20 %
- PASS output ripple 6.2 mV under 25 mV at 12 V in
- PASS efficiency 95.8 % above the 90 % the firmware budgets
- PASS buck junction 68 C under 110 C at 45 C air
- PASS port voltage 4.81 V at 1.5 A, worst case, at or over USB's 4.75 V
- PASS switch junction 82 C at its current limit, under 125 C
- PASS shunt 0.10 W under half its rating
- PASS the highest port current reads 2.22 V, inside the ADC range
- PASS error at 1.5 A (52 mA) small next to the 1.5 A software limit's margin to the switch (420 mA)
- PASS LDO keeps 3.3 V from the PC's USB alone (4.30 V in)
- PASS LED supply inside 3.3-5.3 V
