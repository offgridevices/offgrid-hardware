# 04 Halo

**Pitch:** the product is the OffGrid mark: a machined C-shaped ring with the Beacon node standing in the gap. The node is Power, the ring is the status light, and you set Limit by touching the number printed on the ring.

**Form & size:** Ø96 mm, band 24 mm wide, 18 mm tall. The Ø20 node stands 22 mm tall on a recessed bridge, so it reads as floating. About 160 g.
- Black anodised aluminium, CNC-machined, hollow, with a rubber base.
- A frosted light channel inset along the inner edge.
- Glass over the screen.
- Batch 1: CNC aluminium or MJF nylon with paint. Later: die-cast and machined.

**Boards:**
- **One C-shaped 4-layer board** (OD 92, ID 52, 2 oz outer layers) follows the band.
- The power path (FETs, shunt, pulse resistors) sits in the lower arc, pressed through a gap pad onto bosses in the base. The ring is the heatsink.
- XT60PW + XT30PW male are on the outer wall at 9 o'clock, stacked with a rib between them. The drone leads exit through glands at 3 o'clock.
- USB-C is on the outer wall at 5 o'clock.
- A Ø16 node board (Power switch and ring of LEDs) is joined by a flex through the bridge.
- Capacitive touch pads sit under the printed Limit numbers.

**UX:**
- **Power:** press the dot.
- **Limit:** touch AUTO, 1, 2, 5, 10 or 20 on the left arc. Your choice lights up. Touching 20 asks for a second touch: props off.
- **Bind:** a stainless button on the right arc.
- **Screen:** a 1.14" IPS at 6 o'clock, facing you.
- **Status:** the whole ring glows in the status colour.
- **First use:** 1 Battery in, 2 Drone in, 3 Press the dot.
- **Why it's noob-proof:** the current flows round the ring from the battery side to the drone side, so it explains itself.
- **Pains answered (SPEC §2):** best on 6 (status you can't miss) and 4 (Limit you can see).

**Cost delta:** about +$10 (machined C ring and node +$5, C-shaped board panel waste +$1.2, touch and 16 LEDs +$0.6, IPS and glass +$1.5, flex +$0.4).

**Risks:**
- Touch pads under anodised aluminium need glass or PMMA inlays.
- Accidental touches (Limit only changes on a deliberate press).
- The largest footprint of my four.
- The bridge looks fragile when it is thin.

**Scores:** Premium 5 · Noob-proof 4 · Bench practicality 3 · Build quality 4 · Uniqueness 5
