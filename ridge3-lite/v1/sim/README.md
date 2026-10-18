# ridge3-lite v1: circuit simulations

Electrical studies of the 3-inch AIO (src/circuit.py, src/parts.py) against
its worst case: a full 4S HV pack (17.4 V), iFlight XING2 1404 3800KV on 3"
props (15 A per motor peak, 15.8 A for 60 s), and a board at 100 C on a 50 C
desert day.  The thermal model lives separately in `thermal/` and takes its
power-stage heat from `losses.csv`.

```
sim/run_all.sh                      # everything (about 1 min once the half-bridge cache is warm)
cd sim/halfbridge && python3 run.py # or one study
```

Needs ngspice (44 tested) and Python 3 with numpy and matplotlib.  scipy is
optional: without it, the FET fit reuses its recorded result.  From
`ridge3-lite/v1` the toolchain container works too: `tools/kd sh sim/run_all.sh`.
Netlists as run, ngspice logs and raw data go to `<repo>/out/sim/` (gitignored).
Each study writes `results.txt` (every number quoted here) and its plots
next to its `run.py`.

## Verdict

The board as built takes recommendations 1 and 6 below: every high-side
gate has 22 ohm, every low-side gate 10 ohm, and each ESC's VSENSE has its
100 nF (src/circuit.py).  "As drawn" in this report is the first draft
(4.7 / 4.7 ohm, no VSENSE cap), kept as the baseline the fixes are measured
against.  `losses.csv`, which the thermal model reads, is for 22 / 10 ohm.

| # | check | result | limit | margin | |
|---|---|---|---|---|---|
| 1 | FET peak VDS, as drawn (4.7 / 4.7 ohm), 15 A, 2 nH loop | 41.3 V (low side, die) | 34 V (85 %) | -7.3 V | **FAIL** |
| 1 | FET peak VDS, as drawn, 30 A, 4 nH (abuse) | 49.8 V | 40 V | -9.8 V | **FAIL** |
| 1 | **recommended gates 22 ohm high / 10 ohm low**: VDS 15 A / 2 nH, motoring / braking | 29.7 V / 32.2 V | 34 V | 4.3 V / 1.8 V | PASS |
| 1 | same, 30 A / 4 nH (abuse), motoring / braking | 39.4 V / 37.7 V | 40 V | 0.6 V / 2.3 V | PASS (thin) |
| 1 | switch-node dV/dt, 10-90 % (incl. 0.5 A) | as drawn up to 2.8 V/ns; 22/10: <= 1.85 V/ns | DRV8300D 2 V/ns (rec.) | 0.15 V/ns | as drawn FAIL, 22/10 PASS |
| 1 | DRV8300 GLx pin undershoot | as drawn -7.3 V (30 A, 4 nH); 22/10: -1.4 V | -5 V for 500 ns | 3.6 V | 22/10 PASS |
| 1 | Miller bump, die VGS, 150 C (low side motoring / high side braking) | as drawn 1.67 / 1.79 V; 22/10: 1.47 / 2.03 V | goal 0.7 V | | goal **not met by any option** (incl. snubbers); no measurable shoot-through, see 1.5 |
| 1 | switching loss per motor, 15 A, 150 C, 24 / 48 kHz | as drawn 0.07 / 0.14 W; 22/10: 0.22 / 0.43 W | | | cost of the fix: +0.15 / +0.29 W per motor |
| 2 | VBAT, 60 A released in 1 us (with 470 uF) | 17.9 V | 35 V (electrolytic), 40 V (FETs) | 17 V | PASS |
| 2 | VBAT, brake +60 A -> -40 A for 20 ms | 18.6 V | 35 V | 16 V | PASS |
| 2 | electrolytic missing: worst spike (release) / hot plug | 20.5 V / 26.4 V | 40 V | 19.5 V / 13.6 V | PASS, but 2-7 V p-p PWM ripple |
| 2 | pack unplugged while braking 20 A for 5 ms | 56.8 V; TVS takes 5.0 J | TVS ~0.2 J at that width | | **FAIL** (not protectable by a TVS this size) |
| 2 | electrolytic ripple current (independent ESCs) | 2.3-2.7 A rms hover, 5.2-5.9 A rms worst | typ. 470 uF 35 V electrolytic ~1-2.5 A rms | | **check the part** |
| 3 | TPS7A1601 dissipation / Tj (board 100 C) | 151 mW / 107 C worst | 125 C | 18 C | PASS |
| 3 | GVDD ripple at a driver | 13 mV p-p | | | PASS |
| 3 | bootstrap at 100 % duty, time to BSTUV | 14.7 ms worst -> lowest 1360 eRPM (194 rpm) | | | PASS |
| 3 | sagging pack | works down to VBAT 5.77 V worst (2.88 V/cell on 2S) | | | PASS (2S deep sag marginal) |
| 4 | BEC peak inductor current, 0.6 A, 17.4 V | 0.706 A | ISC 0.87 A min | 23 % | PASS |
| 4 | BEC minimum on-time at 17.4 V, 2.3 MHz | 125 ns | 80 ns max | 45 ns | PASS |
| 4 | BEC Tj at 0.6 A / 0.35 A (board 100 C) | 112 C / 108 C worst | 150 C | 38 C | PASS |
| 5 | ISENSE gain / full scale | 20.0 mV/A / 64 A | AM32 20 mV/A | | PASS |
| 5 | current error, worst case | 0.17 A + 4.8 % (+-0.89 A at 15 A) | | | PASS |
| 5 | CUR (FC) gain | 12.02 mV/A | ibata_scale 120 | | PASS |
| 5 | BEMF comparator inputs, steady state | 3.28 V max | VDDA + 0.3 = 3.6 V | 0.32 V | PASS |
| 5 | BEMF zero crossing vs true neutral | exact (ideal parts); 1 % parts: 3.5 deg typ at startup, < 1 deg at speed | | | PASS |
| 5 | VBAT dividers | ratio 11.0 both (110 / 110) | | | PASS; ESC divider needs a cap or slow ADC sampling |

