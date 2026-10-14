# Ridge 3 Lite (ridge3-lite v1): sourcing for a 10,000-board run

The owner's requirement: "if we produce 10,000 of these boards, we won't have
a snafu", and every part must be "in production today and readily available".

This audit builds on `lifecycle.md`, which established that every part is in
production. It does not repeat that work. It asks a different question: can
the run's quantity be bought, from whom, and how long the wait is.

All figures were read on **3 Oct 2026**.

## Method

* **Quantity per board** is the ref count per `PARTS` key from
  `circuit.build()` (run in the `tools/kd` container).
* **Need for 10k** = qty/board x 10,000 x 1.02 (2 % attrition).
* **Stock sources:**
  * **LCSC / JLC:** `tools/lcsc.py`. The JLC figure is normally the larger one
    and includes LCSC's.
  * **DigiKey:** the digikey.in product page. It gives stock, Product Status,
    "Manufacturer Standard Lead Time" and standard package. Some figures come
    from Octopart's DigiKey feed (marked "oct").
  * **Mouser, Arrow, Avnet, Future, Newark, TME, Rutronik, TTI:** Octopart
    search pages, which carry those distributors' API data. Each offer was
    timestamped 2-3 Oct 2026. mouser.com itself returned a bot wall.
  * **Avnet lead times:** Findchips.
  * **TI direct stock:** TI's store inventory endpoint
    (`ti.com/storeservices/cart/opninventory?opn=...`).
* **Counting rules:**
  * Only authorised channels are counted.
  * Verical is Arrow's marketplace and shows Arrow's stock, so it is not
    counted again. The same goes for Onlinecomponents.com, which is Master
    Electronics.
  * Independent and broker stock (Win Source, Chip Stock, Worldway and others)
    is not counted. It is mentioned only where it is large. Clone listings
    under the same number were found and excluded: VBsemi "...-VB", HXY
    "ICM-42688P-HXY", and the TOKMAS "ICM-42688-P(TOKMAS)" C54308212 at LCSC.
    None of them is the maker's part.
* **Verdicts:**
  * **OK:** more than 2x the need in stock across the channels, or a commodity
    with many drop-in sources (two are named).
  * **LEAD-TIME:** the run needs a factory order of a normal length.
  * **RISK:** single source, stock well short, lead time over 16 weeks, or
    constrained supply.

## Table

Need = qty x 10,200. "k" = thousand. Lead time is the maker's standard lead
time as DigiKey or Avnet states it.

### ICs

| Part | MPN | Qty/board | Need for 10k | Stock by channel | Lead time | Second source(s) | Verdict |
|---|---|---|---|---|---|---|---|
| STM32G473 | STM32G473CEU6 | 1 | 10,200 | LCSC 1,183 / JLC 1,488; DigiKey 0 ("in-stock date unavailable due to market conditions"); Future 6,350; Newark 39; Avnet, Arrow 0. Total about 7.9k | DigiKey 52 wk; Avnet 30-53 wk; tray | STM32G484CEU6 (same UFQFPN-48 pinout, G474 + AES): Mouser 2,705, DigiKey 1,200 (oct). STM32G474CEU6: LCSC C1235412 215, almost none at distributors | **RISK** |
| ICM42688P | ICM-42688-P | 1 | 10,200 | LCSC 4,362 / JLC 4,645; DigiKey 0 (5,000 due 3 Aug 2027); Mouser, Newark, Avnet 0. Total about 4.6k | DigiKey 45 wk; Avnet 52 wk; reel 5,000 | **Bosch BMI270**: LCSC C2836813 1,122; DigiKey 52,986; Mouser 73,591; Future 4,000. ST LSM6DSV16XTR: LCSC C5267406 7,974; Mouser 4,028 | **RISK** |
| STM32G071G | STM32G071GBU6 | 4 | 40,800 | LCSC 1,001 / JLC 1,001; Mouser 4,922 (+96 reel); Newark 5,473-6,781; Avnet 980; Maritex 555; DigiKey 9. Total about 13-14k | DigiKey 52 wk; Avnet 53 wk; reel 3,000, tray 490 | **STM32G071G8U6**: LCSC C724080 953; Arrow 3,582; Mouser 1,328; DigiKey 26. Total about 5.9k | **RISK** |
| DRV8300D | DRV8300DRGER | 4 | 40,800 | TI direct 337,906; DigiKey 57,168; Mouser 34,260; LCSC 15,202 / JLC 15,248 | 20 wk; reel 3,000 | not needed | OK |
| INA186A3 | INA186A3IDCKR | 4 | 40,800 | TI direct 85,786; DigiKey 9,015; Mouser 8,654; LCSC 5,727. Total about 109k (2.7x) | 20 wk; reel 3,000 | not needed | OK |
| LMR36506R5 | LMR36506R5RPER | 1 | 10,200 | TI direct 11,260; DigiKey 3,087; Mouser 3,255; LCSC 1,010. Total about 18.6k (1.8x) | 12 wk; reel 3,000 | none pin-compatible at the same rating | LEAD-TIME |
| TLV76733 | TLV76733DRVR | 2 | 20,400 | TI direct 37,986; LCSC 25,205 / JLC 26,424; Mouser 324; DigiKey 0 (3,000 due 14 Dec 2026). Total about 64k (3.2x) | 20 wk; reel 3,000 | not needed | OK |
| TPS7A1601 | TPS7A1601DRBR | 1 | 10,200 | Mouser 6,760; TI direct 4,542 (the TI product page itself said "out of stock"); LCSC 2,670 / JLC 2,691; DigiKey 4. Total about 14k (1.4x) | 12 wk; reel 3,000 | none pin-compatible at 60 V | LEAD-TIME |
| USBLC6 | USBLC6-2SC6 | 1 | 10,200 | JLC 48,900; Future 168k; TME 141k; Newark 75k; Avnet 45k; Arrow 24.6k | Avnet 25 wk | not needed | OK |

