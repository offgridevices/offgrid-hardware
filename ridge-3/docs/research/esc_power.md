> Research notes written while designing Ridge 3 (September 2026; the working name was OG3).
> Prices and stock are as found on the dates given and will have moved. The design decisions they led to
> are in `src/circuit.py` and `src/parts.py`; where the two disagree, the code is current.
>
> Later changes, made while laying the ESC out (the code has them):
> - **No TVS on the ESC.** The bulk and bridge capacitors across the battery pads absorb
>   the lead-inductance spike, and the flight controller's SMF33A sits on the same battery
>   line through the stack lead.
> - **No 4.7 uF per MCU.** Each G071 keeps its 100 nF at VDD; the bulk ST asks for is the
>   3.3 V buck's shared 10 uF output capacitor.
> - **Back-EMF and neutral dividers:** 20k/2k per phase; the virtual neutral is 30k from
>   each phase to a star with 1k to ground. The neutral then scales like the phases
>   (1k / (10k + 1k) = 2k / 22k).
> - **One SWD clock pad per MCU.** Each channel has its own `Cn` (SWCLK) pad beside its
>   `Dn` (SWDIO) pad. A clock shared by all four MCUs had to run through every other
>   channel to reach each one.
> - **Gate-drive tracks 0.12 mm, switch-node sense 0.15 mm.** Every one crosses the FET
>   row in the corridors between the phases. 10 mm of 0.12 mm copper adds about 0.04 ohm
>   to a gate loop that already has a 10 ohm resistor.
> - **One return via per corridor, not two.** The corridors pass the gate, sense, back-EMF,
>   neutral and SWD lines across the FET row. A centred via leaves room for a track on
>   each side of it. The return's bottom and In3 pours are still tied by these vias and
>   the five at the shunt. In3 is needed: the low-side gate stubs cut the bottom pour at
>   every corridor.

# OG3 ESC: power stage, gate drive, MCU and current sensing (research notes)

Date: 2026-09-27. Scope: the next 4-in-1 ESC for the Cheap Drone stack
(`cheap-drone-stack/v1`, 33.8 x 33.8 mm, 25.5 mm M3 pattern, AM32). **Nothing
was ordered or bought.** No repo file was edited.

How the numbers were obtained:

- **LCSC stock and prices**: LCSC's own product-detail API
  (`wmsc.lcsc.com/ftps/wm/product/detail?productCode=Cxxxx`, the same data the
  `lcsc.com/product-detail/Cxxxx.html` pages show), fetched 2026-09-27, USD, at
  the 1 / 100 / 1000 price ladder. JLCPCB's parts API
  (`jlcpcb.com/api/.../selectSmtComponentList`) was used for searching; its stock
  differs from LCSC's by a few percent on some lines.
- **DigiKey**: digikey.com returns a Cloudflare 403 to scripted fetches (tried
  search and product pages). DigiKey part numbers, stock and price breaks below
  come from **findchips.com's DigiKey feed** (fetched 2026-09-27). Treat every
  DigiKey number as *not verified at DigiKey itself*. Several commodity
  Samsung/Murata MLCC lines read "0 in stock" in that feed, which may be a feed
  artefact.
- **AM32**: source read at `am32-firmware/AM32` commit `55c9684` (v2.21, 25 Sep
  2026) and `am32-firmware/AM32-bootloader` commit `578ff29`. Line numbers below
  refer to those commits.
- Datasheets were downloaded and read (TI, Infineon, ST, ADI/Maxim, MCC,
  Toshiba). Numbers read off graphs are marked "(graph)".
- The loss and thermal calculator is
  `tools/losses.py`; the sourcing script is
  (a working file, not kept) (output `final_parts.json`).

---

## 0. Bottom line

1. **The 60% rule forces 60 V FETs at 6S.** 25.2 V is 63% of a 40 V part
   before any switching spike. At 60 V the bus is 42%, and 58% with a 10 V spike.
2. **Recommended FET: Infineon BSZ040N06LS5** (60 V, 4.0 mOhm max at 10 V,
   ~5.3 mOhm max at 100 degC (graph), PG-TSDSON-8 FL 3.3 x 3.3 mm). You need 24
   single FETs. No 60 V dual/half-bridge part in a 3 x 3 mm package is both in
   stock and low enough in resistance.
   **Alternate: MCC MCG60N06YHE3-TP** (60 V, 6.0 mOhm max, 175 degC, 3.3 x 3.3 mm).
   It is about 50% lossier.
3. **Gate driver: TI DRV8300DRGER.** It has the **same 24-pin 4x4 pinout as the
   FD6288Q/JSM6288Q on v1**, active-high HIN/LIN (MODE pin floating), integrated
   bootstrap diodes, GVDD UVLO at 4.35 V falling, and a 100 V bridge side. GVDD
   is limited to 20 V, so at 5S/6S it needs a regulated rail: one **TI
   TPS7A4101** LDO set to 11.5 V feeds all four drivers (25 mA worst case).
4. **ESC MCU: STM32G071GBU6** (or the 64 KB STM32G071G8U6 on the same pads).
   It is a 4x4 QFN28, has the most mature AM32 support after the F051, and the
   stock **GEN_64K_G071** target (hardware group G0_A) runs it unchanged. **The
   sourcing rule is not met**: LCSC has 1168 + 1305, but DigiKey has only 19-79.
   No AM32-supported ST part is well stocked at both distributors, except the
   STM32G431KBU6 at about 3x the price with thin AM32 support.
5. **Current sense:** per channel, a 0.5 mOhm 2512 shunt (Yageo
   PU2512FKGP60U5L) in the bridge return feeding a TI INA180A3 (100 V/V). That
   gives **50 mV/A** into PA5. Full scale is 66 A and one ADC count is 16 mA.
   It needs a one-line custom AM32 target (`MILLIVOLT_PER_AMP 50`). Stock
   GEN_64K_G071 would read 2.5x high, which errs on the safe side.
6. **3.3 V for the four MCUs: ADI MAX15062AATA+T** (60 V in, 300 mA, fixed
   3.3 V, 2x2 mm) with a 33 uH inductor. **TVS: Littelfuse SMAJ28A. Bridge
   decoupling: Murata GRM31CZ72A475KE11L** (4.7 uF, 100 V, X7R 1206). **Bulk
   (on the lead): 2 x Rubycon 50ZLH100MEFC8X11.5** (50 V).
7. **The board cannot meet 4 motors x 20 A for 60 s with poor airflow.** Each
   part meets 60% if the board is held at 100 degC; the board cannot be held
   there. At 6S and 20 A the four channels dissipate **~24 W** (27 W with
   AM32's stock dead time). A 33.8 mm board sheds about **2.6 W in still air,
   ~6 W with some airflow and ~10 W in strong prop wash** at 100 degC and 25 degC
   ambient. The sustainable currents at a 100 degC board are:
   - **~5 A per motor** in still air
   - **~9 A** with some airflow
   - **~12 A** in strong prop wash

   No FET that fits changes this materially. Even 5x6 mm 1.6 mOhm parts (which
   do not fit 24-up) would still dissipate ~13 W. The owner's XING2 1404 case
   (4S, 4 x 15.8 A, 60 s) dissipates ~15 W and reaches ~107 degC in strong
   prop wash, ~130 degC with little airflow. Normal flying with short punch-outs
   is fine. Enforce the limit in firmware: per-channel current limit, AM32
   temperature limit and stuck-rotor protection.
8. **Area:** the part set fits on 33.8 x 33.8 mm on paper. The courtyard-area
   estimate is ~63% of both sides, against 46% measured on v1. It does so only
   with the three high-side FETs of each channel moved to the top side, stacked
   over their low-side partners. **This is an estimate, not a placement.**
9. Side finding: the **v1 ESC BOM's 10 uF 50 V 0805 (C2932476,
   CL21A106KBYQNNE, 13 per board) now shows 0 in stock at LCSC**.

---

## 1. How the 60% rule was applied

| Quantity | Rule used |
|---|---|
| Voltage (VDS, VIN, cap rating, VGS) | Worst operating voltage <= 60% of the absolute or recommended maximum. 6S full = 25.2 V; spike allowance +10 V at the FETs with local ceramics. |
| Current | Sustained <= 60% of the rating at the stated temperature (for FETs, ID at Tc = 100 degC). |
| Power | Dissipation <= 60% of the rating derated to 100 degC case/board. |
| Junction temperature | A literal 60% of Tj,max (90 degC for a 150 degC part) is below the assumed 100 degC board, so it cannot be met by any part. **Used instead: the rise above the 100 degC board is <= 60% of the headroom** (Tj,max - 100 degC). That means Tj <= 130 degC for 150 degC parts and <= 145 degC for 175 degC parts. |
| Logic supply rails (MCU 3.3 V, INA180 3.3 V) | Exempt. They run at their nominal voltage by design. |
| TVS stand-off | Exempt by nature: a TVS must sit just above the maximum battery voltage. 60% is applied to its surge power instead. |

---

## 2. Power MOSFETs

### 2.1 40 V vs 60 V at 6S

