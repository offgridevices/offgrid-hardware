# 17 — Tag

**Pitch.** An e-ink luggage tag for the bench: the last verdict stays on its face with no power, so a fault can't be forgotten and the device is its own logbook.

**Form & size.** 104 × 76 × 12 mm incl. the eyelet shoulder, ~95 g. CNC aluminium unibody (bead-blast, black anodise), 0.7 mm strengthened glass face. Batch 1: CNC (or MJF nylon + glass); later die-cast.

**Boards.** One 4-layer board, 98 × 56: power path on the bottom right, on a thermal pad to the aluminium. 2.9" e-ink (296 × 128) on a 24-pin FPC. XT60PW + XT30PW male on the left end; drone leads (XT60/XT30 female, 10 cm) out of the right end through grommets; USB-C on the right shoulder. 3 RGB LEDs under a ring light pipe around the eyelet.

**UX.** Three aluminium keys under the e-ink. The screen draws each key's name right above it: *Bind*, *Power* (becomes *Off* when on), *Limit 2A*. Going to 20 A, the label itself asks "Props off? Press again". The ring and beeper are instant; e-ink partial refresh (~0.3 s) handles live amps. Unplugged, the screen keeps "Passed · Drone 3 · 0.42 A", or "SHORT 0.3 Ω". First use: battery in → drone in → press the key under *Power*. Answers pains 2, 6 and 7 best.

**Cost delta.** e-ink +$2.50, CNC aluminium and glass +$7 → about +$9.5 (≈ $20 landed).

**Risks.** e-ink is slow below 0 °C (the ring covers it). The anodised case sits next to live pins, so the shrouds need creepage. The glass face can crack if dropped. The eyelet only hangs an unplugged unit.

| Premium | Noob-proof | Bench practicality | Build quality | Uniqueness |
|---|---|---|---|---|
| 4 | 5 | 4 | 4 | 4 |
