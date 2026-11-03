"""The printer's metrics stream: the layer trigger from the slicer snippet.

Buddy firmware (Prusa-Firmware-Buddy 6.10.1) sends its metrics over UDP to
the host and port set with M334 (src/marlin_stubs/M330.cpp).  Each datagram
(src/common/metric_handlers.cpp) is one syslog header (RFC 5424) followed by
InfluxDB line-protocol points, one per line:

    <14>1 - 0a:bc:12:34:56:7f buddy - - - msg=12,tm=81234567,v=4 gcode v="M118 OGCAM:LAYER:12" 1043
    temp_noz v=215.000000 30051

The trailing number is microseconds since tm (the buffer start).  Points are
buffered and a datagram goes out when the 1 kB buffer fills or, at the next
point, once the oldest is a second old; so a point reaches us up to about a
second after the printer recorded it, and the datagram itself tells us how
late: the last point's offset minus the trigger's.

The "gcode" metric (src/marlin_stubs/gcode.cpp, record_pre_gcode_metrics)
records every G-code line the printer executes, as a string of at most 47
characters, once it is enabled with M331 gcode.  The slicer snippet turns it
on just around the trigger line M118 OGCAM:LAYER:<n> (slicer/README.md).
"""
import re, socket, threading

HEADER = re.compile(r'^<(\d+)>1 (\S+) (\S+) (\S+) (\S+) (\S+) (\S+) msg=(\d+),tm=(-?\d+),v=(\d+) ')
# MeatPack in binary G-code may drop the space after M118, so match anywhere
TRIGGER = re.compile(r'OGCAM:([A-Z]+)(?::([A-Za-z0-9._-]*))?')


class Point:
    __slots__ = ('name', 'tags', 'fields', 'ts')

    def __init__(self, name, tags, fields, ts):
        self.name, self.tags, self.fields, self.ts = name, tags, fields, ts

    def __repr__(self):
        return 'Point(%r, %r, %r, %r)' % (self.name, self.tags, self.fields, self.ts)


def _split(s, sep):
    """Split on sep outside double quotes, honouring backslash escapes."""
    out, cur, q, esc = [], [], False, False
    for ch in s:
        if esc:
            cur.append(ch)
            esc = False
        elif ch == '\\':
            cur.append(ch)
            esc = True
        elif ch == '"':
            cur.append(ch)
            q = not q
        elif ch == sep and not q:
            out.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append(''.join(cur))
    return out


def _value(v):
    if v.startswith('"') and v.endswith('"') and len(v) >= 2:
        return re.sub(r'\\(.)', r'\1', v[1:-1])
    if v.endswith('i') and re.match(r'^-?\d+i$', v):
        return int(v[:-1])
    if v in ('T', 't', 'true', 'True'):
        return True
    if v in ('F', 'f', 'false', 'False'):
        return False
    try:
        return float(v)
    except ValueError:
        return v


def parse_line(line):
    """One line-protocol point, or None if it is not one."""
    parts = _split(line.strip(), ' ')
    parts = [p for p in parts if p != '']
    if len(parts) < 2:
        return None
    head = _split(parts[0], ',')
    name, tags = head[0], {}
    for t in head[1:]:
        if '=' in t:
            k, v = t.split('=', 1)
            tags[k] = v
    fields = {}
    for f in _split(parts[1], ','):
        if '=' in f:
            k, v = f.split('=', 1)
            fields[k] = _value(v)
    ts = None
    if len(parts) >= 3:
        try:
            ts = int(parts[2])
        except ValueError:
            return None
    if not name or not fields:
        return None
    return Point(name, tags, fields, ts)


def parse_datagram(data):
    """-> (header dict or None, [Point])."""
    text = data.decode('utf-8', 'replace')
    header = None
    m = HEADER.match(text)
    if m:
        header = {'host': m.group(3), 'app': m.group(4), 'msg': int(m.group(8)), 'tm': int(m.group(9)),
                  'v': int(m.group(10))}
        text = text[m.end():]
    points = []
    for line in text.split('\n'):
        if line.strip():
            p = parse_line(line)
            if p:
                points.append(p)
    return header, points


class Trigger:
    __slots__ = ('kind', 'arg', 'age_ms', 'source')

    def __init__(self, kind, arg, age_ms, source):
        self.kind, self.arg, self.age_ms, self.source = kind, arg, age_ms, source

    def __repr__(self):
        return 'Trigger(%s, %s, age %d ms, from %s)' % (self.kind, self.arg, self.age_ms, self.source)


def triggers(data, source=''):
    """Every OGCAM trigger in one datagram, with how long before the datagram
    was sent the printer executed it."""
    header, points = parse_datagram(data)
    stamps = [p.ts for p in points if p.ts is not None]
    last = max(stamps) if stamps else None
    out = []
    for p in points:
        if p.name != 'gcode':
            continue
        v = p.fields.get('v')
        if not isinstance(v, str):
            continue
        m = TRIGGER.search(v)
        if not m:
            continue
        age = (last - p.ts) // 1000 if (last is not None and p.ts is not None) else 0
        out.append(Trigger(m.group(1), m.group(2), max(0, age), source))
    return out


class Listener(threading.Thread):
    """Receives the datagrams and hands every trigger to on_trigger."""

    def __init__(self, port, on_trigger, bind='0.0.0.0'):
        threading.Thread.__init__(self, name='metrics', daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((bind, port))
        self.sock.settimeout(1.0)
        self.on_trigger = on_trigger
        self.running = True
        self.datagrams = 0
        self.last_source = None

    def run(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            self.datagrams += 1
            self.last_source = addr[0]
            # cheap filter first: with M331 gcode left on, the stream carries every move
            if b'OGCAM' not in data:
                continue
            for t in triggers(data, addr[0]):
                self.on_trigger(t)

    def stop(self):
        self.running = False
        self.sock.close()
