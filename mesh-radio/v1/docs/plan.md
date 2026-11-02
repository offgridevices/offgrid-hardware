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
                       └───── GPS plug, display / I2C plug        harmonic filter
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

- **251 assembled parts, on both sides** (257 in the circuit: the 6 test
  pads are not assembled). About half of them are the amplifier, filters
  and power protection the RAK does not have.
- **70 × 25.4 mm** (owner, 2 Nov). The Heltec V4 is 51.7 mm long. 58 mm
  placed but would not route; 62 mm (1 Nov) routed to about a dozen open
  connections round the two radio chips and the USB corner. 70 mm also
  makes room for an M3 hole in every corner and for every cable plug on
  one long edge (below).
- **Mounting: four M3 holes**, one per corner (3.2 mm, plated, on ground,
  6.4 mm ring), with a 7 mm keep-out for a washer or a hex standoff.
- **Every cable leaves the upper long edge**, the plugs all on the bottom
  side with their openings at that edge, left to right: solar (JST-SH 2),
  battery (JST-PH 2), drone (JST-GH 6), GPS (JST-SH 6), display / I2C
  (JST-SH 10: GND, 3V3, SDA, SCL, SCK, MOSI, CS, DC, RST, backlight, every
  signal on an ESD array). The USB-C stays on the short edge and the
  antenna U.FL by the antenna end.
- **6-layer board** (owner, 19 Oct), JLCPCB stackup JLC06161H-2116B:
  layer 2 is ground, kept solid under every radio line and the Bluetooth
  antenna; elsewhere it, and layers 3, 4 and 5, carry signals with ground
  filled round them (20 Oct: with fewer signal layers too many connections
  had no way through). JLCPCB fills and caps
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

## Owner decisions (2 Nov 2026)

1. **Board 70 mm long** (was 62 mm): 62 mm left about a dozen connections
   with no way through.
2. **Four M3 mounting holes**, one per corner.
3. **Controls all on top, facing up:** the user and reset buttons side by
   side on the lower long edge, 8.4 mm apart with a clear ring round each,
   and the power switch now a vertical slide switch (C&K JS202011JCQN,
   LCSC C221665, lever up) by the upper-left hole. Each is framed and named
   in the silk (USER, RESET, POWER). The switch's 3D model is a box with
   approximate heights: check a real part before cutting an enclosure.
4. **The LoRa antenna jack stays where it is:** at the end of the transmit
   chain, the electrically best spot (a jack at the back edge would need
   the whole antenna section rebuilt, or a longer line costing ~0.2 dB).
5. **Every cable plug on one long edge.** The 2 x 10 expansion header has
   no room on either long edge (the two antenna circuits take most of
   both), so it gives way to a 10-pin JST-SH display / I2C plug on the
   cable edge. The four spare processor pins and the display's MISO are
   no longer connected (`firmware/variant/variant.h`).
6. **Power study** (`sim/power/`): re-doing the layout would save under
   1 %; the listening current is in the parts that listen. Two firmware
   fixes are in (amplifier supply off between messages, drone port opened
   only when something is plugged in): about 12.7 to 11.9 mA, no range
   lost. The rest is for later (next section).

## Future: lower listening power (2 Nov 2026, not for this board)

The owner asked for these to be written down and looked at later, not now.
Numbers from `sim/power/` (datasheet arithmetic, 3.7 V cell, no traffic).

| Step | Listening | Cost | Work |
|---|---|---|---|
| Today, with the 2 Nov firmware fixes | about 11.9 mA | - | done |
| Radio chip on low-power gain while the receive amp is on | about 11.3 mA | about 0.3-0.5 dB of hearing | a setting |
| Listen in short windows (SX1262 RxDutyCycle: about 91 ms listening, 49 ms asleep, still catching every LongFast preamble) | about 9.4 mA | a busy mesh collides a little more | Meshtastic core change, bench tests for lost packets |
| Receive amp follows those windows | **about 8.0 mA**, under the 10 mA target with full range | same | **board change**, below |

**The board change.** Today the receive amp's enable (LNA_EN) is a
processor pin, so the amp stays on while the radio sleeps between windows.
One small logic chip (a TI or Nexperia 74LVC1G-family gate, SC-70) would
switch it with the radio instead:

    LNA on = DIO3 (the radio's clock supply: on only while it is awake)
             AND NOT DIO2 (high while transmitting)
             AND LNA_EN (the firmware's own on/off, kept for battery saver)

The DIO2 term is needed: with the amp in gain while transmitting, the
radio chip's own input would be overdriven. DIO3 is 2.2 V here, above the
amp's 1.0 V control threshold, and the amp settles in 3-6 µs. Worth doing
only once the windowed-listening firmware exists and is proven.

**Other ideas from the study, smaller:**

- A lower-current receive amp: none from an allowed maker matches the
  BGA7L1BN6's noise at 915 MHz for less current. The NXP BGU7003W can run
  at about 3 mA (2 mA saved, under 0.3 dB lost) but needs its own
  2.2-2.85 V rail and has no bypass.
- Turn the receive amp off automatically when the band is noisy (more than
  about 10 dB above thermal noise, read with the radio's RSSI): there it buys
  little hearing. A firmware feature.
- Bluetooth: "stop advertising after N minutes" saves about 0.1 mA.
- Switched-off leaks of about 10 µA straight across the cell (two 1 M
  resistors and the 4.7 V clamp on the battery polarity check), and the
  bypass diode's leakage when hot (about 100 µA at 75 °C): bench-measure first.

## Owner decisions (1 Nov 2026)

1. **Board 62 mm long** (was 58 mm), keeping every feature, the expansion
   header included.
2. **Keep 3 W.** Above 1 W each transmission starts at 1 W or less (the
   amplifier at 2.25 V, under its 2.7 V data-sheet minimum, for about
   0.75 ms), checks the antenna, then rises. Verify the 2.25 V start on the
   first built boards before using more than 1 W.
3. **Standard 2-pin battery plug.** The one rare reversed-battery sequence
   (a good cell pulled out under external power, then a reversed one) is
   accepted as it is: it passes in simulation and firmware clears it; test
   it on the bench.

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
