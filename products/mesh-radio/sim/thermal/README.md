# Mesh Radio v1: thermal studies

This folder checks how hot the board gets and whether every part's
temperature rating covers where the node will be used. It covers README
requirements E1 to E4 and P7.

The four studies are:

1. a heat model of the board;
2. an audit of every part's temperature rating;
3. cold start at −40 °C;
4. whether the board could be smaller.

```
tools/kd python3 sim/thermal/run.py        # from products/mesh-radio; about 45 min with NPROC=2
tools/kd python3 sim/thermal/followup.py   # the follow-up below; about 55 min with NPROC=2
```

`run.py` reads `src/circuit.py`, `src/parts.py`, `src/pcb.py`,
`src/layout.py`, `src/placement.json` and the routed board
`mesh-radio.kicad_pcb`. It changes nothing outside this folder. It writes
`results.txt`, which holds every number quoted here, and the five plots.
It needs pcbnew, numpy, scipy, matplotlib and PIL, which the pinned image
has. `NPROC` sets the number of worker processes (default: every core).

## What changed on 3 Nov: the routed board

The study was written for the 62 mm, 4-layer board before routing, with
the copper as a guess. It now models the finished board:

- **70 × 25.4 mm, six copper layers**, the board's own stackup
  (JLC06161H-2116B: 35 µm outer, 17.5 µm inner copper, 0.116 / 0.5 /
  0.076 / 0.5 / 0.116 mm dielectric), read from `mesh-radio.kicad_pcb`.
- **The real copper, cell by cell.** `board_copper.py` draws every fill,
  track, pad and via land of each layer into a 0.05 mm bitmap, and
  `run.py` averages it onto its 0.5 mm grid. The board has F 79 %, In1
  91 %, In2–In4 86–87 % and B 81 % copper (the guess was 70 / 100 / 50 /
  50 / 100 / 70 %).
- **The real vias.** The 561 ground vias (0.15 and 0.2 mm drills) sit
  where the board has them: 32 per cm² on average, 21 per cm² within 5 mm
  of the amplifier. The other 270 vias are on signal nets and do not join
  the planes, so the model leaves them out. The nine 0.3 mm vias in the
  amplifier's paddle are counted on the board.
- **The paddle is an island on the top layer, as routed.** The top ground
  fill touches pad 17 only through a 0.2–0.3 mm neck at one package corner
  (read off a render of the fill). That is worth about 100 °C/W, against
  2.3 °C/W through the vias, so the model keeps the paddle as an island.
- **The gap pad is where the board has it:** `layout.GAP_PAD`, 13–23 mm
  by 2.5–12.5 mm on the bottom, below the plug row. The board has 99 %
  copper there and a matching B.Mask opening. Until 2 Nov the study put
  it under the amplifier; that spot is now kept only for comparison.
- **The parts as built:** the amplifier is found by its part (U10, not
  the old U11, which is now the antenna switch); CSD25310Q2 reverse FET
  (33 mΩ hot); 15 mΩ sense resistor; LFCG-1000+ filter; the RF losses
  from `sim/rf` (1.13 dB); the charge current read from the ISET
  resistor (1 k, **300 mA**, was 497 mA); charger U4 at the USB end; NTC
  TH1 beside the battery plug J3, next to the amplifier.
- The Bluetooth antenna box and the gap pad come from `src/layout.py`,
  the board size from `src/pcb.py`; nothing in the model is a hard-coded
  reference or coordinate any more.

Old against new, h = 10 W/m²K, no charging, peak at the end of the burst:

