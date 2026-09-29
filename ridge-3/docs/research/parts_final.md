> Research notes written while designing Ridge 3 (September 2026; the working name was OG3).
> Prices and stock are as found on the dates given and will have moved. The design decisions they led to
> are in `src/circuit.py` and `src/parts.py`; where the two disagree, the code is current.

# Ridge 3 parts library: final part choices (parts_final.md)

Date: 2026-09-27. Owner of this list: the parts library (`src/parts.py`,
`src/footprints.py`, `src/easyeda_raw/`, `aio.pretty/`, `aio.3dshapes/`).
**Nothing was ordered or bought.**

## 1. What changed

- `src/parts.py`: every requested key added. New entries carry `dk` (DigiKey
  part number), `dk_mpn` (the part DigiKey sells under `dk` when it is not
  `mpn`: another reel size of the same die, or a Yageo/Panasonic equivalent
  for a UNI-ROYAL resistor) and `maker` (maker + HQ country). Existing
  entries that `circuit.py` still uses got `dk`/`maker` too. Entries it no
  longer uses are marked `# v1 only`. Replaced in place (same key, new part):
  `LED_RED`, `LED_BLUE`, `XTAL8M`, `USBC`, `BOOTSW`, `C12P`, `C22U25`.
- Keys renamed at the coordinator's request: `C1U_100` (not `C1U_100_0805`),
  `C10U_25` (not `C10U_25_0805`). Added: `C470N`, `C2U2`, `R75`, `C1U_25`,
  `SJ_OPEN` (in `PADS`), `C_BRIDGE` (0805; `C4U7_50_1206` dropped),
  `SMF26A`, `SMF33A`, `INA180A1`, `FET40_ALT`, `R0R`.
- `src/easyeda_raw/`: 21 new EasyEDA footprints converted with easyeda2kicad
  1.0.1 and kept verbatim. The W25Q128JVPIM and both crystals reuse the
  existing raw files: EasyEDA's footprints for them are byte-identical,
  apart from the LCSC property and a wrong `through_hole` attribute on
  ECS's.
- `aio.3dshapes/`: 20 new gzip-STEP models (19 EasyEDA models plus KiCad's
  `R_1206_3216Metric` for the shunt). EasyEDA has no model for the MAX15062.
- `src/footprints.py`:
  - Polygon ("custom") pads are kept as polygons unless they are plain
    rectangles, and are drawn with zero outline width. The old code turned
    every custom pad into its bounding box. That would short the chamfered
    corner pads of the STM32G071's UFQFPN-28 (pads 1/28, 7/8, 14/15, 21/22).
    It would also have grown every polygon by 0.05 mm per edge.
  - `FIXUPS` table (the raw files stay verbatim):
    - USB-C pads renamed `A1-B12` to `A1B12` (and the other three).
    - TPS7A4101 thermal pad set to TI's 1.98 x 1.88 mm.
    - LMR38020 thermal pad set to TI's 3.4 x 2.71 mm.
  - New generated footprints:
    - `SJ_OPEN`: 2 pads 0.8 x 1.2 mm, 0.3 mm gap, one mask opening, no paste,
      excluded from BOM and CPL.
    - `RES-SMD_1206_HCS1206`: Stackpole's land plus Kelvin pads 3 and 4,
      with net-tie groups 1-3 and 2-4.
  - **`PAD_BAT` was not touched**: the coordinator is converting it to a
    plated through-hole pad. The 3.5 x 7.0 mm size from the original brief
    is theirs to apply.
  - Rebuilt with `/usr/bin/python3.12 src/footprints.py`: 51 footprints. All
    28 existing footprints come out identical to HEAD apart from KiCad's
    regenerated UUIDs; those files were restored so `git diff` shows only real
    changes.
- Check run: every component `circuit.py` builds was matched against its
  footprint's pads (pcbnew). The only mismatch is MAX15062A pad `9`, which
  does not exist (section 3). All 54 footprints that `parts.py` references
  load.

## 2. How the numbers were obtained (all 2026-09-27)

- **JLC stock and basic/extended**: JLCPCB parts API (`selectSmtComponentList`).
- **LCSC stock and price at 100 / 1000**: LCSC product API (`wmsc.lcsc.com`).
- **DigiKey**:
  - **(web)** means read from digikey.com product or search pages via
    WebFetch.
  - **(fc)** means DigiKey's feed on findchips.com.
  - The feed is wrong in both directions for commodity MLCCs and resistors.
    It showed 0 for GRM21BR61E226ME44L, which DigiKey has at 1,986. Every
    part where the feed said 0, and every thin or critical part, was
    re-checked on digikey.com.
  - DigiKey prices are cut tape, from the feed.
- **DC-bias data**: Murata SimSurfing's characteristics service
  (`ds.murata.com/simserve/characteristics`, 25 C, 1 Vrms). TDK's and
  Samsung's sites refused scripted access, so bias figures for non-Murata
  capacitors are for the equivalent Murata part.
- The lookup tools are in (a working file, not kept): `look.py`, `final.py`,
  `final.json`, `murata_dc.py`, `mdc.py`. They reuse
  `research/tools/src.py`.

## 3. Pin-map fixes needed in circuit.py (not edited by me)

| Key | What circuit.py has | What the footprint / datasheet says | Fix |
|---|---|---|---|
| `TLV76733` | `'2': None, '5': None` | TI TLV767 DRV, fixed version: **pin 2 = SNS** ("connect to OUT … do not float"), **pin 5 = GND**; 1 OUT, 3 GND, 4 EN, 6 IN, 7 thermal pad | `'2': '+3V3', '5': GND` |
| `MAX15062A` | `'9': GND` | TDFN-8 T822CN+1 has **no exposed pad**. The pin table ends at 8 LX, and EasyEDA's land has 8 pads | delete `'9'` |
| `LED_RED` (FC and ESC) | `{'1': 'LED_PWR_A', '2': GND}` | Lite-On footprint `LED0603-RD`: **pad 1 = cathode, pad 2 = anode**. EasyEDA symbol pin 1 is "-"; silk arrow and chamfer are at pad 1. The v1 KT-0603R had pad 1 = anode | `{'1': GND, '2': 'LED_PWR_A'}` |
| `LED_BLUE` | `{'1': 'LED0', '2': 'LED0_A'}` | pad 1 cathode | correct as is |
| `SMAJ26A` / `SMAJ33A` | used on both boards | TVS moved to SMF | use `SMF26A` (ESC) / `SMF33A` (FC); pad 1 = cathode on VBAT, as now |
| `SHUNT_0M5` | pads 1, 2, 3, 4 | pads 1, 2 current; 3 sense (net-tied to 1); 4 sense (net-tied to 2) | as is. Value 0.5 mOhm, so MILLIVOLT_PER_AMP = 50 with the INA180A3 |
| `TPS7A4101` GVDD output | `C10U_25` (10 uF 25 V 0805) | TI: "> 4.7 uF" on OUT. This cap keeps ~1.9 uF at 11.4 V | use `C10U50_1210` (~9 uF at 11.4 V) |

