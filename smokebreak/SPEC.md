# SmokeBreak: a smoke stopper that checks before it powers

**Status: spec only.** Nothing is designed or built yet. This document is
what the schematic and the board will be built against. Research behind it
is in [`docs/research/market-and-complaints.md`](docs/research/market-and-complaints.md).
Name chosen by the owner, 10 Oct 2026; trademark search pending.

![SmokeBreak Arm](design/arm/hero.png)

*The chosen design, Arm (concept 10, refined in [`design/arm/`](design/arm/)). The arming screens are in [`ui/`](ui/).*

---

## 0. Decisions needed before we build

| # | Decision | Recommendation | Why it matters |
|---|---|---|---|
| D1 | Product name | **SmokeBreak** — decided (no FPV product of that name found, 10 Oct 2026) | Needs a USPTO class 9 search before any print run |
| D2 | Top of the voltage range | **14S (60.9 V LiHV)** — decided | 100 V switch parts, 64 V clamp (§9) |
| D3 | USB-C port | **Yes** — decided | Firmware updates, drone-memory export |
| D4 | Front panel | **The PCB is the front panel**, behind a clear cover | The silkscreen instructions are the product's UI and stay on brand |
| D5 | Price | **No target** — decided: "the best smoke stopper on the market" | Every part is picked for the result, not the cost (§12) |
| D6 | Form factor and industrial design | **Arm** (concept 10) — decided, 11 Oct 2026. Guarded toggle, dramatic arming screens | [`design/arm/`](design/arm/), [`ui/`](ui/); the other 19 concepts stay in [`concepts/`](concepts/) |

---

## 1. What it is

A box that sits between a LiPo and a drone on the bench. Plug both in and
press **Power**. Before any battery voltage reaches the drone, it:

1. **Probes the drone at 3 V** and finds dead shorts, half-shorts and
   **reversed leads** — without a battery's worth of current behind them.
2. **Charges the drone's capacitors slowly**, so there is no inrush and
   nothing to false-trip on.
2. **Turns the drone on** behind a tight electronic fuse, and tells you in
   words what it draws.

It also **remembers each drone** it has seen and warns when one draws more
than last time, or when its big capacitor has shrunk or gone.

One unit covers **1S whoops to 14S heavy-lift**.

## 2. What makes it different

Every smoke stopper today does one thing: apply full voltage and cut off
if current goes over 1 A or 2 A. Users are stuck choosing between false
trips (limit too low) and burnt parts (limit too high). SmokeBreak removes
that trade-off.

| What people complain about (ranked) | What SmokeBreak does |
|---|---|
| 1. False trips on healthy builds (inrush, ESC tones, digital VTX) | Soft pre-charge removes inrush entirely. Two-tier limit: a tight *average* limit plus a fast *peak* limit, so ESC tones pass and shorts don't |
| 2. False sense of security: green light, still smoked | 3 V probe finds the fault **before** battery voltage is applied; half-shorts (e.g. a failing 5 V regulator, ~20 Ω) are named and measured |
| 3. Can't spin motors through it | **25 A motor-test setting** (props off), 60 s window, with the peak fuse still armed |
| 4. Only 1 A / 2 A, set with solder pads | Six settings on a button (Auto, 1, 2, 5, 10, 25 A), changeable while on |
| 5. No 1S, nothing smart above 6S | **1S to 14S** in one unit. No smart competitor covers either end |
| 6. Confusing LEDs → "red meant good to go", burnt motor | A screen that says what happened in words, a status ring, beeps, and printed instructions on the face |
| 7. Dead on arrival, bare boards short on benches, leads rip off | Closed case, panel-mount battery connector, clamped drone lead, self-test at power-up |
| 8. XT30/XT60 only; won't reach a frame-mounted XT60 | XT60 and XT30 built in on both sides, flexible 10 cm drone leads, BT2.0 adapters in the box |
| Loved feature: the power button for binding | Kept and made a ritual: lift the guard, flick the switch. Pull the switch toward you and it does the ELRS three-power-cycle for you |

