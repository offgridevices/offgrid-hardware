"""KiCad DRC, summarised: counts by type, then each violation not skipped.

    kd python3 src/drc_report.py board.kicad_pcb [type-to-skip ...]

The full report is written beside the board as <board>.drc.json.
"""
import json, collections, sys, subprocess

board = sys.argv[1]
report = board[:-len('.kicad_pcb')] + '.drc.json'
subprocess.run(['kicad-cli', 'pcb', 'drc', '--severity-all', '--format', 'json', '-o', report, board],
               capture_output=True)
d = json.load(open(report))
v = d['violations']
print(len(v), 'violations;', len(d['unconnected_items']), 'unconnected')
print(collections.Counter((x['severity'], x['type']) for x in v).most_common())
skip = set(sys.argv[2:])
for x in v:
    if x['type'] not in skip:
        print(x['type'], '|', x['description'][:70], '|', [i['description'][:55] for i in x['items']][:2])
