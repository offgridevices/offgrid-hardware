# Product videos

## To make a product video

Copy `ridge-3/video/` into the board's revision folder, write a few lines of
JSON with the board's title and what is on each side, and run
`make_video.py` in stages: `--check` builds the scene without frames,
`--stills` renders a few labelled frames to read, a 720p draft goes to the
owner, and `--final` renders 4K at 60 fps once a music edit of exactly the
video's length is in place. The house style is in the code: keep it. Read
the brand's version and record it. Publish the MP4; never commit it or the
music. Follow [Recipe for a new board](#recipe-for-a-new-board) step by
step, and stop when everything in [Done means](#done-means) holds.

**If you cannot reach the owner,** stop after the draft (step 6) and report
what you made and what is left: the music edit, the final render and
publishing wait until the owner has seen the draft. The draft needs no
music: add a track only if you can download it under OffGrid's Epidemic
Sound subscription (Ridge 3's is in
[`ridge-3/video/music/README.md`](../ridge-3/video/music/README.md));
otherwise leave `"music"` out, and the draft is silent. Read the brand's
version only from the brand repository; if you cannot read it, record no
version and say so in your report. Never guess it.

## What this is

A product video is an exploded view of a board, rendered from its own
routed KiCad file in the style the owner approved for Ridge 3. The code is
[`ridge-3/video/`](../ridge-3/video/), the reference copy. This page says
what to copy, what to fill in, how to check it and what to commit.

This is a plain document. No instruction file in this repository is loaded
into a contributor's AI assistant automatically (the root
[`.gitignore`](../.gitignore) says why editor settings are kept out). To
have an agent make a video, ask it to follow this page.

Each board gets its own copy of the code, in its revision folder. A
revision folder is frozen once its board is ordered, and a copy keeps a
later change of style from altering an old board's video. Change the style
only in the reference copy, with the owner's approval, and record the change
here.

## What the video shows

The video is 16:9, 32.75 s long for Ridge 3, with music. The board takes
itself apart and goes back together:

1. The board lies flat while a strip of light sweeps across it.
2. It stands on its edge and opens sideways into its layers: the parts on
   each side, each solder mask with its silkscreen printed on it, and every
   copper layer on its FR-4.
3. The camera stops on the top side's parts, then on all the copper at
   once, then on the bottom side's parts. A lower third names each stop.
4. The camera pulls back to the whole board, and every layer gets a label.
5. The board closes and lies down, and the product name comes in.

The labels are read from the board file: the copper layers and what each
one carries, which sides have silkscreen, and how many parts are on each
side. The board's JSON adds only a few words per side and the title. If the
board changes, run the command again.

## House style

Keep every item below. The code sets each one, so a copy keeps them. The
evidence for each is where it is set; the owner approved the result on the
Ridge 3 videos.

**Picture**

- [ ] **16:9, two qualities.** The final is 3840 × 2160 at 60 fps, 32
      Cycles samples, noise threshold 0.02. The draft is 1280 × 720 at
      30 fps, 12 samples, 0.05. Times are set in seconds, so the draft and
      the final have the same edit. *`make_video.py`, `QUALITY`.*
- [ ] **From the routed `.kicad_pcb`**, exported by `kicad-cli` as GLB with
      tracks, pads, zones, inner copper, silkscreen and solder mask. Never a
      hand-built model. *`make_video.py`, `export_glb`.*
- [ ] **The board as its build is assembled.** A part that the build leaves
      off keeps its pads, loses its body and leaves the part counts.
      *`make_video.py`, `build_copy`.*
- [ ] **It stands on its edge and opens sideways** across the frame. Layers
      part 0.125 s apart, outermost first, and close in reverse order. Each
      move takes 3.5 s, and every move and camera glide is cosine-eased.
      Gaps when open: 0.8 board widths beside the parts, 0.7 between copper
      layers, 0.5 elsewhere. *`make_video.py`, `timeline` and
      `DEFAULTS['gaps']`; `scene.py`, `explode`.*
- [ ] **The silkscreen stays on its solder mask.** They are one layer, not
      two. *`scene.py`, `printed`.*
- [ ] **Each copper layer is a card on the FR-4 below it.** The FR-4 is
      solid when closed and turns to tinted glass as the board opens
      (transmission 0.15 to 1.0, roughness 0.45 to 0.08), so the copper
      between the layers shows. *`scene.py`.*
- [ ] **No via barrels between the layers.** They leave the picture as the
      board opens and come back when it has closed. *`DEFAULTS['vias']` is
      `'hide'`.*
- [ ] **85 mm lens, no depth of field.** At these distances it blurred the
      layers. *`DEFAULTS['camera']` (`lens`); depth of field is off in
      `scene.py` (`dof.use_dof`) unless the camera settings set `"dof"`.*
- [ ] **Chip markings painted out.** The library models print a maker's
      logo and the package name on top; these are painted in the body
      colour. *`scene.py`.*
- [ ] **The board looks as ordered:** outer copper (0.80, 0.36, 0.20),
      metallic, roughness 0.26; inner copper at roughness 0.40; gold (ENIG)
      on the outer pads; near-black solder mask (0.014, 0.015, 0.017) with a
      clear coat; off-white silkscreen (0.80, 0.79, 0.75). Part materials are
      sorted into tin or silver, gold and black plastic. *`scene.py`,
      materials.*
- [ ] **Light and colour.** Cycles with OpenImageDenoise, the AgX view
      transform with the look "AgX - Medium High Contrast". Blender's own
      `studio.exr` lights the scene (rotated 120°, strength 0.8), while the
      camera sees a dark radial gradient, from (0.030, 0.032, 0.036) in the
      centre to (0.002, 0.002, 0.003) at the edge. A warm key light, a cool
      fill and a cool back light, scaled with the board's size from a 36 mm
      board. A sheen that lights only the copper, and only while the board
      is open (on the black solder mask it would look grey). A strip of
      light sweeps across the board in the first 4.6 s. *`DEFAULTS`:
      `look`, `world`, `lights`, `sheen`, `sweep`; `scene.py`.*
- [ ] **Camera shots fitted to what is in view**, never placed by hand: the
      camera distance is solved so that each shot's subject fills a set box
      of the frame. It starts wide on the flat board (azimuth −34°,
      elevation 30°), turns as the board stands (−44°, 14°) and opens
      (−40°, 12°), stops on each unit of the tour at elevation 12° (a
      bottom side from the right, where it faces, the rest from the left;
      it drifts from 37° to 34.5° while it rests), pulls back to the whole
      (−38°, 12°) and ends on the flat board (−20°, 30°). *`make_video.py`,
      `shots` and `DEFAULTS['camera']['frame']`; `scene.py`, `fit`.*
- [ ] **The tour stops on the parts**: the top side's, all the copper at
      once, the bottom side's. *`DEFAULTS['tour']`.*

**Edit**

All times are in seconds. The Ridge 3 flight controller has 6 copper
layers; the ESC has 8, so it takes a little longer to open and to close
(its tour comes about 0.12 s later). Its labelled hold is 0.23 s shorter: it
starts to close earlier, and both videos end at 32.75 s.

| Flight controller | ESC | What happens |
|---|---|---|
| 0–4.6 | 0–4.6 | Flat, wide shot; the light sweep |
| 2.25–4.75 | 2.25–4.75 | Stands on its edge |
| 4.5–8.57 | 4.5–8.68 | Opens, outermost layers first |
| 9.87 | 9.98 | Stop 1: the top side's parts (each stop rests 1.6 s, then glides 1.6 s to the next) |
| 13.07 | 13.18 | Stop 2: all the copper |
| 16.27 | 16.38 | Stop 3: the bottom side's parts, seen from the side they face |
| 19.27–23.17 | 19.38–23.05 | The whole board: the labels come in 0.17 s apart, each fading in over 0.5 s, and fade out over 0.6 s |
| 23.17 | 23.05 | Closes |
| 26.48–29.23 | 26.48–29.23 | Lies down |
| 29.48 | 29.48 | The title fades in over 0.8 s |
| 32.75 | 32.75 | End: 1,965 frames at 60 fps |

The timings are in `make_video.py`'s `timeline` and
`DEFAULTS['overlay']`. A board's `"timeline"` overrides any of these keys,
in seconds; Ridge 3's ESC sets `"hold": 3.2667`. Any other key stops the
run with the list of keys.

| `"timeline"` key | Default | What it times |
|---|---|---|
| `stagger` | 0.125 | Between neighbouring layers as they part and close |
| `move` | 3.5 | Each opening and closing move |
| `stand` | [2.25, 4.75] | Standing up: start and end |
| `tour_in` | 1.3 | From open to the first stop |
| `tour_rest` | 1.6 | The rest on each stop |
| `tour_move` | 1.6 | The glide to the next stop |
| `tour_out` | 1.8 | From the last stop back to the whole board |
| `hold` | 3.5 | The whole board with its labels, until it closes |
| `lay_in` | 0.75 | How long before the board has closed it starts to lie down |
| `lay` | 2.75 | Lying down, in all |
| `tail` | 3.5 | The closing shot, after it has lain down |

**Captions**

All sizes are for 720p and scale with the frame's height.

- [ ] **The tour's lower third**, at the bottom left (6.5 % of the width
      in, 80 % down): a counter such as "01 / 03" (13 px, Medium), the
      stop's name (32 px, Medium) and one line on what it is (18 px,
      Regular), over a soft black shade on the bottom third of the frame.
      *`overlay.py`.*
