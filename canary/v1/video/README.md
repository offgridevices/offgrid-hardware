# Canary v1 product video

`out/canary-v1-product-video.mp4`: 1080p30, about 4 minutes, narrated, with
an English subtitle track (also `out/canary-v1-product-video.srt`).

**The video is published, not committed** ([docs/product-video.md](../../../docs/product-video.md)):
the build writes it to `out/`, which git ignores; attach it to the board's
GitHub release or share it where the owner says. This is a narrated
explainer, not the house exploded-view video that guide describes; that one
is still to make for Canary.

Everything in it comes from this revision:
- the board is KiCad 10.0.6's own 3D render of `canary.kicad_pcb`
  (a 240-frame turntable, a top view and a hero view);
- the simulation segment plays back the actual HIL run of the real firmware
  (`sim/hil/out/vent_*`): the gas, CO₂ and temperature traces, the LEDs'
  PWM duty and the sounder's drive pattern (the quiet 4 kHz beeps in the
  audio are that pattern);
- the verification numbers are read from the DRC/ERC reports and the HIL and
  SPICE result files at render time.

Narration: Piper TTS (`en_US-ryan-high` voice), text in `script.py`; word
timings from faster-whisper cue the visuals. Motion graphics use the
OffGrid B-roll design system (`broll_lib.py`, 1080p output variant).

```sh
python3 tts.py && python3 words.py      # narration + word timings
./render_turntable.sh                    # 240 KiCad 3D frames (slow: ~1 h)
./render_stills.sh                       # top + hero stills
python3 make_video.py render && python3 make_video.py mux
```
