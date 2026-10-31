# LayerCam v1: tests and simulations

Every test and simulation for this revision, why it exists, how to run it,
and its v1 result. Results are for this revision only
([`docs/versioning.md`](../../docs/versioning.md)). The build gates, design
checks, simulations and firmware tests run in CI on every push
(`ci / layercam-v1`). The rest were run on the dates given.

## Build gates (`src/make.py`; CI)

Run for each of the three boards (main, LED ring, USB-C).

| Gate | Why | Result |
|---|---|---|
| Every part has a footprint and an LCSC number; no single-pin net; every pin on its footprint, every pad in `circuit.py` | a wrong or missing pad is a dead board | pass: main 168 parts, ring 11, USB 7 |
| KiCad 10.0.7 DRC with PCBWay's limits | the fab rejects or mis-builds what breaks its rules | **all three boards: 0 errors, 0 warnings, 0 unconnected** |
| Every pad's net on the routed board equals `circuit.py` | the copper is the circuit | all three: pass (main 512 pads) |
| Every track corner 45° or less | no acid traps; the owner's rule | all three: pass |
| (main) each MIPI and USB pair's two tracks the same length, within 0.15 mm | a pair that is not matched turns into common-mode noise | pass: worst 0.06 mm (CSI_D0, 50.04 / 50.10 mm); USB 36.8 / 36.8 mm |
| BOM and CPL list exactly the assembled parts | nothing missing or extra on the line | main 155 assembled parts in 51 BOM lines, ring 11, USB 7 |
| Each board's badge: the OffGrid lockup, its name and revision (`LayerCam – Main V1`, `LayerCam – Ring V1`, `LayerCam` / `USB-C V1`), and the US flag on the USB-C board (Flag Code proportions, 5.26 mm hoist), set at an exact place (`src/silk.py`), clear of every pad, hole and via, every stroke at least 0.15 mm | the fab drops silk that is too thin or on a pad | all three: pass |
| Committed Gerbers, drills, BOM, CPL, netlist, rules equal what `make.py` builds (`tools/check_outputs.py`) | someone orders from the committed files | CI |

## Routing (main board)

