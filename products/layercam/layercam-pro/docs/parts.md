# LayerCam Pro v1: parts

The board is made and assembled by **PCBWay**, which buys the parts from
the global distributors. The BOM (`production/layercam-pro-bom-pcbway.csv`)
carries the maker, the maker's part number and an LCSC number for each
line. Every value and its part number is in `src/parts.py`.

Checked twice:
- **31 Oct 2026**, the main parts, for production status, stock, price and
  temperature: the dated record is
  [`parts-check-2026-10-31.md`](parts-check-2026-10-31.md) (Digi-Key's
  product status, LCSC, the makers' pages).
- **1 Nov 2026**, every part in `src/parts.py`, for JLCPCB stock
  (`python3 tools/lcsc.py --parts`). JLCPCB's stock is not PCBWay's, but it
  shows what is thin.

Stock moves: check it again before ordering.

## Chosen for the chamber's heat

The board runs at about 80 °C in a 65 °C chamber (`sim/thermal.md`), so
parts were picked for their temperature rating, not only their price.
LayerCam v1's choices for the heat are kept (X6S / X7S capacitors, the
DRV8210P, 125 °C crystals and inductors, the GCT USB-C, the 6 V TVS, no
button). What the Pro changed:

| LayerCam v1 | Pro v1 | Why |
|---|---|---|
| AMPAK AP6256 Wi-Fi (85 °C; full radio to 75 °C) | Espressif ESP32-C6-MINI-1U-H4 (**105 °C**) | the only Wi-Fi part found above 85 °C, under $5, US approved; 2.4 GHz only (`decisions.md`) |
| SC3336 camera module on a flat cable | bare SmartSens SC4336H on the board | the SC3336 is legacy; no flat cable |
| six IR LEDs on a ring board | six Vishay VSMY3850X01 on the main board (**105 °C ambient, 110 °C junction**) | one board |
| 37.4 MHz crystal, 32 kHz TCXO, flat-cable socket, two JST SH sockets (85 °C) | none | the C6 carries its own crystal and sleep clock; no cables |
| Wi-Fi rail at 3.60 V | 3.255 V | 3.6 V is the C6's absolute maximum |

**They set the ceiling (85 °C, no hotter grade):** the image sensor
SC4336H (best picture to 60 °C), the W25N02KV flash, the USB4105 USB-C
(no 16-contact USB 2.0 socket rated 105 °C exists) and the KT-0603G status
LED. In a 65 °C chamber they sit at 80.9-81.9 °C by night, within 1.0 K of
each other. The main chip RV1106G3 is rated 125 °C junction, 85 °C
ambient.

## Assembled parts (ICs, crystals, inductors, connectors, LEDs)

Stock is JLCPCB's on 1 Nov 2026 unless marked DK (Digi-Key, 31 Oct).