| Class | 25.2 V DC | 25.2 V + 10 V spike | Verdict |
|---|---|---|---|
| 30 V (v1 AON7934) | 84% | 117% | no |
| 40 V (e.g. Toshiba TPN2R304PL) | **63%** | 88% | fails the rule at DC |
| 60 V | **42%** | **58%** | passes |
| 80-100 V | 25-32% | 35-44% | passes, but RDS(on) and Qrr roughly double for the same die area |

The industry does not apply this rule. FETtec's 3-6S 4in1 45A states "High
quality 40V MOSFETs" ([fettec.net][fettec]). The 60 V choice costs conduction
loss: at the same 3.3 x 3.3 mm size, the best 60 V part in stock (4.0 mOhm)
has ~1.7x the resistance of the best 40 V part (Toshiba TPN2R304PL, 2.3 mOhm
max).

### 2.2 Dual/half-bridge packages vs single FETs

v1 used 12 dual half-bridges (AON7934, 30 V). None of the 60 V duals is usable:

- **Nexperia LFPAK56D duals** (BUK9K13-60E, BUK7K13-60E, BUK9K17-60E): 5x6 mm, 10-17 mOhm, 0-2 in stock at LCSC.
- **Vishay SiZ250DT** (60 V dual, PowerPAIR 3.3x3.3): 12.7 mOhm, about 3x the recommended single FET's resistance.
- **ST STL50DN6F7** (60 V dual, 5x6): 9 mOhm.
- **Infineon BSC155N06ND** (60 V dual, 5x6): 15.5 mOhm.
- **TI CSD88599Q5DC** (60 V half-bridge power block, 5x6): very low resistance, but listed at about $15.5 at LCSC (358 pcs), which looks like a pricing anomaly. It is also 5x6 mm.
- **Infineon IAUC60N04S6N050H** (40 V half-bridge, 4499 at LCSC): 40 V only.

So OG3 uses **24 single N-FETs in 3.3 x 3.3 mm**. Sources: LCSC listings,
searched via the JLC API on 2026-09-27.

### 2.3 Candidates (60 V unless noted)

| Part | Maker (country) | RDS(on) max at 10 V, 25 degC | RDS(on) max at 100 degC | Qg (0-10 V) | Qgd | Qrr | Package | RthJC | Tj max |
|---|---|---|---|---|---|---|---|---|---|
| **BSZ040N06LS5** | Infineon (DE) | **4.0 mOhm** (3.3 typ) | **~5.3** (graph, Diagram 9); ~6.0 at 125 degC | 32 typ / 42 max (Qg,sync) | 5.3 / 8.0 (0-4.5 V) | 11 / 22 nC | PG-TSDSON-8 FL, 3.3x3.3 | 1.1 / 1.8 K/W | 150 degC |
| BSZ042N06NS | Infineon (DE) | 4.2 | similar | 27 / 32 | 5 / 7 | 33 | TSDSON-8 3.3x3.3 | 1.8 | 150 |
| **MCG60N06YHE3-TP** | MCC (US) | 6.0 (4.6 typ) | ~9.0 (graph: x2.0 at 175 degC) | 34.5 typ | 9.2 | 32 | DFN3333 | 2.5 | **175** |
| CSD18543Q3A | TI (US) | 9.9 (8.1 typ) | ~14 (est.) | 11.1 / 14.5 | 1.7 | 37 | VSONP 3.3x3.3 | 1.9 | 150 |
| TPN4R806PL | Toshiba (JP) | ~3.5-4.8 (LCSC listing; max not checked) | - | 29 | - | - | TSON Advance 3.1x3.1 | - | 175 |
| NTTFS5C658NL | onsemi (US) | 4.2 | - | - | - | - | WDFN-8 3.3x3.3 | - | 175 |
| TPN2R304PL (**40 V**, reference) | Toshiba (JP) | 2.3 (1.8 typ) | ~3.3 | 41 | 6.2 | 30 | TSON Advance | 1.43 | 175 |
| AON7934 (v1, **30 V**) | AOS (US) | 10.2 / 7.7 (HS / LS) | - | 8-11 | - | - | DFN3x3 dual | - | 150 |

Datasheets:

- [BSZ040N06LS5 (LCSC mirror)][bsz040]: Table 2, Table 3, Table 4, Table 6, Table 7 and Diagram 9. ID is 64 A at Tc = 100 degC and Ptot is 69 W at Tc = 25 degC.
- [BSZ042N06NS][bsz042]
- [MCG60N06YHE3][mcg]: ID is 42 A at Tc = 100 degC; RDS(on) vs Tj is in Fig. 3.
- [CSD18543Q3A][csd]
- [TPN2R304PL][tpn2r3]

The TPN4R806PL and NTTFS5C658NL rows are from LCSC listings only.

Sourcing (full table in section 11):

| Part | LCSC | LCSC stock | LCSC $ 1/100/1k | DigiKey PN | DK stock | DK $ 1/100/1k |
|---|---|---|---|---|---|---|
| **BSZ040N06LS5ATMA1** | [C3279309][l-C3279309] | 4,990 | 1.52 / 0.94 / 0.84 | 448-BSZ040N06LS5ATMA1CT-ND | 891 | 2.14 / 0.92 / 0.73 |
| **MCG60N06YHE3-TP** | [C26691506][l-C26691506] | 2,062 | 0.83 / 0.69 / 0.65 | 353-MCG60N06YHE3-TPCT-ND | 4,589 (9,589 on reel) | 2.22 / 0.95 / 0.76 |
| BSZ042N06NSATMA1 | C3279304 | 514 | 2.30 / 1.39 / 1.22 | BSZ042N06NSATMA1CT-ND | 0 | - |
| CSD18543Q3A | [C840100][l-C840100] | 12,891 | 0.80 / 0.51 / 0.45 | 296-47321-1-ND | 59,345 | 1.29 / 0.53 / 0.41 |
| TPN4R806PL,L1Q | C5986858 | 15 | 2.13 | 264-TPN4R806PLL1QCT-ND | 12,673 | 1.68 / 0.71 / 0.56 |
| NTTFS5C658NLTAG | C900358 | 0 | - | 488-NTTFS5C658NLTAGCT-ND | 758 | 1.36 / 0.56 / 0.44 |
| TPN2R304PL,L1Q (40 V) | C5802634 | 2,575 | 0.89 / 0.54 / 0.46 | TPN2R304PLL1QCT-ND | 50,515 | 1.64 / 0.69 / 0.54 |

Stock limits:

- **BSZ040N06LS5**: 24 per board, so LCSC's 4,990 covers **~207 boards** and DigiKey's 891 covers ~37.
- **MCG60N06YHE3**: LCSC covers ~86 boards.

For volume, reserve stock or buy reels.

Notes on the MCC alternate:

- MCC is a US company (Simi Valley, CA). Where its fab is located was not checked.
- MCC's DFN3333 and Infineon's TSDSON-8 FL are both the common 3.3 x 3.3 "S S S G / D D D D + drain tab" pinout. **Check the two land patterns against each other before calling them drop-in** (not verified).

### 2.4 Loss model and results

AM32 PWM frequency (source):

- The default nominal PWM is **24 kHz**: `NOMINAL_PWM 24000U` sets `TIM1_AUTORELOAD` ([targets.h L5751-5759][t-nom]).
- The EEPROM `pwm_frequency` (default 24, range 8-144 kHz) rescales it ([main.c L637-644][m-pwm]).
- With **variable PWM = 1 (default)**, the period is mapped from `TIMER1_MAX_ARR` (24 kHz) at low rpm to `TIMER1_MAX_ARR/2` (**48 kHz**) at high rpm ([main.c L1977-1979][m-var]).
- The defaults are listed in the DroneCAN parameter table: VARIABLE_PWM 1, PWM_FREQUENCY 24, COMP_PWM 1, CURRENT_LIMIT 0, STUCK_ROTOR_PROTECTION 1 ([DroneCAN.c L169-187][dc]).
- Worst case for switching loss is therefore **48 kHz at full throttle**.
- Maximum duty is ~95-97.5%, so the bridge still switches at full throttle.

Model per motor (6-step, complementary PWM, synchronous rectification):

- **Conduction**: 2 x I^2 x R(Tj). Two FETs are always in the current path, whatever the duty.
- **Switching**: (V x I x t_edge + V x (Qrr + Qoss)) x f. The DRV8300D limits
  SHx slew to **2 V/ns** (rec. operating conditions, [DRV8300 7.3][drv8300]), so
  t_edge = V / (2 V/ns) + 5 ns, which is 17.6 ns per edge at 25.2 V.
  Qrr = 30 nC is used; this is above the datasheet's 22 nC max at 100 A/us.
- **Dead-time diode**: 2 x t_dt x f x VSD x I, with VSD = 0.7 V hot (graph).
  - AM32 G071 dead time is `DEAD_TIME` / 64 MHz: GEN_64K_G071 uses 60, which is **938 ns**.
  - The DRV8300 adds its own 215 ns typical ([DRV8300 7.5][drv8300]).
  - 20 counts = 313 ns is suggested for a custom target, pending a scope check.
