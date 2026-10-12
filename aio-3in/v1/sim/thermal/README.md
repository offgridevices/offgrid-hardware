# Thermal simulator

Steady-state and transient temperatures of the whole board (every copper layer, every FET junction, every part
with a rating), read straight from the `.kicad_pcb`. The question it answers is the owner's: does the drone
keep working under full stress on a hot day in the desert?

```
cd aio-3in/v1
tools/kd python3 sim/thermal/thermal.py aio3.kicad_pcb --case desert          # the worst-case set, ~6 min
tools/kd python3 sim/thermal/thermal.py aio3.kicad_pcb --case full-50C-wash-sun   # one steady case, ~30 s
tools/kd python3 sim/thermal/thermal.py aio3.kicad_pcb --case full60-50C-wash-sun # 60 s full throttle, ~1.5 min
tools/kd python3 sim/thermal/thermal.py --list                                 # every load, profile and set
tools/kd python3 sim/thermal/validate.py                                       # checks 1-4 below, ~10 s
```

Results go to `out/thermal/<board>/` (gitignored):

- `<case>.json` holds every number.
- `<case>_parts.csv` lists every heat source and rated part: pad mean/max, junction, rating and power.
- `<case>_layers.png` maps all copper layers.
- `<case>_top_bottom.png` shows both faces with parts outlined and junction temperatures written on them.
- For transients there is also `<case>_transient.png` and `.csv` (FET junction max/mean, board max/mean and
  wire max against time).
- For a transient, the maps and tables are taken at the moment of the hottest FET junction.

Options:

| Option | What it does |
|---|---|
| `--cell 0.1` | Finer grid. Use it to check narrow diagonal traces (see Limits). Roughly 4x the nodes. |
| `--inner-oz 1` | Overrides the inner copper weight. |
| `--outer-oz` | Overrides the outer copper weight. |
| `--fr4-xy 0.8` | Optimistic in-plane FR-4 conductivity. |
| `--emissivity` | Surface emissivity. |
| `--via-fill 0.5` | Conductivity of epoxy-filled (POFV) vias, W/mK. |
| `--losses` | Another loss table. |
| `--dt` | Transient time step. |
| `--profile` | Part mapping, when the refs are not recognised. |

## Case names

`<load>-<ambient>-<air>-<sun>`, for example `full-50C-wash-sun`. Defaults are `25C-wash-shade`.

| load | per motor (battery side) | duty | air over board top* | motor wires | motor can |
|---|---|---|---|---|---|
| idle | 0 A (armed, on the ground) | - | still | still | ambient |
| hover | 3.5 A | 0.35 | 2.5 m/s | 6 m/s | +20 K |
| cruise | 7 A | 0.55 | 6 m/s | 9 m/s | +35 K |
| full | 15 A | 1.0 | 8 m/s | 12 m/s | +55 K (80 C at 25 C ambient) |
| abuse | motor 1 stalled (prop jammed), 25 A phase at D 0.3; others hover | | 2.5 m/s | 6 m/s | +20 K |
| abuse4 | 28 A, all four | 1.0 | 8 m/s | 12 m/s | +60 K |
| stall | motor 1 locked rotor, 30 A phase (D 0.3), others cruise | | 6 m/s | 9 m/s | +35 K |
| demo | 2 W per FET package, no copper/wire current (sanity demo) | | 6 m/s | 9 m/s | +35 K |

\* The bottom gets half the top's air speed, because the frame plate shields it. `still` sets every speed to 0
(natural convection only). `halfwash` keeps the speeds but halves every forced-convection h (board and wires):
the pessimistic case.

Motor wires: 26 AWG x 60 mm. Battery leads: 18 AWG x 80 mm.

