"""python3 zoom.py board.kicad_pcb out.png x0 y0 x1 y1 [layers F,In2,In3,B]"""
import sys; sys.path.insert(0, '.')
import pcbnew
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon
b = pcbnew.LoadBoard(sys.argv[1]); out = sys.argv[2]
x0, y0, x1, y1 = map(float, sys.argv[3:7])
OX = OY = 100.0; mm = pcbnew.ToMM
LC = {pcbnew.F_Cu: '#d22', pcbnew.In2_Cu: '#2a2', pcbnew.In3_Cu: '#a2a', pcbnew.B_Cu: '#22d', pcbnew.In1_Cu: '#999', pcbnew.In4_Cu: '#c90'}
fig, ax = plt.subplots(figsize=(14, 14 * (y1 - y0) / (x1 - x0)))
for z in b.Zones():
    if z.GetIsRuleArea(): continue
    for l in (pcbnew.F_Cu,):
        if not z.IsOnLayer(l): continue
        ps = z.GetFilledPolysList(l)
        for k in range(ps.OutlineCount()):
            o = ps.Outline(k)
            pts = [(mm(o.CPoint(i).x) - OX, mm(o.CPoint(i).y) - OY) for i in range(o.PointCount())]
            if len(pts) > 2: ax.add_patch(Polygon(pts, fc='#fcc', ec='none', alpha=0.5))
for fp in b.GetFootprints():
    for p in fp.Pads():
        bb = p.GetBoundingBox(); a, c = mm(bb.GetLeft()) - OX, mm(bb.GetRight()) - OX; t, d = mm(bb.GetTop()) - OY, mm(bb.GetBottom()) - OY
        if c < x0 or a > x1 or d < y0 or t > y1: continue
        ax.add_patch(Rectangle((a, t), c - a, d - t, fc='#f80' if p.GetDrillSize().x else '#fa6', ec='k', lw=0.3, alpha=0.8))
        ax.text((a + c) / 2, (t + d) / 2, f'{fp.GetReference()}.{p.GetNumber()}\n{p.GetNetname()[:8]}', fontsize=5, ha='center', va='center')
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        q = t.GetPosition(); x, y = mm(q.x) - OX, mm(q.y) - OY
        if x0 <= x <= x1 and y0 <= y <= y1:
            ax.add_patch(Circle((x, y), mm(t.GetWidth(pcbnew.F_Cu)) / 2, fc='#555', ec='k', lw=0.3))
            ax.text(x, y, t.GetNetname()[:6], fontsize=4, color='w', ha='center')
    else:
        s, e = t.GetStart(), t.GetEnd()
        xs = [mm(s.x) - OX, mm(e.x) - OX]; ys = [mm(s.y) - OY, mm(e.y) - OY]
        if max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1: continue
        ax.plot(xs, ys, color=LC.get(t.GetLayer(), 'k'), lw=mm(t.GetWidth()) * 72 * 14 / (x1 - x0) / 25.4 * 25.4 / 1.0 * 0.35, alpha=0.6, solid_capstyle='round')
        ax.text(sum(xs) / 2, sum(ys) / 2, t.GetNetname()[:6], fontsize=4, color=LC.get(t.GetLayer(), 'k'))
ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_aspect('equal'); ax.grid(lw=0.2)
ax.set_title('F red, In2 green, In3 purple, B blue')
fig.savefig(out, dpi=110, bbox_inches='tight')
