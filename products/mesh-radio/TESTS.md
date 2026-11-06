# Mesh Radio v1: tests and simulations

Every test and simulation for this revision, with its **v1** result so far.
How this record works across the repository:
[`docs/versioning.md`](../../docs/versioning.md). Before a v2, question each
row first (still needed? still right? anything missing? did hardware
disagree?).

> **Where this revision stands (6 Nov 2026).** Revision 1.0 is re-routed
> (70 × 25.4 mm, 6 layers) and every build gate and simulation below has a
> result on it, with the commit it ran on. The last design change is the
> firmware's antenna-fault ceiling (4763321); the board, its outputs and the
> simulations are from 260f321 to 11d3854 and did not change after. No board
> has been built, so every hardware row is empty.

Worst case used in the simulations: ambient −40, −20, 0, 25, 60 and 85 °C; a
1-cell LiPo from fresh (4.2 V, 50 mΩ) to worn (3.3 V, 300 mΩ); a 3 W
(35 dBm) burst; a sealed box at 60 °C.

Words used for results: **PASS**, **FAIL**, and **MARGINAL** (passes, but
close to a limit; the reason is given). They are copied from each study's
own results file.

## Build gates

`src/make.py` stops on the first failure. All run in the pinned toolchain
(`tools/kd`, KiCad 10.0.7), from `products/mesh-radio`.

