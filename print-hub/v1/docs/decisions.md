# Print Hub v1: decisions and trade-offs

Why the board is the way it is. Each choice names what it costs.

## What it has to do

Switch five USB-powered accessories next to a resin printer (exhaust fan,
light, two battery air filters, one spare) on and off from the print
server, measure what each draws, never burn out and never brown out. One
small board, fully assembled by JLCPCB, a printed case around it.

## Wi-Fi and USB, both

The ESP32-S3 does both, so there was no reason to choose:

- **Wi-Fi** (HTTP API, a control page, mDNS `printhub.local`): the server
  talks to it over the network forever after joining once.
- **USB-C DATA** to the server: setup (joining Wi-Fi, setting a token),
  flashing firmware, and control over a cable if Wi-Fi is ever down. The
  same command language on both.

Network settings (Wi-Fi, token, hostname) change only over the USB cable,
so someone who can reach the board on Wi-Fi can switch ports but not move
it to another network.

## Power: a USB-C PD charger, not the server's USB port

A computer's USB-A port gives 0.5 A (USB 2) or 0.9 A (USB 3): about 4.5 W.
The accessories together draw about 2.65 A at 5 V (fan 0.45 A, light
0.6 A, two filters charging 0.8 A each); the firmware allows 3 A
(`sim/power_budget.md`, and *Heat* below). So the board takes its own
charger:

- **POWER IN is a USB-C port that asks a USB-PD charger for 9 V** (Hynetek
  HUSB238), and a buck (Silergy SY8368A, 8 A switches) makes 5.16 V for the
  ports. At 9 V the cable carries half the current; the buck holds the
  ports at 5.16 V whatever the cable drops; any 20 W-or-more USB-C phone or
  laptop charger works.
- **A 5 V-only charger powers the board's logic but no ports.** With 5 V in,
  the buck cannot make 5.16 V (about 4.3 V at the ports, under USB's
  4.75 V). We looked at a bypass switch that would pass a 5 V charger
  straight through (Awinic AW32901): it is a 0.4 mm-pitch chip-scale part
  that needs via-in-pad on a 4-layer board, for a case (an old 5 V charger)
  that is easy to avoid. Left out; the firmware says so in `status`.
- **The server's USB never feeds a port.** The logic runs from the 5 V rail
  OR the DATA port's VBUS through two Schottky diodes, so the ESP32 keeps
  running (and can be flashed) from the server alone, while nothing can push
  the server's 5 V into a port.

## The firmware knows the charger's limit

The HUSB238 tells the ESP32 over I2C what the charger agreed to (volts and
amps). The firmware turns that into a budget for the ports (90 % buck
efficiency, the board's own 150 mA, 10 % margin, never over 5 A): 2.7 A on
a 20 W charger, 4.1 A on a 30 W one. A port is not switched on if what it
drew last time does not fit, and if all of them together go over for a
second (the filters start charging, say), the lowest-priority port is
switched off. Ports switched on together come on 250 ms apart. The exhaust
fan can be set to priority 1 so it is the last to go.

## Each port: a real switch, not a relay

**TI TPS25200**, one per port, instead of a relay:

- **It limits the current itself**: 1.92-2.20 A with the 47k on ILIM. A
  short on a port costs that port, not the rail; the other four stay above
  4.75 V (`sim/port_events.md`).
- **Soft start**: the port's voltage ramps over about 2 ms, so a fan with a
  big capacitor does not yank the rail.
- **Its output is clamped to 5.4 V and its input survives 20 V**: even if the
  buck failed and passed 9 V through, no device would see it.
- **Fault line, thermal shutdown, reverse-current blocking.**
- A relay would be bigger, slower, click, wear out, and protect nothing.

**Current measurement**: a 20 mOhm shunt and an INA180A2 (gain 50, so 1 V
per A) per port, into the ESP32's ADC. About $0.55 a port. A switch with
its own current monitor (TI TPS25947) would save two parts a port but costs
$1.06, reads 0-0.6 V, and is only 6 % accurate above 1 A. Measuring lets the
firmware see a fan stall, a filter finish charging, or a device drawing
more than it should (a software limit, 1.5 A by default, set per port).

**D+ joined to D-** on every USB-A (the BC1.2 "dedicated charging port"
signal), so phones and battery devices take more than 500 mA.

## 4 layers, under 100 mm

Ground has its own unbroken layer (In1) and the 5 V rail its own plane
(In2) under the ports. Every ground and 5 V pad drops straight into its
plane through a via next to it; the two outer layers carry signals and a
ground fill. Standard rules only (0.15 mm track and gap, 0.6 / 0.3 mm
vias): no fine-line or small-via surcharge.

The price decides the size (JLCPCB's own calculator, live, 18 Oct 2026,
five boards, green, lead-free HASL):

| board | 2 layers | 4 layers | 6 layers (black, ENIG) |
|---|---|---|---|
| 104 × 66 mm (the first layout) | $7.40 | $29.30 | $88 |
| anything up to 100 × 100 mm (calculator: up to 102 mm) | $4.00 | $8.00 | $82 |

So the board had to come under 100 mm a side, and once under it, size no
longer changes the price. Four layers cost $4 an order more than two and
were kept: the two planes spread the buck's heat over the whole board (the
heat simulation depends on it), keep the buck quiet, and let the parts sit
closer. Six layers cost ten times more and are not needed: Freerouting
routes the 86 × 50 mm board completely on the two outer layers.

