# Mesh Radio v1: RF simulations

These studies check the radio side of `src/circuit.py`: the LoRa transmit
and receive chains, the clocks and the Bluetooth match. Each check runs
over part tolerances and six temperatures (−40, −20, 0, 25, 60 and 85 °C).

```
tools/kd python3 sim/rf/run.py           # studies 1-7, from mesh-radio/v1, in the pinned container, ~20 s
tools/kd python3 sim/rf/followup.py      # 19 Oct follow-up: R41, antenna-missing heating, 6f-10f fixes, ~1 min
tools/kd python3 sim/rf/run.py --quick   # 200 Monte Carlo runs instead of 1000
tools/kd python3 sim/rf/design_lpf.py    # re-derives the harmonic-filter values (~30-60 min)
```

- **Outputs.**
  - `run.py` writes `results.txt`, with a summary at the end, and the plots
    `tx_chain.png`, `monte_carlo.png`, `pad.png`, `receive.png`,
    `frequency.png`, `bluetooth.png` and `open_antenna.png`.
  - `followup.py` writes `followup.txt`, `followup_heating.png` and
    `followup_filters.png`.
- **Tools.** Plain numpy nodal analysis (`rflib.py`), plus scipy for the
  fits. Nothing is installed.
- **Where the values come from.** Every passive value and part number is
  read from `src/circuit.py` and `src/parts.py` (`rfboard.py`), so the
  results follow the circuit. The results here are for the board as
  committed in 6cb9185, which already includes the 18 Oct fixes.
- **Not yet routed.** Traces are 1–2 mm 50-ohm lines until layout.
  `followup.py` sweeps them, because two reflective filters with a switch
  between them interact.

## Verdict: board as committed (6cb9185)

Criteria are stated in `results.txt` and `followup.txt` before each study.

| # | Check | Result | Key numbers |
|---|---|---|---|
| 1 | Loss from the PA output to the U.FL | PASS | 1.12 dB (filter 0.21, switch 0.30, LFCN 0.67). Monte Carlo: 34.8–35.2 dBm at VPA 4.0 V and 33.9–34.3 dBm at 3.6 V. |
| 1 | Return loss at every interface | PASS | Worst 17.2 dB. The PA load is 27.2 dB and the U.FL 23.9 dB. |
| 1/2 | Harmonics 2f–5f, 30/35 dBm, 2.15/6 dBi, over tolerance and temperature | PASS | Worst margin 14.1 dB. 3f, 4f and 5f are in FCC restricted bands (−41.2 dBm EIRP). |
| C | Harmonics 6f–10f at 35 dBm, 6 dBi (PA at −45 dBc assumed) | **FAIL** | −7.1 dB at the worst trace layout (9f). The LFCN-1000+ re-enters above 5.5 GHz with only 15–19 dB of rejection. |
| C | Default US setting (30 dBm, 2.15 dBi) | MARGINAL | All harmonics pass. The worst margin is 6.9 dB at 2 mm traces and 2.9 dB at the worst layout. |
| 2 | Harmonic-filter notches | MARGINAL (by design) | The notches sit at 1.39 and 2.30 GHz, chosen for low loss. The LFCN carries 2f–5f. |
| 3 | Pad, R41 = Vishay RCS080568R0FKEA | PASS | The worst resistor is at 41 % of its 85 °C rating at +22 dBm and 51 % at +23 dBm. Vishay RCS is taken as 0.4 W at 70 °C, falling to 0 W at 155 °C. |
| 4 | Receive vs a RAK4631 | PASS | 4.9 dB better with the LNA on, 2.1 dB worse in bypass. This confirms the plan's figures. |
| 5 | LoRa frequency offset / 32 MHz crystal | PASS / MARGINAL | The LoRa offset is 8.6 kHz against limits of 31–62 kHz. The crystal's worst case is 42–47 ppm against Nordic's 40 ppm. |
| 6 | Bluetooth match, before layout | PASS | 100 % yield with the ±0.05 pF 0.8 pF part. |
| 7 | PA load with the antenna missing | PASS | 9.1:1, inside Qorvo's 10:1 rating at 3.6 V. |
| 7 | **SKY13330 with the antenna missing, 3.6 V** | **FAIL** | 34.6 V peak (50-ohm-source model) to 50.7 V (saturated-PA model), against the 31.6 V that its +40 dBm rating makes in 50 Ω. The lower-loss filter lets more of the reflection back than the 18 Oct design did. |
| B | L15 heating with the antenna missing, 1 s bursts at 25 % duty, 60 °C | PASS at 2.7 and 3.6 V, FAIL at 4.0 V | 91 °C, 116 °C and 129 °C against Murata's 125 °C. A single burst stays at 106 °C or less, and the solder stays at 86 °C or less. |
| B | L18 heating, the same conditions | PASS | 87 °C or less. |

## Proposed changes (not applied to `src/`)

