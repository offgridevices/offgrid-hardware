# 03 Lantern

**Pitch:** stands upright on the bench like a small lantern. A glowing glass band shows the status in 360°, readable across the room. Turn the knurled crown to set Limit and press its centre for Power.

**Form & size:** Ø46 × 98 mm on a Ø52 × 7 mm stainless base, about 230 g (110 g of it ballast, so the leads can't tip it).
- Body: black anodised aluminium tube.
- Halo: a 5 mm band of frosted glass or PMMA.
- Crown: knurled aluminium.
- Screen cover: curved glass.
- Batch 1: CNC tube and crown, MJF inner chassis. Later: impact-extruded tube and moulded chassis.

**Boards (2):**
- **A, main:** 38 × 70 mm, stands vertically. The power path sits low (FETs, shunt and pulse resistors clamp through a gap pad onto the stainless base, which is the heatsink). Logic, MCU and the 1.47" display are high up.
- XT60PW + XT30PW male are on the left edge, stacked with a rib between them. The drone leads are soldered on the right edge. USB-C is on the back.
- **B, crown:** Ø40, carries the Power switch, the Beacon Ring LEDs and an AS5600 magnetic encoder that reads a magnet in the crown (no contacts to wear).
- A and B are joined by an 8-way FFC.

**UX:**
- **Power:** press the centre of the crown.
- **Limit:** turn the crown. AUTO, 1, 2, 5 and 10 click into place against an index mark. 20 A needs push-and-turn, like a medicine cap: props off, physically.
- **Bind:** a stainless button under the screen.
- **Screen:** a 1.47" portrait IPS with words and big numbers.
- **First use:** 1 Battery in, 2 Drone in, 3 Press the top.
- **Pains answered (SPEC §2):** best on 6 (status you can see across the room) and 4 (Limit is a real dial).

**Cost delta:** about +$9 (machined tube and crown +$4, stainless base +$1.5, encoder and magnet +$0.7, 1.47" IPS +$1.2, glass halo +$0.8, second board and FFC +$0.6).

**Risks:**
- Tall: a knocked lead can still topple it if the base is light.
- The crown seal and its detent feel.
- More parts to assemble.

**Scores:** Premium 5 · Noob-proof 5 · Bench practicality 4 · Build quality 5 · Uniqueness 4
