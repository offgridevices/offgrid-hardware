# SmokeBreak v1 firmware — reference model

`model/` is a Python reference implementation of every decision the STM32G0B1
firmware makes. It is written to port 1:1 to C: integer units in the names
(`_mv`, `_ma`, `_ms`, `_mohm`, `_uj`, `_dc` = deci-°C), C-style truncating
division (`inputs.idiv`), no floats in the decision path, no dynamic
dispatch, fixed-size history. `sim_world.py` is test equipment only (floats,
never ported).

```
cd smokebreak/v1/firmware
python -m pytest -q          # 328 tests, ~18 s
```

Reference documents: `../docs/architecture.md` (the board), `../src/circuit.py`
(the final hardware), `../sim/SIM.md` (power-path simulations and the design
values the firmware must honour), `../docs/spec.md` (§4 stages, §5 protection,
§6 UI, §7 memory), `../ui/screens.py` (S00–S21).

## Hardware the model is written against (circuit.py, SIM.md)

| Item | Value | Firmware consequence |
|---|---|---|
| Pre-charge resistor | **one bank**: R_PRE + R_PRE2, 2 × 3.9 Ω 5 W AC05 in series = **7.8 Ω**, 1S–14S | `precharge.RPRE_MOHM`; no bank select output |
| Pre-charge energy | worst normal attempt ≈ 10.6 J (SIM.md case 1(c)) | abort at **12 J** per attempt; 45 J per minute; 1 s timeout; RPRE NTC 120 °C |
| Main-switch close | BSC040N10NS5 linear SOA is tiny (SIM.md finding 4) | close only after the pre-charge has **settled** (rise < 1 % of VIN in 20 ms) **and VIN − VOUT ≤ 12 V**, else refuse (`PRECHARGE_STALL`, "Drone draws power at x V", "y V gap · z A") |
| Current sense | INA181A2 (gain 50) on a 1 mΩ **low-side** shunt in the drone return, 0–65 A | sees pre-charge current too; offset auto-zeroed with the switch open |
| Peak comparator | LMV331 U8 on the INA181A2 output; input range ends ≈ 2.6 V on 3.3 V (≈ 52 A) | threshold 4 × setting, **capped at 50 A** (SIM.md finding 3a, case 9) |
| Hard-short comparator | fixed LMV331 U12 on the shunt, 64.7 mV ≈ **65 A**, onto the same latch | firmware sees it as a peak trip |
| TPS48000 SCP | RISCP 40.2 kΩ ≈ **99 A** (SIM.md case 3) | `short_trip` (FLT) |
| Board C on VOUT | 0.1 µF + 2 × 4.7 µF / 0.47 Ω snubber = **4.1 µF** as SIM.md case 7 gives it | probe subtracts `probe.BOARD_CAP_NF`; OPEN = < 2 µF net |
| Probe switches | MMBT5401 PNPs (150 V), active low | logic unchanged |
| Battery return | reverse-battery FET Q11; balance black wire to GND through **10 Ω** (R75) | cell voltages taken at idle only (`Machine.batt_idle`) |

## Module map

