# Ridge 3 Lite: bulk capacitor across the battery pads

This capacitor is soldered by hand across `P_BAT+` / `P_BAT-`, next to the XT30
lead. The fab does not fit it. All statuses, stock and prices below were read
on **3 Oct 2026**. DigiKey figures are from digikey.in (INR), as in
`lifecycle.md`. LCSC figures come from `tools/lcsc.py`. I could not read
Mouser from here: it timed out or returned a bot wall.

## What the simulation asks for (sim/README.md, item 4)

* 35 V rating. Pack max is 17.4 V; spikes reach 18.6 V with the capacitor fitted.
* 470 uF or more, ESR 40 mOhm or less at 100 kHz.
* Ripple: 2.3-2.7 A rms at hover, 5.2-5.9 A rms at the worst point (4 ESCs,
  24-48 kHz PWM). Up to 50 °C ambient, in prop wash.
* Radial through-hole, 10 mm diameter or less (8 mm preferred), 20 mm long or less.
* In active production. Stocked.

**Frequency correction.** Ripple is rated at 100 kHz. Both makers' datasheets
derate it to **x0.85 for 20-50 kHz** (Panasonic ZSU-A, Rubycon PZK, for 120 uF
and up). So a "4.0 A" part carries 3.4 A at this board's PWM frequency.

## Recommendation

| | **Primary** | **Alternative** |
|---|---|---|
| MPN | Panasonic **EEH-AZSV681UB** (ZSU-A, polymer hybrid) | Rubycon **35PZK470M10X11** (PZK, polymer hybrid) |
| How many | **1** | **2 in parallel** |
| uF / V | 680 uF / 35 V | 2 x 470 = 940 uF / 35 V |
| Size | 10 x 15.7 mm (16.7 seated), 5 mm pitch, 2.15 g | 10 x 11 mm each (12.5 max per datasheet), 5 mm pitch. DigiKey lists 16.5 mm seated: check the first delivery. |
| ESR (100 kHz, 20 °C) | 11 mOhm | 14 mOhm each, 7 mOhm pair |
| Ripple, 100 kHz | 4.0 A @125 °C, 2.9 A @135 °C | 3.6 A @125 °C each |
| Ripple at 24-48 kHz (x0.85) | 3.4 A @125 °C | 3.06 A each, 6.1 A pair @125 °C |
| Life | 4000 h @125 °C and 4000 h @135 °C (135 °C category) | 4000 h @125 °C |
| Lifecycle | DigiKey **Active**; ZSU-A is in Panasonic's current lineup, datasheet "UPDATE" dated 1 Sep 2025, no NRND/EOL flag | DigiKey **Active**; PZK is in Rubycon's current radial hybrid series list, no discontinued mark |
| Stock | DigiKey 1,740; LCSC 0 (C7271696) | DigiKey 948 (474 boards); not on LCSC |
| Price (DigiKey IN) | Rs 324.87 (1), 218.24 (10), 159.83 (100) | Rs 251.30 (1), 165.97 (10), 119.44 (100) each |
| Covers 2.7 A hover? | **Yes**, even at 125 °C ambient (3.4 A) | **Yes** (1.35 A each against 3.06 A) |
| Covers 6 A worst case? | **Not by the 125 °C rating** (3.4 A). Yes at 50 °C ambient by the thermal estimate below. | **Yes, by the rating** (3.0 A each against 3.06 A, at 125 °C ambient) |

**Choose the primary** if one part on the pads and the lower weight matter more
than having the datasheet cover 6 A. **Choose the alternative** if the owner wants
the 6 A worst case covered by the rating itself. It is a different maker, so it
also gives a second source.

### Why one 680 uF hybrid is enough at 50 °C (this is my inference, not a datasheet figure)

Panasonic rates the same part at 4.0 A @125 °C and at 2.9 A @135 °C. I assume
both ratings take the core to the same limit. Then self-heating is about
1.32 K/A² at 100 kHz, or 1.82 K/A² at 24-48 kHz (x1/0.85²). That puts the core
limit near 146 °C.

