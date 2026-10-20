# -*- coding: utf-8 -*-
"""Behavioural ngspice models of Mesh Radio v1's power path.

TI's PSpice models for these parts are encrypted and do not run in
ngspice, so every IC here is built from its datasheet numbers (sim/README.md
lists each assumption and the datasheet it comes from).  Switching
converters are averaged (no switching ripple): what the studies need is
currents, droops, trip timing and pin voltages over microseconds to
seconds, not the converter's own ripple.

Conventions
  * every function returns netlist lines (a string) and takes a prefix `p`
    that makes its element and internal node names unique;
  * logic inside a model is held on 1 nF "state" nodes driven by B current
    sources (a latch charges toward 1 V or 0 V in ~1 us; a timer ramps at
    1/tau and is "expired" above 1 V), so comparators with hysteresis,
    deglitch filters and fault latches are continuous for the solver;
  * a logic node is true when its voltage is above 0.5 V;
  * currents that the studies report are copied onto monitor nodes
    named <prefix>_i<what> (1 V = 1 A).

Part numbers and pins follow src/circuit.py.
"""

# ------------------------------------------------------------------ temperature

TEMP = 25.0          # ambient = component temperature for every model, set by set_temp() before a build


def set_temp(t):
    global TEMP
    TEMP = float(t)


def rf():
    """On-resistance factor of every MOSFET switch: +0.4 %/C from 25 C."""
    return 1.0 + 0.004 * (TEMP - 25.0)


def ck():
    """Ceramic capacitance factor over temperature (X5R/X7R, on top of the DC-bias
    derating): -15 % at -40 and 85 C, -10 % at -20 C, -5 % at 0 and 60 C."""
    import numpy as np
    return float(np.interp(TEMP, [-40, -20, 0, 25, 60, 85], [0.85, 0.90, 0.95, 1.0, 0.95, 0.85]))


def rint_k():
    """LiPo internal-resistance factor vs 25 C: x2 at 0 C, x5 at -20 C, x9 at -40 C (the
    Arrhenius-like rise reported by Ji, Zhang & Wang, J. Electrochem. Soc. 160 (4) A636 (2013),
    extrapolated below -20 C); x0.8 / x0.75 at 60 / 85 C (the ohmic and contact part
    hardly falls, so less than Arrhenius would give)."""
    import numpy as np
    return float(np.interp(TEMP, [-40, -20, 0, 25, 60, 85], [9.0, 5.0, 2.0, 1.0, 0.8, 0.75]))


# ------------------------------------------------------------------ helpers

def lines(*ls):
    return '\n'.join(l for l in ls if l) + '\n'


def cap(name, a, b, c, esr=5e-3, esl=0.0):
    """Capacitor with ESR (and optional ESL).  `c` is the value left at the
    working DC bias at 25 C (studies pass derated values, README table); the
    temperature factor ck() is applied here."""
    c = c * ck()
    if esl:
        return lines('C%s %s %s_x %g' % (name, a, name, c),
                     'R%s %s_x %s_y %g' % (name, name, name, esr),
                     'L%s %s_y %s %g' % (name, name, b, esl))
    return lines('C%s %s %s_x %g' % (name, a, name, c), 'R%s %s_x %s %g' % (name, name, b, esr))


def rl(name, a, b, r, l=0.0):
    """Trace / cable / lead: series R (and L)."""
    if l:
        return lines('R%s %s %s_m %g' % (name, a, name, r), 'L%s %s_m %s %g' % (name, name, b, l))
    return lines('R%s %s %s %g' % (name, a, b, r))


def latch(n, set_, reset, init_leak=True):
    """State node n: driven to 1 V while set_ is true, to 0 V while reset is
    true (set wins), held otherwise.  ~1 us response."""
    return lines('C%s %s 0 1n' % (n, n), 'R%s %s 0 1e15' % (n, n) if init_leak else '',
                 'B%s 0 %s I = (%s) ? 1e-3*(1-V(%s)) : ((%s) ? -1e-3*V(%s) : 0)' % (n, n, set_, n, reset, n))


def latch_k(n, set_k='0', reset_k='0', t_rec=0.0):
    """Latch driven by continuous 0..1 strengths (used where a timer sets or
    resets it, so the latch's drive does not jump when the timer crosses).
    It holds itself once past ~0.4 V (a fault stays latched when its timer
    resets); reset wins."""
    # self-holding once past ~0.4 V - but not in the DC operating point (time = 0), where a self-holding
    # latch would have two solutions and the solver may pick the faulted one
    hold = '((time > 0) ? max(0, min(1, (V(%s) - 0.3)*5)) : 0)' % n
    pre = ''
    if t_rec:   # the release condition is only looked at after a recovery delay (BQ2970x note 1)
        pre = timer(n + 'r', 'V(%s) > 0.5' % n, t_rec)
        reset_k = '(%s)*%s' % (reset_k, expired(n + 'r'))
    # The self-hold drives only 1 uA (against 10 Meg to ground it holds a set latch at ~0.9 V): with the
    # full 1 mA, a long solver step could find the latch's other (set) solution with nothing setting it -
    # it did, at a charger start-up, latching the USB eFuse's OVLO with VBUS at 5.0 V.  Set and reset act
    # at 1 mA (about 1 us).
    return pre + lines('C%s %s 0 1n' % (n, n), 'R%s %s 0 10Meg' % (n, n),
                 'B%s 0 %s I = 1e-3*((%s)*(1-V(%s))*(1-(%s)) - (%s)*V(%s)) + 1e-6*%s*(1-V(%s))*(1-(%s))'
                 % (n, n, set_k, n, reset_k, reset_k, n, hold, n, reset_k))


def expired(n):
    """Continuous 'timer n has expired' (0 below 1.0 V, 1 above 1.05 V)."""
    return 'max(0, min(1, (V(%s) - 1)*20))' % n


def b(cond):
    return '((%s) ? 1 : 0)' % cond


def timer(n, cond, tau):
    """Timer node n: ramps 0 -> 1.2 V at 1 V per tau while cond is true,
    resets in ~1 us when it is false.  'Expired' = V(n) > 1.  Timers are held
    at zero in the DC operating point (time = 0), so no fault starts latched."""
    return lines('C%s %s 0 1n' % (n, n), 'R%s %s 0 1G' % (n, n),
                 'B%s 0 %s I = (time > 0 && (%s)) ? (1n/%g)*max(0, min(1, (1.2-V(%s))*20)) : -1e-3*V(%s)' % (n, n, cond, tau, n, n))


def mn(*a):
    """min() of any number of expressions (ngspice's min takes two)."""
    return a[0] if len(a) == 1 else 'min(%s, %s)' % (a[0], mn(*a[1:]))


def sat(x):
    """Clamp an expression to 0..1: logic nodes are used as continuous
    multipliers (they move 0 <-> 1 in about a microsecond), so no current
    in the netlist jumps discontinuously and the solver never chatters."""
    return 'max(0, min(1, %s))' % x


def gate(n, target, tau=2e-6):
    """Node n slews toward target (0 or 1 expression) with time constant tau:
    the turn-on / turn-off of a power switch's gate."""
    return lines('C%s %s 0 1n' % (n, n), 'R%s %s 0 1G' % (n, n),
                 'B%s 0 %s I = (1e-9/%g)*(((%s) ? 1 : 0) - V(%s))' % (n, n, tau, target, n))


