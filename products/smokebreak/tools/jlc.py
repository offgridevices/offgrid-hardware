"""Look up parts in JLCPCB/LCSC's catalogue (the same parts PCBWay can buy
by manufacturer part number): python3 jlc.py KEYWORD [KEYWORD...]"""
import json
import sys
import urllib.request

URL = 'https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList'


def search(keyword, n=8):
    req = urllib.request.Request(URL, data=json.dumps({'keyword': keyword, 'currentPage': 1, 'pageSize': n}).encode(),
                                 headers={'content-type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    info = (d.get('data') or {}).get('componentPageInfo') or {}
    out = []
    for c in info.get('list') or []:
        price = None
        for p in c.get('componentPrices') or []:
            if p.get('startNumber', 0) <= 100:
                price = p.get('productPrice')
        out.append(dict(lcsc=c['componentCode'], mpn=c['componentModelEn'], brand=c.get('componentBrandEn'),
                        stock=c.get('stockCount'), pkg=c.get('componentSpecificationEn'), price=price,
                        desc=c.get('describe') or ''))
    return out


if __name__ == '__main__':
    for k in sys.argv[1:]:
        try:
            for c in search(k):
                print(f"{k:24s} {c['lcsc']:10s} {c['mpn'][:34]:34s} {str(c['brand'])[:22]:22s} {str(c['stock']):>8s} "
                      f"{str(c['pkg'])[:16]:16s} {c['price']}")
        except Exception as e:
            print(k, 'ERR', e)
