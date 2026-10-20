# Mesh Radio v1: RF simulations

These studies check the radio side of `src/circuit.py`: the LoRa transmit
and receive chains, the clocks, the Bluetooth match and the missing-antenna
detector. Each check runs over part tolerances and six temperatures (−40,
−20, 0, 25, 60 and 85 °C).

```
tools/kd python3 sim/rf/run.py           # studies 1-8, from mesh-radio/v1, in the pinned container, ~70 s
tools/kd python3 sim/rf/run.py --quick   # 200 Monte Carlo runs instead of 1000
tools/kd python3 sim/rf/coupler.py       # field solve of the detector coupler (sizing, 19 Oct)
tools/kd python3 sim/rf/followup.py      # 19 Oct follow-up (LFCN-era board), kept as a record; superseded, see below
tools/kd python3 sim/rf/design_lpf.py    # re-derives the harmonic-filter values (~30-60 min)
```

- **Outputs.** `run.py` writes `results.txt` (every number, criteria
  before each study, a summary at the end) and the plots `tx_chain.png`,
  `monte_carlo.png`, `pad.png`, `receive.png`, `frequency.png`,
  `bluetooth.png`, `open_antenna.png`, `heating.png` and `detector.png`.
- **Tools.** Plain numpy nodal analysis (`rflib.py`), scipy for the fits
  and the diode solve, and ngspice (in the container) to cross-check the
  detector.
- **Where the values come from.** Every passive value and part number is
  read from `src/circuit.py` and `src/parts.py` (`rfboard.py`). The
  detector coupler's length and gap, the antenna-line lengths and the ESD
  shunt's position are read from `src/layout.py`. The firmware thresholds
  are read from `firmware/variant/variant.h`.

## What changed on 20 Oct

The studies were last run on 6cb9185, before two circuit changes. `run.py`
and `rfboard.py` now model the board as it is in `src/`:

1. **FL1 is the LFCG-1000+.** It uses `followup.py`'s fitted model
   (`lfcn.G_FIT`): pad 8 is the input and pad 4 the output, checked against
   `circuit.py`. Harmonic rejection is capped at Mini-Circuits' typical
   table, which runs to 10 GHz, so 9f and 10f are no longer extrapolated.
   Its data-sheet maximum loss, 1.8 dB, is reported alongside the typical
   loss.
2. **The detector is part of the antenna line.** The antenna line runs as
   `layout.py` draws it: filter → 0.9 mm → a 5.5 mm coupled run → 1.6 mm →
   U.FL. The run uses 0.17 mm lines with a 0.10 mm gap; its even- and
   odd-mode parameters come from `coupler.py`'s field solve, as a new 4-port
   `rflib.CoupledLine`. The 47 nH ESD shunt sits inside the run, 0.6 mm from
   its U.FL end. The coupled line ends in 1 mm stubs: one to the 49.9 R, the
   other to the BAT15 (0.4 nH, 6–8 Ω, 0.2 pF), with the 1 nF and 100 k at
   the cathode. The detector is present in every study, transmit and
   receive.
3. **Mismatches found and fixed in the model:**
   - The model still used the LFCN-1000+ and its 1206 pinout.
   - The detector was missing, and the ESD shunt was placed at the U.FL.
   - The trace lengths were assumed at 2 mm. They are now the placed values:
     PA_TX 1.1 mm and switch-to-filter 2.1 mm, plus the antenna section
     above.
   - `rflib` could not read the VPA bulk capacitors' new TDK part number
     (C3216X7S0J476M160AC), and the model crashed on it.
   - Text in studies 2, 3 and 6 still described the old parts. It now says
     LQW2BAN ±5 %, R41 = Vishay RCS 0.4 W and the 0.8 pF part at ±0.05 pF.

   Every other RF part value and topology in `rfboard.py` matches
   `circuit.py`. That covers the pad (68 AS / 150 / 68 R), the PA match
   (8.1 nH, 15 pF, 10 pF, 3.6 nH LQW2BAN, 5.6 pF, 47 pF), the LPF (2.0, 3.2
   nH‖3.6, 1.3, 3.2 nH‖1.3, 0.9 pF), the 1.5 pF 2F0 trap, the SKY13330
   ports, the receive chain and the Bluetooth pi and tee.
