# Starting and finishing a board

## Before the first line of design

- **Latest KiCad.** Look up the current stable KiCad release and use it. Pin
  that exact version for the board (the official `kicad/kicad` Docker image,
  by digest) so its outputs stay reproducible. A later board starts again on
  whatever is latest then; an existing board revision keeps its pin.
- **Latest dependencies.** The same for everything else the board's tools
  use (Python packages, router, simulator): current stable versions at the
  start, pinned for the board. Check each download's source and checksum
  before installing.
- **Latest brand.** Pull `offgridevices/offgrid-brand` and build from its
  `current/` folder ([brand.md](brand.md)).
- **Requirements in writing.** The revision README starts with what the
  board must do: size, environment (heat, current, voltage), parts
  availability, cost, and how each is checked. Keep the list; at the end it
  says which requirements were met.
- **A new revision of an existing product** starts by questioning the last
  revision's tests ([versioning.md](versioning.md)).

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
- [ ] **CI builds the board** on every push and checks that the committed
      fab files are what the scripts produce.
- [ ] **Brand** artwork from the current brand version ([brand.md](brand.md)).
- [ ] **`TESTS.md`** lists every test and simulation; every build gate and
      simulation has its result on this revision's final commit (hardware
      rows follow once boards are built; [versioning.md](versioning.md)).
- [ ] **The revision is printed on the board** (silkscreen).
- [ ] **README** has: what it is, requirements and whether each was met,
      status, next steps, how to order, how to bring it up, limits, how to
      build; `docs/decisions.md` has the trade-offs.
- [ ] **This folder updated** if the board taught us something
      ([lessons.md](lessons.md)).

## Release

- One PR per revision, merged with **squash** so the history keeps one copy
  of each output ([repo-structure.md](repo-structure.md)). The product
  README's revision table gets the new status.
- "Designed" is not "proven": the README status says *not yet built* until
  a board has been assembled and brought up.
