# -*- coding: utf-8 -*-
"""A minimal KiCad s-expression reader and writer, plus stable UUIDs."""
import re, uuid, hashlib


def parse(s):
    toks = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', s)
    st = [[]]
    for t in toks:
        if t == '(':
            st.append([])
        elif t == ')':
            x = st.pop(); st[-1].append(x)
        else:
            st[-1].append(t)
    return st[0]


def emit(n, ind=0):
    if not isinstance(n, list):
        return n
    pad = '\t' * ind
    if all(not isinstance(c, list) for c in n):
        return pad + '(' + ' '.join(n) + ')'
    head = [c for c in n if not isinstance(c, list)]
    out = pad + '(' + ' '.join(head)
    for c in n:
        if isinstance(c, list):
            out += '\n' + emit(c, ind + 1)
    return out + '\n' + pad + ')'


def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def uid(*key):
    """Stable UUIDs, so a rebuild of an unchanged circuit is byte-identical."""
    h = hashlib.sha1(('mesh-radio-v1/' + '/'.join(map(str, key))).encode()).hexdigest()
    return str(uuid.UUID(h[:32]))


def f(x):
    s = ('%.4f' % x).rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


