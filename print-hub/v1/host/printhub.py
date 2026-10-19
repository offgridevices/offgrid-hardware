#!/usr/bin/env python3
"""printhub: switch the Print Hub's USB ports from the print server.

    printhub status                     every port, the charger, the budget, the board's temperature
    printhub on fan light               switch on
    printhub on filter1 for 2h          switch on for a while
    printhub off fan after 10m          switch off later
    printhub off all
    printhub name 1 fan                 name a port (saved on the board)
    printhub limit fan 1200             software current limit, mA
    printhub priority fan 1             kept on longest when power runs short
    printhub boot light on              switch on whenever the board powers up
    printhub wifi "My Network" "pass"   join Wi-Fi (over USB)
    printhub token SECRET               require this token on Wi-Fi commands
    printhub ota URL                    update firmware from a URL (Wi-Fi)
    printhub raw "any command"          send a command line as is

How it reaches the board, first that works:
    --serial /dev/ttyACM0  or  PRINTHUB_SERIAL     the USB-C cable to this computer
    --host 192.168.1.50    or  PRINTHUB_HOST       Wi-Fi (default: printhub.local)
With neither given it tries the USB cable (any /dev/ttyACM* that answers as a
Print Hub), then printhub.local.  PRINTHUB_TOKEN carries the Wi-Fi token.

Every reply is the board's JSON; --json prints it raw (for scripts and AI
agents), otherwise "status" prints a table.  Exit status 0 on success, 1 when
the board said no, 2 when it could not be reached.

Python 3.8+, standard library only (no pyserial): Linux and macOS.
"""
import argparse, glob, json, os, select, shlex, sys, time, urllib.request, urllib.error

DEFAULT_HOST = 'printhub.local'


class Unreachable(Exception):
    pass


# ---------------------------------------------------------------- transports
def serial_cmd(dev, line, timeout=3.0):
    """One command over the USB serial port (raw termios: no pyserial)."""
    import termios, tty
    try:
        fd = os.open(dev, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    except OSError as e:
        raise Unreachable('%s: %s' % (dev, e))
    try:
        tty.setraw(fd)
        a = termios.tcgetattr(fd)
        a[4] = a[5] = termios.B115200          # USB CDC ignores the rate, but set one
        termios.tcsetattr(fd, termios.TCSANOW, a)
        termios.tcflush(fd, termios.TCIOFLUSH)
        os.write(fd, (line.strip() + '\n').encode())
        buf, end = b'', time.time() + timeout
        while time.time() < end:
            r, _, _ = select.select([fd], [], [], 0.1)
            if r:
                try:
                    buf += os.read(fd, 4096)
                except BlockingIOError:
                    pass
                # the reply is the first line that is a JSON object
                for ln in buf.split(b'\n')[:-1]:
                    ln = ln.strip()
                    if ln.startswith(b'{'):
                        return json.loads(ln)
        raise Unreachable('%s: no reply' % dev)
    finally:
        os.close(fd)


def http_cmd(host, line, token=None, timeout=5.0):
    req = urllib.request.Request('http://%s/api/cmd' % host, data=line.encode(), method='POST',
                                 headers={'Content-Type': 'text/plain'})
    if token:
        req.add_header('Authorization', 'Bearer ' + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except Exception:
            raise Unreachable('%s: HTTP %d' % (host, e.code))
    except (urllib.error.URLError, OSError) as e:
        raise Unreachable('%s: %s' % (host, getattr(e, 'reason', e)))


def find_serial():
    for dev in sorted(glob.glob('/dev/ttyACM*') + glob.glob('/dev/cu.usbmodem*')):
        try:
            r = serial_cmd(dev, 'status', timeout=1.5)
            if 'ports' in r:
                return dev
        except Exception:
            continue
    return None


def send(line, args):
    if args.serial:
        return serial_cmd(args.serial, line)
    if args.host:
        return http_cmd(args.host, line, args.token)
    dev = find_serial()
    if dev:
        return serial_cmd(dev, line)
    return http_cmd(DEFAULT_HOST, line, args.token)


# ---------------------------------------------------------------- output
def table(r):
    inp = r.get('input', {})
    print('Print Hub %s   charger: %s (%.2f V in)   5 V rail: %.2f V   %s' % (
        r.get('version', '?'), inp.get('contract') or 'none', inp.get('mv', 0) / 1000, r.get('rail_mv', 0) / 1000,
        ('Wi-Fi ' + r['ip']) if r.get('ip') else 'Wi-Fi not joined'))
    print('Drawing %d mA of %d mA available (%s)' % (r.get('total_ma', 0), r.get('budget_ma', 0), r.get('budget')))
    t = r.get('temp_c')
    print('Board %s   %s\n' % ('%.1f C' % t if t is not None else 'temperature unknown',
                               {'ok': 'ok',
                                'derating': 'warm: the power for the ports is turned down',
                                'hot': 'TOO HOT: every port off until it cools',
                                'sensor_fault': 'no temperature reading: the power for the ports is turned down'
                                }.get(r.get('heat'), r.get('heat') or '')))
    print('  #  %-15s %-5s %7s %7s  %-4s %-4s  %s' % ('name', 'state', 'mA', 'limit', 'prio', 'boot', 'note'))
    for p in r.get('ports', []):
        state = 'ON' if p['on'] else ('...' if p['pending'] else 'off')
        note = []
        if p.get('off_in_s', -1) >= 0:
            s = p['off_in_s']
            note.append('off in %dm%02ds' % (s // 60, s % 60))
        if p.get('last_off') and not p['on']:
            note.append({'overcurrent': 'switched off: drew more than its limit',
                         'fault': 'switched off: short circuit or overheating',
                         'shed': 'switched off: not enough power (charger or heat)',
                         'hot': 'switched off: the board was too hot',
                         'no_power': 'refused: not enough power left',
                         'timer': 'timer ran out'}.get(p['last_off'], p['last_off']))
        print('  %d  %-15s %-5s %7d %7d  %-4d %-4s  %s' % (p['port'], p['name'], state, p['ma'], p['limit_ma'],
                                                      p['priority'], 'on' if p['boot_on'] else '', '; '.join(note)))


def main(argv=None):
    ap = argparse.ArgumentParser(prog='printhub', description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('--serial', default=os.environ.get('PRINTHUB_SERIAL'))
    ap.add_argument('--host', default=os.environ.get('PRINTHUB_HOST'))
    ap.add_argument('--token', default=os.environ.get('PRINTHUB_TOKEN'))
    ap.add_argument('--json', action='store_true', help='print the board\'s JSON reply')
    ap.add_argument('words', nargs='+')
    args = ap.parse_args(argv)
    if args.words[0] == 'raw':
        line = ' '.join(args.words[1:])
    else:
        # quote the words again so a Wi-Fi name with spaces survives
        line = ' '.join(args.words[:1] + [shlex.quote(w) if ' ' in w else w for w in args.words[1:]])
        if args.words[0] in ('wifi', 'token'):
            line = args.words[0] + ' ' + ' '.join(shlex.quote(w) for w in args.words[1:])
    try:
        r = send(line, args)
    except Unreachable as e:
        print('printhub: cannot reach the board (%s)' % e, file=sys.stderr)
        return 2
    if args.json or args.words[0] != 'status' or not r.get('ok'):
        print(json.dumps(r))
    else:
        table(r)
    return 0 if r.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
