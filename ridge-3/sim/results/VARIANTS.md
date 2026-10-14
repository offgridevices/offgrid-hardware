# Ridge 3 variants

Each column is rev 2 with one change (sim/data.py VARIANTS), run through the same simulations (`stress.py --variant=NAME`).

| | `rev2` | `idrive30` | `lihv` | `alt2250` | `bsz040` | `bsz040-idrive30` | `temp120` | `idrive30-temp120` |
|---|---|---|---|---|---|---|---|---|
| Change | the design as committed | IDRIVE 30 mA source / 60 mA sink (the IDRIVE resistor 18k instead of 75k) | a 6S LiHV pack: 4.35 V per cell, 26.1 V full | 2,250 m up (Mexico City): air at 0.77 of sea-level pressure, so 0.77 of its density | ESC FETs Infineon BSZ040N06LS5 (OptiMOS 5, in stock at JLC) instead of ISZ023N06LM6 | ESC FETs BSZ040N06LS5 and IDRIVE 30 mA / 60 mA | AM32's temperature limit at 120 C instead of 110 C (a configurator setting) | IDRIVE 30 mA / 60 mA and AM32's temperature limit at 120 C |
| Verdicts: pass / marginal / fail | 19 / 1 / 3 | 19 / 2 / 2 | 19 / 1 / 3 | 20 / 1 / 2 | 19 / 1 / 3 | 19 / 2 / 2 | 19 / 1 / 4 | 19 / 2 / 3 |
| SHx below ground (DRV8320H: -7 V for 200 ns) | -9.2 V (-12.8 V in the bracket) | -5.6 V (-7.6 V in the bracket) | -9.3 V (-12.8 V in the bracket) | -9.2 V (-12.8 V in the bracket) | -10.6 V (-14.4 V in the bracket) | -6.1 V (-8.2 V in the bracket) | -9.2 V (-12.8 V in the bracket) | -5.6 V (-7.6 V in the bracket) |
| High-side FET peak at turn-off, 30 A (V) | 37.7 | 31.3 | 38.7 | 37.7 | 40.1 | 32.3 | 37.7 | 31.3 |
| Low-side FET peak (V) | 37.2 | 25.0 | 38.5 | 37.2 | 51.7 | 25.0 | 37.2 | 25.0 |
| Hover throttle | 27 % | 27 % | 26 % | 32 % | 27 % | 27 % | 27 % | 27 % |
| Held all day before AM32 cuts, 25 C, 5 m/s | 58 % (10.5 A/motor) | 55 % (9.2 A/motor) | 56 % (10.1 A/motor) | 71 % (11.7 A/motor) | 54 % (8.7 A/motor) | 52 % (7.9 A/motor) | 60 % (11.3 A/motor) | 57 % (9.9 A/motor) |
| Held all day, every part in rating, 25 C, 5 m/s | 61 % | 58 % | 58 % | 75 % | 56 % | 55 % | 61 % | 58 % |
| Held all day before AM32 cuts, 50 C, 5 m/s | 52 % (7.7 A/motor) | 49 % (6.6 A/motor) | 50 % (7.5 A/motor) | 58 % (8.0 A/motor) | 48 % (6.5 A/motor) | 45 % (5.5 A/motor) | 54 % (8.6 A/motor) | 52 % (7.5 A/motor) |
| Held all day, every part in rating, 50 C, 5 m/s | 55 % | 53 % | 53 % | 64 % | 52 % | 50 % | 55 % | 53 % |
| Held all day before AM32 cuts, 60 C, 5 m/s | 48 % (6.5 A/motor) | 43 % (5.2 A/motor) | 45 % (6.0 A/motor) | 54 % (6.7 A/motor) | 43 % (5.2 A/motor) | 40 % (4.5 A/motor) | 52 % (7.5 A/motor) | 48 % (6.5 A/motor) |
| Held all day, every part in rating, 60 C, 5 m/s | 53 % | 50 % | 51 % | 59 % | 50 % | 46 % | 53 % | 50 % |
| Held all day before AM32 cuts, 50 C, 2 m/s | 45 % (5.6 A/motor) | 41 % (4.6 A/motor) | 42 % (5.3 A/motor) | 52 % (5.9 A/motor) | 41 % (4.6 A/motor) | 35 % (3.6 A/motor) | 49 % (6.6 A/motor) | 44 % (5.4 A/motor) |
| Held all day, every part in rating, 50 C, 2 m/s | 50 % | 46 % | 47 % | 55 % | 45 % | 42 % | 50 % | 46 % |
| Held all day before AM32 cuts, 60 C, 2 m/s | 41 % (4.6 A/motor) | 32 % (3.2 A/motor) | 36 % (4.1 A/motor) | 48 % (4.8 A/motor) | 33 % (3.4 A/motor) | 29 % (2.7 A/motor) | 45 % (5.5 A/motor) | 40 % (4.5 A/motor) |
| Held all day, every part in rating, 60 C, 2 m/s | 46 % | 42 % | 43 % | 53 % | 41 % | 37 % | 46 % | 42 % |
| Full-throttle burst, 50 C: hottest FET with AM32 acting | 126 C | 127 C | 126 C | 122 C | 132 C | 131 C | 137 C | 137 C |
| Hard 3-min flight, 50 C: AM32 cuts a motor | from 62 s, 9 % of the flight | from 42 s, 16 % of the flight | from 43 s, 15 % of the flight | never | from 26 s, 18 % of the flight | from 22 s, 24 % of the flight | from 126 s, 1 % of the flight | from 62 s, 9 % of the flight |
| Hard 3-min flight, 50 C: hottest FET / ESC processor | 128 / 110 C | 129 / 111 C | 128 / 112 C | 116 / 102 C | 132 / 111 C | 132 / 112 C | 134 / 116 C | 140 / 119 C |
| Ground, 60 C, HD 9 V 1.5 A + 5 V 1 A: parts past rating | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 |
