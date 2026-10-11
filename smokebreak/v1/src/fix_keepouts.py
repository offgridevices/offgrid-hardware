"""Apply make.POWER_KEEPOUTS to a routed board: add the rule areas and remove
every unlocked track of another net that crosses one.  IN OUT"""
import sys
import pcbnew
from shapely.geometry import LineString, Polygon
import board as B
import make

src, out = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(src)
zone_net = {'sources': 'SRC', 'Q1 drain': 'VIN', 'drone negative': 'DRONE_NEG', 'battery minus': 'BATT_NEG'}
n = 0
for name, poly, layers in make.POWER_KEEPOUTS:
    P = Polygon([(x + B.OX, y + B.OY) for x, y in poly]).buffer(-0.05)
    for t in list(b.GetTracks()):
        if t.GetClass() != 'PCB_TRACK' or t.GetLayer() not in layers or t.GetNetname() == zone_net[name]:
            continue
        s, e = t.GetStart(), t.GetEnd()
        if LineString([(pcbnew.ToMM(s.x), pcbnew.ToMM(s.y)), (pcbnew.ToMM(e.x), pcbnew.ToMM(e.y))]).intersects(P):
            B.remove(b, t)
            n += 1
    B.rule_area(b, poly, layers, tracks=True, vias=False, pads=False, pours=False, name='keepout ' + name)
b.Save(out)
print('removed', n, 'tracks crossing power copper')
