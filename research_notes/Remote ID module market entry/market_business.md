# Remote ID Add-On Module Market: Size, Demand Drivers, and Business Case (as of Oct 11, 2026)

Scope note: research covers the market, regulatory demand drivers, unit economics, channels and risks for a small open-hardware company (OffGrid Devices) entering broadcast Remote ID (RID) add-on modules. About 20 search/fetch calls were made. The FAA "by the numbers" page returned HTTP 403, so registry figures come from FAA forecast coverage and secondary sources. Figures are dated where possible. **"Inference"** marks my own reasoning or estimates.

## 1. How big is the US installed base, and how many drones lack built-in Standard RID?

### Takeaway
The FAA's 2026 Aerospace Forecast puts the active Part 107 (commercial) fleet at about 424,000 aircraft at the end of 2025. Its 2030 projection ranges from 470,000 (low case) to 540,000 (base case), and new registrations peaked in 2024. Recreational new-owner registrations are falling (4,782/month in 2025, down from 6,053 in 2023). I found no public count of drones that lack built-in Standard RID, and no count of module units sold. Add-on demand is real but modest, probably tens of thousands of units a year in the US (inference). It is a niche, not a mass market.

### Cited Findings
- FAA 2026 Aerospace Forecast (reported Aug 9, 2026): active Part 107 fleet of about 424,000 aircraft at end of 2025, up 24,000 from 2024. — [Unmanned Airspace](https://www.unmannedairspace.info/uncategorized/faa-reports-lower-drone-commercial-registrations-but-stronger-forecast-growth/)
- Commercial new registrations: over 135,000 in 2024 and over 126,000 in 2025. Monthly averages were 10,409 (2023), 11,300 (2024) and about 10,500 (2025). The FAA says commercial new registrations peaked in 2024. — [Unmanned Airspace](https://www.unmannedairspace.info/uncategorized/faa-reports-lower-drone-commercial-registrations-but-stronger-forecast-growth/)
- Recreational new-owner registrations averaged 6,053/month (2023), about 5,810 (2024) and 4,782 (2025). Net Part 107 registry growth fell from 3,740/month (2023) to 3,160 (2024) to about 2,000 (2025). — [Unmanned Airspace](https://www.unmannedairspace.info/uncategorized/faa-reports-lower-drone-commercial-registrations-but-stronger-forecast-growth/)
- Forecast: Part 107 fleet grows from 424,000 (2025) to 540,000 (2030) in the base case (5.0% CAGR), or to 470,000 in the low case (3.0% CAGR). Cumulative new registrations go from 1.07M to 1.49M. Remote pilots: 493,396 in 2025, rising to 628,600 by 2030. — [Unmanned Airspace](https://www.unmannedairspace.info/uncategorized/faa-reports-lower-drone-commercial-registrations-but-stronger-forecast-growth/)
- A secondary blog cites 855,860 total registered drones in early 2026 (63% recreational, 37% commercial), 405,682 Part 107 remote pilots as of Dec 2024, a recreational small-drone fleet of about 1.87M and over 966,000 commercial small drones. These figures are not verified against an FAA page and conflict in definitions; treat them as low confidence. — [voxbooster (secondary)](https://voxbooster.com/blog/consumer-drone-statistics-2026)
- Ruko R111S: 13.5 g, FAA-compliant RID module for drones over 250 g. A buyer-guide page shows a 4.6 rating from 851 reviews (unverified). — [micro-tools listing](https://www.micro-tools.com/products/ruko-r111s-rc-aircraft-gps-tracker-finder-with-beeper-light-weight-rid-module-with-buzzer-for-faa-regulation-spare-part-for-fpv-drone-faa-compliant-remote-id-module-for-drone-3-hours-battery-time); [bestelectronic.org](https://bestelectronic.org/best-remote-id-module-for-rc-planes/)
- Forum reporting: Holy Stone's RID module was once the most popular under $100 at $89.99, and Ruko R111 was listed at $59.99. Most RID boxes later dropped to $30-35. Ruko, Bwine and Holyton are described as "cousin brands" of Potensic and Holy Stone (forum claim, unconfirmed). — [MavicPilots](https://mavicpilots.com/tags/rid-module/)
- The "500+ sold/month" figure for the Ruko R111S comes from the brief (Amazon badge). I did not verify it independently.

### Inferences
- Recreational registration is per owner, not per aircraft, so the recreational fleet is larger than the registration count suggests. The new-owner inflow (about 57,000/year in 2025) is the best proxy for new hobbyists, and it is shrinking about 18% year over year.
- Who still needs an add-on: (a) FPV and home-built quads over 250 g (the core market); (b) fixed-wing and RC models flown outside FRIAs; (c) older pre-RID drones; (d) Part 107 operators running custom or ArduPilot builds. Most mainstream camera drones sold since 2023 (DJI, Autel and others) ship with Standard RID built in, which shrinks the "older drone" segment every year.
- Rough sizing (inference, low confidence): if Ruko sells about 500+/month on Amazon (about 6,000+/year), and Ruko, Holy Stone, BlueMark, Dronetag and others split the market across Amazon, FPV retailers and direct sales, total US add-on demand is plausibly 20,000-60,000 units/year in 2025-2026. At $30-100 average selling price (ASP), that is roughly $1-4M/year of US retail revenue. This is a niche market. OffGrid would likely capture a small fraction (for example 1,000-5,000 units/year) without a strong differentiator.

### Gaps
- FAA "by the numbers" page (faa.gov/uas/resources/by_the_numbers) returned 403. Need the official current total and the recreational vs Part 107 split.
- No public data found on cumulative RID module units sold, or on the share of the fleet without built-in RID.
- No Amazon sales-tracker data (Jungle Scout, Helium 10) was retrieved for Ruko, Holy Stone or BlueMark.

## 2. Compliance, enforcement, and whether enforcement is increasing

### Takeaway
FAA RID enforcement has been possible since the discretion period ended on March 16, 2024. Visible RID-specific penalties are rare, and compliance among FPV hobbyists is widely believed to be low. The policy direction since mid-2025 points toward stricter use of RID data: EO 14305 gives law enforcement real-time access to RID data and pushes "full enforcement," and a reported January 2026 FAA compliance order shifts serious cases toward legal action. Part 108 BVLOS, still not final, would require RID. Demand pressure is rising slowly. Fear of enforcement, more than actual fines, is the purchase driver.

### Cited Findings
- FAA discretionary enforcement for RID ended March 16, 2024. Non-compliant operators can face fines and suspension or revocation of their certificates. — [State Aviation Journal](https://stateaviationjournal.com/index.php/national-news/faa-ends-discretionary-enforcement-policy-on-drone-remote-identification)
- Maximum fine figures conflict: one source says up to $27,500 per violation, another says up to $75,000 per violation under the FAA Reauthorization Act of 2024. Neither was verified against the statute. — [thedroneu](https://www.thedroneu.com/blog/remote-id/); [UAVModel blog](https://blog.uavmodel.com/faa-remote-id-compliance-2026-what-fpv-pilots-need-to-know/)
- One source reports that in 2025 the FAA issued fines of $1,771-$36,770 across 18 drone enforcement actions and suspended or revoked 8 Part 107 certificates. This is general drone enforcement, not RID-specific, and was not verified. — [UAVModel blog](https://blog.uavmodel.com/faa-remote-id-compliance-2026-what-fpv-pilots-need-to-know/)
- A January 2026 FAA order (2150.3C) reportedly sends serious violations to the Office of Chief Counsel instead of counseling. This is from secondary reporting, not confirmed with the FAA. — [UAVModel blog](https://blog.uavmodel.com/faa-remote-id-compliance-2026-what-fpv-pilots-need-to-know/)
- EO 14305, "Restoring American Airspace Sovereignty" (June 6, 2025), Sec. 7(c): directs the FAA to give federal, state, local, tribal and territorial agencies automated, real-time access to personal identifying information linked to RID signals, within 60 days. — [White House](https://www.whitehouse.gov/presidentialactions/2025/06/restoring-american-airspace-sovereignty); [Federal Register](https://www.govinfo.gov/content/pkg/FR-2025-06-11/html/2025-10803.htm)
- EO 14305 also directs DOJ and the FAA toward "full enforcement" against operators who endanger the public or violate airspace restrictions, and creates a Federal Task Force to Restore American Airspace Sovereignty. — [AAAE alert](https://alerts.aaae.org/latest/regulatory_060625)
- Part 108 BVLOS: the NPRM was published in August 2025. The final rule had not been published as of the latest reporting and has been in White House review since July 10, 2026. The 240-day deadline under EO 14307 lapsed on Feb 1, 2026. Secondary sources say the proposal requires RID throughout flight. — [DroneXL FAA coverage](https://dronexl.co/fr/us-government/faa/); [sky.trade](https://sky.trade/articles/bvlos-part-108-2026)
- BlueMark (June 2024, updated June 2025) alleges that several FAA-accepted products are non-compliant: Holy Stone HSRID01/02, Flite Test EZ ID, Phoenix UAS mRID and Holyton HT60. It has filed complaints with the FAA. It notes that DoCs can be rescinded under 14 CFR 89.540, which makes affected products unusable in the US, and cites a rescinded DJI Mavic Pro Platinum DoC as precedent. — [BlueMark](https://bluemark.io/?p=3116)

### Inferences
- Giving law enforcement real-time RID data (EO 14305) makes RID the main identification tool for police and counter-UAS. That strengthens the case that "a non-broadcasting drone is suspect," which nudges compliance-minded hobbyists to buy modules. A crackdown on FPV hobbyists specifically has not been documented.
- Part 108, once final, adds RID-equipped BVLOS demand, but mostly for OEM-integrated or network RID on commercial platforms, not $35 hobby add-ons.

### Gaps
- No count of RID-specific FAA enforcement actions or fines found.
- No survey data on RID compliance rates among FPV and RC pilots.
- Whether the FAA met the EO 14305 60-day data-access deadline, and how it implemented it.

## 3. Is demand shrinking (built-in Standard RID, FRIAs)?

### Takeaway
Two forces are steadily shrinking the add-on market. New camera drones ship with Standard RID, and FRIAs give club RC/FPV fliers an exemption. AMA alone reports 1,835 FRIA club sites, and an unverified 2026 estimate puts all FRIAs at about 2,100. Falling recreational registrations add a third headwind. The surviving core is FPV, freestyle and long-range pilots flying off-field, plus custom and commercial builds.

### Cited Findings
- FRIAs are areas where unmanned aircraft can operate without broadcasting RID. Only FAA-recognized community-based organizations (CBOs) and educational institutions can apply, through DroneZone. A FRIA lasts 48 months and is renewable. The FAA renewed the FRIA information collection in 2025 (Federal Register June 10 and Sept 22, 2025). — [Federal Register 2025-10459](https://www.govinfo.gov/content/pkg/FR-2025-06-10/html/2025-10459.htm); [FR 2025-18301](https://www.govinfo.gov/content/pkg/FR-2025-09-22/pdf/2025-18301.pdf)
- AMA says 1,835 of its chartered club flying sites have gained FRIA status (undated, about 2024). — [AMA blog](https://amablog.modelaircraft.org/amagov/2024/01/17/remote-id-compliance-and-resources)
- About 2,100 FRIAs nationwide as of January 2026, mostly AMA club fields. Unverified blog estimate. — [UAVModel blog](https://blog.uavmodel.com/5942-2/)
- Recreational new-owner registrations fell from 6,053/month (2023) to 4,782/month (2025). — [Unmanned Airspace](https://www.unmannedairspace.info/uncategorized/faa-reports-lower-drone-commercial-registrations-but-stronger-forecast-growth/)

### Inferences
- The FRIA network (about 2,000 sites) means traditional RC fixed-wing club fliers are largely not buyers. FPV freestyle pilots flying at bandos, parks or mountains are the main buyers.
- Add-on demand in the US likely peaked in 2023 to early 2024, around the original Sept 2023 deadline and the March 2024 end of discretion, and is now in a slower replacement and new-entrant phase.
- Counter-trend: new FPV pilots keep entering, and each 250 g+ build needs a module or a flight controller (FC) running ArduPilot/Betaflight with an RID peripheral.

### Gaps
- Official current FRIA count (needs the FAA UDDS map).
- No data on the share of new FPV pilots who buy RID modules.

## 4. International demand (EU, UK, Japan, Canada, Australia)

### Takeaway
There is a real international addressable market, but each market needs separate certification and it is not one unified market. Japan has required RID for 100 g+ drones since June 20, 2022. The EU has required Direct RID for class-marked and Specific-category drones since Jan 1, 2024; for legacy and privately built drones, sources conflict on whether it is "recommended" or mandatory. The UK made RID mandatory for class-marked drones on Jan 1, 2026, and extends it to legacy and privately built 100 g+ camera drones on **Jan 1, 2028**. That is the next big add-on wave. Canada proposed RID in June 2026 (NPA 2026-005), with implementation "years away." Australia reportedly has no RID requirement.

### Cited Findings
- **Japan:** registration is mandatory for drones of 100 g or more, which must display a registration ID and carry a remote ID function (MLIT, effective June 20, 2022). — [MLIT Civil Aviation Bureau](https://www.mlit.go.jp/en/koku/uas.html); [MLIT handbook](https://www1.mlit.go.jp:8088/koku/content/mlit_HB_web_en_2022.pdf)
- **EU:** from Jan 1, 2024, C1-C3 and Specific-category drones must have active RID. Per a forum quote of EASA, legacy drones over 250 g are "recommended" to carry a module. Other sources say it is mandatory for all UAS, including privately built ones. Conflicting; verify with EASA. — [IntoFPV forum (quoting EASA)](https://intofpv.com/t-remote-id-now-mandatory-in-the-eu?pid=212233); [SPH Engineering](https://www.sphengineering.com/news/drone-remote-id-requirements)
- The EU Direct RID standard differs from the FAA's ASTM F3411 implementation (it adds the operator ID). Modules typically need dual FAA/EU firmware. Dronetag and BlueMark market FAA plus EU compliance. — [Pilot Institute](https://pilotinstitute.com/remote-id-drone-modules/)
- **UK:** RID became mandatory on Jan 1, 2026 for UK1, UK2, UK3, UK5 and UK6 class-marked drones. From Jan 1, 2028, it extends to legacy (non-class-marked) drones and privately built UAS of 100 g or more with a camera. EU C-class drones are recognized until Dec 31, 2027. Flying without RID after the deadline is a criminal offence. — [Heliguy](https://www.heliguy.com/blogs/posts/uk-drone-rules-2026-changes/); [DroneDJ](https://dronedj.com/2026/01/01/uk-drone-rules-remote-id/); [FPV UK](https://fpvuk.org/class-marks-and-remote-id/)
- **Canada:** Transport Canada published NPA 2026-005 on June 8, 2026. It would require RID for 250 g-150 kg drones (broadcast or network, ASTM F3411) and exempt CBO sites. Comments closed Sept 9, 2026. A law firm says implementation is several years away. — [DroneXL](https://dronexl.co/2026/06/09/transport-canada-drone-remote-id-npa-2026-005/); [MLT Aikins](https://www.mltaikins.com/insights/transport-canada-proposes-rpas-airspace-regulations/)
- **Australia:** CASA registration applies to 250 g-25 kg drones, with no RID requirement. From a low-confidence aggregator, not verified with CASA. — [goodsacrossborders](https://goodsacrossborders.com/drones)

### Inferences
- The UK 2028 legacy and home-built mandate is a clear, dated demand wave. UK FPV pilots will need modules, and FPV UK is already educating its members. A product launched in 2027 with UK-compatible firmware is well timed.
- Canada's ASTM F3411 basis means a US-compliant module could serve Canada with little rework, but demand won't arrive before about 2028.
- Japan has a mandate but a domestic certification and radio-law (TELEC/giteki) barrier. It is probably not worth it for a small startup.

### Gaps
- Primary EASA text on whether RID is mandatory for legacy and privately built drones.
- UK CAA's primary guidance on technical standards for add-on modules (whether UK modules need a specific conformity route).
- CASA primary confirmation.

## 5. Unit economics and channels

### Takeaway
Retail ASPs have split into two tiers. Chinese commodity modules sell for about $30-40 (Ruko and Holy Stone after price cuts). EU-audited premium modules sell for $85-180 (Dronetag BS at about $85-89, BlueMark DB121 at $119, DB150 at $129-139, DB120 at $140-180, Dronetag Beacon V2 at $149). On Amazon, a $35 module loses about $5.25 to the referral fee (15%, or about $2.80 at 8%) and about $3.1-3.9 to FBA fulfillment. That leaves about $26-29 before cost of goods sold (COGS), compliance and marketing. Competing on price with Ruko at $30-40 is thin-margin. A $60-90 "US-made, open firmware, audited" FPV module, sold through FPV retailers and the YouTube audience, is more defensible.

### Cited Findings
- BlueMark DB120 at about $150-180 (2026 snapshot), $140 in the 2023 Pilot Institute test. DB150 is 12.5 g with a 2 h battery at $129-139. DB121 (powered from 2S-3S) at $119. Flite Test EZ ID at about $109 (2S-8S power). Dronetag BS at $89, 1.5 g. Dronetag Beacon V2 at $149 / €139. — [Pilot Institute](https://pilotinstitute.com/remote-id-drone-modules/); [Gearfocus DB150](https://gearfocus.com/products/bluemark-db150-dronebeacon-faa-remote-id-module-wbattery-the-kbJLg); [AllSpice-hosted market note (search snippet; page later 404)](https://hub.allspice.io/AllSpiceMirrors/incutec-OpenRemoteID/src/branch/main/research/RemoteID_Modules_Research.md)
- Dronetag BS standard price was $85, with a limited-time $99 combo with battery and enclosure that expired March 2024. — [Drones Magazin](https://www.drones-magazin.de/?p=9329)
- Commodity price collapse: Holy Stone RID was $89.99 and Ruko R111 was $59.99, later dropping to "$30-35 for most RID boxes." — [MavicPilots](https://mavicpilots.com/tags/rid-module/)
- Amazon FBA 2026: small standard ≤4 oz costs about $3.06-3.07 per unit. ShipBob gives $3.06-3.87 for items priced $10+. Fees rose about $0.12 on Jan 15, 2026, plus a 3.5% fuel and logistics surcharge from Apr 17, 2026. Referral fee is 15% for most goods and 8% for electronics. Storage is $0.87/cu ft (off-peak), $2.40 in Q4. — [ShipBob](https://shipbob.com/blog/amazon-fba-fees); [Repricer Express](https://www.repricerexpress.com/?p=48423); [Nova Data](https://novadata.io/resources/answers/how-much-does-amazon-fba-cost-per-unit)
- An FAA DoC is required for every broadcast module (14 CFR 89.530). Accepted means of compliance are listed at uasdoc.faa.gov. — [Cornell LII 14 CFR 89.530](https://www.law.cornell.edu/cfr/text/14/89.530); [FAA Remote ID](https://faa.gov/uas/getting_started/remote_id)

### Inferences (estimates, not sourced)
- **Illustrative Amazon P&L at $35 retail:** referral $5.25 (15%), FBA about $3.30 with surcharge, so net about $26.45. Estimated landed COGS for an ESP32-C3/S3 plus a low-cost GNSS module, LiPo, PCB, enclosure and packaging is roughly $8-14 at 500-1,000 unit batches. That leaves a contribution of about $12-18 before ads (Amazon PPC is often 10-20% of sales), returns and warranty. That gives a net of about $7-13/unit. At 1,000-3,000 units/year, that is roughly $10-40k/year of profit, which does not justify a company but could fund a product line.
- **Direct and FPV retail at $60-80:** retailers like GetFPV and RaceDayQuads typically take 30-45% wholesale margin (industry norm, not verified here). Direct sales via YouTube or a web store keep about 90% after Stripe and shipping.
- **Fixed costs to budget:** FCC equipment authorization for the radio (an ESP32 module with modular approval lowers intentional-radiator testing, but the end product still needs FCC labeling and possibly verification), the FAA DoC filing, ASTM F3411 testing (self or third-party), and EU/UK conformity if going international. Low five figures is a reasonable planning assumption.
- **B2B and OEM channels:** ArduPilot already supports an open-source ESP32-based firmware (ArduRemoteID) that integrators flash onto cheap boards. That lowers the barrier for OEMs and limits pricing power on bare hardware. The value an OEM pays for is the DoC and serial-number management, FCC paperwork and NDAA/Buy-American provenance, not the PCB.
- **Education:** university and K-12 drone programs flying outdoors over 250 g need RID or a FRIA. Educational institutions can apply for FRIAs, which partly removes demand.

### Gaps
- Actual Ruko, Holy Stone or BlueMark landed costs and margins.
- FPV retailer wholesale terms (GetFPV, RDQ) and their current RID SKU sell-through.
- Exact FCC and FAA DoC compliance cost for a new entrant.

## 6. Adjacent opportunities: OEM/NDAA RID, US-made differentiation, receivers, LoRa

### Takeaway
The biggest new opportunity comes from US industrial policy, not hobby demand. On Dec 22, 2025 the FCC added all foreign-produced UAS **and UAS critical components** to the Covered List, so new foreign models cannot get FCC authorization. A temporary exemption runs until Jan 1, 2027 for Blue UAS products and components that qualify as **Buy American "domestic end products"** (US-manufactured with at least 65% US content, or COTS). The Aug 2026 Section 232 proclamation adds 25-100% tariffs on imported drones and "critical components" from Sept 3, 2026, with more components (motors, FCs, ESCs) from Feb 9, 2027. If RID modules count as critical components (**not confirmed**), new Chinese RID module models are blocked from FCC authorization and existing imports face tariffs. That opens a niche for a **US-designed and US-assembled RID module or embedded board** sold to US drone makers.

### Cited Findings
- On Dec 22, 2025 the FCC added new models of foreign-made UAS and their critical components to the Covered List, making them ineligible for new or modified FCC equipment authorization. Foreign products authorized before Dec 22, 2025 may still be imported and sold unless modified. Law firms describe it as a de facto ban. — [Holland & Knight](https://www.hklaw.com/en/insights/publications/2025/12/fcc-adds-all-foreign-made-drones); [Wilson Sonsini](https://www.wsgr.com/print/v2/content/49062874/FCC-Restricts-Authorization-of-Foreign-Made-Drones-and-Critical-Components.pdf)
- Jan 7, 2026: two temporary exemptions run until Jan 1, 2027, for Blue UAS list products and for UAS critical components that qualify as Buy American domestic end products. A domestic end product must be manufactured in the US and have at least 65% US content, or be COTS. There is no brand-wide exemption. — [K&L Gates](https://www.klgates.com/FCC-Announces-Wide-Ranging-New-Controls-on-Drones-and-Drone-Components-1-16-2026); [Morgan Lewis](https://www.morganlewis.com/pubs/2026/01/fcc-exempts-certain-drones-and-components-from-covered-list-to-address-national-security-risks)
- "Critical components" examples given: communications systems, navigation systems, motors, batteries. RID modules are not named. — [Wiley](https://www.wiley.law/alert-FCC-Drone-Ban-Update-Roundup-First-Conditional-Approvals-a-Limited-Waiver-Quiet-Revocations-and-First-Challenges-to-the-Ban)
- On Mar 18, 2026, the first Conditional Approvals (SiFly Q12, Mobilicom SkyHopper and others, ScoutDI Scout 137, Verge X1) allowed FCC authorizations until Dec 31, 2026, with an onshoring plan as a key factor. A Jan 21, 2026 OET waiver allows security firmware updates. Some DJI and Autel authorizations were revoked in Jan 2026. DJI challenged the decision in the Ninth Circuit in Feb 2026. — [Wiley](https://www.wiley.law/alert-FCC-Drone-Ban-Update-Roundup-First-Conditional-Approvals-a-Limited-Waiver-Quiet-Revocations-and-First-Challenges-to-the-Ban)
- The exempt list grew as of June 2026, and the FCC issued a May 8, 2026 "Extension and Expansion of Waivers" (details not retrieved). — [DroneDJ](https://dronedj.com/2026/06/09/fcc-drone-ban-exempt-list/); [FCC Covered List](https://www.fcc.gov/supplychain/coveredlist)
- Section 232 Proclamation 11055 (signed Aug 13, 2026, effective Sept 3, 2026): 100% on drones over 25 kg, thermal drones, docking stations and "critical components" (Annex I); 25% on drones of 25 kg or less (Annex II); 25% on motors, FCs and ESCs from Feb 9, 2027 (Annex III). China gets no cap. The EU, Japan, Korea, Taiwan and Switzerland get 15% all-in, and the UK 10%, with "substantially all" origin certification. Blue UAS and FCC Conditional Approval products are deferred to Feb 9, 2027. An onshoring-plan exemption is pending. Whether RID modules are covered is not stated. — [TariffLens](https://www.tarifflens.ai/blog/section-232-drone-tariff-september-2026-importers-guide); [Inside Unmanned Systems](https://insideunmannedsystems.com/trump-imposes-tariffs-up-to-100-on-foreign-made-drones-targeting-chinese-supply-chains/)
- EO 14305 directs agencies to detect, track and identify drones, and gives state and local agencies access to RID data. That supports demand for RID receivers and detectors. — [White House](https://www.whitehouse.gov/presidential-actions/2025/06/restoring-american-airspace-sovereignty/)
- Aerobits (Poland) markets RID solutions for OEMs, an example of the embedded-OEM segment. — [Unmanned Systems Technology](https://www.unmannedsystemstechnology.com/2023/08/aerobits-releases-remote-id-solutions-for-oems/)
- An open-source "OpenRemoteID" project (incutec) mirrored on AllSpice has a RID market-research document. It signals other open-hardware entrants. The page returned 404 on fetch, so its contents are not verified. — [AllSpice mirror](https://hub.allspice.io/AllSpiceMirrors/incutec-OpenRemoteID/src/branch/main/research/RemoteID_Modules_Research.md)

### Inferences
- **Best wedge:** a small "Made in USA / Buy-American-qualifying" RID board, sold as (a) a bare embedded board (UART/MAVLink, ArduPilot/PX4 compatible) to US drone builders who must now source non-Chinese components, and (b) a standalone FPV module. Assembling in the US and sourcing enough US content to clear 65% is hard with ESP32 (Chinese) and typical GNSS chips. A US-made PCB plus US assembly might still not reach 65% by cost. This needs a careful bill-of-materials (BOM) analysis. Note that the "COTS" route may apply instead.
- The Jan 1, 2027 expiry of the domestic end product exemption, and the Dec 31, 2026 expiry of conditional approvals, create timing risk. The policy may be extended or made permanent, or it may change.
- **RID receivers and scanners** for police, event security, prisons and critical infrastructure are a growing adjacency. ESP32 hardware can sniff Wi-Fi NAN, Wi-Fi Beacon and BT4/BT5 RID. A low-cost, open, LoRa-backhauled RID receiver network is a natural fit for OffGrid's ESP32/LoRa expertise. It faces less certification burden, since receive-only devices are unintentional radiators, and gets a policy tailwind from EO 14305.
- LoRa GPS trackers and lost-model finders (the Ruko R111S already bundles a beeper and tracker) can be combined with RID to differentiate.

### Gaps
- Whether FCC or Commerce classify standalone RID broadcast modules as "UAS critical components." This is the most important open question for the business case.
- Content of the May 8, 2026 FCC waiver expansion, and any post-June 2026 updates.
- Size of the US non-Chinese drone OEM market and its RID sourcing.

## 7. Risks

### Takeaway
The main risks: (1) a commoditized, shrinking hobby market with a $30-35 Chinese price floor; (2) regulatory and certification risk, including DoC rescission, FCC Covered List classification and the cost of maintaining FAA, EU and UK compliance; (3) volatile, unclear trade policy (Section 232 component coverage, temporary exemptions expiring in 2027); (4) liability and reputation if a module fails to broadcast correctly. BlueMark is actively filing FAA complaints against non-compliant modules.

### Cited Findings
- DoC rescission (14 CFR 89.540) can make products unusable in the US. BlueMark has filed complaints against several accepted products. — [BlueMark](https://bluemark.io/?p=3116)
- Tariffs: the Supreme Court struck down IEEPA tariffs on Feb 20, 2026. The administration imposed a 10% Section 122 global tariff for 150 days, expiring about July 24, 2026 unless extended (status unverified). Section 232 drone and component tariffs started Sept 3, 2026. — [Dimerco](https://dimerco.com/news-press/supreme-court-ruling-on-ieepa-tariffs/); [CRS via EveryCRSReport](https://www.everycrsreport.com/files/2026-02-26_IF12990_7ab2239b1490ef7489dd800010ce8bc03b33701e.html); [TariffLens](https://www.tarifflens.ai/blog/section-232-drone-tariff-september-2026-importers-guide)
- The FCC exemption window is temporary (until Jan 1, 2027), and the FCC gained authority to revoke existing authorizations for covered equipment. — [K&L Gates](https://www.klgates.com/FCC-Announces-Wide-Ranging-New-Controls-on-Drones-and-Drone-Components-1-16-2026)
- Recreational registration inflow is shrinking, and FRIAs (about 1,835-2,100) exempt club flying. — [Unmanned Airspace](https://www.unmannedairspace.info/uncategorized/faa-reports-lower-drone-commercial-registrations-but-stronger-forecast-growth/); [AMA](https://amablog.modelaircraft.org/amagov/2024/01/17/remote-id-compliance-and-resources)

### Inferences
- **Opportunity inside the risk:** if the FCC and Section 232 rules apply to RID modules, the Chinese price floor rises (no new FCC IDs, plus 25-100% duty). Existing pre-Dec-2025 authorized Chinese models (likely including the Ruko R111S) can keep selling, so the hobby price floor won't vanish overnight.
- **Open-source firmware risk:** publishing full firmware for a DoC-accepted product means users can modify it, for example to spoof serials or disable broadcast. The FAA DoC requires tamper resistance (the module must not be easily modified to transmit false data). Open hardware is fine, but the shipped firmware should be locked or signed.
- **Liability:** a product-liability or false-compliance claim (a pilot fined because the module was faulty) is a reputational risk for a YouTube-driven brand. Budget for third-party test validation.

### Gaps
- Status of the Section 122 tariff after July 24, 2026.
- Any FAA actions rescinding add-on module DoCs in 2025-2026.

## 8. Public revenue and funding data on RID module makers

### Takeaway
There is almost no reliable public financial data. Dronetag (Czech) shows small disclosed funding (about $108k-€673k in different databases), revenue under €1M in 2021 and 2023 per a Spanish government startup database, and an automated estimate of about $2.5M. Ruko and Holy Stone are private Chinese-linked brands with no disclosed RID revenue. BlueMark (Netherlands) discloses nothing.

### Cited Findings
- Dronetag total funding is reported variously: about $108K (pre-seed June 2024) per VCBacked and Seedtable; $634,800 per Prospeo; about €673k per a Spanish startup database. A $16M claim on robotics.press is not supported by its own data (NATO DIANA grant, Nov 2023, no amount). — [VCBacked](https://www.vcbacked.co/company/dronetag); [Seedtable](https://seedtable.com/startups/dronetag-cz); [Prospeo](https://prospeo.io/c/dronetag); [startups.one.gob.es](https://startups.one.gob.es/companies/dronetag); [robotics.press](https://robotics.press/companies/dronetag/)
- Dronetag revenue was under €1M in 2021 and 2023 (Spanish database). Prospeo's automated estimate is about $2.48M per year. — [startups.one.gob.es](https://startups.one.gob.es/companies/dronetag); [Prospeo](https://prospeo.io/c/dronetag)
- Drone industry investment has fallen sharply since 2021. — [The Drone Girl](https://www.thedronegirl.com/2025/04/28/drone-industry-funding-in-2025/)

### Inferences
- The best-known European RID specialist reportedly does about €1M-2.5M/year in revenue, with RID only part of its product mix (it also sells network RID and receivers and does UTM work). That suggests the global add-on RID hardware market is single-digit millions of dollars per year. It supports a side product line for OffGrid, not a venture-scale business on its own. Low confidence, from weak data.
- **Go/no-go framing:** a pure US hobby clone competing with Ruko at $30-40 on Amazon is a no-go: thin margin, shrinking market, a compliance burden. A conditional go: (a) a $60-90 FPV-optimized, US-assembled module with open hardware, signed firmware and an audited DoC, sold direct via YouTube and through FPV retailers; (b) an embedded RID board for US/NDAA drone builders; (c) an ESP32/LoRa RID receiver. Launch timing should also target the UK Jan 2028 legacy and home-built mandate.

### Gaps
- No Ruko, Holy Stone or BlueMark revenue or unit data found.
- No Crunchbase primary data retrieved for Dronetag. Czech business registry filings (justice.cz) would give audited revenue.
