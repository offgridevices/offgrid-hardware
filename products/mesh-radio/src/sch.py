# -*- coding: utf-8 -*-
"""Draw the KiCad schematic from circuit.py.

circuit.py is the design: every part and every connection.  This script
draws it as a KiCad 10 schematic so a person can review it the usual way
(and so KiCad's own electrical rules check can run on it).  One page per
block of circuit.py, every connection made with a net label, so the drawing
cannot disagree with the circuit: check_sch() exports KiCad's netlist from
the drawn schematic and compares it with circuit.py, net by net.

    tools/kd python3 src/sch.py          write ../schematic/, run ERC, export PDF

Symbols: standard parts (resistors, capacitors, diodes, transistors,
crystals, switches) use KiCad's own library symbols, embedded in the file.
Chips and connectors are drawn here from the pin table in parts.py, which
is the datasheet's pin list, so the pin numbers are the footprint's pads.
"""
import os, re, sys, json, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.dirname(HERE)
OUT = os.path.join(V1, 'schematic')
sys.path.insert(0, HERE)
from sexpr import parse, emit, q, uid, f
import parts, circuit

LIBDIR = '/usr/share/kicad/symbols'
PROJECT = 'mesh-radio'
G = 2.54                       # schematic grid


# ---------------------------------------------------------------- library symbols
_libcache = {}

def lib_symbol(lib, name):
    if lib not in _libcache:
        with open(os.path.join(LIBDIR, lib + '.kicad_sym')) as fh:
            _libcache[lib] = parse(fh.read())[0]
    for n in _libcache[lib]:
        if isinstance(n, list) and n[0] == 'symbol' and n[1] == q(name):
            return n
    raise KeyError('%s:%s' % (lib, name))


def walk_pins(sym):
    """(pin node) lists inside a library symbol, with name and number."""
    out = []
    def rec(n):
        for c in n:
            if isinstance(c, list):
                if c[0] == 'pin':
                    name = [d for d in c if isinstance(d, list) and d[0] == 'name'][0][1].strip('"')
                    num = [d for d in c if isinstance(d, list) and d[0] == 'number'][0][1].strip('"')
                    at = [d for d in c if isinstance(d, list) and d[0] == 'at'][0]
                    out.append((c, name, num, float(at[1]), float(at[2]), int(float(at[3]))))
                else:
                    rec(c)
    rec(sym)
    return out


def import_symbol(lib, name, libid, pinmap=None):
    """A copy of a KiCad library symbol under `libid`, with its pin numbers
    renamed to the footprint's pads (pinmap: library pin name or number ->
    pad).  Returns (sexpr, {pad: (x, y)})."""
    import copy
    s = copy.deepcopy(lib_symbol(lib, name))
    s[1] = q(libid)
    # unit sub-symbols are named <symbol>_<unit>_<style>: follow the rename
    base = libid.split(':')[1]
    for n in s:
        if isinstance(n, list) and n[0] == 'symbol' and n[1].startswith(q(name)[:-1] + '_'):
            n[1] = '"' + base + n[1][len(name) + 1:]
    pins = {}
    for node, pname, pnum, x, y, a in walk_pins(s):
        pad = pnum
        if pinmap:
            if pname in pinmap:
                pad = pinmap[pname]
            elif pnum in pinmap:
                pad = pinmap[pnum]
            else:
                raise KeyError('%s: pin %s/%s not mapped' % (libid, pname, pnum))
        for d in node:
            if isinstance(d, list) and d[0] == 'number':
                d[1] = q(pad)
        pins.setdefault(pad, []).append((x, y, a))
    return s, pins


def _font(size=1.27, hide=False, justify=None):
    e = ['effects', ['font', ['size', f(size), f(size)]]]
    if justify and justify != 'center':      # centred is KiCad's default and has no keyword
        e.append(['justify'] + justify.split())
    if hide:
        e.append(['hide', 'yes'])
    return e


