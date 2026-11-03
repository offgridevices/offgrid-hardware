"""Quick look at a board's copper: python3 view.py BOARD OUT.png [LAYERS]
(SVG from kicad-cli, rasterised by headless Chromium at 18 px/mm)."""
import os
import subprocess
import sys

CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'


def view(board, png, layers='F.Cu,B.Cu,In2.Cu,Edge.Cuts,F.Courtyard', px_per_mm=18):
    d = os.path.dirname(os.path.abspath(png))
    svg = os.path.join(d, os.path.basename(png) + '.svg')
    subprocess.run(['kicad-cli', 'pcb', 'export', 'svg', '--layers', layers, '--mode-single', '--page-size-mode', '2',
                    '--exclude-drawing-sheet', '-o', svg, board], capture_output=True, check=True)
    w, h = int(98 * px_per_mm), int(56 * px_per_mm)
    html = os.path.join(d, os.path.basename(png) + '.html')
    open(html, 'w').write(f'<html><body style="margin:0;background:#fff"><img src="{os.path.basename(svg)}" '
                          f'style="width:{w}px;height:{h}px;object-fit:contain"></body></html>')
    subprocess.run([CHROME, '--headless', '--no-sandbox', '--disable-gpu', f'--screenshot={png}',
                    f'--window-size={w},{h}', 'file://' + html], capture_output=True)
    return png


if __name__ == '__main__':
    view(sys.argv[1], sys.argv[2], *sys.argv[3:])
