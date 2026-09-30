# -*- coding: utf-8 -*-
"""The designs the simulations compare, and where their files come from.

  rev1   the stack as committed in REV1_COMMIT: its two boards and its
         circuit.py are read from git, so rev 1 can be simulated again
         under exactly the conditions rev 2 is, by the same code
  rev2   the working tree: esc/ and fc/ boards, src/circuit.py

data.use(name) switches the part figures (data.DESIGNS); this module
switches the files.  Nothing here changes the working tree: rev 1's files
are written under sim/out/rev1/.
"""
import os, subprocess, types

HERE = os.path.dirname(os.path.abspath(__file__))
RIDGE = os.path.dirname(HERE)
REPO = os.path.dirname(RIDGE)
OUT = os.path.join(HERE, 'out')
REV1_COMMIT = 'c2572f6'          # "STRESS.md: the stack simulated flat out, hot, on 6S"
NAMES = {'fc': 'ridge3-fc', 'esc': 'ridge3-esc'}
current = 'rev2'


def _git_file(commit, rel):
    return subprocess.run(['git', '-C', REPO, 'show', '%s:%s' % (commit, rel)], check=True,
                          capture_output=True).stdout


def board_path(board, name=None):
    """The .kicad_pcb of a board ('fc' or 'esc') in a design."""
    name = name or current
    rel = 'ridge-3/%s/%s.kicad_pcb' % (board, NAMES[board])
    if name == 'rev2':
        return os.path.join(REPO, rel)
    path = os.path.join(OUT, name, NAMES[board] + '.kicad_pcb')
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'wb').write(_git_file(REV1_COMMIT, rel))
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
        src = _git_file(REV1_COMMIT, 'ridge-3/src/circuit.py').decode()
        exec(compile(src, 'circuit.py@' + REV1_COMMIT, 'exec'), m.__dict__)
        _circuits[name] = m
    return _circuits[name]


def use(name):
    global current
    assert name in ('rev1', 'rev2'), name
    current = name
