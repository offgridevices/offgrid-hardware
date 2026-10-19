# Part audit, 17 Oct 2026

Every BOM line was checked against DigiKey (number, stock, price at 10 and
100, lifecycle) and LCSC/JLCPCB (stock, and that the LCSC number is the
genuine maker's listing rather than a clone sold under the same part
number). The raw table is
[`part-audit-2026-10-17.tsv`](part-audit-2026-10-17.tsv). Stock moves:
check again before ordering.

## Result

- **125 lines checked; every LCSC number is the genuine maker's.** JLCPCB
  also lists clones under the same part numbers for the SKY13330 (Tokmas),
  the TVS2200 (ElecSuper and others) and the SMF15CA (FUXINSEMI). The BOM
  locks the genuine C-numbers.
- **Every part is from a US, Japanese, Taiwanese, Korean, Norwegian or
  German maker** (`src/parts.py`, `hq`).
- **Country of origin: not yet recorded** (requirement S4). DigiKey's pages
  do not show it, and Mouser and Arrow refused automated reads. Ask the
  distributor, or take it from the assembler's incoming inspection, when a
  compliant build is ordered.
- **Parts cost per board, DigiKey prices:**
  - about **$76 at 10 boards** and **$58 at 100** after the design-review
    changes (`plan.md` has the cost by block);
  - the largest lines are the QPA9510 ($11.34 / $7.46), the SX1262
    ($7.85 / $6.86) and the nRF52840 ($6.29 / $5.49);
  - JLCPCB's prices for the passives are lower, and assembly is extra.

## Lines that need a second source at DigiKey

These are stocked at LCSC for the test boards, but were out of stock (or
not for new designs) at DigiKey. `src/parts.py` (`SECOND`) names the
drop-in a US assembler buys.

| Line | Problem at DigiKey | Second source |
|---|---|---|
| Samsung 0402/0603/0805 capacitors (100 nF, 10 µF, 10 µF 25 V, 12 pF, 1 µF 25 V, 47 nF, 47 µF, 4.7 µF) | 0 in stock, 61-week lead time | Murata, TDK, Taiyo Yuden, KEMET, KYOCERA AVX equivalents (in `SECOND`) |
| Yageo 4.7 k, 510 k, 301 k; 1.5 M | 0 in stock (4.7 k and 510 k: same part on a different reel code); 1.5 M: only 34 | the -13 reel code; Panasonic ERJ-2RKF3013X; Stackpole RMCF0402FT1M50 |
| Murata NCP15XH103F03RC (NTC) | Not for new designs | Murata NCU15XH103F60RC (same B3380) |
| Abracon ABM11W 32 MHz | 0, 3,000 due 23 Oct | Abracon ABM11N-32.0000MHZ-8-D1X-T3 |
| Murata DFE252012F-R47M | 0, due 3 Dec | TDK TFM252012ALMAR47MTAA |
| TI TVS2200, TPD4E05U06 | 0, due 12 Nov / 7 Jan | backorder TI; for the TPD4E05U06, Diodes DT1240-04LP-7 (check its pinout) |
| Murata LQW15AN4N7 | 17 in stock | Würth 744765047A (an RF part: recheck the match) |
| Coilcraft 0908SQ-8N1 | not sold at DigiKey | direct from Coilcraft |
| Qorvo QPA9510 | 0 at LCSC | DigiKey has 4,012: buy there and send them to JLCPCB |
| Infineon BGA7L1BN6, TI TLV75528, ECS TCXO | few at LCSC | DigiKey stock covers it |

## Changed after the audit (design review, 17 Oct)

These lines were added or replaced after the audit. Their DigiKey numbers
were still to be filled in on 17 Oct; the 19 Oct re-audit below has them:

- ECS-TXO-20CSMV4-320-**AP**-TR. It replaces the -AY code, which is rated
  only to −30 °C. DigiKey has 2,765; LCSC has 0.
