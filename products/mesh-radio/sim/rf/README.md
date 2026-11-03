# Mesh Radio v1: RF simulations

These studies check the radio side of Mesh Radio v1 on the routed board
(`mesh-radio.kicad_pcb`). They cover the LoRa transmit and receive chains,
the clocks, the Bluetooth match and the missing-antenna detector. Each check
runs over part tolerances and six temperatures (−40, −20, 0, 25, 60 and
85 °C).

```
tools/kd python3 sim/rf/routed.py        # reads the RF lines off the routed board -> routed.json, routed.txt (~20 s)
tools/kd python3 sim/rf/run.py           # studies 1-8 on the routed board, from products/mesh-radio, in the pinned container (~4 min, one core)
tools/kd python3 sim/rf/run.py --quick   # 200 Monte Carlo runs instead of 1000
RF_DIODE=BAT15 tools/kd python3 sim/rf/run.py   # study 8 with the BAT15 in the same places -> results_BAT15.txt
RF_ROUTED=0 tools/kd python3 sim/rf/run.py      # the pre-route model (lumped nets, placement lengths) -> preroute/
tools/kd python3 sim/rf/coupler.py       # field solve of the detector coupler (sizing, 19 Oct)
RF_ROUTED=0 tools/kd python3 sim/rf/followup.py   # 19 Oct follow-up (LFCN-era board), kept as a record; superseded
tools/kd python3 sim/rf/design_lpf.py    # re-derives the harmonic-filter values on the routed lines (~30-60 min; not re-run)
```

- **Outputs.**
  - `routed.py` writes `routed.json`, the line netlist the studies use. It
    also writes `routed.txt`, the routing audit per RF net: length, layer,
    ground under the line, coplanar gap and ground vias.
  - `run.py` writes `results.txt`: every number, the criteria before each
    study, and a summary at the end.
  - `run.py` also writes the plots: `tx_chain.png`, `monte_carlo.png`,
    `pad.png`, `receive.png`, `frequency.png`, `bluetooth.png`,
    `open_antenna.png`, `heating.png` and `detector.png`.
- **Tools.**
  - `rflib.py`: plain numpy nodal analysis.
  - scipy for the fits and the diode solve.
  - ngspice (in the container) to cross-check the detector.
  - pcbnew and shapely (in the container) to read the board.
- **Where the values come from.**
  - `src/circuit.py` and `src/parts.py`: every passive value and part number
    (`rfboard.py`).
  - The routed board (`routed.json`): every RF line, the detector coupler,
    the ESD shunt's stub, the detector's DC tracks and each shunt part's
    ground return.
  - `firmware/variant/variant.h`: the firmware thresholds.

## The routed board (3 Nov)

### How the board is read now

`routed.py` loads `mesh-radio.kicad_pcb` with pcbnew. For every RF net
(`src/board.py` `RF_NETS` + `RF_EXTRA`) it splits the tracks at every pad
and junction into a line netlist. The part of a track inside a part's own
pad is left out, because the pad is the part's node and the part model
covers its body.

`rfboard.py` builds every network from that netlist. Each part's pin sits on
its own pad's node, so the routed lines between parts are now in the model
for:

- the PA output match;
- the LPF;
- the switch lines;
- the receive line;
- the Bluetooth pi and tee.

The pre-route model joined each net's parts at one node.

- **Line impedance.** A 2-D field solve (`coupler.single_line`) gives the
  0.17 mm line on F.Cu over In1:
  - 49.9 Ω, εeff 3.30, with the pour 0.25 mm away;
  - 50.8 Ω, εeff 3.35, with no copper within 0.8 mm.

  With 0.12 mm of prepreg to In1 the lines are nearly microstrip: the
  pour's distance moves Z0 by less than 1 Ω. Each piece gets the mix its
  open fraction gives.
- **Shunt ground return.**
  - A via in the pad adds 0.06 nH (one 0.2 mm via through 0.15 mm to In1).
  - A pad with no via adds 0.06 nH plus 0.2 nH per mm of pour to its nearest
    via (**estimate**).
  - The pre-route model used 0.15 nH for every shunt part.
- **The amplifier model off the EVB load.** On the routed board the die
  sees a different load from Qorvo's EVB (1c below). The load-line model
  (A) knows only the EVB load. Away from it, its output power rises: +2.4 dB
  here, which is not physical. So:
  - studies 7 and 7b hold model A to the matched power it gives on the
    lumped network at each supply, less the routed lines' extra loss
    (`run.pa_held`), and take the routed network's voltages and currents;
  - study 8 scales the PA to each test level, as before.