def ic_symbol(libid, spec):
    """Draw a box symbol from a pin table:
    spec = {'pins': {pad: (name, type)}, 'left': [pads], 'right': [pads]}
    ('-' in a side list leaves a gap)."""
    left, right = spec['left'], spec['right']
    rows = max(len(left), len(right))
    names = [spec['pins'][p][0] for p in left + right if p != '-']
    width = max(10.16, G * round((max(len(n) for n in names) * 2 * 1.0 + 4) / G))
    h = (rows + 1) * G
    top = G * round((h / 2) / G)
    pins_sx, pos = [], {}
    for side, lst in (('L', left), ('R', right)):
        for i, p in enumerate(lst):
            if p == '-':
                continue
            name, typ = spec['pins'][p]
            y = top - (i + 1) * G
            x = -width / 2 - G if side == 'L' else width / 2 + G
            a = 0 if side == 'L' else 180
            pins_sx.append(['pin', typ, 'line', ['at', f(x), f(y), str(a)], ['length', f(G)],
                            ['name', q(name), _font(1.016)], ['number', q(p), _font(1.016)]])
            pos[p] = [(x, y, a)]
    bottom = top - (rows + 1) * G
    body = ['symbol', q(libid.split(':')[1] + '_0_1'),
            ['rectangle', ['start', f(-width / 2), f(top)], ['end', f(width / 2), f(bottom)],
             ['stroke', ['width', '0.254'], ['type', 'default']], ['fill', ['type', 'background']]]]
    sym = ['symbol', q(libid), ['pin_names', ['offset', '0.508']], ['exclude_from_sim', 'no'],
           ['in_bom', 'yes'], ['on_board', 'yes'],
           ['property', '"Reference"', q(spec.get('prefix', 'U')), ['at', f(-width / 2), f(top + 1.27), '0'], _font(justify='left')],
           ['property', '"Value"', q(libid.split(':')[1]), ['at', f(-width / 2), f(bottom - 1.27), '0'], _font(justify='left')],
           ['property', '"Footprint"', '""', ['at', '0', '0', '0'], _font(hide=True)],
           ['property', '"Datasheet"', '""', ['at', '0', '0', '0'], _font(hide=True)],
           ['property', '"Description"', '""', ['at', '0', '0', '0'], _font(hide=True)],
           body, ['symbol', q(libid.split(':')[1] + '_1_1')] + pins_sx, ['embedded_fonts', 'no']]
    return sym, pos, (width + 2 * G, top, bottom)


def power_symbol(net):
    """A global power port for `net` (GND uses KiCad's ground glyph)."""
    import copy
    if net == 'GND':
        s, pins = import_symbol('power', 'GND', 'power:GND')
        return s, pins
    base = copy.deepcopy(lib_symbol('power', '+3V3'))
    libid = 'og_power:' + net
    txt = emit(base).replace('"+3V3', '"' + net).replace('(symbol "' + net, '(symbol "' + net)
    s = parse(txt)[0]
    s[1] = q(libid)
    pins = {}
    for node, pname, pnum, x, y, a in walk_pins(s):
        pins.setdefault(pnum, []).append((x, y, a))
    return s, pins


# ---------------------------------------------------------------- placement on a page
def _rot(x, y, angle):
    """Symbol-space (y up) point to sheet offset (y down) at a rotation."""
    import math
    r = math.radians(angle)
    xr = x * math.cos(r) - y * math.sin(r)
    yr = x * math.sin(r) + y * math.cos(r)
    return xr, -yr


def label_len(t):
    return 1.0 * len(t) + 3.0


