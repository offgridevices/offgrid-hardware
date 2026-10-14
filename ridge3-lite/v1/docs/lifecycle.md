# Ridge 3 Lite (ridge3-lite v1): production lifecycle audit

The owner's requirement: "Very important to use in-production parts."

This audit covers every entry in `src/parts.py` `PARTS`. I read every status
on **3 Oct 2026**. Stock is LCSC / JLCPCB on the same day, from the LCSC
product-detail API and JLC's component search (`tools/lcsc.py`).

How to read the sources:

* Where the maker's own page could be fetched, it is the source (TI, ST
  eStore, TDK, ROHM, AOS, Omron/Aratas, Samsung, Panjit, Vishay series page).
* st.com, gct.co, ecsxtal.com, the Lite-On site, Murata's PIM pages (which
  need JavaScript), seielect.com and the Yageo site could not be read from
  here. For those parts the source is the DigiKey "Product Status" field,
  read on digikey.in.
* UNI-ROYAL, Fenghua (FH) and the generic SMF22A maker publish no
  per-part lifecycle data and are not carried by DigiKey. Their only
  evidence is LCSC.
* **LCSC's API has a `productCycle` field, but it does not track the
  maker's lifecycle.** It reads `normal` for every part on the board,
  including ROHM's RB160VAM-40TR, which ROHM marks *Not Recommended for New
  Designs*. Do not use it as a lifecycle check.

## Table

All dates are 2026-10-03. Stock is shown as LCSC / JLC. TI rows give the
`marketingStatus` of the exact orderable part number on the TI product page.