def mon(n, expr):
    """Monitor node n = expr (1 V per unit), through 1 k so it never loads."""
    return lines('B%s %s 0 V = %s' % (n, n, expr), 'R%s %s 0 1Meg' % (n, n))


# ------------------------------------------------------------------ diodes and passive models

_MODELS = """
* RB060MM-30 Schottky: VF 0.30 V @ 0.1 A (assumed), 0.40 V @ 1 A, 0.46 V @ 2 A (datasheet typ 0.40/0.44); VR 30 V
.model DRB060 D (IS=2.8e-6 N=1.1 RS=0.039 BV=30 IBV=50e-6 CJO=120p EG=0.69 XTI=2)
* TVS2200 flat clamp: VBR 24.6 / 25.9 / 27.6 V (min / typ / max at 1 mA); the clamp barely rises with current
* (VCLAMP 27.2 typ / 27.7 max at 24 A, 28.0 max at 40 A): sharp knee + 5 mOhm; 105 pF; VF 0.5 V;
* VBR +6.5 mV/C (from VCLAMP 28.35 V max at 125 C vs 27.7 V at 27 C), applied in models()
.model DTVS_TYP D (IS=1e-12 N=1.9 RS=0.005 BV={BV_TYP} IBV=1e-3 NBV=1 CJO=105p)
.model DTVS_MAX D (IS=1e-12 N=1.9 RS=0.005 BV={BV_MAX} IBV=1e-3 NBV=0.6 CJO=105p)
.model DTVS_MIN D (IS=1e-12 N=1.9 RS=0.005 BV={BV_MIN} IBV=1e-3 NBV=1 CJO=105p)
* UDZV4.7B zener (EN clamp): VZ 4.55-4.75 V @ 5 mA, ZZ 100 ohm, soft knee (ZZK 800 ohm @ 0.5 mA);
* reverse leakage below the knee is a separate resistor/current in efuse() (datasheet IR <= 2 uA @ 1 V)
.model DZ47 D (IS=1e-14 N=1 RS=20 BV=4.65 IBV=5e-3 NBV=2.8 CJO=60p)
* UDZV5.6B zener (USB EN clamp since 19 Oct): VZ 5.49-5.73 V @ 5 mA (5.73 used: the EN abs-max check), ZZ 60 ohm,
* +2 mV/C (assumed); IR <= 1 uA at 2.5 V, so nothing at the 1.2 V EN threshold
.model DZ56 D (IS=1e-14 N=1 RS=12 BV={BVZ56} IBV=5e-3 NBV=1.6 CJO=50p)
* body diodes
.model DBODY D (IS=1e-9 N=1.4 RS=0.01 CJO=200p)
.model DLM_BODY D (IS=1e-8 N=1.6 RS=0.05)
* generic substrate / ESD diode on an IC pin
.model DESD D (IS=1e-14 N=1 RS=1)
* CSD25485F5 -20 V P-FET: Vth -0.95 V, RDS(on) 35 mOhm @ -4.5 V (level 1: KP*W/L = 8.05 A/V^2)
.model PREV PMOS (LEVEL=1 VTO=-0.95 KP={KPREV} LAMBDA=0.01 IS=1e-30 CGSO=0 CGDO=0)
* SSM10N954L protector half (one of the two common-drain N-FETs): RSS(on) 2.75 mOhm for both,
* 1.375 mOhm each at VGS 3.7 V, Vth ~0.8 V (assumed)
.model NPROT NMOS (LEVEL=1 VTO=0.8 KP={KPROT} LAMBDA=0.01 IS=1e-30)
.model SWI SW (VT=0.5 VH=0.05 RON=1m ROFF=1G)
* --- parts added by the 19 Oct power-path fixes ---
* CSD25310Q2(T) -20 V P-FET (reverse FET): Vth -0.85 V, RDS(on) typ 27 / 19.9 mOhm at -2.5 / -4.5 V.  Level 1
* fitted at VGS -3.5 V (22 mOhm): KP 17.2 A/V^2 (35 mOhm at -2.5 V, 16 mOhm at -4.5 V)
.model PREV2 PMOS (LEVEL=1 VTO=-0.85 KP={KPREV2} LAMBDA=0.01 IS=1e-30 CGSO=0 CGDO=0)
* SSM3K56ACT N-FET (cell-polarity check, PR1 pull-down): Vth 0.4-1.0 V (0.7 used), ~0.3 ohm at 3.7 V
.model NSIG NMOS (LEVEL=1 VTO=0.7 KP=1 LAMBDA=0.01 IS=1e-30)
* SMF33CA bidirectional TVS (two junctions back to back): VBR 36.7 / 40.6 V min / max at 1 mA, VC 53.3 V at
* 3.8 A (~3.3 ohm); +0.1 %/C (assumed, typical of a 33 V avalanche junction).  BV is VBR less the other junction's
* forward drop.
.model DSMF_MIN D (IS=1e-12 N=1.5 RS=1.6 BV={BVS_MIN} IBV=1e-3 CJO=300p)
.model DSMF_MAX D (IS=1e-12 N=1.5 RS=1.6 BV={BVS_MAX} IBV=1e-3 CJO=300p)
"""


def models():
    """The model cards at the current temperature.  Diodes follow the global
    .temp (Schottky VF and leakage through EG/XTI, the TVS breakdown at +6.5 mV/C
    from its datasheet clamp at 27 and 125 C, the 4.7 V zener taken as flat);
    the MOSFETs are pinned at 25 C internally (instance temp=25) and their KP is
    divided by rf() instead, so RDS(on) rises 0.4 %/C as specified."""
    return ('.temp %g\n.options tnom=25\n' % TEMP +
            _MODELS.replace('{KPREV}', '%g' % (8.05 / rf())).replace('{KPROT}', '%g' % (250.0 / rf()))
            .replace('{BV_TYP}', '%g' % (25.9 + 6.5e-3 * (TEMP - 25)))
            .replace('{BV_MAX}', '%g' % (27.6 + 6.5e-3 * (TEMP - 25)))
            .replace('{BV_MIN}', '%g' % (24.6 + 6.5e-3 * (TEMP - 25)))
            .replace('{KPREV2}', '%g' % (17.2 / rf()))
            .replace('{BVZ56}', '%g' % (5.73 + 2e-3 * (TEMP - 25)))
            .replace('{BVS_MIN}', '%g' % (36.7 * (1 + 1e-3 * (TEMP - 25)) - 0.6))
            .replace('{BVS_MAX}', '%g' % (40.6 * (1 + 1e-3 * (TEMP - 25)) - 0.6)))



def schottky(p, a, k):
    return lines('D%s %s %s DRB060' % (p, a, k))


def tvs2200(p, node, corner='MAX'):
    """TVS2200 from node to GND; its current (node -> GND) is i(V<p>am)."""
    return lines('D%s %sa %s DTVS_%s' % (p, p, node, corner), 'V%sam %sa 0 0' % (p, p))


# ------------------------------------------------------------------ cell and battery block

