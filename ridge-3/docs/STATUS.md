# Ridge 3 rev 2: status, open decisions and next steps

The board's progress record.  Whoever works on Ridge 3 next (the owner, an
engineer, an AI agent) reads this first and keeps it current: tick what is
done, record each decision with its date and who made it, and add a line to
the log at the end.  The evidence behind each item is linked; every test
and simulation with this revision's result is in [`../TESTS.md`](../TESTS.md),
the hardware tests' procedure in [`TEST_PLAN.md`](TEST_PLAN.md), and how to
apply a decision to the design is in [`CHANGING.md`](CHANGING.md).

## Where it stands (2026-10-14)

| | State |
|---|---|
| Design | **Revision 2.0**, both boards.  KiCad DRC 0 errors / 0 warnings / 0 unconnected; the copper matches `src/circuit.py` pad for pad; `../VERIFICATION.md` checks the design against independent sources |
| Simulation | Done: `../STRESS.md` (switching, battery line, stack lead, copper, heat at 25 / 50 / 60 °C), and [`RELIABILITY.md`](RELIABILITY.md) (variants, a crash, a punch), with every report it quotes committed in `../sim/results/` |
| Fabrication files | Committed in `../fc/production/` and `../esc/production/`, single boards and 3 × 2 panels.  CI (the `ridge-3` job) rebuilds them from the committed board files on every pull request into `main` and every push to `main`, and fails if they differ |
| Test record | [`../TESTS.md`](../TESTS.md): every build gate, design check and simulation with revision 2.0's result and date; the hardware rows not run |
| Prototypes | **Not ordered.**  No board has been built or measured |
| Firmware | Betaflight image and AM32 target in `../firmware/`: built, never run on this hardware |
| Certification | Not started |

## Decisions waiting

Each: the options with what they cost, the recommendation, and what settles
it.  When one is made, fill in **Decided** and follow `CHANGING.md`.

### D1. The ESC's FETs

- **Now:** Infineon ISZ023N06LM6 (60 V, 2.3 mΩ max, 175 °C).  Not at LCSC:
  JLCPCB global sourcing, PCBWay turnkey, or DigiKey (448-ISZ023N06LM6ATMA1CT-ND,
  2,518 in stock on 2026-10-13).  24 per ESC; at $1.49 they are most of
  the ESC's cost.
- **Rejected:** Infineon BSZ040N06LS5 (JLC stock, cheaper).  Simulated:
  57.4 V of its 60 V at the low side, hotter in flight (AM32 cuts the hard
  flight for 19 % of it, against 10 %), rated 150 °C, and 258 °C in a hot
  crash ([`RELIABILITY.md`](RELIABILITY.md)).
- **Candidates for a second source** (from the 2026-10-13 sourcing
  research; recheck before ordering): Vishay SiSS22LDN (same land, rated
  150 °C, no SPICE model published) and Infineon ISZ034N06LM5 (same land,
  175 °C, little stock).  Neither part's land or rating has been checked
  against its maker's datasheet here.
  Either needs a simulation run (`CHANGING.md`, C2) and T5, T7 and T8 on
  real boards before it is used.
- **Recommendation:** keep the ISZ023N06LM6.  Before volume, buy a year's
  worth from an authorised source, and qualify a second source.
- **Decided:** _not yet_

### D2. Gate-drive strength (IDRIVE)

- **Now:** 60 / 120 mA (75 kΩ, `R9 R21 R33 R45`).  Chosen on 2026-10-03,
  on numbers from before the heatsink was added.
- **The trade:** at 60 / 120 mA the driver's SHx pin goes past its -7 V
  absolute maximum, at 30 A (-10.3 V) and more in a full-throttle punch
  (-15.5 V at 68 A), and the FETs reach 55-57 V of their 60 V in the 8 nH
  case.  30 / 60 mA (18 kΩ, LCSC C295780) halves that (-6.2 V at 30 A,
  -8.9 V in a punch, FETs under 40 V) and costs heat headroom: 48 % throttle
  held on a 50 °C day instead of 52 %, and AM32 cuts a motor in 18 % of the
  hard flight instead of 10 %.
