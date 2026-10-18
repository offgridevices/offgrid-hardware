# Print Hub v1: board temperatures in the closed case

Written by `sim/thermal/board_heat.py` from the routed board (`print-hub.kicad_pcb`): all four copper layers, every via and pad, 0.4 mm grid. The board is in the closed PETG case: conduction across the air gaps above and below it, radiation to the walls, the walls cooling by natural convection and radiation from the top and sides only (no credit for the floor or the vents). Limits are each part's rated maximum.

Case: the case from mechanical/enclosure/case_gaps.json: outside 90.6 x 53.2 x 18.0 mm on 4 mm feet; air above the board 1.2-8.4 mm (the lid steps down over the low parts), below it 1.0-4.0 mm.


## everyday: fan 0.45 A, light 0.5 A, two filters 0.5 A each; room 25 C

Heat in the case: **1.25 W** (ESP32 0.40 W, buck 0.23 W, 3.3 0.20 W, inductor 0.11 W, port switch 0.06 W, OR 0.06 W, port USB-A 0.06 W, port LED 0.05 W, copper 0.03 W, port shunt 0.02 W, PD 0.02 W, LED 0.01 W). Lid 35.2 C on average, 38.5 C at its hottest; floor 36.9 / 39.5 C (PETG limit 65 C). The thermistor reads 43.9 C. Energy balance error 1.9e-06 W.

| part | temperature (C) | limit (C) | margin (K) |
|---|---|---|---|
| ESP32 module U5 | 49.1 | 85 | +36 |
| cap C6 (X5R) | 48.0 | 85 | +37 |
| cap C2 (X5R) | 46.1 | 85 | +39 |
| cap C16 (X5R) | 45.6 | 85 | +39 |
| cap C9 (X5R) | 44.7 | 85 | +40 |
| cap C10 (X5R) | 44.6 | 85 | +40 |
| cap C3 (X5R) | 44.5 | 85 | +40 |
| cap C11 (X5R) | 44.5 | 85 | +41 |
| cap C12 (X5R) | 44.4 | 85 | +41 |
| LED status | 43.9 | 85 | +41 |
| cap C17 (X5R) | 43.8 | 85 | +41 |
| PD sink U1 | 43.3 | 85 | +42 |
| USB-C J1 | 43.2 | 85 | +42 |
| cap C502 (X5R) | 42.9 | 85 | +42 |

Board copper: F.Cu 34.8-55.3 C, In1.Cu 34.9-47.7 C, In2.Cu 34.8-45.0 C, B.Cu 34.7-44.9 C.

![everyday](board_heat_everyday_top_bottom.png)


## the same in a hot room: 35 C

Heat in the case: **1.26 W** (ESP32 0.40 W, buck 0.23 W, 3.3 0.20 W, inductor 0.12 W, port switch 0.07 W, OR 0.06 W, port USB-A 0.06 W, port LED 0.05 W, copper 0.03 W, port shunt 0.02 W, PD 0.02 W, LED 0.01 W). Lid 45.0 C on average, 48.2 C at its hottest; floor 46.6 / 49.2 C (PETG limit 65 C). The thermistor reads 53.8 C. Energy balance error 2.6e-06 W.

| part | temperature (C) | limit (C) | margin (K) |
|---|---|---|---|
| ESP32 module U5 | 58.9 | 85 | +26 |
| cap C6 (X5R) | 57.9 | 85 | +27 |
| cap C2 (X5R) | 55.9 | 85 | +29 |
| cap C16 (X5R) | 55.3 | 85 | +30 |
| cap C9 (X5R) | 54.6 | 85 | +30 |
| cap C10 (X5R) | 54.5 | 85 | +31 |
| cap C11 (X5R) | 54.3 | 85 | +31 |
| cap C3 (X5R) | 54.3 | 85 | +31 |
| cap C12 (X5R) | 54.2 | 85 | +31 |
| LED status | 53.6 | 85 | +31 |
| cap C17 (X5R) | 53.5 | 85 | +31 |
| PD sink U1 | 53.1 | 85 | +32 |
| USB-C J1 | 53.0 | 85 | +32 |
| cap C502 (X5R) | 52.7 | 85 | +32 |