class Page:
    def __init__(self, name, title):
        self.name, self.title = name, title
        self.items, self.syms = [], {}
        self.maxx, self.maxy = 0, 0
        self.pwr = 0

    def need(self, libid, sym):
        self.syms[libid] = sym

    def place(self, libid, ref, value, x, y, angle, comp, fields, refpos=None, valpos=None, hide_ref=False,
              just='left'):
        u = uid(self.name, ref)
        rx, ry = refpos or (x, y - 3.2)
        vx, vy = valpos or (x, y + 3.2)
        props = [['property', '"Reference"', q(ref), ['at', f(rx), f(ry), '0'], _font(1.0, justify=just, hide=hide_ref)],
                 ['property', '"Value"', q(value), ['at', f(vx), f(vy), '0'], _font(1.0, justify=just)]]
        for k, v in fields:
            props.append(['property', q(k), q(v), ['at', f(x), f(y), '0'], _font(hide=True)])
        node = ['symbol', ['lib_id', q(libid)], ['at', f(x), f(y), str(angle)], ['unit', '1'],
                ['exclude_from_sim', 'no'], ['in_bom', 'yes' if comp else 'no'], ['on_board', 'yes' if comp else 'no'],
                ['dnp', 'yes' if (comp and parts.PARTS[comp.part].get('dnp')) else 'no'], ['uuid', q(u)]] + props
        self.items.append(('sym', node, ref))
        return node

    def wire(self, x1, y1, x2, y2):
        self.items.append(('raw', ['wire', ['pts', ['xy', f(x1), f(y1)], ['xy', f(x2), f(y2)]],
                                   ['stroke', ['width', '0'], ['type', 'default']], ['uuid', q(uid(self.name, 'w', x1, y1, x2, y2))]]))

    def junction(self, x, y):
        self.items.append(('raw', ['junction', ['at', f(x), f(y)], ['diameter', '0'], ['color', '0', '0', '0', '0'],
                                   ['uuid', q(uid(self.name, 'j', x, y))]]))

    def label(self, net, x, y, angle):
        just = {0: 'left', 180: 'right', 90: 'left', 270: 'right'}[angle]
        self.items.append(('raw', ['global_label', q(net), ['shape', 'passive'], ['at', f(x), f(y), str(angle)],
                                   ['fields_autoplaced', 'yes'], _font(justify=just),
                                   ['uuid', q(uid(self.name, 'l', net, x, y))],
                                   ['property', '"Intersheetrefs"', '"${INTERSHEET_REFS}"', ['at', f(x), f(y), '0'],
                                    _font(justify=just, hide=True)]]))

    def noconnect(self, x, y):
        self.items.append(('raw', ['no_connect', ['at', f(x), f(y)], ['uuid', q(uid(self.name, 'nc', x, y))]]))

    def text(self, s, x, y, size=1.8):
        self.items.append(('raw', ['text', q(s), ['exclude_from_sim', 'no'], ['at', f(x), f(y), '0'],
                                   _font(size, justify='left top'), ['uuid', q(uid(self.name, 't', s[:40], x, y))]]))

    def port(self, net, x, y, direction):
        """A power port at a pin end; direction is where the wire leaves the
        pin.  The port sits one grid step out along that direction, turned to
        face the pin, so it can never touch a neighbouring pin's label."""
        self.pwr += 1
        libid = 'power:GND' if net == 'GND' else 'og_power:' + net
        s, _ = power_symbol(net)
        self.need(libid, s)
        dx, dy = {'L': (-G, 0), 'R': (G, 0), 'U': (0, -G), 'D': (0, G)}[direction]
        ex, ey = x + 2 * dx, y + 2 * dy
        self.wire(x, y, ex, ey)
        # body direction: GND hangs "down" at 0 deg, rails stand "up" at 0 deg
        if net == 'GND':
            angle = {'L': 270, 'R': 90, 'U': 180, 'D': 0}[direction]
        else:
            angle = {'L': 90, 'R': 270, 'U': 0, 'D': 180}[direction]
        ref = '#PWR%s%03d' % (self.name[:3].upper(), self.pwr)
        if net == 'GND':
            self.place(libid, ref, net, ex, ey, angle, None, [], hide_ref=True,
                       valpos=(ex, ey + 4.0), just='center')   # GND's value is hidden by its library symbol anyway
        else:
            vp = {'L': (ex - 3.5, ey), 'R': (ex + 3.5, ey), 'U': (ex, ey - 4.0), 'D': (ex, ey + 4.0)}[direction]
            jt = {'L': 'right', 'R': 'left', 'U': 'center', 'D': 'center'}[direction]
            self.place(libid, ref, net, ex, ey, angle, None, [], hide_ref=True, valpos=vp, just=jt)

    def flag(self, net, x, y):
        s, _ = import_symbol('power', 'PWR_FLAG', 'power:PWR_FLAG')
        self.need('power:PWR_FLAG', s)
        self.pwr += 1
        self.label(net, x, y + G, 180)
        self.wire(x, y, x, y + G)
        self.place('power:PWR_FLAG', '#FLG%s%02d' % (self.name[:3].upper(), self.pwr), 'PWR_FLAG', x, y, 0, None, [],
                   hide_ref=True, valpos=(x, y - 4.5), just='center')