| Case | Old (62 mm, 4 layers, guessed copper) | New (routed board) |
|---|---|---|
| 1 W, 1 message/min, 25 °C: case / junction | 60 / 82 °C | **53 / 75 °C** PASS |
| 1 W, 25 % storm, 25 °C: case | 80 °C MARGINAL | **68 °C** PASS |
| 1 W, 1 message/min, 60 °C: case / junction | 95 / 116 °C FAIL | **88 / 109 °C** FAIL |
| 2.5 W, 1 message/min, 25 °C: case / junction | 121 / 180 °C | **103 / 161 °C** FAIL |
| 3 W, 1 message/min, 25 °C: case / junction | 149 / 224 °C | **125 / 201 °C** FAIL |
| 2.5 W, 25 % storm, 60 °C: case | 206 °C | **175 °C** FAIL |
| Highest duty at 25 °C: 1 W / 2.5 W / 3 W | 17 % / none / none | **25 %** / none / none |
| Highest duty at 60 °C, any power | none | none |
| USB charging, 3.0 V cell, 25 °C: charger junction | 115 °C, throttled to 83 % | **79 °C**, full current |
| ... NTC reads / cell area | 60 °C (trips) / 53 °C | **34 / 34 °C** PASS |
| Gap pad, 2.5 W storm at 60 °C, with the board fixes | 135 → 96 °C (pad under the PA) | 134 → **109 °C** (pad as built) |

The better numbers come from the six layers and the denser copper: the
first prepreg is 0.116 mm, not 0.21 mm, so the paddle vias reach In1 at
2.3 °C/W (3.8 before), and the inner layers are fuller. The routed board
runs 1–4 °C cooler than the old uniform guess for six layers would have
said. The charging numbers changed because the charger moved 51 mm away
from the cell plug and the current dropped to 300 mA. The gap pad helps
less than before because it moved away from the amplifier.

## The short version

- **Listening and charging alone are fine.** The charger no longer
  heats the cell area or its own NTC.
- **The amplifier is still the problem.** A 1-second LoRa message at
  2.5 W or 3 W heats the QPA9510 past its 85 °C case rating, even at room
  temperature, even for one message a minute.
  - Most of that heat is a local spike inside the burst, within 2–3 mm
    of the chip. The heat sensor, firmware, or more board cannot stop it.
  - Only a better path for the heat, straight down into metal, can.
- **1 W, the US setting, works in a room** for up to a 25 % storm. In a
  60 °C sealed box nothing passes on the board as built, not even 1 W
  once a minute (case 88 °C).
- **New: transmitting now heats the cell area.** The battery plug J3 sits
  3 mm from the amplifier. While charging, the 45 °C cell rule fails in a
  1 W storm at 25 °C (53 °C) and at 2.5 W once a minute (47 °C).
- **The board's length is set by its parts, not by heat.** 50, 60 or
  80 mm changes the one-message-a-minute peak by 1 °C or less.

### Study 1: heat model (E2, E3)

| Case | Verdict | Key numbers (h = 10 W/m²K) |
|---|---|---|
| Listening, −40 to 60 °C | **PASS** | Board about 1 °C above the air |
| Listening at 85 °C | MARGINAL | The 85 °C-rated chips (the LNA U12 first) sit just over their limit. That is true of any 85 °C box. |
| 1 W, 1 message/min, 25 °C | **PASS** | Amplifier case 53 °C, junction 75 °C |
| 1 W, 25 % storm, 25 °C | **PASS** | Case 68 °C, junction 90 °C |
| 1 W, 1 message/min, 60 °C box | **FAIL** | Case 88 °C, over the 85 °C limit; junction 109 °C |
| 2.5 W, 1 message/min, 25 °C | **FAIL** | Case 103 °C, junction 161 °C (160 °C allowed) |
| 3 W, 1 message/min, 25 °C | **FAIL** | Case 125 °C, junction 201 °C (175 °C rating) |
| Storms (25 %, 50 %) at 2.5–3 W | **FAIL** | At 60 °C the buck-boost (144 °C) also passes 125 °C |
| Continuous transmit, any power | **FAIL** | Steady state, with nothing to stop it |
| USB charging alone, 3.0 V cell, 25 °C | **PASS** | Charger junction 79 °C (TREG 100 °C): full 300 mA. NTC and cell area 34 °C. |
| USB charging alone, 60 °C box | throttled | Charger junction would reach 112 °C; TREG keeps 77 % of the current |
| Charging while transmitting, 25 °C | **FAIL** above 1 W once a minute | Cell area 38 °C at 1 W once a minute (PASS), 53 °C in a 1 W storm, 47 °C at 2.5 W once a minute (45 °C limit) |
| Battery area in a 60 °C box | FAIL, set by the box | The cell is at 60 °C before the radio does anything |

