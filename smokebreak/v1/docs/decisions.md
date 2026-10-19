# SmokeBreak v1: decisions

The trade-offs behind v1, newest first within each topic. Each says what
was chosen, what else was on the table, and why. The pictures each decision
was made from are in [`smokebreak/design/`](../../design/) (see its README).

## The product

- **Form: "Arm"** (concept 10 of 20, 11 Oct 2026). A guarded metal toggle
  you lift and flick, with dramatic arming screens. The other concepts and
  why they lost are in [`smokebreak/design/concepts/`](../../design/concepts/).
- **Compact redesign** (13 Oct 2026). The first layout (a 100 × 58 × 18 mm
  box with side-entry sockets and panel-mount drone plugs) worked, but the
  owner wanted it thinner and smaller without losing a feature. The result
  is 97 × 56 × 15 mm:
  - a 2.25" bar screen, not 1.9";
  - top-entry balance sockets in a well, not along the back wall;
  - flat SMD pre-charge resistors under the screen, not wire-wound ones
    standing up;
  - drone leads on solder pads, not panel-mount plugs.

  The case was first drawn at 54 mm deep. At that size the board was over
  80 % full and could not be placed, so it grew to 56 mm.
- **Cost.** The original spec said "no price target, the best on the
  market" (10 Oct). The owner's later target was $20–22 landed (11 Oct).
  v1 lands at about $55.60 at 100 units, display included. Most of the gap is the two
  pre-charge resistors (about $14.70) and the C&K toggle (about $10.20).
  This decision is still open (README *Next steps*).

## The face

- **One margin, M = 6 mm, everywhere.**
  - The screen window sits M from the left and M from the back edge.
  - The balance well is centred under the screen and ends M before the front.
  - The switch guard ends M before the right edge.
  - The rocker is centred under the switch and ends M before the front.

  Every number is in `src/geometry.py`, so the board and the case cannot
  drift apart. Pictures: [`smokebreak/design/face/`](../../design/face/), [`smokebreak/design/compact/`](../../design/compact/).
- **G2 corners** (a superellipse, n = 5) on the case and on the screen
  window. The screens draw the same rounded outline, so the UI's corners
  meet the window's exactly ([`../ui/`](../ui/)).
- **Text only where it is needed:** "2S … 6S" under the sockets and "LIMIT"
  under the rocker, on one line along the front edge. They are
  multi-material inlays: 2.5 mm caps, strokes at least 0.44 mm.
- **Flip-up = on**, away from the user. That is the trigger every pilot
  already knows. A pull-toward-you toggle was considered and rejected.
- **One rocker, not two buttons.** Limit − and + are the only settings a
  pilot changes at the bench. Forum complaints about other stoppers are
  about too many modes, not too few ([`smokebreak/design/market-research.md`](../../design/market-research.md)).
  Pictures: [`smokebreak/design/packs/`](../../design/packs/).
- **Grip and stability:** rubber feet (Bumpon) on a printed floor, and a
  finger lip under the back edge. Fingertips hook the lip while the thumb
  flips the switch, so the box does not rock when armed. A steel floor was
  considered; printed was chosen for now. Pictures: [`smokebreak/design/stability/`](../../design/stability/).

## Safety

- **A soldered 40 A / 80 V fire fuse** (Eaton 2822HC40), by the battery
  plugs. Three options were drawn ([`smokebreak/design/fuse/`](../../design/fuse/)): the
  soldered fuse, a swappable blade fuse in a bay, and an inline fuse on the
  drone lead.
  - SmokeBreak's own switch clears every outside fault thousands of times
    faster than any fuse, so a fuse only blows when a part inside has
    already failed shorted. A fresh fuse would not bring the box back, so
    swapping it gains nothing.
  - Blade fuses also stop at 58 V (13S), and the bay made the case 8 mm deeper.
- **A 100 V aux supply (TI LM5164)** instead of a 65 V part. A 16S or 24S
  pack plugged in by mistake cannot hurt it. The controller's over-voltage
  input cuts at 64.0 V, and the firmware refuses anything above 62.5 V with
  a "too high" screen. The buck needs 6 V, so USB feeds the 5 V rail
  directly, and a 1S pack needs USB.
- **The simulation review's network** (`sim/SIM.md`). The plain input
  capacitors failed the hot-plug and short-circuit cases. The board uses
  the variant that passes all 21 checks while staying small:
  - Q11 in the battery minus, with a 4.7 MΩ gate (10 µA standby);
  - a damper and a snubber;
  - RISCP 40.2 kΩ;
  - a second, fixed 65 mV hard-short comparator;
  - a slewed gate;
  - 150 V parts in the probe and the pre-charge driver.
- **Pre-charge resistors: 2 × Vishay D2TO020 3.9 Ω** (TO-263, flat, SMD).
  The earlier AC05 wire-wounds stood 7.5 mm tall; under the screen the limit
  is 6.34 mm, and SMD is assembled by PCBWay. The pulse rating (about 10 J
  each at 100 ms) gives the firmware's 12 J abort a 40 % margin. They
  cost $7.35 each, and LCSC has none in stock.

## The board

- **6 layers, 1 oz copper on every layer.** The battery current runs on
  the inner planes; 0.5 oz inner copper was too thin for 25 A.
- **Power copper drawn before routing** (`src/make.py`):
  - **The battery corner is a VBAT island on every layer but ground.** The
    XT30's plus, below the XT60, reaches the fuse through it.
  - **The fuse's load-side vias sit under the fuse body,** because the MCU's
    pins leave no room beside it.
  - Q1's drain vias sit south of the logo's field, so the underside stays clean.
- **Balance taps as straight buses.** Pin k of every socket is tap k, and
  every pin 1 is on one line. So each tap is one straight track along its
  pin row, drawn before routing. The router had failed these tracks twice
  without them.
- **Placement by a spreader** (`src/spread.py`). `place.py` holds the
  intent: fixed parts where the case puts them, and an anchor for every
  other part. The spreader settles the anchors on a 0.05 mm raster, so
  re-placing after a change is one command.
- **Board corner radius 2.5 mm** (the case's is 8 mm). This keeps the
  XT30's locating peg on the board while the board still clears the G2
  wall by 0.4 mm.
- **USB-C in the back wall**, beside the screen's FPC end: the one spot on
  the back edge that the screen module and its connector leave free.

## The case

- **Guard 17.9 mm tall** (13.5 mm was planned). The C&K 7107's lever tip
  stands 26 mm above the board, so a lower guard would need a short-lever
  toggle.
- **Ø6 × 3 mm N52 magnet** in the guard tip, over the hall switch. A
  smaller magnet reached only about 4 mT, at the switch's 4.8 mT maximum
  operate point. The Ø6 × 3 gives 12.9 mT closed, and the switch releases
  past about 40°.
- **The guard's hinge pin is hidden.** It loads along a groove inside the
  back wall before the display goes in, so nothing shows on the outside.
- **The drone leads are clamped by the floor's end tab**, with no separate
  clamp part.
- **Three M3 screws into heat-set inserts.** H2 sits under the rocker
  opening, so its boss steps down under the opening and is tied to the walls.

## Brand

- The logo is built from the brand's own geometry (offgrid-brand v3.2.2) in
  `src/brand.py`. `tools/verify_brand.py` checks it against the brand's SVG.
- On the board's underside: the lockup, centred left to right, 1 mm above
  the middle (the 6S socket's top pin sits at the centre); the name and
  version along the back edge; the US flag under the rocker; the note
  "The magic smoke stays in." under the pre-charge resistors.
