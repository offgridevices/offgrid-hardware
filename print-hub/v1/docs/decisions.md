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
The accessories together draw 3.7 A typical and 5 A worst case at 5 V (fan
0.45 A, light up to 1 A, two filters charging up to 1 A each, a spare)
(`sim/power_budget.md`). So the board takes its own charger:

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

## 4 layers

Ground has its own unbroken layer (In1) and the 5 V rail its own plane
(In2) under the ports. Every ground and 5 V pad drops straight into its
plane through a via next to it; the two outer layers carry signals and a
ground fill. JLCPCB's standard 4-layer price is a few dollars more for five
boards than 2 layers, and it makes the buck quiet and the routing simple.
Standard rules only (0.15 mm track and gap, 0.6 / 0.3 mm vias): no
fine-line or small-via surcharge.

## Through-hole USB-A

The five USB-A receptacles are through-hole (Jing Extension 902-131A,
30,000 in stock at JLCPCB, $0.06). Surface-mount ones were all under 600 in
stock. Through-hole costs JLCPCB's THT assembly (Standard PCBA, not
Economic), and the legs make the receptacles far harder to rip off when a
plug is yanked sideways.

## Parts JLCPCB has

Every part was picked from JLCPCB's assembly catalogue with its stock read
live on 17 Oct 2026 (`docs/parts.md`), favouring basic parts (no setup fee).
14 distinct extended parts at about $3 each per order: the fee is about
$8 a board at five boards, half that at ten.

## Brand

Black mask, white silk, square corners (the brand allows right angles
only), the OffGrid mark on the top and the lockup on the bottom, built from
the brand's own geometry (offgrid-brand v3.2.2) by `src/brand.py`, which
comes from Ridge 3 Lite.

## Ideas for v2

- A bypass for 5 V-only chargers, if that ever matters.
- Optional button-press outputs (an opto-coupler across a device's power
  button), for accessories that need a press to start. Not needed now:
  the filters' buttons will be wired permanently on.
- A 12 V switched output, for the larger enclosures' 12 V fans.
