# Mesh Radio v1: tests and simulations

Every test and simulation for this revision, with its **v1** result so far.
How this record works across the repository:
[`docs/versioning.md`](../../docs/versioning.md). Before a v2, question each
row first (still needed? still right? anything missing? did hardware
disagree?).

> **Where this revision stands (20 Oct 2026).** The layout is placed
> (58 × 25.4 mm, 6 layers). **Routing is in progress, not finished.** So:
>
> - the build gates that need the routed board (DRC, copper nets, BOM and
>   CPL, fab files) have **no result yet**;
> - every simulation below ran on the schematic and on an earlier placement,
>   with estimated copper. **Each one runs again on the routed board**
>   before the order. Until then, no simulation result here is final;
> - no board has been built, so every hardware row is empty.

Worst case used in the simulations: ambient −40, −20, 0, 25, 60 and 85 °C; a
1-cell LiPo from fresh (4.2 V, 50 mΩ) to worn (3.3 V, 300 mΩ); a 3 W
(35 dBm) burst; a sealed box at 60 °C.

Words used for results: **PASS**, **FAIL**, and **MARGINAL** (passes, but
close to a limit; the reason is given). They are copied from each study's
own results file.

## Build gates

`src/make.py` stops on the first failure. All run in the pinned toolchain
(`tools/kd`, KiCad 10.0.7), from `mesh-radio/v1`.

| Test | Why | How | v1 result | Run |
|---|---|---|---|---|
| Circuit check: every part has a footprint and an LCSC number, no single-pin net, every pin on its footprint | Every part can be ordered and placed | `tools/kd python3 src/make.py` (its first gate) | pass, 250 parts | 20 Oct 2026, 3c6d262 |
| Schematic netlist equals `src/circuit.py` | The drawing is the circuit | `tools/kd python3 src/sch.py` | equal | 20 Oct 2026, 3c6d262 |
| KiCad ERC | No wiring mistakes in the drawing | `tools/kd python3 src/sch.py` (writes `schematic/erc.json`) | 0 errors, 0 warnings | 19 Oct 2026 |
| KiCad DRC: 0 errors, 0 warnings, 0 unconnected | The fab can make it | `tools/kd python3 src/make.py` | **pending**: routing not finished | — |
| Copper nets equal the circuit, pad for pad | The copper is the schematic | `tools/kd python3 src/make.py` | **pending**: routing not finished | — |
| BOM and CPL list exactly the 243 assembled parts | Assembly gets what the board needs | `tools/kd python3 src/make.py` | **pending**: needs the routed board | — |
| Committed fab files equal the build (CI) | Someone orders from them | CI job | **pending**: no CI job for this board yet (`.github/workflows/ci.yml` builds only Ridge 3 Lite) | — |
| Meshtastic variant builds | The board has firmware | `pio run -e offgrid_mesh_radio_v1` (steps in `firmware/README.md`) | pass on Meshtastic v2.7.26, with and without the core patch; flash 90.0 %, RAM 41.1 % | 19 Oct 2026 |
| Bootloader builds | Drag-and-drop UF2 flashing | `make BOARD=offgrid_mesh_radio_v1 all` (Adafruit_nRF52_Bootloader 0.11.0) | pass | 19 Oct 2026 |
| Part audit: maker, stock, lifecycle | NDAA sourcing; parts can be bought | by hand, DigiKey and LCSC/JLC (`docs/part-audit.md`) | 129 assembled lines: every maker from the US, Japan, Taiwan, Korea, Norway or Germany; no part last-time-buy; lines short at DigiKey have a non-Chinese second source named, except the 8.1 nH choke (not sold at DigiKey: Coilcraft direct); lines short at LCSC/JLC are bought at DigiKey and sent to JLC. Country of origin not yet recorded. | 19 Oct 2026 |

The schematic was last drawn before one part number changed: it still shows
the old NTC (NCP15XH103F03RC); `src/parts.py` now has NCU15XH103F60RC. The
nets are the same. Re-run `src/sch.py` to refresh it.

## Simulations (run by hand, recorded here)

### Power path (`sim/README.md`)

Ran on 19 Oct 2026 on the circuit as it is now (e83b9c0 / d58b422). The
copper's resistance and inductance are estimates (`TRACE_*` in
`sim/board.py`): **re-run with values from the routed board**.

