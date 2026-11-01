# -*- coding: utf-8 -*-
"""A review picture of a board file: both faces side by side (each seen
from behind the board's F side, so the two line up), the outline, the
courtyards, pads coloured by net, tracks, vias, reference designators and
the keepouts.  For checking placement and routing by eye, not for the fab.

    python3 plot.py main|ring|usb BOARD.kicad_pcb OUT.png [--zoom x0 y0 x1 y1]
"""
import sys, colorsys, hashlib
import pcbnew
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pcb


def colour(net):
    if not net:
        return (0.75, 0.75, 0.75)
    if net == 'GND':
        return (0.35, 0.35, 0.35)
    h = int(hashlib.md5(net.encode()).hexdigest()[:6], 16) / 0xffffff
    return colorsys.hsv_to_rgb(h, 0.65, 0.85)


def poly_xy(sh, i):
    o = sh.Outline(i)
    return ([o.CPoint(k).x / 1e6 - pcb.CX for k in range(o.PointCount())],
            [o.CPoint(k).y / 1e6 - pcb.CY for k in range(o.PointCount())])


def main(board, path, out, zoom=None):
    pcb.configure(board)
    b = pcbnew.LoadBoard(path)
    fig, axs = plt.subplots(1, 2, figsize=(22, 13))
    poly = pcb.board_polygon()
    for ax, (side, cu, crt) in zip(axs, (('F', pcbnew.F_Cu, pcbnew.F_CrtYd), ('B', pcbnew.B_Cu, pcbnew.B_CrtYd))):
        for g in ([poly] if poly.geom_type == 'Polygon' else poly.geoms):
            x, y = g.exterior.xy; ax.plot(x, y, 'k-', lw=1.2)
            for h in g.interiors:
                x, y = h.xy; ax.plot(x, y, 'k-', lw=1.2)
        try:
            import layout_main as L
            if board == 'main':
                for geom, hmax in L.keepouts(side):
                    for gg in (getattr(geom, 'geoms', None) or [geom]):
                        x, y = gg.exterior.xy
                        ax.fill(x, y, color='orange' if hmax else 'red', alpha=0.10)
        except Exception:
            pass
        for z in b.Zones():
            if not z.GetIsRuleArea() and z.IsOnLayer(cu):
                sh = z.GetFilledPolysList(cu)
                for i in range(sh.OutlineCount()):
                    xs, ys = poly_xy(sh, i)
                    ax.fill(xs, ys, color=colour(z.GetNetname()), alpha=0.18)
        for t in b.GetTracks():
            if t.GetClass() == 'PCB_VIA':
                x, y = pcb.xy(t.GetPosition())
                ax.add_patch(plt.Circle((x, y), t.GetWidth(pcbnew.F_Cu) / 2e6, color=colour(t.GetNetname()), ec='k', lw=0.3))
            elif t.GetLayer() == cu:
                (x0, y0), (x1, y1) = pcb.xy(t.GetStart()), pcb.xy(t.GetEnd())
                ax.plot([x0, x1], [y0, y1], color=colour(t.GetNetname()), lw=max(0.5, t.GetWidth() / 1e6 * 18),
                        solid_capstyle='round')
            elif t.GetLayer() not in (pcbnew.F_Cu, pcbnew.B_Cu):
                (x0, y0), (x1, y1) = pcb.xy(t.GetStart()), pcb.xy(t.GetEnd())
                ax.plot([x0, x1], [y0, y1], color=colour(t.GetNetname()), lw=0.5, ls=':', alpha=0.5)
        for fp in b.GetFootprints():
            on = ('B' if fp.IsFlipped() else 'F') == side
            c = fp.GetCourtyard(crt)
            for i in range(c.OutlineCount()):
                xs, ys = poly_xy(c, i)
                ax.plot(xs + xs[:1], ys + ys[:1], color='0.3' if on else '0.85', lw=0.5)
            if not on and not fp.GetReference().startswith('H'):
                continue
            for p in fp.Pads():
                if not p.IsOnLayer(cu) and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                    continue
                sh = p.GetEffectivePolygon(cu, pcbnew.ERROR_INSIDE)
                for i in range(sh.OutlineCount()):
                    xs, ys = poly_xy(sh, i)
                    ax.fill(xs, ys, color=colour(p.GetNetname()), alpha=0.95, lw=0)
            x, y = pcb.xy(fp.GetPosition())
            ax.text(x, y, fp.GetReference(), fontsize=5.5 if not zoom else 9, ha='center', va='center',
                    color='k', weight='bold', clip_on=True)
        ax.set_aspect('equal'); ax.invert_yaxis(); ax.grid(True, lw=0.2)
        x0, y0, x1, y1 = poly.bounds
        if zoom:
            ax.set_xlim(zoom[0], zoom[2]); ax.set_ylim(zoom[3], zoom[1])
        else:
            ax.set_xlim(x0 - 1, x1 + 1); ax.set_ylim(y1 + 1, y0 - 1)
        ax.set_title('%s  (%s side, seen from behind F)' % (board, side))
    plt.tight_layout(); plt.savefig(out, dpi=100)


if __name__ == '__main__':
    a = sys.argv[1:]
    zoom = None
    if '--zoom' in a:
        i = a.index('--zoom'); zoom = [float(v) for v in a[i + 1:i + 5]]; del a[i:i + 5]
    main(a[0], a[1], a[2], zoom)
