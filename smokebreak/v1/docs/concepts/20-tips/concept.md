# 20 — Tips

**Pitch.** One body, swappable magnetic connector tips: BT2.0 whoop to AS150U 14S lifter, with no adapters. Each tip tells the box what it is.

**Form & size.** Body 84 × 52 × 18 mm, plus 9 mm tips at each end. ~130 g with XT60 tips. CNC or die-cast aluminium body; glass-filled nylon tips (MJF for batch 1, moulded later) with N52 magnets and a latch tooth.

**Boards.** One main board, 80 × 48 mm. At each end, a socket with two 4 mm gold spring-banana contacts (40 A class), one ID pogo pin and two magnets. Each tip holds its connector, two mating pins and a 1 % ID resistor. Drone tips carry a 10 cm 14 AWG lead. USB-C on the back face.

**UX.** Power is a 12 mm cap inside the Beacon Ring; Bind and Limit are buttons with arrows; 1.3" OLED. The tips set things for you: a BT2.0 tip selects the 1S profile and 1 A; an XT30 tip blocks 20 A; an XT90 or AS150U tip pre-selects the 22 Ω pre-charge bank. With no drone tip fitted it won't power ("Fit a drone tip"). First use: click in the tips → battery in → drone in → Power. Answers pains 5, 8, 4 and 7.

**Changes the spec.** The box has one battery input (XT60 and XT30 male tips in the box) instead of two built in. The live-but-shrouded spare input disappears, and adapter wobble and resistance go with it.

**Cost delta.** Sockets +$2, XT60/XT30/BT2.0 tip pairs +$4.7, minus built-ins −$2.3, aluminium +$5 → about +$9.5. The heavy-lift tip kit is sold separately.

**Risks.** Two extra mated contacts (+~1 mΩ, so use 4 mΩ FETs), contact wear (~1,000 cycles, tips are replaceable), a tug pulling the magnets free (latch tooth, 20 N), mis-read ID (fails safe).

| Premium | Noob-proof | Bench practicality | Build quality | Uniqueness |
|---|---|---|---|---|
| 4 | 4 | 5 | 4 | 4 |
