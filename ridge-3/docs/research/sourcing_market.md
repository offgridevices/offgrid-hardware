> Research notes written while designing Ridge 3 (September 2026; the working name was OG3).
> Prices and stock are as found on the dates given and will have moved. The design decisions they led to
> are in `src/circuit.py` and `src/parts.py`; where the two disagree, the code is current.

# OG3 sourcing and market check

Cheap-drone-stack v1 (FC + 4-in-1 ESC, 25.5 mm). Research date **27 Sep 2026**. Nothing was ordered.

## Summary

1. **Parts from PRC makers.** The two BOMs have 41 unique LCSC lines and 196 placements.
   - 13 lines come from PRC-headquartered makers.
   - 13 more are UniOhm resistor values. UniOhm was founded in Taiwan, but its operating HQ and plants are in China.
   - 1 is Nexperia, a Dutch company owned by China's Wingtech.
   - Together that is 27 of 41 lines and 97 of 196 placements. It covers every resistor, the 12 pF caps, the flash, LDO, crystal, both inductors, USB-C, boot switch, both LEDs, the USB diode, all four ESC gate drivers, all twelve bootstrap diodes and the four zeners.
   - The chips that matter most are not Chinese: ST MCUs, Bosch gyro, TI buck, AOS FETs, JST connectors and Samsung MLCCs.
2. **Same-footprint replacements exist for most of them**, and each is stocked at both LCSC/JLC and DigiKey:
   - Winbond flash, TI TLV75533P LDO, Toshiba diodes, Lite-On LEDs, Samsung 12 pF, Yageo or Panasonic resistors, ECS crystal.
   - Most useful find: **TI DRV8300DRGE appears to be a pin-for-pin match for the JSM6288Q/FD6288Q on the existing ESC footprint.** I compared it against `circuit.py` pin by pin. Build and test one ESC before relying on it.
   - Two parts need a new footprint: the USB-C connector and the tact switch.
   - Three have no verified non-Chinese drop-in: the AON7934 FET (AOS is a US company, but its packaging is mostly in China), the 5×5 inductor (the Vishay IHLP-2020 is the same size class, but its land pattern needs checking) and the zener (candidates exist, but none is in stock at DigiKey today).
3. **Supply risk matters more than origin right now.**
   - STM32G473CEU6: out of stock at DigiKey with a 52-week lead time.
   - STM32F051K6U6: 0 at DigiKey (490 due 21 Oct 2026, 40-week lead time), and only 770 at LCSC / 886 at JLC.
   - AON7934: 0 at DigiKey until 2 Nov 2026.
   - Samsung CL21A226MAQNNNE (22 µF 0805): **obsolete** at DigiKey.
   - 10 µF 50 V 0805: 0 at DigiKey from every major maker.
   - ICM-42688-P: 0 at LCSC.
4. **The biggest regulatory item is not the NDAA; it is the FCC.** Since **22 Dec 2025** the FCC Covered List includes "UAS and UAS critical components produced in a foreign country" (any country, allies included). Flight controllers are named. New covered models cannot get FCC equipment authorization.
   - Exemptions: Blue UAS listing, Buy American "domestic end product" (US-made with more than 65 % US component cost), or a DoW/DHS Conditional Approval.
   - The first two were extended to **1 Jan 2028** on 21 Jul 2026.
   - Open question: whether a radio-less FC/ESC needs FCC authorization at all. See §2.
   - §848 and ASDA only bind federal buyers. §848 names flight controllers, radios, data links, cameras and gimbals made in China (and Russia, Iran, North Korea). ESCs are not named. ASDA is based on who made or assembled the product.
5. **Market.**
   - The owner's reference board: GEPRC TAKER G4 45A AIO (G473, ICM-42688-P, 45 A, 2–6S, 25.5 mm) sells for **$79.99–$95**.
   - Chinese 3-inch AIOs and stacks sell for **$57–$83** (SpeedyBee, BetaFPV, GEPRC). 20×20 stacks run $65–$155.
   - Every NDAA-claiming FC and ESC I found is **30×30 mm** and costs **$58–$300 per board**. The cheapest FC+ESC pair is $173 (Rotor Riot Brave F7 + Brave 55A).
   - So a $50–70 two-board 25.5 mm stack sits at the price of the Chinese mainstream, with lower specs (4S only, no OSD chip, no current sensor, ESC rating unmeasured). No NDAA-sourced competitor exists in 3-inch yet. The selling point is sourcing and repairability, not performance.
6. **Names.** USPTO has no live OG3, OG7 or OG12 mark in drone-related classes. Two cautions:
   - **"OG7" = OG-7V**, the RPG-7 fragmentation round widely used as an FPV strike-drone warhead.
   - "OFFGRID" is registered in class 9 (EDEC Faraday bags, Reg. 6076046). That is a possible likelihood-of-confusion obstacle for an OffGrid electronics filing.

---

## 0. Method and data caveats

- **LCSC stock** comes from LCSC's product API (`wmsc.lcsc.com/ftps/wm/product/detail?productCode=…`). **JLC stock** comes from JLCPCB's parts API. JLC and LCSC stock differ: JLC holds its own inventory for PCBA, so use the JLC figure for assembly. Links below go to `https://www.lcsc.com/product-detail/<C#>.html`.
- **DigiKey stock** comes from two sources:
  - **(DK)**: read directly from the DigiKey product or search page with WebFetch.
  - **(FC)**: DigiKey's feed as mirrored by [Findchips](https://www.findchips.com) (Supplyframe). It lags. On the same day Findchips showed 1,268 STM32G473CEU6 and 794 STM32F051K8U6 at DigiKey, while DigiKey itself showed "out of stock" and 3. Treat (FC) numbers as indicative only.
  - DigiKey search: `https://www.digikey.com/en/products/result?keywords=<MPN>`.
  - curl gets a Cloudflare 403 from DigiKey, but WebFetch gets through.
