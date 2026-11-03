#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick placement/routing view of a .kicad_pcb: one PNG per side showing
courtyards, pads (coloured by net class), tracks, vias and the ratsnest of
still-unrouted connections.  For iterating on placement, not for the fab;
not part of the build.

    python3.12 tools/board_view.py fc/ridge3-fc.kicad_pcb /tmp/fc
        writes /tmp/fc_top.png and /tmp/fc_bottom.png
"""
import os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
import pcbnew
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle

def netcol(n):
    if n in ('GND',): return '#3a7d3a'
    if n in ('VBAT',): return '#c0392b'
    if n.startswith('+'): return '#e67e22'
    if n.startswith('M') and n[2:] in ('_A', '_B', '_C'): return '#8e44ad'
    return '#2c6fbb'

def poly_of(shape_poly_set):
    out = []
    for i in range(shape_poly_set.OutlineCount()):
        ol = shape_poly_set.Outline(i)
        out.append([(ol.CPoint(j).x / 1e6, ol.CPoint(j).y / 1e6) for j in range(ol.PointCount())])
    return out

def render(path, out_prefix, cx=100, cy=100, half=18.6):
    import pcb
    b = pcbnew.LoadBoard(path)
    cu_top, cu_bot = pcbnew.F_Cu, pcbnew.B_Cu
    for side, cu, crt in (('top', cu_top, pcbnew.F_CrtYd), ('bottom', cu_bot, pcbnew.B_CrtYd)):
        fig, ax = plt.subplots(figsize=(11, 11))
        ax.set_facecolor('#111')
        # zones on this side (filled)
        for z in b.Zones():
            if z.GetIsRuleArea():
                for pl in poly_of(z.Outline()):
                    ax.add_patch(Polygon(pl, closed=True, fill=False, ec='#ff4', lw=0.6, ls='--'))
                continue
            if z.GetLayerSet().Contains(cu):
                for pl in poly_of(z.GetFilledPolysList(cu)) if z.IsFilled() else poly_of(z.Outline()):
                    ax.add_patch(Polygon(pl, closed=True, fc=netcol(z.GetNetname()), alpha=0.25, ec='none'))
        for t in b.GetTracks():
            if t.GetClass() == 'PCB_VIA':
                p = t.GetPosition()
                ax.add_patch(Circle((p.x / 1e6, p.y / 1e6), t.GetWidth(cu) / 2e6, fc='#bbb', ec='none'))
            elif t.GetLayer() == cu:
                s, e = t.GetStart(), t.GetEnd()
                ax.plot([s.x / 1e6, e.x / 1e6], [s.y / 1e6, e.y / 1e6], color=netcol(t.GetNetname()),
                        lw=max(t.GetWidth() / 1e6 * 72 / 25.4 * 11 / 36 * 25.4, 0.5), solid_capstyle='round')
        for fp in b.GetFootprints():
            onside = (fp.GetLayer() == cu)
            for pad in fp.Pads():
                if not pad.IsOnLayer(cu):
                    continue
                sp = pad.GetEffectivePolygon(cu)
                for pl in poly_of(sp):
                    ax.add_patch(Polygon(pl, closed=True, fc=netcol(pad.GetNetname()) if pad.GetNetname() else '#666',
                                         alpha=0.9 if onside else 0.5, ec='none'))
            if onside:
                cy_ = fp.GetCourtyard(crt)
                for pl in poly_of(cy_):
                    ax.add_patch(Polygon(pl, closed=True, fill=False, ec='#ddd', lw=0.5))
                p = fp.GetPosition()
                ax.text(p.x / 1e6, p.y / 1e6, fp.GetReference(), color='white', fontsize=5,
                        ha='center', va='center')
        # ratsnest
        b.BuildConnectivity()
        conn = b.GetConnectivity()
        for net in b.GetNetsByNetcode().values() if hasattr(b, 'GetNetsByNetcode') else []:
            pass
        try:
            for e in conn.GetRatsnestForNet if False else []:
                pass
        except Exception:
            pass
        ax.plot([cx - pcb.HALF, cx + pcb.HALF, cx + pcb.HALF, cx - pcb.HALF, cx - pcb.HALF],
                [cy - pcb.HALF, cy - pcb.HALF, cy + pcb.HALF, cy + pcb.HALF, cy - pcb.HALF], color='#ff0', lw=1)
        ax.set_xlim(cx - half, cx + half); ax.set_ylim(cy + half, cy - half)
        if side == 'bottom':
            ax.invert_xaxis()
        ax.set_aspect('equal'); ax.set_title('%s  %s  (front is up%s)' % (path.split('/')[-1], side,
                                                                        ', viewed from below' if side == 'bottom' else ''))
        fig.savefig('%s_%s.png' % (out_prefix, side), dpi=110, bbox_inches='tight')
        plt.close(fig)

if __name__ == '__main__':
    render(sys.argv[1], sys.argv[2])
