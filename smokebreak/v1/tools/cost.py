"""Landed-cost tally for a production batch (default 100 boards).

Parts with an LCSC number are priced live from JLCPCB/LCSC's catalogue at the
batch quantity; generic passives without one at LCSC's typical price;
everything else (toggle, display, board, assembly, case, freight) from the
estimates below, each with its source.  python3 tools/cost.py [BATCH]
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'src'))
sys.path.insert(0, HERE)
import circuit  # noqa: E402
import parts    # noqa: E402
import jlc      # noqa: E402

BATCH = int(sys.argv[1]) if len(sys.argv) > 1 else 100
CACHE = os.path.join(HERE, '..', 'src', 'out', 'prices.json')

GENERIC = {'R0402': 0.0012, 'R0603': 0.0015, 'R0805': 0.003, 'R1206': 0.004,
           'C0402': 0.002, 'C0603': 0.004, 'C0805': 0.01, 'C1206': 0.03, 'C1210': 0.06}
PRECISION = 0.012          # 0.1 % 0603 thin-film resistors (per piece, 100+)

# Not on LCSC, or bought outside the board order.  (USD per unit at ~100)
OTHER = {
    'TOGGLE': (10.20, 'C&K 7107SYCQE, Digi-Key/Mouser 100+ (E-Switch 100SP3T1B4M6QE: 2.65)'),
    'TFT1901': (2.90, '1.9" 170x320 ST7789 IPS with 30-pin FPC, AliExpress/LCSC-class suppliers'),
}
FIXED = [
    ('PCB, 6 layers 94 x 52 mm, black mask, ENIG, PCBWay, 100 pcs (estimate)', 2.50),
    ('PCBWay SMT assembly (one side), setup + stencil spread over 100', 1.60),
    ('3D-printed case + guard (PETG/PC, ~45 g at $20/kg) + magnet 6x3 N52 + 4 screws + feet', 1.35),
    ('Light pipe ring, Limit paddle (printed), toggle nut/boss hardware', 0.25),
    ('Freight + duties on the PCBA and parts (~8 %)', None),
]


def price(lcsc):
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    if lcsc in cache:
        return cache[lcsc]
    p = None
    try:
        for r in jlc.search(lcsc, n=3):
            if r['lcsc'] == lcsc:
                p = r['price']
                break
    except Exception:
        pass
    cache[lcsc] = p
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(cache, open(CACHE, 'w'), indent=1)
    return p


def tally():
    count = collections.Counter(c['part'] for c in circuit.COMPONENTS.values())
    rows = []
    for key, n in sorted(count.items()):
        pd = parts.PARTS[key]
        if pd['fit'] == 'none':
            continue
        if key in OTHER:
            u, src = OTHER[key]
        elif pd['lcsc'] and price(pd['lcsc']) is not None:
            u, src = price(pd['lcsc']), 'LCSC ' + pd['lcsc']
        else:
            kind = key.split('-')[0]
            if '0.1%' in key:
                u, src = PRECISION, 'thin film 0.1 %, typical'
            else:
                u, src = GENERIC.get(kind, 0.02), 'generic passive, typical'
        rows.append((key, pd['mpn'], n, u, n * u, src))
    return rows


if __name__ == '__main__':
    rows = tally()
    parts_total = sum(r[4] for r in rows)
    print(f'{"part":22s} {"MPN":28s} {"qty":>4s} {"unit":>8s} {"line":>8s}  source')
    for r in sorted(rows, key=lambda r: -r[4]):
        print(f'{r[0]:22s} {str(r[1])[:28]:28s} {r[2]:4d} {r[3]:8.4f} {r[4]:8.3f}  {r[5]}')
    print(f'\nparts total {parts_total:.2f}')
    total = parts_total
    for what, c in FIXED:
        if c is None:
            c = 0.08 * total
        total += c
        print(f'  + {c:5.2f}  {what}')
    print(f'landed per unit (batch {BATCH}): {total:.2f} USD')
