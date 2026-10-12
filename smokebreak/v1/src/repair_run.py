"""Clean a finished board and route what is still open:
remove items DRC finds shorting or dangling, then the finisher again.
python3 repair_run.py IN.kicad_pcb OUT.kicad_pcb"""
import json
import os
import shutil
import subprocess
import sys

import pcbnew

import board as B
import finish_run


def drc(path, out):
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--severity-all', '--format', 'json', '-o', out, path],
                   capture_output=True)
    return json.load(open(out))


def clean(src, dst):
    r = drc(src, dst + '.json')
    bad = set()
    for v in r['violations']:
        if v['type'] in ('shorting_items', 'clearance', 'tracks_crossing', 'copper_edge_clearance',
                         'items_not_allowed'):
            for it in v['items']:
                if it['description'].startswith(('Via', 'Track')):
                    bad.add(it['uuid'])
                    break                     # one of the two is enough
        if v['type'] in ('track_dangling', 'via_dangling'):
            bad.update(it['uuid'] for it in v['items'])
    b = pcbnew.LoadBoard(src)
    n = 0
    for t in list(b.GetTracks()):
        if t.m_Uuid.AsString() in bad and not t.IsLocked():
            B.remove(b, t)
            n += 1
    b.Save(dst)
    finish_run.copy_project(src, dst)
    return n


if __name__ == '__main__':
    src, out = sys.argv[1], sys.argv[2]
    tmp = os.path.splitext(out)[0] + '_clean.kicad_pcb'
    print('removed', clean(src, tmp), 'shorting / dangling items')
    finish_run.run(tmp, out)