POWER_NETS = set()     # filled from circuit.POWER_NETS


def connect(page, net, x, y, a):
    """Attach `net` to a pin end at (x, y); a = direction the pin points
    away from the body (L, R, U, D)."""
    if net is None:
        page.noconnect(x, y)
        return
    if net in POWER_NETS:
        page.port(net, x, y, a)
        return
    if a in ('L', 'R'):
        dx = -G if a == 'L' else G
        page.wire(x, y, x + dx, y)
        page.label(net, x + dx, y, 180 if a == 'L' else 0)
    else:
        dy = -G if a == 'U' else G
        page.wire(x, y, x, y + dy)
        page.label(net, x, y + dy, 90 if a == 'U' else 270)


def _dir(a_pin, angle):
    """Pin angle in the symbol (direction toward the body) -> which way the
    wire leaves on the sheet, after the symbol is rotated by `angle`."""
    out = (a_pin + 180 + angle) % 360
    return {0: 'R', 90: 'U', 180: 'L', 270: 'D'}[out]


# ---------------------------------------------------------------- the drawing
def symbol_for(part):
    p = parts.PARTS[part]
    s = p['sym']
    if s == 'box':
        libid = 'og:' + part
        sym, pos, box = ic_symbol(libid, p['symbol'])
        return libid, sym, pos, box
    lib, name = s
    libid = 'og_%s:%s_%s' % (lib.lower(), name, part) if p.get('pinmap') else '%s:%s' % (lib, name)
    sym, pos = import_symbol(lib, name, libid, p.get('pinmap'))
    xs = [x for v in pos.values() for (x, y, a) in v]
    ys = [y for v in pos.values() for (x, y, a) in v]
    return libid, sym, pos, (max(xs) - min(xs) + 2 * G, max(ys), min(ys))


def two_pin_horizontal(part):
    """Two-terminal parts are drawn lying down, labels at both ends."""
    p = parts.PARTS[part]
    if p['sym'] == 'box' or not p.get('lie', True):
        return False
    return len(symbol_for(part)[2]) == 2


