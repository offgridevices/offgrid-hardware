# Lessons from building boards

Things a board taught us that will matter on the next one. Each says why, so
it can be judged rather than followed blindly. Tool behaviour is noted with
the version it was seen on: re-check it on a newer version before relying on
it. Part availability and prices are not kept here; they go stale (each
board's `docs/` keeps its own dated checks).

## Power and heat

- **Give the supply as much parallel copper as the return.** On Ridge 3 Lite
  the 60 A battery current had one plane while ground had five layers; the
  copper next to the battery pad made the most heat on the board and the
  nearest channel ran 40 °C hotter than the farthest. Flooding the spare
  copper of two inner signal layers with the supply net (joined by the
  supply's existing through vias) took 10 °C off the hottest FET.
- **The power entry is the hot spot.** All the current enters at the battery
  pads; whatever sits next to them runs hottest. Place them so the current
  spreads evenly, and put the most robust parts nearest.
- **Simulate heat on the routed board.** Vias and tracks perforate the
  planes: the routed board ran up to 15 °C hotter than the same design
  modelled before routing.
- **Sun is a heat source.** In the desert case, sunlight on the board was the
  largest single input at hover. A canopy or plate over the board is the
  cheapest cooling.
- **Protection must sense the hot part.** An ESC's own temperature limit
  works when its MCU sits on the FET copper and tracks it; check in the
  thermal model that the sensor reaches its limit before the FETs reach
  theirs.

## Switching and transients

- **Simulate the half-bridge with layout parasitics before choosing gate
  resistors.** Fast gate drive overshot 40 V FETs at 4S; slower drive fixed
  it at a known cost in switching loss.
- **Regenerative braking into an open battery** has nowhere to go: the bus
  rises far beyond any small TVS. State it as a limit (keep the pack
  connected) rather than pretend a part fixes it.
- **A bulk capacitor at the battery pads is part of the design**, even when
  it is fitted by hand; without it ripple and hot-plug ringing exceed the
  ratings.

## Layout and fabrication

- **Congestion, not area, sets the layer count.** On a dense board the
  bottleneck is round the central MCU; a larger board did not help. Decide
  layers and fine rules with an early routing trial.
- **Use the fab's limits as the DRC rules**, not looser defaults, and read
  them from the fab's capability page for the stackup being ordered.
- **Reserve artwork space at placement.** A gold (mask-opening) flag needs a
  ground-only copper area with no other nets on that face; after routing a
  dense board none was left.
- **Fine rules and small vias cost more.** They are fab capability tiers:
  check the quote, and use them only where the density needs them.

## Tools

- **Autorouters stall on the last few connections.** Budget for finishing
  them by hand (or with a targeted script), then lock the copper and re-run
  DRC. Seen with Freerouting 2.4.1, which also ignored some of its own
  options; we removed plane nets from its input instead.
- **KiCad DRC needs the project file** (`.kicad_pro`) next to the board, or
  it runs with default rules and reports nonsense. (KiCad 10.0.6)
- **KiCad saves polygon holes as slits** ("fractured"): after a save, count
  a shape's holes by area, not by its hole count. (KiCad 10.0.6)
- **In KiCad's Python API, keep a reference to anything you remove** from a
  board, or Python frees it and KiCad crashes later. (KiCad 10.0.6)
- **Outputs carry timestamps.** Gerbers and drill files embed their creation
  date and STEP exports renumber their entities on every run. Compare
  outputs with the dates ignored, and do not diff STEP files.
- **Parse firmware configs fully:** a `#define` with no value still enables a
  feature; a parser that only reads `NAME VALUE` pairs misses it.