| Transient profile | Starting point | Sequence | Step |
|---|---|---|---|
| `punch` | steady hover | 8 x (10 s hover + 3 s full) + 10 s hover | 0.25 s |
| `full60` | steady hover | 60 s full (the motor maker's limit) + 30 s hover | 0.2 s |
| `full30` | steady hover | 30 s full + 20 s hover | 0.2 s |
| `abuse2` | steady cruise | 2 s abuse (one motor stalled at 25 A) + 10 s hover | 0.05 s |
| `abuse42` | steady cruise | 2 s abuse4 + 10 s cruise | 0.05 s |
| `stall2` | steady cruise | 2 s locked rotor + 10 s cruise | 0.05 s |

Sets:

- `desert` is the 50 C, sun case list:
  - steady: idle in still air, hover, cruise and full in prop wash, and full in still air as the bound;
  - transient: `full60`, `punch`, `abuse2` and `stall2`.
- `matrix` is idle, hover, cruise and full x {25C, 50C} x {still, wash} x {shade, sun}.
- `report` is hover, cruise, full, full60 and abuse2 x {25C, 50C} x {wash, halfwash} x {shade, sun}: 40 cases,
  about 25 min. Afterwards `tools/kd python3 sim/thermal/report.py out/thermal/<board>` writes `classes.md`,
  the hottest part of each class per case with the margin to its limit.
- `quick`, `ridge` and `tosh` are smaller sets.

The Ridge 3 Lite run (until its stackup block is in the file) is:

```
tools/kd python3 sim/thermal/thermal.py BOARD --inner-oz 1 --outer-oz 1 --stack 0.1,0.5,0.18,0.5,0.1 --case report
```

The dielectrics are approximate figures for JLC's 6-layer 1.6 mm build. `--stack` overrides the file's
dielectric thicknesses (mm, top to bottom).

Capacitors are sorted into classes by their LCSC number: C437557 (GRM21BZ71H475KE15L) and C307331
(CL05B104KB54PNC) are X7R (125 C); all others are X5R (85 C rated, usable to 105 C derated).

The battery current is per motor. Phase current = battery current / duty, because the loss table and the wires
need the phase current.

**Copper what-ifs.** `tools/kd python3 sim/thermal/whatif.py [BOARD]` (about 25 min) does three things on a placed
board and writes `results-placed.md`:

- breaks the copper I^2 R down by net, layer and via region, with the top 10 hot spots;
- reports the path resistances;
- re-runs full60 at 50 C with the copper changed:
  - a: GND fill plus stitching vias;
  - b: a plus vias at the battery pads and R_S1;
  - c: b with 2 oz inner layers;
  - d: b with 2 oz outer layers;
  - e: b with an AM32-style per-channel current cap that holds each ESC MCU at 100 C.

Edits are made on the rasterised copper (`Geom.add_copper`) and the via list, so no KiCad file is touched.

## The model

**Grid.** Square cells, 0.2 mm by default, over the board outline. Cells with less than half their area on the
board are dropped. Each cell has one node per copper layer.

**Copper.** Copper is rasterised at 8 sub-pixels per cell (0.025 mm) from pcbnew, after `ZONE_FILLER` has
refilled every zone. The rasteriser takes zones' filled polygons, tracks, arcs, pads, via pads on every layer
they flash, and copper graphics. The rim of each shape counts half, to undo PIL's half-pixel fill overspill.

**In-plane conductance between cells.** Each node carries its copper (k = 390 W/mK) and half of each adjacent
dielectric (k = 0.3 W/mK). The conductance between neighbouring cells is computed from the sub-pixels between
their centres: `max(lower, min(frac, upper))`.

- `lower` is the parallel sum of series rows.
- `upper` is the series sum of parallel columns.
- `frac` is the harmonic mean of the cells' area-averaged conductivity.

The effect: a 0.1 mm gap between two pours stays an insulator although it is narrower than a cell, straight
traces are exact, and diagonal traces conduct.

**Through-thickness.** Between two copper layers: half of each copper layer (k = f x 390 + (1 - f) x 0.3, where
f is the copper fraction) plus the dielectric at k = 0.3. Each dielectric's heat capacity is split half to each
side.

**Vias and plated holes.** A copper barrel (plating 18 um, k = 390) plus the fill (`--via-fill`, air by
default). The barrel joins its two end layers and every layer where its own net's copper reaches it (checked on a
ring just outside its pad). On the other layers it passes through an antipad, so the barrel bypasses that
layer's node; a VBAT via does not tie into the In1 GND plane. NPTH holes are cut out of the board.