Confirmed as assumed:
- `TPN2R304PL`: 1-3 S, 4 G, 5-8 D, 9 D tab.
- `SMF*`, `SMAJ*`, `RB160VAM40`: pad 1 cathode.
- EPs: `TPS7A4101` 9, `LM76003` 31, `LMR38020F` 9, `AT7456E` 29,
  `DRV8300D` 25, `W25Q128JVPIM` 9.
- `STM32G071G`: 28 pads, no EP.
- `SH6_V`: 1-6 plus tabs 7, 8.
- `USBC`: A1B12 B1A12 A4B9 B4A9 A5 B5 A6 B6 A7 B7 A8 B8, shell 1-4. The two
  locating pegs are unnumbered NPTH.
- `BOOTSW`: 1, 2.
- `XTAL8M` / `XTAL27M`: 1, 3 crystal; 2, 4 GND.
- `INA180A3`: 1 OUT, 2 GND, 3 IN+, 4 IN-, 5 VS.
- `SJ_OPEN`: 1, 2.

## 4. Per-key table

Price columns: LCSC at 100 / 1000 pieces, then DigiKey cut tape at 100 /
1000. "ext" = JLC extended part (setup fee), "basic" = no fee.
### ESC: new parts

| Key | MPN | Footprint (aio: unless a KiCad lib) | Pads (numbers/names in the footprint) | LCSC / JLC stock | DigiKey PN: stock | Maker (HQ) | Price @100 / @1000 | Caveat |
|---|---|---|---|---|---|---|---|---|
| `STM32G071G` | STM32G071GBU6 | `UFQFPN-28_L4.0-W4.0-P0.50-BL` | 1-28 (no EP); 3 VDD/VDDA, 4 VSS/VSSA, 5 NRST (DS12232 GP pinout) | C529347: JLC 999 ext, LCSC 999 | 497-STM32G071GBU6TRCT-ND (STM32G071GBU6TR): tray 497-18343-ND: 0, backorder (web); tape 497-STM32G071GBU6TRCT-ND: 19 (fc) | STMicroelectronics (Switzerland) | LCSC $2.362 / $2.233; DK $1.929 / $1.761 | Fails "stocked at both" (DigiKey 0-19); no AM32-capable ST MCU is. Same-pad alternate STM32G071G8U6 C724080 (JLC 1,305; DK tape 79). No exposed pad. |
| `DRV8300D` | DRV8300DRGER | `VQFN-24_L4.0-W4.0-P0.50-TL-EP2.5` | 1-24, EP 25 (GND) | C3655801: JLC 15,324 ext, LCSC 15,243 | 296-DRV8300DRGERCT-ND: 57,231 (web) | Texas Instruments (USA) | LCSC $0.3896 / $0.3633; DK $0.4961 / $0.4266 | EP 2.45 mm = TI RGE0024B land exactly. |
| `TPN2R304PL` | TPN2R304PL,L1Q | `TSON-8_L3.1-W3.1-P0.65-LS3.3-BL-EP` | 1-3 S, 4 G, 5-8 D, 9 D tab (x3 copper) | C5802634: JLC 2,575 ext, LCSC 2,575 | TPN2R304PLL1QCT-ND: 50,515 (web) | Toshiba (Japan) | LCSC $0.5352 / $0.4571; DK $0.6869 / $0.5377 | LCSC 2,575 = 107 ESCs at 24 each. Pad 9 = 3 copper pieces (tab + 2 side ears), 5-8 overlap it. |
| `FET40_ALT` | DMTH43M8LFGQ-7 | `TSON-8_L3.1-W3.1-P0.65-LS3.3-BL-EP` | as TPN2R304PL (same footprint) | C6540319: JLC 2,100 ext, LCSC 2,100 | 31-DMTH43M8LFGQ-7CT-ND: 824 (web) | Diodes Incorporated (USA) | LCSC $1.246 / $1.114; DK $0.6495 / $0.6495 | Fits the TSON land but not identically (see section 5). JLC footprint origin 0.53 mm off package centre: check CPL. |
| `INA180A3` | INA180A3IDBVR | `SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR` | 1 OUT, 2 GND, 3 IN+, 4 IN-, 5 VS | C122882: JLC 89,459 ext, LCSC 89,455 | 296-47654-1-ND: 4,197 (web) | Texas Instruments (USA) | LCSC $0.1947 / $0.1446; DK $0.2469 / $0.2089 |  |
| `INA180A1` | INA180A1IDBVR | `SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR` | 1 OUT, 2 GND, 3 IN+, 4 IN-, 5 VS | C122228: JLC 88,254 ext, LCSC 88,250 | 296-46627-1-ND (INA180A1IDBVT): 1,013 (web; IDBVT reel; IDBVR 0) | Texas Instruments (USA) | LCSC $0.2287 / $0.1729; DK $0.639 / $0.639 | Only if you want 20 V/V. DigiKey stocks only the 250-reel IDBVT. |
| `SHUNT_0M5` | HCS1206FTL500 | `RES-SMD_1206_HCS1206` | 1, 2 current; 3 sense (tied to 1), 4 sense (tied to 2) | C346511: JLC 1,951 ext, LCSC 1,822 | HCS1206FTL500CT-ND: 31,022 (web) | Stackpole Electronics (USA) | LCSC $0.4655 / $0.395; DK $0.6173 / $0.4561 | Generated footprint (EasyEDA has none). 0.5 mOhm -> MILLIVOLT_PER_AMP 50 with INA180A3. LCSC 1,822 = 455 ESCs. |
| `MAX15062A` | MAX15062AATA+T | `TDFN-8_L2.0-W2.0-P0.50-BL_MAX15062AATA` | 1 VIN, 2 EN/UVLO, 3 VCC, 4 FB/VOUT, 5 MODE, 6 RESET, 7 GND, 8 LX (no EP) | C2846801: JLC 2,636 ext, LCSC 2,636 | MAX15062AATA+TCT-ND: 6,778 (web) | Analog Devices (USA) | LCSC $1.082 / $0.932; DK $1.547 / $1.425 | NO exposed pad: pads 1-8 only (circuit.py maps a pad 9). No 3D model. |
| `L33U` | NRS4018T330MDGJV | `IND-SMD_L4.0-W4.0` | 1, 2 | C1329473: JLC 3,341 ext, LCSC 3,340 | 587-6096-1-ND: 6,657 (web) | Taiyo Yuden (Japan) | LCSC $0.2116 / $0.1638; DK $0.2002 / $0.1646 | Isat 0.70 A max > 0.62 A peak current limit (datasheet rule); < 0.73 A runaway limit. |
| `TPS7A4101` | TPS7A4101DGNR | `MSOP-8_L3.0-W3.0-P0.65-LS5.0-BL-EP` | 1 OUT, 2 FB, 3 NC, 4 GND, 5 EN, 6 NC, 7 NC, 8 IN, 9 EP | C111739: JLC 11,047 ext, LCSC 11,047 | 296-30184-1-ND (TPS7A4101DGNT): 3,101 (web; DGNT reel; DGNR 0) | Texas Instruments (USA) | LCSC $0.6428 / $0.5442; DK $0.7734 / $0.7734 | EP widened to TI 1.98 x 1.88. Needs > 4.7 uF on OUT: 10 uF 0805 25 V gives 1.9 uF at 11.4 V. |
| `SMF26A` | SMF26A-E3-08 | `SMF_L2.8-W1.8-LS3.7-RD` | 1 K, 2 A | C1973422: JLC 35,010 ext, LCSC 35,010 | SMF26A-E3-08GICT-ND: 74,200 (web) | Vishay (USA) | LCSC $0.1755 / $0.1265; DK $0.2389 / $0.18 | Clamp 42.1 V at 4.8 A > 40 V FET VDSS; 200 W. Littelfuse SMF26A 0 at LCSC, so Vishay. |
| `SMAJ26A` | SMAJ26A | `SMA_L4.4-W2.6-LS5.0-RD` | 1 K, 2 A | C148225: JLC 12,572 ext, LCSC 12,570 | SMAJ26ALFCT-ND: 74,571 (fc) | Littelfuse (USA) | LCSC $0.1318 / $0.1032; DK $0.1923 / $0.1436 | Clamp 42.1 V at 9.5 A > 40 V FET VDSS. Stand-off 26 V vs 25.2 V pack. |
| `C_BRIDGE` | GRM21BZ71H475KE15L | `Capacitor_SMD:C_0805_2012Metric` | 1, 2 | C437557: JLC 111,968 ext, LCSC 97,300 | 490-GRM21BZ71H475KE15LCT-ND: 127,160 (web) | Murata (Japan) | LCSC $0.1434 / $0.1264; DK $0.2449 / $0.1983 | Only 1.02 uF effective at 25.2 V (Murata data). |
| `C100N_100` | GRM188R72A104KA35D | `Capacitor_SMD:C_0603_1608Metric` | 1, 2 | C77058: JLC 71,749 ext, LCSC 61,032 | 490-3285-1-ND: 735,979 (web) | Murata (Japan) | LCSC $0.0384 / $0.036; DK $0.0532 / $0.0398 |  |
| `C1U_100` | CC0805KKX7R0BB105 | `Capacitor_SMD:C_0805_2012Metric` | 1, 2 | C5370002: JLC 504,724 ext, LCSC 480,950 | 13-CC0805KKX7R0BB105CT-ND: 50,440 (web) | Yageo (Taiwan) | LCSC $0.0582 / $0.0518; DK $0.3758 / $0.307 |  |
| `C1U_25` | CL05A105KA5NQNC | `Capacitor_SMD:C_0402_1005Metric` | 1, 2 | C52923: JLC 6,527,432 basic, LCSC 735,250 | 1276-1445-1-ND: 2,318,576 (web) | Samsung Electro-Mechanics (South Korea) | LCSC $0.01 / $0.0075; DK $0.0675 / $0.0512 |  |
| `C10U_25` | CL21A106KAYNNNE | `Capacitor_SMD:C_0805_2012Metric` | 1, 2 | C15850: JLC 5,520,471 basic, LCSC 1,332,940 | 490-5523-1-ND (GRM21BR61E106KA73L): 0 (web) - Samsung, Murata (3,000 due 23 Nov 2026), Taiyo Yuden, TDK and Yageo 10 uF 25 V 0805 all 0 | Samsung Electro-Mechanics (South Korea); DK: Murata (Japan) | LCSC $0.0798 / $0.0525; DK $0.0585 / $0.044 | DigiKey out of stock across makers; 1.9 uF at 11.4 V. |
| `LED_RED` | LTST-C191KRKT | `LED0603-RD` | 1 K, 2 A | C125099: JLC 207,223 ext, LCSC 202,580 | 160-1447-1-ND: 1,517,473 (fc) | Lite-On (Taiwan) | LCSC $0.0235 / $0.0155; DK $0.0715 / $0.0517 | Pad 1 = CATHODE (v1 KT-0603R had pad 1 = anode): swap LED_RED pins in circuit.py. |
| `LED_BLUE` | LTST-C191TBKT | `LED0603-RD` | 1 K, 2 A | C99290: JLC 379,654 ext, LCSC 376,650 | 160-1647-1-ND: 358,116 (fc) | Lite-On (Taiwan) | LCSC $0.0214 / $0.017; DK $0.1193 / $0.0881 | Pad 1 = cathode (as v1). |

