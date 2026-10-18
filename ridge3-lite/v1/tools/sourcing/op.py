"""Octopart search scrape: per-seller stock for an MPN (authorised flag, lead days, moq, packaging).
    python3 op.py MPN [MPN ...]
"""
import sys, re, json, os, urllib.request, urllib.parse, time
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'out', 'op') + '/'   # cache, gitignored
os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36',
      'Accept-Language': 'en-US,en;q=0.9'}

def norm(x):
    return re.sub(r'[^A-Z0-9]', '', x.upper())

def fetch(q):
    fn = OUT + norm(q) + '.html'
    if os.path.exists(fn) and os.path.getsize(fn) > 100000:
        return open(fn, encoding='utf-8', errors='ignore').read()
    u = 'https://octopart.com/search?q=' + urllib.parse.quote(q) + '&currency=USD&specs=0'
    s = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode('utf-8', 'ignore')
    open(fn, 'w').write(s)
    time.sleep(1.5)
    return s

def parts(s):
    # The flight data is a JS string: undo one level of escaping
    t = s.replace('\\\\"', '\u0001').replace('\\"', '"').replace('\u0001', '\\"')
    dec = json.JSONDecoder()
    out = []
    seen = set()
    for m in re.finditer(r'"sellers":\[', t):
        try:
            sellers, _ = dec.raw_decode(t, m.end() - 1)
        except Exception:
            continue
        head = t[max(0, m.start() - 6000):m.start()]
        mp = re.findall(r'"mpn":"([^"]+)"', head)
        mf = re.findall(r'"manufacturer":\{"name":"([^"]+)"', head)
        mpn = mp[-1] if mp else '?'
        key = (mpn, json.dumps(sellers)[:200])
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(mpn=mpn, mfr=mf[-1] if mf else '?', sellers=sellers))
    return out

def rows(q):
    out = []
    for p in parts(fetch(q)):
        for s in p['sellers']:
            c = s.get('company', {})
            for o in s.get('offers', []):
                out.append(dict(mpn=p['mpn'], mfr=p['mfr'], seller=c.get('name'), auth=s.get('is_authorized'),
                                broker=s.get('is_broker'), stock=o.get('inventory_level'),
                                lead=o.get('factory_lead_days'), moq=o.get('moq'), pack=o.get('packaging'),
                                mult=o.get('order_multiple'), onorder=o.get('on_order_quantity'),
                                sku=o.get('sku'), updated=(o.get('updated') or '')[:10]))
    return out

def summary(q, prefix=None, maker=None):
    p = norm(prefix or q)
    rs = [r for r in rows(q) if norm(r['mpn']).startswith(p)
          and (not maker or maker.lower() in (r['mfr'] or '').lower())]
    by = {}
    for r in rs:
        if r['auth'] and isinstance(r['stock'], int) and r['stock'] > 0:
            k = r['seller']
            by[k] = max(by.get(k, 0), r['stock'])
    leads = {}
    for r in rs:
        if r['auth'] and r['lead']:
            leads[r['seller']] = r['lead']
    mpns = sorted(set(r['mpn'] for r in rs))
    return dict(q=q, mpns=mpns, auth_total=sum(by.values()), by=by, lead_days=leads,
                indep=sum(r['stock'] for r in rs if not r['auth'] and isinstance(r['stock'], int)),
                makers=sorted(set(r['mfr'] for r in rs)))

if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '-r':
        for q in a[1:]:
            for r in rows(q):
                print(q[:14], r)
    else:
        for q in a:
            try:
                print(json.dumps(summary(q)))
            except Exception as e:
                print(q, 'ERR', repr(e))
            sys.stdout.flush()