- [ ] **One label per layer on the whole board.** Labels alternate above
      the board (their bottom at 20 % of the height) and below it (their
      top at 80 %), each on a hairline leader that ends in a dot on its
      layer. The copper's label has a bracket across the cards, parallel to
      the line of their edges, with a tick for each card. Labels in a row
      push each other apart. Title 17 px Medium, detail 13.5 px Regular,
      wrapped at 200 px. *`overlay.py`.*
- [ ] **Nothing crosses a layer.** Every leader, bracket, label, caption
      and title is checked against every layer's outline in every labelled
      frame, and the run prints each overlap. *`overlay.py`, `check`.*
- [ ] **Words.** Sentence case, short and factual. The titles are made by
      the code: "Top side", "Solder mask", "Copper layers", "Bottom side".
      A detail reads like "38 parts: processor, gyro, flash, USB-C, stack
      plug, HD video pads" or "6 layers: ground and 3.3 V planes, 4 signal
      layers". *`make_video.py`, `labels`.*
- [ ] **Highlights name functions, not part numbers,** and only parts that
      are on that side in this revision and the build shown.
- [ ] **About 70 characters at most per detail**, part count included:
      three lines in the whole view, one line in the lower third. Ridge 3's
      longest is 70.
- [ ] **The end card** is the product name, large, with one line saying
      what it is, at the bottom left (7.5 % in, 82 % down): 46 px SemiBold
      and 20 px Regular. Nothing else: no logo, no web address.
