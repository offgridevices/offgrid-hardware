# Mesh Radio v1: RF simulations

These studies check the radio side of `src/circuit.py`: the LoRa transmit
and receive chains, the clocks and the Bluetooth match. Each check runs
over part tolerances and six temperatures (−40, −20, 0, 25, 60 and 85 °C).

```
tools/kd python3 sim/rf/run.py           # from mesh-radio/v1, in the pinned container, ~20 s
tools/kd python3 sim/rf/run.py --quick   # 200 Monte Carlo runs instead of 1000
tools/kd python3 sim/rf/design_lpf.py    # re-derives the proposed harmonic-filter values (~30-60 min)
```

- **Outputs.** `results.txt` holds every number, with a summary at the end.
  The plots are `tx_chain.png`, `monte_carlo.png`, `pad.png`,
  `receive.png`, `frequency.png`, `bluetooth.png` and `open_antenna.png`.
- **Tools.** Plain numpy nodal analysis (`rflib.py`), plus scipy for two
  fits. There is no scikit-rf and nothing is installed.
- **Where the values come from.** Every passive value and part number is
  read from `src/circuit.py` and `src/parts.py` (`rfboard.py`), so these
  results follow the circuit. Nothing in `src/` was changed. The proposed
  fixes are applied as overrides in `run.py`, in the `fix_overrides()`
  function.
- **Not yet routed.** The board has no layout, so traces are 1–2 mm
  50-ohm lines (`rfboard.LINES`). Re-run the studies with the routed lengths.

## Verdict

Criteria are stated in `results.txt` before each study.

| # | Check | Result | Key numbers |
|---|---|---|---|
| 1 | Loss from the PA output to the U.FL | MARGINAL | 1.44 dB worst in band (filter 0.40, switch 0.30, LFCN 0.67). Monte Carlo: 1.37–1.99 dB, so 34.3–34.9 dBm (2.7–3.1 W) at VPA 4.0 V, not quite 35 dBm. |
| 1 | Return loss at every interface | PASS | Worst 17.8 dB. The PA load is 17.8 dB, the U.FL 20.3 dB, and the pad as seen by the SX1262 30.8 dB. |
| 1 | Harmonics 2f–5f, 30 and 35 dBm, 2.15 and 6 dBi | PASS | At 35 dBm into 6 dBi, the worst margin is 11.1 dB (at 5f). 3f, 4f and 5f all fall in FCC restricted bands, where the limit is −41.2 dBm EIRP. 2f has 79 dB of margin. Part 97 (−43 dBc) has 50 dB or more. |
| 1 | Harmonics 6f–10f | RISK, unverified | The LFCN-1000+ lets 5.5–7 GHz back through (only 15–19 dB of rejection, data sheet), and 8f–10f are in restricted bands. The model margin is about −7 dB at 8f, but that rests on an assumed PA level and on models used past their data. **This must be measured to 10 GHz.** |
| 2 | Monte Carlo, harmonics and PA load | PASS | 100 % yield at every temperature. Worst harmonic margin 4.5 dB, worst PA return loss 12.8 dB. |
| 2 | Harmonic-filter notch placement | MARGINAL | Notches sit at 1.70 and 2.43 GHz (ideal L/C values give 1.82 and 2.78). 99 % of runs fall at 1.63–2.15 and 2.29–2.60 GHz, so they miss both harmonic bands. The LFCN does most of the rejection. |
| 3 | Pad, +20 dBm (firmware cap), 85 °C | MARGINAL | The first 68 R takes 74 mW, which is 72 % of its 85 °C rating (91 % with +1 dB of SX1262 spread). |
| 3 | Pad, +22 dBm, 85 °C | FAIL | 118 mW, or 114 % of its rating (Yageo: full rating to 70 °C, linearly to 0 W at 155 °C). |
| 3 | Pad attenuation over tolerance | PASS | 15.80–16.09 dB. The PA input reaches +5.2 dBm at +22 dBm drive (absolute maximum +13). |
| 4 | Receive, LNA on, vs a RAK4631 | PASS | 4.9 dB better typical, 3.8 dB with every part at its worst. The plan's ~4.5 dB is confirmed. LongFast −135.3 dBm vs −130.5 dBm, and SF12/125 kHz −140.9 dBm. |
| 4 | Receive, LNA bypassed, vs a RAK4631 | PASS | 2.1 dB worse typical, 3.4 dB worst case. The plan's ~2.5 dB is confirmed. |
| 5 | LoRa frequency offset between two nodes | PASS | 8.6 kHz worst pair after 10 years, against limits of 31.25 kHz (SF12/125) and 62.5 kHz (LongFast). |
| 5 | 32 MHz crystal for Bluetooth | MARGINAL | Worst case 42 ppm new and 47 ppm aged, against 50 ppm (Bluetooth) and 40 ppm (Nordic). 12 ppm of that comes from load-capacitance uncertainty. |
| 6 | Bluetooth match, tolerances, before layout | MARGINAL | 98.9 % of runs meet 9.5 dB return loss. The 0.8 pF ±0.1 pF part is the most sensitive. |
| 7 | PA load with the antenna missing | PASS | 9.7:1 at the PA, against Qorvo's 10:1 rating at 3.6 V. **The firmware's 3.6 V ceiling is needed and correct.** 4.0 V is outside the rating. |
| 7 | SKY13330 with the antenna missing, 3.6 V / 4.0 V | MARGINAL / FAIL | 30.0 V peak (95 %) at 3.6 V and 33.4 V (106 %) at 4.0 V, against the 31.6 V that its +40 dBm absolute maximum makes in 50 Ω. Both are above its 0.1 dB compression point. |
| 7 | LFCN-1000+ with the antenna missing | unverified | 35 V (50-ohm source model) to 63 V (saturated-PA model) at 3.6 V. Mini-Circuits publishes no voltage rating; its 10 W rating corresponds to 31.6 V. |
| 7 | Inductor RF heating at 3 W | FAIL | The output-match 3.6 nH (0603), the filter's 5.1 nH (0402) and 4.7 nH (0603) dissipate 112–266 % of the heat their rated current allows (typical Q; matched antenna). With the antenna missing it is several times that. |
| 7 | LNA and SX1262 input during transmit | PASS | LNA input 0.4 dBm worst (absolute maximum +25). SX1262 RFI −1.8 dBm (absolute maximum +10). This relies on firmware putting the LNA in bypass during TX, which RadioLib does. |