| Step | Result |
|---|---|
| Placement: every part placed, every plane pad has its via, 36 of the SoC's 37 escape pins given a stub and a via, DRC on the placed board | 0 errors |
| Freerouting 1.9.0 (its fan-out pass, no optimisation; `src/pipeline.py`) | 5 connections left after its first round |
| The finisher (`src/finish.py`: maze router with rip-up and re-route, plane repair, dangling-stub and fold clean-up) | all 5 made; 8 mm of it hops through In3's 3.3 V fill, which stays whole |
| Result | 467 vias (53 of them the SoC's 0.35 mm escapes), 3.1 m of track: F 1.04 m, In2 1.26 m, B 0.84 m. DRC 0 / 0 / 0 |

Getting there took these changes, each from a jam every run hit
(`docs/decisions.md`, *Routing the main board*): the back-face caps'
plane vias out of the SoC's escape band; an escape stub and via laid at
placement for each SoC pin that leaves its face, at 0.35 mm vias and
0.1 mm stubs; a via in J3's boxed-in contact; no part in the pocket
beside the 0.9 V buck; the 0.9 V feedback network, the RTC cap, the
VBUS divider and the 24 MHz drive resistor moved to where their pins
reach them; VCC_1V8 at 0.127 mm (it carries 0.05 A).

## Design checks (`src/verify.py`; CI)

| Check | Why | Result |
|---|---|---|
| Each buck's output from its feedback divider, against its rail's limits | a wrong resistor is a dead or cooked SoC | pass. 0.9 V at 0.906 V, 3.3 V at 3.255 V, DDR at 1.362 V, 1.8 V at 1.800 V, Wi-Fi at 3.600 V |
| The camera cable, contact by contact by position: each module contact against the J2 contact in line with it | a reversed cable puts 3.3 V on ground | pass: all 20 meet their own net, in line within 0.00 mm |
| The main board inside the pocket measured from Prusa's case files | it must fit the unchanged case | pass, 0.10 mm inside the 0.4 mm-shrunk pocket |
| The USB board's outline, read from its board file, in the slot's grooves, placed as a rotation (its parts' face towards the opening, so board x = -v) | a mirror-image board does not slide in | pass: v -7.9 .. 14.1 in -7.9 .. 14.1. It failed first: the board had been drawn with x = v, its long side where the grooves are short; laid out again and re-routed (DRC 0 / 0 / 0) |
| Parts under the camera module 0.6 mm or lower; parts under the SoC heatsink's overhang 0.8 mm or lower | the module sits 1.0 mm off the board; the heatsink 1.1 mm | pass |
| The firmware's device tree and image against `circuit.py` (`src/check_firmware.py` -> `firmware/pincheck.py`): every GPIO, I2C, UART, PWM, SARADC channel, the SDIO voltage, the camera clock; no button; no SSH, no default password, no rkipc / adb / Samba in the image | a pin mismatch is a dead feature; an open service is an open camera | pass, 55 checks. Each check was shown to fail when its file is broken |

## Simulations (`sim/`; CI)

| Simulation | Why | Result |
|---|---|---|
| `impedance.py`: a 2D field solver (`fieldsolve.py`, within 1 % of two exact results) on PCBWay's 6-layer build No. 1 and its 1.2 mm 2-layer; MIPI, USB and the antenna track, with the ground fill beside them, ±0.015 mm etch and no-mask | 100 / 90 / 50 Ω within ±10 % | **pass, no WARN**: MIPI 100.6 Ω (93.9-107.8), USB 89.5 Ω (83.7-95.5), USB board 92.1 Ω (87.1-97.0), antenna 48.8 Ω (46.7-51.0) |
| `power_budget.py`: every rail's set point at the tolerance corners, each buck's current against its rating, inductor peak against saturation, capacitance after DC bias, the IR LED strings over supply and LED spread, the USB source | never browns out | **no FAIL, 7 WARN**: snapshot mode 0.16 A by day, 0.20 A by night, 0.68 A during a night picture (the printer's port gives 1 A). Notes: the stress bound of 1.08 A; 1.66 A millisecond peaks; the 0.9 V output capacitance past TI's tested range; 91 µF on 5 V at hot plug; L1 / L5 saturating at the buck's current limit; the LED strings' 4.2 : 1 brightness spread over all tolerances |
| `thermal.py`: the main board as a plate on a 0.5 mm grid in Prusa's sealed case (measured from its STL files), radiation and conduction across the air gaps, the lid's slots, the LED ring, the SoC heatsink; each layer's copper measured on the routed board (F 67 %, In1 89 %, In2 66 %, In3 84 %, In4 89 %, B 73 %); each part against its rating | "survive the chamber" | **pass at 63 °C, no FAIL, 5 WARN**: snapshot mode keeps every part in rating up to a 63.3 °C chamber (RV1106 89.5 °C, AP6256 84.6 °C, SC3336 84.7 °C at 63 °C). WARN: the 0.3 K margin, and the AP6256 and SC3336 above 75 °C (full RF and best image end there). Live view: up to 34-36 °C. The CNC block reaches 65.7 °C. The model is good to about ±10 K |

## Independent design review (26 Oct 2026)

A second reviewer went through `circuit.py`, the parts, the footprints and
the device tree against the datasheets. No blockers. Every RV1106 pin
used, its voltage domain, the power-pin rails, the regulator parts, the
AP6256, the camera connector and every IC footprint's pin numbering
checked out. What it found, and what was done:

| Finding | Done |
|---|---|
| The AP6256's crystal, buck inductor and sleep clock were placed for the unmirrored module, 16-17 mm from their pins on the back face | moved to the pins; the antenna feed is a drawn 50 Ω track |
| No feed-forward capacitors on the EA3036C, which both Everanalog and every Luckfox board use | 220 pF across each top resistor |
| 3.3 V could sit over the VCCIO maximum at its tolerance corner in PFM | set to 3.255 V |
| 0.9 V output capacitance past TI's tested range | one 22 µF less, 6.8 pF feed-forward |
| The SoC's exposed pad fully pasted | 16 windows, 55 % |
| Card detect at 0.8-1.3 V at reset (10k against the pin's own pull-up) | 1k |
| The Wi-Fi module's 32 kHz sleep clock drifts past its ±30 ppm when hot | Epson TG-3541CE TCXO |
| Power-up order thin at the enable threshold's corner | 330 / 470 nF enable delays |
| A 5.0 V TVS leaks when hot; the 5 V test pad 3 mm from the console's TX | 6.0 V TVS; the 5 V pad moved 6 mm away |
| Still open: the 37.4 MHz crystal's load (as the reference designs); USB high speed over the unshielded cable; a reversed ring cable stresses the light sensor (the SH sockets are keyed) | hardware rows below |

## Firmware (`firmware/`, host tests; CI)

`python3 -m unittest` from `firmware/`: **192 tests, 191 pass, 1 skipped**
(the `ssh-keygen` cross-check, where the tool is missing). Python 3.13 and
3.11. They cover:
- Prusa Connect: requests, size and rate limits.
- PrusaLink: digest auth and the job.
- The printer's UDP metrics lines and the timelapse state machine.
- The MP4 writer, checked against ffprobe where present.
- S3 SigV4 against AWS's test suite.
- Uploads.
- Config and the thermal governor.
- Wi-Fi supervision and the power-cycle reset.
- The USB setup console, signed updates and rollback.
- The image's security settings.
- The slicer G-code against the printer's metric buffer.

## Hardware (when built)

Not yet built. To do on the first boards:
- [ ] Power-up with a current-limited 5 V supply: each rail's voltage, the power-up order on a scope.
- [ ] The camera cable's continuity before fitting (3.3 V conductors on J2's pins 19-20).
- [ ] MaskROM over USB with the BOOT pads; flash; boot; the console.
- [ ] Current in snapshot mode, day and night, and while uploading: re-run `sim/thermal.py` with them.
- [ ] Fit in a printed case: the flat cable folded behind the module, the two 51 mm JST cables' slack, the antenna's place (5 mm from the board across it, or 15 mm parallel), the lens's focus.
- [ ] Wi-Fi range; the 37.4 MHz crystal's frequency offset; antenna match.
- [ ] USB high speed through the cable (MaskROM flashing speed).
- [ ] Prusa Connect snapshots; a per-layer timelapse on a CORE One; upload to SMB, NFS and S3.
- [ ] A 63 °C oven test in the printed case, snapshot mode, 4 hours: the SoC sensor and a thermocouple on the AP6256.
- [ ] Network: only ports 80 and 8514 open (and 53/67 on the setup AP); SSH refused until enabled.