- [ ] **Type and colour.** All text is Instrument Sans, from the board
      folder's `fonts/`. Names are near-white (242 to 247 of 255), details
      and the counter grey (140 to 176), leaders and dots light grey (205
      to 238). No accent colour.
      *`DEFAULTS['font']`; `overlay.py`.*

**Sound and delivery**

- [ ] **One licensed track**, in the music library's own edit to the
      video's exact length, so the music ends with the picture.
- [ ] **Mixed** with a 0.6 s fade in, a 1 s fade out ending with the video
      and 1 dB of headroom, as AAC at 256 kb/s. A board can add
      `"music_gain_db"`. *`make_video.py`, `add_music`.*
- [ ] **MP4**: H.264 (libx264, CRF 16, preset slow, yuv420p) with
      `+faststart`, at the quality's frame rate. *`overlay.py`.*
- [ ] **Neither the music nor the video is committed.**

## Brand

[`brand.md`](brand.md) says where the brand comes from and how a board
carries it: the private repository `offgridevices/offgrid-brand`, folder
`current/`, whose version is the `$version` field of
`current/handoff/tokens/tokens.json`. Read the version from there before
the final render and record it in the board README's video section. Read
it only from the brand repository, never from memory or another board: if
you cannot read it, ask the owner for access, and without access record no
version and say so. Never copy the brand repository's files or text into
this repository.

Ridge 3's videos were checked against brand v3.2.

What the video takes from the brand:

- **Type.** Instrument Sans in sentence case: Medium (500) for names and
  Regular (400) for details. The font files are the board's own `fonts/`
  (SIL Open Font License), the same files its silkscreen is drawn from.
- **Ground.** Dark, like the brand's Pitch and the board's black solder
  mask.
- **Accent.** None. The brand's accent, Ember, is not used in the Ridge 3
  video.
- **Mark.** The OffGrid mark appears only as the board's own silkscreen,
  which the board's `src/brand.py` builds from the brand's geometry. Never
  draw or approximate a mark in the video.

