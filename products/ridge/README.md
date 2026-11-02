# Ridge

OffGrid's line of flight electronics for FPV quads, named by prop size:
**Ridge 3** for 3-inch quads now, Ridge 7 and Ridge 12 later. Each variant
is its own product, with its own folder, revision, tests and CI job.

| Variant | What it is | Revision | Status |
|---|---|---|---|
| [Ridge 3](ridge-3/) | Two-board stack: a 36 × 36 mm flight controller with HD or analog video, and a separate 4-in-1 ESC on a machined heatsink | 2.0 | designed and simulated, not yet ordered |
| [Ridge 3 Lite](ridge-3-lite/) | One 38 × 38 mm board with the flight controller and 4-in-1 ESC, no FPV parts, for Project Cheap Drone Phase 1 | v1 | designed, not yet built |

## How they differ

Ridge 3 and Ridge 3 Lite are separate designs for the same quads and share
no files.

| | Ridge 3 | Ridge 3 Lite |
|---|---|---|
| Boards | two (FC + ESC), connected by an 8-wire stack lead | one |
| Video | HD or analog, with OSD | none |
| Mount | 25.5 mm | 25.5 mm |
| When one part breaks | replace that board | replace the whole board |
| Firmware | Betaflight (its own target) and AM32, in `firmware/` | stock Betaflight TAKERG4AIO and AM32, in `firmware/` |

Each README has the details, how to order it, and its test record.
How revisions work: [`docs/versioning.md`](../../docs/versioning.md).
