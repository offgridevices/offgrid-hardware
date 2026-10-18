"""A zoomed picture of the top copper in a region: pads coloured by net
(ground grey), tracks, references and a 1 mm grid, for checking RF lines.

    kd python3 src/view.py board.kicad_pcb out.png x0 y0 x1 y1   (board mm)
"""
import sys, pcbnew, hashlib
from PIL import Image, ImageDraw
import pcb
b = pcbnew.LoadBoard(sys.argv[1]); out = sys.argv[2]
x0, y0, x1, y1 = map(float, sys.argv[3:7]); S = 80
img = Image.new('RGB', (int((x1-x0)*S), int((y1-y0)*S)), 'white'); d = ImageDraw.Draw(img)
X = lambda v: (v/1e6 - pcb.CX - x0)*S; Y = lambda v: (v/1e6 - pcb.CY - y0)*S
def col(n):
    if n == 'GND': return (150, 150, 150)
    h = hashlib.md5(n.encode()).digest(); return (h[0]//2+40, h[1]//2+40, h[2]//2+40)
for fp in b.GetFootprints():
    for p in fp.Pads():
        if not p.IsOnLayer(pcbnew.F_Cu): continue
        poly = p.GetEffectivePolygon(pcbnew.F_Cu)
        for i in range(poly.OutlineCount()):
            o = poly.Outline(i); pts = [(X(o.CPoint(k).x), Y(o.CPoint(k).y)) for k in range(o.PointCount())]
            if len(pts) > 2: d.polygon(pts, fill=col(p.GetNetname()), outline='black')
    c = fp.GetPosition()
    if fp.GetLayer() == pcbnew.F_Cu: d.text((X(c.x), Y(c.y)), fp.GetReference(), fill='red')
for t in b.GetTracks():
    if t.GetLayer() != pcbnew.F_Cu or t.Type() != pcbnew.PCB_TRACE_T: continue
    a, e = t.GetStart(), t.GetEnd()
    d.line([X(a.x), Y(a.y), X(e.x), Y(e.y)], fill=col(t.GetNetname()), width=max(1, int(t.GetWidth()/1e6*S)))
    d.line([X(a.x), Y(a.y), X(e.x), Y(e.y)], fill='black', width=1)
for g in range(int(x0), int(x1)+1):
    d.text(((g-x0)*S+1, 1), str(g), fill='blue')
for g in range(int(y0), int(y1)+1):
    d.text((1, (g-y0)*S+1), str(g), fill='blue')
img.save(out)
