# LayerCam Pro v1: decisions and trade-offs

The decisions made while planning (31 Oct 2026) and designing (1 Nov
2026), each with what it costs. The owner's choices are marked *(owner)*.
What the owner still has to decide is under *Open*, at the end.

## One board, not three

LayerCam uses three boards in Prusa's case (main, LED ring, USB-C), joined
by two cables and a camera flat cable. That is three PCB orders, each with
PCBWay's minimum quantity and its own assembly set-up, plus cables to buy
and stock. LayerCam Pro puts everything on one board. *(owner)*

Cost: the infrared LEDs end up about 19 mm behind the front face and need
light rods; the USB-C plug goes in level instead of tilted (below).

## Where the board sits: the case's widest point

The lens sets the depth. An M12 lens wide enough for the whole bed is about
21 mm long from its front to the sensor, and its front has to sit just
behind the case's front face. So the sensor sits about 21 mm into the case,
and the sensor is soldered on the board's front face: the board's front
face is at about Z 21 (measured from the case's front face).

That is where Prusa's case is widest (about 72 x 67 mm outside) and where
its two printed halves meet. With a new inside and 2-2.5 mm walls, the board
was planned at about 66 x 60 mm with its corners cut, nearly twice the area
of LayerCam's main board. More area spreads the heat and the parts.

The case check then found two concave shoulders in Prusa's case at about
(±26, -12), where the plain outline ran 2.9 mm into the wall. The board is
cut to the outline that fits (`geometry.OUTLINE`, 2710 mm²), 0.5 mm from
the case all round.

## Keep Prusa's outside, redo the inside *(owner)*

The outside (shape, magnets, corner) is what fits the printer. Prusa's
case is published on Printables (model 1343977, last updated 23 Sep 2025,
still the latest) under **GPL v2**, which allows selling a case built from
it if our case files are published under GPL v2 too, with credit. The
product must not use Prusa's names (Prusa, CORE One, Buddy3D) as its own.
Prusa's full CORE One CAD is under a different licence (OCL v1, no
commercial use); nothing is taken from it.

## USB-C: same side wall, plug level *(owner)*

Prusa's USB-C plug goes in tilted about 28° towards the front. A socket on
a flat board can only point along the board. The opening stays on the
same side wall, about 4 mm further forward, and the plug goes in level.

Rejected: a bendable rigid-flex board to keep Prusa's angle. Still one
board, but about 3-5 times the board price.

## The image sensor on the board: SC4336H

LayerCam's SC3336 camera module needs a flat cable; a bare sensor soldered
on the main board does not. SmartSens now lists the SC3336 as legacy, and
every part must be in production, so the Pro uses the **SC4336H**: in mass
production since Q3 2025, 4 MP, and SmartSens says it fits its predecessor's
35-ball package. The SDK has a driver and tuning files for its relative,
the SC4336; the SC4336H needs its own (usually a small port).

Cost: no authorised distributor stocks bare sensors; it is sourced through
SmartSens or its agents, or by PCBWay. Rated -30 to 85 °C, with its best
image to 60 °C. It cannot go to a cool end of the board: the lens bore
fixes it on the case's axis (see *Heat* for what that means for the main
chip).

## Wi-Fi: ESP32-C6, 2.4 GHz only *(owner)*

The owner set the budget at under $5 and every part in production. No
2.4 + 5 GHz Wi-Fi chip met that, was in stock, and was approved for sale
in the US:

