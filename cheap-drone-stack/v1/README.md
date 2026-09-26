# Cheap Drone stack v1: flight controller + 4-in-1 ESC for the Phase 1 3" quad

Two 33.8 × 33.8 mm boards on the 25.5 mm (M3, or M2 with grommets) pattern.
Together they replace the GEPRC TAKER G4 AIO that Phase 1 flew. They are
drawn for the Phase 1 hardware:

| | Phase 1 part | What this stack does for it |
|---|---|---|
| Motors | iFlight XING2 1404 3800KV (9N12P: 12 magnet poles) | Four AM32 ESCs, 30 V half-bridges, bidirectional DShot for the RPM filter |
| Props | Gemfan 3016 | – |
| Battery | OVONIC 4S 650 mAh, XT30 | 4S only (see [Limits](#limits)); battery pads on the ESC's rear edge |
| Receiver | RadioMaster RP3 ELRS (CRSF, 5 V) | 5 V / G / R2 / T2 pads on the FC's front-left edge, CRSF on UART2 by default |
| Frame | 25.5 mm mount, USB-C out the left side, lead out the back | Same hole pattern, board size, and USB and lead directions as the TAKER G4 |

**Status: designed, not yet built.** Both boards pass KiCad DRC with **zero
errors, zero warnings and zero unconnected items** against JLCPCB's rules
(FC 4 layers, ESC 6 layers). The routed copper was checked pad by pad
against the circuit in `src/circuit.py`, and
[`VERIFICATION.md`](VERIFICATION.md) checks the design against sources other
than itself: the pin maps against KiCad's STM32 libraries and the Betaflight
and AM32 sources, the regulator and divider arithmetic, the fab outputs, and
the silkscreen. **No board has been made or measured yet.** Order the
minimum quantity, assemble one stack, and go through the
[bring-up](#bring-up) steps before building more.

![flight controller](fc/images/cheapdrone-fc-iso.png)

---

## What is on each board

**Flight controller**, `fc/`: all parts on the top side, 53 parts, 4 layers.

- **MCU:** STM32G473CEU6 (170 MHz Cortex-M4). Same MCU and pin map as the
  TAKER G4. Flash the board's own `CHEAPDRONE_G473` build from `firmware/`:
  stock `TAKERG4AIO` has no BMI270 driver.
- **Gyro:** Bosch BMI270 on SPI1, on its own filtered 3.3 V supply. The
  same pads take a TDK ICM-42688-P. The two chips' axes differ by 90° on the
  same pads, so `firmware/` has one Betaflight build for each chip
  (`CW270` for the BMI270, `CW0` for the ICM). The wrong build shows no gyro
  and will not arm. Board rotation is 0/0/0 with either chip.
- **Blackbox:** 16 MB SPI NOR flash on SPI2: Puya PY25Q128HA in the BOM, or a
  Winbond W25Q128 on the same pads. Betaflight knows both.
- **Power:** 5 V 2 A buck (LMR51420, 36 V input) from the battery, and a
  3.3 V LDO. USB-C alone powers the board for setup.
- **Pads:**
  - UART2 for the receiver.
  - UART4 and UART1 spare (VTX, GPS).
  - 5 V and 3.3 V outputs, a VBAT output for a VTX.
  - LED strip, and buzzer (low-side switched): the left-rear column reads
    `G`, `5V`, `BZ-`, `LED`. The buzzer goes between `5V` (its +) and
    `BZ-`.
  - SWD.
- **Also:** voltage divider for battery monitoring, current input from the
  ESC lead, status LED, and a DFU **BOOT** button.

**4-in-1 ESC**, `esc/`: parts on both sides, 6 layers, 4S.

- **Per motor:**
  - STM32F051K6U6 running AM32 (target `FD6288_F051`).
  - JSM6288Q 3-phase gate driver (pin-for-pin with FD6288Q).
  - Three AON7934 dual N-MOSFET half-bridges (30 V).
  - Back-EMF dividers and a virtual-neutral network.
  - Bulk capacitors directly under the FETs.
- **Layout:**
  - Each channel owns one board edge, and its three half-bridges face their
    motor pads. Each gate driver sits behind the middle of its FET row, and
    each MCU sits in its own corner.
  - Every chip is on the bottom: the four MCUs, the four gate drivers, the
    twelve FETs and the buck. The four channels are one drawing turned by
    90°. A channel built on the other side would come out mirrored, and its
    MCU would land in a neighbour's corner.
  - The top carries the passives that need not sit against a chip:
    back-EMF dividers, bootstrap diodes and part of the decoupling. The top
    also holds all twelve motor pads, the battery pads and the stack
    connector, so everything can be soldered with the stack assembled.
  - Six layers: signals on the outer layers and on In2 and In3, a solid
    ground plane on In1 and a solid battery plane on In4. Every FET pin
    reaches its plane through a column of vias beside the pin.
  - Vias in pads: the small parts, the chips' ground pads and the FET gates
    connect through vias inside their own pads. QFN pins that change layer
    escape through a via just outside the pin. JLCPCB fills and caps every
    via free on 6-layer boards (see [Ordering](#ordering)).
- **Also:**
  - 3.3 V buck for the four MCUs.
  - Shared battery-voltage divider for AM32.
  - SWD pads for each MCU.
  - Vertical 8-pin JST-SH to the FC.

**Stack lead:** JST-SH 1.0 mm, 8 pins, pin 1 to pin 1. This is the FPV
standard pinout: `1 VBAT, 2 GND, 3 CUR, 4 TLM, 5 M1, 6 M2, 7 M3, 8 M4`.

**Motor numbering:** Betaflight's Quad X. Motor 1 is rear-right, 2
front-right, 3 rear-left and 4 front-left. On the ESC, each motor's number
is printed beside its three pads. The order of the three wires within
a motor does not matter: set the direction in ESC-configurator.

---

## Ordering

Everything to upload is in `fc/production/` and `esc/production/`. You do
not need KiCad or Python.

### Bare boards (JLCPCB or PCBWay)

Upload `cheapdrone-fc-gerbers.zip` and `cheapdrone-esc-gerbers.zip` as two
separate orders. They differ only in layer count:

| Setting | Value |
|---|---|
| Layers | **FC 4, ESC 6** |
| Dimensions | 33.8 × 33.8 mm (read from the outline) |
| Thickness | 1.6 mm |
| Material | FR-4, TG155 or better |
| Solder mask | **Black** (JLCPCB) / **Matte black** (PCBWay): the brand's Pitch ground |
| Silkscreen | **White**: the brand's Bone |
| Surface finish | **ENIG** (the QFN and LGA parts need a flat finish; HASL is a gamble on the 0.5 mm pitch and the gyro) |
| Outer copper | 1 oz |
| Inner copper | **1 oz for the ESC** (its In1/In4 planes carry the motor current); 0.5 oz is fine for the FC |
| Via covering | FC: tented (the default). **ESC: "Epoxy Filled & Capped" (POFV)**: the ESC has vias in pads. JLCPCB makes POFV the free default on 6–20 layer boards. At PCBWay, ask for via-in-pad filled and capped, which is a paid option there |
| Min track / spacing | 0.1 / 0.1 mm (JLCPCB standard multilayer capability) |
| Min via | FC 0.45 mm pad / 0.25 mm drill. ESC 0.35 mm / 0.2 mm (JLCPCB's 6-layer standard allows 0.25 / 0.15); vias in pads are 0.45 / 0.3. Every via keeps 0.45 mm from the unplated mounting holes, which are drilled after the via fill, as JLC's POFV rules ask |
| Stackup | The fab's standard 1.6 mm build: JLC04161H-7628 for the FC; any standard 6-layer 1.6 mm for the ESC (no impedance control needed) |
| Order number | "Remove" or "specify location". The boards have no free spot reserved for it. |

### Assembly (JLCPCB PCBA)

| | FC | ESC |
|---|---|---|
| Sides | Top only | **Both sides** |
| BOM | `cheapdrone-fc-bom-jlcpcb.csv` | `cheapdrone-esc-bom-jlcpcb.csv` |
| CPL (pick & place) | `cheapdrone-fc-cpl-jlcpcb.csv` | `cheapdrone-esc-cpl-jlcpcb.csv` |

Every part has an LCSC number. All were in stock at JLCPCB when the boards
were designed. Most passives are "basic" parts; the ICs, connectors, FETs
and a few values are "extended".

- **Placement preview:** in JLCPCB's placement preview, check pin 1 of the
  QFN parts and the orientation of the two SH connectors before paying.
  Rotations follow each part's JLCPCB library footprint, so they should need
  no changes.
- **PCBWay:** use `*-bom-pcbway.csv`. It lists the manufacturer part numbers
  and the LCSC numbers, together with the same CPL.
- **Not assembled:** the battery lead, the 470 µF capacitor, motor wires,
  the receiver and the stack cable. These are hand-soldered or plugged in.

### Also needed (not on the boards)

- **Bulk capacitor for the ESC:** 470 µF 35 V low-ESR electrolytic, e.g.
  Panasonic EEU-FR1V471 or any "FPV ESC capacitor". Solder it across BAT+
  and BAT- together with the XT30 lead. **Do not fly without it.** It
  absorbs the voltage spikes that otherwise kill the FETs.
- **XT30 pigtail:** 18 AWG.
- **Stack cable:** 8-pin JST-SH, pin 1 to pin 1. Most 4-in-1 ESCs come with
  one. Check it with a multimeter: VBAT (pin 1) must go to pin 1 at both ends.
- **ST-Link V2** (or clone) to flash the ESC bootloaders once.

### Ordering in volume

The boards use no exotic parts. Every part is a stocked JLCPCB/LCSC
catalogue part, most passives are JLC "basic" parts, and each part that
matters has a second source that fits the same pads.

**Panels.** JLCPCB's Standard assembly, which is the only JLC service that
places both sides and takes large quantities, needs a board or panel of at
least 70 × 70 mm. `make.py` therefore also writes a **3 × 2 panel** of each
board to `production/panel/`: Gerbers, BOM and CPL, ready to upload in
place of the single-board files. The panel is 105.4 × 83.6 mm with six
boards, 5 mm rails, mouse-bite tabs, three fiducials per side and four 2 mm
tooling holes. The tabs sit only where no part or copper is near the edge.
The rail reads `JLCJLCJLCJLC`, so JLC prints its order number there rather
than on a board. After depanelling, sand the tab stubs flush (up to 0.25 mm).
`make.py` checks that every copy on the panel is the single board exactly:
Gerbers, BOM and CPL, every copy. It also checks that the panel's DRC
result equals six copies of the board's own.

![FC panel](fc/images/cheapdrone-fc-panel-top.png)

**Second sources.** These fit the same pads without any copper change:

| Part | In the BOM | Drop-in alternative | What changes |
|---|---|---|---|
| Gyro | Bosch BMI270 (C2836813) | TDK ICM-42688-P (C1850418) | Flash the `_ICM` Betaflight image |
| Blackbox flash | Puya PY25Q128HA (C18208279) | Winbond W25Q128JVPIQ (C190862) | Nothing |
| FC MCU | STM32G473CEU6 (C1342773) | STM32G474CEU6 (C1235412), a superset in the same package | Nothing: Betaflight's G47x target is built for the G474 |
| BEC inductor | cjiang FXL0530-4R7-M (C177246) | Sunlord MWSA0503S-4R7MT (C408410) | Nothing |
| ESC MCU | STM32F051K6U6 (C81451) | Artery AT32F421K8U7 (C2965611), **untested** | AM32 image and flashing tool, see `firmware/README.md` |
| Gate driver | JSMSEMI JSM6288Q (C19077370) | DOINGTER DO6288Q (C42386238), YLPTEC YC6288Q (C54157432) | Nothing; build one ESC first |
| Bootstrap diode | JSCJ RB521S-30 (C8523) | onsemi RB521S30T1G (C145179) | Nothing |
| 10 µF 50 V 0805 | Samsung CL21A106KBYQNNE (C2932476) | Murata GRM21BR61H106KE43L (C440198) | Nothing |

**Component cost** (JLC catalogue prices on 26 Sep 2026, before assembly
fees and bare boards):

| | 1 set | 100 sets | 1,000 sets |
|---|---|---|---|
| FC | $15.62 | $9.79 | $9.13 |
| ESC | $16.91 | $10.73 | $9.51 |
| **Stack** | **$32.53** | **$20.52** | **$18.64** |
| Stack with AT32F421 ESC MCUs | | | about $16.1 |

- **What limits a large run is stock, not price.** On 26 Sep 2026, JLC's
  866 STM32F051K6U6 were enough for 216 ESCs. That is why the AT32F421 path
  exists: build and test one AT32 ESC before a big order. The next limit is
  the STM32G473 (1,690 FCs). Reserve it, or buy it in, before committing.
- **Assembly fees at JLC:** Standard assembly has a setup, stencil and
  $1.53-per-unique-part loading fee per order: about $78 for the FC and
  $100 for the ESC. On top of that is $0.0016 per solder joint: 208 joints
  per FC and about 600 per ESC. At 1,000 sets this adds roughly $0.40 per
  FC and $0.90 per ESC.
- **Bare boards** (6-layer ESC, 4-layer FC, ENIG, black) were not priced
  here. Get a JLC or PCBWay quote for the panels at the volume you need.
- **Programming** is the one per-unit labour step. Each FC flashes over USB
  (hold BOOT, plug in). Each ESC needs four SWD sessions on its test pads.
  At volume, use a pogo-pin fixture on those pads, or the assembler's
  pre-programming service.

---

## Assembly

1. **FC to receiver:** receiver on the FC's front-left pads: `5V`, `G`,
   `R2` to the receiver's TX, `T2` to the receiver's RX.
2. **Flash the ESCs** while the ESC board is still bare: no battery lead,
   no capacitor, not stacked. See [`firmware/README.md`](firmware/README.md).
   The ST-Link's 3.3 V also reaches the battery net through the 3.3 V
   buck's body diode. With the 470 µF fitted it would have to charge that
   too.
3. **XT30 lead and capacitor:** onto the ESC's rear-left pads, `+` outer,
   `-` inner. The capacitor goes across the same two pads, observing its
   polarity.
4. **Motor wires:** each motor's three wires to the three pads beside its
   number.
5. **Stack:** ESC at the bottom, FC on top, both with the **Front arrow
   forward**. Fit the stack cable.

## Bring-up

Do these in order. Each step catches a fault before it can damage the next.

1. **No power:**
   - Measure BAT+ to BAT- on the ESC. It must not read as a short: the
     meter should climb past a few kΩ as the capacitors charge.
   - Measure the FC's `5V` and `3V3` pads to `G` in the same way.
2. **FC on USB only:**
   - The red power LED lights.
   - Flash Betaflight: hold **BOOT**, plug in USB, and follow
     `firmware/README.md`.
   - Paste `firmware/betaflight/cli-setup.txt` into the CLI.
3. **Orientation, before anything spins.** Phase 1 lost three crashes to a
   wrong board alignment, so check it on the bench, not in the air. In the
   Setup tab:
   - Nose down, and the model goes nose down.
   - Right side down, and the model rolls right.
   - Yaw right, and the model yaws right.
   Then calibrate the accelerometer on a level surface: `acc_calibration`
   should come out as small numbers, not about -4000 (see the Phase 1
   notes).
4. **ESC on a current-limited supply:** 15 V, 0.3 A limit, or use a smoke
   stopper on the battery.
   - It should idle at a few tens of mA.
   - Check the 3.3 V buck at the `3V3` test pad.
5. **Stack plus battery, props off:**
   - ESC-configurator via Betaflight passthrough must see four AM32 ESCs.
     Set KV 3800 and 12 poles.
   - In Betaflight's Motors tab, spin each motor slowly. Confirm the order
     is 1 rear-right, 2 front-right, 3 rear-left, 4 front-left, and fix the
     directions in ESC-configurator.
   - Check the RPM readout. Bidirectional DShot working means the ESC
     telemetry path is sound.
6. **Heat, props on, before the first real flight.** Tape a thermocouple
   to the hottest FET package (the channel with the longest run to the
   battery pads). Run 10 s, then 30 s, at full throttle with the quad
   held down. Stop at 100 °C. This is the ESC's only current rating
   until it has been measured: see [Limits](#limits).
7. **Props on:** hover test on a leash or in a net first.

## Limits

- **4S only.**
  - Each gate driver runs straight from the pack through 10 Ω. That puts
    12–16.8 V on the FETs' gates, which is inside the driver's range and
    the AON7934's ±20 V gate rating.
  - 3S (9–12.6 V) is near the driver's undervoltage lockout: do not.
  - 5S/6S exceed the FETs' 30 V rating: do not.
- **Current.** The ESC is built for the 1404 3800KV on 4S with 3" props;
  it is not a 35 A-per-motor racing ESC. Its current rating has not been
  measured. From the AON7934 datasheet's maximum on-resistance, conduction
  loss is about 0.45 W per motor at 5 A, 1.8 W at 10 A and 4 W at 15 A (the
  arithmetic is in `VERIFICATION.md`): check FET temperatures during
  bring-up before long full-throttle runs. The ESC has no current sensor.
  Betaflight shows voltage but reports current as 0; `cli-setup.txt` sets
  `current_meter = NONE`.
- **Heat.** All twelve FETs are on the ESC's underside, facing the frame,
  away from the FC. They dump heat into the ground and battery planes.
  Keep the stack in the airflow and do not run full throttle on the bench.
  The XING2 1404's published maximum is 15.8 A for 60 s. At that current
  each motor's FETs dissipate about 4 W, which suits full-throttle bursts
  of a few seconds, not a full minute without airflow. Bring-up step 6
  measures it. If it runs hot, order the ESC with **2 oz inner copper**
  (the In1/In4 planes carry all four motors' current) before changing parts.
- **USB power back-feeds the battery net.** On USB alone, about 3.9 V
  reaches VBAT through the FC's 5 V buck (its high-side FET's body diode).
  That powers the `VBAT` pad and the stack lead at a level where the ESC's
  buck may start and stop. It does no harm, but unplug the stack lead
  and the VTX while configuring on USB. Betaflight will show a "1S"
  battery.
- **VTX power.** The stack lead's JST-SH contacts are rated 1 A, and they
  already carry the FC's own BEC current. Wire a VTX that draws more than
  about 300 mA (any digital or 800 mW analog VTX) to the ESC's battery
  pads, not to the FC's `VBAT` pad.
- **Dead time.** AM32's `FD6288_F051` inserts about 0.94 µs, about five
  times what the gate driver needs. That is safe, and costs about 0.3 W per
  motor at 8 A in body-diode conduction. A shorter value needs a custom
  AM32 build, and should be checked on a scope first.

---

## The look

Both boards follow the OffGrid brand hand-off (v3.2). Dark is the brand's
default expression, so the boards are **Pitch** (black solder mask) with
**Bone** type (white silkscreen) and ENIG gold pads.

- The FC's bottom carries the horizontal lockup: the Beacon Ring and
  "OffGrid" in Instrument Sans 600, at the lockup SVG's own proportions.
  Under it sit the company line and what the board is. The top carries the
  bare mark.
- Pad names, part codes and numerals are JetBrains Mono 500, uppercase and
  tracked 0.06 em. Words ("Boot", "Front") are Instrument Sans 500. Both
  follow `tokens.json`.
- Everything is drawn as filled outlines from the fonts in `fonts/` (SIL
  OFL), not KiCad's stroke font. The Gerbers carry the exact letterforms,
  and nobody needs the fonts installed.
- No Ember: silkscreen prints one colour, and the brand's rule is one accent
  or none.

**Black or white, and heat:** mask colour makes almost no difference to how
hot the board runs. Solder mask of any colour emits infrared about equally
well, and the heat leaves through the copper planes and the airflow. White
only helps under direct sun. Black is the brand's default, so both boards
are specified black.

## Why two boards, not one

An all-in-one board (FC and four ESCs on one 33.8 mm square) was checked
first. The parts alone cover about 1,080 mm², over half of both sides.
Every channel would then share its patch of board with the flight
controller's MCU, gyro and flash, on at least six layers. The gyro would
also sit next to the switching FETs. Two boards keep the gyro away from the
power stage and let either board be replaced alone.

---

## Files

```
v1/
  README.md               this file
  VERIFICATION.md         every design check that can be made without
                          hardware, with its result (src/verify.py)
  fc/                     flight controller
    cheapdrone-fc.kicad_pcb / .kicad_pro / .kicad_dru   open in KiCad 10
    production/           gerbers zip, BOM + CPL (JLCPCB), BOM (PCBWay),
                          netlist, assembly drawing (PDF)
      panel/              the same for a 3 x 2 panel, for volume assembly
    images/               renders
  esc/                    4-in-1 ESC, same layout
  mechanical/             STEP models of both boards (zipped), for frame CAD
  firmware/               Betaflight targets + hex (one per gyro chip), AM32
                          bootloader + firmware (STM32F051, and AT32F421
                          untested), flashing scripts, CLI setup
  aio.pretty/ aio.3dshapes/   footprints and 3D models (from JLCPCB/EasyEDA's
                          own library entries for the exact LCSC parts)
  fonts/                  Instrument Sans and JetBrains Mono (SIL OFL), for
                          the silkscreen
  src/                    the design, as Python (see below)
  requirements.txt
```

## How it is made (and how to change it)

The design is the Python in `src/`:

| File | What it holds |
|---|---|
| `circuit.py` | The schematic: every part and every connection, pin by pin, with the reasons. |
| `parts.py` | Every orderable part, with its LCSC number, MPN and footprint. |
| `footprints.py` | Builds `aio.pretty` from the JLCPCB/EasyEDA library entries. |
| `fc_layout.py`, `esc_layout.py` | Placement, power copper, planes and silkscreen. The ESC is one motor channel written once and stamped onto four edges. |
| `route.py`, `fanout.py`, `finish.py` | Plane fan-out and escape vias, then Freerouting for the signal routing, then an in-house maze router with rip-up to finish the last connections. |
| `esc_fixes.py` | The ESC's last connection (motor 1's FET C low-side gate), which both routers left sealed at both ends: two written-down, deterministic edits, applied by the pipeline and checked by its DRC. |
| `cleanup.py`, `pofv.py` | ESC clean-up after routing: unused escape vias and stubs come out one at a time, each removal kept only if KiCad's DRC agrees; vias move off the POFV hole spacing if needed. |
| `pipeline.py` | The order the above run in for `--reroute`. |
| `artwork.py` | Silkscreen placement: labels go only where they touch no pad, hole, part body or other label. |
| `brand.py` | The OffGrid mark, lockup and type as outlines, from the brand hand-off's numbers. |
| `fab.py` | Gerbers, drills, BOM, CPL, netlist, assembly PDF, renders, STEP. |
| `panel.py` | The 3 × 2 production panel (KiKit), checked copy by copy against the single board. |
| `make.py` | Runs it all with gates. |
| `verify.py` | Writes `VERIFICATION.md`. |

`python3 make.py` rebuilds every output from the committed `.kicad_pcb`
files and fails unless each board has zero DRC errors and zero unconnected
items, the copper matches `circuit.py` pad for pad, and every assembled part
is in the BOM and the CPL. `python3 make.py --reroute` places and routes both
boards from scratch first. A reroute must pass the same gates, but it does
not reproduce the committed copper: every fresh build gives the board's
items new IDs, which changes the order the router sees them in. On the ESC,
a reroute also leaves a connection or two for someone to finish, the way
`esc_fixes.py` finished the committed board's last one, so it can stop at
the DRC gate. The committed `.kicad_pcb` files are the reference.

The tools: KiCad 10 (`pcbnew` Python module and `kicad-cli`), Freerouting 1.9
(Java, headless via `xvfb-run`), KiKit 1.8 for the panel, and Python 3.12
with the packages in `requirements.txt`.