4. **The superseded `fixes()` section is removed.** It re-applied the 18 Oct
   fixes, which are already in `src/`. Its useful rows moved into studies 7
   and 7b. Studies 7b (transient inductor heating, from `followup.py`) and
   1f (harmonics over 108 trace layouts, from `followup.py`) are now part
   of `run.py`.
5. **Study 8 is new: the detector against the firmware.**

## Verdict: board as in src/ on 20 Oct (LFCG-1000+, detector fitted)

| # | Check | Result | Key numbers |
|---|---|---|---|
| 1 | Loss from the PA output to the U.FL | PASS | 1.13 dB (LPF 0.21, switch 0.30, LFCG 0.67, coupler section 0.08). 35 dBm at 4.0 V gives 35.2 dBm at the U.FL. With the LFCG at its 1.8 dB data-sheet maximum the loss is 2.27 dB. |
| 1 | Return loss at every interface | PASS | Worst 16.3 dB. The PA load is 21.3 dB and the U.FL 22.2 dB. |
| 1 | Harmonics 2f–5f, 30 and 35 dBm, 6 dBi | PASS | Worst margins 23.6 and 17.0 dB, both at 5f. |
| 1 | Harmonics 6f–10f, 35 dBm, 6 dBi, layout as placed | PASS | Worst margin 13.7 dB, at 6f. This is with the PA at −45 dBc, which is assumed. The 19 Oct board failed this check by 7.1 dB. |
| 1f | Harmonics 2f–10f, worst of 108 trace layouts | PASS | 6.8 dB at 4f for 35 dBm / 6 dBi, and 15.7 dB for the US default of 30 dBm / 2.15 dBi. |
| 2 | Monte Carlo, harmonics and PA match | PASS | 100 % yield; worst margin 13.5 dB. |
| 2 | Monte Carlo TX loss (is 3 W reachable?) | MARGINAL | 47 % of boards at 1.3 dB or less; loss 1.13–1.51 dB, giving 34.8–35.2 dBm at 4.0 V. This uses an assumed LFCG spread of ×1.0–1.5. |
| 2 | LPF notch placement | MARGINAL (by design) | Notches at 1.39 and 2.30 GHz. The LFCG carries 2f–5f. |
| 3 | Pad power at +20 and +22 dBm, 85 °C; pad attenuation | PASS | Worst resistor 26 % and 41 % of its rating; attenuation 15.80–16.09 dB. |
| 4 | Receive vs a RAK4631 | PASS | 4.8 dB better with the LNA on (3.0 dB with every part at its worst, including the LFCG at 1.8 dB). 2.1 dB worse in bypass. |
| 5 | LoRa frequency offset / 32 MHz crystal | PASS / MARGINAL | 8.6 kHz against a 31.2 kHz limit. The crystal's worst case is 42 ppm new and 47 ppm aged. |
| 6 | Bluetooth match, before layout | PASS | 100 % yield; worst RL 9.6 dB. |
| 7 | **PA load with the antenna missing** | **FAIL** | 10.5:1 at the worst phase, against Qorvo's 10:1 rating at 3.6 V. The LFCG reflects more than the LFCN did (9.1:1 on 19 Oct). Only the detector cut-off limits how long the PA sees it. |
| 7 | **SKY13330 with the antenna missing, 2.7 V** | **FAIL** | Model A 40.8 V (129 %), model B 26.8 V (85 %). At exactly 30 dBm (the US cap): **A 30.5 V (97 %), B 20.2 V (64 %)**. The limit is 31.6 V, what +40 dBm makes in 50 Ω. |
| 7 | **SKY13330 with the antenna missing, 3.6 V** | **FAIL** | **Model A 54.4 V (172 %), model B 35.7 V (113 %)**. |
| 7 | **SKY13330 with the antenna missing, 4.0 V** | **FAIL** | Model A 60.5 V (191 %), model B 39.6 V (125 %). |
| 7 | LFCG port voltage with the antenna missing | (no rating) | 47 / 63 / 70 V peak at 2.7 / 3.6 / 4.0 V, against the 23.5 V its 5.5 W rating makes in 50 Ω (16.7 V at 85 °C). |
| 7 | Inductor RF heating (steady), 3.6 and 4.0 V | MARGINAL | Matched: 52 % and 65 % of rated-current heating. Antenna missing: L15 437 % and 540 %. |
| 7 | LNA and SX1262 input during transmit | PASS | LNA 5.5 dBm (abs max +25); SX1262 3.3 dBm (abs max +10). |
| 7b | L15, antenna missing, 60 °C, 1 s bursts at 25 % duty, no cut-off | PASS at 2.7 and 3.6 V, **FAIL at 4.0 V** | 94, 121 and 135 °C against a 125 °C limit. With the 0.75 ms cut-off it rises 0.1 °C or less per event. |
| 7b | L18, the same conditions | PASS | 101 °C or less. |
| 8 | **Detector against the firmware thresholds** (typical BAT15, as designed) | **FAIL** | A missing antenna reads up to 80 mV **below** the threshold in model A, at some cable lengths, at both 30 and 35 dBm and every temperature. Model B reads at least 178 mV above it. A VSWR-2 antenna reads at least 113 mV below it in both models. |
| 8 | Detector over BAT15 spread, EG, ±0.02 mm gap and ±1 dB of power | FAIL | Worst −186 mV (gap 0.12 mm). A 0.08 mm gap passes, with margins of +19 / +12 mV. |
| 8 | **Detector with the 1 nF / 100 k as placed** | **FAIL** | C82 and R52 sit 21 mm from the diode, by the nRF52840. Worst margin −23 mV. Move them to D9 in the layout. |
| 8 | Detector parts with the antenna missing | **FAIL** | The BAT15 sees a reverse peak of 5.1 / 5.7 V in model A at 3.6 / 4.0 V (3.5 / 3.9 V in model B), against its 4 V VR maximum. The 49.9 R takes up to 85 mW against its 63 mW rating, but only for 0.75 ms when the cut-off works. |