- **Shunt**: (0.95 x I)^2 x 0.5 mOhm.
- **Gate charge**: 2 x Qg x 11.5 V x f.
- **Hottest FET**: the low side of the PWM leg, I^2 R/3 x (1 + (1 - D)) + P_dt/3.
- **Tj**: 100 degC + P_FET x (RthJC + 10 K/W). The 10 K/W local spreading into the
  planes through a via array is an **assumption**.

Results, BSZ040N06LS5 (R at 125 degC max = 6.0 mOhm):

| Case | Cond. | Sw. | Dead time | Shunt | Per motor | x4 | Hottest FET | Tj (board 100 degC) | Headroom used |
|---|---|---|---|---|---|---|---|---|---|
| 6S 25.2 V, 20 A, 48 kHz, stock DEAD_TIME 60 | 4.80 | 0.51 | 1.26 | 0.18 | **6.8 W** | **27.2 W** | 1.26 W | 115 degC | 30% |
| 6S 25.2 V, 20 A, 48 kHz, DEAD_TIME 20 | 4.80 | 0.51 | 0.42 | 0.18 | **6.0 W** | **23.8 W** | 0.98 W | 112 degC | 23% |
| 6S, 20 A, 24 kHz, DEAD_TIME 20 | 4.80 | 0.26 | 0.21 | 0.18 | 5.5 W | 21.9 W | 0.91 W | 111 degC | 21% |
| 6S, **30 A peak**, 48 kHz, DT 20 | 10.8 | 0.73 | 0.63 | 0.41 | **12.6 W** | 50.4 W | 2.10 W | 125 degC | 50% |
| **Owner: 4S 16.8 V, 15.8 A**, 48 kHz, DT 20 | 3.00 | 0.23 | 0.33 | 0.11 | **3.7 W** | **14.9 W** | 0.63 W | 108 degC | 15% |

For comparison, at 6S, 20 A, 48 kHz with DEAD_TIME 20:

| FET | Per motor | x4 | Tj |
|---|---|---|---|
| MCG60N06YHE3 | 9.1 W | 36 W | 119 degC |
| CSD18543Q3A | 13.4 W | 53 W | 127 degC |
| TPN2R304PL (40 V, fails the voltage rule) | 4.1 W | 16.5 W | - |
| Infineon BSC016N06NS (5x6 mm, 1.6 mOhm; does not fit 24-up) | 3.3 W | 13.2 W | - |

v1's AON7934 at 4S and 15 A was about 4 W per motor (README). OG3 with
BSZ040N06LS5 is slightly better than v1 at the owner's operating point, while
also being rated for 6S.

**60% check, BSZ040N06LS5, at the 6S 20 A worst case (board at 100 degC):**

| Quantity | Value | vs rating |
|---|---|---|
| VDS | 25.2 V DC / ~35 V with spike | **42% / 58%** of 60 V |
| VGS | 11.5 V (LS), ~10.7 V (HS) | **58% / 54%** of +/-20 V |
| ID | 20 A sustained / 30 A burst | **31% / 47%** of 64 A (Tc = 100 degC) |
| Power per FET | 1.0-1.3 W | ~5% of Ptot derated to Tc = 100 degC (69 W x 50/125 = 27.6 W) |
| Tj rise | +12-15 degC (20 A); +25 degC (30 A burst) | 24-30% / 50% of the 50 degC headroom |

The FET passes on every line. **The board does not; see section 3.**

### 2.5 Do 24 of them fit?

Measured with KiCad's `pcbnew` on the committed v1 ESC (courtyard bounding boxes):

- **Top**: 545 mm2, 48% of 1142 mm2. This includes 148 mm2 of mounting-hole keep-outs.
- **Bottom**: 506 mm2, 44%.
- **Both sides**: 1051 of 2285 mm2 (46%).

Changes for OG3 (courtyard estimates):

| Change | Area |
|---|---|
| Remove 12 x AON7934 | -154 |
| Add 24 x TSDSON-8 FL (~14.4 mm2 each) | +346 |
| QFN32 5x5 -> QFN28 4x4 MCU (x4) | -50 |
| Remove 16 x SOD-523 (bootstrap diodes now inside the DRV8300D; the zener clamp is gone) | -38 |
| 4 x 2512 shunt | +115 |
| 4 x INA180 + RC | +72 |
| GVDD LDO + parts | +38 |
| TVS (SMA) | +19 |
| Larger battery pads | +30 |
| 0805 -> 1206 bridge MLCCs | +26 |
| Buck change | ~0 |
| **Net** | **~+400 mm2 -> ~1450 mm2, ~63% of both sides** |

Geometry per edge:

- Between the hole keep-outs there is about 18.9 mm of free edge (holes at +/-12.75 mm, ~3.3 mm keep-out radius).
- Six 3.3 mm FETs in one row plus gaps need ~22 mm, so they do not fit on one side.
- Three FETs at v1's 5.2 mm pitch span 13.7 mm, which does fit.

The layout that fits is **high-side FETs on the top side at v1's FET positions,
low-side FETs directly under them on the bottom**, with the switch node joined
by a via field. The motor pads stay on top at the edge (v1: pads at yr 15.4 mm,
FET row at 12.15 mm; a 3.3 mm FET ends at 13.8 mm and the pad starts at 14.25 mm).

Costs of this layout:

- The top side loses v1's "passives only" role.
- The bridge MLCCs can no longer sit directly under the FETs on the opposite side.
- Via fields compete.
- Budget 2 oz inner copper (README already suggests it).

**Plausible, not placed.**

---

## 3. Board-level thermal: the binding constraint

Model (a first-order estimate; it has not been measured):

- Board plus parts heat capacity **~6.5 J/K**:
  - FR4 3.4 g x 1.1 J/gK
  - Six 1 oz layers at ~85% cover, 1.8 g Cu x 0.385 J/gK
  - ~2 g of parts
- Area **22.8 cm2** (both sides of 33.8 x 33.8 mm).
- h, convection plus radiation (ε ~0.9, which adds ~8 W/m2K at 100 degC):
  - **still air**: ~15 W/m2K
  - **some airflow**: ~35 W/m2K
  - **strong prop wash**: ~60 W/m2K (flat plate at ~5 m/s gives h ~ 50 before radiation)
- Ambient 25 degC. Wires, battery lead and the stacked FC are ignored. They add capacity and some conduction, but the FC also blocks airflow on the top side.

| Airflow | Board sheds at 100 degC | Time constant | Max sustained per motor (6S) | Max sustained per motor (4S) | 4x20 A 6S for 60 s from 40 degC | Owner 4x15.8 A 4S for 60 s from 40 degC |
|---|---|---|---|---|---|---|
| Still air | **2.6 W** | 190 s | **4.9 A** | 5.4 A | ~225 degC | ~154 degC |
| Some airflow | **6.0 W** | 81 s | **8.9 A** | 9.4 A | ~188 degC | ~129 degC |
| Strong prop wash | **10.3 W** | 47 s | **12.4 A** | 12.9 A | ~154 degC | **~107 degC** |

The 60 s temperatures assume DEAD_TIME 20 and 48 kHz.

Plain statement: on a 33.8 x 33.8 mm board, **the owner's worst case (4 x 20 A
for 60 s at 6S, poor airflow) cannot be met under the 60% rule, or at all**.
The 24 W has nowhere to go. Doubling the heat capacity to ~13 J/K still gives
~114 degC after 60 s in strong prop wash.

The 3-inch products that claim 35-55 A per motor (section 10) are quoting
burst ratings with airflow. To make the board honest:

1. Set the AM32 **current limit** per channel. It works once current sensing exists (section 6).
2. Set the AM32 **temperature limit** (70-140 degC). The brushless path derates maximum duty from limit-10 to limit+10 degC ([main.c L2244-2246][m-temp]), using the G071's internal sensor, which reads die temperature and is a proxy for board temperature.
3. Keep **stuck-rotor protection** on (default).
4. Order 2 oz inner copper.
5. Publish a rating such as "20 A burst / ~10 A continuous per motor in flight airflow".

---

## 4. Gate driver

### 4.1 Candidates

