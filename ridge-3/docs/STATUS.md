# Ridge 3 rev 2: status, open decisions and next steps

The board's progress record.  Whoever works on Ridge 3 next (the owner, an
engineer, an AI agent) reads this first and keeps it current: tick what is
done, record each decision with its date and who made it, and add a line to
the log at the end.  The evidence behind each item is linked; every test
and simulation with this revision's result is in [`../TESTS.md`](../TESTS.md),
the hardware tests' procedure in [`TEST_PLAN.md`](TEST_PLAN.md), and how to
apply a decision to the design is in [`CHANGING.md`](CHANGING.md).

## Where it stands (2026-10-20)

| | State |
|---|---|
| Design | **Revision 2.0**, both boards.  KiCad DRC 0 errors / 0 warnings / 0 unconnected; the copper matches `src/circuit.py` pad for pad; `../VERIFICATION.md` checks the design against independent sources |
| Simulation | Done on the FC as routed on 2026-10-20 (D10-D12, with power vias): [`../STRESS.md`](../STRESS.md) (rev 2: 19 pass, 1 marginal, 3 fail; rev 1: 6, 5, 15) and every report in `../sim/results/`, all generated 2026-10-20.  [`RELIABILITY.md`](RELIABILITY.md) has the variants, a crash and a punch |
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
  51.7 V of its 60 V at the low side, hotter in flight (AM32 cuts the hard
  flight for 18 % of it, against 9 %), rated 150 °C, and 256 °C in a hot
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
  absolute maximum, at 30 A (-9.2 V) and more in a full-throttle punch
  (-13.5 V at 68 A), and the FETs reach 52.0-52.6 V of their 60 V in the
  8 nH case.  30 / 60 mA (18 kΩ, LCSC C295780) halves that (-5.6 V at 30 A,
  -7.6 V in a punch, FETs under 38 V) and costs heat headroom: 49 % throttle
  held on a 50 °C day instead of 52 %, and AM32 cuts a motor in 16 % of the
  hard flight instead of 9 %.
- **At both settings:** the off low-side FET's gate is kicked up when the
  high side turns on.  The driver holds the gate pin to PGND with its 2 A
  ISTRONG, but the FET's source moves against PGND through the source
  copper and the shunt (common-source inductance): on the die the gate
  reaches 1.76 V at 150 °C with 60 / 120 mA and 1.46 V with 30 / 60 mA
  (the worst of the 3-8 nH runs), above the FET's threshold hot (about
  0.4 V minimum, 1.0 V typical), so `../STRESS.md` and the `idrive30`
  variant mark it marginal.  The simulated switching energies show no
  shoot-through.  It has not been measured: T5 measures it.
- **Recommendation:** order one ESC panel with each (`TEST_PLAN.md`), measure
  (T5), and ship 30 / 60 mA unless the scope shows 60 / 120 mA within the
  driver's limits.  If neither passes, or the off gate reaches the FET's
  threshold, see D6.
- **Decided:** _not yet_

### D3. AM32's stuck-rotor cut

- **Now:** AM32 as it ships cuts a stalled motor after 11 back-EMF timeouts
  (about 248 ms).  In a crash that stops a motor dead at full throttle right
  after hard flying on a 50 °C day, the simulation takes the low-side FET to
  221 °C for about 200 ms.
- **Option:** a change in the `RIDGE3_F421` firmware target to cut after 3
  (about 68 ms): 195 °C for 22 ms in the same crash.  Risk: a motor cut in
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

Open until T5, T6 and T7 are done.  Candidates, from
[`RELIABILITY.md`](RELIABILITY.md) and `../STRESS.md` (section 3):

- a VDS resistor footprint per driver, left unfitted (0.6 V as now);
- a test pad on each driver's nFAULT (pin 17), so trips can be seen;
- each driver's SLx and VDRAIN routed as their own traces to the FETs
  (Kelvin), so the overcurrent monitor measures the FET, not the copper;