**Stackup.** Read from the board file's `(stackup)`. If the file has none, it is 1 oz outer / 0.5 oz inner with
the dielectrics `src/pcb.py` writes for 6 layers: 0.10 / 0.40 / 0.45 / 0.40 / 0.10 mm.

**Heat sources.** Each part's power goes in at its pads on its own side.

- Parts with a junction-to-board resistance get a junction node. The node is tied through Rth to the pads that
  carry its heat: for a TSON FET these are the drain pads 5-9, at Rth(ch-c) = 1.43 K/W.
- The node attaches to 9 representative cells spread over those pads. A node tied to hundreds of cells makes
  the sparse factorisation take minutes instead of seconds.
- The package's copper leadframe (0.2 mm) is added to the lateral conductance under those pads, so the heat
  spreads as it does from a real die.
- Junction capacity: 3.5 mJ/K. This is Toshiba's Zth(ch-c) (Fig. 8.13) settling in about 5 ms, divided by
  1.43 K/W.
- Every package also adds side-wall convective area (perimeter x height) and body heat capacity
  (volume x 1.8 MJ/m3K) to its pad cells. The height comes from the 3D model's name (`-H0.9`) or a table.

**FET losses.** From `sim/losses.csv` (the switching study, `sim/halfbridge/run.py`). For each phase current and
junction temperature (25/100/150 C, interpolated, extrapolated linearly) the table gives the conduction,
switching and dead-time loss of one motor's six FETs at 24 kHz. Each component is shared by the FETs that carry
it under AM32's 6-step complementary PWM:

- Each phase is the PWM phase 1/3 of the time and the return phase 1/3. Each FET's share of the conduction loss
  is the fraction of time it conducts:
  - high side: D/3;
  - low side: (2 - D)/3 (pwm-phase low side plus the return phase).
- The high side takes the switching loss and the low side's body diode the dead-time loss, 1/3 each.
- Locked rotor: phase A high side (D) and low side (1 - D), phase B low side (always on).
- Each FET is evaluated at its own junction temperature every iteration (or every time step), so R_DS(on)(T)
  feeds back.
- Without a table, a built-in model is used: datasheet R_DS(on) max with the Fig. 8.9 temperature fit, tr + tf,
  Qoss, and 1.155 us dead time per edge.

**Other parts (AIO profile).**

| Part | Loss | Note |
|---|---|---|
| Shunt | I_batt^2 x 0.5 mOhm | |
| U_FC STM32G473 | 0.10 W | Designer: under 0.1 W |
| ESC MCUs | 0.05 W each | Designer: 30-80 mW |
| DRV8300s | 2 Qg Vg f + 11 mW | |
| U_GVDD | 0.10 W with motors running | `sim/gate_supply/results.txt`, 24 kHz, maximum currents |
| BEC | 0.30 W, plus 0.021 W in L_BEC | `sim/bec/results.txt`: 0.35 A at 5 V, 2.2 MHz, 17.4 V in, worst case |
| U_LDO | 1.7 V x 0.12 A | |
| U_LDOE | 1.7 V x 0.045 A | |
| IMU, flash, crystal, USB, all capacitors | ~0 | Monitored against their ratings |

**Copper I^2 R.** The DC current flow in each power net is solved on the same grid: the copper of that net only,
resistivity 1.72e-8 ohm m, with via barrels.

- Sources and sinks:
  - VBAT: battery pad to the high-side drains;
  - GND: the shunts to the battery pad;
  - each SRC: the low-side sources to the shunt;
  - each phase: high-side source or low-side drain to the motor pad, weighted by the fraction of time each
    conducts.
- Heat is dissipated where the current flows (necks show up). It scales with 1 + 0.00393 (T - 20) cell by cell.
- The path resistance of each net is printed: the "copper path" lines.

**Wires.** Twelve motor wires and two battery leads are 1-D chains of 10 nodes from the pad.

