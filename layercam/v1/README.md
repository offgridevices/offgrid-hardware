# LayerCam v1

A camera for the inside of a Prusa CORE One. It sits in Prusa's own printed
Buddy3D camera case, sees the whole bed in daylight and in infrared, and
feeds Prusa Connect. It takes one picture per layer while the head is
parked, makes the timelapse into an MP4 on the camera, and uploads it to a
NAS or S3.

Three boards in the case (main, LED ring, USB-C), a camera module and lens
bought separately, and a stick-on heatsink. Fab and assembly: PCBWay.

**Status: designed, every check and simulation run; not yet built.**
Nothing here has been made or powered.

| | |
|---|---|
| Main board (6 layers) | ![main](main/images/layercam-main-top.png) |
| LED ring | ![ring](ring/images/layercam-ring-top.png) |
| USB-C board | ![usb](usb/images/layercam-usb-top.png) |

## What it had to do, and whether it does

| Requirement | Met? | How it is checked |
|---|---|---|
| Fit Prusa's Buddy3D case for the CORE One, case unchanged | **Yes, on paper.** The outlines come from Prusa's files, 0.5 mm clear | `src/verify.py` checks the main board is inside the measured pocket; `docs/housing.md`. Not yet tried in a printed case |
| Survive a 65 °C chamber | **No: rated for 63 °C.** With the stock heatsink, snapshot mode keeps every part in rating up to a 63 °C chamber; the optional CNC block (`mechanical/heat-plate/`) reaches 65.7 °C. The model is good to about ±10 K | `sim/thermal.md`. An oven test of the first board decides. Live video is limited to cooler chambers (see Limits) |
| 1080p, wide angle | **Yes.** 3 MP sensor (2304 x 1296); timelapse at 1920 x 1080 by default; 2.8 mm lens, about 137° diagonal | the lens's fit and focus are untested |
| Night vision like the Buddy3D: IR LEDs, light sensor, day/night filter | **Yes.** Six 850 nm LEDs, a light sensor, an IR-cut filter | `sim/power.md` (LED currents) |
| USB-C for power only; Wi-Fi | **Yes.** USB-C also flashes the firmware; Wi-Fi 5 (2.4 / 5 GHz) | |
| Feed the Prusa app (Prusa Connect) | **Yes, in software.** Snapshots to Connect's camera API | `firmware/` host tests; not tried against Connect yet |
| Per-layer timelapse: the slicer parks the head, the camera snaps | **Yes, in software.** PrusaSlicer G-code in `firmware/slicer/` makes the printer send the camera a UDP message at each layer | host tests emulate the printer; not tried on a printer |
| Know the print from the printer's local API | **Yes.** PrusaLink: the job's name, start and end | host tests from Prusa's own source formats |
| Make the video and upload it to SMB / NFS / S3 / NAS | **Yes, in software.** H.264 encoded frame by frame in hardware, wrapped as MP4 while uploading | SigV4 against AWS's test suite; MP4 against ffprobe |
| No SD card | **Yes.** Video and settings on the 256 MB on-board flash | |

## Where things are

| | |
|---|---|
| `src/` | the boards as code: `circuit.py` (the schematic), `parts.py`, placement and routing, fab files, design checks |
| `main/`, `ring/`, `usb/` | each board: KiCad files, `production/` (Gerbers, BOM, CPL, netlist, assembly PDF), `images/` |
| `mechanical/` | STEP models of the assembled boards; `heat-plate/` the heat block |
| `sim/` | impedance, power and thermal simulations |
| `firmware/` | the camera software, device tree, SDK config, slicer G-code ([`firmware/README.md`](firmware/README.md)) |
| `docs/` | [`decisions.md`](docs/decisions.md) (why), [`parts.md`](docs/parts.md), [`housing.md`](docs/housing.md) |
| [`TESTS.md`](TESTS.md) | every test and simulation, and its result |

## How to order

All three boards at **PCBWay**, with assembly ("PCB + SMT"). Upload each
board's `production/layercam-*-gerbers.zip`, BOM (`*-bom-pcbway.csv`) and
placement file (`*-cpl-jlcpcb.csv`: designator, X, Y, side, rotation).

**Main board** (`main/`):
- 6 layers, 1.6 mm, PCBWay's standard 6-layer stackup (No. 1: 1 oz on every
  layer, 2116 prepreg next to the outer layers).
- **Impedance control:** 100 Ω differential (MIPI, 0.12 / 0.15 mm, F),
  90 Ω differential (USB, 0.15 / 0.13 mm), 50 Ω single (antenna, 0.18 mm,
  B), all referenced to the next layer in.
- **Via in pad, resin filled and capped (POFV):** the SoC's exposed pad and
  fine-pitch pads have vias in them.
- Minimum track and gap 0.1 mm (only round the SoC's pins; 0.127 mm
  elsewhere), minimum drill 0.2 mm. Two via sizes: 0.45 / 0.2 mm, and
  0.35 / 0.2 mm round the SoC.
