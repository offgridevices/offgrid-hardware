"""Zoomed look at part of a board: python3 crop.py BOARD OUT.png x0 y0 x1 y1 [LAYERS] (board mm)."""
import os
import subprocess
import sys

CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
board, png = sys.argv[1], sys.argv[2]
x0, y0, x1, y1 = map(float, sys.argv[3:7])
layers = sys.argv[7] if len(sys.argv) > 7 else 'F.Cu,In2.Cu,In3.Cu,B.Cu,F.Fab,Edge.Cuts'
d = os.path.dirname(os.path.abspath(png))
svg = os.path.join(d, os.path.basename(png) + '.svg')
subprocess.run(['kicad-cli', 'pcb', 'export', 'svg', '--layers', layers, '--mode-single', '--page-size-mode', '2',
                '--exclude-drawing-sheet', '-o', svg, board], capture_output=True, check=True)
k = 40                                                     # px per mm
html = os.path.join(d, os.path.basename(png) + '.html')
W, H = int((x1 - x0) * k), int((y1 - y0) * k)
open(html, 'w').write(f'''<html><body style="margin:0;overflow:hidden;background:#fff">
<div style="position:absolute;left:{-x0 * k}px;top:{-y0 * k}px;width:{94 * k}px;height:{52 * k}px">
<img src="{os.path.basename(svg)}" style="width:{94 * k}px;height:{52 * k}px"></div></body></html>''')
subprocess.run([CHROME, '--headless', '--no-sandbox', '--disable-gpu', f'--screenshot={png}', f'--window-size={W},{H}',
                'file://' + html], capture_output=True)
