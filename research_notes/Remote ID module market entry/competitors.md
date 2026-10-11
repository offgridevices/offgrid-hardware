# Competitive Landscape: Broadcast Remote ID (RID) Modules, US (and EU where relevant), as of October 2026

Research date: 2026-10-11. Prices are as found on the cited page on that date unless a date is given. Many review and roundup sites disagree on weights and prices, and several 2026 "guides" are affiliate or SEO content. Conflicts are flagged inline. Live Amazon pages could not be read: automated fetches got a captcha or a truncated, cart-gated page. Amazon signals below come from search snippets and third-party roundups, not direct reads.

## 1. Product list and spec comparison

### Takeaway
The market splits into two tiers. The first is about $40 consumer "self-contained" battery tags (Ruko R111S, Holy Stone HSRID02/03, Potensic RID-916, Holyton), around 13.5–20 g with 3–5 h battery, sold on Amazon. These dominate volume. The second is $89–$330 European and US "pro" products (Dronetag, BlueMark, Aerobits, uAvionix, Zing, Pierce). The only tiny FPV-friendly options are bare boards powered by the drone, at 0.5–5 g (Dronetag BS/DRI, BlueMark db122FPV/db202mav, Phoenix UAS mRID, Aerobits idME). No Chinese FPV electronics brand (BETAFPV, Happymodel, Flywoo, Foxeer, HGLRC, Axisflying) turned up with a confirmed FAA-accepted standalone module. SpeedyBee has reportedly added RID by firmware to its Bluetooth flight controllers.

### Master comparison table

