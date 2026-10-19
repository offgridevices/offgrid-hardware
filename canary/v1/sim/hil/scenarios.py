"""Hardware-in-the-loop scenarios for Canary v1.

Each scenario is a world (what the air and the pack do, second by second),
the real firmware ELF running on simavr's ATmega328P against it (harness.c),
and a list of checks on what a person would see and hear.

  python3 scenarios.py [name ...]      (all when none given)

Writes out/<name>_world.csv, _uart.log, _io.csv, results.json and plots.

World models (stated assumptions, not measurements):
  - SGP40 raw signal ~30000 ticks in clean air, +-15 ticks noise; a VOC
    event lowers it (the signal is proportional to log of MOX resistance).
  - SCD41 CO2 ~550 ppm indoors, +-10 ppm noise, read every 5 s.
  - Venting cell (first vent, before runaway): solvent vapour drives SRAW
    down by thousands of ticks within ~20 s, CO2 rises by thousands of ppm
    within a minute, and the pack surface then heats at a growing rate.
    Thresholds therefore need validating against real vent gas; see the
    README's Limits.
"""
import csv, json, math, os, random, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
ELF = os.path.join(HERE, '..', '..', 'firmware', 'build', 'canary.elf')
HARNESS = os.path.join(HERE, 'harness')
ST = {0: 'WARMUP', 1: 'NORMAL', 2: 'WARN', 3: 'ALARM', 4: 'FAULT'}


def base_world(n, seed):
    rnd = random.Random(seed)
    rows = []
    for t in range(n):
        rows.append(dict(t=t, t_pack=22.0 + rnd.gauss(0, 0.03), t_probe=None, t_amb=22.0, rh=45.0,
                         sraw=30000 + rnd.gauss(0, 15), co2=550 + rnd.gauss(0, 10),
                         sgp=1, sht=1, scd=1, button=0))
    return rows


def charging_heat(rows, start=0, rise=10.0, tau=900.0):
    for r in rows:
        if r['t'] >= start:
            r['t_pack'] += rise * (1 - math.exp(-(r['t'] - start) / tau))


def vent(rows, t0, voc=8000, co2=6000, heat=True):
    """First vent at t0: solvent + CO2 cloud, then accelerating self-heating."""
    for r in rows:
        dt = r['t'] - t0
        if dt < 0:
            continue
        r['sraw'] -= voc * (1 - math.exp(-dt / 8.0))
        r['co2'] += co2 * (1 - math.exp(-dt / 25.0))
        if heat:
            # dT/dt grows from 0.3 C/min to ~6 C/min over ~6 min
            r['t_pack'] += 0.3 / 60 * dt + 0.5 * (math.exp(dt / 120.0) - 1)


def scenario(name):
    S = {}
    if name == 'normal_charge':
        w = base_world(1500, 1); charging_heat(w, 0, 12.0, 1200.0)
        w[200]['button'] = 1                      # self-test press
        S = dict(world=w, desc='Normal overnight-style charge: pack warms 22 -> 34 C slowly; '
                 'self-test button at 200 s.')
    elif name == 'late_vent':
        w = base_world(6500, 9); charging_heat(w, 0, 12.0, 1800.0)
        vent(w, 6000)
        S = dict(world=w, desc='Long charge, cell vents at 100 min: past the 71.6 min at which '
                 'a 32-bit tick-to-ms product would overflow.', onset=6000)
    elif name == 'cleaning_spray':
        w = base_world(900, 2); charging_heat(w)
        for r in w:
            dt = r['t'] - 300
            if dt >= 0:
                r['sraw'] -= 4000 * (1 - math.exp(-dt / 5)) * math.exp(-dt / 120)
        S = dict(world=w, desc='Household VOC (cleaning spray) at 300 s: gas evidence only.')
    elif name == 'breath':
        w = base_world(600, 3)
        for r in w:
            dt = r['t'] - 300
            if 0 <= dt:
                r['co2'] += 2500 * (min(dt, 20) / 20) * math.exp(-max(dt - 20, 0) / 30)
                r['sraw'] -= 300 * math.exp(-dt / 60)
        S = dict(world=w, desc='Someone breathes on the board at 300 s: CO2 spike, trace VOC.')
    elif name == 'vent':
        w = base_world(900, 4); charging_heat(w)
        vent(w, 400)
        S = dict(world=w, desc='Cell vents at 400 s: solvent vapour + CO2, then self-heating.', onset=400)
    elif name == 'overheat':
        w = base_world(900, 5)
        for r in w:
            r['t_pack'] = 30.0 + (max(r['t'] - 200, 0) * 4.0 / 60) + random.Random(r['t']).gauss(0, 0.03)
        S = dict(world=w, desc='Pack heats 4 C/min from 200 s with no gas (charger fault).', onset=200)
    elif name == 'hush':
        w = base_world(900, 6); charging_heat(w)
        vent(w, 300, heat=False)
        for r in w:                               # heat arrives later
            dt = r['t'] - 420
            if dt >= 0:
                r['t_pack'] += 5.0 / 60 * dt
        w[340]['button'] = 1
        S = dict(world=w, desc='Vent at 300 s, HUSH pressed at 340 s, heat joins at 420 s.', onset=300)
    elif name == 'sensor_fault':
        w = base_world(400, 7)
        for r in w:
            if r['t'] >= 200:
                r['sgp'] = 0
        S = dict(world=w, desc='SGP40 stops answering at 200 s.', onset=200)
    elif name == 'probe':
        w = base_world(700, 8)
        for r in w:
            r['t_probe'] = 24.0 + max(r['t'] - 200, 0) * 4.5 / 60
        S = dict(world=w, desc='Remote probe on a pack inside a frame heats 4.5 C/min from 200 s; '
                 'the board tab stays cool.', onset=200)
    S['name'] = name
    return S


