"""Finish the routed board: ground pours on both faces, silkscreen artwork,
zone fill. Runs inside KiCad 10.0.6.   finish.py <routed.kicad_pcb> <out.kicad_pcb>"""
import os, sys
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import board as B

MM = pcbnew.FromMM


def pours(b):
    gnd = b.FindNet('GND')
    m = 0.0
    pts = [(B.X0 + m, B.Y0 + m), (B.X1 - m, B.Y0 + m), (B.X1 - m, B.Y1 - m), (B.X0 + m, B.Y1 - m)]
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        B.zone(b, gnd, layer, pts, prio=0, name='GND_' + ('F' if layer == pcbnew.F_Cu else 'B'))


def silk(b):
    T = B.text
    # front
    T(b, 'CANARY', 111.6, 123.0, size=2.2, thick=0.35, bold=True)
    T(b, 'Li-ion first-vent detector', 111.6, 125.6, size=0.8, thick=0.15)
    T(b, 'v1  2026', 111.6, 127.4, size=0.8, thick=0.15)
    T(b, 'OK', 138.6, 108.4, size=0.8)
    T(b, 'WARN', 142.8, 108.4, size=0.8)
    T(b, 'ALARM', 147.0, 108.4, size=0.8)
    T(b, 'AIR IN', 155.4, 124.6, size=0.9, thick=0.18)
    T(b, 'VOC  RH/T', 155.4, 126.4, size=0.8)
    T(b, 'TEST / HUSH', 146.2, 132.6, size=0.8)
    T(b, 'PROBE', 124.6, 128.6, size=0.8)
    T(b, 'NTC TAB', 108.0, 131.0, size=0.8)
    T(b, '5V USB-C', 104.2, 118.6, size=0.8)
    T(b, 'CO2', 143.6, 113.6, size=0.8)
    T(b, 'TXD RXD GND', 147.6, 129.4, size=0.8)
    # back (mirrored)
    bl = pcbnew.B_SilkS
    T(b, 'CANARY v1', 125.0, 106.0, size=2.0, layer=bl, thick=0.3, mirror=True, bold=True)
    T(b, 'Lay the NTC tab on the pack while it charges.', 125.0, 110.0, size=0.8, layer=bl, mirror=True)
    T(b, 'Green breathing: watching. Amber: odd air.', 125.0, 111.8, size=0.8, layer=bl, mirror=True)
    T(b, 'Red + siren: vent signature. Unplug, get out.', 125.0, 113.6, size=0.8, layer=bl, mirror=True)
    T(b, 'Not a certified safety device.', 125.0, 116.4, size=0.8, layer=bl, mirror=True)
    T(b, 'Keep your smoke alarm.', 125.0, 118.2, size=0.8, layer=bl, mirror=True)
    T(b, 'OffGrid Devices  CERN-OHL-S v2', 125.0, 121.4, size=0.8, layer=bl, mirror=True)
    T(b, 'THERMAL TAB', 108.0, 134.8, size=1.0, layer=bl, mirror=True, thick=0.18)
    T(b, 'SENSOR HEAD', 155.2, 114.0, size=0.8, layer=bl, mirror=True)


STACKUP = """		(stackup
			(layer "F.SilkS" (type "Top Silk Screen") (color "Black"))
			(layer "F.Paste" (type "Top Solder Paste"))
			(layer "F.Mask" (type "Top Solder Mask") (color "Yellow") (thickness 0.01))
			(layer "F.Cu" (type "copper") (thickness 0.035))
			(layer "dielectric 1" (type "core") (thickness 1.51) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
			(layer "B.Cu" (type "copper") (thickness 0.035))
			(layer "B.Mask" (type "Bottom Solder Mask") (color "Yellow") (thickness 0.01))
			(layer "B.Paste" (type "Bottom Solder Paste"))
			(layer "B.SilkS" (type "Bottom Silk Screen") (color "Black"))
			(copper_finish "ENIG")
			(dielectric_constraints no)
		)
"""


def colours(path):
    """Canary-yellow solder mask, black silkscreen, ENIG, 1.6 mm FR-4: the
    board stackup the renders use and the order notes repeat. pcbnew's
    Python API does not expose the stackup, so it goes into the file."""
    t = open(path).read()
    if '(stackup' not in t:
        i = t.index('(setup') + len('(setup')
        t = t[:i] + '\n' + STACKUP.rstrip('\n') + t[i:]
        open(path, 'w').write(t)


def fields(b):
    """Part data (MPN, maker, LCSC, description) from circuit.py, so a
    sourcing change needs no re-route."""
    import circuit
    for p in circuit.PARTS:
        fp = b.FindFootprintByReference(p['ref'])
        for k, v in (('MPN', p['mpn']), ('Manufacturer', p['mfr']), ('LCSC', p['lcsc']),
                     ('Description', p['desc'])):
            fp.SetField(k, v)
            fp.GetField(k).SetVisible(False)


def main(src, dst):
    b = pcbnew.LoadBoard(src)
    fields(b)
    tb = b.GetTitleBlock()
    tb.SetTitle('Canary - Li-ion first-vent detector'); tb.SetRevision('v1')
    tb.SetDate('2026-10-14'); tb.SetCompany('OffGrid Devices')
    pours(b)
    silk(b)
    filler = pcbnew.ZONE_FILLER(b)
    filler.Fill(b.Zones())
    b.Save(dst)
    colours(dst)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