| Role | Part | Ref | LCSC | Rated | Stock | Notes |
|---|---|---|---|---|---|---|
| Main chip | Rockchip RV1106G3 | U1 | C5328706 | -20..85 °C ambient, 125 °C junction | **257** (LCSC 306 on 31 Oct) | Linux, ISP, H.264, 256 MB DDR3L inside, QFN-128 0.35 mm. No second source on the land |
| Image sensor | SmartSens **SC4336H** | U8 | (C9900187041 is the **SC4336P**, used for the land only) | -30..85 °C; best image to 60 °C | **none at any distributor** | 4 MP, 35-ball CSP. Sold by SmartSens and its agents: PCBWay sources it or it is consigned. Datasheet, ball map and reflow limits under NDA; the land and balls are the SC4336P's, said to be the same |
| Wi-Fi | Espressif ESP32-C6-MINI-1U-H4 | U6 | C20627095 | -40..105 °C | 3,950 (LCSC 0 on 31 Oct) | Wi-Fi 6, 2.4 GHz, external antenna socket, FCC modular approval. Fallback: ESP32-C6-WROOM-1U-N4 (85 °C, a different land) |
| Flash | Winbond W25N02KVZEIR | U5 | C3010298 | -40..85 °C | 1,737 (DK 7,945) | SPI NAND 2 Gbit (256 MB). Second source: W25N01GVZEIG on the same land |
| Sensor 2.8 V LDO | TI TLV75528PDRVR | U9 | C2865214 | Tj to 125 °C | **120** (DK 8,526) | low-noise, WSON-6 |
| 0.9 V and Wi-Fi bucks | TI TLV62569DBVR | U2, U4 | C141836 | Tj to 125 °C | 302,766 | 2 A, SOT-23-5 |
| Triple buck | Everanalog EA3036CQBR | U3 | C570857 | Tj to 125 °C | 20,996 | 3.3 V, DDR, 1.8 V |
| IR-cut driver | TI DRV8210PDSGR | U7 | C5218852 | -40..125 °C | 2,801 | H-bridge, WSON-8 |
| IR LED switch | Alpha & Omega AO3400A | Q1 | C20917 | Tj to 150 °C | 1,199,585 | N-MOSFET, SOT-23 |
| IR LEDs | Vishay **VSMY3850X01-GS08** | D2-D7 | C6925914 | **-40..105 °C ambient, Tj 110 °C** (datasheet 80225 rev 1.2) | **0** | 850 nm, ±60°, 100 mA, PLCC-2 3.5 x 2.8 x 1.75 mm, AEC-Q101. Check Digi-Key and Mouser before ordering |
| Light sensor | Vishay TEMT6000X01 | Q2 | C94098 | -40..100 °C | 9,465 | eye response, blind to the 850 nm LEDs |
| USB ESD | ST USBLC6-2SC6 | U10 | C7519 | Tj to 125 °C | 45,036 | |
| 5 V TVS | Jingdao SMF6.0CA | D1 | C353271 | Tj to 150 °C | 200,118 | 6 V stand-off, so it does not leak when hot |
| 24 MHz crystal | ECS ECS-240-12-33Q-JES-TR | Y1 | C435181 | -40..125 °C | **110** | Digi-Key XC2150CT-ND |
| RTC crystal | Abracon ABS07AIG-32.768KHZ-1-T | Y2 | C1985607 | -40..125 °C | **127** | Digi-Key 535-ABS07AIG-32.768KHZ-1-TCT-ND |
| Inductors 2.2 µH | Murata DFE252012F-2R2M=P2 | L1, L5 | C576403 | -40..125 °C | 14,313 | 2.3 A sat. Second source: any 2520 part rated 2 A and 125 °C |
| Inductors 1.5 µH | Murata DFE252012F-1R5M=P2 | L2-L4 | C909806 | -40..125 °C | 6,514 | 2.7 A sat |
| Supply beads | Murata BLM15PD121SN1D | | C76891 | -55..125 °C | 631,747 | 0402 |
| USB-C | GCT USB4105-GF-A | J1 | C3020560 | -40..85 °C | 2,775 (DK 84,457) | USB 2.0, 16 contacts, on the board's edge tab |
| IR-cut socket | Molex 53261-0271 | J3 | C177225 | -40..105 °C | 31,183 | PicoBlade 1.25 mm, 2 pin, right angle |
| Status LED | Hubei KENTO KT-0603G | LED1 | C12624 | -40..85 °C | 386,573 | green 0603 |

Resistors are UNI-ROYAL 0402 (155 °C), one 1206 (47 Ω) per LED string.
Capacitors are C0G / X7R / X6S / X7S, 0402 and 0603. Thin among them:
22.6 kΩ (C26960, 1,991), 22 µF X6S 0603 (C393031, 2,473), 10 µF X6S 0603
(C576470, 8,074), 4.7 µF X6S 0402 (Taiyo Yuden JMK105BC6475MV-F, C697614,
9,775; the Murata part LayerCam v1 used is out of stock until 2027).

**Thin stock, check first:**
- The SC4336H: no distributor. Ask PCBWay first.
- The VSMY3850X01: 0 at JLCPCB.
- The RV1106G3: 257.
- The TLV75528, the 24 MHz and 32 kHz crystals: about 110-130 each.
- The ESP32-C6-MINI-1U-H4: 3,950 at JLCPCB, 0 at LCSC on 31 Oct.