### What still fails, and why

- **SKY13330 voltage with the antenna missing.** The switch sees the voltage
  as soon as the RF starts, so the detector cannot prevent it.
  - At 3.6 V the peak is 35.7 V (model B, a 50-ohm source) to 54.4 V
    (model A, a saturated PA). Both are above the 31.6 V that the switch's
    +40 dBm rating makes in 50 Ω.
  - In US mode (VPA 2.7 V, driven to 30 dBm) the peak is 20.2 V (model B)
    to 30.5 V (model A). That is under the rating, but model A leaves only
    3 % of margin.
  - At 2.7 V with the PA saturated (32.5 dBm) model A reaches 40.8 V.

  Skyworks publishes no voltage or VSWR rating, so only a bench test into an
  open settles it.
- **What the 0.75 ms firmware cut-off does and does not protect:**
  - *It does protect, when it trips,* against everything that takes time.
    That covers L15 and L18 heating (0.1 °C or less per event against
    94–135 °C without it), the LFCG's power rating, the 49.9 R and the PA's
    exposure to more than 10:1. It cuts the amplifier within 0.75 ms and
    retries at 1 W after 30 s, doubling up to 600 s.
  - *It does not protect against* the peak voltage on the SKY13330, the LFCG
    or the BAT15, which is there from the first RF cycle of every packet and
    every 1 W retry.
  - *It does not protect against* an antenna lost mid-packet, because it
    samples only once, 750 µs into each packet; the packet then runs to its
    end, up to ~5 s.
  - *It does not protect against* packets whose modelled power is below
    27 dBm, which are not checked.
  - *It does not protect against* the cases it fails to detect. In model A a
    missing antenna on some cable lengths reads below the threshold, so it
    never trips; the steady-heating and 4.0 V L15 FAIL rows then apply in
    full.
