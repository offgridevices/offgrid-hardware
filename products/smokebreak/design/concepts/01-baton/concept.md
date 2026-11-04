# 01 Baton

**Pitch:** a torch-sized aluminium tube. Battery in one end, drone out the other. Everything you touch sits in a line on one flat spine.

**Form & size:** Ø32 × 140 mm (144 mm with the pins), about 130 g.
- Black anodised aluminium tube. The flat top spine and flat foot stop it rolling.
- Rubber boot at the drone end.
- Batch 1: milled stock tube, MJF sled and caps. Later: a custom extrusion with card guides, moulded caps.

**Boards (2, stacked, slide in from the battery end):**
- **A, power:** 20 × 96 mm, 2 oz. XT60PW male on top and XT30PW male below, so the board is the rib between them. The FETs and resistors underneath sit on a gap pad over a rib in the tube, and the tube is the heatsink.
- **B, logic and face:** 18 × 112 mm, 6 mm above A. It carries the MCU, the 1.14" IPS, the switches, the ring LEDs, a slider hall sensor and USB-C at the drone end.
- A and B are joined by a 2 × 6, 1.27 mm board-to-board header.

**UX:**
- **Power:** press inside the Beacon Ring.
- **Bind:** a button next to the ring.
- **Limit:** a stainless slider. 20 A sits behind a sideways gate (props off), and the setting is readable even unpowered.
- **First use:** 1 Battery in, 2 Drone in, 3 Press the ring.
- **Pains answered (SPEC §2):** 4 and 6.

**Cost delta:** about +$6 (tube +$3.5, IPS +$1.2, second board +$0.6, slider +$0.6).

**Risks:**
- The slider can't drop back on its own after the 30 s at 20 A.
- The leads pull on a light body.
- Tight stack: 5.6 mm under board B.

**Scores:** Premium 4 · Noob-proof 4 · Bench practicality 4 · Build quality 5 · Uniqueness 4