def draw_page(page, comps):
    x0, y0 = 25.4, 35.56
    page.text(page.title, 15.24, 12.7, 3.0)
    notes = circuit.BLOCK_NOTES.get(page.name, '')
    if notes:
        page.text(notes, 15.24, 19.05, 1.5)
        y0 += G * (notes.count('\n') + 2)
    # big parts first, in a row that wraps
    big = [c for c in comps if not two_pin_horizontal(c.part)]
    small = [c for c in comps if two_pin_horizontal(c.part)]
    x, y, rowh = x0, y0, 0
    for c in big:
        libid, sym, pos, (w, top, bottom) = symbol_for(c.part)
        page.need(libid, sym)
        nets = [n for n in c.pins.values() if n]
        lw = max([label_len(n) for n in nets] + [6])
        full_w = w + 2 * lw
        if x + full_w > 380 and x > x0:
            x, y, rowh = x0, y + rowh + 10, 0
        cx = x + lw + w / 2
        cy = y + top + G
        cy = G * round(cy / G); cx = G * round(cx / G)
        page.place(libid, c.ref, parts.PARTS[c.part]['value'], cx, cy, 0, c, fields(c),
                   refpos=(cx - w / 2 + G, cy - top - 1.5), valpos=(cx - w / 2 + G, cy - bottom + 2.5))
        done = set()
        spec = parts.PARTS[c.part].get('symbol')
        if spec:
            # runs of neighbouring pins on one power net share one wire and one port
            for side in ('left', 'right'):
                run = []
                for pad in spec[side] + ['-']:
                    n = c.pins.get(pad) if pad != '-' else None
                    if run and (pad == '-' or n != c.pins.get(run[0]) or n not in POWER_NETS):
                        if len(run) > 1:
                            pts = [(cx + pos[r][0][0], cy - pos[r][0][1], _dir(pos[r][0][2], 0)) for r in run]
                            d = pts[0][2]
                            bx = pts[0][0] + (-G if d == 'L' else G)
                            for (px_, py_, _) in pts:
                                page.wire(px_, py_, bx, py_)
                            for (_, ya, _), (_, yb, _) in zip(pts, pts[1:]):
                                page.wire(bx, ya, bx, yb)
                            for (_, ya, _) in pts[1:-1]:
                                page.junction(bx, ya)
                            mid = pts[len(pts) // 2][1]
                            if len(pts) == 2:
                                page.junction(bx, mid)
                            page.port(c.pins.get(run[0]), bx, mid, d)
                            done.update(run)
                        run = []
                    if pad != '-' and n in POWER_NETS:
                        run.append(pad)
        for pad, plist in pos.items():
            if pad in done:
                continue
            for (px, py, pa) in plist:
                sx, sy = cx + px, cy - py
                connect(page, c.pins.get(pad, '__missing__'), sx, sy, _dir(pa, 0))
        x += full_w + 5.08
        rowh = max(rowh, (top - bottom) + 2 * G + 6)
    # two-pin parts below: standing up (rail on top, ground at the bottom)
    # when either end is a power net, lying down between two labels otherwise
    y = G * round((y + rowh + 12.7) / G)
    stand = [c for c in small if c.pins.get('1') in POWER_NETS or c.pins.get('2') in POWER_NETS]
    lie = [c for c in small if c not in stand]
    x, col = x0, 12.7

    def upright(pos):
        """Library symbols draw resistors and capacitors with pins top and
        bottom, but diodes, LEDs and switches with pins left and right:
        the rotation that puts pin 1 at the top differs."""
        (px, py, _), = pos['1'][:1]
        return 0 if abs(py) > abs(px) else 270

    def lab(n):
        return 0 if (n in POWER_NETS or n is None) else label_len(n)
    rowh = 0
    for c in stand:
        libid, sym, pos, _ = symbol_for(c.part)
        page.need(libid, sym)
        n1, n2 = c.pins.get('1'), c.pins.get('2')
        flip = n1 == 'GND' or (n2 in POWER_NETS and n2 != 'GND' and n1 not in POWER_NETS)
        top, bot = (n2, n1) if flip else (n1, n2)
        h_top = 3.81 + 2 * G + max(lab(top), 4)
        h_bot = 3.81 + 2 * G + max(lab(bot), 4)
        if x + col > 390:
            x, y, rowh = x0, y + rowh + 7.62, 0
        cy = G * round((y + h_top) / G)
        cx = G * round(x / G)
        angle = (upright(pos) + (180 if flip else 0)) % 360
        page.place(libid, c.ref, parts.PARTS[c.part]['value'], cx, cy, angle, c, fields(c),
                   refpos=(cx + 1.8, cy - 1.0), valpos=(cx + 1.8, cy + 1.6))
        for pad, plist in pos.items():
            for (px, py, pa) in plist:
                ox, oy = _rot(px, py, angle)
                connect(page, c.pins.get(pad, '__missing__'), cx + ox, cy + oy, _dir(pa, angle))
        x += col
        rowh = max(rowh, h_top + h_bot)
    y = G * round((y + rowh + 10.16) / G)
    x = x0
    for c in lie:
        libid, sym, pos, _ = symbol_for(c.part)
        page.need(libid, sym)
        l1, l2 = lab(c.pins.get('1')), lab(c.pins.get('2'))
        span = l1 + l2 + 2 * 3.81 + 4 * G + 5.08
        if x + span > 390:
            x, y = x0, y + 12.7
        cx = G * round((x + l1 + 2 * G + 3.81) / G)
        angle = (upright(pos) + 90) % 360        # pin 1 on the left
        page.place(libid, c.ref, parts.PARTS[c.part]['value'], cx, y, angle, c, fields(c),
                   refpos=(cx, y - 2.6), valpos=(cx, y + 3.0), just='center')
        for pad, plist in pos.items():
            for (px, py, pa) in plist:
                ox, oy = _rot(px, py, angle)
                connect(page, c.pins.get(pad, '__missing__'), cx + ox, y + oy, _dir(pa, angle))
        x += span
    page.maxy = y + 20


def fields(c):
    p = parts.PARTS[c.part]
    out = [('Footprint', p.get('fp', '')), ('MPN', p.get('mpn', '')), ('Manufacturer', p.get('maker', '')),
           ('DigiKey', p.get('digikey', '')), ('LCSC', p.get('lcsc', '')), ('Description', p.get('desc', ''))]
    return [(k, v) for k, v in out if v]


def pin_type(part, pad):
    p = parts.PARTS[part]
    if p['sym'] == 'box':
        return p['symbol']['pins'][pad][1]
    return 'passive'


def power_flags(comps):
    """{block: [nets]} for nets with a power_in pin and no power_out pin,
    each flagged once on the first page it appears on."""
    types, first = {}, {}
    for c in comps:
        for pad, n in c.pins.items():
            if n:
                types.setdefault(n, set()).add(pin_type(c.part, pad))
                first.setdefault(n, c.block)
    out = {}
    for n, t in sorted(types.items()):
        if 'power_in' in t and not t & {'power_out'}:
            out.setdefault(first[n], []).append(n)
    return out


def write_sheet(path, page, root_uuid, sheet_uuid, paper):
    lib = ['lib_symbols'] + [page.syms[k] for k in sorted(page.syms)]
    body = []
    for kind, node, *rest in page.items:
        if kind == 'sym':
            ref = rest[0]
            inst = ['instances', ['project', q(PROJECT), ['path', q('/%s/%s' % (root_uuid, sheet_uuid)),
                                                        ['reference', q(ref)], ['unit', '1']]]]
            body.append(node + [inst])
        else:
            body.append(node)
    doc = ['kicad_sch', ['version', '20250114'], ['generator', '"eeschema"'], ['generator_version', '"10.0"'],
           ['uuid', q(sheet_uuid + '0' if False else uid('sheetfile', page.name))], paper,
           ['title_block', ['title', q(page.title)], ['rev', '"v1"'], ['company', '"OffGrid Devices"']],
           lib] + body + [['embedded_fonts', 'no']]
    with open(path, 'w') as fh:
        fh.write(emit(doc) + '\n')


def build():
    global POWER_NETS
    POWER_NETS = set(circuit.POWER_NETS)
    comps = circuit.build()
    os.makedirs(OUT, exist_ok=True)
    root_uuid = uid('root')
    flags = power_flags(comps)
    sheets = []
    for i, (block, title) in enumerate(circuit.BLOCKS):
        cs = [c for c in comps if c.block == block]
        page = Page(block, title)
        draw_page(page, cs)
        # a net with power inputs but nothing KiCad recognises as a source
        # (a connector, the battery, an inductor output) gets a power flag
        page.maxy = G * round(page.maxy / G)
        for k, net in enumerate(flags.get(block, [])):
            page.flag(net, 15.24 + 30.48 * k, page.maxy)
        page.maxy = G * round((page.maxy + 10) / G)
        h = max(297, G * round((page.maxy + 15) / G))
        paper = ['paper', '"User"', f(420), f(h)] if h > 297 else ['paper', '"A3"']
        su = uid('sheet', block)
        write_sheet(os.path.join(OUT, block + '.kicad_sch'), page, root_uuid, su, paper)
        ALLSYMS.update(page.syms)
        sheets.append((block, title, su, i + 2))
    # the root page: the block diagram as sheet boxes, plus the design notes
    root = ['kicad_sch', ['version', '20250114'], ['generator', '"eeschema"'], ['generator_version', '"10.0"'],
            ['uuid', q(root_uuid)], ['paper', '"A3"'],
            ['title_block', ['title', '"Mesh Radio v1 (working name)"'], ['rev', '"v1"'], ['company', '"OffGrid Devices"'],
             ['comment', '1', q('Generated from src/circuit.py by src/sch.py. Edit the circuit, not this file.')]],
            ['lib_symbols']]
    for k, (block, title, su, pg) in enumerate(sheets):
        col, row = k % 4, k // 4
        x, y = 20.32 + col * 99.06, 60.96 + row * 50.8
        root.append(['sheet', ['at', f(x), f(y)], ['size', '83.82', '30.48'], ['exclude_from_sim', 'no'],
                     ['in_bom', 'yes'], ['on_board', 'yes'], ['dnp', 'no'],
                     ['stroke', ['width', '0'], ['type', 'solid']], ['fill', ['color', '0', '0', '0', '0.0000']],
                     ['uuid', q(su)],
                     ['property', '"Sheetname"', q(title), ['at', f(x), f(y - 0.8), '0'], _font(1.524, justify='left bottom')],
                     ['property', '"Sheetfile"', q(block + '.kicad_sch'), ['at', f(x), f(y + 31.3), '0'], _font(1.27, justify='left top')],
                     ['instances', ['project', q(PROJECT), ['path', q('/' + root_uuid), ['page', q(str(pg))]]]]])
        note = circuit.BLOCK_NOTES.get(block, '')
        if note:
            root.append(['text', q(note.replace('\n', ' ')), ['exclude_from_sim', 'no'], ['at', f(x + 1.5), f(y + 2.0), '0'],
                         _font(1.1, justify='left top'), ['uuid', q(uid('note', block))]])
    root.append(['text', q(circuit.OVERVIEW), ['exclude_from_sim', 'no'], ['at', '20.32', '17.78', '0'],
                 _font(1.8, justify='left top'), ['uuid', q(uid('overview'))]])
    root.append(['sheet_instances', ['path', '"/"', ['page', '"1"']]])
    root.append(['embedded_fonts', 'no'])
    with open(os.path.join(OUT, PROJECT + '.kicad_sch'), 'w') as fh:
        fh.write(emit(root) + '\n')
    write_libraries(ALLSYMS)
    # Footprints are linked by name now and the library (og.pretty) is built
    # with the board layout; until then KiCad cannot find it, so that one
    # check is switched off here, and only that one.
    with open(os.path.join(OUT, PROJECT + '.kicad_pro'), 'w') as fh:
        json.dump({'meta': {'filename': PROJECT + '.kicad_pro', 'version': 3},
                   'erc': {'rule_severities': {'footprint_link_issues': 'ignore'}}}, fh, indent=2)
        fh.write('\n')
    return comps


ALLSYMS = {}


def write_libraries(syms):
    """Every symbol the drawing uses, as project libraries (lib/<nickname>.kicad_sym)
    with a sym-lib-table, so the schematic opens in KiCad with its symbols
    editable and the library check clean."""
    import copy
    libdir = os.path.join(OUT, 'lib')
    os.makedirs(libdir, exist_ok=True)
    bynick = {}
    for libid, sym in syms.items():
        nick, name = libid.split(':', 1)
        s = copy.deepcopy(sym)
        s[1] = q(name)
        bynick.setdefault(nick, []).append((name, s))
    rows = []
    for nick in sorted(bynick):
        doc = ['kicad_symbol_lib', ['version', '20241209'], ['generator', '"mesh_radio_sch"'],
               ['generator_version', '"10.0"']] + [s for _, s in sorted(bynick[nick], key=lambda t: t[0])]
        with open(os.path.join(libdir, nick + '.kicad_sym'), 'w') as fh:
            fh.write(emit(doc) + '\n')
        rows.append(['lib', ['name', q(nick)], ['type', '"KiCad"'], ['uri', q('${KIPRJMOD}/lib/%s.kicad_sym' % nick)],
                     ['options', '""'], ['descr', '"Mesh Radio v1 schematic symbols"']])
    with open(os.path.join(OUT, 'sym-lib-table'), 'w') as fh:
        fh.write(emit(['sym_lib_table', ['version', '7']] + rows) + '\n')


def kicad_nets(netfile):
    """{net: {(ref, pad)}} from a KiCad s-expression netlist."""
    t = parse(open(netfile).read())[0]
    nets = {}
    for n in t:
        if isinstance(n, list) and n[0] == 'nets':
            for net in n[1:]:
                name = [d for d in net if isinstance(d, list) and d[0] == 'name'][0][1].strip('"')
                nodes = set()
                for d in net:
                    if isinstance(d, list) and d[0] == 'node':
                        ref = [e for e in d if isinstance(e, list) and e[0] == 'ref'][0][1].strip('"')
                        pin = [e for e in d if isinstance(e, list) and e[0] == 'pin'][0][1].strip('"')
                        if not ref.startswith('#'):
                            nodes.add((ref, pin))
                if nodes:
                    nets[name.lstrip('/')] = nodes
    return nets


def check_sch(comps):
    """The drawn schematic's netlist must equal circuit.py's, net by net."""
    root = os.path.join(OUT, PROJECT + '.kicad_sch')
    net = os.path.join(OUT, PROJECT + '.net')
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', net, root],
                   check=True, capture_output=True)
    got = kicad_nets(net)
    want = {}
    for c in comps:
        for pad, n in c.pins.items():
            if n:
                want.setdefault(n, set()).add((c.ref, pad))
    # KiCad names unlabelled single-pin nets "unconnected-..."; drop them
    got = {k: v for k, v in got.items() if not k.startswith('unconnected-')}
    bad = []
    for n in sorted(set(want) | set(got)):
        if want.get(n) != got.get(n):
            bad.append((n, sorted(want.get(n, set()) ^ got.get(n, set()))[:6]))
    os.remove(net)
    return bad


