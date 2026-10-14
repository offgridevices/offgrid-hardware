# Repository structure and size

## Layout

One folder per product, named after it; one folder per revision inside
([versioning.md](versioning.md)).

```
<product>/
  README.md                 every revision and its status
  v1/                       one revision; frozen once ordered
    README.md               what it is, requirements, status, next steps, ordering, bring-up, limits, build
    TESTS.md                every test and simulation, with this revision's results
    docs/decisions.md       the trade-offs and why
    <board>.kicad_pcb       the routed board (with .kicad_pro / .kicad_dru)
    production/             Gerber zip, BOM, CPL, netlist (what a fab needs)
    images/                 renders (compact PNG)
    mechanical/             STEP model, zipped
    src/                    the scripts that generate and check the board
    tools/                  pinned toolchain (Dockerfile) and helpers
    sim/                    simulations and their results
    docs/                   dated board-specific records (part audits, sourcing)
docs/                       how we build boards (this folder)
```

A board may add folders it needs (`firmware/`, `fonts/`), but keeps these
names for the ones above. (`packet-logger-carrier/v1` predates this layout
and stays as it was ordered.  `ridge-3/` predates it too: both boards of its
stack in one folder with no revision folder, the revision in its code and on
its silkscreen (`REV 2.0`), its trade-offs in `docs/RELIABILITY.md` and its
decisions in `docs/STATUS.md`; its `TESTS.md` and README are where this
layout puts them.  Where its next revision goes is decision D9 in its
`docs/STATUS.md`.)

## What gets committed

- **Source:** scripts, footprints, 3D models the renders need, fonts.
- **Outputs, once each:** the board file, the Gerber **zip** (not also the
  unzipped Gerbers), BOM, CPL, netlist, assembly drawing, compact renders,
  zipped STEP. Committed outputs must equal what the scripts produce; CI
  checks this. If the routing was finished by hand, the routed board file is
  the design of record and CI rebuilds from it (artwork, then fab files).
- **Not committed:** scratch and intermediate files (keep them in `out/`,
  which git ignores), downloaded datasheets, raw simulation data, duplicate
  or full-resolution images, anything a build regenerates that is not an
  output someone orders from.

## Size

- **Budget: the whole repository stays well under 1 GB.** A board revision
  should add tens of MB, not hundreds. Check before a PR:
  `git count-objects -vH` (repository) and the PR's own size
  (`git rev-list --objects origin/main..HEAD | git pack-objects --stdout | wc -c`).
- **Every binary version stays in history forever.** Regenerating outputs
  on each commit of a branch multiplies their size; **squash-merge** so
  `main` keeps one copy per merged change.
- Images: renders are saved as 256-colour PNG by the build (about a third of
  the size, no visible change). STEP is zipped; 3D models are `.stpZ`.
- If the repository nears its budget, move large generated binaries to
  release assets rather than deleting history.

## CI

Each board has a job in `.github/workflows/ci.yml` that runs its build in its
pinned toolchain, every gate included, and fails if the committed fab files
differ from the build. The build includes the artwork, so a brand change that
was not applied to the board fails CI. A new board adds its job in the same PR.
