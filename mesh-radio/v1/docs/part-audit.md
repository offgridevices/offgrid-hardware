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
are still to be filled in:

- ECS-TXO-20CSMV4-320-**AP**-TR. It replaces the -AY code, which is rated
  only to −30 °C. DigiKey has 2,765; LCSC has 0.
- Murata GRM21BR61C226ME44L, 22 µF 16 V. It replaces the Samsung 25 V part,
  which is obsolete at DigiKey.
- TI LM66100DCKR (LCSC C2869734).
- Rohm UDZVTE-174.7B (C209560).
- Yageo 287 k (C327358).

## Exceptions to the −40 °C rule (E1)

These are mechanical parts:

- **Omron/Aratas B3U buttons:** −25 to +70 °C.
- **JST PH/GH/SH connectors:** −25 to +85 °C.

None of them is in the RF or power path. Cairn's environment is hot, not
cold, and the 60 °C sealed box is inside every one of these ratings. No
−40 °C part that fits was found. This is recorded for the owner, and is
also in `docs/plan.md`.
