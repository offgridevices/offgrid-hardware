# Mesh Radio v1: decisions and the research behind them

What was decided, why, and what it costs. The owner made the product decisions
on 17 Oct 2026. Part choices are filled in as the design settles them.
Prices and stock are dated and go stale: re-check before ordering.

## Product decisions (owner, 17 Oct 2026)

| Decision | Why | Cost |
|---|---|---|
| **Top transmit power about 3 W (35 dBm); 1 W whenever the region is US** | About 1.5–2× the open-air range of 1 W for licensed or experimental use. Normal use stays legal. | About 2 A bursts from the cell, a bigger amplifier and filter, more heat |
| **Test boards from JLCPCB/PCBWay; files that a US or allied assembler can build unchanged** | Cheap, fast prototypes. A defence build changes only the factory. | The test boards themselves are not NDAA compliant. Every part needs both a DigiKey and an LCSC number. |
| **Drone link: locking serial cable** (JST-GH, Pixhawk TELEM pinout) | Same method the Phase 2B field loggers already use (Meshtastic serial module, PROTO mode, 38400 baud). It adds no 2.4 GHz traffic, and Notion records that the Jetson's Wi-Fi already disturbs the ELRS control link. | One cable per carried node |
| **No GPS on the board; a plug for an add-on** | The drone knows where it dropped the node, and saves 20–30 mA, space and cost | A node without the add-on cannot find its own position |
| **Battery plug wired the standard way (Adafruit/SparkFun), not RAK's** | Matches most cells sold | Existing RAK cells need their plug re-pinned (reverse protection stops damage if one is plugged in) |
| **As compact as possible; narrow and long is fine** | Node boxes and weight | — |
| **Working name until the owner picks one** | — | — |

## What "NDAA compliant" means for this board

Researched 17 Oct 2026. This is not legal advice; a contracting officer has
the final say.

| Rule | What it restricts |
|---|---|
| FY2019 NDAA §889 | Equipment from Huawei, ZTE, Hytera, Hikvision and Dahua (named companies) |
| FY2020 NDAA §848 (amended by FY2023 §817) | DoD drones whose **flight controllers, radios, data transmission devices**, cameras, gimbals, ground control or software were made in a covered foreign country (China; secondary sources add Russia, Iran and North Korea) or by a company based there. This board is a "radio" and a "data transmission device". |
| FY2024 NDAA (American Security Drone Act) | From 22 Dec 2025, no federal purchase of a drone "manufactured or assembled by" a listed company. Communication links count as part of the drone. |
| FCC Covered List, 22 Dec 2025 | No new FCC approval for drone "critical components" (including data transmission and communications parts) **produced in a foreign country**, if they are designed mainly for drones. Blue UAS-listed and Buy-American items are exempt until 1 Jan 2027. |
| Blue UAS / Drone Dominance sourcing schedule | Assembly outside covered countries for flight-critical boards from Aug 2026, with fabrication there preferred. Comms security hardware from Feb 2027. Full traceability by Aug 2027. |

Conclusions for the design:

- **Where the board is assembled counts, not only where its chips come
  from.** A board assembled at JLCPCB in China fails §848 and Drone
  Dominance, even if every chip is American. US or allied assembly clears
  both. US assembly also avoids the FCC "produced in a foreign country" bar
  for a board sold mainly for drones.
- **No law bans a passive part or chip for its country of origin**, except
  the §889 companies and, from Dec 2027, chips from SMIC, YMTC and CXMT.
  Drone Dominance traceability may reach further, so the BOM records country
  of origin from the start.
- **RAKwireless (Shenzhen) and Heltec (Chengdu) are Chinese companies**, so
  neither today's nodes nor a Heltec-based design can be called compliant.
  Notion records the same: never claim "NDAA-compliant" or "US-made" for the
  current RAK nodes.

