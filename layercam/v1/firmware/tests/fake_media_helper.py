"""Stands in for native/layercam-media in the tests: the same line protocol
on stdin/stdout, frames taken from a ready-made H.264 stream.

    python3 fake_media_helper.py AU_DIR      (AU_DIR/000000.au, 000001.au, ...: one access unit each)
"""
import os, sys


def main():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from layercam.capture import TINY_JPEG
    au_dir = sys.argv[1]
    aus = sorted(n for n in os.listdir(au_dir) if n.endswith('.au'))
    out = sys.stdout.buffer
    out.write(b'READY 2304 1296\n')
    out.flush()
    video, nxt = None, 0
    for line in sys.stdin.buffer:
        p = line.decode().split()
        if not p:
            continue
        cmd = p[0]
        if cmd == 'SNAP':
            out.write(b'JPEG %d\n' % len(TINY_JPEG) + TINY_JPEG)
        elif cmd == 'VSTART':
            video = open(p[1], 'ab')
            out.write(b'OK\n')
        elif cmd == 'VFRAME':
            if video is None:
                out.write(b'ERR video not started\n')
            else:
                with open(os.path.join(au_dir, aus[nxt % len(aus)]), 'rb') as f:
                    au = f.read()
                off = video.tell()
                video.write(au)
                video.flush()
                key = 1 if nxt % len(aus) == 0 else 0
                nxt += 1
                out.write(b'FRAME %d %d %d\n' % (off, len(au), key))
        elif cmd == 'VSTOP':
            if video:
                video.close()
            video = None
            out.write(b'OK\n')
        elif cmd == 'NIGHT':
            out.write(b'OK\n')
        elif cmd == 'PING':
            out.write(b'OK 2304 1296\n')
        elif cmd == 'DIE':
            sys.exit(3)
        elif cmd == 'QUIT':
            break
        else:
            out.write(b'ERR unknown command\n')
        out.flush()


if __name__ == '__main__':
    main()
