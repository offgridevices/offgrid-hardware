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
   other to the detector diode (BAT15 at first; BAT68-04W since item 6), with the 1 nF and 100 k at
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
6. **Later on 20 Oct: the ratio detector.** It adds a forward BAT68-04W at
   the 49.9 R end (FWD_DET, P0.02/AIN0) and a second 49.9 R at the U.FL end.
   Both detector diodes are BAT68-04W (8 V) instead of BAT15-02EL. The 49.9 R
   parts are now 0805 0.5 W.
   - `rfboard.py` places each part at its end of the coupled line, by the
     notes in `circuit.py`.
   - `run.py` study 8 evaluates the ratio, the two-condition rule, the diode
     spread (unmatched pairs) and the BAT15 for comparison
     (`RF_DIODE=BAT15 tools/kd python3 sim/rf/run.py` writes
     `results_BAT15.txt`).

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
| 7 | **PA load with the antenna missing** | **FAIL** | 10.6:1 at the worst phase, against Qorvo's 10:1 rating at 3.6 V. The LFCG reflects more than the LFCN did (9.1:1 on 19 Oct). Only the detector cut-off limits how long the PA sees it. |
| 7 | **SKY13330 with the antenna missing, 2.7 V** | **FAIL** | Model A 40.8 V (129 %), model B 26.8 V (85 %). At exactly 30 dBm (the US cap): **A 30.5 V (97 %), B 20.2 V (64 %)**. The limit is 31.6 V, what +40 dBm makes in 50 Ω. |
| 7 | **SKY13330 with the antenna missing, 3.6 V** | **FAIL** | **Model A 54.4 V (172 %), model B 35.7 V (113 %)**. |
| 7 | **SKY13330 with the antenna missing, 4.0 V** | **FAIL** | Model A 60.5 V (191 %), model B 39.6 V (125 %). |
| 7 | LFCG port voltage with the antenna missing | (no rating) | 47 / 63 / 70 V peak at 2.7 / 3.6 / 4.0 V, against the 23.5 V its 5.5 W rating makes in 50 Ω (16.7 V at 85 °C). |
| 7 | Inductor RF heating (steady), 3.6 and 4.0 V | MARGINAL | Matched: 52 % and 65 % of rated-current heating. Antenna missing: L15 437 % and 540 %. |
| 7 | LNA and SX1262 input during transmit | PASS | LNA 5.5 dBm (abs max +25); SX1262 3.3 dBm (abs max +10). |
| 7b | L15, antenna missing, 60 °C, 1 s bursts at 25 % duty, no cut-off | PASS at 2.7 and 3.6 V, **FAIL at 4.0 V** | 94, 121 and 135 °C against a 125 °C limit. With the 0.75 ms cut-off it rises 0.1 °C or less per event. |
| 7b | L18, the same conditions | PASS | 101 °C or less. |
| 8 | **Ratio detector, two conditions** (fault if FWD_DET < Fmin(P,T) or REFL/FWD > R(P,T)) | PASS from 30 dBm | Every diode pairing, both PA models, −40..85 °C, worst margin +1.9 dB. Fmin(30 dBm, 25 °C) 53 mV, +0.64 %/°C, +25 %/dB. R(30 dBm, 25 °C) 0.245, +1.0 %/°C, +5 %/dB. |
| 8 | The same with ±1 dB between the power model and the real power | MARGINAL | Fitted with that 1 dB built in, it works from **33 dBm**: Fmin 70 mV × 1.0054^(T−25) × 1.231^(P−30), R 0.424 × 1.0020^(T−25) × 1.010^(P−30), +1.9 dB. At 30–33 dBm, a real power 1 dB under the model gives false "antenna missing" readings (a needless 1 W retry, never a missed fault). |
| 8 | **The rule in firmware as committed (1a8f864)**: trip if FWD_DET ≥ 50 mV and ratio > 0.35, else the old REFL_DET thresholds | **FAIL** | A missing antenna passes at 30 dBm (−38 dB) and 33 dBm (−18 dB). At those cable lengths FWD_DET stays under 50 mV, and the fallback thresholds sit above every REFL_DET reading. It is fine at 35–36 dBm (+5.4 dB). Use the two-condition rule: a low FWD_DET is a fault, not a reason to wait. |
| 8 | Ratio detector, one ratio threshold only | MARGINAL | Works from 33 dBm. At 30 dBm and −40 °C the forward reading collapses with the antenna missing (model A), so a ratio alone misreads by up to 5.9 dB. |
| 8 | Detector parts with the antenna missing | PASS | BAT68-04W reverse peak 2.8 V (35 % of 8 V). Each 49.9 R takes 21 mW (5 % of the 0.5 W part's 85 °C rating), continuous. |
| 8 | Coupler gap ±0.02 mm, CJ 1 pF, REFL_DET 1 nF as placed (21 mm away) | PASS (from 33 dBm) | +1.7 dB or better each. The 1 nF must still sit at each diode. |

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
    or the detector diodes, which is there from the first RF cycle of every packet and
    every 1 W retry.
  - *It does not protect against* an antenna lost mid-packet, because it
    samples only once, 750 µs into each packet; the packet then runs to its
    end, up to ~5 s.
  - *It does not protect against* packets whose modelled power is below
    27 dBm, which are not checked.
  - *It does not protect against* readings it cannot make: at 27-30 dBm a
    real power more than ~1 dB under the firmware's model makes the forward
    reading unreliable cold (study 8).
- **The detector, before the 20 Oct ratio change.** A single reflected
  detector against fixed thresholds misread a missing antenna by up to 80 mV
  at some cable lengths with a saturated PA. That design is replaced by the
  ratio detector below.
- **The ratio detector needs both ends of the coupled line terminated.** With
  the U.FL end left to the reflected diode alone (high impedance), the
  reflected wave's coupled copy bounces off it back to the forward diode and
  cancels the forward reading at some cable lengths. The forward port then
  swings 0.003–0.085 V per volt incident; with the second 49.9 R it holds at
  0.041–0.045. `src/circuit.py` now has a 49.9 R at each end (R51 at the
  filter end, R75 at the U.FL end).
- **The BAT68 reads little at 30 dBm when cold.** It is a medium-barrier
  diode (VF 318 mV at 1 mA, against 250 mV for the BAT15). With the antenna
  missing and a saturated PA at some cable lengths, FWD_DET falls to a few
  mV at −40 °C, because the PA delivers little into the open. The firmware
  therefore needs the second condition, FWD_DET below Fmin(P,T). Faster or
  stronger options, none of them applied:
  - a tighter gap: 0.08 mm adds ~1.5 dB of margin;
  - a longer coupler;
  - a small forward bias on both diodes;
  - a later sample point.
  REFL_DET needs up to 335 µs to settle at 30 dBm and −40 °C, so the RF must
  be at full power by ~415 µs after startTransmit.
- **The BAT15 compared** (`results_BAT15.txt`, `detector_BAT15.png`; the same
  places, the same rule). It is more sensitive, with +4.1 dB for a fixed ratio
  using typical diodes. But its data-sheet VF spread at 1 mA (0.16–0.32 V)
  makes unmatched pairs fail below 33–35 dBm, and its 2.8 V reverse peak is
  69 % of its 4 V rating. The BAT68's tighter spread (318 typ / 340 max mV)
  makes it the more robust part.
- **The PA's mismatch rating.** 10.6:1 is just past Qorvo's 10:1 rating at
  3.6 V. This is the LFCG's stop-band and pass-band reflection combining
  with the open.

### Ratio detector (study 8): the firmware rule and its margins

The board now has:

- the coupled line terminated in 49.9 R (Vishay CRCW0805 HP, 0.5 W) at both
  ends;
- **FWD_DET**: a BAT68-04W at the filter end into 1 nF ∥ 100 k, to P0.02/AIN0;
- **REFL_DET**: a BAT68-04W at the U.FL end into 1 nF ∥ 100 k, to P0.30/AIN6.

Firmware samples both in one SAADC scan and calls the antenna missing if
**FWD_DET < Fmin(P, T)** or **REFL_DET / FWD_DET > R(P, T)**. P is the
modelled U.FL power and T the board temperature.

| Fitted for | Works from | Fmin(P, T) | R(P, T) | Worst margin |
|---|---|---|---|---|
| Nominal power | 30 dBm | 53 mV × 1.0064^(T−25) × 1.252^(P−30) | 0.245 × 1.0101^(T−25) × 1.051^(P−30) | +1.9 dB |
| ±1 dB power-model error | 33 dBm | 70 mV × 1.0054^(T−25) × 1.231^(P−30) | 0.424 × 1.0020^(T−25) × 1.010^(P−30) | +1.9 dB |

Margins for the nominal fit, in dB, as good-antenna / missing-antenna. Each
is the worst over seven diode pairings (VF 296–340 mV, EG 0.60–0.70,
unmatched), both PA models, every phase and 902–928 MHz:

| P | −40 °C | 0 °C | 25 °C | 60 °C | 85 °C |
|---|---|---|---|---|---|
| 30 dBm | +1.9 / +2.2 | +6.4 / +7.1 | +4.4 / +6.8 | +2.2 / +5.2 | +3.1 / +3.9 |
| 33 dBm | +7.4 / +10.9 | +4.8 / +9.0 | +3.1 / +7.4 | +3.1 / +4.9 | +4.2 / +3.2 |
| 35 dBm | +6.0 / +12.0 | +2.9 / +9.1 | +2.7 / +7.2 | +3.6 / +4.5 | +5.0 / +2.6 |
| 36 dBm | +3.5 / +12.1 | +2.3 / +9.0 | +2.7 / +7.1 | +3.9 / +4.3 | +5.0 / +2.3 |

- **A single ratio threshold does not work at every level.** Over 27–36 dBm
  the VSWR-2 and missing ratios overlap, by −0.4 dB with typical diodes. That
  is because the diodes move from square-law to linear detection as the
  level rises.
- **A threshold compensated for temperature and level, alone,** works from
  33 dBm.
- **Below 30 dBm nothing works with these parts.** Firmware should check
  from 30 dBm, not from 27 dBm (`OFFGRID_REFL_MIN_DBM`).
- **ngspice agrees** with the averaged diode solve to within 32 mV over five
  cases.

## Models and sources

| Part | Model | Source |
|---|---|---|
| GJM / GQM capacitors | C with ESR rising with √f, plus ESL. ESL: 0402 0.30, 0603 0.40, 0805 0.50 nH, plus 0.15 nH via (assumed). | Murata GJM catalogue C-29-C, maximum-ESR table. GQM is given the same limits (assumed). Temperature: C0G 0±30 ppm/°C. |
| LQW15AN / LQW18AN / LQW2BAN inductors | L with R(f) from the minimum Q, scaled by √f, and a parallel C from the minimum SRF. | Murata reference specs; DigiKey listing for LQW2BAN. Temperature: +25..+125 ppm/°C (assumed). |
| Inductor thermal data | Two-node RC. L15: 35 / 65 K/W and 0.016 / 0.25 J/K. L18: 200 / 220 K/W and 0.001 / 0.08 J/K. | **Estimated** from Murata's rated current (20 °C rise) and the parts' size. |
| LFCG-1000+ (FL1) | Lumped 7-section ladder fitted to Mini-Circuits' typical table (`lfcn.G_FIT`). The table sets the magnitude and the model gives the phase. The model's stop-band VSWR is higher than the table's. Unit spread: loss ×1.0–1.5, ±1 % frequency (**assumed**). | Mini-Circuits data sheet: 0.8 dB typical / 1.8 dB maximum; 5.5 W at 25 °C, derated to 1 W at 125 °C. |
| Detector coupler | Even/odd-mode coupled microstrip, 0.17 mm lines, 0.10 mm gap, 5.5 mm long: Z0e 60.0 Ω, Z0o 38.2 Ω, εeff 3.42 / 3.19. FR-4 loss as for the lines. Coupling about −27 dB; directivity about 23 dB in the board, with the ESD shunt and stubs. | `coupler.py` 2-D field solve (JLC06161H-2116B, 35 µm copper, mask assumed). Not EM-simulated in 3-D. |
| BAT68-04W (detectors since 20 Oct) | RF: Ls 1.4 nH + Rs 9.2 Ω + Cj 0.65 pF (1.0 pF maximum as a corner); D2 shorted. DC: mean diode current over an RF cycle equals V/100 k, plus a 6 nS leak. IS 2.35e-9 A (318 mV at 1 mA), N 0.932, EG 0.65 eV, XTI 2, fitted to the IF–VF curves at −40/25/85 °C (within 4 mV). Corners: IS at 340 mV (data-sheet max) and 296 mV (**assumed**); EG 0.60 / 0.70 eV. | Infineon BAT68 data sheet (2011-06-15). Cross-checked with an ngspice transient. |
| BAT15-02EL (comparison only) | Ls 0.4 nH + Rs 8 Ω + Cj 0.20 pF; IS 1.15e-7 A, N 1.08 (typical curve); corners from VF 0.16 / 0.32 V at 1 mA; EG 0.55 (0.50 / 0.69). | Infineon data sheet v1.0 (2018-06-30). |
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
  they disagree about the detector. The switch, the LFCG and the BAT68 have
  no published ratings for this case. Only a bench test settles it: measure
  REFL_DET with a good antenna, a VSWR-2 load and an open U.FL on several
  cable lengths, at 30 and 35 dBm, hot and cold.
- **Anything above 7 GHz from the PA.** Its harmonics above 3f are assumed.
  **Measure to 10 GHz.**
- **Drift during a packet.** Keep the TCXO thermally away from the PA.
