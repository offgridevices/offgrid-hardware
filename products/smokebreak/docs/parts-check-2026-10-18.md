# Parts availability check, 18 Oct 2026

Every BOM line with an LCSC number looked up in JLCPCB/LCSC's catalogue
(`tools/jlc.py`) on 18 Oct 2026. Stock goes stale: check again before
ordering. Lines without an LCSC number are generic Yageo resistors and
Samsung capacitors that PCBWay buys by manufacturer part number.

## Found and fixed in this check

- **D3 (SS2H10-E3/52T) is an SMB (DO-214AA) part**, as Vishay's
  datasheet and Digi-Key give it. The board had an SMA footprint. It now
  has the SMB footprint, re-routed locally, DRC 0 / 0 / 0 (19 Oct 2026).
- **D3 and U10 had no LCSC numbers.** They are now C435843 (SS2H10-E3/52T,
  3029 in stock) and C7484 (SN74AHCT1G125DBVR, 50 793 in stock).
- **The display (X1, ER-TFT2.25-1)** is bought from BuyDisplay: CNY 16.12
  each at 100. Its product page names an NV3023B controller, while the
  firmware assumes an ST7789P3; confirm before ordering (README *Next steps*).

## Needs action before ordering

| Designator | Part | LCSC | Stock | What to do |
|---|---|---|---|---|
| F1 | 2822HC40-RTR | C5493215 | 0 | Source by MPN (Digi-Key, Mouser); or consign. The BOM line says so. Stocked fallback: Littelfuse 0456040.DRSDE (needs a 12.2 mm footprint, a board change). |
| R_PRE,R_PRE2 | D2TO020C3R900FRE3 | C4267031 | 0 | Source by MPN (Mouser, Digi-Key); or consign. The BOM line says so. |
| D1 | SMBJ64CA | C151269 | 3 | SMBJ64CA is a standard part number, made by several makers in the same SMB package (Littelfuse, Bourns, Vishay among them); PCBWay can buy any of them by MPN. Check the quote. |

## Everything else checked

| Designator | Part | LCSC | Type | Stock |
|---|---|---|---|---|
| BZ1 | MLT-8530 | C94599 | SMD | 44,131 |
| D18 | BZT52C15-7-F | C177014 | SMD | 29,746 |
| D2 | BZT52C10-7-F | C155227 | SMD | 153,467 |
| D20 | BZT52C12-7-F | C727004 | SMD | 3,517 |
| D4,D14,D16 | BAT46WJ,115 | C114696 | SMD | 107,310 |
| D5 | BAT54S,215 | C47546 | SMD | 333,938 |
| D6,D7,D8,D9,D10,D11,D15,D17,D19 | 1N4148WS | C2128 | SMD | 2,697,460 |
| J1 | XT60PW-M | C98732 | THT | 11,036 |
| J10 | B5B-XH-A(LF)(SN) | C157991 | THT | 49,369 |
| J11 | B4B-XH-A(LF)(SN) | C144395 | THT | 478,276 |
| J12 | B3B-XH-A(LF)(SN) | C144394 | THT | 151,387 |
| J2 | XT30PW-M30.G.Y | C431092 | THT | 62,608 |
| J3 | XT60H-F.G.Y | C30170202 | THT | 12,153 |
| J4 | XT30U-F | C99102 | THT | 42,521 |
| J5 | B7B-XH-A(LF)(SN) | C144398 | THT | 30,366 |
| J7 | FH12-8S-0.5SH(55) | C597995 | SMD | 8,979 |
| J8 | TYPE-C-31-M-12 | C165948 | SMD | 357,288 |
| J9 | B6B-XH-A(LF)(SN) | C144397 | THT | 26,631 |
| L1 | SWPA6045S470MT | C36414 | SMD | 13,181 |
| LED1,LED2,LED3,LED4,LED5,LED6,LED7,LED8,LED9,LED10,LED11,LED12 | WS2812B-2020-V6 | C52917434 | SMD | 933,537 |
| Q1,Q2 | BSC040N10NS5 | C534334 | SMD | 35,933 |
| Q11 | BSC070N10LS5ATMA1 | C3278731 | SMD | 2,435 |
| Q3 | SUD50P10-43L-E3 | C913430 | SMD | 1,406 |
| Q4 | MMBTA42LT1G | C94389 | SMD | 164,582 |
| Q5,Q10 | BC817-40,215 | C52801 | SMD | 180,388 |
| Q6,Q7 | MMBT5401LT1G | C21488 | SMD | 35,033 |
| Q8,Q12 | 2N7002,215 | C65189 | SMD | 500,328 |
| Q9 | AO3401A | C15127 | SMD | 695,594 |
| RS1 | WSK12161L000FEA | C844476 | SMD | 4,029 |
| RT1,RT2 | NCP15XH103F03RC | C77131 | SMD | 305,696 |
| SW2,SW3 | B3U-1000P | C231329 | SMD | 116,142 |
| U1 | TPS48000QDGXRQ1 | C43131315 | SMD | 409 |
| U11 | USBLC6-2SC6 | C7519 | SMD | 33,474 |
| U2 | INA181A2IDBVR | C2058784 | SMD | 56,019 |
| U3 | LM5164DDAR | C477928 | SMD | 10,877 |
| U4 | TLV75533PDBVR | C404027 | SMD | 116,968 |
| U5 | STM32G0B1RBT6 | C5143679 | SMD | 1,687 |
| U6 | DRV5032FADBZR | C140921 | SMD | 24,051 |
| U7 | 74LVC1G11GW,125 | C282348 | SMD | 28,822 |
| U8,U12 | LMV331IDBVR | C34731 | SMD | 146,483 |
| U9 | SN74LVC1G74DCUR | C70285 | SMD | 7,157 |
