"""Generate canary.kicad_sch from circuit.py.

Every pin gets a short stub and a net label (or a power symbol), so the
schematic is exactly the netlist in circuit.py; check.py proves it by
comparing KiCad's own netlist export against circuit.nets().
"""
import math, os, uuid
import circuit, libsym, canary_lib
from sexpr import dump, find, findall, Sym

ROOT = canary_lib.ROOT
PROJECT = 'canary'
NS = uuid.UUID('6f0d1c1e-3a52-4c55-9d1b-6361e1a5ca7e')
ROOT_UUID = str(uuid.uuid5(NS, 'root'))
POWER = {'GND': 'power:GND', '+3V3': 'power:+3V3', 'VBUS': 'power:VBUS'}
STUB = 2.54


def U(*k):
    return str(uuid.uuid5(NS, '/'.join(map(str, k))))


def snap(v):
    return round(round(v / 1.27) * 1.27, 3)


def font(size=1.27, hide=False, justify=None):
    e = ['effects', ['font', ['size', size, size]]]
    if justify:
        e.append(['justify'] + [Sym(j) for j in justify.split()])
    if hide:
        e.append(['hide', Sym('yes')])
    return e


def prop(name, value, x, y, ang=0, hide=False, justify=None, size=1.27):
    return [Sym('property'), name, value, ['at', x, y, ang], font(size, hide, justify)]


def xform(px, py, X, Y, R):
    sx, sy = px, -py
    r = math.radians(R)
    return (round(X + sx * math.cos(r) + sy * math.sin(r), 3),
            round(Y - sx * math.sin(r) + sy * math.cos(r), 3))


def outward(pin_ang, R):
    t = (pin_ang + R + 180) % 360
    return t, (round(math.cos(math.radians(t))), -round(math.sin(math.radians(t))))