def smf33ca(p, node, corner='MAX'):
    """SMF33CA bidirectional TVS from node to GND; its current (node -> GND) is i(V<p>am)."""
    return lines('D%sa %s %s_m DSMF_%s' % (p, node, p, corner), 'D%sb %sa %s_m DSMF_%s' % (p, p, p, corner),
                 'V%sam %sa 0 0' % (p, p))


def cell(p, pos, neg, ocv, rint, rlead=0.020, llead=0.1e-6, plug_t=None, reverse=False):
    """One LiPo cell: OCV behind its internal resistance (the DC resistance a
    1 s burst sees; no RC polarisation, the conservative choice), then two
    leads of rlead / llead each (JST-PH contact ~10 mOhm + ~7 cm of 26 AWG,
    ~0.1 uH each).  pos / neg are the board pads (BATT_PLUS / CELL_MINUS).
    plug_t: the cell is connected at that time (a switch).  reverse: plugged
    in backwards."""
    a, b = (neg, pos) if reverse else (pos, neg)
    s = lines('V%s_ocv %s_p %s_n %g' % (p, p, p, ocv),
              'R%s_int %s_p %s_r %g' % (p, p, p, rint),
              'R%s_lp %s_r %s_lp %g' % (p, p, p, rlead), 'L%s_lp %s_lp %s_q %g' % (p, p, p, llead),
              'R%s_ln %s_n %s_ln %g' % (p, p, p, rlead), 'L%s_ln %s_ln %s %g' % (p, p, b, llead))
    if plug_t is None:
        s += lines('V%s_am %s_q %s 0' % (p, p, a))
    else:
        s += lines('V%s_ctl %s_ctl 0 pwl(0 0 %g 0 %g 1)' % (p, p, plug_t, plug_t + 1e-7),
                   'S%s %s_q %s_s %s_ctl 0 SWI' % (p, p, p, p),
                   'V%s_am %s_s %s 0' % (p, p, a))
    return s   # cell current (out of its + lead into the board) = i(V<p>_am)


PROT = dict(ovp=4.275, ovp_t=1.25, uvp=2.80, uvp_t=0.144, ocd=0.100, ocd_t=0.020, scd=0.500, scd_t=250e-6,
            occ=-0.100, occ_t=0.008, rss=2.75e-3, rsense=15e-3)   # 15 mOhm since 19 Oct (was 22)


def battery_block(p, lm='tps', prot=None, lm_ron=0.079, trace_bat=(0.006, 6e-9), rev='v2', on='1'):
    """src/circuit.py charger(): JST pads BATT_PLUS / CELL_MINUS, the
    CSD25485F5 reverse P-FET (gate 100 k to CELL_MINUS), the BQ29700 + SSM10N954L
    + 22 mOhm protector on the minus side, the LM66100 from BAT_P to VSYS
    (lm='gnd': CE tied to GND as drawn; lm='vout': CE tied to VSYS, the
    datasheet's ideal-diode connection) and the 1 M / 1.5 M battery sense.

    Since the 19 Oct fixes (rev='v2', lm='tps', the defaults): the reverse
    FET is a CSD25310Q2 whose gate is pulled up to BAT_P (1 M) and pulled
    down to CELL_MINUS by an SSM3K56ACT whose gate is BATT_PLUS (1 M from
    BATT_PLUS to CELL_MINUS keeps it off with no cell), and the cell-to-SYS
    path is a TPS22950 (on = the power switch, expression `on`) then an
    RB060MM Schottky (BYP_OUT -> VSYS) that blocks SYS from charging the cell.

    BQ29700 behaviour (SLUSBU9I): supply valid above BAT-VSS 1.5 V; OVP
    BAT-VSS > ovp for ovp_t -> COUT low; UVP < uvp for uvp_t -> DOUT low
    (release: > uvp + 0.1 V and BAT - V- > 1 V); OCD V- - VSS > ocd for ocd_t
    and SCD > scd for scd_t -> DOUT low (release BAT - V- > 1 V); OCC
    V- - VSS < occ for occ_t -> COUT low.  DOUT swings VSS..BAT, COUT
    V-..BAT, through 10 k into the FET gates (gate charge ignored: ~1 us
    turn-off is assumed, the datasheet gives none).  V- has the 16 uA
    sink to VSS while an OCD/SCD fault is latched (load-release detection)
    and the 300 k pull-up to BAT in the over-discharge state (charger
    detection); neither in normal operation (assumed from SLUSBU9I 6.5).
    ESD diodes VSS->BAT and V-->BAT (abs max BAT >= VSS - 0.3 V,
    V- <= BAT + 0.3 V) carry the reported pin currents."""
    q = dict(PROT)
    q.update(prot or {})
    k = p
    vb = 'V(PROT_BAT,CELL_MINUS)'
    vm = 'V(PROT_VM,CELL_MINUS)'
    if rev == 'v2':
        revfet = lines('* --- reverse-battery P-FET CSD25310Q2 (D = BATT_PLUS, S = BAT_P_C, G = REV_G), off unless',
                       '*     the polarity check (SSM3K56ACT, G = BATT_PLUS, S = CELL_MINUS) pulls REV_G down',
                       'M%srev BATT_PLUS REV_G BAT_P_C BAT_P_C PREV2 temp=25' % k,
                       'D%srevb BATT_PLUS BAT_P_C DBODY' % k,
                       'R%srevg REV_G BAT_P_C 1Meg' % k, 'C%srevc REV_G BAT_P_C 650p' % k,
                       'M%spol REV_G POL_G CELL_MINUS CELL_MINUS NSIG temp=25' % k,
                       'C%spolc BATT_PLUS CELL_MINUS 50p' % k,
                       'R%spolr BATT_PLUS POL_G 100k' % k, 'C%spolg POL_G CELL_MINUS 100n' % k,   # gate filter, 10 ms
                       # gate clamp since 20 Oct (UDZVTE-174.7B, K = POL_G): |VGS| <= 4.7 V / 0.7 V
                       'D%spolz CELL_MINUS POL_G DZ47' % k,
                       'R%spold BATT_PLUS CELL_MINUS 1Meg' % k)
    else:
        revfet = lines('* --- reverse-battery P-FET (D = BATT_PLUS, S = BAT_P_C, G = REV_G)',
                       'M%srev BATT_PLUS REV_G BAT_P_C BAT_P_C PREV temp=25' % k,
                       'D%srevb BATT_PLUS BAT_P_C DBODY' % k,
                       'R%srevg REV_G CELL_MINUS 100k' % k, 'C%srevc REV_G BAT_P_C 400p' % k)
    s = lines(
        revfet,
        '* gate ESD: back-to-back zeners, assumed +-14 V',
        'D%sgz1 REV_G %s_gz DZ14' % (k, k), 'D%sgz2 BAT_P_C %s_gz DZ14' % (k, k),
        '.model DZ14 D (IS=1e-14 BV=14 IBV=1e-6)',
        rl(k + 'tb', 'BAT_P_C', 'BAT_P', *trace_bat),
        '* --- BQ29700 cell protector',
        'R%sprb BAT_P PROT_BAT 330' % k, cap(k + 'cprb', 'PROT_BAT', 'CELL_MINUS', 100e-9),
        'V%samvss %s_vss CELL_MINUS 0' % (k, k),
        'B%siq PROT_BAT %s_vss I = %s > 1.5 ? 4e-6 : 0' % (k, k, vb),
        'D%sesd1 %s_vss PROT_BAT DESD' % (k, k),
        'V%samvm PROT_VM %s_vm 0' % (k, k),
        'D%sesd2 %s_vm PROT_BAT DESD' % (k, k),
        'R%svm PROT_VM 0 2.2k' % k,
        latch(k + 'val', '%s > 1.5' % vb, '%s < 1.4' % vb),
        timer(k + 'tovp', '%s > %g' % (vb, q['ovp']), q['ovp_t']),
        latch_k(k + 'ovp', expired(k + 'tovp'), b('%s < %g' % (vb, q['ovp'] - 0.1)), 12e-3),
        timer(k + 'tuvp', '%s < %g' % (vb, q['uvp']), q['uvp_t']),
        latch_k(k + 'uvp', expired(k + 'tuvp'), b('%s > %g && (%s - %s) > 1' % (vb, q['uvp'] + 0.1, vb, vm)), 8e-3),
        timer(k + 'tocd', '%s > %g && V(%socd) < 0.5' % (vm, q['ocd'], k), q['ocd_t']),
        timer(k + 'tscd', '%s > %g && V(%socd) < 0.5' % (vm, q['scd'], k), q['scd_t']),
        latch_k(k + 'ocd', 'max(%s, %s)' % (expired(k + 'tocd'), expired(k + 'tscd')), b('(%s - %s) > 1' % (vb, vm)), 8e-3),
        latch_k(k + 'scdf', expired(k + 'tscd'), '0'),
        timer(k + 'tocc', '%s < %g' % (vm, q['occ']), q['occ_t']),
        latch_k(k + 'occ', expired(k + 'tocc'), b('%s > %g' % (vm, q['occ'] + 0.04)), 8e-3),
        'B%sdo %s_do CELL_MINUS V = (V(%sval) > 0.5 && V(%suvp) < 0.5 && V(%socd) < 0.5) ? max(%s, 0) : 0'
        % (k, k, k, k, k, vb),
        'R%sdo %s_do PROT_DOUT 10k' % (k, k), 'C%sgd PROT_DOUT CELL_MINUS 2n' % k,
        'B%sco %s_co PROT_VM V = (V(%sval) > 0.5 && V(%sovp) < 0.5 && V(%socc) < 0.5) ? max(V(PROT_BAT,PROT_VM), 0) : 0'
        % (k, k, k, k, k),
        'R%sco %s_co PROT_COUT 10k' % (k, k), 'C%sgc PROT_COUT PROT_S2 2n' % k,
        'B%svmsk %s_vm %s_vss I = (V(%sval) > 0.5 && V(%socd) > 0.5) ? 16e-6 : 0' % (k, k, k, k, k),
        'B%svmpu PROT_BAT %s_vm I = (V(%sval) > 0.5 && V(%suvp) > 0.5 && V(%socd) < 0.5) ? V(PROT_BAT,%s_vm)/300k : 0'
        % (k, k, k, k, k, k),
        '* --- SSM10N954L: DSG FET (S1 = CELL_MINUS, G1 = DOUT), CHG FET (S2 = PROT_S2, G2 = COUT), common drain',
        'M%sdsg PROT_D PROT_DOUT CELL_MINUS CELL_MINUS NPROT temp=25' % k,
        'D%sdsgb CELL_MINUS PROT_D DBODY' % k,
        'M%schg PROT_D PROT_COUT PROT_S2 PROT_S2 NPROT temp=25' % k,
        'D%schgb PROT_S2 PROT_D DBODY' % k,
        'R%ssns PROT_S2 %s_gnd %g' % (k, k, q['rsense']),
        'V%samgnd %s_gnd 0 0' % (k, k),
        '* --- battery sense 1 M / 1.5 M',
        'R%sbs1 BAT_P VBAT_SENSE 1Meg' % k, 'R%sbs2 VBAT_SENSE 0 1.5Meg' % k,
        (tps22950(k + 'lm', 'BAT_P', 'BYP_OUT', on) + schottky(k + 'byd', 'BYP_OUT', 'VSYS') + 'R%sbyp BYP_OUT 0 10Meg\n' % k)
        if lm == 'tps' else lm66100(k + 'lm', 'BAT_P', 'VSYS', lm, lm_ron),
    )
    return s


