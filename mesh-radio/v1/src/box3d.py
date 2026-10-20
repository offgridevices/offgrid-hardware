# -*- coding: utf-8 -*-
"""Plain box 3D models (gzip STEP, .stpZ) for the few parts that have no
maker or KiCad model: the body's outline and height from the data sheet,
nothing more.  For renders and the enclosure STEP, not for the fab.

    python3 src/box3d.py        writes the boxes in BOXES to ../og.3dshapes
"""
import gzip, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, '..', 'og.3dshapes'))

# name: (x, y, height) mm, centred on the footprint origin, sitting on the board
BOXES = {
    # Coilcraft 0908SQ air-core inductor: coil length 1.473 (x, the coil
    # axis), width 2.134, height 1.829 mm (Coilcraft 0908SQ data sheet, as
    # in footprints.coilcraft_0908sq_fp)
    'BOX_Coilcraft_0908SQ': (1.473, 2.134, 1.829),
    # Toshiba SSM10N954L, TCSPED-302701 chip-scale package: about
    # 3.0 x 1.7 mm, 0.11 mm thick (approximate: the lands span 2.82 x 1.26)
    'BOX_TCSPED-302701': (2.98, 1.68, 0.11),
}


def step_box(name, x, y, h):
    """An AP214 STEP file of one box, x by y by h, base centred at the origin."""
    e = []

    def add(s):
        e.append(s)
        return '#%d' % len(e)

    X0, X1, Y0, Y1 = -x / 2, x / 2, -y / 2, y / 2
    corners = [(X0, Y0, 0), (X1, Y0, 0), (X1, Y1, 0), (X0, Y1, 0),
               (X0, Y0, h), (X1, Y0, h), (X1, Y1, h), (X0, Y1, h)]
    pt = lambda p: add("CARTESIAN_POINT('',(%.4f,%.4f,%.4f))" % p)
    dr = lambda d: add("DIRECTION('',(%.1f,%.1f,%.1f))" % d)
    V = [add("VERTEX_POINT('',%s)" % pt(c)) for c in corners]
    edges = {}

    def edge(i, j):
        if (i, j) in edges:
            return edges[(i, j)], '.T.'
        if (j, i) in edges:
            return edges[(j, i)], '.F.'
        a, b = corners[i], corners[j]
        d = tuple(b[k] - a[k] for k in range(3))
        n = max(abs(v) for v in d)
        line = add("LINE('',%s,%s)" % (pt(a), add("VECTOR('',%s,%.4f)" % (dr(tuple(v / n for v in d)), n))))
        ec = add("EDGE_CURVE('',%s,%s,%s,.T.)" % (V[i], V[j], line))
        edges[(i, j)] = ec
        return ec, '.T.'

    # each face: its corner loop counter-clockwise seen from outside, and its outward normal
    faces = [((0, 3, 2, 1), (0, 0, -1)), ((4, 5, 6, 7), (0, 0, 1)), ((0, 1, 5, 4), (0, -1, 0)),
             ((1, 2, 6, 5), (1, 0, 0)), ((2, 3, 7, 6), (0, 1, 0)), ((3, 0, 4, 7), (-1, 0, 0))]
    F = []
    for loop, nrm in faces:
        oes = []
        for k in range(4):
            ec, sense = edge(loop[k], loop[(k + 1) % 4])
            oes.append(add("ORIENTED_EDGE('',*,*,%s,%s)" % (ec, sense)))
        el = add("EDGE_LOOP('',(%s))" % ','.join(oes))
        fb = add("FACE_OUTER_BOUND('',%s,.T.)" % el)
        ref = (1, 0, 0) if nrm[0] == 0 else (0, 1, 0)
        ax = add("AXIS2_PLACEMENT_3D('',%s,%s,%s)" % (pt(corners[loop[0]]), dr(nrm), dr(ref)))
        F.append(add("ADVANCED_FACE('',(%s),%s,.T.)" % (fb, add("PLANE('',%s)" % ax))))
    shell = add("CLOSED_SHELL('',(%s))" % ','.join(F))
    solid = add("MANIFOLD_SOLID_BREP('%s',%s)" % (name, shell))
    origin = add("AXIS2_PLACEMENT_3D('',%s,%s,%s)" % (pt((0, 0, 0)), dr((0, 0, 1)), dr((1, 0, 0))))
    unc = add("UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-07),#LEN,'distance_accuracy_value','')")
    ln = add("(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.))")
    an = add("(NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.))")
    sa = add("(NAMED_UNIT(*)SI_UNIT($,.STERADIAN.)SOLID_ANGLE_UNIT())")
    e[int(unc[1:]) - 1] = e[int(unc[1:]) - 1].replace('#LEN', ln)
    ctx = add("(GEOMETRIC_REPRESENTATION_CONTEXT(3)GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((%s))"
              "GLOBAL_UNIT_ASSIGNED_CONTEXT((%s,%s,%s))REPRESENTATION_CONTEXT('',''))" % (unc, ln, an, sa))
    shape = add("ADVANCED_BREP_SHAPE_REPRESENTATION('%s',(%s,%s),%s)" % (name, solid, origin, ctx))
    app = add("APPLICATION_CONTEXT('automotive_design')")
    add("APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,%s)" % app)
    pc = add("PRODUCT_CONTEXT('',%s,'mechanical')" % app)
    prod = add("PRODUCT('%s','%s','',(%s))" % (name, name, pc))
    pdf = add("PRODUCT_DEFINITION_FORMATION('','',%s)" % prod)
    pdc = add("PRODUCT_DEFINITION_CONTEXT('part definition',%s,'design')" % app)
    pd = add("PRODUCT_DEFINITION('design','',%s,%s)" % (pdf, pdc))
    pds = add("PRODUCT_DEFINITION_SHAPE('','',%s)" % pd)
    add("SHAPE_DEFINITION_REPRESENTATION(%s,%s)" % (pds, shape))
    head = ("ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('box model'),'2;1');\n"
            "FILE_NAME('%s.step','2026-10-20T00:00:00',(''),(''),'box3d.py','','');\n"
            "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));\nENDSEC;\nDATA;\n" % name)
    return head + ''.join('#%d=%s;\n' % (i + 1, s) for i, s in enumerate(e)) + 'ENDSEC;\nEND-ISO-10303-21;\n'


def main():
    for name, (x, y, h) in sorted(BOXES.items()):
        # fixed gzip time, so a rebuild is byte-identical
        with open(os.path.join(OUT, name + '.stpZ'), 'wb') as f:
            with gzip.GzipFile(filename='', mode='wb', fileobj=f, mtime=0) as g:
                g.write(step_box(name, x, y, h).encode())
        print('wrote %s.stpZ (%.2f x %.2f x %.2f mm)' % (name, x, y, h))


if __name__ == '__main__':
    main()