### Routing findings (the board was not edited)

The RF lines are the ones `src/board.py` drew and locked. The router did
not move them, so the routed geometry is the placement geometry. What is
new is the copper around the lines, and the pieces the model had left out.

| # | Finding | Effect in the studies |
|---|---|---|
| R1 | **No layer change and no via on any RF net.** Every RF line is on F.Cu, 0.17 mm wide. The gap to the ground pour is never under 0.25 mm (the DRC rule holds). | none |
| R2 | **The PA output match is spread along 0.17 mm line.** The four RF OUT pins (U10.9–12) each run their own 2.57 mm line to a 6.15 mm trunk. Along the trunk sit the choke L14, C71 15 pF and C72 10 pF (on 0.55 mm stubs) and L15. Then come 2.9 mm on PA_M1 and 5.6 mm on PA_M2 to the LPF's first part. At the die's ~2 Ω level, each mm of 50 Ω line is ~1.7 Ω of series reactance. Qorvo's EVB has the 15 and 11 pF hard at the pins. | **The die load moves from the EVB's 1.90−2.96j to 3.84−0.71j Ω.** That is \|Γ\| 0.48 against it, about 1.2 dB of mismatch. Expect about that much less saturated power than the data sheet's 35.4 dBm, unless the match is re-tuned. **FAIL (new check 1c).** |
| R3 | **The LPF's two parallel traps have their capacitor on 1.6 mm stubs at both ends.** C76 (3.6 pF, across L16) and C78 (1.3 pF, across L17) sit 1.6 mm off the main line. That puts ~3.2 mm of line (~1 nH) in series with each. | The notches move from 1.39 and 2.30 GHz to about 2.14 GHz, nearly merged. The LPF's own 2f and 3f rejection falls; the LFCG still carries 2f–5f. LPF loss rises from 0.21 to 0.35 dB. |
| R4 | **Bluetooth: 10.7 mm of line through the match.** 4.71 mm from the ANT ball to the pi; 1.79 and 1.88 mm between the pi and the tee's parts; 2.30 mm from the tee to the antenna feed. Nordic and Johanson put their parts side by side. | **RL falls from 15.5 dB (lumped) to 5.7 dB nominal and 3.5 dB worst, with 0 % yield: FAIL.** The pi and tee need re-tuning on the board (VNA). |
| R5 | **Coplanar gap below the 0.25 mm spec to signal copper:**<br>• LNA_OUT runs 0.137 mm from BYP_ILIM and 0.142 mm from DRN_P3, for about 4 mm of its 15.8 mm (27 % of samples).<br>• LORA_TXB is 0.216 mm from I2C_SDA.<br>• PA_DRIVE is 0.221 mm from a VPA track.<br>• LORA_RFO is 0.165 mm from LORA_VRPA, at the SX1262 pins.<br>• NRF_ANT is 0.215 mm from NRF_DEC4 and 0.24 mm from an unused ball, at the BGA. | Z0 barely moves (field solve: under 1 Ω). Not modelled: DC and digital nets coupling into the receive line after the LNA, and I2C coupling into the SX1262's TX match. |
| R6 | **Ground reference.** In1 is solid under every LoRa line, apart from small via voids. The exceptions:<br>• the first 0.93 mm of NRF_ANT (the BGA escape) has In1 under only 46–59 % of the line and its margins;<br>• **LORA_NRESET runs on In1 under that escape**, inside the chip cut-out of the "RF reference: In1 solid" keepout;<br>• LNA_OUT has 88 % for 0.35 mm at the LNA pin;<br>• BLE_FEED has 90 %, by design: it runs along the antenna's ground-free box. | Short; not modelled. |
| R7 | **Almost no ground vias beside the lines.** No TX or antenna line has a ground via within 0.6 mm. Within 1 mm: ANT has 7 over 8.6 mm and PA_OUT 11 over 17.5 mm; PA_M1, PA_DRIVE, LORA_TXA, LORA_TXC and LORA_TX50 have none. | In1 at 0.12 mm sets the impedance, so the vias do not change it. Unstitched pour fingers between the lines can resonate at 5–10 GHz, where the harmonics are. That needs an EM model. |
| R8 | **Shunt grounds.** Most RF shunts have a via in the pad: 0.06 nH, less than the 0.15 nH assumed. Pour only, with the distance to the nearest via:<br>• C38 (BLE pi, 0.5 pF): 0.66 mm;<br>• C51: 0.66 mm;<br>• R46: 1.05 mm;<br>• R51 and R75 (49.9 R): 1.1 mm;<br>• C82 and C99 (detector 1 nF): 0.66 mm.<br>**FL1 (LFCG-1000+) has a via in only one of its six ground pads**; the others are 0.62–0.95 mm from a via. | Modelled for the R, L and C parts. Not modelled for FL1: its model is Mini-Circuits' own test board, and its stop band (2f–10f) depends on those grounds. |
| R9 | **The detector as routed.** As designed: the coupled run is 5.5 mm with a 0.100 mm gap, and the ESD shunt is 0.6 mm from its U.FL end on a 0.26 mm stub. New in the model:<br>• the forward diode is 0.54 mm past R51, and the reflected diode 0.66 mm past R75 (each pair was modelled at one node before);<br>• the 1 nF is 1.4 mm (FWD) and 2.0 mm (REFL) from each cathode (21 mm on 20 Oct). | Modelled. The 1 nF placement now costs nothing (+4.3 / +4.4 dB). |
| R10 | **Antenna keepout.** D4's VIN_CHG pad on B.Cu reaches 0.14 mm² into the Bluetooth antenna's ground-free box, 3 mm past the antenna's open end. The rule area does not stop pads. | Negligible. |