Three things no product on the market does today:

- **Checks before it powers** (3 V probe: short, reversed, half-short).
- **No inrush, so no false trips**, even with a tight limit.
- **Remembers each drone** and warns when its draw or capacitor changes.

---

## 3. Headline specifications

| | Value |
|---|---|
| Battery | **1S–14S** LiPo, LiHV, Li-ion: **3.5–60.9 V** |
| Survives | Reversed battery to −61 V; 80 V input transients |
| Pre-check | 3 V probe, ≤ 30 mA, before any battery voltage reaches the drone |
| Detects before power | Dead short (< 1 Ω), half-short (1–150 Ω), reversed drone lead, missing bulk capacitor |
| Pre-charge | Through pulse-rated resistors (≈ 2 Ω for 1–7S, ≈ 22 Ω for 8–14S), up to 5,000 µF in < 1 s |
| Trip settings | Auto · 1 · 2 · 5 · 10 · 25 A (25 A = motor test, 60 s, props off) |
| Peak (short) cut-off | ≤ 5 µs at 4 × the setting (comparator), plus the driver's own short trip (speed to confirm, §14) |
| Through-resistance | ≤ 20 mΩ battery-to-drone through the XT60s |
| Current rating | 15 A continuous, 25 A for 60 s |
| Measures | Battery V (±1 %), drone current 0–40 A; idle current ±10 mA + 2 % (0.05–3 A) |
| Remembers | 32 drones (capacitance, idle current, cell count) |
| Connectors | Battery side: XT60 + XT30 **male**, panel-mount. Drone side: XT60 + XT30 **female** on 10 cm leads. BT2.0 adapters in the box |
| USB-C | Firmware update, drone-memory export, powers the screen for reading memory without a battery |
| UI | Guarded toggle (lift, flick), Limit rocker, 1.9" colour screen, Beacon Ring light, beeper |
| Power use | ~30 mA on, < 30 µA off (battery still plugged in) |
| Size / weight | 96 × 58 × 18 mm body (guard 17 mm above it closed), ~150 g (bench tool; not for flying) |
| Price | No target: best on the market (§12) |

---

## 4. How it powers a drone

Every press of **Power** runs the whole sequence. Nothing is skipped.

```
 battery in ─► [0 Idle] ─Power─► [1 Probe 3 V] ─pass─► [2 Pre-charge] ─pass─► [3 On]
                                    │ fail                │ fail                 │ over limit
                                    ▼                     ▼                      ▼
                                 [Stopped: reason, value, what to check]  ◄───────┘
```

### Stage 0 — Idle

- Battery detected: screen shows voltage and cell count ("16.8 V · 4S").
- Battery reversed into the device: nothing conducts; screen and beeper
  say "Battery reversed" (powered through the protection diode).
- Cell count is a guess from voltage; it is shown, never acted on silently.

### Stage 1 — 3 V probe (~0.3 s)

The main switch stays **off**. A 3.0 V source drives the drone's power
lead through 1 kΩ, then through 100 Ω. The device reads the drone's
voltage at both currents and the rise time.

| Reading | Verdict |
|---|---|
| Stays below 50 mV at both currents | **Short** (resistance shown) |
| Settles between, scales with the source resistor | **Half-short**, resistance shown (e.g. "18 Ω") |
| Clamps at 0.9–1.6 V and barely moves between the two currents | **Reversed lead**: the ESC's FET body diodes are conducting |
| Charges up like a capacitor | **Pass.** The rise time gives the drone's capacitance |
| Capacitance under 100 µF on 4S or more | Pass, with a warning: "No big capacitor found" |

**Why reversed leads show up:** with the drone's red and black swapped,
the probe's current flows through each half-bridge's two body diodes in
series, so the voltage clamps at about two diode drops. A resistor scales
with current; a diode barely moves. That is why two probe currents are used.