### FC: new parts

| Key | MPN | Footprint (aio: unless a KiCad lib) | Pads (numbers/names in the footprint) | LCSC / JLC stock | DigiKey PN: stock | Maker (HQ) | Price @100 / @1000 | Caveat |
|---|---|---|---|---|---|---|---|---|
| `LMR38020F` | LMR38020FDDAR | `ESOP-8_L4.9-W3.9-P1.27-LS6.0-BL-EP-1` | 1 GND, 2 EN, 3 VIN, 4 RT, 5 FB, 6 PG, 7 BOOT, 8 SW, 9 EP | C5149193: JLC 7,706 ext, LCSC 7,706 | 296-LMR38020FDDARCT-ND: 155 (web) | Texas Instruments (USA) | LCSC $0.7499 / $0.6662; DK $2.508 / $2.225 | DigiKey only 155. EP widened to TI 3.4 x 2.71. |
| `LM76003` | LM76003RNPR | `WQFN-30_L6.0-W4.0-P0.50-BL-EP` | 1-5 SW, 6 BOOT, 8 VCC, 9 BIAS, 10 RT, 11 SS, 12 FB, 13-15 AGND, 16 PG, 17 SYNC, 18 EN, 20-22 PVIN, 24-26 PGND, 7/19/23/27-30 NC, 31 EP | C470958: JLC 3,747 ext, LCSC 3,452 | 296-47536-1-ND (LM76003RNPT): 938 (web; RNPT reel; RNPR 0) | Texas Instruments (USA) | LCSC $2.042 / $1.841; DK $4.035 / $4.035 | DigiKey only the 250-reel RNPT (938). |
| `L6U8_BIG` | IHLP2525CZER6R8M01 | `IND-SMD_L6.5-W6.5_VISHAY` | 1, 2 | C506575: JLC 3,070 ext, LCSC 3,070 | 541-1011-1-ND: 27,790 (web) | Vishay (USA) | LCSC $0.3224 / $0.2451; DK $0.7668 / $0.6319 |  |
| `L4U7_5V` | SPM5020T-4R7M-LR | `IND-SMD_L5.4-W5.1_SPM5020T-100M-LR` | 1, 2 | C307807: JLC 1,998 ext, LCSC 1,840 | 445-174499-1-ND: 6,699 (web) | TDK (Japan) | LCSC $0.2225 / $0.1661; DK $0.8617 / $0.8617 | Ripple 43 % of 2 A at 25.2 V in (TI guidance 20-40 %; TI table uses 6.8 uH). LCSC 1,840. |
| `TLV76733` | TLV76733DRVR | `WSON-6_L2.0-W2.0-P0.65-TL-EP` | 1 OUT, 2 SNS, 3 GND, 4 EN, 5 GND, 6 IN, 7 EP | C2848334: JLC 27,664 ext, LCSC 26,305 | 296-TLV76733DRVTCT-ND (TLV76733DRVT): 1,023 (web; DRVT reel; DRVR 0) | Texas Instruments (USA) | LCSC $0.2292 / $0.1759; DK $0.7178 / $0.7178 | Pin 2 = SNS must go to OUT; pin 5 = GND (circuit.py leaves both open). |
| `AT7456E` | AT7456E | `TSSOP-28_L9.7-W4.4-P0.65-LS6.4-BL-EP-2` | 1-28, EP 29 (pinout = MAX7456) | C82351: JLC 40,392 ext, LCSC 35,480 | -: not sold (bare IC) | Hangzhou Zhongke Microelectronics (China) - approved exception | LCSC $1.861 / $1.709 | Owner-approved exception (Chinese maker, no DigiKey). |
| `XTAL27M` | E3SB27E00000DE | `CRYSTAL-SMD_4P-L3.2-W2.5-BL` | 1, 3 crystal; 2, 4 GND | C2687904: JLC 2,943 ext, LCSC 2,940 | 3186-E3SB27E00000DECT-ND: 2,332 (web) | Hosonic Electronic (Taiwan) | LCSC $0.0914 / $0.0683; DK $0.2595 / $0.2255 | -20..+70 C. Epson X1E0000210158 not at DigiKey. |
| `FB600` | BLM15PX601SN1D | `Inductor_SMD:L_0402_1005Metric` | 1, 2 | C160977: JLC 78,675 ext, LCSC 73,600 | 490-9657-1-ND: 694,669 (web) | Murata (Japan) | LCSC $0.0207 / $0.0171; DK $0.0489 / $0.0331 |  |
| `SH6_V` | BM06B-SRSS-TB(LF)(SN) | `CONN-SMD-6P-P1.00_BM06B-SRSS-TB-LF-SN` | 1-6 contacts, 7-8 tabs | C160392: JLC 42,978 ext, LCSC 33,830 | 455-BM06B-SRSS-TBCT-ND (BM06B-SRSS-TB): 33,665 (fc) | JST (Japan) | LCSC $0.2827 / $0.2544; DK $0.6434 / $0.5742 |  |
| `W25Q128JVPIM` | W25Q128JVPIM | `WSON-8_L6.0-W5.0-P1.27-BL-EP` | 1-8, 9 EP | C2441427: JLC 25,146 ext, LCSC 25,110 | 256-W25Q128JVPIMTRCT-ND (W25Q128JVPIM TR): 63,269 (fc, TR cut tape; tube 14,990) | Winbond Electronics (Taiwan) | LCSC $2.554 / $2.206; DK $3.427 / $3.156 | Same WSON-8 land/raw file as v1 W25Q128. |
| `XTAL8M` | ECS-80-10-33-CHN-TR3 | `CRYSTAL-SMD_4P-L3.2-W2.5-BL` | 1, 3 crystal; 2, 4 GND | C5727434: JLC 3,510 ext, LCSC 3,510 | 50-ECS-80-10-33-CHN-TR3CT-ND: 19,121 (web) | ECS Inc. International (USA) | LCSC $0.5142 / $0.4452; DK $0.4903 / $0.4261 | CL 10 pF: 12 pF load caps unchanged. gm_crit 0.91 mA/V < 1.5 mA/V. |
| `RB160VAM40` | RB160VAM-40TR | `SOD-323HE_L2.0-W1.4-LS2.5-RD` | 1 K, 2 A | C703624: JLC 29,347 ext, LCSC 29,250 | RB160VAM-40CT-ND: 9,541 (web; feed: 641 on cut tape) | ROHM (Japan) | LCSC $0.057 / $0.049; DK $0.185 / $0.1382 | Pad 1 = cathode (big pad). |
| `USBC` | USB4105-GF-A-120 | `USB-C-SMD_MC-311D` | A1B12 B1A12 A4B9 B4A9 A5 B5 A6 B6 A7 B7 A8 B8, shell 1 2 3 4, 2 unnumbered NPTH pegs | C5184243: JLC 4,947 ext, LCSC 3,794 | 2073-USB4105-GF-A-120CT-ND: 50,551 (web) | Global Connector Technology (UK) | LCSC $0.5289 / $0.5289; DK $0.5745 / $0.5385 | Pads renamed from EasyEDA A1-B12 style. |
| `BOOTSW` | B3U-1000P | `KEY-SMD_B3U-1000PM` | 1, 2 | C231329: JLC 153,222 ext, LCSC 149,040 | SW1020CT-ND: 135,347 (fc) | Omron / Aratas (Japan) | LCSC $0.1476 / $0.1102; DK $0.8261 / $0.685 | DigiKey lists maker as Aratas (Omron components spin-off, July 2026). |
| `SMF33A` | SMF33A-E3-08 | `SMF_L2.8-W1.8-LS3.7-RD` | 1 K, 2 A | C1972966: JLC 4,498 ext, LCSC 4,495 | SMF33A-E3-08CT-ND: 42,426 (web) | Vishay (USA) | LCSC $0.2308 / $0.1725; DK $0.2389 / $0.18 | Clamp 53.3 V at 3.8 A (63 % of LMR38020 85 V abs, 82 % of LM76003 65 V abs). |
| `SMAJ33A` | SMAJ33A | `SMA_L4.3-W2.6-LS5.0-RD` | 1 K, 2 A | C223988: JLC 11,560 ext, LCSC 11,560 | SMAJ33ALFCT-ND: 46,757 (fc) | Littelfuse (USA) | LCSC $0.1101 / $0.0899; DK $0.1814 / $0.1355 | Kept as SMA alternative; TVS moved to SMF. |
| `C10U50_1210` | UMK325AB7106KM-T | `Capacitor_SMD:C_1210_3225Metric` | 1, 2 | C386167: JLC 6,801 ext, LCSC 6,801 | 587-3167-1-ND: 180,319 (web) | Taiyo Yuden (Japan) | LCSC $0.3121 / $0.2759; DK $0.3906 / $0.3906 |  |
| `C22U25` | GRM21BR61E226ME44L | `Capacitor_SMD:C_0805_2012Metric` | 1, 2 | C86816: JLC 374,325 ext, LCSC 285,785 | 490-10749-1-ND: 1,986 (web; feed said 0) | Murata (Japan) | LCSC $0.1822 / $0.1415; DK $0.1405 / $0.1106 | 9.96 uF at 5 V, 5.13 uF at 9.1 V effective. |
| `C470N` | CL10B474KA8NNNC | `Capacitor_SMD:C_0603_1608Metric` | 1, 2 | C1623: JLC 987,282 basic, LCSC 472,380 | 1276-2083-1-ND: 53,644 (web) | Samsung Electro-Mechanics (South Korea) | LCSC $0.0299 / $0.0204; DK $0.0525 / $0.0393 | 0603, not 0402: no 0402 X7R >= 16 V at both. |
| `C2U2` | CL10A225KO8NNNC | `Capacitor_SMD:C_0603_1608Metric` | 1, 2 | C23630: JLC 2,746,346 basic, LCSC 1,348,800 | 1276-1040-1-ND: 213,560 (web) | Samsung Electro-Mechanics (South Korea) | LCSC $0.0182 / $0.0134; DK $0.0345 / $0.0252 |  |
| `C12P` | CL05C120JB5NNNC | `Capacitor_SMD:C_0402_1005Metric` | 1, 2 | C26406: JLC 187,303 ext, LCSC 184,000 | 1276-1178-1-ND: 10,228 (web) | Samsung Electro-Mechanics (South Korea) | LCSC $0.0087 / $0.0072; DK $0.0142 / $0.01 |  |