def erc():
    root = os.path.join(OUT, PROJECT + '.kicad_sch')
    rpt = os.path.join(OUT, 'erc.json')
    subprocess.run(['kicad-cli', 'sch', 'erc', '--format', 'json', '--severity-all', '-o', rpt, root],
                   capture_output=True)
    d = json.load(open(rpt))
    vio = [v for s in d.get('sheets', []) for v in s.get('violations', [])]
    return vio


def pdf():
    root = os.path.join(OUT, PROJECT + '.kicad_sch')
    out = os.path.join(OUT, PROJECT + '-schematic.pdf')
    subprocess.run(['kicad-cli', 'sch', 'export', 'pdf', '-o', out, root], check=True, capture_output=True)
    return out


if __name__ == '__main__':
    comps = build()
    bad = check_sch(comps)
    print('netlist vs circuit.py: %s' % ('equal' if not bad else '%d nets differ' % len(bad)))
    for b in bad[:20]:
        print('   ', b)
    vio = erc()
    from collections import Counter
    print('ERC: %d violations' % len(vio), dict(Counter((v['severity'], v['type']) for v in vio)))
    for v in vio[:40]:
        print('   ', v['severity'], v['type'], '|', v['description'], '|', [i.get('description') for i in v.get('items', [])][:3])
    print(pdf())
    sys.exit(1 if bad else 0)
