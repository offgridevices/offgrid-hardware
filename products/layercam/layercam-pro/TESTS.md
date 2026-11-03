# LayerCam Pro v1: tests and simulations

Every test and simulation for this revision, why it exists, how to run it,
and its v1 result. Results are for this revision only
([`docs/versioning.md`](../../../docs/versioning.md)). A result in double
braces, such as pass: 0 errors, 0 warnings, 0 unconnected, is filled in from the routed board's build on the
final commit (built 2 Nov 2026). The rest were run on 1 Nov 2026.

CI (`ci / layercam-pro-v1`) rebuilds the artwork and fab files from the
committed board on every pull request and checks them against the
committed ones, then runs the design checks, the simulations and the
firmware's host tests. The case's checks need Prusa's files, which are not
committed: they are run by hand.

## LayerCam v1's tests, questioned

LayerCam Pro is a new product, not a new revision of LayerCam, but it
starts from LayerCam v1's main board and software. Each of v1's tests was
looked at before it was carried over:

| v1 test | Here |
|---|---|
| Build gates, DRC, nets, 45° corners, pair lengths, BOM/CPL, badge | **kept**, for one board. The pairs are the MIPI lanes only: USB is routed as plain tracks |
| Routing record | **kept** |
| Buck outputs from their dividers | **kept**; the Wi-Fi rail is 3.255 V now (the C6's maximum is 3.6 V) |
| Camera flat cable, contact by contact | **dropped**: no flat cable. **New:** the image sensor's balls, by position on the routed board |
| Board in Prusa's case pocket; USB board in its grooves | **changed**: the one board inside the new case's outline, the USB-C mouth at the case's opening; and the case's own checks (`enclosure/src/check.py`) |
| Part heights under the camera module and the heatsink | **changed**: under the IR-cut holder and under the heatsink |
| Firmware pins against `circuit.py` | **kept**, for the ESP32-C6 and the SC4336H |
| Impedance | **changed**: MIPI on both outer layers; USB, the USB board and the antenna track are gone |
| Power budget | **changed**: the ESP32-C6, the SC4336H and its LDO, the LEDs on the main board |
| Thermal | **changed**: one board in the new case, 65 °C, power save on and off |
| Firmware host tests | **kept**, plus the C6 flasher and the sensor driver port |
| Hardware rows | **kept**, less the cables; **new:** the sensor's chip ID, its flip and mirror, the C6's flashing, the rods, the magnets |

## Build gates (`src/make.py`)

| Gate | Why | Result |
|---|---|---|
| Every part has a footprint and an LCSC number; no single-pin net; every pin on its footprint, every pad in `circuit.py` | a wrong or missing pad is a dead board | pass: 189 footprints, 175 assembled parts |
| KiCad 10.0.7 DRC with PCBWay's limits | the fab rejects or mis-builds what breaks its rules | pass: 0 errors, 0 warnings, 0 unconnected |
| Every pad's net on the routed board equals `circuit.py` | the copper is the circuit | pass: 572 pads (the six plated mounting holes are ground pads now) |
| Every track corner 45° or less | no acid traps; the owner's rule | pass |
| Each MIPI pair's two tracks the same length, within 0.15 mm | an unmatched pair turns into common-mode noise | pass: D0 23.20 / 23.20 mm, clock 20.63 / 20.63, D1 17.40 / 17.38 (P on D0 and the clock tuned by a serpentine, `pairs.tune`) |
| BOM and CPL list exactly the assembled parts; the board's footprints equal `circuit.py`'s parts | nothing missing or extra on the line | 175 parts in 52 BOM lines |
| The Gerber job file says 1.6 mm, ENIG, green mask | the fab's CAM reads it | pass: 1.6 mm, ENIG, green |
| The silkscreen: the US flag (8 mm hoist, round stars) over the OffGrid lockup, centred; each test pad's name; `IR-cut` and `LayerCam Pro V1` on the front. Clear of every pad and via; ink at least 0.18 mm and enclosed gaps at least 0.25 mm (PCBWay prints 0.15 mm lines and keeps 0.25 mm knocked-out shapes) | the fab drops silk that is too thin, fills in what is too small, and holds an order with silk on a pad | pass: the flag and lockup centred on x = 0 above the lens; the eight test pad names above their pads (parts and vias are kept out of each name's box at placement); `IR-cut` upright beside its socket, clear of the socket's body; `LayerCam Pro V1` centred above the lens on the front |
| Committed fab files equal what `make.py` builds (`tools/check_outputs.py`) | someone orders from the committed files | pass, in CI |

## Routing