| Case, 50 °C ambient, still air | Rise | Core | Life, Panasonic formula L = 4000 x 2^((146 - Tcore)/10) |
|---|---|---|---|
| Hover, 2.7 A | 13 °C | 63 °C | > 1 Mh (capped by the 15-year seal life) |
| Worst, 6 A continuous | 66 °C | 116 °C | ~32,000 h |

Prop wash only lowers these. 116 °C is below the 135 °C category, so a single
part survives even a sustained worst case. A single 470 uF part does not:
Rubycon PZK has no 135 °C rating, and Panasonic EEH-AZSV471UB (2.31 K/A²)
estimates about 133 °C at 6 A. That is why the 470 uF option needs two.

## Everything compared (35 V, radial)

| Part | Type | uF | Size mm | ESR mOhm | Ripple @100 kHz | Life | Status | Stock DigiKey / LCSC | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| **Panasonic EEH-AZSV681UB** (ZSU-A) | hybrid | 680 | 10 x 15.7 | 11 | 4.0 A @125, 2.9 @135 | 4000 h @125/135 | Active | 1,740 / 0 | **Primary** |
| Panasonic EEH-AZSV471UB (ZSU-A) | hybrid | 470 | 10 x 11.7 | 14 | 3.5 A @125, 2.5 @135 | 4000 h | Active | 358 / 0 | Good, but stock is thin (179 boards as a pair) |
| Panasonic EEH-AZS1V471B (ZS-A) | hybrid | 470 | 10 x 15.7 | 11 | 4.0 A @125 | 4000 h | - | 0, 500 due 3 Dec / 10 | Out of stock |
| Panasonic EEH-AZT1V271B (ZT-A) | hybrid | 270 | 10 x 9.5 | 16 | 3.5 A @125 | 4000 h | Active | 0, 500 overdue / 0 | 2 x = 540 uF, 7 A: good, but no stock |
| Panasonic EEH-AZKV391UB (ZKU-A) | hybrid | 390 | 10 x 9.5 | 20 | 2.8 A @125 | 4000 h | Active | 1,016 / - | 2 x = 780 uF, 4.8 A at PWM: short of 6 A |
| Panasonic ZA-A / ZC-A (EEH-AZA1V221B, -AZC1V271B) | hybrid | 220 / 270 | 10 x 9.5 | 20 | 2.5 A @105 / 2.0 A @125 | 10000 h @105 / 4000 h @125 | not checked | - | Lower ripple than ZT/ZS at the same size |
| Panasonic ZK (EEH-ZK1V331P) | hybrid | 330 | 10 x 10.2 | 20 | 2.8 A | 4000 h | - | - | Surface-mount V-chip: fails "radial" (THT version is ZK-A, above) |
| **Rubycon 35PZK470M10X11** (PZK) | hybrid | 470 | 10 x 11 | 14 | 3.6 A @125 | 4000 h @125 | Active | 948 / - | **Alternative (x2)** |
| Rubycon 35PZK390M10X9 (PZK) | hybrid | 390 | 10 x 9 | 20 | 2.8 A @125 | 4000 h | Active | 373 / 0 | 2 x = 4.8 A at PWM: short of 6 A |
| Rubycon 35PZK680M10X15 (PZK) | hybrid | 680 | 10 x 15 | 11 | 4.3 A @125 | 4000 h | Active | 0 / - | Best single part on paper, but no stock |
| Rubycon 35ZLH470MEFC10X16 (ZLH) | wet | 470 | 10 x 16 | 28 (Z) | 1.76 A @105 | 10000 h @105 | Active | 122,573 / 31,547 | Below 2.7 A hover: would need 2-3 |
| Rubycon 35ZLJ470M10X16 (ZLJ) | wet | 470 | 10 x 16 | - | 2.0 A @105 | 9000 h @105 | Active | 5,180 / - | Below 2.7 A |
| Panasonic EEU-FR1V471 / EEUFR1V471L (FR) | wet | 470 | 10 x 16 / 8 x 20 | 28 / 30 | 1.79 / 1.56 A @105 | 8000-9000 h | DigiKey in stock | - / 2,074 (LB) | Below 2.7 A |
| Panasonic EEU-FM1V471 (FM) | wet | 470 | 10 x 20 (22 seated) | 19 (Z) | 2.18 A @105 | 5000 h | in stock | - | Too long, below 2.7 A |
| Panasonic FS 35 V 470 uF | wet | - | - | - | - | - | not found at DigiKey | - | - |
| Nichicon hybrids (GYA-GYF, GWC) | hybrid | - | - | - | - | - | - | - | Nichicon's hybrid catalog is all chip-type: fails "radial". I found no Nichicon "HZ/HD" hybrid series. |
| Chemi-Con HXD / HXE | hybrid | - | - | - | HXD 35 V max 270 uF, 2.5 A @105 | - | - | - | Surface-mount: fails "radial" |
| Würth WCAP-HTG5 / WCAP-HTAH | hybrid THT | - | - | - | - | - | Active | - | No 35 V rating in either series |
| Würth WCAP-PSHP 875115657008 | solid polymer | 120 | 10 x 10.5 | 30 | 3.2 A | - | Active | - | 35 V tops out at 120 uF: needs 4 |

