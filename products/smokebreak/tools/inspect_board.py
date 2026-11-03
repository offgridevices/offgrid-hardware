"""Print courtyard boxes and pad positions of placed parts (board mm)."""
import sys
import os
import pcbnew
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import board as B

b = pcbnew.LoadBoard(sys.argv[1])
refs = sys.argv[2:]
for fp in b.GetFootprints():
    r = fp.GetReference()
    if refs and r not in refs:
        continue
    fp.BuildCourtyardCaches()
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox()
    f = lambda v, o: pcbnew.ToMM(v) - o
    print(f'{r:6s} cy x {f(bb.GetLeft(), B.OX):6.2f}..{f(bb.GetRight(), B.OX):6.2f}  y {f(bb.GetTop(), B.OY):6.2f}..{f(bb.GetBottom(), B.OY):6.2f}')
    if refs:
        for p in fp.Pads():
            q = p.GetPosition()
            print(f'    pad {p.GetNumber():5s} ({f(q.x, B.OX):6.2f},{f(q.y, B.OY):6.2f}) {p.GetNetname()}')