Board copper: F.Cu 44.5-65.1 C, In1.Cu 44.6-57.6 C, In2.Cu 44.5-54.9 C, B.Cu 44.4-54.7 C.

![everyday-hot](board_heat_everyday-hot_top_bottom.png)


## most allowed: 3 A (ports 1 and 2, next to the buck, at their 1.5 A limit), rail at its highest corner; room 35 C

Heat in the case: **2.43 W** (port switch 0.60 W, buck 0.41 W, ESP32 0.40 W, port USB-A 0.27 W, inductor 0.22 W, 3.3 0.20 W, copper 0.09 W, port shunt 0.09 W, OR 0.06 W, port LED 0.05 W, PD 0.02 W, LED 0.01 W). Lid 53.0 C on average, 63.5 C at its hottest; floor 56.1 / 66.3 C (PETG limit 65 C). The thermistor reads 75.3 C. Energy balance error 4.0e-06 W.

| part | temperature (C) | limit (C) | margin (K) |
|---|---|---|---|
| cap C6 (X5R) | 83.1 | 85 | +2 |
| cap C12 (X5R) | 80.7 | 85 | +4 |
| cap C9 (X5R) | 79.7 | 85 | +5 |
| cap C10 (X5R) | 79.6 | 85 | +5 |
| cap C11 (X5R) | 79.4 | 85 | +6 |
| port 1 USB-A | 79.2 | 85 | +6 |
| cap C102 (X5R) | 79.1 | 85 | +6 |
| cap C2 (X5R) | 79.0 | 85 | +6 |
| cap C105 (X5R) | 78.7 | 85 | +6 |
| port 1 LED | 77.0 | 85 | +8 |
| port 2 USB-A | 76.9 | 85 | +8 |
| cap C202 (X5R) | 76.4 | 85 | +9 |
| cap C205 (X5R) | 76.3 | 85 | +9 |
| cap C3 (X5R) | 75.8 | 85 | +9 |

Board copper: F.Cu 48.1-88.1 C, In1.Cu 48.1-85.1 C, In2.Cu 48.0-78.7 C, B.Cu 47.9-79.2 C.

![max](board_heat_max_top_bottom.png)


## Hotter rooms: where the thermal protection takes over

No turning down in these runs: they show what the thermistor reads when the first part reaches its limit, which sets the firmware's thresholds (`firmware/lib/hub/src/hub.h`).

| room (C) | load | heat (W) | thermistor (C) | first part to its limit | its margin (K) | thermistor reading at that part's limit (C) |
|---|---|---|---|---|---|---|
| 35 | 3 A | 2.43 | 75.3 | cap C6 (X5R) | +1.9 | 77.3 |
| 35 | 1.5 A | 1.50 | 57.8 | port 1 USB-A | +21.5 | 79.3 |
| 35 | none | 0.81 | 44.3 | ESP32 module U5 | +29.5 | 73.8 |
| 40 | 3 A | 2.44 | 80.3 | cap C6 (X5R) | -3.1 | 77.2 |
| 40 | 1.5 A | 1.50 | 62.7 | port 1 USB-A | +16.6 | 79.3 |
| 40 | none | 0.81 | 49.2 | ESP32 module U5 | +24.6 | 73.8 |
| 45 | 3 A | 2.45 | 85.3 | cap C6 (X5R) | -8.1 | 77.2 |
| 45 | 1.5 A | 1.51 | 67.6 | port 1 USB-A | +11.7 | 79.3 |
| 45 | none | 0.81 | 54.1 | ESP32 module U5 | +19.7 | 73.8 |
| 50 | 3 A | 2.47 | 90.3 | cap C6 (X5R) | -13.1 | 77.1 |
| 50 | 1.5 A | 1.51 | 72.5 | cap C12 (X5R) | +6.7 | 79.3 |
| 50 | none | 0.81 | 59.0 | ESP32 module U5 | +14.8 | 73.8 |

The lowest thermistor reading at which some part reaches its limit: **73.8 C**. The firmware switches every port off at a lower reading (TRIP_C) and starts turning them down well before (DERATE_C).


## Result

**OVER LIMIT: max: case wall 66 C over 65 C**
