"""Remove the routers' dangling stubs from the finished board, one at a time,
keeping each removal only if DRC stays as clean (no new error, no new
unconnected item).

    python3 dedangle.py          ../smokebreak.kicad_pcb, in place

Run it last, after polish.py.  A stub that is really a join (a track that
overruns the one it meets, so KiCad calls its end free) cannot be removed
this way: the script says so, and it is trimmed to the crossing by hand."""
import json
import os
import shutil
import subprocess

import pcbnew

import board as B
import make

WORK = os.path.join(B.HERE, 'out', 'dedangle')


def drc(path):
    out = os.path.join(WORK, 'drc.json')
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--severity-all', '--format', 'json', '-o', out,
                    path], capture_output=True)
    return json.load(open(out))


def main():
    os.makedirs(WORK, exist_ok=True)
    try_pcb = os.path.join(WORK, 'try.kicad_pcb')
    for rnd in range(40):
        r = drc(make.OUT)
        unc = len(r['unconnected_items'])
        errs = len([v for v in r['violations'] if v['severity'] == 'error'])
        dang = [i['uuid'] for v in r['violations'] if v['type'] in ('track_dangling', 'via_dangling')
                for i in v['items']]
        print('round %d: %d errors, %d dangling, %d unconnected' % (rnd, errs, len(dang), unc), flush=True)
        if not dang:
            return
        for u in dang:
            b = pcbnew.LoadBoard(make.OUT)
            for t in list(b.GetTracks()):
                if t.m_Uuid.AsString() == u:
                    B.remove(b, t)
            pcbnew.ZONE_FILLER(b).Fill(b.Zones())
            pcbnew.SaveBoard(try_pcb, b)
            for ext in ('.kicad_pro', '.kicad_dru'):
                shutil.copy(os.path.splitext(make.OUT)[0] + ext, os.path.splitext(try_pcb)[0] + ext)
            rt = drc(try_pcb)
            if len(rt['unconnected_items']) <= unc and \
                    len([v for v in rt['violations'] if v['severity'] == 'error']) <= errs:
                shutil.copy(try_pcb, make.OUT)
                B.set_stackup(make.OUT, inner_oz=1.0)
                break
        else:
            print('the rest are joins, not stubs: trim them by hand')
            return


if __name__ == '__main__':
    main()