**1S exception:** 1S flight controllers start running near 3 V, so they look
like a load. On 1S the half-short verdict is replaced by a softer limit
(below 10 Ω only) and the pre-charge stage does the rest.

### Stage 2 — Pre-charge at battery voltage (≤ 1 s)

- A small switch connects the drone through pulse-rated pre-charge
  resistors. The resistors, not a transistor, take the charging energy,
  so this holds at 14S. Two values, picked by cell count: about 2 Ω for
  1–7S and about 22 Ω for 8–14S. That is low enough for a drone whose
  digital VTX switches on part-way up (≈ 10–15 W) to still climb past
  75 % of battery voltage. Peak current is a few amps for a few
  milliseconds, against hundreds of amps when a battery is plugged in
  directly.
- The device watches the voltage and current all the way up.
- **Abort** if the drone's voltage stops rising below 75 % while current
  flows (a fault that appears only at higher voltage, e.g. a 5 V part on
  battery voltage), or the ramp takes over 1 s. The screen shows at what
  voltage and current it stopped.
- **Pass** above 75 % of battery voltage. The main switch then turns on
  over about 50 ms and closes the rest of the gap: no spark, and the
  remaining charge current stays well under the trip limit.

### Stage 3 — On

- Ring turns green. Screen shows live current.
- After 10 s, idle current is recorded and compared with this drone's last
  visit (§7).
- **Two-tier limit:**
  - **Average limit** = the setting, averaged over 200 ms. ESC start-up
    tones and VTX boot spikes pass.
  - **Peak limit** = 4 × the setting, cut off in ≤ 5 µs by a hardware
    comparator. Real shorts never get near the average.
  - **Short-circuit trip** in the driver chip, at a fixed threshold,
    whatever the firmware is doing.
- Trip reason is always shown: "Over 2 A for 0.2 s (peak 2.6 A)" or
  "Spike over 8 A".

---

## 5. Protection layers

From the fastest, independent of firmware, to the smartest:

1. **Short-circuit trip** in the high-side controller (TPS48111-Q1, ≤ 1.2 µs): a
   fixed hardware threshold. Works with the MCU halted.
2. **Programmable peak comparator:** MCU sets the threshold (4 × setting),
   the comparator pulls the switch off directly, ≤ 5 µs.
3. **Firmware average limit:** current sampled at ≥ 10 kHz, 200 ms window.
3. **Pre-charge abort:** voltage-versus-time watch during the ramp.
4. **3 V probe:** no battery current behind it at all.
5. **Back-to-back MOSFETs:** blocks current both ways when off; a reversed
   battery or a drone with its own battery plugged in cannot back-feed.
6. **Thermal:** NTC at the switch; firmware cuts at 100 °C and limits the
   25 A window. The pre-charge resistors have an energy budget per attempt.
8. **Guard closed = off, in hardware:** the guard sensor gates the
   controller's enable directly, so closing the guard cuts the drone even if
   the MCU has crashed.
9. **Self-test at power-up:** switch off-state leakage, probe source and
   comparator checked; a failed self-test locks the switch off and says so.

---

## 6. User interface — the Arm

Powering a drone is a deliberate act, like arming a switch in a cockpit:
**lift the guard, flick the switch**. Closing the guard always cuts power.
The screen makes it dramatic: hazard stripes when armed, a checklist that
ticks off line by line, a green flash when the drone goes live, and a
flashing red ABORT when something is wrong.

Demo: [`design/arm/arm-demo.mp4`](design/arm/arm-demo.mp4).
Screens: [`ui/storyboard.png`](ui/storyboard.png) (S01–S13) and
[`ui/arm-sequence.mp4`](ui/arm-sequence.mp4) (with beeps).

### The face (96 × 58 mm)

| Where | What |
|---|---|
| Left | Male XT60 + XT30 through the end. "Battery →" |
| Top left | **1.9" 320 × 170 colour IPS** under black glass |
| Bottom left | **Limit** rocker: a brushed-aluminium paddle, − and + |
| Right | **The guarded toggle**: translucent Ember guard over a metal toggle, the **Beacon Ring** lit round its bushing |
| Right end | Female XT60 + XT30 on 10 cm leads. "Drone →" |
| Back | USB-C |