| Option | Price | Why not |
|---|---|---|
| AMPAK AP6256 (LayerCam's) | about $5.33 | over budget, full signal only to 75 °C, its US approval for Wi-Fi unclear |
| Ezurio LWB5+ | about $20 | four times the budget |
| ESP32-C5 (2.4 + 5 GHz) | about $4.30 | out of stock everywhere, about 20 weeks |
| AIC8800DC (Luckfox's boards) | about $1-2 | no US approval found |

**ESP32-C6-MINI-1U-H4:** Wi-Fi 6 at 2.4 GHz, US approved, in production,
about $4.40, and **rated to 105 °C**, the only Wi-Fi part found above
85 °C. It removes the Wi-Fi as LayerCam's weakest part in the heat. Prusa's
own camera is also 2.4 GHz only, and 2.4 GHz goes through the printer's
walls better than 5 GHz.

Cost: it is a small processor, not a plain Wi-Fi chip. It runs Espressif's
`esp-hosted` firmware and talks to the RV1106 over SDIO with Espressif's
Linux driver. That driver is not proven on the RV1106, so it is tested on
a bench first. The main chip programs it over its serial port, so the
factory does not need a second programming step.

## Antenna: a socket in the case wall, a cable to the module

The module's antenna socket is the third-generation kind, MHF III (I-PEX)
or W.FL (Hirose), not U.FL: Espressif's datasheet (v1.5, 10.2) says so,
and the two do not mate. The lead is W.FL to an RP-SMA female bulkhead, about 10 cm of
1.13 mm cable. The bulkhead sits on the back shell's +X +Y facet, the only
place with a flat outside and room inside for the nut and the jack. In the
printer that facet faces the front frame, so a 2 dBi tilt-swivel antenna
folds down the front-left post, out of the gantry's way.

Rejected: an RP-SMA socket soldered on the board. It would need the bare
ESP32-C6 chip with our own radio layout, which loses the module's US
approval.

US rules allow only antennas of the same type and no more gain than the
module was approved with, so the product names (or ships) a matching
antenna. Most Amazon antennas are sold as 5-9 dBi and are not covered.
The module is approved with 2.33 dBi, so the camera uses a 2 dBi antenna.

## Heat: 65 °C chamber, stock heatsink, no fan *(owner)*

Prusa's firmware caps the chamber at 55 °C (CORE One) and 60 °C (CORE One
L). Prusa rates its own camera to 65 °C, and owners report it stops
streaming at a 50-60 °C chamber. The Pro was first designed for 70 °C, past both.

LayerCam's model showed that a heatsink inside a closed case only heats
the air trapped in it. So the Pro's heatsink reaches the back vents and
sits in the chamber's own air. Prusa's lid is 3.4 mm thick under its vents
(inner face Z 38.45); a 20 x 20 x 10 mm heatsink on the chip would stop at
Z 33.7, 5 mm short. The new lid is 1.6 mm thick there (inner face Z 39.4
or higher) and the heatsink is 20 x 20 x 15 mm, whose top is at Z 38.7:
0.7 mm or more under the vents.

The vent slots are part of Prusa's outside: six of them, X -10..10,
Y -15.5..6.5, round the lens axis, where the image sensor has to be. So
the main chip and its heatsink cannot be far from the sensor. The chip
sits at (0, -15): three slots over the heatsink, and about 5.8 mm of board
between the two chips' edges (the sensor's 6.2 x 4.14 mm package with its
long side towards the chip, the worst case; the SC3336's size from
SmartSens' flyer, which the SC4336H is said to share). (0, -15.5) is as far as the heatsink fits in
the case; at (0, -12) four slots are over it but the chips nearly back
onto each other. The thermal model of the routed board decides; the
sensor's own copper island and a slot between them help.
`src/plan_section.py` checks the heatsink's fit at every height, its gap to
the lid and the slots over it. The camera works in snapshots and the
timelapse at any chamber temperature up to its rating; live video only while
it is cool.

Rejected: a small fan (noise, a part that wears out); designing only for
Prusa's 60 °C limit (no headroom for owners who insulate the printer).

**Rated for 65 °C, not 70 °C *(owner, 1 Nov 2026)*.** The thermal model
(`sim/thermal.md`) put the whole board 16-20 K above the chamber: the
three vent slots over the heatsink are too narrow for air to move through
them, and most of the heat leaves through the case's walls. At 70 °C the
four 85 °C parts (the image sensor, the USB-C, the flash, the status LED)
were 2-4 K over. The image sensor sets the ceiling: no hotter grade of it
exists, and it reaches 85 °C at about a 66 °C chamber. The owner chose to
rate the camera for 65 °C with the Wi-Fi's power save on (about 3 K cooler;
the C6's firmware is built with it on, `firmware/tools/c6-power-save.sh`),
5-10 K above anything Prusa's firmware lets the chamber reach.

Rejected: a 25 mm fan (noise, a wearing part); bigger vents (changes
Prusa's outside; a gain of perhaps 3-6 K, uncertain).

## Infrared lights: leaning rods to Prusa's holes

Six 850 nm LEDs on the board's front face, about 19 mm behind Prusa's
2.4 mm front holes. Behind a hole that far back, an LED's light comes out
as a narrow spot, not a flood over the bed. A 2 mm clear rod over each LED
traps the light and lets it out at the hole with nearly the LED's own wide
beam.

**The clash with the IR-cut holder is settled.** A straight pipe puts its
LED right under its hole, at R 13.0 every 60°, and the CLA219's base (a
full 21.2 x 19.6 mm rectangle) covered four of them. So the LEDs at 60°,
120°, 240° and 300° moved out to **R 14.4**; the two at 0° and 180° stay at
R 13.0, straight under their holes (`geometry.LED_R`). Each LED carries a
loose 2.0 mm clear polycarbonate rod in a printed channel in the front
shell. The channels lean the rods to Prusa's holes where Prusa's STEP file
has them: 0.5°, 4.4°, 3.5°, 1.1°, 4.6° and 2.9° (0° to 300°). `verify.py`
checks each LED under its rod and 0.3 mm or more clear of the holder.

Cost: the rods are bought and fitted by hand, with a drop of epoxy, not
fitted by PCBWay. Polycarbonate softens near 145 °C; acrylic (100 °C) is
the second choice.

Rejected: Bivar's straight board-mounted pipes (they cannot lean); a
holder with a smaller base (none found); bigger front holes or one infrared
window (changes the outside, and a window is a part to buy).

**The LEDs are Vishay VSMY3850X01** (850 nm, PLCC-2, ±60°, AEC-Q101), in
three strings of two, in place of the plan's OSRAM SFH 4715CS. Vishay's
datasheet for the X01 grade (document 80225, rev 1.2) rates it -40 to
105 °C ambient and 110 °C junction. JLCPCB had none in stock on 1 Nov
2026 (`parts.md`).

## Magnets: round discs *(owner)*

Prusa's case holds two 10 x 10 x 2 mm block magnets in slots. The owner
uses round disc magnets. They go in two Ø10.3 x 3.1 mm printed pockets on
the outside, on the two faces where Prusa's magnets act, set with
heat-proof epoxy (J-B Weld Original), not super glue, which goes soft and
brittle near 80 °C. Prusa's slots are closed. The magnets are 10 x 3 mm
discs of a high-temperature grade (SH, rated 150 °C); ordinary N grades
are rated 80 °C and can lose pull for good near a 65 °C chamber.

Cost: no Amazon listing found names an SH grade in this size. K&J
Magnetics' D62SH (3/8 x 1/8 in, N42SH) fits the pocket (*Open*).

## The case: designed, printed by the owner in PCCF *(owner)*

The case exists as code (`enclosure/src/case.py`) and three STLs
(`enclosure/print/`): a front shell, a back shell and a lid, as Prusa's.
The outside is Prusa's own surface. What changed on it: the USB-C opening
(a level plug in a seat cut square to it, in the same -X facet), the
RP-SMA hole, the two round magnet pockets, two new screw holes, and
Prusa's SD-card slot and antenna-lead slit closed. Inside: the board seat
at Prusa's seam, the six rod channels, the light-sensor tube, the room
for the lens and IR-cut holder, a 1.6 mm lid over the heatsink. Built
from Prusa's published files (GPL v2), so `enclosure/` is GPL v2 too.

The owner prints it in PC carbon fibre (PCCF), as Prusa recommends for
this case: hardened 0.4 mm nozzle, 0.20 mm layers, 4 perimeters (Prusa
uses 2; the new walls are 1.6-2.1 mm), no supports. Carbon-fibre plastic
conducts a little, so no bare copper may touch it: copper and parts keep
0.6 mm from the board's edge, and the case keeps off the board everywhere
but round the four screw holes. The holes are unplated, with no copper
(the plan had grounded holes; the design has none).

## Mounting: four M2 screws through board and case

The board has four M2 holes at `geometry.SCREWS`: (±13, 25.5) and
(±28, 0), lens frame. Four M2 x 8 socket head screws go in from the back,
through the back shell and the board, into 1.7 mm pilots in the front
shell's bosses. One set of screws clamps the board and joins the two
shells. The two at (±13, 25.5) use Prusa's holes, moved 0.6 mm; the two at
(±28, 0) are new holes in the side chamfers (*Open*). The lid keeps
Prusa's two M2 x 6.

## The image sensor turned 180°

KiCad flips a part on the board's front face top to bottom. Turned 180°,
the sensor's balls land where the MIPI lanes start, so the lanes stay
short and on their pairs (`layout_main.py`, `pairs.py`). The picture then
comes out upside down and mirrored, so the firmware sets the sensor's
flip and mirror bits (`camera.flip = both`). `firmware/README.md`'s
bring-up does not say this yet.

## USB as plain tracks

USB is only for flashing and the setup console, and it runs a few
centimetres from the edge to the main chip. It is routed as ordinary
tracks, without LayerCam v1's 90 Ω control. Only the MIPI pairs are
impedance controlled.

## Fab: PCBWay, one order

One board: one Gerber zip, one BOM, one placement file. PCBWay buys every
part from the usual distributors. The one exception is the bare image
sensor (above): PCBWay sources it, or it is consigned. The sensor's side
is reflowed last, so it goes through the oven once, with no-clean flux and
no wash. The board is Tg 170 material (the plan's requirement).

Everything else the camera needs comes from Amazon where an exact part
is sold there: the antenna, its lead, the screws, the rods, the epoxy. The
lens (Towin), the IR-cut holder (Commonlands), the heatsink tape
(Digi-Key) and the SH-grade magnets (K&J Magnetics) are not; the
heatsink's Amazon listing is still to be confirmed.

## Open: for the owner to decide

1. **The two new screw holes** at (±28, 0) in the back chamfers. The top
   two could reuse Prusa's holes exactly if `geometry.SCREWS` had y 26.1.
2. **The antenna's face** rests on the camera's pose in the printer,
   worked out from Prusa's files and photos: check it in a CORE One
   before ordering.
3. **The USB-C seat** is 4 mm deep at its top, deeper than Prusa's recess:
   a level plug on a 30° facet needs it.
4. **The light window** is left open (Prusa fits a blue window piece); a
   Ø5.8 x 2 mm clear disc would close it.
5. **Prusa's holes are up to 0.45 mm off** `geometry.hole_xy`'s R 13.0
   every 60°; the case leans the rods to Prusa's. The two straight LEDs
   could move under their real holes.
6. **The magnets:** K&J's D62SH (not on Amazon), or an Amazon disc whose
   grade cannot be checked.
7. **Coating.** The plan said the board is coated. It is not in the order:
   a conformal coat must keep off the sensor's glass, the USB-C, J3 and
   the antenna socket. Order it masked, or drop it.