### Old estimates vs the routed board

"Old" is `results.txt` of 20 Oct. `RF_ROUTED=0` on the current tree
reproduces it to 0.1 dB.

| Check | Old (pre-route) | Routed | Requirement |
|---|---|---|---|
| Loss PA (EVB plane) → U.FL, max in band | 1.13 dB (LPF 0.21) | **1.24 dB** (LPF 0.35) | ≤ 1.3 dB: **PASS** |
| Loss with the LFCG at 1.8 dB max | 2.27 dB | 2.37 dB | information |
| Monte Carlo loss; boards ≤ 1.3 dB | 1.13–1.51 dB; 47 % | **1.20–1.68 dB; 12 %** | MARGINAL (both) |
| PA die load vs Qorvo EVB (new check) | 1.91−2.91j Ω, 0.00 dB | **3.84−0.71j Ω, 1.23 dB** | **FAIL** |
| Worst return loss / PA load / U.FL | 16.3 / 21.3 / 22.3 dB | 14.9 / 19.2 / 26.9 dB | ≥ 10 dB: **PASS** |
| Harmonics 2f–5f, 35 dBm, 6 dBi | +16.9 dB (5f) | **+11.6 dB** (5f) | ≥ 3 dB: **PASS** |
| Harmonics 2f–5f, 30 dBm, 6 dBi | +23.5 dB | +17.0 dB | **PASS** |
| Harmonics 6f–10f, 35 dBm (PA level assumed) | +13.4 dB (6f) | +20.3 dB (6f) | **PASS** |
| 1f layout sweep, 35 dBm / 30 dBm US | +6.8 / +15.7 dB over 108 placed lengths | +1.7 / +10.5 dB, routed **plus** up to 11 mm at each switch port (a re-layout margin, not this board) | information |
| LPF notches (nominal) | 1.39 / 2.30 GHz | 2.14 / ~2.15 GHz (merged) | MARGINAL (both; the LFCG carries) |
| RX passive loss U.FL → RX_SW; vs RAK4631 | 0.97 dB; +4.8 dB | 0.96 dB; +4.9 dB | **PASS** |
| Pad power, +22 dBm, 85 °C | 41 % | 41 % | **PASS** |
| **Bluetooth RL, nominal / worst; yield** | 15.5 / 9.6 dB; 100 % | **5.7 / 3.5 dB; 0 %** | ≥ 9.5 dB: **FAIL** |
| PA VSWR, antenna missing | 10.6:1 | 11.2:1 | ≤ 10:1: FAIL (both) |
| SKY13330 peak, open, 3.6 V, model A / B | 54.5 / 35.7 V | 30.3 / 38.3 V | < 30 V: FAIL (both) |
| SKY13330 peak, open, 2.7 V, model A / B; both at 30 dBm | 40.8 / 26.8 V; 30.6 / 20.2 V | 22.7 / 28.7 V; 17.2 / 22.1 V | FAIL → **PASS** |
| SKY13330 peak, open, 4.0 V | 60.5 / 39.6 V | 33.7 / 42.6 V | FAIL (both) |
| LFCG port peak, open, 3.6 V | 63.0 V | 38.5 V | no rating (164 % of the 5.5 W equivalent) |
| Inductor heating, 4.0 V, matched / open (L15) | 65 % / 541 % | 68 % / 91 % | MARGINAL → **PASS** |
| L15 transient, 4.0 V, 25 % duty, no cut-off | 135 °C | 72 °C | FAIL → **PASS** |
| Coupler: forward wave into the 49.9 R | 30.5 dB down | 30.5 dB down | (as designed) |
| Detector, two conditions, nominal fit | from 30 dBm, +1.9 dB | from **33 dBm**, +1.9 dB | PASS → MARGINAL |
| Detector, fitted with ±1 dB of power error | from 33 dBm | **from 30 dBm, +1.9 dB** | MARGINAL → **PASS** |
| **Firmware rule as committed (default constants)** | +1.9 / +1.2 dB (fitted here) | **missing antenna −0.9 dB at 30 dBm** | **FAIL** |
| Firmware rule, robust constants, from 33 dBm | +3.8 / +2.1 dB | +3.6 / +1.3 dB; −1.1 dB with the power 1 dB low | MARGINAL |
| Detector parts, open, 4.0 V | BAT68 2.8 V; 49.9 R 21 mW | 1.9 V; 10 mW | **PASS** |
| REFL_DET settling, 30 dBm, −40 °C | 339 µs | 323 µs | needs the RF at full power by ~427 µs |

