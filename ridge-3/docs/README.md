# Ridge 3: the board's records

Start with the board's [README](../README.md): what the stack is, how to
order, assemble and bring it up, and how it is made.  This folder holds the
rest, and is where the board's progress is kept.

| File | What it holds |
|---|---|
| [STATUS.md](STATUS.md) | **Start here when taking the board on.**  Where it stands, the decisions still open with their options and a recommendation, what to do before prototypes and before volume, and a dated log |
| [TEST_PLAN.md](TEST_PLAN.md) | The tests for the first prototypes: equipment, procedure, the simulated value each test checks, pass criteria, and the decision it settles |
| [CHANGING.md](CHANGING.md) | How to carry a decision into the design: which files to edit, which commands rebuild and re-check it |
| [RELIABILITY.md](RELIABILITY.md) | The reliability review: design variants side by side, a motor jammed at full throttle, a full-throttle punch, the stack on the ground, and the recommendations |
| [REV2.md](REV2.md) | Every change from revision 1, and why |
| [MOUNTING.md](MOUNTING.md) | The mounting holes and slots, and why they are where they are |
| [DATASHEETS.md](DATASHEETS.md) | The datasheets `verify.py` reads (not committed): each file's name, document and revision, how its text was made, and the hashes of the copies used |
| [research/](research/) | The research behind the revision 1 part choices: ESC power stage, FC video, sourcing |
| `tests/` | Test results, one dated file per test (`TEST_PLAN.md`, *Recording results*); created with the first result |

The simulations these documents quote are in `../sim/`: `../STRESS.md` is
their main report, and the others (the variants, the crash, the punch, the
ground runs) are committed in `../sim/results/`.  The design checks are in
`../VERIFICATION.md`.