- Motor wires: 26 AWG (0.405 mm copper, 0.25 mm silicone), 50 mm long, far end held at the motor can's
  temperature.
- Battery leads: 18 AWG (1.024 mm, 0.4 mm silicone), 80 mm, far end at the pack (ambient +5 to +10 K).
- Each segment has copper conduction, copper + insulation heat capacity, and Joule heat I^2 rho(T)/A.
  - Motor wires carry the phase RMS, I_ph sqrt(2/3).
  - Battery leads carry the total battery current.
- Each segment loses heat to the air through the silicone (k 0.2) in series with cylinder convection
  (Churchill-Bernstein forced + Churchill-Chu natural, cubic blend) plus radiation.
- They are fins when the board is hotter than the motor, and heaters when the motors or their own I^2 R are
  hotter.
- The solder joint is 50 W/mK over 0.1 mm across the pad.

**Surfaces.**

- Natural convection uses each face's own local temperature:
  - hot face up: Nu = 0.54 Ra^1/4 (Incropera eq. 9.30);
  - hot face down: Nu = 0.52 Ra^1/5 (Incropera 7th ed. eq. 9.32);
  - L = area / perimeter.
- Forced convection: Nu = 0.664 Re^1/2 Pr^1/3, the laminar flat plate over the board's side (eq. 7.30). It is
  combined with natural convection as (h_n^3 + h_f^3)^(1/3).
- Air properties: Incropera Table A.4 at the film temperature, 1 atm.
- Radiation: eps sigma (T^4 - Ta^4), with eps 0.9 for solder mask, from each face to surroundings at ambient.
- Sun: 1000 W/m2 x absorptivity 0.9 (black mask) on the top's plan area.

Typical values for this 34 mm board:

| Mechanism | h, W/m2K |
|---|---|
| Natural, top, 20-50 K rise | 9-12 |
| Natural, bottom, 20-50 K rise | 6.5-8 |
| Forced, 2.5 m/s | 33 |
| Forced, 6 m/s | 51 |
| Forced, 8 m/s | 59 |
| Forced, 15 m/s | 81 |
| Radiation, 80-125 C surface against 50 C | 8-10 |
| Wire, 0.9 mm OD, still air | 29 |
| Wire, 0.9 mm OD, 12 m/s | 380 |

**Prop wash.** Momentum theory, v_i = sqrt(T / (2 rho A)), with A = pi x (38.1 mm)^2 = 4.56e-3 m2 for a 3" prop
and rho = 1.09 kg/m3 at 50 C:

- hover, 250 g all-up, 0.61 N per motor: 7.8 m/s at the disk;
- full throttle, about 2.7 N per motor: 16.5 m/s;
- the far wake doubles both.

The board sits in the middle of the frame, between the four disks rather than in their wake. It sees the inflow
the props draw past it and the forward-flight wind, so the speeds over it are taken as about a third to a half
of v_i: 2.5 / 6 / 8 m/s. The motor wires run under the disks: 6 / 9 / 12 m/s. These numbers are the biggest
judgement call in the model. Forced h goes as v^1/2, so halving every speed raises the board's rise above
ambient by roughly 25-35 %. The `still` cases bound that end.

**Solver.**

- The network is symmetric, assembled with scipy.sparse and factored with SuperLU (`MMD_AT_PLUS_A` ordering).
- Steady state: fixed point on the nonlinear terms (radiation, natural convection, R_DS(on)(T), copper and wire
  resistivity(T)).
  - The surface conductance is kept in the matrix (refactored when it drifts by more than 25 %) and the
    difference goes on the right-hand side.
  - It converges in 5-20 iterations, and the energy balance closes to about 1e-5 W.
- Transient: implicit Euler with one factorisation per run. Surface and loss terms lag one step.
- A solution past 600 C is reported as "NO STEADY STATE": losses grow with temperature faster than the board can
  shed them.

## Materials and constants