Sources:
[§848](https://www.wifcon.com/dodauth20/dod20_848.htm),
[FAR 52.240-1](https://www.acquisition.gov/far/52.240-1),
[Pillsbury on the FCC Covered List](https://www.pillsburylaw.com/en/news-and-insights/fcc-categorical-prohibition-foreign-produced-uas-critical-components.html),
[Holland & Knight, Jan 2026](https://www.hklaw.com/en/insights/publications/2026/01/fcc-exempts-certain-drones-from-covered-list),
[DIU Blue UAS](https://www.diu.mil/blue-uas/framework),
[Drone Dominance schedule](https://insideunmannedsystems.com/inside-the-drone-dominance-supply-chain-what-every-u-s-drone-company-must-source-and-by-when/).
Not yet verified: the enacted text of FY2023 §817.

## How much transmit power is allowed

| Rules | Limit at 902–928 MHz |
|---|---|
| FCC Part 15.247, no licence | 1 W into the antenna, with antenna gain up to 6 dBi (about 4 W radiated). Above 6 dBi, power drops dB for dB. Digital modulation needs at least 500 kHz bandwidth. |
| FCC Part 97, amateur licence | 1.5 kW in general, but **spread-spectrum emissions are capped at 10 W**. Whether LoRa counts as spread spectrum here is unsettled. Encryption is not allowed, and there are exclusion zones in parts of TX/NM and CO/WY. |
| FCC Part 5, experimental licence | The power the licence grants. It is for testing, not for selling a device. |
| Government contract | Frequencies and power assigned by the agency (NTIA) |

Notes:

- **Meshtastic's LongFast uses 250 kHz**, which may not meet the 500 kHz
  rule. Alpha firmware is moving US defaults to 500 kHz
  ([Hackaday, Sep 2026](https://hackaday.com/2026/09/17/fcc-ism-rules-may-shatter-lora-mesh-communities/)).
  Watch this; it is firmware, not hardware.
- **What the firmware does today** (meshtastic/firmware, `RadioInterface::limitPower`):
  - The US region caps output at 30 dBm.
  - The board's amplifier gain (`TX_GAIN_LORA`, a single value or a
    22-point table) is subtracted before the SX1262 is set.
  - In licensed mode both the cap and the subtraction are skipped. So this
    board needs only an accurate gain table to sit at 1 W in US mode and
    reach 3 W in licensed mode.
- **Practical ceiling:** commercial LoRa nodes top out around 35–37 dBm (the
  B&Q Station G2/G3). From one LiPo cell, about 35 dBm is realistic.
- **Range, from Cairn's own field data:** height matters more than power.
  At Denton (10 Oct 2026) nodes on the ground failed (0 of 46 packets), while
  a node 2 m up reached 5.5 km at 0.16 W. Lifting one end 2 m gave about
  12 dB; going from 0.16 W to 1 W gives about 8 dB, and to 3 W about 13 dB.

## Starting part shortlist (DigiKey, 17 Oct 2026; to be verified in design)

| Job | Candidate | Maker (home) | Notes |
|---|---|---|---|
| Processor + Bluetooth | nRF52840 | Nordic (Norway) | The same chip as the RAK4631, so Meshtastic and MeshCore support carries over. Bare chip or a Taiwanese pre-certified module: decided in design. The nRF54L15 is cheaper, but Meshtastic support is still experimental. |
| LoRa radio | SX1262IMLTRT | Semtech (US); final test in Taiwan | 19,487 in stock, $9.04 each |
| Amplifier, 1 W class | SE2435L, SKY66122-11 | Skyworks (US) | +30 dBm, receive amplifier with bypass. Not enough for 3 W. |
| Amplifier, 3 W class | QPA9510 | Qorvo (US) | 35.4 dBm at 3.6 V, about 1.7 A. Needs a separate T/R switch, receive amplifier and harmonic filter. DigiKey listing not yet found. Skyworks and Qorvo merged in Oct 2026: watch lifecycle. |
| 32 MHz TCXO | ECS-TXO-20CSMV4-320, NDK NSC5332B | ECS (US), NDK (Japan) | |
| Charger | BQ25185 | TI (US) | |
| 3.3 V supply | TPS62840 / TPS62841 | TI (US) | 60 nA quiescent. The TPS62840 is out of stock until 24 Nov 2026. |
| Input protection | TPS259470 eFuse | TI (US) | |
| Cell protection | BQ29700 | TI (US) | |
| Connectors | U.FL (Hirose, Japan), JST-PH / GH / SH (JST, Japan), USB-C (Amphenol, GCT) | | |
| Bluetooth antenna | 2450AT18A100 | Johanson (US) | |

Excluded: ESP32 (Espressif, China) and the amplifiers on Heltec boards
(GC1109, KCT8103L, believed Chinese). Passives come from Murata, TDK,
Panasonic, KEMET, Vishay and Yageo. Many of these makers run plants in
China, so country of origin is recorded per part.
