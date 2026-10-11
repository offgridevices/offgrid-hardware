# SmokeBreak v1 — electrical architecture

The board that goes in the Arm (`../design/arm/`). This file is the
reference the circuit (`src/circuit.py`), the simulations (`sim/`) and the
firmware model (`firmware/`) are built against. Where they disagree, fix
this file first.

Owner's targets (11 Oct 2026): retail **$30**, landed cost **$20–22**
(PCBWay assembly of the SMD side, owner hand-solders the through-hole
parts and assembles a 3D-printed case). Upload-ready for PCBWay: BOM with
manufacturer part numbers, pick-and-place, Gerbers.

---

## 1. What the board does

| Function | How |
|---|---|
| Smoke stopper, 1S–14S (3.5–60.9 V) | High-side back-to-back N-FETs under a smart controller, 3 V probe, pre-charge, two-tier current limit |
| Battery checker | Pack voltage from the main lead; **per-cell voltages 1S–8S** from a JST-XH balance lead; cell delta, lowest/highest cell, state of charge, storage hint, internal-resistance estimate under load, mismatch between balance and main |
| Arm UX | Guard magnet sensed by a hall switch (hardware power cut), ON-OFF-(ON) metal toggle, Limit rocker (two tact switches), 1.9" 320×170 colour IPS, plain status-ring light (12 RGB LEDs), beeper |
| Wrong connections | Survives and explains every miswiring in §4 |
| USB-C | Firmware update, drone-memory export, powers the screen alone |

## 2. Blocks

```
 XT60/XT30 male ─┬─ TVS (bidirectional, 64 V) ─ shunt 1 mΩ (Kelvin) ─ Q1 ─┬─ Q2 ─┬──────── XT60/XT30 female (drone)
 (battery in)    │                          │                    common    │      │
                 │                    INA290 (precise I)     source node  │      ├─ pre-charge: QP (P-FET) + RPRE ── from VIN
                 │                          │                              │      ├─ 3 V probe (1 kΩ / 100 Ω via P-FETs, 100 V Schottky)
                 │                 TPS48111 smart high-side controller ────┘      ├─ VOUT sense: 0–65 V divider + 0–3.3 V clamped channel
                 │                 (charge pump, 1.2 µs short trip, IMON)         └─ diode-OR into AUX (warns "battery on drone side")
                 │                          ▲ INP = AND3( MCU_EN, GUARD_CLOSED̅ (hall), PEAK_OK (comparator) )
                 │
                 └─ diode-OR ─► AUX ─► LMR36503 buck 5 V ─► LEDs, buzzer ─► TLV75533 3.3 V ─► MCU, display, sensors
                    (VIN, VOUT, balance top pin, USB 5 V)

 JST-XH 9-pin balance ── pin 1 = GND (B−), pins 2–9 ── 0.1 % dividers ── switched ground (N-FET) ── ADC ×8
```

### 2.1 Power path

- **Q1, Q2**: 100 V N-MOSFETs, ≤ 4 mΩ, common-source back-to-back. Q1
  blocks a reversed battery; Q2 blocks a battery or charged capacitors on
  the drone side from back-feeding.
- **Shunt**: 1 mΩ 2512 four-terminal, high side, between the TVS and Q1.
  The TPS48111 reads it for its short-circuit trip and IMON; the INA290
  reads the same Kelvin pads for the precise idle current.
- **Pre-charge**: P-channel FET from VIN through RPRE (~22 Ω, pulse-rated)
  to the drone side, driven by the MCU through a level shifter with a
  zener-clamped gate. The resistor, not a transistor, takes the charging
  energy. After the drone passes 75 % of VIN, the TPS48111 closes Q1/Q2
  with a slow gate (Cdvdt) to close the remaining gap.
- **Two-tier limit**: firmware average limit (200 ms) from the INA290; peak
  limit by a push-pull comparator on the INA290 output with an MCU-set
  threshold (PWM + RC), pulling INP low in ≤ 5 µs; the TPS48111's own
  short-circuit trip (fixed, ≤ 1.2 µs) independent of firmware.
- **Guard = hardware off**: the hall switch output is one input of the AND
  gate driving INP. Guard closed → INP low → Q1/Q2 off, whatever the MCU does.
- **TVS**: bidirectional, 64 V stand-off: does not conduct at 14S LiHV
  (60.9 V) and does not conduct a reversed battery.

### 2.2 Aux supply

Diode-OR of VIN, VOUT, the balance lead's top pin and USB 5 V into AUX,
then a 3–65 V buck to 5 V (LEDs, buzzer) and an LDO to 3.3 V. The OR is
what lets the board wake up and explain itself when the battery is on the
wrong side or only the balance lead is plugged in.