### Discretes, connector, switch

| Part | MPN | Qty/board | Need for 10k | Stock by channel | Lead time | Second source(s) | Verdict |
|---|---|---|---|---|---|---|---|
| TPN2R304PL | TPN2R304PL,L1Q | **24** | **244,800** | Newark 22,120; DigiKey 10,515; Mouser 6,959; LCSC 2,315; Avnet, Arrow, TTI 0. Total about 42k (17 %) | 24 wk (DigiKey and Avnet); MOQ and reel 5,000 | **Infineon BSZ018N04LS6ATMA1**: about 65k (Mouser 33,989, DigiKey 14,920, Arrow 5,625, Newark 5,383, Avnet 5,000; LCSC C534643 42). onsemi NTTFS002N04CLTAG: about 12k (Rochester 6,000, Avnet 3,000, Mouser 2,468, DigiKey 347; LCSC C900330 0) | **RISK** |
| AO3400A | AO3400A | 1 | 10,200 | JLC 953,763 (Basic); DigiKey 292k; TME 44k | - | Vishay SI2302CDS-T1-GE3 (C10488, 91k; 20 V, same G-S-D pinout); UMW AO3400A | OK |
| SMF22A | SMF22A-TP (MCC) | 1 | 10,200 | LCSC 3,650 / JLC 3,652; DigiKey 3,422 ("unable to accept backorders due to temporary constrained supply"); Arrow 0. Total about 7k (0.7x) | not stated | **Eaton SMF22A** (SOD-123FL): DigiKey 8,817, Active, 34 wk. **Littelfuse SMF22A** (SOD-123FL): Arrow about 7.4k, CoreStaff 2,940. TSC SMF22A: DigiKey 19,748, Mouser 7,579, Active, 20 wk (DigiKey lists the case as SOD-123W, so check the land) | **RISK** (this MPN alone) |
| SS1040HE | SS1040HEWS_R1_00001 | 1 | 10,200 | LCSC 9,960 / JLC 9,968; Maritex 34,749; Mouser 8,527; DigiKey not stocked. Total about 53k | DigiKey 16 wk; MPQ 50,000 | ROHM RBR1VAM40ATR (ROHM's SOD-323HE successor; not at LCSC) | OK |
| LED_RED | LTST-C191KRKT | 1 | 10,200 | JLC 201,861; Future 1.245M; Avnet 285k; TME 84k; Arrow 80k | Avnet 14-20 wk | Hubei KENTO KT-0603R (C2286, 4.8M; check the cathode mark against pad 1) | OK |
| LED_BLUE | LTST-C191TBKT | 1 | 10,200 | JLC 376,711; Future 365k; Mouser 310k; Avnet 120k; DigiKey 13k | Avnet 14 wk | none needed | OK |
| XTAL8M | ECS-80-10-33-CHN-TR3 | 1 | 10,200 | DigiKey 19,081; Mouser 6,076; LCSC 3,435; Arrow 3,000. Total about 31.6k (3.1x) | DigiKey 19 wk; reel 3,000 | Yajingxin TAXM8M4RDBCCT2T (C400090, 178,900; 8 MHz 10 pF +/-10 ppm 3225, 250 ohm); JLYE Y32258MEBCX (C49158085, 25,730; 8 MHz 10 pF +/-10 ppm 3225). The load is the same 10 pF, so C12P stays. | OK |
| L10U | SWPA3015S100MT | 1 | 10,200 | JLC 57,308 (the LCSC API returned no record); DigiKey 608 | DigiKey 16 wk; reel 2,000 | TDK VLS3015CX-100M-1 (C2044430, 2,775; plus about 27k at Mouser, Arrow, Future and TTI; 0.92 A sat, 239 mOhm). cjiang FNR3015S100MT (C167757, 32,820; 0.92 A, 325 mOhm). Both 3 x 3 x 1.5. | OK |
| SHUNT_0M5 | HCS1206FTL500 | 4 | 40,800 | DigiKey 28,022; Future 4,000; LCSC 1,753 / JLC 1,927; Avnet 0. Total about 34k (0.83x) | 17 wk (DigiKey and Avnet); reel 2,000 | Milliohm HoSRX1206-2W-0.5mR-1% (C18724160, 9,005; 2 W, 1 %, +/-50 ppm). Yezhan ASH-M-1206-0.5F (C521527, 31,670; 1.5 W, 1 %). Neither has a published maker lifecycle; check the land (below). | **RISK** |
| USBC | USB4110-GF-A | 1 | 10,200 | **DigiKey 142,346; Mouser 210,699**; Future 19,200; TME 12,697; Newark 6,933; Rutronik 2,400; **LCSC 0 / JLC 424** | DigiKey 7 wk; reel 1,200 | HRO TYPE-C-31-M-22 (C530612, 3,393): the same land; see below | OK, but short at JLC |
| BOOTSW | B3U-1000P | 1 | 10,200 | JLC 140,464; Arrow 402,500; Rutronik 182,000; TTI 21,000; Mouser 9,774 | Findchips 4 wk | none needed | OK |

### Resistors

These are commodities: every row is OK. Second sources are the same value,
size and tolerance.

| Part | MPN | Qty/board | Need for 10k | Stock by channel | Lead time | Second source(s) | Verdict |
|---|---|---|---|---|---|---|---|
| R10R_0402 | 0402WGF100JTCE | 1 | 10,200 | JLC 1.75M (Basic) | - | Yageo RC0402FR-0710RL (C138066, 1.33M); Panasonic ERJ-2GEJ100X (289k) | OK |
| R10K | 0402WGF1002TCE | 13 | 132,600 | JLC 21.7M (Basic) | - | Yageo RC0402FR-0710KL (C60490, 8.7M); Panasonic ERJ-2RKF1002X (9.1M) | OK |
| R82K | CRCW040282K0FKED | 1 | 10,200 | JLC 30,482; Arrow 1.7M; Avnet 1.42M; TTI 840k | 11-20 wk | Yageo RC0402FR-0782KL (C137932, 5.6k); Panasonic ERJ-2RKF8202X (206k) | OK |
| R100K | 0402WGF1003TCE | 5 | 51,000 | JLC 8.24M (Basic) | - | Yageo RC0402FR-07100KL (C60491, 9.05M); Panasonic ERJ-2RKF1003X (2.84M) | OK |
| R22R_0201 | RC0201FR-0722RL | 12 | 122,400 | JLC 1.37M; Rutronik 5.58M | 12 wk | FOJAN RC-01W22R0FT (C320768, 492k); Panasonic ERJ-1GNF22R0C (853k) | OK |
| R10R_0201 | RC0201FR-0710RL | 13 | 132,600 | **LCSC 0 / JLC 73,666 (0.56x)**; Rutronik 12.35M; Arrow 5.2M; Future 560k | 12 wk | FOJAN RC-01W10R0FT (C304508, 34k); Panasonic ERJ-1GNF10R0C (419k) | OK (commodity; JLC short) |
| R100R_0201 | RC0201FR-07100RL | 1 | 10,200 | JLC 2.16M | - | UNI-ROYAL 0201WMF1000TEE (C270366, 504k); Panasonic ERJ-1GNF1000C (C717000; 470k) | OK |
| R330_0201 | RC0201FR-07330RL | 1 | 10,200 | JLC 1.42M | - | UNI-ROYAL 0201WMF3300TEE (C516485, 96k); Panasonic ERJ-1GNF3300C (332k) | OK |
| R1K_0201 | RC0201FR-071KL | 6 | 61,200 | JLC 2.31M | - | UNI-ROYAL 0201WMF1001TEE (C270365, 1.76M); Panasonic ERJ-1GNF1001C (500k) | OK |
| R1K5_0201 | 0201WMF1501TEE | 4 | 40,800 | LCSC 0 / JLC 80,490 (1.97x) | - | FOJAN RC-01W1501FT (C304512, 20k); Yageo AF0201FR-071K5L (C850744, 13k); Samsung RC0603F152CS (Avnet 15k) | OK (commodity) |
| R2K2_0201 | RC0201FR-072K2L | 12 | 122,400 | JLC 1.32M; Arrow 10.3M | 12 wk | UNI-ROYAL 0201WMF2201TEE (C473508, 278k); Panasonic ERJ-1GNF2201C (649k) | OK |
| R5K1_0201 | RC0201FR-075K1L | 2 | 20,400 | JLC 139k | - | FOJAN RC-01W5101FT (C320937, 174k); UNI-ROYAL 0201WMF5101TEE (C270344, 74.6k) | OK |
| R10K_0201 | RC0201FR-0710KL | 23 | 234,600 | JLC 2.44M; Future 55.6M | 12 wk | UNI-ROYAL 0201WMF1002TEE (C473048, 9.97M); Vishay CRCW020110K0FKED (C844303, 181k) | OK |
| R27K_0201 | RC0201FR-0727KL | 1 | 10,200 | JLC 35,212 | - | UNI-ROYAL 0201WMF2702TEE (C270351, 33k); Yageo AC0201FR-0727KL (C226489, 9.7k) | OK |
| R62K_0201 | RC0201FR-0762KL | 1 | 10,200 | JLC 21,661 (2.1x) | - | FOJAN RC-01W6202FT (C320989, 14k); Panasonic ERJ-1GNF6202C (C2073881; 120k) | OK |

### Capacitors

These are commodities: every row is OK. Second sources are the same value,
size, dielectric and voltage rating.

| Part | MPN | Qty/board | Need for 10k | Stock by channel | Lead time | Second source(s) | Verdict |
|---|---|---|---|---|---|---|---|
| C12P | 0402CG120J500NT | 2 | 20,400 | JLC 1.97M (Basic) | - | Samsung CL05C120JB5NNNC (C26406; 10.6M); Murata GRM1555C1H120JA01D (C76948, 48k) | OK |
| C100N_0201 | CL03A104KO3NNNC | 26 | 265,200 | JLC 1.16M; Future 1.42M; Avnet 120k | Avnet 30 wk | Murata GRM033R61C104KE84D (C76937; 1.49M); TDK C0603X5R1C104K030BC (87k) | OK |
| C1U_0201 | GRM033R61A105ME44D | 1 | 10,200 | JLC 785k; Arrow 75k | 10 wk | Samsung CL03A105MP3NSNC (C170153, 411k; Future 320k); CGA0201X5R105M100ET (C6119758, 221k) | OK |
| C100N_50 | CL05B104KB54PNC | 2 | 20,400 | JLC 12.47M (Basic) | - | Murata GRM155R71H104KE14D (C77020, 2.3M); TDK C1005X7R1H104K050BB (6.2M) | OK |
| C1U_25 | CL05A105KA5NQNC | 15 | 153,000 | JLC 5.6M (Basic) | - | Murata GRM155R61E105KA12D (C77009, 299k); TDK C1005X5R1E105K050BC (1.87M) | OK |
| C4U7_0402 | CL05A475MP5NRNC | 2 | 20,400 | JLC 2.36M (Basic) | - | Yageo CC0402MRX5R6BB475 (C469468, 135k); TDK C1005X5R1A475K050BC (8.8M) | OK |
| C10U_25 | CL10A106MA8NRNC | 5 | 51,000 | JLC 3.34M (Basic) | - | Murata GRM188R61E106MA73D (C91606, 638k); Yageo CC0603MRX5R8BB106 (C596327, 91k) | OK |
| C4U7_25 | CL21A475KAQNNNE | 2 | 20,400 | JLC 3.03M (Basic) | - | Murata GRM21BR61E475KA12L (C77077; 102k); TDK C2012X5R1E475K125AB (131k) | OK |
| C22U_25 | GRM21BR61E226ME44L | 2 | 20,400 | JLC 351k; Future 2.18M | 10 wk | Samsung CL21A226MAQNNNE (C45783, 3.98M); Yageo CC0805MKX5R8BB226 (C784585, 162k) | OK |
| C4U7_50 | GRM21BZ71H475KE15L | 14 | 142,800 | **LCSC 100,000 / JLC 117,516 (0.82x)**; Future 108k; Avnet 72k; TME 22.7k; Newark 17.4k; Arrow 12k. Total about 349k (2.4x) | 10 wk; reel 3,000 | TDK C2012X7R1H475K125AC (240k); CCTC TCC0805X7R475K500FT (C20416422, 69.8k) | OK (JLC short) |

### Board-level bulk capacitor (hand-fitted, from `bulk-capacitor.md`)

| Part | MPN | Qty/board | Need for 10k | Stock by channel | Lead time | Second source(s) | Verdict |
|---|---|---|---|---|---|---|---|
| BULK (primary) | Panasonic EEH-AZSV681UB | 1 | 10,200 | DigiKey 1,740; Newark 937; Arrow 42; LCSC 0 | **43 wk**; box 500 | the Rubycon option below | **RISK** |
| BULK (alternative) | Rubycon 35PZK470M10X11 | 2 | 20,400 | DigiKey 948; nothing else found | **30 wk** | the Panasonic option above | **RISK** |

## The risk parts in detail

### TPN2R304PL (24 per board, 244,800 for the run)

* **Toshiba's own stock:** Toshiba publishes no stock of its own. The product
  page's "Stock Check & Purchase" link goes to the netCOMPONENTS list of
  distributors (`toshiba.semicon-storage.com/us/semiconductor/where-to-buy/stockcheck.TPN2R304PL.html`).
* **Orderable part and lead time:** the orderable part is `TPN2R304PL,L1Q`,
  MOQ 5,000 (one reel). Both DigiKey and Avnet give a 24-week standard lead
  time.
* **Channel stock:** about 42k, or 1,700 boards' worth.
* **Broker stock:** brokers list about 275k more (Component Stockers 61.8k,
  Anlinkda 96k and others). It is not counted: provenance is unverified.

**Second sources checked** (Toshiba: 2.3 mOhm max at 10 V, Qg 41 nC, Qgd 6.2
nC, Qoss 27 nC, Coss 650 pF, internal Rg 0.5 ohm):

| Candidate | RDS(on) max at 10 V | Qg at 10 V (vs 41) | Qgd | Coss / Qoss | Int. Rg | Package | Stock / lead | Result |
|---|---|---|---|---|---|---|---|---|
| **Infineon BSZ018N04LS6ATMA1** | 1.8 mOhm | 31 nC (-24 %) | 3.8 nC | 690 pF / 34 nC | 1.3 ohm | PG-TSDSON-8 FL, 3.3 x 3.3 | about 65k authorised; DigiKey 52 wk | **Use: second source** |
| onsemi NTTFS002N04CLTAG | 2.2 mOhm | 49 nC (+20 %) | 7.4 nC | 1,260 pF / - | - | WDFN8 (u8FL) 3.3 x 3.3, case 511DY | about 12k | Third source; low stock |
| onsemi NTTFS002N04CTAG | 2.0 mOhm (JLC) | 34 nC | - | - | - | WDFN8 3.3 x 3.3 | DigiKey 670 | No: no stock |
| Infineon BSZ021N04LS6 | 2.1 mOhm | 31 nC | - | - | - | TSDSON-8 FL | about 2.9k | No: no stock. "BSZ022N04LS6" does not exist. |
| Vishay SiSS42DN | **14.4 mOhm, 100 V** | - | - | - | - | PowerPAK 1212-8S | - | No: wrong part for this job |
| Vishay SiSS12DN-T1-GE3 | 1.98 mOhm | **59 nC (+44 %)**; the 28.7 nC usually quoted is at 4.5 V | 7.6 nC | 680 pF / 28 nC | 1 ohm | PowerPAK 1212-8S | about 30.6k | No: Qg is out of the +/-30 % window |
| AOS AONR32340C | - | - | - | - | - | - | not found at Octopart, Findchips or JLC | No: no such orderable part found |

**Footprint (pad map).** I compared JLC/EasyEDA's own land for each part. The
board's `og:TSON-8...` footprint is one of these. The datasheet outlines
agree.

* **The same on all three:**
  * pinout: 1-3 source, 4 gate, 5-8 drain, plus the exposed drain pad;
  * pin pitch 0.65 mm;
  * gate in the same corner.
* **Row spacing:** Toshiba's land puts the source row 3.35 mm from the drain
  row. Infineon's and onsemi's put it 3.20 mm away. Each source pad would sit
  0.15 mm off the terminal's centre. The Toshiba pad is 0.60 mm long, so it
  still covers most of a 0.30-0.51 mm terminal.
* **Exposed pad:** it fits inside the board's 2.70 x 2.30 mm drain pad.
  Infineon's is 2.19-2.39 x 2.01-2.21; onsemi's land is 2.40 x 2.30.
* **Side drain pads:** Toshiba's land has two 0.4 x 0.6 mm side drain pads
  for TSON Advance's flank terminals. The other two packages have no terminal
  there. That copper is harmless, but its paste would make solder balls.

So the FETs are **pin-compatible**, and the existing land works. For a
qualified second source, make a **union land**:

* extend each source pad 0.15 mm towards the package centre (0.75 mm long;
  0.40 mm left to the exposed pad);
* drop paste on the two side drain pads.

That one land then suits all three makers.

**Switching (qualitative).** Today: 22 ohm high-side and 10 ohm low-side gate
resistors. They hold the switch node to 1.85 V/ns, against the DRV8300D's
2 V/ns limit, and the low-side drain to 32-39 V (circuit.py, sim/halfbridge).

* **Infineon BSZ018N04LS6:**
  * **Faster edges.** Its Qgd is about 40 % lower (3.8 vs 6.2 nC), so the
    Miller plateau is shorter. With the same 22 ohm, and counting its higher
    internal Rg, the plateau is about 37 % shorter: dv/dt is about 1.6x, or
    roughly 2.9 V/ns. That is over the DRV8300D's 2 V/ns, with more drain
    overshoot.
  * **New resistors.** First estimate, same Qgd x R product: about 33 ohm
    high side and about 15 ohm low side. Confirm by re-running
    `sim/halfbridge` and on the bench.
  * **Lower losses elsewhere.** Its lower Qg (31 nC) eases the bootstrap and
    the TPS7A1601 load.
  * **Output charge.** Its Qoss is a little higher (34 vs 27 nC): slightly
    more switching loss at 24-48 kHz.
* **onsemi NTTFS002N04CL:**
  * Qg and Qgd are about 20 % higher, so the edges are slower. The existing
    resistors are safe for dv/dt, but switching loss goes up.
  * Coss is about 2x (1,260 pF), which adds Coss loss and hard-switching
    current.
  * The resistors could come down slightly; this needs simulation.
* **Mixing makers:** never mix makers on one board. Build each lot with one
  maker and its own resistor values. AM32 dead time (DEAD_TIME 60) and the
  DRV8300D's 215 ns cover both parts' turn-off delays, but check them in the
  same run.

### STM32G071GBU6 (4 per board, 40,800)

* **Stock and lead time:** about 13-14k in authorised channels. The lead time
  is 52-53 weeks.
* **Drop-in alternate: STM32G071G8U6.** The board flashes AM32's
  `GEN_64K_G071` target, which defines `SIXTY_FOUR_KB_MEMORY`. Its linker
  puts the application in 62 KB above the 4 KB bootloader. So the 64 KB
  STM32G071G8U6 (same die family, same UFQFPN-28 pinout, same footprint) runs
  the same two hex files, with no PCB or firmware change.
* **Both together:** about 19-20k, which is enough for half the run.
* **Rejected alternates:**
  * The "N" parts (STM32G071GBU6N, G8U6N) are the USB-PD product version.
    They have no authorised stock.
  * STM32G031 has no comparators, and AM32's G071 port uses them. It is not a
    drop-in.

### STM32G473CEU6 (1 per board, 10,200)

* **Stock and lead time:** about 7.9k in authorised channels: Future 6,350
  and LCSC 1,488. The lead time is 30-53 weeks.
* **Alternate: STM32G484CEU6.** It is the same UFQFPN-48 pinout (G474 + AES),
  512 KB. It should run the board's `STM32G474` Betaflight image, which is
  380 KB, so a 256 KB G473CC will not do. Stock: Mouser 2,705, DigiKey 1,200.
  Check one board first.

### ICM-42688-P (1 per board, 10,200)

* **Stock and lead time:** no authorised distributor has it. DigiKey's next
  5,000 arrive 3 Aug 2027, and the lead time is 45-52 weeks. LCSC's 4.6k is
  the only real stock.
* **Replacement: Bosch BMI270.** About 127k at DigiKey and Mouser, plus 1,122
  at LCSC (C2836813). It is LGA-14 2.5 x 3.0 at 0.5 mm pitch, with the same
  pad order. EasyEDA's land for it is slightly smaller: pads 0.60 x 0.27 at
  +/-1.17 mm against the board's 0.68 x 0.28 at +/-1.26 mm. The board's land
  fits it, so **the footprint is the same**.
* **Pins:** they match functionally:
  * 1 SDO = MISO; 4 INT1; 5 VDDIO; 6 GND; 7 GND; 8 VDD; 12 CS; 13 SCK;
    14 SDI.
  * Pins 2, 3, 10 and 11 (aux interface) stay open.
  * Pin 9 is tied to GND for the ICM's FSYNC. On the BMI270 it is INT2, an
    output that stays disabled unless firmware enables it, and Betaflight does
    not. Check pins 2/3/10/11 against Bosch's pin table before release.
* **Firmware:**
  * Add `USE_ACCGYRO_BMI270` to `firmware/betaflight/RIDGE3LITE/config.h`.
    The land and wiring take either chip, but their axes are 90 degrees apart, so each needs its own
    Betaflight build (RIDGE3LITE for the ICM-42688-P, a BMI270 build with GYRO_1_ALIGN_YAW 2250);
    see gyro-second-source.md.
  * The BMI270 runs a 3.2 kHz gyro loop, against the ICM's 8 kHz: lower
    performance, but the most common Betaflight gyro.
  * Its axes relative to pin 1 may differ from the ICM's. Re-run
    `firmware/gyro_orientation_check.py` and set `GYRO_1_ALIGN` for each
    gyro.
* **Third choice: ST LSM6DSV16XTR.** It has the same land, but only about 12k
  in stock.

### HCS1206FTL500 shunt (4 per board, 40,800)

* **Stock and lead time:** about 34k, of which 28k is at DigiKey. The lead
  time is 17 weeks, and there is one maker.
* **Second sources:**
  * The Chinese 2 W parts at LCSC (Milliohm HoSRX1206-2W, 9k; Yezhan
    ASH-M-1206-0.5F, 31.7k) have the same value and size. They publish no
    lifecycle data.
  * Vishay WSLP1206 at 0.5 mOhm (Arrow 15.5k) is 1 W and **2 % only**, per
    Vishay's own datasheet. Its land differs: a 0.58 mm gap against the
    board's 1.40 mm, and 2.26 x 1.93 mm pads against 1.70 x 1.80 mm.
* **Check before qualifying any of them:**
  * the land against `og:RES-SMD_1206_HCS1206`;
  * where the Kelvin sense picks up (pads 3/4 at the inner corners);
  * the INA186 gain and AM32 current scaling (20 mV/A).

### SMF22A-TP (1 per board, 10,200)

* **Stock:** about 7k. DigiKey reports constrained supply and takes no
  backorders.
* **Alternates:** add Eaton SMF22A and Littelfuse SMF22A as approved
  alternates. Both are SOD-123FL with the same 22 V / 35.5 V / 200 W ratings.
  Together they bring more than 25k.
* **TSC SMF22A:** 27k in stock, but DigiKey lists its case as SOD-123W. Use it
  only after checking its land against `og:SOD-123FL...`.

### USB-C (GCT USB4110-GF-A)

The part itself is not scarce: DigiKey has 142k and Mouser 211k, at a 7-week
lead time. Only JLC's own shelf is short (424). Buy it from DigiKey or Mouser
and consign it to JLC, or use JLC's global-sourcing order.

I checked every 16-contact USB-C at JLC with more than 3,000 in stock against
the board's land. These all have **four plated through-hole shell legs** at
x = +/-4.32 mm:

| Part | LCSC # | Stock at JLC |
|---|---|---|
| HRO TYPE-C-31-M-12 | C165948 | 425k |
| SHOU HAN TYPE-C16PIN | C393939 | 398k |
| KH-TYPE-C-16P | C709357 | 256k |
| USB-TYPE-C-019 | C2927039 | 175k |
| TYPEC-304-ACP16 | C2982555 | 74k |
| HC-TYPE-C-16P-01A | C2894897 | 43k |
| GT-USB-7010ASV | C2988369 | 100k |
| LAIL-TYPE-C-16PIN | - | 48-50k |
| U262-161N-4BVC11 | C319148 | 53k |

They would put holes where the ESC FETs sit under the connector, so they are
rejected.

The all-SMD shells found:

* **Korean Hroparts TYPE-C-31-M-22 (C530612, 3,393 at JLC, not at
  distributors).**
  * Its pad map matches USB4110-GF-A:
    * 12 signal pads at the same x positions; VBUS at +/-2.45 against
      +/-2.40, 0.50 wide against 0.60;
    * four 2.18 x 2.00 mm SMD shell pads at x +/-5.11, y +0.58 / +4.47
      (against +4.50);
    * two 0.65 mm NPTH pegs at +/-2.89.
  * **No footprint change.** It is numbered 1-16 instead of A1B12..., so
    `parts.py` and `circuit.py` need a pin-name map.
  * It is the land-compatible fallback, but **not** a high-availability part.
* SHOU HAN SH-U262-161N-4B (C22383469, 4,206): the shell pads are 0.2 mm
  further out and 1.2-1.5 mm wide. **The footprint would change.**
* USB-TYPE-C-020 (C2927040, 15,623): split signal pads and 1.5 mm shell pads
  at +/-5.33. **The footprint would change.**

No high-availability, land-identical, all-SMD alternative exists at JLC
today. The high-availability source is the GCT part itself, through
DigiKey and Mouser.

### Bulk capacitor

* **The shortfall:** both qualified hybrids are far short of the run. The
  Panasonic has about 2.7k against a need of 10.2k, at a 43-week lead time.
  The Rubycon has 948 against 20.4k, at 30 weeks.
* **The wet alternative falls short:** Rubycon 35ZLH470MEFC10X16 is readily
  available (about 52k authorised plus DigiKey and LCSC 31.5k). But it is
  rated 1.76 A at 105 C. Two cover the 2.7 A hover, but not the 5.2-5.9 A
  worst case from `bulk-capacitor.md`, and they are 16 mm long. It is a
  fallback with a known derating, not a replacement.

## Changes recommended for volume

1. **ESC MCU:**
   * List STM32G071G8U6 (LCSC C724080) as an approved alternate to
     STM32G071GBU6 in `parts.py`. No PCB or firmware change is needed.
   * Place an ST factory order through Avnet, Arrow or Future now. Both parts
     have a 52-53 week lead time.
2. **Gyro:**
   * Qualify the Bosch BMI270 (C2836813) on the existing land.
   * Add `USE_ACCGYRO_BMI270` to the RIDGE3LITE target and re-verify the
     alignment.
   * Unless TDK confirms a firm delivery date, build the volume run on the
     BMI270.
3. **FC MCU:** list STM32G484CEU6 as an alternate after a one-board Betaflight
   boot test. Factory-order the STM32G473CEU6.
4. **Power FETs:**
   * Change the TSON land to the union land: source pads +0.15 mm inwards, no
     paste on the side drain pads.
   * Qualify Infineon BSZ018N04LS6ATMA1 with its own gate-resistor pair
     (start at 33 ohm / 15 ohm) after re-running `sim/halfbridge`.
   * Keep one maker per build lot.
5. **Shunt:**
   * Qualify a second 0.5 mOhm 1206 source after a land and Kelvin check.
     Milliohm HoSRX1206-2W is the closest match on rating (2 W, 1 %).
   * Recalibrate AM32's current reading per maker if the value differs.
6. **TVS:** add Eaton SMF22A and Littelfuse SMF22A (SOD-123FL) as approved
   alternates to MCC SMF22A-TP.
7. **USB-C:**
   * Keep USB4110-GF-A and supply it to JLC by consignment.
   * Optionally, add HRO TYPE-C-31-M-22 (C530612) as an alternate with a
     pin-name map. No land change is needed.
8. **JLC BOM alternates for passives:** JLC's own stock is short of 2x the
   run on these lines. Add the second sources from the table as approved
   alternates, or pre-buy reels.
   * R10R_0201: JLC has 0.56x the need.
   * C4U7_50: 0.82x.
   * R1K5_0201: 1.97x.
9. **Bulk capacitor:**
   * Factory-order both Panasonic EEH-AZSV681UB and Rubycon 35PZK470M10X11
     now. They are two makers, so this is also the second source.
   * The capacitor is fitted by hand, so it can ship in the box. The board
     run does not wait for it.

## What to buy now vs. order from factory

**Buy now from stock** (authorised stock covers the whole run):

| Part | Where to buy | Note |
|---|---|---|
| DRV8300DRGER | TI direct (338k) | |
| INA186A3IDCKR | TI direct (86k) | |
| TLV76733DRVR | TI direct (38k) and LCSC | |
| LMR36506R5RPER | TI direct 11,260 | covers the run, about 1.1x |
| TPS7A1601DRBR | Mouser 6,760 + TI 4,542 + LCSC 2,670 | about 1.4x; buy today, as there is no margin |
| USBLC6-2SC6 | | |
| AO3400A | | |
| SS1040HE | Maritex / LCSC / Mouser | |
| LEDs | | |
| ECS crystal | DigiKey 19k | |
| SWPA3015S100MT | JLC 57k | |
| B3U-1000P | | |
| USB4110-GF-A | DigiKey / Mouser, consigned to JLC | |
| SMF22A | MCC + Eaton (DigiKey 8.8k) together | |
| All resistors and capacitors | | |

**Buy all channel stock now AND place a factory order today** (no channel
covers the run):

| Part | Buy now | Factory order | Lead time |
|---|---|---|---|
| TPN2R304PL,L1Q | about 42k (Newark, DigiKey, Mouser, LCSC) | about 203k from Toshiba via an authorised distributor (41 reels of 5,000) | 24 wk |
| STM32G071GBU6 + G071G8U6 | about 20k (about 4,900 boards) | about 21k | 52-53 wk |
| STM32G473CEU6 | about 7.9k (Future 6,350 + LCSC) | the balance | 30-52 wk |
| ICM-42688-P | LCSC 4.6k | TDK (or move to BMI270, whose 127k in stock covers the run) | 45-52 wk |
| HCS1206FTL500 | DigiKey 28k + Future 4k + LCSC 1.9k | about 7k | 17 wk |
| Bulk capacitor | DigiKey and Newark stock of both | the balance, from both makers | Panasonic 43 wk / Rubycon 30 wk |

**What this means for the schedule:**

* Channel stock today builds about **1,700 complete boards**, limited by the
  FETs. With the Infineon second source it is about 4,400 boards.
* Then the ESC MCU limits it to about 4,900, and the FC MCU (with G484) to
  about 11k.
* The ICM-42688-P limits it to about 4,600, unless the BMI270 is qualified.
* The full 10,000 depend on the 52-week ST and TDK orders, unless those
  substitutions are made.
* Independent distributors list much of the short stock (MCUs, gyro, FETs).
  It is not counted here, and should not be used for a production run without
  traceability.

## Sources (all read 3 Oct 2026)

* LCSC / JLC: `tools/lcsc.py` (wmsc.lcsc.com product detail; jlcpcb.com
  component search). EasyEDA footprints: `easyeda.com/api/products/<C#>/components`.
* DigiKey product pages (digikey.in), looked up by DigiKey part number, e.g.
  `digikey.in/en/products/result?keywords=497-STM32G071GBU6TRCT-ND`,
  `...=TPN2R304PLL1QCT-ND`, `...=1428-ICM-42688-PCT-ND`, `...=STM32G473CEU6-ND`,
  `...=296-40969-1-ND`, `...=296-LMR36506R5RPERCT-ND`, `...=296-INA186A3IDCKRCT-ND`,
  `...=296-DRV8300DRGERCT-ND`, `...=TLV76733DRVR`, `...=3442-SWPA3015S100MTCT-ND`,
  `...=HCS1206FTL500CT-ND`, `...=SMF22A-TPMSCT-ND`, `...=283-SMF22ACT-ND`,
  `...=1801-SMF22ACT-ND`, `...=USB4110-GF-A`, `...=ECS-80-10-33-CHN-TR3`,
  `...=SS1040HEWS_R1_00001`, `...=BSZ018N04LS6ATMA1`, `...=EEH-AZSV681UB`,
  `...=1189-35PZK470M10X11-ND`.
* Octopart search pages, `octopart.com/search?q=<MPN>`: distributor offers
  (DigiKey, Mouser, Arrow, Avnet, Future, Newark, TME, Rutronik, TTI).
  Parsed by `tools/sourcing/op.py`.
* Findchips, `findchips.com/search/<MPN>`: Avnet lead times. Parsed by
  `tools/sourcing/fc.py`.
* TI direct inventory: `ti.com/storeservices/cart/opninventory?opn=<OPN>`.
* Toshiba TPN2R304PL product page and stock-check link:
  https://toshiba.semicon-storage.com/us/semiconductor/product/mosfets/12v-300v-mosfets/detail.TPN2R304PL.html
* Datasheets:
  * Toshiba TPN2R304PL Rev 3.0;
  * Infineon BSZ018N04LS6 Rev 2.1 (https://www.infineon.com/dgdl/Infineon-BSZ018N04LS6-DataSheet-v02_01-EN.pdf?fileId=5546d46269e1c0190169e2e8e05601f7);
  * onsemi NTTFS002N04CL/D (https://www.onsemi.com/pdf/datasheet/nttfs002n04cl-d.pdf);
  * Vishay SiSS12DN S18-0118 (https://www.vishay.com/docs/75281/siss12dn.pdf);
  * Vishay WSLP (https://www.vishay.com/docs/30122/wslp.pdf);
  * Stackpole HCS;
  * ST DS12232 (STM32G071, ordering information);
  * TDK ICM-42688-P (pin table).
* AM32: https://github.com/am32-firmware/AM32 (Mcu/ ports; `Inc/targets.h`
  GEN_64K_G071; `Mcu/g071/STM32G071GBUX_FLASH.ld`).