## 86 × 50 mm

The first layout was 104 × 66 mm. The depth is now the USB-A receptacle
(13.6 mm) + its port block packed into 9.2 mm + the ESP32 module (26.4 mm,
its antenna at the back edge, over port 5's block); the width is five
receptacles 17 mm apart (from 18): their shield legs, all ground, nearly
touch, and two wide plugs still fit side by side. Two M3 holes instead of
four (one in the back-left corner, one beside the module, both more than
10 mm from the antenna); the USB-A receptacles hold the front edge in the
case's front wall. Stacked (two-high) USB-A would have made it smaller
still (about 65 × 50 mm) but the case 26 mm tall; one row was the owner's
choice.

Every track corner is cut to 45 degrees or less after routing
(`src/miter.py`; a build gate checks it). The router's 90-degree corners
are harmless electrically at these speeds (USB 2.0 full speed, slow edges
everywhere else); the 45-degree corners keep acid traps out of the etch and
look as intended.

## Heat: 3 A in total, and a thermistor

A board this small in a closed plastic case cannot shed what the buck can
deliver. The heat simulation (`sim/thermal/board_heat.md`) solves the
routed copper, every part's loss and the case around it: at the buck's
full 5 A the parts by the buck would pass their ratings even in a cool
room. So:

- **3 A for all the ports together** (the firmware's MAX_BUDGET_MA): with
  the two ports next to the buck at 1.5 A each, the rail at its highest
  corner and the room at 35 C, every part stays inside its rating. The
  usual load (fan, light, two filters charging) is about 2.65 A.
- **The case hugs the board**: the lid's underside steps down to 0.6 mm
  over the parts and the floor sits 1 mm under the board, on feet. Still
  air conducts heat only across a thin gap: this takes the hottest
  capacitor from 96 C to 81 C at 3 A in a 35 C room, for no cost but some
  plastic (the lid is printed solid).
- **A thermistor between the buck and its inductor** (Murata
  NCP15XH103F03RC, on an ADC1 pin): if the room is hotter, or the vents or
  feet are blocked, the firmware turns ports down (lowest priority first)
  before any part passes its rating, and switches them all off if the board
  keeps heating. The thresholds come from the simulation: at 3 A in a 35 C
  room the thermistor reads 73 C with every part inside its rating, and
  with ports on no part reaches its rating below 77 C on the thermistor; so
  the budget falls from 3 A at 74 C to 1 A at 77 C, every port goes off at
  80 C, and they come back under 70 C.
- **The ESP32 runs at 80 MHz** (Wi-Fi needs no more), which takes a few
  tenths of a watt out of the case.
- **Cheapest board**: green mask and lead-free HASL instead of black and
  ENIG save $25 an order of five, and green lets the order use JLCPCB's
  Economic assembly.

## Through-hole USB-A

The five USB-A receptacles are through-hole (Jing Extension 902-131A,
30,000 in stock at JLCPCB, $0.06). Surface-mount ones were all under 600 in
stock. Through-hole costs JLCPCB's hand-soldering fee (Standard PCBA;
JLCPCB's capability page now lists it for Economic too: check the
quote), and the legs make the receptacles far harder to rip off when a
plug is yanked sideways.

## Parts JLCPCB has

Every part was picked from JLCPCB's assembly catalogue with its stock read
live on 17 Oct 2026 (`docs/parts.md`), favouring basic parts (no setup fee).
15 distinct extended parts (the thermistor added on 18 Oct) at about $3
each per order: the fee is about $9 a board at five boards, half that at
ten.

## Brand

Green mask (the cheapest; the brand's black adds $8 an order), white silk,
square corners (the brand allows right angles only), the OffGrid mark on the top and the lockup on the bottom, built from
the brand's own geometry (offgrid-brand v3.2.2) by `src/brand.py`, which
comes from Ridge 3 Lite.

## Ideas for v2

- A bypass for 5 V-only chargers, if that ever matters.
- Optional button-press outputs (an opto-coupler across a device's power
  button), for accessories that need a press to start. Not needed now:
  the filters' buttons will be wired permanently on.
- A 12 V switched output, for the larger enclosures' 12 V fans.
