# Products, revisions and their tests

## Names

- **Product:** one folder per product under `products/`, named after it
  (`products/print-hub/`). It is edited in place for the product's whole
  life: there are no revision folders. Variants of one line sit together in
  a family folder (`products/ridge/ridge-3/`, `products/ridge/ridge-3-lite/`),
  each still a product of its own ([repo-structure.md](repo-structure.md)).
- **Revision:** one orderable design of a product, numbered `N.M` (1.0,
  2.0, 2.1). The number is set in one place in the product's code, printed
  on the board, and listed in the product README's **Revisions** table.
  The PR that changes it says so.

Where each product sets its revision, and what the board prints:

| Product | Set in | Printed |
|---|---|---|
| Canary | `src/finish.py` (silkscreen and title block), `src/schematic.py` (title block) | `CANARY v1`, `v1  2026` |
| LayerCam | `REV` in `src/silk.py` | `V1` on all three boards |
| Mesh Radio | `REV` in `src/silk.py` | `V1` |
| Packet Logger Carrier | `src/design.py` (silkscreen), `src/emit_kicad.py` (title block), `src/emit_gerber.py` (Gerber header) | `PACKET LOGGER CARRIER V1` |
| Print Hub | `REV` in `src/silk.py` | `V1` |
| Ridge 3 | `REVISION` in `src/fc_layout.py` and `src/esc_layout.py`, one per board | `REV 2.0` |
| Ridge 3 Lite | `REV` in `src/silk.py` | `V1` |
| SmokeBreak | `src/make.py` (the bottom silkscreen) | `v1.0` |

A board prints its revision in its own style (`V1` is revision 1.0). Never
derive it from a folder name: a moved folder must not change the copper.

## When the number changes

| Change | Revision |
|---|---|
| Docs, comments, tests, CI | same |
| Anything in the fab files **before** the revision is ordered | same; every test whose inputs changed runs again (CI re-runs the build gates on every push; a copper change re-runs every simulation, a silkscreen-only change none) |
| After the revision has been ordered: anything that changes the Gerbers (copper, outline, drills, mask, silkscreen) | **next whole number** (1.0 → 2.0, Ridge 3's 2.0 → 3.0) |
| After the revision has been ordered: the Gerbers stay identical, only what is assembled changes (BOM or CPL) | **next minor** (2.0 → 2.1) |

The change that bumps the number also sets it in the code (so the board
prints it), adds a row to the README's Revisions table, and starts the new
revision's change list in the README or the product's `docs/`.

## Ordering freezes a revision with a git tag

A revision is frozen by a tag, not by a folder:

1. Before an order is placed, tag the commit its files come from:
   `git tag <product>-rev<N.M> <commit>` (`print-hub-rev1.0`,
   `ridge-3-rev2.0`) and push the tag.
2. Make a GitHub Release from the tag with the Gerber zip, BOM and CPL that
   were uploaded attached, so the exact files ordered are one click away.
3. Write the tag in the README's Revisions table (*Order tag*), and the
   order (date, fab, quantity) in the product's log.

The folder then moves on. To see or rebuild an ordered revision, download
its release or `git checkout <tag>`. Records of what the built boards
measured go in the product's folder on `main`, against the revision and its
tag.

Packet Logger Carrier 1.0 was ordered before this rule: its tag is still to
be made (its README says so).

## Tests belong to a revision

Each product has a **`TESTS.md`**: every test and simulation, why it
exists, how to run it, and its result, with the **revision and commit** it
ran on. A result never carries over from another revision; it is re-run on
the new design, even if nothing near it changed (the routed board always
differs).

A revision is ready to order only when every build gate and simulation in
`TESTS.md` has a result on its final commit (CI covers the build gates on
every push; the simulations are run by hand and recorded). Hardware rows
are filled in from the built boards after ordering, against the order tag.

## Starting a new revision: question the tests first

Before re-running anything for revision N+1, go through `TESTS.md` row by
row and decide, writing the answer beside the row:

- **Still needed?** Does the thing it tests still exist in the new design?
- **Still right?** Are its inputs (loads, temperatures, battery, parts,
  firmware) still the ones the product faces? Update them if not.
- **Missing?** Does the new design have a risk nothing tests yet (a new part,
  a new load, a field failure from the last revision)? Add a test.
- **Proven wrong by hardware?** Where measurements from built boards
  disagree with a simulation, fix the model before trusting it again.

Then bump the number, make the changes in place, and run the reviewed list.
The last revision's results stay readable at its tag.
