# LayerCam v1: parts

The boards are made and assembled by **PCBWay**, which buys the parts from
the global distributors. Each BOM (`*/production/layercam-*-bom-pcbway.csv`)
carries the maker, the maker's part number, an LCSC number and, where
the part was chosen from Digi-Key's catalogue, a Digi-Key number.

Stock was checked on **26 Oct 2026**: JLCPCB/LCSC by `tools/lcsc.py
--parts`, Digi-Key by hand. Stock moves, so check it again before
ordering.

## Chosen for the chamber's heat

Every part runs at 75-90 °C in a 65 °C chamber (`sim/thermal.md`), so
parts were picked for their temperature rating, not only their price:

| Was | Now | Why |
|---|---|---|
| X5R capacitors, 1-22 µF (85 °C) | Murata X6S / X7S, same sizes (105 / 125 °C) | the board reaches 84 °C |
| DRV8837 (85 °C ambient) | DRV8210P, pin for pin (125 °C) | |
| Abracon ASH7KW 32 kHz oscillator | Epson TG-3541CE TCXO | the Wi-Fi module's sleep clock must hold ±30 ppm; a tuning-fork oscillator drifts -100 to -150 ppm when hot, a TCXO holds ±3.4 ppm (±8 above 85 °C) |
| YXC 24 MHz, Epson 32 kHz crystals (85 °C) | ECS / Abracon (125 °C), same lands | |
| Fenghua 2520 inductors (no rating published) | Murata DFE252012F (125 °C), same land | |
| HRO USB-C (80 °C) | GCT USB4105 (85 °C), same land | GCT's drawing checked pad by pad against the HRO land |
| XKB side button (70 °C) | none: a BOOT pad beside a ground pad | no plastic part to creep in the heat; setup needs no key (`firmware/README.md`) |
| SMF5.0CA TVS | SMF6.0CA | 6 V stand-off, above USB's 5.5 V maximum, so it does not leak when hot |

**Cannot be upgraded, and they set the ceiling:** the RV1106G3 (125 °C
junction), the AP6256 Wi-Fi module (85 °C, full radio performance to
75 °C) and the SC3336 camera module (85 °C).

**Kept at 85 °C, about 75-80 °C in use with the heat block:** the JST SH
sockets (JST makes no hotter SH; Molex Pico-Clasp is 105 °C but needs new
lands and cables) and the Omron XF2M camera socket (the only 105 °C
parts are single-sided).

## Assembled parts (ICs, crystals, inductors, connectors, LEDs)

