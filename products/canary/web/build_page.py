"""Build the Canary product page (web/page.html + renders + HIL data) into one
self-contained HTML file: python3 build_page.py <out.html>"""
import base64, io, json, os, sys
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)

def webp(im, q=82):
    b = io.BytesIO(); im.save(b, 'WEBP', quality=q, method=6)
    return 'data:image/webp;base64,' + base64.b64encode(b.getvalue()).decode()

top = Image.open(os.path.join(V, 'video/out/stills/top.png')).convert('RGBA')
top = top.crop((863, 370, 2945, 1758)).resize((1040, 693), Image.LANCZOS)   # board outline only
hero = Image.open(os.path.join(V, 'video/out/stills/hero.png')).convert('RGBA')
hero = hero.crop(hero.getbbox()); hero = hero.resize((1200, int(hero.height * 1200 / hero.width)), Image.LANCZOS)
tel = []
for line in open(os.path.join(V, 'sim/hil/out/vent_uart.log')):
    ts, _, msg = line.partition(' ')
    if msg.startswith('t='):
        k = dict(x.split('=') for x in msg.split())
        if 330 <= int(k['t']) <= 560:
            tel.append([int(k['t']), int(k['sraw']), int(k['co2']), int(k['tp']), int(k['st'])])
res = json.load(open(os.path.join(V, 'sim/hil/out/results.json')))
n = sum(len(v['checks']) for v in res.values()); ok = sum(c['ok'] for v in res.values() for c in v['checks'])
s = open(os.path.join(HERE, 'page.html')).read()
s = (s.replace('{{HERO}}', webp(hero)).replace('{{TOP}}', webp(top)).replace('{{VENT}}', json.dumps(tel))
      .replace('{{HILOK}}', str(ok)).replace('{{HILN}}', str(n)))
open(sys.argv[1], 'w').write(s)
print(sys.argv[1], len(s) // 1024, 'KB')