| Quantity | Value | Source / reason |
|---|---|---|
| Copper k | 390 W/mK | Pure Cu 401 (Incropera Table A.1); foil a little lower |
| Copper rho x cp | 8930 x 385 = 3.44 MJ/m3K | Incropera Table A.1 |
| Copper resistivity | 1.72e-8 ohm m, +0.393 %/K | Annealed copper (IACS 1.724e-8) |
| FR-4 k | 0.3 W/mK, through and in-plane | Through-plane 0.3 is the usual laminate figure. Glass-weave laminates measure higher in-plane (about 0.8). 0.3 isotropic is what reproduces Toshiba's two Rth(ch-a) numbers (Validation), so it is the default; `--fr4-xy 0.8` is the optimistic bound |
| FR-4 rho x cp | 1900 x 1100 = 2.09 MJ/m3K | rho 1.85-1.95 g/cm3, cp 1.1-1.2 J/gK |
| Via plating | 18 um | IPC-6012 class 2: 20 um average, 18 um minimum; the low end is taken |
| Solder mask emissivity | 0.9 | Epoxy / LPI mask |
| Solder mask solar absorptivity | 0.9 | Black mask |
| Solar irradiance | 1000 W/m2 | Standard clear-sky figure; desert noon reaches it |
| Package body rho x cp | 1.8 MJ/m3K x 0.9 fill | Mould compound / ceramic. TSON: 0.017 J/K against 0.029 g x ~600 J/kgK from Toshiba's weight |
| TPN2R304PL | Rth(ch-c) 1.43 K/W; Tch 175 C; R_DS(on) 2.3 mOhm max at 10 V | Datasheet section 5. R_DS(on)(T) from Fig. 8.9 (via losses.csv) |
| LMR36506 | RthJB 26.1 K/W; Tj 150 C | Datasheet 6.4 |
| DRV8300 RGE | RthJC(bot) 11.5 K/W; Tj 150 C | Datasheet 7.4 |
| TLV767 DRV | RthJC(bot) 18.9 K/W | Datasheet |
| TPS7A16 DRB | RthJC(bot) 4.7 K/W | Datasheet |
| STM32G473 | Rth junction-board 30 K/W | Designer's figure for the UFQFPN |
| STM32G071 | Rth junction-board 30 K/W | Designer's figure for the UFQFPN |
| STM32 suffix 6 | Tj max 105 C | STM32G071 datasheet, "Suffix 6" |
| ICM-42688-P | 85 C | Operating range |
| W25Q128JV-IM | 85 C | Operating range |
| X5R MLCC | 85 C | Rating |
| HCS1206 shunt | 170 C | Datasheet |
| 26 AWG | 0.405 mm, 0.129 mm2 | Standard AWG table |
| 18 AWG | 1.024 mm, 0.823 mm2 | Standard AWG table |
| Silicone insulation | k 0.2 W/mK | |

## Validation (`validate.py`)

Run with the defaults: 0.2 mm cells, FR-4 0.3 W/mK, emissivity 0.9.

**1. Spreading in a copper plate.** A 1 oz copper disc, 20 mm radius, 1 W over r < 1.5 mm, h = 10 W/m2K on each
face. Compared with the exact Bessel-function solution of the circular fin:

| r, mm | 0 | 3 | 6 | 10 | 18 |
|---|---|---|---|---|---|
| model, K | 66.61 | 53.30 | 45.56 | 40.64 | 37.20 |
| exact, K | 66.62 | 53.30 | 45.54 | 40.61 | 37.15 |

All within 0.1 %.

**2. Through-thickness.** 1.53 mm FR-4 between two copper layers, 1 W uniform over 20 x 20 mm, h only under the
bottom. Top-to-bottom difference: 12.750 K against q t / k = 12.750 K.

**3. Transient.** A 1 oz plate heated uniformly: tau = 6.02 s, the same as rho c t / 2h by hand. The temperature
at 0.5, 1, 2 and 3 tau is within 0.3 % of 1 - exp(-t/tau) with 0.05 s implicit-Euler steps.

**4. Toshiba's own mounting tests.** These are the key check. The TPN2R304PL datasheet gives Rth(ch-a) =
56 C/W on board (a) and 235 C/W on board (b), Ta = 25 C.