| Driver | Maker | Input polarity vs AM32 | Bootstrap diodes | Supply range / UVLO | Bridge-side rating | Package | AM32 precedent | LCSC stock | DK stock |
|---|---|---|---|---|---|---|---|---|---|
| **DRV8300DRGE** | TI (US) | INHx and INLx active-high with MODE floating (MODE has a pull-down), **same as FD6288**. MODE tied to GVDD inverts INLx. | **Integrated** (D variant) | GVDD 5-20 V (abs 21.5 V); UVLO 4.6 rising / 4.35 falling; BST UV 4.0 V typ, 4.5 V max falling | SHx 85 V op / 110 V abs; **SHx slew <= 2 V/ns for D variants** | VQFN-24 4x4, 0.5 mm, EP 2.45 mm | Same polarity as FD6288 targets; no inverted flags needed | **15,243** | **57,636** |
| DRV8300NRGE | TI | Same | External (SHx slew up to 50 V/ns) | Same | Same | Same footprint | Same | 8,533 | 12,932 |
| DRV8328A (RUY) | TI | 6x PWM, active-high | Integrated + trickle charge pump | **PVDD 4.5-60 V (65 V abs)**, internal GVDD charge pump **13 V (11.5-15.5)** down to 8 V, 2xPVDD-1.4 below 6.75 V; VDS OCP, OTSD, nFAULT, nSLEEP, DRVOFF | 65 V abs | WQFN-28 4x4, 0.4 mm | **ARK_4IN1_F051** (US-made ARK 4IN1) uses it: `USE_DRV8328_NSLEEP` PA15, `USE_DRV8328_NFAULT` PB5, 10 mV/A current sense ([targets.h L2316-2336][t-ark]). nSLEEP/nFAULT code exists only for F051 ([f051 peripherals.c][f051p]). | 924 | **84** |
| DRV8328C | TI | 6x | same, **plus 3.3 V 80 mA LDO**, no DT/VDSLVL pins | same | same | same | - | 36 | 10,835 |
| STDRIVE101 | ST (EU) | INxH/INxL | integrated, 12 V internal LDO | VS 5.5-75 V | 75 V | VFQFPN-24 4x4 | none found | 574 | 170 |
| MP6531A | MPS (US) | FD6288-like | charge pump | 5-60 V | 60 V | QFN-28 4x4 | `MP6531_F051` (dev target, F0_C) | 99 | 0 |
| 6ED2742S01Q | Infineon (DE) | 6 inputs | integrated | 6-140 V | 160 V | VQFN-32 5x5 | none | 50 | - |

Sources: [DRV8300 datasheet][drv8300] (sections 5, 6, 7.1, 7.3, 7.5, 8.3.1.1.2);
[DRV8328 datasheet][drv8328] (sections 5, 7.3, 7.5); AM32 targets.h; stock from
LCSC and findchips. The GVDD/UVLO numbers for STDRIVE101, MP6531A and
6ED2742S01Q come from LCSC listings; their datasheets were not read.

### 4.2 Recommendation: TI DRV8300DRGER

**Pin-for-pin with v1's JSM6288Q/FD6288Q footprint.** The table compares
`src/circuit.py` `esc()` (lines 321-331) with DRV8300 Figure 6-1:

| Pin | v1 JSM6288Q net | DRV8300 RGE |
|---|---|---|
| 1-3 | LIN1-3 | INLA-INLC |
| 4 | VCC | GVDD |
| 5 | n/c | **MODE** (leave open: non-inverting) |
| 6 | GND | GND |
| 7, 8 | n/c | NC |
| 9-11 | LO3, LO2, LO1 | GLC, GLB, GLA |
| 12-20 | VS3 HO3 VB3 / VS2 HO2 VB2 / VS1 HO1 VB1 | SHC GHC BSTC / SHB GHB BSTB / SHA GHA BSTA |
| 21 | n/c | **DT** (open: 215 ns typ fixed dead time) |
| 22-24 | HIN1-3 | INHA-INHC |
| EP | GND | GND (EP is 2.45 mm on the TI package vs 2.7 mm on v1's land: use TI's land pattern) |

JLC's library even carries a "DRV8300-JSM" QFN-24 4x4 footprint entry (C9900208615).

Why it is chosen:

- It is non-Chinese (TI), the best stocked at both distributors, and the cheapest ($0.36 LCSC / $0.43 DK at 1k).
- It needs no firmware flags.
- Its integrated bootstrap diodes remove v1's 12 RB521S30 diodes. Those are 30 V parts and would fail at 6S anyway.

Caveats:

- **SHx slew <= 2 V/ns** (D variant). With fast 60 V FETs (Qgd 5-8 nC against 0.75 A source / 1.5 A sink), expect to add ~5-10 Ohm gate resistors, tuned on a scope. This is already in the loss model.
- **No overcurrent protection.** The DRV8328 has VDS OCP.
- **At 2S under deep sag** the bootstrap margin is small. GVDD tracks the pack through the LDO at ~VBAT - 0.3 V. At VBAT 6.0 V that gives about 5.7 V GVDD, so VBST - VSH is about 4.9 V against a 4.5 V max BSTUV. If bench tests show high-side dropouts at 2S, fit DRV8300N**RGE** (same pads) with external 60 V Schottky bootstrap diodes, e.g. Nexperia PMEG6002EB (60 V 0.2 A SOD-523, LCSC C426869, 4,956), for about 0.3 V more margin.
- If 2S matters more than cost and DigiKey stock, the DRV8328A generates 11.5-15.5 V gate drive at any pack voltage from 8 V up, and ~10.6 V from a 6 V pack. It also removes the GVDD regulator. It is limited by 84 at DigiKey and 924 at LCSC, and it needs a new footprint.

### 4.3 Gate-drive supply (GVDD) for four DRV8300s

Current budget per driver:

| Item | Current |
|---|---|
| GVDD quiescent, active | 1.4 mA max |
| Gate charge: 2 FETs switching in the PWM leg x Qg(0-11.5 V) ~48 nC (Qg,sync 42 nC max at 10 V, extrapolated) x 48 kHz | 4.6 mA |
| Bootstrap leakage | 0.15 mA |
| **Per driver** | **~6.2 mA** |
| **Four drivers** | **~25 mA worst case** (~16 mA typical) |

Voltage:

- 11.5 V nominal gives 58% of the FET's +/-20 V VGS, 58% of the DRV8300's 20 V operating GVDD and 53% of its 21.5 V absolute maximum.
- 12 V with 2% tolerance would be 61% of 20 V, so 11.5 V is used.

**Recommended: TI TPS7A4101DGNR** (LCSC [C111739][l-C111739], 11,047 in stock,
$1.09 / 0.64 / 0.54; at DigiKey the same device on the small reel is
**TPS7A4101DGNT**, 296-30184-1-ND, 3,106 in stock, $1.33 / 0.77 / 0.77).

| Parameter | Value | Check |
|---|---|---|
| VIN | 7-50 V | 25.2 V = 50% |
| IOUT | 50 mA | 25 mA = 50% |
| VREF | 1.173 V | - |
| Dropout | 290 mV | - |
| RθJB | 38.1 degC/W | at (25.2-11.5) V x 25 mA = 0.34 W, +13 degC over a 100 degC board, i.e. 52% of the 25 degC headroom to its 125 degC operating limit |

Source: [TPS7A4101 datasheet][tps7a41].

Circuit:

- Feedback: 11.5 V = 1.173 V x (1 + R1/R2), e.g. R1 = 88.7k, R2 = 10.2k (E96), which gives 11.37 V.
- Place a 22 Ohm + 1 uF (100 V) RC ahead of IN to blunt spikes.
- 10 uF 25 V on OUT, then the existing per-driver 10 uF + 100 nF at each GVDD pin. A 25 V rating is 46% at 11.5 V. Use e.g. Murata GRM21BR61E106KA73L (LCSC C84416, 220k in stock; DigiKey feed showed 0, not verified).

Caveat at 2S: the TPS7A4101's **specified minimum VIN is 7 V**. A 2S pack under
load (6.0-7.0 V) runs it below spec. It will most likely pass through at
~VBAT - 0.3 V, but that is not guaranteed.

**2S-proof, cheapest alternative**, an emitter follower:

- Nexperia **BCP56-16** NPN, 80 V (LCSC [C92221][l-C92221], 38,385 in stock, $0.16 / 0.13 / 0.09)
- Nexperia **BZX84-C12** 12 V zener (LCSC [C108437][l-C108437], 239,000 in stock, $0.02)
- 33k from VBAT to the zener
- Output ~11.3 V at 6S (11.4-12.7 V zener), ~VBAT - 0.8 V at 2S. 80 V is 32%. It has no current limit.
- DigiKey rows for both read 0 in the findchips feed (1727-BCP56-16,115CT-ND, 1727-2936-1-ND), which is not verified and odd for such common parts.

---

## 5. ESC MCU

| MCU | Package | LCSC stock (code) | LCSC $1/100/1k | DigiKey stock (PN) | DK $1/100/1k | AM32 targets in targets.h | AM32 bootloader build | Current-sense ADC / analog |
|---|---|---|---|---|---|---|---|---|
| STM32F051K6U6 (v1) | QFN32 5x5 | 770 (C81451) | 1.87/1.26/1.15 | **0** (497-18979-1-ND) | 3.97/2.47/2.26 | 52 | yes | 12-bit ADC, 2 COMP |
| **STM32G071GBU6** | **QFN28 4x4** | **1,168** (C529347) | 3.10/2.36/2.23 | **19** (497-STM32G071GBU6TRCT-ND) | 3.15/1.93/1.76 | **53 G071 targets** (TBS, T-Motor, Mamba, iFlight, Lumenier Siege NDAA, Sequre, Flycolor...) | yes (G071, G071_64K) | 12-bit ADC (PA5 = ADC_IN5 current), 2 COMP, no op-amp |
| STM32G071G8U6 (64 KB) | QFN28 4x4 | 1,305 (C724080) | 3.28/2.35/2.20 | 79 (497-STM32G071G8U6CT-ND) | 2.95/1.79/1.54 | same (use `SIXTY_FOUR_KB_MEMORY` targets) | yes (G071_64K) | same |
| STM32G071KBU6 | QFN32 5x5 | 17 (C529350) | 6.69/4.45/4.04 | 0 (KBU6N "PD" variant: 1,401, different pinout, needs an N_VARIANT group) | - | same | yes | same |
| STM32G431KBU6 | QFN32 5x5 | 3,483 (C529358) | **9.07/6.33/6.33** | 2,257 (497-19474-ND) | 6.36/4.06/3.65 | 5 (+2 CAN): REF/AS/SCAR/PROTONDRIVE/SEQURE; only SEQURE_G431 defines current sense | yes | 2 ADCs, 3 op-amps (unused by AM32 on G4), 4 COMPs, 170 MHz |
| STM32G031K8U6 | QFN32 5x5 | 200 (C432207) | 2.88/1.85/1.67 | 20,268 (497-19558-ND) | 2.55/1.53/1.35 | 1 (GEN_G031 dev) | **no G031 build** | **no comparator**: AM32's G031 group reads back-EMF on EXTI pins, i.e. needs external comparators |
| STM32L431KBU6 | QFN32 5x5 | 124 (C2826408) | 8.85/6.29/6.29 | 0 (497-18831-1-ND) | 4.42/2.77/2.54 | 9 (+CAN), mostly DroneCAN ESCs | yes | ADC, 1 op-amp (PGA x16 used via `USE_INTERNAL_AMP` on NEUTRON_L431) |
| NXP MCXA153VFM (EU, for reference) | HVQFN32 | 0 (C22419885) | 4.78 | 547 (NXP) | 2.82/1.73/1.53 | 1 (FRDM_A153 dev board) | yes (A153) | 16-bit ADC |

