# Fonts

The two typefaces of the OffGrid brand, vendored so that a build anywhere
draws the same letterforms.  Both are under the SIL Open Font License 1.1;
each licence file sits beside its font and goes wherever the font goes.

| File | Licence | Version (the font's own name table) | SHA-256 |
|---|---|---|---|
| `InstrumentSans-VariableFont.ttf` | `OFL-InstrumentSans.txt` | Version 1.000 (gftools 0.9.28); axes width 75-100, weight 400-700 | `b24f1812584816958afcf22e22d08e44318c5e51651e25d2438efdde389b33b1` |
| `JetBrainsMono-VariableFont.ttf` | `OFL-JetBrainsMono.txt` | Version 2.211; axis weight 100-800 | `48715a42ec242c21e9f02692891e147d022299a52e48d5e413e1a942193ffeda` |

The projects, as their licence files name them: Instrument Sans
(<https://github.com/Instrument/instrument-sans>) and JetBrains Mono
(<https://github.com/JetBrains/JetBrainsMono>).  Where these copies were
downloaded from, and at which commit or release, was not recorded; the
version above is what the files themselves say.

## What uses them

- **The silkscreen** of both boards: `../src/brand.py` shapes the type with
  HarfBuzz from these files and draws it as filled outlines, which
  `../src/artwork.py`, `../src/fc_layout.py` and `../src/esc_layout.py`
  place.  Pad names, part codes and numerals are JetBrains Mono; words are
  Instrument Sans.  The Gerbers carry the outlines, so nobody needs the
  fonts installed to order a board.
- **The stack sheet** (`../images/ridge3-stack.png`): its type is
  Instrument Sans (`../src/fab.py`, `stack_sheet`).
- **The exploded-view videos**: the labels and the title are Instrument
  Sans (`../video/make_video.py`, `DEFAULTS['font']`, drawn by
  `../video/overlay.py`).
- `../src/verify.py` checks that both files are present and prints the
  start of each one's SHA-256 in `../VERIFICATION.md`.

Another version of either font can move the silkscreen outlines, and with
them the committed Gerbers: check a replacement's SHA-256 against this
table before a rebuild.