### Resistors (both boards)

| Key | MPN | Footprint (aio: unless a KiCad lib) | Pads (numbers/names in the footprint) | LCSC / JLC stock | DigiKey PN: stock | Maker (HQ) | Price @100 / @1000 | Caveat |
|---|---|---|---|---|---|---|---|---|
| `R10R` | 0402WGF100JTCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C25077: JLC 1,957,399 basic, LCSC 258,100 | 311-10.0LRCT-ND (RC0402FR-0710RL): 3,656,195 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0029 / $0.0022; DK $0.0124 / $0.0068 |  |
| `R20K` | 0402WGF2002TCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C25765: JLC 3,299,967 basic, LCSC 2,165,600 | 311-20.0KLRCT-ND (RC0402FR-0720KL): 2,372,480 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0023 / $0.0017; DK $0.0097 / $0.0051 |  |
| `R2K` | 0402WGF2001TCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C4109: JLC 8,504,166 basic, LCSC 6,974,100 | 311-2KLRCT-ND (RC0402FR-072KL): 178,633 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0026 / $0.002; DK $0.0097 / $0.0051 |  |
| `R680` | RC0402FR-07680RL | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C137948: JLC 876,694 ext, LCSC 763,700 | P680LCT-ND (ERJ-2RKF6800X): 81,550 (fc, Panasonic ERJ-2RKF6800X; Yageo RC0402FR-07680RL 0 on web) | Yageo (Taiwan); DK: Panasonic (Japan) | LCSC $0.0034 / $0.0028; DK $0.0164 / $0.0092 | UNI-ROYAL 680R has 917 left: Yageo at JLC; Panasonic for DigiKey. |
| `R100K` | 0402WGF1003TCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C25741: JLC 9,760,454 basic, LCSC 5,251,800 | 311-100KLRCT-ND (RC0402FR-07100KL): 6,854,918 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0025 / $0.0019; DK $0.0097 / $0.0051 |  |
| `R88K7` | 0402WGF8872TCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C25922: JLC 101,433 ext, LCSC 96,000 | 311-88.7KLRCT-ND (RC0402FR-0788K7L): 230,536 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0016 / $0.0012; DK $0.0097 / $0.0051 |  |
| `R10K2` | 0402WGF1022TCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C11660: JLC 55,378 ext, LCSC 40,800 | YAG2950CT-ND (RC0402FR-0710K2L): 52,668 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0015 / $0.0012; DK $0.0097 / $0.0051 |  |
| `R22R` | 0402WGF220JTCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C25092: JLC 5,211,820 basic, LCSC 2,440,300 | 311-22.0LRCT-ND (RC0402FR-0722RL): 5,207,739 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0028 / $0.0021; DK $0.0103 / $0.0054 |  |
| `R0R` | 0402WGF0000TCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C17168: JLC 10,230,933 basic, LCSC 4,794,400 | P0.0JCT-ND (ERJ-2GE0R00X): 9,890,212 (web, Panasonic ERJ-2GE0R00X; Yageo 0R 0 on web) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DK: Panasonic (Japan) | LCSC $0.0025 / $0.0019; DK $0.0095 / $0.0063 |  |
| `R30K` | 0402WGF3002TCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C25776: JLC 73,275 ext, LCSC 40,100 | 311-30.0KLRCT-ND (RC0402FR-0730KL): 1,211,795 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0016 / $0.0013; DK $0.0097 / $0.0051 |  |
| `R24K9` | 0402WGF2492TCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C25874: JLC 25,811 ext, LCSC 15,700 | 311-24.9KLRCT-ND (RC0402FR-0724K9L): 63,651 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0014 / $0.0011; DK $0.0097 / $0.0051 |  |
| `R12K4` | 0402WGF1242TCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C11692: JLC 264,652 ext, LCSC 228,600 | 311-12.4KLRCT-ND (RC0402FR-0712K4L): 24,115 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0014 / $0.0011; DK $0.0097 / $0.0051 |  |
| `R11K` | 0402WGF1102TCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C25749: JLC 111,206 ext, LCSC 65,000 | 311-11.0KLRCT-ND (RC0402FR-0711KL): 657,771 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0039 / $0.003; DK $0.0097 / $0.0051 |  |
| `R24K3` | 0402WGF2432TCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C26969: JLC 174,968 ext, LCSC 174,700 | YAG3071CT-ND (RC0402FR-0724K3L): 89,727 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0021 / $0.0016; DK $0.0097 / $0.0051 |  |
| `R25K5` | 0402WGF2552TCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C26970: JLC 35,108 ext, LCSC 35,100 | YAG3076CT-ND (RC0402FR-0725K5L): 143,342 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0019 / $0.0015; DK $0.0097 / $0.0051 |  |
| `R75` | 0402WGF750JTCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C25133: JLC 673,224 ext, LCSC 334,300 | 311-75.0LRCT-ND (RC0402FR-0775RL): 51,098 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0026 / $0.002; DK $0.0097 / $0.0051 |  |
| `R10` | 0402WGF100JTCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C25077: JLC 1,957,509 basic, LCSC 258,100 | 311-10.0LRCT-ND (RC0402FR-0710RL): 3,656,195 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0029 / $0.0022; DK $0.0124 / $0.0068 |  |
| `R100` | 0402WGF1000TCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C25076: JLC 4,646,345 basic, LCSC 1,421,200 | 311-100LRCT-ND (RC0402FR-07100RL): 2,985,832 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0013 / $0.001; DK $0.0097 / $0.0051 |  |
| `R1K` | 0402WGF1001TCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C11702: JLC 8,604,291 basic, LCSC 465,300 | 311-1.00KLRCT-ND (RC0402FR-071KL): 5,435,324 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0019 / $0.0014; DK $0.0097 / $0.0051 |  |
| `R10K` | 0402WGF1002TCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C25744: JLC 23,592,983 basic, LCSC 10,629,200 | 311-10.0KLRCT-ND (RC0402FR-0710KL): 11,721,670 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0034 / $0.0027; DK $0.0097 / $0.0051 |  |
| `R330` | 0402WGF3300TCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C25104: JLC 1,303,509 basic, LCSC 583,200 | 311-330LRCT-ND (RC0402FR-07330RL): 3,437,857 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0041 / $0.0032; DK $0.0097 / $0.0051 |  |
| `R5K1` | 0402WGF5101TCE | `Resistor_SMD:R_0402_1005Metric` | 1, 2 | C25905: JLC 6,567,152 basic, LCSC 4,450,200 | 311-5.10KLRCT-ND (RC0402FR-075K1L): 1,031,683 (fc) | UNI-ROYAL (Uniroyal Electronics; HQ Taiwan, plants in China); DigiKey equivalent: Yageo (Taiwan) | LCSC $0.0024 / $0.0019; DK $0.0097 / $0.0051 |  |