Sources:

- AM32 [targets.h][targets]. Target counts come from parsing every `FILE_NAME` block by MCU suffix, as `make/tools.mk` `get_targets` does. The list is in (a working file, not kept).
- AM32-bootloader [Makefile][blmk] `MCU_BUILDS`.
- [STM32G071 datasheet DS12232][g071ds], Table 12 pin table and Table 25 run current.
- AM32 [g031 comparator.c][g031c] and targets.h `HARDWARE_GROUP_G031_A`.

**Recommendation: STM32G071GBU6.** STM32G071G8U6 is the same die with 64 KB
and fits the same pads, which pools LCSC stock to ~2,470, about 618 boards.

- AM32 maturity is second only to the F051.
- It is a smaller package than v1's F051 (4x4 vs 5x5).
- It runs at 64 MHz with a comparator on PA2/PB3/PB7 and PA3.
- The stock GEN_64K_G071 target runs on it unchanged (section 7).
- 3.3 V budget: 6.3-6.8 mA run at 64 MHz with peripherals off (Table 25), so ~12 mA with peripherals x4 is **~50 mA**.

**It does not meet the "in stock at both LCSC and DigiKey" requirement. Nothing
in ST's AM32-supported range does.** Options:

- (a) Build at JLC from LCSC stock, and reserve it.
- (b) Take the STM32G431KBU6. It is in stock at both, but costs +$16 per board at LCSC (4 x $6.33) and needs a new AM32 target on the thinly supported G4 port.
- (c) Keep a G071 KBU6N ("PD") footprint variant for DigiKey builds. That is a different pinout and needs the `N_VARIANT` groups G0_G/G0_H (e.g. `TMOTOR_G071`, `IFLIGHT_BLITZ_N_G071`).

---

## 6. Current sensing

### 6.1 How AM32 reads and uses current (source)

**Where it is read:**

- Each MCU samples one `CURRENT_ADC_PIN`.
- For G071 the default is **PA5 / ADC_IN5**, and voltage is PA6 / ADC_IN6 ([targets.h L5435-5470][t-g071]).
- The ADC runs at the 1 kHz PID tick (`PROCESS_ADC_FLAG`).
- `getSmoothedCurrent()` is a **50-sample moving average**, i.e. 50 ms ([main.c L820-833][m-smooth]).

**Scaling** ([main.c L2173-2178][m-cur]):
`actual_current [10 mA] = (raw x 3300/41 - CURRENT_OFFSET x 100) / MILLIVOLT_PER_AMP`.
The defaults are `MILLIVOLT_PER_AMP 20` and `CURRENT_OFFSET 0` (mV) ([targets.h L3388-3394][t-def]).
`NO_CURRENT_SENSE` zeroes it.

**Current limit:**

- Enabled when EEPROM `limits.current` is 1-100 ([main.c L730][m-lim]). The target is `limits.current x 2 A`; DroneCAN exposes it as amps (0-200).
- A 1 kHz PID (default Kp 400, Kd 1000) lowers `use_current_limit_adjust`, which caps the duty ([main.c L1442-1452][m-pid], L1338-1341).
- It is a *battery-side, averaged* current limit, not a cycle-by-cycle trip.

**Stall and "cut":**

- Cutting a stalled motor is done by **stuck-rotor protection**, default on. After a back-EMF timeout it calls `allOff()` and forces input to 0 ([main.c L1144-1150][m-stuck]). It does not use current sensing.
- `stall_protection` is a crawler throttle *boost*. Its comment says: do not use for multirotors ([main.c L1453-1454][m-pid]).
- **Why battery-side current cannot catch a stall at low throttle:** the shunt sees I_batt = D x I_phase. A stalled 0.2 Ohm motor at 10% duty on 6S draws ~12.6 A of phase current, but only ~1.3 A from the battery.
- Current sensing therefore gives: per-motor current limiting at high duty, telemetry, and consumed mAh (`consumed_current`, L2040).

**Temperature:** `limits.temperature` (70-140 degC) derates maximum duty
([main.c L2244-2246][m-temp]).

### 6.2 Existing AM32 targets with current sensing (G071 / G0_A family)

| Target | Group | Current pin | Voltage pin | mV/A | Offset | Vdiv | Dead time |
|---|---|---|---|---|---|---|---|
| GEN_64K_G071 | G0_A | PA5 (default) | PA6 (default) | 20 | 0 | 110 (default) | 60 |
| TBS_4IN1_G071 | G0_A | PA5 | PA6 | 20 | 0 | 110 | 60 |
| AM32_ESC_G071 | G0_A | PA6 | PA4 | 16 | 0 | 110 | 40 |
| SEQURE_4IN1_G071 | G0_A | PA4 | PA6 | 9 | 0 | 210 | 60 |
| ZTW_A_LV_G071 | G0_A | PA0 | PA1 | 33 | 0 | 210 | 30 |
| ARK_4IN1_F051 (DRV8328) | F0_B | PA3 | PA6 | 10 | 25 mV | 210 | 25 |

Full list: (a working file, not kept). ARK's STEP model
names a Vishay **WSLF2512 1 mOhm** shunt, a TI TPSM365R15 buck module and
Infineon PG-TDSON-8 (SuperSO8) FETs ([ARK repo][arkgit]). That points to a
1 mOhm shunt x 10 V/V amplifier, but the amplifier part was not identified.

### 6.3 Recommended design (per channel, not shared)

The shunt goes in each channel's bridge return: the three low-side sources
join, then pass through the shunt to the GND plane. It then carries that
channel's DC-link current, i.e. that motor's battery current. The signal is
chopped at the PWM rate.

| Item | Choice | Reason |
|---|---|---|
| Shunt | **Yageo PU2512FKGP60U5L**, 0.5 mOhm, 1%, 6 W, 2512 (Yageo, Taiwan) | 0.2 W at 20 A (**~5% of rating**), 0.45 W at 30 A. Stocked at both distributors. |
| Amplifier | **TI INA180A3IDBVR** (100 V/V, SOT-23-5) | VCM -0.2 to 26 V; Vos +/-150 uV max at VCM = 0 (0.3 A); gain error +/-1%; 350 kHz BW (A1). Stocked at both. INA180A1/A2 (20, 50 V/V) are **0 at DigiKey** per the feed. Source: [INA180 datasheet][ina180]. |
| Scale | 0.5 mOhm x 100 = **50 mV/A** | 30 A -> 1.5 V; full scale 3.3 V -> **66 A**; 1 LSB (0.806 mV) = 16 mA |
| Filter | 1 kOhm series + 100 nF at the ADC pin (fc ~1.6 kHz) | Knocks the 24-48 kHz chopping down ~15-30x before AM32's 50 ms average |
| AM32 | Custom target with `MILLIVOLT_PER_AMP 50`, `CURRENT_OFFSET 0` | With stock GEN_64K_G071 (20 mV/A) it reads **2.5x high**: the limit trips early, which is the safe direction for bring-up |
| FC CUR pin (stack pin 3) | Four 10 kOhm resistors from the four amplifier outputs to CUR, 100 nF to GND | CUR = average = (sum of I) x 12.5 mV/A; Betaflight `ibata_scale = 125`; 4 x 30 A -> 1.5 V |

Alternative scaling: **1 mOhm + INA180A1** gives 20 mV/A, which matches stock
GEN_64K_G071 exactly. It costs **2x the shunt loss** (0.4 W per channel at
20 A, 1.6 W for the board), and INA180A1 showed 0 at DigiKey. Use the Bourns
CRE2512-FZ-R001E-3 shunt (LCSC C840615, 2,324; DigiKey CRE2512-FZ-R001E-3CT-ND,
40,594).

