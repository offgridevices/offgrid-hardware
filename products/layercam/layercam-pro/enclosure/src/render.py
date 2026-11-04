# -*- coding: utf-8 -*-
"""Cut-away drawings of the case (enclosure/images/*.png, 256-colour PNG).

    draw(parts, info, outdir)   -- called by case.py after a build
"""
import os

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

import case as C
import geometry as G

COL = {'front-shell': '#3d4550', 'back-shell': '#5b6572', 'lid': '#7d8794'}
PRUSA = '#c2c8cf'


def cut(mesh, origin, u, v):
    """Section of a trimesh by the plane through origin spanned by u, v:
    shapely polygons in (u, v) coordinates."""
    n = np.cross(u, v)
    s = mesh.section(plane_origin=origin, plane_normal=n)
    if s is None:
        return Polygon()
    F = np.eye(4)
    F[:3, 0], F[:3, 1], F[:3, 2], F[:3, 3] = u, v, n, origin
    p, _ = s.to_2D(to_2D=np.linalg.inv(F))
    return unary_union([q.buffer(0) for q in p.polygons_full])


def fill(ax, poly, **kw):
    geoms = poly.geoms if hasattr(poly, 'geoms') else [poly]
    for g in geoms:
        if g.is_empty:
            continue
        x, y = g.exterior.xy
        ax.fill(x, y, **kw)
        for h in g.interiors:
            hx, hy = h.xy
            ax.fill(hx, hy, color='white', lw=0)


def proj(p, origin, u, v):
    d = np.asarray(p, float) - origin
    return d @ u, d @ v


def box_poly(lo, hi, origin, u, v, n):
    """The section of an axis-aligned box by the plane (approximate: corners
    of the box's cut, via shapely on a fine grid of the plane)."""
    import trimesh
    b = trimesh.creation.box(bounds=[lo, hi])
    return cut(b, origin, u, v)


def view(ax, parts_tm, info, origin, u, v, title, extras=True):
    n = np.cross(u, v)
    for k, m in parts_tm.items():
        fill(ax, cut(m, origin, u, v), color=COL[k], lw=0, zorder=2)
    # Prusa's outside, for comparison
    for m in info['prusa'].values():
        fill(ax, cut(m, origin, u, v), color='none', ec=PRUSA, lw=0.6, zorder=3)
    if not extras:
        return
    import trimesh
    # the board
    bp = info['board']
    board = trimesh.creation.extrude_polygon(bp, G.BOARD_T)
    board.apply_translation((0, 0, G.BOARD_Z))
    fill(ax, cut(board, origin, u, v), color='#1f7a3a', lw=0, zorder=4)
    # heatsink, IR-cut holder, lens
    x0, y0, z0, x1, y1, z1 = info['sink']
    fill(ax, box_poly((x0, y0, z0), (x1, y1, z1), origin, u, v, n), color='#b7bec6', ec='#555', lw=0.6, zorder=4)
    hx0, hy0, hx1, hy1 = G.HOLDER_BOX
    fill(ax, box_poly((hx0, hy0, C.HOLDER_Z0), (hx1, hy1, G.BOARD_Z), origin, u, v, n),
         color='none', ec='#333', lw=0.8, hatch='//', zorder=4)
    lens = trimesh.creation.cylinder(radius=7.0, segment=[(0, 0, -0.6), (0, 0, C.HOLDER_Z0)])
    fill(ax, cut(lens, origin, u, v), color='#6b7c93', lw=0, zorder=4)
    # rods
    for a in G.LED_ANGLES:
        p0, p1 = C.rod_axis(a)
        rod = trimesh.creation.cylinder(radius=G.ROD_D / 2, segment=[p0, p1])
        fill(ax, cut(rod, origin, u, v), color='#e0474c', alpha=.8, lw=0, zorder=5)
        lx, ly = G.led_xy(a)
        led = trimesh.creation.box(bounds=[(lx - C.LED_SIZE / 2, ly - C.LED_SIZE / 2, G.BOARD_Z - C.LED_H),
                                           (lx + C.LED_SIZE / 2, ly + C.LED_SIZE / 2, G.BOARD_Z)])
        fill(ax, cut(led, origin, u, v), color='#222', lw=0, zorder=5)
    # USB-C receptacle
    ui = info['usb']
    o, uu, ss = ui['origin'], ui['u'], ui['s']
    rec = trimesh.creation.box(extents=(C.USB_L, C.USB_W, C.USB_H))
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2] = uu, ss, (0, 0, 1)
    M[:3, 3] = o + uu * (ui['t_mouth'] - C.USB_L / 2)
    rec.apply_transform(M)
    fill(ax, cut(rec, origin, u, v), color='#c9a227', lw=0, zorder=5)
    # RP-SMA bulkhead (a cylinder Ø6.35 through the wall, Ø8 hex outside)
    si = info['sma']
    c, nn = si['centre'], si['n']
    for a0, a1, r in ((-C.WALL - 7.0, 0.0, 3.17), (0.0, 4.0, 4.0), (-C.WALL - 2.0, -C.WALL, 4.6)):
        cy = trimesh.creation.cylinder(radius=r, segment=[c + nn * a0, c + nn * a1])
        fill(ax, cut(cy, origin, u, v), color='#d4af37', lw=0, zorder=5)
    # magnets
    for k, (c, nn) in info['magnets'].items():
        cy = trimesh.creation.cylinder(radius=C.MAG_D / 2, segment=[c - nn * C.MAG_T, c])
        fill(ax, cut(cy, origin, u, v), color='#8a2be2', lw=0, zorder=5)
    ax.set_aspect('equal')
    ax.set_title(title, fontsize=10)
    ax.tick_params(labelsize=7)


