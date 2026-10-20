# Mesh Radio v1: the plan

Written 17 Oct 2026 for the owner's review. Nothing past the schematic is
built until the owner approves this plan. The requirements are in
[`../README.md`](../README.md); the research behind them is in
[`decisions.md`](decisions.md).

## What the board is

One board, about the width of a Heltec V4, that does a RAK WisBlock's job
with three additions:

- an amplifier that reaches about 3 W;
- a locking serial port for the Cairn drone;
- protection on every input.

Every part comes from a US, Japanese, Taiwanese, Korean, Norwegian or
German maker.

```
                    USB-C ─┐  solar ─┐  drone 5 V ─┐
                           ▼         ▼             ▼
                    [surge clamp + eFuse] x3  ──►  charger ──► battery (protected,
                                                     │          reverse-proof)
                                                     ▼
                     slide switch ─► load switch ─► 3.3 V rail
                                                     │
   Bluetooth ◄── nRF52840 (processor) ◄─SPI─► SX1262 (LoRa) ─► 15.9 dB pad ─► QPA9510 amplifier
   chip antenna        │    │                    ▲                              │ (battery-first
                       │    └─ drone port (serial, JST-GH)                      ▼  supply, buck-boost)
                       └───── GPS plug, expansion header          harmonic filter
                                                     │                          │
                                                     LNA ◄── antenna switch ◄───┘
                                                                   │
                                                          low-pass filter ─► U.FL (LoRa antenna)
```

## Key choices, in plain words

| Choice | Why |
|---|---|
| **nRF52840 bare chip** (Nordic, Norway) | It is the same chip as the RAK4631, so Meshtastic and MeshCore carry over. No module from a non-Chinese maker is stocked at both DigiKey and LCSC. |
| **SX1262** (Semtech, US) | The same radio chip as the RAK. Wired to the same processor pins as the RAK4631. |
| **QPA9510 amplifier** (Qorvo, US), up to about 35 dBm (3 W) | No ready-made module reaches 3 W any more. This is the part B&Q-class 3 W boards use. |
| **Power is set by the radio chip's drive, through a 15.9 dB pad** | The amplifier has fixed gain. The radio chip's setting moves output from about 10 mW to 3 W, and the pad keeps the amplifier safe even at the chip's maximum. The firmware's gain table holds 1 W in US mode. |
| **Amplifier runs from the battery through its own buck-boost** (TPS63810) | At 1 W the firmware lowers its voltage to save current; for 3 W it raises it to 4 V. With no battery it falls back to the charger, so the board still transmits on USB alone (at 1 W or less). |
| **SKY13330 antenna switch** (Skyworks, US) | Rated 10 W, 0.35 dB loss, in stock. The 3 W-class switch everyone uses is out of stock until January. |
| **Low-noise receive amplifier with bypass** (Infineon) | About 4.5 dB better hearing than a RAK. Firmware can turn it off to save about 5 mA. |
| **One 3.3 V rail for the processor and radio** | Both chips then always see the same signal level, even when the battery is low. |
| **Three protected inputs** (USB, solar, drone 5 V) | Each input gets a surge clamp, an over-voltage cut-off, a current limit and reverse blocking. The drone keeps the cell charged while it carries the node. |
| **Battery protection on the board**, plus reverse-battery protection | Unprotected cells are safe. A backwards plug does no damage. |
| **Drone port = locking JST-GH, Pixhawk TELEM wiring** | It plugs straight into a flight controller, or into the Jetson through a cable. It carries the same Meshtastic serial link the field loggers use. |

## Power: what it should draw

These are estimates from datasheets. They are measured on the built boards,
and those measurements replace these numbers.

| State | From the battery | Hearing vs a RAK | RAK WisBlock (owner-measured) |
|---|---|---|---|
| Listening, receive amp on (**default**) | **about 12–14 mA** | about 4.5 dB better (~1.7x the range in open air) | about 20 mA |
| Listening, receive amp off (battery saver) | **about 7–9 mA** | about 2.5 dB worse (~0.75x the range) | about 20 mA |
| Bluetooth connected to the phone | about +0.2–1 mA | |
| Transmitting at 1 W (30 dBm) | about 1.0 A while sending | about 0.12 A at 0.16 W |
| Transmitting at 2.5 W (34 dBm) | about 2.0 A while sending | |
| Transmitting at 3 W (35 dBm) | about 2.3 A while sending | |
| Switched off | about 20–30 µA | |

A message at LongFast lasts about 1 second on air. At 1 W that costs about
0.3 mAh per message, so the battery is spent listening, not sending.

