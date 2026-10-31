# LayerCam Pro v1: decisions and trade-offs

The decisions made while planning (31 Oct 2026), each with what it costs.
The owner's choices are marked *(owner)*.

## One board, not three

LayerCam uses three boards in Prusa's case (main, LED ring, USB-C), joined
by two cables and a camera flat cable. That is three PCB orders, each with
PCBWay's minimum quantity and its own assembly set-up, plus cables to buy
and stock. LayerCam Pro puts everything on one board. *(owner)*

Cost: the infrared LEDs end up about 19 mm behind the front face and need
light pipes; the USB-C plug goes in level instead of tilted (below).

## Where the board sits: the case's widest point

The lens sets the depth. An M12 lens wide enough for the whole bed is about
21 mm long from its front to the sensor, and its front has to sit just
behind the case's front face. So the sensor sits about 21 mm into the case,
and the sensor is soldered on the board's front face: the board's front
face is at about Z 21 (measured from the case's front face).

That is where Prusa's case is widest (about 72 x 67 mm outside) and where
its two printed halves meet. With a new inside and 2-2.5 mm walls, the board
can be about 66 x 60 mm with its corners cut, nearly twice the area of
LayerCam's main board. More area spreads the heat and the parts.

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
image to 60 °C, so it goes at the board's cool end.

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

The module has a U.FL socket. A short U.FL to RP-SMA cable runs to a
socket in the case wall, and a 2.4 GHz antenna screws on outside. These
cables are cheap and sold in bulk.

Rejected: an RP-SMA socket soldered on the board. It would need the bare
ESP32-C6 chip with our own radio layout, which loses the module's US
approval.

US rules allow only antennas of the same type and no more gain than the
module was approved with, so the product names (or ships) a matching
antenna. Most Amazon antennas are sold as 5-9 dBi and are not covered.

## Heat: 70 °C chamber, stock heatsink, no fan *(owner)*

Prusa's firmware caps the chamber at 55 °C (CORE One) and 60 °C (CORE One
L). Prusa rates its own camera to 65 °C, and owners report it stops
streaming at a 50-60 °C chamber. The Pro is designed for 70 °C, past both.

LayerCam's model showed that a heatsink inside a closed case only heats
the air trapped in it. So the Pro's heatsink reaches the back vents and
sits in the chamber's own air. The camera works in snapshots and the
timelapse at any chamber temperature up to 70 °C; live video only while
it is cool.

Rejected: a small fan (noise, a part that wears out); designing only for
Prusa's 60 °C limit (no headroom for owners who insulate the printer).

## Infrared lights: light pipes to Prusa's holes

Six 860 nm LEDs on the board, about 19 mm behind Prusa's 2.4 mm front holes.
Behind a hole that far back, an LED's light comes out as a narrow spot, not
a flood over the bed. A clear rod over each LED traps the light and lets it
out at the hole with nearly the LED's own wide beam. The pipes are stock
PCB parts that PCBWay fits.

Rejected: bigger front holes or one infrared window (changes the outside,
and a window is a part to buy).

The OSRAM SFH 4715AS is not for new designs; its maker-recommended
replacement, the SFH 4715CS (rated to 125 °C), is used.

## Magnets: round discs from Amazon *(owner)*

Prusa's case holds two 10 x 10 x 2 mm block magnets in slots. The owner
uses round disc magnets from Amazon. They go in printed pockets on the
outside, set with heat-proof epoxy (J-B Weld), not super glue, which goes
soft and brittle near 80 °C. They are high-temperature grade (SH, rated
150 °C); ordinary N grades are rated 80 °C and can lose pull for good near
a 70 °C chamber.

## Case material: PC carbon fibre

Prusa recommends PCCF for this case, and the owner prints in carbon fibre.
Carbon-fibre plastic conducts a little, so no bare copper may touch it:
the board's edge is kept clear and the board is coated.

## Fab: PCBWay, one order

One board: one Gerber zip, one BOM, one placement file. PCBWay buys every
part from the usual distributors. The one possible exception is the bare
image sensor (above). Everything else the camera needs (heatsink,
magnets, antenna, antenna cable, USB-C cable) comes from Amazon.
