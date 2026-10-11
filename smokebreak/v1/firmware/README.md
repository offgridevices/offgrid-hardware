# SmokeBreak v1 firmware — reference model

`model/` is a Python reference implementation of every decision the STM32C071
firmware makes. It is written to port 1:1 to C: integer units in the names
(`_mv`, `_ma`, `_ms`, `_mohm`, `_uj`, `_dc` = deci-°C), C-style truncating
division (`inputs.idiv`), no floats in the decision path, no dynamic
dispatch, fixed-size history. `sim_world.py` is test equipment only (floats,
never ported).

```
cd smokebreak/v1/firmware
python -m pytest -q          # 227 tests, ~15 s
```

Reference documents: `../ARCHITECTURE.md` (the board), `../../SPEC.md`
(§4 stages, §5 protection, §6 UI, §7 memory), `../../ui/screens.py` (S00–S18).

## Module map

| Module | What it decides | C unit / where it runs |
|---|---|---|
| `inputs.py` | `Inputs`: one sample of the world (VIN, VOUT signed, VOUT_low, INA290 current, peak/short trip flags, 8 balance taps, 2 NTCs, hall, toggle, rocker, VBUS). `aux_powered()`: would the diode-OR wake the MCU. | `sb_inputs_t`, filled by the ADC/DMA and GPIO layer before each control tick |
| `probe.py` | 3 V probe verdict: SHORT / HALF_SHORT (with Ω) / REVERSED / OPEN / OK (with µF). All thresholds are module constants. | `probe.c`, pure function over three DMA'd sample buffers |
| `precharge.py` | Pre-charge supervisor: PASS at 75 % of VIN; ABORT on stall, 1 s timeout, energy per attempt, energy per minute, hot resistor, input collapse. Picks RPRE from VIN. | `precharge.c`, stepped from the 1 kHz control task |
| `limits.py` | AUTO limit, 200 ms average limiter (20 × 10 ms buckets), peak comparator threshold (4 × setting, ≤ 40 A), rocker with 25 A confirm (400 ms dead time, 3 s window, 60 s motor test). | `limits.c`; the bucket accumulator lives in the ADC ISR |
| `battery.py` | Cell count from VIN (with ambiguity flag), balance-lead decoding (shift, broken wire, other pack, count/sum mismatch), per-cell warnings, delta verdict, SoC from OCV tables (LiPo, LiHV), storage hint, IR from ΔV/ΔI. | `battery.c`, 10 Hz task |
| `memory.py` | 32 drone profiles keyed by cell count + capacitance (±15 %), idle at 10 s, idle-up and capacitance-down warnings, LRU replacement. | `memory.c`, one flash page, wear-levelled |
| `machine.py` | The state machine: STARTUP, SAFE, ARMED, CHECKING, PRECHARGE, ENGAGING, LIVE, WARNING, ABORT, BIND, POWER_CUT; overlays S11/S13. Per tick: switch commands, screen (S-number + data), ring colour, beep. | `machine.c`, the 1 kHz control task |
| `sim_world.py` | Plant: pack (cells + IR), balance lead (shift, broken wires, other pack), drone (caps, leakage, 1S FC, shorts, reversed diodes, regulators, constant-power VTX, voltage-dependent fault, motor demand, its own battery), board (probe, RPRE, slow-gate switch, INP AND gate, comparator and driver latches, thermal). `Rig` gives tests human verbs. | not ported |

## Mapping to the C firmware

| Context | Rate | Work |
|---|---|---|
| ADC ISR (DMA half/full) | INA290 at 10 kHz (TIM-triggered, oversampled ×4) | add samples into the current 10 ms bucket (`AverageLimiter.add`), track window peak |
| ADC scan, DMA | 1 kHz: VIN, VOUT-high, VOUT-low (×16 oversampled); 100 Hz: BAL1–8, NTC×2, VREFINT, IMON | fills `sb_inputs_t` |
| Probe capture | VOUT-low at 1 kHz into three buffers (50 + 250 + 50 samples) while CHECKING | `probe_classify()` at the end |
| Control task | 1 kHz (SysTick) | `machine_step()`: guard rule first, then the state handler, then outputs |
| Battery task | 10 Hz | `battery_analyse()` (the model runs it every tick; result is identical) |
| UI task | 30 Hz | draws `Outputs.screen` (ST7789 over SPI DMA), ring LEDs, beeper patterns |
| GPIO | EXTI on hall + toggle, 1 kHz scan for debounce (rocker 20 ms) | debounced levels into `sb_inputs_t` |
| Hardware, no firmware | ≤ 5 µs / ≤ 1.2 µs | peak comparator pulls INP low (threshold = `Outputs.peak_threshold_ma` via PWM+RC); TPS48111 short trip; hall gates INP |
| Flash | on change | drone memory page; energy ledger stays in RAM |