- **Mouser could not be checked.** It returned PerimeterX "Access to this page has been denied" to curl and HTTP 503 to WebFetch. The only Mouser fact I have comes from its search index: it lists Royalohm (UniOhm) [0402WGF1002TCE](https://www.mouser.com/ProductDetail/Royalohm/0402WGF1002TCE?qs=e8oIoAS2J1T9/SfQTy4YqQ%3D%3D) and [0402WGF2201TCE](https://www.mouser.com/ProductDetail/Royalohm/0402WGF2201TCE?qs=e8oIoAS2J1QvBi%2FbAiHH2g%3D%3D), stock unknown. Mouser stock is **unconfirmed for every part**.
- Blocked sites: TME (403), Octopart (403), GEPRC.com (202 with empty body), GetFPV (403). The FCC covered-list page gave 403, but the FCC PDFs downloaded fine.
- **HQ country** comes from LCSC brand pages or maker sites, cited per row. Where the brand page was unreadable (XINGLIGHT, XUNPU, DOINGTER, YLPTEC), "PRC" is marked *unverified*.
- **Fab/assembly country** is given only where a source says so. Otherwise it is "unknown". For a compliant build, record the COO from each reel label or the distributor's COO field.
- Raw data (JSON/HTML/PDF text) is in working files not kept in the repo: `lcsc.json`, `jlc.json`, `fc.json`, `jlc_search.json`, `notes_digikey_direct.txt`, the FCC PDFs and their text.

---

## 1. Part-by-part audit

The README's stock claims have moved since design (26 Sep):
- STM32G473: README 1,690 → JLC 1,430 today.
- ICM-42688-P: 392 → JLC 343, LCSC 0.
- Samsung 10 µF 0805 (C2932476): 216k at JLC but 0 at LCSC.

### 1a. Flight controller (populated parts)

| Ref (qty) | MPN | Maker (HQ; fab if known) | LCSC # | LCSC / JLC stock | DigiKey PN, stock | Flag |
|---|---|---|---|---|---|---|
| U_FC (1) | STM32G473CEU6 | STMicroelectronics (Geneva, CH) | [C1342773](https://www.lcsc.com/product-detail/C1342773.html) | 1,430 / 1,430 | [STM32G473CEU6-ND](https://www.digikey.com/en/products/detail/stmicroelectronics/STM32G473CEU6/10326718): **out of stock, backorder, 52-wk lead** (DK), $9.11 | Supply risk |
| U_IMU (1) | BMI270 | Bosch Sensortec (Reutlingen, DE) | [C2836813](https://www.lcsc.com/product-detail/C2836813.html) | 2,250 / 2,250 | [828-1091-1-ND](https://www.digikey.com/en/products/detail/bosch-sensortec/BMI270/9974486): 53,485 (DK), $4.23 | OK |
| U_FLASH (1) | PY25Q128HA-WXH-IR | **Puya Semiconductor (Shanghai, CN)** ([LCSC brand](https://www.lcsc.com/brand-detail/11580.html)) | [C18208279](https://www.lcsc.com/product-detail/C18208279.html) | 9,850 / 10,021 | **Not at DigiKey** (DK search: no results) | **PRC** |
| U_BUCK (1) | LMR51420YDDCR | Texas Instruments (Dallas, US) | [C5383002](https://www.lcsc.com/product-detail/C5383002.html) | 13,015 / 13,015 | [296-LMR51420YDDCRCT-ND](https://www.digikey.com/en/products/result?keywords=LMR51420YDDCR): 9,455 (DK), $1.32 | OK |
| U_LDO (1) | ME6211C33M5G-N | **Nanjing Micro One (MICRONE), CN** ([LCSC brand](https://www.lcsc.com/brand-detail/250.html)) | [C82942](https://www.lcsc.com/product-detail/C82942.html) | 170,120 / 178,448 | **Not at DigiKey** (DK) | **PRC** |
| U_ESD (1) | USBLC6-2SC6 | STMicroelectronics | [C7519](https://www.lcsc.com/product-detail/C7519.html) | 42,655 / 44,638 | [497-5235-1-ND](https://www.digikey.com/en/products/detail/stmicroelectronics/USBLC6-2SC6/1040559): **out of stock, 25 wk** (DK). USBLC6-2SC6**Y** 497-11882-1-ND: 39,426 (DK), $0.71 | OK. DigiKey also lists this MPN from UMW, SLKOR and Goodwork (PRC second-source makers), so order by manufacturer, not MPN alone |
| Q_BZ (1) | AO3400A | Alpha & Omega Semiconductor (Sunnyvale, US; Bermuda-incorporated). Wafer fab Hillsboro, OR ([AOS](https://www.aosmd.com/about)). Assembly/test "primarily … in-house facilities in China" and foundry HHGrace Shanghai ([2019 10-K](https://www.sec.gov/Archives/edgar/data/1387467/000138746719000040/aosl630201910k.htm)) | [C20917](https://www.lcsc.com/product-detail/C20917.html) | 659,520 / 1,066,474 | [785-1000-1-ND](https://www.digikey.com/en/products/detail/alpha-omega-semiconductor-inc/AO3400A/1855772): 303,649 (DK), $0.52 | US maker, **COO likely CN** (check label). The MPN is also sold by UMW, Goodwork and EVVO (PRC) |
| D_USB (1) | 1N5819WS | **Guangdong Hottech, CN** ([LCSC brand](https://www.lcsc.com/brand-detail/11439.html)) | [C191023](https://www.lcsc.com/product-detail/C191023.html) | 4,507,350 / 5,091,045 | Hottech not at DigiKey. The MPN there comes only from PRC makers (Goodwork, SLKOR, HUXN) (FC) | **PRC** |
| LED_PWR (1) | KT-0603R | **Hubei KENTO (Zigui, Hubei, CN)** ([LCSC brand](https://www.lcsc.com/brand-detail/70.html)) | [C2286](https://www.lcsc.com/product-detail/C2286.html) | 2,363,300 / 4,007,383 | **Not at DigiKey** (DK) | **PRC** |
| LED_STAT (1) | XL-1608UBC-04 | **XINGLIGHT (PRC, unverified)** | [C965807](https://www.lcsc.com/product-detail/C965807.html) | 2,340,700 / 2,373,554 | 5962-XL-1608UBC-04TR-ND: 64,000 (DK), **Marketplace, ships from XINGLIGHT, 4,000-pc reels only** | **PRC** |
| Y1 (1) | TAXM8M4RDBCCT2T (8 MHz, 10 pF, 3225) | **Yajingxin / Shenzhen ABEL Electronics, CN** ([LCSC brand](https://www.lcsc.com/brand-detail/1181.html)) | [C400090](https://www.lcsc.com/product-detail/C400090.html) | 179,180 / 191,883 | **Not at DigiKey** (DK) | **PRC** |
| L1 (1) | FXL0530-4R7-M (4.7 µH, Isat 5 A) | **cjiang / Shenzhen CJiang Technology, CN** ([LCSC brand](https://www.lcsc.com/brand-detail/11425.html)) | [C177246](https://www.lcsc.com/product-detail/C177246.html) | 133,425 / 135,608 | **Not at DigiKey** (DK) | **PRC** |
| J_USB (1) | TYPE-C-31-M-12 | **"Korean Hroparts Elec" = HRO Electronics, PRC**. The name is misleading: LCSC says "Hro Electronics (Beijing) Co." ([brand](https://www.lcsc.com/brand-detail/947.html)); the datasheet address is Futian, Shenzhen ([GlobalSpec](https://datasheets.globalspec.com/ds/korean-hroparts-electronics-co-ltd/type-c-31-m-12/96051c6d-88f4-4ada-a496-ac84b7d8b9bc)) | [C165948](https://www.lcsc.com/product-detail/C165948.html) | 454,120 / 470,963 | **Not at DigiKey** (DK) | **PRC** |
| J_ESC (1) | SM08B-SRSS-TB(LF)(SN) | JST (Osaka, JP) | [C160407](https://www.lcsc.com/product-detail/C160407.html) | 120,870 / 123,874 | [455-1808-1-ND](https://www.digikey.com/en/products/result?keywords=SM08B-SRSS-TB(LF)(SN)): 52,530 (DK), $0.85 | OK |
| SW_BOOT (1) | TS-1088-AR02016 | **XUNPU (PRC, unverified)** | [C720477](https://www.lcsc.com/product-detail/C720477.html) | 788,460 / 937,757 | **Not at DigiKey** (DK) | **PRC** |
| C18, C19 (2) | 0402CG120J500NT (12 pF C0G) | **Guangdong Fenghua Advanced Technology (FH), CN** ([LCSC brand](https://www.lcsc.com/brand-detail/63.html)) | [C1547](https://www.lcsc.com/product-detail/C1547.html) | 1,264,300 / 2,084,824 | **Not at DigiKey** (DK) | **PRC** |
| 100 nF ×13 | CL05B104KB54PNC | Samsung Electro-Mechanics (Suwon, KR). MLCC plants in Suwon and Busan (KR), **Tianjin (CN)**, Calamba (PH) ([Samsung/Korea Herald](https://www.koreaherald.com/article/3488889), [SEMCO network](https://www.samsungsem.com/global/about-us/company/location.do)) | [C307331](https://www.lcsc.com/product-detail/C307331.html) | 2,936,300 / 14,265,042 | [1276-CL05B104KB54PNCCT-ND](https://www.digikey.com/en/products/result?keywords=CL05B104KB54PNC): 48,207 (DK) | KR maker; COO may be CN |
| 1 µF ×2 | CL05A105KA5NQNC | Samsung EM | [C52923](https://www.lcsc.com/product-detail/C52923.html) | 733,550 / 6,484,266 | [1276-1445-1-ND](https://www.digikey.com/en/products/result?keywords=CL05A105KA5NQNC): 2,318,576 (DK) | as above |
| 4.7 µF ×3 | CL05A475MP5NRNC | Samsung EM | [C23733](https://www.lcsc.com/product-detail/C23733.html) | 949,650 / 2,580,600 | [1276-1482-1-ND](https://www.digikey.com/en/products/result?keywords=CL05A475MP5NRNC): **out of stock**, no date (DK) | DigiKey supply |
| C3 10 µF 50 V 0805 (1) | CL21A106KBYQNNE | Samsung EM | [C2932476](https://www.lcsc.com/product-detail/C2932476.html) | **0** / 216,393 | [1276-CL21A106KBYQNNECT-ND](https://www.digikey.com/en/products/result?keywords=CL21A106KBYQNNE): **0; 2,000 due 15 Jun 2027** (DK) | DigiKey supply |
| C6, C7 22 µF 25 V 0805 (2) | CL21A226MAQNNNE | Samsung EM | [C45783](https://www.lcsc.com/product-detail/C45783.html) | 1,817,420 / 4,256,083 | 1276-2908-2-ND: **"Obsolete and no longer manufactured"** (DK) | **Obsolete** |
| 9 resistor values (10R, 100R, 330R, 1k, 2k, 5.1k, 10k, 15k, 100k), 0402 1 % | 0402WGFxxxxTCE | **UNI-ROYAL (UniOhm/Royalohm)**. Founded 1978 in Hsinchu, Taiwan ([LCSC blog](https://www.lcsc.com/blog/uni-royal-has-become-the-worlds-leading-manufacturer-of-chip-and-dip-resistor/)); operating HQ in Kunshan, Jiangsu, CN ([uni-royal.cn](https://www.uni-royal.cn/en/article.php?id=14)); plants in TW, Kunshan, Shenzhen, Xiamen and TH | e.g. 10k [C25744](https://www.lcsc.com/product-detail/C25744.html) (10.6M / 23.7M). All values are in stock at LCSC/JLC in the 100k–10M range (1.44M for 100R) | **Not at DigiKey** (DK search "0402WGF1002TCE": no results). Mouser lists Royalohm (index only) | Treat as **PRC-made** |

### 1b. 4-in-1 ESC (populated parts)

| Ref (qty) | MPN | Maker (HQ) | LCSC # | LCSC / JLC stock | DigiKey PN, stock | Flag |
|---|---|---|---|---|---|---|
| U_ESC1–4 (4) | STM32F051K6U6 | STMicroelectronics | [C81451](https://www.lcsc.com/product-detail/C81451.html) | **770 / 886** | [497-12950-ND](https://www.digikey.com/en/products/detail/stmicroelectronics/STM32F051K6U6/3193385): **0; 490 due 21 Oct 2026; 40-wk lead** (DK), $3.97 | **Largest supply risk** (4 per ESC) |
| U_GD1–4 (4) | JSM6288Q | **Shenzhen JSMicro (JSMSEMI), CN** ([LCSC brand](https://www.lcsc.com/brand-detail/12313.html)) | [C19077370](https://www.lcsc.com/product-detail/C19077370.html) | 21,922 / 31,887 | **Not at DigiKey** (DK) | **PRC** |
| Q (12) | AON7934 | Alpha & Omega (see AO3400A) | [C485677](https://www.lcsc.com/product-detail/C485677.html) | 129,080 / 129,263 | [785-1509-1-ND](https://www.digikey.com/en/products/detail/alpha-omega-semiconductor-inc/AON7934/3603569): **0; 5,000 due 2 Nov 2026; 16 wk** (DK), $1.73 | US maker, COO likely CN; DigiKey supply |
| U_BUCK (1) | LMR51420YDDCR | TI | as FC | | as FC | OK |
| L1 (1) | FNR3015S4R7MT | **cjiang, CN** | [C167753](https://www.lcsc.com/product-detail/C167753.html) | 97,060 / 97,608 | **Not at DigiKey** (DK) | **PRC** (a copy of Taiyo Yuden NR3015) |
| D1/5/9/13 (4) | BZX585-C15,135 (15 V zener, SOD-523) | **Nexperia (Nijmegen, NL), owned by Wingtech (CN)**. Wingtech was put on the BIS Entity List in Dec 2024. The Dutch government took control of Nexperia on 30 Sep / 13 Oct 2025 and suspended that control on 19 Nov 2025. Nexperia China now operates de facto separately (2026) ([CNBC](https://www.cnbc.com/2025/10/13/dutch-government-takes-control-of-chinese-owned-chipmaker-nexperia.html), [Morgan Lewis](https://www.morganlewis.com/pubs/2025/11/dutch-and-german-regulators-scrutinize-nexperia-transactions-amid-us-export-pressures), [Wikipedia](https://en.wikipedia.org/wiki/Nexperia)) | [C550633](https://www.lcsc.com/product-detail/C550633.html) | 154,900 / 154,919 | [1727-BZX585-C15,135CT-ND](https://www.digikey.com/en/products/result?keywords=BZX585-C15,135): **0; 10,000 due 4 Oct 2027** (DK) | **Chinese-owned**; DigiKey supply |
| D bootstrap (12) | RB521S-30 | **Jiangsu Changjing Electronics Technology (JSCJ), CN** ([LCSC brand](https://www.lcsc.com/brand-detail/64.html)) | [C8523](https://www.lcsc.com/product-detail/C8523.html) | 237,450 / 238,139 | JSCJ not at DigiKey. The MPN there comes from Goodwork and SLKOR (PRC), MCC and others (FC) | **PRC** |
| J_FC (1) | BM08B-SRSS-TB(LF)(SN) | JST | [C160394](https://www.lcsc.com/product-detail/C160394.html) | 10,535 / 12,480 | [455-BM08B-SRSS-TBCT-ND](https://www.digikey.com/en/products/result?keywords=BM08B-SRSS-TB(LF)(SN)): $0.82 (DK); 22,856 (FC) | OK |
| LED_PWR (1) | KT-0603R | Hubei KENTO, CN | as FC | | | **PRC** |
| MLCCs | 10 µF 0805 ×13, 100 nF ×19, 1 µF ×16, 4.7 µF ×4, 22 µF 0805 ×2 | Samsung EM | as FC | | as FC | 10 µF 0805: 0 at LCSC and DigiKey; 22 µF obsolete |
| Resistors (9 values) | 0402WGF… (1k, 330R, 750R, 100k, 10k ×24, 11k, 22k, 2.2k ×12, 2k) | UNI-ROYAL | 750R [C25132](https://www.lcsc.com/product-detail/C25132.html) 933,000; 11k [C25749](https://www.lcsc.com/product-detail/C25749.html) 65,200; 2.2k [C25879](https://www.lcsc.com/product-detail/C25879.html) 23,800 (the tightest) | Not at DigiKey | Treat as **PRC-made** |

### 1c. Entries in parts.py not placed on either board, and the README's second sources

| Entry | Maker (HQ) | LCSC # | LCSC / JLC | DigiKey | Note |
|---|---|---|---|---|---|
| ICM-42688-P | TDK InvenSense (JP/US) | [C1850418](https://www.lcsc.com/product-detail/C1850418.html) | **0** / 343 | 1428-ICM-42688-PCT-ND: 0 (FC); $4.86 on DigiKey search (DK, stock not shown) | OK origin, poor stock |
| W25Q128JVPIQ | Winbond (Taichung, TW) | [C190862](https://www.lcsc.com/product-detail/C190862.html) | **0** / 240 | [256-W25Q128JVPIQ-TUBE-ND](https://www.digikey.com/en/products/detail/winbond-electronics/W25Q128JVPIQ/6819668): 13,187 (DK), $3.93 | Non-PRC flash, already a drop-in |
| INA186A2IDCKR | TI | [C2058238](https://www.lcsc.com/product-detail/C2058238.html) | 10,244 / 10,244 | 296-INA186A2IDCKRCT-ND: 8,912 (DK) | Unused |
| 2N7002 | **JSCJ, CN** | [C8545](https://www.lcsc.com/product-detail/C8545.html) | 1,396,200 / 1,760,055 | JSCJ not at DigiKey | Use onsemi 2N7002LT1G instead ([C16338](https://www.lcsc.com/product-detail/C16338.html), 241,807 JLC; DigiKey 2N7002LT1GOS*: 972,839 (FC)) |
| RLM25FEGMR50M (shunt) | TA-I Technology (TW) | [C710260](https://www.lcsc.com/product-detail/C710260.html) | 203,110 / 203,115 | Not at DigiKey (DK) | Unused; not PRC |
| CL31A106KBHNNNE (1206) | Samsung EM | [C13585](https://www.lcsc.com/product-detail/C13585.html) | 217,940 / 2,545,427 | 1276-2876-1-ND: 0 (FC) | Unused |
| STM32G474CEU6 (README second source) | ST | [C1235412](https://www.lcsc.com/product-detail/C1235412.html) | **0** / 481 | 497-STM32G474CEU6-ND: 0 (FC) | No relief |
| MWSA0503S-4R7MT (README second source for L1) | **Sunlord (Shenzhen, CN)** | C408410 (LCSC API returned no record) | – / 26,334 | 3442-MWSA0503S-4R7MTCT-ND: 1,720 (FC) | **Also PRC**, so not an origin fix |
| AT32F421K8U7 (README ESC MCU second source) | **Artery Technology (Chongqing, CN)** ([LCSC brand](https://www.lcsc.com/brand-detail/12248.html)) | [C2965611](https://www.lcsc.com/product-detail/C2965611.html) | 4,599 / 4,874 | Not at DigiKey (DK) | **PRC**: keep out of any compliant SKU |
| DO6288Q, YC6288Q (README gate-driver second sources) | DOINGTER, YLPTEC (PRC, *unverified*) | [C42386238](https://www.lcsc.com/product-detail/C42386238.html), [C54157432](https://www.lcsc.com/product-detail/C54157432.html) | 3,428 / 3,428; 9,867 / 9,867 | Not found at DigiKey (FC) | **PRC** |
| RB521S30T1G (README second source) | onsemi (US) | [C145179](https://www.lcsc.com/product-detail/C145179.html) | 48,890 / 53,002 | RB521S30T1GOSCT-ND: 0; NSVRB521S30T1G: 2,531 (FC) | Non-PRC but thin at DigiKey |
| GRM21BR61H106KE43L (README second source) | Murata (Kyoto, JP) | [C440198](https://www.lcsc.com/product-detail/C440198.html) | 493,035 / 1,744,461 | 490-18663-1-ND: **0; 3,000 due 1 Apr 2027** (DK) | |

### 1d. Suggested non-PRC replacements

Each row below is a non-PRC-maker part stocked at both LCSC/JLC and DigiKey. "Same land?" says whether it fits the existing pads.

| Replace | With | Maker (HQ) | LCSC # (JLC stock) | DigiKey PN (stock) | Same land? |
|---|---|---|---|---|---|
| PY25Q128HA | **W25Q128JVPIM** (or …PIQ) | Winbond (TW) | [C2441427](https://www.lcsc.com/product-detail/C2441427.html) (25,157) / C190862 (240) | 256-W25Q128JVPIMTRCT-ND (63,269, FC) / 256-W25Q128JVPIQ-TUBE-ND (13,187, DK) | **Yes.** Same WSON-8 6×5 pads per README. /WP and /HOLD are tied to 3V3 in `circuit.py`, so the -IM variant (QE=0) works too. The CPL rotation differs; `parts.py` already has a W25Q128 entry for this |
| ME6211C33 | **TLV75533PDBVR** | TI (US) | [C404027](https://www.lcsc.com/product-detail/C404027.html) (138,951) | 296-50411-1-ND (84,742, DK), $0.45 | **Yes.** SOT-23-5 IN/GND/EN/NC/OUT, the same as `circuit.py`'s ME6211 map. Alt: Torex XC6220B331MR-G (JP) [C86534](https://www.lcsc.com/product-detail/C86534.html) (18,016), 893-1133-1-ND (15,602, FC) |
| 1N5819WS | **CUS10S40,H3F** (40 V, 1 A, USC = SOD-323) | Toshiba (JP) | [C5331522](https://www.lcsc.com/product-detail/C5331522.html) (5,445), C2762697 (7,369) | CUS10S40H3FCT-ND (50,084, FC) | Body yes; check that the cathode is pad 1 |
| KT-0603R | **LTST-C191KRKT** | Lite-On (TW) | [C125099](https://www.lcsc.com/product-detail/C125099.html) (207,243) | 160-1447-1-ND (1,517,473, FC) | 0603; check the polarity mark against the JLC footprint |
| XL-1608UBC-04 | **LTST-C191TBKT** | Lite-On (TW) | [C99290](https://www.lcsc.com/product-detail/C99290.html) (379,982) | 160-1647-1-ND (358,116, FC) | 0603, as above |
| TAXM8M4RDBCCT2T | **ECS-80-10-33-CHN-TR3** (8 MHz, 10 pF, 3.2×2.5) | ECS Inc. (Olathe, KS, US) | [C5727434](https://www.lcsc.com/product-detail/C5727434.html) (3,510) | 50-ECS-80-10-33-CHN-TR3CT-ND (19,121, DK), $0.65 | 3225 4-pad, yes. **ESR is 400 Ω max, so check the STM32G4 HSE gain margin (ST AN2867).** Alt: KDS 1C208000CE0Q (JP, 10 pF) [C133366](https://www.lcsc.com/product-detail/C133366.html) (5,202), not found at DigiKey |
| 0402CG120J500NT | **CL05C120JB5NNNC** | Samsung EM (KR) | [C26406](https://www.lcsc.com/product-detail/C26406.html) (187,443) | 1276-1178-1-ND (83,979, FC) | Yes |
| UniOhm 0402 | **Yageo RC0402FR-07xxxL** or **Panasonic ERJ-2RKFxxxxX** | Yageo (TW), Panasonic (JP) | 10k: [C60490](https://www.lcsc.com/product-detail/C60490.html) (9,003,293) / [C191123](https://www.lcsc.com/product-detail/C191123.html) (488,985) | 311-10.0KLRCT-ND (11.7M, FC) / P10.0KLCT-ND (4.07M, FC) | Yes. These are **extended** parts at JLC (setup fee per unique part). Yageo also has PRC plants (COO unverified) |
| JSM6288Q | **DRV8300DRGER** | TI (US) | [C3655801](https://www.lcsc.com/product-detail/C3655801.html) (15,324) | 296-DRV8300DRGERCT-ND (57,231, DK), $0.88 | **Pin map matches, checked against `circuit.py`.** See the note below this table |
| RB521S-30 (JSCJ) | **CES520,L3F** (30 V, 200 mA, SOD-523) | Toshiba (JP) | [C5618940](https://www.lcsc.com/product-detail/C5618940.html) (7,970) | CES520L3FCT-ND (5,523, DK), $0.19 | Body yes; check that the cathode is pad 1. The ROHM original RB521S-30TE61 (C84981) is 0 at LCSC and DigiKey |
| BZX585-C15 (Nexperia) | **ROHM EDZVT2R15B** (15 V, EMD2 ≈ SOD-523) | ROHM (Kyoto, JP) | [C209631](https://www.lcsc.com/product-detail/C209631.html) (12,141) | EDZVT2R15BTR-ND: **0; 8,000 due 11 Dec 2026** (DK) | Body yes. Alt: onsemi MM5Z15VT1G [C236108](https://www.lcsc.com/product-detail/C236108.html) (2,941); DigiKey stock *unconfirmed* (search says "in stock", Findchips says 0) |
| FXL0530-4R7-M | **Vishay IHLP2020CZER4R7M01** (5.49×5.18×3.0 mm, Isat 8.2 A, Irms 3.5 A, DCR 77.5 mΩ max) | Vishay (Malvern, US) | [C845006](https://www.lcsc.com/product-detail/C845006.html) (11,519) | 541-1270-1-ND (10,532, DK), $0.92 | **Same size class; land pattern not verified.** Higher DCR than the cjiang part, so expect about 0.3 W at 2 A |
| FNR3015S4R7MT | **TDK VLS3015ET-4R7M** (3×3×1.5) | TDK (Tokyo, JP) | [C76865](https://www.lcsc.com/product-detail/C76865.html) (5,589) | 445-6679 (2,327, FC); -CA variant 445-16723-1-ND (15,038, FC) | 3×3; land pattern not verified. Taiyo Yuden NR3015T4R7M (the original design) is 0 at both |
| CL21A226MAQNNNE (obsolete) | **Murata GRM21BR61E226ME44L** | Murata (JP) | [C86816](https://www.lcsc.com/product-detail/C86816.html) (356,719) | 490-10749-1-ND (1,986, DK) | Yes |
| CL05A475MP5NRNC (DigiKey out) | Murata GRM155R61A475MEAAD / TDK C1005X5R1A475M050BC | JP | [C335105](https://www.lcsc.com/product-detail/C335105.html) (30,767) / C3852325 (0) | 490-14306 (0, FC) / 445-8023-1-ND (≈1.0M, FC) | Yes, but **no single 4.7 µF 0402 part is in stock at both today** |
| CL21A106KBYQNNE (10 µF 50 V 0805) | none in stock at DigiKey | – | – | DigiKey's own substitute list shows Murata, TDK, Yageo and Samsung all at 0. Only Cal-Chip GMC21X5R106K50NT had 50,481 (origin unverified) (DK) | Buy early, or make a design decision (e.g. 4.7 µF 50 V X7R GRM21BZ71H475KE15L, 77,946 at DigiKey (FC)) |
| AO3400A (only if a non-China COO is wanted) | onsemi NTR4003NT1G / Vishay Si2302CDS-T1-GE3 | US | [C82325](https://www.lcsc.com/product-detail/C82325.html) (48,250) / [C10488](https://www.lcsc.com/product-detail/C10488.html) (90,072) | NTR4003NT1GOSCT-ND (48,809, FC) / SI2302CDS-T1-GE3CT-ND (231,202, FC) | SOT-23 G-S-D; both specified at 2.5 V Vgs. COO not verified |
| TYPE-C-31-M-12 | GCT USB4105-GF-A | GCT (UK) | [C3020560](https://www.lcsc.com/product-detail/C3020560.html) (1,188) | 2073-USB4105-GF-ACT-ND (132,187, FC) | **No: new footprint.** No verified non-PRC drop-in |
| TS-1088-AR02016 | C&K PTS810 SJM/SJG 250 SMTR LFS | C&K (US) | [C116501](https://www.lcsc.com/product-detail/C116501.html) (2,062), C221895 (14,452) | CKN10502CT-ND (75,873, FC) | **No: 4.2×3.2 body, new footprint** |
| AON7934 | **no verified pin-compatible non-PRC part** | – | – | – | Vishay PowerPAIR 3×3 or onsemi 3.3×3.3 dual-N parts likely need new pads (unverified). AOS itself is a US company |
| STM32F051K6U6 | STM32F051K8U6 (64 KB superset, same package and pins) | ST | C72339 (**2**) | 497-12892-ND: **3** (DK), 40 wk | No relief. Pre-buy or broker. STM32G071 (an AM32 target) needs a PCB change. ModalAI's NDAA ESCs use STM32F051K8 too ([ModalAI](https://www.modalai.com/products/voxl-esc-mini)), so the MCU choice is fine; the problem is supply |

**DRV8300 vs JSM6288Q (FD6288Q) pin by pin.** The repo's `circuit.py` map against the [DRV8300 datasheet](https://www.ti.com/lit/ds/symlink/drv8300.pdf) (Table 6-1):

| Pins | JSM6288Q (repo) | DRV8300 |
|---|---|---|
| 1–3 | LIN1–3 | INLA–C |
| 4 | VCC | GVDD |
| 5 | NC | MODE (floating = non-inverting) |
| 6 | GND | GND |
| 7–8 | NC | NC |
| 9–11 | LO3–1 | GLC–GLA |
| 12–20 | VS/HO/VB for each phase | SHx/GHx/BSTx in the same order |
| 21 | NC | DT (floating = fixed 200 ns dead time) |
| 22–24 | HIN1–3 | INHA–C |
| Pad | GND | GND |

The repo leaves pins 5 and 21 open, which gives non-inverted inputs and fixed dead time. Differences to check:

- **Gate supply.** GVDD is rated 5–20 V. The existing 15 V clamp stays.
- **Drive strength.** The DRV8300 sources 0.75 A and sinks 1.5 A, weaker than the FD6288 class, so edges are slower; watch FET temperature in bring-up step 6.
- **Bootstrap diodes.** The **DRV8300D** has them built in, so the external RB521S parts become optional (leave the pads).
- **Exposed pad.** 2.45 mm on the DRV8300 against a 2.7 mm land: check the paste aperture.
- **Dead time.** The chip's 200 ns adds to AM32's ~0.94 µs.

Build one ESC first.

**Distributor trap.** At DigiKey, "1N5819WS", "USBLC6-2SC6", "AO3400A", "RB521S-30" and "2N7002" each resolve to several makers, including PRC second-source makers (Goodwork, UMW, SLKOR, HUXN, EVVO). A DigiKey BOM for a compliant build must pin the **manufacturer** and the DigiKey part number, not just the MPN.

---

## 2. NDAA / US-government angle

### What each rule actually restricts

**FY2020 NDAA §848** (Pub. L. 116-92, as amended by FY2023 NDAA §817; set out as a note to 10 U.S.C. 4871; text on [govinfo, p. 2846](https://www.govinfo.gov/content/pkg/USCODE-2023-title10/pdf/USCODE-2023-title10-subtitleA-partV-subpartI-chap385-subchapIII-sec4872.pdf)).
- It binds **DoD only**. The Secretary of Defense may not operate or procure a UAS that:
  - (A) "is manufactured in a covered foreign country or by an entity domiciled in a covered foreign country";
  - (B) "uses **flight controllers, radios, data transmission devices, cameras, or gimbals** manufactured in a covered foreign country or by an entity domiciled" there;
  - (C) uses a ground control system or operating software developed there;
  - (D) uses network or data storage administered by such an entity.
- Covered countries: PRC, Russia, Iran, North Korea.
- From 1 Oct 2024 DoD also may not contract with firms that operate equipment from a "covered UAS company" (DJI and similar).
- **ESCs and motors are not named. Nor are the chips inside a flight controller.** The FC as a unit must not be manufactured in China (or the other three), and an FC assembled by JLCPCB or PCBWay is. The statute does not reach resistors inside a US-assembled FC. DIU's component-definition guidance page ([diu.mil/blue-uas-policy](https://www.diu.mil/blue-uas-policy)) now only shows the DCMA-transition notice, so I could not read DIU's sub-component interpretation (*unverified*).

**American Security Drone Act of 2023** (FY2024 NDAA §§1821–1833; [Pub. L. 118-31 text](https://www.govinfo.gov/content/pkg/PLAW-118publ31/pdf/PLAW-118publ31.pdf); implemented by [FAR 52.240-1](https://www.acquisition.gov/far/52.240-1)).
- It applies to **all federal executive agencies**. The test is **who built it**, not where the components come from.
- **§1823:** no procurement of a UAS "manufactured or assembled by a covered foreign entity", including "associated elements … (consisting of communication links and the components that control the unmanned aircraft)". This took effect immediately.
- **§1824:** no federal operation of such UAS from **22 Dec 2025**.
- **§1825:** no federal funds (contracts, grants, cooperative agreements) for them from 22 Dec 2025. This reaches state and local grantees.
- **§1826:** no purchase with government purchase cards, immediately.
- **§1833:** §§1823–1825 sunset on 22 Dec 2028.
- A "covered foreign entity" is one on the FASC list published in SAM. The list's categories include the Consolidated Screening List and "any entity domiciled in the People's Republic of China or subject to influence or control" by the PRC or CCP, plus their affiliates (§1822). I did not check whether the FASC list names any PCB assembler.

**DIU / DCMA Blue UAS.**
- Two lists: the Cleared List (whole UAS) and the **Framework** (components and software assessed as §848-compliant).
- Per the 10 Jul 2025 Secretary of War memo "Unleashing U.S. Military Drone Dominance", both are **moving from DIU to DCMA** ([DIU notice](https://www.diu.mil/blue-uas/framework)). The live portal is at [bluelist.appsplatformportals.us](https://bluelist.appsplatformportals.us/UAS-Framework/). Its data endpoint returned an empty list to my anonymous request, so **I could not read the live list.**
- FPV items that the makers say are on the Framework:
  - Rotor Riot Brave F7 FC ([Aug 2024 press release](https://www.nasdaq.com/press-release/unusual-machines-fpv-flight-controller-approved-blue-uas-framework-2024-08-07));
  - Brave 55A 4-in-1 ESC ([Jan 2025](https://www.nasdaq.com/press-release/unusual-machines-adds-electronic-speed-controller-blue-uas-framework-2025-01-17));
  - ARK FPV FC and ARK 4IN1 ESC ([ARK](https://arkelectron.com/product/ark-4in1-esc/));
  - ModalAI VOXL ESCs ([ModalAI](https://www.modalai.com/pages/blue-uas-framework));
  - Vertiq modules (directory listings only; *unverified*).

**FCC Covered List: the rule that affects commercial sales to US buyers.**
- **22 Dec 2025** ([DA 25-1086](https://docs.fcc.gov/public/attachments/DA-25-1086A1.pdf)): added "UAS and UAS critical components **produced in a foreign country**".
  - Critical components "include[] but [are] not limited to": data transmission devices, communications systems, **flight controllers**, GCS/controllers, navigation, sensors and cameras, batteries/BMS, **motors**.
  - Covered equipment can get **no new FCC equipment authorization, SDoC included**. Already-authorized models are unaffected.
  - FAQ ([FCC fact sheet/FAQ, 7 Jan 2026](https://docs.fcc.gov/public/attachments/DOC-417528A1.txt)): "The specific nationality of the entity or entities producing … is not relevant". An allied-country assembler is therefore covered too.
  - Only parts "designed and intended primarily for use in UAS" count, which a 3" FC/ESC plainly is.
  - "No device now requires FCC equipment authorization that did not already require FCC equipment authorization."
- **7 Jan 2026:** exemptions added for (a) Blue UAS Cleared List/Framework items and (b) "domestic end products" under Buy American (48 CFR 25.101(a)). The FCC describes (b) as "assembled in the U.S. with at least 65 % of components by value produced in the U.S." ([21 Jul 2026 fact sheet](https://docs.fcc.gov/public/attachments/DOC-423277A1.pdf)).
- **18 Mar 2026:** first DoW **Conditional Approvals** ([DA 26-253](https://docs.fcc.gov/public/attachments/DA-26-253A1.txt)), granted to foreign producers who commit to an **onshoring plan**. More followed on 26 May 2026 ([DA 26-524](https://docs.fcc.gov/public/attachments/DA-26-524A1.pdf)).
- **15 Jun 2026:** "Toy Drone" exemption ([DA 26-588](https://docs.fcc.gov/public/attachments/DA-26-588A1.pdf)): at most 150 g, no camera, **no brushless motors**. FPV does not qualify.
- **17 and 21 Jul 2026:** two proposals to ban further import and marketing of some *previously authorized* foreign UAS and components ([DA 26-742](https://docs.fcc.gov/public/attachments/DA-26-742A1.pdf), aimed at named entities such as XAG; [DA 26-758](https://docs.fcc.gov/public/attachments/DA-26-758A1.pdf), aimed at "military-grade" ≥55 lb or swarm-capable systems). These are not final.
- **21 Jul 2026:** the Blue UAS and Buy American exemptions were **extended to 1 Jan 2028**, and Conditional Approvals no longer expire as long as the onshoring plan is followed ([fact sheet](https://docs.fcc.gov/public/attachments/DOC-423277A1.pdf)).
- **Open question for OG3.** A radio-less FC/ESC is a Part 15 "digital device". 47 CFR 15.103(a) exempts "a digital device utilized exclusively in any transportation vehicle including … aircraft" ([LII](https://www.law.cornell.edu/cfr/text/47/15.103)). §15.103(j) removes that exemption only for entities "identified on the Covered List", and the FCC says UAS-component producers are *not* "identified" ([FAQ](https://docs.fcc.gov/public/attachments/DOC-417528A1.txt)). **Whether the stack needs an SDoC at all is therefore arguable. Get a TCB or FCC-counsel opinion; this is my reading, not settled.** Anything with a radio (ELRS receiver, VTX) clearly needs authorization.

**Also relevant.**
- **10 U.S.C. §4873 (PCBs).** From **1 Jan 2027** DoD may not acquire "covered" bare or assembled PCBs from China, Russia, Iran or North Korea for mission-critical or defense-security-system uses ([LII](https://www.law.cornell.edu/uscode/text/10/4873)). The DFARS rule was still an ANPR (2 Jul 2026, comments closed 31 Aug 2026; [Crowell](https://www.crowell.com/en/insights/client-alerts/at-long-last-dow-signals-rule-implementing-pcb-prohibition-and-commercial-exemptions)). The *bare board* fab location matters for DoD work, not only the assembler.
- **10 U.S.C. §4872.** Restricts DoD buying "covered materials" (e.g. certain magnets, tungsten, tantalum) from the same four countries ([same govinfo PDF](https://www.govinfo.gov/content/pkg/USCODE-2023-title10/pdf/USCODE-2023-title10-subtitleA-partV-subpartI-chap385-subchapIII-sec4872.pdf)). It is relevant to motors later; OG3 has no tantalum capacitors.
- **Commerce.** The FCC FAQ notes a separate BIS ICTS rulemaking and a Section 232 investigation covering UAS. I did not research either.
- **Tariffs.** The de minimis exemption for imports stays suspended ([EO 14388, 20 Feb 2026](https://www.whitehouse.gov/presidential-actions/2026/02/continuing-the-suspension-of-duty-free-de-minimis-treatment-for-all-countries/)). SpeedyBee's US store collects a "54 % prepaid tax" on US orders ([SpeedyBee listing](https://www.speedybee.com/speedybee-f405-aio-v2-35-40a-bluejay-25-5x25-5-3-6s-flight-controller/)). I did not verify the current tariff stack for PCBAs; ask a customs broker.

### What this implies

**(a) Where the boards are assembled**

| Assembly | §848 (DoD) | ASDA (federal agencies and grantees) | FCC (any US retail, if authorization is needed) |
|---|---|---|---|
| JLCPCB / PCBWay (PRC) | FC fails ("manufactured in" PRC) | Assembler is a PRC-domiciled entity: in the listable category | Foreign-produced; no exemption realistically available |
| Allied country (TW, JP, KR, EU, UK, CA, AU …) | FC passes if the assembler is not PRC-controlled | Passes | **Still "produced in a foreign country"**; needs Blue UAS listing or a Conditional Approval |
| US | Passes | Passes | Covered unless Blue UAS **or** Buy American (US-assembled **and** >65 % US component value). With ST, Bosch, Winbond and TI chips largely made abroad, 65 % is unlikely, so **Blue UAS Framework listing is the practical exemption** (currently to 1 Jan 2028) |

**(b) Which component makers to avoid**

The law only bans named assemblies. In practice, keep these out of any compliant SKU:
- PRC-domiciled makers of every active part and connector. Today that means Puya, Microne, JSMSEMI, JSCJ, Hottech, HRO, XUNPU, cjiang and Sunlord, Yajingxin, KENTO, XINGLIGHT, FH, and also Artery, DOINGTER and YLPTEC from the README's second sources.
- PRC-owned makers (Nexperia/Wingtech).
- Anything on the Entity List or Consolidated Screening List.

Passives matter less legally but show up in assessor and customer questionnaires. Also watch parts sold under a "clean" MPN by PRC second-source makers.

"NDAA compliant" claims in the market are loose. Rotor Riot lists the TBS Lucid 90A ESC as "NDAA Compliant Product Made in USA", yet its firmware target is `AM32_TBS_12S_F421` ([listing](https://rotorriot.com/products/lucid-90a-12s-am32-esc-ndaa)). That naming implies an Artery AT32F421 MCU, which is my inference and *unverified*. Such claims are about assembly location, not the full BOM.

### What a small maker should do now so it can become compliant later

1. **One PCB, two BOMs.** Keep the JLC BOM ("OG3") and add a DigiKey BOM ("OG3-N") using §1d. Most swaps fit the current pads. In the next revision, before any board is built, change the **USB-C** (GCT USB4105) and **boot switch** (C&K PTS810) footprints. Also check the IHLP-2020 and VLS3015 lands, or add dual footprints.
2. **Prototype the DRV8300 ESC variant now.** It removes the only PRC IC on the ESC with no copper change. Keep the STM32F051. Do **not** use the AT32F421 path in any "compliant" SKU.
3. **Lock down supply.** Pre-buy STM32F051K6/K8 and STM32G473 from authorized distributors; both are 40–52-week parts at DigiKey. Choose replacements for the obsolete 22 µF and the scarce 10 µF 50 V 0805.
4. **Keep provenance records per lot.** Record maker, HQ, COO (from the reel label or DigiKey), date and lot codes, and the distributor invoice. Buy compliant builds only from authorized distributors (DigiKey, Mouser, Arrow). This is what DCMA/Blue UAS assessors and government customers ask for.
5. **Move the bare-board fab out of China for the compliant SKU** (10 U.S.C. 4873 from 2027). The same Gerbers fit any 6-layer ENIG vendor; the ESC's POFV via-in-pad is a standard option.
6. **Get the FCC question answered** (SDoC needed or §15.103(a) exempt?) before selling in the US. If authorization is needed, a foreign-assembled OG3 can only reach US retail through Blue UAS listing or a Conditional Approval. Plan **US final assembly plus a Blue UAS Framework submission** before scaling US sales (process and cost not researched).
7. **Firmware.** Build Betaflight and AM32 from pinned source in-house, as the repo already does. §848(C) covers GCS and operating software "developed in" a covered country; Blue UAS assessments include software. *How open-source firmware is treated: unverified.*
8. **Be precise in marketing.** Say, for example, "assembled in USA; BOM free of PRC-domiciled manufacturers (list on request)". Do not say "NDAA compliant" or "Blue UAS" until it is true and documented. False compliance claims carry real risk, including False Claims Act exposure on government sales.
9. Export classification for allied customers (EAR/ITAR) was not researched.

---

## 3. Market benchmark

### Reference board: GEPRC TAKER G4 AIO (owner paid about $80)

Specs are from the retailer copies of GEPRC's spec sheet; geprc.com blocked automated fetches.

| | TAKER G4 **45A** 8-bit AIO | TAKER G4 **35A** AIO |
|---|---|---|
| MCU | STM32G473CEU6, 170 MHz | same |
| Gyro | ICM-42688-P | same |
| OSD | AT7456E (analog, Betaflight OSD) | same |
| UARTs | 1, 2, 4, 5 | same |
| BEC | 5 V 3 A | 5 V 3 A |
| ESC | 45 A continuous, 50 A burst; "ESC MCU: QF32MT", 8-bit (as listed) | 35 A continuous, 45 A burst; BB21F16G; J-H-15 |
| Input | **2–6S** | **2–4S** |
| Current meter | yes | yes |
| Board / mount | 33.8 × 34.1 mm; **25.5 × 25.5 mm** | 33.4 × 34.4 mm; 25.5–26.5 mm slots |
| Weight | 9 g | 7.7 g |
| FC target | TAKERG4AIO | TAKERG4AIO |
| VTX | Analog via on-board OSD; digital via a UART (no HD plug mentioned in the listing) | same |
| Price (27 Sep 2026) | [MyFPV $79.99 (out of stock)](https://www.myfpvstore.com/fpv-electronics/flight-controllers/aio-boards/geprc-taker-g4-45a-8bit-aio/), [Pyrodrone $82.99](https://pyrodrone.com/products/geprc-taker-g4-45a-aio-flight-controller-and-2-6s-45a-esc-25x25mm), [FPVFaster $95.00](https://www.fpvfaster.com/products/geprc-taker-g4-45a-8bit-aio-flight-controller-25-5x25-5mm) | [Pyrodrone $73.99](https://pyrodrone.com/products/geprc-taker-g4-35a-aio-flight-controller-and-2-4s-35a-esc-25x25mm) |

The owner's ~$80 matches the **45A** board.

### Comparable 3-inch AIOs and 20×20 stacks (all PRC-made; none claims NDAA)

| Product | Format | MCU / gyro | ESC | Input | Street price |
|---|---|---|---|---|---|
| SpeedyBee F405 Mini BLS 35A stack | 2-board, 20×20 (M2/M3), 32 × 35 mm | F405 / ICM-42688P, AT7456E, baro, BLE | 35 A BLHeli_S 8-bit | 3–6S | [$64.99 SpeedyBee](https://www.speedybee.com/speedybee-f405-mini-bls-35a-20x20-stack/); [$76.99 Pyrodrone](https://pyrodrone.com/products/speedybee-f405-mini-bls-stack-w-35a-3-6s-blheli_s-4in1-esc-20x20mm); [$110.99 RDQ](https://www.racedayquads.com/products/speedybee-f4-3-6s-20x20-stack-combo-f405-fc-35a-8bit-4in1-esc) |
| SpeedyBee F405 AIO 40A (V1) / AIO V2 35/40A | AIO, 25.5 × 25.5; V1 33 × 33 mm, V2 36.5 × 36.5 mm | F405 / ICM-42688P, 8 MB flash | 40 A / 45 A (10 s), Bluejay | 3–6S | V1 [$71.99 Pyrodrone](https://pyrodrone.com/products/speedybee-f405-40a-bluejay-3-6s-aio-flight-controller-esc-25-5x25-5mm) / [NewBeeDrone](https://newbeedrone.com/products/speedybee-f405-aio-40a-bluejay-25-5x25-5-3-6s-flight-controller); V2 [$56.99 SpeedyBee, "Discontinued"](https://www.speedybee.com/speedybee-f405-aio-v2-35-40a-bluejay-25-5x25-5-3-6s-flight-controller/) |
| BetaFPV F405 4S 20A Toothpick V5 | AIO, 25.5 × 25.5 | F405RGT6 / ICM42688, AT7456E | 20 A / 25 A, EFM8BB21, Bluejay | 2–4S | [$67.99 BetaFPV](https://betafpv.com/products/f405-4s-20a-toothpick-brushless-flight-controller-v5-blheli_s-icm42688); [$81.99 RDQ](https://www.racedayquads.com/products/betafpv-f405-v5-2-4s-aio-whoop-toothpick-flight-controller-w-20a-8bit-4in1-esc-icm42688) |
| Holybro Kakute H7 Mini + Tekko32 F4 Mini 50A (AM32) | 2-board, 20×20 | H7 / ICM-42688-P (v1.5), 1 Gb NAND | 50 A / 60 A, F4 MCU, AM32 | 4–6S | [$128.98 Holybro store](https://holybro.com/products/kakute-h7-mini-stacks). Holybro's PRC location is *unverified* here |
| iFlight BLITZ Mini F722 + E55 V1.3 | 2-board, 20×20 | F722 / BMI270, 16 MB, DPS310 | 55 A / 60 A, G071, BLHeli_32 | 2–6S | [$139.99 RDQ (out of stock)](https://www.racedayquads.com/products/iflight-blitz-mini-f722-e55-2-6s-20x20-stack-combo-f722-fc-55a-32bit-4in1-v1-3-esc) |
| HGLRC Zeus F745 V2 (F722 mini + 45A) | 2-board, 20×20 M3 | F722 / MPU6000 or BMI270 | 45 A / 55 A, BLHeli_S | 3–6S | [$122.99 Pyrodrone](https://pyrodrone.com/products/hglrc-zeus-f745-v2-stack-20x20-3-6s-f722-flight-controller-45a-blheli_s-4in1-esc) |
| T-Motor Mini F7 + Mini F45A | 2-board, 20×20 | F7 / BMI270, 10 V BEC | 45 A, BLHeli_32 | 3–6S | [$154.99 Pyrodrone](https://pyrodrone.com/products/t-motor-mini-f45a-mini-f7-stack-20-20mm) |

Happymodel: its 3-inch-class AIOs are 1–4S whoop boards with an integrated receiver, such as the [Super F405HD ELRS 20A](https://www.happymodel.cn/index.php/2024/01/05/super-f405hd-elrs-aio-3in1-flight-controller-built-in-uart-2-4g-elrs-and-20a-esc-for-hd-whoops-25-5x25-5mm-mount-hole/). I found no Happymodel product that is a direct 4S 3-inch stack, and got no price.

### NDAA-claiming FCs and ESCs (none found in 20×20 or 25.5 mm)

| Product | Made in / claim | Format | Key specs | Price |
|---|---|---|---|---|
| Rotor Riot (Unusual Machines) **Brave F7 V2** FC | Orlando, FL; Blue UAS Framework | 37 × 37 mm, 30×30 holes (per search summary) | STM32F722RET6, BMI270, 3–8S (per search summary) | [$58](https://rotorriot.com/products/rotor-riot-brave-f7-flight-controller-made-in-usa) |
| Rotor Riot **Brave 55A** 4-in-1 (AM32) | USA; Blue UAS Framework | 30×30 class | 55 A continuous | [$115](https://rotorriot.com/products/rotor-riot-brave-55a-4in1-32bit-esc-am32-made-in-usa). Brave FC + ESC = **$173** |
| TBS **Lucid H7** FC | "NDAA Compliant Product Made in USA" (Rotor Riot listing) | 30×30 | H743, MPU6000, 2–8S, SD card | [$69.95](https://rotorriot.com/products/lucid-h7-30x30-flight-controller-ndaa) |
| TBS Lucid 90A 12S ESC (single, not 4-in-1) | same claim | 57.75 × 29 mm | 70 A, 3–12S; target `AM32_TBS_12S_F421` | [$59.95](https://rotorriot.com/products/lucid-90a-12s-am32-esc-ndaa) |
| **ARK FPV** FC | USA; Blue Framework listed | 30.5 mm | STM32H743IIK6, IIM-42653, 3–12S | [$194.99](https://arkelectron.com/product/ark-fpv-flight-controller/) |
| **ARK 4IN1 ESC** | USA; Blue Framework listed | 30.5 mm, 43 × 40.5 mm | STM32F0, 50 A continuous / 75 A burst | [$218.50](https://arkelectron.com/product/ark-4in1-esc/) (connectorized version [$238.50](https://arkelectron.com/product/ark-4in1-esc-cons/)) |
| **ModalAI VOXL ESC Mini** (M0129) | US-assembled; §848; Blue UAS Framework | 36.5 × 36.5 mm | STM32F051K8, 40 A continuous / 100 A peak, 2–4S or 2–6S, UART protocol (PX4/VOXL) | [$229.99](https://www.modalai.com/products/voxl-esc-mini) |
| ModalAI VOXL ESC FPV (M0138) | same | 30.5 mm | 40 A continuous, 2–6S | [$299.99](https://www.modalai.com/products/m0138) |
| **Orqa** 3030 Lite F405 FC | "made in the EU", NDAA | 30×30 | F405, MPU6000 or BMI270, 2–6S | [$147.99 RDQ](https://www.racedayquads.com/products/orqa-3030-lite-f405-flight-controller-ndaa); Orqa 3030 FC [$125.50 NewBeeDrone (out of stock)](https://newbeedrone.com/products/orqa-3030-flight-controller) |
| **Orqa 4in1 3030 ESC** | EU, NDAA | 30×30, ~28 g | 70 A continuous / 80 A (10 s), AM32, 3–6S | [$169.95 Orqa](https://shop.orqafpv.com/products/orqa-orqa-electronic-speed-controller); [$181 NewBeeDrone](https://newbeedrone.com/products/orqa-4in1-3030-esc-electronic-speed-controller) |
| Vertiq | Motor + ESC modules; Blue UAS Framework per directories | – | – | Price not found |
| "Holybro Pixhawk-derived" | Holybro is a PRC company (*unverified*). The US-made Pixhawk-standard option is ARK's (ARKV6X family) | – | – | not priced |

### Where a $50–70 two-board swappable stack would sit

- **Price.** At the level of the Chinese mainstream: SpeedyBee F405 AIO $57–72, SpeedyBee Mini stack $65–77, BetaFPV V5 $68, GEPRC TAKER G4 $74–95. It is about **one third of the cheapest NDAA-claiming FC+ESC pair** ($173), and there is no NDAA option at all in 25.5 mm or 20×20.
- **Specs.** Below the market.
  - OG3 is 4S only; the ESC current rating is not yet measured; there is no OSD chip (analog OSD would not work; MSP DisplayPort for digital would), no current sensor, no barometer, and 3 UARTs.
  - The TAKER G4 45A has 45 A, 2–6S, an AT7456E OSD, a current meter and 4 UARTs.
- **Positioning.** OG3 cannot win on specs at the same price. Its case is:
  1. **repairability**: two swappable boards, a standard 8-pin JST-SH lead, a 25.5 mm drop-in for TAKER-class frames;
  2. **an open design with a documented non-PRC BOM**;
  3. a **path to US assembly and Blue UAS listing**, where the only competition is 30×30 at $58–300 per board.
- **Cost check.** Component cost is $32.53 at 1 set, $20.52 at 100 and $18.64 at 1,000 (README; JLC prices, before assembly and boards). The DigiKey non-PRC BOM costs more (MCUs alone: G473 $5.97 and F051 about $2.47 each at 100 on DigiKey), and US assembly costs more again. At $50–70 retail, US-assembled margins are thin. A higher "NDAA-path 3-inch" price point, perhaps $90–130, is more realistic for OG3-N; that figure is my estimate, not researched. The JLC-built OG3 competes head-on with SpeedyBee and BetaFPV on price, and faces US tariffs and the open FCC question.

---

## 4. Name check

**USPTO.** I queried the backend of the USPTO trademark search (`tmsearch.uspto.gov/prod-stage-v1-0-0/tmsearch`) on 27 Sep 2026. The public UI is at [tmsearch.uspto.gov](https://tmsearch.uspto.gov); records can be looked up by serial number.

| Query | Results | Drone-relevant conflict? |
|---|---|---|
| OG3 | Live: **OG3** SN 99938119 (class 3, dental preparations; individual, Ojai CA; filed 13 Jul 2026). **CARL OG3** Reg. 7967324 (class 43, restaurant). Dead: OG3 THREE (class 35); CARL OG3 BURGER SHOP | **None** in classes 9/12/28/42 |
| OG 3 / OG-3 | Dead: **OG-3**, Jada Toys, Reg. 3051440, class 28 (diecast and RC toy vehicles), *cancelled §8*. Others unrelated | None live |
| OG7 / OG 7 / OG-7 | 0 hits; only "7-ELEVEN OG TO-GO…" (class 30) | None |
| OG12 / OG 12 / OG-12 | 0 relevant hits | None |
| OFFGRID / OFF GRID / OFF-GRID | 39 and 230+ records. Live class 9 marks: **OFFGRID** Reg. 6076046 (EDEC Digital Forensics; Faraday bags / RF shielding); OFF-GRID SERIES Reg. 7214454 (Lithionics, lithium batteries); OFF GRID Reg. 5439610 (Wind Rivers, solar batteries and chargers); OFF-GRID APPS Reg. 7183635 (software); RECOIL OFFGRID Reg. 5286845; OFFGRID SN 97528198 (class 12/22 vehicle tents, suspended). A combined query for "OFFGRID"/"OFF GRID"/"OG" marks whose goods mention drones or unmanned craft returned **none** | No drone mark found. **But OFFGRID in class 9 (electronics-adjacent) could cause a likelihood-of-confusion refusal** for an "OffGrid" house mark on drone electronics. Needs attorney clearance |

**Web.**
- **"OG7" collides with the OG-7(V)**, the RPG-7 fragmentation round, one of the standard FPV strike-drone warheads in the Russia–Ukraine war ([DroneXL](https://dronexl.co/2023/02/01/ukraine-fpv-drones-rpg-7/), [BattlePolicy](https://www.battlepolicy.com/rpg-7/)). "OG7" is also a warhead in the Steam game *FPV Kamikaze Drone* ([Steam discussion](https://steamcommunity.com/app/2707940/discussions/0/4511002214528149843/)). This is not a legal conflict, but it is a strong association for a 7-inch drone product sold to government and allied customers, with bad optics and possible export-screening questions. **Consider another suffix scheme.**
- **"OG3"** is one letter from DJI's "O3" air unit, which is ubiquitous in FPV. That is a search and SEO confusion risk, not a legal one. I found no FPV product called OG3.
- **"OffGrid" drones.** [Off Grid Drone Service LLC](https://www.offgriddroneservice.com/) (drone inspection services) and [RECOIL OFFGRID](https://www.offgridweb.com/transportation/drones-for-disaster-preparedness/) (a magazine that covers drones). I found no drone hardware brand named OffGrid.
- **Not checked:** EUIPO, UKIPO, CIPO, IP Australia or WIPO, which would matter for "allied nations" sales. Also no common-law and domain search beyond the above.

---

## 5. What I could not confirm

- Any **Mouser** stock (site blocked).
- Live **Blue UAS Framework** entries (portal data not served to anonymous clients). The makers' own claims are cited instead.
- HQ city for **XINGLIGHT, XUNPU, DOINGTER, YLPTEC** (brand pages unreadable; PRC assumed).
- Country of origin for most ICs (ST, Bosch, TI, Winbond, Samsung lots vary). Only AOS (China assembly) and Samsung's MLCC plants are sourced.
- DigiKey stock for these parts: MM5Z15VT1G, ICM-42688-P (quantities not shown on the pages I could read), BM08B-SRSS-TB, and all rows marked (FC).
- Land-pattern compatibility for the IHLP-2020, VLS3015, CUS10S40 and CES520 polarity, LTST-C191 polarity, and the DRV8300 exposed pad (checked against datasheet pin tables only, not the footprint files).
- GEPRC's own price and full spec page (blocked); whether the 45A board's "QF32MT" ESC MCU name is accurate.
- Brave F7 V2 MCU, gyro and hole pattern (from a search summary only).
- Whether OG3 needs FCC equipment authorization (legal reading in §2, not a determination).
- Tariff rates on PCBAs from China (the de minimis suspension is confirmed; the rest is not).