def tps22950(p, vin, vout, on='1', rilim=1150.0, ron=0.041):
    """TPS22950 (SLVSFJ2B) load switch, VIN = BAT_P, VOUT = VSYS (the cell bypass): RON 41 mOhm typ at
    3.3 V (+0.4 %/C), current limit 1.18 x RILIM[k]^-1.072 = 1.02 A for 1.15 k (0.75-1.25 A), acting in
    ~5 us (taken as instant); turn-on ramp ~0.55 ms (tON at 3.3 V, an RC here); reverse current blocking:
    off when VOUT > VIN + 44 mV, on again below VIN + 16 mV (3 us), so up to ~1 A can flow backwards
    while VOUT is less than 44 mV above VIN; 40 uA quiescent while on.  Monitor <p>_i (VIN -> VOUT)."""
    ron = ron * rf()
    ilim = 1.18 * (rilim / 1000.0) ** -1.072
    V = lambda n: 'V(%s)' % n
    return lines(
        latch(p + 'rcb', '%s > %s + 0.044' % (V(vout), V(vin)), '%s < %s + 0.016' % (V(vout), V(vin))),
        gate(p + 'g', '(%s) && %s > 1.6' % (on, V(vin)), 0.2e-3),
        mon(p + '_i', '%s*(1 - %s)*max(-%g, min(%g, V(%s,%s)/%g))' % (sat('V(%sg)' % p), sat('V(%srcb)' % p), ilim, ilim,
                                                                    vin, vout, ron)),
        'B%s %s %s I = V(%s_i)' % (p, vin, vout, p),
        'B%sq %s 0 I = 40e-6*%s*%s' % (p, vin, sat('V(%sg)' % p), sat(V(vin))),
    )


def lm66100(p, vin, vout, mode, ron=0.079):
    ron = ron * rf()
    """LM66100: P-FET switch with body diode VIN->VOUT and reverse-polarity
    protection.  mode 'gnd' (CE = GND, as drawn): ON whenever VIN > CE +
    0.25 V, i.e. a plain bidirectional switch - it does NOT block current
    from VOUT back into VIN (datasheet 8.3.2: reverse blocking needs CE =
    VOUT).  mode 'vout' (CE = VOUT): on when VOUT < VIN - 0.15 V (VON),
    off when VOUT > VIN + 0.035 V (VOFF typ) - so up to ~0.44 A (35 mV /
    79 mOhm; IRCB 0.5-1 A in the datasheet) can still flow backwards while
    the source cannot lift VOUT 35 mV above VIN.  mode 'diode': a Schottky
    (RB060MM) instead of the LM66100; its current is not on the monitor.  Monitor <p>_i = VIN->VOUT
    current through the channel (body diode excluded)."""
    if mode == 'diode':
        # proposed alternative: a Schottky (RB060MM) in place of the LM66100
        return lines('D%sd %s %s DRB060' % (p, vin, vout), mon(p + '_i', '0'))
    if mode == 'gnd':
        s = ''
        k = sat('(V(%s) - 0.15)/0.2' % vin)
    else:
        s = latch(p + 'st', 'V(%s) < V(%s) - 0.15 && V(%s) > 1.0' % (vout, vin, vin),
                  'V(%s) > V(%s) + 0.035 || V(%s) < 0.9' % (vout, vin, vin))
        k = sat('V(%sst)' % p)
    s += lines(mon(p + '_i', '%s*V(%s,%s)/%g' % (k, vin, vout, ron)),
               'B%s %s %s I = V(%s_i)' % (p, vin, vout, p),
               'D%sb %s %s DLM_BODY' % (p, vin, vout))
    return s


