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
- **In a sealed plastic case the wall is the limit, not the chip.** On
  LayerCam (a camera in a printer's 65 °C chamber) a stick-on heatsink took
  only 2 °C off: it moves heat into the trapped air, which still has to
  leave through the same plastic. Only a part that reaches the outside
  (metal pressed against the thinnest wall, at the vents) moved the limit.
  Model the path to the outside air first; size the fins last.
- **Run the hot product only as hard as its job needs.** LayerCam's video
  pipeline at full rate put the SoC at its limit; Prusa Connect only takes
  a still every 10 s, so the camera sleeps its sensor between shots and
  the same hardware runs 30 °C cooler.
- **Check every part's rating against the box's temperature, not the
  room's.** At 85-90 °C board temperature the cheap choices fail first:
  X5R capacitors (85 °C), tactile switches (70 °C), USB-C receptacles
  (80 °C), a tuning-fork 32 kHz clock (drifts -100 to -150 ppm, past a Wi-Fi
  module's +-30 ppm sleep-clock limit, whatever its temperature grade).

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
- **Pre-route what has an obvious path.** On SmokeBreak every balance
  socket's pin k is tap k and all the pin 1s share a line, so each tap is
  one straight track along its pin row. Freerouting failed those taps twice;
  drawn first, they took no effort and freed the router for the rest.
- **Leave via room beside a controller's gate and source pins.** The
  TPS48000's SRC and GATE pins sit side by side above the first FET's gate
  pad; with 0.5 mm between the controller and the FET there was no room to
  cross them. Moving the controller 1 mm away fixed it.
- **Fine rules and small vias cost more.** They are fab capability tiers:
  check the quote, and use them only where the density needs them.

- **A switch node on an inner pad needs a pour, not a track.** Some small
  bucks (Silergy SY8368A, QFN 3x3) put LX on a pad boxed in by the ground
  pads; a track through the gap is a long thin neck carrying the inductor
  current. Draw a pour: the fill takes the whole gap and widens at once.
  (Print Hub v1)
- **Never let a saved setting or a power-up default switch a load on
  without checking the supply first.** On Print Hub the "on at power-up"
  ports came on with no charger at all; the review caught it. Gate every
  switch-on on the supply being there, and switch everything off when it
  goes. (Print Hub v1)
- **Read the module's drawing for where its optical axis is.** LayerCam's
  camera module has its lens 8.4 mm from one edge and 15.6 mm from the
  other; placing to a centred outline put the camera's cable socket under
  the module.
- **Check a board's handedness in its slot in 3D, not in plan.** LayerCam's
  USB board was drawn from its parts' face with its x along the slot's v
  axis; placed with that face towards the opening, x runs along -v, so the
  board was a mirror image and its long side would have hit the wall where
  the grooves are short. Writing down the placement as a rotation (det
  +1) and checking the outline against the housing caught it; the check
  promised in the docstring had never been written.
- **Check a mirrored module's pins after the flip.** A module on the back
  face is mirrored: the crystal, antenna and buck parts placed for the
  unflipped pin-out ended 17 mm from their pins. Place them from the pad
  positions read off the placed footprint.
- **Lay out a fine-pitch chip's escapes at placement, not in the router.**
  LayerCam's RV1106 (QFN-128, 0.35 mm pitch) jammed every routing run at
  the same pins until each pin that leaves the chip's face got a stub and a
  via before routing, the pin between two other escapes first. Check the
  via against the pitch: with 0.45 mm vias two escapes a pin apart leave
  0.25 mm, too little for the pin between; 0.35 / 0.2 mm vias and 0.1 mm
  stubs (in the fab's 6-layer rules) let it through.
- **Keep the escape band clear on both faces.** Decoupling caps on the
  back face under a QFN's pins put their own plane vias in the band its
  signals must cross (38 on LayerCam).
- **Look for pockets.** A spot walled in by a buck's switch node and its
  ground (between the inductor, the buck and the SoC's band) trapped
  whichever small part the placer put there, three in turn. Keep parts out
  of such pockets, and put a feedback network where its plane can reach.
- **Size a rail's tracks by its current, not by its being a rail.**
  LayerCam's 1.8 V carries 0.05 A; at 0.2 mm it was the net every routing
  run left open; at 0.127 mm it routed.
- **A placer that cannot place a part must stop the build.** An unplaced
  part sits at the origin, which on LayerCam is inside the lens window; a
  warning in a long log is not enough.

## Tools

- **Autorouters stall on the last few connections.** Budget for finishing
  them by hand (or with a targeted script), then lock the copper and re-run
  DRC. Seen with Freerouting 2.4.1, which also ignored some of its own
  options; we removed plane nets from its input instead.
- **KiCad DRC needs the project file** (`.kicad_pro`) next to the board, or
  it runs with default rules and reports nonsense. (KiCad 10.0.6)
- **Saving a board also writes its project.** Load a board copied without
  its `.kicad_pro`, save it back over the original, and the project's net
  classes become KiCad's defaults. Copy the project before loading.
  (KiCad 10.0.7)
- **Freerouting drops vias it does not need.** A via placed before routing
  for the router to use, with only one connection, is gone after the
  session import; add such vias after routing. (Freerouting 2.5.0)
- **"Dangling" is not always a stub.** KiCad calls a track's end free when
  the track overruns the one it joins, so deleting every dangling track can
  disconnect a net. Remove them one at a time and keep each removal only if
  DRC stays as clean (SmokeBreak `src/dedangle.py`). (KiCad 10.0.7)
- **A courtyard's bounding box can miss the pins.** For some footprints
  (an LQFP's cross-shaped courtyard) `GetCourtyard().BBox()` came back
  smaller than the pads. A placer should check the pads' boxes too.
  (KiCad 10.0.7)
- **KiCad saves polygon holes as slits** ("fractured"): after a save, count
  a shape's holes by area, not by its hole count. (KiCad 10.0.6)
- **In KiCad's Python API, keep a reference to anything you remove** from a
  board, or Python frees it and KiCad crashes later. (KiCad 10.0.6)
- **Outputs carry the KiCad build string.** Gerbers and drill files name
  the exact build (`10.0.7-10.0.7~ubuntu24.04.1` from Ubuntu's package,
  `10.0.7` in the official image), so committed outputs only match CI when
  they are built in the same pinned image. (KiCad 10.0.7)
- **Outputs carry timestamps.** Gerbers and drill files embed their creation
  date and STEP exports renumber their entities on every run. Compare
  outputs with the dates ignored, and do not diff STEP files.
- **Parse firmware configs fully:** a `#define` with no value still enables a
  feature; a parser that only reads `NAME VALUE` pairs misses it.
- **KiCad's rotation: a standard two-terminal part at 90 degrees has pad 1
  at the bottom** (y down on screen), not the top. Check a placement plot
  coloured by net before drawing power copper by hand. (KiCad 10.0.6)
- **Keep the autorouter off the planes:** mark the inner plane layers as
  power layers (`SetLayerType(..., LT_POWER)`) in the copy exported for
  Freerouting, or it routes signals through them. (Freerouting 1.9.0)
- **Freerouting 2.5.0 stalled** with a dozen connections left on Print Hub
  (after a few passes, no progress, no end); 1.9.0 finished the same board.
- **EasyEDA's 3D models can sit off their own land** (the HRO
  TYPE-C-31-M-12 by 2.55 mm). Look at a render before trusting the STEP for
  an enclosure; correct it with a model offset in the footprint.
- **Python default arguments are read once, at import.** `def f(c=pcb.CLEAR)`
  kept the first board's clearance after `pcb.configure()` switched boards;
  read module settings inside the function.
- **Freerouting reads every rule area as a keepout,** even one that only
  scopes a DRC rule: a rule area round the SoC for a finer clearance made
  it route nothing there (80 connections open). Leave such areas out of
  the copy exported for it. (Freerouting 1.9.0, KiCad 10.0.7)
- **Freerouting will not start a route from a pad that fixed copper
  crowds** below its own clearance class, even by 0.001 mm: locked escape
  stubs 0.126 mm from their neighbours against a 0.127 mm class left every
  SoC net unrouted. Give it the fixed copper a hair smaller and put the
  real sizes back after the import. (Freerouting 1.9.0)
- **Freerouting 1.9 can crash on its own fed-back wiring** (a
  NullPointerException in a later round): keep the best round and go on
  with that.
- **A repair step must be able to undo itself.** The finisher's plane
  repair tore up nine signal nets' vias to rejoin one cut-off 3.3 V pad and
  could not route them again; it now rolls back a round that leaves a net
  open and joins the pad with a track instead.
- **"Dangling" also means a track that runs past its joint,** or a via
  that only joins one layer's tracks. Trim the overrun back to where it
  enters the copper; replace such a via by short tracks inside its copper.
  Keep each change only if nothing comes apart. (KiCad 10.0.7)
- **Give each concurrent tool run its own files.** Two boards routed in one
  work folder shared `route0.dsn` / `.ses` names and overwrote each other;
  name them after the board.

## Mechanical

- **One file of mechanical numbers, read by the board and the case.**
  SmokeBreak's `src/geometry.py` holds the case, the margins, the height
  stack and every connector position. The placement and the CadQuery case
  both import it, so a change moves both and the fit check catches the rest.
- **Check the height under a display early.** A module over the board
  limits every part beneath it (6.34 mm on SmokeBreak); the standing
  pre-charge resistors had to become flat SMD ones.
- **Compute a magnet's field before printing the pocket.** The first guard
  magnet gave about 4 mT at a hall switch whose maximum operate point is
  4.8 mT; a Biot–Savart estimate in the fit check caught it.