Highest transmit duty that passes, on the board as built with 1-second
messages, no gap pad and no charging (`max_duty.png`). The
battery-at-60-°C limit is left out, because the box sets it:

| Ambient | 1 W | 2.5 W | 3 W |
|---|---|---|---|
| −40 °C | continuous (h=5: 50 %) | 1 msg / 6 s (h=5: 1/15 s) | 1 msg / 15 s (h=5: 1/30 s) |
| −20 °C | 50 % | 1 msg / 15 s | none |
| 0 °C | 50 % | 1 msg / min | none |
| 25 °C | 25 % | none | none |
| 60 °C | none | none | none |
| 85 °C | none | none | none |

With fixes (h = 10, `results.txt`):

| Board | 25 °C: 1 W / 2.5 W / 3 W | 60 °C: 1 W / 2.5 W / 3 W |
|---|---|---|
| As built | 25 % / none / none | none / none / none |
| As built + gap pad to a metal wall | continuous / none / none | none / none / none |
| All board fixes (fix 2) | 50 % / 1 per 15 s / 1 per min | 1 per 15 s / none / none |
| All board fixes + gap pad | continuous / 25 % / 1 per 15 s | 25 % / none / none |

The old study had, with the fixes and the pad under the amplifier, 1 W at
50 % in a 60 °C box and 2.5 W at 50 % at 25 °C. The routed board with
its pad where it is now gets 25 % and 25 %.

The amplifier heat path, with its data-sheet values:

- Junction to case: θjc 12.5 °C/W (Qorvo QPA9510 data sheet, 23 Jun 2025,
  p.3, CW). At 3 W the junction alone is 75 °C above the case.
- Case limit: TCASE 85 °C (p.2).
- Junction limit: 175 °C for a 10⁶-hour life (p.2), so 160 °C with the
  15 °C margin.
- The nine 0.3 mm vias, resin-filled with 20 µm plating:
  - **2.3 °C/W** to the first inner layer (In1), 0.12 mm down;
  - **23 °C/W** right through to the bottom.
  - Copper-filled, the second figure would be 5.8 °C/W.
- In 1 second the heat spreads only about 5 mm. The case swings 27 °C
  with each 1 W burst, 75 °C at 2.5 W and 97 °C at 3 W.
- The heat sensor (TMP1075, U16, on the bottom 6.3 mm from the amplifier)
  sees only the slow average: the case runs 31 °C ahead of it at 1 W and
  85 °C at 2.5 W. Firmware can use it to enforce a duty limit, not to
  protect a single burst.

### What each fix is worth

QPA9510 case peak, 2.5 W, 25 % storm, 60 °C, h = 10 (`fixes.png`):

| Change | Case peak |
|---|---|
| The routed board as built | 175 °C |
| The old uniform-copper guess for six layers | 179 °C |
| 2 oz outer copper | 171 °C |
| Paddle joined to the top pour (no island) | 158 °C |
| Copper-filled paddle vias (VIPPO) | 154 °C |
| M3 screw at the hole nearest the amplifier, to a metal standoff | 166 °C |
| Gap pad as built (`layout.GAP_PAD`) to a metal wall | 150 °C |
| Gap pad at its old spot under the amplifier | 138 °C |
| All board fixes (joined paddle, copper vias, 2 oz outer) | 134 °C |
| All board fixes + gap pad as built | **109 °C** |
| Board 50 / 60 / 80 mm long | 182 / 178 / 174 °C |

The gap pad as built takes 25 °C off a storm but almost nothing off one
message a minute (88 → 87 °C at 1 W, 60 °C): in one second the heat does
not reach it. At its old spot under the amplifier it was worth 12 °C more
in a storm.

### Study 2: temperature-rating audit (E1)