**Open decisions.** The approved Ridge 3 video differs from brand v3.2 in
the points below. They are the owner's to decide. Until then, keep the
Ridge 3 look; do not change any of them on your own. For what the brand
says on each, read its `current/` folder.

1. **The end card's weight.** The product name is SemiBold (600). Compare
   the brand's weights for display type and for the wordmark.
2. **Colour.** The caption whites and greys, and the background gradient,
   are neutral or slightly cool. Compare the brand's dark theme: its
   ground, type, secondary text and hairlines.
3. **Numerals.** The tour counter ("01 / 03") is Instrument Sans;
   [`brand.md`](brand.md) sets numerals in JetBrains Mono 500.
4. **Tracking.** No letter tracking is applied. Compare the brand's
   tracking for display type and labels.
5. **The mark in motion.** Whether the video should show the mark beyond
   the silkscreen, and how the mark may move. Compare what the brand says
   about the mark in motion, and ask the owner.
6. **Imagery.** Whether photoreal renders of a board fit the brand's rules
   on imagery.

## Tools

| Tool | Version used for Ridge 3 | What it does |
|---|---|---|
| KiCad: `kicad-cli` and the `pcbnew` Python module | 10.0.6 | The GLB export; reading the board's facts |
| Python with `pcbnew` | 3.12.3 (`python3.12`, Ubuntu 24.04's) | Runs `make_video.py` |
| Python for the video venv | 3.11.15 (`python3.11`, or `$VIDEO_PYTHON`) | `video/.venv`, made on the first run; bpy needs 3.11 |
| bpy (Blender as a Python module) | 4.5.14 LTS | Builds the scene; renders with Cycles |
| numpy, Pillow, imageio-ffmpeg | 1.26.4, 12.3.0, 0.6.0 (bundles ffmpeg 7.0.2) | The captions, the MP4, the music |
| Instrument Sans | 1.000, variable (`fonts/`) | All text |
| A GPU (optional) | OptiX, CUDA, HIP, Metal or oneAPI | Rendering, when Blender finds one; otherwise the CPU |

Ubuntu 24.04 has no Python 3.11. The one that made the Ridge 3 videos is
the deadsnakes PPA's `python3.11` 3.11.15-1+noble1, with `python3.11-venv`
for the venv:

```
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.11 python3.11-venv
```

On 2026-10-14 the PPA offered 3.11.16-1+noble1, no longer 3.11.15.
KiCad 10.0.6 and the `python3.12` with `pcbnew` are installed as
[Setup in ridge-3/README.md](../ridge-3/README.md#setup) describes. The
Docker image of `ridge-3/tools/Dockerfile` has neither Python 3.11 nor
bpy, so the videos are made outside it.

`video/requirements.txt` pins every package in the venv. The venv takes
about 1.1 GB. On a 4-core CPU without a GPU, a 4K frame takes 2–4.5
minutes, so a full final video takes 65–147 hours. Render the final on a
GPU machine if there is one.

## Recipe for a new board

`<board>/<rev>` is the board's revision folder (for example
`ridge3-lite/v1`), and `<name>` is its `.kicad_pcb` file's name without
`.kicad_pcb`. Run every command from `<board>/<rev>`, except in step 1.

1. **Copy the reference code**, from the repository's root. This takes only
   the committed files: no venv, work files or music.

   ```
   git archive HEAD ridge-3/video | tar -x --strip-components=1 -C <board>/<rev>
   ```

   If `<board>/<rev>/fonts/InstrumentSans-VariableFont.ttf` does not exist,
   copy the fonts too, then make `fonts/README.md`'s "What uses them" this
   board's:

   ```
   git archive HEAD ridge-3/fonts | tar -x --strip-components=1 -C <board>/<rev>
   ```

2. **Make the copy this board's.** In `<board>/<rev>/video/`:
   - Delete `fc.json` and `esc.json`.
   - In `make_video.py`, set `BOARDS = {}`. Only a board whose
     `src/circuit.py` has Ridge 3's build API (`build`, `fitted`, `BUILDS`,
     `DEFAULT_BUILD`) may map a short name to its board file here, which
     is what makes `--build` work.
   - In `make_video.py`, change the texts that name Ridge 3: in the
     docstring, the examples, "Run it from ridge-3/", step 0 ("For fc and
     esc") and "(fc.json, esc.json)"; the help of `board` and `--build`;
     and the message `--build is for fc and esc`.
   - Check three assumptions the code makes, and change the code where
     they do not hold for this board:
     - `DEFAULTS['mask']` says "gold pads show through", and `scene.py`
       gives every outer pad its `ENIG gold` material (`M_GOLD`): both hold
       only for an ENIG finish.
     - `human()` names only the `GND` and `VBAT` nets, and voltages written
       like `3V3` or `5V`. Other plane nets appear under their raw names.
     - `scene.py` paints out chip markings only on references that start
       with U or Q.
   - Rewrite `music/README.md` for this board (step 7 fills it in).
   - Add `*.mp4` to the board's own `.gitignore` (make one if there is
     none), as Ridge 3 does: a second guard, beside `video/out/`, against
     committing a video.