# ------------------------------------------------------------------ charger

# ichg 300 mA: ISET 1 k since 19 Oct (was 604 R, 497 mA); precharge 20 % of it
CHG = dict(ilim=1.05, ron_in=0.40, ron_bat=0.130, vsys=4.5, vreg=4.2, ichg=0.300, iprech=0.060, itrickle=0.007,
           buvlo=3.0, buvlo_hys=0.15, buvlo_t=60e-6, batocp=3.13, vdpm_track=0.33, vdpm_min=3.6, ce=1, ts=1,
           rth=68.3)


def bq25185(p, vin, sys, bat, cfg=None):
    """BQ25185 power path, averaged (SLUSF65B):
      IN -> SYS: SYS regulated to 4.5 V (VBATREG 4.2 V <= 4.3 V), input
        current limit ILIM 1.05 A (0.995-1.1), input FET 330-470 mOhm,
        VINDPM = VBAT + 330 mV (VBAT > 3.5 V) else 3.6 V: input current is
        cut back to hold VIN there.  Valid input: VIN > 3.15 V and > VBAT +
        152 mV (sleep exit), < 18.5 V (OVP).
      SYS -> BAT (charging, /CE low, TS ok): CC 497 mA (ISET 604 R),
        precharge 20 % below 3.0 V, trickle 7 mA below 1.8 V, CV 4.2 V;
        DPPM cuts charge current when SYS falls to VBAT + 100 mV.
      BAT -> SYS (battery FET 115-140 mOhm): supplement when SYS < VBAT -
        40 mV with an input, fully on without one; off when VBAT < BUVLO
        3.0 V for 60 us (BUVLO, back on above 3.15 V); BATOCP 3.13 A ->
        off 250 ms (10 us response assumed).
    Thermal regulation (TREG 100 C) is static: the charge current is limited so
    TA + 68.3 C/W x P stays at 100 C (TA = the study's ambient).
    Not modelled: thermal-shutdown, safety timers, termination toggling,
    TS/MR button timer, ship mode, SYS-short hiccup."""
    c = dict(CHG)
    c.update(cfg or {})
    c['ron_in'] *= rf()
    c['ron_bat'] *= rf()
    V = lambda n: 'V(%s)' % n
    s = lines(
        latch(p + 'ok', '%s > 3.15 && %s > %s + 0.152 && %s < 18.5' % (V(vin), V(vin), V(bat), V(vin)),
              '%s < 2.95 || %s < %s + 0.082 || %s > 18.5' % (V(vin), V(vin), V(bat), V(vin))),
        timer(p + 'tbuv', '%s < %g' % (V(bat), c['buvlo']), c['buvlo_t']),
        latch_k(p + 'buv', b('%s > %g' % (V(bat), c['buvlo'] + c['buvlo_hys'])), expired(p + 'tbuv')),
        latch_k(p + 'buvf', expired(p + 'tbuv'), '0'),
        timer(p + 'tocp', 'V(%s_isup) > %g' % (p, c['batocp']), 10e-6),
        timer(p + 'tocpr', 'V(%socp) > 0.5' % p, 0.25),
        latch_k(p + 'ocp', expired(p + 'tocp'), expired(p + 'tocpr')),
        latch(p + 'trk', '%s > 3.5' % V(bat), '%s < 3.4' % V(bat)),
        latch(p + 'lowv', '%s < 2.9' % V(bat), '%s > 3.0' % V(bat)),
        latch(p + 'bsc', '%s < 1.6' % V(bat), '%s > 1.8' % V(bat)),
        mon(p + '_vdpm', 'V(%strk) > 0.5 ? max(%g, %s + %g) : %g' % (p, c['vdpm_min'], V(bat), c['vdpm_track'], c['vdpm_min'])),
        mon(p + '_iin', '%s*max(0, %s)' % (sat('V(%sok)' % p), mn(
            '%g*max(0, min(1, (%s - V(%s_vdpm))/0.05))' % (c['ilim'], V(vin), p),
            '20*(%g - %s)' % (c['vsys'], V(sys)), '(%s - %s)/%g' % (V(vin), V(sys), c['ron_in'])))),
        mon(p + '_ichg', '%s*%g*%g*max(0, %s)' % (sat('V(%sok)' % p), c['ce'], c['ts'], mn(
            '(%g*%s + (1 - %s)*(%g*%s + %g*(1 - %s)))' % (c['itrickle'], sat('V(%sbsc)' % p), sat('V(%sbsc)' % p),
                                                      c['iprech'], sat('V(%slowv)' % p), c['ichg'], sat('V(%slowv)' % p)),
            '20*(%g - %s)' % (c['vreg'], V(bat)), '10*(%s - %s - 0.1)' % (V(sys), V(bat)),
            '(%s - %s)/%g' % (V(sys), V(bat), c['ron_bat']),
            # TREG: the charge current is cut so the die stays at 100 C (RthJA 68.3 C/W JEDEC, static)
            'max(0, %g - (%s - %s)*V(%s_iin))/max(%s - %s, 0.05)' % ((100.0 - TEMP) / c['rth'], V(vin), V(sys), p,
                                                                   V(sys), V(bat))))),
        mon(p + '_isup', '%s*(1 - %s)*max(0, %s - %s - 0.04*%s)/%g'
            % (sat('V(%sbuv)' % p), sat('V(%socp)' % p), V(bat), V(sys), sat('V(%sok)' % p), c['ron_bat'])),
        'B%sin %s %s I = V(%s_iin)' % (p, vin, sys, p),
        'B%siq %s 0 I = %s > 3 ? 0.75e-3 : 0' % (p, vin, V(vin)),
        'B%sch %s %s I = V(%s_ichg)' % (p, sys, bat, p),
        'B%ssu %s %s I = V(%s_isup)' % (p, bat, sys, p),
        'B%sbq %s 0 I = 4e-6*%s' % (p, bat, sat('V(%s)' % bat)),
        'D%sesdb %sesb %s DESD' % (p, p, bat), 'V%sesb %sesb 0 0' % (p, p),
        'D%sesds %sess %s DESD' % (p, p, sys), 'V%sess %sess 0 0' % (p, p), 'D%sesdi 0 %s DESD' % (p, vin),
    )
    return s


# ------------------------------------------------------------------ amplifier supply

# PR1 562 k / 374 k since 19 Oct (was 301 k): IN1 priority down to 2.60 V
MUX = dict(ron=0.059, ilm=4.5, iss=0.4, tss=0.7e-3, tsw=100e-6, pr_ratio=374.0 / (562 + 374), vcomp=0.28)