- Board (a), Note 3, Fig. 5.1: FR-4 25.4 x 25.4 x 1.6 mm, 2 oz, one face almost all copper, split into a drain
  half and a source half.
- Board (b), Note 4, Fig. 5.2: the same board with only the footprint and thin traces to three test pads. The
  trace widths are not given; 0.3 mm is assumed.

`validate.py` draws both boards with pcbnew around the AIO's own `og:TSON-8` footprint, saves them as
`.kicad_pcb`, reads them back through the normal KiCad path and applies Toshiba's PD (2.67 W and 0.63 W, which
give Tch = 175 C at Ta = 25 C) in still air, board horizontal:

| Board | FR-4 in-plane | Top emissivity | PD | Tj | Rth(ch-a) model | Datasheet |
|---|---|---|---|---|---|---|
| (a) | 0.3 | 0.9 | 2.67 W | 173.7 C | **55.7 C/W (-1 %)** | 56 |
| (a) | 0.3 | 0.15 (bare copper) | 2.67 W | 192.4 C | 62.7 (+12 %) | 56 |
| (a) | 0.8 | 0.9 | 2.67 W | 164.1 C | 52.1 (-7 %) | 56 |
| (a) | 0.3 | 0.9 | 1.00 W | 89.2 C | 64.2 (+15 %; natural convection and radiation weaken at a lower rise) | - |
| (b) | 0.3 | 0.9 | 0.63 W | 175.7 C | **239 C/W (+2 %)** | 235 |
| (b) | 0.3 | 0.15 | 0.63 W | 189.6 C | 261 (+11 %) | 235 |
| (b) | 0.8 | 0.9 | 0.63 W | 129.3 C | 166 (-30 %) | 235 |

The defaults reproduce both datasheet numbers within 2 %. Those are a copper-dominated board and an
FR-4-dominated board, a factor of four apart in Rth, so the copper, laminate, junction and surface models are
right together. They are not merely compensating each other on one geometry.

Board (b) is the sensitive one: it rests almost entirely on the laminate's in-plane conductivity. Toshiba's
numbers are consistent with 0.3 W/mK isotropic FR-4 (probably how they were computed), so that is the default.
Measured glass-weave laminates reach about 0.8 in-plane, so the default errs hot. On a 6-layer board with
planes the choice moves results by only a few percent: run `--fr4-xy 0.8` to see the difference.

**5. Copper resistance (the I^2 R solve).** A 1 oz strip, 20 mm long, fed over a 2 mm pad at each end (scratch
test, `out/thermal/scratch/strip.py`). Model resistance over exact:

| Strip | 0.2 mm cells | 0.1 mm cells |
|---|---|---|
| Straight, 2 mm and 0.3 mm wide | 0.99 / 0.98 | |
| 45 degrees, 2 mm | 1.04 | 1.01 |
| 45 degrees, 1 mm | 1.08 | 1.04 |
| 45 degrees, 0.3 mm | 1.46 | 1.12 |

**6. Grid convergence on a real board.** The Ridge at full throttle, 50 C, sun:

| Cells | Hottest FET junction | VBAT path | GND path | Run time |
|---|---|---|---|---|
| 0.2 mm | 425.9 C | 1.86 mOhm | 1.37 mOhm | 20 s |
| 0.1 mm | 428.4 C | 1.83 mOhm | 1.36 mOhm | 3.5 min |

The Toshiba test boards give the same Rth at 0.1 and 0.2 mm.

**7. Energy balance.** Every steady case prints its energy balance: heat in against heat to the air and into the
wires' far ends. The error is about 1e-5 W.

## Demonstration on the Ridge-3 ESC

`out/r3/ridge-3/esc/ridge3-esc.kicad_pcb`: 36 x 36 mm, 6 layers, 1 oz outer / 15 um inner. It carries twelve
AON7934 dual FETs, on the bottom.

The Ridge is not the AIO, and several of its inputs are borrowed:

- The AON7934 junction-to-tab Rth is assumed at 4 K/W; its datasheet is not in `out/ds`.
- The losses come from the TPN2R304PL table, with the high-side die on tab 9 and the low-side die on tab 10.