Outputs per tick: `precharge_on` (QP gate), `main_on` (MCU_EN into the INP
AND gate), `probe_src` (OFF / 1 kΩ / 100 Ω P-FETs), `divider_en` (balance
divider ground FET), `rpre_mohm` (bank select), `peak_threshold_ma`,
`screen`, `led`, `beep` (one-shot), `beep_loop` (abort alarm).

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
   the guess for anything dangerous: RPRE comes from VIN, 1S rules can't be
   confused with 2S.
10. **Two RPRE banks** (SPEC §4: ~2 Ω ≤ 7S, ~22 Ω above, switch at 30.45 V),
    although ARCHITECTURE §2.1 lists only 22 Ω.
11. **Battery reversed on the input** is dark (ARCHITECTURE §4); SPEC §4
    stage 0 says the screen explains it, which the hardware cannot do (VIN
    reads 0, the aux OR blocks).

## Findings for the hardware/spec

- **RPRE energy**: 5000 µF + a 15 W VTX at 14S puts **~17 J** into RPRE (the
  VTX current flows through it too), not the 9.3 J of SPEC §14.1. Budgets set
  to 20 J per attempt, 45 J per minute.
- **22 Ω at 8S** delivers only ~9.6 W at 75 % of VIN, so a 10–15 W VTX that
  starts part-way up stalls (SPEC §4 claims it passes). A middle bank (~8 Ω)
  or a higher switch point is needed. `test_8s_with_15w_vtx_stalls...`
  documents it.
- The pre-charge FET is MCU-driven only; the guard does not gate it in
  hardware. Recommend ANDing QP's drive with the hall output too.
- SPEC example "Pack sags 1.9 V at 10 A — 95 mΩ" is inconsistent
  (1.9 V / 10 A = 190 mΩ).

## Tests (227)

| File | Count | Covers |
|---|---|---|
| `test_probe.py` | 28 | shorts 0.01–0.8 Ω, half-shorts 2–140 Ω (±10 %), half-short behind 5000 µF, reversed with 10–4700 µF, open, capacitance 20–10 000 µF (±10 %), 1S FC rule, no-big-cap rule |
| `test_precharge.py` | 13 | RPRE choice, 6S pass, 14S 5000 µF in budget, VTX part-way up, stall at higher voltage (V and A reported), timeout, energy per attempt, per minute + recovery, hot resistor, collapse |
| `test_limits.py` | 22 | AUTO table, peak 4× and clamp, ESC tones pass, sustained trip, rocker steps, 25 A confirm, 60 s timeout, 3 s confirm timeout, mashing (4 rates), dead-time cancel, minus, both halves |
| `test_battery.py` | 81 | 1–14S full LiPo/LiHV, storage 1–7S, 9–14S ambiguity flag, balance 1–8S, LiHV vs LiPo, over-charged LiPo vs over-charged, plug shift 1–3 pins, other pack (same/different count), sum mismatch at 2 %, broken mid/top wire, delta verdict boundaries, low/high marks, over-discharged, dead cell, SoC tables, storage hint, balance-only, IR dI minimum |
| `test_memory.py` | 8 | ±15 % match, cell key, closest wins, idle-up thresholds, cap-down, LRU at 32, export |
| `test_flow.py` | 30 | S00→S01, S02→S06 order with LEDs/beeps, nothing powered during check, toggle off, guard close live/mid-precharge/mid-check, flick on with guard closed, toggle held on through guard cycle, bind mid-check, bind cycles (<2 s each, then stays on), bind needs guard, S13/S11 overlays, 25 A live + 60 s, confirm timeout, mashing live, guard ends motor test, rocker ignored in abort, fault latch, start-up with toggle on, battery swap, average/peak/driver trips, over-temp, stall, energy budget at 14S |
| `test_wiring.py` | 22 | every ARCHITECTURE §4 row (reversed input with/without USB, battery on drone side, both sides, reversed on drone side, drone backwards, short, half-short, plug shifted, balance alone shifted = dark, other pack, deeply discharged, over-charged, high IR, collapse, USB while live), USB only, §3 screens S14/S15/S16 |
| `test_packs.py` | 23 | 1–14S end to end, 1S/new-drone AUTO, 14S 5000 µF + VTX, 8S + 15 W VTX stall, memory: same → draws more, cap broke off, no big cap, residual-charge re-power, unknown charged drone |
