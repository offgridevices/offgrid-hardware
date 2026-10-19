# SmokeBreak: design

How SmokeBreak came to be, before any one revision: what it should do, what
pilots complain about, the forms considered, and the studies behind the
face and the case. Every revision builds on these; they are records, not
part of any board's build. The decision each study led to is in
[`v1/docs/decisions.md`](../v1/docs/decisions.md).

| File or folder | What |
|---|---|
| [`spec.md`](spec.md) | the original product spec (10 Oct 2026), kept as written |
| [`market-research.md`](market-research.md) | other smoke stoppers and what their users complain about |
| [`concepts/`](concepts/) | the 20 form-factor concepts; **10 Arm** was chosen |

## Design studies

The pictures each design decision was made from, and the scripts that draw
them.

| Study | Question | Pictures | Script |
|---|---|---|---|
| [`arm/`](arm/) | The chosen form (concept 10, "Arm"), refined | `hero.png`, `top.png`, `showcase-*.png` | `arm.py` (Blender) |
| [`battery-side/`](battery-side/) | Where the battery plugs and the balance sockets go, so a pack's short leads reach both | `page/` | `sides.py` (Blender) |
| [`faceplate/`](faceplate/) | What the face says, and where | `concept-faceplate.png` | `concept_faceplate.py` (Chromium) |
| [`fuse/`](fuse/) | Soldered fuse, swappable blade fuse, or inline lead fuse | `a-board.png`, `b-*.png`, `c-inline.png` | `options.py` (Blender) |
| [`packs/`](packs/) | One Limit rocker, packs remembered by number, a thinner case | `1-…`, `2-…`, `3-….png` | `visuals.py` |
| [`stability/`](stability/) | Why a light box rocks when the switch is flicked, and the fix | `1-why-it-rocks.png`, `2-thumb-rest.png`, `3-underside.png` | `forces.py`, `grip.py` (Blender) |
| [`face/`](face/) | The one-margin face with G2 corners; screen corners matched in the UI | `1-face-options.png`, `2-screen-corners.png` | `layout.py` |
| [`compact/`](compact/) | The compact case: face, height stack, grip | `1-compact-face.png`, `2-height.png`, `3-grip.png` | `study.py` |

## Running the scripts

- **Blender** scripts run in Blender's Python (`bpy`); its version is pinned
  in [`v1/enclosure/requirements-render.txt`](../v1/enclosure/requirements-render.txt).
  Those that show the screen (`arm.py`, `grip.py`) need the frames that
  `python3 v1/ui/screens.py` renders first.
- The **others** run in any Python with Pillow and matplotlib.
- Fonts come from [`v1/fonts/`](../v1/fonts/), the logo from
  [`v1/src/brand.py`](../v1/src/brand.py) and the screens from
  [`v1/ui/`](../v1/ui/).

Images are committed as 256-colour PNG, at most 1200 px wide. Videos are not
committed; the scripts render them again.
