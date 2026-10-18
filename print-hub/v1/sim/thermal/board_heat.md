# Print Hub v1: board temperatures in the closed case

Written by `sim/thermal/board_heat.py` from the routed board (`print-hub.kicad_pcb`): all four copper layers, every via and pad, 0.4 mm grid. The board is in the closed PETG case: conduction across the air gaps above and below it, radiation to the walls, the walls cooling by natural convection and radiation from the top and sides only (no credit for the floor or the vents). Limits are each part's rated maximum.


## everyday: fan 0.45 A, light 0.5 A, two filters 0.5 A each; room 25 C

Heat in the case: **1.26 W** (ESP32 0.40 W, buck 0.23 W, 3.3 0.20 W, inductor 0.12 W, port switch 0.06 W, OR 0.06 W, port USB-A 0.06 W, port LED 0.05 W, copper 0.03 W, port shunt 0.02 W, PD 0.02 W, LED 0.01 W). Case wall: 35.9 C inside, 34.8 C outside (PETG limit 65 C). The thermistor reads 51.9 C. Energy balance error 3.1e-06 W.

| part | temperature (C) | limit (C) | margin (K) |
|---|---|---|---|
| ESP32 module U5 | 56.5 | 85 | +28 |
| cap C6 (X5R) | 55.8 | 85 | +29 |
| cap C2 (X5R) | 53.8 | 85 | +31 |
| cap C16 (X5R) | 52.9 | 85 | +32 |
| cap C9 (X5R) | 52.5 | 85 | +33 |
| cap C10 (X5R) | 52.4 | 85 | +33 |
| cap C11 (X5R) | 52.2 | 85 | +33 |
| cap C3 (X5R) | 52.2 | 85 | +33 |
| cap C12 (X5R) | 52.1 | 85 | +33 |
| USB-C J1 | 51.1 | 85 | +34 |
| cap C17 (X5R) | 51.1 | 85 | +34 |
| LED status | 51.0 | 85 | +34 |
| PD sink U1 | 50.9 | 85 | +34 |
| cap C18 (X5R) | 50.2 | 85 | +35 |

Board copper: F.Cu 43.1-62.7 C, In1.Cu 43.1-55.5 C, In2.Cu 43.1-52.8 C, B.Cu 43.0-52.7 C.

![everyday](board_heat_everyday_top_bottom.png)


## the same in a hot room: 35 C

Heat in the case: **1.26 W** (ESP32 0.40 W, buck 0.23 W, 3.3 0.20 W, inductor 0.12 W, port switch 0.07 W, OR 0.06 W, port USB-A 0.06 W, port LED 0.05 W, copper 0.03 W, port shunt 0.02 W, PD 0.02 W, LED 0.01 W). Case wall: 45.6 C inside, 44.5 C outside (PETG limit 65 C). The thermistor reads 61.0 C. Energy balance error 3.0e-06 W.

| part | temperature (C) | limit (C) | margin (K) |
|---|---|---|---|
| ESP32 module U5 | 65.5 | 85 | +20 |
| cap C6 (X5R) | 64.9 | 85 | +20 |
| cap C2 (X5R) | 62.9 | 85 | +22 |
| cap C16 (X5R) | 62.0 | 85 | +23 |
| cap C9 (X5R) | 61.6 | 85 | +23 |
| cap C10 (X5R) | 61.5 | 85 | +23 |
| cap C11 (X5R) | 61.3 | 85 | +24 |
| cap C3 (X5R) | 61.2 | 85 | +24 |
| cap C12 (X5R) | 61.2 | 85 | +24 |
| USB-C J1 | 60.2 | 85 | +25 |
| cap C17 (X5R) | 60.1 | 85 | +25 |
| PD sink U1 | 60.0 | 85 | +25 |
| LED status | 60.0 | 85 | +25 |
| cap C102 (X5R) | 59.2 | 85 | +26 |

Board copper: F.Cu 52.2-71.7 C, In1.Cu 52.3-64.6 C, In2.Cu 52.2-61.8 C, B.Cu 52.2-61.8 C.

![everyday-hot](board_heat_everyday-hot_top_bottom.png)


## most allowed: 3 A (ports 1 and 2, next to the buck, at their 1.5 A limit), rail at its highest corner; room 35 C

