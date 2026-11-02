"""Cut every right-angle (or sharper) track corner into two 45 degree turns
(runs in the KiCad container):

  miter.py <routed board> <out board>

Freerouting draws 45 degree routing but leaves the odd 90 degree corner where
a track turns onto a pad or around an obstacle. Where exactly two tracks of a
net meet, each is shortened by up to 0.5 mm and a diagonal joins the new
ends. check_geometry.py is the gate; DRC proves the diagonals clear.
"""
import math, sys
from collections import defaultdict
import pcbnew

CUT = pcbnew.FromMM(0.5)


def main(src, dst):
    b = pcbnew.LoadBoard(src)
    at = defaultdict(list)
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_TRACK':
            for end in ('Start', 'End'):
                p = getattr(t, 'Get' + end)()
                at[(t.GetNetCode(), t.GetLayer(), p.x, p.y)].append((t, end))
    vias = {(v.GetPosition().x, v.GetPosition().y) for v in b.GetTracks() if v.GetClass() == 'PCB_VIA'}
    n = 0
    for (net, layer, x, y), hits in sorted(at.items(), key=lambda kv: kv[0]):
        if len(hits) != 2 or (x, y) in vias:
            continue
        legs = []
        for t, end in hits:
            far = t.GetEnd() if end == 'Start' else t.GetStart()
            dx, dy = far.x - x, far.y - y
            legs.append((t, end, dx, dy, math.hypot(dx, dy)))
        (_, _, ax, ay, al), (_, _, bx, by, bl) = legs
        cos = (ax * bx + ay * by) / (al * bl)
        if cos < math.cos(math.radians(135)) + 1e-3:      # turn of 45 deg or less
            continue
        d = min(CUT, 0.45 * al, 0.45 * bl)
        pts = []
        for t, end, dx, dy, L in legs:
            p = pcbnew.VECTOR2I(int(round(x + dx * d / L)), int(round(y + dy * d / L)))
            getattr(t, 'Set' + end)(p)
            pts.append(p)
        diag = pcbnew.PCB_TRACK(b)
        diag.SetStart(pts[0]); diag.SetEnd(pts[1])
        diag.SetLayer(layer); diag.SetNetCode(net)
        diag.SetWidth(min(legs[0][0].GetWidth(), legs[1][0].GetWidth()))
        b.Add(diag)
        n += 1
        print(f'mitered {b.FindNet(net).GetNetname()} at ({x / 1e6:.3f}, {y / 1e6:.3f}), cut {d / 1e6:.2f} mm')
    print(f'{n} corners mitered')
    b.Save(dst)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