**No second source on the same land:** the RV1106G3, the SC4336H, the
ESP32-C6 module.

## The IR LEDs' rating, checked

`src/parts.py` gave the VSMY3850X01 as -40..105 °C, from the distributors.
`sim/thermal.py` used the base part's 100 °C junction, because the X01's
own datasheet had not been read. Vishay's datasheet for the X01
(document 80225, rev 1.2, 24 Jun 2025) gives:
- operating temperature -40 to +105 °C; storage -40 to +110 °C;
- junction temperature **110 °C** (the base VSMY3850: 100 °C junction,
  85 °C ambient, document 83399);
- forward voltage 1.6 V typical, **1.9 V maximum** at 100 mA (the base
  part: 2.0 V), 100 mA continuous, 200 mW, RthJA 250 K/W;
- 1.75 mm tall.

So the thermal model's 100 °C limit for the lit junction is 10 K
conservative: at 65 °C by night it is 87.5 °C, 22.5 K under 110 °C.

## Bought separately

The shopping list, with quantities, is in the README (*How to order*).
Why each:

- **Lens.** Towin CCL127028MPR, LayerCam v1's: the IR-corrected version
  with no IR-cut filter of its own, or night pictures go dark. Its back
  focal length against the CLA219's 3.0 mm and its focus are untested. No
  temperature rating published.
- **IR-cut holder.** Commonlands CLA219: its own M12 thread, 9.5 mm tall,
  M1.6 screws 18.0 mm apart. Its lead ends in a "1.25 mm JST" 2-pin plug;
  J3 is a Molex PicoBlade (1.25 mm). If the plug is a JST GH (it does not
  mate), cut it off and crimp on a Molex 51021-0200 housing with two
  50079-8100 contacts. No temperature rating published: ask Commonlands.
- **Holder screws.** M1.6 x 5 thread-forming: the board is 1.6 mm, so they
  leave 3.4 mm in the holder's 4.3 mm base. An M1.6 x 6 would reach 4.4 mm
  and bottom out.
- **Heatsink.** 20 x 20 x 15 mm: its top ends 0.84 mm under the lid's
  1.6 mm plate, under three vent slots (`enclosure/`). The thermal model
  assumed a 2 mm base and seven straight 1.2 mm fins, black anodised.
  Without it the main chip runs 6 K hotter.
- **Heatsink tape.** 3M 8810, rated 100 °C (UL 746C); it sits at about
  82 °C in a 65 °C chamber. The heatsink comes without tape.
- **Light rods.** Clear polycarbonate (Tg about 145 °C); clear acrylic
  softens near 100 °C. They replace the plan's Bivar light pipes, which
  are straight and board-mounted: four of the six LEDs had to move out to
  R 14.4 to clear the IR-cut holder, so their rods lean up to 4.4° in
  printed channels, each ending 0.3 mm from its LED (1.75 mm tall).
- **Magnets.** SH grade (150 °C): ordinary N grades are rated 80 °C and
  can lose pull for good near a 65 °C chamber. No Amazon listing names an
  SH grade at 10 x 3 mm; K&J Magnetics D62SH (3/8 x 1/8 in, N42SH) fits
  the pocket. Set in J-B Weld Original (287 °C), not super glue, which
  goes soft near 80 °C.
- **Antenna lead.** The ESP32-C6-MINI-1U's socket is MHF III / W.FL
  (Espressif's datasheet v1.5, 10.2: "W.FL series from Hirose, MHF III from
  I-PEX"), not U.FL; the two do not mate. Buy a W.FL (MHF III) lead.
- **Antenna.** 2 dBi: the module's US approval covers antennas of the same
  type with no more gain than it was tested with (2.33 dBi). Read the
  module's FCC grant for its antenna list before selling.
- **Screws.** M2 x 8 for the board and shells, M2 x 6 for the lid,
  self-tapping into the case's 1.7 mm pilots, as Prusa's.
- **Case material.** PCCF, as Prusa prints its case; PETG softens near
  70 °C. It conducts a little: the board's copper stops 0.3 mm from its
  edge, under solder mask, and the case touches it only at the screw pads.
