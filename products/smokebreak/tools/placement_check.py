"""Compact placement check: overlaps + plot with the case overlays.
    cd src && python3 ../tools/placement_check.py out.png"""
import sys, os; sys.path.insert(0, '.')
import importlib
import pcbnew, board as B, place, geometry as G
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
GAP = 0.25
def boxes(fp):
    out = []; fp.BuildCourtyardCaches()
    lay = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    cy = fp.GetCourtyard(lay)
    mm = pcbnew.ToMM
    if cy.OutlineCount():
        bb = cy.BBox(); out.append((mm(bb.GetLeft())-B.OX, mm(bb.GetTop())-B.OY, mm(bb.GetRight())-B.OX, mm(bb.GetBottom())-B.OY, 0.0))
    for p in fp.Pads():
        if fp.IsFlipped() and not p.GetDrillSize().x: continue
        bb = p.GetBoundingBox()
        out.append((mm(bb.GetLeft())-B.OX, mm(bb.GetTop())-B.OY, mm(bb.GetRight())-B.OX, mm(bb.GetBottom())-B.OY, GAP))
    return out
b = B.new_board(os.path.join('out', 'placement-check.kicad_pcb'))
fps = B.place_components(b, place.PL)
items = {r: boxes(fp) for r, fp in fps.items() if not fp.IsFlipped()}
refs = list(items)
bad = []
for i, r1 in enumerate(refs):
    for r2 in refs[i+1:]:
        w = 0
        for (a,b_,c,d,g) in items[r1]:
            for (e,f,h,k,g2) in items[r2]:
                m = max(g, g2)
                ox = min(c,h)-max(a,e)+m; oy = min(d,k)-max(b_,f)+m
                if ox > 0 and oy > 0: w = max(w, min(ox, oy))
        if w > 0.001: bad.append((r1, r2, w))
# outside the board (inset 0.5), except the plugs whose mouths go through the wall
for r, bs in items.items():
    if r in ('J1', 'J2', 'J8'): continue
    a = min(v[0] for v in bs); b_ = min(v[1] for v in bs); c = max(v[2] for v in bs); d = max(v[3] for v in bs)
    if a < 0.5 or b_ < 0.5 or c > B.W - 0.5 or d > B.H - 0.5: bad.append((r, 'EDGE', round(max(0.5-a, 0.5-b_, c-B.W+0.5, d-B.H+0.5), 2)))
# height zones: under the module only parts <= UNDER_SCREEN_MAX
TALL = {'J1': 8.2, 'SW1': 8.9, 'J5': 7, 'J9': 7, 'J10': 7, 'J11': 7, 'J12': 7}
mx0, my0 = G.b(G.MODULE[0], G.MODULE[1]); mx1, my1 = mx0 + G.MODULE[2], my0 + G.MODULE[3]
for r, h in TALL.items():
    bs = items[r]; a = min(v[0] for v in bs); b_ = min(v[1] for v in bs); c = max(v[2] for v in bs); d = max(v[3] for v in bs)
    if a < mx1 and c > mx0 and b_ < my1 and d > my0: bad.append((r, 'UNDER-MODULE', h))
for x in bad: print(*x)
print(len(bad), 'conflicts')
fig, ax = plt.subplots(figsize=(19, 10.5))
def rect(x0, y0, w, h, **k): ax.add_patch(plt.Rectangle((x0, y0), w, h, **k))
rect(0, 0, B.W, B.H, fill=False, ec='k', lw=1.2)
rect(mx0, my0, G.MODULE[2], G.MODULE[3], fc='#9cf', alpha=0.15, ec='#36c', lw=1)
wx, wy = G.b(G.WELL[0], G.WELL[1]); rect(wx, wy, G.WELL[2], G.WELL[3], fc='#fc9', alpha=0.15, ec='#c60', lw=1)
rx, ry = G.b(G.ROCK[0], G.ROCK[1]); rect(rx, ry, G.ROCK[2], G.ROCK[3], fill=False, ec='#999', ls='--')
gx, gy = G.b(G.GUARD_X0, G.M); rect(gx, gy, G.GUARD_W, G.GUARD_L, fill=False, ec='#e60', ls='--')
for (x, y) in G.HOLES: ax.add_patch(plt.Circle((x, y), 3.75, fill=False, ec='#a0a', lw=1))
badrefs = {x[0] for x in bad} | {x[1] for x in bad}
for r, fp in fps.items():
    bs = boxes(fp)
    col = 'b' if fp.IsFlipped() else ('r' if r in badrefs else 'k')
    for (a,b_,c,d,g) in bs[:1]: rect(a, b_, c-a, d-b_, fill=False, ec=col, lw=0.6)
    for (a,b_,c,d,g) in bs[1:]: rect(a, b_, c-a, d-b_, fc='#f2b', alpha=0.3, lw=0)
    p = fp.GetPosition(); ax.text(pcbnew.ToMM(p.x)-B.OX, pcbnew.ToMM(p.y)-B.OY, r, fontsize=5, ha='center', va='center', color=col)
ax.set_xlim(-6, 96); ax.set_ylim(51, -3); ax.set_aspect('equal'); ax.grid(lw=.3); ax.set_xticks(range(-6, 97, 2)); ax.set_yticks(range(-2, 51, 2)); ax.tick_params(labelsize=6)
if len(sys.argv) > 5:
    x0, y0, x1, y1 = map(float, sys.argv[2:6]); ax.set_xlim(x0, x1); ax.set_ylim(y1, y0)
plt.tight_layout(); plt.savefig(sys.argv[1], dpi=110)
