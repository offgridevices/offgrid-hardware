# SmokeBreak v1: design studies

The pictures each design decision was made from, and the scripts that draw
them. They are records, not part of the board's build. The decision each
one led to is in [`../decisions.md`](../decisions.md).

| Study | Question | Pictures | Script |
|---|---|---|---|
| [`arm/`](arm/) | The chosen form (concept 10, "Arm"), refined | `hero.png`, `top.png`, `showcase-*.png` | `arm.py` (Blender) |
| [`battery-side/`](battery-side/) | Where the battery plugs and the balance sockets go, so a pack's short leads reach both | `page/` | `sides.py` (Blender) |
| [`faceplate/`](faceplate/) | What the face says, and where | `concept-faceplate.png` | `concept_faceplate.py` (Chromium) |
| [`fuse/`](fuse/) | Soldered fuse, swappable blade fuse, or inline lead fuse | `a-board.png`, `b-*.png`, `c-inline.png` | `options.py` (Blender) |
| [`packs/`](packs/) | One Limit rocker, packs remembered by number, a thinner case | `1-…`, `2-…`, `3-….png` | `visuals.py` |
| [`stability/`](stability/) | Why a light box rocks when the switch is flicked, and the fix | `1-why-it-rocks.png`, `2-thumb-rest.png`, `3-underside.png` | `forces.py`, `grip.py` |
| [`face/`](face/) | The one-margin face with G2 corners; screen corners matched in the UI | `1-face-options.png`, `2-screen-corners.png` | `layout.py` |
| [`compact/`](compact/) | The compact case: face, height stack, grip | `1-compact-face.png`, `2-height.png`, `3-grip.png` | `study.py` |

The 20 form-factor concepts the Arm was chosen from are in
[`../concepts/`](../concepts/).

Scripts marked Blender run in Blender's Python (`bpy`); the others run in
any Python with Pillow and matplotlib. Fonts come from `../../fonts/`, and
the logo from `../../src/brand.py`. Images are committed as 256-colour PNG,
at most 1200 px wide. Videos are not committed; the scripts render them
again.