Board area per channel: the 2512 courtyard is ~29 mm2, INA180 ~12 mm2,
decoupling plus RC ~6 mm2. **~47 mm2 per channel, ~190 mm2 for four**. A
shared single shunt, using less area, cannot give per-motor limiting.

An MCU-internal op-amp is not an option: the G071 has none. On the L431 AM32
supports it (`USE_INTERNAL_AMP`, PGA x16 on PA0), but on the G431 AM32 does not
use its op-amps.

---

## 7. AM32 target to reuse: GEN_64K_G071 (hardware group G0_A)

`GEN_64K_G071` ([targets.h L2609-2617][t-gen]) defines:

- `DEAD_TIME 60`
- `MILLIVOLT_PER_AMP 20`
- `CURRENT_OFFSET 0`
- `HARDWARE_GROUP_G0_A`
- `USE_SERIAL_TELEMETRY`
- `SIXTY_FOUR_KB_MEMORY`
- `TARGET_VOLTAGE_DIVIDER` left at the default 110 (10k/1k)

The pin map comes from G0_A ([targets.h L3720-3753][t-g0a]), the MCU_G071
defaults (L5435-5470) and g071 `peripherals.c` / `serial_telemetry.c`. AM32
enables the PA11->PA9 and PA12->PA10 remap by default
([g071 peripherals.c L25-27][g071p]). That is what makes the 28-pin package
work.

| Function | STM32 pin | Peripheral | G071**G**xU6 QFN28 pin (DS12232 Table 12) |
|---|---|---|---|
| DShot / PWM input | PB4 | TIM3_CH1 | 24 |
| Phase A high | PA10 | TIM1_CH3 | 19 (pad "PA12 [PA10]", remapped) |
| Phase A low | PB1 | TIM1_CH3N | 15 |
| Phase B high | PA9 | TIM1_CH2 | 18 (pad "PA11 [PA9]", remapped) |
| Phase B low | PB0 | TIM1_CH2N | 14 |
| Phase C high | PA8 | TIM1_CH1 | 16 |
| Phase C low | PA7 | TIM1_CH1N | 13 |
| Back-EMF A | PB7 | COMP2_INM IO2 | 27 |
| Back-EMF B | PB3 | COMP2_INM IO1 | 23 |
| Back-EMF C | PA2 | COMP2_INM IO3 | 8 |
| Virtual neutral | PA3 | COMP2_INP IO3 | 9 |
| Current sense | PA5 | ADC_IN5 | 11 |
| Battery voltage | PA6 | ADC_IN6 | 12 |
| Serial telemetry TX | PB6 | USART1_TX | 26 |
| SWDIO / SWCLK | PA13 / PA14 | SWD | 20 / 21 |
| NRST, VDD/VDDA, VSS | - | - | 5, 3, 4 |

Other targets using G0_A with current sense on PA5 and voltage on PA6 include
the production `TBS_4IN1_G071` (L2650-2662). ESC-configurator lists
GEN_64K_G071 as "G071 64kESC".

Proposed minimal extension (a new block in targets.h, same pins):

```c
#ifdef OG3_G071
#define FILE_NAME "OG3_G071"
#define FIRMWARE_NAME "OffGrid OG3 "
#define DEAD_TIME 20              // 313 ns at 64 MHz; DRV8300 adds >=150 ns; scope before flying
#define MILLIVOLT_PER_AMP 50      // 0.5 mOhm x INA180A3 (100 V/V)
#define CURRENT_OFFSET 0
#define TARGET_VOLTAGE_DIVIDER 110 // 10k / 1k (25.2 V -> 2.29 V at PA6)
#define HARDWARE_GROUP_G0_A
#define USE_SERIAL_TELEMETRY
#define SIXTY_FOUR_KB_MEMORY
#endif
```

Firmware and dividers:

- **Bootloader**: AM32-bootloader `G071_64K` build on pin **PB4**. The Makefile has `MCU_BUILDS ... G071 G071_64K` and `BOOTLOADER_PINS = PB4 PA2 PA6 PA15 PA0 PB2`.
- **Back-EMF dividers for 2S-6S**: change v1's 10k/2.2k to **10k/1k**. The worst phase spike, ~35 V, then reaches 3.2 V at the comparator. The neutral is 3 x 10k to a star with 330 Ohm to ground (1k/3). This was not bench-verified; low 2S amplitude (~0.6-0.8 V at the pins) is the trade-off.

---

## 8. Capacitors, TVS and the 3.3 V supply

| Role | Part | Rating vs 6S | LCSC (stock, $1/100/1k) | DigiKey (stock, $1/100/1k) |
|---|---|---|---|---|
| Bridge decoupling, 1 per half-bridge (12) plus bulk MLCC | **Murata GRM31CZ72A475KE11L** 4.7 uF 100 V X7R 1206 | 25% (35 V spike: 35%) | [C2997285][l-C2997285] (33,147; 0.74/0.52/0.48) | 490-GRM31CZ72A475KE11LCT-ND (185,082; 0.87/0.38/0.32) |
| HF decoupling at each FET pair | Murata GRM188R72A104KA35D 100 nF 100 V X7R 0603 | 25% | C77058 (71,724; 0.056/0.038/0.036) | 490-3285-1-ND (1,056,791; 0.16/0.053/0.040) |
| Bulk on the battery lead (hand-soldered) | **2 x Rubycon 50ZLH100MEFC8X11.5** (100 uF 50 V low-ESR, 8x11.5) | 50%; for 40% use Rubycon 63ZLH100MEFC8X16 (LCSC C88747 41,124; DK 242) | [C109393][l-C109393] (44,510; 0.12/0.10/0.07) | 1189-2327-ND (67,954; 0.48/0.19/0.15) |
| Bulk alternative | Panasonic EEU-FR1H151 150 uF 50 V (10x12.5, 1.17 A ripple at 100 kHz) | 50% | C542038 (760) | P15372CT-ND (293); P14456-ND bulk (1,991) |
| TVS on the battery pads | **Littelfuse SMAJ28A** (400 W, VRWM 28 V, VBR 31.1 V min, VC 45.4 V at 8.8 A; SMA) | stand-off 90% (by design); clamp 76% of 60 V at full surge, ~57% at low currents | [C148227][l-C148227] (17,185; 0.13/0.11/0.09) | SMAJ28ALFCT-ND (97,340; 0.50/0.19/0.14) |
| 3.3 V buck (4 MCUs, ~50 mA) | **ADI (Maxim) MAX15062AATA+T**, 4.5-60 V (70 V abs), 300 mA, fixed 3.3 V, synchronous, 2x2 TDFN | VIN 42%, IOUT 17% | [C2846801][l-C2846801] (2,636; 1.63/1.08/0.93) | MAX15062AATA+TCT-ND (6,841; 2.54/1.55/1.42) |
| Its inductor (datasheet Table 1: 33 uH) | **Bourns SRN4018-330M** (33 uH, 4x4, 700 mA) | ~0.1 A peak | [C2041909][l-C2041909] (**187**; 0.85/0.54/0.47) | SRN4018-330MCT-ND (28,188; 0.40/0.27/0.22) |
| Buck alternative | TI LMR38010SDDAR (80 V, 1 A, SO-8 PowerPAD) | 32% | C5219310 (517; 0.92/0.51/0.44) | 296-LMR38010SDDARCT-ND (1,028; 3.43/2.12/1.87) |

Notes on the capacitors:

- **100 V instead of 50 V MLCCs**: a 50 V X5R 10 uF keeps only ~30-40% of its capacitance at 25 V bias. The 100 V 4.7 uF part keeps more and gives 25% voltage use. That is still a guess; check Murata SimSurfing for the exact DC-bias curve.
- **Ripple current** on the bulk capacitor is not within 60% of any single small electrolytic at 4 x 20 A. The input ripple approaches ~I x sqrt(D(1-D)) per channel. This is standard FPV practice; ceramics and the pack's own low impedance carry much of it. Use 2 in parallel and keep leads short.
- **Buck output capacitor**: 10 uF X7R 1206 at 10 V (the datasheet uses 6.3 V). CIN is 1 uF at 100 V.
- **SRN4018-330M at LCSC is only 187 pcs.** Taiyo Yuden NRS4018T330MDGJ (DigiKey 587-6096-1-ND, 6,689) is the same size but shows 0 at LCSC.

Source: [MAX15062 datasheet][max15062] (Typical Operating Circuit, Tables 1-2).

---

## 9. Battery lead and pads

| Connector | Rating (source) | 4 x 15.8 A = 63 A (owner, 60 s) | 4 x 20 A = 80 A sustained | 60% rule for 80 A (needs >= 133 A) |
|---|---|---|---|---|
| XT30U | 15 A continuous ([TME XT30U-M][tme]); "20 A max with 16 AWG" in Amass's catalogue ([MiniProto][mini]); 15/30 A (web summaries) | over | over | no |
| XT60 / XT60H | 30 A continuous, 60 A for 1 min with 12 AWG, Amass genuine, <60 degC rise ([Holybro][holy]); 35 A max with 12 AWG ([MiniProto][mini]) | burst only | over | no |
| XT90 | 45 A / 90 A with 10 AWG ([Holybro][holy]) | ok | burst | no |