| Module | What it decides | C unit / where it runs |
|---|---|---|
| `inputs.py` | `Inputs`: one sample of the world (VIN, VOUT signed, VOUT_low, INA181A2 current, peak/short trip flags, 8 balance taps, 2 NTCs, hall, toggle, rocker, VBUS). `aux_powered()`: would the diode-OR wake the MCU. | `sb_inputs_t`, filled by the ADC/DMA and GPIO layer before each control tick |
| `probe.py` | 3 V probe verdict: SHORT / HALF_SHORT (with Ω) / REVERSED / OPEN / OK (with µF, board's 4.1 µF subtracted). All thresholds are module constants. | `probe.c`, pure function over three DMA'd sample buffers |
| `precharge.py` | Pre-charge supervisor (one 7.8 Ω bank): PASS when settled with VIN − VOUT ≤ 12 V; ABORT when settled with a larger gap (stall: refused), 1 s timeout, 12 J per attempt, 45 J per minute, hot resistor, input collapse. | `precharge.c`, stepped from the 1 kHz control task |
| `limits.py` | AUTO limit, 200 ms average limiter (20 × 10 ms buckets), peak comparator threshold (4 × setting, ≤ 50 A), rocker with 25 A confirm (400 ms dead time, 3 s window, 60 s motor test). | `limits.c`; the bucket accumulator lives in the ADC ISR |
| `battery.py` | Cell count from VIN (with ambiguity flag), balance-lead decoding (shift, broken wire, other pack, count/sum mismatch), per-cell warnings (valid at idle only), delta verdict, SoC from OCV tables (LiPo, LiHV), storage hint, IR from ΔV/ΔI. | `battery.c`, 10 Hz task |
| `memory.py` | 32 drone profiles keyed by cell count + capacitance (±15 %), idle at 10 s, idle-up and capacitance-down warnings, LRU replacement. | `memory.c`, one flash page, wear-levelled |
| `packs.py` | 32 battery packs remembered by a number the box gives them: fingerprint (exact cell count, pack and per-cell IR within ±25 % / ±30 %, recency), the "Pack 7?" question on the rocker (+ yes, − next, then "new", 5 s timeout = skip), uses, first/last seen (RTC or visit counter), IR at first sight and latest, "wearing" at > +40 %, worst cell, imbalance, LRU, numbers never reused. | `packs.c`, one flash page, wear-levelled |
| `machine.py` | The state machine: STARTUP, SAFE, ARMED, CHECKING, PRECHARGE, ENGAGING, LIVE, WARNING, ABORT, BIND, POWER_CUT, TOO_HIGH; overlays S11/S13; the pack question on the battery screens. Per tick: switch commands, screen (S-number + data), ring colour, beep. | `machine.c`, the 1 kHz control task |
| `sim_world.py` | Plant: pack (cells + IR), balance lead (shift, broken wires, other pack), drone (caps, leakage, 1S FC, shorts, reversed diodes, regulators, constant-power VTX, voltage-dependent fault, motor demand, its own battery), board (probe, 4.1 µF on VOUT, D3 + 7.8 Ω pre-charge, slow-gate switch, low-side shunt, INP AND gate, peak latch with the 52 A LMV331 ceiling and the 65 A hard-short comparator, 99 A SCP, Q11 lifting the taps under load, thermal). `Rig` gives tests human verbs. | not ported |

## Mapping to the C firmware

| Context | Rate | Work |
|---|---|---|
| ADC ISR (DMA half/full) | INA181A2 at 10 kHz (TIM-triggered, oversampled ×4) | add samples into the current 10 ms bucket (`AverageLimiter.add`), track window peak |
| ADC scan, DMA | 1 kHz: VIN, VOUT-high, VOUT-low (×16 oversampled); 100 Hz: BAL1–8, NTC×2, VREFINT, IMON | fills `sb_inputs_t` |
| Probe capture | VOUT-low at 1 kHz into three buffers (50 + 250 + 50 samples) while CHECKING | `probe_classify()` at the end |
| Control task | 1 kHz (SysTick) | `machine_step()`: guard rule first, then the state handler, then outputs |
| Battery task | 10 Hz | `battery_analyse()` (the model runs it every tick; result is identical) |
| UI task | 30 Hz | draws `Outputs.screen` (ST7789 over SPI DMA), ring LEDs, beeper patterns |
| GPIO | EXTI on hall + toggle, 1 kHz scan for debounce (rocker 20 ms) | debounced levels into `sb_inputs_t` |
| Hardware, no firmware | < 5 µs (SIM.md case 9) | peak LMV331 clears the latch → INP low (threshold = `Outputs.peak_threshold_ma` via DAC+RC, ≤ 50 A); hard-short LMV331 at ≈ 65 A onto the same latch; TPS48000 SCP at ≈ 99 A; hall gates INP |
| Flash | on change | drone memory page; energy ledger stays in RAM |

Outputs per tick: `precharge_on` (Q3 gate, via Q4/Q5), `main_on` (MCU_EN
into the INP AND gate), `probe_src` (OFF / 1 kΩ / 100 Ω, MMBT5401 PNPs Q6/Q7,
active low), `divider_en` (balance divider ground FET), `peak_threshold_ma`,
`screen`, `led`, `beep` (one-shot), `beep_loop` (abort alarm). There is no
resistor-bank output: the pre-charge has one resistor value.

## Decisions taken where the documents were silent or disagreed

1. **Probe is 1 kΩ → 100 Ω → 1 kΩ (350 ms).** With reversed leads on a drone
   with a big capacitor, the first 1 kΩ phase ends before the cap reaches the
   diode clamp, so "barely moves between currents" can only be judged after
   100 Ω has charged it. A half-short hidden by a big cap is found by
   extrapolating the 100 Ω rise (Aitken Δ²).
2. **OPEN** (nothing on the lead) proceeds to pre-charge, because SPEC §14.3
   says AIO boards with ideal-diode protection can look open; the checklist
   shows Capacitor "none".
3. **Residual charge.** After any power-off the drone's caps stay charged,
   so the next ON would read "Drone side already has power". If we powered
   this drone in the last 60 s and VOUT is no higher than when we let go, the
   probe is skipped (held charge rules out a short, half-short and reversal)
   and the supervised pre-charge runs. Otherwise VOUT > 1 V is
   "both sides powered".
4. **Re-arming.** ON or BIND counts only after the toggle was seen at OFF in
   ARMED; after a run it must rest at OFF for 300 ms (stops ON→OFF→BIND
   chaining mid-check). After bind the drone stays on with the toggle at OFF
   (it springs back); ON then OFF turns it off.
5. **Bind** = full check, then 3 short power-ups (on 0.8 s, off 0.8 s, each
   with its own supervised pre-charge), then a fourth that stays on.
6. **25 A confirm**: + within the first 400 ms of the prompt *cancels* it, so
   mashing can never arm the motor test. Closing the guard ends it.
7. **AUTO** uses the idle current from the previous visit; this visit's
   reading only applies next time (the limit never tightens under a live drone).
8. **Capacitance-down warning** can only match the *last drone seen* (a cap
   drop of > 30 % never matches within ±15 %). Stored values update every
   visit, so each warning shows once.
9. **Cell-count guess** picks the fewest cells in 3.45–4.40 V/cell and flags
   ambiguity. Correct for any full pack 1–14S; at storage charge 9–14S (no
   balance lead) it guesses one cell low and says so. Firmware never acts on
   the guess for anything dangerous: there is one RPRE for every pack, 1S
   rules can't be confused with 2S.
10. **One RPRE bank, closing on a small gap.** The old two-bank scheme
    (~2 Ω ≤ 7S, ~22 Ω above) is gone; 7.8 Ω serves 1S–14S. The 75 % pass
    point is replaced by SIM.md's close rule: settled (net rise < 1 % of VIN
    in 20 ms; a net rise, so a regulator hiccuping at its UVLO still counts
    as settled) and the lowest VOUT in that window within 12 V of VIN. A
    stall is therefore *not* a fault when the gap is ≤ 12 V (SIM.md 1(b):
    2S–5S drones whose 10 W VTX sits at its 6 V UVLO close safely); it is
    refused when the gap is larger. Consequence: a fault that appears at
    higher voltage on a low-cell pack (e.g. 3 Ω above 6 V on 4S, 10.8 V gap)
    is no longer stopped by the pre-charge; the switch closes and the current
    limit trips (`test_fault_under_12v_gap_closes_then_limit_trips`).
