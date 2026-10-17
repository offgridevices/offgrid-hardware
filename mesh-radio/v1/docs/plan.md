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

| State | From the battery | vs RAK WisBlock (owner-measured) |
|---|---|---|
| Listening, Bluetooth off, LNA off | **about 7–9 mA** | about 20 mA |
| Listening, LNA on (best range) | **about 12–14 mA** | about 20 mA |
| Bluetooth connected to the phone | about +0.2–1 mA | |
| Transmitting at 1 W (30 dBm) | about 1.0 A while sending | about 0.12 A at 0.16 W |
| Transmitting at 2.5 W (34 dBm) | about 2.0 A while sending | |
| Transmitting at 3 W (35 dBm) | about 2.3 A while sending | |
| Switched off | about 20–30 µA | |

A message at LongFast lasts about 1 second on air. At 1 W that costs about
0.3 mAh per message, so the battery is spent listening, not sending.

**The 10 mA listening target (P1) is met only with the LNA off.** With it on,
listening rises to about 13 mA. That is still below the RAK, and it buys
about 4.5 dB of hearing, worth about as much range as 3 W of transmit power.
Both modes are a firmware setting; see question 1.

## Cost

**Parts: about $76 per board at 10 boards and $58 at 100, at DigiKey
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

- **About 238 assembled parts, on both sides.** About half of them are the
  amplifier, filters and power protection the RAK does not have.
- **Size target: 25.4 mm wide, length set at layout.** The Heltec V4 is
  51.7 mm long. The amplifier stage adds about 10–12 mm of length, so expect
  roughly 25 × 60 mm. Layout will make it as short as it can.
- **4-layer board.** The nRF52840 package needs filled vias in its pads,
  which JLCPCB charges extra for on 4 layers. Get quotes for both.
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

## Questions for the owner

1. **Listening mode:** LNA on (about 13 mA, about 4.5 dB better hearing) or
   off (about 8 mA) as the default? Both are a firmware setting.
2. **Cost vs 3 W:** keep 3 W (about $58 of parts at 100), or make v1 a
   1 W-only board (about $40)?
3. **Battery polarity:** check the battery plug on a real Adafruit cell with
   a meter before the order (the footprint drawing says pad 1 = +).
4. **Mechanical parts rated to −25 °C**, not −40 °C (buttons, JST
   connectors). Acceptable for Cairn's hot environment?

## After approval

1. Lay out the board: RF chain first, then power, then the processor.
2. Run every simulation on the routed board (`TESTS.md`).
3. Write the Meshtastic board variant: pins, the amplifier gain table, and
   1 W in US mode.
4. Order 5 test boards. Bring them up and tune the RF on a network analyser.
   Measure current, range against a RAK, heat, and output into a missing
   antenna.
