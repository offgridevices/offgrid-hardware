"""Look parts up in the JLCPCB / LCSC catalogues (stock, price, basic/extended).

    python3 lcsc.py C5802634 C3655801 ...      by LCSC number
    python3 lcsc.py -s "TPN2R304PL"             keyword search at JLCPCB
"""
import json, sys, urllib.request

UA = {'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'}

def lcsc(code):
    u = 'https://wmsc.lcsc.com/ftps/wm/product/detail?productCode=' + code
    d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))
    r = d.get('result') or {}
    prices = {p['ladder']: p['usdPrice'] for p in r.get('productPriceList', [])}
    return dict(code=code, mpn=r.get('productModel'), maker=r.get('brandNameEn'),
                pkg=r.get('encapStandard'), stock=r.get('stockNumber'),
                price=prices, desc=(r.get('productIntroEn') or '')[:90])

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

if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '-s':
        for kw in a[1:]:
            print('##', kw)
            for r in jlc(kw):
                print('  %(code)-10s %(mpn)-28s %(pkg)-18s stock %(stock)-8s %(kind)-9s %(price)s | %(desc)s' % r)
    else:
        for c in a:
            try:
                print(lcsc(c))
            except Exception as e:
                print(c, 'ERR', e)
