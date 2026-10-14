"""Specctra round trip for Freerouting (runs in the KiCad container).
  route.py export <board> <dsn>
  route.py import <board> <ses> <out_board>"""
import sys, pcbnew
cmd = sys.argv[1]
b = pcbnew.LoadBoard(sys.argv[2])
if cmd == 'export':
    if not pcbnew.ExportSpecctraDSN(b, sys.argv[3]):
        raise SystemExit('DSN export failed')
elif cmd == 'import':
    if not pcbnew.ImportSpecctraSES(b, sys.argv[3]):
        raise SystemExit('SES import failed')
    # Freerouting leaves the odd zero-length segment at a stub end
    junk = [t for t in b.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetLength() < 10000]
    for t in junk:
        b.Remove(t)
    b.Save(sys.argv[4])