### Existing entries still used (kept; dk/maker added)

| Key | MPN | Footprint (aio: unless a KiCad lib) | Pads (numbers/names in the footprint) | LCSC / JLC stock | DigiKey PN: stock | Maker (HQ) | Price @100 / @1000 | Caveat |
|---|---|---|---|---|---|---|---|---|
| `STM32G473` | STM32G473CEU6 | `UFQFPN-48_L7.0-W7.0-P0.50-BL-EP5.6` | 1-48, 49 EP | C1342773: JLC 1,430 ext, LCSC 1,430 | STM32G473CEU6-ND: 1,268 (fc) | STMicroelectronics (Switzerland) | LCSC $5.253 / $5.253; DK $5.971 / $5.539 |  |
| `BMI270` | BMI270 | `LGA-14_L3.0-W2.5-P0.50-TL` | 1-14 | C2836813: JLC 2,222 ext, LCSC 2,222 | 828-1091-1-ND: 54,195 (fc) | Bosch Sensortec (Germany) | LCSC $1.496 / $1.378; DK $3.171 / $2.833 |  |
| `ICM45686` | ICM-45686 | `LGA-14_L3.0-W2.5-P0.50-TL` | 1-14 | C22459454: JLC 1,022 ext (2026-09-29) | 1428-ICM-45686CT-ND: 0 (fc, 2026-09-29) | TDK InvenSense (Japan/US) | LCSC $8.122 / $8.122; DK $5.26 @1 / $3.56 @1000 | Added 2026-09-29 as the fitted gyro; `BMI270` became the second source. Same land pattern (TDK DS-000577 fig. 13 and JLC's footprint for C22459454 match `aio:`'s). |
| `AO3400A` | AO3400A | `SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR` | 1 G, 2 S, 3 D | C20917: JLC 1,062,507 basic, LCSC 659,200 | 785-1000-1-ND: 316,253 (fc) | Alpha & Omega Semiconductor (USA) | LCSC $0.0683 / $0.0524; DK $0.2043 / $0.1532 |  |
| `USBLC6` | USBLC6-2SC6 | `SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BL` | 1-6 | C7519: JLC 46,765 ext, LCSC 44,995 | 497-11882-1-ND (USBLC6-2SC6Y): USBLC6-2SC6 0 (web, 3,000 past due) - USBLC6-2SC6Y 39,426 (web) | STMicroelectronics (Switzerland) | LCSC $0.1373 / $0.0993; DK (-Y) $0.71 @1 | DigiKey: order the -Y (automotive) variant. |
| `SH8_RA` | SM08B-SRSS-TB(LF)(SN) | `CONN-TH_SM08B-SRSS-TB-LF-SN` | 1-8, 9-10 tabs | C160407: JLC 123,874 ext, LCSC 120,870 | 455-1808-1-ND (SM08B-SRSS-TB): 62,910 (fc) | JST (Japan) | LCSC $0.2702 / $0.2084; DK $0.6121 / $0.5202 |  |
| `SH8_V` | BM08B-SRSS-TB(LF)(SN) | `CONN-TH_BM08B-SRSS-TB-LF-SN` | 1-8, 9-10 tabs | C160394: JLC 12,480 ext, LCSC 10,535 | 455-BM08B-SRSS-TBCT-ND (BM08B-SRSS-TB): 22,856 (fc) | JST (Japan) | LCSC $0.3308 / $0.2976; DK $0.5918 / $0.5282 |  |
| `C100N` | CL05B104KB54PNC | `Capacitor_SMD:C_0402_1005Metric` | 1, 2 | C307331: JLC 14,230,363 basic, LCSC 2,934,700 | 1276-CL05B104KB54PNCCT-ND: 48,207 (web) | Samsung Electro-Mechanics (South Korea) | LCSC $0.009 / $0.0069; DK $0.0272 / $0.0197 |  |
| `C1U` | CL05A105KA5NQNC | `Capacitor_SMD:C_0402_1005Metric` | 1, 2 | C52923: JLC 6,527,872 basic, LCSC 735,250 | 1276-1445-1-ND: 2,318,576 (web) | Samsung Electro-Mechanics (South Korea) | LCSC $0.01 / $0.0075; DK $0.0675 / $0.0512 |  |
| `C4U7` | CL05A475MP5NRNC | `Capacitor_SMD:C_0402_1005Metric` | 1, 2 | C23733: JLC 2,591,229 basic, LCSC 947,750 | 1276-1480-1-ND (CL05A475KP5NRNC): 0 (web, 61-week lead time) - equivalent CL05A475KP5NRNC 2,815 (web) | Samsung Electro-Mechanics (South Korea) | LCSC $0.0167 / $0.013; DK $0.0978 / $0.0757 | DigiKey equivalent is the +/-10 % CL05A475KP5NRNC. |

