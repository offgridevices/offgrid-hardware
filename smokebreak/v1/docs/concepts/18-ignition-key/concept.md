# 18 — Ignition

**Pitch.** Power is a key you turn, and the key *is* the drone: each key carries that drone's history, and with the key out nothing can power.

**Form & size.** Desk-instrument wedge, 92 × 64 mm, 26 mm high at the back to 13 mm at the front, ~160 g. CNC aluminium body (later die-cast zinc), stainless barrel, anodised aluminium key heads, one colour per drone.

**Boards.** Main board 86 × 58 mm, horizontal (power path + MCU); 1.3" OLED on an FPC under the sloped glass. Barrel board 24 × 24 mm with 2 hall sensors (key position) and 4 spring contacts; it joins the main board through an 8-pin board-to-board connector, with a 90° flex loop in the rotor. The key blade is a gold-pad PCB with a 2 kB EEPROM. XT60/XT30 male on the left end, female leads on the right, USB-C at the back.

**UX.** *Power*: turn Off → On (detent) for probe, pre-charge, on. Turn back for off. *Bind*: turn past On to the spring position and let go; it runs the 3 cycles and returns to On. *Limit*: one button with six lit dots; 20 A asks for a second press. The key closes the driver-enable loop in hardware. The key stores capacitance, idle amps, limit and the last checks; the probe cross-checks them ("Wrong key?"). A Guest key falls back to fingerprinting. First use: battery in → insert key → turn to On. Answers pains 6 and 1, keeps the loved bind button, and removes spec risk 14.5.

**Cost delta.** Barrel and halls, 4 keys, CNC body → about +$12.

**Risks.** Lost keys (Guest key spare), contact wear (gold, 10k cycles), barrel tooling, dirty contacts.

| Premium | Noob-proof | Bench practicality | Build quality | Uniqueness |
|---|---|---|---|---|
| 5 | 5 | 4 | 4 | 5 |
