# -*- coding: utf-8 -*-
"""The routed board's copper, for the thermal model (run.py).

Reads mesh-radio.kicad_pcb with KiCad's pcbnew (the pinned image has it) and
returns, in board coordinates (mm, board centre at (0, 0), y down as in
KiCad and placement.json):

  raster   copper on each layer (F, In1 ... B), a 0.05 mm bitmap: every zone
           fill, track, arc, pad and via land, whatever its net
  vias     (x mm, y mm, drill m) of every via but the amplifier's paddle
           vias, and via_net: each one's net
  pa_vias  the paddle vias (count, drill), found under the QPA9510's pad 17
  t_cu, t_diel   copper and dielectric thicknesses from the board's stackup
  pa_fill  area of the top-layer fill outline that holds pad 17 (mm2), and
           the paddle's centre and half-size
  mask     B.Mask openings drawn on the board (the gap pad's bare copper)

Nothing here changes the board.  run.py bins the bitmap onto its own grid.
"""
import os
import re

import numpy as np

PX = 0.05          # mm per pixel


def _chains(ps):
    """(outline points, [hole points]) of each polygon in a SHAPE_POLY_SET, mm."""
    out = []
    for i in range(ps.OutlineCount()):
        def pts(ch):
            return np.array([(ch.CPoint(j).x, ch.CPoint(j).y) for j in range(ch.PointCount())], float) / 1e6
        out.append((pts(ps.Outline(i)), [pts(ps.Hole(i, k)) for k in range(ps.HoleCount(i))]))
    return out


def stackup(path):
    """(copper thicknesses m, dielectric thicknesses m) in stack order, from the file."""
    s = open(path).read()
    blk = re.search(r'\(stackup(.*?)\(copper_finish', s, re.S).group(1)
    t_cu, t_d = [], []
    for m in re.finditer(r'\(layer "([^"]+)"\s*\(type "([^"]+)"\)(.*?)\n\t\t\t\)', blk, re.S):
        name, typ, body = m.groups()
        th = re.search(r'\(thickness ([0-9.]+)\)', body)
        if typ == 'copper':
            t_cu.append(float(th.group(1)) * 1e-3)
        elif typ in ('prepreg', 'core'):
            t_d.append(float(th.group(1)) * 1e-3)
    return t_cu, t_d