## Recommended changes (proposals, re-checked in `results.txt` → FIXES)

| Change | What it fixes | Re-checked result |
|---|---|---|
| **R41** (the first 68 R of the pad): RC0805FR-0768RL → **Panasonic ERJ-P06F68R0V**. Same value and footprint, 0.5 W. DigiKey 10-ERJ-P06F68R0VCT-ND, 19,204 in stock. | Pad (study 3) | 29 % of rating at +22 dBm, 85 °C |
| **L15** (3.6 nH output match): LQW18AN3N6D00D → **Murata LQW2BAN3N6J00L**. Same value, 0805, 2 A, Q 75. DigiKey product 6799467, 1,935 in stock. | Heating (study 7) | 53 % of rated heating with a matched antenna (typical Q). With the antenna missing, the saturated-PA model still puts about 4× its rated heating into this inductor, so the open-antenna bench test applies. |
| **Harmonic filter re-tune**, same 7 parts. Shunt 2.0 pF, then 3.2 nH ∥ 3.6 pF, shunt 1.3 pF, 3.2 nH ∥ 1.3 pF, shunt 0.9 pF. Both inductors are **Murata LQW2BAN3N2J00L** (0805, 3.8 A, Q 95; DigiKey product 6799466). The capacitors are GQM1875C2E 250 V 0603: 2R0/3R6/1R3/1R3/R90 BB12D. | Heating, loss, notches (studies 1, 2, 7) | Loss 1.12 dB (was 1.44), so 34.8–35.2 dBm at 4.0 V. 2f–5f yield 100 %, worst margin 4.9 dB. Inductors at 27 % or less of rated heating. The 6f–8f model margin is no better (−8.6 dB, against −6.6 dB for the drawn values). |
| **C39** (Nordic 0.8 pF): GJM1555C1HR80BB01D → **GJM1555C1HR80WB01D** (±0.05 pF). DigiKey 490-11253-1-ND. | Bluetooth (study 6) | 100 % yield before layout |
| **Firmware:** keep the 3.6 V licensed ceiling, and keep 4.0 V behind an explicit "antenna fitted" opt-in. | Switch, PA (study 7) | — |
| **Bench:** spectrum-analyser sweep to 10 GHz at 30 and 35 dBm. Open-antenna test at 3.6 V with short packets first. Measure the 32 MHz frequency and retrim the 12 pF crystal capacitors if it is more than 10 ppm off. | 6f–10f, LFCN and switch stress, crystal | — |

**Caveats on these changes:**

- **Harmonic-filter values.** They come from `design_lpf.py`, which runs the
  whole chain with the same models. Like the drawn values, they are a
  starting point for tuning on the network analyser.
- **Stock.** GQM1875C2E2R0, 1R3 and R90 are active at DigiKey, but no stock
  was shown on 19 Oct 2026. GQM1875C2E3R6BB12D had 12,651 in stock. Check
  all of them before ordering.