class Sheet:
    def __init__(self):
        self.items, self.libs, self.pwr_n = [], {}, 0

    def lib(self, lib_id):
        if lib_id not in self.libs:
            path = os.path.join(ROOT, 'canary.kicad_sym') if lib_id.startswith('canary:') else None
            self.libs[lib_id] = libsym.load(lib_id, path)
        return self.libs[lib_id]

    def symbol(self, lib_id, ref, value, X, Y, R=0, fields=(), in_bom=True, on_board=True,
               ref_xy=None, val_xy=None, hide_val=False):
        sym = self.lib(lib_id)
        pins = libsym.pins(sym)
        e = [Sym('symbol'), ['lib_id', lib_id], ['at', X, Y, R], ['unit', 1],
             ['body_style', 1], ['exclude_from_sim', Sym('no')],
             ['in_bom', Sym('yes' if in_bom else 'no')], ['on_board', Sym('yes' if on_board else 'no')],
             ['dnp', Sym('no')], ['uuid', U('sym', ref)]]
        rx, ry = ref_xy or (X + 3, Y - 3)
        vx, vy = val_xy or (X + 3, Y + 3)
        e.append(prop('Reference', ref, rx, ry, 0, ref.startswith('#'), 'left'))
        e.append(prop('Value', value, vx, vy, 0, hide_val or ref.startswith('#'), 'left'))
        for k, v in fields:
            e.append(prop(k, v, X, Y, 0, True))
        for p in pins:
            e.append([Sym('pin'), p[0], ['uuid', U('pin', ref, p[0])]])
        e.append([Sym('instances'), [Sym('project'), PROJECT,
                  [Sym('path'), '/' + ROOT_UUID, ['reference', ref], ['unit', 1]]]])
        self.items.append(e)
        return pins

    def power(self, net, x, y, theta):
        self.pwr_n += 1
        base = 270 if net == 'GND' else 90
        R = (theta - base) % 360
        self.symbol(POWER[net], f'#PWR0{self.pwr_n:02d}', net, x, y, R)

    def wire(self, a, b):
        self.items.append([Sym('wire'), ['pts', ['xy', *a], ['xy', *b]],
                           ['stroke', ['width', 0], ['type', Sym('default')]], ['uuid', U('w', a, b)]])

    def label(self, net, x, y, theta):
        just = 'left bottom' if theta in (0, 90) else 'right bottom'
        self.items.append([Sym('label'), net, ['at', x, y, theta], font(1.27, False, just),
                           ['uuid', U('l', net, x, y)]])

    def nc(self, x, y):
        self.items.append([Sym('no_connect'), ['at', x, y], ['uuid', U('nc', x, y)]])

    def text(self, s, x, y, size=2.5):
        self.items.append([Sym('text'), s, ['exclude_from_sim', Sym('no')], ['at', x, y, 0],
                           font(size, False, 'left bottom'), ['uuid', U('t', s)]])

    def part(self, p):
        X, Y = snap(p['pos'][0]), snap(p['pos'][1])
        fields = [('Footprint', p['fp']), ('Datasheet', ''), ('Description', p['desc']),
                  ('MPN', p['mpn']), ('Manufacturer', p['mfr']), ('LCSC', p['lcsc'])]
        # Footprint must be the real property, not a duplicate field
        pins = self.symbol(p['lib'], p['ref'], p['value'], X, Y, p['rot'],
                           fields=fields, in_bom=p['bom'])
        done = set()
        for num, name, typ, px, py, ang, ln, unit in pins:
            x, y = xform(px, py, X, Y, p['rot'])
            if (x, y) in done:
                continue
            done.add((x, y))
            net = p['pins'].get(num)
            if net is None:
                self.nc(x, y)
                continue
            theta, (dx, dy) = outward(ang, p['rot'])
            ex, ey = round(x + dx * STUB, 3), round(y + dy * STUB, 3)
            self.wire((x, y), (ex, ey))
            if net in POWER:
                self.power(net, ex, ey, theta)
            else:
                self.label(net, ex, ey, theta)

    def pwr_flag(self, net, x, y):
        self.pwr_n += 1
        self.symbol('power:PWR_FLAG', f'#FLG0{self.pwr_n:02d}', 'PWR_FLAG', x, y, 0)
        self.wire((x, y), (x, y + STUB))
        self.power(net, x, y + STUB, 270 if net == 'GND' else 90) if net == 'GND' else \
            self.power(net, x, y + STUB, 90)

    def write(self, path):
        lib_symbols = [Sym('lib_symbols')]
        for lid, s in sorted(self.libs.items()):
            s = [x for x in s]
            lib_symbols.append(s)
        doc = [Sym('kicad_sch'), ['version', Sym('20250901')], ['generator', 'canary_schematic'],
               ['generator_version', '10.0'], ['uuid', ROOT_UUID], ['paper', 'A3'],
               ['title_block', ['title', 'Canary — first-vent detector for lithium batteries'],
                ['date', '2026-10-14'], ['rev', 'v1'], ['company', 'OffGrid Devices'],
                ['comment', 1, 'Generated by src/schematic.py from src/circuit.py — edit the script, not this file'],
                ['comment', 2, 'CERN-OHL-S v2']],
               lib_symbols] + self.items + [
            [Sym('sheet_instances'), [Sym('path'), '/', ['page', '1']]],
            ['embedded_fonts', Sym('no')]]
        open(path, 'w').write(dump(doc) + '\n')


def fix_footprint_props(sheet):
    """symbol() wrote Footprint/Datasheet/Description as hidden fields; the
    library symbol already carries those keys, so de-duplicate by keeping the
    instance values only once."""
    for e in sheet.items:
        if e[0] != 'symbol':
            continue
        seen, out = set(), []
        for x in e:
            if isinstance(x, list) and x and x[0] == 'property':
                if x[1] in seen:
                    continue
                seen.add(x[1])
            out.append(x)
        e[:] = out


def build():
    canary_lib.write()
    s = Sheet()
    for p in circuit.PARTS:
        s.part(p)
    for i, net in enumerate(circuit.PWR_FLAGS):
        s.pwr_flag(net, snap(330 + 12 * i), snap(30))
    s.text('POWER — USB-C 5 V in, TVS, 3.3 V LDO', 20, 25)
    s.text('MCU — ATmega328P, internal 8 MHz', 100, 70)
    s.text('SENSORS — VOC (SGP40), CO2 (SCD41), RH/T (SHT40)', 215, 25)
    s.text('TEMPERATURE — on-board tab NTC + optional probe', 60, 150)
    s.text('ALARM — 4 kHz 100 dB sounder, low-side switch', 15, 95)
    s.text('INDICATION & TEST/HUSH', 170, 145)
    s.text('PROGRAMMING (Tag-Connect TC2030) & TEST PADS', 180, 70, 1.8)
    fix_footprint_props(s)
    s.write(os.path.join(ROOT, PROJECT + '.kicad_sch'))


if __name__ == '__main__':
    build()
