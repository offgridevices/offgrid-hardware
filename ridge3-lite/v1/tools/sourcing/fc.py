"""Findchips scrape: per-distributor stock, lead time, MOQ/multiple for an MPN.
    python3 fc.py MPN [MPN ...]   -> prints summary, caches JSON in out/fc/
"""
import sys, re, json, html, os, urllib.request, urllib.parse, time
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'out', 'fc') + '/'   # cache, gitignored
os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36'}

def fetch(q):
    u = 'https://www.findchips.com/search/' + urllib.parse.quote(q, safe='')
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode('utf-8', 'ignore')

def parse(s, q):
    rows = []
    # split into distributor blocks
    blocks = re.split(r'<div id="list\d+" class="distributor-results', s)[1:]
    for b in blocks:
        name = re.search(r'data-distributor_name="([^"]+)"', b)
        name = html.unescape(name.group(1)) if name else '?'
        h2 = re.search(r'<h2 class="distributor-title">(.*?)</h2>', b, re.S)
        auth = bool(h2 and 'Authorized' in h2.group(1))
        for tr in re.split(r'<tr data-id=', b)[1:]:
            g = lambda pat: (re.search(pat, tr, re.S) or [None, None])[1]
            mpn = html.unescape(g(r'data-mfrpartnumber="([^"]*)"') or '')
            mfr = html.unescape(g(r'data-mfr="([^"]*)"') or '')
            stock = g(r'data-stock="([^"]*)"')
            def field(t):
                v = g(r'data-title="%s">\s*(.*?)\s*</span>' % re.escape(t))
                return html.unescape(re.sub(r'<[^>]+>', '', v)).strip() if v else None
            disti = g(r'DISTI #</span>\s*<span class="additional-value">([^<]*)<')
            rows.append(dict(dist=name, auth=auth, mpn=mpn, mfr=mfr, disti=disti,
                             stock=(int(re.match(r'\d+', stock).group()) if stock and re.match(r'\d+', stock) else stock),
                             moq=field('Min Qty'), mult=field('Package Mult.'),
                             lead=field('Lead time'), container=field('Container'),
                             desc=html.unescape((g(r'<span class="td-description more">(.*?)</span>') or '')[:80])))
    return rows

def norm(x):
    return re.sub(r'[^A-Z0-9]', '', x.upper())

def get(q, exact_prefix=None):
    fn = OUT + norm(q) + '.json'
    if os.path.exists(fn):
        return json.load(open(fn))
    s = fetch(q)
    rows = parse(s, q)
    json.dump(rows, open(fn, 'w'), indent=1)
    time.sleep(1)
    return rows

def summary(q, prefix=None):
    rows = get(q)
    p = norm(prefix or q)
    rows = [r for r in rows if norm(r['mpn']).startswith(p)]
    auth = [r for r in rows if r['auth']]
    tot = {}
    for r in auth:
        if isinstance(r['stock'], int):
            tot[r['dist']] = max(tot.get(r['dist'], 0), r['stock'])
    leads = sorted(set(r['lead'] for r in auth if r['lead']))
    mults = sorted(set(r['mult'] for r in auth if r['mult'] and r['mult'] != '1'))
    return dict(q=q, auth_total=sum(tot.values()), by_dist=tot, leads=leads, mults=mults,
                indep=sum(r['stock'] for r in rows if not r['auth'] and isinstance(r['stock'], int)))

if __name__ == '__main__':
    for q in sys.argv[1:]:
        try:
            s = summary(q)
            print(json.dumps(s))
        except Exception as e:
            print(q, 'ERR', e)
        sys.stdout.flush()
