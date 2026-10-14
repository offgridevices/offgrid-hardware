"""Build the Canary v1 product video.

  python3 make_video.py test <segment> <t> [<t> ...]   -> out/test_<seg>_<t>.png
  python3 make_video.py render [segment ...]           -> out/seg_<name>.mp4 (video only)
  python3 make_video.py mux                            -> canary-v1-product-video.mp4

Pipeline: tts.py (narration WAVs) -> words.py (word timings) ->
render_turntable.sh + stills (KiCad 3D renders) -> this script.
"""
import json, os, subprocess, sys, wave
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, 'out')
from script import SEGMENTS
import scenes
FPS = 30
DUR = json.load(open(os.path.join(OUT, 'durations.json')))


def seg_len(name):
    d = scenes.LEAD + DUR[name] + 1.6
    if name == 'turntable':
        d = max(d, 17.0)              # let the board turn slowly after the words
    if name == 'end':
        d += 2.5
    if name == 'title':
        d += 0.8
    return round(d * FPS) / FPS


def render_segment(name):
    D = seg_len(name)
    n = int(round(D * FPS))
    path = os.path.join(OUT, f'seg_{name}.mp4')
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                           '-s', '1920x1080', '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium',
                           '-crf', '18', '-pix_fmt', 'yuv420p', path], stdin=subprocess.PIPE)
    fn = scenes.SCENES[name]
    for i in range(n):
        im = fn(i / FPS, D).convert('RGB')
        ff.stdin.write(im.tobytes())
    ff.stdin.close()
    ff.wait()
    return name, n


def beeps(total):
    """The sounder's real drive pattern from the simulation, quiet, under the
    'sim' segment while it runs in real time."""
    sr = 48000
    a = np.zeros(int(total * sr), np.float32)
    t0 = sum(seg_len(n) for n, _ in SEGMENTS[:[n for n, _ in SEGMENTS].index('sim')])
    io = scenes.sim_data()[1]
    D = seg_len('sim')
    tone = {round(r[0], 1): r[4] for r in io}
    for k in range(int(D * 100)):          # 10 ms steps of segment time
        tt = k / 100
        st, speed = scenes.sim_clock(tt)
        if speed != 1.0:
            continue
        if tone.get(round(st - (st % 0.1), 1), 0) > 0.5:
            i0 = int((t0 + tt) * sr)
            n = sr // 100
            x = np.arange(n) / sr
            a[i0:i0 + n] += 0.05 * np.sin(2 * np.pi * 4000 * (x + tt))
    # soften edges
    k = np.ones(96) / 96
    env = np.convolve((np.abs(a) > 0).astype(np.float32), k, mode='same')
    return a * np.clip(env, 0, 1), sr


def mux():
    names = [n for n, _ in SEGMENTS]
    lst = os.path.join(OUT, 'concat.txt')
    open(lst, 'w').write(''.join(f"file 'seg_{n}.mp4'\n" for n in names))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst,
                    '-c', 'copy', os.path.join(OUT, 'video_only.mp4')], check=True)
    total = sum(seg_len(n) for n in names)
    sr = 48000
    mix = np.zeros(int(total * sr) + sr, np.float32)
    t = 0.0
    srt, idx = [], 1
    words = json.load(open(os.path.join(OUT, 'words.json')))
    for n, text in SEGMENTS:
        w = wave.open(os.path.join(OUT, 'audio', n + '.wav'))
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        xs = np.interp(np.arange(0, len(x), w.getframerate() / sr), np.arange(len(x)), x)
        i0 = int((t + scenes.LEAD) * sr)
        mix[i0:i0 + len(xs)] += xs * 0.9
        # subtitles: the script's own sentences, timed by the spoken words
        sents = [s.strip() for s in text.replace('. ', '.|').replace('? ', '?|').replace(': ', ':|').split('|') if s.strip()]
        ws = words[n]
        wi = 0
        for s in sents:
            k = max(1, len(s.split()))
            if wi >= len(ws):
                break
            a, b = ws[wi][1], ws[min(len(ws) - 1, wi + k - 1)][2]
            wi += k
            srt.append((idx, t + scenes.LEAD + a, t + scenes.LEAD + b + 0.3, s)); idx += 1
        t += seg_len(n)
    b, _ = beeps(total)
    mix[:len(b)] += b
    mix = np.clip(mix, -1, 1)
    wav = os.path.join(OUT, 'mix.wav')
    with wave.open(wav, 'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    def ts(x):
        h, m, s = int(x // 3600), int(x % 3600 // 60), x % 60
        return f'{h:02d}:{m:02d}:{s:06.3f}'.replace('.', ',')
    srtp = os.path.join(HERE, 'canary-v1-product-video.srt')
    with open(srtp, 'w') as f:
        for i, a, b, s in srt:
            f.write(f'{i}\n{ts(a)} --> {ts(b)}\n{s}\n\n')
    final = os.path.join(HERE, 'canary-v1-product-video.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', os.path.join(OUT, 'video_only.mp4'), '-i', wav,
                    '-i', srtp, '-map', '0:v', '-map', '1:a', '-map', '2:s', '-c:v', 'copy', '-c:a', 'aac',
                    '-b:a', '160k', '-c:s', 'mov_text', '-metadata:s:s:0', 'language=eng', '-shortest',
                    '-movflags', '+faststart', final], check=True)
    print('wrote', final, round(total, 1), 's')


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'test':
        name = sys.argv[2]
        for tt in sys.argv[3:]:
            p = os.path.join(OUT, f'test_{name}_{tt}.png')
            scenes.SCENES[name](float(tt), seg_len(name)).convert('RGB').save(p)
            print(p)
    elif cmd == 'render':
        names = sys.argv[2:] or [n for n, _ in SEGMENTS]
        from multiprocessing import Pool
        with Pool(int(os.environ.get('NPROC', 3))) as p:
            for name, n in p.imap_unordered(render_segment, names):
                print('rendered', name, n, 'frames', flush=True)
    elif cmd == 'mux':
        mux()