def tps2121(p, in1, in2, out, en='1', cfg=None):
    """TPS2121 (SLVSEA3F), CP2 grounded (as drawn): IN1 = BAT_P has priority
    while PR1 = 0.349 x VIN1 > 1.06 V (falls at 1.04 V: 3.04 / 2.98 V on
    BAT_P); below that the higher input wins (VCOMP: IN1 only if it is
    280 mV above IN2).  Changing input leaves OUT open for tSW = 100 us
    (CP2 < VREF; Fig 9-8/9-9 show OUT sagging at IOUT/COUT through it).
    Each channel 59 mOhm, forward only (reverse blocking), current limit
    4.5 A (RILM 22.1 k).  Soft start after enable (CSS 10 nF, ~7.8 V/ms
    into ~35 uF): modelled as a 0.4 A limit for the first 0.7 ms.  UV
    2.65 / 2.55 V per input.  en = PA_PWR_EN (OV1/
    OV2 pulled low).  Monitors <p>_i1, <p>_i2, <p>_sel (1 = IN1, 2 = IN2)."""
    c = dict(MUX)
    c.update(cfg or {})
    c['ron'] *= rf()
    V = lambda n: 'V(%s)' % n
    want1 = '(%s) && V(%sv1) > 0.5 && (V(%spr) > 0.5 || V(%sv2) < 0.5 || V(%svc) > 0.5)' % (en, p, p, p, p)
    want2 = '(%s) && V(%sv2) > 0.5 && !(%s)' % (en, p, want1)
    s = lines(
        latch(p + 'v1', '%s > 2.65' % V(in1), '%s < 2.55' % V(in1)),
        latch(p + 'v2', '%s > 2.65' % V(in2), '%s < 2.55' % V(in2)),
        latch(p + 'pr', '%g*%s > 1.06' % (c['pr_ratio'], V(in1)), '%g*%s < 1.04' % (c['pr_ratio'], V(in1))),
        latch(p + 'vc', '%s > %s + %g' % (V(in1), V(in2), c['vcomp']), '%s < %s + %g' % (V(in1), V(in2), c['vcomp'] * 0.3)),
        timer(p + 't1', want1, c['tsw']), timer(p + 't2', want2, c['tsw']),
        timer(p + 'ss', en, c['tss']),
        gate(p + 'g1', '(%s) && V(%st1) > 1' % (want1, p)),
        gate(p + 'g2', '(%s) && V(%st2) > 1' % (want2, p)),
        mon(p + '_on1', sat('V(%sg1)' % p)), mon(p + '_on2', sat('V(%sg2)' % p)),
        mon(p + '_ilm', '%g + %g*%s' % (c['iss'], c['ilm'] - c['iss'], sat('(V(%sss) - 0.9)*10' % p))),
        mon(p + '_i1', 'V(%s_on1)*max(0, min(V(%s_ilm), %s/%g))' % (p, p, 'V(%s,%s)' % (in1, out), c['ron'])),
        mon(p + '_i2', 'V(%s_on2)*max(0, min(V(%s_ilm), %s/%g))' % (p, p, 'V(%s,%s)' % (in2, out), c['ron'])),
        mon(p + '_sel', 'V(%s_on1) > 0.5 ? 1 : (V(%s_on2) > 0.5 ? 2 : 0)' % (p, p)),
        'B%s1 %s %s I = V(%s_i1)' % (p, in1, out, p),
        'B%s2 %s %s I = V(%s_i2)' % (p, in2, out, p),
        'B%sq1 %s 0 I = (15e-6 + 0.285e-3*V(%s_on1))*%s' % (p, in1, p, sat('V(%s)' % in1)),
        'B%sq2 %s 0 I = (15e-6 + 0.285e-3*V(%s_on2))*%s' % (p, in2, p, sat('V(%s)' % in2)),
    )
    return s


BB = dict(eff=0.92, gm=20.0, iin_boost=4.7, iout_buck=3.5, uvlo_on=2.1, uvlo_off=1.9, ss=3.3e3, vdefault=3.3)


def tps63810(p, vin, vout, en, vset, cfg=None):
    """TPS63810 buck-boost (SLVSEK4C), averaged: output regulated to vset
    (soft-start 3.3 V/ms assumed), loop transconductance 20 A/V (with ~45 uF
    effective at VPA: ~70 kHz, in the range of a 2 MHz peak-current-mode
    converter), efficiency 92 % (flat), input current = POUT / (0.92 VIN).
    Current limit from the switch limit minimums: 5.2 A boost (4.7 A average
    input after half the ~1 A ripple), 3.8 A buck (3.5 A output), joined as
    IOUT <= min(3.5 A, 4.7 A x 0.92 x VIN / VOUT).  UVLO 2.1 V
    rising / 1.9 V falling; a UVLO resets the I2C registers, after which the
    output setting is the 3.3 V default (VSEL low) - flagged on <p>rst.
    Monitors <p>_iout, <p>_iin."""
    c = dict(BB)
    c.update(cfg or {})
    c['eff'] = 1 - (1 - c['eff']) * rf()        # conduction losses grow with RDS(on): 92 % -> ~90 % at 85 C
    V = lambda n: 'V(%s)' % n
    s = lines(
        latch(p + 'on', '(%s) && %s > %g' % (en, V(vin), c['uvlo_on']), '!(%s) || %s < %g' % (en, V(vin), c['uvlo_off'])),
        latch(p + 'was', 'V(%son) > 0.5' % p, '0'),
        latch(p + 'rst', '(%s) && %s < %g && V(%swas) > 0.5' % (en, V(vin), c['uvlo_off'] + 0.01, p), '0'),
        mon(p + '_vt', 'V(%srst) > 0.5 ? %g : %g' % (p, c['vdefault'], vset)),
        'C%sref %sref 0 1n' % (p, p), 'R%sref %sref 0 1G' % (p, p),
        'B%sref 0 %sref I = V(%son) > 0.5 ? 1n*max(-1e4, min(%g, (V(%s_vt) - V(%sref))*1e6)) : -1e-3*V(%sref)'
        % (p, p, p, c['ss'], p, p, p),
        mon(p + '_imax', 'min(%g, %g*%g*max(%s, 0)/max(%s, 0.5))' % (c['iout_buck'], c['iin_boost'], c['eff'], V(vin), V(vout))),
        mon(p + '_iout', '%s*max(-0.35, min(V(%s_imax), %g*(V(%sref) - %s)))' % (sat('V(%son)' % p), p, c['gm'], p, V(vout))),
        mon(p + '_iin', 'V(%s_iout)*max(%s, 0)/(%g*max(%s, 0.8)) + 5e-5*%s*%s' % (p, V(vout), c['eff'], V(vin), sat('V(%son)' % p), sat(V(vin)))),
        'B%so 0 %s I = V(%s_iout)' % (p, vout, p),
        'B%si %s 0 I = V(%s_iin)' % (p, vin, p),
    )
    return s


def qpa9510(p, vcc, apc, rf, vnom, inom, iq=0.208):
    """QPA9510 supply current: standby 58 uA; APC on (PA_EN) with no RF: 208
    mA quiescent; with RF: inom (the total at vnom: 1.0 A @ 2.7 V / 30 dBm,
    1.7-2.0 A @ 3.6 V / 34 dBm, 2.3 A @ 4.0 V / 35 dBm).  A saturated PA's
    current falls with its supply: current scales as VCC / vnom below vnom.
    apc, rf: expressions 0..1 (rf ramps in 40 us, the SX1262 ramp)."""
    return lines('B%s %s 0 I = ((%s)*(%g + (%s)*(%g)) + 58e-6)*min(1, max(V(%s), 0)/%g)'
                 % (p, vcc, apc, iq, rf, inom - iq, vcc, vnom),
                 mon(p + '_i', '((%s)*(%g + (%s)*(%g)) + 58e-6)*min(1, max(V(%s), 0)/%g)' % (apc, iq, rf, inom - iq, vcc, vnom)))