| Change | Fixes | Result |
|---|---|---|
| **FL1: LFCN-1000+ → Mini-Circuits LFCG-1000+.** Same function, but a new footprint: 0805, 8 pads, instead of the 1206 4-pad. DigiKey 3157-LFCG-1000+CT-ND (989 in stock); LCSC C4989745 (105). | 6f–10f | Worst layout +7.7 dB at 35 dBm / 6 dBi and +16.6 dB at 30 dBm / 2.15 dBi. Loss is unchanged at 1.10 dB. |
| **Firmware: TEMP_ALERT back-off** to 2.7 V at a board temperature of about 60 °C or more at VPA 3.6 V, and about 40 °C or more at 4.0 V. | LFCG power rating (5.5 W at 25 °C, falling to 1 W at 125 °C; no pulse rating) | 69 % of rating at 3.6 V and 60 °C. At 4.0 V it reaches 84 % at 60 °C and 118 % at 85 °C. At 1 W it is 39 % even at 85 °C. |
| **Missing-antenna detector:** a ~10 mm printed line coupled to the U.FL feed, a BAT15-02EL diode (DigiKey BAT1502ELE6327XTMA1CT-ND, 69,528; LCSC C533619, 714), 49.9 Ω (311-49.9LRCT-ND; C87044) and 1 nF (already on the BOM), into a spare nRF analog pin. | Switch voltage, L15 heating | It reads the reflected wave, so it sees a missing antenna on any cable length, with 8 dB or more of contrast against a VSWR-2 antenna. Firmware cuts VPA within about 1 ms. This is a first-order estimate, not EM-simulated. |
| **Until the detector exists:** licensed ceiling 3.1 V, not 3.6 V (about 33.3 dBm, 2.1 W). | Switch voltage | 95 % in the 50-ohm-source model. The saturated-PA model still exceeds it. |

**Second sources found for this follow-up:**

- **LCSC.** No in-stock equivalent of LQW2BAN3N2/3N6 with the same or
  better current and Q from a non-Chinese maker. The "XR0806SQ/XR0908SQ"
  parts are unbranded copies of Coilcraft's. Buy the LQW2BAN parts at
  DigiKey and consign them to JLC.
- **DigiKey.** GQM1875C2E1R3BB12D is not stocked at DigiKey; use Johanson
  **QSCP251Q1R3B1GV001T** (250 V, ±0.1 pF, 0603), 712-QSCP251Q1R3B1GV001TCT-ND,
  40,828 in stock.

## Models and sources

| Part | Model | Source |
|---|---|---|
| GJM / GQM capacitors | C with ESR rising with √f, plus ESL. ESL: 0402 0.30, 0603 0.40, 0805 0.50 nH, plus 0.15 nH via (assumed). | Murata GJM catalogue C-29-C, maximum-ESR table. GQM is given the same limits (assumed). Temperature: C0G 0±30 ppm/°C. |
| LQW15AN / LQW18AN / LQW2BAN inductors | L with R(f) from the minimum Q at its test frequency, scaled by √f, and a parallel C from the minimum SRF. | Murata reference specs (LQW15AN, LQW18AN); DigiKey listing for LQW2BAN. Temperature: +25..+125 ppm/°C (assumed). |
| Inductor thermal data | Two-node RC. L15: 35 / 65 K/W and 0.016 / 0.25 J/K. L18: 200 / 220 K/W and 0.001 / 0.08 J/K. | **Estimated** from Murata's rated current (20 °C rise) and the parts' size; sensitivity in `followup.txt`. |
| LFCN-1000+, LFCG-1000+ | Lumped models fitted to Mini-Circuits' typical tables. The tables set the magnitude and the models give the phase. LFCN above 7 GHz: 18.6 dB **assumed**. | Mini-Circuits data sheets (`lfcn.py`). |
| SKY13330 | Loss 0.30/0.35 dB (typ/max) below 1 GHz, rising with frequency; 20 dB return loss; reflective short on the isolated port. | Skyworks 201407E. Its harmonics are not published: −65/−60 dBc for 2f/3f at +35 dBm assumed. |
| QPA9510 | Saturated current source with a voltage clamp at the die, through assumed bond wires; calibrated to 35.4 dBm on the EVB network. | Qorvo data sheet, 23 Jun 2025: 2f −28.5 dBm and 3f −26.6 dBm at the EVB; 10:1 ruggedness at 3.6 V. 4f–10f −45 dBc **assumed**. |
| BGA7L1BN6, SX1262, TCXO, crystal, chip antenna | As in `results.txt`. | Infineon rev 3.1, Semtech DS rev 1.2, ECS, Abracon, Johanson data sheets. |

Harmonic verdicts use the 50-ohm insertion loss of the chain, which is how
Qorvo measured its harmonics. The PA-die-source result is printed for
sensitivity: above 5 GHz it is 10–35 dB worse with reflective filters, but
it rests on guessed values inside the PA package.

## What this does not prove

- **The layout.** Trace lengths, vias and coupling come from the routed
  board. Re-run with extracted lengths, and EM-model the Bluetooth antenna
  and the detector's coupler.
- **Anything above 7 GHz.** The PA's harmonics above 3f, the switch's own
  harmonics and the LFCN above 7 GHz are assumptions. **Measure to 10 GHz
  with a spectrum analyser.**
- **PA behaviour into a missing antenna.** Two simple models bracket it.
  The switch and LFCN ratings into an open load are not published. Only a
  bench test settles it.
- **Drift during a packet.** A 6 W PA shares the board with the TCXO.
  Keep the TCXO thermally away from the PA (Semtech AN1200.37).
