# Regulatory path to legally sell a broadcast Remote ID (RID) module (US, plus EU/UK/Japan), as of October 2026

Research date: 2026-10-11. Primary sources: 14 CFR Part 89 (via Cornell LII mirror of eCFR, since eCFR blocked automated access), FAA AC 89-2, Federal Register notices, the FAA DoC portal's public API (uasdoc.faa.gov), and FCC public notices DA 25-1086, DA 26-314, DA 26-758 and DA 26-875. Trade press and vendor pages are labeled as such.

---

## 1. 14 CFR Part 89: Standard RID vs Broadcast Module, and the performance requirements for modules

### Takeaway
A broadcast module (§89.315/§89.320) is a bolt-on transmitter for aircraft that do not have Standard RID. It broadcasts the module's own serial number, the aircraft's position, altitude and velocity, the **take-off location** (not the live operator location) and a UTC time mark, at ≥1 Hz with ≤1.0 s latency. Position must be accurate to 100 ft (95%) and altitude to 150 ft (95%). It must self-test, be tamper resistant, use error correction, and use a non-proprietary Part 15 broadcast. Unlike Standard RID it has no takeoff interlock, no control-station position and no emergency-status element. Use is limited to visual line of sight.

### Cited Findings
- **Broadcast module message elements (§89.315):** (a) the aircraft's identity, which is "the serial number assigned to the remote identification broadcast module by the person responsible for the production" of the module; (b) aircraft lat/long; (c) aircraft geometric altitude; (d) aircraft velocity; (e) lat/long of the **take-off location**; (f) geometric altitude of the take-off location; (g) a UTC time mark of the position source output. — [14 CFR 89.315 (LII)](https://www.law.cornell.edu/cfr/text/14/89.315)
- **Standard RID message elements (§89.305), for contrast:** serial number **or session ID**, **control station** lat/long and geometric altitude, aircraft lat/long, altitude and velocity, a UTC time mark, and **emergency status**. — [14 CFR 89.305 (LII)](https://www.law.cornell.edu/cfr/text/14/89.305)
- **Broadcast module performance (§89.320):**
  - (a) Must be capable of determining the take-off location.
  - (b) The time mark must be synchronized with all other message elements.
  - (c) Self-test: "Prior to take-off… must automatically test the remote identification functionality and notify the person manipulating the flight controls" of the result, and must continuously monitor from takeoff to shutdown and notify of malfunction or failure.
  - (d) "Designed and produced in a way that reduces the ability of a person to tamper with the remote identification functionality."
  - (e) Error correction in the broadcast.
  - (f) Must not interfere with, or be interfered with by, other equipment on "compatible unmanned aircraft."
  - (g) Must broadcast using "a non-proprietary broadcast specification" on spectrum compatible with personal wireless devices under 47 CFR Part 15, and be "designed to maximize the range at which the broadcast can be received."
  - (h) Aircraft position within 100 ft (95% probability); aircraft geometric altitude within 150 ft (95%); take-off position within 100 ft (95%); take-off altitude within 150 ft (95%); lat/long/altitude broadcast "no later than 1.0 seconds from the time of measurement to the time of broadcast"; "at a rate of at least 1 message per second."
  - [14 CFR 89.320 (LII)](https://www.law.cornell.edu/cfr/text/14/89.320)
- **Standard RID (§89.310) adds requirements that modules do not have:**
  - The aircraft "must not be able to take off if the remote identification equipment is not functional" (§89.310(c)(2)), plus a separate take-off limitation (§89.310(i)).
  - The control station location must correspond to the pilot's location.
  - The control station altitude must be accurate to 15 ft (95%).
  - The broadcasting device must be integrated "without modification to its authorized radio frequency parameters."
  - [14 CFR 89.310 (LII)](https://www.law.cornell.edu/cfr/text/14/89.310)
- **Cybersecurity:** Part 89 has no explicit "cybersecurity" clause. The relevant hooks are the tamper-resistance requirement and the FAA's additions to the ASTM means of compliance (see section 2). — [14 CFR 89.320](https://www.law.cornell.edu/cfr/text/14/89.320); [FAA NOA, 87 FR 49520](https://www.govinfo.gov/content/pkg/FR-2022-08-11/html/2022-16997.htm)
- **Operating rules for modules (§89.115(a)):**
  - The module must meet §89.320, and its serial number must be listed on an FAA-accepted DoC.
  - The module's serial number must be on the aircraft's Certificate of Registration (or given in a notice of identification).
  - The module must broadcast the §89.315 elements "directly from the unmanned aircraft" from takeoff to shutdown.
  - The pilot "must be able to see the unmanned aircraft at all times," must check before takeoff that the module is functioning, and must land as soon as practicable if the broadcast is lost.
  - [14 CFR 89.115 (LII)](https://www.law.cornell.edu/cfr/text/14/89.115)
- **FRIA alternative (§89.115(b)):** No RID equipment is needed if the aircraft and pilot stay within an FAA-recognized identification area and the aircraft stays within visual line of sight. — [14 CFR 89.115 (LII)](https://www.law.cornell.edu/cfr/text/14/89.115)
- **Production-rule exclusions (§89.501(c)):** Unless designed as Standard RID, Subpart F does not apply to home-built aircraft, US government aircraft, aircraft weighing ≤0.55 lb (250 g) at takeoff, or aircraft built exclusively for research or compliance demonstration. — [14 CFR 89.501 (LII)](https://www.law.cornell.edu/cfr/text/14/89.501)
- **Module production rule (§89.520):** "After April 21, 2021, no person may produce remote identification broadcast modules unless" the module is designed and produced to §89.320 "in accordance with an FAA-accepted means of compliance," together with the inspection, audit, product-support and instructions obligations covered in section 3. — [14 CFR 89.520 (LII)](https://www.law.cornell.edu/cfr/text/14/89.520)

### Inferences
- The module needs its own GNSS receiver to meet the 100 ft and 150 ft accuracy targets and to record take-off position at power-up or arming. An R111S-style standalone design with on-board GPS, battery, an LED or buzzer and a phone app for "notify the person manipulating the flight controls" fits this rule.
- The self-test notification requirement is the hardest part for a module with no link to the flight controller or ground station. Existing standalone modules typically use LEDs, beepers or a phone app; whether each approach satisfies the "notify" requirement is decided by the MoC test procedures in F3586.
- No takeoff interlock is needed, which makes standalone modules mechanically simple. The trade-off is that the operator rules (VLOS only, module serial number registered) limit the market to hobbyists, retrofits, FPV and kit or home-built aircraft.

### Gaps
- eCFR itself could not be fetched (bot block). The section text came from the Cornell LII mirror, and I found no amendments to these sections since 2021. The final rule is at [86 FR 4390](https://www.federalregister.gov/documents/2021/01/15/2020-28948/remote-identification-of-unmanned-aircraft).

---

## 2. Means of Compliance (ASTM F3586-22 / F3411-22a): what they require, reuse by new manufacturers, and cost

### Takeaway
The only FAA-accepted RID means of compliance is **ASTM F3586-22 with FAA additions and corrections, tracking number RID-ASTM-F3586-22-NOA-23-01**. Any producer may cite it on a DoC without its own MoC submission. F3586-22 overlays ASTM F3411-22a, which specifies the broadcast formats (Bluetooth 4 legacy advertising, Bluetooth 5 Long Range, Wi-Fi Beacon/NAN), and defines the test methods. The standards cost money: F3586-22 is $80 from ASTM, and F3411-22a must be bought separately.

### Cited Findings
- The FAA DoC portal's public MoC list (queried 2026-10-11) shows exactly **two RID MoCs** ever. "ASTM-F3586-22 with additions," RID-ASTM-F3586-22-NOA-22-01, has status **rescinded**: created 2022-08-11, updated 2023-11-14. "ASTM-F3586-22 with corrections," **RID-ASTM-F3586-22-NOA-23-01**, has status **accepted** from 2023-11-14. The other 8 MoCs on the list are for Operations Over People. — [FAA uasdoc public MoC API](https://uasdoc.faa.gov/api/v1/complianceMeans/public?itemsPerPage=200&pageIndex=0); UI at [uasdoc.faa.gov/listMOC](https://uasdoc.faa.gov/listMOC)
- **Aug 2022 NOA:** The FAA accepted F3586-22 "with additions" because "Section 7.5.2 of ASTM F3586-22, requiring specific items to be masked from user input, does not adequately ensure compliance with the tamper resistance requirement." The additions are:
  1. The system "shall protect the part 89-required broadcasted message from being altered or disabled by any person."
  2. It shall incorporate techniques that "reduce the ability of any person to physically and functionally modify or disable any aspect or component."
  3. The applicant must assess whether masking alone is adequate and, if not, add further tamper-resistance measures.
  - [87 FR 49520 (Aug 11, 2022)](https://www.govinfo.gov/content/pkg/FR-2022-08-11/html/2022-16997.htm)
- **Nov 2023 correction (effective Nov 14, 2023):**
  - Fixes Table 3 so that the §89.320(h)(5) latency test method is section 8.6, not 8.9.3.
  - Renames section 8.6 "Broadcast Protocol, Message Elements, Periodicity and Latency Testing."
  - Adds that "using a time-accurate test setup, the difference in time between the broadcasted timestamp and received packet time must be measured to be less than or equal to 1 second."
  - DoCs already accepted under NOA-22-01 remain valid. "The FAA will no longer accept new or revised DOC submissions using the original MOC"; new and revised DoCs must cite RID-ASTM-F3586-22-NOA-23-01.
  - [88 FR 77895 (Nov 14, 2023)](https://www.govinfo.gov/content/pkg/FR-2023-11-14/html/2023-23058.htm)
- **"Any person" may submit an MoC (§89.405).** An MoC must include "testing and validation procedures… to demonstrate through analysis, ground test, or flight test, as appropriate." — [14 CFR 89.405 (LII)](https://www.law.cornell.edu/cfr/text/14/89.405)
- **Multiple MoCs:** AC 89-2 says producers enter the tracking number of the FAA-accepted MoC they used on the DoC form, and "may use multiple FAA-accepted MOCs." — [FAA AC 89-2, §5.12](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_89-2.pdf)
- **ASTM F3586-22** is "Standard Active," last updated Jul 26, 2022, priced at **$80.00**. It covers Standard RID UAS and broadcast modules (FRIAs are out of scope), references **ASTM F3411-22a** "Standard Specification for Remote ID and Tracking," and "provides additional details on minimal testing requirements for those submitting a DOC based on this MOC." Section 8 is "Test Methods." The ASTM store page lists no newer revision (no F3586-2x). — [ASTM store F3586-22](https://store.astm.org/f3586-22.html)
- **F3411** is also sold separately (F3411-22 on the ANSI webstore; F3411-22a cataloged). — [ANSI webstore F3411-22](https://webstore.ansi.org/standards/astm/ASTMF341122); [iTeh F3411-22a](https://standards.iteh.ai/catalog/standards/astm/1459a5be-dbaf-4f87-b1d0-8a3644ddf234/astm-f3411-22a)
- **Training:** ASTM offers an F3586 eLearning course covering "key information on minimum testing requirements." — [ASTM newsroom](https://newsroom.astm.org/newsroom-articles/astm-announces-compliance-training-remote-id-unmanned-aircraft)
- **Open-source reference implementation:** The Open Drone ID core C library implements ASTM F3411 / ASD-STAN EN 4709-002 message encoding. — [opendroneid-core-c (GitHub)](https://github.com/opendroneid/opendroneid-core-c)
- **Development tools (vendor guidance):** Dronetag suggests the nRF Sniffer and the DroneScanner app, and warns that iOS devices lack Bluetooth 5 Long Range (Coded PHY) support. — [Dronetag help: USA manufacturer](https://help.dronetag.com/dronetag-dri/integration/usa-manufacturer/)

### Inferences
- A new manufacturer does **not** need its own MoC. It cites RID-ASTM-F3586-22-NOA-23-01, runs the F3586 section 8 tests (analysis, ground or flight test) on its design, and keeps the evidence on file.
- Minimum standards outlay is about **$80 for F3586-22 plus the price of F3411-22a**. I could not get the F3411-22a price; ASTM standards of that length typically cost around $100. That is my estimate, so verify it.
- The FAA's tamper-resistance additions effectively require locked firmware: no user-editable serial number, signed or locked updates, and no user-disable switch. Firmware and BOM design should treat this as a requirement.

### Gaps
- The exact text of the F3586-22 test procedures (section 8) and the F3411-22a price; both are paywalled.
- Whether ASTM has a revised F3586 or F3411 (for example F3411-24/25) in ballot. None was visible on the store page, and the FAA has not accepted any newer RID MoC.

---

## 3. FAA Declaration of Compliance process: submission, documents, review time, rescissions, audits, records, labeling, serial numbers

### Takeaway
- **Filing:** The DoC is a self-declaration filed online in the FAA "UAS Declaration of Compliance" portal (uasdoc.faa.gov, logged in through FAA DroneZone/MyAccess). It lists the producer, make/model, serial numbers or range, the FCC ID, the MoC tracking number, and a set of attestations (FAA inspection, independent audits, a 15-day defect notification, and installation instructions). Test data is not required at filing but must be retained and produced on request.
- **The accepted list:** 89 broadcast-module DoCs from about 37 makes are on the public list today, out of 478 accepted RID DoCs. The portal has a full rejection/rescission workflow. One notable rescission (DJI Mavic Pro Platinum, 2023) shows the FAA will act publicly.
- **Serial numbers:** ANSI/CTA-2063-A format, using a 4-character manufacturer code obtained from ICAO.

### Cited Findings
**DoC content (§89.530(c), for broadcast modules)**
- Producer name, physical address, phone and email.
- Module make and model.
- Serial number or range.
- "The FCC Identifier of the 47 CFR part 15-compliant radio frequency equipment used and integrated."
- The MoC used.
- Initial vs amended (with the reason).
- Declarations that the producer can demonstrate compliance with §89.320 via an accepted MoC and complies with §89.520(b).
- A statement that Part 15 equipment is integrated "without modification to its authorized radio frequency parameters" and that installation instructions are provided.
- [14 CFR 89.530 (LII)](https://www.law.cornell.edu/cfr/text/14/89.530)

**AC 89-2 details**
- "One DOC contains a single producer, make, and model."
- Serial numbers can be listed as a batch (first and last), with "an explanation of the process by which individual serial numbers are assigned."
- Amended DoCs are used to add serial numbers, fix errors, update contacts, or resolve a safety issue.
- The FAA assigns a tracking number on acceptance.
- DoCs "should be submitted electronically through the FAA website," and "all FAA-accepted DOCs will be listed on the FAA's website."
- [FAA AC 89-2 (Dec 22, 2020), §§5.8–6.2](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_89-2.pdf)
- The FAA estimates the public reporting burden at about 5 minutes per response (paperwork burden statement). — [AC 89-2](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_89-2.pdf)

**Test data**
- "Test data substantiating compliance is not required for the DOC submission, however this data should be readily available because the FAA can request the data at any time." — [UAS Remote Identification FAQs (CDA-hosted copy of FAQ, 3/17/2024)](https://assets-002.noviams.com/novi-file-uploads/cda/UAS_Remote_Identification_FAQs__3_17_2024_-1669be50.pdf)
- §89.535 says the FAA "will evaluate a declaration of compliance… and may request additional information or documentation." — [14 CFR 89.535 (LII)](https://www.law.cornell.edu/cfr/text/14/89.535)

**The portal**
- The portal front end (uasdoc.faa.gov, app version 2.8.4) shows these DoC statuses: draft, pending, pending_amendment, accepted, **rejected**, **withdrawn**, **rescinded**, "accepted_rescision_proposed," and "accepted_marked_for_rescision."
- It supports document attachments on a DoC, CSV upload of up to 100,000 serial numbers per DoC (10,000 via text box), and an amendment flow.
- It links to ICAO's manufacturer-code page for "obtain MFR code" and to faadronezone-access.faa.gov for login.
- [uasdoc.faa.gov app bundle](https://uasdoc.faa.gov/static/js/main.84270040.js) (JS bundle inspected 2026-10-11; primary but technical)

**Public accepted list (queried 2026-10-11)**
- 507 public DoCs: 478 RID accepted (389 "Unmanned Aircraft" and 89 "Broadcast Module"), plus 29 Operations Over People.
- The RID tracking-number counter stands at about 2,733, and the highest public RID tracking number is RID000002731. — [FAA publicDOCRev API](https://uasdoc.faa.gov/api/v1/publicDOCRev?itemsPerPage=5000&pageIndex=0); [MoC API (counter field)](https://uasdoc.faa.gov/api/v1/complianceMeans/public?itemsPerPage=200&pageIndex=0)
- Broadcast-module DoC holders include BlueMark (db100 to db154), Dronetag (Mini, Beacon, DRI, BS, Beacon gen.2), Holy Stone (HSRID01/02/03), Ruko (R111 x4, R111S), Zing (Z-RID, Z-RID Lite, Lite V2), Spektrum SkyID, uAvionix pingRID, Aerobits idME/idME+, Potensic, SJRC, Holyton, Bwine, Veeniix, Gleesfun, FrSky, Lumenier, SwellPro, Freefly, NewBeeDrone, Pierce Aerospace, DIY-D LLC (ESP32-C3-MINI-1 based) and others.
- The most recent module DoCs are Aero Systems West (2026-04-14) and Aurelia X8 PRO (2026-08-20). — [FAA publicDOCRev API](https://uasdoc.faa.gov/api/v1/publicDOCRev?itemsPerPage=5000&pageIndex=0)
- The **Ruko R111S** DoC is RID000001939, dated 2024-08-19, with one serial range "186975000001-186976000000" (1,000,000 serials). — [FAA serialNumbers API for RID000001939](https://uasdoc.faa.gov/api/v1/serialNumbers?findBy=docTrackingNumber&docTrackingNumber=RID000001939&formatForDocView=true&limit=3)

**Rescission**
- §89.540 makes a DoC "subject to ongoing review." The FAA may rescind if the product does not meet §89.320, the DoC is deficient, or the MoC is rescinded.
- The FAA may first give "a reasonable period of time… to remediate." Notice of rescission is published in the Federal Register.
- The holder or adversely affected persons may petition for reconsideration within 60 days.
- [14 CFR 89.540 (LII)](https://www.law.cornell.edu/cfr/text/14/89.540)
- AC 89-2 §7: on notice of non-compliance the producer "must arrange for an independent audit" and submit the report, and propose corrective action. If no audit or proposal arrives, the FAA "may rescind." Units may keep operating during the notice period unless the FAA orders immediate rescission. — [AC 89-2 §7](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_89-2.pdf)

**Notable rescission**
- The FAA rescinded DoC RID000000111 (DJI Mavic Pro Platinum, accepted Jan 19, 2023) effective immediately via a July 12, 2023 Federal Register notice.
- DJI had told the FAA in Feb 2023 that the products "were, in fact, not compliant." The employee listed on the application no longer had RID certification responsibilities and said they did not submit it.
- [88 FR 44437 (Jul 12, 2023)](https://www.federalregister.gov/documents/2023/07/12/2023-14802/notice-of-rescission-of-unmanned-aircraft-systems-remote-identification-declaration-of-compliance); [DroneXL coverage](https://dronexl.co/2023/07/13/faa-rescinds-remote-id-dji-mavic-pro-platinum/)
- The MoC itself (NOA-22-01) shows "rescinded" in the portal after being superseded in Nov 2023. Existing DoCs under it stayed valid. — [FAA MoC API](https://uasdoc.faa.gov/api/v1/complianceMeans/public?itemsPerPage=200&pageIndex=0); [88 FR 77895](https://www.govinfo.gov/content/pkg/FR-2023-11-14/html/2023-23058.htm)

**Ongoing obligations (§89.520(b))**
- (1) Allow FAA inspection of facilities, technical data and modules, and witnessed tests.
- (2) "Cause independent audits to be performed on a recurring basis," and also whenever the FAA notifies of non-compliance, and provide the results on request.
- (3) Product support and notification procedures to tell the public and the FAA of any defect "within 15 calendar days."
- (4) Make installation and operating instructions available.
- [14 CFR 89.520 (LII)](https://www.law.cornell.edu/cfr/text/14/89.520)
- AC 89-2 says the FAA "does not require product support and notification procedures to take a specific form"; a website and customer email can suffice. — [AC 89-2 §5.16](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_89-2.pdf)

**Records (§89.545)**
- Keep the MoC, all documentation and substantiating data, "records of all test results," and other compliance information for as long as the module is produced **plus 24 calendar months**, available for FAA inspection. — [14 CFR 89.545 (LII)](https://www.law.cornell.edu/cfr/text/14/89.545)

**Labeling (§89.525(b))**
- The module must display "a label indicating that the equipment meets the requirements of this part… in English and be legible, prominent, and permanently affixed to the broadcast module." — [14 CFR 89.525 (LII)](https://www.law.cornell.edu/cfr/text/14/89.525)

**Serial numbers (§89.505)**
- The serial must comply with ANSI/CTA-2063-A (Sept 2019), which is incorporated by reference and available from CTA. — [14 CFR 89.505 (LII)](https://www.law.cornell.edu/cfr/text/14/89.505)
- Under CTA-2063-A, the manufacturer code is 4 characters (digits and uppercase letters, excluding O and I). "ICAO is responsible for assigning a unique MFR Code to UAS manufacturers," and the code is obtained via ICAO's Doc 8643 Manufacturers-Codes page. — [CTA-2063-A text (Scribd copy)](https://www.scribd.com/document/649066881/Cta-2063-a-Final); the portal also links to [ICAO Doc 8643 Manufacturer Codes](https://www.icao.int/publications/DOC8643/Pages/Manufacturers-Codes.aspx)
- The code goes to the company producing the UAS or module, not to the radio-chip vendor. — [CubePilot forum](https://discuss.cubepilot.org/t/cubepilots-manufacturer-code/12101) (forum, low authority)
- Vendor guidance gives the format as "ICAO Manufacturer Code + Unique Device Serial" (e.g., `1596ABC1234567890`) and recommends hard-coding the serial in firmware to resist tampering. — [Dronetag help](https://help.dronetag.com/dronetag-dri/integration/usa-manufacturer/)

**Conflicting vendor claims**
- Dronetag's integration guide says "a DoC can only be filed after your MoC has been reviewed and accepted by the FAA" and that F3586 test procedures "are mandatory and carried out by accredited laboratories." — [Dronetag help](https://help.dronetag.com/dronetag-dri/integration/usa-manufacturer/)
- This is **contradicted** by the regulation and the FAA materials. The MoC has already been accepted, so producers cite it (AC 89-2 §5.12). The DoC is a self-declaration, and test data need not be submitted ([FAQ](https://assets-002.noviams.com/novi-file-uploads/cda/UAS_Remote_Identification_FAQs__3_17_2024_-1669be50.pdf); [§89.530](https://www.law.cornell.edu/cfr/text/14/89.530)). Part 89 requires *independent audits* but not accredited-lab testing.

### Inferences
- **Review time is not published.** From tracking numbers and dates, Ruko's R111 DoCs went from RID000000506 (Sept 2023) to RID000000827/828/1008, all dated 2024-01-22. That suggests either batch acceptance or multi-month queues in late 2023. This is anecdotal and uses the "updatedAt" date, not a confirmed acceptance date. Plan for **1 to 4+ months**, and budget for FAA follow-up questions.
- **Approval rate (inference).** About 2,731 RID tracking numbers have been issued but only 478 RID DoCs are public and accepted. That implies many submissions were rejected, withdrawn, superseded by amendments, or abandoned drafts. The counter may also include drafts, so this is not a rejection rate, but it does mean an incomplete or inconsistent filing will likely bounce.
- **Serial range (inference).** The R111S range 186975000001–186976000000 parses as MFR code "1869," length code "7" and a 7-digit serial, which suggests Ruko's ICAO code is 1869. A startup can likewise reserve one large range in a single DoC and amend later.
- **Audits.** "Recurring independent audits" are required but undefined in frequency and form. A small startup should budget for a periodic third-party audit (consultant or test lab) of production conformity, plus an internal QA test log (for example a GNSS fix, broadcast check and serial-number check per unit).

### Gaps
- No official FAA DoC review-time statistics were found.
- The ICAO manufacturer-code fee and timeline were not found. I believe it is free and done by email request, but I could not confirm it, so verify directly with ICAO.
- The CTA-2063-A standard itself appears to be free from CTA, but this is unconfirmed.
- I found no Federal Register rescission notice for a *broadcast module* DoC specifically. Rescinded DoCs do not appear in the public API list, so the number of module rescissions is unknown.

---

## 4. Third-party testing vs self-declaration; test labs and cost

### Takeaway
US RID compliance is **self-declared**. No FAA-designated or accredited RID test lab is required, and the producer runs the F3586 tests itself (an outside lab is optional). Part 89 does require recurring **independent audits**. Third-party testing is mandatory only on the FCC side, for radio certification. I found no published price list for RID-specific F3586 testing services.

### Cited Findings
- §89.530 frames the DoC as the producer's declaration that it "can demonstrate" compliance using an accepted MoC. §89.520(b)(2) requires producers to "cause independent audits to be performed on a recurring basis." — [14 CFR 89.530](https://www.law.cornell.edu/cfr/text/14/89.530); [14 CFR 89.520](https://www.law.cornell.edu/cfr/text/14/89.520)
- AC 89-2 §5.15: the producer "is responsible for coordinating and performing independent audits to inspect the facilities, technical data, and any… broadcast module… manufactured and listed under a DOC," with results given to the FAA on request. — [AC 89-2](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_89-2.pdf)
- Vendors such as Dronetag offer a ready-made "ASTM F3411-22a Compliance Matrix" and certification help to OEMs integrating their modules. Its guidance asserts that testing is by accredited labs (contradicted above). — [Dronetag help](https://help.dronetag.com/dronetag-dri/integration/usa-manufacturer/)

### Inferences
- The realistic path for a startup is in-house F3586 testing: GNSS accuracy logging against a surveyed reference, a time-accurate sniffer setup for the ≤1 s latency test, message-rate and format capture, a self-test and monitoring demonstration, and a tamper analysis. Optionally, pay an EMC/RF lab or consultant to witness or review the test report.
- Estimate (no source): in-house test rig and engineering time of $5k–$20k equivalent, or $5k–$15k for a consultant. Treat both as **unverified estimates**.

### Gaps
- No RID-specific test lab pricing was found. Labs that do F3411 testing for EU/US RID exist, but I found no public quotes.

---

## 5. FCC: Part 15 certification, pre-certified module vs full certification, cost, and the 2025–2026 Covered List

### Takeaway
- **FCC ID requirement:** A broadcast module is a Part 15 intentional radiator (BLE and/or Wi-Fi), and the DoC must list an FCC ID.
- **Before Dec 2025:** Startups typically used a pre-certified radio module, either cited under its modular grant ("Contains FCC ID") or with a new FCC ID for the finished device, plus Part 15B for the host. Cost ran from a few thousand to about $10–20k.
- **Covered List, Dec 22, 2025:** The FCC added **all foreign-produced UAS and "UAS critical components"** (explicitly including "data transmission devices" and "communications systems") to the Covered List. Covered equipment **cannot receive new FCC equipment authorizations**.
- **Exemptions as of Oct 2026:**
  - Blue UAS Cleared List items, until **Jan 1, 2028**.
  - "Domestic end products" under the Buy American Standard (US-manufactured, more than 65% domestic component cost), until **Jan 1, 2028**.
  - Items with a DoW/DHS Conditional Approval.
  - "Toy Drones."
- **Previously authorized** devices can still be sold. The FCC has never said whether a standalone RID module counts as a "UAS critical component," which leaves a new foreign-made RID module legally exposed.

### Cited Findings
- **FCC Public Notice DA 25-1086 (Dec 22, 2025):** adds "Uncrewed aircraft systems (UAS) and UAS critical components produced in a foreign country and all communications and video surveillance equipment and services listed in Section 1709(a)(1) of the FY25 NDAA" to the Covered List.
  - Definitions: "UAS critical components" "includes but is not limited to the following UAS components and any associated software: Data transmission devices; Communications systems; Flight controllers; Ground control stations and UAS controllers; Navigation systems; Sensors and Cameras; Batteries and Battery Management Systems; Motors."
  - Under §2.903(a), "covered" equipment "is prohibited from receiving equipment authorizations," and under §2.911 applicants must certify that equipment is not covered.
  - [FCC DA 25-1086](https://docs.fcc.gov/public/attachments/DA-25-1086A1.pdf)
- **FCC DA 26-314 (Apr 1, 2026):** "foreign-produced UAS and UAS critical components may no longer receive authorization for importation, marketing, or sale in the United States, although already-authorized devices can continue to be used." It describes the DoW Conditional Approval process (guidance Jan 7, 2026) and a Mar 18, 2026 update exempting "devices which have been granted a Conditional Approval by DoW or DHS." — [FCC DA 26-314](https://docs.fcc.gov/public/attachments/DA-26-314A1.txt); [DoW Conditional Approval guidance](https://www.fcc.gov/sites/default/files/UAS-Guidance-Submissions-Conditional-Approvals.pdf)
- **FCC DA 26-875 (Aug 21, 2026):**
  - On June 15, 2026 the Covered List was updated to exempt "Toy Drones" and "Toy Drones that contain foreign-produced components."
  - On **July 21, 2026** the Blue UAS and Buy-American "domestic end product" exemptions were extended **to January 1, 2028** (previously Jan 1, 2027).
  - Conditional Approvals "will not terminate on December 31, 2026, so long as the applicant complies with its approved onshoring plan and updated vetting," and terminate if the onshoring plan is not followed or misrepresentations are found.
  - [FCC DA 26-875](https://docs.fcc.gov/public/attachments/DA-26-875A1.pdf)
- **Date conflict, resolved:** FCC DA 26-758 (released July 21, 2026) still recites "until January 1, 2027," while DA 26-875 records the same-day extension to Jan 1, 2028. Use **Jan 1, 2028**. — [DA 26-758](https://docs.fcc.gov/public/attachments/DA-26-758A1.pdf); [DA 26-875](https://docs.fcc.gov/public/attachments/DA-26-875A1.pdf)
- **"Domestic end product" test:** manufactured in the US, with domestic components exceeding 65% of total component cost (per law-firm and press summaries of 48 CFR 25.101(a)). — [Steptoe](https://www.steptoe.com/en/news-publications/global-trade-and-investment-law-blog/fcc-adds-drones-to-the-covered-list.html); [HSToday](https://www.hstoday.us/subject-matter-areas/unmanned-vehicles/fcc-revises-covered-list-rules-introducing-temporary-exemptions-for-blue-uas-and-buy-american-drones/)
- **Firmware waiver:** Previously authorized UAS can receive software and firmware updates through at least Jan 1, 2029 (per a secondary summary). — [DroneXL, Jul 22, 2026](https://dronexl.co/2026/07/22/fcc-sales-ban-foreign-drones/) (secondary; not verified in FCC text)
- **FCC DA 26-758 (Jul 21, 2026) proposal:** to prohibit continued importation and marketing of *previously authorized* foreign-produced UAS and components that are "military-grade." It "would not apply to any non-military-grade UAS or UAS critical components." Comments are due 30 days after Federal Register publication. — [FCC DA 26-758](https://docs.fcc.gov/public/attachments/DA-26-758A1.pdf)
- **RID modules and the Covered List:** DroneXL (Oct 6, 2026) notes the Dec 2025 notice "never mentions Remote ID" and does not say whether a general-purpose BLE/Wi-Fi module becomes a drone component inside a RID broadcaster.
  - It reports that Zing Drone Solutions (Z-RID Lite maker, Oregon) signed an MoU with NUCODE (Korea; Nordic-chip-based BLE/Wi-Fi modules) and is testing samples. Zing is seeking secure boot, signed firmware and BOM/origin transparency.
  - The author argues a Korean module would still need a DoW Conditional Approval.
  - [DroneXL, Oct 6, 2026](https://dronexl.co/2026/10/06/zing-nucode-korean-radio-remote-id-fcc-foreign-parts/)
- **Modular transmitters:** A Federal Register summary says the FCC prohibits equipment authorization for any modular transmitter on the Covered List from Dec 26, 2025 (EA Security rules). — [PolicyRisk summary of FR 2025-21001](https://policyrisk.com/federal-register/2025-21001) (secondary)
- **Pre-certified module reuse:** Dronetag's DRI uses a u-blox ANNA-B4 (FCC ID XPYANNAB4). Host products can use "Contains FCC ID" labeling if the module is used per its grant and the antenna type and gain match the approved configuration. — [Dronetag help](https://help.dronetag.com/dronetag-dri/integration/usa-manufacturer/)
- **Modular grant types matter:** A Limited Modular Approval needs host review, while Single Modular grants allow OEM integration. — [fccid.io example](https://fccid.io/2ACP4BT); [Espressif ESP32-C61 FCC grant](https://documentation.espressif.com/ESP32-C61-WROOM-1%20FCC.pdf)
- **Cost estimates (vendor sources, ballpark):**
  - Bluetooth-type unlicensed transmitter certification: $9,000–$12,000.
  - Devices using FCC-certified modules: $6,500–$10,000. — [compliancetesting.com](https://compliancetesting.com/fcc-certification-faqs/fcc-certification-cost/)
  - Custom 2.4 GHz radio, full Part 15C suite: "$10K–$20K per round." — [Hubble guide](https://hubble.com/community/guides/unlicensed-but-not-unregulated-the-certification-path-for-2-4-ghz-ble-products/)
  - Part 15B test report plus SDoC for a host with a pre-certified module: about $690 with a 9-working-day lead time (Chinese lab). — [JJR Lab](https://www.jjrlab.com/news/fcc-sdoc-certification-cost-for-smart-switches.html)

### Inferences
- **Highest-impact item in this research.** A standalone RID broadcast module is very plausibly a "data transmission device" or "communications system" UAS critical component.
  - If it is **produced abroad** (as the Ruko, Holy Stone, Potensic and SJRC modules appear to be), a *new* model probably cannot get a new FCC ID after Dec 22, 2025 without a DoW Conditional Approval.
  - Without an FCC ID the DoC cannot be completed, because §89.530(c)(4) requires one.
  - Existing authorized modules can still be sold, so incumbents are grandfathered and new foreign entrants are blocked.
- **US assembly with a pre-certified radio:**
  - A US startup assembling in the US with more than 65% domestic component cost qualifies as a "domestic end product," exempt until Jan 1, 2028; the post-2028 status is unknown.
  - Chinese radio SoCs and modules (e.g., Espressif ESP32 modules, used by DIY-D's DoC'd module) may themselves be covered "communications" components or "modular transmitters" when sold for UAS use.
  - Citing such a module's existing FCC ID ("Contains FCC ID") may avoid a new authorization, but this is an untested legal theory. **Get FCC counsel's opinion.**
  - A Nordic/u-blox (Europe-made) module is still "foreign-produced" under the literal rule.
- **Possible demand upside:** Domestic production becomes a moat. Grandfathered foreign modules can keep selling, but new foreign competitors are blocked, which may help a US-made entrant win government or enterprise buyers.
- The "Toy Drones" exemption (June 2026) does not obviously cover RID modules. The definition was not retrieved.

### Gaps
- The FCC's official "Covered List FAQs: UAS and UAS Critical Components" page returned HTTP 403 to automated fetches, so I could not confirm whether it addresses RID modules or general-purpose radio modules.
- No FCC or DoW statement on RID broadcast modules was found.
- I did not retrieve the FCC ID grants of specific RID modules (Ruko R111S, Holy Stone HSRID) to see whether they used modular or full certification.

---

## 6. 2025–2026 regulatory changes affecting demand or requirements (Part 108, EOs, enforcement, network RID)

### Takeaway
- **Part 108:** The BVLOS rule (NPRM Aug 7, 2025) would require **Standard RID** (not broadcast modules) for Part 108 operations. The final rule went to OIRA on July 10, 2026 and is **not yet published** as of Oct 2026.
- **June 2025 EOs:** EO 14305 directs the FAA to give law enforcement real-time access to RID-linked personal data. EO 14307 drives "drone dominance," and through it the FCC Covered List.
- **Enforcement:** FAA discretion ended Mar 16, 2024. FAA Enforcement Bulletin 2026-1 (Feb 2026) makes legal action the default for operating without RID (§89.105) in the qualifying categories.
- **Network RID:** No network RID mandate exists; Part 89 remains broadcast-only.

### Cited Findings
- **Part 108 NPRM (proposed):**
  - Proposed §108.200(a)(1): no person may operate a UA under Part 108 "unless the UA meets the requirements for standard remote identification."
  - Control-station location broadcast is not required when operating without a flight coordinator.
  - Adds an operational-status message showing whether the UA is BVLOS, and broadcast range "optimized" for other aircraft.
  - [Federal Register, Part 108 NPRM (Aug 7, 2025)](https://www.federalregister.gov/documents/2025/08/07/2025-14992/normalizing-unmanned-aircraft-systems-beyond-visual-line-of-sight-operations); [FAA NPRM PDF](https://www.faa.gov/newsroom/BVLOS_NPRM_website_version.pdf)
- **Part 108 status:** final rule at OIRA since July 10, 2026, and "NOT published, NOT in effect" as of Sept 18, 2026. The FAA hopes to publish by the end of calendar 2026. — [USI Part 108 guide](https://www.flyusi.org/guides/get-108-ready) (secondary)
- **EO 14305 "Restoring American Airspace Sovereignty" (June 6, 2025):**
  - "Within 60 days… the Administrator of the FAA shall provide… automated real-time access to personal identifying information associated with UAS remote identification signals to appropriate executive departments and agencies and SLTT agencies for the purposes of enforcing applicable Federal or State law."
  - It also directs DOJ toward "full enforcement" when operators endanger the public, violate airspace restrictions, or commit other crimes, and makes SLTT grants available for detection, tracking and identification equipment.
  - [EO 14305 text (govinfo)](https://www.govinfo.gov/content/pkg/DCPD-202500668/html/DCPD-202500668.htm)
- **EO 14307 "Unleashing American Drone Dominance" (June 6, 2025)** underpins the FCC's domestic-supply-chain actions. — [FCC DA 26-314](https://docs.fcc.gov/public/attachments/DA-26-314A1.txt)
- **Enforcement discretion:** the FAA's policy (effective Sept 15, 2023) cited "unanticipated issues with the available supply and excessive cost of remote identification broadcast modules." It ended **March 16, 2024**, with no further extension. — [88 FR, Sept 15, 2023](https://www.govinfo.gov/content/pkg/FR-2023-09-15/html/2023-20074.htm); [AMA blog](https://amablog.modelaircraft.org/amagov/?p=6983)
- **FAA Compliance & Enforcement Bulletin No. 2026-1 (Feb 2026):**
  - Qualifying cases go to the Chief Counsel for legal action by default.
  - The listed triggers include "operating without Remote ID in violation of 14 CFR § 89.105."
  - Reported civil penalties ranged from $1,771 to $36,770 across 18 operations (2023–2025 violations), and eight remote-pilot certificate actions were taken in 2025.
  - [Autonomy Global, Feb 10, 2026](https://www.autonomyglobal.co/hammer-and-nails-the-faas-uas-enforcement-order-just-made-legal-action-the-default/) (secondary; the bulletin itself was not retrieved)
- **FCC drone-dominance proceeding (GN Docket 26-74):** the FCC sought comment (Apr 2026) on reducing device-certification friction for domestic drone makers. — [FCC DA 26-314](https://docs.fcc.gov/public/attachments/DA-26-314A1.txt)

### Inferences
- **Part 108:** If finalized as proposed, BVLOS (commercial and enterprise) operations need Standard RID, so broadcast modules are **not** a Part 108 product. Demand for modules stays concentrated in Part 107 VLOS and recreational retrofit, FPV, kit and home-built aircraft.
- **Enforcement:** The 2026 shift to default legal action, plus law-enforcement access to RID data under EO 14305, raises the cost of flying non-compliant. That supports continued retrofit demand among FPV and legacy-aircraft owners.
- **Supply side:** The Covered List (section 5) freezes the module supply to grandfathered models and makes it harder for new foreign entrants.

### Gaps
- FAA Bulletin 2026-1 itself was not retrieved.
- I found no Remote ID-specific FAA enforcement statistics.
- I found no evidence of an FAA proposal to amend Part 89, for example to add network RID or change the module rules, in 2025–2026.

---

## 7. Who can use broadcast modules: the demand drivers

### Takeaway
Modules are the compliance route for any aircraft above 250 g (or any Part 107 aircraft) that lacks Standard RID: legacy drones, FPV and home-built aircraft, kits and RC planes. Use is limited to visual line of sight, and the module's serial number must be registered to the aircraft. The alternative is flying at an FRIA, which is VLOS only and within the area's boundaries.

### Cited Findings
- §89.115(a): modules are for "an unmanned aircraft that is not a standard remote identification unmanned aircraft." The pilot "must be able to see the unmanned aircraft at all times," and the module's serial number must be on the registration certificate. §89.115(b) is the FRIA option. — [14 CFR 89.115](https://www.law.cornell.edu/cfr/text/14/89.115)
- Home-built aircraft and aircraft of 250 g or less are excluded from the *production* rule, so their operators turn to modules. — [14 CFR 89.501](https://www.law.cornell.edu/cfr/text/14/89.501)
- Modules can be moved from aircraft to aircraft. Recreational operators do not need one per aircraft. — [AMA blog](https://amablog.modelaircraft.org/amagov/?p=6983)
- Only modules listed on an FAA DoC count for compliance. — [NBAA (via search summary)](https://nbaa.org/?p=87105)

### Inferences
- Each new airframe sold by Standard-RID makers shrinks the legacy pool. FPV, home-built and RC fixed-wing aircraft are a persistent market because they never get built-in RID.
- A module that is light (under about 15 g), cheap and long-running on battery (like the R111S at 13.5 g) targets FPV.

### Gaps
- No official count of module-equipped registrations was found. The FAA's registration data was not researched here.

---

## 8. EU, UK and Japan, and whether one design can serve multiple markets

### Takeaway
- **EU and UK:** They use a "direct remote identification add-on" (Part 6 of Delegated Reg. 2019/945, in EU and UK-retained versions). The add-on must also transmit the **operator registration number**, which the user uploads and the device validates, plus the pilot's position (or take-off point) and course and speed. Compliance is shown against ASD-STAN **EN 4709-002**. Conformity is by manufacturer declaration plus a CE mark (Module A internal production control is in the Annex), together with RED (radio) and, since Aug 1, 2025, RED cybersecurity (EN 18031).
- **UK:** RID is mandatory for UK1–UK3/UK5/UK6 from Jan 1, 2026. Legacy, privately built and UK0 aircraft (100 g or more with a camera) follow from **Jan 1, 2028**.
- **Japan:** RID has been mandatory for aircraft of 100 g or more since June 20, 2022, using ASTM F3411-style BLE/Wi-Fi with Japan's registration ID, plus MIC radio approval ("giteki").
- **Common design:** One hardware design (BLE 4/5 Long Range plus Wi-Fi Beacon/NAN, with GNSS) can serve all markets with region-specific firmware and certifications. Dronetag, Aerobits and Zing all claim multi-market approvals.

### Cited Findings
- **UK/EU Part 6 add-on requirements:**
  - Allow upload of the operator registration number (per Art. 14 of 2019/947), with a consistency check and an error message if it fails.
  - Broadcast "in real time during the whole duration of the flight, the direct periodic broadcast… using an open and documented transmission protocol," receivable by existing mobile devices.
  - Content: operator registration number; the add-on's unique serial number; time stamp; UA position and height above surface or take-off point; route course (clockwise from true north) and ground speed; and the remote pilot's position (or take-off point if not available).
  - Reduce the ability to tamper; serial number per ANSI/CTA-2063-A-2019, affixed to the add-on and its packaging or included in the instructions; instructions giving the transmission protocol reference and the install and upload steps.
  - [UK CAA regulatory library, 2019/945 Part 6](https://regulatorylibrary.caa.co.uk/2019-945/Content/Regs/PART%206%20-%20Requirements%20for%20a%20direct%20remote%20identification%20add-on.htm)
- **EU structure:** Part 6 sets the add-on requirements and Part 7 is "Conformity assessment Module A – Internal production control." Manufacturers must draw up technical documentation (Art. 17), carry out the Art. 13 procedure, issue an EU declaration of conformity and affix the CE marking. Add-ons must bear a type and unique serial number. — [EUR-Lex consolidated 2019/945 (as of 2025-06-24)](https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX%3A02019R0945-20250624)
- **Privately built aircraft:** Amending Reg. (EU) 2020/1058 introduced the add-on provisions and exempts privately built UAS from Chapter II product rules. — [EUR-Lex 2020/1058](https://eur-lex.europa.eu/eli/reg/2020/1058/oj)
- **EASA add-on list:** EASA publishes a list of add-on modules supplied by manufacturers, "did not verify the compliance of such components," and the declaration of conformity is "under the sole responsibility of the manufacturer." — [EASA (via search summary)](https://www.easa.europa.eu/en/document-library/easy-access-rules/online-publications/easy-access-rules-unmanned-aircraft-systems?page=16)
- **EN 4709-002:2023** "provides means of compliance with the 'Direct Remote Identification' requirements set in Regulation (EU) 2019/945." — [iTeh SIST EN 4709-002:2023](https://standards.iteh.ai/catalog/standards/sist/b3891f06-f0ea-474f-940c-ba5a4e0bef46/sist-en-4709-002-2023)
- **EU open-category scope:** Some sources say that from Jan 1, 2024 RID is needed for most open-category operations. Others point to the privately built carve-out, so this is **unresolved**. — [Dronavia](https://www.dronavia.com/2024/04/04/drone-remote-identification-european-union/); [IntoFPV forum](https://intofpv.com/archive/index.php/thread-25142.html) (low authority)
- **RED cybersecurity:** Delegated Reg. (EU) 2022/30 (RED Art. 3(3)(d), (e), (f)) has been mandatory since **Aug 1, 2025**. The harmonised standards EN 18031-1/-2/-3:2024 were cited Jan 30, 2025 (Decision 2025/138) "with certain restrictions." Self-declaration is possible via EN 18031; otherwise a notified body is needed. — [SGS](https://www.sgs.com/en-se/news/2025/06/red-cybersecurity-requirements-mandatory-on-1-august-2025)
- **UK CAA dates:**
  - UK1, UK2 and UK3: Jan 1, 2026. UK5 and UK6: Jan 1, 2026 (specific category).
  - UK0 (100 g or more with camera), UK4, legacy non-class-marked (100 g or more with camera) and privately built (100 g or more with camera): Jan 1, 2028.
  - "From 1 January 2028, you must use Remote ID for all drone and model operations (unless you have an exemption)."
  - The broadcast includes the Operator ID, serial number, position and height, route course, the remote pilot's position and emergency status.
  - [UK CAA Remote ID page](https://www.caa.co.uk/drones/moving-on-to-more-advanced-flying/remote-id-rid/)
- **UK retrofit:** "at each manufacturer's discretion — the CAA does not oversee it." — [heliguy (secondary)](https://www.heliguy.com/blogs/posts/remote-id-what-it-means-for-uk-drone-pilots/)
- **Japan:**
  - From June 20, 2022 unmanned aircraft must be registered and fitted with a Remote ID function. — [MLIT handbook 2022 (EN)](https://www1.mlit.go.jp:8088/koku/content/mlit_HB_web_en_2022.pdf)
  - The threshold is 100 g including battery (previously 200 g). RID uses BLE 5.x Long Range, Wi-Fi NAN or Wi-Fi Beacon per ASTM F3411-19, at least once per second. — [apollomaniacs guide (secondary)](https://apollomaniacs.com/ipod/howto_ar_drone_flightrule_remoteid_en.htm)
  - External module makers obtained MIC specified-radio-equipment certification. — [MONOist (Japan Drone 2022)](https://monoist.itmedia.co.jp/mn/spv/2206/29/news064.html)
  - Dronetag entered Japan in 2024. — [Dronetag news](https://preview.dronetag.cz/news/2024/06/03/dronetag-enters-japan-market-remote-id-drones/)
- **Multi-market vendors:** Zing says Z-RID Lite holds approvals in the US, Europe and Singapore. — [DroneXL](https://dronexl.co/2026/10/06/zing-nucode-korean-radio-remote-id-fcc-foreign-parts/)
- Dronetag markets DRI and Beacon as meeting both EN 4709-002 and the US broadcast rules. — [Dronetag DRI](https://www.dronetag.com/products/dri)

### Inferences
- **Firmware differences:** The core RF and message stack (Open Drone ID / F3411) is shared. The EU and UK need an operator-ID upload with checksum validation, pilot location (or take-off fallback) and a CE/UKCA declaration package (RED plus EN 18031 cybersecurity plus RoHS). The US needs a module serial number on the FAA DoC and FCC authorization. Japan needs its own registration-number handling and MIC/TELEC certification.
- **The UK 2028 date is a key market window.** Legacy and privately built aircraft of 100 g or more with a camera need RID from Jan 1, 2028, a retrofit wave comparable to the US in 2023–2024.

### Gaps
- Exact EU dates and legacy rules after the 2024 transition.
- Whether UK add-ons need UKCA plus UK class documentation, and whether CE is accepted in Great Britain for add-ons.
- Japan's exact module certification process and whether a separate MLIT listing exists for external devices.
- The EASA add-on list contents. Primary EASA pages were not fetched successfully.

---

## 9. Battery, shipping and other product compliance (UN38.3, CE, RoHS, Prop 65)

### Takeaway
A module with an internal Li-ion or LiPo cell, like the R111S, needs a **UN38.3 test summary** for the cell or battery. It ships under the lithium-ion "contained in equipment" rules (UN3481, PI 967 for air). The EU also needs CE (RED, including EN 18031, RoHS and WEEE/battery rules), and California needs Prop 65 warnings if listed chemicals are present. Sourcing cells that already have UN38.3 reports minimizes cost.

### Cited Findings
- **UN38.3 tests:** the suite is T.1–T.8, and T.6 and T.8 are not required for "small rechargeable batteries." Ten of twenty third-party Li-ion sets tested by Transport Canada failed UN38.3, while all OEM sets passed. — [Transport Canada research summary](https://tc.canada.ca/en/dangerous-goods/publications/lithium-battery-transport-research/research-summary-evaluation-analysis-substandard-lithium-ion-batteries-383-testing)
- **PI 967 (contained in equipment):** no state-of-charge requirement. — [NetApp lithium battery test summary page](https://www.netapp.com/en/company/lithium-battery-safety-data-sheet-test-summary/)
- A UN38.3 test summary remains valid only "as long as no changes, modifications or additions are made to the model(s)." — [Jauch test summary example](https://asset.conrad.com/media10/add/160267/c1/-/en/002348596TS00/test-summary-report-2348596-jauch-quartz-jpb27ahb-power-bank-spare-battery-li-ion-26800-mah-249297.pdf)
- **Test labs:** UN38.3 testing is offered by major labs such as TÜV SÜD. — [TÜV SÜD UN38.3](https://www.tuvsud.com/en-my/industries/consumer-products-and-retail/electrical-and-electronics/lithium-batteries-testing-under-undot-383)
- **Covered List battery risk:** "Batteries and Battery Management Systems" are themselves listed UAS critical components. — [FCC DA 25-1086](https://docs.fcc.gov/public/attachments/DA-25-1086A1.pdf)

### Inferences
- **Cell sourcing:** Buy a cell with an existing UN38.3 test summary and MSDS from the cell maker. Commissioning your own UN38.3 test typically costs a few thousand dollars and takes several weeks (my estimate; no source found).
- **Covered List exposure:** The FCC equipment-authorization prohibition attaches to the radio device. A foreign-made battery inside a domestically assembled module mainly affects the 65% domestic-content calculation, not a separate authorization (inference).
- **Other likely requirements (standard practice, not researched in depth here):**
  - FCC Part 15B labeling and user-manual statements.
  - The FAA §89.525 English label.
  - EU WEEE registration and the new EU Battery Regulation 2023/1542 labeling.
  - RoHS (EU) and Prop 65 (California) warnings.

### Gaps
- No sourced UN38.3 cost or timeline.
- No research on EU Battery Regulation 2023/1542 obligations for a small embedded cell.
- No research on Prop 65 specifics.