## Verdict: the routed board (3 Nov)

| # | Check | Result | Key numbers |
|---|---|---|---|
| 1c | **PA die load vs Qorvo's EVB load** (new) | **FAIL** | 3.84−0.71j against 1.90−2.96j Ω: \|Γ\| 0.48, ~1.2 dB of mismatch (R2). Expect about that much less saturated power, which would take 4.0 V to ~34 dBm at the U.FL. Re-tune C71, C72 and L15 on the board, or move them to the pins. |
| 1 | Loss from the PA output to the U.FL | PASS | 1.24 dB (LPF 0.35, switch 0.30, LFCG 0.67, coupler section 0.08). The data-sheet 35.4 dBm × (4.0/3.6)² gives 35.1 dBm at the U.FL, before 1c. With the LFCG at its 1.8 dB maximum: 2.37 dB. |
| 1 | Return loss at every interface | PASS | Worst 14.9 dB (the LPF alone). PA load 19.2 dB, U.FL 26.9 dB. |
| 1 | Harmonics 2f–5f, 30 and 35 dBm, 6 dBi | PASS | Worst margins 17.0 and 11.6 dB, both at 5f (were 23.5 and 16.9). |
| 1 | Harmonics 6f–10f, 35 dBm, 6 dBi, as routed | PASS | +20.3 dB at 6f, with the PA at −45 dBc (assumed). FL1's ground vias are not in the model (R8). |
| 1f | Harmonics with up to 11 mm added at each switch port | MARGINAL (information) | +1.7 dB at 4f for 35 dBm / 6 dBi; +10.5 dB for 30 dBm / 2.15 dBi. This is the margin for a re-layout, not for this board. |
| 2 | Monte Carlo, harmonics and PA match | PASS | 100 % yield; worst margin 9.2 dB. |
| 2 | Monte Carlo TX loss (is 3 W reachable?) | MARGINAL | 12 % of boards at 1.3 dB or less. Loss 1.20–1.68 dB gives 34.6–35.1 dBm at 4.0 V from the data-sheet power, and 1c's ~1.2 dB comes on top. |
| 2 | LPF notch placement | MARGINAL | Both notches near 2.14 GHz (R3). The LFCG carries 2f–5f. |
| 3 | Pad power at +20 and +22 dBm, 85 °C; attenuation | PASS | 26 % and 41 % of rating; 15.81–16.10 dB. |
| 4 | Receive vs a RAK4631 | PASS | 4.9 dB better with the LNA on (3.0 dB worst case); 2.1 dB worse in bypass. |
| 5 | LoRa frequency offset / 32 MHz crystal | PASS / MARGINAL | Unchanged: 8.6 kHz against a 31.2 kHz limit; 42 ppm new, 47 ppm aged. |
| 6 | **Bluetooth match, routed lines** | **FAIL** | RL 5.7 dB nominal, 3.5 dB worst, 0 % yield, against 9.5 dB (15.5 dB lumped). See R4. |
| 7 | **PA load with the antenna missing** | **FAIL** | 11.2:1 at the worst phase, against the 10:1 rating at 3.6 V. |
| 7 | SKY13330 with the antenna missing, 2.7 V | PASS | A 22.7 V (72 %), B 28.7 V (91 %) against 31.6 V. At 30 dBm: 17.2 / 22.1 V. |
| 7 | **SKY13330 with the antenna missing, 3.6 / 4.0 V** | **FAIL** | A 30.3 / 33.7 V; B 38.3 / 42.6 V (121 / 135 %). |
| 7 | LFCG port voltage, antenna missing | (no rating) | 29 / 39 / 43 V peak at 2.7 / 3.6 / 4.0 V, against the 23.5 V its 5.5 W rating makes in 50 Ω. |
| 7 | Inductor RF heating (steady), 3.6 and 4.0 V | PASS | Matched 55 % and 68 %; antenna missing 74 % and 91 % (L15; was 438–541 %). |
| 7 | LNA and SX1262 input during transmit | PASS | LNA 2.6 dBm; SX1262 0.4 dBm. |
| 7b | L15 and L18, antenna missing, 60 °C, 25 % duty, no cut-off | PASS | L15 at most 72 °C, L18 69 °C (L15 was 135 °C at 4.0 V). |
| 8 | Ratio detector, two conditions, nominal fit | MARGINAL | Works from 33 dBm, +1.9 dB. Fmin 115 mV × 1.0039^(T−25) × 1.203^(P−30); R 0.368 × 1.0040^(T−25) × 1.010^(P−30). |
| 8 | **Two conditions, fitted with ±1 dB of power error** | **PASS** | Works from 30 dBm, +1.9 dB. **Fmin 42 mV × 1.0070^(T−25) × 1.265^(P−30); R 0.277 × 1.0085^(T−25) × 1.030^(P−30).** Suggested for the firmware. |
| 8 | **Firmware rule as committed (default, the 20 Oct fit)** | **FAIL** | At 30 dBm a missing antenna passes by 0.9 dB, also with the power 1 dB under the model. From 33 dBm it is fine: +1.9 dB or more, and +1.0 dB or more with ±1 dB of power error. The robust constants are MARGINAL from 33 dBm (−1.1 dB with the power 1 dB low). |
| 8 | Detector parts with the antenna missing | PASS | BAT68-04W reverse peak 1.9 V (24 % of 8 V); 49.9 R 10 mW. |
| 8 | Gap ±0.02 mm, CJ 1 pF, 1 nF along the routed tracks | PASS (from 33 dBm) | +2.8 dB or better each. |

