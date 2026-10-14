"""Build Canary v1 end to end; every gate fails the build.

  python3 src/make.py            (from canary/v1; needs docker, java, xvfb-run)

KiCad steps run in the pinned kicad/kicad:10.0.6-full image (tools/kd);
Freerouting 1.9.0 runs on the host JVM (FREEROUTING_JAR)."""
import os, re, subprocess, sys, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'out')
KD = os.path.join(ROOT, 'tools', 'kd')
JAR = os.environ.get('FREEROUTING_JAR', '/opt/fr/freerouting-1.9.0.jar')


def run(*cmd, **kw):
    print('+', ' '.join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=ROOT, **kw)
    if r.returncode:
        raise SystemExit(f'FAILED: {" ".join(cmd)}')


def kd(*cmd):
    run(KD, *cmd)


def drc_gate(report):
    txt = open(report).read()
    v = re.findall(r'^\[(\w+)\]', txt, re.M)
    print(f'DRC: {len(v)} items', sorted(set(v)))
    if v:
        raise SystemExit('DRC gate failed, see ' + report)


def route(src, stem):
    kd('python3', 'src/route.py', 'export', src, stem + '.dsn')
    run(sys.executable, 'src/dsn_tweak.py', stem + '.dsn')
    with open(os.path.join(ROOT, stem + '.log'), 'w') as log:
        run('timeout', '1500', 'xvfb-run', '-a', 'java', '-jar', JAR, '-de', stem + '.dsn',
            '-do', stem + '.ses', '-mp', os.environ.get('FR_PASSES', '60'), stdout=log, stderr=log)
    kd('python3', 'src/route.py', 'import', src, stem + '.ses', 'out/routed.kicad_pcb')


def main(steps):
    os.makedirs(OUT, exist_ok=True)
    if 'sch' in steps:
        run(sys.executable, 'src/schematic.py')
        kd('kicad-cli', 'sch', 'erc', '--exit-code-violations', '-o', 'out/erc.rpt', 'canary.kicad_sch')
        kd('kicad-cli', 'sch', 'export', 'netlist', '-o', 'out/canary.net', 'canary.kicad_sch')
        run(sys.executable, 'src/check_netlist.py', 'out/canary.net')
    if 'place' in steps:
        run(sys.executable, 'src/project.py')
        for f in ('fp-lib-table', 'sym-lib-table', 'canary.kicad_pro'):
            shutil.copy(os.path.join(ROOT, f), OUT)
        shutil.copy(os.path.join(ROOT, 'canary.kicad_pro'), os.path.join(OUT, 'placed.kicad_pro'))
        kd('python3', 'src/board.py', 'out/placed.kicad_pcb')
    if 'route' in steps:
        route('out/placed.kicad_pcb', 'out/route')
    if 'finish' in steps:
        for rnd in range(4):
            kd('python3', 'src/finish.py', 'out/routed.kicad_pcb', 'canary.kicad_pcb')
            kd('kicad-cli', 'pcb', 'drc', '--refill-zones', '--schematic-parity', '--severity-all',
               '-o', 'out/drc.rpt', 'canary.kicad_pcb')
            v = set(re.findall(r'^\[(\w+)\]', open(os.path.join(OUT, 'drc.rpt')).read(), re.M))
            if v != {'unconnected_items'}:
                break
            # Freerouting stalls on the last few connections: give the routed
            # board back to it; it keeps the existing wiring and finishes.
            print(f'routing round {rnd + 2}: connections left, routing again')
            route('out/routed.kicad_pcb', f'out/route_r{rnd + 2}')
        drc_gate(os.path.join(OUT, 'drc.rpt'))
    if 'fab' in steps:
        run(sys.executable, 'src/fab.py')


if __name__ == '__main__':
    main(sys.argv[1:] or ['sch', 'place', 'route', 'finish', 'fab'])
