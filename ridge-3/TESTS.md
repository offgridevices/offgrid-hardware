# Ridge 3 revision 2.0: tests and simulations

Every test and simulation of revision 2.0 (both boards, printed `REV 2.0`):
why it exists, how to run it, its result for this revision and the date it
ran.  How this record works across the repository:
[`../docs/versioning.md`](../docs/versioning.md).  `ridge-3/` is the exception
that [`../docs/repo-structure.md`](../docs/repo-structure.md) names: both
boards of the stack in one folder with no revision folder, the revision in
the code (`REVISION`) and on the silkscreen, the decisions in
[`docs/STATUS.md`](docs/STATUS.md) and the trade-offs in
[`docs/RELIABILITY.md`](docs/RELIABILITY.md).  Before the next revision,
question each row first (still needed? still right? anything missing? did
hardware disagree?).  Where the next revision lives is decision
[D9](docs/STATUS.md#d9-where-the-next-revision-lives-owner).

Commands run from `ridge-3/`; the tools and their setup are in the
[README](README.md#setup).  The runs below were made on the pull request's
branch before its squash-merge into `main`, so no commit on `main` names
them: each row gives its date, and the next run of a row records the
commit it ran on.  Nothing has been built: every hardware row is not run,
and [`docs/TEST_PLAN.md`](docs/TEST_PLAN.md) has their procedure.

Worst case used throughout the simulations: a full 6S pack (25.2 V), 50 °C
air (the design's hot day), a BrotherHobby VY1507 3100KV on a 3-inch
tri-blade, AM32 at 20 A and 110 °C per motor.

## Build gates (`make.py`, and CI)

`python3.12 src/make.py --fab-only` runs every gate below and stops on the
first failure; `python3.12 src/make.py` runs them too and also makes the
renders and STEP models.  CI's `ridge-3` job ([`../.github/workflows/ci.yml`](../.github/workflows/ci.yml))
runs `--fab-only`, the comparison and `verify.py` on every pull request
into `main` and every push to `main`.

| Test | Why | How | Rev 2.0 result | Ran |
|---|---|---|---|---|
| The circuit's own checks | A broken schematic stops before it becomes a board | `python3.12 src/make.py --fab-only` | pass, both boards: every part has a footprint, no single-pin net, every assembled part orderable (an LCSC number, or an MPN and DigiKey number for global sourcing) | 2026-10-19 |
| KiCad DRC | The fab can make it, to JLCPCB's rules | the same | FC and ESC: 0 errors, 0 warnings, 0 unconnected | 2026-10-19 |
| Copper nets equal `circuit.py` | The copper is the schematic | the same | pass pad for pad, both boards; footprints equal the circuit's parts (FC 124, ESC 193) | 2026-10-19 |
| BOM and CPL equal the placed parts | Assembly gets what each build needs | the same | FC 83 parts, its analog build 94, ESC 159: BOM and CPL exactly those | 2026-10-19 |
| The heatsink is the ESC's | The CNC order fits the ESC's bottom parts | the same (ESC) | pass: every bottom part pocketed to its maximum height, no wall under 0.8 mm, the pad at 17 % squeeze; plate 14.5 g, pad 5.0 g | 2026-10-19 |
| Production panels | The 3 × 2 panels are six true copies | the same | FC and ESC: 112 × 88 mm, 6 copies, DRC six times the board's own, every copy's Gerbers, BOM and CPL equal the board's | 2026-10-19 |
| Committed outputs equal the build | Someone orders from them | the same, then `git status --porcelain -- .` (CI's step) | pass: after the run only the ignored unzipped Gerbers changed; the 23 order files, the boards and `mechanical/` unchanged | 2026-10-19 |
| Renders and STEP models rebuild unchanged | CI does not compare them | `python3.12 src/make.py` | pass: a second default run left all 57 outputs byte for byte (321 s) | 2026-10-14 |
| CI job `ridge-3` | The same gates in a pinned toolchain, on every pull request into `main` and push to `main` | [`../.github/workflows/ci.yml`](../.github/workflows/ci.yml), in `kicad/kicad:10.0.6` by digest | on GitHub (pull request #4, run 39323866008, after the FC was routed again): exit 0, every committed file unchanged, `verify.py` 214 passed, 0 failed, 31 SKIP; the job took 2 min 42 s.  Later runs are in the repository's Actions tab | 2026-10-19 |

## Design checks (`verify.py`)

`python3.12 src/verify.py` writes [`VERIFICATION.md`](VERIFICATION.md) and
exits 1 on any failure.  With the five outside sources set (the README's
[*What `verify.py` reads from outside the repository*](README.md#what-verifypy-reads-from-outside-the-repository)):
**263 passed, 0 failed**, 12 informational lines.  Without them: 217
passed, 0 failed, 29 SKIP; in CI, whose image has none of KiCad's own 3D
models, two more SKIP lines (72 FC and 118 ESC parts left out of the
3D-model checks), 31 in all.  Both on 2026-10-19.  By section, with
every source set:

| Section | Why | Rev 2.0 result | Ran |
|---|---|---|---|
| FC pin map | Every processor pin against KiCad's STM32G473 symbol and Betaflight's `RIDGE3` config: a wrong pin is a dead board | 67 passed | 2026-10-19 |
| ESC pin map | Each AT32F421's pins against Artery's datasheet and AM32's target; supplies, reset, SWD pads | 25 passed, 1 informational (AM32's dead time, not scoped) | 2026-10-19 |
| Firmware scales | The current, voltage and thermistor scales in Betaflight and AM32 against the hardware's (Betaflight's current scale within 3 %: 125 against the 12.2 mV/A its input sees, 122 exact, as `firmware/README.md` says); the gyro patch applies and matches the IIM-42652's datasheet | 15 passed | 2026-10-19 |
| Power and analog | Supply voltages, dividers, pin tables against the datasheets, the 60 % voltage rule, inductor saturation, gate drive, decoupling | 55 passed, 7 informational (inductor margins, gate drive at 2S, conduction losses); with the 5 V BEC's enable divider against USB back-feed (D11) and the 3.3 V buck's output capacitance (D10) | 2026-10-19 |
| Option groups | The FC's video, analog and blackbox groups: each reaches no part outside it, and the board keeps every supply and no single-pin net without it | 9 passed | 2026-10-19 |
| Board FC | DRC, nets, outline, mounting slots, stackup, fab files, CPL rotations, 3D models in their courtyards, solder pads | 27 passed, 1 informational (nearest part body to a wire pad, 0.68 mm); with each supply's feedback line: one pour and no load's pad on it, and the 2 A supplies' vias all power vias (D12) | 2026-10-20 |
| Silkscreen FC | Strokes the fab prints cleanly, only the brand's faces, the mark at its minimum size, the front arrow | 14 passed | 2026-10-19 |
| Board ESC | The same for the ESC, and its drivers' capacitors, thermistors and MCU supplies placed at their parts | 21 passed, 3 informational (thermistor and capacitor distances, nearest part body to a wire pad, 0.50 mm) | 2026-10-19 |
| Silkscreen ESC | As for the FC | 12 passed | 2026-10-19 |
| Brand | The mark against the brand repository's art (`OFFGRID_BRAND`); the vendored fonts' hashes against `fonts/README.md`, with or without it | 5 passed | 2026-10-19 |
| Firmware | Each image and patch against its SHA-256 in `firmware/README.md`; nothing left from revision 1; the AM32 image holds the patch's thermistor table; the bootloader's device info | 13 passed | 2026-10-19 |

## Simulations (run by hand, recorded here)

They need `sim/.venv` and the FET makers' SPICE models (the README's
[Stress simulations](README.md#stress-simulations) has both, the order of
the runs and their times).  Dates are each report's "Generated" line.
Every report was run again on 2026-10-14 on corrected models: the battery
line takes each design's own FC input capacitance and stack lead (it had
rev 1's for both); the DRV8320H's 2 A ISTRONG holds the off gate while the
other FET switches, and gate voltages are read on the die; Infineon's FET
models carry their packages' 0.7 nH, now counted once; the losses count
only the body diode's share of the dead time; gate charge is taken at
rev 2's 11 V drive, and the LiHV variant's throttle chop at its own pack
voltage.

### `STRESS.md`: the stack flat out, hot, on 6S

All its sections come from one run: `sim/.venv/bin/python sim/stress.py`
(about 3 h 25 min on four cores; the rev 1 comparison needs Toshiba's
model).  Rev 2: 19 pass, 1 marginal, 3 fail.

| Section | Why | Rev 2.0 result | Ran |
|---|---|---|---|
| Rev 2 against rev 1 | Rev 2 was made to fix rev 1's heat; the same simulations on both say whether it did | rev 1: 6 pass, 5 marginal, 15 fail; rev 2: 19 pass, 1 marginal, 3 fail.  Hard flight at 50 °C: AM32 cut a motor for 96 % of it on rev 1, 9 % on rev 2 | 2026-10-14 |
| 1. The FET model against its datasheet | Every switching result rests on Infineon's ISZ023N06LM6 model | R<sub>DS(on)</sub>, C<sub>iss</sub>, C<sub>rss</sub>, C<sub>oss</sub> and Q<sub>g</sub> within 2 % of the datasheet's typical values; Q<sub>gd</sub> 4.9 nC against 6.0; recovery 95 nC, 56 ns as supplied (datasheet 23 + 50 nC, 29 ns), used as supplied | 2026-10-14 |
| 2. The ESC's copper under motor current | Where the motor current heats the copper, and the resistance the monitors see | phase copper 0.26 / 0.20 mΩ (high / low side), sense node 1.2-2.7 mΩ, battery planes 0.70 + 0.44 mΩ; 14.3 W of copper loss at 4 × 20 A; the funnel via under Q1AL carries 12 A at 20 A per motor.  No pass or fail | 2026-10-14 |
| 3. Switching edges | Voltage on the FETs and on the gate driver's SHx pin at full voltage | **FAIL:** SHx -9.2 V at 30 A in the 5 nH loop (-12.8 V at 8 nH), against the DRV8320H's -7 V for 200 ns.  **MARGINAL:** while the high side turns on, the off low-side FET's gate reaches 1.76 V on its die at 150 °C (the worst of the 3-8 nH runs), above its threshold hot (about 0.4 V minimum, 1.0 V typical): the driver holds the gate pin to PGND, but the FET's source bounces through the source copper and the shunt (common-source inductance).  The switching energies show no shoot-through; it has not been measured (T5 measures the gate at the FET).  Pass: FET peaks 37.7 V (high side) and 37.2 V (low side, worst case) of 60 V; 44.9 V during a throttle chop | 2026-10-14 |
| 4. The battery line | Plugging in, full throttle, a throttle chop | pass: 41.5 V plugging in a full pack on 300 nH of leads; bus capacitors 16.7 A rms at 4 × 30 A, 4.6 °C self-heating (20 °C allowed); a chop 28.0-35.4 V at the FETs (25-100 mΩ packs) | 2026-10-14 |
| 5. The stack lead and the FC's supply | The lead's contacts and the ground loop | pass: 0.57 A in the lead at the FC's full load on an empty 6S pack (1.5 A per contact); 0 A of ground-loop current with the video pads also wired | 2026-10-14 |
| 6. Heat | What the stack can hold in hot air, in bursts, in a hard flight and on the ground | pass: 53-61 % throttle held indefinitely with every part in its rating at 5 m/s, 25-60 °C (hover 27 %); full-throttle bursts at 5 m/s: the hottest FET 126 °C with AM32 acting; hard 3-minute flight at 50 °C: FETs 128 °C, ESC processors 110 °C; on the ground at 25 and 50 °C the video on 69 % and 8 % of the time.  **FAIL:** in that flight AM32 cuts a motor from 62 s, for 9 % of it; on the ground at 60 °C in still air the video is off and the FC processor reaches 107 °C (105 °C) | 2026-10-14 |

### `sim/results/`: the variants, the ground, a crash, a punch

Each variant is rev 2 with one change (`sim/data.py`, `VARIANTS`), run
through the whole of `STRESS.md`'s simulations into
`sim/results/variants/NAME/`.  [`docs/RELIABILITY.md`](docs/RELIABILITY.md)
draws the conclusions.

| Run | Why | How | Rev 2.0 result | Ran |
|---|---|---|---|---|
| Variant `rev2` | The design as committed; its `found.json` is where the crash, punch and ground runs start | `sim/.venv/bin/python sim/stress.py --variant=rev2` | 19 pass, 1 marginal, 3 fail, the same verdicts as `STRESS.md`: SHx -9.2 V; the hard flight cut from 62 s, 9 % of it; on the ground at 60 °C the FC processor at 107 °C; the off low-side gate at 1.76 V (marginal).  52 % held at 50 °C, 5 m/s (153 min) | 2026-10-14 |
| Variant `idrive30` | D2: IDRIVE 30 / 60 mA (the 18 kΩ resistor) | `sim/.venv/bin/python sim/stress.py --variant=idrive30` | 19 / 2 / 2: SHx -5.6 V (-7.6 V at 8 nH); FETs 31.3 / 25.0 V; the off low-side gate 1.46 V; 49 % held; the flight cut from 42 s, 16 % of it (146 min) | 2026-10-14 |
| Variant `lihv` | D8: a full 6S LiHV pack (26.1 V) | `sim/.venv/bin/python sim/stress.py --variant=lihv` | 19 / 1 / 3, the same verdicts as LiPo: FETs 38.7 / 38.5 V; 50 % held; the flight cut from 43 s, 15 % of it (131 min) | 2026-10-14 |
| Variant `alt2250` | Thin air: 2,250 m up | `sim/.venv/bin/python sim/stress.py --variant=alt2250` | 20 / 1 / 2: hover 32 %; 58 % held; the flight never cut; on the ground at 60 °C two parts past their rating (124 min) | 2026-10-14 |
| Variant `bsz040` | D1: the cheaper Infineon BSZ040N06LS5 (JLC stock) | `sim/.venv/bin/python sim/stress.py --variant=bsz040` | 19 / 1 / 3: SHx -10.6 V; low-side FET 51.7 V of its 60 V; the off low-side gate 1.24 V (marginal); 48 % held; the flight cut from 26 s, 18 % of it; FETs 132 °C on a 150 °C part.  Rejected (105 min) | 2026-10-14 |
| Variant `bsz040-idrive30` | D1 with D2 | `sim/.venv/bin/python sim/stress.py --variant=bsz040-idrive30` | 19 / 2 / 2: SHx -6.1 V; FETs 32.3 / 25.0 V; the off low-side gate 1.08 V; 45 % held; the flight cut from 22 s, 24 % of it (80 min) | 2026-10-14 |
| Variant `temp120` | AM32's temperature limit at 120 °C instead of 110 °C | `sim/.venv/bin/python sim/stress.py --variant=temp120` | 19 / 1 / 4: the flight cut from 126 s, 1 % of it, but an X7R bridge capacitor at 126 °C (125 °C) from 122 s; FETs 134 °C, ESC processors 116 °C (102 min) | 2026-10-14 |
| Variant `idrive30-temp120` | D2 with the 120 °C limit | `sim/.venv/bin/python sim/stress.py --variant=idrive30-temp120` | 19 / 2 / 3: the flight cut from 62 s, 9 % of it, and an X7R bridge capacitor at 130 °C (125 °C) from 62 s; FETs 140 °C, ESC processors 119 °C (90 min) | 2026-10-14 |
| The variants side by side | One table to decide from | `sim/.venv/bin/python sim/variants.py` | [`sim/results/VARIANTS.md`](sim/results/VARIANTS.md) | 2026-10-14 |
| On the ground | The video thermostat, and how the FC's loads are wired | `sim/.venv/bin/python sim/ground.py` | HD unit on the 9 V pads, still air: video on 69 % of the time at 25 °C, 46 % at 35 °C, 8 % at 50 °C, 0 % at 60 °C with the FC processor at 107 °C (105 °C); both rails at their 2 A rating put parts past their ratings even at 25 °C ([`GROUND.md`](sim/results/variants/rev2/GROUND.md)) | 2026-10-14 |
| A crash | A motor stopped dead at full throttle: D3, D4 | `sim/.venv/bin/python sim/crash.py` | as built (0.6 V trip, cut after 248 ms): the low-side FET past its 175 °C for 11 ms from a cool board (182 °C) and 199 ms from a hot one (221 °C); with the cut after 68 ms, 22 ms (195 °C) ([`CRASH.md`](sim/results/crash/CRASH.md); 1256 s) | 2026-10-14 |
| A crash, BSZ040 | The same on the rejected FET | `sim/.venv/bin/python sim/crash.py --variant=bsz040` | as built: 131 °C from a cool board, 256 °C from a hot one, on a 150 °C part ([`CRASH.md`](sim/results/crash/bsz040/CRASH.md); 1236 s) | 2026-10-14 |
| A punch | Full throttle from hover: the current, the overcurrent trip's margin, the switching edges at that current (D2, D4) | `sim/.venv/bin/python sim/punch.py` | 64-68 A per motor about 4 ms in; the 0.6 V trip keeps a 73 % margin with a 128 °C FET; at 68 A in the 5 nH loop, FET at 25 °C, SHx reaches -13.5 V (60 / 120 mA) or -7.6 V (30 / 60 mA) against -7 V ([`PUNCH.md`](sim/results/punch/PUNCH.md); 2217 s) | 2026-10-14 |

`GROUND.md` and `VARIANTS.md` carry no date line: `ground.py` and
`variants.py` were run on 2026-10-14 on the new runs' `found.json`, and
`ground.py` gave the committed `GROUND.md` byte for byte.

## The product videos

| Check | Why | How | Rev 2.0 result | Ran |
|---|---|---|---|---|
| FC video, draft | The video still builds from the board file: scene, labels, length | `python3.12 video/make_video.py fc --check` | exit 0: 6 copper layers, 982 frames, 32,733 ms at 30 fps | 2026-10-14 |
| FC video, analog build | The same for the analog build | `python3.12 video/make_video.py fc --build analog --check` | exit 0 | 2026-10-14 |
| ESC video, final | The same at 4K 60 fps; its length must equal the music edit's | `python3.12 video/make_video.py esc --final --check` | exit 0: 8 copper layers, 1,965 frames, 32,750 ms (286 s) | 2026-10-14 |

## On hardware (not yet run)

The procedure, equipment and pass criteria are in
[`docs/TEST_PLAN.md`](docs/TEST_PLAN.md); results go in `docs/tests/`
(*Recording results* there), then here.

| Test | Why | How | Rev 2.0 result |
|---|---|---|---|
| Bring-up | That it works at all: power, flashing, orientation, motor order | README [Bring-up](README.md#bring-up), steps 1-8 | not run |
| T1. Inspection | Assembly quality: voids under the FETs, the stack lead, the heatsink's bosses | `docs/TEST_PLAN.md`, T1 | not run |
| T2. Firmware settings read back | The programming procedure: an erased settings page has both limits off | T2 | not run |
| T3. Current sensing | AM32's current limit acts on this reading | T3 | not run |
| T4. Temperature sensing | AM32's temperature limit acts on this reading | T4 | not run |
| T5. Switching edges | D2 (IDRIVE), D6: SHx against -7 V, the FET peaks, the off low-side FET's gate | T5 | not run |
| T6. Overcurrent monitor in punches | D4, D6: no trips in flight | T6 | not run |
| T7. Locked rotor (destructive) | D3, D6: the FET in a crash, AM32's cut | T7 | not run |
| T8. Heat on a hot day | The thermal model and the 50 °C rating | T8 | not run |
| T9. On the ground with video | The video thermostat | T9 | not run |
| T10. Supplies | The FC's 5 V, 9 V and 3.3 V rails; the 3.3 V buck's load step (D10); the board on USB alone (D11) | T10 | not run |
| T11. Battery transients | The voltage ratings: hot plug, throttle chop | T11 | not run |
| T12. LiHV | D8: the LiHV rating | T12 | not run |
| T13. Flight | Everything together; false stuck-rotor cuts | T13 | not run |
| T14. Before volume | EMC, environmental, crash shock, flight hours, the production test | T14 | not run |

Where a measurement disagrees with a simulation, correct the simulation's
inputs (`sim/data.py`) from it and run the simulations again before the
next revision trusts them.
