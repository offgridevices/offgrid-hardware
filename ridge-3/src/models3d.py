# -*- coding: utf-8 -*-
"""Where the boards' 3D models sit, for the checks in verify.py.

KiCad converts every model (STEP, assemblies and all) for its VRML export;
the per-model files it writes hold each model's geometry in its own frame
(0.1 inch units).  Each footprint's model offset, rotation and scale, then
the footprint's side, turn and position, carry those points onto the board.
Only the outline on the board plane is kept (a box in the footprint's
frame, turned onto the board), which is what can sit over a pad.

Also refresh(): a board's footprints take their 3D models from the
footprint library again (models only; copper, pads and positions stay).
"""
import os, re, math, subprocess, tempfile
import numpy as np
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.normpath(os.path.join(HERE, '..', 'aio.pretty'))
STD_FP = '/usr/share/kicad/footprints'


def _rot(a, axis):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    if axis == 'x':
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == 'y':
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def model_points(board_path, prjmod=None):
    """{model file's base name: Nx3 points, mm, in the model's frame}.
    prjmod: the folder ${KIPRJMOD} stands for (default: the board's)."""
    d = tempfile.mkdtemp(prefix='models3d-')
    path = os.path.abspath(board_path)
    subprocess.run(['kicad-cli', 'pcb', 'export', 'vrml', '-D', 'KIPRJMOD=' + (prjmod or os.path.dirname(path)),
                    '--units', 'mm', '--models-dir', 'models', '--models-relative',
                    '-o', os.path.join(d, 'board.wrl'), path], capture_output=True, cwd=d, check=True)
    out = {}
    md = os.path.join(d, 'models')
    for f in os.listdir(md) if os.path.isdir(md) else []:
        txt = open(os.path.join(md, f)).read()
        # KiCad writes each model's shapes under identity transforms
        if re.search(r'translation (?!0 0 0\b)', txt) or re.search(r'rotation [-\d.e]+ [-\d.e]+ [-\d.e]+ (?!0\b)', txt):
            raise ValueError('%s: nested transforms in the converted model' % f)
        pts = []
        for blk in re.findall(r'point \[(.*?)\]', txt, re.S):
            v = [float(x) for x in re.split(r'[\s,]+', blk.strip()) if x]
            pts += [v[i:i + 3] for i in range(0, len(v) - 2, 3)]
        out[os.path.splitext(f)[0]] = np.array(pts) * 2.54
    return out


def z_range(fp, points):
    """Lowest and highest point of the footprint's models above its side of
    the board (mm), or None when it has no model."""
    zs = []
    for m in fp.Models():
        p = points.get(os.path.splitext(os.path.basename(m.m_Filename))[0])
        if p is None or not len(p):
            continue
        p = p * np.array([m.m_Scale.x, m.m_Scale.y, m.m_Scale.z])
        R = _rot(-m.m_Rotation.z, 'z') @ _rot(-m.m_Rotation.y, 'y') @ _rot(-m.m_Rotation.x, 'x')
        z = (p @ R.T)[:, 2] + m.m_Offset.z
        zs += [z.min(), z.max()]
    return (min(zs), max(zs)) if zs else None


def local_box(fp, points):
    """The footprint's models' outline on the board plane, as a box
    (x0, y0, x1, y1) in the footprint's own frame (mm, y down, unturned,
    top side), or None when it has no model."""
    box = None
    for m in fp.Models():
        if not m.m_Show:
            continue
        p = points.get(os.path.splitext(os.path.basename(m.m_Filename))[0])
        if p is None or not len(p):
            continue
        p = p * np.array([m.m_Scale.x, m.m_Scale.y, m.m_Scale.z])
        R = _rot(-m.m_Rotation.z, 'z') @ _rot(-m.m_Rotation.y, 'y') @ _rot(-m.m_Rotation.x, 'x')
        p = p @ R.T + np.array([m.m_Offset.x, m.m_Offset.y, m.m_Offset.z])
        xs, ys = p[:, 0], -p[:, 1]           # model y is up, the footprint's down
        b = (xs.min(), ys.min(), xs.max(), ys.max())
        box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    return box