def write_world(S):
    p = os.path.join(OUT, S['name'] + '_world.csv')
    with open(p, 'w') as f:
        f.write('t,t_pack,t_probe,t_amb,rh,sraw,co2,sgp,sht,scd,button\n')
        for r in S['world']:
            tp = '' if r['t_probe'] is None else '%.3f' % r['t_probe']
            f.write('%d,%.3f,%s,%.2f,%.1f,%.0f,%.0f,%d,%d,%d,%d\n' % (
                r['t'], r['t_pack'], tp, r['t_amb'], r['rh'], max(r['sraw'], 0), max(r['co2'], 0),
                r['sgp'], r['sht'], r['scd'], r['button']))
    return p


def run(S):
    wp = write_world(S)
    pre = os.path.join(OUT, S['name'])
    r = subprocess.run([HARNESS, ELF, wp, pre], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stderr)
    S['harness'] = [l for l in r.stderr.splitlines() if l.startswith('done')][0]
    tel = []
    for line in open(pre + '_uart.log'):
        ts, _, msg = line.partition(' ')
        if msg.startswith('t='):
            d = dict(kv.split('=') for kv in msg.split())
            d['sim_t'] = float(ts)
            tel.append(d)
        elif msg.strip():
            tel.append({'sim_t': float(ts), 'msg': msg.strip()})
    io = list(csv.DictReader(open(pre + '_io.csv')))
    for k in io:
        for f in k:
            k[f] = float(k[f])
    S['tel'], S['io'] = tel, io
    return S


def states(S):
    return [(float(d['sim_t']), int(d['st'])) for d in S['tel'] if 'st' in d]


def first(S, st, after=0):
    for t, s in states(S):
        if s == st and t >= after:
            return t
    return None


def checks(S):
    n, res = S['name'], []
    def chk(desc, ok, value=None):
        res.append(dict(check=desc, ok=bool(ok), value=value))
    sts = states(S)
    io = S['io']
    tone = [r for r in io if r['tone_on'] > 0.4]
    hz = [r['buz_hz'] for r in io if r['tone_on'] > 0.99]
    msgs = [d.get('msg', '') for d in S['tel']]
    chk('firmware banner printed', any('CANARY v1' in m for m in msgs))
    chk('no sensor faults while sensors present',
        all(d.get('f', '0') in ('0', '00') for d in S['tel'] if 'f' in d and float(d['sim_t']) < S.get('fault_from', 1e9)) or n == 'sensor_fault')
    if hz:
        chk('sounder frequency 4 kHz +-2 %', all(abs(h - 4000) < 80 for h in hz), round(sum(hz) / len(hz)))
    if n == 'normal_charge':
        chk('never WARN/ALARM/FAULT after warm-up', all(s in (0, 1) for t, s in sts))
        chk('green LED breathing in NORMAL', max(r['green'] for r in io if r['t'] > 120) > 0.1)
        chk('self-test ran and passed', any('selftest sgp40=ok' in m for m in msgs))
        st_tone = [r for r in io if 199 <= r['t'] <= 204 and r['tone_on'] > 0.4]
        chk('self-test beeps', len(st_tone) > 0)
    if n == 'cleaning_spray':
        chk('WARN raised for gas alone', first(S, 2) is not None, first(S, 2))
        chk('no ALARM for gas alone', all(s != 3 for t, s in sts))
        chk('back to NORMAL afterwards', sts[-1][1] == 1)
    if n == 'breath':
        chk('no ALARM for a breath', all(s != 3 for t, s in sts))
    if n in ('vent', 'overheat', 'hush', 'probe', 'late_vent'):
        ta = first(S, 3)
        lat = None if ta is None else round(ta - S['onset'], 1)
        S['latency'] = lat
        chk('ALARM raised', ta is not None, ta)
        limit = {'vent': 30, 'hush': 30, 'late_vent': 30, 'overheat': 120, 'probe': 120}[n]
        chk(f'ALARM within {limit} s of onset', lat is not None and lat <= limit, lat)
        chk('no ALARM before onset', all(s != 3 for t, s in sts if t < S['onset']))
        if ta:
            after = [r for r in io if ta + 1 <= r['t'] <= ta + 9]
            chk('siren sounding after ALARM (T3 pattern ~37 % on)',
                0.25 < sum(r['tone_on'] for r in after) / len(after) < 0.5,
                round(sum(r['tone_on'] for r in after) / len(after), 2))
            chk('red LED flashing in ALARM', max(r['red'] for r in after) > 0.3)
    if n == 'hush':
        quiet = [r for r in io if 342 <= r['t'] <= 418]
        chk('HUSH silences the siren', sum(r['tone_on'] for r in quiet) == 0)
        chk('red LED keeps flashing while hushed', max(r['red'] for r in quiet) > 0.3)
        loud = [r for r in io if 470 <= r['t'] <= 540]
        chk('siren returns when heat joins (it got worse)', sum(r['tone_on'] for r in loud) > 5)
    if n == 'late_vent':
        tt = [int(d['t']) for d in S['tel'] if 't' in d and 'st' in d]
        chk('telemetry every second to the end (firmware clock keeps running)',
            len(tt) > 6400 and all(b - a == 1 for a, b in zip(tt, tt[1:])), len(tt))
    if n == 'sensor_fault':
        tf = first(S, 4, after=200)
        chk('FAULT within 3 s of the sensor going silent', tf is not None and tf - 200 <= 3, tf)
        late = [r for r in io if r['t'] > tf + 1] if tf else []
        chk('amber double-blink in FAULT', late and max(r['amber'] for r in late) > 0.3)
        chk('fault chirp sounded', any(r['tone_on'] > 0 for r in late))
    if n == 'probe':
        chk('probe reading used (tpr present)', any(d.get('tpr', '-9999') != '-9999' for d in S['tel'] if 'tpr' in d))
    S['checks'] = res
    return res