## Recommended component changes

1. **Change the gate resistors: 22 ohm on every high-side gate, 10 ohm on
   every low-side gate** (value changes only, no added parts; 0201 is fine,
   dissipation is under 1 mW).  The overshoot comes from fast switch-node
   edges ringing the 3.2 nH loop against Coss.  It is not mainly diode
   recovery: with no stored charge at all the as-drawn low side still
   reaches 41 V.  A slower high-side turn-on fixes motoring.  Braking (phase
   current into the node, where the low side hard-switches at its turn-on)
   needs the low side slowed too: with 4.7 ohm low-side gates every option,
   including the switch-node snubber, overshoots 40 V at -30 A / 4 nH.  The
   options study (`halfbridge/options.py`, `options.txt`, `options.png`)
   tried these:

   | option (15 A / 2 nH, 30 A / 4 nH; motoring and braking) | worst VDS | dV/dt | GL min | verdict |
   |---|---|---|---|---|
   | as drawn 4.7 / 4.7 | 41.3 / 49.8 V | 2.83 | -7.3 V | fail |
   | high 10 / 15 ohm, low 4.7 or 3.3 | 36.5-38.1 / 42.1-46.8 V | 2.2-2.6 | to -9.1 V | fail |
   | high 22 or 33 ohm, low 4.7 or 3.3 | 36.7-37.8 V braking / 41.1-42.1 V braking | 1.4-1.9 | to -5.9 V | fail (braking) |
   | **high 22, low 10** | **32.2 / 39.4 V** | **1.85** | **-1.4 V** | **PASS** |
   | high 22, low 22 | 30.4 / 40.6 V | 1.78 | -0.6 V | fail (motoring, 30 A) |
   | high 15, low 10 or 15 | 34.2-34.7 / 44.0-44.5 V | 2.2 | -1.6 V | fail |
   | DC-link damper 1R + 22n or 2.2R + 10n, gates 4.7 (B) | 41.0 / 49.5 V | 2.7-2.9 | -7.2 V | fail: it barely touches the FET-level ring |
   | 22 / 4.7 + 2.2 or 4.7 nF low-side Cgs (C) | 28.9-31.6 / 38.5-38.6 V | 1.82-1.87 | -3.4 V | PASS, but 12 added caps |
   | 1R + 4.7n switch node to SRC (the earlier recommendation) | 36.0 / 40.7 V braking | 1.85 | -4.0 V | fail (braking) |

   Cost: Eon + Eoff at 15 A rises from 2.9 to 9.0 uJ (150 C).  Psw per motor
   at 15 A, 150 C goes from 0.07 / 0.14 W to 0.22 / 0.43 W (24 / 48 kHz), and
   at 30 A from 0.17 / 0.33 to 0.47 / 0.94 W.  The total FET loss per motor
   at 15 A, 150 C becomes 2.37 / 2.98 W (24 / 48 kHz), up from 2.22 / 2.69 W.
   Dead-time diode conduction is still the bigger lever (below).
