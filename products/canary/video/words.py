"""Word timestamps for each narration WAV (faster-whisper base.en), used to
cue visuals on the spoken words. Writes out/words.json."""
import json, os, sys, wave
import numpy as np
from faster_whisper import WhisperModel
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from script import SEGMENTS
m = WhisperModel('base.en', device='cpu', compute_type='int8')
out = {}
for name, _ in SEGMENTS:
    w = wave.open(os.path.join(HERE, 'out', 'audio', name + '.wav'))
    sr = w.getframerate()
    a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    a16 = np.interp(np.arange(0, len(a), sr / 16000), np.arange(len(a)), a).astype(np.float32)
    segs, _ = m.transcribe(a16, word_timestamps=True)
    out[name] = [(wd.word.strip(), round(wd.start, 2), round(wd.end, 2)) for s in segs for wd in s.words]
json.dump(out, open(os.path.join(HERE, 'out', 'words.json'), 'w'), indent=0)
for k, v in out.items():
    print(k, len(v), ' '.join(f'{w}@{s}' for w, s, e in v)[:400])