- if T5 fails at both IDRIVE settings: a clamp or series resistor at the SHx
  pins, or an RC snubber, sized from the measured waveforms;
- if T5 shows the off low-side FET's gate reaching its threshold (D2): the
  low-side gate drive returned closer to the FET's source, so less source
  inductance is shared with the power path (the DRV8320H sinks the
  low-side gates through its PGND pin), or a gate-source capacitor or a
  Miller clamp at each low-side FET, sized from that measurement.

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
  the FETs peak at 38.7 / 38.5 V of their 60 V on LiHV, and the hard flight
  is cut for 15 % of it instead of 9 % ([`RELIABILITY.md`](RELIABILITY.md),
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

### D10. The FC's 3.3 V buck output capacitance (fixed)

- **Found** in the pre-merge review (2026-10-14): the
  TPS628501's output had 2 × Murata GRM188Z71A475KE15D (4.7 µF 10 V X7R
  0603, `C4U7_X7R`, `'3.3V buck output'`).  On Murata's DC-bias curve each
  is 3.6 µF at 3.3 V, 7.2 µF together.  TI (SLUSEC8C, recommended
  operating conditions and table 8-1 for COMP/FSET to ground) asks at least
  8 µF of effective output capacitance close to the device (10 µF below
  3.3 V; the output is 3.31 V).  The 3.3 V plane's other capacitors sit at
  the processor, about 14 mm away, and do not count.
- **Risk:** too little output capacitance for its compensation can make the
  loop ring or oscillate on the processor's and the gyro's load steps.
  Nothing has been measured.
