# LayerCam v1: decisions and trade-offs

Why the boards are the way they are. Each choice names what it costs.

## What it has to do

A camera inside a Prusa CORE One's heated chamber (up to 65 °C), in Prusa's
own printed Buddy3D housing, that:

- sees the whole bed in 1080p through a wide lens, and at night in IR;
- feeds Prusa Connect (the Prusa app) its snapshots;
- takes one frame per layer while the print head is parked, makes an MP4
  of them, and uploads it to a NAS (SMB, NFS), S3 or a web server;
- knows what is printing by asking the printer's own API;
- takes only power from its USB-C, talks over Wi-Fi, and has no SD card.

## Rockchip RV1106G3, not an ESP32

The RV1106G3 is a Linux SoC with a camera ISP, a hardware H.264 encoder and
256 MB of DDR3L inside its package. It can take a full-resolution frame,
encode it into a video one frame at a time, and run the network code
(SMB/NFS mounts, S3 signing, Connect, PrusaLink).

An ESP32-S3 camera board could only manage JPEG snapshots at lower
resolution and could not make an MP4 itself. The RV1106 costs about $25
and needs a 6-layer board for its 0.35 mm-pitch QFN.

The pin plan follows Luckfox's RV1106 boards (Pico Pro / Max) so the
Luckfox SDK's drivers and device trees apply almost unchanged.

## Three boards, as in the Buddy3D

The housing has three places for electronics:

- the main pocket behind the lens;
- a ring around the lens under the six IR windows;
- a slot for a USB-C board at the case's wall.

LayerCam keeps that split: a main board, an LED ring and a USB board,
joined by two 6-way JST SH cables. Each board is the shape Prusa's case
holds, so nothing in the case changes.

## The camera module and its lens

The sensor is Luckfox's SC3336 module (3 MP, 2-lane MIPI): it has Linux
drivers and ISP tuning files in the SDK. Its own lens (3.95 mm, 98°) is
replaced by a Towin 2.8 mm M12 lens (about 137° diagonal) for the whole
bed. The lens is IR-corrected so night frames stay sharp.

A Commonlands CLA219 IR-cut holder on the main board's front face carries
the lens, so the day/night filter sits in front of the sensor as in any IP
camera.

The module sits behind the main board, looking through a 14.4 mm window,
on two 1 mm stacks of stainless washers (nylon creeps in the heat and
the stack sets the focus). Cost: the module's lens is not centred on it
(`docs/housing.md`), so the main board's cable socket and the parts
under the module had to be placed around its real outline.

## No SD card: the video is built as the print runs

There is no card to fill or wear out. Each frame goes through the hardware
encoder as it is taken and is appended to one H.264 stream on the NAND.
At the end of the print the stream is wrapped as an MP4 while it is being
uploaded. A whole print's timelapse is tens of MB, so the 256 MB NAND
holds it with the firmware.

Cost: if the upload target is down, the video waits on the NAND until it
comes back, and only a few of them fit.

## The per-layer trigger: the printer tells the camera

PrusaSlicer's "after layer change" G-code parks the head and makes the
printer send a UDP line to the camera through the Buddy firmware's metrics
(`M334` / `M331`). The camera takes the frame while the head waits.

The slicer snippet is in `firmware/slicer/`.

Polling PrusaLink cannot do this: it does not report the layer or the
head's position while printing. PrusaLink is still used, for the job's
name and its start and end.

## Heat: a snapshot camera, not a video camera

The chamber is 65 °C and the case is sealed plastic. Measured from Prusa's
files and modelled (`sim/thermal.md`), streaming video continuously puts
the SoC at its 125 °C limit.

Prusa Connect only takes stills (one per 10 s at most), and the timelapse
takes one frame per layer. So by default:

- the sensor sleeps between pictures;
- the CPU runs at its lowest speed;
- Wi-Fi stays in power-save;
- the IR LEDs light only while a night picture is taken.

A thermal governor slows down and then stops the camera before anything
overheats.

A stock 14 x 14 x 10 mm heatsink on thermal tape sits on the SoC. That
is the tallest that fits under the case's rounded end, so it rates the
camera for a 63 °C chamber.