So these numbers show what the tool does, not a verdict on the Ridge. All maps and tables are in
`out/thermal/ridge3-esc/`.

| Case | Heat in | FET Tj max | Board max | Note |
|---|---|---|---|---|
| demo-25C-wash-shade (2 W per package, nothing else) | 24.8 W | 237 C | 234 C | FETs spread 163-237 C |
| demo-25C-still-shade | 24.8 W | 342 C | 340 C | Still air cannot shed 25 W from a 36 mm board |
| hover-25C-wash-shade | 9.0 W | 68 C | 68 C | |
| idle-50C-still-sun (on the ground, armed) | 1.7 W + 1.0 W sun | 71 C | 91 C | Buck regulator 97 C |
| hover-50C-wash-sun | 10.6 W | 99 C | 98 C | |
| cruise-50C-wash-sun | 22.4 W | 139 C | 138 C | ESC1 MCU 117 C > its 105 C |
| full-50C-wash-sun, steady | 80.7 W | 426 C | 528 C | 30 W copper I^2 R, 38 W wire I^2 R |
| full-50C-still-sun | | | | No steady state (runaway) |
| full60-50C-wash-sun | | 413 C at 60 s | | The board's time constant is about 25 s, so 60 s is nearly steady |
| punch-50C-wash-sun (10 s hover / 3 s full) | | 192 C | | Q1A.LS, the 8th punch |
| abuse2-50C-wash-sun (2 s at 112 A total) | | | 600 C at 0.6 s | Runaway in In4.Cu next to the battery pads |
| stall2-50C-wash-sun (locked rotor, 30 A) | | 600 C at 1.6 s | | Q1B.LS, the FET that carries the full phase current |

The same 600 C crossings come out at 0.05 s and at 0.01 s time steps. These are runaways in the model's physics,
not numerical artefacts.

What the tool found on the Ridge:

- **The power copper dominates above cruise.** About 94 % of the VBAT current's loss is in In4.Cu and about
  93 % of GND's in In1.Cu, each a single 15 um plane. The path resistances are 1.86 and 1.37 mOhm, so 60 A puts
  11.6 W into the board at 20 C (more when hot). At 112 A, a neck in In4.Cu next to the battery pads reaches
  450 W/cm2 and runs away.
- **The wires matter both ways.** At idle they are useful fins: they roughly double the heat-sink conductance of
  the bare board. At full throttle they heat the board:
  - 18 AWG silicone leads at 60 A make 75 W/m and settle above 300 C;
  - 26 AWG motor wires at 12 A RMS make about 20 W/m.
- **The FETs are not the problem; the copper and the ESC MCUs (105 C) are.**

The same pattern is what to look for on the AIO.

## Runtime

On this machine (4 cores; SuperLU itself is single-threaded), with 0.2 mm cells, about 170-180k nodes:

| Step | Time |
|---|---|
| Reading and rasterising the board | ~1 s |
| Building the network | <1 s |
| One factorisation | ~9 s |
| Steady case (1-2 factorisations, 5-20 cheap iterations, ~30 copper-current solves cached across cases) | 10-30 s |
| Transient | ~0.12 s per step: `full60` ~1 min, `punch` ~1 min, `stall2` ~20 s |
| The whole `desert` set plus 4 more cases on the Ridge | 5 min |
| `--cell 0.1` (4x the nodes) | ~90 s per factorisation |

## Limits

- **Narrow diagonal traces.** The in-plane grid is 5-point. A trace narrower than about two cells running at 45
  degrees reads too resistive:
  - 0.3 mm trace: x1.46 at 0.2 mm cells, x1.12 at 0.1 mm;
  - 1 mm trace: x1.08 at 0.2 mm cells;
  - straight traces: within 2 %.

  Pours, planes and straight or wide traces are fine. Run `--cell 0.1` once on the final board to see whether
  anything moves.