- **Options:**
  - 2 × Murata GRM21BZ71E106KE15L (10 µF 25 V X7R 0805, already on this
    board as the buck's input capacitor, `C10U25_X7R`): 8.4 µF each at
    3.3 V, about 17 µF.  An 0805 land in place of the 0603: the two parts
    are placed again (`src/fc_layout.py`, `'3.3V buck output'`) and the FC
    routed again (`--reroute fc`), then the loop in `CHANGING.md`;
  - a 0603 X7R part with at least 4 µF each at 3.3 V on its maker's curve,
    on the same land: a part swap with no new layout (`CHANGING.md`, the
    loop), if such a part is found in stock;
  - a third 4.7 µF 0603 beside the two (10.8 µF): a placement change and a
    reroute, like the first.
- **Recommendation:** the 0805 part, already qualified on this board, before
  the prototypes are ordered; then T10 checks the 3.3 V rail's ripple and a
  load step.
- **Decided:** 2026-10-19, by the owner: fix it before ordering.  Done as a
  variant of the first option: there was room for one 0805 beside the two
  0603, not for two 0805 in their place without moving the OSD's parts, so
  one GRM21BZ71E106KE15L (`'3.3V buck output bulk'`, under the inductor's
  switch end) was added and the two 0603 stay: 3.6 + 3.6 + 8.4 = 15.6 µF
  at 3.3 V, against TI's 8 µF minimum and 200 µF maximum.  `verify.py`
  checks the sum.  T10 still checks the rail's ripple and a load step.

### D11. The FC's 5 V buck on USB power (fixed)

- **Found** in the pre-merge review (2026-10-14): the 5 V
  buck (`U_BUCK5`, LMR38020F, forced PWM) had EN tied to VIN.  On USB alone
  the USB diode feeds +5V, the buck's output, and the buck's high-side body
  diode back-feeds VBAT at about 4.1-4.6 V: at or above the part's 4.2 V
  maximum start-up threshold (SNVSC40E 7.5).  The buck can then start with
  its output above its input, which TI forbids (9.3), and in forced PWM it
  passes current backwards (8.4.2): it pumps VBAT to about 4.8-5 V, or,
  when USB's 5 V less the diode is above the buck's 5 V set point (from
  about 5.3 V of VBUS, inside USB's 4.75-5.5 V), sinks up to 0.9 A from USB
  into VBAT with nothing to limit it.  VBAT can then pass the 9 V BEC's
  5.5 V turn-on and the gate drivers' UVLO, so the VTX and the ESC's
  drivers run from USB.  No simulation models this.
- **Options:**
  - an EN divider like the 9 V BEC's: 100 kΩ VBAT to EN, 24.9 kΩ EN to
    ground (both values already on the board): on at 5.5-7.0 V, off at
    4.8-6.1 V (SNVSC40E equations 13, 14), clear of the back-feed.  Two
    0402 parts at `U_BUCK5` pin 2, so the FC is placed and routed again
    (`--reroute fc`), with D10 in the same pass.  The 5 V rail then needs
    about 7 V to start, in line with D8's 3S-6S rating;
  - 30 kΩ for the bottom keeps 2S starting from 6 V, but leaves no margin
    over the back-feed at 5.5 V of VBUS on a hot board.
- **Recommendation:** 100 kΩ / 24.9 kΩ, in the same FC change as D10.  T10
  then checks the board on USB alone.
- **Decided:** 2026-10-19, by the owner: the recommendation.  EN leaves its
  pin by a via in the pad, as the 9 V BEC's does, to the divider on the top
  beside the stack lead's corridor.  `verify.py` checks that EN's lowest
  falling threshold (0.95 V) through the divider, 4.77 V, is above the
  4.6 V back-feed.  T10 checks the board on USB alone.

### D12. The FC's 5 V rail through its feedback line (fixed)

- **Found** on 2026-10-17 while answering a question about trace corners
  and current: on the routed FC, all 2 A of the 5 V rail at full load ran
  through the 0.2 mm, 7.6 mm track that joins the 5 V BEC's feedback
  resistor to the rail, and through 12 mm of 0.3 mm track, 8 mm of it on an
  inner layer.  The router that joins the feedback resistor first
  (`finish.route_taps`) had joined it to the nearest pad that was not
  another feedback line, the USB diode's, on the loads' side; the
  autorouter then fed the loads through it.  The design note behind the
  0.3 mm rule had assumed no 5 V branch carries more than about 0.7 A.  The
  simulation had shown 332 A/mm² there, with no verdict.
- **Fixed** 2026-10-19 (the owner asked for it with D10 and D11):
  - each supply's feedback line is joined straight to its converter's
    output pour and to nothing else, and is hidden from every router until
    the routing is done (`finish.route_taps`, `finish.hide_taps`,
    `src/pipeline.py`), so no load can be fed through it;
  - the 5 V and 9 V tracks are 0.5 mm instead of 0.3 and 0.4 mm: the
    router joins each rail's loads in a tree, so one track can carry the
    BEC's whole 2 A (21 °C rise on the IPC-2221 external curve, which
    overstates it for a short track over a plane; `src/fc_layout.py`);
  - every via the routers put on the 5 V, 9 V and video-battery nets is a
    0.5 / 0.25 mm power via (`VIA_BY_NET`): the first reroute still took
    the 5 V rail's 2 A through one 0.15 mm signal via (212 A/mm² in its
    barrel); a 0.25 mm barrel holds the copper of a 0.45 mm track;
  - `verify.py` checks every feedback line (it reaches one pour and no pad
    but its divider's) and every via on those three nets.
- **Result** (2026-10-20, `../STRESS.md` section 5, simulated): at 2 A
  the 5 V copper drops 110 mV and loses 0.19 W (130 mV and 0.24 W before);
  its densest cell is 175 A/mm² on In2.Cu, where it was 332 A/mm² on B.Cu
  in the feedback line.  The current crosses three 0.25 mm power vias in
  series, 2.00 A in each: 127 A/mm² in their barrels (212 A/mm² in the
  first reroute's 0.15 mm via), about what the 0.5 mm tracks carry
  (114 A/mm²).  The 9 V rail's 2 A splits 1.03 / 0.97 A over two power
  vias.  No verdict changed: rev 2 still 19 pass, 1 marginal, 3 fail.
- **Settled by:** T10 (a thermal camera on the 5 V copper at 2 A).

## Before ordering prototypes

- [x] Fix D10 (the FC's 3.3 V buck output capacitance), D11 (the 5 V
      buck's enable on USB power) and D12 (the 5 V rail through its
      feedback line): one change to the FC, placed and routed again
      (2026-10-19).

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
| T10 | Supplies | the FC's rails, D10, D11, D12 | [ ] |
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
- **2026-10-14** Pre-merge review of the documents against the code and the
  datasheets.  Found: the FC's 3.3 V buck has 7.2 µF of effective output
  capacitance against TI's 8 µF minimum, opened as D10 (fix before
  ordering); the battery-line simulation used revision 1's capacitance and
  stack lead for every design (fixed in `../sim/data.py`, every report run
  again); the Betaflight image had been built from an older `config.h`
  (rebuilt).  A fourth pass found the 5 V buck's enable tied to its input,
  which lets it run backwards on USB power: opened as D11 (fix before
  ordering).  The switching simulation now holds the off gate with the
  DRV8320H's 2 A ISTRONG, reads gate voltages on the die and counts the FET
  packages' inductance once; the losses take the body diode's real share of
  the dead time; every report was run again.  The off low-side FET's gate
  check is now marginal (1.76 V on the die at 150 °C; D2, D6, T5): rev 2
  has 19 checks passing, 1 marginal, 3 failing.  Decisions D1-D11 open.
  Nothing ordered.
- **2026-10-17** A question about trace corners: corner shape (miters,
  arcs, Euler bends) matters to neither board's signals or currents (edges
  of 1.7 ns or slower on traces a few centimetres long; at DC a corner
  moves a track's resistance by under half a milliohm), but the review
  found the 5 V rail's whole 2 A in its 0.2 mm feedback line: opened as
  D12.  The copper solver's strip and ring check, claimed and not in the
  repository, written (`../sim/selfcheck.py`): the solver is exact; the
  grid draws a track one 0.05 mm cell wider than it is.
- **2026-10-19** D10, D11 and D12 fixed, on the owner's word, in one change
  to the FC: a third 3.3 V output capacitor, the 5 V BEC's enable divider,
  feedback lines joined to their pours and hidden from the routers, 5 V and
  9 V at 0.5 mm.  The FC placed and routed again (DRC 0 / 0 / 0, every
  gate); `verify.py` 260 passed with every source.  The branch merged
  `main` (Print Hub, SmokeBreak).  Every simulation is being run again on
  the new FC.  REVISION stays 2.0: nothing of it was ordered.  Decisions D1-D9
  open.  Nothing ordered.
- **2026-10-20** D12 finished: every via on the 5 V, 9 V and video-battery
  nets is a 0.5 / 0.25 mm power via (`VIA_BY_NET`), after the review found
  the 5 V rail's 2 A in one 0.15 mm signal via; the FC routed again (DRC
  0 / 0 / 0, every gate); `verify.py` 263 passed with every source, 217
  without, a new check holding those nets to power vias.  Every
  simulation run again on this board: `../STRESS.md`, the eight variants,
  ground, both crashes and the punch.  No verdict changed (D12's
  **Result** has the 5 V figures); on the ground, both rails at 2 A in
  60 °C still air put 75 parts past their rating (99 before), and the
  video stays on 71 % of the time at 25 °C (69 %).  `sim/stress.py` now
  sorts the X7R and X7S capacitor rows by name as well as limit (their
  order had come from a set), and keeps each finished design's result in
  `sim/out/`, named by a hash of all it reads, so a run stopped by a
  container restart takes up again.  Decisions D1-D9 open.  Nothing
  ordered.