- **Detector thresholds.** `coupler.py` gave 6.7–7.5 dB of contrast between
  a missing and a VSWR-2 antenna, but it fed the coupler from an ideal
  50-ohm source. In the full chain the wave the open antenna returns
  bounces off the filter, the switch and the PA and comes back, so the
  forward wave varies with cable length:
  - With a saturated PA (model A) the lowest missing reading is only 2.0 dB
    above the highest VSWR-2 reading.
  - The firmware's thresholds (350 / 730 mV, +1.4 mV/°C) sit above that
    window.
  - Thresholds centred in it would be **V30 272 mV, V35 582 mV and
    +1.15 mV/°C**. That gives ±37 mV with a typical BAT15. It still misreads
    with a diode at the data-sheet VF limits, or with 1 dB of error between
    the firmware's power model and the real power.
  - The robust fix is a circuit change, not a threshold: read the forward
    wave too. A second BAT15 at the coupler's filter end, behind the 49.9 R,
    into a spare analog pin, lets firmware compare reflected with forward.
    That cancels PA-power error, cable-length effects and most of the diode
    spread and temperature drift.
  - A tighter gap (0.08 mm) also helps. Thresholds must be set from bench
    data in any case.
- **The BAT15's reverse voltage.** The peak exceeds the 4 V maximum when the
  antenna is missing at 3.6 and 4.0 V. Options are a weaker coupling, a
  series resistor, or a detector diode with a higher reverse rating; none of
  these was checked here.
- **The PA's mismatch rating.** 10.5:1 is just past Qorvo's 10:1 rating at
  3.6 V. This is the LFCG's stop-band and pass-band reflection combining
  with the open.

### Detector margins (study 8, typical BAT15, as designed)

Thresholds are the firmware's (V30 350 mV, V35 730 mV, +1.4 mV/°C). Each
cell gives the reading, then the margin (positive means read correctly).
All values are in mV.

| P | T | Threshold | Missing, lowest (both models) | VSWR 2, highest | Matched |
|---|---|---|---|---|---|
| 30 dBm | −40 °C | 259 | 235 (−24) | 146 (+113) | 0 |
| 30 dBm | 25 °C | 350 | 325 (−25) | 235 (+115) | 17 |
| 30 dBm | 85 °C | 434 | 381 (−53) | 289 (+145) | 34 |
| 35 dBm | −40 °C | 639 | 586 (−53) | 415 (+224) | 3 |
| 35 dBm | 25 °C | 730 | 674 (−56) | 504 (+226) | 49 |
| 35 dBm | 85 °C | 814 | 734 (−80) | 563 (+251) | 81 |

With model B alone, the lowest missing readings are 463, 552 and 612 mV at
30 dBm and 1008, 1094 and 1155 mV at 35 dBm, all at least 178 mV above the
threshold. The averaged diode solve agrees with ngspice to within 13 mV over
six cases.

REFL_DET settles within 20 µs of the RF reaching full power, and decays with
a 100 µs time constant. The 750 µs sample therefore reads the steady level
only if the SX1262 start-up, its PA ramp and the APC LDO bring the RF to full
power within ~730 µs. That timing is not modelled and needs a bench check.

## Models and sources

