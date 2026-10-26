"""python3 -m layercam [--config PATH] [--port N] [--check]

--check reads the settings, prints any problem and exits (1 if there is one).
"""
import argparse, logging, sys

from . import config, service

DEFAULT_CONFIG = '/userdata/layercam/layercam.ini'


def main(argv=None):
    ap = argparse.ArgumentParser(prog='layercam')
    ap.add_argument('--config', default=DEFAULT_CONFIG)
    ap.add_argument('--port', type=int, help='web port (default: web.port from the settings)')
    ap.add_argument('--check', action='store_true', help='check the settings and exit')
    ap.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format='%(asctime)s %(name)s %(levelname)s %(message)s')
    if a.check:
        errs = config.load(a.config).errors()
        print('\n'.join(errs) or 'settings OK')
        return 1 if errs else 0
    service.Service(a.config, a.port).run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