3. **Write `video/<name>.json`.** Every value comes from the design, not
   from memory:

   ```json
   {
     "title": ["<Product name>", "<What it is, in a few words>"],
     "highlights": {
       "top": "<the main parts on the top, by function>",
       "bottom": "<the main parts on the bottom, by function>"
     },
     "silkscreen": {"bottom": "<what that side's silkscreen shows, if worth saying>"}
   }
   ```

   - Take the highlights from `src/` and the BOM, and check which side each
     part is on in the placement file (CPL). Name parts by function
     ("processor, gyro, flash"), give counts where the circuit has them
     ("12 high-side FETs"), and put first the parts a reader cares about.
   - Keep each detail, "N parts: " included, to about 70 characters.
   - Leave the style alone. Other keys exist for facts the board file
     cannot give:
     - `labels` (`{unit: [title, detail]}`) replaces a label outright, the
       surest fix for a label that reads wrong.
     - `roles` (`{"In5.Cu": "ground plane"}`) sets what a copper layer
       carries. The keys are KiCad's layer names, as step 4's summary
       line prints them; a name the board does not have stops the run. In
       the copper label, a role ending in "plane" counts that layer as
       that net's plane ("ground plane": a ground plane), and any other
       role as a signal layer.
     - `tour` changes the stops (the units are `components top`,
       `mask top`, `copper`, `mask bottom`, `components bottom`).
     - `builds` holds settings for one build.
     - `timeline` changes the edit's times, in seconds; its keys and
       defaults are under **Edit** in [House style](#house-style).

4. **Check the scene, without frames:**

   ```
   python3.12 video/make_video.py <name>.kicad_pcb --check
   ```

   The first run makes `video/.venv`. Read the summary line: the copper
   layers and what each carries (as read from the board, before any
   `roles`), the sides with silkscreen, the parts per side and the length.
   Compare it with the board's README and circuit. If a plane, a net or a
   count reads wrong, fix it in the JSON (`labels`, `roles`) and run the
   check again. The labels themselves are in
   `video/out/<name>/spec-<name>-draft.json`, under `"labels"`.

5. **Read labelled stills, in draft.** Print the frames worth a still (the
   middle of each tour stop, the whole board with its labels, the end
   card) from the spec that step 4 wrote:

   ```
   python3 -c "import json,sys; t=json.load(open(sys.argv[1]))['timeline']; print(','.join(str(f) for f in [a + t['dwell'] // 2 for a in t['tour']] + [(t['tour_end'] + t['close']) // 2, t['end'] - 15]))" video/out/<name>/spec-<name>-draft.json
   ```

   Then render them (frame numbers are at the draft's 30 fps):

   ```
   python3.12 video/make_video.py <name>.kicad_pcb --stills <frames>
   ```

   Open the PNGs in `video/out/<name>/stills-<name>-labelled/`. The run
   must print no `overlap:` line; if it does, shorten that text or change
   the tour. Check every word against the design. (The overlap check runs
   only on labelled frames, so `--check` cannot catch one.)

6. **Draft the whole video**, at 720p and 30 fps:

   ```
   python3.12 video/make_video.py <name>.kicad_pcb
   ```

   This writes `video/out/<name>/<name>-explode-draft.mp4`. Its frames take
   about 1.8 GB. If the run stops, run the same command again: it resumes.
   Watch the draft from start to end, then show it to the owner.

7. **Music.**
   - Get the final video's length in milliseconds:

     ```
     python3.12 video/make_video.py <name>.kicad_pcb --final --check
     ```

     Its last line says `(N frames, L ms)`. Use `L`.
   - Ask the owner which track, or reuse the last board's. The owner
     licenses music from Epidemic Sound. Get Epidemic Sound's own edit of
     that recording at exactly `L` ms, as WAV: in Epidemic Sound, or with
     its connector if you have one (ask for an edit with the target
     duration `L` ms, the duration forced and WAV; poll the job until it
     completes; download that edit). Ridge 3's music is Epidemic Sound's
     own edit to 32.75 s, recorded in `ridge-3/video/music/README.md`.
   - Save it as `video/music/<track>-<L>ms.wav` and check its length:

     ```
     python3 -c "import wave,sys; w=wave.open(sys.argv[1]); print(round(w.getnframes() / w.getframerate() * 1000), 'ms')" video/music/<track>-<L>ms.wav
     ```

   - Set `"music": "music/<track>-<L>ms.wav"` in `video/<name>.json`.
   - In `video/music/README.md`, record the title, the artist, the library,
     the recording's id, the edit's length and the licence it was
     downloaded under, and how to get it again.
   - Never commit the audio. `video/.gitignore` ignores everything in
     `music/` but the README.
   - If the edit cannot be had at exactly `L`, lengthen or shorten the
     labelled hold instead, `"timeline": {"hold": ...}` (3.5 s by default),
     by the difference, as Ridge 3's ESC does, and run `--final --check`
     again until its length is the edit's. That changes the frames, so do
     it before step 8.
   - Run the draft command of step 6 again to hear it. If you changed the
     hold above, its frames are rendered again; otherwise they are kept, and
     only the captions and the music are laid on again.

8. **Read the brand's version** (see [Brand](#brand)), then **render the
   final**:

   ```
   python3.12 video/make_video.py <name>.kicad_pcb --final
   ```

   This writes `video/out/<name>/<name>-explode.mp4`. If it stops, run it
   again: it resumes. A change to the captions or the music later does not
   render the frames again; a change to the board, the scene's settings,
   `scene.py` or `render.py` does. Watch the result with sound.

9. **Publish, don't commit.** The MP4 stays in `video/out/`, which git
   ignores. Attach it to the board's GitHub release, or share it where the
   owner says.
   - Commit `video/*.py`, `video/requirements.txt`, `video/.gitignore`,
     `video/<name>.json`, `video/music/README.md`, the board's
     `.gitignore` (step 2) and its README's video section (below), and
     `fonts/` if step 1 copied it.
   - Never commit `video/.venv/`, `video/out/`, the audio or the video.
   - Add a short video section to the board's README: the commands, the
     length, the music (or a link to `video/music/README.md`) and the
     brand version, like Ridge 3's
     ([Exploded-view videos](../ridge-3/README.md#exploded-view-videos)).

### Done means

- [ ] No `overlap:` line in the stills or the final run.
- [ ] Every caption checked against the circuit, the BOM and the board.
- [ ] The final run's length equals the music edit's, within a frame
      (17 ms at 60 fps).
- [ ] The brand version is recorded in the board's README.
- [ ] The owner has seen the draft.
- [ ] Nothing rendered and no audio is staged: `git status` shows only the
      files of step 9.

Without the owner, the work stops after step 6 and is not done: the report
says which of these items are left.

## Ridge 3, the worked example

The flight controller and the ESC each have their settings:
[`fc.json`](../ridge-3/video/fc.json) and
[`esc.json`](../ridge-3/video/esc.json). The flight controller also has an
analog build, with its own title and highlights. Ridge 3 maps `fc` and
`esc` to its boards in `BOARDS`. Run from `ridge-3/`:

```
python3.12 video/make_video.py fc --check                     # the scene only, no frames
python3.12 video/make_video.py fc --stills 319,415,511,641,966  # labelled draft stills
python3.12 video/make_video.py fc                             # 720p 30 fps draft
python3.12 video/make_video.py fc --final                     # video/out/fc/ridge3-fc-explode.mp4
python3.12 video/make_video.py fc --final --build analog      # video/out/fc/ridge3-fc-analog-explode.mp4
python3.12 video/make_video.py esc --final                    # video/out/esc/ridge3-esc-explode.mp4
```

The ESC's draft stills are frames 323, 419, 515, 642 and 967.

| Board | Copper layers | Planes | Parts (top / bottom) |
|---|---|---|---|
| Flight controller, HD build (the default) | 6 | ground, 3.3 V | 38 / 42 |
| Flight controller, analog build | 6 | ground, 3.3 V | 43 / 48 |
| ESC | 8 | ground, battery | 119 / 40 |

Both final videos are 1,965 frames, 32.75 s. The drafts are 982 frames
(the flight controller) and 983 (the ESC) at 30 fps. The music is
"Observatory" by Out To The World (Epidemic Sound), in a 32.75 s edit;
[`music/README.md`](../ridge-3/video/music/README.md) has the credit and
the recording's id. The type was checked against brand v3.2.

Measured on a 4-core CPU without a GPU (15 GB of memory):

| Command | Time |
|---|---|
| `fc --check` | 66–88 s |
| `fc --build analog --check` | 68–69 s |
| `esc --final --check` | 209–286 s |
| `fc --stills` with two frames | 85 s |
| `esc --stills` with one frame | 175–259 s |
| `--check`, and `--stills` with one frame, on a larger board: Ridge 3 Lite (223 parts, 8 copper layers) | 10.8 min and 9.6 min |

The higher figures were measured with other work on the same CPU. Every
command builds the scene again before it renders anything, so on a larger
board each one starts with minutes of scene building. Before any frames, a
board's work folder in `video/out/` holds the GLB (28.5 MB for the flight
controller, 62 MB for the ESC, 94 MB for Ridge 3 Lite) and a `.blend` for
each quality and build (42 MB for the flight controller's draft, 109–111 MB
for the ESC's draft and final, 150 MB for Ridge 3 Lite's draft). When a
run saves a `.blend` again, Blender keeps the previous one beside it as a
`.blend1` of about the same size; delete `video/out/<name>/*.blend1`.

## Troubleshooting

| You see | Do this |
|---|---|
| `render stopped with N of M frames; run again to resume` | Run the same command again. |
| `no music: ... is not here` | Download the edit that `video/music/README.md` names and save it under that name. Without it the video is silent. |
| `overlap: the label X crosses Y in N frames (a-b)` | Shorten that label's text or change `tour`, and render those frames again with `--stills`. Ask the owner before moving the rows (`overlay`: `above`, `below`): that changes the look. |
| `AssertionError: copper bands ... for layers ...` from `scene.py` | The GLB's copper heights do not match the board's copper layers. Check the stackup in KiCad. `scene.py` relies on KiCad 10's names in the GLB (`_PCB`, `_copper`, `_pad`, `_via`, `_silkscreen`, `_soldermask`); another KiCad may name them otherwise. |
| `no build 'x'`, `--build is for fc and esc` or `... has no option groups` | `--build` works only for boards in `BOARDS` whose `src/circuit.py` has the build API, and only for builds in `circuit.BUILDS`. |
| The venv will not install `bpy` | bpy 4.5 needs Python 3.11: `VIDEO_PYTHON=/path/to/python3.11`. Delete a half-made `video/.venv` first. |
| `import pcbnew` fails | Run `make_video.py` with the Python that KiCad installed `pcbnew` for (`python3.12` on Ubuntu 24.04 with KiCad 10). |
| The final render is very slow | It is probably on the CPU: the run does not say. `video/.venv/bin/python -c "import bpy; p = bpy.context.preferences.addons['cycles'].preferences; p.refresh_devices(); print(sorted({d.type for d in p.devices}))"` prints `['CPU']` when Blender finds no GPU. Render on a GPU machine. `--jobs` sets how many renders run at once (2 by default). |
| The disk fills up | `video/out/` keeps every frame twice, raw and labelled: about 1.8 GB for a 720p draft and far more at 4K (not measured; tens of GB). Delete `video/out/<name>/frames-*` once the MP4 is published, and the `.blend1` backups Blender leaves beside each `.blend` (`video/out/<name>/*.blend1`, as large as the `.blend`) at any time. |
| `"timeline": no key ...` or `"roles": no layer ...` | A key in the board's JSON is misspelt. The message lists the valid ones: the `timeline` keys under **Edit** in [House style](#house-style), or the board's copper layers. |
| The frames render again after a caption change | They should not. Only the board, the scene's settings (`SCENE_KEYS` in `make_video.py`), `scene.py` and `render.py` make them render again. |
