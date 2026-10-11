# Beat the Ruko on proof, not price

**Bottom line: a conditional go, as a side product line, not as a Ruko clone.** OffGrid can build a broadcast Remote ID module that beats the Ruko R111S on every spec line: about 8–10 g against 13.5 g, 8–12 h of battery against about 3 h, power from the drone or its own cell, and a status light that tells you without an app whether you are legal to fly. The bill of materials for that build is about **$20–27 at 1k units (est.)**. That rules out fighting Ruko at $33–40 on Amazon, where a $35 sale nets about $26 after fees. The product makes sense at about **$49 sold direct and through FPV retailers (est.)**, priced against the $89–99 bare-board "pro" tier rather than the $40 commodity tier. Pre-launch costs (NRE) are low, about **$15–40k (est.)**. The FAA side is a self-declared Declaration of Compliance (DoC), not a certification. The gate that decides go or no-go is the FCC: since Dec 22, 2025, foreign-produced "UAS critical components" cannot get new FCC authorizations, an FCC ID is mandatory on the FAA DoC, and nobody has ruled on whether a standalone RID module counts. The US market is small (an estimated 20,000–60,000 add-on units a year) and shrinking slowly. Its dated upside is the UK, where legacy and home-built drones must carry Remote ID from Jan 1, 2028. Spend the first money on an FCC counsel opinion and a bench power measurement. Commit to tooling and a DoC only if both come back clean.

*How to read figures: a number followed by a linked source is sourced. A number tagged **(est.)** is an estimate, either from the research team's notes or derived here, and needs a quote or a bench measurement before anyone relies on it.*

## What it takes, on one screen

| Item | What OffGrid has to do | Cost | Time | Basis |
|---|---|---|---|---|
| Hardware | nRF52840 module + u-blox MAX-M10S GNSS, 150–250 mAh LiPo, power path for 1S–6S drone input, buzzer, status lights, USB-C, 0.6–0.8 mm 4-layer PCB | BOM $20–27 @1k, $15–20 @10k | 2–3 months to a DVT board | est. |
| Firmware | Zephyr/nRF Connect SDK built on the Apache-2.0 opendroneid-core-c encoder, sending BT4 Legacy and BT5 Long Range at the same time; signed builds, serial number in one-time-programmable memory | Engineering time | 2–3 months, in parallel with the board | est. |
| FAA | Buy ASTM F3586-22, run its tests in-house, get an ICAO manufacturer code, file the DoC at uasdoc.faa.gov | ~$180 for the standards; $5–20k for the test rig and engineering | 1–4+ months of FAA review | Partly sourced |
| FCC | Pre-certified radio module plus a Part 15B report/SDoC, **after** counsel confirms the Covered List does not block it | ~$0.7k–10k | ~2–6 weeks | Sourced ranges |
| Covered List | Written opinion on whether the module is a "UAS critical component", and on the assembly location | Not researched | 2–4 weeks | — |
| Enclosure | 3D-printed for the first batch, then a simple aluminium mould | $0 now; $1.5–8k later | — | Partly sourced |
| Battery shipping | Buy a cell that already has a UN38.3 test summary | ~$0 extra | — | est. |
| **Total NRE** | | **~$15–40k** | **~6–9 months to first sale** | est. |
| Price / landed cost | $49 direct; landed cost cap ≤ $22 @1k | ~$22 contribution per direct sale | | est. |