Wire resistance (standard copper AWG values):

| Gauge | mOhm/m | Loss at 60 A in a 2 x 8 cm lead |
|---|---|---|
| 18 AWG | 20.9 | ~12 W |
| 16 AWG | 13.2 | ~7.6 W |
| 14 AWG | 8.3 | ~4.8 W |

These are brief peaks.

Recommendation:

- **Pads**: 3.5 x 7 mm, up from v1's 2.6 x 5 mm. They take 14-16 AWG with the bulk-capacitor legs on the same pads. Stitch each with >= 30 filled vias into the VBAT/GND planes plus a top pour to the FET rows, and use 2 oz inner copper.
- **6S 2004 builds**: XT60 with 14 AWG. That is still not "60%-rated" for 80 A; nothing that fits a 3" is.
- **Owner's 4S 1404 build**: XT30 with 16-18 AWG is common practice. Be clear that a 63 A full-throttle minute exceeds XT30's rating. It survives because punch-outs last seconds.
- **Motor ratings**: XING2 1404 3800KV maximum current (60 s) is 15.84 A and 253.4 W. Sources: [RaceDayQuads][rdq1404], [DrUAV][druav1404]; the iFlight figure was not read at iFlight directly.

---

## 10. Benchmark: small 3" 4-in-1s and AIOs

| Product | Mount / board | Input | Claimed per motor | Firmware / MCU | FETs / notes |
|---|---|---|---|---|---|
| GEPRC TAKER G4 45A AIO (the board v1 replaces) | 25.5 x 25.5 mm, AIO | 2-6S | 45 A cont / 50 A burst | BLHeli_S, "F4A AIO" ESC target | not published ([MyFPV][taker]) |
| SpeedyBee F405 Mini BLS 35A | 20x20 | 3/4-6S | 35 A / 45 A (5 s) | BLHeli_S | TVS onboard, TDK caps; FETs not published ([SpeedyBee][sb]) |
| T-Motor Mini F45A 6S | 20x20, 9.2 g | 3-6S | 45 A / 55 A | BLHeli_32 | not published ([T-Motor][tm]) |
| iFlight BLITZ Mini E55S | 20x20 | 2-6S | 55 A / 60 A | BLHeli_S (8-bit) | "metal MOSFETs on the bottom" (v1.1) ([iFlight/retailers][blitz]) |
| Holybro Tekko32 F4 Mini 50A | 20x20 holes, **46.6 x 38 mm board** | 4-6S | 50 A / 60 A | AM32 `AM32_F4A_4IN1_F421` (Artery) | onboard analog current sensor; "individual metal heatsinking" ([Holybro][tekko]) |
| BetaFPV Toothpick F405 V4 AIO | whoop/toothpick AIO | 2-4S (also a 2-6S version) | 20 A / 22 A | BLHeli_32 / BLHeli_S | not published ([BetaFPV][betafpv]) |
| FETtec 4in1 45A (DE, reference) | 30.5 mm, 38 x 38 mm | 3-6S | "active current limiting @ 45A" | STM32G071 at 64 MHz, 128 kHz PWM | **"High quality 40V MOSFETs"**; 50 V cap ([FETtec][fettec]) |
| ARK 4IN1 ESC (US, NDAA, AM32, reference) | 30.5 mm, 43 x 40.5 mm, 14.5 g | 3-8S (65 V abs) | 50 A / 75 A | AM32 on STM32F0 (`ARK_4IN1_F051`); TI DRV8328 per the AM32 target | Infineon SuperSO8 FETs, Vishay WSLF2512 1 mOhm shunt, TI TPSM365R15 (from STEP part names); 450 uF onboard ([ARK docs][arkdoc], [ARK GitHub][arkgit]) |

What this shows:

- The claimed 35-55 A per motor on 20x20 and 25.5 mm boards are burst figures with airflow, not 60% ratings.
- FETtec states 40 V FETs at 6S.
- Only the ARK (a much larger 30.5 mm board, 60 V-class driver) approaches the OG3 derating philosophy.
- FET part numbers are not published for the Chinese-brand boards and were not found. The FETs used in these products are **not verified**.

---

## 11. Sourcing table: recommended and compared parts

Fetched 2026-09-27. LCSC numbers come from LCSC's product API; DigiKey numbers
from findchips' DigiKey feed (**not verified on digikey.com**, which blocked
scripted fetches). "Qty" is per board.

| Role | MPN | Maker | Qty | LCSC | LCSC stock | LCSC $ 1/100/1k | DigiKey PN | DK stock | DK $ 1/100/1k |
|---|---|---|---|---|---|---|---|---|---|
| **Power FET** | BSZ040N06LS5ATMA1 | Infineon | 24 | [C3279309][l-C3279309] | 4,990 | 1.52/0.94/0.84 | 448-BSZ040N06LS5ATMA1CT-ND | 891 | 2.14/0.92/0.73 |
| Power FET alternate | MCG60N06YHE3-TP | MCC | 24 | [C26691506][l-C26691506] | 2,062 | 0.83/0.69/0.65 | 353-MCG60N06YHE3-TPCT-ND | 4,589 | 2.22/0.95/0.76 |
| **Gate driver** | DRV8300DRGER | TI | 4 | [C3655801][l-C3655801] | 15,243 | 0.59/0.39/0.36 | 296-DRV8300DRGERCT-ND | 57,636 | 0.88/0.50/0.43 |
| Gate driver, same pads, external diodes | DRV8300NRGER | TI | 4 | C3655266 | 8,533 | 0.57/0.34/0.29 | 296-DRV8300NRGERCT-ND | 12,932 | 0.74/0.41/0.36 |
| Gate driver alternate (no GVDD rail) | DRV8328ARUYR | TI | 4 | C3681415 | 924 | 2.10/1.55/1.45 | 296-DRV8328ARUYRCT-ND | **84** | 2.68/1.64/1.51 |
| **GVDD LDO 11.5 V** | TPS7A4101DGNR / DGNT | TI | 1 | [C111739][l-C111739] | 11,047 | 1.09/0.64/0.54 | 296-30184-1-ND (DGNT) | 3,106 | 1.33/0.77/0.77 |
| **ESC MCU** | STM32G071GBU6 | ST | 4 | [C529347][l-C529347] | 1,168 | 3.10/2.36/2.23 | 497-STM32G071GBU6TRCT-ND | **19** | 3.15/1.93/1.76 |
| ESC MCU, same pads | STM32G071G8U6 | ST | 4 | C724080 | 1,305 | 3.28/2.35/2.20 | 497-STM32G071G8U6CT-ND | **79** | 2.95/1.79/1.54 |
| **Current-sense amplifier** | INA180A3IDBVR | TI | 4 | [C122882][l-C122882] | 89,455 | 0.25/0.19/0.14 | 296-47654-1-ND | 4,763 | 0.46/0.25/0.21 |
| **Shunt 0.5 mOhm** | PU2512FKGP60U5L | Yageo | 4 | [C2084576][l-C2084576] | 10,792 | 0.53/0.32/0.28 | YAG5784CT-ND | 13,140 | 2.21/1.03/0.78 |
| **3.3 V buck** | MAX15062AATA+T | ADI/Maxim | 1 | [C2846801][l-C2846801] | 2,636 | 1.63/1.08/0.93 | MAX15062AATA+TCT-ND | 6,841 | 2.54/1.55/1.42 |
| Buck inductor 33 uH | SRN4018-330M | Bourns | 1 | [C2041909][l-C2041909] | 187 | 0.85/0.54/0.47 | SRN4018-330MCT-ND | 28,188 | 0.40/0.27/0.22 |
| **TVS** | SMAJ28A | Littelfuse | 1 | [C148227][l-C148227] | 17,185 | 0.13/0.11/0.09 | SMAJ28ALFCT-ND | 97,340 | 0.50/0.19/0.14 |
| **Bridge MLCC** | GRM31CZ72A475KE11L | Murata | 12+ | [C2997285][l-C2997285] | 33,147 | 0.74/0.52/0.48 | 490-GRM31CZ72A475KE11LCT-ND | 185,082 | 0.87/0.38/0.32 |
| HF MLCC | GRM188R72A104KA35D | Murata | ~16 | C77058 | 71,724 (JLC API) | 0.056/0.038/0.036 | 490-3285-1-ND | 1,056,791 | 0.16/0.053/0.040 |
| **Bulk (lead)** | 50ZLH100MEFC8X11.5 | Rubycon | 2 | [C109393][l-C109393] | 44,510 | 0.12/0.10/0.07 | 1189-2327-ND | 67,954 | 0.48/0.19/0.15 |

Sensitive-part cost per board (rough, LCSC at 1k):

| Line | Cost |
|---|---|
| FETs, 24 x 0.84 | $20.1 |
| MCUs, 4 x 2.23 | $8.9 |
| Drivers, 4 x 0.36 | $1.45 |
| Shunts + amplifiers, 4 x (0.28 + 0.14) | $1.7 |
| LDO + buck + inductor + TVS | $2.0 |
| MLCCs | ~$6.5 |
| **Total** | **~$41** |