- Murata GRM21BR61C226ME44L, 22 µF 16 V. It replaces the Samsung 25 V part,
  which is obsolete at DigiKey.
- TI LM66100DCKR (LCSC C2869734).
- Rohm UDZVTE-174.7B (C209560).
- Yageo 287 k (C327358).

## 19 Oct re-audit

All 129 assembled lines in `circuit.build()` (243 parts; the 6 test pads
and the unfitted `HDR_2x10` header are skipped) were re-read: DigiKey
(number, stock, price at 10 and 100, lifecycle) and LCSC plus JLC stock by
exact C-number. Table:
[`part-audit-2026-10-19.tsv`](part-audit-2026-10-19.tsv). Every BOM
C-number is still the genuine maker's. The four missing DigiKey numbers
(C22u16, HV1.3pF, TCXO32, R287k) are now in `src/parts.py`; the L8.1nH has
none because DigiKey does not sell it.

**Makers (NDAA).** No flag: every maker is in the US, Japan, Taiwan, South
Korea, Norway or Germany. JLC lists same-MPN clones from Chinese makers for
SMF33CA (Shandong Jingdao), TVS2200 (Wuxi Maxinmicro, ElecSuper), SKY13330
(Tokmas) and TPD4E05U06 (MSKSEMI and others): the BOM C-numbers are the
genuine ones, and the second sources below are all non-Chinese.

**Mistakes in the 17 Oct table.** DigiKey shows another part's stock when
the one searched is out of stock, and two reads took it. NMOS
(SSM3K56ACT) is 0, not 4,664 (the 4,664 is a Nexperia part); L2u2 (Murata
DFE201610E) is 0, not 88,488 (a TDK part). Three "second sources" in
`SECOND` had the same fault and were replaced: Diodes DT1240-04LP-7,
Stackpole RMCF0402FT1M50 and TDK TFM252012ALMAR47MTAA are not stocked.

### Flags

