"""Look parts up in the JLCPCB / LCSC catalogues (stock, price, basic/extended).

    python3 tools/lcsc.py C5328706 C3010298 ...     JLCPCB stock by LCSC number
    python3 tools/lcsc.py -s "W25N02KV"              keyword search at JLCPCB
    python3 tools/lcsc.py --parts                    every part in src/parts.py

JLCPCB assembles from its own stock, which is not LCSC's: an LCSC number
with no LCSC stock can still be in JLCPCB's.  (Print Hub's tools/lcsc.py,
with a lookup by number at JLCPCB added.)
"""
import json, os, sys, urllib.request

UA = {'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'}


def jlc(keyword, n=25):
    u = 'https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList'
    body = json.dumps({'keyword': keyword, 'currentPage': 1, 'pageSize': n}).encode()
    d = json.load(urllib.request.urlopen(urllib.request.Request(u, body, UA), timeout=30))
    out = []
    for c in ((d.get('data') or {}).get('componentPageInfo') or {}).get('list') or []:
        out.append(dict(code=c.get('componentCode'), mpn=c.get('componentModelEn'),
                        pkg=c.get('componentSpecificationEn'), stock=c.get('stockCount'),
                        kind=c.get('componentLibraryType'), desc=(c.get('describe') or '')[:90],
                        price=[(p.get('startNumber'), p.get('productPrice'))
                               for p in (c.get('componentPrices') or [])][:3]))
    return out


def by_code(code):
    """The JLCPCB catalogue entry for one LCSC number, or None."""
    for r in jlc(code, 10):
        if r['code'] == code:
            return r
    return None


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '-s':
        for kw in a[1:]:
            print('##', kw)
            for r in jlc(kw):
                print('  %(code)-10s %(mpn)-28s %(pkg)-18s stock %(stock)-8s %(kind)-9s %(price)s | %(desc)s' % r)
    else:
        if a and a[0] == '--parts':
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
            import parts
            a = sorted({p['lcsc'] for p in parts.PARTS.values()})
        for c in a:
            r = by_code(c)
            print('%-10s %s' % (c, ('%(mpn)-26s %(pkg)-22s stock %(stock)-8s %(kind)-9s %(price)s' % r) if r else 'NOT FOUND'))