| Simulation | Checks | How | v1 result |
|---|---|---|---|
| Hot plug and over-voltage (X3) | USB, solar and drone inputs: 5 V, 20 V faults, a 5 → 20 V step, 6 V and 12 V panels, reversed panel and drone supply | `tools/kd python3 sim/hotplug/run.py` | **PASS** at every temperature. USB from a 5.5 V source: MARGINAL by design (the board stays off; the cut-off keeps the nRF52840 safe). USB turn-on at 85 °C with worst zener leakage: MARGINAL (bench). |
| Battery plugged in backwards (X1) | A reversed cell, with and without USB; a right-way cell for reference | `tools/kd python3 sim/reverse/run.py` | **PASS** in five cases. **FAIL in one: a reversed cell plugged into live pads** (see below). |
| Short circuits (X2, X5) | Shorts on 3V3, the header's 3V3, VSYS, VPA, PA_IN and the cell; the protector's trip time | `tools/kd python3 sim/shorts/run.py` | **PASS** on every rail. Cell terminals shorted: MARGINAL. The protector trips in about 0.3 ms; whether the board restarts on the cell alone is a bench test. |
| Transmit bursts from a worn cell (P2, X4) | 1 to 3 W bursts from fresh, mid and worn cells, at every temperature; USB with no cell | `tools/kd python3 sim/burst/run.py` | **PASS** at the levels the firmware cap allows. 3 W from a fresh cell at −20 to 85 °C (2 W at −40 °C). Worn cell: 1 W at 25 °C and up, none at 0 °C and below. USB only, no cell: 1 W passes. The highest passing level is the firmware's cap table. |
| Solar charging (P5, P7) | A 6 V panel charges the cell inside 0–45 °C, and nothing flows outside it | `tools/kd python3 sim/solar/run.py` | **PASS** at every temperature. Harvest 56–76 % of the panel's maximum at full sun. |
| Derating (E4) | Every part at no more than 70 % of its rating | `tools/kd python3 sim/derating/run.py` (runs last) | 81 rows: **1 FAIL** (the live-pad case below), **11 MARGINAL**: mostly the 3 W path the owner chose (amplifier at 2.3 of 2.4 A, buck-boost, power mux), the charger's input limit, and the nRF52840's USB pin at 96 % of its maximum. |

All six in order: `tools/kd sh sim/run_all.sh` (about 40 minutes on 4 cores).

**The one power FAIL, in plain words.** With USB, solar or drone power
plugged in, pulling out a right-way battery leaves the reverse-protection
switch on. If a battery is then plugged in backwards, it meets live pads:
21–24 A for about 0.2 ms, and the polarity-check transistor sees 9–11 V on a
gate rated 8 V.

- **Firmware mitigation:** with external power in, the firmware holds
  charging off for 1 s and reads the battery pin. With no cell, the voltage
  falls and the switch lets go (`firmware/README.md`, *Cell test*).
- **Not covered:** when the board is switched off with external power in,
  the firmware is not running, so the window stays open.
- **A hardware cure** needs a battery-present signal (a 3-pin battery plug).
- **Left for the bench:** test the whole sequence on a built board.

### Radio (`sim/rf/README.md`)

`run.py` ran on 19 Oct 2026 on 6cb9185, before the LFCG-1000+ filter and the
missing-antenna detector were added. `followup.py` (same day) checked the
LFCG-1000+ as a swap; that swap is now in the circuit. Traces are short
ideal 50 Ω lines: **re-run with the routed board's lengths**.

| Simulation | Checks | How | v1 result |
|---|---|---|---|
| Transmit loss, amplifier to U.FL | 3 W can reach the antenna | `tools/kd python3 sim/rf/run.py` | **PASS**: 1.12 dB. 34.8–35.2 dBm at 4.0 V over part tolerances. |
| Return loss | Every part sees a good match | same | **PASS**: worst 17.2 dB |
| Harmonics 2f–5f (R6) | FCC limits at 30 and 35 dBm, 2.15 and 6 dBi antennas | same | **PASS**: worst margin 14.1 dB |
| Harmonics 6f–10f (R6) | The same, higher up | `tools/kd python3 sim/rf/followup.py` | With the old LFCN-1000+: **FAIL** (−7.1 dB). With the LFCG-1000+ now fitted: **PASS**, worst margin 7.7 dB at 35 dBm / 6 dBi, 16.6 dB at 30 dBm / 2.15 dBi. The amplifier's own levels above 3f are assumed. |
| Filter notches | Where the low-pass notches fall | `sim/rf/run.py` | MARGINAL by design: chosen for low loss; the LFCG carries the rejection |
| Attenuator power | The 15.9 dB pad's resistors stay cool | `sim/rf/run.py`, `followup.py` | **PASS**: R41 at 36 % of its 85 °C rating at +22 dBm |
| Receive vs a RAK4631 (R4) | Hears at least as well as a RAK | `sim/rf/run.py` | **PASS**: 4.9 dB better with the receive amp on, 2.1 dB worse in battery-saver bypass |
| Frequency | LoRa offset between nodes; the 32 MHz Bluetooth crystal | same | LoRa **PASS** (8.6 kHz against a 31 kHz limit). Crystal MARGINAL: 42–47 ppm against Nordic's 40 ppm. |
| Bluetooth match (R7) | The chip antenna's match over tolerance | same | **PASS** before layout (100 % yield). Re-check on the routed board. |
| Antenna missing: amplifier (X7) | The QPA9510 survives an open U.FL | same | **PASS**: 9.1:1, inside its 10:1 rating at 3.6 V |
| Antenna missing: antenna switch (X7) | The SKY13330 survives an open U.FL | same | **FAIL**: 34.6–50.7 V peak at 3.6 V, against 31.6 V. The missing-antenna detector and the firmware cut-off were added for this; not yet re-simulated with them. |
| Antenna missing: inductor heating (X7) | L15 and L18 with an open U.FL, 60 °C | `sim/rf/followup.py` | L15 **PASS** at 2.7 and 3.6 V, **FAIL** at 4.0 V (129 °C against 125 °C). L18 **PASS**. |
| Missing-antenna detector | A missing antenna reads clearly above a poor one | `tools/kd python3 sim/rf/coupler.py` | 6.7 dB of contrast at 30 dBm, 7.5 dB at 35 dBm (thresholds 0.35 / 0.73 V). A first-order estimate, not an EM model. Run 19 Oct 2026, 16821fc. |
| 50 Ω line width (M4) | RF lines are 50 Ω on this stackup | `sim/rf/coupler.py` (field solve) | 0.17 mm line with 0.25 mm gaps = 49.9 Ω; used in `src/board.py` |

