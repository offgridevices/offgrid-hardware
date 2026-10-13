# Repository structure and size

## Layout

One folder per board, named after the board; one folder per revision inside.

```
<board-name>/
  v1/                       one folder per revision; never edited once ordered
    README.md               what it is, status, ordering, bring-up, checks, limits, build
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
and stays as it was ordered.) A change that alters copper is a new revision
folder beside the old one.

## What gets committed

- **Source:** scripts, footprints, 3D models the renders need, fonts.
- **Outputs, once each:** the board file, the Gerber **zip** (not also the
  unzipped Gerbers), BOM, CPL, netlist, assembly drawing, compact renders,
  zipped STEP. Committed outputs must equal what the scripts produce; CI
  checks this.
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
differ from the build. A new board adds its job in the same PR.