| Step | Result |
|---|---|
| Placement (`src/layout_main.py`, `src/placer.py`): every part placed in rows facing the pin it serves, plane vias, the SoC's and the sensor's escapes | 189 parts placed, placement DRC 0 errors (checked before routing); 228 plane vias; 37 of the SoC's pins escape by vias; the IR-cut bridge's two outputs leave by fixed stubs (`STUBS`) |
| Freerouting, then the finisher (`src/finish.py`), then straight runs (`src/straighten.py`) and 45° corners (`src/miter.py`) | Freerouting (12 passes) left 31 connections in 20 nets; the finisher routed all but IRCUT_1 (maze router to 4, rip-up and re-route to 1), which the IR-cut stubs then closed; 131 stair-stepped tracks redrawn as 81 straight ones |
| Vias, plane vias, track length per layer | 568 vias (510 at 0.45 mm, 58 at 0.40 mm round the SoC and the sensor); tracks 2.24 m (F 817 mm, In2 735, B 658, In3 26); plane vias 228, and 121 ground stitching vias |

## Design checks (`src/verify.py`)

| Check | Why | Result |
|---|---|---|
| Each buck's output from its feedback divider, against its rail's limits | a wrong resistor is a dead or cooked chip | pass (by `sim/power.md`: 0.9 V at 0.906 V, DDR 1.362 V, 1.8 V 1.800 V, 3.3 V 3.255 V, Wi-Fi 3.255 V, all inside their limits) |
| The image sensor's balls: every net on the ball the library names for it, by position on the routed board; the MIPI stubs start on their own balls | a ball off by one row is a dead camera; the sensor is turned 180° | pass |
| The board inside the case's outline (but for the USB-C tab); screws 3 mm or more from the edge; each IR LED under its rod; the LEDs clear of the IR-cut holder's base by 0.3 mm; the USB-C mouth 4.2 mm out from the edge | it must fit the printed case | pass |
| Parts under the IR-cut holder and under the heatsink's overhang no taller than the room there (0.8 mm under the heatsink) | the holder and heatsink sit on the board | pass |
| The firmware's device tree and image against `circuit.py` (`src/check_firmware.py` -> `firmware/pincheck.py`): every GPIO, I2C, UART, PWM, SARADC pin, the C6's EN, GPIO9 and UART, the sensor's node, no button, no SSH or open services in the image | a pin mismatch is a dead feature; an open service is an open camera | **pass, 75 checks** (1 Nov 2026). Each was shown to fail when its file is broken |

## The case (`enclosure/src/check.py`)

Run against the committed `print/*.stl` and Prusa's own files (not
committed): `python3 enclosure/src/check.py <folder with Prusa's files>`.
Run on 2 Nov 2026, with `geometry.OUTLINE` as committed.

| Check | Why | Result |
|---|---|---|
| Prusa's front holes: the six LED holes, the light window, the lens bore where Prusa's STEP file has them | the outside stays Prusa's | pass |
| **Board clearance**: 0.5 mm from the case everywhere but the screw pads | carbon-filled plastic conducts a little | pass: 0.50 mm to the front and back shells, 3.00 to the lid; the USB-C tab's end 0.24 mm (its 0.6 mm bare border) |
| Board outline against the case's walls (1.6 mm wall, 0.5 mm gap) | the board has to go in | pass: the outline, cut down at Prusa's two shoulders, lies wholly inside |
| Board seat: four 4.5 mm bosses at the seam, 1.7 x 5.5 mm pilots | the board's height sets the focus | pass |
| Light rods: six 2.15 mm channels from each LED to its hole, walled end to end | the light reaches the holes | pass: leaning 0.5°, 4.2°, 3.4°, 1.1°, 4.4°, 2.9° (0° to 300°), rods 18.95-19.01 mm, 0.07 mm rod to case, 0.3 mm to each LED (1.75 mm tall) |
| Light-sensor tube | the sensor sees the window | pass: 0.65 mm short of the sensor |
| IR-cut holder volume and the lens bore | the lens stack fits | pass, clear by 0.01 mm |
| Heatsink | it fits and reaches the vents | pass: 0.84 mm to the lid (1.6 mm thick there), 0.50 mm to the back shell, 3 slots over it |
| USB-C mouth | a level plug reaches the socket | pass: axis level at Z 24.23; the mouth 4.20 mm out from the board's edge, as the board places it, 0.20 mm inside the seat floor |
| Walls | thin walls print weak | pass: front shell 1.95 mm thinnest, back shell 1.51 mm at one spot (0.03 % under 1.6), lid 1.48 mm at two corners (0.09 %) |
| Parts do not overlap; magnet pockets 3.10 mm deep, 1.50 mm floors; RP-SMA hole 2.0 mm wall, nut and jack room clear | it goes together | pass |

## Simulations (`sim/`)

The power and impedance models do not depend on the routing. The thermal
model reads the routed board: its parts' places and each layer's copper
coverage.