Heat in the case: **2.46 W** (port switch 0.61 W, buck 0.42 W, ESP32 0.40 W, port USB-A 0.27 W, inductor 0.23 W, 3.3 0.20 W, copper 0.10 W, port shunt 0.09 W, OR 0.06 W, port LED 0.05 W, PD 0.02 W, LED 0.01 W). Case wall: 54.0 C inside, 52.0 C outside (PETG limit 65 C). The thermistor reads 86.7 C. Energy balance error 2.5e-06 W.

| part | temperature (C) | limit (C) | margin (K) |
|---|---|---|---|
| cap C6 (X5R) | 94.1 | 85 | -9 |
| cap C12 (X5R) | 91.2 | 85 | -6 |
| cap C9 (X5R) | 90.7 | 85 | -6 |
| cap C10 (X5R) | 90.5 | 85 | -6 |
| cap C11 (X5R) | 90.3 | 85 | -5 |
| cap C2 (X5R) | 89.9 | 85 | -5 |
| cap C102 (X5R) | 89.6 | 85 | -5 |
| port 1 USB-A | 89.3 | 85 | -4 |
| cap C105 (X5R) | 88.8 | 85 | -4 |
| port 1 LED | 86.9 | 85 | -2 |
| port 2 USB-A | 86.6 | 85 | -2 |
| cap C3 (X5R) | 86.5 | 85 | -2 |
| cap C202 (X5R) | 86.5 | 85 | -1 |
| cap C205 (X5R) | 86.1 | 85 | -1 |

Board copper: F.Cu 61.9-99.2 C, In1.Cu 62.0-95.7 C, In2.Cu 61.9-89.7 C, B.Cu 61.8-89.6 C.

![max](board_heat_max_top_bottom.png)


## Hotter rooms: where the thermal protection takes over

No turning down in these runs: they show what the thermistor reads when the first part reaches its limit, which sets the firmware's thresholds (`firmware/lib/hub/src/hub.h`).

| room (C) | load | heat (W) | thermistor (C) | first part to its limit | its margin (K) | thermistor reading at that part's limit (C) |
|---|---|---|---|---|---|---|
| 35 | 3 A | 2.46 | 86.7 | cap C6 (X5R) | -9.1 | 77.6 |
| 35 | 1.5 A | 1.50 | 66.0 | cap C12 (X5R) | +13.9 | 79.9 |
| 35 | none | 0.81 | 49.3 | ESP32 module U5 | +25.0 | 74.2 |
| 40 | 3 A | 2.47 | 91.0 | cap C6 (X5R) | -13.4 | 77.6 |
| 40 | 1.5 A | 1.51 | 70.4 | cap C12 (X5R) | +9.4 | 79.8 |
| 40 | none | 0.81 | 53.9 | ESP32 module U5 | +20.4 | 74.3 |
| 45 | 3 A | 2.48 | 95.3 | cap C6 (X5R) | -17.8 | 77.5 |
| 45 | 1.5 A | 1.51 | 74.9 | cap C12 (X5R) | +4.8 | 79.8 |
| 45 | none | 0.81 | 58.6 | ESP32 module U5 | +15.8 | 74.3 |
| 50 | 3 A | 2.49 | 99.6 | cap C6 (X5R) | -22.1 | 77.5 |
| 50 | 1.5 A | 1.52 | 79.4 | cap C12 (X5R) | +0.3 | 79.7 |
| 50 | none | 0.81 | 63.2 | ESP32 module U5 | +11.2 | 74.4 |

The lowest thermistor reading at which some part reaches its limit: **74.2 C**. The firmware switches every port off at a lower reading (TRIP_C) and starts turning them down well before (DERATE_C).


## Result

**OVER LIMIT: max: cap C6 (X5R) 94 C over 85 C; max: cap C12 (X5R) 91 C over 85 C; max: cap C9 (X5R) 91 C over 85 C; max: cap C10 (X5R) 91 C over 85 C; max: cap C11 (X5R) 90 C over 85 C; max: cap C2 (X5R) 90 C over 85 C; max: cap C102 (X5R) 90 C over 85 C; max: port 1 USB-A 89 C over 85 C; max: cap C105 (X5R) 89 C over 85 C; max: port 1 LED 87 C over 85 C; max: port 2 USB-A 87 C over 85 C; max: cap C3 (X5R) 87 C over 85 C; max: cap C202 (X5R) 86 C over 85 C; max: cap C205 (X5R) 86 C over 85 C**