None of the 8 mm parts works. The largest 35 V hybrid in 8 mm is 220 uF
(EEH-AZKV221UB, 35PZK220M8X9). Two of them give 440 uF, short of 470 uF, and
three take more room than one 10 mm part. Every standard (wet) electrolytic
that fits is rated 1.6-2.2 A at 105 °C. That is below the 2.7 A hover current,
as the simulation warned.

## Fitting notes

* Polarity: the stripe goes to `P_BAT-`. Keep the leads short (about 1 nH/mm).
* Two caps (alternative): solder the second cap's legs to the first cap's legs,
  as close to the pads as possible. Keep both lead lengths equal so they share
  the current.
* The standard Panasonic radial vibration rating is 10-55 Hz, 1.5 mm p-p
  (9.1 G). Hold the can down with heat-shrink and a dab of glue/RTV, so the
  leads are not the only support.
* Lead times are long: Panasonic 43 weeks, Rubycon 30 weeks. Buy the run's
  quantity now.

## Sources (all read 3 Oct 2026)

* EEH-AZSV681UB: DigiKey, https://www.digikey.in/en/products/result?keywords=EEH-AZSV681UB (Active, 1,740).
  Panasonic model page: https://na.industrial.panasonic.com/products/capacitors/polymer-capacitors/lineup/polymer-hybrid-aluminum-electrolytic-capacitor/series/142649/model/142864
  ZSU-A series list: https://na.industrial.panasonic.com/products/capacitors/polymer-capacitors/lineup/polymer-hybrid-aluminum-electrolytic-capacitor/series/142649
  Datasheet (frequency factors, life formula): https://industrial.panasonic.com/cdbs/www-data/pdf/RDD0000/ast-ind-156938.pdf
* EEH-AZSV471UB: https://industrial.panasonic.com/ww/products/pt/hybrid-aluminum/models/EEHAZSV471UB ; DigiKey https://www.digikey.in/en/products/result?keywords=EEH-AZSV471UB
* 35PZK470M10X11: DigiKey, https://www.digikey.in/en/products/result?keywords=35PZK470M10X11 (Active, 948, DigiKey # 1189-35PZK470M10X11-ND).
  Rubycon series list: https://www.rubycon.co.jp/en/products/hybrid/
  Datasheet (sizes, ripple, frequency factors): https://www.rubycon.co.jp/wp-content/uploads/catalog-hybrid/PZK.pdf
* Panasonic radial hybrid series pages (ZA-A, ZC-A, ZK-A, ZKU-A, ZS-A, ZT-A): na.industrial.panasonic.com series 135819, 135820, 135822, 135823, 135824, 135825.
* Panasonic lineup: https://industrial.panasonic.com/sa/products/pt/hybrid-aluminum/lineup
* Würth: https://www.we-online.com/en/components/products/pbs/capacitors/aluminium_hybrid_polymer_capacitors/info , .../WCAP-PSHP
* Nichicon hybrid catalog: https://www.nichicon.com/getmedia/bf6a4a11-1a12-49ef-a02a-dfd185bc6e42/e-hybrid_aluminum.pdf
* Chemi-Con HXD: https://chemi-con.com/wp-content/uploads/2021/05/HXD-Series.pdf
