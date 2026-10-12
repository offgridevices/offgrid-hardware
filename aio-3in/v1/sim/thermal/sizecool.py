# -*- coding: utf-8 -*-
"""Board size x copper x cooling study for Ridge 3 Lite.

    tools/kd python3 sim/thermal/sizecool.py --board 35 --cu 1 --cool none     (one combination, ~10 min)
    python3 sim/thermal/sizecool.py --launch                                   (all 20 on the host, 3 at a time)
    tools/kd python3 sim/thermal/sizecool.py --report                          (results-size-cooling.md)

Every combination carries variant b's copper (whatif.py: GND fill with
stitching, vias in and around the battery pads, 8 vias on R_S1's GND pad).
  board  35: out/thermal/sc/b35.kicad_pcb (copy of out/r7/placed.kicad_pcb)
         38: out/thermal/sc/b38.kicad_pcb (copy of out/m38k/placed.kicad_pcb; read with BOARD_HALF=19)
  cu     1: 1 oz on all six layers; 2: 2 oz inner (In1-In4), 1 oz outer
  cool   none | top | bottom | both | fins  (thermal.Model.add_plates: 1.0 mm
         6061 plates on stepped 3 W/mK gap pad; fins = top plate + 4 mm fins at 1.5 mm pitch)
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
SC = os.path.join(REPO, 'out', 'thermal', 'sc')
BOARDS = {'35': os.path.join(SC, 'b35.kicad_pcb'), '38': os.path.join(SC, 'b38.kicad_pcb')}
SOURCES = {'35': os.path.join(REPO, 'out', 'r7', 'placed.kicad_pcb'), '38': os.path.join(REPO, 'out', 'm38k', 'placed.kicad_pcb')}
COOL = {'none': {}, 'top': {'top': dict(t=1e-3)}, 'bottom': {'bottom': dict(t=1e-3)},
        'both': {'top': dict(t=1e-3), 'bottom': dict(t=1e-3)}, 'fins': {'top': dict(t=1e-3, fins=True)}}
# the same with the pad filling the whole face (bare board through 1.5 mm of pad): the optimistic bound
for _k in ('top', 'bottom', 'both', 'fins'):
    COOL[_k + 'F'] = {sd: dict(o, fill=True) for sd, o in COOL[_k].items()}
COOL['finsbot'] = {'top': dict(t=1e-3, fins=True), 'bottom': dict(t=1e-3)}     # extra: finned top + flat bottom
CASES_F = ['full60-50C-wash-sun', 'hover-50C-wash-sun']
CASES = ['hover-50C-wash-sun', 'hover-25C-wash-shade', 'full60-50C-wash-sun', 'full60-25C-wash-shade',
         'full60-50C-halfwash-sun', 'punch-50C-wash-sun', 'abuse2-50C-wash-sun', 'abuse2-25C-wash-shade']
DT = {'full60': 0.5, 'punch': 0.25, 'abuse2': 0.05}


def build(board, cu, cool):
    import thermal as th
    import cases
    import whatif as w
    P = th.Params
    P.cell_mm, P.ss = 0.2, 8
    P.stack = w.STACK
    P.inner_oz = 2.0 if cu == '2' else 1.0
    P.outer_oz = 1.0
    g = th.load_kicad(BOARDS[board], P)
    info = {}
    info['vias_bat+'] = w.pad_vias(g, 'P_BAT+', '1', (3, 4), 10)
    info['vias_bat-'] = w.pad_vias(g, 'P_BAT-', '1', (3, 4), 10)
    info['vias_rs1'] = w.pad_vias(g, 'R_S1', '2', (2, 2), 4, ring_mm=0.8)
    info.update(w.gnd_fill(g))
    g.name = 'b%s_cu%s_%s' % (board, cu, cool)
    topo = cases.topology('aio3', g)
    m = th.Model(g, topo, P, cooling=COOL[cool])
    info['mass_g'] = dict(getattr(m, 'plate_mass', {}))
    info['board_mm2'] = float(m.area * 1e6)
    return g, topo, m, info


def metrics(g, m, T, res):
    rows = res['parts']
    mx = lambda test: max([r['T_j'] for r in rows if test(r)] or [float('nan')])
    nL = m.nL
    bat = []
    for ref in ('P_BAT+', 'P_BAT-'):
        f = g.fp(ref)
        l = nL - 1 if f['side'] else 0
        cells, _ = m.pad_cells(f, None, l)
        bat.append(float(T[cells * nL + l].max()))
    tr = res.get('transient', {}).get('peak', {})
    out = dict(FET=tr.get('FET junction max', mx(lambda r: r['kind'] == 'fet')),
               MCU=tr.get('ESC MCU max', mx(lambda r: r['name'].startswith('U_E'))),
               IMU=mx(lambda r: r['name'] == 'U_IMU'), X5R=mx(lambda r: r['kind'] == 'capX5R'),
               shunt=mx(lambda r: r['name'].startswith('R_S')), batpad=max(bat),
               board=max(b for a, b in res['layers'].values()), heat=res['total_heat_W'])
    for name, nodes in m.plates.items():
        out['plate_' + name] = float(T[nodes].max())
    out['runaway'] = bool(res.get('runaway'))
    return out


def derate(m, topo, losses, air, target=100.0):
    """Common AM32 current cap (all four channels alike): largest k <= 1 with every ESC MCU <= target, steady."""
    import thermal as th
    import cases
    env = dict(Ta=50.0, air=air, sun=True)
    s = th.Solver(m)
    mcu = [e['name'] for e in topo['elements'] if e['name'].startswith('U_E') and e['name'] in m.junc]

    def f(k, T0=None):
        dv = cases.drive_for('aio3', topo, dict(cases.LOADS['full'], scale=[k] * 4, name='full'), env, losses)
        T, _ = s.steady(dv, T0=T0, verbose=False, reuse=True)
        if getattr(s, 'runaway', False):
            return T, 1e3
        return T, max(float(T[m.junc[u]]) for u in mcu) - target
    T1, f1 = f(1.0)
    if f1 <= 0:
        return dict(k=1.0, MCU=f1 + target, iters=1)
    T0, f0 = f(1e-3, T1)
    if f0 > 0:
        return dict(k=0.0, MCU=f0 + target, iters=2, note='MCU over the cap with motors at idle')
    a, fa, b, fb, Tw = 1e-3, f0, 1.0, f1, T0
    side = 0
    for it in range(10):
        k = (a * fb - b * fa) / (fb - fa)            # regula falsi (Illinois)
        Tw, fk = f(k, Tw)
        if abs(fk) < 0.4:
            break
        if fk > 0:
            b, fb = k, fk
            if side == -1:
                fa /= 2
            side = -1
        else:
            a, fa = k, fk
            if side == 1:
                fb /= 2
            side = 1
    k_ok = k if fk <= 0.4 else a
    return dict(k=float(k_ok), MCU=float(fk + target), iters=it + 3)


def run_one(board, cu, cool, cases_=CASES):
    import thermal as th
    import cases
    sys.stdout.reconfigure(line_buffering=True)
    t0 = time.time()
    g, topo, m, info = build(board, cu, cool)
    losses = cases.Losses(os.path.join(HERE, '..', 'losses.csv'))
    path = os.path.join(SC, 'res', 'b%s_cu%s_%s.json' % (board, cu, cool))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    src = '%s %d' % (os.path.basename(os.path.dirname(SOURCES[board])), os.path.getsize(BOARDS[board]))
    out = dict(board=board, cu=cu, cool=cool, info=info, cases={}, src=src)
    if os.path.exists(path):           # resume: keep every case already written for this board file
        old = json.load(open(path))
        if old.get('src', src) == src:
            out['cases'] = old.get('cases', {})
            for k in ('derate_wash', 'derate_halfwash'):
                if k in old:
                    out[k] = old[k]
    for cname in cases_:
        if cname in out['cases']:
            continue
        case = cases.make_case(cname, 'aio3', topo, losses)
        dt = DT.get(cname.split('-')[0])
        res = th.run_case(m, topo, case, os.path.join(SC, 'maps', g.name), plots=(cname == 'full60-50C-wash-sun'), dt=dt)
        if 'parts' not in res:
            out['cases'][cname] = dict(runaway=True)
        else:
            out['cases'][cname] = metrics(g, m, th.run_case.last['T'], res)
        json.dump(out, open(path, 'w'), indent=1)
    for air in ('wash', 'halfwash'):
        if 'derate_' + air in out:
            continue
        out['derate_' + air] = derate(m, topo, losses, air)
        print('  AM32 cap, 50 C sun %s: k = %.2f' % (air, out['derate_' + air]['k']))
        json.dump(out, open(path, 'w'), indent=1)
    out['runtime_s'] = time.time() - t0
    json.dump(out, open(path, 'w'), indent=1)
    print('  done %s in %.0f s' % (g.name, time.time() - t0))


def launch(workers=3):
    """On the host: run every combination through tools/kd, `workers` at a time
    (counting study processes started by any launcher).  Each run resumes from
    its JSON, so after a restart just launch again.  A board is copied from its
    source once the source has stopped changing for a minute."""
    import shutil
    kd = os.path.join(REPO, 'aio-3in', 'v1', 'tools', 'kd')
    v1 = os.path.join(REPO, 'aio-3in', 'v1')
    jobs = [(b, cu, cool) for b in ('35', '38') for cu in ('1', '2') for cool in ('none', 'top', 'bottom', 'both', 'fins')]
    jobs += [(b, '2', 'finsbot') for b in ('35', '38')]
    if os.environ.get('SIZECOOL_ONLY'):                                                  # e.g. '38'
        jobs = [j for j in jobs if j[0] in os.environ['SIZECOOL_ONLY'].split(',')]
    skip = os.environ.get('SIZECOOL_SKIP', '')                                           # 'b38_cu1_top,...' running elsewhere
    jobs = [j for j in jobs if 'b%s_cu%s_%s' % j not in skip.split(',')]
    logdir = os.path.join(SC, 'logs')
    os.makedirs(logdir, exist_ok=True)
    running = []
    while jobs or running:
        running = [(j, p) for j, p in running if p.poll() is None]
        def busy():        # study processes running on this host, from any launcher
            r = subprocess.run(['pgrep', '-fc', '^python3 -u sim/thermal/sizecool.py --board'], capture_output=True, text=True)
            return int(r.stdout.strip() or 0)
        while jobs and len(running) < workers and busy() < workers:
            b = jobs[0][0]
            if not os.path.exists(BOARDS[b]):
                if os.path.exists(SOURCES[b]) and time.time() - os.path.getmtime(SOURCES[b]) > 60:
                    shutil.copy(SOURCES[b], BOARDS[b])     # copied once it has stopped changing
                else:
                    break
            j = jobs.pop(0)
            if os.path.exists(os.path.join(SC, 'res', 'b%s_cu%s_%s.json' % j)) and \
                    'runtime_s' in json.load(open(os.path.join(SC, 'res', 'b%s_cu%s_%s.json' % j))):
                continue
            cmd = 'export BOARD_HALF=%s; python3 -u sim/thermal/sizecool.py --board %s --cu %s --cool %s' % (
                19 if j[0] == '38' else 17.5, j[0], j[1], j[2])
            log = open(os.path.join(logdir, 'b%s_cu%s_%s.log' % j), 'a')
            p = subprocess.Popen([kd, 'sh', '-c', cmd], cwd=v1, stdout=log, stderr=subprocess.STDOUT)
            running.append((j, p))
            print(time.strftime('%H:%M:%S'), 'started', j, flush=True)
        time.sleep(10)
    print(time.strftime('%H:%M:%S'), 'all done', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--board'); ap.add_argument('--cu'); ap.add_argument('--cool')
    ap.add_argument('--cases', help='comma list (default: the study set)')
    ap.add_argument('--launch', action='store_true'); ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--report', action='store_true')
    a = ap.parse_args()
    if a.launch:
        return launch(a.workers)
    if a.report:
        import sizecool_report
        return sizecool_report.main()
    run_one(a.board, a.cu, a.cool, a.cases.split(',') if a.cases else (CASES_F if a.cool.endswith('F') else CASES))


if __name__ == '__main__':
    main()
