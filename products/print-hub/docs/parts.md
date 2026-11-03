# Print Hub v1: parts, stock and second sources

Read from JLCPCB's assembly catalogue on **17 Oct 2026** (`tools/lcsc.py`).
Stock moves: read it again before ordering. Price is JLCPCB's unit price at
about 10 pieces. "Basic" parts carry no setup fee; every distinct
"extended" part adds about $3 to an order (preferred-extended ones may be
waived: check the quote). Every IC below is listed as active (not NRND).

| Role | Part (maker) | LCSC | JLC | Stock | $ each | Second source |
|---|---|---|---|---|---|---|
| Wi-Fi + USB microcontroller | ESP32-S3-WROOM-1-N8 (Espressif) | C2913198 | extended | 1,696 | 4.24 | ESP32-S3-WROOM-1-N16R8, C2913202 (32,719): same land, IO35-37 unused here |
| USB-PD sink, I2C | HUSB238_002DD (Hynetek) | C7471904 | extended | 13,752 | 0.47 | HUSB238A-BB001 C24833806; CH224A C42459160 (different pinout and registers) |
| Buck 9 V -> 5.16 V, 8 A | SY8368AQQC (Silergy) | C207642 | extended | 14,077 | 0.52 | TPS566238PRQFR C2876603 (18 V max in); LMR51450 C6890985 |
| 3.3 V LDO, 600 mA | AP2112K-3.3TRG1 (Diodes) | C51118 | extended | 7,685 | 0.17 | XC6220B331MR-G C86534 (1 A) |
| USB ESD | USBLC6-2SC6 (ST) | C7519 | extended | 34,727 | 0.18 | USBLC6-2SC6 (UMW) C2687116, pin compatible |
| Port switch x5 | TPS25200DRVR (TI) | C128401 | extended | 20,531 | 0.33 | AP22653W6-7 C2158037 (6 V input max, no output clamp) |
| Current-sense amplifier x5 | INA180A2IDBVR (TI) | C192764 | extended | 100,584 | 0.19 | INA181A2IDBVR C2058784 (SOT-23-6: new land) |
| Current shunt x5 | RLS12FTCR020, 20 mOhm 1 W 1206 (TA-I) | C163047 | extended | 25,568 | 0.035 | RLM12FTCMR020 C393094 |
| RGB LED x6 | WS2812B-2020-V6 (Worldsemi) | C52917434 | extended | 932,040 | 0.09 | WS2812C-2020-V6 C55109522 |
| Buck inductor | FXL0630-2R2-M, 2.2 uH 9.5 A (Changjiang) | C167218 | extended | 52,956 | 0.09 | MWSA0603S-2R2MT C408445 |
| Input TVS | SMAJ15A (hongjiacheng) | C19077535 | preferred | 102,505 | 0.04 | SMAJ15A from any maker (SMA) |
| Logic OR diodes x2 | B5819W SL (Changjiang) | C8598 | basic | 357,817 | 0.03 | |
| USB-C x2 | TYPE-C-31-M-12 (Korean Hroparts) | C165948 | extended | 365,608 | 0.19 | TYPE-C-31-M-12A C5337088 |
| USB-A x5 | 902-131A1011D10100, through-hole (Jing Extension) | C2345 | extended | 30,391 | 0.06 | 903-131A C46407; Molex 67643-0910 C2798029 |
| Buttons x2 | TS-1187A-B-A-B (XKB) | C318884 | basic | 295,813 | 0.02 | |
| 75k feedback resistor | 0402WGF7502TCE (UNI-ROYAL) | C25798 | preferred | 23,956 | 0.002 | |
| Other resistors and capacitors | UNI-ROYAL 0402, Samsung MLCC | (parts.py) | basic | millions | | |

**Fees:** 13 extended + 2 preferred-extended part types: about $39-45 per
order. Parts on the board come to about $11.50; the module is $4.24 of it.

## Pin numbers checked against the maker's symbol

The EasyEDA footprint's pad numbers are the ones JLCPCB places by. Each
was read back from the part's EasyEDA symbol (17 Oct 2026):

| Part | Pads |
|---|---|
| TPS25200 | 1 OUT, 2 ILIM, 3 FAULT, 4 EN, 5 GND, 6 IN, 7 pad |
| WS2812B-2020 | 1 DO, 2 GND, 3 DI, 4 VDD |
| B5819W | 1 cathode (-), 2 anode (+) |
| SMAJ15A | 1 cathode (K), 2 anode (A) |
| USB-A C2345 | 1 VBUS, 2 D-, 3 D+, 4 GND, SH1/SH2 shell |
| USB-C C165948 | contacts by name (A5 CC1, B5 CC2, A6/B6 D+, A7/B7 D-, A4B9/B4A9 VBUS, A1B12/B1A12 GND), 1-4 shell |
| Button C318884 | A, B, C, D: which pairs are joined inside is not marked, so the board uses the diagonal pads 1 and 4, which are always on opposite sides |

The other ICs' pins were checked against their datasheets: HUSB238 (DFN-10:
1 VIN, 4 CC1, 5 CC2, 6 SDA, 7 SCL, 8 VSET, 9 ISET, 10 GATE, 11 GND),
SY8368A (QFN-12: 1/3 GND, 2 LX, 4-6 IN, 7 BS, 8 VCC, 9 FB, 10 ILMT, 11 PG,
12 EN), INA180 pinout A (1 OUT, 2 GND, 3 IN+, 4 IN-, 5 VS), AP2112K
(SOT-25: 1 VIN, 2 GND, 3 EN, 4 NC, 5 VOUT), USBLC6-2SC6.

**Check in JLCPCB's placement preview before paying:** the WS2812B pin-1
corner, the two B5819W cathode bands and the SMAJ15A's band.
