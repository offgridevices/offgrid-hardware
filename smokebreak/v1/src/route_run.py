"""Route the placed board into out/<tag>/ with one set of router costs:
python3 route_run.py TAG [via_costs] [passes]"""
import os
import shutil
import sys

import make
import route

tag = sys.argv[1]
via = int(sys.argv[2]) if len(sys.argv) > 2 else 50
passes = int(sys.argv[3]) if len(sys.argv) > 3 else 40
d = os.path.join('out', tag)
shutil.rmtree(d, ignore_errors=True)
os.makedirs(d)
src = os.path.join(d, 'p.kicad_pcb')
shutil.copy(make.OUT, src)
for ext in ('.kicad_pro', '.kicad_dru'):
    shutil.copy(os.path.splitext(make.OUT)[0] + ext, os.path.join(d, 'p' + ext))
route.PRE_EXPORT = make.dsn_keepouts
route.AUTOROUTE = dict(via_costs=via, plane_via_costs=5, start_ripup_costs=100)
route.export_dsn(src, os.path.join(d, 'r.dsn'))
route.freeroute(os.path.join(d, 'r.dsn'), os.path.join(d, 'r.ses'), passes=passes, log=os.path.join(d, 'fr.log'))
route.import_ses(src, os.path.join(d, 'r.ses'), os.path.join(d, 'r.kicad_pcb'))
for ext in ('.kicad_pro', '.kicad_dru'):
    shutil.copy(os.path.join(d, 'p' + ext), os.path.join(d, 'r' + ext))
print(tag, 'unrouted', route.unrouted(os.path.join(d, 'r.kicad_pcb'))[0])