| Brand / model | Type / power | Weight | Size | Battery | Radios / GPS | Extras | Price (MSRP → street) | FAA DoC / EU | Sources |
|---|---|---|---|---|---|---|---|---|---|
| **Ruko R111S** | Self-contained, internal battery, USB-C | 13.5 g (0.48 oz) | 1.3 × 1.1 × 0.5 in | Not quantified by Ruko. Third party: 3 h (2.5 h with beeper on). An eBay R111 listing says "5 hours" | GPS; BT (version not stated by Ruko); claimed locate range 500–1000 m | Buzzer ("S" = beeper); app; "locates aircraft when GPS lost" | Launch $59.99 → $39.99 (ruko.net and Amazon). A 2024 buyer reported ~$33 with coupon. Bundles $49.39 (128 GB SD) to $59.98 (landing pad) | Marketed "FAA compliant"; DoC number not on page | [ruko.net](https://www.ruko.net/products/ruko-r111-remote-id-module); [Ruko launch blog](https://www.ruko.net/blogs/ruko/introducing-ruko-r111-remote-id-module-enhancing-drone-safety-and-compliance); [Amazon bundle](https://www.amazon.com/Ruko-R111S-Remote-Module-Micro/dp/B0HG8ZT58H); [Amazon landing-pad bundle](https://www.amazon.com/Ruko-Compliant-Remote-Module-Landing/dp/B0F62V1QPG); [eBay R111](https://www.ebay.com/itm/306012640770); [Ohio Drone roundup, Apr 2026](https://www.ohiodronellc.com/?p=1949); [PhantomHelp forum](https://forum.phantomhelp.com/t/i-just-bought-the-ruko-r111-faa-compliant-remote-id-module-for-drone-with-the-2-year-assurion-protection-coverage-for-37-44/9805) |
| **Holy Stone HSRID01** (2023) | Self-contained battery | 14 g (Drone Girl, FPVFC). Other sources say 20 g and 22 g | — | ~5 h (Drone Girl) | GPS + BT. BlueMark alleges no proper BT Legacy + BT5 LR format | — | $89 (FPVFC sheet, ~2023) → $40–60 | DoC accepted at launch. BlueMark alleges non-compliance (see §5) | [FPVFC sheet](https://docs.google.com/spreadsheets/d/1LPgSf_qI3JWOzmDOCqM31eQnzRBKPzUu_8RW2VCqAWU/); [Drone Girl](https://www.thedronegirl.com/2023/11/06/best-remote-id-module/); [RotatePilot](https://rotatepilot.com/guides/remote-id-guide); [BlueMark](https://bluemark.io/2024/06/faa-remoteid-compliance-an-inconvenient-truth/) |
| **Holy Stone HSRID02** (newer) | Self-contained battery | Not found | — | 4 h (Amazon title) | GPS | Strobe light, buzzer, "waterproof GPS tracker" | Amazon price is cart-gated | "FAA compliant" (title) | [Amazon B0FP49QWT5](https://amazon.com/dp/B0FP49QWT5) |
| **Holy Stone HSRID03** | Self-contained battery | Not stated | — | "Long battery life" (no figure) | GPS; BT and Wi-Fi (reviewer says iPhone receives BT only) | LED status; overcharge, over-discharge and low-temperature protection | $39.99 (Holy Stone store) | Reviewer says it meets the FAA DoC | [Holy Stone store](https://store.holystone.com/products/hsrid03) |
| **Holyton** (Holy Stone sister brand, HT60 module) | Self-contained battery | 13.5 g | — | 5 h | GPS + BT | Overcharge protection; multi-drone sharing | ~$40 | BlueMark flags an FCC ID oddity | [Ohio Drone](https://www.ohiodronellc.com/?p=1949); [BlueMark](https://bluemark.io/2024/06/faa-remoteid-compliance-an-inconvenient-truth/) |
| **Potensic RID-916** | Self-contained battery | <20 g (Potensic); 19 g (third party) | — | Up to 4 h | GPS (<3 m claimed); BT 5.1, "300 m+" claimed | IP54 | ~$40 (Ohio Drone). One document says ~$30–35 (unverified) | "FAA compliant" (Amazon title) | [Potensic](https://potensic.com/rid-916.html); [Amazon B0CXTHLMKZ](https://www.amazon.com/Potensic-Compliant-Identification-Broadcast-Regulation/dp/B0CXTHLMKZ); [Ohio Drone](https://www.ohiodronellc.com/?p=1949) |
| **Dronetag Mini** | Self-contained; LiPo 3.7 V 500 mAh | 32 g | 54 × 35 × 15 mm | 8–14 h | GPS; broadcast + **network** RID (LTE) | App, flight logging | €299 / $329 (official); resellers as low as $229. One guide says $149 (likely an error) | FAA + EASA | [Dronetag Mini](https://www.dronetag.com/products/mini); [Dronetag shop](https://shop.dronetag.com/products/20-dronetag-mini.html); [RotatePilot](https://rotatepilot.com/guides/remote-id-guide) |
| **Dronetag Beacon (Gen 2 / V2)** | Self-contained, USB-C | 16 g | 37 × 26 × 16 mm | 8–18 h (official); 10–18 h (Adorama) | GPS; BT, "3 km" claimed | App | Official €139 / $149. Drone Nerds V2 $219. Earlier Gen 1 €199 | FAA + EU. Gen 2 shipped from mid-Nov 2023 | [Dronetag Beacon](https://www.dronetag.com/products/beacon); [Dronetag CZ](https://dronetag.cz/products/beacon); [Drone Nerds](https://www.dronenerds.com/products/dronetag-beacon-v2); [FPVFC sheet](https://docs.google.com/spreadsheets/d/1LPgSf_qI3JWOzmDOCqM31eQnzRBKPzUu_8RW2VCqAWU/) |
| **Dronetag BS** (bare board) | Drone-powered, 3.3–17 V (1S–4S) | 1.3 g incl. antennas (Gen 1) | — | None. "BS Combo" adds battery and charger | GNSS + BT; external antennas | — | €89 / $89 | "FAA approved, EU compliant" | [Dronetag BS](https://www.dronetag.com/products/bs); [Drone Nerds](https://www.dronenerds.com/products/dronetag-bs-remote-id-solution-for-fpv) |
| **Dronetag BS Gen 2** (Mar 2024) | Standalone with battery | 5 g | — | Small internal cell | GNSS + BT | — | $99 | FAA | [DroneDJ, Mar 2024](https://dronedj.com/2024/03/07/dronetag-remote-id-module-price/) |
| **Dronetag DRI** | OEM / integrator, drone-powered | 0.5 g | — | None | No GPS (uses the FC's) | — | €49 | Module + standard RID | [FPVFC sheet](https://docs.google.com/spreadsheets/d/1LPgSf_qI3JWOzmDOCqM31eQnzRBKPzUu_8RW2VCqAWU/) |
| **BlueMark DB120 (DroneBeacon)** | Self-contained battery | 25 g | — | — | GPS + BT | — | €129 → $139 (DroneGearHQ) | FAA module | [FPVFC sheet](https://docs.google.com/spreadsheets/d/1LPgSf_qI3JWOzmDOCqM31eQnzRBKPzUu_8RW2VCqAWU/); [Droneblog](https://www.droneblog.com/best-remote-id-modules/); [DroneGearHQ](https://dronegearhq.com/guides/drone-remote-id/) |
| **BlueMark DB121** | Module | 11 g | — | — | GPS built in | — | €109 | FAA module | [FPVFC sheet](https://docs.google.com/spreadsheets/d/1LPgSf_qI3JWOzmDOCqM31eQnzRBKPzUu_8RW2VCqAWU/) |
| **BlueMark db122FPV** | Drone-powered | 4 g | — | — | No GPS (uses the FC's) | — | €69 | Module RID | [FPVFC sheet](https://docs.google.com/spreadsheets/d/1LPgSf_qI3JWOzmDOCqM31eQnzRBKPzUu_8RW2VCqAWU/) |
| **BlueMark db201** (Dec 2022) | OEM, MAVLink + 2× DroneCAN | ~4–5 g (without antenna) | — | — | Uses FC GPS | — | €99 ex VAT at launch → €40 ex VAT ($46.18) now | Standard RID (OEM) | [BlueMark launch](https://bluemark.io/2022/12/remote-id-db201-module-launched/); [DroneScout](https://dronescout.co/product/dronebeacon-mavlink-db201-transponder/?v=0b3b97fa6688) |
| **BlueMark db202mav** (Mar 2023) | OEM, MAVLink | ~2.6 g | — | — | Uses FC GPS | — | €49 → €29 ex VAT ($32.91) | Standard RID | [BlueMark](https://bluemark.io/2023/03/bluemark-introduces-the-cost-effective-db202mav-module-and-announces-two-other-family-members/); [DroneScout](https://dronescout.co/product/dronebeacon-mavlink-db202mav-transponder/?v=5f02f0889301) |
| **BlueMark db203can / db210pro** | OEM | 2.8 g / 6 g | — | — | Uses FC GPS | — | €64 / €99 | Standard RID | [FPVFC sheet](https://docs.google.com/spreadsheets/d/1LPgSf_qI3JWOzmDOCqM31eQnzRBKPzUu_8RW2VCqAWU/) |
| **Zephyr Module 100** | Rebranded db120/db121 | 11 g | — | — | GPS | — | $305 | — | [FPVFC sheet](https://docs.google.com/spreadsheets/d/1LPgSf_qI3JWOzmDOCqM31eQnzRBKPzUu_8RW2VCqAWU/) |
| **Aerobits idME / idME Pro** | OEM, JST to Pixhawk | ~5 g with antenna (idME Pro; inferred) | — | — | BLE + Wi-Fi (Pro); optional GNSS | — | idME Pro €229 (FPVFC) → €99 after May 2024 price cut. US OzRobotics $115 → $110.40 | FCC; FAA MoC (F3411); CE pending (per retailer) | [UST, May 2024](https://www.unmannedsystemstechnology.com/2024/05/aerobits-announces-price-reduction-on-remote-id-modules/); [OzRobotics](https://ozrobotics.com/shop/uas-drones-remote-identification-device-idme-pro-remote-id/); [FPVFC sheet](https://docs.google.com/spreadsheets/d/1LPgSf_qI3JWOzmDOCqM31eQnzRBKPzUu_8RW2VCqAWU/) |
| **CubePilot Cube ID (Serial)** | OEM, built-in (standard) RID | 8 g (UAVMODEL; unverified) | — | — | Uses FC | — | $39 (2023 launch) | Called the "cheapest FCC-certified" standard RID solution | [DroneDJ](https://dronedj.com/guides/cubepilot/) |
| **Holybro Remote ID** | OEM / integrator; the buyer files their own DoC | 14 g (UAVMODEL; unverified) | — | — | — | — | — | Not a turnkey DoC: "you need to do your own approval process at the FAA (DoC submission)" | [Holybro](https://holybro.com/products/remote-id); [NewBeeDrone](https://newbeedrone.com/products/holybro-remote-id) |
| **Phoenix UAS mRID** (incl. Rotor Riot Edition) | Drone-powered | 2.2 g | — | None | BT 5 LE; **needs a user-supplied M10 GPS** | Betaflight passthrough | $69.99 (FPVFC) / $79.99 (MyFPV) | FAA module. BlueMark alleges antenna non-compliance | [Rotor Riot](https://rotorriot.com/products/mrid-remote-id-module-rotor-riot-edition); [MyFPV](https://www.myfpvstore.com/fpv-electronics/remote-id/); [BlueMark](https://bluemark.io/2024/06/faa-remoteid-compliance-an-inconvenient-truth/) |
| **Flite Test / Tritium FT EZ ID** | Drone-powered, with plug | 10 g | — | None | GPS + BT built in | Betaflight + ArduPilot | $99.99 | FAA module. BlueMark flagged an invalid FCC ID on the DoC | [Pyrodrone](https://pyrodrone.com/products/flite-test-ft-ez-id-remote-id-module); [ReadyMadeRC](https://www.readymaderc.com/products/details/85732-flite-test-ft-ez-id-remote-id-module); [BlueMark](https://bluemark.io/2024/06/faa-remoteid-compliance-an-inconvenient-truth/) |
| **Spektrum SkyID (SPMA9500)** | Powered by receiver or 2S | **Conflict:** 14 g (FPVFC) vs 58.9 g (Ohio Drone) | — | None | GPS + BT | Telemetry to the Spektrum transmitter; status LED | $99 ("nearly $100") | FAA module | [FPVFC sheet](https://docs.google.com/spreadsheets/d/1LPgSf_qI3JWOzmDOCqM31eQnzRBKPzUu_8RW2VCqAWU/); [Ohio Drone](https://www.ohiodronellc.com/?p=1949) |
| **uAvionix pingRID** | Self-contained | 21 g (UAVCoach) / 28 g (UAVMODEL) | — | — | GPS + BT | — | $299 | FAA module | [UAVCoach](https://uavcoach.com/remote-id-module/); [FPVFC sheet](https://docs.google.com/spreadsheets/d/1LPgSf_qI3JWOzmDOCqM31eQnzRBKPzUu_8RW2VCqAWU/) |
| **Zing Z-RID** (US-made) | Self-contained | 35 g | — | — | GPS + BT | — | $199 | FAA module | [Drone Girl](https://www.thedronegirl.com/2023/11/06/best-remote-id-module/) |
| **Zing Z-RID Lite** (Jan 2024) | Self-contained | — | — | — | — | — | Intro $84.99 → $99.99 | FAA module | [Drone Girl, Jan 2024](https://www.thedronegirl.com/2024/01/15/z-rid-lite/) |
| **Pierce Aerospace B1** | Self-contained | Not listed | — | — | GPS | — | $264.95 | FAA module | [FPVFC sheet](https://docs.google.com/spreadsheets/d/1LPgSf_qI3JWOzmDOCqM31eQnzRBKPzUu_8RW2VCqAWU/) |
| **Drone Defence Aeroping** (UK) | Self-contained | 38 g | — | — | GPS | — | €178.80 | UK/EU | [FPVFC sheet](https://docs.google.com/spreadsheets/d/1LPgSf_qI3JWOzmDOCqM31eQnzRBKPzUu_8RW2VCqAWU/) |
| **SINOSCOGO DIY (18089)** (Amazon, new) | Bare module, CAN + serial, non-rechargeable alkaline | 2 g (no case) | — | — | PX4/ArduPilot | — | Not stated. "No customer reviews yet" (Apr 2026) | Unclear | [Ohio Drone](https://www.ohiodronellc.com/?p=1949) |
| **SpeedyBee BT FC/AIOs** | Firmware-added RID over the FC's onboard Bluetooth | 0 g added | — | Drone-powered | Needs the FC's GPS | — | Free firmware update | **No FAA DoC found** | [IntoFPV](https://intofpv.com/t-speedybee-adds-rid-to-their-bt-fc-aio-with-firmware-update) |

### Cited Findings (beyond the table)
- GetFPV runs a dedicated Remote ID category, but the page returned 403 to automated fetch, so its current product list and prices could not be read. — [GetFPV](https://www.getfpv.com/electronics/remote-id.html)
- MyFPV lists only one RID product, the Phoenix UAS module at $79.99, though its brand list includes Flywoo, HappyModel and BetaFPV. — [MyFPV](https://www.myfpvstore.com/fpv-electronics/remote-id/)
- FPV Freedom Coalition highlights only four modules for FPV: FT EZ ID, Holy Stone, Phoenix mRID and Dronetag BS. — [FPVFC](https://fpvfc.org/remote-id-modules)
- Non-self-contained modules powered by the aircraft are lighter, and many FPV pilots prefer them. — [Droneblog](https://www.droneblog.com/best-remote-id-modules/)

### Inferences
- The "about $40, 13.5–20 g, 3–5 h battery, buzzer, Amazon" form factor is now commoditized by Ruko, Holy Stone/Holyton and Potensic, which are all drone OEMs that bundle and cross-sell. Spec differences are small. The real differentiators are battery life, app quality and GPS lock time.
- No product in the sweep combines all three of: (a) **<5 g**, (b) **its own battery and GPS** (needs no FC wiring), and (c) **under $50**. Dronetag BS Gen 2 (5 g, $99) is closest but costs twice the commodity tier.

### Gaps
- Not found: Ruko models other than R111/R111S (e.g., R111 vs R111S differences), mRo's RID product, and any FAA-accepted standalone module from BETAFPV, Happymodel, Flywoo, Foxeer, HGLRC or Axisflying. These brands may sell RID-enabled flight controllers or receivers, but I found no evidence.
- "Beyond" and "Nyx" RID products: nothing found.
- Exact FAA DoC tracking numbers per module were not retrieved. The FAA DoC system is a web app and was not queried.
- Radio formats (BT4 legacy vs BT5 Long Range vs Wi-Fi Beacon/NAN) are unverified for most consumer modules. Manufacturers rarely state them.
- Release dates for HSRID02, HSRID03, RID-916 and R111S were not found. HSRID02's ASIN (B0FP…) suggests a 2025 listing, but that is an inference only.

## 2. Amazon sales signals

### Takeaway
Ruko R111S looks like the clear Amazon volume leader. The figures provided by the caller (4.6 stars, 929 ratings, 500+ bought/month) are consistent with an April 2026 roundup citing 851 reviews for R111S versus 136 for Potensic RID-916. Holy Stone HSRID02 shows 100+ bought/month and #22 in Unmanned Aerial Vehicles. Pro products (Dronetag, BlueMark) sell mainly through specialist retailers, not Amazon.

### Cited Findings
- Holy Stone HSRID02 (ASIN B0FP49QWT5): "100+ bought in past month", Best Sellers Rank #32,930 in Toys & Games, #22 in Unmanned Aerial Vehicles (search snippet, undated). — [Amazon](https://amazon.com/dp/B0FP49QWT5)
- A Holy Stone module (listing unclear) is reported at 4.5 stars on "nearly 700 reviews" (article ~197 days old as of Oct 2026). — [Drone Nestle](https://dronenestle.com/drone-remote-id-module-review-is-holy-stone-faa-co/)
- Ohio Drone (April 2026) cites the Potensic RID-916 at 136 reviews versus the Ruko R111S at 851. — via search snippet of [Ohio Drone](https://www.ohiodronellc.com/?p=1949)
- On the Holy Stone store, the HSRID03 has 7 product reviews (71% 5-star, 29% 1-star). The 4.80 stars from 2,239 ratings figure appears to be store-wide, not for this product. — [Holy Stone store](https://store.holystone.com/products/hsrid03)
- On ruko.net, the R111 has two inconsistent rating sets: 4.9 from 24 reviews and 4.42 from 50. — [ruko.net via search](https://www.ruko.net/products/ruko-r111-remote-id-module)
- The SINOSCOGO DIY module had "no customer reviews yet" as of April 2026. — [Ohio Drone](https://www.ohiodronellc.com/?p=1949)

### Inferences
- If the Ruko R111S really sells 500+ units a month, that is roughly 6,000+ units/year at about $40, or about $240k/yr gross on that one ASIN. That is a modest category. The Amazon RID segment is small and probably capped by the number of non-RID drones over 250 g still flying.
- The Ruko and Holy Stone listings are often bundled (SD cards, landing pads, chargers). This suggests sellers are using bundles to escape head-to-head price comparison at $39.99.

### Gaps
- Direct Amazon reads for star rating, rating count, bought-past-month and BSR on Ruko R111S, Potensic RID-916, Holy Stone HSRID01/03, Dronetag and BlueMark failed (captcha/cart gate). These need a manual browser check.

## 3. Customer pain points

### Takeaway
Repeated complaints fall into six groups: short battery life (often only about 3 h in practice), slow GPS lock (up to 15 minutes reported on Potensic), buggy or platform-specific apps (Android for Ruko, iPhone for Holyton and Holy Stone), modules that fail to program or register, cheap labelling, and confusion over whether scanner apps "see" the module. For FPV, the pains are weight, wiring and the need for a separate GPS.

### Cited Findings
- Ruko R111S: needs a charger under 15 W, and users report Android app issues. Battery is about 3 h, or 2.5 h with the beeper on. — [Ohio Drone](https://www.ohiodronellc.com/?p=1949)
- Ruko R111: the registration number is a "printed paper label" on the side that a buyer worried could wear off. Praise centres on weight (<1 oz), and one user claims over 3,000 ft of connection. — [ruko.net reviews via search](https://www.ruko.net/products/ruko-r111-remote-id-module); [MavicPilots first impression](https://mavicpilots.com/threads/i-just-bought-the-ruko-r111-remote-id-module-here-is-my-first-impression.147468/)
- Potensic RID-916: GPS lock can take up to 15 minutes, users report firmware issues, and it is heavier than rivals. — [Ohio Drone](https://www.ohiodronellc.com/?p=1949)
- Holyton: a non-aerodynamic shape, reported iPhone app problems, and setup that confuses first-time users. — [Ohio Drone](https://www.ohiodronellc.com/?p=1949)
- Holy Stone HSRID03: one review says "Will not program", altitude readings are "sometimes questionable", iPhone receives only BT because Wi-Fi reception is blocked, and support took nearly a week to reply. — [Holy Stone store](https://store.holystone.com/products/hsrid03)
- Spektrum SkyID: reported FAA registration validation problems, ecosystem lock-in and mixed support. — [Ohio Drone](https://www.ohiodronellc.com/?p=1949)
- Dronetag Beacon V2: limited availability and a non-standard battery. — [Ohio Drone](https://www.ohiodronellc.com/?p=1949)
- Small self-powered units give only about 3 hours of battery, and "the charging cable DOES NOT COME WITH THE UNIT." — [CommercialDronePilots forum](https://commercialdronepilots.com/threads/recommendations-for-which-remote-id-to-buy.4495/)
- Scanner-app confusion: OpenDroneID-type apps detect standalone broadcast modules but not some built-in RID, and BT range is limited. Users see the apps as "just to verify operation, not real-time track." — [YuneecPilots](https://yuneecpilots.com/threads/remote-id-apps-opendroneid.22636/)
- GPS lock is needed before RID broadcasts properly, and a module that is flat or uncharged may not broadcast. — [MyDroneAuthority](https://mydroneauthority.com/how-to-check-that-your-drone-is-actually-broadcasting-remote-id/)
- FPV: bare boards need external antennas and a power source (Dronetag BS). Phoenix mRID needs a user-supplied M10 GPS. — [Dronetag BS](https://www.dronetag.com/products/bs); [Rotor Riot](https://rotorriot.com/products/mrid-remote-id-module-rotor-riot-edition)
- On sub-250 g builds, adding a module can push the drone over the threshold. — [UAVMODEL](https://blog.uavmodel.com/faa-remote-id-compliance-guide-for-fpv-drone-pilots-2026/)

### Inferences
- Several pains are cheap to fix with engineering: a quick-acquisition GNSS (multi-constellation with a good antenna), a laser-etched or engraved serial, a cross-platform app tested on both iOS and Android, USB-C that charges from any charger, a cable in the box, and 8+ h battery at 15 g or less.
- A built-in "am I broadcasting correctly?" self-test (an LED showing GPS fix and broadcast status, plus a companion app check) would address the scanner-app confusion.

### Gaps
- Reddit r/fpv and r/drones, and RCGroups threads, did not come up in searches. No verbatim Amazon 1–3 star review text was retrieved. Joshua Bardwell and Mads Tech review content was not found in this sweep.

## 4. Underserved segments

### Takeaway
The most underserved segment is **sub-30 g whoops and small FPV craft that are still "over 250 g" or flown recreationally outside FRIAs**. More specifically, it is pilots who want a module that is **light, self-powered, GPS-equipped and cheap** without wiring into a flight controller. Fixed-wing RC (Spektrum ecosystem) and integrators (MAVLink/DroneCAN OEM boards at $29–46) are already reasonably served.

### Cited Findings
- FPV-friendly options are either bare boards that need drone power and an external GPS (Phoenix mRID 2.2 g, needs M10 GPS; Dronetag BS 1.3 g, needs power) or $99 standalone units (Dronetag BS Gen 2 at 5 g, FT EZ ID at 10 g). — [Rotor Riot](https://rotorriot.com/products/mrid-remote-id-module-rotor-riot-edition); [Dronetag BS](https://www.dronetag.com/products/bs); [DroneDJ](https://dronedj.com/2024/03/07/dronetag-remote-id-module-price/); [Pyrodrone](https://pyrodrone.com/products/flite-test-ft-ez-id-remote-id-module)
- Integrator OEM boards are already cheap: db202mav at €29 ex VAT, db201 at €40, Cube ID at $39. — [DroneScout](https://dronescout.co/product/dronebeacon-mavlink-db202mav-transponder/?v=5f02f0889301); [DroneDJ](https://dronedj.com/guides/cubepilot/)
- Holybro sells to integrators only, who must file their own DoC, so there is no turnkey DIY option there. — [Holybro](https://holybro.com/products/remote-id)
- SpeedyBee added RID to its BT flight controllers via firmware, with no DoC confirmed. This could become a free, zero-gram threat if FC-integrated RID is accepted for module-type compliance. — [IntoFPV](https://intofpv.com/t-speedybee-adds-rid-to-their-bt-fc-aio-with-firmware-update)
- Fixed-wing RC: Spektrum SkyID uses receiver power and sends telemetry to the transmitter at about $99. — [Ohio Drone](https://www.ohiodronellc.com/?p=1949)
- Commercial Part 107: Dronetag Mini adds network RID, logging and 8–14 h battery at $329. — [Dronetag Mini](https://www.dronetag.com/products/mini)

### Inferences
- **A "Dronetag BS Gen 2 at a Ruko price" product** stands out as a gap: ~3–6 g, its own small cell and GNSS, BT Legacy + BT5 LR (+ Wi-Fi beacon), optional pass-through drone power (1S–6S), under $50, with a verifiable DoC.
- Schools and clubs (FRIA alternatives) may want multi-packs and fleet management for shared modules. No vendor targets this explicitly in the sources found. This is an inference with no direct source.
- A risk to the FPV segment is that FC-integrated RID (SpeedyBee) or ELRS/receiver-integrated RID could make add-on modules redundant for builders with GPS.

### Gaps
- No sales or market-size data by segment. No survey data on how many FPV pilots fly in FRIAs versus with modules.

## 5. DoC rescissions and quality controversies

### Takeaway
I found **no confirmed FAA rescission of a broadcast-module DoC**. The only rescission found is for an aircraft: the DJI Mavic Pro Platinum (RID000000111), requested by DJI itself and published in July 2023. The biggest quality controversy is BlueMark's (a competitor's) public allegation that the Holy Stone HSRID01, Holyton, FT EZ ID and Phoenix mRID do not meet ASTM F3586-22 or Part 89.

### Cited Findings
- The FAA rescinded the DoC RID000000111 for the DJI Mavic Pro Platinum (accepted Jan 19, 2023) at DJI's request, after DJI said the products did not comply with Part 89. — [Federal Register, Jul 12, 2023](https://www.federalregister.gov/documents/2023/07/12/2023-14802/notice-of-rescission-of-unmanned-aircraft-systems-remote-identification-declaration-of-compliance); [Unmanned Airspace](https://www.unmannedairspace.info/latest-news-and-information/faa-rescinds-remote-id-compliance-declaration-for-dji-mavic-pro-platinum/)
- Rule mechanics: the FAA may rescind when a module fails §89.310/89.320. It may allow time to remediate first, publishes a notice in the Federal Register, and products under a rescinded DoC can then fly only in FRIAs. — [eCFR Part 89](https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-89)
- BlueMark (June 2024, updated June 2025) tested the Holy Stone HSRID01. It says the module does not broadcast in the required BT Legacy + BT5 LR formats or the required non-connectable advertising type. It also reports a take-off position drift of more than 300 m (the limit is 100 ft) and output power of about -0.3 dBm against a +3 dBm minimum. BlueMark is a competitor and caveats that its findings may be "incomplete, outdated or incorrect." — [BlueMark](https://bluemark.io/2024/06/faa-remoteid-compliance-an-inconvenient-truth/)
- The same post alleges that Holy Stone drones (HS600/720/700E/900) registered as standard RID use what is effectively an add-on module. It also flags the Holyton HT60's FCC ID pointing to a drone, the FT EZ ID DoC citing "NRF52840" as its FCC ID, and Phoenix mRID's inverted-F antenna as missing pattern and power requirements. — [BlueMark](https://bluemark.io/2024/06/faa-remoteid-compliance-an-inconvenient-truth/)

### Inferences
- Independent RF and conformance testing (power, BT LR, message rates, position accuracy) is a credible differentiator. Publishing third-party ASTM F3586 test reports could win trust against $40 modules that face allegations.

### Gaps
- I could not check whether the FAA acted on BlueMark's allegations. No 2025–2026 Federal Register rescission notices for modules were found, but the Federal Register was not exhaustively searched.

## 6. Pricing trends

### Takeaway
Prices have fallen sharply since 2023. The consumer tier dropped from $89 (Holy Stone HSRID01, 2023) and $59.99 (Ruko launch) to a $39.99 standard with coupons around $33. Pro and OEM prices fell 40–60% (db201 €99→€40, db202mav €49→€29, Aerobits idME Pro €229→€99, Dronetag Beacon €199→€139). **No FAA-compliant standalone module was confirmed below $30.** The floor is about $33–40 for consumer modules and about $29–39 for OEM boards that need FC integration.

### Cited Findings
- Holy Stone HSRID01 cost $89 on the ~2023 FPVFC sheet. HSRID03 is now $39.99. — [FPVFC sheet](https://docs.google.com/spreadsheets/d/1LPgSf_qI3JWOzmDOCqM31eQnzRBKPzUu_8RW2VCqAWU/); [Holy Stone](https://store.holystone.com/products/hsrid03)
- Ruko launched at $59.99, now sells at $39.99, and has been seen at ~$33 with a coupon. — [Ruko blog](https://www.ruko.net/blogs/ruko/introducing-ruko-r111-remote-id-module-enhancing-drone-safety-and-compliance); [ruko.net](https://www.ruko.net/products/ruko-r111-remote-id-module); [PhantomHelp](https://forum.phantomhelp.com/t/i-just-bought-the-ruko-r111-remote-id-module-here-is-my-first-impression/9816)
- BlueMark db201 went from €99 ex VAT (Dec 2022) to €40 ex VAT. The db202mav went from €49 to €29 ex VAT. — [BlueMark](https://bluemark.io/2022/12/remote-id-db201-module-launched/); [DroneScout](https://dronescout.co/product/dronebeacon-mavlink-db201-transponder/?v=0b3b97fa6688)
- Aerobits announced price reductions in May 2024, with the idME Pro at €99. — [UST](https://www.unmannedsystemstechnology.com/2024/05/aerobits-announces-price-reduction-on-remote-id-modules/)
- Dronetag Beacon went from €199 (Gen 1, FPVFC sheet) to €139/$149 (official), while Drone Nerds still lists it at $219. Dronetag Mini stays at $329, with resellers at $229. — [FPVFC](https://docs.google.com/spreadsheets/d/1LPgSf_qI3JWOzmDOCqM31eQnzRBKPzUu_8RW2VCqAWU/); [Dronetag](https://www.dronetag.com/products/beacon); [Drone Nerds](https://www.dronenerds.com/products/dronetag-beacon-v2)
- Zing Z-RID Lite launched at $84.99 intro / $99.99, against $199 for the Z-RID. — [Drone Girl](https://www.thedronegirl.com/2024/01/15/z-rid-lite/)
- A search for compliant modules under $30 found none confirmed. Potensic at "~$30–35" comes from a single unverifiable document. — [Pilot Institute](https://pilotinstitute.com/remote-id-drone-modules/)

### Inferences
- The consumer tier has bottomed out at about $40, where drone OEMs (Ruko, Holy Stone, Potensic) treat RID as an accessory. A new entrant is unlikely to win on price alone, and would need a structural cost advantage to go below $30 with margin. Better ground: being lighter at the same price (5 g vs 13.5 g), longer battery, better GNSS and app, and published conformance tests.
- US-specialist retail prices (Drone Nerds, B&H) run 30–60% above manufacturer list for European brands, which leaves an opening for a US-stocked, mid-priced product.

### Gaps
- No time-series price data (e.g., Keepa/CamelCamelCamel) was retrieved. Trend claims rest on launch versus current list prices.