# ------------------------------------------------------------------ system rail

def system_rail(p, vsys='VSYS', vsw='VSYS_SW', v3='3V3', iload='0.013', sw_ron=0.018, c_v3=17e-6, t_on=None,
                loadsw=False):
    """VSYS caps (C10u25 + 2 x C1u25 at 4 V), TPS22965 (on, RON 16-18 mOhm,
    no current limit), VSYS_SW caps (C10u + C4u7), TPS62840 averaged (3.3 V,
    HS 0.43-0.6 Ohm + L2u2 DCR 0.14 Ohm in 100 % mode, current limit 1.0-1.4 A
    peak -> 1.1 A average used, UVLO 1.8 / 1.6 V, efficiency 90 %), 3V3 caps
    (~17 uF left of 2 x 10 uF + the nRF52840 / SX1262 decoupling) and the 3V3
    load iload (A; scaled down below 1.8 V so a collapsed rail does not stall
    the solver).  Monitors <p>_ib (buck output), <p>_iinb (buck input).
    loadsw=False (the circuit since 19 Oct): no TPS22965; the buck runs from VSYS and the slide switch
    drives its EN (t_on: the switch closes then), its input caps (C10u + C4u7) sit on VSYS."""
    V = lambda n: 'V(%s)' % n
    if not loadsw:
        vsw = vsys
        en = 'time > %g' % t_on if t_on is not None else '1'
        return lines(
            cap(p + 'cs1', vsys, '0', 7e-6), cap(p + 'cs2', vsys, '0', 0.6e-6), cap(p + 'cs3', vsys, '0', 0.6e-6),
            cap(p + 'cw1', vsw, '0', 5e-6), cap(p + 'cw2', vsw, '0', 2.4e-6),
            latch(p + 'bon', '(%s) && %s > 1.8' % (en, V(vsw)), '!(%s) || %s < 1.6' % (en, V(vsw))),
            mon(p + '_ib', '%s*max(0, %s)' % (sat('V(%sbon)' % p), mn('1.1', '5*(3.3 - %s)' % V(v3), '(%s - %s)/%g' % (V(vsw), V(v3), 0.74 * rf())))),
            mon(p + '_iinb', 'V(%s_ib)*min(1, max(%s, 0)/(0.9*max(%s, 0.5))) + 1e-6*%s' % (p, V(v3), V(vsw), sat(V(vsw)))),
            'B%sbo 0 %s I = V(%s_ib)' % (p, v3, p),
            'B%sbi %s 0 I = V(%s_iinb)' % (p, vsw, p),
            cap(p + 'c3', v3, '0', c_v3),
            'B%sld %s 0 I = (%s)*min(1, max(%s, 0)/1.8)' % (p, v3, iload, V(v3)),
        )
    s = lines(
        cap(p + 'cs1', vsys, '0', 7e-6), cap(p + 'cs2', vsys, '0', 0.6e-6), cap(p + 'cs3', vsys, '0', 0.6e-6),
        ('R%ssw %s %s %g' % (p, vsys, vsw, sw_ron * rf())) if t_on is None else
        # slide switch closed at t_on: TPS22965 turns on over ~1.5 ms (CT 1 nF), modelled as a conductance ramp
        ('B%ssw %s %s I = max(0, min(1, (time - %g)/1.5e-3))*V(%s,%s)/%g' % (p, vsys, vsw, t_on, vsys, vsw, sw_ron * rf()) +
         '\nR%ssw0 %s %s 1Meg' % (p, vsys, vsw)),
        cap(p + 'cw1', vsw, '0', 5e-6), cap(p + 'cw2', vsw, '0', 2.4e-6),
        latch(p + 'bon', '%s > 1.8' % V(vsw), '%s < 1.6' % V(vsw)),
        mon(p + '_ib', '%s*max(0, %s)' % (sat('V(%sbon)' % p), mn('1.1', '5*(3.3 - %s)' % V(v3), '(%s - %s)/%g' % (V(vsw), V(v3), 0.74 * rf())))),
        mon(p + '_iinb', 'V(%s_ib)*min(1, max(%s, 0)/(0.9*max(%s, 0.5))) + 1e-6*%s' % (p, V(v3), V(vsw), sat(V(vsw)))),
        'B%sbo 0 %s I = V(%s_ib)' % (p, v3, p),
        'B%sbi %s 0 I = V(%s_iinb)' % (p, vsw, p),
        cap(p + 'c3', v3, '0', c_v3),
        'B%sld %s 0 I = (%s)*min(1, max(%s, 0)/1.8)' % (p, v3, iload, V(v3)),
    )
    return s


# ------------------------------------------------------------------ input protection

def efuse(p, vin, vout, rt_uv, rb_uv, rt_ov, rb_ov, rilm, zleak=0.0, cdvdt=1e-9, citimer=1e-9, ron=0.045,
          zener=True, zmodel='DZ56', cov=5e-12):
    """TPS259470A eFuse (SLVSFC9C) with its EN/UVLO and OVLO dividers and the
    4.7 V zener on EN/UVLO.  UVLO/OVLO comparators 1.20 V rising / 1.09 V
    falling, OVLO response 1.2 us, UVP 2.53 / 2.42 V.  Output slews at
    2000 / CdVdt[pF] V/ms (2 V/ms for 1 nF) while enabled; ILIM = 3334 /
    RILM, 2 x ILIM (fast-trip level) allowed during the ITIMER blanking
    (1.51 V x C / 1.8 uA = 0.84 ms for 1 nF), ILIM after it.  RON 45 mOhm
    max.  Once started (the output has reached the input) the ramp no longer
    limits it: a step on the input passes through the on switch until OVLO
    (or the current limit) acts.  cov: capacitance on the OVLO pin.  Forward
    current only (reverse blocking).  zleak: zener leakage
    (A at 1.2 V, modelled as a resistor 1.2 / zleak from EN to GND).
    Monitor <p>_i (IN -> OUT current), nodes <p>_EN, <p>_OV."""
    ron = ron * rf()
    ilim = 3334.0 / rilm
    sr = 2000.0 / (cdvdt * 1e12) * 1e3   # V/s
    tblank = 1.51 * citimer * 1e9 / 1.8 * 1e-3
    en, ov = p + '_EN', p + '_OV'
    V = lambda n: 'V(%s)' % n
    s = lines(
        'R%sut %s %s %g' % (p, vin, en, rt_uv), 'R%sub %s 0 %g' % (p, en, rb_uv),
        'D%sz 0 %s %s' % (p, en, zmodel) if zener else '',
        'R%szl %s 0 %g' % (p, en, 1.2 / zleak) if zleak > 0 else '',
        'C%sen %s 0 5p' % (p, en),
        'R%sot %s %s %g' % (p, vin, ov, rt_ov), 'R%sob %s 0 %g' % (p, ov, rb_ov), 'C%sov %s 0 %g' % (p, ov, cov),
        latch(p + 'uv', '%s > 1.20' % V(en), '%s < 1.09' % V(en)),
        timer(p + 'tov', '%s > 1.20' % V(ov), 1.2e-6),
        latch_k(p + 'ovl', expired(p + 'tov'), b('%s < 1.09' % V(ov))),
        latch(p + 'uvp', '%s > 2.53' % V(vin), '%s < 2.42' % V(vin)),
        mon(p + '_ena', '%s*(1 - %s)*%s' % (sat('V(%suv)' % p), sat('V(%sovl)' % p), sat('V(%suvp)' % p))),
        'C%sramp %sramp 0 1n' % (p, p), 'R%sramp %sramp 0 1G' % (p, p),
        latch(p + 'st', 'V(%s_ena) > 0.5 && V(%sramp) > %s - 0.05' % (p, p, V(vin)), 'V(%s_ena) < 0.5' % p),
        'B%sramp 0 %sramp I = V(%s_ena) > 0.5 ? 1n*(%g + V(%sst)*1e8)*max(0, min(1, (%s - V(%sramp))*20)) : -1e-3*V(%sramp)'
        % (p, p, p, sr, p, V(vin), p, p),
        timer(p + 'tbl', 'V(%s_i) > %g' % (p, ilim), tblank),
        mon(p + '_i', 'V(%s_ena)*max(0, %s)' % (p, mn(
            '(V(%stbl) > 1 ? %g : %g)' % (p, ilim, 2 * ilim), '(%s - %s)/%g' % (V(vin), V(vout), ron),
            '20*(V(%sramp) - %s + 0.02)' % (p, V(vout))))),
        'B%s %s %s I = V(%s_i)' % (p, vin, vout, p),
        'B%sq %s 0 I = (%s > 2.5 ? 0.43e-3 : 5e-6)*%s' % (p, vin, V(vin), sat(V(vin))),
    )
    return s