def plot(S):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    tel = [d for d in S['tel'] if 'st' in d]
    t = [float(d['sim_t']) for d in tel]
    fig, ax = plt.subplots(5, 1, figsize=(10, 9), sharex=True)
    ax[0].plot(t, [int(d['tp']) / 10 for d in tel], color='#c0392b', label='pack (firmware)')
    ax[0].set_ylabel('°C')
    ax[0].legend(loc='upper left')
    ax[1].plot(t, [int(d['sraw']) for d in tel], color='#8e44ad')
    ax[1].set_ylabel('SGP40 raw')
    ax[2].plot(t, [int(d['co2']) for d in tel], color='#2c3e50')
    ax[2].set_ylabel('CO₂ ppm')
    ax[3].step(t, [int(d['st']) for d in tel], color='#e67e22', where='post')
    ax[3].set_yticks(range(5)); ax[3].set_yticklabels([ST[i] for i in range(5)])
    io = S['io']
    ax[4].fill_between([r['t'] for r in io], [r['tone_on'] for r in io], step='post', color='#e74c3c', alpha=.6, label='sounder')
    ax[4].plot([r['t'] for r in io], [r['red'] for r in io], color='#c0392b', lw=.5, label='red LED')
    ax[4].plot([r['t'] for r in io], [r['amber'] for r in io], color='#f39c12', lw=.5, label='amber LED')
    ax[4].plot([r['t'] for r in io], [r['green'] for r in io], color='#27ae60', lw=.5, label='green LED')
    ax[4].set_ylabel('outputs'); ax[4].legend(loc='upper left', fontsize=7, ncol=4)
    ax[4].set_xlabel('simulated time (s)')
    ax[0].set_title(f"{S['name']}: {S['desc']}", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, S['name'] + '.png'), dpi=110)
    plt.close(fig)


ALL = ['normal_charge', 'cleaning_spray', 'breath', 'vent', 'overheat', 'hush', 'sensor_fault', 'probe',
       'late_vent']


def one(name):
    S = run(scenario(name))
    checks(S)
    plot(S)
    return S


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    names = sys.argv[1:] or ALL
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=int(os.environ.get('JOBS', 4))) as ex:
        results = list(ex.map(one, names))
    summary, bad = {}, 0
    for S in results:
        print(f"== {S['name']}: {S['desc']}")
        print('   ' + S['harness'])
        for c in S['checks']:
            print(f"   [{'PASS' if c['ok'] else 'FAIL'}] {c['check']}" + (f"  ({c['value']})" if c['value'] is not None else ''))
            bad += not c['ok']
        summary[S['name']] = dict(desc=S['desc'], latency_s=S.get('latency'), checks=S['checks'])
    json.dump(summary, open(os.path.join(OUT, 'results.json'), 'w'), indent=1)
    print(f'{sum(len(S["checks"]) for S in results) - bad} passed, {bad} failed')
    sys.exit(1 if bad else 0)