### What still fails, and why

- **The PA output match as routed (1c, R2).** The pins' own lines and the
  trunk put about 1–4 mm of 0.17 mm line between the die and the first
  shunt capacitors, at a ~2 Ω impedance level. The die load moves well away
  from what Qorvo tuned. The model cannot say how much power is lost; ~1.2 dB
  of mismatch against the EVB load is the estimate.
  - Bench check: output power and supply current at 3.6 and 4.0 V into
    50 Ω.
  - Possible fixes (not applied): join the four RF OUT pins with one wide
    pad, as on the EVB; put C71 and C72 at the pins; or re-tune the values
    on the board.
- **The Bluetooth match as routed (6, R4).** The lumped Nordic pi and
  Johanson tee were tuned with their parts side by side. With 10.7 mm of
  line through them the model gives 5.7 dB RL. The antenna is still
  Johanson's EVB model, not an EM model of this board, so the real number
  may be better or worse. The pi and tee pads are there to tune on: measure
  at the ANT pin with a VNA.
- **SKY13330 voltage with the antenna missing, 3.6 and 4.0 V.** Against the
  31.6 V limit, model A (power held) now gives 30–34 V and model B (a 50-ohm
  source) 38–43 V. The 2.7 V US mode now passes, at 72–91 %. The detector
  cannot prevent this: the switch sees the voltage as soon as the RF starts.
  Skyworks publishes no voltage or VSWR rating, so only a bench test into an
  open settles it.