| Role | Part | Where | LCSC | Digi-Key | Notes |
|---|---|---|---|---|---|
| 0.9 V and Wi-Fi bucks | Texas Instruments TLV62569DBVR | main x2 | C141836 |  | 2 A synchronous buck, 0.6 V reference, SOT-23-5, Tj to 125 degC |
| triple buck | Everanalog EA3036CQBR | main x1 | C570857 |  | Triple 1 A synchronous buck, 2.7-5.5 V in, WQFN-20 3 x 3 |
| SoC | Rockchip RV1106G3 | main x1 | C5328706 |  | Camera SoC: Cortex-A7 1.2 GHz, 256 MB DDR3L inside, ISP, H.264/H.265, QFN-128 0.35 mm |
| SPI NAND | Winbond W25N02KVZEIR | main x1 | C3010298 |  | SPI NAND flash 2 Gbit (256 MB), 3.3 V, WSON-8 8 x 6 |
| Wi-Fi module | AMPAK AP6256 | main x1 | C5248079 |  | Wi-Fi 5 (2.4 + 5 GHz) + BT 5 module, BCM43456, SDIO; full RF to 75 degC, rated 85 degC |
| IR-cut driver | Texas Instruments DRV8210PDSGR | main x1 | C5218852 | 296-DRV8210PDSGRCT-ND | H-bridge, for the IR-cut filter, WSON-8 2 x 2, -40..125 degC |
| USB ESD | STMicroelectronics USBLC6-2SC6 | usb x1 | C7519 |  | USB ESD protection, SOT-23-6 |
| IR LED switch | Alpha & Omega AO3400A | main x1 | C20917 |  | N-MOSFET 30 V 5.7 A, logic level, SOT-23 (IR LED switch) |
| light sensor | Vishay TEMT6000X01 | ring x1 | C94098 |  | Ambient light phototransistor, eye response (blind to the 850 nm LEDs), -40..100 degC |
| 5 V TVS | Leiditech SMF6.0CA | usb x1 | C353271 |  | TVS 6 V stand-off, bidirectional, 200 W, SOD-123FL |
| 24 MHz crystal | ECS ECS-240-12-33Q-JES-TR | main x1 | C435181 | XC2150CT-ND | Crystal 24 MHz 12 pF, 3225, -40..125 degC |
| RTC crystal | Abracon ABS07AIG-32.768KHZ-1-T | main x1 | C1985607 | 535-ABS07AIG-32.768KHZ-1-TCT-ND | Crystal 32.768 kHz 12.5 pF (the SoC's RTC), 3215, -40..125 degC |
| 37.4 MHz crystal | Shenzhen Crystal 3225-37.4-12-10-10/A | main x1 | C2981708 |  | Crystal 37.4 MHz 12 pF, 10 ppm tolerance and stability, -40..85 degC, 3225 |
| 32 kHz oscillator | Epson TG-3541CE 32.7680KXA0 | main x1 | C1987384 | 114-TG-3541CE32.7680KXA0CT-ND | 32.768 kHz TCXO, CMOS out, 1.5-5.5 V, -40..105 degC, 3.2 x 2.5 mm |
| 0.9 V and Wi-Fi inductors | Murata DFE252012F-2R2M=P2 | main x2 | C576403 | 490-13055-1-ND | Inductor 2.2 uH 2.3 A sat, 2520 |
| triple-buck inductors | Murata DFE252012F-1R5M=P2 | main x3 | C909806 | 490-13054-1-ND | Inductor 1.5 uH 2.7 A sat, 2520 |
| supply beads | Murata BLM15PD121SN1D | main x3 | C76891 |  | Ferrite bead 120 ohm at 100 MHz, 1.3 A, 0402 |
| Wi-Fi internal buck inductor | Murata DFE252012F-4R7M=P2 | main x1 | C668313 | 490-13051-1-ND | Inductor 4.7 uH 1.5 A sat, 2520 (the Wi-Fi module's own buck) |
| cable sockets (USB, ring) | JST BM06B-SRSS-TB(LF)(SN) | main x2, ring x1 | C160392 |  | JST SH 1.0 mm 6 pin, vertical, SMD |
| antenna | Hirose U.FL-R-SMT-1(80) | main x1 | C88374 |  | U.FL coaxial receptacle (Wi-Fi antenna), -40..90 degC |
| camera FFC | Omron XF2M-2015-1A | main x1 | C57541 |  | FFC connector 20 pin 0.5 mm, contacts top AND bottom (either cable type), flip lock |
| IR-cut connector | Molex 53261-0271 | main x1 | C177225 |  | PicoBlade 1.25 mm 2 pin, right angle, SMD, -40..105 degC |
| USB-C | GCT USB4105-GF-A-120 | usb x1 | C5184243 | 2073-USB4105-GF-A-120CT-ND | USB-C receptacle, USB 2.0, 16 contacts, 1.2 mm board, -40..85 degC |
| cable socket | JST SM06B-SRSS-TB(LF)(SN) | usb x1 | C160405 |  | JST SH 1.0 mm 6 pin, right angle, SMD |
| status LED | Hubei KENTO KT-0603G | main x1 | C12624 |  | LED green 0603 (status) |
| IR LEDs | JNJ JNJ-LTJI0106W90/14mil-D/850NM | ring x6 | C7500094 |  | IR LED 850 nm, 100 mA, 90 degrees, 2835, -40..100 degC (pad 1 anode) |

Resistors are UNI-ROYAL 0402 (155 °C), one 1206 per LED string. Capacitors
are C0G / X7R / X6S / X7S, 0402 and 0603. Every value and its part number
is in `src/parts.py` and the BOMs.

**Thin stock, check first:**
- RV1106G3: 865 at LCSC.
- AP6256: 3,651.
- W25N02KV: 2,702.
- The TG-3541CE: Digi-Key 8,360, 16 weeks from the factory.
- The DRV8210P at LCSC: 3; Digi-Key has about 3,000.

**Second sources:**
- The NAND: W25N01GVZEIG on the same land (1 Gbit is enough for the firmware).
- The inductors: any 2520 part rated 2 A and 125 °C.
- The SoC, the Wi-Fi module and the TCXO have none on the same land.

## Bought separately

| Part | What | Where |
|---|---|---|
| Camera module | Luckfox SC3336 3MP Camera (B): SC3336 sensor on a 25 x 24 mm board, 20-pin 0.5 mm FFC connector; its own lens holder is removed | Luckfox / Waveshare |
| Lens | Towin CCL127028MPR: M12, 2.8 mm, F2.5, IR corrected, about 137° diagonal | Towin (quote by email) |
| IR-cut filter | CLA219 IR-cut holder for M12 lenses, 20 Ω coil on a 2-pin lead | Commonlands. The lead's plug is assumed to be a Molex PicoBlade (1.25 mm, J3): check it on the part in hand |
| Camera cable | 20-way 0.5 mm FFC, 0.3 mm thick, about 15 mm, same-side contacts (opposite-side also works), not twisted | short lengths are often custom |
| Heat block | black-anodised 6061 aluminium, `mechanical/heat-plate/` | PCBWay CNC |
| Gap pads | t-Global TG-A6200, 1.5 mm (SoC) and 0.5 mm (lid) | Digi-Key |
| Wi-Fi antenna | 2.4 / 5 GHz flex antenna on a U.FL pigtail, about 100 mm | any |
| Cables | two 6-way JST SH (1.0 mm) cables, about 60 mm | JST SH pre-crimped |
| Screws | 4 x M2 self-tapping (board to case), 2 x M1.6 x 8 (holder and module), 2 nylon M1.6 x 1.0 washers | any |
