"""Simple 3D models (VRML, KiCad's 0.1 inch units) for parts whose makers
publish none we can use: the toggle, the 2020 RGB LED, the AC05 resistor
and the TPS48000's VSSOP-19.  Dimensions from the datasheets; for renders
and the case's clearance check, not for tooling.

    python3 tools/models3d.py      writes lib/smokebreak.3dshapes/*.wrl
"""
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib', 'smokebreak.3dshapes')
U = 1 / 2.54

COL = {
    'black': (0.06, 0.06, 0.06, 0.4), 'metal': (0.78, 0.78, 0.80, 0.9), 'nickel': (0.70, 0.70, 0.72, 0.8),
    'white': (0.94, 0.94, 0.92, 0.2), 'clear': (0.95, 0.95, 0.9, 0.6), 'tin': (0.82, 0.82, 0.84, 0.9),
    'cement': (0.62, 0.66, 0.60, 0.1), 'gold': (0.85, 0.65, 0.25, 0.9),
}


def mat(c):
    r, g, b, sh = COL[c]
    return ('appearance Appearance { material Material { diffuseColor %.3f %.3f %.3f '
            'specularColor %.2f %.2f %.2f shininess %.2f } }' % (r, g, b, sh, sh, sh, sh))


def box(c, x, y, z, sx, sy, sz):
    """Box centred at (x, y) with its base at z (mm)."""
    return ('Transform { translation %.4f %.4f %.4f children [ Shape { %s geometry Box { size %.4f %.4f %.4f } } ] }'
            % (x * U, y * U, (z + sz / 2) * U, mat(c), sx * U, sy * U, sz * U))


def cyl(c, x, y, z, r, h, axis='z'):
    """Cylinder: axis z with its base at z; axis x or y centred on (x, y, z)."""
    if axis == 'z':
        rot, t = '1 0 0 1.5708', (x, y, z + h / 2)
    elif axis == 'x':
        rot, t = '0 0 1 1.5708', (x, y, z)
    else:
        rot, t = '0 0 1 0', (x, y, z)
    return ('Transform { translation %.4f %.4f %.4f rotation %s children [ Shape { %s geometry Cylinder { radius %.4f height %.4f } } ] }'
            % (t[0] * U, t[1] * U, t[2] * U, rot, mat(c), r * U, h * U))


def write(name, shapes):
    with open(os.path.join(OUT, name + '.wrl'), 'w') as f:
        f.write('#VRML V2.0 utf8\n' + '\n'.join(shapes) + '\n')


def toggle():
    # C&K 7107 PC-mount: body 12.7 x 8.1, shoulder 8.89 above the board,
    # 1/4-40 bushing, bat lever at centre (OFF).  Pins along y.
    s = [box('black', 0, 0, 0.5, 8.1, 12.7, 7.4), box('metal', 0, 0, 7.9, 8.6, 13.2, 1.0),
         cyl('metal', 0, 0, 8.89, 3.17, 6.1), cyl('nickel', 0, 0, 10.0, 4.0, 0.6)]
    for k in (-4.7, 0, 4.7):
        s.append(box('tin', 0, k, -3.0, 0.8, 0.8, 3.5))
    # bat: tapered lever, a stack of shrinking cylinders
    for i in range(10):
        s.append(cyl('metal', 0, 0, 15.0 + i * 1.1, 1.6 - i * 0.05, 1.1))
    write('SW_Toggle_CK7107', s)


def led2020():
    s = [box('white', 0, 0, 0, 2.0, 2.0, 0.6), box('clear', 0, 0, 0.6, 1.6, 1.6, 0.24),
         cyl('gold', 0, 0, 0.6, 0.35, 0.05)]
    write('LED_WS2812B-2020', s)


def ac05():
    # Vishay AC05: Ø6.5 x 17 mm cement-coated body, 22 mm pitch, leads bent down
    s = [cyl('cement', 0, 0, 3.75, 3.25, 17.0, axis='x')]
    for x in (-11.0, 11.0):
        s.append(box('tin', x, 0, -3.0, 0.8, 0.8, 6.75))
    s.append(box('tin', 0, 0, 3.35, 22.0, 0.8, 0.8))
    write('R_AC05_P22mm', s)


def vssop19():
    s = [box('black', 0, 0, 0.05, 5.1, 3.0, 1.0)]
    for i in range(10):
        x = -2.25 + 0.5 * i
        s.append(box('tin', x, 2.2, 0, 0.25, 1.4, 0.2))
        if i != 8:
            s.append(box('tin', x, -2.2, 0, 0.25, 1.4, 0.2))
    write('VSSOP-19_TPS48000', s)


if __name__ == '__main__':
    toggle(); led2020(); ac05(); vssop19()
    print('models written to', os.path.normpath(OUT))