2. **Layout: keep each bridge cap's loop (cap, high-side drain, low-side
   source) at 2 nH of PCB or less.**  At 4 nH the 22 / 10 gates leave only
   0.6 V of margin at 30 A; at 2 nH, 30 A motoring peaks at 34.8 V.
3. **Do not add the 24 switch-node snubbers.**  They were the first
   recommendation; they fail braking at -30 A / 4 nH (40.7 V).  The DC-link
   damper option was also rejected.
4. **Bulk electrolytic: keep the 470 uF 35 V, ESR 40 mOhm or less, and
   pick it for ripple current, not just capacitance.**  It is what keeps
   VBAT clean: without it the PWM ripple is 2.0-6.8 V p-p and a hot plug
   rings to 26.4 V.  It carries 2.3-2.7 A rms at hover and 5-6 A rms at the
   worst point of a prop load (four free-running ESCs).  At 40 mOhm that is
   0.2-0.3 W, rising to 1.1-1.4 W.  A part rated for 3 A rms or more (a
   polymer-hybrid, or 35 V low-ESR 10 x 16-20 mm), or two caps in parallel
   (a quarter of the heat each), is recommended.  A second cap is not
   needed for spikes.
5. **Keep the SMF22A.**  It never conducts in any normal event: the
   highest VBAT with the electrolytic fitted is 18.6 V, against its 24.4 V
   minimum breakdown.  It only touches its knee on a hot plug with the
   electrolytic missing.  It cannot save the board if the pack is unplugged
   while the motors brake: 5 J against about 0.2 J.  It would fail, most
   likely short.  No TVS of this size can absorb that.  The defences are a
   pack that stays connected (XT30, solder) and AM32's brake settings.
6. **Add 100 nF (0201, 16 V) from each ESC's VSENSE (PA6) to ground.**  The
   100k / 10k divider is a 9.1 kohm source.  Unbuffered, the G071's 12-bit
   ADC needs at least 39.5 sampling cycles (DS12232 Table 57).  With the cap
   any sampling time reads correctly.  Alternatively, confirm what AM32
   uses.

Not component changes, but found on the way:

- **Dead time dominates the FET loss.**  AM32's DEAD_TIME 60 at 64 MHz
  (0.94 us), plus the DRV8300's 215 ns as the brief assumes, keeps a body
  diode conducting 5.5 % (24 kHz) / 11 % (48 kHz) of every cycle.  At 15 A
  that is 0.44-1.3 W per motor, 20-54 % of the FET heat.  A custom AM32
  target with a shorter DEAD_TIME (the DRV8300 already guarantees 150 ns
  minimum) is the cheapest thermal improvement available.  Whether the
  driver's 215 ns adds to the input dead time or overlaps it is not stated
  in the datasheet.  Additive is the conservative reading, used here.
- circuit.py comments that disagree with the numbers: the current filter is
  2.65 kHz (1.5k || 1k = 600 ohm with 100 nF), not 1.0 kHz.  The TPS7A16's
  EN is rated 62 V absolute, not 40 V.  With the recommended 22 / 10 ohm
  gates the switch node slews at most 1.85 V/ns (10-90 %, worst at light
  load; 1.0-1.4 V/ns at 15-30 A), with 5-7 V/ns at the top of the edge.  As
  drawn it was 1.2-2.8 V/ns, not "near 3 V/ns".  The gate-resistor comment
  cites `sim/halfbridge.cir`; the study is `sim/halfbridge/options.py`.