This is against v1's $9.51 for the whole ESC. **The FETs dominate.** Using
MCG60N06YHE3 saves ~$4.5 per board but costs ~50% more heat.

---

## 12. Not verified / open items

- **DigiKey numbers** are from findchips' feed, not digikey.com (Cloudflare 403). Some commodity MLCC, BJT and zener lines read 0 there, which looks wrong.
- **Loss model**:
  - RDS(on) at 100/125 degC for BSZ040N06LS5 and MCG60N06YHE3 was read off datasheet graphs.
  - The +10 K/W local case-to-board resistance, the 2 V/ns edges plus 5 ns, the 0.7 V hot body-diode drop, Qrr = 30 nC and the h values are assumptions.
  - The board heat capacity of 6.5 J/K is a hand estimate.
  - Measure on the first build: thermocouple on the hottest low-side FET, 10 s / 30 s steps as in the v1 bring-up.
- **DRV8300D**:
  - Whether the 2 V/ns SHx limit applies to both edges (the rising/falling split was not found in the datasheet) is unknown, as are the gate resistor values needed. Scope it.
  - Bootstrap margin at 2S under sag is only ~0.4 V at a 6.0 V pack.
- **TPS7A4101 below 7 V** (2S sag) is outside the datasheet; pass-through behaviour is expected, not guaranteed.
- **AM32 DEAD_TIME 20** (313 ns) with the DRV8300's own 215 ns has not been tested. The stock 60 (938 ns) is safe but costs ~0.8 W per motor at 20 A and 48 kHz.
- **Land-pattern compatibility** of MCC DFN3333 vs Infineon TSDSON-8 FL, and of the DRV8300 RGE EP (2.45 mm) on v1's 2.7 mm land, was not checked in detail.
- **MCU sourcing**: no AM32-supported ST MCU is well stocked at both LCSC and DigiKey today (section 5).
- **Benchmarks**: FET part numbers used in commercial 3" 4-in-1s are not published and were not found. The ARK details come from STEP model part names plus the AM32 target, not a BOM.
- **Area budget**: ~63% of both sides is an estimate. Run a placement study (`esc_layout.py`) before committing.
- **Side finding**: v1 BOM part **C2932476** (Samsung CL21A106KBYQNNE 10 uF 50 V 0805, 13 per ESC) shows **0 in stock at LCSC** on 2026-09-27. The v1 README says it was plentiful.

---

## Sources

AM32 (commit 55c96847a0cddfee9852eb65d2b10e58f563b3d7):

- [targets.h][targets]
- [main.c][mainc]
- [DroneCAN.c parameter defaults][dc]
- [Mcu/g071/Src/peripherals.c][g071p]
- [Mcu/f051/Src/peripherals.c][f051p]
- [Mcu/g031/Src/comparator.c][g031c]
- AM32-bootloader [Makefile][blmk]

Datasheets:

- TI [DRV8300][drv8300], [DRV8328][drv8328], [INA180][ina180], [TPS7A4101][tps7a41], [CSD18543Q3A][csd]
- Infineon [BSZ040N06LS5][bsz040], [BSZ042N06NS][bsz042]
- MCC [MCG60N06YHE3][mcg]
- Toshiba [TPN2R304PL][tpn2r3]
- ST [STM32G071 DS12232][g071ds]
- ADI [MAX15062][max15062]

Products and connectors: [ARK docs][arkdoc], [ARK GitHub][arkgit], [FETtec][fettec], [Holybro Tekko32 F4 Mini][tekko], [SpeedyBee][sb], [T-Motor][tm], [iFlight BLITZ][blitz], [BetaFPV][betafpv], [GEPRC TAKER G4 (MyFPV)][taker], [Holybro connector ratings][holy], [MiniProto XT guide][mini], [TME XT30U-M][tme], [RaceDayQuads XING2 1404][rdq1404], [DrUAV XING2 1404][druav1404].

Stock and prices: LCSC product pages (links in the tables) and findchips DigiKey rows (`https://www.findchips.com/search/<MPN>`).

[targets]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Inc/targets.h
[t-nom]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Inc/targets.h#L5751-L5759
[t-def]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Inc/targets.h#L3380-L3394
[t-g0a]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Inc/targets.h#L3720-L3753
[t-g071]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Inc/targets.h#L5435-L5470
[t-gen]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Inc/targets.h#L2609-L2617
[t-ark]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Inc/targets.h#L2316-L2336
[mainc]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Src/main.c
[m-pwm]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Src/main.c#L637-L644
[m-var]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Src/main.c#L1977-L1990
[m-lim]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Src/main.c#L730
[m-pid]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Src/main.c#L1438-L1462
[m-stuck]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Src/main.c#L1144-L1150
[m-smooth]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Src/main.c#L820-L833
[m-cur]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Src/main.c#L2127-L2179
[m-temp]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Src/main.c#L2244-L2246
[dc]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Src/DroneCAN/DroneCAN.c#L150-L200
[g071p]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Mcu/g071/Src/peripherals.c
[f051p]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Mcu/f051/Src/peripherals.c#L521-L545
[g031c]: https://github.com/am32-firmware/AM32/blob/55c96847a0cddfee9852eb65d2b10e58f563b3d7/Mcu/g031/Src/comparator.c
[blmk]: https://github.com/am32-firmware/AM32-bootloader/blob/578ff29/Makefile
[drv8300]: https://www.ti.com/lit/ds/symlink/drv8300.pdf
[drv8328]: https://www.ti.com/lit/ds/symlink/drv8328.pdf
[ina180]: https://www.ti.com/lit/ds/symlink/ina180.pdf
[tps7a41]: https://www.ti.com/lit/ds/symlink/tps7a4101.pdf
[csd]: https://www.ti.com/lit/ds/symlink/csd18543q3a.pdf
[bsz040]: https://datasheet.lcsc.com/datasheet/pdf/d26d749181c7ca2ac92c1d0b543ccc8c.pdf?productCode=C3279309
[bsz042]: https://datasheet.lcsc.com/datasheet/pdf/4c8aa8e8ecd53baeca110f6973209c36.pdf?productCode=C3279304
[mcg]: https://datasheet.lcsc.com/datasheet/pdf/f494691290ef56b270a58a670244f1cf.pdf?productCode=C26691506
[tpn2r3]: https://datasheet.lcsc.com/datasheet/pdf/b6fa6511775f5a4f13f7319d3e2e8d31.pdf?productCode=C5802634
[g071ds]: https://www.st.com/resource/en/datasheet/stm32g071c8.pdf
[max15062]: https://www.analog.com/media/en/technical-documentation/data-sheets/MAX15062.pdf
[arkdoc]: https://docs.arkelectron.com/products/electronic-speed-controller/ark-4in1-esc
[arkgit]: https://github.com/ARK-Electronics/ARK_4IN1_ESC
[fettec]: https://fettec.net/en/shop/electronics/esc/fettec-4in1-esc-45a
[tekko]: https://holybro.com/products/tekko32-f4-4in1-mini-50a-escam32
[sb]: https://www.speedybee.com/speedybee-f405-mini-bls-35a-20x20-stack/
[tm]: https://store.tmotor.com/product/mini-f45a-4in1-fpv-esc.html
[blitz]: https://wrekd.com/products/iflight-blitz-mini-e55s-mini-v1-1-8bit-55a-2-6s-20x20-4in1-esc
[betafpv]: https://betafpv.com/products/toothpick-f405-2-4s-aio-brushless-flight-controller-20a-blheli_32-v4
[taker]: https://www.myfpvstore.com/fpv-electronics/flight-controllers/aio-boards/geprc-taker-g4-45a-8bit-aio/
[holy]: https://docs.holybro.com/power-module-and-pdb/power-module/connector-and-wire-rating
[mini]: https://www.miniproto.com/connectors/xt-connectors
[tme]: https://www.tme.eu/en/details/xt30u-m/dc-power-connectors/amass/
[rdq1404]: https://www.racedayquads.com/products/iflight-xing2-1404-3800kv-micro-motor
[druav1404]: https://druav.com/products/iflight-xing2-1404-fpv-motor
[l-C3279309]: https://www.lcsc.com/product-detail/C3279309.html
[l-C26691506]: https://www.lcsc.com/product-detail/C26691506.html
[l-C840100]: https://www.lcsc.com/product-detail/C840100.html
[l-C3655801]: https://www.lcsc.com/product-detail/C3655801.html
[l-C111739]: https://www.lcsc.com/product-detail/C111739.html
[l-C92221]: https://www.lcsc.com/product-detail/C92221.html
[l-C108437]: https://www.lcsc.com/product-detail/C108437.html
[l-C529347]: https://www.lcsc.com/product-detail/C529347.html
[l-C122882]: https://www.lcsc.com/product-detail/C122882.html
[l-C2084576]: https://www.lcsc.com/product-detail/C2084576.html
[l-C2846801]: https://www.lcsc.com/product-detail/C2846801.html
[l-C2041909]: https://www.lcsc.com/product-detail/C2041909.html
[l-C148227]: https://www.lcsc.com/product-detail/C148227.html
[l-C2997285]: https://www.lcsc.com/product-detail/C2997285.html
[l-C109393]: https://www.lcsc.com/product-detail/C109393.html