- ENIG, green mask, white silk.
- Parts on both sides.

**LED ring** (`ring/`): 2 layers, 1.6 mm, parts on both sides.

**USB-C board** (`usb/`): 2 layers, **1.2 mm ±0.1 mm** (the case's
grooves take 1.2 mm), parts on one side.

**Bought separately** (`docs/parts.md`): the camera module, the lens, the
IR-cut holder, the camera's flat cable, the Wi-Fi antenna, two 6-way JST SH
cables, a 14 x 14 x 10 mm stick-on heatsink, screws.

## How to build one

1. Print Prusa's case (Printables 1343977).
2. Remove the camera module's own lens holder. Fit the IR-cut holder and
   lens on the main board's front face over the window. Fit the module
   behind the board on the two nylon washers. Clamp all three with the two
   M1.6 screws.
3. Fit the camera's flat cable from the module to J2. **Check it before
   power-up:** with the cable in the module only, the two outermost
   conductors at one end are 3.3 V (shorted together) and must land on J2's
   pins 19-20. A reversed cable puts 3.3 V on ground.
4. Fit the LED ring in the front of the case and its cable to J4. Slide the
   USB-C board into its grooves and connect its cable to J1. Plug the
   antenna onto J5 and stick the antenna inside the case.
5. Clean the SoC's top (the large chip on the back face) with alcohol and
   press the heatsink on for 10 s, centred 3.5 mm towards the cable
   socket J2 from the chip's middle (`mechanical/heat-plate/README.md`).
   Close the lid.

## How to bring it up

Full steps in [`firmware/README.md`](firmware/README.md).
1. **Flash a new board.** The test pads are on the back face by the round
   edge: 5V on its own on the left (labelled), and a row of four on the
   right, unlabelled (too close together for printable text): `TX RX G BOOT`
   in that order from left to right, seen from the back face. Bridge BOOT
   and G with tweezers while
   plugging USB-C into a computer: the SoC waits in MaskROM. Then flash the
   image with Rockchip's tool.
2. **First power-up:** the camera opens its own setup Wi-Fi (its name and
   passphrase come from the chip's serial number: `tools/layercam-ap.py`
   reads them over USB). Join it, enter your Wi-Fi, the Prusa Connect
   token, PrusaLink and the upload target.
3. **Slicer:** paste `firmware/slicer/` into PrusaSlicer's printer
   profile (custom G-code). The first print asks on the printer's screen to
   allow the camera's metrics: allow it once.
4. **Console:** TX, RX and G test pads, 3.3 V, 115200 baud.

## Limits

- **Not built.** Every result below is a design check or a simulation.
- **Rated for a 63 °C chamber, not 65 °C.** The case is sealed plastic;
  with the stock heatsink, snapshot mode keeps every part in rating up to
  63 °C in the model, which is good to about ±10 K. For 65 °C, fit the
  optional CNC aluminium block instead (65.7 °C, `mechanical/heat-plate/`).
  The firmware's thermal governor slows the camera down and then stops it
  before anything overheats, and refuses live view when the board is hot
  (thresholds in `sim/thermal.md`).
- **The Wi-Fi module and the sensor run above 75 °C** in a 65 °C chamber,
  where the module's full radio performance and the sensor's best image
  quality end: expect some range and noise loss in a hot chamber.
- **Snapshot-mode currents are estimates** (no published idle figures for
  the RV1106): measure them on the first board, then re-run
  `sim/thermal.py`.
- **The lens and the IR-cut holder's fit**, the focus, and the flat cable's
  bend are untested. The lens is a quoted part from Towin. The IR-cut
  holder's plug type is assumed (PicoBlade).
- **The 37.4 MHz Wi-Fi crystal's load** follows the reference designs: measure
  its frequency on the first boards.
- **USB IDs are a placeholder**, and the USB console needs a real
  vendor/product ID before the camera is sold.

## How to build the outputs

Everything is generated by `src/` in a pinned toolchain (KiCad 10.0.7,
Freerouting 1.9.0; `tools/Dockerfile`). The main board was routed with
`KD_IMAGE=ogkicad-layercam:1 FR_FANOUT=1 FR_EXTRA="-mt 0" FINISH_SEED=1`
(Freerouting's fan-out pass, no optimisation; `docs/decisions.md`,
*Routing the main board*):

```sh
cd layercam/v1
tools/kd python3 src/make.py                # every gate and output, all three boards
tools/kd python3 src/make.py --reroute main # place and route a board from scratch
tools/kd python3 src/verify.py              # design checks
tools/kd python3 sim/thermal.py             # and sim/impedance.py, sim/power_budget.py
cd firmware && python3 -m unittest          # camera software host tests
```

CI (`ci / layercam-v1`) rebuilds all three boards on every push and checks
the committed fab files are exactly what the scripts produce.

Licence: CERN-OHL-S-2.0 (hardware), as the rest of this repository.