### Controls

| Control | Action | Result |
|---|---|---|
| **Guard** | Lift | ARMED (S02): Ember stripes, beep, ring pulses Ember. Nothing is powered yet |
| **Toggle** | Flick away from you (On) | Full check (S03), pre-charge (S04), LIVE (S05–S06) |
| **Toggle** | Flick back (Off) | Drone off |
| **Toggle** | Pull toward you (spring-return) | **Bind**: three power cycles (S10) |
| **Guard** | Close | POWER CUT (S12). The guard cams the toggle back to Off and a magnet sensor cuts power in hardware, whatever the firmware is doing |
| **Limit** | − / + | AUTO, 1, 2, 5, 10, 25 A (S13). Going to 25 A asks "Props off?" (S11); press + again within 3 s |

- With the guard closed the toggle cannot be reached: nothing can be
  powered by accident, and a fault (S08, S09) is cleared by closing the
  guard, a physical reset.
- The toggle carries no drone current: it only signals the MCU.

### Status ring (round the toggle, lights the guard from inside)

| Colour | Meaning |
|---|---|
| Ember, dim | Safe, guard closed, battery present |
| Ember, pulsing | Armed |
| White | Checking |
| Green | Live, all good |
| Ember, steady | Live, but something changed since last time — look at the screen |
| Red, flashing | Abort — read the screen |
| Blue | Bind |

### Screens

| # | Screen | When |
|---|---|---|
| S01 | SAFE · battery voltage and cells · "Lift the guard to arm" | Guard closed |
| S02 | **ARMED** · hazard stripes · "Flick the switch up" | Guard lifted |
| S03 | CHECKING · 3 V probe, short, polarity, capacitor, ticking off | Switch on |
| S04 | Pre-charge bar and voltage climbing | |
| S05 | Green flash, the ring draws itself, **LIVE** | Main switch on |
| S06 | Live current in large figures, sparkline, limit, timer, "Same as last time" | |
| S07 | LIVE · LOOK · "Draws more than last time 0.42 → 0.71 A" | Drone memory warning |
| S08 | **ABORT** · Short circuit · 0.3 Ω · "The battery never reached the drone" | Probe found a short |
| S09 | **ABORT** · Leads reversed | Probe found reversed leads |
| S10 | BIND 1/3 … 3/3 | Toggle pulled |
| S11 | 25 A MOTOR TEST · "Props off?" | Limit + to 25 A |
| S12 | POWER CUT · "Guard closed · drone off" | Guard closed |
| S13 | Limit picker | Rocker |

Wording follows the noob-proof rule: say what happened and what to do.

### Beeps

Arm: rising chirp. Each check: a tick. Live: two-tone up. Warning: double
beep. Abort: alarm until the guard is closed. Power cut: falling tone.
Bind: a pip per cycle. Sounds are in the screen video.

### Printing and arrows (face)

Same rules as before: one brand arrow, sentence case, few words.
"Battery →" and "Drone →" at the ends, "Lift ↑" beside the guard, "On /
Off / Bind" beside the toggle, "Limit" and `AUTO 1 2 5 10 25 A` by the
rocker, lockup and "SmokeBreak" at the bottom, "ARM" moulded into the
guard. "Bench use only. Do not fly with this attached." on the base.

---

## 7. Drone memory