| Approval | Needed? | Route |
|---|---|---|
| FAA (14 CFR Part 89) | **Yes.** Every broadcast module must be listed on an accepted DoC ([14 CFR 89.530](https://www.law.cornell.edu/cfr/text/14/89.530)) | Self-declaration citing MoC RID-ASTM-F3586-22-NOA-23-01. No accredited lab required, but recurring independent audits are |
| FCC (Part 15) | **Yes.** The DoC must list an FCC ID | Pre-certified module path, gated by the Covered List question |
| UK | Optional, but the biggest dated wave (Jan 1, 2028) | Manufacturer declaration; firmware must accept an operator ID |
| EU | Optional | CE Module A self-declaration + RED + EN 18031 cybersecurity + EN 4709-002 |
| Japan | Skip | Separate MIC radio approval ("giteki") |
| Canada | Later | Proposed rule only, based on ASTM F3411 |

## The R111S leads a $40 commodity tier, and there is a gap above it

The add-on market has split in two. The bottom tier is about $40 self-contained tags made by drone brands that sell RID as an accessory: Ruko R111S, Holy Stone HSRID02/03, Holyton and Potensic RID-916. They weigh 13.5–20 g and run 3–5 h. Above them sits a $89–330 tier of European and US specialists (Dronetag, BlueMark, Aerobits, uAvionix, Zing). The R111S launched at **$59.99**, now sells at **$39.99**, and has been seen at about $33 with a coupon ([ruko.net](https://www.ruko.net/products/ruko-r111-remote-id-module); [Ruko launch blog](https://www.ruko.net/blogs/ruko/introducing-ruko-r111-remote-id-module-enhancing-drone-safety-and-compliance)). Its DoC is **RID000001939, dated Aug 19, 2024, covering one million serials** ([FAA DoC API](https://uasdoc.faa.gov/api/v1/serialNumbers?findBy=docTrackingNumber&docTrackingNumber=RID000001939&formatForDocView=true&limit=3)). An April 2026 roundup counted 851 reviews for the R111S against 136 for the Potensic, which is consistent with the brief's "500+ bought per month" badge. That badge was not verified directly ([Ohio Drone](https://www.ohiodronellc.com/?p=1949)). Nobody has published what is inside the R111S. Its roughly 3 h at 13.5 g suggests an ESP32-class radio and a budget GNSS, but that is unconfirmed.

| Product | Weight | Battery | Own GPS? | Price | Note |
|---|---|---|---|---|---|
| Ruko R111S | 13.5 g | ~3 h (2.5 h with beeper) | Yes | $33–40 | Buzzer; Android app complaints ([Ohio Drone](https://www.ohiodronellc.com/?p=1949)) |
| Holy Stone HSRID03 | n/a | n/a | Yes | $39.99 | BT + Wi-Fi ([Holy Stone](https://store.holystone.com/products/hsrid03)) |
| Potensic RID-916 | <20 g | Up to 4 h | Yes | ~$40 | GPS lock up to 15 min reported ([Potensic](https://potensic.com/rid-916.html)) |
| Dronetag BS Gen 2 | 5 g | Small cell | Yes | $99 | Closest to the gap ([DroneDJ](https://dronedj.com/2024/03/07/dronetag-remote-id-module-price/)) |
| Dronetag Beacon | 16 g | 8–18 h | Yes | $149 | nRF-based ([Dronetag](https://www.dronetag.com/products/beacon)) |
| Phoenix UAS mRID | 2.2 g | None | **No**, needs an M10 GPS | $69.99–79.99 | Drone-powered ([Rotor Riot](https://rotorriot.com/products/mrid-remote-id-module-rotor-riot-edition)) |
| BlueMark db300 | 2.5 g | None | No | €69 ex VAT | On Blue UAS since Jul 2026; moved to nRF52840 ([BlueMark](https://bluemark.io/2026/10/db300-blue-uas-approved/)) |

The research found **no module that is under 5 g, carries its own battery and GPS, and costs under $50**. Dronetag's 5 g BS Gen 2 comes closest at twice the commodity price. The price floor is real: no FAA-compliant standalone module was confirmed below $30 ([Pilot Institute](https://pilotinstitute.com/remote-id-drone-modules/)). Specialist prices have fallen 40–60% since 2023, with BlueMark's db201 going from €99 to €40 ([DroneScout](https://dronescout.co/product/dronebeacon-mavlink-db201-transponder/?v=0b3b97fa6688)). Quality is also an open flank. BlueMark, a competitor with a commercial interest, has publicly alleged that the Holy Stone HSRID01 outputs about -0.3 dBm against a +3 dBm minimum and lets its take-off position drift more than 300 m ([BlueMark](https://bluemark.io/2024/06/faa-remoteid-compliance-an-inconvenient-truth/)). A module that publishes its own conformance test report would stand out in this market.

The user complaints are concrete, and each points to a fix. This list plays the same role the smoke-stopper complaint list played for SmokeBreak.

| Real complaint | Source | OffGrid fix |
|---|---|---|
| Only ~3 h of battery; 2.5 h with the beeper on | [Ohio Drone](https://www.ohiodronellc.com/?p=1949) | nRF + M10 architecture: 8–12 h (est.), and unlimited on drone power |
| GPS lock takes up to 15 min (Potensic) | [Ohio Drone](https://www.ohiodronellc.com/?p=1949) | Multi-constellation M10, patch antenna, backup rail for hot starts |
| "Is it actually broadcasting?" confusion; scanner apps only verify | [YuneecPilots](https://yuneecpilots.com/threads/remote-id-apps-opendroneid.22636/); [MyDroneAuthority](https://mydroneauthority.com/how-to-check-that-your-drone-is-actually-broadcasting-remote-id/) | A **LIVE** light that turns on only when GPS fix, take-off point and broadcast all pass the self-test |
| Buggy, platform-specific apps (Android for Ruko, iPhone for Holyton) | [Ohio Drone](https://www.ohiodronellc.com/?p=1949) | No app needed. Setup runs from a USB-C web page |
| Serial number on a paper label that can wear off | [MavicPilots](https://mavicpilots.com/threads/i-just-bought-the-ruko-r111-remote-id-module-here-is-my-first-impression.147468/) | Laser-etched serial plus QR code |
| Fussy about chargers; "the charging cable DOES NOT COME WITH THE UNIT" | [Ohio Drone](https://www.ohiodronellc.com/?p=1949); [CommercialDronePilots](https://commercialdronepilots.com/threads/recommendations-for-which-remote-id-to-buy.4495/) | Correct USB-C CC resistors so any charger works; cable in the box |
| Small builds pushed over 250 g; FPV needs wiring and a separate GPS | [UAVMODEL](https://blog.uavmodel.com/faa-remote-id-compliance-guide-for-fpv-drone-pilots-2026/); [Rotor Riot](https://rotorriot.com/products/mrid-remote-id-module-rotor-riot-edition) | 8–10 g (est.); optional UART that feeds GPS to Betaflight, so the module also serves as the quad's GPS |

## A 9 g, 8-hour, dual-power module beats the R111S on every spec line

### The concept, shaped to how OffGrid designs

The recommended product is one module for every airframe. It runs on its own cell, or on drone power from 1S to 6S, and hands over between them without rebooting. Its signature feature is an honest **LIVE** status. A single light turns green only when the module has a GPS fix inside the accuracy limits, has locked the take-off point, and has passed its broadcast self-test. **Nothing else on the device is ever green**, so the "red meant good to go" mistake cannot happen. Three small labelled icons (GPS, Broadcast, Battery) explain why when LIVE is off, and distinct tones mark each state. This turns a legal duty into the main UX feature. Part 89 already requires a module to self-test before take-off, monitor itself continuously and "notify the person manipulating the flight controls" ([14 CFR 89.320](https://www.law.cornell.edu/cfr/text/14/89.320)). The pilot is also required to check that it works before take-off ([14 CFR 89.115](https://www.law.cornell.edu/cfr/text/14/89.115)). Competitors hand that check to a phone app. OffGrid puts it on the case in words.

| OffGrid principle | How the concept meets it |
|---|---|
| Universal fit | Internal cell **or** 1S–6S input with protection rated to ~30 V (est.); velcro, zip-tie slots and a GoPro adapter; UART for Betaflight MSP GPS passthrough (Betaflight 4.4.3+, per [Flite Test](https://www.flitetest.com/articles/connecting-ez-id-to-betaflight-for-gps-passthrough)) and MAVLink OpenDroneID |
| Unique, from real complaints | Honest LIVE status, 8–12 h (est.), hot-start GPS, crash finder that combines the buzzer with a last-known position readable over BLE |
| Noob-proof, no app | Zero buttons in normal use: it wakes on drone power or a long press. Printed flow "1 Charge → 2 Mount, arrow to sky → 3 Wait for LIVE". Serial and setup shown on a USB-C web page |
| Premium within budget | Designed shell, laser-etched serial, one OffGrid mark (never a light, never animated), a satisfying click on the single button; landed cost capped at ≤ $22 (est.) |
| Safety in hardware | Power path, battery protection IC, reverse-polarity and overvoltage protection, external watchdog that can sound the buzzer even if firmware hangs (see failure table) |
| Small-team manufacturing | One-sided SMD, PCBWay-ready BOM with manufacturer part numbers, 3D-printed first batch, end-of-line test jig |
| Open hardware | CERN-OHL-S board; firmware source published; only OffGrid-provisioned units carry DoC-listed serials and signed builds |

| Spec | Ruko R111S (sourced) | OffGrid target (est.) |
|---|---|---|
| Weight | 13.5 g | 8–10 g |
| Battery | ~3 h; 2.5 h with beeper ([micro-tools](https://www.micro-tools.com/products/ruko-r111s-rc-aircraft-gps-tracker-finder-with-beeper-light-weight-rid-module-with-buzzer-for-faa-regulation-spare-part-for-fpv-drone-faa-compliant-remote-id-module-for-drone-3-hours-battery-time)) | 8–12 h on the cell; unlimited on drone power |
| Status | Phone app ([ManualsLib](https://www.manualslib.com/manual/3562819/Ruko-R111.html)) | LIVE light + labelled icons + tones, no app |
| Finder | Buzzer | Buzzer + last-known position over BLE; auto-chirp after a crash |
| FC integration | None | Optional GPS passthrough / MAVLink |
| Compliance evidence | DoC on file | DoC + published F3586 test report |
| Price | $33–40 | $49 direct |

### Radio and GNSS: battery life is the lever, and it costs about $10

The choice of radio and GNSS sets battery life, cost and FCC exposure all at once. In the US a module must send **Bluetooth 4 Legacy and Bluetooth 5 Long Range at the same time**, or else Wi-Fi Beacon; Wi-Fi NAN is not an FAA-allowed method ([opendroneid-core-c](https://github.com/opendroneid/opendroneid-core-c)). Both the ESP32-C3 and the nRF52840 can do the Bluetooth pair. BlueMark shipped FAA-accepted ESP32-C3 + ATGM336H modules (the low-cost reference). Dronetag and BlueMark's new db300 use nRF52840-class radios for longer battery life ([AMA report](https://www.modelaircraft.org/system/files/documents/AMA_RID_Module_Status_Report.pdf); [BlueMark db300](https://bluemark.io/2026/10/db300-blue-uas-approved/)). On GNSS, the u-blox MAX-M10S draws about **25 mW** but costs about **$10.60**. The ATGM336H costs about **$1.82** but draws up to 25 mA ([DigiKey](https://www.digikey.com/en/product-highlight/u/u-blox/max-m10-series); [LCSC](https://www.lcsc.com/product-detail/C4153167.html); [ATGM336H datasheet](https://datasheet.lcsc.com/lcsc/ZHONGKEWEI-ATGM336H-5N31_C90770.pdf)).

| | A: ESP32-C3 + ATGM336H | C: nRF52840 + ATGM336H | **B: nRF52840 + MAX-M10S (recommended)** |
|---|---|---|---|
| Average current | 40–60 mA (est.) | ~25–35 mA (derived est.) | 12–20 mA (est.) |
| Runtime on 150–200 mAh | ~3 h (Ruko parity) | ~5–7 h | 8–12 h |
| BOM @1k / @10k | $9–14 / $6–9 (est.) | ~$11–18 / ~$8–13 (derived est.) | $20–27 / $15–20 (est.) |
| Firmware | Fork ArduRemoteID (GPLv2+), proven in DoC'd BlueMark modules | Zephyr + opendroneid-core-c (Apache-2.0); more work | Same as C |
| Extra radios | Wi-Fi Beacon possible (wider Android/EU phone reach) | BT only | BT only |
| Origin story | Chinese radio and GNSS | European radio, Chinese GNSS | European radio and GNSS; better NDAA/Blue UAS narrative, still "foreign-produced" for the FCC |

**Recommendation: B**, because battery life is the one spec where OffGrid wins by a multiple rather than a margin. The runtime figures are modelled, not measured. No one has published an nRF52840 RID advertising current, so a PPK2 bench run on dev kits is the first engineering task. Variant C is the fallback if the landed cost has to drop below about $18. Both B and C must still send the BT4 Legacy stream, because iPhones cannot receive BT5 Long Range ([Dronetag help](https://help.dronetag.com/dronetag-dri/integration/usa-manufacturer/)).

The hardware checklist is short but has two traps. First, the radio must radiate at least **+3 dBm**, and the antenna must stay within a **4 dB peak-to-average gain** limit. BlueMark argues that "any inverted-F antenna product will likely fail" ([BlueMark](https://bluemark.io/2024/06/faa-remoteid-compliance-an-inconvenient-truth/)), so the board should use a well-tuned chip or monopole antenna and get a pattern pre-scan. Second, the GNSS needs a solid ground plane and about a 15 × 15 mm patch for fast fixes (est.). Position must be accurate to **100 ft** and altitude to **150 ft** at 95% confidence, broadcast at **≥1 Hz with ≤1.0 s latency** ([14 CFR 89.320](https://www.law.cornell.edu/cfr/text/14/89.320)). Any modern GNSS meets these easily.

### Firmware: open source, but production units locked

Use **opendroneid-core-c (Apache-2.0)**, which covers F3411-22a and EN 4709-002 ([GitHub](https://github.com/opendroneid/opendroneid-core-c)), with the nRF BT4/BT5 reference implementation ([sxjack/remote_id_bt5](https://github.com/sxjack/remote_id_bt5)). Publishing the source fits OffGrid's open-hardware stance. Tamper resistance is a hard requirement, though. The FAA accepted F3586-22 only with additions saying the system "shall protect the part 89-required broadcasted message from being altered or disabled by any person" ([87 FR 49520](https://www.govinfo.gov/content/pkg/FR-2022-08-11/html/2022-16997.htm)). The answer is the model ArduRemoteID already uses: signed updates, locked parameters, and a serial number burned into one-time-programmable memory at the end-of-line test ([ArduRemoteID](https://github.com/ArduPilot/ArduRemoteID)). Anyone can build the board from OffGrid's Gerbers. Only OffGrid-provisioned units carry a serial number listed on the DoC. Serial numbers follow ANSI/CTA-2063-A, with a 4-character manufacturer code from ICAO ([14 CFR 89.505](https://www.law.cornell.edu/cfr/text/14/89.505); [ICAO Doc 8643](https://www.icao.int/publications/DOC8643/Pages/Manufacturers-Codes.aspx)). A per-region setting (US / UK / EU) adds the operator-ID field that Europe requires.

### Failure modes, handled in hardware and explained

| Event | What the module does | What the pilot sees and hears |
|---|---|---|
| No GPS fix at power-up | Will not lock the take-off point until accuracy is within limits | GPS icon pulses; LIVE stays off; no ready chime |
| GPS lost in flight | Keeps broadcasting and reports the fault, as §89.320(c) requires | LIVE off, triple beep; the pilot must land ([§89.115](https://www.law.cornell.edu/cfr/text/14/89.115)) |
| Drone battery unplugged or crash | Power path switches to the internal cell without a reboot; keeps broadcasting; finder chirps after N minutes without motion | Finder beeps; last-known position over BLE |
| Internal cell too low for a flight | Refuses LIVE below a reserve threshold (est. ~30 min left); the protection IC prevents over-discharge | Battery icon on, low-battery tone |
| Firmware hang | External watchdog resets the MCU; after repeated resets it drives the buzzer and fault light directly | Fault tone that firmware cannot suppress |
| Reverse polarity or overvoltage on drone input | Input protection survives; module falls back to the cell | Distinct input-fault tone; keeps working |
| Tamper or unsigned update | Bootloader rejects it; serial cannot be changed | n/a |

## The BOM lands at $20–27, so Amazon at $35 does not pay

The line-item BOM for architecture B comes from the hardware notes and is entirely an estimate. Only the GNSS price is a cited LCSC snapshot, and the nRF52840 module price was not verified.

| Line (B, nRF52840 + MAX-M10S) | @1k (est.) | @10k (est.) |
|---|---|---|
| Pre-certified nRF52840 module | $4–7 | $3–5 |
| MAX-M10S GNSS ([LCSC](https://www.lcsc.com/product-detail/C4153167.html), sourced single-qty) | $10.60 | $8–9 |
| GNSS antenna | $0.5–1.2 | $0.4–0.8 |
| Barometer (optional) | $0.8–1.5 | $0.6–1.0 |
| LiPo 150–250 mAh + protection | $1.0–1.8 | $0.7–1.2 |
| Charger, regulator, USB-C, passives | $0.5–0.9 | $0.4–0.6 |
| Buzzer + lights | $0.2–0.4 | $0.15–0.3 |
| 4-layer PCB + SMT assembly | $1.5–3.0 | $0.8–1.5 |
| Enclosure | $0.3–0.6 | $0.15–0.3 |
| Packaging, cable, strap, label | $0.5–1.0 | $0.3–0.6 |
| Programming, provisioning, test | $0.3–0.8 | $0.2–0.4 |
| **Total** | **~$20–27** | **~$15–20** |

At realistic volumes (1–5k units a year, est.), OffGrid buys at 1k pricing. The SmokeBreak rule of retail at about 1.4–1.5× landed cost would put this product near $30–40, Ruko's price. That rule does not survive Amazon's fees, though. Amazon takes a 15% referral fee (8% if the electronics category applies) plus **$3.06–3.87** for FBA fulfillment ([ShipBob](https://shipbob.com/blog/amazon-fba-fees)), and ads typically cost another 10–20% of sales (est.).

| Channel at a given price (all est.) | Net to OffGrid | Minus $22 landed |
|---|---|---|
| Amazon at $35 (Ruko parity) | ~$26.45 | **~$4.45 before ads → loss after ads** |
| Amazon at $49 | ~$38.35 | ~$16 before ads |
| FPV retailer at $49 retail (30–45% retailer margin, unverified norm) | ~$27–34 | ~$5–12 |
| **Direct (web store, YouTube audience) at $49, ~90% kept** | **~$44** | **~$22** |

At $49, OffGrid sits at half the price of the closest functional rival (Dronetag BS Gen 2, $99) and charges $10–15 more than the Ruko for roughly 3× the battery life and 30% less weight. At 1,000–3,000 units a year, mostly sold direct, that is roughly **$15–60k a year of contribution (est.)**. That funds a product line but does not make a company. The NRE is modest, about **$15–40k (est.)**. Most of it is FCC testing, the in-house F3586 test rig, the end-of-line fixture and, later, a mould. Protolabs moulding starts around $1,495 and a simple aluminium tool runs about $3,000 ([Protolabs](https://www.protolabs.com/help-center/pricing-and-payment-options/); [Cad Crowd](https://www.cadcrowd.com/blog/complete-costs-of-injection-molding-design-dfm-engineering-rates-manufacturing-pricing-for-cad-services/)). Leave the tempting LoRa lost-drone beacon for v2. It is not part of RID compliance, and it would need its own Part 15C certification at **$10–20k per round** ([Hubble](https://hubble.com/community/guides/unlicensed-but-not-unregulated-the-certification-path-for-2-4-ghz-ble-products/)).

## FAA approval is a self-declaration; the FCC's 2025 drone rule is the real gate

### FAA: cheap and self-run, but it never ends

OffGrid does not need its own means of compliance (MoC). The only accepted RID MoC is **ASTM F3586-22 with corrections, RID-ASTM-F3586-22-NOA-23-01** ([FAA MoC list](https://uasdoc.faa.gov/api/v1/complianceMeans/public?itemsPerPage=200&pageIndex=0)). Any producer can cite it ([AC 89-2](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_89-2.pdf)). The standard costs **$80** ([ASTM](https://store.astm.org/f3586-22.html)), and F3411-22a must be bought separately (about $100, est.). The DoC is filed online with the producer's details, the make and model, the serial range, **the FCC ID**, the MoC and a set of attestations. Test data stays on file rather than being submitted ([14 CFR 89.530](https://www.law.cornell.edu/cfr/text/14/89.530); [FAA FAQ](https://assets-002.noviams.com/novi-file-uploads/cda/UAS_Remote_Identification_FAQs__3_17_2024_-1669be50.pdf)). Dronetag's integrator guide says testing must be done by accredited labs. The regulation and FAA guidance contradict that ([Dronetag help](https://help.dronetag.com/dronetag-dri/integration/usa-manufacturer/)). The public list now holds **89 broadcast-module DoCs out of 478 accepted RID DoCs** ([FAA public DoC API](https://uasdoc.faa.gov/api/v1/publicDOCRev?itemsPerPage=5000&pageIndex=0)), so the process works for small makers. Review time is not published. Ruko's DoC dates suggest planning for **1–4+ months** (inference).

The real cost is ongoing. Producers must allow FAA inspection, "cause independent audits to be performed on a recurring basis", notify the public of defects **within 15 days**, and supply instructions ([14 CFR 89.520](https://www.law.cornell.edu/cfr/text/14/89.520)). They must keep all test records for the production life **plus 24 months** ([§89.545](https://www.law.cornell.edu/cfr/text/14/89.545)) and fit a permanent English compliance label ([§89.525](https://www.law.cornell.edu/cfr/text/14/89.525)). The FAA can rescind a DoC after a remediation window. The DJI Mavic Pro Platinum rescission in 2023 shows it will do so publicly ([88 FR 44437](https://www.federalregister.gov/documents/2023/07/12/2023-14802/notice-of-rescission-of-unmanned-aircraft-systems-remote-identification-declaration-of-compliance)). For a YouTube-driven brand, a published, independently reviewed F3586 report is both cheap insurance and marketing.

### FCC: an open legal question decides the business

On **Dec 22, 2025** the FCC added foreign-produced UAS and "UAS critical components" to the Covered List. The definition explicitly includes "data transmission devices", "communications systems", "navigation systems" and "batteries". Covered equipment "is prohibited from receiving equipment authorizations" ([FCC DA 25-1086](https://docs.fcc.gov/public/attachments/DA-25-1086A1.pdf)). Products authorized before that date can still be sold ([FCC DA 26-314](https://docs.fcc.gov/public/attachments/DA-26-314A1.txt)). Incumbents such as the R111S, Holy Stone and Potensic modules therefore appear grandfathered (inference; the R111S's own FCC ID was not confirmed), while new foreign entrants are frozen out. The notice "never mentions Remote ID". Zing, a US module maker, is already testing Korean radio modules to work around the uncertainty ([DroneXL](https://dronexl.co/2026/10/06/zing-nucode-korean-radio-remote-id-fcc-foreign-parts/)).

Two exemptions matter: products on the Blue UAS list, and Buy American "domestic end products". A domestic end product must be made in the US with domestic components making up more than 65% of component cost ([Steptoe](https://www.steptoe.com/en/news-publications/global-trade-and-investment-law-blog/fcc-adds-drones-to-the-covered-list.html)). Both exemptions now run **until Jan 1, 2028** ([FCC DA 26-875](https://docs.fcc.gov/public/attachments/DA-26-875A1.pdf)). *The market notes give Jan 1, 2027, based on January 2026 law-firm summaries ([K&L Gates](https://www.klgates.com/FCC-Announces-Wide-Ranging-New-Controls-on-Drones-and-Drone-Components-1-16-2026)). FCC DA 26-875 (Aug 21, 2026) records that the extension to 2028 was made on July 21, 2026, so 2028 is the date to use.*

For OffGrid this leaves an uncomfortable fork. The radio module, the GNSS and the cell are all imported, so clearing 65% domestic component cost on a roughly $20 BOM is implausible (inference). Assembly at PCBWay in China would make the module plainly foreign-produced. US final assembly may or may not change that. The likely workable path is integrating a pre-certified radio whose grant predates the rule and labelling the product "Contains FCC ID", plus a Part 15B report. The cost is low (about **$690** at a Chinese lab, **$6,500–10,000** for US testing of a device with certified modules, per [JJR Lab](https://www.jjrlab.com/news/fcc-sdoc-certification-cost-for-smart-switches.html) and [compliancetesting.com](https://compliancetesting.com/fcc-certification-faqs/fcc-certification-cost/)). But that path is **an untested legal theory**, and the FCC also bars authorization of covered modular transmitters ([PolicyRisk summary](https://policyrisk.com/federal-register/2025-21001)). A DoW Conditional Approval with an onshoring plan is the heavier fallback ([FCC DA 26-875](https://docs.fcc.gov/public/attachments/DA-26-875A1.pdf)). The upside is real: if OffGrid finds a clean path, few new competitors can follow it.

### Other markets

| Market | Rule | Route for OffGrid | Verdict |
|---|---|---|---|
| UK | Remote ID mandatory for class-marked drones since Jan 1, 2026; **legacy and home-built ≥100 g with a camera from Jan 1, 2028** ([UK CAA](https://www.caa.co.uk/drones/moving-on-to-more-advanced-flying/remote-id-rid/)) | Add-on rules under retained Reg. 2019/945 Part 6: operator-ID upload with validation, pilot or take-off position ([CAA library](https://regulatorylibrary.caa.co.uk/2019-945/Content/Regs/PART%206%20-%20Requirements%20for%20a%20direct%20remote%20identification%20add-on.htm)); whether UKCA or CE applies is unresolved | **Second market; ship UK firmware by late 2027** |
| EU | Add-on per EN 4709-002; Module A self-declaration + CE ([EUR-Lex](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX%3A02019R0945-20250624)); RED cybersecurity (EN 18031) mandatory since Aug 1, 2025 ([SGS](https://www.sgs.com/en-se/news/2025/06/red-cybersecurity-requirements-mandatory-on-1-august-2025)) | Same hardware; whether legacy and private builds must carry Remote ID is disputed | Third, after the UK |
| Japan | 100 g+ since 2022 ([MLIT](https://www.mlit.go.jp/en/koku/uas.html)) | Separate MIC radio approval | Skip |
| Canada | NPA 2026-005 proposed Jun 2026, ASTM F3411 basis, "years away" ([DroneXL](https://dronexl.co/2026/06/09/transport-canada-drone-remote-id-npa-2026-005/)) | US design reusable | Later |

## A small US market shrinking slowly, with one dated wave in the UK

Nobody publishes module sales figures, so the size of the market has to be inferred. The FAA counts about **424,000 active Part 107 drones at the end of 2025**. New recreational owners fell from **6,053 a month in 2023 to 4,782 a month in 2025** ([Unmanned Airspace](https://www.unmannedairspace.info/uncategorized/faa-reports-lower-drone-commercial-registrations-but-stronger-forecast-growth/)). Two forces shrink the add-on pool every year. New camera drones ship with Standard RID built in, and **1,835 AMA club fields** are FRIAs where no broadcast is required ([AMA](https://amablog.modelaircraft.org/amagov/2024/01/17/remote-id-compliance-and-resources)). The buyers who remain are FPV, freestyle and home-built pilots flying outside club fields, who will never get built-in RID ([14 CFR 89.501](https://www.law.cornell.edu/cfr/text/14/89.501)). Scaling from Ruko's roughly 6,000 units a year gives total US add-on demand of an estimated **20,000–60,000 units, or $1–4M a year**. The best-known specialist, Dronetag, reported revenue under €1M in 2021 and 2023 ([startups.one.gob.es](https://startups.one.gob.es/companies/dronetag)).

Enforcement is pushing the other way. Discretion ended **Mar 16, 2024** ([88 FR](https://www.govinfo.gov/content/pkg/FR-2023-09-15/html/2023-20074.htm)). EO 14305 gives police real-time access to RID data ([govinfo](https://www.govinfo.gov/content/pkg/DCPD-202500668/html/DCPD-202500668.htm)). A February 2026 FAA bulletin reportedly makes legal action the default for flying without RID ([Autonomy Global](https://www.autonomyglobal.co/hammer-and-nails-the-faas-uas-enforcement-order-just-made-legal-action-the-default/), secondary). Part 108 BVLOS will not help module makers, because it requires Standard RID, not modules ([Federal Register](https://www.federalregister.gov/documents/2025/08/07/2025-14992/normalizing-unmanned-aircraft-systems-beyond-visual-line-of-sight-operations)).

The argument against entering is serious. The market is small and shrinking, Ruko is grandfathered on both FAA and FCC paperwork, and SpeedyBee has already added RID to its Bluetooth flight controllers by firmware, at zero added grams and with no DoC yet ([IntoFPV](https://intofpv.com/t-speedybee-adds-rid-to-their-bt-fc-aio-with-firmware-update)). BlueMark's 2.5 g db300 shows where integrators are heading. The argument for entering is that NRE is low, the skills match OffGrid's, the honest-status feature turns a legal duty into the selling point, and the FCC freeze plus the UK 2028 mandate create a window that a nimble US maker can use.

## Conclusion

The R111S is beatable on specs at almost no technical risk. Battery life, weight, dual power and glanceable status are each solved problems, and only OffGrid would combine them in one module under $50. The difficulty is not engineering. It is that the market's moats are paperwork: grandfathered FCC IDs, DoCs with standing audit duties, and a Covered List whose scope no one has defined. That changes the goal. The competition is less about specs than about being one of the few new modules that can legally get an FCC ID after 2025, and then being the one pilots trust because its LIVE light and its published test report tell them the truth. If counsel finds a clean FCC path, OffGrid gets a low-NRE, on-brand product line with little new competition behind it. If counsel does not, no amount of product polish fixes that, and the right call is to stop before spending on tooling.

## Decisions to make next

1. **Commission an FCC counsel opinion first** on whether an OffGrid RID module is a covered "UAS critical component", and whether integrating a pre-Dec-2025 certified radio module ("Contains FCC ID") is enough. *Recommendation: do it now. Treat it as the go/no-go gate and spend nothing on tooling until it is answered.*
2. **Choose the assembly location** (PCBWay China, or US final assembly) in light of that opinion. *Recommendation: decide after #1. Keep the design PCBWay-ready either way.*
3. **Choose the architecture.** B (nRF52840 + MAX-M10S, 8–12 h, ~$20–27 BOM, all est.), C (nRF + ATGM336H, ~5–7 h, ~$11–18) or A (ESP32-C3, Ruko parity). *Recommendation: B, confirmed by a PPK2 current measurement on dev kits within 2 weeks.*
4. **Set the price, channel and landed-cost cap.** *Recommendation: $49, sold direct first and through FPV retailers second, with no $35 Amazon price war. Cap landed cost at ≤ $22 at 1k (est.).*
5. **Lock the v1 feature set.** *Recommendation: LIVE status with labelled icons and tones, internal cell plus 1S–6S drone power, crash finder, optional Betaflight/MAVLink UART, laser-etched serial, cable in the box. Defer LoRa to v2.*
6. **Commission 10–20 numbered form-factor concepts** with renders, held to an 8–10 g budget (est.) and a single OffGrid mark. *Recommendation: run this in parallel with #1, since it costs little.*
7. **Set the firmware licence and lock policy.** *Recommendation: publish Apache-2.0 firmware built on opendroneid-core-c. Production builds are signed and serials live in OTP. Publish the in-house F3586 test report and pay for one independent review.*
8. **Choose the market sequence.** *Recommendation: US first, with a DoC targeted about 6–9 months out (est.). UK firmware ready by Q4 2027 for the Jan 1, 2028 mandate. EU after the UK. Skip Japan.*
