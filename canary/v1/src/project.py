"""Write canary.kicad_pro: KiCad 10 project settings with PCBWay's standard
2-layer limits as the DRC rules, and net classes for the supply nets.

PCBWay standard 2-layer service (pcbway.com/capabilities.html): 0.127 mm
(5 mil) track/space, 0.2 mm min drill, 0.15 mm annular ring; we design with
margin: 0.15 mm minimum, 0.2 mm default, 0.3 mm drill vias."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def write():
    d = json.load(open(os.path.join(ROOT, 'tools', 'kicad_pro_template.json')))
    d['meta']['filename'] = 'canary.kicad_pro'
    d['boards'] = []; d['sheets'] = [['da879783-92b5-536d-b757-2fef00827f80', 'Root']]
    d['text_variables'] = {}
    d['libraries'] = {'pinned_footprint_libs': [], 'pinned_symbol_libs': []}
    r = d['board']['design_settings']['rules']
    r.update({'min_clearance': 0.15, 'min_track_width': 0.15, 'min_via_diameter': 0.5,
              'min_through_hole_diameter': 0.3, 'min_via_annular_width': 0.1,
              'min_copper_edge_clearance': 0.3, 'min_hole_to_hole': 0.25,
              'min_hole_clearance': 0.25, 'min_silk_clearance': 0.0,
              'min_text_height': 0.8, 'min_resolved_spokes': 1, 'min_text_thickness': 0.15})
    ds = d['board']['design_settings']
    ds['track_widths'] = [0.0, 0.2, 0.3, 0.5, 0.8]
    ds['via_dimensions'] = [{'diameter': 0.0, 'drill': 0.0}, {'diameter': 0.6, 'drill': 0.3}]
    base = dict(d['net_settings']['classes'][0])
    default = dict(base, name='Default', clearance=0.2, track_width=0.25, via_diameter=0.6, via_drill=0.3)
    power = dict(base, name='Power', clearance=0.2, track_width=0.3, via_diameter=0.8, via_drill=0.4,
                 priority=0)
    d['net_settings']['classes'] = [default, power]
    d['net_settings']['netclass_patterns'] = [{'netclass': 'Power', 'pattern': p}
                                              for p in ('VBUS', 'GND', '+3V3', 'BUZ_D')]
    d['net_settings']['netclass_assignments'] = None
    json.dump(d, open(os.path.join(ROOT, 'canary.kicad_pro'), 'w'), indent=2)

if __name__ == '__main__':
    write()
