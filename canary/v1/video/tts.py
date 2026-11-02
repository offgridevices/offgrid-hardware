"""Narration audio, one WAV per segment (Piper, en_US-ryan-high voice)."""
import json, os, subprocess, sys, wave
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from script import SEGMENTS
MODEL = os.environ.get('PIPER_MODEL', '/opt/piper/en_US-ryan-high.onnx')
out = {}
for name, text in SEGMENTS:
    p = os.path.join(HERE, 'out', 'audio', name + '.wav')
    subprocess.run([sys.executable, '-m', 'piper', '-m', MODEL, '-f', p, '--length-scale', '1.08',
                    '--sentence-silence', '0.45'], input=text.encode(), check=True, capture_output=True)
    with wave.open(p) as w:
        out[name] = round(w.getnframes() / w.getframerate(), 2)
    print(name, out[name])
json.dump(out, open(os.path.join(HERE, 'out', 'durations.json'), 'w'), indent=1)
print('total', round(sum(out.values()), 1))
