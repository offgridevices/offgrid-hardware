# SmokeBreak industrial-design concepts

Twenty form-factor and UX concepts for SmokeBreak (spec: [`../SPEC.md`](../SPEC.md)),
plus 00, the flat box from the spec, for comparison. Give feedback by number.

- [`reel.mp4`](reel.mp4): every concept turning, one after another (63 s)
- [`contact-sheet-3d.png`](contact-sheet-3d.png): every 3D render in one grid
- [`contact-sheet-2d.png`](contact-sheet-2d.png): every 2D design sheet in one grid

| # | Concept | Views |
|---|---|---|
| 00 | [Flat Box](00-flat-box/concept.md) | [3D](00-flat-box/hero.png) · [top](00-flat-box/top.png) · [spin](00-flat-box/turntable.mp4) |
| 01 | [Baton](01-baton/concept.md) | [3D](01-baton/hero.png) · [top](01-baton/top.png) · [spin](01-baton/turntable.mp4) · [sheet](01-baton/render.png) |
| 02 | [Puck](02-puck/concept.md) | [3D](02-puck/hero.png) · [top](02-puck/top.png) · [spin](02-puck/turntable.mp4) · [sheet](02-puck/render.png) |
| 03 | [Lantern](03-lantern/concept.md) | [3D](03-lantern/hero.png) · [top](03-lantern/top.png) · [spin](03-lantern/turntable.mp4) · [sheet](03-lantern/render.png) |
| 04 | [Halo](04-halo/concept.md) | [3D](04-halo/hero.png) · [top](04-halo/top.png) · [spin](04-halo/turntable.mp4) · [sheet](04-halo/render.png) |
| 05 | [Inline bar](05-inline-bar/concept.md) | [3D](05-inline-bar/hero.png) · [top](05-inline-bar/top.png) · [spin](05-inline-bar/turntable.mp4) · [sheet](05-inline-bar/render.png) |
| 06 | [Plug-through](06-plug-through/concept.md) | [3D](06-plug-through/hero.png) · [top](06-plug-through/top.png) · [spin](06-plug-through/turntable.mp4) · [sheet](06-plug-through/render.png) |
| 07 | [Field clip](07-field-clip/concept.md) | [3D](07-field-clip/hero.png) · [top](07-field-clip/top.png) · [spin](07-field-clip/turntable.mp4) · [sheet](07-field-clip/render.png) |
| 08 | [Cable spine](08-cable-spine/concept.md) | [3D](08-cable-spine/hero.png) · [top](08-cable-spine/top.png) · [spin](08-cable-spine/turntable.mp4) · [sheet](08-cable-spine/render.png) |
| 09 | [Crown](09-crown-dial/concept.md) | [3D](09-crown-dial/hero.png) · [top](09-crown-dial/top.png) · [spin](09-crown-dial/turntable.mp4) · [sheet](09-crown-dial/render.png) |
| 10 | [Arm](10-armed-toggle/concept.md) | [3D](10-armed-toggle/hero.png) · [top](10-armed-toggle/top.png) · [spin](10-armed-toggle/turntable.mp4) · [sheet](10-armed-toggle/render.png) |
| 11 | [Flip](11-flip-lid/concept.md) | [3D](11-flip-lid/hero.png) · [top](11-flip-lid/top.png) · [spin](11-flip-lid/turntable.mp4) · [sheet](11-flip-lid/render.png) |
| 12 | [Slide](12-slide/concept.md) | [3D](12-slide/hero.png) · [top](12-slide/top.png) · [spin](12-slide/turntable.mp4) · [sheet](12-slide/render.png) |
| 13 | [Bench Clock](13-bench-clock/concept.md) | [3D](13-bench-clock/hero.png) · [top](13-bench-clock/top.png) · [spin](13-bench-clock/turntable.mp4) · [sheet](13-bench-clock/render.png) |
| 14 | [Build Mat](14-build-mat/concept.md) | [3D](14-build-mat/hero.png) · [top](14-build-mat/top.png) · [spin](14-build-mat/turntable.mp4) · [sheet](14-build-mat/render.png) |
| 15 | [Battery Rider](15-battery-rider/concept.md) | [3D](15-battery-rider/hero.png) · [top](15-battery-rider/top.png) · [spin](15-battery-rider/turntable.mp4) · [sheet](15-battery-rider/render.png) |
| 16 | [Wall Tile](16-wall-tile/concept.md) | [3D](16-wall-tile/hero.png) · [top](16-wall-tile/top.png) · [spin](16-wall-tile/turntable.mp4) · [sheet](16-wall-tile/render.png) |
| 17 | [Tag](17-tag/concept.md) | [3D](17-tag/hero.png) · [top](17-tag/top.png) · [spin](17-tag/turntable.mp4) · [sheet](17-tag/render.png) |
| 18 | [Ignition](18-ignition-key/concept.md) | [3D](18-ignition-key/hero.png) · [top](18-ignition-key/top.png) · [spin](18-ignition-key/turntable.mp4) · [sheet](18-ignition-key/render.png) |
| 19 | [Instrument](19-instrument/concept.md) | [3D](19-instrument/hero.png) · [top](19-instrument/top.png) · [spin](19-instrument/turntable.mp4) · [sheet](19-instrument/render.png) |
| 20 | [Tips](20-tips/concept.md) | [3D](20-tips/hero.png) · [top](20-tips/top.png) · [spin](20-tips/turntable.mp4) · [sheet](20-tips/render.png) |

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
