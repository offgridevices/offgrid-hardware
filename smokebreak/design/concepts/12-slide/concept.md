# 12 — Slide

**Pitch.** One machined slider tells the whole story from left to right: Off, Check, On, and a spring past On for Bind. Where the knob sits is the state, readable from across the bench.

**Form & size.** 114 × 58 × 16 mm, 23.5 mm at the knob, ~130 g. Moulded soft-touch body (MJF for batch 1). Bead-blasted CNC aluminium knobs on steel carriages, riding two 3 mm ground rods.

**Boards.** One 108 × 52 mm 2 oz board. A 2.08" 256 × 64 bar OLED on an FPC. Magnets in the carriages are read by linear hall sensors (two under the slider, one under the fader), so position is absolute and contactless. The rods, detent strip and return spring sit in a sub-frame screwed to the top shell. XT60/XT30 male on the left, drone leads on the right, USB-C on the back.

**UX.** Off → Check runs the 3 V probe and drone memory and stops there: nothing at battery voltage reaches the drone. → On checks again, then powers. Slide back for off. Bind: push past On into the spring zone and let go; it binds and returns to On. Limit: a fader (AUTO, 1, 2, 5, 10 A); 20 A is behind a sideways gate, so "props off?" is confirmed by hand. After a trip the ring goes red, and the slider must go back to Check to re-arm (no auto-retry). Check before On is built into the layout. Answers pain points 2, 3, 4 and 6.

**Cost delta.** Bar OLED +$4, knobs +$2.5, rods/carriages/springs +$1.5, halls +$0.9: ≈ +$9.

**Risks.** The knob reads On after a trip (handled by the re-arm rule and the red ring). Dust in the slot (brush seal). Larger footprint. Fader gate wear.

**Scores.** Premium 4 · Noob-proof 5 · Bench practicality 4 · Build quality 4 · Uniqueness 4