**Why the receive amp is on by default.** The 3 W stage puts an antenna
switch and two filters between the antenna and the radio chip, a RAK has
neither, and they cost about 3 dB of incoming signal. The receive amp
(an Infineon chip in front of the radio, about 5 mA) more than makes that
back.

- **On:** the board hears weaker signals than a RAK, about 4.5 dB better,
  while still drawing less than a RAK (about 13 mA against about 20 mA).
- **Off:** it hears about 2.5 dB worse than a RAK.

Off is only a battery saver, for nodes that are close together. It is a
firmware setting. The 10 mA target (P1) is met only in that saver mode;
the owner accepted about 13 mA in exchange for the range (18 Oct 2026).

## Cost

**Update, 19 Oct 2026: about $87 per board at 10 boards and $68 at 100**
(the re-audit in `part-audit.md`). The +$10 is mostly the power-path
changes the −40 to +85 °C simulations called for (two 60 V current
limiters, +$8.46) and the better antenna filter (+$3.66). The table below
is the 17 Oct breakdown, kept for comparison.

**17 Oct: about $76 per board at 10 boards and $58 at 100, at DigiKey
prices.** The figures come from the audit (`part-audit.md`), with three
small lines estimated. That is above the roughly $40 the owner expected,
and well above the RAK's $32 retail. Assembly is extra.

| Block (DigiKey, 100 boards) | Cost |
|---|---|
| RF front end: amplifier, filters, antenna switch, LNA | $17.20 |
| Amplifier power: power mux, buck-boost, control voltage, temperature sensor | $4.85 |
| LoRa radio: SX1262, clock, matching | $8.97 |
| Input protection: 3 eFuses, surge clamps, ESD | $8.11 |
| Processor + Bluetooth | $7.96 |
| Charger and battery protection | $4.53 |
| Ports, buttons, LEDs | $3.85 |
| Power switch and 3.3 V rail | $2.89 |
| **Total** | **$58.39** |

The 3 W stage (the first two rows) is about $22 of that. A 1 W-only
version would replace it with a single Skyworks front-end chip (about $4
with its parts), for a total of roughly **$40**. See question 2.

## Size and build

- **243 assembled parts, on both sides** (250 in the circuit: 6 test pads
  and the unfitted expansion header are not assembled). About half of them
  are the amplifier, filters and power protection the RAK does not have.
- **58 × 25.4 mm** (19 Oct). The Heltec V4 is 51.7 mm long. 57 mm does not
  fit: the amplifier's choke meets a mounting hole.
- **6-layer board** (owner, 19 Oct), JLCPCB stackup JLC06161H-2116B:
  a solid ground plane on layer 2 (under the radio lines); signals on
  layers 3, 4 and 5 with ground filled round them (20 Oct: with layer 5 a
  second solid plane, too many connections had no way through). JLCPCB fills and caps
  vias in pads at no extra cost on 6 layers, which the nRF52840's inner
  balls and the amplifier's heat path need.
- **Test boards at JLCPCB.**
  - Every part has an LCSC number. A few (the amplifier and the LNA) are
    not stocked at LCSC, so JLC buys them through global sourcing, or they
    are shipped in from DigiKey.
  - The same files build at a US or allied assembler from DigiKey parts.

## What is proven now, and what is not

**Proven on the schematic (17 Oct 2026):**

- Every part was chosen against the requirements, from a non-Chinese maker.
- Every chip's pin list was taken from LCSC's data for that exact part and
  checked pin by pin against the maker's datasheet.
- The schematic is drawn by code from the circuit, and KiCad's netlist of
  the drawing equals the circuit, net by net.
- KiCad's electrical rules check: 0 errors, 0 warnings.
- Values come from the makers' reference designs (Nordic, Semtech, Qorvo,
  Infineon, TI), with the formulas shown in `src/circuit.py`.

**Also done:**

- An independent design review, with all its findings fixed (above).
- A DigiKey and LCSC audit of every line (`part-audit.md`).

**Not proven yet:**

- **Layout and the simulations.** Power surges, short circuits, bad
  batteries, heat at 60 °C in a message storm, filter performance and trace
  impedance are all run on the routed board, after approval.
- **Bench-only items.** These are set on built boards with a network
  analyser:
  - the RF matching values (marked "tune" in the code);
  - the exact output power and the firmware gain table;
  - receive sensitivity;
  - real current draw.
- **The QPA9510 at 902–928 MHz.** Qorvo's evaluation board is tuned 2%
  lower, so its output match is shifted by calculation and then tuned.
