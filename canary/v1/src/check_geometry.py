"""Copper geometry gate (runs in the KiCad container):

  check_geometry.py <board>

1. Corners: where two tracks of a net meet away from a pad or via, they
   must turn by 45 degrees or less (no right-angle or sharper corners). Where
   three or more meet, no two may form an acute angle (an etchant trap).
2. Current: every track of a net that carries real current must be at least
   as wide as IPC-2221 needs for its worst-case current with a 10 C rise,
   outer layer, 1 oz copper. Currents are the worst cases in TESTS.md
   (Analog and power); GND is the poured planes on both layers.
"""
import math, sys
from collections import defaultdict
import pcbnew

MAX_TURN_DEG = 45.0
OZ_MIL = 1.378                  # 1 oz copper thickness, mil
RISE_C = 10.0
MIN_SIGNAL_MM = 0.2
CURRENT_A = {                   # worst-case peak, TESTS.md
    'VBUS': 0.52,               # alarm: sounder + SCD41 pulse + LEDs
    '/BUZ_D': 0.33,             # sounder coil current
    '+3V3': 0.20,               # SCD41 measurement pulse + MCU + LEDs
}


def ipc2221_width_mm(amps, rise=RISE_C, oz=OZ_MIL):
    """External-layer width from I = 0.048 * dT^0.44 * A^0.725 (A in mil^2)."""
    area = (amps / (0.048 * rise ** 0.44)) ** (1 / 0.725)
    return area / oz * 0.0254


def key(p):
    return (round(p.x / 1000), round(p.y / 1000))      # 1 um grid


def turn(a, b):
    """Turn angle at a shared point: 0 = straight on, 90 = right angle."""
    d = math.degrees(math.atan2(a[0] * b[1] - a[1] * b[0], a[0] * b[0] + a[1] * b[1]))
    return 180.0 - abs(d)


def check(path):
    b = pcbnew.LoadBoard(path)
    ends = defaultdict(list)        # (net, layer, point) -> outward directions
    stops = set()                   # (layer, point) of via and pad centres
    widths = defaultdict(list)
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                stops.add((layer, key(t.GetPosition())))
            continue
        if t.GetClass() != 'PCB_TRACK':
            continue
        s, e = t.GetStart(), t.GetEnd()
        net, layer = t.GetNetname(), t.GetLayer()
        widths[net].append(t.GetWidth() / 1e6)
        ends[(net, layer, key(s))].append((e.x - s.x, e.y - s.y))
        ends[(net, layer, key(e))].append((s.x - e.x, s.y - e.y))
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                if pad.IsOnLayer(layer):
                    stops.add((layer, key(pad.GetPosition())))
                    # a track that ends anywhere on the pad ends at the pad
                    for (net, lay, pt), dirs in ends.items():
                        if lay == layer and net == pad.GetNetname() and \
                                pad.HitTest(pcbnew.VECTOR2I(pt[0] * 1000, pt[1] * 1000)):
                            stops.add((layer, pt))
    bad, bends, worst = [], 0, 0.0
    for (net, layer, pt), dirs in ends.items():
        if (layer, pt) in stops or len(dirs) < 2:
            continue
        where = f'{net} at ({pt[0] / 1000:.3f}, {pt[1] / 1000:.3f}) {b.GetLayerName(layer)}'
        if len(dirs) == 2:
            a = turn(*dirs)
            if a > 0.5:
                bends += 1
                worst = max(worst, a)
            if a > MAX_TURN_DEG + 0.5:
                bad.append(f'corner {a:.0f} deg: {where}')
        else:
            for i in range(len(dirs)):
                for j in range(i + 1, len(dirs)):
                    if 180.0 - turn(dirs[i], dirs[j]) < 90.0 - 0.5:
                        bad.append(f'acute junction: {where}')
    for net, ws in sorted(widths.items()):
        need = ipc2221_width_mm(CURRENT_A[net]) if net in CURRENT_A else MIN_SIGNAL_MM
        if min(ws) + 1e-6 < need:
            bad.append(f'width: {net} has {min(ws):.3f} mm, needs {need:.3f} mm')
    print(f'geometry: {bends} bends, sharpest {worst:.0f} deg (limit {MAX_TURN_DEG:.0f}); ' +
          ', '.join(f'{n} {min(widths[n]):.2f} mm >= {ipc2221_width_mm(i):.3f} mm @ {i} A'
                    for n, i in CURRENT_A.items()))
    for x in bad:
        print('  FAIL', x)
    return not bad


if __name__ == '__main__':
    sys.exit(0 if check(sys.argv[1]) else 1)
