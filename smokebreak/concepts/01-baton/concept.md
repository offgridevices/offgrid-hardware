# 01 Baton

**Pitch:** a torch-sized aluminium tube. Battery in one end, drone out the other, and everything you touch sits in one line on a flat spine: screen, Power ring, Bind, Limit slider.

**Form & size:** Ø32 × 140 mm (144 mm with the battery pins), about 130 g. Black anodised 6063 aluminium tube with a milled 18 mm flat on top (the spine) and a flat foot underneath, so it cannot roll. Rubber boot at the drone end. Batch 1: stock 32 × 1.6 mm tube, milled, with a printed inner sled (MJF) and printed end caps. Later: a custom extrusion with card-guide rails (~$1.5k die) and moulded caps.

**Boards (2, stacked, slide in from the battery end):**
- **A, power:** 20 × 96 mm, 2 oz. XT60PW male on top and XT30PW male underneath at the end, so the board itself is the rib between them. FETs, shunt, pulse resistors and TVS on the underside, pressed onto a rib in the tube through a gap pad. The tube is the heatsink. Drone leads are soldered at the far end.
- **B, logic and face:** 18 × 112 mm, 6 mm above A. It carries the MCU, the 1.14" IPS, the switches, the ring LEDs, a hall sensor for the slider and the beeper, with USB-C at the drone end above the lead gland.
- A and B are joined by a 2 × 6, 1.27 mm board-to-board header.

**UX:**
- **Power:** press inside the Beacon Ring.
- **Bind:** a small button next to the ring.
- **Limit:** a stainless slider that runs AUTO, 1, 2, 5 and 10. 20 A sits behind a sideways gate, so you can't land on it by accident (props off). The setting can be read without power. Answers SPEC §2 pains 4 and 6.
- **Screen:** a colour 1.14" IPS with three lines of words.
- **First use:** 1 Battery in, 2 Drone in, 3 Press the ring.

**Cost delta:** about +$6 (tube and machining +$3.5, IPS and glass +$1.2, second board and header +$0.6, slider and hall sensor +$0.6). Landed cost about $16.5.

**Risks:**
- A physical slider can't drop back on its own after the 30 s at 20 A, so the screen has to say "Slide back".
- The leads pull on the end of a light, round body.
- The board stack is a tight fit (5.6 mm under board B).
- A long, narrow board 18 mm wide.

**Scores:** Premium 4 · Noob-proof 4 · Bench practicality 4 · Build quality 5 · Uniqueness 4