- **Recommendation:** order one ESC panel with each (`TEST_PLAN.md`), measure
  (T5), and ship 30 / 60 mA unless the scope shows 60 / 120 mA within the
  driver's limits.  If neither passes, see D6.
- **Decided:** _not yet_

### D3. AM32's stuck-rotor cut

- **Now:** AM32 as it ships cuts a stalled motor after 11 back-EMF timeouts
  (about 248 ms).  In a crash that stops a motor dead at full throttle right
  after hard flying on a 50 °C day, the simulation takes the low-side FET to
  221 °C for about 200 ms.
- **Option:** a change in the `RIDGE3_F421` firmware target to cut after 3
  (about 68 ms): 195 °C for 21 ms in the same crash.  Risk: a motor cut in
  flight if three timeouts ever come in a row without a crash.
- **Recommendation:** make the change, then prove it: T7 (locked rotor) and
  T13 (flying hard, looking for false cuts).
- **Decided:** _not yet_

### D4. The gate driver's overcurrent trip level

- **Now:** the DRV8320H's VDS pin is open: 0.6 V.  It trips at 118-143 A
  with a hot FET (counting the board copper it measures through), so never
  in flight, and it does most of the work in a crash.
- **Option:** 75 kΩ to AGND (0.26 V) protects the FET outright in a crash
  together with D3's shorter cut (141 °C from a hot board; with AM32's cut
  as it ships, 193 °C, 67 ms past its rating), but trips at 51-62 A on a
  hot FET, under a punch's 64-68 A: it would cut motors in flight.  It also needs a footprint the board does not have.
- **Recommendation:** keep 0.6 V.  In the next ESC revision add the
  footprint unfitted (D6).
- **Decided:** _not yet_

### D5. The FC's 3.3 V inductor

- **Now:** TDK TFM252012ALMAR47MTAA.  Out of stock at JLC / LCSC on
  2026-10-13 (DigiKey had stock).
- **Options:** buy the TDK part at DigiKey and consign it, or Bourns
  SRP2512TMA-R47M (0.47 µH, 2.5 × 2.0 mm, 150 °C; DigiKey stock on
  2026-10-13; check the land and its LCSC number before using it).  Not
  the Murata DFE252012PD-R47M: a 125 °C part, and the FC's supplies run
  hot.  The two alternatives' figures and stock are from the 2026-10-13
  sourcing research, not checked against their makers' datasheets here;
  recheck before ordering.
- **Recommendation:** keep the TDK part if it can be bought; the Bourns
  part otherwise, after the land check (`CHANGING.md`, C4).
- **Decided:** _not yet_

### D6. The next ESC revision (after the prototypes)

Open until T5, T6 and T7 are done.  Candidates, all from
[`RELIABILITY.md`](RELIABILITY.md):

- a VDS resistor footprint per driver, left unfitted (0.6 V as now);
- a test pad on each driver's nFAULT (pin 17), so trips can be seen;
- each driver's SLx and VDRAIN routed as their own traces to the FETs
  (Kelvin), so the overcurrent monitor measures the FET, not the copper;
- if T5 fails at both IDRIVE settings: a clamp or series resistor at the SHx
  pins, or an RC snubber, sized from the measured waveforms.

### D7. Business decisions (owner)

- Where the boards are assembled, and the volume of the first year.
- The certification path: FCC Part 15 B for the US, the marks of each
  export market, and whether US institutional buyers (NDAA, the FCC
  Covered List) are a target, since that constrains where parts and
  assembly come from.

### D8. The battery rating

- **Now:** 2-6S, as the ESC's silkscreen (`src/esc_layout.py`), the stack
  sheet's subtitle (`src/make.py`) and the README's title print it.  The
  firmware reads 2S to 6S.
