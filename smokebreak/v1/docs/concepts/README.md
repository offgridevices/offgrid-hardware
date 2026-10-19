# SmokeBreak industrial-design concepts

Twenty form-factor and UX concepts for SmokeBreak (spec: [`../spec.md`](../spec.md)),
plus 00, the flat box from the spec, for comparison. Give feedback by number.

**Chosen: 10 Arm**, developed in [`../design/arm/`](../design/arm/).

Logo rule (SPEC §11): the mark is never a part, light or frame. Every
status ring in these concepts is a plain closed ring; logos are exact
lockups from `../../src/brand.py`. **04 Halo is retired**: the product
itself is the mark's shape, which the rule forbids. Some write-ups (02,
09) still describe a Bind key on the ring's node; that predates the rule.

- [`contact-sheet-3d.png`](contact-sheet-3d.png): every concept's render in one grid

Each folder keeps the concept's write-up (`concept.md`), the CadQuery model
that draws it (`model.py`) and one render (`hero.png`). The turntable videos,
top views and design sheets are not committed: `_blender/render_concept.py`
renders them again from the models.

| # | Concept | Views |
|---|---|---|
| 00 | [Flat Box](../spec.md) (the spec's baseline) | [render](00-flat-box/hero.png) |
| 01 | [Baton](01-baton/concept.md) | [render](01-baton/hero.png) |
| 02 | [Puck](02-puck/concept.md) | [render](02-puck/hero.png) |
| 03 | [Lantern](03-lantern/concept.md) | [render](03-lantern/hero.png) |
| 04 | [Halo](04-halo/concept.md) | [render](04-halo/hero.png) |
| 05 | [Inline bar](05-inline-bar/concept.md) | [render](05-inline-bar/hero.png) |
| 06 | [Plug-through](06-plug-through/concept.md) | [render](06-plug-through/hero.png) |
| 07 | [Field clip](07-field-clip/concept.md) | [render](07-field-clip/hero.png) |
| 08 | [Cable spine](08-cable-spine/concept.md) | [render](08-cable-spine/hero.png) |
| 09 | [Crown](09-crown-dial/concept.md) | [render](09-crown-dial/hero.png) |
| 10 | [Arm](10-armed-toggle/concept.md) | [render](10-armed-toggle/hero.png) |
| 11 | [Flip](11-flip-lid/concept.md) | [render](11-flip-lid/hero.png) |
| 12 | [Slide](12-slide/concept.md) | [render](12-slide/hero.png) |
| 13 | [Bench Clock](13-bench-clock/concept.md) | [render](13-bench-clock/hero.png) |
| 14 | [Build Mat](14-build-mat/concept.md) | [render](14-build-mat/hero.png) |
| 15 | [Battery Rider](15-battery-rider/concept.md) | [render](15-battery-rider/hero.png) |
| 16 | [Wall Tile](16-wall-tile/concept.md) | [render](16-wall-tile/hero.png) |
| 17 | [Tag](17-tag/concept.md) | [render](17-tag/hero.png) |
| 18 | [Ignition](18-ignition-key/concept.md) | [render](18-ignition-key/hero.png) |
| 19 | [Instrument](19-instrument/concept.md) | [render](19-instrument/hero.png) |
| 20 | [Tips](20-tips/concept.md) | [render](20-tips/hero.png) |

## How the renders are made

`_blender/` holds a shared Blender kit (`studio.py`: materials, the Beacon
Ring, XT60/XT30, leads, screens, the brand arrow) and the renderer. Each
concept's `model.py` builds it at true size in millimetres.

```bash
pip install bpy                          # Blender 5.2 as a Python module
python _blender/render_concept.py 09-crown-dial --video
python3 _blender/make_gallery.py         # contact sheets and reel
```

Fonts come from `ridge-3/fonts` (branch `claude/fpv-stack-3in`); point
`SB_FONTS` at them.
