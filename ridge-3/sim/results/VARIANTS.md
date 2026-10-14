# Ridge 3 variants

Each column is rev 2 with one change (sim/data.py VARIANTS), run through the same simulations (`stress.py --variant=NAME`).

| | `rev2` | `idrive30` | `lihv` | `alt2250` | `bsz040` | `bsz040-idrive30` | `temp120` | `idrive30-temp120` |
|---|---|---|---|---|---|---|---|---|
| Change | the design as committed | IDRIVE 30 mA source / 60 mA sink (the IDRIVE resistor 18k instead of 75k) | a 6S LiHV pack: 4.35 V per cell, 26.1 V full | 2,250 m up (Mexico City): air at 0.77 of sea-level pressure, so 0.77 of its density | ESC FETs Infineon BSZ040N06LS5 (OptiMOS 5, in stock at JLC) instead of ISZ023N06LM6 | ESC FETs BSZ040N06LS5 and IDRIVE 30 mA / 60 mA | AM32's temperature limit at 120 C instead of 110 C (a configurator setting) | IDRIVE 30 mA / 60 mA and AM32's temperature limit at 120 C |
| Verdicts: pass / marginal / fail | 20 / 0 / 3 | 20 / 1 / 2 | 20 / 0 / 3 | 21 / 0 / 2 | 19 / 1 / 3 | 20 / 1 / 2 | 20 / 0 / 4 | 20 / 1 / 3 |
| SHx below ground (DRV8320H: -7 V for 200 ns) | -10.3 V (-14.2 V in the bracket) | -6.2 V (-8.5 V in the bracket) | -10.3 V (-14.2 V in the bracket) | -10.3 V (-14.2 V in the bracket) | -11.8 V (-15.9 V in the bracket) | -6.7 V (-9.0 V in the bracket) | -10.3 V (-14.2 V in the bracket) | -6.2 V (-8.5 V in the bracket) |
| High-side FET peak at turn-off, 30 A (V) | 39.6 | 32.3 | 40.5 | 39.6 | 42.1 | 33.4 | 39.6 | 32.3 |
| Low-side FET peak (V) | 42.5 | 26.8 | 43.8 | 42.5 | 57.4 | 27.4 | 42.5 | 26.8 |
| Hover throttle | 27 % | 27 % | 26 % | 32 % | 27 % | 27 % | 27 % | 27 % |
| Held all day before AM32 cuts, 25 C, 5 m/s | 58 % (10.3 A/motor) | 55 % (8.9 A/motor) | 55 % (9.9 A/motor) | 70 % (11.4 A/motor) | 54 % (8.6 A/motor) | 52 % (7.7 A/motor) | 60 % (11.1 A/motor) | 57 % (9.8 A/motor) |
| Held all day, every part in rating, 25 C, 5 m/s | 61 % | 57 % | 57 % | 74 % | 56 % | 54 % | 61 % | 57 % |
| Held all day before AM32 cuts, 50 C, 5 m/s | 52 % (7.5 A/motor) | 48 % (6.3 A/motor) | 50 % (7.3 A/motor) | 58 % (7.9 A/motor) | 48 % (6.3 A/motor) | 44 % (5.3 A/motor) | 54 % (8.4 A/motor) | 51 % (7.4 A/motor) |
| Held all day, every part in rating, 50 C, 5 m/s | 55 % | 52 % | 53 % | 63 % | 52 % | 50 % | 55 % | 52 % |
| Held all day before AM32 cuts, 60 C, 5 m/s | 48 % (6.3 A/motor) | 42 % (4.9 A/motor) | 45 % (5.9 A/motor) | 54 % (6.6 A/motor) | 43 % (5.1 A/motor) | 39 % (4.3 A/motor) | 51 % (7.4 A/motor) | 47 % (6.2 A/motor) |
| Held all day, every part in rating, 60 C, 5 m/s | 52 % | 50 % | 50 % | 59 % | 49 % | 45 % | 52 % | 50 % |
| Held all day before AM32 cuts, 50 C, 2 m/s | 44 % (5.4 A/motor) | 39 % (4.2 A/motor) | 41 % (5.1 A/motor) | 51 % (5.7 A/motor) | 40 % (4.5 A/motor) | 33 % (3.4 A/motor) | 48 % (6.5 A/motor) | 43 % (5.1 A/motor) |
| Held all day, every part in rating, 50 C, 2 m/s | 50 % | 45 % | 46 % | 55 % | 45 % | 41 % | 50 % | 45 % |
| Held all day before AM32 cuts, 60 C, 2 m/s | 40 % (4.4 A/motor) | 30 % (2.9 A/motor) | 35 % (3.9 A/motor) | 47 % (4.7 A/motor) | 32 % (3.2 A/motor) | 28 % (2.5 A/motor) | 44 % (5.3 A/motor) | 38 % (4.1 A/motor) |
| Held all day, every part in rating, 60 C, 2 m/s | 45 % | 41 % | 43 % | 52 % | 41 % | 35 % | 45 % | 41 % |
| Full-throttle burst, 50 C: hottest FET with AM32 acting | 126 C | 127 C | 129 C | 122 C | 133 C | 131 C | 138 C | 137 C |
| Hard 3-min flight, 50 C: AM32 cuts a motor | from 62 s, 10 % of the flight | from 26 s, 18 % of the flight | from 42 s, 15 % of the flight | never | from 25 s, 19 % of the flight | from 22 s, 24 % of the flight | from 106 s, 2 % of the flight | from 46 s, 11 % of the flight |
| Hard 3-min flight, 50 C: hottest FET / ESC processor | 128 / 111 C | 128 / 111 C | 130 / 111 C | 118 / 104 C | 134 / 112 C | 134 / 112 C | 136 / 117 C | 140 / 120 C |
| Ground, 60 C, HD 9 V 1.5 A + 5 V 1 A: parts past rating | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 |