The 3 V probe measures each drone's capacitance before it is powered.
Capacitance (mostly the ESC's bulk capacitor) differs from drone to drone,
so together with cell count it identifies a drone without any setup.

- **Stored per drone:** capacitance, idle current at 10 s, cell count,
  date of last visit. 32 drones, oldest dropped first.
- **Match:** same cell count and capacitance within ±15 %. No match = new
  drone ("Drone 7, new").
- **Warnings** (ring turns Ember, screen explains):
  - Idle current up by more than 30 % and 0.1 A: dying regulator, VTX,
    water damage, a motor dragging.
  - Capacitance down by more than 30 %: capacitor broken off, dried or
    open. This kills ESCs on the next hard flight.
- **Auto limit** uses the memory: for a known drone, average limit =
  1.5 × its idle current, at least idle + 0.5 A, clamped 0.5–5 A. For a
  new drone: 1 A on 1S, 3 A on 2S and up.

---

## 8. Connectors

**Rule: male on the battery side, female on the drone side.** In FPV the
battery carries the female connector and the drone carries the male. The
device copies both, so it drops in between with nothing to adapt, and its
live output is always the female side, whose contacts are recessed.

| Side | Built in | Gender | Why |
|---|---|---|---|
| Battery in (left end) | XT60 + XT30, panel-mounted (Amass XT60PW / XT30PW class) | **Male** | Mates the battery's female. Mounted in the case: no lead to rip off |
| Drone out (right end) | XT60 + XT30, each on a 10 cm 14 AWG silicone lead, clamped | **Female** | Mates the drone's male. Flexible enough for frame-mounted XT60s |
| In the box | BT2.0 pair: BT2.0 male → XT30 female (battery), XT30 male → BT2.0 female (drone) | — | 1S whoops |
| Accessory | XT90 pair and AS150U pair, same pattern | — | 8–14S heavy-lift |

- XT60 and XT30 between them cover almost every 2–8S FPV build, so most
  users never need an adapter.
- Only one input may be used at a time. The unused input's pins are
  live but recessed in their shroud (as on ShortSaver 2); the case puts a
  rib between the two so a stray wire cannot bridge them.
- Adapter resistance does not matter at bench currents.

---

## 9. Electronics

### Block diagram

```
 XT60/XT30 in ─┬─ TVS ─ [FET A]─[FET B] ──────┬──────────────── XT60/XT30 out (+)
               │        back-to-back          │
               │   ┌─ switch + pre-charge R ──┤
               │   │                          ├─ 3 V probe (1 kΩ / 100 Ω, 100 V diode)
               │   high-side driver           ├─ voltage sense (0–65 V and 0–3.3 V ranges)
               │   (charge pump, own short    │
               │    trip, reverse protect)    │
               │        ▲                     │
               │        └── peak comparator ◄── 120 V current amp ◄── high-side shunt
               │
               └─ reverse-protected 3.0–65 V buck ─┐
                                   USB-C 5 V ──────┴─► 3.3 V ─► MCU ─► screen, ring LEDs,
                                                                     buttons, beeper, NTC, USB
```

### Candidate parts (to be confirmed at schematic stage)

| Function | Candidate | Notes |
|---|---|---|
| High-side controller | **TI TPS48111-Q1** | 3.5–80 V (100 V abs max), back-to-back N-FET drive, 1.2 µs short-circuit trip, current monitor, and a second gate driver that runs the pre-charge switch |
| Main switch | 2 × 100 V N-MOSFET, ≤ 3 mΩ, 5 × 6 mm | Infineon OptiMOS 6 100 V class; a second maker qualified for supply |
| Pre-charge | Small 100 V switch + two pulse-rated resistor banks (≈ 2 Ω and ≈ 22 Ω), picked by cell count | The resistors take the ≈ 9 J at 14S, not a transistor |
| Shunt | 1 mΩ, 2512, 4-terminal (Kelvin), 3 W, **high side** | 0.6 W at 25 A. High side, so USB can stay connected while the drone is on |
| Current amp | **TI INA290** (2.7–120 V common mode), auto-zeroed before each power-on | ±10 mA idle figure, 14S with margin |
| Peak comparator | Push-pull comparator, MCU-set threshold | Output pulls the driver's input low directly |
| Aux supply | **TI LMR36503** buck, 3.0–65 V in | 1S–14S. Fed through an RC filter and its own clamp, so input spikes stay under its 70 V limit |
| MCU | ST **STM32C071** | USB without a crystal, 12-bit ADC, non-PRC maker |
| USB-C | 16-pin receptacle + ESD array | Data and 5 V. Works with the drone powered |
| Screen | **1.9" 320 × 170 colour IPS** (ST7789, SPI) under black glass | The arming screens are drawn for this panel ([`ui/`](ui/)) |
| Status ring | 12 × addressable RGB LED under the ring light pipe round the toggle | Also lights the translucent guard from inside |
| Input clamp | 64 V stand-off TVS (SMBJ64A class) | Clears 14S LiHV at 60.9 V |
| Toggle | Metal-bushed toggle, ON-OFF-(ON), PCB mount (C&K 7000 / APEM class) | Signals only; Bind is the spring-return position |
| Guard sensor | Hall-effect switch under the guard tip's magnet | Its output also gates the controller's enable: guard closed = off in hardware |
| Limit rocker | Two tact switches under an aluminium paddle | |

### Board

- Two layers, 2 oz copper; power path on the bottom, top side kept clean
  as the face (only the screen, buttons, LEDs and silkscreen).
- Built with the repository's generator and verification gates, like
  `packet-logger-carrier` and Ridge 3.
- Programming and test pads on the bottom, reachable with the case open;
  everyday updates go over USB-C.

---

## 10. Mechanical

- **Body:** 96 × 58 × 18 mm, soft-touch black (printed MJF nylon for the
  first batch, moulded or machined aluminium later), anodised face plate.
- **Guard:** translucent Ember polycarbonate, 24 × 34 mm, walls 17 mm, on
  a 2 mm stainless pin with a torsion spring and a detent at closed. A
  magnet in its tip; a cam on its inside pushes the toggle to Off as it
  closes. Opens to about 108°.
- **Toggle:** metal bat and bushing, through the face, Beacon Ring light
  pipe round the bushing.
- **Ends:** XT60 and XT30 (male) through the left end with a rib between
  them; the two drone leads through clamped grommets on the right end;
  USB-C on the back.
- **Underside:** rubber feet; fully closed so it cannot short on a
  conductive bench.
- 3D model and demo: [`design/arm/arm.py`](design/arm/arm.py).

---

## 11. Brand

Taken from the existing boards (`packet-logger-carrier`, Ridge 3):

- **The logo is never redrawn by hand.** The Beacon Ring and the lockup
  come only from [`brand/mark.py`](brand/mark.py), which builds them from
  the brand file's own numbers (ring r 58, stroke 22 with round caps, node
  r 17 at (100, 40) in the 200-unit box; lockup per v3.2 with the word's
  capitals centred on the ring). [`brand/verify_mark.py`](brand/verify_mark.py)
  checks it against the brand SVG rendered by Chromium and fails on any
  edge more than 0.2 units off. Every render, screen, silkscreen and
  animation takes the mark from there; a status-light ring in the shape
  of the mark is the mark, at its exact proportions.

