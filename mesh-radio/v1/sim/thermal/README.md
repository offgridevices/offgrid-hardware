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
tools/kd python3 sim/thermal/run.py     # from mesh-radio/v1; about 10-15 min on 4 cores
```

`run.py` reads `src/circuit.py`, `src/parts.py` and `src/placement.json`.
It changes nothing in `src/`. It writes `results.txt`, which holds every
number quoted here, and the five plots. It needs numpy, scipy and
matplotlib, which the pinned image has. `NPROC` sets the number of worker
processes.

**The board is not routed yet.** The copper is an input: a coverage
fraction for each layer, a stitching-via density, and whether the
amplifier's pad joins the top ground pour. When the board is routed, put the
real copper into `PARAMS` at the top of `run.py` and run it again.

## The short version

- **Listening and charging are fine.** One fault needs fixing: the
  charger's own heat reaches its battery-temperature sensor.
- **The amplifier is the problem.** A 1-second LoRa message at 2.5 W or
  3 W heats the QPA9510 past its ratings, even at room temperature, even
  for one message a minute.
  - Most of that heat is a local spike that builds up during the burst
    itself, within 2–3 mm of the chip.
  - So the heat sensor beside it, firmware, a longer board or more board
    area cannot stop that spike.
  - Only a better path for the heat, straight down through the board into
    metal, can.
- **1 W, the US setting, works in a room** for up to one message every
  6 seconds. It does not pass in a 60 °C sealed box unless the board
  changes listed below are made.
- **The board's length is set by its parts, not by heat.** Making it
  10–20 mm shorter or longer moves the hot spot by less than 2 °C.

### Study 1: heat model (E2, E3)

| Case | Verdict | Key numbers (h = 10 W/m²K) |
|---|---|---|
| Listening, −40 to 60 °C | **PASS** | Board about 1 °C above the air |
| Listening at 85 °C | MARGINAL | The 85 °C-rated chips sit 1–2 °C over their limit. That is true of any 85 °C box. |
| 1 W, 1 message/min, 25 °C | **PASS** | Amplifier case 60 °C, junction 82 °C |
| 1 W, 25 % storm, 25 °C | MARGINAL | Case 80 °C (limit 85 °C) |
| 1 W, 1 message/min, 60 °C box | **FAIL** | Case 95 °C, over the 85 °C limit; junction 116 °C, inside the 160 °C allowed with margin |
| 2.5 W, 1 message/min, 25 °C | **FAIL** | Case 121 °C, junction 180 °C (175 °C rating) |
| 3 W, 1 message/min, 25 °C | **FAIL** | Case 149 °C, junction 224 °C |
| Storms (25 %, 50 %) at 2.5–3 W | **FAIL** | The buck-boost and the power switch also pass 125 °C |
| Continuous transmit, any power | **FAIL** | Steady state, with nothing to stop it |
| USB charging, low cell (3.0 V), 25 °C | **FAIL** | See below |
| Battery area while charging, 25 °C | **FAIL** | 53 °C (limit 45 °C), heated by the charger |
| Battery area in a 60 °C box | FAIL, set by the box | The cell is at 60 °C before the radio does anything |

The charging failure works like this:

- The charger's junction would reach 115 °C. It throttles itself at
  100 °C (its TREG limit) and keeps only 83 % of the charge current.
- Its battery-temperature sensor (the NTC, TH1) sits 2.8 mm from the
  charger and reads **60 °C**. That is the charger's own "battery too hot"
  trip, so charging stops and restarts in a loop.

Highest transmit duty that passes, on the board as placed with 1-second
messages and no charging (`max_duty.png`). The battery-at-60-°C limit is
left out, because the box sets it:

| Ambient | 1 W | 2.5 W | 3 W |
|---|---|---|---|
| −40 °C | 50 % | 1 msg / 15 s | none |
| −20 °C | 50 % (h=5: 25 %) | 1 msg / min | none |
| 0 °C | 25 % | none | none |
| 25 °C | 1 msg / 6 s (17 %) | none | none |
| 60 °C | none | none | none |
| 85 °C | none | none | none |

With all of the board fixes (fix 2 below): 1 W runs at 50 % at 25 °C and one message every 15 s at 60 °C; 2.5 W gets one message every 15 s at 25 °C.
With the board fixes and a thermal pad to a metal wall (fixes 2 and 3): 1 W runs continuously at 25 °C and at 50 % at 60 °C; 2.5 W runs at 50 % and 3 W at 25 %, but only at 25 °C. Nothing above 1 W passes at 60 °C.

The amplifier heat path, with its data-sheet values:

- Junction to case: θjc 12.5 °C/W (Qorvo QPA9510 data sheet, 23 Jun 2025,
  p.3, CW). At 3 W the junction alone is 75 °C above the case.
- Case limit: TCASE 85 °C (p.2).
- Junction limit: 175 °C for a 10⁶-hour life (p.2), so 160 °C with the
  15 °C margin.
- The nine 0.3 mm vias, resin-filled with 20 µm plating:
  - **3.8 °C/W** to the first inner layer (In1);
  - **25 °C/W** right through to the bottom.
  - Copper-filled, the second figure would be 6.3 °C/W.
- In 1 second the heat spreads only about 5 mm. Over that time the case
  rises about 20 °C for each watt of heat (the amplifier gives off 1.7 W
  at 1 W out and 4.7 W at 2.5 W out).
- The heat sensor (TMP1075) sees only the slow average: up to 36 °C behind
  the case at 1 W, and 100 °C behind at 2.5 W. Firmware can use it to
  enforce a duty limit, not to protect a single burst.

### Study 2: temperature-rating audit (E1)

| Item | Verdict | Detail |
|---|---|---|
| ICs, crystals, TCXO, passives | **PASS** | All cover −40 to +85 °C; the data sheet for each is cited in `results.txt` |
| Omron B3U buttons (SW2, SW3) | **FAIL** | −25 to **+70 °C**. The owner accepted the cold end, but the hot end is under E1's 85 °C. In a 60 °C box they reach 61–68 °C. |
| JST PH/GH/SH (J2, J3, J5, J6) | accepted | −25 to +85 °C (owner decision 3) |
| Amphenol USB-C | unverified | Distributor listings say −40 or −20 °C |
| X5R capacitors | MARGINAL | Rated to 85 °C exactly. The ones on the amplifier rails (C60, C70, C92, C93, C94) reach 82 °C in a 1 W, 25 % storm at 60 °C, and 120 °C at 2.5 W. |
| Charger NTC window | MARGINAL | The hardware stops charging below about +1.4 °C typical, but a worst-case part charges down to −0.6 °C. It stops above about 59.5 °C (55.6 to 63.8 °C), **not at 45 °C**. |
| 45 °C charging rule | **FAIL as built** | Only firmware enforces it, but the processor cannot read the NTC: CHG_TS goes nowhere else. The NTC is on the board, not on the cell. |

### Study 3: cold start at −40 °C

| Item | Verdict | Detail |
|---|---|---|
| Parts out of range | owner-accepted | Buttons and JST connectors (−25 °C); USB-C unverified |
| 32 MHz crystal start-up | **PASS** | ESR 50 Ω against the nRF52840's 100 Ω limit |
| 32.768 kHz crystal start-up | **PASS** | ESR 70 kΩ against a 100 kΩ limit |
| 32.768 kHz accuracy | MARGINAL | Off by −152 ppm at −40 °C and −130 ppm at +85 °C. The Adafruit core declares it a 20 ppm crystal, so Bluetooth connections can drop when the node is cold or hot. |
| TCXO (−AP code) | **PASS** | −40 to +105 °C, 2 ms start-up |
| TPS63810 loop capacitance | **PASS** | 29.8 µF effective at −40 °C, worst tolerance, against 16 µF needed |
| TPS63810 input capacitance | **PASS** | 24 µF against 5 µF needed |
| TPS62840 loop | **PASS** | Output 13 µF (allowed 3–40 µF); input 5.7 µF (1 µF needed) |
| Battery at −40 °C | note | A LiPo cannot deliver 2–3 A bursts below about −20 °C |
| U.FL, 0908SQ choke, WLCSP solder joints | MARGINAL (shock, not cold) | Stake the U.FL and the choke. Consider underfill for the field build. At 2.5 W, the amplifier swings about 90 °C with every burst. |

### Study 4: size

| Question | Answer |
|---|---|
| Is the length set by heat? | **No.** A 42, 52 or 72 mm board changes the one-message-a-minute peak by 1 °C or less, and the 25 % storm by −4 to +9 °C. |
| Can the amplifier area shrink? | **No.** It needs more copper and a metal heat path, not less area. Cutting copper coverage to 50 % adds 1–9 °C. |

## Fixes, layout and values first

1. **A firmware limit on power and duty (E3).**
   - At 25 °C or below, at 1 W, allow up to one message every 6 seconds.
   - Above 1 W, and in a hot box, allow nothing unless fixes 2 and 3 are
     made.
   - With the board fixes, use the duty table above.
   - The TMP1075 should block transmitting when it reads above
     (85 °C − the burst spike) for the power in use: 49 °C at 1 W on this
     board.
2. **Board changes under the amplifier.** The figures are the case peak at
   2.5 W in a 25 % storm at 60 °C (`fixes.png`):
   - join the pad (pin 17) and the ground pins to the top ground pour with
     a solid connection, not as an island: 206 → 177 °C;
   - copper-filled vias in the pad (via-in-pad, VIPPO): → 184 °C;
   - 2 oz outer and 1 oz inner copper: → 177 °C;
   - solid pours on every layer round the amplifier end, and stitching
     vias at 25 per cm²;
   - **all of these together: 135 °C.**
3. **A thermal pad from the bottom of the board under the amplifier end
   to a metal wall or plate of the enclosure.** Use a 10 × 10 mm gap pad of
   at least 3 W/mK. Keep that bottom area free of parts and open in the
   solder mask.
   - With fix 2, the case drops to **96 °C**.
   - At 25 °C, 1 W is then allowed **continuously**, 2.5 W up to 50 % and
     3 W up to 25 %.
   - In a 60 °C box, 1 W passes up to 50 %: one message a minute gives a
     72 °C case. Nothing above 1 W passes in a 60 °C box.
4. **Charger.**
   - Move TH1 onto the cell, or use a cell with a 10 k NTC lead.
   - Route CHG_TS to a spare nRF52840 analog input, so firmware can apply
     the 0–45 °C rule. The bias is 38 µA, which puts 0.1–1.0 V on the pin.
   - Lower ISET to **300 mA**: R21 from 604 Ω to 1.0 kΩ, a part already on
     the BOM (Yageo RC0402FR-071KL). At 25 °C the charger junction is then
     80 °C, with no throttling, and the NTC reads 50 °C.
   - Or move the charger away from J3 and TH1.
5. **Firmware variant:** declare the 32.768 kHz crystal as 250 ppm
   (`NRF_CLOCK_LF_ACCURACY_250_PPM`), not 20 ppm.
6. **Mechanical:**
   - put a drop of low-loss RF adhesive at the base of the 0908SQ choke;
   - fit a U.FL retention clip;
   - underfill the WLCSPs on field units.

If a part must change:

- **Buttons:** C&K PTS810 SJM 250 SMTR LFS, rated −40 to +85 °C.
  - DigiKey CKN10502CT-ND; check the stock.
  - C&K is a US company.
  - Its footprint is 4.2 × 3.2 mm, against the B3U's 3.0 × 2.5 mm.
- **47 µF capacitors on the amplifier rail (C93, C94):** TDK
  C3216X7S0J476M160AC.
  - Its X7S dielectric is rated −55 to +125 °C, but it is a larger 1206
    package.
  - DigiKey 445-8037-1-ND.
  - TDK is a Japanese company.
- **More than 1 W for 1-second messages:** this needs a power amplifier
  rated for continuous output, with a large metal tab.
  - The QPA9510 is a GSM handset part. Its data are taken at 37.5 % duty
    of 577 µs time slots.
  - No candidate was checked for stock in this study.
  - Until fixes 2 and 3 are measured on a built board, treat 1 W as the
    field limit.
- **Charger, optional:** a switching charger with programmable
  battery-temperature (JEITA) thresholds, such as one of TI's BQ2562x
  family. It would cut the 1 W of charger heat to about 0.2 W. Its stock
  has not been checked.

## Follow-up, 19 Oct: data-sheet efficiency, 6 layers, power per board option

`followup.py` uses the same model and the same pass criteria as `run.py`,
with h = 10 W/m²K and no charging. It writes `results_followup.txt` and
`power_table.png`.

```
tools/kd python3 sim/thermal/followup.py     # about 20 min on 3 cores
```

### The amplifier's efficiency

**Nominal case: the QPA9510 data sheet (23 Jun 2025), p.4, "PAE vs.
Average Output Power".** PAE is the power-added efficiency: the share of
supply power that becomes RF. The curve used is the 915 MHz one, measured
at:

- VCC = 3.6 V and VAPC = 2.8 V;
- quiescent current 215 mA, 25 °C, 50 Ω;
- GSM bursts: Pin +4.5 dBm at 37.5 % duty (p.3).

Read off that curve:

- PAE is 31.5 % at 30 dBm, 45 % at 33 dBm, 56 % at 35 dBm, and peaks at
  57.5 % at 35.5 dBm.
- That cross-checks with p.3: 35.4 dBm at 1.7 A from 3.6 V is 56.7 %.
- The current at 3.6 V is 0.88 A at 30 dBm, 1.23 A at 33 dBm and 1.57 A at
  35 dBm.

How the curve is applied:

- The amplifier must deliver the antenna power plus 1.1 dB, the loss to
  the U.FL found by `sim/rf`.
- Firmware sets VPA so the amplifier works at its 35 dBm-equivalent point,
  within 2.7–4.0 V. This assumes a saturated amplifier keeps its PAE when
  VCC and the output scale together.
- On that basis the amplifier gives off **1.36 / 1.43 / 2.02 / 2.54 /
  3.13 W** at 30 / 31.5 / 33 / 34 / 35 dBm at the antenna.

**Pessimistic case: the plan's supply power.** The amplifier then gives off
1.41 / 1.88 / 2.62 / 3.96 / 5.13 W.

### Highest dBm at the antenna that passes

Each cell is the nominal / pessimistic result. "–" means not even 30 dBm
passes. A storm is 1 s on and 3 s off.

{{FUTABLE}}

### Which fix helps most

Starting from the plain 6-layer board, the case peak at 25 °C (34 dBm, one
1 s packet a minute) changes as follows:

| Change | Case peak |
|---|---|
| Plain 6-layer board | 70 °C |
| Join the pad to the top pour | 60 °C (−10) |
| Copper-filled pad vias | 59 °C (−11) |
| Dense stitching vias and 85 % pours | −1 °C |
| 2 oz outer copper on its own | −1 °C |
| All the fixes together | 52 °C |
| All the fixes with 2 oz outer copper | 47 °C |
| All of that plus the gap pad | 43 °C |

The gap pad helps most in storms: at 60 °C and 30 dBm, the case drops from
84 to 71 °C. The two pad fixes help only together with copper to spread
the heat into. On its own, 6 layers is worth 8–9 °C over 4 layers as
placed. The 4-layer board with fixes and 2 oz outer / 1 oz inner copper
matches the 6-layer board with 2 oz outer copper (45 °C).

### The charger again, 4-layer as placed

{{FUCHG}}

## Model

- **Copper layers.** Four sheets: F 35 µm at 70 % coverage, In1 15 µm at
  100 %, In2 15 µm at 50 %, B 35 µm at 70 %. FR-4 between them is
  0.21 / 1.065 / 0.21 mm (JLC04161H-7628), with a conductivity of
  0.29 W/mK through the board and 0.81 W/mK along it.
- **Grid and vias.** A 0.5 mm grid. Stitching vias at 8 per cm², each
  0.2 mm with 20 µm plating.
- **Amplifier pad.** The 1.5 mm pad is an island of copper on F, joined to
  the board only through its nine vias. The solder is 50 µm of SAC305
  wetting 60 % of the pad.
- **Bluetooth antenna area.** No copper.
- **Cooling.** Convection h = 10 or 5 W/m²K on both faces, plus radiation
  at emissivity 0.9, linearised 20 K above the air.
- **Heat sources** sit at their parts' positions from `placement.json`:
  - PA heat is VCC × ICC minus the RF power out, using 1.0 A at 2.7 V,
    2.0 A at 3.6 V and 2.3 A at 4.0 V from the plan.
  - TPS63810 efficiency: 92 / 89 / 87 %, from its Fig. 32/33 less two
    points for boosting from a 3.4 V cell.
  - FET resistance (RON) losses in the TPS2121 (90 mΩ), the reverse FET
    (62 mΩ), the protection FETs, the sense resistor and the JST contacts.
  - Filter and switch losses from `sim/rf`.
  - SX1262 at +20 dBm: 102 mA (rev 1.2, Table 3-6) with the pad
    dissipation.
  - Charger: (5.0 V − VBAT) × 497 mA, plus the Schottky and the eFuse.
- **Junction temperatures** are the board under the part plus ψJB × the
  part's power, using each data sheet's ψJB:
  - TPS63810 20.5, TPS2121 15.5, BQ25185 34.7, TPS62840 39.4 and
    TPS25947 27.6 °C/W;
  - the FemtoFET and the SOD-123FL diode are assumed at 30 and 60 °C/W.
- **Transients.** Implicit Euler, run to a periodic steady state. The peak
  is taken at the end of the 1 s burst.

## Not verified (assumptions)

- **Copper and vias.** The coverage, via plating, resin fill, solder voids
  and the pad island are all assumptions. The routed board decides them.
  - Joining the pad to the top pour is worth up to 36 °C, so the routing
    matters a great deal.
- **Heat capacity.** Only the amplifier package is counted. Leaving out
  the other parts' heat capacity makes the burst peaks somewhat too high.
- **Amplifier supply current at each power level** is the plan's
  estimate, not a measurement. `sim/rf` says 35 dBm at the U.FL needs
  36.3 dBm from the amplifier. If the DC current stays the same, the
  amplifier then dissipates less, about 1.1 W less at 3 W.
- **Junction-to-board values** for the CSD25485F5 and the RB060MM, and
  the TPS63810 efficiency in deep boost.
- **The TS bias current.** It is taken to be ITSMR, 38 µA, and the NTC's
  1 % and B-value tolerances are not included.
- **The cell.** It is not modelled. "Cell area" means the board under J3.
- **Ratings marked `d` in `results.txt`:** passive series specifications,
  Hirose U.FL, Amphenol USB-C, Coilcraft 0908SQ, Lite-On LEDs, C&K slide
  switch and Toshiba SSM3K56ACT. These come from series data or
  distributor listings; no copy of their data sheets was read here.
- **Hirose U.FL-R-SMT-1(80).** LCSC flags it "not recommended for new
  designs". Check its lifecycle.

## Files

| File | What it is |
|---|---|
| `run.py` | The model and all four studies |
| `results.txt` | Every number |
| `thermal_map.png` | The board at the end of a 2.5 W burst, 25 % storm, 60 °C |
| `pa_burst.png` | Amplifier junction and case through one storm period |
| `max_duty.png` | Highest allowed duty against ambient |
| `charging.png` | Charger junction and throttling against ambient |
| `fixes.png` | Effect of each fix on the amplifier case |
| `followup.py`, `results_followup.txt`, `power_table.png` | The 19 Oct follow-up: data-sheet efficiency, 6-layer options, the power table, the charger at lower current |