| Simulation | Why | Result |
|---|---|---|
| `impedance.py`: a 2D field solver (`fieldsolve.py`, within 1.5 % of three exact results) on PCBWay's 6-layer build No. 1; the MIPI pairs on F over In1 and B over In4, with the ground fill beside them, ±0.015 mm etch and no-mask | 100 Ω ±10 % | **pass, no WARN**: MIPI 100.6 Ω (93.9-107.8) on both layers |
| `power_budget.py`: every rail's set point at the tolerance corners, each buck's current against its rating, inductor peaks against saturation, capacitance after DC bias, the IR LED strings over supply and LED spread, the USB source | never browns out | **no FAIL, 5 WARN**. Snapshot mode 0.15 A by day and 0.18 A by night with power save on (0.18 / 0.21 A off); 0.53 A during a night picture; the port gives 1 A. WARN: L1 and L5 saturate below the TLV62569's typical current limit; 91 µF on 5 V at hot plug; the 47 Ω string resistors at 0.138 W; the LED strings' 2.6 : 1 brightness spread |
| `thermal.py`: the board as a plate on a 0.5 mm grid in the new case (Prusa's outside), radiation and conduction across the air gaps, the lid's slots, the 20 x 20 x 15 mm heatsink; each part against its rating; 65 °C chamber, power save on | "survive the chamber" | **pass at 65 °C, no FAIL, 3 WARN**: on the routed board (its parts' places and each layer's copper coverage, measured): every part in rating up to a 68.3 °C chamber by night and 70.5 °C by day. At 65 °C by night: flash 81.9 °C (85), USB-C 81.7 (85), image sensor 81.5 (85), main chip junction 85.2 (125), ESP32-C6 82.4 (105). WARN: the 3.3 K margin against the model's ±10 K; the sensor above its 60 °C best-image limit. Power save off: 64.7 °C (0.3 K short of 65; information). Live view: to 53.1 °C by day, 41.6 °C by night |

## Firmware (`firmware/`, host tests)

`python3 -m unittest` from `firmware/`: **212 run, all pass** in CI
(`ci / layercam-pro-v1`, which has ffmpeg and `ssh-keygen`). On a PC
without them the MP4 and recording tests and the SSH fingerprint
cross-check skip themselves (2 Nov 2026: 212 run, 1 skipped, without
`ssh-keygen`). They cover:
- Prusa Connect: requests, size and rate limits.
- PrusaLink: digest auth and the job.
- The printer's UDP metrics lines and the timelapse state machine.
- The MP4 writer, checked against ffprobe.
- S3 SigV4 against AWS's test suite; uploads.
- Config and the thermal governor.
- Wi-Fi supervision, the setup access point, the power-cycle reset.
- The USB setup console, signed updates and rollback.
- The image's security settings.
- The pins against `circuit.py` (`test_pins.py`).
- Flashing the ESP32-C6 from the camera, against a simulated ROM.
- The SC4336H driver port from the SDK's SC4336 driver.
- The slicer G-code against the printer's metric buffer.

Also checked by hand on a PC (1 Nov 2026), not as tests: the device tree
through `cpp` and Zephyr's `dtlib` (every label resolves; not compiled
with `dtc`); the shell scripts with `sh -n`.

## Hardware (when built)

Not yet built. To do on the first boards:
- [ ] Power-up with a current-limited 5 V supply: each rail's voltage, the power-up order on a scope.
- [ ] MaskROM over USB with the BOOT pads; flash; boot; the console.
- [ ] The ESP32-C6 flashed from the camera (`layercam-c6-flash`), with power save on; `wlan0` up; the SDIO link at 25 then 50 MHz.
- [ ] The sensor's chip ID read over I2C; the driver rebuilt with it; a picture.
- [ ] The picture the right way up with the sensor's flip and mirror set.
- [ ] Focus through the front bore; the lens and IR-cut holder's fit; day/night switching.
- [ ] Current in snapshot mode, day and night, power save on and off, and while uploading: re-run `sim/thermal.py` with them.
- [ ] Fit in the printed case: board clearance at the USB-C tab, the rods' gap to the LEDs, the light-sensor tube, the screws, the magnets' hold on the frame.
- [ ] Wi-Fi range in a CORE One with the 2 dBi antenna on the case wall; the antenna's place by the gantry.
- [ ] Oven test at 65 °C in the printed case, snapshot mode, 4 hours: the main chip's own sensor and thermocouples on the flash, the USB-C and the sensor.
- [ ] Prusa Connect snapshots; a per-layer timelapse on a CORE One; upload to SMB, NFS and S3.
- [ ] Network: only ports 80 and 8514 open (and 53/67 on the setup access point); SSH refused until enabled.
