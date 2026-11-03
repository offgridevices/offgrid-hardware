"""Simple dimensioned VRML models for parts KiCad 10.0.6 ships no 3D model
for (renders only; not for mechanical checks). Sizes from the datasheets:
  SCD41   10.1 x 10.1 x 6.5 mm module
  SGP40   2.44 x 2.44 x 0.85 mm DFN, 0.8 mm opening
  SHT40   1.5 x 1.5 x 0.5 mm DFN
  CMT-8504 8.5 x 8.5 x 4.0 mm, 2.0 mm sound port
  JST S2B-PH-SM4-TB  side-entry housing, ~7.9 x 7.5 x 4.75 mm
VRML units are 0.1 inch; footprint y points down, VRML y up."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), 'canary.3dshapes')
K = 1 / 2.54


def _mat(c, shin=0.3):
    return ('appearance Appearance { material Material { diffuseColor %.3f %.3f %.3f '
            'specularColor 0.3 0.3 0.3 shininess %.2f } }' % (c[0], c[1], c[2], shin))


def box(x, y, z0, sx, sy, sz, c, shin=0.3):
    """centre x,y (footprint frame, mm), bottom z0, size; returns VRML node"""
    return ('Transform { translation %.4f %.4f %.4f children Shape { %s geometry Box { size %.4f %.4f %.4f } } }\n'
            % (x * K, -y * K, (z0 + sz / 2) * K, _mat(c, shin), sx * K, sy * K, sz * K))


def cyl(x, y, z0, r, h, c, shin=0.3):
    return ('Transform { translation %.4f %.4f %.4f rotation 1 0 0 1.5708 children Shape { %s '
            'geometry Cylinder { radius %.4f height %.4f } } }\n'
            % (x * K, -y * K, (z0 + h / 2) * K, _mat(c, shin), r * K, h * K))


BLACK, GREY, WHITE = (0.08, 0.08, 0.09), (0.55, 0.56, 0.58), (0.92, 0.92, 0.9)
TIN, GOLD, CREAM = (0.78, 0.78, 0.8), (0.85, 0.68, 0.25), (0.93, 0.9, 0.8)


def write(name, nodes):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name + '.wrl'), 'w') as f:
        f.write('#VRML V2.0 utf8\n' + ''.join(nodes))


def main():
    # SCD41: green module PCB, light housing, dark membrane window
    write('SCD41', [box(0, 0, 0, 10.1, 10.1, 0.8, (0.05, 0.25, 0.12)),
                    box(0, 0, 0.8, 9.2, 9.2, 5.7, (0.86, 0.86, 0.84), 0.5),
                    cyl(0, 0, 6.5, 1.6, 0.02, BLACK),
                    box(-3.2, -3.2, 6.5, 1.0, 1.0, 0.02, GOLD)])
    write('SGP40', [box(0, 0, 0, 2.44, 2.44, 0.85, BLACK), cyl(0.5, 0.5, 0.85, 0.4, 0.02, TIN, 0.8),
                    cyl(-0.85, -0.85, 0.85, 0.12, 0.02, WHITE)])
    write('SHT40', [box(0, 0, 0, 1.5, 1.5, 0.5, GREY), box(0, 0, 0.5, 0.7, 0.7, 0.02, BLACK)])
    write('CMT8504', [box(0, 0, 0, 8.5, 8.5, 4.0, BLACK, 0.2), cyl(0, 0, 4.0, 1.0, 0.02, (0.25, 0.25, 0.25)),
                      cyl(0, 0, 4.0, 1.6, 0.01, (0.15, 0.15, 0.15))]
          + [box(sx * 3.5, sy * 3.5, 0, 2.4, 2.4, 0.3, TIN, 0.8) for sx in (-1, 1) for sy in (-1, 1)])
    # JST PH side entry: housing towards +y (board edge), mouth on the front
    write('JST_PH_S2B_SM4', [box(0, 0.6, 0, 7.9, 7.6, 4.75, CREAM),
                             box(0, 4.42, 0.9, 5.4, 0.04, 3.0, (0.15, 0.13, 0.1)),
                             box(-3.35, 2.9, 0, 1.4, 3.2, 0.5, TIN, 0.8), box(3.35, 2.9, 0, 1.4, 3.2, 0.5, TIN, 0.8),
                             box(-1.0, -2.9, 0, 0.6, 2.4, 0.3, TIN, 0.8), box(1.0, -2.9, 0, 0.6, 2.4, 0.3, TIN, 0.8)])


MODELS = {'U5': 'SCD41.wrl', 'U3': 'SGP40.wrl', 'U4': 'SHT40.wrl', 'BZ1': 'CMT8504.wrl',
          'J3': 'JST_PH_S2B_SM4.wrl'}

if __name__ == '__main__':
    main()