- **3 W into a missing antenna.** The antenna switch is rated 10 W into a
  good antenna, but its rating into an open port is not published.
  Firmware should watch for it and back off. Bench test on built boards.
- **Battery plug polarity.** The pin numbering was worked out from footprint
  drawings. Check it with a meter on a real Adafruit cell before the order.

## Fixed after an independent design review (17 Oct 2026)

A second engineer reviewed the circuit before this plan went to the owner.
Every finding was fixed:

| Finding | Fix |
|---|---|
| A battery plugged in backwards was safe only when nothing else powered the board | The reverse-battery switch now takes its gate from the cell's own minus terminal, so it stays off whatever powers the board |
| A 12 V solar panel (about 21 V open-circuit) would have overheated the solar and drone surge clamps | Both inputs now have a reverse-blocking diode and the same 22 V clamp as USB. A 4.7 V clamp on each eFuse's enable pin keeps that pin inside its rating at 20 V. |
| A 3 W burst on a worn cell could make the charger let go of the system rail and reset the board | An ideal diode now holds the system rail on the cell |
| The charge LED was on the fault pin | Moved to the "charging" pin |
| The USB cut-off (5.8 V) was at the processor's absolute limit | Lowered to 5.4 V |
| The charger's own temperature window is 0–60 °C, and above about 67 °C a hot cell can look like a held reset button | The processor can now stop charging. Firmware holds charging to 0–45 °C and keeps that reset timer from running. |
| The radio clock was rated only to −30 °C | Changed to the −40 °C version |
| The power mux drew 0.3 mA whenever the board was on | It now runs only while the amplifier is enabled |
| No-antenna safety at 3 W is not covered by the datasheets | Firmware ceiling is 3.6 V on the amplifier (about 34 dBm, 2.5 W), the voltage at which Qorvo rates it for a missing antenna. 35 dBm is an opt-in setting. |
| The first resistor of the 15.9 dB pad would run at 92 % of its rating at the radio's maximum drive | Firmware caps the radio chip at +20 dBm, which puts it at 58 % |
| An unprotected battery-voltage pin on the expansion header | Removed (now ground) |

## Owner decisions (18 Oct 2026)

1. **Keep 3 W.** One board, with power set in firmware or from the
   Meshtastic app at any time:
   - 1 W whenever the region is US;
   - up to 2.5 W in licensed mode;
   - 3 W opt-in for a known-good antenna.

   Going between 1 W and 3 W is a setting change, never a hardware change.
2. **Receive amp on by default** (see *Power*); off is a firmware battery
   saver.
3. **Buttons and JST connectors rated to −25 °C are accepted for now.**
   Revisit if a contract asks for −40 °C.
4. **3 W confirmed, at about $58 of parts per board** (a 1 W-only board
   would be about $40). Now about $68 after the 19 Oct changes.
5. **Above 1 W:** the owner gets a ham licence before taking boards into
   the field. Until then the boards stay in US mode, which caps them at 1 W.
   The hardware does not change.
6. **RF test gear:** to be bought later. Until it is, the test boards run
   with the makers' reference values, untuned. They should work, but output
   power, harmonics and the firmware gain table stay unproven, and nothing
   above 1 W is used until they are measured.
7. **Battery: 1-cell LiPo, 1,800 mAh or larger**, which handles the 3 W
   bursts.
8. **The node is on, on the mesh and charging while the drone carries it**
   (the 14 Oct Cairn decision; Notion's 16 Sep note said off until release).

## Owner decisions (19 Oct 2026)

1. **Keep 3 W and fix the heat:** a 10 × 10 mm gap pad from under the
   amplifier to a metal enclosure wall, nine filled vias under its paddle.
2. **6 layers.**
3. **New parts:** the designer's choice where the simulations needed them
   (60 V current limiters on solar and drone, the Alps SKRP buttons rated
   −40 °C, the LFCG-1000+ filter, the missing-antenna detector).
4. **Charging at 300 mA.**
5. Layout approved (18 Oct), with standard (Adafruit/SparkFun) battery
   polarity.

Still open:

- **Battery polarity:** check the plug on a real Adafruit cell with a meter
  before the order (the footprint drawing says pad 1 = +).

## After approval

1. Lay out the board: RF chain first, then power, then the processor.
2. Run every simulation on the routed board (`TESTS.md`).
3. Write the Meshtastic board variant: pins, the amplifier gain table, and
   1 W in US mode.
4. Order 5 test boards. Bring them up and tune the RF on a network analyser.
   Measure current, range against a RAK, heat, and output into a missing
   antenna.