- **Dielectric not resolved.** The dielectric is not a node of its own. Steady state is exact for it (check 2).
  In transients its heat capacity is lumped onto the copper either side, which is good for events of about 1 s
  and longer: the diffusion time of the 0.45 mm core is about 1.3 s.
- **Surroundings at ambient.** Radiation goes to ambient. A desert sky is colder (helps); hot sand under a
  drone sitting on the ground is hotter (hurts).
- **Sea-level air.** At altitude, forced h falls roughly as sqrt(density), so -13 % at 2500 m.
- **No board edges, no stack.** Edge convection is ignored (slightly pessimistic). There is no enclosure,
  canopy airflow or neighbouring board: the board is alone in the air stream.
- **Package interiors.** Package tops are at their pad temperature: the internal resistance of mould compound is
  ignored. The FET junction connects to the drain only; the source-clip path is ignored, which is pessimistic.
- **Copper current is DC.** Fixed injection points, per-net duty-weighted phase currents. The ripple currents
  in the capacitors and the switching-node AC are not in it.
- **FET losses** are whatever `losses.csv` says. That table assumes PWM switching even at full throttle, which
  is pessimistic at 100 % duty.

## What the board designer needs to give or confirm

1. **A stackup block in the board file.** `src/pcb.py set_stackup(path, inner_oz)` writes it. Without one the
   tool assumes 0.5 oz inner copper.
   - Inner copper weight, and how many layers carry VBAT and GND, is the single biggest thermal lever at
     60 A: see the Ridge.
   - For an early look, run with `--inner-oz 1`.
2. **Refs and pads.** The `aio3` profile (`cases.py`, `topology()`) keys on the names `circuit.py` uses today,
   and is picked automatically when `Q1AH` exists:
   - FETs `Q{1-4}{A,B,C}{H,L}`: drain pads 5-9 carry the junction heat; source pads 1-3;
   - shunts `R_S{n}`, pads 1/2;
   - `U_E{n}`, `U_D{n}` (exposed pad 25), `U_A{n}`, `U_FC`, `U_BEC`, `L_BEC`, `U_LDO`, `U_LDOE`, `U_GVDD`,
     `U_IMU`, `U_FLASH`, `Y1`, `J_USB`, every `C*`;
   - motor pads `P_M{n}{A,B,C}` and battery pads `P_BAT+` / `P_BAT-`.

   If any of these change, edit `topology()` and `joule_scenarios()`. Parts that are missing are skipped, so an
   unrouted or partial board still runs.
3. **Operating points**, per motor:
   - battery current and throttle for hover, cruise and full: currently 3.5 / 7 / 15 A at duty 0.45 / 0.65 / 1.0
     (depends on motor KV, prop, all-up weight and cell count);
   - motor can temperature at full throttle: assumed 80 C at 25 C ambient;
   - motor wire gauge and length as soldered: assumed 26 AWG, 50 mm;
   - battery lead gauge and length: assumed 18 AWG, 80 mm;
   - what 25-30 A "abuse" means: four motors at once (112 A from the pack, the `abuse` load) or one stalled
     motor (`stall`).
4. **Where the board sits.** Open frame, under a canopy, or stacked under a VTX. Which face sees the air and
   which the sun. These set the air speeds and the sun load, the least certain inputs.
5. **Load on the 5 V BEC.** Assumed 0.35 A (receiver, FC, ESC MCUs; no video).
6. **Temperature ratings to plan around.** The FETs (175 C) will not be the limit; these will be:

   | Part | Rating |
   |---|---|
   | STM32G473CEU**6**, STM32G071GBU**6** | Tj 105 C. Suffix 3 or 7 parts go to 125-130 C |
   | ICM-42688-P | 85 C operating |
   | W25Q128JV-IM | 85 C |
   | X5R MLCCs | 85 C |

   The tool flags every `C*` against 85 C because the board file does not say which capacitors are X7R. A
   per-ref list would sharpen that.
7. **Thermal data for the MCUs.** Rth junction-to-board for the STM32s (assumed 10 and 20 K/W) and, if a
   snubber is fitted, its resistor's loss (`psnub_w` in `losses.csv` is not yet mapped to a part).
