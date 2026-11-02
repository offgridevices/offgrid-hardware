# Starting and finishing a board

## Before the first line of design

- **A folder in `products/`.** A new product gets `products/<product>/`,
  or `products/<family>/<product>/` when it is a variant of a line that has
  a family folder ([repo-structure.md](repo-structure.md)). It starts at
  revision 1.0, set in its code and printed on the board
  ([versioning.md](versioning.md)).
- **Latest KiCad.** Look up the current stable KiCad release and use it. Pin
  that exact version for the board (the official `kicad/kicad` Docker image,
  by digest) so its outputs stay reproducible. A later board starts again on
  whatever is latest then; an existing product keeps its pin.
- **Latest dependencies.** The same for everything else the board's tools
  use (Python packages, router, simulator): current stable versions at the
  start, pinned for the board. Check each download's source and checksum
  before installing.
- **Latest brand.** Pull `offgridevices/offgrid-brand` and build from its
  `current/` folder ([brand.md](brand.md)).
- **Requirements in writing.** The product README starts with what the
  board must do: size, environment (heat, current, voltage), parts
  availability, cost, and how each is checked. Keep the list; at the end it
  says which requirements were met.
- **A new revision of an existing product** is made in the product's own
  folder, and starts by questioning the last revision's tests
  ([versioning.md](versioning.md)).

## Design

1. **Circuit in code** (`src/`), every part with a manufacturer part number
   and an assembly part number (LCSC for JLCPCB). Choose parts that are in
   production today, and record the check with its date in the board's
   `docs/`.
2. **Placement, then routing.** Reserve room for the artwork (logo, flag)
   during placement; on a dense board nothing is left after routing.
3. **Power copper first.** Give the supply as much parallel copper as the
   return ([lessons.md](lessons.md)).
4. **DRC: 0 errors, 0 warnings, 0 unconnected**, with the fab's own limits
   as the rules.

## Done means all of these

A board is not finished, and not merged, until:

- [ ] **Every simulation** that applies has run on the routed board and
      passes, or its limit is written in the README's *Limits*: switching
      (spikes, slew), supply transients (hot plug, braking), each regulator,
      each sensing chain, and **thermal under worst-case stress** (hottest
      environment, sustained full load, stalled load, weak airflow).
- [ ] **Every check** passes: DRC 0 / 0 / 0, nets equal the circuit, BOM and
      CPL equal the placed parts, firmware pin maps against the firmware's
      own source.
- [ ] **CI builds the board**: `tools/ci.sh` runs every gate and checks that
      the committed fab files are what the scripts produce, with
      `tools/ci-setup.sh` and `tools/ci.json` beside it
      ([repo-structure.md](repo-structure.md#ci)); it passes locally
      (`tools/kd tools/ci.sh`) and as the product's job in CI.
- [ ] **Brand** artwork from the current brand version ([brand.md](brand.md)).
- [ ] **`TESTS.md`** lists every test and simulation; every build gate and
      simulation has its result on this revision's final commit (hardware
      rows follow once boards are built; [versioning.md](versioning.md)).
- [ ] **The revision is printed on the board** (silkscreen), from a
      constant in `src/`, never from a folder name.
- [ ] **README** has: what it is, the Revisions table, requirements and whether each was met,
      status, next steps, how to order, how to bring it up, limits, how to
      build; `docs/decisions.md` has the trade-offs.
- [ ] **This folder updated** if the board taught us something
      ([lessons.md](lessons.md)).

## Release

- One PR per revision, merged with **squash** so the history keeps one copy
  of each output ([repo-structure.md](repo-structure.md)). The product
  README's Revisions table gets the new status.
- **Ordering:** tag the commit the order's files come from
  (`<product>-rev<N.M>`), make a GitHub Release from it with the Gerber zip,
  BOM and CPL, and write the tag in the Revisions table
  ([versioning.md](versioning.md#ordering-freezes-a-revision-with-a-git-tag)).
- "Designed" is not "proven": the README status says *not yet built* until
  a board has been assembled and brought up.