## The FET model (`fet_model/`)

Toshiba publishes PSpice/LTspice/SIMetrix models for the TPN2R304PL.  Every
automated download from toshiba.semicon-storage.com (`docget.jsp`) was
refused (HTTP 403, Akamai), so `models/tpn2r304pl.lib` is an ngspice VDMOS
fitted to the datasheet (Rev 3.0).  Capacitances are fitted by Nelder-Mead to
Fig 8.11.  Threshold and transconductance come from Figs 8.2/8.3/8.8,
RDS(on) from Fig 8.9, and the body diode from Fig 8.6.  The checks
(`fet_model.png`) compare model to datasheet: Qg(10 V) 39.6 nC vs 41; Qgd
5.0 vs 6.2 nC; Qgs 9.6 vs 9.6 nC; Qoss(20 V) 25.0 vs 27 nC; Miller plateau
3.5 V vs ~3.6 V; Vth (0.3 mA) 1.90 V at 25 C and 1.26 V at 150 C (typical
curve: 1.95 / 1.25 V); RDS(on) at 10 V 1.80 / 2.43 / 3.06 mOhm at
25 / 100 / 150 C.  The package inductances (0.15 nH drain, 0.25 nH source,
0.5 nH gate) are estimates; Toshiba does not publish them.

The least certain parameter is the body diode's reverse recovery.  The
SPICE diode stores TT x IF and recovers abruptly.  TT = 1.5 ns, the value
used, stores 22 nC at 15 A, close to the 30 nC Qrr in the datasheet.  The
sensitivity is reported: the low-side peak at 30 A, 2 nH is 41.3 / 42.1 /
47.2 / 59.5 V for TT = 0 / 0.5 / 1.5 / 3 ns, and 37.2 V at 15 A with TT = 0.
Even with no stored charge at all, the Coss and loop resonance alone takes
the as-drawn die to or above 40 V.  That is why recommendation 1 does not
hinge on this parameter.

## 1. Half-bridge switching (`halfbridge/`)

**What is modelled:** one leg, high side PWM'd with the phase current
flowing out (AM32 complementary PWM), at 17.4 V.  The DRV8300D outputs are
tanh-limited current sources, from SLVSFG5D 7.5: 0.75 A source and 6 ohm
(0.6 V at 100 mA), 1.5 A sink and 1.5 ohm (0.15 V at 100 mA).  The
bootstrap diode is 0.7 V at 100 uA with 15 ohm.  The bootstrap cap is
0.4 uF effective; GVDD is 11 V with 4 uF local.  Each gate has R_ext, 3 nH
of gate trace and rg 0.7 ohm.  Bridge caps: this leg's 4.7 uF 50 V 0805 at
1.75 uF / 0.4 nH / 4 mOhm, the ESC's other two 1 nH away, and the 470 uF
behind 15 nH.  The commutation loop is L_loop of PCB (swept 1 / 2 / 4 nH)
plus 0.8 nH of packages and 0.4 nH of cap ESL.  The shunt is 0.5 mOhm +
0.3 nH; the low-side gate returns through it, because the DRV8300 has no
SLx pin.  Dead time is 0.94 + 0.215 = 1.155 us.  The load is an ideal 15 or
30 A current source.  Tj 25 / 100 / 150 C variants of the FET shift Vth and
RDS(on).

**Results** (`results.txt` has every run; `halfbridge.png` compares as drawn
with 22 / 10 ohm; `rg_sweep.png`, `loop_sweep.png`; `options.txt` /
`options.png` for the damping options).  The table below is the as-drawn
4.7 ohm baseline:

| Rg 4.7, 2 nH | 15 A, 25 C | 15 A, 150 C | 30 A, 25 C | 30 A, 150 C |
|---|---|---|---|---|
| low-side die VDS peak (sw rising) | 41.3 V | 39.6 V | 47.2 V | 44.8 V |
| high-side die VDS peak (sw falling) | 27.7 V | 25.8 V | 33.5 V | 30.0 V |
| same with 1 ohm + 4.7 nF snubber, low / high | 21.8 / 23.3 V | 21.5 / 23.0 V | 22.5 / 31.5 V | 22.0 / 28.6 V |
| sw dV/dt rising, 10-90 % / peak | 1.69 / 9.6 V/ns | 1.64 / 9.0 | 1.22 / 11.5 | 1.19 / 10.5 |
| low-side die VGS bump (Miller) | 1.46 V | 1.39 V | 0.96 V | 0.89 V |
| Eon / Eoff | 0.85 / 1.53 uJ | 0.98 / 1.89 uJ | 1.39 / 4.71 uJ | 1.50 / 5.44 uJ |

- **dV/dt:** 10-90 % rising is 1.2-2.9 V/ns, falling 0.2-1.3 V/ns; it is
  fastest at light load.  The top of the rising edge snaps at 5-13 V/ns.
  At high VDS, Crss falls to ~50-66 pF, so the 0.66 A gate current slews
  the node at ~10 V/ns.  That fast tail, faster than the ~8 ns ring period,
  excites the loop.
- **Overshoot:** LS peaks at 15 A are 37.2 / 41.3 / 45.9 V for 1 / 2 / 4 nH
  (25 C).  Above 40 V the real part avalanches: V(BR)DSS is ~40 V typical
  at 25 C (Fig 8.7).  The model has no breakdown, so these are would-be
  values.  With 22 / 10 ohm gates: 29.7 V (15 A, 2 nH) and 39.4 V (30 A,
  4 nH) motoring; 32.2 / 37.7 V braking.
- **Miller bump and shoot-through (1.5):** the 0.7 V goal is not reached by
  any option, snubbers included.  The bump is 1.4-1.7 V on the off low side
  at light load and 1.8-2.0 V on the off high side when braking (150 C).
  Partly it comes from Cgd coupling, partly from the 0.25 nH common source
  inductance ringing.  To test whether it matters, the 150 C runs were
  repeated with a minimum-Vth part (threshold 0.55 V below typical).  The
  switching energy changed by at most 11 %, and that comes from a slower
  turn-off.  The braking edge changed by under 8 %, and the high side's
  peak current during the low side's turn-on rose by under 0.5 A.  The
  bumps last 3-10 ns, too short to turn a die on measurably in this model.
  A gate-source cap does not reduce the high-side bump (it was tried on the
  low side only, where it brings that bump to 0.85 V).
- **Losses** (`losses.png`, `../losses.csv`), per motor (one ESC, six FETs,
  two conducting at a time), 6-step with complementary PWM, switching
  every cycle, RDS(on) datasheet maximum x Fig 8.9, **with the
  recommended 22 / 10 ohm gates**:

| per motor, 15 A | Pcond | Psw | Pdead | FETs total | + shunt |
|---|---|---|---|---|---|
| 24 kHz, Tj 25 / 100 / 150 C | 1.01 / 1.36 / 1.71 W | 0.19 / 0.20 / 0.22 W | 0.65 / 0.53 / 0.44 W | 1.85 / 2.09 / 2.37 W | +0.11 W |
| 48 kHz, Tj 25 / 100 / 150 C | 0.98 / 1.32 / 1.66 W | 0.38 / 0.41 / 0.43 W | 1.30 / 1.06 / 0.89 W | 2.66 / 2.78 / 2.98 W | +0.11 W |

  At 30 A, 150 C: 8.3 W (24 kHz) / 9.5 W (48 kHz) per motor.

**`losses.csv`**: one row per PWM frequency (24 / 48 kHz), Tj (25 / 100 /
150 C) and phase current (0-30 A in 1 A steps), for the recommended 22 / 10
ohm gates.  Columns: fpwm_hz, tj_c, phase_current_a, pcond_w, psw_w,
pdead_w, ptotal_w (the six FETs), pshunt_w, psnub_w (0: no snubber; the
column is kept so readers do not break), pboard_w.  Multiply by four for
the board.

