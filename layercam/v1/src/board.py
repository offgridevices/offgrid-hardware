# -*- coding: utf-8 -*-
"""Build a placed, unrouted board: outline, parts, net classes, planes and
keepouts.  Routing (route.py), the fills and the artwork come after, in
pipeline.py.

    python3 board.py main|ring|usb OUT.kicad_pcb

Main board layers (JLCPCB 6-layer, JLC06161H-3313):
    F.Cu    the back face: SoC, flash, power stage; signals
    In1.Cu  ground plane, unbroken
    In2.Cu  signals (the long runs round the window), ground fill
    In3.Cu  power planes: 0.9 V under the SoC, 3.3 V, 1.8 V, DDR, 5 V
    In4.Cu  ground plane, unbroken
    B.Cu    the front face: Wi-Fi, connectors, SoC decoupling; signals
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew
import pcb, circuit, placer, geometry as G

# net classes: width for the current each carries
POWER = {
    'main': {'VSYS': 0.5, 'VDD_0V9': 0.5, 'SW_0V9': 0.5, 'VCC_3V3': 0.4, 'LX_3V3': 0.4, 'VCC_DDR': 0.4,
             'LX_DDR': 0.4, 'VCC_1V8': 0.3, 'LX_1V8': 0.3, 'VWIFI': 0.5, 'SW_WIFI': 0.5, 'WIFI_LX': 0.4,
             'WIFI_VLDO': 0.4, 'LED_K': 0.4, 'IRCUT_1': 0.3, 'IRCUT_2': 0.3},
    'ring': {'VSYS': 0.4, 'LED_K': 0.4, 'STR1_A': 0.3, 'STR2_A': 0.3, 'STR3_A': 0.3,
             'STR1_M': 0.3, 'STR2_M': 0.3, 'STR3_M': 0.3},
    'usb': {'VSYS': 0.4},
}
PLANE_NETS = {'main': ('GND', 'VDD_0V9', 'VCC_3V3'), 'usb': ('GND',), 'ring': ()}
# differential pairs (width, gap) for 100 ohm (MIPI) and 90 ohm (USB) on
# the outer layers over the 0.1 mm prepreg, centred in the etch tolerance
# (sim/impedance.md: 98.8 and 92.7 ohm on the main board, 91 ohm on the
# 2-layer USB board)
DIFF = {'main': {'MIPI': (['CSI_D0P', 'CSI_D0N', 'CSI_D1P', 'CSI_D1N', 'CSI_CKP', 'CSI_CKN'], 0.12, 0.15),
                 'USB': (['USB_DP', 'USB_DM'], 0.14, 0.15)},
        'ring': {}, 'usb': {'USB': (['USB_DP', 'USB_DM'], 0.25, 0.13)}}


def build(board, path, rounds=6):
    """Build the board; a small part that ends up with a plane pad and no
    room for its via is moved: the board is built again with that spot
    barred to it (placer.place's `avoid`), up to `rounds` times."""
    avoid = {}
    for k in range(rounds):
        b, failed, stuck = _build(board, path, avoid)
        if not stuck:
            break
        print('  no via room for %s: placing again' % ' '.join(sorted(stuck)))
        for ref in stuck:
            fp = b.FindFootprintByReference(ref)
            avoid.setdefault(ref, []).append(placer.courtyard(fp, 'B' if fp.IsFlipped() else 'F'))
    return b, failed


def _build(board, path, avoid):
    pcbnew.KIID.SeedGenerator({'main': 11, 'ring': 12, 'usb': 13}[board])
    pcb.configure(board)
    layout = __import__('layout_' + board)
    b = pcb.new_board(path)
    pcb.outline(b)
    comps = circuit.build(board)
    fixed = layout.FIXED
    pl = {c.ref: fixed.get(c.ref, (0.0, 0.0, 0, 'F')) for c in comps}
    pcb.place_components(b, comps, pl)
    if hasattr(layout, 'zones'):
        layout.zones(b)
    # copper drawn first (pairs, the USB board's VBUS), then the fixed
    # parts' plane vias, then the small parts round them, then theirs
    import power
    manual = power.draw(b)
    nets = PLANE_NETS[board]
    allowed = layout.plane_polys() if hasattr(layout, 'plane_polys') else None
    inward = getattr(layout, 'INWARD', ())
    small = {c.ref for c in comps if placer.is_small(c) and c.ref not in fixed}
    big = {c.ref for c in comps} - small
    d1, f1 = power.fanout(b, nets=nets, done_pads=manual, allowed=allowed, inward=inward, refs=big)
    failed = placer.place(b, comps, layout, layout.height, avoid)
    if failed:
        print('  NO ROOM for: %s' % ' '.join(failed))
    d2, f2 = power.fanout(b, nets=nets, done_pads=manual, allowed=allowed, inward=inward, refs=small)
    print('  plane vias: %d%s' % (d1 + d2, ('; NO SPOT for ' + ' '.join(f1 + f2)) if f1 + f2 else ''))
    for w in sorted(set(POWER[board].values())):
        group = [n for n, x in POWER[board].items() if x == w]
        pcb.netclass(b, ('Power_%g' % w).replace('.', '_'), group, w)
    for name, (nets, w, gap) in DIFF[board].items():
        pcb.netclass(b, name, nets, w, diff_w=w, diff_gap=gap)
    pcb.rule_area_shape(b, pcb.edge_band(), pcb.cu_layers(), name='edge clearance')
    pcbnew.SaveBoard(path, b)
    pcb.write_rules(path)
    stuck = {f.split('.')[0] for f in f2} & small
    return b, failed, stuck


if __name__ == '__main__':
    bd = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else '/tmp/layercam-%s-placed.kicad_pcb' % bd
    build(bd, out)
    print('wrote', out)