### Heat (`sim/thermal/README.md`)

`run.py` ran on 19 Oct 2026 (95b5e69) on a **62 × 25.4 mm, 4-layer model of
an earlier placement**. `followup.py` (19 Oct, 8ec13da) added 6-layer board
options. The board is now 58 mm and 6 layers. The copper is an input
(coverage and via figures): **re-run with the routed board's copper**.

| Simulation | Checks | How | v1 result |
|---|---|---|---|
| Listening (E2) | Board temperature while receiving | `tools/kd python3 sim/thermal/run.py` | **PASS** at −40 to 60 °C. MARGINAL at 85 °C (85 °C-rated chips 1–2 °C over). |
| Transmitting, 4-layer board as placed (E2, E3) | Amplifier case and junction in bursts and storms | same | 1 W, one message a minute at 25 °C: **PASS**. 1 W in a 60 °C box: **FAIL**. 2.5 W and 3 W: **FAIL**. Continuous transmit: **FAIL**. This is why the heat fixes were added. |
| Transmitting, 6-layer with the heat fixes and a gap pad (E2, E3) | The highest power that passes, per ambient and duty | `tools/kd python3 sim/thermal/followup.py` | Nominal / pessimistic dBm at the antenna. 25 °C: 35 / 35 in every pattern. 45 °C, one message a minute: 35 / 33. 60 °C: 33 / 31.5 one a minute, 31.5 / 31.5 in a storm. The firmware's temperature caps come from this row. |
| Charging heat (P7) | Charger and battery-sensor temperature | `run.py`, `followup.py` | At the old 497 mA: **FAIL** (charger throttles; its own heat trips the sensor). At 300 mA, now in the circuit: no throttling, charger junction 80 °C at 25 °C. The sensor still reads the board beside the plug, not the cell. |
| Rating audit (E1) | Every part rated −40 to +85 °C | `run.py` (study 2) | Chips, crystals and passives **PASS**. The buttons failed then (−25 to +70 °C); they have since been changed to Alps SKRP, rated −40 °C (`docs/part-audit.md`), not re-run. JST plugs −25 °C (owner-accepted). USB-C not verified. |
| Cold start at −40 °C | Crystals, TCXO and regulator loops start | `run.py` (study 3) | **PASS**. The 32.768 kHz crystal drifts up to −152 ppm: MARGINAL, so the firmware declares it 250 ppm. |
| Board size | Is the length set by heat? | `run.py` (study 4) | No: 10–20 mm shorter or longer moves the hot spot by less than 2 °C |

**What "the heat fixes" means in that model.** The amplifier's paddle joined
solidly to the top ground pour; its nine vias copper-filled; stitching vias
at 25 per cm²; 85 % copper on the outer layers; and a 10 × 10 mm gap pad from
the bottom of the board to a metal enclosure wall. The routed board must
have these, or the 6-layer rows above do not apply.

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
| Reversed cell onto live pads (X1) | The one power FAIL and its firmware fix | the sequence above, with and without the processor running | not built |
| Short on the cell, restart (X2) | Protector releases on the cell alone | short and release | not built |
| USB 5 → 20 V step (X3) | The eFuse's real cut-off speed | bench supply | not built |
| Weak panel start-up (P5) | MAX17608 with a weak panel | dimmed 6 V panel | not built |
| Amplifier heat (E2, E3) | Check the thermal model | thermocouple on the amplifier case, with the gap pad, at 25 and 60 °C | not built |
| Charging window (P7) | 0–45 °C rule; sensor reading | heat and cool the board while charging | not built |
| Bursts from worn and cold cells (P2) | Check the firmware cap table | worn cell, cold chamber | not built |

When these run, record the results here. Where they disagree with a
simulation, fix the model before the next revision trusts it.