- **Pitch** `#1B1813` matte black solder mask; **Bone** `#F1ECE0` white
  silkscreen; **Ember** `#FF6A00` as light, not ink: the ring's caution
  colour and the Beacon Ring itself.
- Labels: Instrument Sans 500, sentence case, never bold. Numbers, units
  and codes: JetBrains Mono 500, uppercase. Weight 600 belongs to the
  wordmark only.
- Horizontal lockup (mark + "OffGrid") bottom right; `REV` and serial in
  mono.
- ENIG gold on exposed pads, as on Ridge 3.

---

## 12. Parts: best result, not lowest cost

Owner's decision (10 Oct 2026): no price target; SmokeBreak is to be the
best smoke stopper on the market. Where the earlier cost-down traded
something away, the better part is back:

| Area | Cost-down version | This spec | Why |
|---|---|---|---|
| Controller | TPS4800-Q1 | **TPS48111-Q1** | 1.2 µs short trip, current monitor and a pre-charge gate driver built in |
| Current sense | Low-side shunt + op-amp | **High-side Kelvin shunt + INA290** | USB can stay connected with the drone on; no ground-loop caveat |
| Main FETs | ≤ 6 mΩ | **≤ 3 mΩ** | Motor test back to 25 A for 60 s, cooler at 15 A continuous |
| Status ring | 3 LEDs | **12 LEDs** | Even light; the ring fills as the check runs |
| Connectors | Generic | **Genuine Amass, gold-plated** | Insertion life and contact resistance |
| Pre-charge | Resistors | **Resistors** (unchanged) | Still the most robust way to take 9 J at 14S |