| Test | Why | How | v1 result | Run |
|---|---|---|---|---|
| Circuit check: every part has a footprint and an LCSC number, no single-pin net, every pin on its footprint | Every part can be ordered and placed | `tools/kd python3 src/make.py` (its first gate) | pass, 257 parts | 1.0, 5 Nov 2026, 260f321 |
| Schematic netlist equals `src/circuit.py` | The drawing is the circuit | `tools/kd python3 src/sch.py` | equal | 1.0, 5 Nov 2026, cd01a5d |
| KiCad ERC | No wiring mistakes in the drawing | `tools/kd python3 src/sch.py` (writes `schematic/erc.json`) | 0 violations | 1.0, 5 Nov 2026, cd01a5d |
| KiCad DRC: 0 errors, 0 warnings, 0 unconnected | The fab can make it | `tools/kd python3 src/make.py` | pass: 0 / 0 / 0 (re-routed board) | 1.0, 5 Nov 2026, 260f321 |
| Copper nets equal the circuit, pad for pad | The copper is the schematic | `tools/kd python3 src/make.py` | pass, 792 pads | 1.0, 5 Nov 2026, 260f321 |
| BOM and CPL list exactly the 251 assembled parts | Assembly gets what the board needs | `tools/kd python3 src/make.py` | pass: 251 parts, 133 BOM lines, 18 Gerber files | 1.0, 5 Nov 2026, 260f321 |
| Committed fab files equal the build (CI) | Someone orders from them | `tools/ci/local.sh products/mesh-radio` (as `.github/workflows/ci.yml`; the proxy's CA passed in here) | pass: all gates, Gerbers, drills, BOM, CPL, netlist and rules match the committed files | 1.0, 6 Nov 2026, aa66297 |
| Meshtastic variant builds | The board has firmware | `pio run -e offgrid_mesh_radio_v1` (steps in `firmware/README.md`) | pass on Meshtastic v2.7.26 with the core patch: flash 90.2 %, RAM 41.1 %; with `OFFGRID_PA_ALLOW_4V0=1` flash 90.3 %. Compile only | 1.0, 6 Nov 2026, 4763321 |
| Bootloader builds | Drag-and-drop UF2 flashing | `make BOARD=offgrid_mesh_radio_v1 all` (Adafruit_nRF52_Bootloader 0.11.0) | pass | 1.0, 19 Oct 2026; its board files unchanged since (`firmware/bootloader/`: moved on 3 Nov, contents identical), not rebuilt |
| Part audit: maker, stock, lifecycle | NDAA sourcing; parts can be bought | by hand, DigiKey and LCSC/JLC (`docs/part-audit.md`) | 129 assembled lines: every maker from the US, Japan, Taiwan, Korea, Norway or Germany; no part last-time-buy; lines short at DigiKey have a non-Chinese second source named, except the 8.1 nH choke (not sold at DigiKey: Coilcraft direct); lines short at LCSC/JLC are bought at DigiKey and sent to JLC. Country of origin not yet recorded. | 1.0, 19 Oct 2026; JLCPCB stock of the 250 V capacitors, 0805 inductors and 8.1 nH choke re-checked 6 Nov (README *Ordering*) |


## Simulations (run by hand, recorded here)

### Power path (`sim/README.md`)

Ran on 5 Nov 2026 on the re-routed board's copper: `sim/extract.py` reads
each path's resistance and inductance off `mesh-radio.kicad_pcb` (since
5 Nov counting the power nets' pours), copied into `sim/board.py`.

| Simulation | Checks | How | v1 result | Run |
|---|---|---|---|---|
| Hot plug and over-voltage (X3) | USB, solar and drone inputs: 5 V, 20 V faults, a 5 → 20 V step, 6 V and 12 V panels, reversed panel and drone supply | `tools/kd python3 sim/hotplug/run.py` | **PASS** at every temperature (unchanged; peaks within 0.1 V of 3 Nov). USB from a 5.5 V source: MARGINAL by design | 1.0, 8f88f31 |
| Battery plugged in backwards (X1) | A reversed cell, with and without USB; a right-way cell for reference | `tools/kd python3 sim/reverse/run.py` | **PASS** in all six cases, −40 to 85 °C | 1.0, 8f88f31 |
| Short circuits (X2, X5) | Shorts on 3V3, the header's 3V3, VSYS, VPA, PA_IN and the cell; the protector's trip | `tools/kd python3 sim/shorts/run.py` | **PASS** on every rail, VSYS and PA_IN included (3 Nov: MARGINAL at 0–85 °C). BAT_P shorts MARGINAL: the protector cuts the cell; restart is a bench test. Protector over-current trip 4.6–6.6 A at 25 °C (3 Nov: 2.4–3.3 A, its sense loop's copper now 0.4 mΩ, was 18.1) | 1.0, 8f88f31 |
| Transmit bursts (P2, X4) | 1 to 3 W from fresh, mid and worn cells, every temperature; USB cases; 85 °C hot case | `tools/kd python3 sim/burst/run.py` | 3 W from a fresh cell **PASS** at 0 to 85 °C electrically (3 Nov: capped at 2.5 W); heat limits 3 W to below 45 °C on the board (Derating, `sim/thermal`); mid cell (3.7 V / 150 mΩ) 2.5 W at 25–60 °C (was 2 W); worn cell 2.5 W at 25–85 °C (4.2 V). USB + weak cell with PA_SRC_SYS: **PASS** (was FAIL). 85 °C hot case 2.5 W: **PASS** (was FAIL). The highest passing level per cell and ambient is the firmware's cap table (`burst/results.txt`) | 1.0, fdc1260 |
| Solar charging (P5, P7) | A 6 V panel charges inside 0–45 °C, nothing flows outside it | `tools/kd python3 sim/solar/run.py` | **PASS** at every temperature run: charging at 25 °C only (169 mA in full sun, 56–76 % harvest; 22 mA at 20 % sun); ≤ 1 mA at −40, −20, 0, 60 and 85 °C. No other temperature inside 0–45 °C is run | 1.0, 11d3854 |
| Derating (E4) | Every part at no more than 70 % of its rating | `tools/kd python3 sim/derating/run.py` (runs last) | 81 rows: **0 FAIL**, **2 OVER (owner-accepted)**: the TPS63810's dissipation in a 3 W burst, 204 % of its rating at 85 °C and 114 % at 60 °C (junction 152 / 127 °C in `sim/thermal`, over its 125 °C); the firmware's temperature cap never runs 3 W there (2 W above 45 °C, 1 W above 60 °C, off above 75 °C on the board). 9 MARGINAL: the 3 W path at 70–100 % (amplifier current, mux and buck-boost currents), the charger's input limit and the nRF52840's USB pin at OV max | 1.0, 6 Nov 2026, ce92315 |

All six in order: `tools/kd sh sim/run_all.sh` (about 3 hours on 4 cores, nearly all of it the burst grid (6 Nov, re-routed board, empty cache); runs are cached in `sim/out/`, so a re-run is quicker).

**The live-pad sequence, in plain words** (a FAIL until 20 Oct). With USB,
solar or drone power plugged in, pulling out a right-way battery leaves the
reverse-protection switch on. If a battery is then plugged in backwards, it
meets live pads: 12.3 / 11.5 / 10.8 A peak at 25 / 60 / 85 °C (0.07 A at
−40 to 0 °C) until the cell protector trips,
inside the parts' pulse ratings. The polarity-check transistor's gate saw
9–11 V (rated 8 V) until a 4.7 V zener was added across it on 20 Oct; the
study now passes at every temperature. (Until 20 Oct the study read the
plug pins, not the gate behind its 100 k filter.)

- **Firmware mitigation:** with external power in, the firmware holds
  charging off for 1 s and reads the battery pin. With no cell, the voltage
  falls and the switch lets go (`firmware/README.md`, *Cell test*).
- **Not covered:** when the board is switched off with external power in,
  the firmware is not running, so the window stays open.
- **A hardware cure** needs a battery-present signal (a 3-pin battery plug).
- **Left for the bench:** test the whole sequence on a built board.

### Radio (`sim/rf/README.md`)

`routed.py` and `run.py` ran on 5 Nov 2026 on the re-routed board (c28e3ef),
with the RF lines read off it and the re-fitted Bluetooth match and harmonic
filter values.

| Simulation | Checks | How | v1 result | Run |
|---|---|---|---|---|
| Amplifier load (1c) | The QPA9510 sees Qorvo's EVB load through the routed match | `tools/kd python3 sim/rf/routed.py` then `sim/rf/run.py` | **PASS**: 0.20 dB mismatch (3 Nov board: FAIL, 1.23 dB) | 1.0, c28e3ef |
| Transmit loss, amplifier to U.FL | 3 W can reach the antenna | same | **PASS**: 1.22 dB. Over tolerance MARGINAL (18 % of boards ≤ 1.3 dB, all ≤ 2.0 dB, 3.0–3.2 W): the assumed LFCG and switch loss spreads | 1.0, c28e3ef |
| Return loss | Every part sees a good match | same | **PASS**: worst 16.3 dB | 1.0, c28e3ef |
| Harmonics 2f–5f (R6) | FCC limits at 30 and 35 dBm, 2.15 and 6 dBi antennas | same | **PASS**: worst margin 21.7 dB at 35 dBm / 6 dBi (3 Nov: 11.6), 18.4 dB over tolerance; worst of 108 re-layouts 12.2 dB (4f) | 1.0, c28e3ef |
| Harmonics 6f–10f (R6) | The same, higher up | same | **PASS**: 20.4 dB at 6f (the amplifier's own levels there are assumed); worst of 108 re-layouts 8.7 dB (10f) | 1.0, c28e3ef |
| Filter notches | Where the low-pass notches fall | same | MARGINAL by design: 1.42 / 2.44 GHz (values re-fitted 5 Nov); the LFCG carries the rejection | 1.0, c28e3ef |
| Attenuator power | The 15.9 dB pad's resistors stay cool | same | **PASS**: worst resistor 41 % of its 85 °C rating at +22 dBm | 1.0, c28e3ef |
| Receive vs a RAK4631 (R4) | Hears at least as well as a RAK | same | **PASS**: 4.9 dB better with the receive amp on, 2.1 dB worse in bypass | 1.0, c28e3ef |
| Frequency | LoRa offset between nodes; the 32 MHz Bluetooth crystal | same | LoRa **PASS** (8.6 kHz against 31 kHz). Crystal MARGINAL: 42–47 ppm against Nordic's 40 ppm | 1.0, c28e3ef |
| Bluetooth match (R7) | The chip antenna's match over tolerance, routed lines | same | **PASS**: 16.4 dB nominal, 9.6 dB worst, 100 % yield (values re-fitted 5 Nov; 3 Nov: FAIL, 5.7 dB). Antenna = Johanson EVB model, not an EM model of this board | 1.0, c28e3ef |
| Antenna missing: amplifier (X7) | The QPA9510 survives an open U.FL | same | **PASS**: 9.0:1, inside its 10:1 rating at 3.6 V (3 Nov: FAIL 11.2:1) | 1.0, c28e3ef |
| Antenna missing: antenna switch (X7) | The SKY13330 survives an open U.FL | same | 2.7 V **PASS** (74 %); 3.6 V MARGINAL (98 % of +40 dBm); 4.0 V **FAIL** (109 %), handled in firmware: after an antenna fault the supply stays at or under 3.6 V until restart (6 Nov; sim only); the fault packet itself runs ≤ 750 µs before the cut-off | 1.0, c28e3ef, 4763321 (firmware ceiling) |
| Antenna missing: inductor heating (X7) | L15 and L18 with an open U.FL, 60 °C | same (7b) | **PASS**: L15 105 °C at 4.0 V, 25 % duty, no cut-off (limit 125 °C) | 1.0, c28e3ef |
| Missing-antenna detector (study 8) | The firmware rule tells a good antenna from a missing one | same | Rule from 30 dBm **PASS** (+1.6 dB); firmware default constants (re-fitted 5 Nov) MARGINAL (fail with ±1 dB power-model error); robust constants **PASS** from 33 dBm | 1.0, c28e3ef |
| 50 Ω line width (M4) | RF lines are 50 Ω on this stackup | `sim/rf/coupler.py` (field solve) | 0.17 mm line with 0.25 mm gaps = 49.9 Ω; used in `src/board.py` | 1.0, c28e3ef |

### Heat (`sim/thermal/README.md`)

`run.py` and `followup.py` ran on 5 Nov 2026 (bcb634f, NPROC=2) on the
re-routed 70 × 25.4 mm, 6-layer board, its copper, vias and stackup read
from `mesh-radio.kicad_pcb`.

| Simulation | Checks | How | v1 result | Run |
|---|---|---|---|---|
| Listening (E2) | Board temperature while receiving | `tools/kd python3 sim/thermal/run.py` | **PASS** at −40 to 60 °C. MARGINAL at 85 °C (85 °C-rated chips 1–2 °C over) | 1.0, bcb634f |
| Transmitting, as built (E2, E3) | Highest duty that passes every limit, 1 s messages, no charging | same | 1 W: 25 % at 25 °C, 50 % at 0 °C; at 60 °C none (the cell area passes 60 °C while only listening). 2.5 W: 1/60 at 0 °C, none at 25 °C. 3 W: 1/15 at −40 °C only. Unchanged from the 3 Nov board | 1.0, bcb634f |
| Transmitting, gap pad on a metal wall | The same with the 10 × 10 mm pad (now 4.3 mm below the amplifier) | same | 1 W: 100 % at 25 °C. 25 °C, 25 % storm at 35 dBm (`followup.py`): amplifier case 86 °C (3 Nov: 89), over its 85 °C limit, junction 125 °C (128), TPS63810 72 °C (80) | 1.0, bcb634f |
| Highest dBm at the antenna (`followup.py`) | Nominal / pessimistic, per ambient and pattern | `tools/kd python3 sim/thermal/followup.py` | As built + gap pad: 25 °C 35/33 one a minute, 34/33 in a 25 % storm; 45 °C 33/31.5 and 31.5/30; 60 °C none (listening limit). With the paddle fixes, 2 oz outer copper and the pad: 35/35 at 25 °C in every pattern (without the pad 34/33 in a storm) | 1.0, bcb634f |
| Charging heat (P7) | The cell area ≤ 45 °C while charging | `run.py` | 25 °C: 1 W one a minute **PASS**; 2.5 W one a minute cell 42 °C (3 Nov: 47); 3 W one a minute 45 °C, at the limit and flagged (52); 1 W in a 25 % storm 51 °C **FAIL** | 1.0, bcb634f |
| Rating audit (E1) | Every part rated −40 to +85 °C | `run.py` (study 2) | Chips, crystals, buttons and passives **PASS**. JST plugs −25 °C (owner-accepted). USB-C lower limit and every rating added since 19 Oct unverified | 1.0, bcb634f |
| Cold start at −40 °C | Crystals, TCXO and regulator loops start | `run.py` (study 3) | **PASS**. The 32.768 kHz crystal drifts to −152 ppm: MARGINAL, so the firmware declares 250 ppm | 1.0, bcb634f |

**What "the heat fixes" means in that model** (`results.txt`, "with the
board fixes"): the amplifier's paddle joined to the top ground pour (on the
board it is an island), its nine vias copper-filled (they are epoxy-filled),
and 2 oz copper on the outer layers (it is 1 oz); the gap pad is a separate
option. The rows above marked "as built" are the board as ordered, read from
the routed file: 26 ground vias per cm², outer copper 80 % (top) and 82 %
(bottom). The fixes are not on that board; the rows that use them say so.

## On hardware (not yet run)

No boards have been built.

| Test | Why | How | v1 result |
|---|---|---|---|
| Bring-up | Powers on, enumerates, flashes | bootloader over SWD, then UF2 (`firmware/README.md`) | not built |
| Battery plug polarity | The footprint drawing says pad 1 = + | a meter on a real Adafruit cell, **before ordering** | not done |
| Listening current (P1) | Default and battery-saver modes | meter, LNA on and in bypass | not built |
| Output power and gain table (R2, R3) | 1 W in US mode; licensed levels | power meter at 2.7, 3.6 and 4.0 V; replace the model table | not built |
| Harmonics to 10 GHz (R6) | FCC limits | spectrum analyser at 30 and 35 dBm | not built |
| Receive side by side with a RAK (R4) | Sensitivity | two nodes, same antenna and place | not built |
| RF tuning | Matching values marked "tune" | network analyser | not built |
| Missing antenna (X7) | Switch, inductors and detector | open U.FL, VSWR-2 load, good antenna, hot and cold; set the detector thresholds | not built |
| Reversed cell onto live pads (X1) | The live-pad sequence (passes in simulation since the gate clamp) and its firmware fix | the sequence above, with and without the processor running | not built |
| Short on the cell, restart (X2) | Protector releases on the cell alone | short and release | not built |
| USB 5 → 20 V step (X3) | The eFuse's real cut-off speed | bench supply | not built |
| Weak panel start-up (P5) | MAX17608 with a weak panel | dimmed 6 V panel | not built |
| Amplifier heat (E2, E3) | Check the thermal model | thermocouple on the amplifier case, with the gap pad, at 25 and 60 °C | not built |
| Charging window (P7) | 0–45 °C rule; sensor reading | heat and cool the board while charging | not built |
| Bursts from worn and cold cells (P2) | Check the firmware cap table | worn cell, cold chamber | not built |

When these run, record the results here. Where they disagree with a
simulation, fix the model before the next revision trusts it.