11. **Battery reversed on the input** is dark (ARCHITECTURE §4); SPEC §4
    stage 0 says the screen explains it, which the hardware cannot do (VIN
    reads 0, the aux OR blocks).

12. **Over-voltage refusal (TOO_HIGH).** VIN ≥ 62.5 V (`VIN_TOO_HIGH_MV`:
    14S LiHV 60.9 V + 2.6 % for the 1 % divider and ADC gain, below the
    SMBJ64CA's 64 V stand-off), or a reading at the
    ADC's full scale (≈ 66 V: "over 66.0 V"), refuses the pack from any state
    on the tick it is seen: nothing switches, S08 shows the voltage, alarm.
    The guard does not clear it; only the input going away (VIN < 2.5 V, or
    the box going dark) does, then ON needs OFF first. A 15S pack below
    ≈ 4.17 V/cell is inside the 14S window and cannot be told apart.
13. **Pack memory.** 2 s after a plug-in, in SAFE with the rocker idle (no
    S11/S13/S18), the battery screen asks "Pack 7?" or "New pack 12"
    (`data['pack']`); the rocker answers it instead of changing the limit.
    Opening the guard, any other state, or 5 s without input skips it, and a
    skipped plug-in records nothing. At a plug-in nothing has drawn current,
    so matching is usually cell count + recency; IR measured in a run before
    the question was answered (box woken with the guard open) ranks the
    candidates and is stored on confirmation. A count that is ambiguous
    without the balance lead is not asked about. Cell 1's IR includes the
    B− return (corrected by 10 mΩ, `CELL1_RETURN_MOHM`). `Inputs.clock_s`
    (0 = RTC not set) is the new input for first/last-seen dates. The
    question rides on S01/S14/S15/S18 as data; `ui/screens.py` does not draw
    it yet.

## Findings for the hardware/spec

- **TPS48000 OV is not at ~64 V.** circuit.py says the OV divider "cuts
  above ~64 V", but 1 MΩ / 18 kΩ with the 1.23 V OV threshold (SIM.md) is
  ≈ 69.6 V, above the SMBJ64CA's 64 V stand-off. Between 62.5 V and
  ≈ 69.6 V only the firmware refusal keeps the switch open; the aux buck
  sees the pack either way (check its input rating against 16S+).

- **Superseded by the final hardware (circuit.py, SIM.md):** the earlier
  findings here (~17 J into the 22 Ω bank, 22 Ω stalling a 15 W VTX at 8S,
  pre-charge FET not gated by the guard) are resolved: one 7.8 Ω bank
  (worst attempt ≈ 10.6 J, 12 J abort; an 8S drone with a 15 W VTX now goes
  live, `test_8s_with_15w_vtx_goes_live_on_7_5_ohm`), and Q5 puts the guard
  in series with the pre-charge drive.
- **7.8 Ω still cannot power every low-voltage drone with a big VTX.** A 6S
  pack at 3.5 V/cell with a 10 W VTX stuck at its 6 V UVLO ends ≈ 15 V short
  of VIN and is refused (SIM.md case 1(b), open risk 7; here
  `test_6s_at_3v5_with_10w_vtx_is_refused_not_closed_across_15v`); in the
  model so is a full 6S with a 15 W VTX that starts at 8 V and 0.4 A of
  FC/RX (`test_load_too_big_stalls_and_says_where`). SIM.md's remedy is a
  3.9 Ω tap (second pre-charge switch at the resistor mid-point); with
  2 × 15 Ω in parallel that would be a separate switch on one resistor
  (15 Ω), which does not help, so it needs a different arrangement.
- **Board capacitance at probe voltage.** SIM.md case 7 gives 4.1 µF (the
  snubber's 2 × 4.7 µF at their 60 V effective value). At the probe's 3 V
  the X7S parts are near nominal (≈ 9.5 µF total). `probe.BOARD_CAP_NF` is
  a calibration constant: measure an empty board and set it.
- The probe source constant is 3.0 V *after* the Schottky; on the board it
  is 3.3 V through a saturated MMBT5401 and a BAT46WJ (SIM.md case 7 uses
  3.3 V, 0.30 / 0.42 V). Calibrate `PROBE_SRC_MV` on the bench.
- SPEC example "Pack sags 1.9 V at 10 A — 95 mΩ" is inconsistent
  (1.9 V / 10 A = 190 mΩ).

## Tests (328)

| File | Count | Covers |
|---|---|---|
| `test_probe.py` | 30 | shorts 0.01–0.8 Ω, half-shorts 2–140 Ω (±10 %), half-short behind 5000 µF, reversed with 10–4700 µF, open (board C only), board 4.1 µF measured and subtracted, 4 µF drone is not open, capacitance 20–10 000 µF (±10 %), 1S FC rule, no-big-cap rule |
| `test_precharge.py` | 19 | single 7.8 Ω bank, settle then pass with a small gap, 14S 5000 µF inside 12 J, VTX part-way up (6S 10 W, 8S/14S 15 W), VTX at UVLO with an 11.4 V gap closes, 6S 3.5 V/cell + 10 W refused at a ~15 V gap, 12 V boundary, still-rising is not settled, stall at higher voltage (V and A reported; 8S refused, 4S left to the limiter), timeout, 12 J abort and under-12 J not cut, per minute + recovery, hot resistor, collapse, booked once |
| `test_limits.py` | 23 | AUTO table, peak 4× capped at 50 A, no setting above the LMV331 ceiling, ESC tones pass, sustained trip, rocker steps, 25 A confirm, 60 s timeout, 3 s confirm timeout, mashing (4 rates), dead-time cancel, minus, both halves |
| `test_battery.py` | 78 | 1–14S full LiPo/LiHV, storage 1–7S, 9–14S ambiguity flag, balance 1–6S, LiHV vs LiPo, over-charged LiPo vs over-charged, plug shift 1–3 pins (guard only: the sockets are keyed), other pack (same/different count), sum mismatch at 2 %, broken mid/top wire, delta verdict boundaries, low/high marks, over-discharged, dead cell, SoC tables, storage hint, balance-only, IR dI minimum |
| `test_memory.py` | 8 | ±15 % match, cell key, closest wins, idle-up thresholds, cap-down, LRU at 32, export |
| `test_flow.py` | 31 | S00→S01, S02→S06 order with LEDs/beeps, nothing powered during check, toggle off, guard close live/mid-precharge/mid-check, flick on with guard closed, toggle held on through guard cycle, bind mid-check, bind cycles (<2 s each, then stays on), bind needs guard, S13/S11 overlays, 25 A live + 60 s, confirm timeout, mashing live, guard ends motor test, rocker ignored in abort, fault latch, start-up with toggle on, battery swap, average/peak/driver trips, over-temp, stall refused (8S, "Drone draws power at …"), fault under a 12 V gap closes then the limit trips (4S), energy budget at 14S |
| `test_wiring.py` | 23 | every ARCHITECTURE §4 row (reversed input with/without USB, battery on drone side, both sides, reversed on drone side, drone backwards, short, half-short, plug shifted, balance alone shifted = dark, other pack, deeply discharged, over-charged, high IR, collapse, USB while live), USB only, §3 screens S14/S15/S16, cell voltages from idle readings (not under load) |
| `test_packs.py` | 24 | 1–14S end to end, 1S/new-drone AUTO, 14S 5000 µF + VTX (8–12 J), 8S + 15 W VTX goes live, 6S 3.5 V/cell + 10 W VTX refused, memory: same → draws more, cap broke off, no big cap, residual-charge re-power, unknown charged drone |
| `test_pack_memory.py` | 65 | new pack 1, match, cell count exact (5 counts), pack IR ±25 % edges and 5 mΩ floor, per-cell ±30 % edges and 2 mΩ floor, same total told apart by the cell pattern, unknown IR on either side, ranking (closest IR, then uncompared, then recency), + / − / wrap through "new", 300 ms dead time, held button, both halves, 5 s timeout and − restarting it, skip records nothing, numbers never reused across 3 table wraps, LRU at 32, 32-bit visit counter wrap, missing clock, IR first/latest, wearing at 40 % edges, per-cell IR rounding and cell 1, worst cell, imbalance, export; machine: asked 2 s after plug-in, + confirms, replug proposes it, timeout hands the rocker back, rocker never reaches the limit while asked, guard open skips (arming unaffected), waits for S13 and a held rocker, asked after waking with the guard open, run IR stored (29 mΩ pack, 4 mΩ cells), wearing on the battery screen, IR from an earlier run ranks and is stored, RTC stored / absent, unplug drops the question, imbalance and weak cell at plug-in, ambiguous count not asked |
| `test_too_high.py` | 27 | threshold vs 14S LiHV + tolerance, TVS and ADC range, at / just below / just above 62.5 V, full scale, refused from the first tick, "over 66.0 V", cannot arm (guard, ON, BIND, guard cycle), rocker ignored, latched until VIN < 2.5 V (not by a lower reading), ON needs OFF after clearing, 15S end to end (nothing ever on), 16S saturating the ADC, 14S at 4.46 V/cell not refused, clears on unplug (USB) then a good pack goes live, clears by going dark, guard does not clear it, rise while live cuts the same tick, no pack question |