**Limitations:** this is not Toshiba's model.  Package L is estimated and
the PCB is swept, not extracted.  The 30 A / 4 nH margin of the 22 / 10 ohm
gates (0.6 V) is inside the model's uncertainty: it is an abuse case at
twice the motor's rating, but measure the switch node on the first board.  There is no avalanche, no skin-effect
damping and no clamp diodes on the driver pins (so the GLx undershoot is a
would-be value).  The motor is an ideal current source.  Losses assume
PWM every cycle (at 100 % duty Psw = 0 and Pdead is about 0).  The dead
time is taken as additive.

## 2. Battery-lead spikes (`battery/`)

**What is modelled:** pack 17.4 V + 25 mOhm; lead 150 nH (and 100 nH) +
6 mOhm; 470 uF with ESR 30/40/60 mOhm and 8 nH; 1 nH of plane (1 ohm across
it, for HF loss); ceramics 26 uF / 0.5 mOhm (13 x 4.7 uF at ~2 uF each +
100 nF).  SMF22A: conducts from 26.9 V (VBR max) with 1.5 ohm, giving
35.5 V at 5.6 A.  The four ESCs are one current source.

| scenario | peak VBAT | TVS |
|---|---|---|
| a. 60 A released in 1 us, 470 uF (ESR 30-60), 100-150 nH | 17.4-17.9 V | off |
| b. brake +60 A -> -20/-30/-40 A in 20 us, held 5/20 ms (ESR 60) | 18.0 / 18.3 / 18.6 V | off |
| c. a without the electrolytic | 19.7 V (100 nH) / 20.5 V (150 nH) | off |
| c. b without the electrolytic | 18.6 / 19.0 / 19.4 V | off |
| f. hot plug, 470 uF / without | 17.4 V (overdamped) / 26.4 V | off / at the knee |
| e. PWM ripple, 4 ESCs in phase, worst / hover, 24 kHz | 17.5 V (1.7 / 0.65 V p-p) | off |
| e. same without the electrolytic | 19.6 V (6.8 / 2.3 V p-p) | off |
| d. pack unplugged, braking 20 A for 5 ms, with / without 470 uF | 56.8 / 56.9 V | 5.0 / 5.7 J: destroyed |

Against the limits (FETs 40 V, electrolytic 35 V, MLCCs 50 V, TPS7A1601 IN
62 V abs / EN 62 V, LMR36506 70 V, DRV8300 110 V), every scenario except d
leaves at least 13.6 V to the FETs.  In d, VBAT is over the FET, MLCC and
electrolytic ratings; only the LMR36506, TPS7A16 and DRV8300 survive.
Regenerative braking with the pack connected is mild: the energy goes into
the pack at 40 A x 31 mOhm = 1.2 V of rise.

**Limitations:** the network is lumped and the ESCs are an ideal current
source.  Real braking current depends on AM32's brake settings and the
props.  ESR is flat with frequency.  Ripple heating for free-running ESCs is
taken as the in-phase rms / 2 (four uncorrelated sources).  The TVS energy
limit scales the 200 W, 10/1000 us rating as t^-0.5 and derates it to 50 %
at a 100 C board.

## 3. Gate-drive supply (`gate_supply/`)

**What is modelled:** VBAT -> 10 ohm -> 2 uF -> TPS7A1601.  The LDO is a
macro-model: 10.98 V, 0.2 ohm, a 5 us lag (the TPS7A16 is a 5 uA-IQ, slow
part, so the caps carry the gate pulses), a 101 mA current limit and a
5 ohm dropout.  The rail has 4 uF at the LDO and 4 uF at each of four
drivers, each 3 nH / 30 mOhm away.  Per driver: 1.4 mA quiescent, bootstrap
leakage 220 uA switching and 150 uA static, a 45 nC low-side gate pulse
and a 45 nC bootstrap refill through the diode, all four ESCs in phase at
50 %.

- GVDD ripple at a driver: 13 mV p-p (24 and 48 kHz).  The LDO draws
  15.7 / 24.3 mA average at 24 / 48 kHz.