## 5. FET40_ALT: does the land really match?

Candidate: **Diodes Inc. DMTH43M8LFGQ-7** (USA; 40 V; RDS(on) 3.0 mOhm max at
10 V, 2.3 typ; Qg 40 nC; 175 C; AEC-Q101; PowerDI3333-8).
- JLC 2,100 (extended), $1.25 / $1.11.
- DigiKey 824 (web).

Other 40 V, 3 mOhm-or-less, 3.3 x 3.3 mm parts from non-Chinese makers,
rejected on stock:
- Infineon BSZ028N04LS: LCSC 116, DigiKey 0.
- Infineon BSZ024N04LS6: LCSC 92.
- Infineon BSZ018N04LS6: LCSC 42, DigiKey 0.
- Infineon BSZ021N04LS6: 0 at both.
- onsemi NVTFS003N04C: LCSC 84.
- AOS AON7140: LCSC 31, DigiKey 0.
- Vishay SiSS10ADN: LCSC 0.
- Toshiba's own TPN3R704PL (same package): stocked at both, but 3.7 mOhm
  max, over the limit.

Overlay (`research/parts_fet_overlay.png`): Diodes' suggested PowerDI3333-8
land, centred on the package, drawn on the TPN2R304PL's EasyEDA TSON Advance
land.
- **Matches:**
  - 0.65 mm pitch.
  - Pin order: 1-3 source, 4 gate, 5-8 drain on the opposite side, pin 1 in
    the same corner.
  - The whole PowerDI drain pad and its 4 drain fingers fall inside the
    TSON drain copper (pad 9 plus pads 5-8).
