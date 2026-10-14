# Products, revisions and their tests

## Names

- **Product:** one top-level folder per product, named after it
  (`ridge3-lite/`). Its `README.md` lists every revision and its status.
- **Revision:** one folder per revision inside it: `v1/`, `v2/`, ... A
  revision is one orderable design. Its number is the same everywhere: the
  folder, its README, the PR that adds it, and the silkscreen (Ridge 3 Lite
  prints it from the folder name, so a copy into `v2/` prints V2).

## When the number changes

| Change | Revision |
|---|---|
| Docs, comments, tests, CI | same |
| Anything in the fab files **before** the revision is ordered | same; every test whose inputs changed runs again (CI re-runs the build gates on every push; a copper change re-runs every simulation, a silkscreen-only change none) |
| Anything in the fab files **after** the revision has been ordered | **new revision** (`v2/` beside `v1/`; `v1/` stays as ordered) |

Once a revision is ordered its folder is frozen, apart from records of what
the built boards measured.

## Tests belong to a revision

Each revision has a **`TESTS.md`**: every test and simulation, why it
exists, how to run it, its result for **this** revision and the date and
commit it ran on. A result never carries over from another revision; it is
re-run on the new design, even if nothing near it changed (the routed board
always differs).

A revision is ready to order only when every build gate and simulation in
its `TESTS.md` has a result on its final commit (CI covers the build gates
on every push; the simulations are run by hand and recorded). Hardware rows
are filled in from the built boards after ordering.

## Starting a new revision: question the tests first

Before re-running anything for `vN+1`, go through `vN/TESTS.md` row by row
and decide, writing the answer in the new `TESTS.md`:

- **Still needed?** Does the thing it tests still exist in the new design?
- **Still right?** Are its inputs (loads, temperatures, battery, parts,
  firmware) still the ones the product faces? Update them if not.
- **Missing?** Does the new design have a risk nothing tests yet (a new part,
  a new load, a field failure from the last revision)? Add a test.
- **Proven wrong by hardware?** Where measurements from built boards
  disagree with a simulation, fix the model before trusting it again.

Copy `vN/` to `vN+1/` to start, then make the changes, then run the reviewed
list.