Case material, screen type and controls follow the industrial design
chosen from [`concepts/`](concepts/). Cost is tracked there per concept
for information only.

Market reference: polyfuse $5–8; smart $15–23 (ShortSaver 2 $16–17,
SpeedyBee ≈ $20–23, 4–6S only). Nothing above 6S is smart; nothing has a
screen that explains the fault in words.

---

## 13. Compliance

- No radio. In the US it needs an FCC Part 15B Supplier's Declaration of
  Conformity as an unintentional radiator (USB-C does not change that).
  CE/UKCA (EMC + RoHS) for Europe.
- It is ground test equipment that never flies, so the FCC Covered List
  entry for "UAS critical components" (Ridge 3 research) should not apply.
  **Confirm before launch.**
- LiPo safety wording on the box and the face: bench use only, props off
  for the 25 A setting, never leave unattended.

---

## 14. Risks and open questions

1. **Pre-charge resistor energy.** Charging 5,000 µF to 60.9 V puts
   ≈ 9.3 J into the resistors in under 1 s. Size them from their pulse
   curves and limit retries (energy budget per minute).
2. **Probe on 1S.** 1S flight controllers run near 3 V. Measure real whoops
   before fixing the 1S thresholds.
3. **Reversed-lead signature** on AIO boards with a reverse-protection
   diode or ideal-diode chip: they will look "open". Test on several boards;
   the pre-charge stage still stops a reversed drone at low current.
4. **Capacitance fingerprint repeatability** across temperature and
   capacitor age. Bench data needed before promising "remembers".
5. **Name** needs a trademark search (the Ridge 3 research already found
   "OFFGRID" registered in class 9 by another company).

---

## 15. How v1 will be proven

Before a second batch, each of these passes on the bench:

| Test | Pass |
|---|---|
| Dead short (10 mΩ) on the output, 1S–14S | Probe stops it; zero battery current |
| 18 Ω and 100 Ω half-shorts | Named, resistance within 10 % |
| Reversed lead on 3 different ESCs and 2 AIOs | "Reversed" on every one, or stopped in pre-charge |
| 2,000 µF + 470 µF at 6S, 5,000 µF at 14S | No trip, pre-charge resistors within their pulse rating |
| ESC start-up tones, O4 + 6S, Walksnail + 6S | No trip on Auto |
| Guard closed while live, MCU held in reset | Drone off within 1 ms |
| Guard hinge, 10,000 open/close cycles | Still detents, still cams the toggle off |
| O4 Pro on 3S and 7S, Walksnail on 14S heavy-lift | Pre-charge passes 75 %, then on |
| Short applied while on, at each setting | Off in ≤ 5 µs (scope) |
| 25 A for 60 s | Switch < 100 °C, drops back after 60 s |
| Reversed battery to −61 V | No damage, message shown |
| USB-C connected to a laptop, drone on | Readings and trips unchanged |
| Same drone, 10 plug-ins over a week | Recognised every time |
| ELRS 3.x receiver, Bind button | Enters bind on every try |
| MCU held in reset, short applied | Driver's own trip still cuts off |

---

## 16. Not in v1

- A native XT90 version.
- **Pro version:** an in-line unit for 8–14S heavy-lift that stays
  connected in flight as an anti-spark switch and runs the same pre-check
  at every power-up. Anti-spark filters (~$15) don't detect shorts and
  smoke stoppers can't be flown through; nothing does both today.
- Battery internal-resistance test, phone app.
