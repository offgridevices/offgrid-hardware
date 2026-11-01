# 09 — Crown

**Pitch.** The whole product is one control: a machined crown round a round glass display. Turn it for Limit, press the glass for Power, and the Beacon Ring's node is the Bind key.

**Form & size.** 88 × 72 × 18 mm slab, 24.5 mm at the crown, ~120 g. Soft-touch body (MJF nylon for batch 1, moulded PC/ABS later). Crown: CNC 6061, knurled, bead-blasted, graphite anodised. Glass cover over a 1.43" round AMOLED.

**Boards.** One 84 × 66 mm 2 oz board. The power path sits under the battery end, with XT60PW/XT30PW male on the left edge. Logic is in the middle. The display is on an FPC. Two hall sensors under the crown's 24-pole magnet ring. A tact switch under the floating display carrier, and one under the node. USB-C on the back edge. Drone leads exit the right end through clamped grommets.

**UX.** Power: press the glass (check, then on; press again for off). Limit: turn the crown. The scale is drawn round the display rim, with 24 crisp ball-detent clicks. Turning past 10 A shows "Props off? Press to confirm". Bind: press the lit node. Status: the Beacon Ring light pipe round the crown, plus words on the glass. First use: battery in, drone in, press the glass. There is one thing to touch, so you can't press the wrong button. Answers pain points 6 (words, not LED codes) and 4 (limit changed live with a turn).

**Cost delta.** Round AMOLED +$5, CNC crown +$3.5, magnets/halls +$0.8, glass +$0.5, MCU with more RAM +$0.5: ≈ +$10.

**Risks.** Display bandwidth (the STM32C071 needs partial updates, or move to a bigger MCU). Dust in the crown gap. Press feel of a floating display. Keep the warm power path away from the display.

**Scores.** Premium 5 · Noob-proof 5 · Bench practicality 4 · Build quality 4 · Uniqueness 4