| Item | Verdict | Detail |
|---|---|---|
| ICs, crystals, TCXO, passives | **PASS** | All cover −40 to +85 °C; the source for each is in `results.txt` |
| Buttons (Alps SKRP, SW2, SW3) | **PASS** | −40 to +85 °C (`docs/part-audit.md`; `parts.py` says +90 °C). The B3U's +70 °C failure is gone. |
| JST PH/GH/SH (J2, J3, J5, J6, J7) | accepted | −25 to +85 °C (owner decision 3) |
| Amphenol USB-C | unverified | Distributor listings say −40 or −20 °C |
| Parts added since 19 Oct | unverified | MAX17608, TPS22950, CSD25310Q2, LFCG-1000+, BAT68-04W, SMF33CA, the new resistors and capacitors: ratings from series data or listings, no data sheet read here (flag `d`) |
| X5R capacitors | MARGINAL | Rated to 85 °C exactly. The hottest are on the amplifier rails (C58, C68 on VPA; C89 on PA_IN; C96 on PA_APC): 78 °C in a 1 W storm at 60 °C, 110 °C at 2.5 W. The 47 µF VPA capacitors are now X7S (125 °C). |
| Charger NTC window | MARGINAL | The hardware stops charging below about +1.4 °C typical, but a worst-case part charges down to −0.6 °C. It stops above about 59.5 °C (55.6 to 63.8 °C), **not at 45 °C**. |
| 45 °C charging rule | firmware | CHG_TS now reaches the nRF52840 (an analog input), so firmware can read the NTC and stop charging through /CE. The NTC is still on the board, beside J3, not on the cell. |

### Study 3: cold start at −40 °C

| Item | Verdict | Detail |
|---|---|---|
| Parts out of range | owner-accepted | JST connectors (−25 °C); USB-C unverified |
| 32 MHz crystal start-up | **PASS** | ESR 50 Ω against the nRF52840's 100 Ω limit |
| 32.768 kHz crystal start-up | **PASS** | ESR 70 kΩ against a 100 kΩ limit |
| 32.768 kHz accuracy | MARGINAL | Off by −152 ppm at −40 °C and −130 ppm at +85 °C. The Adafruit core declares it a 20 ppm crystal, so Bluetooth connections can drop when the node is cold or hot. |
| TCXO (−AP code) | **PASS** | −40 to +105 °C, 2 ms start-up |
| TPS63810 loop capacitance | **PASS** | 29.8 µF effective at −40 °C, worst tolerance, against 16 µF needed (the 47 µF parts are now 1206 X7S; the 0805 X5R derating is kept, so this is conservative) |
| TPS63810 input capacitance | **PASS** | 24 µF against 5 µF needed |
| TPS62840 loop | **PASS** | Output 13 µF (allowed 3–40 µF); input 5.7 µF (1 µF needed) |
| Battery at −40 °C | note | A LiPo cannot deliver 2–3 A bursts below about −20 °C |
| U.FL, 0908SQ choke, WLCSP solder joints | MARGINAL (shock, not cold) | Stake the U.FL and the choke. Consider underfill for the field build. At 2.5 W the amplifier case swings about 75 °C with every burst. |

### Study 4: size

| Question | Answer |
|---|---|
| Is the length set by heat? | **No.** A 50, 60 or 80 mm board changes the one-message-a-minute peak by 1 °C or less, and the 25 % storm by −1 to +7 °C. |
| Can the amplifier area shrink? | **No.** It needs more copper and a metal heat path, not less area. |

## Fixes, layout and values first

1. **A firmware limit on power and duty (E3).**
   - At 25 °C or below, at 1 W, allow up to a 25 % storm.
   - Above 1 W, and in a hot box, allow nothing unless fixes 2 and 3 are
     made; with them, use the tables above.
   - The TMP1075 should block transmitting when it reads above
     (85 °C − the burst spike) for the power in use: **54 °C at 1 W** on
     this board.
   - While USB charging, also hold the cell rule: stop charging (/CE)
     while transmitting above 1 W, since J3 sits next to the amplifier.
2. **Board changes under the amplifier** (case peak, 2.5 W, 25 % storm,
   60 °C):
   - join the paddle (pad 17) to the top ground pour with a solid
     connection, for instance wide copper from GND pins 2 and 4 out to the
     pour: 175 → 158 °C;
   - copper-filled vias in the paddle (VIPPO): → 154 °C;
   - 2 oz outer copper: → 171 °C;
   - **all of these together: 134 °C.**