- **Simulated:** 6S LiPo and 6S LiHV (26.1 V full) pass the same checks:
  the FETs peak at 40.5 / 43.8 V of their 60 V on LiHV, and the hard flight
  is cut for 15 % of it instead of 10 % ([`RELIABILITY.md`](RELIABILITY.md),
  the variants).  2S has three limits the design does not meet:
  - the 9 V video supply cannot hold 9 V: it regulates down to about 9.5 V
    of battery, and a 2S pack is 6.0-8.4 V;
  - the stack lead's contacts: at the FC's full load (both rails at their
    2 A rating, 11.3 W) the lead carries about 1.9 A on an empty 2S pack
    (6.0 V), past the Molex contact's 1.5 A (0.57 A on an empty 6S pack,
    `../STRESS.md` section 5);
  - the gate drive: at 6 V the DRV8320H drives the gates to 4-6 V (typ
    5 V), at the edge of the 4.5 V down to which the FETs' on-resistance is
    specified (`../VERIFICATION.md`).
- **Recommendation:** rate it 3S-6S LiPo and 6S LiHV (`RELIABILITY.md`,
  recommendation 8).  The silkscreen is a board change: the ESC's `2-6S`
  (`src/esc_layout.py`), the stack sheet's subtitle (`src/make.py`), the
  README's title and battery row, the summary at the top of
  `src/circuit.py`, and the comment in the AM32 target patch (then
  its SHA-256 in `../firmware/README.md`) change together, and the boards
  are rebuilt (`python3.12 src/make.py --artwork`: both boards, so the
  stack sheet is drawn again too).  For LiHV, also set
  `vbat_max_cell_voltage` to 440 in `../firmware/betaflight/cli-setup.txt`:
  Betaflight counts cells as the pack's voltage divided by that figure,
  rounded down, plus one, so at its 430 a full 6S LiHV pack (26.1 V)
  counts as 7 cells and its
  cell-voltage warnings are wrong; at 440 it counts 6, and a 6S LiPo still
  counts 6.
- **Decided:** _not yet_

### D9. Where the next revision lives (owner)

- **Now:** both boards of revision 2.0 in one folder, `ridge-3/`, the
  revision only in the code (`REVISION`) and on the silkscreen.  The
  repository's rule ([`docs/versioning.md`](../../docs/versioning.md))
  is a folder per revision, frozen once ordered;
  [`docs/repo-structure.md`](../../docs/repo-structure.md) names
  `ridge-3/` as an exception.
- **Options:**
  - a folder per revision as `docs/versioning.md` has it
    (`ridge-3/v2/`, then the next beside it).  The CI job, the documents'
    links and the commands name `ridge-3/` paths, so the move is a change
    of its own;
  - one folder, with a git tag per ordered revision: the ordered files stay
    at their tag, and the folder moves on to the next revision.
- **Until it is decided:** before an order is placed, tag the commit its
  files come from (`CHANGING.md`, step 6).  Either option keeps that tag.
- **Decided:** _not yet_

## Before ordering prototypes

- [ ] Recheck stock and lead time of every part, dated, in a file in this
      folder (`sourcing-YYYY-MM-DD.md`).  Single-source parts to watch:
      the ESC FETs (DigiKey only), the AT32F421 (JLC / LCSC only), the
      3.3 V inductor (D5), the flash (JLC 0 on 2026-10-13; an optional
      part).