| Part key | MPN | Maker | Status | Source | Stock LCSC / JLC (LCSC #) | Verdict |
|---|---|---|---|---|---|---|
| STM32G473 | STM32G473CEU6 | ST | Active | https://estore.st.com/en/stm32g473ceu6-cpn.html | 1183 / 1488 (C1342773) | OK |
| ICM42688P | ICM-42688-P | TDK InvenSense | Production | https://invensense.tdk.com/products/motion-tracking/6-axis/icm-42688-p/ (no NRND/EOL notice, no successor named) | 4362 / 4645 (C1850418) | OK (see gyro note) |
| STM32G071G | STM32G071GBU6 | ST | Active | https://estore.st.com/en/stm32g071gbu6-cpn.html | 1001 / 1001 (C529347) | OK |
| DRV8300D | DRV8300DRGER | TI | ACTIVE | https://www.ti.com/product/DRV8300 | 15202 / 15248 (C3655801) | OK |
| INA186A3 | INA186A3IDCKR | TI | ACTIVE | https://www.ti.com/product/INA186 | 5727 / 5727 (C2058245) | OK |
| LMR36506R5 | LMR36506R5RPER | TI | ACTIVE | https://www.ti.com/product/LMR36506 | 1010 / 1010 (C2866484) | OK |
| TLV76733 | TLV76733DRVR | TI | ACTIVE | https://www.ti.com/product/TLV767 | 25205 / 26424 (C2848334) | OK |
| TPS7A1601 | TPS7A1601DRBR | TI | ACTIVE | https://www.ti.com/product/TPS7A16 | 2670 / 2691 (C2867753) | OK |
| USBLC6 | USBLC6-2SC6 | ST | Active | https://estore.st.com/en/usblc6-2sc6-cpn.html | 30075 / 34107 (C7519) | OK |
| TPN2R304PL | TPN2R304PL,L1Q | Toshiba | Active. Toshiba's page lists it as orderable with no NRND/EOL flag. DigiKey: Active. | https://toshiba.semicon-storage.com/ap-en/semiconductor/product/mosfets/12v-300v-mosfets/detail.TPN2R304PL.html ; https://www.digikey.in/en/products/detail/toshiba-semiconductor-and-storage/TPN2R304PL-L1Q/6099955 | 2315 / 2315 (C5802634) | OK (12 per board: about 190 boards of stock) |
| AO3400A | AO3400A | Alpha & Omega | Full Production | https://www.aosmd.com/products/mosfets/low-voltage-mosfets-12v-30v/ao3400a | 523250 / 954006, Basic (C20917) | OK |
| SMF22A | SMF22A | Generic. LCSC lists the brand as **GOODWORK**; parts.py says TECH PUBLIC. | No maker lifecycle data | LCSC C2943862 only | 107000 / 107010 (C2943862) | **Replace**: status cannot be established |
| RB160VAM40 | RB160VAM-40TR | ROHM | **Not Recommended for New Designs**. ROHM: "This product cannot be used for new designs". | https://www.rohm.com/products/diodes/schottky-barrier-diodes/low-vf/rb160vam-40-product | 29280 / 29347 (C703624) | **Replace** |
| LED_RED | LTST-C191KRKT | Lite-On | Active | https://www.digikey.in/en/products/detail/liteon/LTST-C191KRKT/386837 | 197060 / 201881 (C125099) | OK |
| LED_BLUE | LTST-C191TBKT | Lite-On | Active | https://www.digikey.in/en/products/detail/liteon/LTST-C191TBKT/388530 | 373850 / 376711 (C99290) | OK |
| XTAL8M | ECS-80-10-33-CHN-TR3 | ECS | Active | https://www.digikey.in/en/products/detail/ecs-inc/ECS-80-10-33-CHN-TR3/14825134 | 3435 / 3435 (C5727434) | OK |
| L10U | SWPA3015S100MT | Sunlord | Active | https://www.digikey.in/en/products/detail/shenzhen-sunlord-electronics-co-ltd/SWPA3015S100MT/14119952 | LCSC detail API returned no record / 57308 (C45403) | OK |
| SHUNT_0M5 | HCS1206FTL500 | Stackpole | Active | https://www.digikey.in/en/products/detail/stackpole-electronics-inc/HCS1206FTL500/5574626 | 1753 / 1927 (C346511) | OK |
| USBC | USB4110-GF-A | GCT | Active | https://www.digikey.in/en/products/detail/gct/USB4110-GF-A/10384548 | **0** / 424 (C5143397) | OK on lifecycle. Stock is thin: 424 at JLC, 0 at LCSC. |
| BOOTSW | B3U-1000P | Omron | In production | https://www.aratas.com/us-en/products/switches/B3U (Omron components site) | 136055 / 140514 (C231329) | OK |
| R10R_0402 | 0402WGF100JTCE | UNI-ROYAL | No maker data. JLC Basic part. | LCSC C25077 | 0 / 1753120 | OK (low risk) |
| R10K | 0402WGF1002TCE | UNI-ROYAL | No maker data. JLC Basic part. | LCSC C25744 | 6841500 / 21705992 | OK (low risk) |
| R82K | CRCW040282K0FKED | Vishay Dale | Active. The D/CRCW e3 series page is current, with no "not for new designs" notice. | https://www.digikey.in/en/products/detail/vishay-dale/CRCW040282K0FKED/1178225 ; https://www.vishay.com/en/product/20035/ | 30450 / 30482 (C482240) | OK |
| R100K | 0402WGF1003TCE | UNI-ROYAL | No maker data. JLC Basic part. | LCSC C25741 | 3818300 / 8226337 | OK (low risk) |
| R22R_0201 | RC0201FR-0722RL | Yageo | Active | https://www.digikey.in/en/products/result?keywords=RC0201FR-0722RL | 1028500 / 1370016 (C155743) | OK |
| R10R_0201 | RC0201FR-0710RL | Yageo | Active | https://www.digikey.in/en/products/result?keywords=RC0201FR-0710RL | 0 / 73666 (C106226) | OK |
| R100R_0201 | RC0201FR-07100RL | Yageo | Active | https://www.digikey.in/en/products/result?keywords=RC0201FR-07100RL | 1942700 / 2158653 (C77623) | OK |
| R330_0201 | RC0201FR-07330RL | Yageo | Active | https://www.digikey.in/en/products/result?keywords=RC0201FR-07330RL | 1361800 / 1416230 (C274872) | OK |
| R1K_0201 | RC0201FR-071KL | Yageo | Active | https://www.digikey.in/en/products/result?keywords=RC0201FR-071KL | 2162800 / 2306571 (C138165) | OK |
| R1K5_0201 | 0201WMF1501TEE | UNI-ROYAL | No maker data | LCSC C270361 | 0 / 80490 | OK (low risk). The Yageo RC0201FR-071K5L (C155737) has only 60 in stock, so it is no alternative. |
| R2K2_0201 | RC0201FR-072K2L | Yageo | Active | https://www.digikey.in/en/products/result?keywords=RC0201FR-072K2L | 1215200 / 1318262 (C142018) | OK |
| R5K1_0201 | RC0201FR-075K1L | Yageo | Active | https://www.digikey.in/en/products/result?keywords=RC0201FR-075K1L | 104700 / 139032 (C274341) | OK |
| R10K_0201 | RC0201FR-0710KL | Yageo | Active | https://www.digikey.in/en/products/result?keywords=RC0201FR-0710KL | 1741100 / 2435907 (C106225) | OK |
| R27K_0201 | RC0201FR-0727KL | Yageo | Active | https://www.digikey.in/en/products/result?keywords=RC0201FR-0727KL | 35200 / 35212 (C273283) | OK |
| R62K_0201 | RC0201FR-0762KL | Yageo | Active | https://www.digikey.in/en/products/result?keywords=RC0201FR-0762KL | 21600 / 21661 (C295812) | OK |
| C12P | 0402CG120J500NT | Fenghua (FH) | No maker data. JLC Basic part. | LCSC C1547 | 1085600 / 1974116 | OK (low risk). The optional swap is Samsung CL05C120JB5NNNC, C26406: Mass Production, 158232 at JLC. |
| C100N_0201 | CL03A104KO3NNNC | Samsung | Mass Production | https://product.samsungsem.com/mlcc/CL03A104KO3NNN.do | 769500 / 1163379 (C307380) | OK |
| C1U_0201 | GRM033R61A105ME44D | Murata | Active | https://www.digikey.in/en/products/detail/murata-electronics/GRM033R61A105ME44D/13905074 | 564040 / 785248 (C76935) | OK |
| C100N_50 | CL05B104KB54PNC | Samsung | Mass Production | https://product.samsungsem.com/mlcc/CL05B104KB54PN.do | 0 / 12468779, Basic (C307331) | OK |
| C1U_25 | CL05A105KA5NQNC | Samsung | Mass Production | https://product.samsungsem.com/mlcc/CL05A105KA5NQN.do | 2620400 / 5609717 (C52923) | OK |
| C4U7_0402 | CL05A475MP5NRNC | Samsung | Mass Production | https://product.samsungsem.com/mlcc/CL05A475MP5NRN.do | 590250 / 2357164 (C23733) | OK |
| C10U_25 | CL10A106MA8NRNC | Samsung | Mass Production | https://product.samsungsem.com/mlcc/CL10A106MA8NRN.do | 0 / 3348269, Basic (C96446) | OK |
| C4U7_25 | CL21A475KAQNNNE | Samsung | Mass Production | https://product.samsungsem.com/mlcc/CL21A475KAQNNN.do | 1900040 / 3029709 (C1779) | OK |
| C22U_25 | GRM21BR61E226ME44L | Murata | Active | https://www.digikey.in/en/products/detail/murata-electronics/GRM21BR61E226ME44L/5251351 | 286715 / 351460 (C86816) | OK |
| C4U7_50 | GRM21BZ71H475KE15L | Murata | Active | https://www.digikey.in/en/products/detail/murata-electronics/GRM21BZ71H475KE15L/13904833 | 99510 / 117026 (C437557) | OK |

## Gyro note (ICM-42688-P)

TDK's own product page labels the ICM-42688-P **"Production"**. It carries
no NRND or EOL banner and points to no successor. The reports of TDK steering
new designs to the ICM-45686 or ICM-42688-V are not reflected on the maker's
page as of 3 Oct 2026. No change is needed.

I checked a contingency anyway:

* Betaflight `master` has drivers for all the candidates:
  * `accgyro_spi_icm426xx.c` (42688-P)
  * `accgyro_spi_icm456xx.c` (ICM-45686)
  * `accgyro_spi_lsm6dsv16x.c`
  * `accgyro_spi_bmi270.c`

  I checked master. I did not check the 2026.6 release tag.
* The official target `configs/GEPR/TAKERG4AIO/config.h` in betaflight/config
  defines the following, and has no ICM456xx or LSM6DSV16X entry:
  * `USE_GYRO_SPI_ICM42688P` and `USE_ACC_SPI_ICM42688P`
  * `USE_GYRO_SPI_MPU6000`
  * `USE_ACCGYRO_LSM6DSK320X`

  So switching the gyro would also mean carrying a custom target.
* The ICM-45686 is at JLC as C22459454 (LGA-14 3x2.5): 381 in stock at
  US$11.85. The 42688-P has 4645 in stock at about US$3.

## Changes recommended

### 1. RB160VAM40 (USB OR-ing Schottky): ROHM marks it NRND

* ROHM names RBR1VAM40ATR as its "same pinout, package" successor. It is not
  in the JLC/LCSC catalogue (searched 3 Oct 2026).
* **Use the PANJIT SS1040HEWS_R1_00001, LCSC C282389.** It has 9968 in stock
  at JLC. PANJIT's page shows it as **Active**:
  https://www.panjit.com.tw/en/Product/Bond/SS1040HEWS
* It is 40 V, 1 A, 22 A IFSM, in SOD-323HE.

What differs:

* **Package and footprint:** the package is the same SOD-323HE. Both
  EasyEDA symbols put the cathode on pin 1 (the large pad). PANJIT's own land
  has a 1.9 mm cathode pad where ROHM's is 2.0 mm, at a 1.90 mm pad pitch
  instead of 1.95 mm. The board's existing `og:SOD-323HE_L2.0-W1.4-LS2.5-RD`
  footprint stays as it is.
* **Electrical:** VF is 0.58 V max at 1 A. The RB160VAM-40 is 0.55 V at
  0.7 A. IR is 100 uA max at 40 V, against 50 uA. Neither matters for USB
  OR-ing at a few hundred mA.
* **Edit:** change the `RB160VAM40` entry in `parts.py` (lcsc, mpn, maker,
  value, desc). No firmware change.

### 2. SMF22A (battery TVS): the maker is unknown, so production status cannot be shown

* LCSC sells C2943862 under the brand "GOODWORK", not TECH PUBLIC as
  `parts.py` says. That maker publishes no lifecycle data.
* Vishay's **SMF22A-HE3-08** (C1973936) is at JLC, but DigiKey lists it as
  **Obsolete**.
* Vishay's current SMF22A-E3-08 (C3707819) and SMF22A-M3-08 (C3712352) have
  0 in stock.
* Littelfuse SMF22A-T13 (C1977156) has 0 in stock, and SZSMF22AT1G
  (C3710987) has 50.
* **Use the Micro Commercial Components (MCC) SMF22A-TP, LCSC C1974299.**
  It has 3652 in stock at JLC, and DigiKey lists it as **Active**
  (https://www.digikey.in/en/products/result?keywords=SMF22A-TP).
* It has the same ratings: 22 V stand-off, 35.5 V clamp at 5.6 A, 200 W
  10/1000 us, SOD-123FL.

What differs:

* **Package and footprint:** the package is the same SOD-123FL, and the
  board's `og:SOD-123FL_L2.8-W1.9-LS3.7-RD` land (1.2 x 1.4 mm pads, 3.4 mm
  pitch) fits it. MCC's own land is smaller (1.0 x 1.08 mm, 3.3 mm pitch).
* **Polarity check:** MCC's EasyEDA symbol does not label K/A. Check the
  cathode band against pad 1 in JLC's placement preview.
* **Price:** about US$0.085, against US$0.027.
* **Edit:** change the `SMF22A` entry in `parts.py`. No firmware change.

### 3. Optional: no lifecycle risk found, but noted

* USB4110-GF-A is Active, but stock is thin: 424 at JLC, 0 at LCSC.
  Pre-order or consign before a large run.
* UNI-ROYAL and FH passives have no maker lifecycle data. They are
  high-stock JLC Basic parts.
* If every line must have a published maker status, these swaps have the
  same values, packages and footprints:

  | Current part | Swap to | LCSC # | Stock at JLC |
  |---|---|---|---|
  | 0402WGF100JTCE | Yageo RC0402FR-0710RL | C138066 | 1.33 M |
  | 0402WGF1002TCE | Yageo RC0402FR-0710KL | C60490 | 8.7 M |
  | 0402WGF1003TCE | Yageo RC0402FR-07100KL | C60491 | 9.1 M |
  | 0402CG120J500NT | Samsung CL05C120JB5NNNC (Mass Production) | C26406 | 158 k |

  Keep UNI-ROYAL 0201WMF1501TEE: Yageo's 1.5 k 0201 has 60 in stock.
