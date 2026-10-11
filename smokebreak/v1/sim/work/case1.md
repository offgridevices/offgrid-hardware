### (a) 8S-14S, 2200 µF + 15 W VTX (+1 W FC/RX)

Requirement: VOUT > 75 % of VIN within 1 s for every 8S-14S pack at 3.7, 3.85, 4.2 and 4.35 V/cell. 3.5 V/cell (nearly empty) is also simulated; a stall there is handed to the (b) path (close the main switch from the stall).

| RPRE | (a) requirement | slowest t75 (req. set) | stalls below 75 % (any V/cell) |
|---|---|---|---|
| 6.8 Ω | PASS | 53 ms | - |
| 8.2 Ω | PASS | 99 ms | 8S@3.5 |
| 10 Ω | **FAIL** | never | 8S@3.5, 8S@3.7, 8S@3.85, 9S@3.5, 9S@3.7 |
| 15 Ω | **FAIL** | never | 8S@3.5, 8S@3.7, 8S@3.85, 8S@4.2, 8S@4.35, 9S@3.5, 9S@3.7, 9S@3.85, 9S@4.2, 9S@4.35, 10S@3.5, 10S@3.7, 10S@3.85, 10S@4.2, 10S@4.35, 11S@3.5, 11S@3.7, 11S@3.85, 11S@4.2, 12S@3.5, 12S@3.7, 12S@3.85, 13S@3.5 |
| 22 Ω | **FAIL** | never | 8S@3.5, 8S@3.7, 8S@3.85, 8S@4.2, 8S@4.35, 9S@3.5, 9S@3.7, 9S@3.85, 9S@4.2, 9S@4.35, 10S@3.5, 10S@3.7, 10S@3.85, 10S@4.2, 10S@4.35, 11S@3.5, 11S@3.7, 11S@3.85, 11S@4.2, 11S@4.35, 12S@3.5, 12S@3.7, 12S@3.85, 12S@4.2, 12S@4.35, 13S@3.5, 13S@3.7, 13S@3.85, 13S@4.2, 13S@4.35, 14S@3.5, 14S@3.7, 14S@3.85, 14S@4.2, 14S@4.35 |
| 33 Ω | **FAIL** | never | 8S@3.5, 8S@3.7, 8S@3.85, 8S@4.2, 8S@4.35, 9S@3.5, 9S@3.7, 9S@3.85, 9S@4.2, 9S@4.35, 10S@3.5, 10S@3.7, 10S@3.85, 10S@4.2, 10S@4.35, 11S@3.5, 11S@3.7, 11S@3.85, 11S@4.2, 11S@4.35, 12S@3.5, 12S@3.7, 12S@3.85, 12S@4.2, 12S@4.35, 13S@3.5, 13S@3.7, 13S@3.85, 13S@4.2, 13S@4.35, 14S@3.5, 14S@3.7, 14S@3.85, 14S@4.2, 14S@4.35 |
| 47 Ω | **FAIL** | never | 8S@3.5, 8S@3.7, 8S@3.85, 8S@4.2, 8S@4.35, 9S@3.5, 9S@3.7, 9S@3.85, 9S@4.2, 9S@4.35, 10S@3.5, 10S@3.7, 10S@3.85, 10S@4.2, 10S@4.35, 11S@3.5, 11S@3.7, 11S@3.85, 11S@4.2, 11S@4.35, 12S@3.5, 12S@3.7, 12S@3.85, 12S@4.2, 12S@4.35, 13S@3.5, 13S@3.7, 13S@3.85, 13S@4.2, 13S@4.35, 14S@3.5, 14S@3.7, 14S@3.85, 14S@4.2, 14S@4.35 |

Time to 75 % with RPRE = 8.2 Ω:

| pack | 3.5 V/cell | 3.7 V/cell | 3.85 V/cell | 4.2 V/cell | 4.35 V/cell |
|---|---|---|---|---|---|
| 8S | stall 6.1 V (22 %) | 99 ms | 79 ms | 59 ms | 54 ms |
| 9S | 72 ms | 60 ms | 55 ms | 47 ms | 44 ms |
| 10S | 54 ms | 48 ms | 45 ms | 41 ms | 39 ms |
| 11S | 45 ms | 42 ms | 41 ms | 37 ms | 36 ms |
| 12S | 41 ms | 39 ms | 37 ms | 35 ms | 34 ms |
| 13S | 38 ms | 36 ms | 35 ms | 34 ms | 33 ms |
| 14S | 36 ms | 35 ms | 34 ms | 32 ms | 32 ms |

**Chosen RPRE = 8.2 Ω** (largest value meeting (a)). None of the requested values 10-47 Ω meets (a) at the low end (8S below ~4.2 V/cell): the binding limit is not the 75 % point but getting *past the VTX UVLO*. At VOUT = 6 V the VTX switches on and wants P/6 V; if (VIN − 6 V)/R is less than that, VOUT is trapped at the UVLO (the low equilibrium of a constant-power load). Condition: R < 6 V·(VIN − 6 V)/P_total (8S at 3.7 V/cell with 15 W + 1 W FC → R < 8.9 Ω; 14S LiHV → R < 21 Ω). The second condition, an operating point above 0.75·VIN, needs R ≤ 0.1875·VIN²/P and is less strict.


### (b) 2S-7S with 2200 µF + 10 W VTX: stall, then close the main switch slowly

Gate network (TI fig. 8-6): PU → R1 = 100 kΩ → gate, PD direct to gate, gate → R2 = 10 Ω + C1 (= 'Cdvdt') → GND, CBST = 2.2 µF. Output slew ≈ (12 V − Vth)/(R1·C1). The pre-charge stays on until the main switch has closed (it keeps feeding the VTX while the gate climbs). SOA assumed (single pulse, Tc 25 °C): 100 µs 2.5 kW, 1 ms 750 W (25 V × 30 A), 10 ms 200 W (25 V × 8 A), 100 ms 36 W (60 V × 0.6 A); pass = worst sliding-window average power ≤ 50% of that (Tc ≈ 80 °C, spread).

C1 sweep at the worst gap (7S LiHV, 30.45 V, stalled at the VTX UVLO):

| C1 | Cload | stall | close time | Q1 peak I | Q1 peak P | Q1 energy | worst % of derated SOA | SOA |
|---|---|---|---|---|---|---|---|---|
| 47 nF | 2200 µF | 75 % reached | 17 ms | 4.2 A | 17 W | 0.03 J | 4 % | PASS |
| 47 nF | 5000 µF | 75 % reached | 17 ms | 9.0 A | 39 W | 0.09 J | 10 % | PASS |
| 100 nF | 2200 µF | 75 % reached | 35 ms | 2.2 A | 7 W | 0.03 J | 3 % | PASS |
| 100 nF | 5000 µF | 75 % reached | 35 ms | 4.5 A | 19 W | 0.08 J | 8 % | PASS |
| 150 nF | 2200 µF | 75 % reached | 53 ms | 1.6 A | 5 W | 0.02 J | 2 % | PASS |
| 150 nF | 5000 µF | 75 % reached | 53 ms | 3.2 A | 12 W | 0.07 J | 7 % | PASS |
| 220 nF | 2200 µF | 75 % reached | 77 ms | 1.2 A | 3 W | 0.02 J | 2 % | PASS |
| 220 nF | 5000 µF | 75 % reached | 77 ms | 2.3 A | 8 W | 0.06 J | 5 % | PASS |
| 330 nF | 2200 µF | 75 % reached | 116 ms | 0.9 A | 2 W | 0.02 J | 2 % | PASS |
| 330 nF | 5000 µF | 75 % reached | 116 ms | 1.7 A | 5 W | 0.05 J | 4 % | PASS |