- **Differs:**
  - TSON source/gate pads run from 1.38 to 1.98 mm from centre. The
    PowerDI's 0.40 mm leads sit at 1.25-1.65 mm, so each lead overlaps its
    pad by only 0.27 mm of its 0.40 mm length.
  - The TSON drain copper reaches 0.83 mm towards the source row; Diodes'
    land stops at 0.40 mm. That leaves 0.42 mm, under the package body,
    between drain copper and the PowerDI's source leads (Diodes' own gap is
    0.75 mm).
  - Paste on the larger TSON drain pad is ~25 % more than Diodes' land.
- **Verdict:**
  - Electrically correct and solderable: no pad bridges a different net.
  - It is not an exact match. Expect weaker source-lead fillets. X-ray the
    first boards if the alternate is fitted.
  - JLC's own footprint for C6540319 has its origin 0.53 mm from the package
    centre (EasyEDA's body outline runs from -2.18 to +1.12 mm). Check the
    placement in JLC's preview, and correct the CPL if it is shifted.

Package facts used:
- Toshiba TSON Advance (datasheet p.9): drain pad 2.49 x 2.1 mm, leads 0.32
  x 0.25 mm, 3.3 mm body.
- Diodes PowerDI3333-8 (datasheet p.6):
  - Suggested land: X 0.42, Y 0.70, X3 2.37, Y2 2.25, Y3 3.70, C 0.65.
  - Package: E2 1.61, D2 2.27, L 0.40.

## 6. Footprints against the makers' recommended lands

| Footprint (key) | Maker land | EasyEDA / ours | Note |
|---|---|---|---|
| UFQFPN-28 (STM32G071G) | ST fig. 51: pads 0.30 x 0.55 at +/-1.875 mm, chamfered corners, **no EP** | 0.30 x 0.70 at +/-1.93, chamfered polygons kept | Pads reach 0.13 mm further out; fine |
| VQFN-24 EP2.5 (DRV8300D) | TI RGE0024B: 0.60 x 0.25 at +/-1.90, EP 2.45 | identical | - |
| TSON-8 (TPN2R304PL) | Toshiba gives package dimensions only; pad 2.49 x 2.1 mm | tab 2.7 x 2.3 mm plus side ears; leads 0.4 x 0.6 mm | Consistent with the package |
| SOT-23-5 BR (INA180) | TI DBV: 1.1 x 0.6 at +/-1.3 | identical | Pins 1-3 on one side as the datasheet |
| TDFN-8 (MAX15062) | Maxim 90-0349 (not fetched) | 0.25 x 0.8 at 0.5 pitch, no EP | Package has no EP (pin table) |
| MSOP-8-EP (TPS7A4101) | TI DGN0008B: 0.45 x 1.4 at +/-2.2, EP 1.88 x 1.98 | pads 0.36 x 1.66 at +/-2.13; **EP widened 1.8 x 1.5 -> 1.98 x 1.88** | Pad-to-EP gap 0.36 mm |
| ESOP-8 EP (LMR38020F) | TI DDA0008B: 0.6 x 1.55 at +/-2.7, EP 2.71 x 3.4 | pads 0.63 x 1.87 at +/-2.68; **EP widened 3.3 x 2.4 -> 3.4 x 2.71** | Pad-to-EP gap 0.39 mm |
| WQFN-30 (LM76003) | TI RNP0030B: 0.25 x 0.75 at +/-1.825 / +/-2.9, EP 1.8 x 4.5 | 0.25 x 0.8 at +/-1.90 / +/-3.00, EP 1.8 x 4.5 | EasyEDA pads 0.05-0.1 mm further out |
| WSON-6 (TLV76733) | TI DRV0006A: 0.45 x 0.3 at +/-0.975, EP 1.0 x 1.6 | oval 0.61 x 0.36 at +/-1.03, EP 1.0 x 1.6 | Fine |
| HTSSOP-28 (AT7456E) | Package EP 6.2 x 2.75 (ref), lead span 6.4 | EP land 6.7 x 2.9, pads 0.34 x 1.73 at +/-2.87 | Fine |
| USB-C MC-311D (USB4105) | GCT drawing: pads 1.15 long, 0.6/0.3 wide at 0.5 pitch; slots 0.6 x 1.7 / 0.6 x 1.4 at 8.64 mm; pegs 0.65 at 5.78 mm | identical | NPTH peg to pad A1B12 0.18 mm (GCT's own layout) |
| KEY B3U (BOOTSW) | Omron: 0.8 x 1.7 at 3.4 mm centres | identical | - |
| SOD-323HE (RB160VAM40) | ROHM: b4 1.1, l1 2.0, l2 0.8, l3 3.3 | 2.0 x 1.1 cathode + 0.9 x 1.1 anode, 3.39 overall | Fine |
| SMF (SMF26A/33A) | Vishay: 1.3 x 1.4 pads, 2.9 mm | 1.2 x 1.2 at 3.38 mm centres | EasyEDA/JLC land; covers the leads |
| LED0603-RD | Lite-On: 0.8 x 0.8 at 1.5 mm centres (2.3 overall) | identical | Pad 1 = cathode |
| CONN BM06B (SH6_V) | JST: 0.6 x 1.55 contacts, tabs 1.2 x 1.8 at +/-3.8 | identical | - |
| RES-SMD_1206_HCS1206 | Stackpole: a 1.40, b 1.70, c 1.80 | generated from these, plus Kelvin pads | Courtyard 5.0 x 2.45 (slot 3.4 x 6.2) |
| IND 4.0x4.0 (L33U), SPM5020 (L4U7_5V), IHLP2525 (L6U8_BIG), SMA | not re-checked beyond pad sizes | EasyEDA / JLC lands for these exact parts | - |

Copper check: minimum gap between pads of different numbers in every new
footprint is at least 0.2 mm (UFQFPN-28 and VQFN at 0.2-0.25 mm). The only
exception is TSON pads 5-8 over pad 9, which are all drain.

## 7. Capacitors: effective capacitance under DC bias (Murata SimSurfing, 25 C)

| Part | 0 V | 3.3 V | 5 V | 9.1 V | 11.4 V | 16.8 V | 22.2 V | 25.2 V |
|---|---|---|---|---|---|---|---|---|
| **C_BRIDGE** GRM21BZ71H475KE15 4.7 uF 50 V X7R 0805 | 4.98 | - | - | - | 2.26 | 1.55 | 1.17 | **1.02** |
| 4.7 uF 50 V X7R 1206 (GRM31CR71H475KA12) | 4.71 | 4.66 | 4.58 | 4.28 | 4.03 | 3.44 | - | 2.53 |
| 4.7 uF 100 V X7S 1206 (GRM31CZ72A475KE11) | 4.86 | - | - | - | 3.99 | 3.38 | 2.87 | 2.60 |
| 10 uF 50 V X7S 1210 (GCM32EC71H106KA03; ~UMK325AB7106KM) | 10.2 | - | 10.1 | 9.56 | 9.14 | 8.05 | 6.79 | 6.12 |
| C10U_25 class, 10 uF 25 V X5R 0805 (GRM21BR61E106KA73) | 10.5 | 7.29 | 5.03 | 2.48 | **1.93** | 1.30 | - | 0.82 |
| C22U25 GRM21BR61E226ME44 22 uF 25 V X5R 0805 | 21.5 | 14.4 | **9.96** | **5.13** | 4.07 | 2.64 | - | 1.79 |
| C100N_100 GRM188R72A104KA35 100 nF 100 V 0603 | 0.102 | - | - | - | 0.097 | 0.091 | 0.085 | 0.081 |

- **C_BRIDGE**:
  - No 10 uF 50 V X7R 0805 exists at JLCPCB. Samsung makes 4.7 uF 50 V
    0805 only in X7S.
  - Murata's GRM21BZ71H475KE15L is the stocked 4.7 uF 50 V X7R 0805 with
    published bias data. TDK's C2012X7R1H475K and CGA4J1X7R1H475K have no
    reachable data and are very likely no better.
  - 12 per ESC give ~12 uF at 25.2 V. The same count in 1206 would give
    ~30 uF, and in 1210 10 uF ~73 uF.
- **TPS7A4101 output** needs "> 4.7 uF". Use `C10U50_1210`, not `C10U_25`.
- **LMR38020 5 V output**: 3 x `C22U25` = 30 uF effective, exactly TI's
  1 MHz / 5 V minimum (2 x 15 uF).
- **LM76003 9 V output**: 4 x `C22U25` = 20.5 uF. The research notes
  suggested ~30 uF effective; add one or two, or check with WEBENCH.
- **10 uF 25 V 0805 at DigiKey**: 0 today at Samsung, Murata, Taiyo Yuden,
  TDK and Yageo; Murata is due 23 Nov 2026. JLC has 5.5 M of the basic
  Samsung part.

## 8. TVS against the 40 V FETs (ESC)

| TVS | VRWM | VBR min-max | VC at IPP | Note |
|---|---|---|---|---|
| SMAJ26A (Littelfuse, SMA 400 W) | 26 V | 28.9-31.9 V | 42.1 V at 9.5 A | 25.2 V pack = 97 % of VRWM (1 uA leakage) |
| SMF26A-E3-08 (Vishay, SMF 200 W) | 26 V | 28.9-32 V | 42.1 V at 4.8 A | half the surge rating in a third of the area |

The clamp at full rated surge (42.1 V) is above the TPN2R304PL's 40 V VDSS.
The TVS protects against slow battery-line transients. The FETs' avalanche
rating (EAS 39 mJ, IAS 80 A) covers the rest. A lower stand-off (SMF24A,
VBR 26.7 V min) would conduct on a full 6S pack plus ripple, so 26 V is the
right choice at 6S.

## 9. Stock and sourcing risks

- **STM32G071GBU6 / G8U6**: fails the DigiKey half of the rule. DigiKey has
  the tray at 0 (backorder) and tape at 19 / 79. LCSC has 999 + 1,305 (~576
  ESCs at 4 each). Known and accepted in esc_power.md.
- **LMR38020FDDAR**: DigiKey 155 (LCSC 7,706).
- **DigiKey carries only the small-reel variants**, so `dk_mpn` differs from
  `mpn`:
  - LM76003: RNPT 938.
  - TPS7A4101: DGNT 3,101.
  - TLV76733: DRVT 1,023.
  - INA180A1: IDBVT 1,013.
- **LCSC depth**:

  | Part | LCSC stock | Boards |
  |---|---|---|
  | TPN2R304PL | 2,575 | 107 ESCs |
  | HCS1206FTL500 | 1,822 | 455 ESCs |
  | SPM5020T-4R7M-LR | 1,840 | - |
  | STM32G071 | 999 | - |
  | E3SB27E00000DE | 2,940 | - |
  | ECS 8 MHz | 3,510 | - |
  | NRS4018 | 3,340 | - |

- **Commodity parts at 0 at DigiKey today** (fine at JLC):
  - 10 uF 25 V 0805.
  - Samsung CL05A475MP5NRNC; the ±10 % CL05A475KP5NRNC is in stock.
  - ST USBLC6-2SC6; the -Y variant is in stock.
  - Yageo 680R and 0R; Panasonic equivalents are given.
- **Chinese-made parts left in use**:
  - AT7456E: the approved exception.
  - UNI-ROYAL resistors: HQ Taiwan, plants in China. These are JLC basic
    parts; Yageo/Panasonic `dk_mpn` are given for every value.
- **Stock-rule failures** for existing parts not in the new circuit:
  ICM-42688-P (0 at LCSC and DigiKey), W25Q128JVPIQ (0 at LCSC), v1
  CL21A106KBYQNNE (0 at LCSC).
- **ICM-45686 (added 2026-09-29):** 0 at DigiKey; JLC's 1,022 cover 1,022
  FCs. The BMI270 fits the same pads as the fallback.

## 10. Entries marked `# v1 only`

ICM42688P, PY25Q128, W25Q128 (JVPIQ, an equal second source for JVPIM),
LMR51420, ME6211, INA186A2, STM32F051, JSM6288Q, AON7934, 2N7002, 1N5819WS,
BZX585C15, RB521S30, L4U7H, L4U7, SHUNT (RLM25), R750, R2K2, R15K, R22K,
C10U50, C10U50B.

## 11. Not done / open

- `PAD_BAT` left at 2.6 x 5.0 mm for the coordinator's through-hole
  redesign.
- DigiKey figures marked (fc) were not re-read on digikey.com. They are all
  lines with 10,000+ in the feed, except BM06B (33,665) and SMAJ33A (46,757).
- TDK, Samsung and Taiyo Yuden DC-bias curves could not be fetched. The
  Murata equivalents stand in for them.
- The Maxim land drawing 90-0349 for the MAX15062 was not fetched. The
  EasyEDA land for this exact part is used.
