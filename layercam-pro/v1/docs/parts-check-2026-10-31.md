# LayerCam Pro v1: parts check, 31 Oct 2026

The plan's main parts, checked for the rule that **every part is in
production today**, and for stock, price and temperature rating. Checked
again, with the full BOM, before ordering.

Sources: Digi-Key's "Product Status" (DK); LCSC/JLCPCB listings (their
lifecycle field reads "normal" for every part, so it only shows the part is
still listed); the makers' own pages. Octopart and Mouser could not be
reached. Prices are for 1 / 100 pieces where both were shown.

## Chosen parts

| Role | Part | In production? | Stock | Price | Rated to | Notes |
|---|---|---|---|---|---|---|
| Main chip | Rockchip RV1106G3 | LCSC lists it (Rockchip publishes no lifecycle) | LCSC 306 | $25.44 | -20..85 °C ambient, 125 °C junction | Thin stock; no second source on the same land |
| Image sensor | SmartSens SC4336H (4 MP, 35-ball CSP) | **Yes:** SmartSens lists it as new, in mass production since Q3 2025 | not stocked by any distributor; SmartSens or its agents | quote | -30..85 °C (family); best image to 60 °C | Replaces the SC3336, which SmartSens lists as legacy. Said to fit the SC3336's pads |
| Wi-Fi | Espressif ESP32-C6-MINI-1U-H4 | **Yes** (Espressif datasheet) | LCSC 0; a Mouser catalogue showed about 3,600 (not confirmed live) | LCSC about $4.43 | **-40..105 °C** | Wi-Fi 6, 2.4 GHz, U.FL socket, US approval (FCC) for the module family. Fallback: ESP32-C6-WROOM-1U-N4 (DK 177, about $3.19 at 2,000; rated 85 °C) |
| IR LEDs (x6) | ams OSRAM SFH 4715CS R33 (860 nm) | **Yes:** DK "Active", the maker's recommended replacement for the SFH 4715AS (not for new designs) | DK 2,790 | $3.29 / $1.87 | -40..125 °C | ams-osram.com still calls it pre-production. Its package is 3.75 mm square, not 3.85 mm: the land pattern is checked against its drawing |
| Light pipes (x6) | Bivar LPV2-0750FP or -0750DP (2.01 mm, 19.1 mm, board mount) | **Yes** (DK "Active") | DK 167 (FP) / 598 (DP), 14 weeks | $2.35 / $1.30 | Bivar gives -40..125 °C for its polycarbonate pipes in general, not for this part | Sits in Bivar's black adapter over the LED: check the adapter fits the LED |
| Sensor 2.8 V supply | TI TLV75528PDRVR | **Yes** (DK) | DK 8,526 | $0.39 / $0.21 | -40..125 °C | Low-noise LDO |
| USB-C | GCT USB4105-GF-A | **Yes** (DK) | DK 84,457 | $0.80 / $0.57 | -40..85 °C | No 16-contact USB 2.0 socket rated 105 °C exists; it goes at the board's cool edge |
| Memory (256 MB) | Winbond W25N02KVZEIR | **Yes** (DK) | DK 7,945 (reel) | about $11.65 (LCSC) | -40..85 °C | Cool edge |
| Bucks, inductors, crystals, ESD, IR-cut driver, light sensor, MOSFET, beads | as on LayerCam v1 (`../../layercam/v1/docs/parts.md`) | **Yes** (DK) for every part Digi-Key carries | | | 105-125 °C for most | |

## Parts LayerCam v1 needed that the Pro drops

The ESP32-C6 module carries its own crystal and sleep clock, and the
Pro has no cables, so these go: the AP6256 Wi-Fi module, its 37.4 MHz
crystal, the 32 kHz TCXO, the camera flat-cable socket and the two JST SH
cable sockets.

## Problems found in LayerCam v1's records

Noted for LayerCam v1's next revision; they are not used here.

- LCSC C353271 (the SMF6.0CA TVS) is made by Jingdao, not Leiditech.
- LCSC C1987384 is the TG-3541CE in ordering code KXA3, not KXA0.
- LCSC C2981708 (the 37.4 MHz crystal) is made by "LIMING", not Shenzhen Crystal.
- Murata GRM155C80J475MEAAD (4.7 µF X6S 0402) is in production but out of
  stock everywhere until 2027; Digi-Key's substitute is Taiyo Yuden
  JMK105BC6475MV-F (X6S, in stock).

## Not confirmed yet

- Live stock of the ESP32-C6-MINI-1U-H4 at a distributor PCBWay buys from.
- The ESP32-C6 module's FCC antenna list (sets which antenna is allowed).
- Whether PCBWay can source the SC4336H; SmartSens' package drawing and
  reflow limits (under NDA).
- Temperature ratings of the light pipes, the IR-cut holder and the lens.
- A maker lifecycle for the Chinese parts (RV1106G3 and the passives):
  only LCSC's listing was found.
