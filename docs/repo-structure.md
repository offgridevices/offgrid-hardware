# Repository structure and size

## Layout

Every product lives in `products/`, one folder each, named after it and
edited in place; there are no revision folders ([versioning.md](versioning.md)).
Variants of one line share a family folder with a short README that says
how they differ: `products/ridge/` (Ridge 3, Ridge 3 Lite) and
`products/layercam/` (LayerCam, LayerCam Pro). Each variant is still a
product of its own, with its own revision, `TESTS.md` and CI job.

```
products/
  <product>/                one product (or <family>/<product>/)
    README.md               what it is, Revisions table, requirements, status,
                            next steps, ordering, bring-up, limits, build
    TESTS.md                every test and simulation, with its result,
                            revision and commit
    docs/decisions.md       the trade-offs and why
    docs/                   dated product records (part audits, sourcing)
    design/                 optional: spec, research, concepts, design studies
    <board>.kicad_pcb       the routed board (with .kicad_pro / .kicad_dru)
    production/             Gerber zip, BOM, CPL, netlist (what a fab needs)
    images/                 renders (compact PNG)
    mechanical/             STEP model, zipped
    src/                    the scripts that generate and check the board
    sim/                    simulations and their results
    tools/                  pinned toolchain (Dockerfile, and kd to run in it)
                            and its CI: ci.sh, ci-setup.sh, ci.json
docs/                       how we build boards (this folder)
.github/workflows/          CI and the Claude review
```

A product may add folders it needs (`firmware/`, `fonts/`, `enclosure/` for
a printed case: its code and `print/` STLs; one folder per board when it
has several, as Ridge 3's `fc/` and `esc/` and LayerCam's `main/`, `ring/`
and `usb/`), but keeps these names for the ones above. Older products
differ in small ways their README describes: the Packet Logger Carrier keeps
its fab files at its top level and has no `TESTS.md`; Ridge 3 keeps its
trade-offs in `docs/RELIABILITY.md` and its decisions in `docs/STATUS.md`.

Scripts find what they need relative to their own folder or the
repository's root (the folder holding `.git`), never by counting folders
up, so a product can move without its outputs changing.

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

Each product carries its own CI in `tools/`:

- `ci.sh` runs every gate of the build, from the product's folder, and
  fails if a committed output differs from what the scripts produce.
- `ci-setup.sh` installs what CI needs on top of the bare pinned image (the
  packages the product's `tools/Dockerfile` adds, and the compilers and
  simulators its tests use).
- `ci.json` names the pinned image, by digest, and the job's timeout.

To run a product's CI on your machine exactly as CI does (same image, both
scripts), from the repository root: `tools/ci/local.sh products/<product>`.
It needs only Docker. Commit first: like CI, it compares the build against
`HEAD`.

`.github/workflows/ci.yml` finds the products by their `tools/ci.json`
(`tools/ci/matrix.py` at the repository's root picks them) and runs one job
per product, named after its folder (`canary`, `ridge-3-lite`; inside a
pull request's review run they show as `ci / canary`).
On a pull request it builds only the products whose folder changed, and
every product when a shared file changes (`.github/`, the root `tools/`,
`.gitignore`); pushes to `main`, a weekly run (Monday) and a manual run
build them all. A change to `docs/`, `README.md` or `LICENSE` alone builds
no board. Every run also has `repo-checks`: the Markdown link check
over every `.md`, a Python syntax check, and that every product has its
three CI files (`python3 tools/ci/check_repo.py`). One job, `ci-ok`, is
the check that must be green: it fails if any other job failed or was
cancelled.

The build includes the artwork, so a brand change that was not applied to
a board fails CI. (Ridge 3's job builds from the committed boards'
silkscreen without drawing it again, so there a brand or silkscreen change
is applied with its `make.py --artwork` before it is committed.) A new
product adds its three `tools/` files in the same PR; nothing in the
workflow changes.
