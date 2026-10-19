# -*- coding: utf-8 -*-
"""Build the placed, unrouted board: outline, parts, net classes, planes,
keepouts and the power copper.  Routing (route.py), the ground fills and
the artwork come after, in pipeline.py.

Layers:
    F.Cu    parts, signals, the power copper (input, switch node, ports)
    In1.Cu  ground plane, unbroken
    In2.Cu  the 5 V port rail as a plane (ground under the input stage)
    B.Cu    signals, ground fill
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew
import pcb, circuit, layout, power

F, IN1, IN2, BK = pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu

# net classes: width for the current each carries (1 oz outer copper)
POWER_NETS = {
    'VBUS_IN': 0.4, 'VRAIL': 1.0, 'BUCK_LX': 0.4,
    **{'PORT%d_SW' % n: 0.8 for n in range(1, 6)}, **{'VBUS%d' % n: 0.8 for n in range(1, 6)},
}
LOGIC_NETS = {'VLOGIC': 0.4, 'VBUS_DATA': 0.4, '+3V3': 0.4}


def build(path):
    pcbnew.KIID.SeedGenerator(7)
    b = pcb.new_board()
    pcb.outline(b)
    comps = circuit.build()
    pcb.place_components(b, comps, layout.placement(comps))
    for name, nets in (('Power', POWER_NETS), ('Logic', LOGIC_NETS)):
        for w in sorted(set(nets.values())):
            group = [n for n, x in nets.items() if x == w]
            pcb.netclass(b, ('%s_%g' % (name, w)).replace('.', '_'), group, w)
    planes(b)
    keepouts(b)
    manual = power.draw(b)
    done, failed = power.fanout(b, done_pads=manual)
    print('  fanout: %d plane vias%s' % (done, ('; NO SPOT for ' + ' '.join(failed)) if failed else ''))
    b.Save(path)
    pcb.write_rules(path)
    return b


def planes(b):
    e = 0.5
    full = pcb.rect(-pcb.HX + e, -pcb.HY + e, pcb.HX - e, pcb.HY - e)
    pcb.zone(b, 'GND', IN1, full, name='GND plane', thermal=False)
    # In2: the 5 V rail everywhere the ports and the buck output are; ground
    # behind the input stage and the logic (the back strip), so the 9 V input and
    # the USB data have ground on both sides
    pcb.zone(b, 'VRAIL', IN2, power.VRAIL_PLANE, name='5V rail plane',
             thermal=False, priority=1)
    pcb.zone(b, 'GND', IN2, full, name='GND (In2)', thermal=False, priority=0)


def keepouts(b):
    # nothing but air under and beside the ESP32's PCB antenna (Espressif:
    # no copper under the antenna, all layers)
    ex, ey = layout.ESP
    pcb.rule_area(b, pcb.rect(ex - 10.5, -pcb.HY, ex + 10.5, ey - 10.0), pcb.CU, tracks=True, vias=True,
                  pads=True, pours=True, footprints=False, name='antenna keepout')


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else '/tmp/printhub-placed.kicad_pcb'
    build(out)
    print('wrote', out)
