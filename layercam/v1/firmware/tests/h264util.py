"""Test streams: H.264 made by ffmpeg/libx264 when the host has them, split
into access units at the access unit delimiters, as the camera's encoder
hands them over one frame at a time."""
import os, shutil, subprocess, tempfile


def have_ffmpeg():
    if not (shutil.which('ffmpeg') and shutil.which('ffprobe')):
        return False
    r = subprocess.run(['ffmpeg', '-hide_banner', '-encoders'], capture_output=True, text=True)
    return 'libx264' in r.stdout


def make_aus(width, height, frames, gop=30):
    """-> a directory of 000000.au ... files, one access unit each."""
    d = tempfile.mkdtemp(prefix='aus-')
    raw = os.path.join(d, 'all.h264')
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i',
                    'testsrc=size=%dx%d:rate=30' % (width, height), '-frames:v', str(frames),
                    '-c:v', 'libx264', '-profile:v', 'main', '-bf', '0', '-g', str(gop), '-pix_fmt', 'yuv420p',
                    '-x264-params', 'aud=1', '-f', 'h264', raw], check=True)
    with open(raw, 'rb') as f:
        data = f.read()
    os.unlink(raw)
    # cut before every AUD (00 00 00 01 09)
    cuts = []
    i = data.find(b'\x00\x00\x00\x01\x09')
    while i >= 0:
        cuts.append(i)
        i = data.find(b'\x00\x00\x00\x01\x09', i + 5)
    cuts.append(len(data))
    for k in range(len(cuts) - 1):
        with open(os.path.join(d, '%06d.au' % k), 'wb') as f:
            f.write(data[cuts[k]:cuts[k + 1]])
    return d


def write_stream(au_dir, folder):
    """Concatenate the access units as the helper would, with the index."""
    h264, idx = os.path.join(folder, 'video.h264'), os.path.join(folder, 'video.idx')
    with open(h264, 'wb') as v, open(idx, 'w') as x:
        for n in sorted(os.listdir(au_dir)):
            with open(os.path.join(au_dir, n), 'rb') as f:
                au = f.read()
            x.write('%d %d 0\n' % (v.tell(), len(au)))
            v.write(au)
    return h264, idx


def probe(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames', '-show_entries',
                        'stream=codec_name,width,height,nb_read_frames,avg_frame_rate', '-of',
                        'default=noprint_wrappers=1', path], capture_output=True, text=True, check=True)
    out = dict(line.split('=', 1) for line in r.stdout.split())
    dec = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'null', '-'], capture_output=True, text=True)
    out['decode_errors'] = dec.stderr.strip()
    return out