3. **The gap pad from the bottom to a metal wall or plate** of the
   enclosure, at `layout.GAP_PAD` (bare copper, mask open, on the board):
   a 10 × 10 mm gap pad of at least 3 W/mK.
   - With fix 2 the storm case drops to **109 °C**; at 25 °C, 1 W is then
     allowed continuously, 2.5 W up to 25 % and 3 W one message in 15 s.
   - In a 60 °C box 1 W passes up to 25 %. Nothing above 1 W passes.
   - Under the amplifier it was worth 12 °C more; that bottom area now
     holds the plugs and the amplifier's power parts.
4. **Charger: done on this board.** ISET 1 k (300 mA), the charger at the
   USB end, the NTC beside the plug and readable by firmware. What is left
   is firmware: the 0–45 °C rule from the NTC, which also sees the
   amplifier's heat (in a 1 W storm at 25 °C it reads 43 °C, 51 °C while
   charging).
5. **Firmware variant:** declare the 32.768 kHz crystal as 250 ppm
   (`NRF_CLOCK_LF_ACCURACY_250_PPM`), not 20 ppm.
6. **Mechanical:**
   - put a drop of low-loss RF adhesive at the base of the 0908SQ choke;
   - fit a U.FL retention clip;
   - underfill the WLCSPs on field units.

If a part must change:

- **More than 1 W for 1-second messages:** this needs a power amplifier
  rated for continuous output, with a large metal tab.
  - The QPA9510 is a GSM handset part. Its data are taken at 37.5 % duty
    of 577 µs time slots.
  - No candidate was checked for stock in this study.
  - Until fixes 2 and 3 are measured on a built board, treat 1 W as the
    field limit.

## Follow-up: data-sheet efficiency, power per board option

`followup.py` uses the same model, the routed board and the same pass
criteria as `run.py`, with h = 10 W/m²K and no charging. It writes
`results_followup.txt` and `power_table.png`. (Its first version, 19 Oct,
compared 4- and 6-layer guesses; those rows are gone, the board is
built.)

### The amplifier's efficiency

**Nominal case: the QPA9510 data sheet (23 Jun 2025), p.4, "PAE vs.
Average Output Power",** 915 MHz curve, VCC = 3.6 V, VAPC = 2.8 V, 215 mA
quiescent, 25 °C, GSM bursts (Pin +4.5 dBm, 37.5 % duty, p.3). PAE is
31.5 % at 30 dBm, 45 % at 33 dBm, 56 % at 35 dBm, peak 57.5 % at
35.5 dBm (p.3 cross-check: 35.4 dBm at 1.7 A from 3.6 V is 56.7 %).

- The amplifier must deliver the antenna power plus 1.13 dB, the loss to
  the U.FL found by `sim/rf`.
- Firmware sets VPA so the amplifier works at its 35 dBm-equivalent point,
  within 2.7–4.0 V. This assumes a saturated amplifier keeps its PAE when
  VCC and the output scale together.
- The amplifier then gives off **1.36 / 1.44 / 2.03 / 2.56 / 3.14 W** at
  30 / 31.5 / 33 / 34 / 35 dBm at the antenna.

**Pessimistic case: the plan's supply power.** The amplifier then gives off
1.40 / 1.87 / 2.60 / 3.94 / 5.10 W.

### Highest dBm at the antenna that passes

Each cell is nominal / pessimistic; "–" means not even 30 dBm. A storm is
1 s on, 3 s off. "Paddle fixes" = the paddle joined to the top pour and
copper-filled paddle vias; "pad" = the 10 × 10 mm gap pad at
`layout.GAP_PAD` to a metal wall.

