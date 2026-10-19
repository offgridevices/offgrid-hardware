"""The last joins on a finished routing (out/prefill.kicad_pcb, before the
fills), then `final.py --tail` seals it.

    python3 touchup.py && python3 final.py --tail

  * GATE: a via on the controller's short drop to Q1's gate, so the rest of
    GATE (Q2's gate, the pull-down) can reach it on an inner layer
  * C14's minus pad into the drone-negative copper
  * any track that shorts or crowds a pad or via is ripped, its net routed again
  * then every net still in pieces, by the maze router (fine grid, small vias)
"""
import os
import sys

import pcbnew

import board as B
import final
import finish
import finish_run
import make

PATH = os.path.join(B.HERE, 'out', 'prefill.kicad_pcb')


def offenders(path):
    """Tracks DRC calls shorting or too close (the routers' leftovers)."""
    import json
    import subprocess
    out = os.path.join(B.HERE, 'out', 'touchup-drc.json')
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--severity-error', '--format', 'json', '-o', out, path],
                   capture_output=True)
    r = json.load(open(out))
    bad = []
    for v in r['violations']:
        if v['type'] in ('shorting_items', 'clearance', 'tracks_crossing'):
            for it in v['items']:
                if it['description'].startswith('Track'):
                    bad.append((it['uuid'], it['description']))
    return bad, [u for u in r['unconnected_items']]


def main():
    finish_run.copy_project(make.OUT, PATH)
    b = pcbnew.LoadBoard(PATH)
    finish.ROUTE_LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu]
    finish.VIA_D, finish.VIA_DRILL, finish.RES = 0.45, 0.2, 0.025
    w, cl = finish_run.rules()
    u14, q14 = final.pad_xy(b, 'U1', '14'), final.pad_xy(b, 'Q1', '4')
    vy = (u14[1] + 0.72 + q14[1] - 0.3) / 2
    if not any(t.GetClass() == 'PCB_VIA' and t.GetNetname() == 'GATE' and
               abs(pcbnew.ToMM(t.GetPosition().y) - B.OY - vy) < 0.05 for t in b.GetTracks()):
        v = B.via(b, u14[0], vy, 'GATE', d=0.45, drill=0.2)
        v.SetLocked(True)
    c14 = final.pad_xy(b, 'C14', '2')
    if c14[0] < make.NEG[1][0]:
        B.track(b, [c14, (make.NEG[1][0] + 0.3, make.NEG[2][1] + 0.3)], 0.3, pcbnew.F_Cu, 'DRONE_NEG')
    b.Save(PATH)
    bad, unc = offenders(PATH)
    nets = set()
    if bad:
        b = pcbnew.LoadBoard(PATH)
        ids = {u for u, _ in bad}
        for t in list(b.GetTracks()):
            if t.m_Uuid.AsString() in ids:
                nets.add(t.GetNetname())
                B.remove(b, t)
        print('ripped', len(ids), 'tracks of', sorted(nets))
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    for net in sorted(nets | {n for n in ('GATE', 'VIN', 'DRONE_NEG')}):
        print(net, 'islands left', finish.route_net(b, net, track_w=w.get(net, 0.15), clmap=cl), flush=True)
    b.Save(PATH)
    finish_run.copy_project(make.OUT, PATH)
    bad, unc = offenders(PATH)
    print('after touch-up:', len(bad), 'crowding tracks,', len(unc), 'unconnected')
    for u in unc:
        print('  ', [(i['description'][:50]) for i in u['items']])


if __name__ == '__main__':
    main()
