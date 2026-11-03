"""Project-local symbol and footprints that KiCad 10.0.6's libraries lack.

SGP40 (Sensirion datasheet v1.2, Feb 2022, section 5.3 "Land Pattern"):
6-pin DFN 2.44 x 2.44 mm, pitch 0.8 mm; pads 0.55 x 0.40 mm on 2.30 mm
centres; die pad 1.25 x 1.70 mm (stencil 1.05 x 1.50). Pins 1-3 down the
left side, 4-6 up the right (top view), die pad is ground.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def sgp40_symbol():
    def pin(num, name, typ, x, y, ang):
        return f'''			(pin {typ} line (at {x} {y} {ang}) (length 2.54)
				(name "{name}" (effects (font (size 1.27 1.27))))
				(number "{num}" (effects (font (size 1.27 1.27)))))
'''
    pins = (pin(1, 'VDD', 'power_in', 0, 10.16, 270) + pin(5, 'VDDH', 'power_in', 2.54, 10.16, 270)
            + pin(2, 'VSS', 'power_in', 0, -10.16, 90) + pin(4, 'GND', 'passive', 2.54, -10.16, 90)
            + pin(7, 'EP', 'passive', -2.54, -10.16, 90)
            + pin(3, 'SDA', 'bidirectional', -10.16, 1.27, 0) + pin(6, 'SCL', 'input', -10.16, -1.27, 0))
    return f'''(kicad_symbol_lib
	(version 20250114)
	(generator "canary_lib")
	(symbol "SGP40"
		(exclude_from_sim no) (in_bom yes) (on_board yes)
		(property "Reference" "U" (at -7.62 8.89 0) (effects (font (size 1.27 1.27)) (justify left)))
		(property "Value" "SGP40" (at 3.81 -8.89 0) (effects (font (size 1.27 1.27)) (justify left)))
		(property "Footprint" "canary:Sensirion_DFN-6_2.44x2.44mm_P0.8mm_SGP40" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
		(property "Datasheet" "https://sensirion.com/media/documents/296373BB/6203C5DF/Sensirion_Gas_Sensors_Datasheet_SGP40.pdf" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
		(property "Description" "Sensirion SGP40 MOX VOC sensor, I2C 0x59, DFN-6" (at 0 0 0) (hide yes) (effects (font (size 1.27 1.27))))
		(symbol "SGP40_0_1"
			(rectangle (start -7.62 7.62) (end 7.62 -7.62)
				(stroke (width 0.254) (type default)) (fill (type background))))
		(symbol "SGP40_1_1"
{pins}		)
	)
)
'''


def sgp40_footprint():
    pads = []
    y = [-0.8, 0.0, 0.8]
    for i, yy in enumerate(y):        # pins 1..3 left, top to bottom
        pads.append((i + 1, -1.15, yy))
    for i, yy in enumerate(reversed(y)):  # pins 4..6 right, bottom to top
        pads.append((i + 4, 1.15, yy))
    s = ['''(footprint "Sensirion_DFN-6_2.44x2.44mm_P0.8mm_SGP40"
	(version 20250114)
	(generator "canary_lib")
	(layer "F.Cu")
	(descr "Sensirion SGP40/SGP41 DFN-6, land pattern per SGP40 datasheet v1.2 fig. 14")
	(tags "Sensirion SGP40 SGP41 DFN")
	(property "Reference" "REF**" (at 0 -2.2 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))
	(property "Value" "SGP40" (at 0 2.2 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))
	(attr smd)
	(fp_line (start -1.22 -1.22) (end 1.22 -1.22) (stroke (width 0.1) (type solid)) (layer "F.Fab"))
	(fp_line (start 1.22 -1.22) (end 1.22 1.22) (stroke (width 0.1) (type solid)) (layer "F.Fab"))
	(fp_line (start 1.22 1.22) (end -1.22 1.22) (stroke (width 0.1) (type solid)) (layer "F.Fab"))
	(fp_line (start -1.22 1.22) (end -1.22 -1.22) (stroke (width 0.1) (type solid)) (layer "F.Fab"))
	(fp_circle (center 0.5 0.5) (end 0.9 0.5) (stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab"))
	(fp_line (start -0.6 -1.6) (end 0.6 -1.6) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
	(fp_line (start -0.6 1.6) (end 0.6 1.6) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))
	(fp_circle (center -1.75 -1.35) (end -1.65 -1.35) (stroke (width 0.2) (type solid)) (fill yes) (layer "F.SilkS"))
	(fp_rect (start -1.7 -1.7) (end 1.7 1.7) (stroke (width 0.05) (type solid)) (fill no) (layer "F.CrtYd"))
''']
    for n, x, yy in pads:
        s.append(f'\t(pad "{n}" smd roundrect (at {x} {yy}) (size 0.55 0.4) (layers "F.Cu" "F.Mask" "F.Paste") (roundrect_rratio 0.15))\n')
    # die pad with the pin-1 chamfer; paste reduced to the stencil aperture
    s.append('\t(pad "7" smd rect (at 0 0) (size 1.25 1.7) (layers "F.Cu" "F.Mask"))\n')
    s.append('\t(pad "" smd rect (at 0 0) (size 1.05 1.5) (layers "F.Paste"))\n')
    s.append(f'''	(model "${{KIPRJMOD}}/canary.3dshapes/SGP40.wrl" (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))
)
''')
    return ''.join(s)


def write():
    open(os.path.join(ROOT, 'canary.kicad_sym'), 'w').write(sgp40_symbol())
    d = os.path.join(ROOT, 'canary.pretty')
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'Sensirion_DFN-6_2.44x2.44mm_P0.8mm_SGP40.kicad_mod'), 'w').write(sgp40_footprint())
    open(os.path.join(ROOT, 'sym-lib-table'), 'w').write(
        '(sym_lib_table\n\t(version 7)\n\t(lib (name "canary") (type "KiCad") (uri "${KIPRJMOD}/canary.kicad_sym") (options "") (descr "Canary project parts"))\n)\n')
    open(os.path.join(ROOT, 'fp-lib-table'), 'w').write(
        '(fp_lib_table\n\t(version 7)\n\t(lib (name "canary") (type "KiCad") (uri "${KIPRJMOD}/canary.pretty") (options "") (descr "Canary project footprints"))\n)\n')


if __name__ == '__main__':
    write()