def max17608(p, vin, vout, rt_ov=1.5e6, rb_ov=267e3, rset=2100.0, ron=0.26, uvr=4.02, uvf=3.5, ok=None,
             r_ok=(1.5e6, 100e3)):
    """MAX17608 (19-100264 rev 1) current limiter on the solar / drone input, as wired since 19 Oct:
    internal UVLO 4.02 V rising (3.46-4.45) / 3.5 V falling (the UVLO pin is tied high), OVLO = 1.5 V x
    (1 + rt/rb) rising, 3.3 % hysteresis, switch off 1 us after OVLO crosses (tOFF_OVP), back on after
    20 us (tDEB_OVP) + the ~1 ms turn-on ramp (tON_SWITCH); at power-up the input must be good for tDEB
    = 16 ms first.  Continuous current limit (CLMODE = GND) 1.5 V / RSETI = 0.71 A for 2.1 k (+-3 %), taken as
    instant (tOCP_RES 100 us).  RON 260 mOhm typ (490 max) +0.4 %/C.  Forward current only (reverse
    current blocking, and -60 V reverse input: nothing flows).  Supply 0.88 mA from IN while on, 0.89 mA
    from OUT while OUT is above IN.  ok: the node of the 1 M / 137 k input-voltage divider (the
    processor's <name>_OK, 1.5 M / 100 k).  Monitors <p>_i, <p>_ena; nodes <p>_OV.  Thermal shutdown not modelled."""
    ron = ron * rf()
    ilim = 1.5 / (rset / 1000.0)
    ov = p + '_OV'
    V = lambda n: 'V(%s)' % n
    s = lines(
        'R%sot %s %s %g' % (p, vin, ov, rt_ov), 'R%sob %s 0 %g' % (p, ov, rb_ov), 'C%sov %s 0 5p' % (p, ov),
        ('R%sok1 %s %s %g\nR%sok2 %s 0 %g' % (p, vin, ok, r_ok[0], p, ok, r_ok[1])) if ok else '',
        latch(p + 'uv', '%s > %g' % (V(vin), uvr), '%s < %g' % (V(vin), uvf)),
        timer(p + 'tov', '%s > 1.5' % V(ov), 1.0e-6),
        latch_k(p + 'ovl', expired(p + 'tov'), b('%s < 1.45' % V(ov)), 20e-6),
        timer(p + 'tdeb', 'V(%suv) > 0.5 && V(%sovl) < 0.5' % (p, p), 16e-3),
        latch_k(p + 'up', expired(p + 'tdeb'), b('V(%suv) < 0.5' % p)),
        mon(p + '_ena', '%s*%s*(1 - %s)' % (sat('V(%sup)' % p), sat('V(%suv)' % p), sat('V(%sovl)' % p))),
        'C%sramp %sramp 0 1n' % (p, p), 'R%sramp %sramp 0 1G' % (p, p),
        'B%sramp 0 %sramp I = V(%s_ena) > 0.5 ? 1n*%g*max(0, min(1, (%s - V(%sramp))*20)) : -1e-3*V(%sramp)'
        % (p, p, p, 10e3, V(vin), p, p),   # ~10 V/ms: the ~1 ms tON_SWITCH
        mon(p + '_i', 'V(%s_ena)*max(0, %s)' % (p, mn('%g' % ilim, '(%s - %s)/%g' % (V(vin), V(vout), ron),
                                                       '20*(V(%sramp) - %s + 0.02)' % (p, V(vout))))),
        'B%s %s %s I = V(%s_i)' % (p, vin, vout, p),
        'B%sq %s 0 I = 0.88e-3*%s' % (p, vin, sat('(V(%s) - 3)' % vin)),
        # reverse-blocking supply: drawn from OUT only while OUT can power the part (above ~3 V)
        'B%sqr %s 0 I = 0.89e-3*%s*%s' % (p, vout, sat('(V(%s) - V(%s) - 0.1)*20' % (vout, vin)), sat('V(%s) - 3' % vout)),
    )
    return s


def panel(p, plus, minus, voc, isc, ncell, temp_c=25.0, rs_cell=0.01, rsh=None, cpanel=20e-9):
    """Single-diode solar panel: I = Isc - I0 (exp(V / (Ns n Vt)) - 1) - V / Rsh,
    Ns cells in series, n = 1.3, I0 set so that I(Voc) = 0 at 25 C; Voc
    falls 2.2 mV/C per cell above 25 C.  isc is the short-circuit current
    at the irradiance of the run (it scales with sun)."""
    vt = 8.617e-5 * (273.15 + temp_c)
    nvt = 1.3 * vt * ncell
    voc_t = voc - 0.0022 * ncell * (temp_c - 25.0)
    import math
    i0 = isc / (math.exp(voc_t / nvt) - 1.0)
    rsh = rsh or 300.0 * ncell
    return lines('B%s %s %s_x I = %g - %g*(exp(min(V(%s_x,%s)/%g, %g)) - 1) - V(%s_x,%s)/%g'
                 % (p, minus, p, isc, i0, p, minus, nvt, voc_t / nvt + 8, p, minus, rsh),
                 '.nodeset v(%s_x)=%g' % (p, voc_t),
                 'C%s %s_x %s %g' % (p, p, minus, cpanel),
                 'R%ss %s_x %s %g' % (p, p, plus, rs_cell * ncell))
