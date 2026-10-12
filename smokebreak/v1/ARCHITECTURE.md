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
| Battery checker | Pack voltage from the main lead; **per-cell voltages 2S–6S** from a JST-XH balance lead (one keyed socket per size); cell delta, lowest/highest cell, state of charge, storage hint, internal-resistance estimate under load, mismatch between balance and main |
| Arm UX | Guard magnet sensed by a hall switch (hardware power cut), ON-OFF-(ON) metal toggle, Limit rocker (two tact switches), 1.9" 320×170 colour IPS, plain status-ring light (12 RGB LEDs), beeper |
| Wrong connections | Survives and explains every miswiring in §4 |
| USB-C | Firmware update, drone-memory export, powers the screen alone |

## 2. Blocks

```
 XT60/XT30 male ─┬─ TVS SMBJ64CA (bidirectional) ── Q1 ─┬─ Q2 ──┬──────────── XT60/XT30 female (+, drone)
 (battery in)    │   + input caps (damped)        common │       ├─ pre-charge: Q3 (P-FET) + D3 + RPRE ── from VIN
                 │                               source  │       ├─ 3 V probe (1 kΩ / 100 Ω via P-FETs, Schottky)
                 │          TPS48000 high-side driver ───┘       ├─ VOUT sense: 0–65 V divider + 0–3.3 V clamped channel
                 │          (charge pump, 4 µs short trip,       └─ diode-OR into AUX (wakes on "battery on the drone side")
                 │           -65 V tolerant, low-side sense)
                 │          ▲ INP = AND3( MCU_EN, GUARD_OPEN (hall), LATCH_OK (peak comparator latch) )
                 │
 GND ────────────┴──────────── RS1 1 mΩ (Kelvin) ──────────────── XT60/XT30 female (−, DRONE_NEG)
                               │  │
                               │  └ INA181A2 (gain 50) ─► I_ADC, LMV331 peak comparator ─► latch
                               └─── TPS48000 CS+/CS− (short-circuit trip)

 AUX = diode-OR (VIN, VOUT, balance taps, USB 5 V) ─► LMR36506 buck 5 V ─► LEDs, beeper, backlight ─► TLV75533 3.3 V

 JST-XH 2S–6S sockets (pin k of each = tap k) ── pin 1 = GND (B−), pins 2–7 ── 0.1 % dividers ── switched ground (2N7002) ── ADC ×6
```

### 2.1 Power path

- **Q1, Q2**: Infineon BSC040N10NS5 (100 V, 4 mΩ), common source, back to
  back. Q2 blocks the battery (or charged capacitors) on the drone side
  from back-feeding; together they block both polarities when off.
- **Driver**: TI TPS48000: charge-pump gate drive (PU/PD pins, BST cap),
  short-circuit trip in ~4 µs set by RISCP, VS/SRC rated to −65 V so a
  reversed 14S pack on either side cannot hurt it (a reversed input pack
  pulls SRC to VIN through Q1's body diode; Q2 blocks the path).
- **Shunt, low side**: 1 mΩ four-terminal WSK1216 in the drone's return.
  The TPS48000 reads it in low-side mode (CS_SEL high); the INA181A2 reads
  the same Kelvin pads. Low-side sense keeps every sense pin at ground
  potential, so cheap 26 V parts do the precise measurement.
- **Pre-charge**: P-channel FET from VIN through the series Schottky D3
  (blocks back-feed from the drone side) and RPRE to the drone side, gated
  by the MCU AND the guard (two NPNs in series). The resistor, not a
  transistor, takes the charging energy; firmware limits each attempt's
  energy and watches the resistor's thermistor. Value and rating from the
  simulations (`sim/SIM.md`).
- **Two-tier limit**: firmware average limit (200 ms window) from the
  INA181A2; peak limit by the LMV331 comparator on the INA181A2 output
  against an MCU DAC threshold, latched in a 74LVC1G74 and pulling INP low
  in under 1 µs; the TPS48000's own short-circuit trip, independent of
  firmware.
- **Guard = hardware off**: the DRV5032 hall switch is one input of the AND
  gate driving INP and one of the two series NPNs of the pre-charge. Guard
  closed → nothing can switch on, whatever the MCU does.
- **TVS**: SMBJ64CA, bidirectional, 64 V stand-off: does not conduct at 14S
  LiHV (60.9 V) or for a reversed pack.

### 2.2 Aux supply

Diode-OR of VIN, VOUT, the balance taps and USB 5 V into AUX, then the
LMR36506 (3.6–65 V in) buck to 5 V (LEDs, beeper, backlight) and a
TLV75533 LDO to 3.3 V. The OR is
what lets the board wake up and explain itself when the battery is on the
wrong side or only the balance lead is plugged in.

### 2.3 Measurement (MCU ADC)

| Channel | Range | Use |
|---|---|---|
| VIN | 0–66 V | pack voltage, cell count |
| VOUT high | 0–66 V | drone side voltage, pre-charge progress |
| VOUT low | 0–3.3 V (clamped) | 3 V probe |
| I precise | INA181A2 (gain 50) | 0–60 A; offset auto-zeroed with the switch open before every arm |
| BAL1..BAL8 | taps up to 36 V | per-cell voltages |
| NTC ×2 | | Q1/Q2, RPRE |
| VREFINT | | ADC calibration |

### 2.4 Balance lead

- Five JST-XH side-entry sockets, one per size (2S 3-pin … 6S 7-pin), along
  the back wall; pin k of every socket is tap k, **pin 1 = GND (B−)**, marked
  under each socket with an arrow. A plug only fits its own socket.
- Each of taps 2–7 has its own 0.1 % divider to an ADC pin; all divider
  bottoms return through one N-FET so nothing drains the cells when the
  board is off.
- Cells = differences of adjacent taps, oversampled; accuracy target
  ±10 mV per cell after factory calibration (±20 mV uncalibrated).
- Cell count from the pattern. The keyed sockets make a shifted plug
  impossible; the firmware still recognises one (a lead through an
  adapter) and reads it correctly when the main lead is connected.

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
| USB plugged into a computer while the drone is on | the switch is high side, so the drone's minus never floats; a second ground path through USB only bypasses the shunt (reading low), never the switch | — |

## 5. Mechanical interface (Arm, 100 × 58 × 18 mm body)

- Board 94 × 52 mm, 4 layers (1.6 mm, 1 oz outer), sits with its top face
  11.5 mm under the top panel's underside, so the XT connectors' axes are
  at the body's mid-height. The toggle (8.89 mm PCB-to-shoulder) seats on
  a 2.6 mm printed boss under the panel. Under the screen (board x 2.5–48.5,
  y 5–31) parts stay below 8.5 mm (tallest: XT60 at 8.1 mm).
- All SMD parts on the top side (one-sided assembly); connectors, toggle
  and pre-charge resistor through-hole, hand-soldered from the bottom (the
  bottom silkscreen carries the words for that).
- Left wall: XT60PW-M + XT30PW-M (battery in). Right wall: XT60PW-F +
  XT30PW-F (drone out), panel-mounted on the board like the inputs (no
  leads to rip out). Back wall: the five balance sockets, 2S–6S, mouths
  flush with the outer face. Front wall: USB-C at the battery end.
- Layers: F.Cu parts, signals and the power pours under the FETs; In1 a
  solid ground plane; In2 VIN (west side and south band) and VOUT (east
  side) planes with signals in between; B.Cu signals, ground fill and the
  drone-negative strip.
- Through-resistance budget ≤ 20 mΩ: FETs 2 × 4 mΩ, shunt 1 mΩ, planes
  and connectors the rest.
