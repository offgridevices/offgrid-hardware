# -*- coding: utf-8 -*-
"""The designs the simulations compare, and where their files come from.

  rev1   revision 1 as it stood when revision 2 began, frozen into sim/rev1/:
         its two boards (gzipped .kicad_pcb) and its circuit.py, so rev 1 can
         be simulated again under exactly the conditions rev 2 is, by the
         same code
  rev2   the working tree: esc/ and fc/ boards, src/circuit.py

data.use(name) switches the part figures (data.DESIGNS); this module
switches the files.  Nothing here changes the working tree: rev 1's boards
are unpacked under sim/out/rev1/.
"""
import os, gzip, types

HERE = os.path.dirname(os.path.abspath(__file__))
RIDGE = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'out')
REV1 = os.path.join(HERE, 'rev1')
REV1_COMMIT = 'c2572f6'          # where sim/rev1/ was frozen from: a commit on the branch revision 2
                                 # was developed on, not on main (provenance only; nothing reads git)
NAMES = {'fc': 'ridge3-fc', 'esc': 'ridge3-esc'}
current = 'rev2'


def board_path(board, name=None):
    """The .kicad_pcb of a board ('fc' or 'esc') in a design."""
    name = name or current
    if name == 'rev2':
        # SIM_BOARD_ESC / SIM_BOARD_FC: simulate another file as rev 2's board
        # (a board still being routed; its power copper is what matters here)
        return (os.environ.get('SIM_BOARD_' + board.upper()) or
                os.path.join(RIDGE, board, NAMES[board] + '.kicad_pcb'))
    path = os.path.join(OUT, name, NAMES[board] + '.kicad_pcb')
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with gzip.open(os.path.join(REV1, NAMES[board] + '.kicad_pcb.gz')) as f:
            open(path, 'wb').write(f.read())
    return path


_circuits = {}


def circuit(name=None):
    """That design's circuit.py as a module (its build() and nets())."""
    name = name or current
    if name == 'rev2':
        import circuit as c
        return c
    if name not in _circuits:
        m = types.ModuleType('circuit_' + name)
        path = os.path.join(REV1, 'circuit.py')
        exec(compile(open(path, encoding='utf-8').read(), path, 'exec'), m.__dict__)
        _circuits[name] = m
    return _circuits[name]


def use(name):
    global current
    assert name in ('rev1', 'rev2'), name
    current = name
