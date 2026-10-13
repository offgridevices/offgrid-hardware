# The brand on a board

## The source

All brand artwork comes from **`offgridevices/offgrid-brand`**, folder
`current/` (private repository; one version at a time). The version is the
`$version` field in `current/handoff/tokens/tokens.json`; geometry is in the
same file (`logo`, `logo.lockup`) and the SVGs in `current/handoff/logo/svg/`.

- **Never draw or approximate a logo.** Build it from the brand's own
  geometry and fonts: mark, lockup spacing, weights and tracking exactly as
  the tokens and SVGs give them.
- **Pull the latest brand at the start of every board and again before its
  release.** If the brand has changed, update the board's artwork to match
  before it is ordered.
- **Record the version** the artwork was built from, in the code that draws
  it (Ridge 3 Lite: `src/brand.py`).
- Only derived geometry belongs in this public repository: do not copy the
  brand repository's files here.

## How it maps onto a PCB

| Brand | Board |
|---|---|
| Pitch (ground) | matte black solder mask |
| Bone (type, mark) | white silkscreen |
| Ember (accent) | none: silkscreen has one colour |
| Gold detail | ENIG through a mask opening, over ground copper only |

- **Type:** labels in the brand's sans (Instrument Sans 500), codes and
  numerals in its mono (JetBrains Mono 500), from the font files in the
  board folder, turned into outlines so the Gerbers need no font.
- **Clear space** round the mark: at least the brand's minimum (one node
  radius).
- **Silkscreen floor:** strokes at least 0.15 mm, or the fab drops them.
  Below that size, simplify (fewer details), never distort.

## Reference

`ridge3-lite/v1/src/brand.py` draws the mark and lockup from the brand
geometry, and `src/silk.py` places them; start a new board from these.