def draw(parts, info, outdir, names=('case-cutaway.png', 'case-cutaway-usb-antenna.png')):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from PIL import Image
    os.makedirs(outdir, exist_ok=True)
    tm = {k: C.to_trimesh(m) for k, m in parts.items()}
    X, Y, Z = np.eye(3)
    legend = [Patch(color=COL['front-shell'], label='front shell'), Patch(color=COL['back-shell'], label='back shell'),
              Patch(color=COL['lid'], label='lid'), Patch(color='#1f7a3a', label='board'),
              Patch(color='#e0474c', label='2 mm light rod'), Patch(color='#b7bec6', label='heatsink'),
              Patch(color='#c9a227', label='USB-C'), Patch(color='#d4af37', label='RP-SMA'),
              Patch(color='#8a2be2', label='magnet'), Patch(facecolor='none', edgecolor=PRUSA, label="Prusa's case")]

    def save(fig, name):
        tmp = os.path.join(outdir, name + '.tmp.png')
        fig.savefig(tmp, dpi=90)
        plt.close(fig)
        Image.open(tmp).convert('RGB').quantize(256).save(os.path.join(outdir, name), optimize=True)
        os.remove(tmp)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.4))
    view(axes[0], tm, info, np.zeros(3), X, Z, 'Cut through the lens, left-right (Y 0)')
    view(axes[1], tm, info, np.zeros(3), -Y, Z, 'Cut through the lens and light sensor, top-bottom (X 0)')
    for ax in axes:
        ax.set_xlim(-44, 44)
        ax.set_ylim(44, -3)
        ax.set_ylabel('Z mm from the front face')
    axes[0].set_xlabel('X mm')
    axes[1].set_xlabel('-Y mm (board y)')
    fig.legend(handles=legend, loc='lower center', ncol=10, fontsize=7, frameon=False)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    save(fig, names[0])

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.4))
    ui = info['usb']
    o, uu = ui['origin'], ui['u']
    view(axes[0], tm, info, np.array([o[0], o[1], 0.0]), -uu, Z, 'Cut along the USB-C plug axis (level, Z %.1f)' % ui['axis_z'])
    si = info['sma']
    c, nn = si['centre'], si['n']
    w = C.unit(Z - nn * (Z @ nn))
    view(axes[1], tm, info, c, -nn, w, 'Cut along the RP-SMA bulkhead axis (up = towards the lid)')
    axes[0].set_xlim(-14, 40)
    axes[0].set_ylim(44, -2)
    axes[0].set_xlabel('mm along the plug axis, inwards')
    axes[0].set_ylabel('Z mm')
    axes[1].set_xlim(-22, 22)
    axes[1].set_ylim(-16, 16)
    axes[1].set_xlabel('mm along the bulkhead axis, inwards')
    fig.legend(handles=legend, loc='lower center', ncol=10, fontsize=7, frameon=False)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    save(fig, names[1])