- LDO: 80-151 mW, giving Tj 101-102 C with RthJB 11.3 (board 100 C), or
  104-107 C using RthJA 44.5 on top of 100 C.  The limit is 125 C.  The
  10 ohm dissipates 6 mW.
- Bootstrap: 10.0-10.2 V after a high-side turn-on; the 45 nC gate charge
  costs 0.11 V of the 0.4 uF.  Held on (100 % duty), it droops at 213 V/s
  typ / 375 V/s max (ILBS_DC 85 / 150 uA) and reaches BSTUV (4.0 typ /
  4.5 V max falling) after 29 / 14.7 ms.  A 120-degree on-time lasts that
  long only below 690 / 1360 eRPM, i.e. 99 / 194 rpm on the 7-pole-pair
  1404.  That is a stalled motor at full throttle; spinning at any useful
  speed, the bootstrap is refreshed every commutation.  Below 100 % duty
  it is refreshed every PWM cycle.  Even when the low side never turns on
  (duty above ~89-94 %, where the dead times eat the off time), the body
  diode pulls SH low during the dead time and recharges it.
- Sagging pack: GVDD = VBAT - 0.36 V below 11.3 V.  3S at 3.0 V/cell gives
  8.6 V GVDD and 7.7 V VBST.  2S at 3.0 V/cell gives 5.6 V and 4.7 V, just
  above the 4.5 V worst BSTUV.  Below 5.77 V of pack (2.88 V/cell on 2S,
  worst-case parts; 5.11 V typical) a high side can trip BSTUV.  The 5 V BEC
  drops out at a similar point (~5.3-5.5 V in), so the gate drive is not
  the 2S limit.  FET RDS(on) at VGS 5 V is ~2.5-3 mOhm (Fig 8.4), fine.

**Limitations:** the LDO is a macro-model, not TI's.  Gate charge at 11 V is
extrapolated from the 10 V figure.  Bootstrap droop uses the datasheet's
leakage maxima, which are specified at 20 kHz switching.

## 4. 5 V BEC (`bec/`)

**What is modelled:** closed-form checks from SNVSBB6C at the worst corner
(L -20 % = 8 uH, fSW 2.1-2.3 MHz).  An ideal-switch ngspice model uses the
RDS(on) maxima (0.92 / 0.46 ohm), DCR x 1.3 and 26 uF effective output.
The loss model is Irms^2 R + Vin I tsw f + Vin^2 Csw f + Pfix, fitted to
TI's efficiency curves (Fig 6-3 / 6-4: 400 kHz and 1 MHz, 5 V fixed):
tsw 3.4 ns, Csw 135 pF, Pfix 64 mW, residuals within 35 mW.  It is then
evaluated at 2.2 MHz with hot RDS(on).  TI's PSpice model is encrypted and
does not run in ngspice.

- Ripple: 0.16 A p-p typ, 0.21 A worst at 17.4 V (27-35 % of 0.6 A; TI
  recommends 20-40 %).  Peak 0.706 A at 0.6 A vs 0.87 A ISC min (23 %
  margin).  Inductor Isat 2.4 A (parts.py description; the Sunlord sheet
  is not in out/ds, verify).  Simulated IL is 0.49-0.71 A, and VOUT
  ripple 1.1 mV p-p.
- On-time at 17.4 V, 2.3 MHz: 125 ns vs 80 ns max.  Foldback would only
  start above 27 V in.  Maximum duty at 2.3 MHz is 0.82, so the part folds
  its frequency below ~6.1 V in, as designed.
- Output capacitance: 2 x 22 uF rated, which is TI's nominal 1 MHz value
  and twice its minimum.  Subharmonic limit L >= 3.6 uH; we have 8-10 uH.
- Dissipation at 17.4 V, 2.2 MHz: 0.26-0.30 W at 0.35 A and 0.42-0.48 W at
  0.6 A (IC only; the inductor adds 21 / 61 mW).  Efficiency is 86 %.
  Tj = 100 C + P x 25.9 C/W (PsiJB) = 107-108 C / 111-112 C, against
  150 C (thermal shutdown 158 C min).