- **Not fixed: the 6f–10f risk.** If the bench shows it, the only part
  found without a stop-band re-entry is the Mini-Circuits **LFCG-1000+**
  (0805; 37–60 dB rejection from 1.75 to 10 GHz; DigiKey
  3157-LFCG-1000+CT-ND). It is rated 5.5 W at 25 °C, falling to about
  2.8 W at 85 °C, so at full 3 W it only suits the 1 W US mode or a cool
  board.
- **Not fixed: the switch.** No drop-in SPDT switch with more headroom was
  found in production at DigiKey.

## Models and sources

| Part | Model | Source |
|---|---|---|
| GJM / GQM capacitors | C with ESR rising with √f, plus ESL. ESL: 0402 0.30, 0603 0.40, 0805 0.50 nH, plus 0.15 nH via (assumed). | Murata GJM catalogue C-29-C, maximum-ESR table. GQM is given the same limits (assumed). Temperature: C0G 0±30 ppm/°C. |
| LQW15AN / LQW18AN / LQW2BAN inductors | L with R(f) taken from the minimum Q at its test frequency, scaled by √f, and a parallel C taken from the minimum SRF. | Murata reference specs JELF243A-0050AC-01 (LQW15AN) and LQW18AN_00; DigiKey listing for LQW2BAN. Temperature: +25..+125 ppm/°C (Coilcraft's range, assumed). |
| 0908SQ-8N1 | Q 100, SRF 5 GHz, ±5 % | **Assumed.** The Coilcraft site was unreachable and DigiKey does not stock the part. |
| RC0805 resistors | R with 0.7 nH | Yageo RC series: 0.125 W to 70 °C, 0 W at 155 °C, ±100 ppm/°C (distributor copies of the data sheet). |
| LFCN-1000+ | 7-section lumped model fitted to Mini-Circuits' typical table (REV. R, 50 MHz–7 GHz). Its rejection is never credited above the table. | Mini-Circuits data sheet, `lfcn.py`. No .s2p file was found. |
| SKY13330 | Loss 0.30/0.35 dB (typ/max) below 1 GHz, rising with frequency; 20 dB return loss; reflective short on the isolated port. | Skyworks 201407E, Table 3. Its harmonics are not published: −65/−60 dBc for 2f/3f at +35 dBm assumed. |
| QPA9510 | Saturated current source with a voltage clamp at the die, through assumed bond wires (0.25 nH, 6 pF, 2F0 trap 4.6 nH). Calibrated to 35.4 dBm on the EVB network. | Qorvo data sheet, 23 Jun 2025. 2f −28.5 dBm and 3f −26.6 dBm at the EVB output; 10:1 ruggedness at 3.6 V and +4.5 dBm in. 4f–10f −45 dBc **assumed**. Output scales as VPA². |
| BGA7L1BN6 | NF 0.75/1.3 dB, gain 13.6/12.1 dB; bypass NF 1.8/2.8 dB, loss 2.2/3.2 dB; input max +25 dBm | Infineon rev 3.1, 25 °C only. Temperature behaviour **assumed** (noise ∝ T, −0.01 dB/°C). |
| SX1262 | NF 6.03 dB including Semtech's balun, from −137 dBm at SF12/125 kHz. FERR_L ±25 % of BW and ±50/100/200 ppm. RF input absolute maximum +10 dBm. | Semtech DS rev 1.2, Table 3-8. The RAK4631 is the same plus 1 dB (owner's figure). |
| TCXO | ±1.0 ppm at 25 °C, ±0.5 ppm over −40..105 °C, ±1 ppm in year 1 | ECS-TXO-20CSMV4 data sheet (AP option). 10-year ageing ±3 ppm assumed. |
| 32 MHz crystal | ±10 ppm at 25 °C, ±20 ppm over −40..85 °C (code D1X), ±2 ppm/yr; C0 2 pF or less | Abracon ABM11W data sheet. Motional C1 of 1.3–2.5 fF (Semtech's range) and nRF pin capacitance of 3–4 pF are assumed. |
| 2450AT18A100 | Series RLC whose 2.442 GHz impedance is what Johanson's EVB tee matches; 180 MHz 2:1 bandwidth (assumed) | Johanson data sheet. **Pre-layout only.** |

## What this does not prove

- **The layout.** Trace lengths, vias and coupling all come from the
  routed board. Re-run with extracted lengths, and EM-model the
  Bluetooth antenna.
- **Anything above 7 GHz.** Harmonics 8f–10f are beyond any data here.
  The PA's 4f–10f levels and the switch's own harmonics are assumptions.
- **PA behaviour into a missing antenna.** Two simple models bracket it.
  Only a bench test settles it.
- **PA output power vs temperature, and its true load-pull.** Neither is
  published.
- **Drift during a packet.** A 6 W PA shares the board with the TCXO.
  Semtech AN1200.37 says to keep them thermally apart.
