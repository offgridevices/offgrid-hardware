"""Load (and flatten) symbols from KiCad .kicad_sym libraries."""
import copy, os
from sexpr import parse, find, findall, Sym

SYMDIR = os.environ.get('KICAD_SYMBOL_DIR') or next(
    (d for d in ('/opt/kicad-share/symbols', '/usr/share/kicad/symbols') if os.path.isdir(d)),
    '/usr/share/kicad/symbols')
_cache = {}

def _lib(name, path=None):
    if name not in _cache:
        p = path or os.path.join(SYMDIR, name + '.kicad_sym')
        _cache[name] = parse(open(p).read())
    return _cache[name]

def _raw(lib, name, path=None):
    for s in findall(_lib(lib, path), 'symbol'):
        if s[1] == name:
            return s
    raise KeyError(f'{lib}:{name}')

def load(lib_id, path=None):
    """Return a flattened copy of the symbol, renamed to lib_id."""
    lib, name = lib_id.split(':')
    s = copy.deepcopy(_raw(lib, name, path))
    ext = find(s, 'extends')
    if ext:
        parent = load(f'{lib}:{ext[1]}', path)
        # child properties override parent's
        child_props = {p[1]: p for p in findall(s, 'property')}
        out = [Sym('symbol'), lib_id]
        for x in parent[2:]:
            if isinstance(x, list) and x[0] == 'property' and x[1] in child_props:
                out.append(child_props.pop(x[1]))
            elif isinstance(x, list) and x[0] == 'symbol':
                y = copy.deepcopy(x)
                y[1] = name + y[1][len(ext[1]):] if y[1].startswith(ext[1]) else y[1]
                out.append(y)
            else:
                out.append(x)
        # insert remaining child props after the last property
        idx = max(i for i, x in enumerate(out) if isinstance(x, list) and x[0] == 'property')
        for p in child_props.values():
            idx += 1
            out.insert(idx, p)
        s = out
    s[1] = lib_id
    return s

def pins(sym):
    """[(number, name, type, x, y, angle, length, unit)] in symbol coords (y up)."""
    res = []
    for u in findall(sym, 'symbol'):
        parts = u[1].rsplit('_', 2)
        unit = int(parts[-2]) if len(parts) >= 3 else 0
        for p in findall(u, 'pin'):
            at = find(p, 'at'); ln = find(p, 'length')
            res.append((find(p, 'number')[1], find(p, 'name')[1], str(p[1]),
                        float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0,
                        float(ln[1]), unit))
    return res