- **2.2 MHz vs 1 MHz:** 1 MHz would save ~70-90 mW, but with the fitted
  10 uH the ripple becomes 0.48 A p-p.  The peak at 0.6 A is then 0.84 A
  against the 0.87 A current limit, and the subharmonic floor rises to
  8.1 uH, the inductor's -20 % value.  1 MHz needs a 22 uH inductor
  (bigger).  **Keep 2.2 MHz** with this inductor.

**Limitations:** the efficiency points are read off log-axis plots
(+-1 %), and 2.2 MHz is an extrapolation from two frequencies.  The thermal
path is the JEDEC PsiJB, not this board.

## 5. Sense chains (`sense/`)

**(a) Current.**  0.5 mOhm x 100 = 50 mV/A, and x 1k / 2.5k = **20.0 mV/A**
at PA5.  The filter is a 600 ohm Thevenin with 100 nF, giving fc 2.65 kHz.
The INA186 swings to ~3.2 V, so full scale is **64 A** (the ADC sees
1.28 V and never clips); 1 LSB is 0.04 A.  Error: offset 0.10 A (VOS) +
0.075 A (drift over 75 C).  Gain: 1 % (INA) + 1 % (shunt) + 1.5 % (shunt
TCR 200 ppm/C over 75 C) + 1.2 % (1 % divider) + 0.08 % = 4.8 % worst,
2.4 % RSS.  At 15 A that is +-0.89 A worst case.  The shunt sees a pulse
train (the phase current while the high side is on).  Through the INA186's
35 kHz and 0.3 V/us the average is within 0.04 % for 5-15 A at any duty,
and reads 1-1.9 % low at 30 A with 5 % duty.  Regenerative current reads
0, since the amplifier is unidirectional.
**CUR (FC PB1): 12.02 mV/A** of total current (ibata_scale 120), fc
662 Hz.  The ripple with four ESCs in phase at 15 A, 50 % duty is 22 mV p-p
(1.8 A) at 24 kHz and 10 mV at 48 kHz.

**(b) Back-EMF** (`bemf.png`, 60k eRPM, 48 kHz, 50 % and 98 % duty).
CMP_x - NEUTRAL = (V_x - mean of the three phases) / 6.545.  With the
neutral held, the effective ratio is (10k || 2.2k) / (10k + 10k || 2.2k) =
1/6.545, against 1/5.545 unloaded.  Each phase alone gives 1/6.174 at its
CMP pin.  The floating phase's comparator crosses zero exactly where its
back-EMF does, for PWM-on samples, as the plot shows.  The highest steady
CMP voltage is 3.28 V, when all phases are at VBAT + 0.8 V while coasting;
that leaves 0.32 V under VDDA + 0.3 V.  The lowest is -0.13 V.  With 1 %
resistors (Monte Carlo, 2000 boards), the comparator offset is 58 mV typ
and 210 mV at the 99th percentile.  That shifts the zero crossing by 3.5 /
12.6 electrical degrees at startup (back-EMF 0.5 V) and by under 1 degree
at speed.  Switching-node spikes reach the pins divided:
the as-drawn 41 V overshoot gives 6.6-7.4 V, at the FT_a pin's 7.3 V
absolute maximum.  The snubbed 24 V gives 3.9-4.3 V.  The pin capacitance
smooths these ns spikes further.

**(c) Battery dividers.**  FC 10k / 1k and ESC 100k / 10k are both ratio
11.0 (scale 110), giving 1.58 V at 17.4 V and 36.3 V full scale (3.23 V at
the TVS clamp), +-1.8 % with 1 % parts.  The FC divider has 100 nF (91 us).
The ESC divider has none and is a 9.1 kohm source: see recommendation 6.

**Limitations:** the INA186 is behavioural (bandwidth, slew, rails; no
chopper ripple).  The motor is ideal: balanced, trapezoidal, no winding
inductance in the floating phase, no demagnetisation tail after
commutation (AM32 blanks that).  The comparator's own offset and
hysteresis are not included.
