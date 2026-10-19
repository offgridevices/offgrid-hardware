# -*- coding: utf-8 -*-
"""A review picture of a board file: outline, courtyards, pads coloured by
net, tracks, vias, and reference designators.  For checking placement and
routing by eye, not for the fab.

    python3 plot.py BOARD.kicad_pcb OUT.png [--layer F|B|all] [--zoom x0 y0 x1 y1]
"""
import sys, colorsys, hashlib
import pcbnew
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pcb


def colour(net):
    h = int(hashlib.md5(net.encode()).hexdigest()[:6], 16) / 0xffffff
    return colorsys.hsv_to_rgb(h, 0.65, 0.85)


def poly_xy(sh, i):
    o = sh.Outline(i)
    return ([o.CPoint(k).x / 1e6 - pcb.CX for k in range(o.PointCount())],
            [o.CPoint(k).y / 1e6 - pcb.CY for k in range(o.PointCount())])


def main(path, out, layer='all', zoom=None):
    b = pcbnew.LoadBoard(path)
    fig, ax = plt.subplots(figsize=(22, 14) if not zoom else (14, 14))
    ax.add_patch(plt.Rectangle((-pcb.HX, -pcb.HY), pcb.W, pcb.H, fill=False, lw=1.5))
    show = {'F': [pcbnew.F_Cu], 'B': [pcbnew.B_Cu], 'all': [pcbnew.F_Cu, pcbnew.B_Cu]}[layer]
    for z in b.Zones():
        if z.GetIsRuleArea():
            sh = z.Outline()
            for i in range(sh.OutlineCount()):
                xs, ys = poly_xy(sh, i)
                ax.fill(xs, ys, color='red', alpha=0.08, hatch='//')
            continue
        for l in show:
            if z.IsOnLayer(l) and z.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu):
                sh = z.GetFilledPolysList(l)
                for i in range(sh.OutlineCount()):
                    xs, ys = poly_xy(sh, i)
                    ax.fill(xs, ys, color=colour(z.GetNetname()), alpha=0.25 if l == pcbnew.F_Cu else 0.12)
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            x, y = pcb.xy(t.GetPosition())
            ax.add_patch(plt.Circle((x, y), t.GetWidth(pcbnew.F_Cu) / 2e6, color=colour(t.GetNetname()), ec='k', lw=0.3))
        elif t.GetLayer() in show:
            (x0, y0), (x1, y1) = pcb.xy(t.GetStart()), pcb.xy(t.GetEnd())
            ax.plot([x0, x1], [y0, y1], color=colour(t.GetNetname()), lw=max(0.6, t.GetWidth() / 1e6 * 14),
                    alpha=1.0 if t.GetLayer() == pcbnew.F_Cu else 0.5, solid_capstyle='round',
                    ls='-' if t.GetLayer() == pcbnew.F_Cu else '--')
    for fp in b.GetFootprints():
        crt = fp.GetCourtyard(pcbnew.F_CrtYd)
        for i in range(crt.OutlineCount()):
            xs, ys = poly_xy(crt, i)
            ax.plot(xs + xs[:1], ys + ys[:1], color='0.5', lw=0.4)
        for p in fp.Pads():
            sh = p.GetEffectivePolygon(pcbnew.F_Cu, pcbnew.ERROR_INSIDE)
            for i in range(sh.OutlineCount()):
                xs, ys = poly_xy(sh, i)
                ax.fill(xs, ys, color=colour(p.GetNetname()) if p.GetNetname() else '0.8', alpha=0.9, lw=0)
        x, y = pcb.xy(fp.GetPosition())
        ax.text(x, y, fp.GetReference(), fontsize=6 if not zoom else 9, ha='center', va='center', color='k')
    ax.set_aspect('equal'); ax.invert_yaxis()
    if zoom:
        ax.set_xlim(zoom[0], zoom[2]); ax.set_ylim(zoom[3], zoom[1])
    else:
        ax.set_xlim(-pcb.HX - 2, pcb.HX + 2); ax.set_ylim(pcb.HY + 2, -pcb.HY - 2)
    ax.grid(True, lw=0.2)
    plt.tight_layout(); plt.savefig(out, dpi=110)


if __name__ == '__main__':
    a = sys.argv[1:]
    layer = 'all'; zoom = None
    if '--layer' in a:
        i = a.index('--layer'); layer = a[i + 1]; del a[i:i + 2]
    if '--zoom' in a:
        i = a.index('--zoom'); zoom = [float(v) for v in a[i + 1:i + 5]]; del a[i:i + 5]
    main(a[0], a[1], layer, zoom)