- **The PA's mismatch rating.** 11.2:1 with the antenna missing, just past
  Qorvo's 10:1 rating at 3.6 V.
- **The firmware's detector constants.** They were fitted on the pre-route
  model, and on the routed board they miss a missing antenna at 30 dBm by
  0.9 dB. The routed board's ±1 dB fit (above) works from 30 dBm with
  +1.9 dB. Changing `variant.h` is a firmware decision; it was not edited
  here.
- **The 0.75 ms firmware cut-off.** Unchanged from 20 Oct (below).
  - *It protects against* everything that takes time: L15 and L18 heating,
    the LFCG's power rating, the 49.9 R, and the PA's time beyond 10:1.
  - *It does not protect against* the peak voltage on the SKY13330, the
    LFCG or the diodes, which is there from the first RF cycle.
  - *It does not catch* an antenna lost mid-packet, or packets modelled
    below 30 dBm.

### Ratio detector (study 8) on the routed board

The detector is as on 20 Oct:

- the coupled line terminated in 49.9 R at both ends;
- **FWD_DET**: a BAT68-04W at the filter end;
- **REFL_DET**: a BAT68-04W at the U.FL end;
- each diode into 1 nF ∥ 100 k.

Firmware calls the antenna missing if **FWD_DET < Fmin(P, T)** or
**REFL_DET / FWD_DET > R(P, T)**.

| Fitted for | Works from | Fmin(P, T) | R(P, T) | Worst margin |
|---|---|---|---|---|
| Nominal power | 33 dBm | 115 mV × 1.0039^(T−25) × 1.203^(P−30) | 0.368 × 1.0040^(T−25) × 1.010^(P−30) | +1.9 dB |
| ±1 dB power-model error | **30 dBm** | **42 mV × 1.0070^(T−25) × 1.265^(P−30)** | **0.277 × 1.0085^(T−25) × 1.030^(P−30)** | +1.9 dB |
| As in `variant.h` (the 20 Oct nominal fit) | 33 dBm (−0.9 dB at 30 dBm) | 53 mV × 1.0064^(T−25) × 1.252^(P−30) | 0.245 × 1.0101^(T−25) × 1.051^(P−30) | +1.9 dB from 33 dBm (+1.0 with ±1 dB) |

The results files hold the rest:

- the per-level margins;
- the BAT15 comparison (`results_BAT15.txt`): it works from 35 dBm, and the
  firmware's BAT68 constants do not suit it;
- the ngspice cross-check, within 56 mV.

Below 30 dBm nothing works with these parts. REFL_DET settles in 323 µs at
30 dBm and −40 °C, so the RF must be at full power by ~427 µs after
startTransmit.

## What changed on 20 Oct (pre-route; kept as the record)

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

### 20 Oct verdict (pre-route model), superseded by the routed verdict above

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

#### What failed on 20 Oct, and why

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

