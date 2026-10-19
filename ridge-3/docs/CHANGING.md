# Changing Ridge 3: how to apply a decision

How to carry a decision from [`STATUS.md`](STATUS.md) into the design, for
an engineer or an AI agent.  The design is the Python in `../src/`; the board
files, Gerbers, BOMs and renders are generated from it.  Never edit a
`.kicad_pcb`, a Gerber or a BOM by hand for a change that is meant to stay
(the one exception, a prototype BOM variant, is in C1).

Commands run from the `ridge-3/` folder.  The tools and their setup are in
the main README:
[How it is made](../README.md#how-it-is-made-and-how-to-change-it) for the
boards (the pinned toolchain, or its Docker image), [Stress
simulations](../README.md#stress-simulations) for `sim/`, and
[`../firmware/README.md`](../firmware/README.md) for the firmware images.

## The loop, for any change

1. **Edit the source:** `src/circuit.py` (parts and connections),
   `src/parts.py` (orderable parts: footprint, LCSC and maker part numbers),
   `src/fc_layout.py` / `src/esc_layout.py` (placement, copper, silkscreen).
   Copy part numbers from the distributor's or maker's page; never type one
   from memory.
2. **Rebuild:** `python3.12 src/make.py esc` (or `fc`, or both with no
   argument).  From the committed board file it refreshes each part's value
   and LCSC number from `circuit.py` (a part swapped for another on the same
   land needs no new layout), runs DRC and the netlist check, and writes
   every output.  A part whose land changed stops it: then
   `python3.12 src/make.py --reroute esc`, which places and routes the board
   again (Freerouting 1.9.0, Java and `xvfb-run`; `make.py --help`).  A new
   land and its 3D model come into `aio.pretty` and `aio.3dshapes` as the
   README's [footprints](../README.md#adding-a-parts-footprint-and-3d-model)
   note says.  Plain `make.py` keeps the committed board's outline and
   silkscreen: after a change to them (`src/*_layout.py`, `src/artwork.py`,
   `src/brand.py`) or to `REVISION` (step 6), run
   `python3.12 src/make.py --artwork esc` (or `fc`, or both with no
   argument, which also draws the stack sheet again).
3. **Verify:** `python3.12 src/verify.py` writes `VERIFICATION.md` and
   exits 1 on any failure.  Its datasheet checks need the datasheets'
   text (`RIDGE3_DATASHEETS`, [`DATASHEETS.md`](DATASHEETS.md)) and its
   firmware checks the firmware sources (`AM32_SRC`, `AM32_BL_SRC`,
   `BF_SRC`, at the commits in `../firmware/README.md`); without them those
   checks SKIP.  Commit a `VERIFICATION.md` made with all of them, and
   with `OFFGRID_BRAND` for the mark's check (the README's *What
   `verify.py` reads from outside the repository*).  A new
   part with figures checked in `verify.py` needs its entry there and its
   datasheet in `DATASHEETS.md`.
4. **Simulate:** `sim/.venv/bin/python sim/stress.py` writes `STRESS.md`
   and `images/stress/` (about 3 h 25 min on four cores; it needs both
   revisions' FET models).  Then `sim/stress.py --variant=rev2`, which
   writes the `found.json` that `sim/crash.py`, `sim/punch.py` and
   `sim/ground.py` start from, and those three.  The README's [Stress
   simulations](../README.md#stress-simulations) has the order, the model
   libraries and the times.  For a change that is still being evaluated,
   run it as a variant instead (C2): `stress.py --variant=NAME`, then
   `crash.py --variant=NAME` and `variants.py`.  The reports go to
   `sim/results/`, which is committed with the documents that quote it;
   the caches stay in `sim/out/`, which is not.  The conclusions go in
   `RELIABILITY.md`.
5. **Document:** the README where it states the changed fact, the revision's
   change list (`REV2.md`, or the next revision's), `RELIABILITY.md` if its
   numbers moved, the rows of [`../TESTS.md`](../TESTS.md) whose runs were
   repeated (result and date), and in `STATUS.md` the decision, its date
   and a log line.
6. **Revision:** a change to the copper of a revision that has been
   ordered is a new revision: `REVISION` in `src/fc_layout.py` or
   `src/esc_layout.py` (printed on the board), and a new change list.
   Before a revision's first order its changes join its own change list
   (D10-D12 went into revision 2.0's).  Before an order is placed, tag the commit its files
   come from (`git tag ridge-3-rev2.0 <commit>` and push the tag) and
   record the tag in `STATUS.md`'s log.  A later copper change bumps
   `REVISION` and starts a new change list; the ordered files stay at their
   tag (`STATUS.md`, D9).
7. **Commit** the source and every output it regenerated together.  The
   committed outputs must be what the scripts produce: the `ridge-3` CI job
   rebuilds the fab files (`make.py --fab-only`) and fails if any differs.

## C1. Gate-drive strength to 30 / 60 mA (D2)

- **For a prototype order only:** in the BOM you upload, change the IDRIVE
  line from LCSC C295816, RC0201FR-0775KL (75 kΩ) to LCSC **C295780**,
  RC0201FR-0718KL (18 kΩ).  It is line 11 of each ESC BOM: for single
  boards `../esc/production/ridge3-esc-bom-jlcpcb.csv` (`75k,
  "R9,R21,R33,R45"`) and `ridge3-esc-bom-pcbway.csv`; for a panel, the
  same files in `../esc/production/panel/` with `-panel` in their names
  (`R9_1` ... `R45_6`, 24 parts).  These commands, run from `ridge-3/`,
  write changed copies of the single-board BOMs outside the repository,
  changing only line 11 (the value, LCSC number, part number and, in the
  PCBWay file, the description); [`TEST_PLAN.md`](TEST_PLAN.md) has the
  panel's:

  ```
  sed '11s/^75k,\(.*\),C295816,RC0201FR-0775KL,/18k,\1,C295780,RC0201FR-0718KL,/' \
    esc/production/ridge3-esc-bom-jlcpcb.csv > ~/ridge3-esc-bom-jlcpcb-18k.csv
  sed '11s/,RC0201FR-0775KL,Resistor 75k 1% 0201,75k,\(.*\),C295816,/,RC0201FR-0718KL,Resistor 18k 1% 0201,18k,\1,C295780,/' \
    esc/production/ridge3-esc-bom-pcbway.csv > ~/ridge3-esc-bom-pcbway-18k.csv
  ```

  Upload the `-18k` BOM with the unchanged Gerbers and CPL.  Do not commit
  such a BOM: CI would fail on it.
- **For the design:** in `src/circuit.py` set `IDRIVE = 0.03` (beside
  `IDRIVE_LEVELS`, which maps it to `R18K_0201` to AGND) and rewrite the
  comment above `IDRIVE_LEVELS` with the reason and the measured T5
  results.  Only 0.03 and 0.06 share the land and the nets: 0.03 needs
  only `python3.12 src/make.py esc`, which rewrites the BOMs and CPLs;
  0.12 (no resistor) and 0.26 (75 kΩ to DVDD) change the nets and need
  `python3.12 src/make.py --reroute esc`.  The switching simulation reads
  `IDRIVE` from `circuit.py`; run `sim/stress.py` for a new `STRESS.md`
  (the `idrive30` variant already gives its numbers).  Update the texts
  that quote 60 / 120 mA or its figures: the README's *Headroom* (the
  punch's FET peaks), `REV2.md` (the gate drivers' row), `STATUS.md` (D2),
  `TEST_PLAN.md` (T5 and what to order), `RELIABILITY.md`, and the
  comment in `../firmware/am32/AM32_2738df3_RIDGE3_F421_target.patch`.  The
  patch's comment does not change the image, but it changes the patch's
  SHA-256: run `(cd firmware && sha256sum am32/AM32_2738df3_RIDGE3_F421_target.patch)`
  and put the line it prints in place of the patch's line in
  `../firmware/README.md` (`verify.py` checks it; the paths there are
  relative to `firmware/`),
  and check that the patch still applies (`git apply --check` in an AM32
  checkout at `2738df3`).

## C2. Evaluating and changing the ESC's FETs (D1)

Evaluate a candidate in the simulations first, without touching the design
(this is how the BSZ040N06LS5 was rejected):

1. `sim/data.py`: a dict for the part from its datasheet, the same fields as
   `ISZ023N06LM6` and `BSZ040N06LS5` (ratings, thermal impedance,
   on-resistance against temperature, charges, body diode), each value
   with its source; add it to `FETS_BY_NAME`.
2. `sim/spice.py`: an entry in `FETS` for the maker's SPICE model (library,
   subcircuit, any solver option the model needs; see `BSZ040N06LS5`).
   Put the maker's library in `sim/out/spice/`, or point an environment
   variable at it as `spice.py` does for the others: makers' models are not
   committed.  A part with no published model cannot go through the
   switching simulation; say so in `RELIABILITY.md`.
3. `sim/data.py`: a variant in `VARIANTS` naming the FET, then
   `sim/stress.py --variant=NAME` (about 1.5-2.5 h on four cores),
   `sim/crash.py --variant=NAME` (about 21 minutes) and `sim/variants.py` to
   compare it with the others (`sim/results/VARIANTS.md`).
4. If it is adopted: its entry in `src/parts.py` (footprint, LCSC, maker part
   number, DigiKey number, maker).  On the same land as the ISZ023N06LM6
   (check the maker's recommended land against
   `aio:TSDSON-8FL_L3.3-W3.3-P0.65_IFX`) it can reuse that footprint; if not,
   add its footprint and its 3D model (the README's
   [footprints](../README.md#adding-a-parts-footprint-and-3d-model) note),
   and expect a `--reroute`.  Its body height goes in `src/parts.py`'s
   `HEIGHTS` (the heatsink stops without one).  Any new part on the ESC's
   bottom, the low-side FETs included, makes the heatsink again whatever
   its height, because the heatsink's record names each pocketed part
   (`heatsink.current`).  That needs CadQuery (`CADQUERY_PYTHON` pointing
   at a venv made from `../requirements-cadquery.txt`) and rewrites the
   STEP, STL, DXF and PDF in `../mechanical/`: send the CNC shop the new
   files.
5. `src/circuit.py`: the two `add('Q', 'ISZ023N06LM6', ...)` lines of the
   ESC channel (high and low side) and the summary at the top of the file.
6. `sim/data.py`: `DESIGNS['rev2']`'s `FET`, so `STRESS.md` describes the
   design as built.
7. `src/verify.py` is tied to the part by name (`grep -n ISZ023N06LM6
   src/verify.py`): the datasheet figures `fet_vds`, `fet_vgs`, `fet_rds`,
   `fet_rds45` and `fet_qg` (with the new datasheet's text file and
   patterns), the pin map `ISZ023N06LM6_PINS`, the part name where the ESC's
   FETs are picked out and in the voltage-rating table `RATED` (a part
   missing there skips the 60 % rule), and the docstring.  The new
   datasheet goes in `RIDGE3_DATASHEETS` and in
   [`DATASHEETS.md`](DATASHEETS.md).
8. Rebuild (`python3.12 src/make.py esc`, or `--reroute esc`), verify
   (`python3.12 src/verify.py`), then `sim/stress.py`,
   `sim/stress.py --variant=rev2`, `sim/crash.py`, `sim/punch.py` and
   `sim/ground.py`, in that order.  The overcurrent monitor's trip currents
   depend on the FET's on-resistance (`crash.py` prints them): check them
   against a punch again.
9. The README's cost and sourcing sections, the change list, `STATUS.md`,
   and the AM32 target patch's comment ("60 V Infineon OptiMOS 6 FETs"),
   then the patch's SHA-256 in `../firmware/README.md` (C1).

## C3. AM32's stuck-rotor cut after 3 timeouts (D3)

In AM32 at the commit the target is built on (`2738df3`), the stuck-rotor
cut is not a setting: `Src/main.c` declares `char bemf_timeout = 10;`, sets
it to 100 at low throttle (`adjusted_input < 150`) and to 10 above it
(lines 2064-2067), and cuts the motor when
`bemf_timeout_happened > bemf_timeout` (line 1144).

1. In an AM32 checkout at `2738df3`, apply the target patch (`git apply`;
   it changes only `Inc/`, so the line numbers above hold).  In
   `Src/main.c`, replace the high-throttle assignment `bemf_timeout = 10;`
   at line 2067 with `#ifdef RIDGE3_F421` / `bemf_timeout = 2;` / `#else` /
   `bemf_timeout = 10;` / `#endif`.  Then write the patch again from the
   checkout: `git diff > <this repo>/ridge-3/firmware/am32/AM32_2738df3_RIDGE3_F421_target.patch`.
2. Build the image as `../firmware/README.md` describes and replace
   `AM32_RIDGE3_F421_2.21.hex` with it.
3. Replace both hash lines in `../firmware/README.md`, the patch's and the
   image's: `(cd firmware && sha256sum am32/AM32_2738df3_RIDGE3_F421_target.patch am32/AM32_RIDGE3_F421_2.21.hex)`
   prints both lines as the README lists them (paths relative to
   `firmware/`).  `verify.py`, and so CI, fails on either.
4. Update the texts that quote 11 timeouts or 248 ms: the README's
   *Headroom*, `STATUS.md` (D3), `TEST_PLAN.md` (T7), `RELIABILITY.md`
   (the crash and recommendation 5) and `../TESTS.md`'s crash rows (after
   running `sim/crash.py` again).
5. `sim/crash.py` already models it (`N_CUT_SHORT`); test T7 and T13 on
   hardware before it ships.

## C4. The FC's 3.3 V inductor (D5)

The part is `L470N_TFM` in `src/parts.py` (TDK TFM252012ALMAR47MTAA,
LCSC C404800, footprint `aio:IND-SMD_L2.5-W2.0_TFM252012ALMA2R2MTAA`), used
once in `src/circuit.py` (`ref='L_3V3'`).  Its saturation current is checked
in `src/verify.py` (`tfm_r47`, and the `ISAT` table) and its resistance and
temperature limit are in `sim/data.py` (`'L_3V3'`).  For another part: a new
entry in `parts.py` with its own numbers, the maker's land drawing compared
with the current footprint's pads (the same footprint if they match, else a
new one and `--reroute fc`), the `circuit.py` line, the `verify.py` and
`sim/data.py` entries, then the loop.  Keep a 150 °C part.

## C5. The next ESC revision (D6)

These change the copper, so they make a new revision (the loop's step 6):

- **VDS resistor footprint, unfitted:** `src/circuit.py`, the DRV8320H's pin
  map (pin 20, `VDS`, now `None`), a resistor footprint to AGND marked not
  fitted; place it in the channel template in `src/esc_layout.py`.
- **nFAULT test pad:** pin 17 (now `None`) to a test pad on the top.
- **Kelvin sense:** each driver's SLx pins to its low-side FETs' sources and
  VDRAIN to the high-side drains, as their own traces, instead of the shared
  copper (`RELIABILITY.md`, the crash: up to 0.7 mΩ (low side) and
  0.9-1.0 mΩ (high side) of copper sits in what the monitor measures
  today).
- **SHx clamp or snubber**, if T5 calls for one, sized from its waveforms.
- **Off low-side gate**, if T5 shows the off low-side FET's gate reaching
  its threshold (`STATUS.md`, D2 and D6): the low-side gate drive returned
  closer to the FET's source (the DRV8320H sinks the low-side gates through
  PGND), or a gate-source capacitor or a Miller clamp at each low-side FET,
  sized from T5's waveforms.

Then `python3.12 src/make.py --reroute esc`, `verify.py`, every simulation,
and a change list for the new revision.