| Line (qty) | Flag | Second source (non-Chinese) |
|---|---|---|
| C100n (13), C10u (3), C10u25 (3), C1u25 (4), C47n (2), C12p (2) | (a) DK 0, 61 wk (Samsung) | Murata GRM155R71C104KA88J 7.4M; TY EMK107BBJ106MA-T 704k; Kyocera AVX KGM21AR51E106KU 4,559; TDK CGA3E1X7R1E105K080AC 854k; KEMET C0402C473K3RACTU 276k; KEMET C0402C120J5GACTU 980k (Murata 12 pF is now 0 too) |
| C22u16 (2) | (a) DK 0, due 15 Feb 2027; LCSC shop 0, JLC 2,637 | Samsung CL21A226MOQNNNE, DK 2,888, $0.1225@100; JLC C98190 |
| HV0.9pF (1), HV1.3pF (2) | (a) DK 0, 21 wk (Murata) | Johanson QSCP251Q0R9B1GV001T 69,420, $0.0998@100; QSCP251Q1R3B1GV001T 40,828, $0.2556@100. JLC has 0 of both: use the Murata C-numbers there |
| HV5.6pF (1) | (a) DK 143 | Vishay VJ0603D5R6CXPAJ 117,926, $0.2037@100 |
| L2u2 (1) | (a) DK 0 | TDK TFM201610GHM-2R2MTAA 5,582, $0.303@100 (check DCR) |
| L470n (1) | (a) DK 0, due 3 Dec | Bourns SRP2512TMA-R47M 1,750, $0.2018@100 (check land pattern) |
| L2.7nH (1), L4.7nH (2) | (a) DK 126 / 17; L4.7nH LCSC 0, JLC 87 (b) | Murata LQW15AN2N7B00D 38,938, $0.0836@100; Bourns CW100505-4N7J 171,521, $0.1699@100 (lower Q) |
| NMOS SSM3K56ACT (3) | (a) DK 0 | onsemi NTNS3164NZT5G 25,686, $0.2191@100, but Id 361 mA: check the 3 uses. Toshiba SSM3K56CT is out too (9,022 due 21 Oct) |
| SKRP SKRPADE010 (2) | (a) DK 0, 20 wk | C&K PTS810 SJS 250 SMTR LFS 44,489, $0.5076@100, -40 to +85 C |
| TPD4E05U06 (3) | (a) DK 0, due 7 Jan | TI TPD4E05U06QDQARQ1 (same package) 137,744, $0.5787@100 |
| XTAL32M (1) | (a) DK 0, 3,000 due 23 Oct | Abracon ABM11N-32.0000MHZ-8-D1X-T3 1,000, $0.4803@100 |
| R1.5M (5), R2.21k (1), R4.7k (3) | (a) DK 34 / 0 / 0 | KOA RK73H1ETTP1504F 69,039; Vishay CRCW04022K21FKED 306,497; Yageo RC0402FR-134K7L 68,336 |
| L8.1nH_PA (1) | (a)(b) not at DigiKey; LCSC/JLC 73 | none (Coilcraft only): buy from Coilcraft direct, 0908SQ-8N1JLB. Farnell lists the -GLB (2%). Mouser not confirmed |
| MAX17608 (2) | (b) LCSC 0, JLC 2 | none; consign from DigiKey (5,872) |
| L3.2nH_0805 (2), L3.6nH_0805 (1) | (b) JLC 2 / 3 | consign from DigiKey (1,318 / 1,935) |
| C47u (2) | (b) LCSC 0, JLC 0 | consign from DigiKey (29,829); X5R fallback Samsung CL31A476MQHNNNE (re-run bias sim) |
| R68_0805_AS (1) | (b) LCSC 195, JLC 198 | Panasonic ERJ-P06F68R0V, DK 19,204, $0.0542@100 |
| LFCG1000, TLV75528, BGA7L1BN6, QPA9510, TCXO32 | (b) LCSC/JLC 104 / 40 / 21 / 0 / 0 | consign from DigiKey (989 / 990 / 3,206 / 4,001 / 2,765) |
| NTC10K (1) | (d) Not For New Designs | Murata NCU15XH103F60RC 40,000, $0.0527@100, B3380 |

Watch only: TVS2200 (DK 390, back from 0; JLC 683), L11nH 276, L15nH 420,
HV5.6pF, ANT2450 (LCSC shop 0, JLC 307), C4u7_50 (DK 4,043, 61 wk).
No part is marked last-time-buy.

### Cost per board (DigiKey prices, same method as 17 Oct)

- **$68.22 at 100 boards, $87.26 at 10 boards** (sum of quantity times the
  DigiKey price at 100 or 10; list price for the lines that are out of
  stock; $1.17 placeholder for the 8.1 nH). On 17 Oct: $58.39 at 100.
- Buying the second sources above for the lines that are 0 at DigiKey
  makes it **$70.87 at 100** and $91.02 at 10.
- The +$9.83 is mostly the 19 Oct design changes, not prices: two
  MAX17608 (+$8.46), the LFCG-1000+ in place of the LFCN-1000+ (+$3.66),
  the snubber, zener and eFuse parts; less the parts removed since 17 Oct.
  Price moves on lines that exist in both audits add only $0.82 (the TDK
  47 uF at $0.35 and the ECS -AP oscillator at $1.67 are the largest).
- Largest lines: MAX17608 pair $8.46, QPA9510 $7.46, SX1262 $6.86,
  LFCG-1000+ $6.56, nRF52840 $5.49.
- `plan.md` still says $58 / $76: update it when the owner has seen this.

## Exceptions to the −40 °C rule (E1)

These are mechanical parts:

- **Omron/Aratas B3U buttons:** −25 to +70 °C.
- **JST PH/GH/SH connectors:** −25 to +85 °C.

None of them is in the RF or power path. Cairn's environment is hot, not
cold, and the 60 °C sealed box is inside every one of these ratings. No
−40 °C part that fits was found. This is recorded for the owner, and is
also in `docs/plan.md`.
