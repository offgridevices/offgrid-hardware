# 10 — Arm

**Pitch.** Powering a drone becomes a deliberate act. Lift an aircraft-style guard to arm, then flick a toggle. Close the guard and the drone is off, always.

**Form & size.** 96 × 56 × 18 mm, ~140 g. The guard adds 13 mm when closed and stands 40 mm when open. Soft-touch moulded body. Smoked polycarbonate guard on a 2 mm stainless pin with a torsion spring. Metal-bushed C&K-class toggle.

**Boards.** One 90 × 50 mm 2 oz board. The toggle (ON-OFF-(ON), PCB mount) only signals the MCU: no drone current goes through its contacts. A hall sensor sits under the guard-tip magnet. 1.3" OLED. The rocker is two tact switches under an aluminium paddle. XT60/XT30 male on the left, drone leads on the right, USB-C on the back.

**UX.** Power: lift the guard (screen says "Armed"), flick away from you to check and power on; flick back for off. Closing the guard cams the lever to Off and the hall sensor cuts power. Bind: pull the toggle toward you (momentary). It runs the three-cycle bind, the ring goes blue, and the screen says "flick up to carry on". Limit: rocker − / +; 20 A needs + again within 3 s. The Beacon Ring round the bushing glows through the closed guard. First use: battery in, drone in, lift and flick. Answers pain points 2 and 6, and the loved "power switch for binding".

**Cost delta.** Toggle +$3, guard/pin/spring +$1.5, hall +$0.3, paddle +$0.6, bigger OLED +$1: ≈ +$6.5.

**Risks.** Guard hinge abuse. The lever can snag leads. After a Bind the lever and the power state disagree (the screen explains). The open guard is tall.

**Scores.** Premium 4 · Noob-proof 5 · Bench practicality 4 · Build quality 4 · Uniqueness 4