def to_board(fp, pts):
    """Points in the footprint's own frame (mm) onto the board (mm): the
    bottom side mirrors y, then the footprint's turn, then its position."""
    a = math.radians(fp.GetOrientationDegrees())
    c, s = math.cos(a), math.sin(a)
    x0, y0 = fp.GetPosition().x / 1e6, fp.GetPosition().y / 1e6
    out = []
    for x, y in pts:
        if fp.IsFlipped():
            y = -y
        out.append((x0 + x * c + y * s, y0 - x * s + y * c))
    return out


def library_footprint(fp):
    """The footprint as the library has it: ../aio.pretty, else KiCad's own
    library it names (a board's footprints may carry no library name)."""
    import glob
    lib, name = str(fp.GetFPID().GetLibNickname()), str(fp.GetFPID().GetLibItemName())
    if lib in ('', 'aio') and os.path.exists(os.path.join(LIB, name + '.kicad_mod')):
        return pcbnew.FootprintLoad(LIB, name)
    d = os.path.join(STD_FP, lib + '.pretty') if lib not in ('', 'aio') else None
    if not d or not os.path.exists(os.path.join(d, name + '.kicad_mod')):
        hits = glob.glob(os.path.join(STD_FP, '*.pretty', name + '.kicad_mod'))
        d = os.path.dirname(hits[0]) if len(hits) == 1 else None
    return pcbnew.FootprintLoad(d, name) if d else None


def board_outlines(board_path, board=None):
    """{reference: (side, polygon on the board, local box, (lowest, highest)
    point above its side)} for every footprint with a model.  Checks the frame mapping on the pads: each
    library pad's position, carried by to_board, must land on the board's."""
    from shapely.geometry import Polygon
    b = board or pcbnew.LoadBoard(board_path)
    pts = model_points(board_path)
    out = {}
    for fp in b.GetFootprints():
        lb = local_box(fp, pts)
        if lb is None:
            continue
        lf = library_footprint(fp)
        if lf is not None:
            on = {}
            for p in fp.Pads():
                on.setdefault(p.GetNumber(), []).append((p.GetPosition().x / 1e6, p.GetPosition().y / 1e6))
            for p in lf.Pads():
                x, y = to_board(fp, [(p.GetPosition().x / 1e6, p.GetPosition().y / 1e6)])[0]
                if not any(math.hypot(x - q[0], y - q[1]) < 0.01 for q in on.get(p.GetNumber(), [])):
                    raise ValueError('%s: footprint frame does not map onto its pad %s'
                                     % (fp.GetReference(), p.GetNumber()))
        corners = [(lb[0], lb[1]), (lb[2], lb[1]), (lb[2], lb[3]), (lb[0], lb[3])]
        out[fp.GetReference()] = ('B' if fp.IsFlipped() else 'T', Polygon(to_board(fp, corners)), lb, z_range(fp, pts))
    return out


def refresh(board_path):
    """The board's footprints take their 3D models from the library again.
    Returns the references whose models changed."""
    b = pcbnew.LoadBoard(board_path)
    changed = []
    for fp in b.GetFootprints():
        lf = library_footprint(fp)
        if lf is None:
            continue
        key = lambda ms: [(m.m_Filename, round(m.m_Offset.x, 4), round(m.m_Offset.y, 4), round(m.m_Offset.z, 4),
                           round(m.m_Rotation.x, 3), round(m.m_Rotation.y, 3), round(m.m_Rotation.z, 3),
                           round(m.m_Scale.x, 4), round(m.m_Scale.y, 4), round(m.m_Scale.z, 4)) for m in ms]
        if key(fp.Models()) == key(lf.Models()):
            continue
        fp.Models().clear()
        for m in lf.Models():
            n = pcbnew.FP_3DMODEL()
            n.m_Filename, n.m_Offset, n.m_Rotation, n.m_Scale = m.m_Filename, m.m_Offset, m.m_Rotation, m.m_Scale
            n.m_Show, n.m_Opacity = m.m_Show, m.m_Opacity
            fp.Models().append(n)
        changed.append(fp.GetReference())
    if changed:
        # pcbnew's save rewrites the project file too; keep it as it was
        pro = os.path.splitext(board_path)[0] + '.kicad_pro'
        keep = open(pro).read() if os.path.exists(pro) else None
        b.Save(board_path)
        if keep is not None:
            open(pro, 'w').write(keep)
    return changed