| Board option | 25 °C: 1 s/min | 25 °C: 2 s/min | 25 °C: storm | 45 °C: 1 s/min | 45 °C: 2 s/min | 45 °C: storm | 60 °C: 1 s/min | 60 °C: 2 s/min | 60 °C: storm |
|---|---|---|---|---|---|---|---|---|---|
| As built | 35/33 | 34/33 | 31.5/31.5 | 33/31.5 | 31.5/30 | –/– | –/– | –/– | –/– |
| As built + pad | 35/33 | 34/33 | 34/33 | 33/31.5 | 31.5/30 | 31.5/30 | –/– | –/– | –/– |
| As built + pad at its old spot | 35/33 | 34/33 | 35/33 | 33/31.5 | 31.5/31.5 | 33/31.5 | –/– | –/– | –/– |
| Paddle fixes | 35/35 | 35/34 | 33/33 | 35/33 | 34/33 | –/– | 31.5/31.5 | 31.5/30 | –/– |
| Paddle fixes + pad | 35/35 | 35/34 | 35/34 | 35/33 | 34/33 | 33/31.5 | 31.5/31.5 | 31.5/30 | 31.5/30 |
| Paddle fixes + 2 oz outer | 35/35 | 35/35 | 34/33 | 35/34 | 34/33 | –/– | 33/31.5 | 31.5/31.5 | –/– |
| Paddle fixes + 2 oz outer + pad | 35/35 | 35/35 | 35/34 | 35/34 | 35/33 | 34/33 | 33/31.5 | 33/31.5 | 31.5/31.5 |

At 60 °C the cell-at-60 °C criterion is left out, because the box sets
it. Against 19 Oct: the routed board with the two paddle fixes gives
exactly what the old "6-layer + fixes, 1 oz" guess gave (that guess had
the paddle joined and copper-filled vias); as built, without them, it
passes nothing at 60 °C. The best row is 1 dB short of the old best
(34 → 33 dBm once a minute at 60 °C, 33 → 31.5 dBm in a storm), because
the gap pad moved away from the amplifier.

### Which fix helps most

Case / junction peak, nominal PAE:

| Change | 25 °C, 34 dBm, 1 s/min | 45 °C, 33 dBm, 2 s/min | 60 °C, 30 dBm, storm |
|---|---|---|---|
| As built | 68 / 100 °C | 86 / 111 °C | 95 / 112 °C |
| The 19 Oct uniform guess for six layers | 70 / 102 | 88 / 113 | 96 / 113 |
| Paddle joined to the top pour | 59 / 91 | 78 / 103 | 90 / 107 |
| Copper-filled paddle vias | 57 / 89 | 75 / 101 | 88 / 105 |
| 2 oz outer | 67 / 99 | 84 / 110 | 93 / 110 |
| Both paddle fixes | 52 / 84 | 72 / 97 | 86 / 103 |
| Both paddle fixes + 2 oz outer | 48 / 80 | 67 / 92 | 83 / 100 |
| Gap pad as built | 67 / 99 | 84 / 109 | 87 / 104 |
| Gap pad at its old spot under the PA | 65 / 97 | 81 / 106 | 83 / 100 |
| Both paddle fixes + 2 oz outer + gap pad | 46 / 78 | 65 / 90 | 75 / 92 |

The two paddle fixes are worth 9–11 °C each, and most together (16 °C at
25 °C). The gap pad matters in storms (−8 °C at 60 °C) and hardly for a
single packet (−1 °C); at its old spot it was worth 4 °C more.

### The charger as built

ISET 1 k (300 mA), the charger U4 at the USB end, NTC TH1 beside J3:

- **At 25 °C** the charger junction is 79 °C from a 3.0 V cell (TREG
  100 °C: full current); the board under J3 and the NTC read 34 °C.
  400 mA would also pass (97 °C); 497 mA would throttle to 84 %.
- **At 45 °C ambient** the board round J3 is 51–53 °C at any current, so
  firmware must stop charging (the 45 °C rule); the charger's own NTC
  hot stop (55.6 °C at the earliest) does not trip.
- The NTC now reads the cell plug's board, and the amplifier's heat with
  it: firmware should not read it during or just after a burst.


## Model

- **Copper layers.** Six sheets, the stackup and copper of
  `mesh-radio.kicad_pcb` (see above), each cell's copper fraction from
  the board. FR-4 between them at 0.29 W/mK through the board and
  0.81 W/mK along it. All copper counts, whatever its net.
- **Grid and vias.** A 0.5 mm grid. The board's ground vias, 0.15 and
  0.2 mm, with 20 µm plating, in the cells where they are.
- **Amplifier pad.** The 1.5 mm pad is an island of copper on F, joined to
  the board only through its nine vias. The solder is 50 µm of SAC305
  wetting 60 % of the pad.
