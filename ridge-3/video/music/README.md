# Music for the videos

A board's settings (`../fc.json`, `../esc.json`) can name an audio file here
as `"music"`. `make_video.py` lays it under the video, with a short fade in,
a fade out over the last second and 1 dB of headroom, cut or padded to the
video's length. Without the file, the video comes out silent and the run
says so.

The tracks are licensed, so they stay out of the repository (see
`../.gitignore`). The one in use:

- `observatory-32750ms.wav`: "Observatory" by Out To The World, from
  Epidemic Sound (recording `0c47304b-4e50-43b2-8230-2397e7991316`), in
  Epidemic Sound's own edit to 32.75 s, the length of both videos (1,965
  frames at 60 fps). It was downloaded under OffGrid's Epidemic Sound
  subscription, so publishing with it follows that plan's licence. When
  the timeline changes length, ask Epidemic Sound for an edit of the new
  length (the run prints the video's length). The tool pads or cuts the
  audio, with fades, but a native edit ends on the music.

To use it again after a fresh checkout, download the edit from Epidemic Sound
and save it here under the same name.
