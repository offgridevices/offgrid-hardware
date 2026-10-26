# LayerCam v1: parts and stock

Read from JLCPCB's assembly catalogue on **26 Oct 2026** (`tools/lcsc.py
--parts`).  Stock moves: read it again before ordering.  Price is JLCPCB's
unit price at about 10 pieces.  "Basic" parts carry no setup fee; every
distinct "extended" part adds about $3 to an order.

## Assembled by JLCPCB

| Role | Part (maker) | Where | LCSC | JLC | Stock | $ each |
|---|---|---|---|---|---|---|
| 0.9 V and Wi-Fi bucks | TLV62569DBVR (Texas Instruments) | main x2 | C141836 | extended | 432,314 | 0.071 |
| 3.3 V / DDR / 1.8 V bucks | EA3036CQBR (Everanalog) | main x1 | C570857 | extended | 22,315 | 0.277 |
| SoC | RV1106G3 (Rockchip) | main x1 | C5328706 | extended | 865 | 25.180 |
| SPI NAND | W25N02KVZEIR (Winbond) | main x1 | C3010298 | extended | 2,702 | 11.550 |
| Wi-Fi module | AP6256 (AMPAK) | main x1 | C5248079 | extended | 3,651 | 7.315 |
| IR-cut driver | DRV8837DSGR (Texas Instruments) | main x1 | C39159 | extended | 84,700 | 0.256 |
| USB ESD | USBLC6-2SC6 (STMicroelectronics) | usb x1 | C7519 | extended | 37,238 | 0.180 |
| IR LED switch | AO3400A (Alpha & Omega) | main x1 | C20917 | basic | 1,218,755 | 0.089 |
| light sensor | TEMT6000X01 (Vishay) | ring x1 | C94098 | extended | 6,579 | 0.941 |
| 5 V TVS | SMF5.0CA (Leiditech) | usb x1 | C169425 | extended | 74,005 | 0.025 |
| 24 MHz crystal | X322524MOB4SI (YXC) | main x1 | C70590 | extended | 56,447 | 0.095 |
| RTC crystal | Q13FC13500004 (Epson) | main x1 | C32346 | basic | 489,771 | 0.171 |
| 37.4 MHz crystal | 3225-37.4-12-10-10/A (Shenzhen Crystal) | main x1 | C2981708 | extended | 1,496 | 0.102 |
| 32 kHz oscillator | ASH7KW-32.768KHZ-L-T (Abracon) | main x1 | C6277865 | extended | 850 | 2.663 |
| 0.9 V and Wi-Fi inductors | FPA252012D-2R2MT0 (Fenghua) | main x2 | C29780705 | extended | 3,532 | 0.140 |
| triple-buck inductors | FPA252012D-1R5MT0 (Fenghua) | main x3 | C29780704 | extended | 617 | 0.141 |
| supply beads | BLM15PD121SN1D (Murata) | main x3 | C76891 | extended | 760,526 | 0.012 |
| Wi-Fi internal buck inductor | FPA252012D-4R7MT0 (Fenghua) | main x1 | C29780707 | extended | 2,732 | 0.140 |
| cable sockets (USB, ring) | BM06B-SRSS-TB(LF)(SN) (JST) | main x2, ring x1 | C160392 | extended | 40,545 | 0.352 |
| antenna | U.FL-R-SMT-1(80) (Hirose) | main x1 | C88374 | extended | 119,089 | 0.119 |
| camera FFC | XF2M-2015-1A (Omron) | main x1 | C57541 | extended | 21,803 | 0.481 |
| IR-cut connector | 53261-0271 (Molex) | main x1 | C177225 | extended | 36,600 | 0.142 |
| USB-C | TYPE-C-31-M-12 (Korean Hroparts) | usb x1 | C165948 | extended | 314,379 | 0.187 |
| cable socket | SM06B-SRSS-TB(LF)(SN) (JST) | usb x1 | C160405 | extended | 21,354 | 0.740 |
| button | TS24CA (XKB) | main x1 | C393942 | extended | 393,600 | 0.025 |
| status LED | KT-0603G (Hubei KENTO) | main x1 | C12624 | extended | 443,518 | 0.012 |
| IR LEDs | JNJ-LTJI0106W90/14mil-D/850NM (JNJ) | ring x6 | C7500094 | extended | 1,050 | 0.059 |

Resistors (UNI-ROYAL 0402, one 1206 per LED string) and capacitors (Samsung
and Fenghua 0402 / 0603 MLCC) are all in stock in the hundreds of
thousands or more; every value and its LCSC number is in `src/parts.py`
and the BOMs.

**Cost of the assembled parts:** main board about $51 (the SoC $25, the
NAND $11.50, the Wi-Fi module $7.30), LED ring $1.70, USB board $1.20.
31 distinct extended parts across the three boards (fees about $3 each,
per board order).

**Thin stock, check first:** RV1106G3 (865), the AP6256's 32 kHz
oscillator ASH7KW (850), the 3.3 V inductor FPA252012D-1R5 (617; three
per board), the 37.4 MHz crystal (1,496) and the IR LEDs (1,050; six per
ring).

**Second sources:**
- the NAND: W25N02KVZEIR on another reel, C17626844 (3,912); or the 1 Gbit
  W25N01GVZEIG, C907680, on the same land (128 MB is enough for the
  firmware, as on the Luckfox Pico Pro).
- the inductors: any 2520 (1008) 1.5 / 2.2 / 4.7 uH part rated 2 A or more.
- the SoC and the Wi-Fi module have none on the same land.

## Bought separately (not on JLCPCB's line)

| Part | What | Where |
|---|---|---|
| Camera module | Luckfox SC3336 3MP Camera (B): SC3336 sensor on a 25 x 24 mm board, M12 lens holder, 20-pin 0.5 mm FFC connector | Luckfox / Waveshare / AliExpress |
| Lens | Towin CCL127028MPR: M12, 2.8 mm, F2.5, IR corrected (sharp at 850 nm too), about 137 deg diagonal | Towin (quote by email; not a catalogue item) |
| IR-cut filter | CLA219 IR-cut holder for M12 lenses, 20 ohm coil on a 2-pin lead | Commonlands. The lead's plug is assumed to be a Molex PicoBlade (1.25 mm, J3): check it on the part in hand; re-crimp if not |
| Camera cable | 20-way 0.5 mm FFC, 0.3 mm thick, about 15 mm long, same-side contacts (opposite-side works too), not twisted | any FFC maker (short lengths are often custom) |
| Wi-Fi antenna | 2.4 / 5 GHz flex antenna on a U.FL pigtail, about 100 mm | any |
| Cables | two 6-way JST SH (1.0 mm) cables, about 60 mm: USB board to main board, ring to main board | JST SH pre-crimped |
| Screws | 4 x M2 self-tapping (board to case), 2 x M1.6 x 8 (holder, module), 2 nylon M1.6 x 1.0 washers | any |
