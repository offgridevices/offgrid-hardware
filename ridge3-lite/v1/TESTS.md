# Ridge 3 Lite v1: tests and simulations

Every test and simulation for this revision, with its **v1** result. How
this record works across the repository: [`docs/versioning.md`](../../docs/versioning.md).
Before a v2, question each row first (still needed? still right? anything
missing? did hardware disagree?).

Worst case used throughout: 4S HV pack (17.4 V), XING2 1404 3800KV on 3"
props (15 A per motor sustained, 25 A stalled), 50 °C air, 1000 W/m² sun.

## Build gates (CI, every push)

`ci / ridge3-lite-v1` runs these on every push; the build stops on a failure.

| Test | Why | How | v1 result |
|---|---|---|---|
| Parts and footprints | Every part orderable and on its footprint | `src/make.py` | pass, 260 parts, every assembled part with an LCSC number |
| KiCad DRC | The fab can make it | `src/make.py` | 0 errors, 0 warnings, 0 unconnected |
| Nets equal the circuit | The copper is the schematic | `src/make.py` | pass, 931 pads |
| BOM and CPL equal the placed parts | Assembly gets what the board needs | `src/make.py` | pass, 223 placed parts |
| Artwork rebuilt from source | Brand and labels are what `src/` draws | `src/make.py --artwork` | pass |
| Committed fab files equal the build | Someone orders from them | `tools/check_outputs.py` | pass |
| Design checks | Firmware pin maps against Betaflight and AM32 source, gyro orientation, parts, outputs, simulation verdicts | `src/verify.py` → `VERIFICATION.md` | 100 passed, 0 failed |

## Simulations (run by hand, recorded here)

| Simulation | Why | How | v1 result | Run |
|---|---|---|---|---|
| FET model fit | Every switching result rests on it | `sim/fet_model` | fitted to the TPN2R304PL datasheet | 13 Oct 2026 |
| Half-bridge switching | Spikes must stay under the FETs' 40 V | `sim/halfbridge` | 29.7 / 32.2 V (15 A); 39.4 V at 30 A, 4 nH abuse; slew ≤ 1.85 V/ns | 13 Oct 2026 |
| Battery transients | Load release, braking, hot plug | `sim/battery` | 18.6 V worst with the bulk capacitor; **pack unplugged while braking: 57 V** (a limit, not protectable) | 13 Oct 2026 |
| Gate-drive supply | 11 V LDO heat, ripple, bootstrap, sagging pack | `sim/gate_supply` | pass; works down to 5.8 V | 13 Oct 2026 |
| 5 V BEC | Current limit, on-time, heat | `sim/bec` | pass; 23 % current margin | 13 Oct 2026 |
| Sensing | Current and voltage readings Betaflight and AM32 use | `sim/sense` | 20.0 mV/A per motor, 12.02 mV/A total; back-EMF inputs in range | 13 Oct 2026 |
| Thermal model check | The heat model against the FET maker's published figures | `sim/thermal/validate.py` | within 1–2 % at the datasheet's conditions | 13 Oct 2026 |
| Thermal, desert set | Survives worst-case heat | `sim/thermal/thermal.py ridge3-lite.kicad_pcb --case desert` | hottest FET (rated 175 °C): hover 98, cruise 110, punches 119, 60 s full throttle 165 °C. Stalled motor (179) and weak airflow (225) exceed it: the ESC's 100 °C limit and stuck-rotor cut act first (README *Heat*) | 13 Oct 2026 |

All run with `tools/kd` on this folder's committed files (`sim/run_all.sh`
for the circuit set). Details and plots: `sim/README.md`,
`sim/thermal/README.md`.

## On hardware (not yet run)

| Test | Why | How | v1 result |
|---|---|---|---|
| Bring-up | Powers, enumerates, flashes | README *Bring-up* | not built |
| Motors | Order, direction, current limit | Betaflight Motors tab, AM32 settings | not built |
| Temperatures | Check the thermal model | thermocouple on the hottest FET at hover and on punches | not built |
| Current sense | Check the calibration | against a meter | not built |
| Gyro and flight | Stable flight | gyro noise log, test flight | not built |

When these run, record the results here; where they disagree with a
simulation, fix the model before the next revision trusts it.
