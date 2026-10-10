"""Gather every concept's renders into review files, in concepts/:

    contact-sheet-3d.png   every hero.png, numbered, in a grid
    contact-sheet-2d.png   every render.png (the 2D sketches), numbered
    reel.mp4               every turntable.mp4 one after another

    python3 make_gallery.py
"""
import glob
import os
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.environ.get('SB_FONTS', '/tmp/claude-0/-home-user-offgrid-hardware/'
                       'bb4d9657-83a6-5d9a-b4a3-ba3efc9cb84f/scratchpad/ref')
MONO = os.path.join(FONTS, 'JetBrainsMono-VariableFont.ttf')


def concepts():
    return sorted(d for d in glob.glob(os.path.join(ROOT, '[0-9][0-9]-*')) if os.path.isdir(d))


def sheet(image_name, out, cols=4, w=800, h=500, number=False):
    files = [(os.path.basename(d)[:2], os.path.join(d, image_name)) for d in concepts()
             if os.path.exists(os.path.join(d, image_name))]
    if not files:
        return None
    rows = (len(files) + cols - 1) // cols
    inputs, chains = [], []
    for i, (num, f) in enumerate(files):
        inputs += ['-i', f]
        c = f'[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0xE9E4D8'
        if number:
            c += (f",drawbox=x=iw-120:y=ih-84:w=120:h=84:color=0x1B1813:t=fill,"
                  f"drawtext=fontfile={MONO}:text='{num}':x=w-98:y=h-70:fontsize=56:fontcolor=0xF1ECE0")
        chains.append(c + f'[v{i}]')
    layout = '|'.join(f'{(i % cols) * w}_{(i // cols) * h}' for i in range(len(files)))
    fc = ';'.join(chains) + ';' + ''.join(f'[v{i}]' for i in range(len(files))) + \
        f'xstack=inputs={len(files)}:layout={layout}:fill=0xE9E4D8[out]'
    if len(files) == 1:
        fc = chains[0].replace(f'[v0]', '[out]')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', *inputs, '-filter_complex', fc,
                    '-map', '[out]', '-frames:v', '1', out], check=True)
    return out


def reel(out):
    vids = [os.path.join(d, 'turntable.mp4') for d in concepts()
            if os.path.exists(os.path.join(d, 'turntable.mp4'))]
    if not vids:
        return None
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f:
        for v in vids:
            f.write(f"file '{v}'\n")
        lst = f.name
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst,
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '22', out], check=True)
    os.unlink(lst)
    return out


if __name__ == '__main__':
    print(sheet('hero.png', os.path.join(ROOT, 'contact-sheet-3d.png')))
    print(sheet('render.png', os.path.join(ROOT, 'contact-sheet-2d.png'), number=True))
    print(reel(os.path.join(ROOT, 'reel.mp4')))