- [ ] Quote: one FC panel and two ESC panels at JLCPCB (README,
      [Ordering](../README.md#ordering)); the second ESC panel's BOM with
      the 18 kΩ IDRIVE resistor (`TEST_PLAN.md`).
- [ ] Quote the heatsink (STEP and PDF in `../mechanical/`) at two CNC shops.
- [ ] Gap pads, stack leads, grommets and hardware (README, *Also needed*).
- [ ] The test equipment in `TEST_PLAN.md`.
- [ ] Decide D9, and tag the commit the order's files come from
      (`CHANGING.md`, step 6); record the tag in the log below.

## Prototype tests

From [`TEST_PLAN.md`](TEST_PLAN.md).  Results go in `tests/`.

| Test | What | Settles | Done |
|---|---|---|---|
| Bring-up | README steps 1-8 | that it works at all | [ ] |
| T1 | Inspection, X-ray | assembly quality | [ ] |
| T2 | Firmware settings read back | the programming procedure | [ ] |
| T3 | Current sensing | AM32's current limit | [ ] |
| T4 | Temperature sensing | AM32's temperature limit | [ ] |
| T5 | Switching edges, both IDRIVE | **D2**, D6 | [ ] |
| T6 | Overcurrent monitor in punches | D4, D6 | [ ] |
| T7 | Locked rotor (destructive) | **D3**, D6 | [ ] |
| T8 | Heat on a hot day | the thermal model, the 50 °C rating | [ ] |
| T9 | On the ground with video | the video thermostat | [ ] |
| T10 | Supplies | the FC's rails | [ ] |
| T11 | Battery transients | the voltage ratings | [ ] |
| T12 | LiHV | the LiHV rating | [ ] |
| T13 | Flight | everything together | [ ] |

## Before volume

- [ ] **Factory programming:** one image per ESC MCU (bootloader, firmware,
      settings: 110 °C, 20 A, stuck-rotor protection on, stall protection,
      3D and car-reverse off, a fixed 24 kHz PWM with variable PWM off), written and read back
      over SWD on a pogo fixture; no manual configurator step.  Make the
      target fall back to 110 °C / 20 A when a stored limit reads as
      disabled.
- [ ] **Production test** of every stack, results kept by serial number:
      the four ESC temperatures read sensibly, each current sensor against a
      known load, each motor spins, the gyro reads about 1 g level, the
      rails, stack-lead continuity, the heatsink insulated from battery and
      ground.
- [ ] **The ESC shipped on its heatsink**, gap pad fitted, boss height
      inspected per lot.
- [ ] **Buy ahead**, with quantities, from authorised sources: the ESC FETs
      (D1), the STM32G473 (FC), the AT32F421 (ESC), the DRV8320H (TI store),
      the IIM-42652 gyro, the LMR38020F supplies, the ESC's bus capacitors,
      the shunts, the 3.3 V inductor (D5).
- [ ] Betaflight's ESC temperature warning (OSD) set about 10 °C below
      AM32's 110 °C in `../firmware/betaflight/cli-setup.txt`.
- [ ] The Betaflight gyro fix and the AM32 target sent upstream, and a
      Betaflight manufacturer ID registered, so customers who update with
      the official tools get correct firmware.
- [ ] T14 in `TEST_PLAN.md` (EMC, environmental, flight hours).
- [ ] Specification, as simulated: 3S-6S LiPo and 6S LiHV (D8); 50 °C air in
      flight (AM32 trims power in the hardest flying at that heat); the 5 V
      rail 1 A continuous on the ground (0.5 A at 60 °C), 2 A with airflow;
      HD video on the 9 V pads.  Correct it from the measurements.
- [ ] The HD build first; the analog build's OSD (AT7456E) is an 85 °C part
      and needs its own decision before it is sold.

## Log

- **2026-10-13** Reliability review: variant simulations, a crash, a punch
  ([`RELIABILITY.md`](RELIABILITY.md)); this file and the test plan
  written.  Decisions D1-D7 open.  Nothing ordered.
- **2026-10-13** Prepared for handover: the simulation reports the
  documents quote committed in `../sim/results/` (they had been only in the
  ignored `sim/out/`), and revision 1's board files frozen in
  `../sim/rev1/` for the comparison; the toolchain pinned
  (`../requirements.txt`, `../requirements-cadquery.txt`,
  `../tools/Dockerfile`) and a CI job, `ridge-3`, that rebuilds both boards'
  fab files (`make.py --fab-only`), fails if they differ from the committed
  ones, then runs `verify.py`; the datasheets `verify.py` reads listed in
  [`DATASHEETS.md`](DATASHEETS.md).  The battery rating opened as D8.
  Decisions D1-D8 open.  Nothing ordered.
- **2026-10-14** Brought in line with the repository's docs
  (`docs/versioning.md`, `docs/repo-structure.md`): [`../TESTS.md`](../TESTS.md)
  written, every build gate, design check and simulation with revision
  2.0's result, the hardware tests not run; where the next revision lives
  opened as D9.  Decisions D1-D9 open.  Nothing ordered.
