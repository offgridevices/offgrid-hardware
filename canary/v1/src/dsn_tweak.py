"""Give the supply nets their own wider class in the Specctra file (KiCad's
DSN export puts every net in kicad_default)."""
import re, sys
POWER = ['VBUS', '+3V3', '/BUZ_D']
p = sys.argv[1]
t = open(p).read()
# KiCad's single-pin "unconnected-(...)" nets: nothing to route, and their
# names (with parentheses and {slash}) break the class list and stall
# Freerouting 1.9.0's reader. Drop them.
t = re.sub(r'\n\s*\(net "unconnected-[^"]*"\s*\(pins[^)]*\)\s*\)', '', t)
t = re.sub(r'\s*"unconnected-[^"]*"', '', t)
m = re.search(r'\(class kicad_default([^()]*)', t)
names = m.group(1).split()
rest = [n for n in names if n not in POWER]
t = t[:m.start()] + '(class kicad_default ' + ' '.join(rest) + '\n      ' + t[m.end():]
cls_end = t.index('(class kicad_default')
# copy the default class's circuit block for the power class
blk = re.search(r'\(class kicad_default.*?\n    \)\n', t, re.S).group(0)
power = re.sub(r'\(class kicad_default [^\n(]*', '(class Power ' + ' '.join(POWER) + ' ', blk, count=1)
power = power.replace('(width 200)', '(width 300)')
t = t.replace(blk, blk + power)
open(p, 'w').write(t)

# Ground is not routed: every ground pad has its own via into the planes
# (board.fanout). Empty its pin list and give each fixed ground wire/via a
# net of its own, so Freerouting treats them as obstacles and joins nothing.
import itertools
t = open(p).read()
t, k = re.subn(r'(\(net GND\s*\n\s*\(pins)[^)]*\)', r'\1)', t)
assert k == 1, k
j = t.index('(wiring')
cnt = itertools.count()
extra = []
def solo(m):
    n = 'GNDFIX%d' % next(cnt); extra.append(n); return '(net %s)' % n
t = t[:j] + re.sub(r'\(net GND\)', solo, t[j:])
j = t.index('(network') + len('(network')
t = t[:j] + ''.join('\n    (net %s\n      (pins)\n    )' % e for e in extra) + t[j:]
open(p, 'w').write(t)
