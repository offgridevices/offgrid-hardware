#!/usr/bin/env python3
"""Make and sign LayerCam app updates (layercam/update.py).

    python3 tools/layercam-sign.py keygen update.key
        a new key pair: update.key (private, keep it safe and off the cameras)
        and update.pub (the public key: build it into the image with
        UPDATE_PUBKEY=update.pub board/install-into-sdk.sh ...)
    python3 tools/layercam-sign.py pack update.key layercam-0.2.1.lcup [--min-rootfs N]
        package this checkout's layercam/ as the version in its __init__.py
    python3 tools/layercam-sign.py verify update.pub layercam-0.2.1.lcup

Install a package from the camera's setup page (Software, Install update)
or copy it to the camera and run `layercam-setup update FILE` on the USB
console.  Raise layercam.VERSION for every release: the camera refuses a
version that is not newer than the one it runs.
"""
import argparse, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIRMWARE = os.path.join(HERE, '..')
sys.path.insert(0, FIRMWARE)
from layercam import VERSION, ed25519, update  # noqa: E402


def read_hex(path, n):
    with open(path) as f:
        for line in f:
            line = line.split('#', 1)[0].strip()
            if line:
                b = bytes.fromhex(line)
                if len(b) == n:
                    return b
    sys.exit('%s: no %d-byte hex key' % (path, n))


def main(argv=None):
    ap = argparse.ArgumentParser(prog='layercam-sign')
    sub = ap.add_subparsers(dest='cmd', required=True)
    k = sub.add_parser('keygen')
    k.add_argument('key')
    p = sub.add_parser('pack')
    p.add_argument('key')
    p.add_argument('out')
    p.add_argument('--min-rootfs', type=int, default=1, help='the oldest image (etc/layercam/rootfs-version) it runs on')
    p.add_argument('--src', default=FIRMWARE, help=argparse.SUPPRESS)
    v = sub.add_parser('verify')
    v.add_argument('pub')
    v.add_argument('package')
    a = ap.parse_args(argv)
    if a.cmd == 'keygen':
        if os.path.exists(a.key):
            sys.exit('%s exists: not overwritten' % a.key)
        seed = os.urandom(32)
        fd = os.open(a.key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write('# LayerCam update signing key: private, never on a camera\n%s\n' % seed.hex())
        pub = os.path.splitext(a.key)[0] + '.pub'
        with open(pub, 'w') as f:
            f.write('%s\n' % ed25519.public_key(seed).hex())
        print('private key %s, public key %s' % (a.key, pub))
    elif a.cmd == 'pack':
        version = update.version_of(a.src) or VERSION
        m = update.build_package(a.src, version, read_hex(a.key, 32), a.out, a.min_rootfs)
        print('%s: version %s, %d files, signed by %s' % (a.out, m['version'], len(m['files']),
                                                          ed25519.public_key(read_hex(a.key, 32)).hex()))
    else:
        try:
            m, _ = update.read_package(a.package, [read_hex(a.pub, 32)])
        except update.UpdateError as e:
            sys.exit('refused: %s' % e)
        print('good: %s version %s (needs rootfs %s), %d files' % (m['product'], m['version'], m['min_rootfs'],
                                                                  len(m['files'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