#### 20 Oct ratio detector fit (now in variant.h)

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
| GJM / GQM capacitors | C with ESR rising with √f, plus ESL. ESL: 0402 0.30, 0603 0.40, 0805 0.50 nH, plus the ground return: on the routed board 0.06 nH for a via in the pad, else 0.06 nH + 0.2 nH/mm of pour to the nearest via (**estimate**); pre-route 0.15 nH (assumed). | Murata GJM catalogue C-29-C, maximum-ESR table. GQM is given the same limits (assumed). Temperature: C0G 0±30 ppm/°C. |
| LQW15AN / LQW18AN / LQW2BAN inductors | L with R(f) from the minimum Q, scaled by √f, and a parallel C from the minimum SRF. | Murata reference specs; DigiKey listing for LQW2BAN. Temperature: +25..+125 ppm/°C (assumed). |
| Inductor thermal data | Two-node RC. L15: 35 / 65 K/W and 0.016 / 0.25 J/K. L18: 200 / 220 K/W and 0.001 / 0.08 J/K. | **Estimated** from Murata's rated current (20 °C rise) and the parts' size. |
| LFCG-1000+ (FL1) | Lumped 7-section ladder fitted to Mini-Circuits' typical table (`lfcn.G_FIT`). The table sets the magnitude and the model gives the phase. The model's stop-band VSWR is higher than the table's. Unit spread: loss ×1.0–1.5, ±1 % frequency (**assumed**). | Mini-Circuits data sheet: 0.8 dB typical / 1.8 dB maximum; 5.5 W at 25 °C, derated to 1 W at 125 °C. |
| Board lines | Routed pieces from `routed.json` as lossy lines: 49.9 Ω / εeff 3.30 with the pour at 0.25 mm, 50.8 Ω / 3.35 with no pour within 0.8 mm, mixed by each piece's open fraction; the length inside a part's own pad left out; FR-4 loss 0.002 dB/mm × √f + 0.003 dB/mm × f (GHz). | `coupler.single_line` 2-D field solve; `routed.py`. |
| Detector coupler | Even/odd-mode coupled microstrip, 0.17 mm lines, 0.10 mm gap (0.100 mm as routed), 5.5 mm long: Z0e 60.0 Ω, Z0o 38.2 Ω, εeff 3.42 / 3.19. FR-4 loss as for the lines. Coupling about −27 dB; directivity about 23 dB in the board, with the ESD shunt and stubs. | `coupler.py` 2-D field solve (JLC06161H-2116B, 35 µm copper, mask assumed). Not EM-simulated in 3-D. |
| BAT68-04W (detectors since 20 Oct) | RF: Ls 1.4 nH + Rs 9.2 Ω + Cj 0.65 pF (1.0 pF maximum as a corner); D2 shorted. DC: mean diode current over an RF cycle equals V/100 k, plus a 6 nS leak. IS 2.35e-9 A (318 mV at 1 mA), N 0.932, EG 0.65 eV, XTI 2, fitted to the IF–VF curves at −40/25/85 °C (within 4 mV). Corners: IS at 340 mV (data-sheet max) and 296 mV (**assumed**); EG 0.60 / 0.70 eV. | Infineon BAT68 data sheet (2011-06-15). Cross-checked with an ngspice transient. |
| BAT15-02EL (comparison only) | Ls 0.4 nH + Rs 8 Ω + Cj 0.20 pF; IS 1.15e-7 A, N 1.08 (typical curve); corners from VF 0.16 / 0.32 V at 1 mA; EG 0.55 (0.50 / 0.69). | Infineon data sheet v1.0 (2018-06-30). |
| SKY13330 | Loss 0.30/0.35 dB (typ/max) below 1 GHz, rising with frequency; 20 dB return loss. | Skyworks 201407E. Its harmonics are not published: −65/−60 dBc for 2f/3f at +35 dBm assumed. |
| QPA9510 | (A) A saturated current source with a voltage clamp at the die, through assumed bond wires (0.25 nH in all; one per RF OUT pin on the routed board), calibrated to 35.4 dBm on the EVB network. Off the EVB load its own power is not trusted: studies 7 and 7b hold it to the lumped network's power. (B) A 50-ohm source. | Qorvo data sheet, 23 Jun 2025. 4f–10f at −45 dBc is **assumed**. |
| BGA7L1BN6, SX1262, TCXO, crystal, chip antenna | As in `results.txt`. | Infineon rev 3.1, Semtech DS rev 1.2, ECS, Abracon, Johanson data sheets. |

`coupler.py` was not re-run: the routed coupler is the one it sized (5.5 mm, 0.100 mm gap).
`followup.py` and `followup.txt` record the 19 Oct comparison that led to
the LFCG-1000+ and the detector, made on the LFCN board. They were not
re-run. `coupler.txt`'s detector levels assumed an ideal 50-ohm source;
study 8 supersedes them.

## What this does not prove

- **The board's EM behaviour.** The lines are modelled as 2-D lines between
  lumped parts. Not modelled: coupling between neighbouring lines and nets
  (R5), the unstitched pour (R7), FL1's ground vias (R8), the U.FL and the
  antenna's surroundings. An EM model of the RF area, or a VNA on built
  boards, is the next check, above all for the Bluetooth match and the PA
  output.
- **PA behaviour off its EVB load and into a missing antenna.** Two simple
  models bracket it, and on the routed board the die load is far from the
  EVB's. Measure output power, supply current and harmonics at 3.6 and
  4.0 V. Measure REFL_DET and FWD_DET on several cable lengths, at 30 and
  35 dBm, hot and cold, with each of:
  - a good antenna;
  - a VSWR-2 load;
  - an open U.FL.
- **Anything above 7 GHz from the PA.** Its harmonics above 3f are assumed.
  **Measure to 10 GHz.**
- **Drift during a packet.** Keep the TCXO thermally away from the PA.
