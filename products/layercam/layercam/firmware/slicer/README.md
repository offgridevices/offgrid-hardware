# PrusaSlicer snippets for per-layer timelapses

Four pieces of custom G-code for the **Prusa CORE One** printer profile in
PrusaSlicer (Printer Settings > Custom G-code). With them, after every
layer the printer moves the head to a corner, tells the camera, holds still
for 1.2 seconds while the camera takes the frame, and carries on. The video
then shows the print growing with no head in the way.

| File | Goes into | What it does |
|---|---|---|
| [`start.gcode`](start.gcode) | Start G-code, **at the end** | tells the printer where the camera is (`M334`) |
| [`after_layer_change.gcode`](after_layer_change.gcode) | After layer change G-code, **after Prusa's two lines** | park, trigger, hold, return |
| [`end.gcode`](end.gcode) | End G-code, **at the end** | one last frame of the finished print |
| [`before_layer_change.gcode`](before_layer_change.gcode) | nothing to change | Prusa's own text, for reference |

Keep Prusa's lines; add ours after them. Save the printer profile under a
new name (e.g. "CORE One + LayerCam") so profile updates do not overwrite it.

## Before the first print

1. Put the camera's address in `start.gcode` instead of `192.0.2.40`. The
   camera's setup page shows it; give the camera a fixed address in your
   router (DHCP reservation), or the snippet points at the wrong place
   after a router restart. A name works too if your router's DNS knows it
   (the printer resolves it with ordinary DNS, at most 20 characters), but
   not a `.local` name.
2. The first print with a new address **stops on the printer's screen** and
   asks whether to allow the metrics change: tap **Yes**. The printer keeps
   the setting, so it asks again only if the address changes. (This prompt
   is Buddy's own safety check, `MetricsConfigChangePrompt` in
   `src/marlin_stubs/M330.cpp`.)
3. On the camera's setup page, leave `timelapse.trigger` at `auto` and
   `timelapse.dwell_ms` at 1200 (the two `G4 P600` holds).

## How a frame is taken

```
{local park_x = 2}{local park_y = 218}   the park position, set once
G1 X{park_x} Y{park_y} F18000    the head goes to the back-left corner, 300 mm/s
M400                   the printer waits until it is there and stopped
M331 gcode             the printer starts reporting each G-code line it runs
M118 OGCAM:LAYER:12    <- this line, reported over UDP, is the camera's trigger
M118 _xxxx... x15      filler: fills the printer's report buffer so it is sent now
G4 P600                hold still
M118 OGCAM:LAYER:12    the same trigger again, in case the first datagram was lost
M118 _xxxx... x15
G4 P600                hold still
M332 gcode             reporting off again
G1 X{position[0]} Y{position[1]} F18000   back to where the slicer left the head
```

What happens on the printer, from the Buddy firmware's source
(Prusa-Firmware-Buddy 6.10.1):

- Every G-code line the printer runs is recorded as the `gcode` metric,
  *before* it runs, when that metric is on (`src/marlin_stubs/gcode.cpp`,
  `record_pre_gcode_metrics`, called for every command). So `M331 gcode`
  itself is not reported, the `M118` lines are, and `M332 gcode` turns it
  off. Keeping it off the rest of the time keeps every move of the print
  from being sent to the camera.
- The printer collects metrics in a 1 kB buffer and sends it when it is
  nearly full, or at the next metric once it is a second old
  (`src/common/metric_handlers.cpp`). Without the filler lines the trigger
  would reach the camera up to about a second late; 15 lines of 47
  characters (the most a string metric keeps, `value_str[48]` in
  `metric.h`) fill the buffer, so it goes out at once. `tests/test_slicer.py`
  emulates the buffer and checks this.
- `M118` only echoes its text to the USB serial console
  (`lib/Marlin/Marlin/src/gcode/host/M118.cpp`); nothing appears on the
  screen and nothing moves.
- `G4 P600` waits for all moves to finish and then 600 ms
  (`lib/Marlin/Marlin/src/gcode/motion/G4.cpp`).
- The return move uses PrusaSlicer's `position` variable, the head's
  position when the custom G-code starts (PrusaSlicer 2.9.6
  `src/libslic3r/GCode.cpp`, `PlaceholderParserIntegration`). In PrusaSlicer
  2.9 the "After layer change" G-code runs after the travel to the new
  layer's first point, with the nozzle already retracted
  (`retract_layer_change = 1` in Prusa's CORE One profiles), so nothing
  oozes while it waits and the slicer's next move starts from where it
  expects.

On the camera: it sees the trigger, knows from the datagram's timestamps how
long ago the printer ran the line, waits out the rest of a 150 ms settle,
drops the frames the sensor had already queued and encodes the next one.
The second trigger is ignored unless the first was lost. If a trigger
arrives too late for the hold, the camera says so on its page (lengthen
the `G4`s and `timelapse.dwell_ms` together).

## Choices and checks

- **Park position X2 Y218** (back left) is inside the CORE One's travel
  (X -2 to 252, Y -19 to 221: `include/marlin/Configuration_COREONE.h`).
  Prusa's own end-of-print park is X242 Y211 (back right). Pick the
  corner where the head hides least of the print from where your camera
  looks, and change `park_x`/`park_y` in the `{local ...}` line (PrusaSlicer
  local variables, 2.6 and later: `PlaceholderParser.cpp`) if you move it.
- **Why 1.2 s:** at night the camera ramps the IR LEDs up and gives the
  exposure 500 ms to follow them before the frame (the LEDs are never left
  on: heat, sim/thermal.md); by day the frame is taken about 0.4 s in. The
  camera warns on its page when a trigger arrives too late for the hold.
- **No `G90`/`G91`.** On Buddy they set the extruder to absolute or
  relative too (`set_relative_mode` in `lib/Marlin/Marlin/src/gcode/gcode.h`,
  outside MK3 compatibility mode), which would undo the slicer's `M83`.
  The snippet only uses absolute X/Y, which PrusaSlicer always prints in.
- **No retraction in the snippet**, no `G10`/`G11` (firmware retraction)
  and no `M240` (camera trigger): neither is in Buddy's G-code table. If
  your profile has "Retract on layer change" off, add `G1 E-0.7 F2700`
  before the park and `G1 E0.7 F1500` after the return (relative E).
- Every line is under Buddy's 96-character command limit
  (`MAX_CMD_SIZE`, `Configuration_COREONE_adv.h`).
- The first layer has no "After layer change" call in PrusaSlicer, so the
  first frame is layer 1 (the second layer).
- **Cost:** 1.2 s of hold plus two moves of up to ~300 mm at 300 mm/s,
  2.5-3.5 s a layer: 10-15 minutes on a 250-layer print.
- **Without the snippet**, the camera still makes a timelapse, from
  PrusaLink's Z height (`timelapse.trigger = auto` falls back after three
  layers with no trigger). Those frames show the head wherever it is.

`tests/test_slicer.py` checks these files: only the commands listed above,
the park inside the limits, the line lengths, the hold matching
`dwell_ms`, the metric switched on only around the triggers, and the
buffer flush.

Not yet tried on a printer: see the firmware README's limits.
