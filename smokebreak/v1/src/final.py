"""SmokeBreak v1: from the routed board to the finished one.

    python3 final.py ROUTED.kicad_pcb        -> ../smokebreak.kicad_pcb (+ DRC report)

  * ground fill on every signal layer (lowest priority, after routing so the
    router never saw it), tied in with stitching where it is cut off
  * the routers' neck-down slivers widened to the fab minimum
  * the silkscreen art (make.add_art): the words, the arrows and the lockup
  * stackup (6 layers, black mask, white silk, ENIG), DRC rules
  * KiCad DRC: errors and unconnected items are printed; the board is still
    written so it can be looked at
"""
import json
import os
import shutil
import subprocess
import sys

import pcbnew

import board as B
import make

MIN_TRACK = 0.1


def ground_fill(b):
    full = B.board_poly(0.5)
    for layer in (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu):
        z = B.zone(b, 'GND', layer, full, clearance=0.25, min_width=0.25, priority=0, name='GND fill')
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)      # SMD pads solid, hand-soldered pins relieved


def widen(b):
    n = 0
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_TRACK' and t.GetWidth() < pcbnew.FromMM(MIN_TRACK):
            t.SetWidth(pcbnew.FromMM(MIN_TRACK))
            n += 1
    return n


def drc(path):
    out = os.path.join(os.path.dirname(os.path.abspath(path)), 'src', 'out', 'drc-final.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--save-board', '--severity-all', '--format', 'json',
                    '-o', out, path], capture_output=True)
    r = json.load(open(out))
    errs = [v for v in r['violations'] if v['severity'] == 'error']
    warns = [v for v in r['violations'] if v['severity'] != 'error']
    return errs, warns, r['unconnected_items']


if __name__ == '__main__':
    src = sys.argv[1]
    b = pcbnew.LoadBoard(src)
    print('widened', widen(b), 'slivers')
    # each FET's three source pins strapped together, then the SRC net
    # (driver sense pin, BST cap, the source copper) joined by the maze router
    for ref in ('Q1', 'Q2'):
        fp = b.FindFootprintByReference(ref)
        src = sorted((p.GetPosition() for p in fp.Pads() if p.GetNetname() == 'SRC'), key=lambda q: (q.x, q.y))
        for a_, c_ in zip(src, src[1:]):
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(a_); t.SetEnd(c_); t.SetWidth(pcbnew.FromMM(0.6)); t.SetLayer(pcbnew.F_Cu)
            t.SetNet(b.FindNet('SRC')); b.Add(t)
    import finish, finish_run
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    widths, clmap = finish_run.rules()
    for net in ('SRC', 'GND', 'VIN', 'VOUT'):
        left = finish.route_net(b, net, track_w=widths.get(net, B.TRACK), clmap=clmap)
        print('  joined', net, '- islands left', left)
    ground_fill(b)
    # the routing keep-outs become DRC rules (a rule area would bar the power
    # nets' own tracks too)
    for z in list(b.Zones()):
        if z.GetIsRuleArea() and z.GetZoneName().startswith('keepout '):
            B.remove(b, z)
    placed = make.add_art(b, os.path.join(B.HERE, 'out'))
    for p in placed:
        print('  art', p)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(make.OUT, b)
    B.set_stackup(make.OUT)
    extra = ''.join('(rule "no other track across the %s copper"\n'
                    '  (condition "A.Type == \'Track\' && A.NetName != \'%s\' && A.intersectsArea(\'%s\')")\n'
                    '  (constraint disallow track))\n' % (zn, net, zn)
                    for zn, net in (('sources', 'SRC'), ('Q1 drain', 'VIN'), ('battery minus', 'BATT_NEG')))
    # the drone-negative strip also hosts C14's and the snubber's short VOUT stubs
    extra += ('(rule "no other track across the drone negative copper"\n'
              '  (condition "A.Type == \'Track\' && A.NetName != \'DRONE_NEG\' && A.NetName != \'VOUT\' '
              '&& A.NetName != \'VOUT_SNUB\' && A.intersectsArea(\'drone negative\')")\n'
              '  (constraint disallow track))\n')
    B.write_rules(make.OUT, extra)
    errs, warns, unc = drc(make.OUT)
    import collections
    print('DRC errors', len(errs), collections.Counter(v['type'] for v in errs))
    print('DRC warnings', len(warns), collections.Counter(v['type'] for v in warns))
    print('unconnected', len(unc))