- **Cooling.** Convection h = 10 or 5 W/m²K on both faces, plus radiation
  at emissivity 0.9, linearised 20 K above the air. The gap pad is
  3000 W/m²K (1 mm at 3 W/mK) to a wall at ambient.
- **Heat sources** sit at their parts' positions from `placement.json`:
  - PA heat is VCC × ICC minus the RF power out, using 1.0 A at 2.7 V,
    2.0 A at 3.6 V and 2.3 A at 4.0 V from the plan.
  - TPS63810 efficiency: 92 / 89 / 87 %, from its Fig. 32/33 less two
    points for boosting from a 3.4 V cell.
  - FET resistance (RON) losses in the TPS2121 (90 mΩ), the reverse FET
    (CSD25310Q2, 33 mΩ), the protection FETs, the 15 mΩ sense resistor
    and the JST contacts.
  - Filter and switch losses from `sim/rf` (LPF 0.21, SKY13330 0.30,
    LFCG-1000+ 0.67, coupler section 0.08 dB).
  - SX1262 at +20 dBm: 102 mA (rev 1.2, Table 3-6) with the pad
    dissipation.
  - Charger: (5.0 V − VBAT) × 300 mA, plus the Schottky and the eFuse.
- **Junction temperatures** are the board under the part plus ψJB × the
  part's power, using each data sheet's ψJB:
  - TPS63810 20.5, TPS2121 15.5, BQ25185 34.7, TPS62840 39.4 and
    TPS25947 27.6 °C/W;
  - the CSD25310Q2 and the SOD-123FL diode are assumed at 30 and 60 °C/W.
- **Transients.** Implicit Euler, run to a periodic steady state. The peak
  is taken at the end of the 1 s burst.

## Not verified (assumptions)

- **Copper details.** Via plating (20 µm), resin fill, solder voids and
  the paddle's neck to the top pour are assumptions or read off a
  render. Copper of every net counts as spreading copper; 0.1–0.2 mm gaps
  between nets are not resolved by the 0.5 mm grid, so lateral spreading
  is somewhat optimistic. Signal-net vias are left out.
- **Inner copper** is the stackup's nominal 17.5 µm (the old model used
  15.2 µm finished).
- **Heat capacity.** Only the amplifier package is counted. Leaving out
  the other parts' heat capacity makes the burst peaks somewhat too high.
- **Amplifier supply current at each power level** is the plan's
  estimate, not a measurement (the follow-up's nominal case uses the data
  sheet's efficiency instead).
- **Junction-to-board values** for the CSD25310Q2 and the RB060MM, and
  the TPS63810 efficiency in deep boost.
- **Not modelled:** the new bypass diode D8 and TPS22950, and the
  MAX17608 solar/drone limiters (each well under 0.1 W in the cases here).
- **The TS bias current.** It is taken to be ITSMR, 38 µA, and the NTC's
  1 % and B-value tolerances are not included.
- **The cell.** It is not modelled. "Cell area" means the board under J3.
- **Ratings marked `d` in `results.txt`:** passive series specifications,
  every part added since 19 Oct, Hirose U.FL, Amphenol USB-C, Coilcraft
  0908SQ, Lite-On LEDs, C&K slide switch and Toshiba SSM3K56ACT. No copy
  of their data sheets was read here.
- **Study 3's converter rows** were not re-derived from the current
  circuit, beyond the 47 µF X7S change.

## Files

| File | What it is |
|---|---|
| `run.py` | The model and all four studies |
| `board_copper.py` | Reads the routed board's copper, vias and stackup for `run.py` |
| `results.txt` | Every number |
| `thermal_map.png` | The board at the end of a 2.5 W burst, 25 % storm, 60 °C |
| `pa_burst.png` | Amplifier junction and case through one storm period |
| `max_duty.png` | Highest allowed duty against ambient |
| `charging.png` | Charger junction and throttling against ambient |
| `fixes.png` | Effect of each fix on the amplifier case |
| `followup.py`, `results_followup.txt`, `power_table.png` | The follow-up: data-sheet efficiency, the board options, the power table, the charger |