**Chosen C1 (Cdvdt) = 100 nF** with R1 = 100 kΩ (CBST ≥ Qg + 10·C1 → 2.2 µF).

| pack | VTX | pre-charge result | main close | Q1 peak I | Q1 peak P | E(Q1) / E(Q2) | worst % of derated SOA | result |
|---|---|---|---|---|---|---|---|---|
| 2S @ 3.5 | 10 W | stall 4.8 V (68 %) | 11 ms | 3.5 A | 3 W | 0.01 J / 0.004 J | 1 % | PASS |
| 2S @ 4.35 | 10 W | stall 5.9 V (68 %) | 13 ms | 3.3 A | 7 W | 0.02 J / 0.003 J | 2 % | PASS |
| 3S @ 3.5 | 10 W | stall 6.0 V (57 %) | 15 ms | 3.1 A | 12 W | 0.04 J / 0.003 J | 3 % | PASS |
| 3S @ 4.35 | 10 W | stall 6.0 V (46 %) | 18 ms | 2.9 A | 18 W | 0.08 J / 0.004 J | 8 % | PASS |
| 4S @ 3.5 | 10 W | stall 6.0 V (43 %) | 19 ms | 2.7 A | 20 W | 0.10 J / 0.004 J | 10 % | PASS |
| 4S @ 4.35 | 10 W | stall 6.0 V (35 %) | 22 ms | 2.5 A | 25 W | 0.17 J / 0.004 J | 15 % | PASS |
| 5S @ 3.5 | 10 W | stall 6.0 V (34 %) | 22 ms | 2.5 A | 25 W | 0.17 J / 0.004 J | 16 % | PASS |
| 5S @ 4.35 | 10 W | stall 6.1 V (28 %) | 27 ms | 2.4 A | 26 W | 0.25 J / 0.004 J | 19 % | PASS |
| 6S @ 3.5 | 10 W | stall 6.1 V (29 %) | 26 ms | 2.4 A | 27 W | 0.24 J / 0.004 J | 19 % | PASS |
| 6S @ 4.35 | 10 W | 75 % at 68 ms | 31 ms | 2.3 A | 8 W | 0.03 J / 0.002 J | 3 % | PASS |
| 7S @ 3.5 | 10 W | 75 % at 92 ms | 29 ms | 2.3 A | 9 W | 0.04 J / 0.002 J | 4 % | PASS |
| 7S @ 4.35 | 10 W | 75 % at 48 ms | 35 ms | 2.2 A | 7 W | 0.03 J / 0.001 J | 3 % | PASS |
| 8S @ 3.5 | 15 W | stall 6.1 V (22 %) | 34 ms | 2.4 A | 38 W | 0.44 J / 0.005 J | 27 % | PASS |

### (c) Energy in RPRE per attempt

| case | peak I(RPRE) | peak P(RPRE) | energy per attempt | main enabled at |
|---|---|---|---|---|
| 14S LiHV, 2200 µF, 15 W | 7.27 A | 434 W | 4.74 J | 32 ms |
| 6S LiHV, 5000 µF, 10 W | 3.09 A | 78 W | 3.15 J | 155 ms |
| 14S LiHV, 5000 µF, 15 W (worst) | 7.27 A | 434 W | 10.65 J | 73 ms |

A failed attempt is worse: with a fault that clamps the drone near 0 V the resistor sees 439 W at 14S LiHV, i.e. 439 J if the firmware waited the full 1 s. The firmware must therefore integrate (VIN−VOUT)²/RPRE and abort at an energy budget of 12 J (reached after 27 ms of a dead clamp), in addition to the 1 s timeout and the stall rule.

**RPRE pulse rating required:** ≥ 24 J single pulse in ≤ 100 ms (2 × the 12 J budget; normal worst case 10.6 J), peak 452 W, ≥ 100 V working voltage, through-hole ceramic-composition (bulk) or pulse-rated wirewound; NTC beside it gates the next attempt.