def read(path, length, width, cx=100.0, cy=100.0, pa_ref=None):
    import pcbnew
    from PIL import Image, ImageDraw
    b = pcbnew.LoadBoard(path)
    n = b.GetCopperLayerCount()
    names = ['F.Cu'] + ['In%d.Cu' % i for i in range(1, n - 1)] + ['B.Cu']
    ids = [b.GetLayerID(nm) for nm in names]
    x0, y0 = -length / 2, -width / 2
    nxp, nyp = int(round(length / PX)), int(round(width / PX))
    ras = np.zeros((n, nyp, nxp), np.uint8)

    def paint(layer_i, ps):
        for outline, holes in _chains(ps):
            if len(outline) < 3:
                continue
            u = (outline[:, 0] - cx - x0) / PX
            v = (outline[:, 1] - cy - y0) / PX
            i0, i1 = max(int(np.floor(u.min())) - 1, 0), min(int(np.ceil(u.max())) + 1, nxp)
            j0, j1 = max(int(np.floor(v.min())) - 1, 0), min(int(np.ceil(v.max())) + 1, nyp)
            if i1 <= i0 or j1 <= j0:
                continue
            im = Image.new('L', (i1 - i0, j1 - j0), 0)
            d = ImageDraw.Draw(im)
            d.polygon(list(zip(u - i0, v - j0)), fill=1)
            for h in holes:
                if len(h) >= 3:
                    d.polygon(list(zip((h[:, 0] - cx - x0) / PX - i0, (h[:, 1] - cy - y0) / PX - j0)), fill=0)
            ras[layer_i, j0:j1, i0:i1] |= np.asarray(im, np.uint8)

    for z in b.Zones():
        if z.GetIsRuleArea() or not z.IsFilled():
            continue
        for k, lid in enumerate(ids):
            if z.IsOnLayer(lid):
                paint(k, z.GetFilledPolysList(lid))
    maxerr = pcbnew.FromMM(0.005)
    for t in b.GetTracks():
        for k, lid in enumerate(ids):
            if t.IsOnLayer(lid):
                ps = pcbnew.SHAPE_POLY_SET()
                t.TransformShapeToPolygon(ps, lid, 0, maxerr, pcbnew.ERROR_INSIDE)
                paint(k, ps)
    for fp in b.GetFootprints():
        for p in fp.Pads():
            for k, lid in enumerate(ids):
                if p.IsOnLayer(lid) and p.FlashLayer(lid):
                    ps = pcbnew.SHAPE_POLY_SET()
                    p.TransformShapeToPolygon(ps, lid, 0, maxerr, pcbnew.ERROR_INSIDE)
                    paint(k, ps)

    # the amplifier's paddle and the vias in it
    pa = None
    if pa_ref:
        f = b.FindFootprintByReference(pa_ref)
        pa = [p for p in f.Pads() if p.GetNumber() == '17'][0]
    vias, vnet, pav = [], [], []
    for t in b.GetTracks():
        if t.GetClass() != 'PCB_VIA':
            continue
        if t.GetViaType() != pcbnew.VIATYPE_THROUGH:
            raise ValueError('board_copper: only through vias are modelled (%s)' % t.m_Uuid.AsString())
        x, y = t.GetPosition().x / 1e6 - cx, t.GetPosition().y / 1e6 - cy
        dr = t.GetDrillValue() * 1e-9
        if pa is not None and pa.HitTest(t.GetPosition()):
            pav.append(dr)
        else:
            vias.append((x, y, dr))
            vnet.append(t.GetNetname())
    res = dict(raster=ras, px=PX, x0=x0, y0=y0, layers=names, vias=np.array(vias), via_net=np.array(vnet),
               file=os.path.abspath(path))
    res['t_cu'], res['t_diel'] = stackup(path)
    if pa is not None:
        res['pa_vias'] = (len(pav), float(np.mean(pav)) if pav else 0.0)
        c = pa.GetPosition()
        area = 0.0
        for z in b.Zones():
            if not z.GetIsRuleArea() and z.IsOnLayer(pcbnew.F_Cu) and z.GetNetname() == pa.GetNetname():
                ps = z.GetFilledPolysList(pcbnew.F_Cu)
                for i in range(ps.OutlineCount()):
                    if ps.Outline(i).PointInside(c):
                        area = abs(ps.Outline(i).Area()) / 1e12
        # (the fill outline's area says whether the paddle joins the top pour
        # at all; how wide the joint is was read off a render: README)
        hx = pa.GetSize().x / 2e6
        px_, py_ = c.x / 1e6 - cx, c.y / 1e6 - cy
        res['pa_fill'] = (area, px_, py_, hx)
    mask = []
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.B_Mask:
            bb = d.GetBoundingBox()
            mask.append((bb.GetX() / 1e6 - cx, bb.GetY() / 1e6 - cy, bb.GetRight() / 1e6 - cx, bb.GetBottom() / 1e6 - cy))
    res['mask_B'] = mask
    return res


def coverage_in(res, layer, box):
    """Copper fraction of one layer inside (x0, y0, x1, y1) mm."""
    r = res['raster'][layer]
    px, x0, y0 = res['px'], res['x0'], res['y0']
    i0, i1 = int(round((box[0] - x0) / px)), int(round((box[2] - x0) / px))
    j0, j1 = int(round((box[1] - y0) / px)), int(round((box[3] - y0) / px))
    return float(r[max(j0, 0):j1, max(i0, 0):i1].mean())