A stuck-on heatsink only moves heat into the air trapped in the case. The
case wall is the real limit. A CNC aluminium block that reaches the lid's
vent slots gets past that wall and reaches 65.7 °C. It is designed
(`mechanical/heat-plate/`) but optional: the user chose the part anyone
can buy.

Live view (a local preview) is allowed only while the board is cool.

The parts were chosen for heat:

- X6S / X7S capacitors (105 / 125 °C) in place of X5R (85 °C);
- string resistors sized for the ring's temperature;
- (`docs/parts.md`) higher-rated parts where the cheap ones stop at 70-80 °C.

Cost: no smooth live video in a hot chamber.

## Power

5 V from the printer's USB port (Prusa rates it 1 A for its own camera).

| Rail | Supply |
|---|---|
| 0.9 V core | TLV62569, 2 A |
| 3.3 V / DDR / 1.8 V | EA3036C triple buck |
| Wi-Fi | its own TLV62569 at 3.6 V |

The Wi-Fi supply is separate so its 1 A transmit bursts never dip the
SoC's rails.

The rails start in the order the RV1106 needs (0.9 V, then 1.8 V and DDR,
then 3.3 V), set by the bucks' enables.

The 0.9 V rail is set to 0.906 V instead of Luckfox's 0.882 V, so its low
tolerance corner stays above the core's 0.85 V minimum.

Snapshot mode draws 0.16-0.2 A on average and 0.7 A during a night
picture (`sim/power.md`).

## Main board: 6 layers

The RV1106's QFN-128 at 0.35 mm pitch, its exposed pad and the MIPI and USB
pairs need a ground plane under every signal layer and filled vias in
pads. The layers, in order:

| Layer | Use |
|---|---|
| F | back face: SoC, flash, power |
| In1 | ground |
| In2 | signals |
| In3 | 0.9 V under the SoC, 3.3 V elsewhere |
| In4 | ground |
| B | front face: Wi-Fi, connectors, decoupling under the SoC |

The camera's MIPI lanes and the USB pair are drawn by script as coupled
pairs (`src/pairs.py`), sized for 100 Ω and 90 Ω on the fab's stackup
(`sim/impedance.md`). Everything else is routed by Freerouting, finished by
`src/finish.py`, and checked by KiCad's DRC.

## Routing the main board

The RV1106's pins are 0.35 mm apart and the case leaves no room to make
the board bigger. Every routing run jammed at the same few places, so
each was fixed where it starts, not by routing harder:

- **Escapes laid at placement.** Each SoC pin whose net leaves its face
  (its nearest other pad is on the back, or the net runs over 20 mm) gets
  a stub and a via before routing; a pin between two other escapes is
  laid first. 36 of 37.
- **Smaller vias for those escapes: 0.35 / 0.2 mm, 0.1 mm stubs.** With
  the board's 0.45 mm vias, two escapes a pin apart left 0.25 mm between
  them and the pin in the middle could not get out. At 0.35 mm a 0.1 mm
  stub passes with 0.125 mm each side. The 0.2 mm drill and 0.075 mm ring
  are inside the board's existing rules; the 0.1 mm gap is PCBWay's
  6-layer floor and the DRC allows it only in the band round the SoC.
- **An escape band kept clear.** No part on either face, and no other
  part's plane via, within the 2.4 mm round the SoC's pins (the back-face
  caps had put 38 vias there).
- **Parts where their pins reach them.** The 0.9 V buck's feedback
  network under the buck, the RTC supply cap under its pin, the VBUS
  divider and the 24 MHz drive resistor on the back by their escapes; no
  part in the pocket between the 0.9 V inductor and its buck (walled in by
  the switch node); a filled via in J3's contact 2, which its neighbour
  and the connector's tabs box in on the back.
- **VCC_1V8 at 0.127 mm.** It carries 0.05 A; at 0.2 mm it was the net
  every run left open.

Cost: two via sizes and a 0.1 mm gap near the SoC on the order (both
within the build already quoted), and the finisher's 8 mm of track
through In3's 3.3 V fill. The routed board is the design of record:
`make.py --reroute main` re-runs the whole chain, but Freerouting does not
give the same board twice.

## Fab and assembly: PCBWay

All three boards are made and assembled by PCBWay, which buys parts from
the global distributors, so hotter-rated parts that JLCPCB does not stock
could be used.

The BOMs carry the maker's part number and an LCSC number for each part.
