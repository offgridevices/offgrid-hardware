"""Clean up a finished board without routing it all again.

    python3 polish.py            ../smokebreak.kicad_pcb -> the same, cleaner

The ground fills come off (to the maze router a fill is solid copper), the
power keep-outs go back on, every track or via KiCad's DRC flags (clearance,
short, crossing, board edge, across another net's power copper, dangling)
is removed, the open joins are routed again on the fine grid, and then the
board is filled, stitched and checked exactly as final.py does.
"""
import json
import os
import subprocess

import pcbnew

import board as B
import final
import finish
import finish_run
import make

# power copper and the nets whose own tracks may cross it
ALLOWED = {'sources': {'SRC'}, 'Q1 drain': {'VIN'}, 'battery minus': {'BATT_NEG'},
           'battery plus': {'VBAT'}, 'fuse load side': {'VIN'}, 'Q2 drain': {'VOUT'},
           'Q11 sources': {'GND'}, 'shunt GND': {'GND'},
           'drone negative': {'DRONE_NEG', 'VOUT', 'VOUT_SNUB'}}
REMOVE = ('shorting_items', 'clearance', 'tracks_crossing', 'copper_edge_clearance')
not_allowed = set()


def flagged(path):
    out = path + '.json'
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--severity-all', '--format', 'json', '-o', out,
                    path], capture_output=True)
    r = json.load(open(out))
    bad = set()
    for v in r['violations']:
        items = [i for i in v['items'] if i['description'].startswith(('Via', 'Track'))]
        if v['type'] in REMOVE and items:
            bad.add(items[0]['uuid'])
        if v['type'] in ('track_dangling', 'via_dangling'):
            bad.update(i['uuid'] for i in items)
        if v['type'] == 'items_not_allowed':
            bad.update(i['uuid'] for i in items)
            not_allowed.update(i['uuid'] for i in items)
    return bad


def main():
    b = pcbnew.LoadBoard(make.OUT)
    for z in list(b.Zones()):
        if z.GetZoneName() == 'GND fill':
            B.remove(b, z)
    make.power_keepouts(b)
    for z in list(b.Zones()):                            # the art fields as make.py has them now
        if z.GetIsRuleArea() and z.GetZoneName() in [n for n, _ in make.ART_FIELDS]:
            B.remove(b, z)
    make.art_fields(b)
    work = os.path.join(B.HERE, 'out', 'polish')
    os.makedirs(work, exist_ok=True)
    tmp = os.path.join(work, 'a.kicad_pcb')
    b.Save(tmp)
    finish_run.copy_project(make.OUT, tmp)
    bad = flagged(tmp)
    b = pcbnew.LoadBoard(tmp)
    n = 0
    for t in list(b.GetTracks()):
        if t.m_Uuid.AsString() in bad and not t.IsLocked():
            # a power net's own track over its own copper is fine (the keep-out
            # only stands in for the DRC rule while routing)
            if t.GetClass() == 'PCB_TRACK' and any(t.GetNetname() in nets for nets in ALLOWED.values()) \
                    and t.m_Uuid.AsString() in not_allowed:
                continue
            B.remove(b, t)
            n += 1
    print('removed', n, 'flagged items')
    b.Save(tmp)
    finish.ROUTE_LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu]
    finish.VIA_D, finish.VIA_DRILL = 0.45, 0.2
    finish.RES = 0.05
    out = os.path.join(work, 'b.kicad_pcb')
    finish_run.run(tmp, out)
    b = pcbnew.LoadBoard(out)
    final.hand_routes(b)
    for z in list(b.Zones()):
        if z.GetIsRuleArea() and z.GetZoneName().startswith('keepout '):
            B.remove(b, z)
    final.ground_fill(b)
    final.seal(b)


if __name__ == '__main__':
    main()
