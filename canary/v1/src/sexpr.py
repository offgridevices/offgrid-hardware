"""Minimal S-expression reader/writer for KiCad files."""
import re

class Sym(str):
    """An unquoted atom (keyword or number) as opposed to a quoted string."""
    pass

_tok = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)

def parse(text):
    pos, stack, cur = 0, [], []
    n = len(text)
    while True:
        m = _tok.match(text, pos)
        if not m:
            break
        pos = m.end()
        if m.group(1):
            stack.append(cur); cur = []
        elif m.group(2):
            done = cur; cur = stack.pop(); cur.append(done)
        elif m.group(3) is not None:
            cur.append(m.group(3).replace('\\"', '"').replace('\\\\', '\\'))
        else:
            cur.append(Sym(m.group(4)))
        if pos >= n:
            break
    return cur[0]

def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'

def dump(e, ind=0):
    if isinstance(e, list) and e and type(e[0]) is str:
        e = [Sym(e[0])] + e[1:]
    if not isinstance(e, list):
        if isinstance(e, Sym):
            return str(e)
        if isinstance(e, bool):
            return 'yes' if e else 'no'
        if isinstance(e, (int, float)):
            return fmt(e)
        return q(e)
    # short lists on one line
    simple = all(not isinstance(x, list) for x in e)
    if simple:
        return '(' + ' '.join(dump(x) for x in e) + ')'
    out = '(' + ' '.join(dump(x) for x in e if not isinstance(x, list))
    # keep atoms leading, lists on new lines
    head = [x for x in e if not isinstance(x, list)]
    out = '(' + ' '.join(dump(x) for x in head)
    for x in e:
        if isinstance(x, list):
            out += '\n' + '\t' * (ind + 1) + dump(x, ind + 1)
    out += '\n' + '\t' * ind + ')'
    return out

def fmt(v):
    if isinstance(v, int):
        return str(v)
    s = ('%.4f' % v).rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s

def find(e, key):
    for x in e:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None

def findall(e, key):
    return [x for x in e if isinstance(x, list) and x and x[0] == key]
