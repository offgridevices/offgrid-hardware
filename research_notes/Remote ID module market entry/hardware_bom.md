# Broadcast Remote ID Module: Hardware, Firmware and BOM (research notes, October 2026)

Scope: what goes inside a broadcast RID module, which chips and modules to use, a realistic BOM and unit cost at 1k/10k, and which features would beat the Ruko R111S (13.5 g, GPS, buzzer, about 3 h, $30-40). Research covered about 19 tool calls. **All prices are snapshots or estimates. Every estimate is marked [EST].**

## Q1. Teardowns: what chips do existing modules use?

### Takeaway
Most shipping modules use one of two radio families: an Espressif ESP32-C3 module (BlueMark db12x/db20x, uAvionix pingRID, Phoenix mRID, Holybro) or a Nordic nRF52840-class module (Dronetag BL653/ANNA-B412, BlueMark db300 on the BMD-345, FT EZ-ID). GNSS is split between budget ATGM336H and u-blox M8/M10 parts. I could not find what is inside the Ruko R111S.

### Cited Findings
- AMA's spring 2024 module chart lists each module's radio, GNSS, weight, battery and price — [AMA RID Module Status Report](https://www.modelaircraft.org/system/files/documents/AMA_RID_Module_Status_Report.pdf):
  - **uAvionix pingRID:** ESP32-C3-MINI-1 + u-blox SAM-M8Q, 21 g, 2 h battery, $299.
  - **BlueMark db121pcb:** ESP32-C3-WROOM-02 + ATGM336H-5N31, 5 g, no battery (5-14 V), $106. The cased db121 is 11 g, $118.
  - **BlueMark db120:** same chips, 25 g, 3 h battery, $139.
  - **BlueMark db122fpv:** ESP32-C3-MINI-1U, no GNSS (uses the drone's GPS), 4.5 g, $76.
  - **Dronetag Beacon:** Laird BL653 (nRF52833-based) + u-blox MIA-M10Q, 16 g, 8-16 h, $215.
  - **Dronetag Mini:** BL653 + MIA-M10Q, 32 g, 8-16 h, $299.
  - **Dronetag "Basic Solution":** u-blox ANNA-B412 + MIA-M10Q, 3 g, $89.
  - **Dronetag DRI:** ANNA-B412, no GNSS, 1.5 g, $49.
  - **Aerobits idME:** "ESP32 series" + u-blox ZOE-M8B, 4 g, $191-250.
  - **B1 Remote ID Beacon:** Laird BL654 (nRF52840), 30 g, 6 h, $265.
  - **FliteTest EZ-ID:** nRF52840 (the chart says "NFR52849") + SAM-M8Q, 10 g, powered from 2S-8S, $109.
  - **Holy Stone HSRID01:** chips not published, 14 g, 5 h, $89.99.
  - **Z-RID Lite:** chips not published, 30 g, 4 h, $84.99.
- The AMA report states that BT 5.x chips "draw much less current providing more hours of runtime". It notes that the FAA's 2020 estimate of $50 per module was based on now-obsolete chips. — [AMA report](https://www.modelaircraft.org/system/files/documents/AMA_RID_Module_Status_Report.pdf)
- **BlueMark db201:** a drop-in replacement for the db200 in which only the ESP32-C3 module changed. It runs the open-source ArduRemoteID firmware. It weighs about 4-5 g without antenna, launched at €99 ex VAT, and was later about €79. — [BlueMark db201 launch](https://bluemark.io/2022/12/remote-id-db201-module-launched/); [BlueMark db200 datasheet](https://download.bluemark.io/db200.pdf); [POM USA guide](https://www.pomusa.com/remote-id-modules/)
- **BlueMark db300** (announced 8 Oct 2026):
  - Built on the u-blox BMD-345 module with a Nordic nRF52840.
  - 2.5 g, 27.5 × 27.5 mm.
  - Broadcasts BT4 Legacy + BT5 Long Range.
  - MAVLink + DroneCAN (CAN 2.0/CAN FD); updates via Bluetooth OTA, SWD or CAN.
  - €69 ex VAT.
  - On the Blue UAS Framework since 10 Jul 2026 and NDAA 848/889 compliant.
  - It is a software drop-in for the db201, which signals that BlueMark moved from ESP32-C3 to nRF52840. — [BlueMark db300 Blue UAS](https://bluemark.io/2026/10/db300-blue-uas-approved/)
- **Dronetag Mini:**
  - 32 g, 3.7 V 500 mAh LiPo, 8-14 h battery life.
  - GPS/GLONASS/Galileo/SBAS.
  - Sensors: GNSS, **barometer** and accelerometer.
  - Internal LTE, BT and GNSS antennas.
  - Complies with prEN 4709-002 and ASTM F3411.
  - The Mini 4G is 36 g with a 600 mAh battery.
  — [Dronetag Mini spec](https://help.dronetag.com/dronetag-mini/specification/); [Dronetag Mini 4G](https://www.dronetag.com/products/mini-4g)
- BlueMark's own compliance review (a competitor with a commercial interest; these are not FAA findings):
  - **Holy Stone HSRID01/02** (FCC ID 2AJ55HOLYSTONEBM) uses a non-connectable, non-scannable advertising type the standard does not allow. Its take-off position drifted more than 300 m, and it puts out about -0.3 dBm against a +3 dBm minimum.
  - **FT EZ-ID** used "NRF52840" as its FCC ID.
  - **Phoenix UAS mRID** uses an ESP32-C3-MINI-1 (2AC7Z-ESPC3MINI1). BlueMark judges that its inverted-F antenna likely fails the 4 dB peak-to-average gain limit and the +3 dBm minimum power.
  - The page says "any inverted-F antenna product will likely fail."
  — [BlueMark: FAA RemoteID compliance, an inconvenient truth](https://bluemark.io/2024/06/faa-remoteid-compliance-an-inconvenient-truth/)
- **Ruko R111/R111S:**
  - The FCC ID for the R111 is **2AXQL-R111**; its manual is on fcc.report. I could not confirm that the R111S uses the same FCC ID. — [fcc.report R111 manual](https://fcc.report/FCC-ID/2AXQL-R111/7529586.pdf)
  - The serial number is registered with the FAA and shown in the "Ruko Scanner" app. — [ManualsLib R111 manual](https://www.manualslib.com/manual/3562819/Ruko-R111.html)
  - Retail listings give 13.5 g, about 3 h with the buzzer off and about 2.5 h with it on, a 40-minute charge, and 500-1000 m tracking range. — [micro-tools listing](https://www.micro-tools.com/products/ruko-r111s-rc-aircraft-gps-tracker-finder-with-beeper-light-weight-rid-module-with-buzzer-for-faa-regulation-spare-part-for-fpv-drone-faa-compliant-remote-id-module-for-drone-3-hours-battery-time); [PropelRC](https://www.propelrc.com/?p=105092)

### Inferences
- The ESP32-C3 + ATGM336H combination (BlueMark db12x) is the proven low-cost reference that gained FAA DoC acceptance. nRF52840 + u-blox M10 is the premium, long-battery path (Dronetag, BlueMark db300).
- The radio has to clear +3 dBm minimum output, and the antenna pattern has to meet the 4 dB peak-to-average limit. A pre-certified module with a good antenna, plus a pre-scan of the antenna pattern, is a real certification risk item, not just a formality.
- Because R111 battery life (about 3 h at 13.5 g) is short compared with nRF-based units, the R111 probably uses an ESP32-class radio and a budget GNSS. This is **unverified**; FCC internal photos would settle it.

### Gaps
- No teardown or internal photos found for the Ruko R111S, Potensic, Pierce Aerospace or Cube ID. fcc.report returned 403 for 2AXQL-R111; fccid.io search found no RID-specific filings. Next step: pull the 2AXQL-R111 internal photos exhibit by hand on fccid.io or apps.fcc.gov.
- Holybro RID weight and chips were not confirmed here. ArduRemoteID lists the Holybro module as supported, which implies an ESP32-S3 or C3.

## Q2. Radio requirements: BT4, BT5 LR, Wi-Fi NAN, Wi-Fi Beacon (US vs EU) and SoC support

### Takeaway
In the US, a module must broadcast either BT4 Legacy **and** BT5 Long Range at the same time, or Wi-Fi Beacon; Wi-Fi NAN is not an allowed FAA method. The EU (prEN 4709-002) allows the Bluetooth and Wi-Fi methods. Of the candidate SoCs:
- **ESP32-C3/S3/C6** can do all four transports.
- **nRF52840/nRF5340** do BT4 + BT5 Coded PHY only, which is enough for the US, and are far more power-efficient.
- The original ESP32 cannot do BT5 Long Range.

### Cited Findings
- From the opendroneid-core-c comparison table (the table text was garbled in the fetch, so footnote mapping is approximate):
  - FAA: only one of the mandatory broadcast methods is required.
  - BT4 and BT5 must be sent at the same time.
  - Only BT4+BT5 together, or Wi-Fi Beacon (2.4 or 5 GHz), is allowed.
  - A non-standard Wi-Fi channel (other than 2.4 GHz ch6 or 5 GHz ch149) requires a 5 Hz rate.
  - Japan: BT5 LR or Wi-Fi Beacon is mandatory and BT4 is optional.
  — [opendroneid-core-c README](https://github.com/opendroneid/opendroneid-core-c)
- The original ESP32 supports only BT Legacy Advertising. BT Long Range and Extended Advertising need the ESP32-S3 or ESP32-C3. ArduRemoteID on C3/S3 supports BT4, BT5 LR, Wi-Fi Beacon and Wi-Fi NAN. — [opendroneid-core-c](https://github.com/opendroneid/opendroneid-core-c); [ArduRemoteID](https://github.com/ArduPilot/ArduRemoteID)
- An nRF52 implementation of BT4 and BT5 for ASTM F3411 / EN 4709-002 exists. — [sxjack/remote_id_bt5](https://github.com/sxjack/remote_id_bt5)
- prEN 4709-002 is the means of compliance for EU Direct Remote ID under Regulation (EU) 2019/945. It was published 1 Feb 2023. — [GlobalSpec prEN 4709-002](https://standards.globalspec.com/std/14594346/pren-4709-002)
- The EU requires an operator ID to be broadcast, and Japan requires a Bluetooth app link, so region-specific firmware or configuration is needed. — [BlueMark compliance post](https://bluemark.io/2024/06/faa-remoteid-compliance-an-inconvenient-truth/)
- **Range:** AMA reports the maximum broadcast range is about 2 km, limited by Bluetooth, and position data stayed accurate "at ranges over a kilometer". Ruko claims 500-1000 m. — [AMA report](https://www.modelaircraft.org/system/files/documents/AMA_RID_Module_Status_Report.pdf); [PropelRC](https://www.propelrc.com/?p=105092)
- **Minimum output and antenna limits:** +3 dBm minimum radiated output and a 4 dB peak-to-average antenna gain limit (BlueMark's reading of the FAA MoC). — [BlueMark](https://bluemark.io/2024/06/faa-remoteid-compliance-an-inconvenient-truth/)
- ESP32-C3 power at the radio (forum measurements):
  - TX peaks of about 300 mA at +21 dBm and about 200 mA at +18 dBm.
  - About 17 mA idle with RF off at 80 MHz.
  - Datasheet sleep figures of 130 µA (light) and 5 µA (deep).
  — [esp32.com thread](https://esp32.com/viewtopic.php?p=113068); [esp32.com](https://esp32.com/viewtopic.php?p=106434)

### Inferences
- **US-only product:** BT4 + BT5 LR on an nRF52840 module is enough, and gives the longest battery life. Wi-Fi Beacon adds range for some receivers but costs a lot of power.
- **US + EU product:** BT4 + BT5 LR is still compliant in the EU. Wi-Fi Beacon/NAN on an ESP32-C3/C6 widens phone compatibility, since many Android phones receive NAN or Beacon but not Coded PHY. Many iPhones cannot receive BT5 LR or NAN at all.
- **ESP32-C6:** already used by OffGrid, and supports BLE 5 including Coded PHY and Wi-Fi. ArduRemoteID officially targets only S3/C3, so a C6 port would be new work. **Unverified:** C6 Coded PHY extended advertising has not been confirmed with ArduRemoteID.

### Gaps
- I did not retrieve the normative transport table from ASTM F3586-22 or EN 4709-002; the footnote mapping above comes from a garbled README fetch. The ASTM F3586-22 text should be read before finalising the radio choice.
- No measured average current found for ArduRemoteID in BT-only vs Wi-Fi modes.

## Q3. GNSS: modules, accuracy, constellations, TTFF, power; barometer

### Takeaway
14 CFR 89.320 requires reported position within 100 ft at 95% confidence and geometric altitude within 150 ft at 95%; any modern GNSS meets this easily. The cheapest proven part is the ATGM336H (about $1.50-1.90 at LCSC, under 25 mA). The u-blox MAX-M10S costs about $10.60 but draws about 25 mW, roughly 3x less power, which is what enables long battery life. A barometer is optional; Dronetag adds one.

### Cited Findings
- Reported geometric position must be within 100 ft of true position at 95% confidence (14 CFR 89.320). — [eCFR 89.320](https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-89/subpart-D/section-89.320)
- Geometric altitude must be within 150 ft and control station altitude within 15 ft (secondary source; confirm against eCFR). — [mmoww guide](https://mmoww.net/us/drone/remote-id-part-89-guide/)
- ASTM F3586-22 was accepted as an FAA means of compliance, with a correction notice. — [Federal Register 2023-23058](https://public-inspection.federalregister.gov/2023-23058.pdf)
- Modern GNSS achieves 5-10 ft horizontal and 16 ft or better vertical at 95%. — [AMA report](https://www.modelaircraft.org/system/files/documents/AMA_RID_Module_Status_Report.pdf)
- **LCSC prices (snapshot, single qty):** — [LCSC MAX-M10S](https://www.lcsc.com/product-detail/C4153167.html); [LCSC ATGM336H-5N31](https://www.lcsc.com/product-detail/GNSS-Modules_ZHONGKEWEI-ATGM336H-5N31_C90770.html); [LCSC ATGM336H-5NR32](https://www.lcsc.com/product-detail/Satellite-Positioning-Modules_ZHONGKEWEI-ATGM336H-5NR32_C5117921.html)

  | Part | Price |
  |---|---|
  | MAX-M10S-00B | about $10.60 |
  | ATGM336H-5N31 | about $1.82 |
  | ATGM336H-5N71 | about $1.92 |
  | ATGM336H-5NR32 | about $1.53 |

- **Power:**
  - MAX-M10S: 25 mW continuous tracking (about 7.6 mA at 3.3 V, my conversion). — [DigiKey MAX-M10](https://www.digikey.com/en/product-highlight/u/u-blox/max-m10-series)
  - ATGM336H: under 25 mA at 3.3 V (GPS+BDS). — [ATGM336H datasheet](https://datasheet.lcsc.com/lcsc/ZHONGKEWEI-ATGM336H-5N31_C90770.pdf)
  - Quectel L76K: 29 mA acquisition/tracking, 8 µA backup, 2.0 m CEP. — [Waveshare L76K wiki](https://www.waveshare.com/wiki/L76K_GPS_Module)
- The ATGM336H is not compatible with u-center or UBX commands. — [petertanner.dev comparison](https://www.petertanner.dev/posts/Chinese-ZHONGKEWEI-ATGM-GNSS-modules-comparison/)
- **Barometer:** Dronetag Mini includes a barometer and accelerometer. — [Dronetag spec](https://help.dronetag.com/dronetag-mini/specification/)

### Inferences
- **GNSS choice:**
  - ATGM336H for the lowest cost; BlueMark shipped it with an FAA DoC.
  - MAX-M10S for long battery life and UBX tooling (power-save modes, a well-documented module). MAX-M10S is also NDAA-friendlier than a Chinese GNSS if Blue UAS or government buyers matter.
  - The L76K draws the most power of the three.
- **Barometer:** 89.320 references geometric altitude, so a baro is optional. Adding a BMP390/DPS310-class baro (about $1-2 [EST]) allows the optional pressure-altitude field and better relative height for the app.
- **Antenna and fix behaviour:** a 25 × 25 or 18 × 18 mm patch gives the best TTFF and fix holding. A chip antenna saves about 2-4 g [EST] but hurts cold starts. Keeping a supercap or backup rail powered for hot-starts cuts TTFF to seconds.

### Gaps
- No measured TTFF comparison was found. No current LCSC price for the L76K or LC76G.

## Q4. Open-source firmware: licensing, FAA DoC use, security

### Takeaway
ArduRemoteID is **GPLv2-or-later** and runs on ESP32-C3/S3. It powers FAA-DoC-accepted BlueMark modules, supports MAVLink and DroneCAN, and already implements signed firmware, parameter locking and eFuse lock. opendroneid-core-c (the message encoder) is **Apache-2.0**, so it can go into closed or nRF-based firmware.

### Cited Findings
- **ArduRemoteID:**
  - License: GPLv2 or later.
  - Boards: ESP32-S3/C3 dev boards, BlueMark DB110/DB200/DB201/DB202mav/DB210pro, and the Holybro RID.
  - Transports: Wi-Fi Broadcast, Wi-Fi NAN, BT4 Legacy, BT5 LR + Extended Advertising.
  - Interfaces: MAVLink OpenDroneID messages and DroneCAN.
  - Security: OTA requires signatures matching up to 5 public keys. LOCK_LEVEL 1 requires a signed SecureCommand for parameter changes. LOCK_LEVEL 2 burns eFuses so that only signed web updates are possible, and cannot be undone.
  — [ArduRemoteID GitHub](https://github.com/ArduPilot/ArduRemoteID)
- **opendroneid-core-c:**
  - License: Apache-2.0.
  - Complies with F3411-19, F3411-22a and ASD-STAN prEN 4709-002; protocol versions 0-2.
  - Includes the mav2odid MAVLink conversion.
  — [opendroneid-core-c](https://github.com/opendroneid/opendroneid-core-c)
- The OpenDroneID Android receiver app supports the Bluetooth, Wi-Fi NAN and Beacon parts of F3411 and prEN 4709-002. — [receiver-android](https://github.com/opendroneid/receiver-android); [OpenDroneID OSM on Play](https://play.google.com/store/apps/details?id=org.opendroneid.android_osm&hl=en-US)
- The db201 runs ArduRemoteID; BlueMark modules are on the FAA DoC list. — [BlueMark db201](https://bluemark.io/2022/12/remote-id-db201-module-launched/); [AMA report](https://www.modelaircraft.org/system/files/documents/AMA_RID_Module_Status_Report.pdf)
- BlueMark offers a partner program with a manual and template for drone makers' own FAA DoC. — [BlueMark db300](https://bluemark.io/2026/10/db300-blue-uas-approved/)
- Recommended buyer checks: was the module externally audited, can its firmware be updated, is the FCC ID valid, does it match its DoC. — [BlueMark compliance post](https://bluemark.io/2024/06/faa-remoteid-compliance-an-inconvenient-truth/)

### Inferences
- **Licensing:** shipping ArduRemoteID (GPL) is fine for an open-hardware company. The firmware source must be published, which suits OffGrid. Production builds stay locked through signing keys; the keys themselves are not GPL-covered.
- **Firmware paths:**
  - ESP32: fork ArduRemoteID.
  - nRF52840: write firmware in Zephyr/nRF Connect SDK around opendroneid-core-c (Apache-2.0). This means more work, but no GPL obligation.
- **Required security features:**
  - A serial number that cannot be altered, held in eFuse or OTP.
  - Firmware that resists tampering: secure boot plus signed updates.
  - A self-test and failure indication; standard practice is an LED or buzzer that fires if broadcast or GPS fails.
  - Note: 89.320 specifics on tamper resistance were not fetched here.

### Gaps
- No confirmed list of which FAA DoCs (mRo, CubePilot Cube ID, Holybro) rely on ArduRemoteID; the README does not name DoC holders. The FAA DoC list on DroneZone should be checked.

## Q5. Power: battery, charging, drone-powered options and FC integration

### Takeaway
The radio and GNSS currents decide the battery size:
- **ESP32-C3 + ATGM336H**, about 40-60 mA average [EST]: about 150-200 mAh for 3 h. This matches the Ruko and the 25 g BlueMark db120 at 3 h.
- **nRF52840 + MAX-M10S**, about 12-20 mA [EST]: the same cell lasts about 8-12 h. That is the clearest technical lever to beat the R111S.

FPV integration (5 V from the FC plus MSP/GPS passthrough to Betaflight) exists but is not standardised.

### Cited Findings
- **Cell sizes and runtimes:**
  - Dronetag Mini: 500 mAh LiPo for 8-14 h (with LTE). — [Dronetag spec](https://help.dronetag.com/dronetag-mini/specification/)
  - Mini 4G: 600 mAh for 10 h. — [Mini 4G](https://www.dronetag.com/products/mini-4g)
  - Dronetag Beacon: 16 g, 8-16 h, nRF-based. — [AMA report](https://www.modelaircraft.org/system/files/documents/AMA_RID_Module_Status_Report.pdf)
- BT 5.x chips "draw much less current providing more hours of runtime". — [AMA report](https://www.modelaircraft.org/system/files/documents/AMA_RID_Module_Status_Report.pdf)
- Ruko R111S: about 3 h without buzzer, 2.5 h with, 40-minute charge. — [micro-tools listing](https://www.micro-tools.com/products/ruko-r111s-rc-aircraft-gps-tracker-finder-with-beeper-light-weight-rid-module-with-buzzer-for-faa-regulation-spare-part-for-fpv-drone-faa-compliant-remote-id-module-for-drone-3-hours-battery-time)
- **Drone-powered modules:**
  - BlueMark db121/db122: 4.5-15 V input.
  - FT EZ-ID: 2S-8S input.
  - Dronetag DRI/Basic: 3.3-17 V input.
  — [AMA report](https://www.modelaircraft.org/system/files/documents/AMA_RID_Module_Status_Report.pdf)
- **Betaflight GPS passthrough (Flite Test EZ-ID):**
  - Wiring: module TX goes to a free FC RX pad; MSP is enabled on that UART and the GPS protocol is set to MSP.
  - Version: needs Betaflight 4.4.3 or newer.
  - Limit: at most 3 MSP UARTs.
  — [Flite Test guide](https://www.flitetest.com/articles/connecting-ez-id-to-betaflight-for-gps-passthrough)
- libdrone describes a similar UART GPS-passthrough setup at 57,600 baud. — [libdrone](https://libdrone.eu/reference/remote-id-compliance/)
- Phoenix UAS passes GPS to Betaflight via MSP and works with M9/M10 GPS modules (vendor claim). — [Phoenix UAS](https://www.phoenixuas.us/remoteid)
- A claim that Betaflight 4.5+ natively supports serial RID modules over MSP is **unverified** and contradicted: libdrone says Betaflight has no native RID. — [UAVMODEL blog](https://blog.uavmodel.com/faa-remote-id-requirements-2026-what-every-fpv-pilot-must-know/); [libdrone](https://libdrone.eu/reference/remote-id-compliance/)
- ArduPilot/PX4 integration via MAVLink OpenDroneID or DroneCAN is mature. — [ArduRemoteID](https://github.com/ArduPilot/ArduRemoteID); [MAVLink OpenDroneID service](https://github.com/mavlink/mavlink-devguide/blob/master/en/services/opendroneid.md)

### Inferences
- **Battery sizing [EST]:**
  - 3 h on an ESP32-C3: a 150-200 mAh LiPo (about 3.5-4.5 g).
  - 8 h+ on an nRF52840 + MAX-M10S: a 150-250 mAh cell.
  - This assumes the nRF52840 averages a few mA while advertising BT4+BT5 at the required rates and the MAX-M10S draws about 8 mA. These numbers need bench measurement on a PPK2.
- **Charger:** a single-cell linear charger (TP4054/TP4056 class or BQ25100 for tiny cells) plus USB-C with 5.1 kΩ CC pull-downs. Add a low-Iq LDO or buck (for example TPS62840 or a TLV755-class LDO).
- **Dual power:** a power-path diode or OR-ing lets the module run from the drone's 5 V when present and switch to its own battery otherwise. A battery-backed module keeps broadcasting and locating after a crash disconnects the drone battery.

### Gaps
- No published average current for any specific RID module, and no measured nRF52840 RID-advertising current.

## Q6. Weight optimisation: lightest achievable, PCB and antennas

### Takeaway
Bare drone-powered PCB modules already reach 1.5-5 g (Dronetag DRI 1.5 g, Dronetag Basic 3 g, BlueMark db300 2.5 g, db122fpv 4.5 g). A self-powered module with GNSS and battery sits at 11-32 g in competitors, with Ruko at 13.5 g. A sub-10 g self-powered unit with 3 h+ runtime looks achievable, but not cheaply.

### Cited Findings
- **Bare modules:** Dronetag DRI 1.5 g (no GNSS, no case); Dronetag Basic 3 g with MIA-M10Q; Aerobits idME 4 g with ZOE-M8B; db122fpv 4.5 g; db121pcb 5 g with ATGM336H. — [AMA report](https://www.modelaircraft.org/system/files/documents/AMA_RID_Module_Status_Report.pdf)
- BlueMark db300: 2.5 g, 27.5 × 27.5 mm. — [BlueMark db300](https://bluemark.io/2026/10/db300-blue-uas-approved/)
- **Antenna risk:** inverted-F antennas likely fail the 4 dB peak-to-average gain limit and the +3 dBm minimum, which favours a dipole, monopole or well-tuned chip antenna with an omnidirectional pattern. — [BlueMark compliance post](https://bluemark.io/2024/06/faa-remoteid-compliance-an-inconvenient-truth/)

### Inferences
- **Lightest self-powered design [EST]:** a few chips plus the cell and a thin shell.

  | Part | Weight |
  |---|---|
  | nRF52840 module (BMD-345/MS88SF2-class) | ~1 g |
  | MIA-M10Q or MAX-M10S + chip/small patch | 1-2 g |
  | 0.8 mm 4-layer PCB | 1-1.5 g |
  | 150 mAh LiPo | 3-3.5 g |
  | Thin PC/ABS shell | 1.5-2.5 g |
  | **Total** | **8-10 g** |

- **PCB:** 0.6-0.8 mm FR4 4-layer at JLCPCB with a solid ground under the GNSS. A 15 × 15 mm patch is a good trade-off between weight and TTFF.

### Gaps
- No primary weight breakdowns for any module.

## Q7. Differentiating features

### Takeaway
The strongest differentiators against the R111S:
- 3x longer battery from an nRF + M10 architecture.
- Lower weight, under 10 g.
- USB-C.
- Dual power (drone 5 V and its own battery).
- A finder mode: buzzer, plus last-known GPS readable over BLE after a crash.
- An optional LoRa beacon for lost-drone recovery, using OffGrid's existing RAK/LoRa experience.
- Open firmware that is externally audited.

### Cited Findings
- **Competitor feature points:**
  - Dronetag adds network RID over LTE, a barometer and an accelerometer. — [Dronetag spec](https://help.dronetag.com/dronetag-mini/specification/)
  - Ruko's finder is a buzzer. — [micro-tools](https://www.micro-tools.com/products/ruko-r111s-rc-aircraft-gps-tracker-finder-with-beeper-light-weight-rid-module-with-buzzer-for-faa-regulation-spare-part-for-fpv-drone-faa-compliant-remote-id-module-for-drone-3-hours-battery-time)
  - BlueMark db300 targets Blue UAS/NDAA buyers. — [BlueMark db300](https://bluemark.io/2026/10/db300-blue-uas-approved/)
- **Receiver apps:** Drone Scanner (Dronetag) on Android and iOS, and OpenDroneID OSM. Some older phones cannot receive all BT4/BT5 modules. — [AMA report](https://www.modelaircraft.org/system/files/documents/AMA_RID_Module_Status_Report.pdf)
- Independent audits and firmware updatability are what buyers should check. — [BlueMark compliance post](https://bluemark.io/2024/06/faa-remoteid-compliance-an-inconvenient-truth/)

### Inferences
- **Ranked by value per cost [EST]:**
  1. Battery life of 8-12 h (nRF + M10).
  2. Weight under 10 g.
  3. FPV wiring option: 5 V in plus GPS/MSP passthrough to Betaflight. The module then doubles as the quad's GPS, which removes a separate GPS unit and saves weight.
  4. "Last-known position" finder over BLE, plus buzzer and LED, through the phone app.
  5. LoRa 868/915 beacon (SX1262 adds about $2-3 and 1 g) for multi-km lost-drone recovery.
  6. Flight logging to internal flash.
  7. IP54 conformal coating.
  8. Mounting by velcro, zip-tie slots or a GoPro mount.
- **LoRa caution:** LoRa beacons are not part of RID compliance. They need separate FCC Part 15.247 testing and must not interfere with RC links.

### Gaps
- No market data on which features buyers value most; that sits in another researcher's scope.

## Q8. BOM at 1k and 10k, NRE and manufacturing

### Takeaway
A self-powered RID module costs roughly **$9-14 [EST] at 1k** and **$6-9 [EST] at 10k** in ESP32-C3 + ATGM336H form. The nRF52840 + MAX-M10S version costs about **$18-25 [EST] at 1k** and **$13-18 [EST] at 10k**. NRE runs about **$15-40k [EST]**, most of it injection-mould tooling, FCC/FAA testing and test fixtures. Hitting $30-40 retail is feasible only with the ESP32 + ATGM336H design or at volume.

### Cited Findings
- **Component prices:**
  - ESP32-C3-MINI-1-N4: LCSC shows about $1.01-1.29 on one snapshot and $3.15 at qty 1 on another (Flux mirror). The sources conflict; treat about $1.3-2.0 as a realistic volume price. — [LCSC C2838502](https://fat.lcsc.com/product-detail/RF-Modules_Espressif-Systems-ESP32-C3-MINI-1-N4_C2838502.html); [Flux LCSC mirror](https://www.flux.ai/lcsc/esp32-c3-mini-1-n4~1vnr.md)
  - ATGM336H: about $1.53-1.92. MAX-M10S: about $10.60 (LCSC). — [LCSC](https://www.lcsc.com/product-detail/C4153167.html)
- **Tooling costs:**
  - Simple aluminium tools for a basic electronic enclosure cost about $3,000 (CAD services blog). — [Cad Crowd](https://www.cadcrowd.com/blog/complete-costs-of-injection-molding-design-dfm-engineering-rates-manufacturing-pricing-for-cad-services/)
  - Protolabs injection moulding starts at about $1,495. — [Protolabs](https://www.protolabs.com/help-center/pricing-and-payment-options/)
  - Aluminium prototype tooling runs about £5k per part (forum). — [SFF forum](https://smallformfactor.net/forum/threads/lazer3d-lz7-quiet-gaming-cube-pc-case.596/post-29503)
  - No JLCPCB-specific mould price was found.
- The FAA's 2020 estimate of $50 per module is outdated. Retail prices of comparable DoC'd modules run $49-299. — [AMA report](https://www.modelaircraft.org/system/files/documents/AMA_RID_Module_Status_Report.pdf)

### Inferences — line-item BOM (all [EST] unless cited above)

Two columns per volume: **A = ESP32-C3 + ATGM336H**, **B = nRF52840 + MAX-M10S**.

| Line | A @1k | A @10k | B @1k | B @10k | Notes |
|---|---|---|---|---|---|
| Radio module | $1.5-2.0 | $1.2-1.5 | $4-7 | $3-5 | B uses a pre-certified nRF52840 module (BMD-345, Minew, Raytac, Fanstel); nRF52840 module pricing was not verified in this research |
| GNSS module | $1.6-1.9 | $1.4-1.6 | $10.6 | $8-9 | Cited LCSC single-qty prices |
| GNSS antenna (patch or chip) | $0.5-1.2 | $0.4-0.8 | same | same | |
| Barometer (optional) | $0.8-1.5 | $0.6-1.0 | same | same | |
| LiPo 150-250 mAh + protection | $1.0-1.8 | $0.7-1.2 | same | same | Needs UN38.3 docs for shipping |
| Charger + LDO/buck + USB-C + passives | $0.5-0.9 | $0.4-0.6 | same | same | |
| Buzzer + LED | $0.2-0.4 | $0.15-0.3 | same | same | |
| PCB (0.8 mm 4-layer) + SMT assembly | $1.5-3.0 | $0.8-1.5 | same | same | JLCPCB; panelised |
| Enclosure (2-part moulded) | $0.3-0.6 | $0.15-0.3 | same | same | Mould amortised separately |
| Packaging, label, manual, velcro/strap | $0.5-1.0 | $0.3-0.6 | same | same | |
| Programming, provisioning, test labour | $0.3-0.8 | $0.2-0.4 | same | same | |
| **Unit total** | **~$9-14** | **~$6-9** | **~$20-27** | **~$15-20** | |

**NRE [EST]:**
- **Enclosure tooling:**
  - $3-8k for a two-part aluminium/P20 mould.
  - About $10-15k for a steel multi-cavity tool at 10k+.
  - [cited ranges above]
- **FCC testing:**
  - With a pre-certified radio module, a Part 15B unintentional radiator test plus SDoC/modular integration is about $3-8k.
  - A new Part 15C certification with a discrete radio or LoRa runs about $10-20k.
- **FAA RID compliance:** testing to ASTM F3586 and the DoC submission (BlueMark says independent audit is good practice).
- **End-of-line test fixture:** pogo-pin bed, GNSS re-radiator or simulator, BLE sniffer, plus about $1-3k for scripts.
- **Certification units:** 5-20.

**Manufacturing and provisioning [EST]:**
- Flash firmware and burn the serial number into eFuse or OTP at EOL test. ArduRemoteID LOCK_LEVEL 2 burns eFuses.
- Use ANSI/CTA-2063-A serial format with an FAA-assigned manufacturer code.
- Print the serial number and FCC ID label.
- Verify BLE advertising output (RSSI above threshold) and GNSS fix (or NMEA from a re-radiator), test buzzer current, and charge-test the battery.
- Log the serial number, firmware hash and test results to a database for the DoC record.

### Gaps
- No verified nRF52840 module prices, LiPo prices, JLCPCB injection-moulding quotes or FCC/FAA test-lab quotes. All of these need a real quote.
- ASTM F3586-22 test-lab costs were not found.