### 2.3 Measurement (MCU ADC)

| Channel | Range | Use |
|---|---|---|
| VIN | 0–66 V | pack voltage, cell count |
| VOUT high | 0–66 V | drone side voltage, pre-charge progress |
| VOUT low | 0–3.3 V (clamped) | 3 V probe |
| I precise | INA290 | 0–40 A, idle ±10 mA after auto-zero |
| IMON | TPS48111 | cross-check |
| BAL1..BAL8 | taps up to 36 V | per-cell voltages |
| NTC ×2 | | Q1/Q2, RPRE |
| VREFINT | | ADC calibration |

### 2.4 Balance lead

- 9-pin JST-XH, **pin 1 = GND (B−)** marked with the brand arrow and
  "Black wire here".
- Each of pins 2–9 has its own 0.1 % divider to an ADC pin; all divider
  bottoms return through one N-FET so nothing drains the cells when the
  board is off.
- Cells = differences of adjacent taps, oversampled; accuracy target
  ±10 mV per cell after factory calibration (±20 mV uncalibrated).
- Cell count from the pattern; a plug shifted along the header still reads
  correctly when the main lead is connected (black wire = 0 V wherever it
  lands); with the balance lead alone, a shifted plug leaves the board
  unpowered (safe) and the arrow on the case shows where black goes.

## 3. Battery information on screen

| Shown | From |
|---|---|
| Pack voltage, cell count, % (resting OCV curve) | VIN, balance |
| Each cell's voltage as a bar, lowest and highest marked | balance |
| Cell delta (max − min) with a verdict: balanced ≤ 20 mV, drifting ≤ 50 mV, out of balance > 50 mV | balance |
| Storage hint: 3.80–3.85 V/cell | balance |
| Warnings: cell < 3.0 V (over-discharged), > 4.25 V LiPo / > 4.40 V LiHV (over-charged), a dead cell (< 2.5 V), balance cell count ≠ main cell count (broken balance wire or different packs), sum of cells ≠ pack voltage by > 2 % | balance + VIN |
| Internal resistance estimate: ΔV/ΔI of the pack between idle and a motor-test step | VIN, current |
| Battery check alone (no drone): balance lead only | balance, AUX from top pin |

## 4. Wrong connections and bad batteries (every one must be survivable)

| Case | What happens | Screen |
|---|---|---|
| Battery reversed on the input (miswired pigtail) | Q1 body diode blocks; bidirectional TVS blocks; aux OR diodes block; nothing powers | (dark) — no damage |
| Battery on the drone side, nothing on the input | Q2 blocks; aux wakes from VOUT | "Battery on the drone side — move it to Battery" |
| Batteries on both sides | Probe stage sees VOUT > 1 V before anything closes → no pre-charge, no switch | "Drone side already has power" |
| Battery reversed on the drone side | Q2 body diode conducts into the common node, Q1 blocks; probe sees negative VOUT | "Reversed battery on the drone side" |
| Drone wired backwards | 3 V probe: diode clamp signature | "Leads reversed" |
| Dead short / half-short | 3 V probe | "Short 0.3 Ω" / "Half-short 18 Ω" |
| Balance plug shifted | readings still correct with main connected | "Balance plug shifted — reading OK" |
| Balance lead from another pack | cells ≠ pack | "Balance lead is not from this battery" |
| Deeply discharged pack (< 3.0 V/cell) | check runs; power allowed with a warning | "Cell 3 at 2.71 V — over-discharged" |
| Over-charged / LiHV detection | | "Cell 2 at 4.31 V — over-charged for LiPo" |
| High internal resistance (sags) | IR estimate | "Pack sags 1.9 V at 10 A — 95 mΩ" |
| Pack collapsing under load (bad cell) | input UV during on → off | "Battery voltage collapsed" |
| Input surge / hot-plug spark | TVS, input capacitance limited | — |
| USB plugged into a computer while drone is on | high-side shunt: no ground-loop issue | — |

## 5. Mechanical interface (Arm, 100 × 58 × 18 mm body)

- Board ≈ 94 × 52 mm, 4 layers, sits under the top panel. Top side:
  display (FPC), toggle (through the top panel), 12 LEDs round the toggle,
  hall switch under the guard tip, two tact switches under the rocker.
  Everything else on the bottom side? No: all SMD on the **top** side
  (one-sided assembly is cheaper); the toggle, connectors and the
  pre-charge resistor are through-hole, hand-soldered.
- Left edge: XT60PW-M + XT30PW-M (male, right-angle PCB mount). Right
  edge: pads for the two drone leads (XT60/XT30 female on 14 AWG / 18 AWG).
  Back edge: USB-C. Front-left corner: JST-XH 9-pin balance header.