| Part | Model | Source |
|---|---|---|
| GJM / GQM capacitors | C with ESR rising with √f, plus ESL. ESL: 0402 0.30, 0603 0.40, 0805 0.50 nH, plus 0.15 nH via (assumed). | Murata GJM catalogue C-29-C, maximum-ESR table. GQM is given the same limits (assumed). Temperature: C0G 0±30 ppm/°C. |
| LQW15AN / LQW18AN / LQW2BAN inductors | L with R(f) from the minimum Q, scaled by √f, and a parallel C from the minimum SRF. | Murata reference specs; DigiKey listing for LQW2BAN. Temperature: +25..+125 ppm/°C (assumed). |
| Inductor thermal data | Two-node RC. L15: 35 / 65 K/W and 0.016 / 0.25 J/K. L18: 200 / 220 K/W and 0.001 / 0.08 J/K. | **Estimated** from Murata's rated current (20 °C rise) and the parts' size. |
| LFCG-1000+ (FL1) | Lumped 7-section ladder fitted to Mini-Circuits' typical table (`lfcn.G_FIT`). The table sets the magnitude and the model gives the phase. The model's stop-band VSWR is higher than the table's. Unit spread: loss ×1.0–1.5, ±1 % frequency (**assumed**). | Mini-Circuits data sheet: 0.8 dB typical / 1.8 dB maximum; 5.5 W at 25 °C, derated to 1 W at 125 °C. |
| Detector coupler | Even/odd-mode coupled microstrip, 0.17 mm lines, 0.10 mm gap, 5.5 mm long: Z0e 60.0 Ω, Z0o 38.2 Ω, εeff 3.42 / 3.19. FR-4 loss as for the lines. Coupling about −27 dB; directivity about 23 dB in the board, with the ESD shunt and stubs. | `coupler.py` 2-D field solve (JLC06161H-2116B, 35 µm copper, mask assumed). Not EM-simulated in 3-D. |
| BAT15-02EL | RF: Ls 0.4 nH + Rs 8 Ω + Cj 0.20 pF. DC: mean diode current over an RF cycle equals V/100 k, plus a 0.13 µS reverse leak. IS 1.15e-7 A, N 1.08 (typical IF–VF curve, digitised). Corners: IS from VF 0.16 / 0.32 V at 1 mA; EG 0.55 / 0.69 eV, XTI 2. | Infineon data sheet v1.0 (2018-06-30). It gives no temperature data, so the temperature behaviour is **assumed**. Cross-checked with an ngspice transient. |
| SKY13330 | Loss 0.30/0.35 dB (typ/max) below 1 GHz, rising with frequency; 20 dB return loss. | Skyworks 201407E. Its harmonics are not published: −65/−60 dBc for 2f/3f at +35 dBm assumed. |
| QPA9510 | (A) A saturated current source with a voltage clamp at the die, through assumed bond wires, calibrated to 35.4 dBm on the EVB network. (B) A 50-ohm source. | Qorvo data sheet, 23 Jun 2025. 4f–10f at −45 dBc is **assumed**. |
| BGA7L1BN6, SX1262, TCXO, crystal, chip antenna | As in `results.txt`. | Infineon rev 3.1, Semtech DS rev 1.2, ECS, Abracon, Johanson data sheets. |

`followup.py` and `followup.txt` record the 19 Oct comparison that led to
the LFCG-1000+ and the detector, made on the LFCN board. They were not
re-run. `coupler.txt`'s detector levels assumed an ideal 50-ohm source;
study 8 supersedes them.

## What this does not prove

- **The layout.** The routed lengths will differ from the placed ones; 1f
  sweeps them for harmonics. The detector depends on its layout: the 1 nF
  must sit at the diode, and the coupler should be EM-simulated with the
  U.FL and the ESD pad.
- **PA behaviour into a missing antenna.** Two simple models bracket it, and
  they disagree about the detector. The switch, the LFCG and the BAT15 have
  no published ratings for this case. Only a bench test settles it: measure
  REFL_DET with a good antenna, a VSWR-2 load and an open U.FL on several
  cable lengths, at 30 and 35 dBm, hot and cold.
- **Anything above 7 GHz from the PA.** Its harmonics above 3f are assumed.
  **Measure to 10 GHz.**
- **Drift during a packet.** Keep the TCXO thermally away from the PA.
