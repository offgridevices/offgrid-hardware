# -*- coding: utf-8 -*-
"""Circuit transients with ngspice: one half-bridge switching, and the battery bus.

The FET is Toshiba's own SPICE model of the TPN2R304PL: the "G0" PSpice
file (TPN2R304PL_G0_00_PSpice_rev1.lib), a BSIM3 model.  Toshiba gives it
out behind a free model-use agreement on the part's page
(toshiba.semicon-storage.com, TPN2R304PL, "Design & Development" ->
"SPICE model"), for simulation, not for passing on, so it is not in this
repository.  Download the PSpice zip, and either point TPN2R304PL_LIB at the
.lib inside or put the .lib in sim/out/spice/.  PSpice's BSIM3 is LEVEL=7;
ngspice calls it level 8, which fet_lib() changes.

Everything else is built here from datasheet figures (data.py): the DRV8300
gate driver as its output resistance up to its peak current behind the gate
resistor, the capacitors at their DC-bias capacitance with ESR and ESL, the
battery as a source behind its internal resistance and lead inductance, the
SMF33A TVS as a breakdown diode with its clamping resistance.
"""
import os, re, glob, subprocess
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out', 'spice')
FET_NAME = 'TPN2R304PL_G0_00'


def fet_lib():
    """The TPN2R304PL model as an ngspice include file."""
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, 'TPN2R304PL_G0.lib')
    if os.path.exists(path):
        return path
    src = os.environ.get('TPN2R304PL_LIB') or next(iter(glob.glob(os.path.join(OUT, 'TPN2R304PL_G0_00_PSpice*.lib'))), None)
    if not src or not os.path.exists(src):
        raise SystemExit('Toshiba\'s TPN2R304PL G0 PSpice model is needed: see the note at the top of sim/spice.py')
    text = open(src, errors='replace').read()
    assert '.SUBCKT %s' % FET_NAME in text, 'not the G0 PSpice model'
    text = re.sub(r'LEVEL=7', 'LEVEL=8\n+ VERSION=3.3.0', text)
    open(path, 'w').write(text)
    return path


def run(name, netlist, vectors):
    """Run a transient; return {vector: array} with 'time' included."""
    os.makedirs(OUT, exist_ok=True)
    cir = os.path.join(OUT, name + '.cir')
    dat = os.path.join(OUT, name + '.dat')
    ctl = '.control\nset wr_singlescale\nset wr_vecnames\nrun\nwrdata %s %s\n.endc\n.end\n' % (
        dat, ' '.join(vectors))
    open(cir, 'w').write(netlist + '\n' + ctl)
    p = subprocess.run(['ngspice', '-b', cir], capture_output=True, text=True, timeout=1800)
    if p.returncode != 0 or not os.path.exists(dat):
        raise RuntimeError('ngspice failed on %s:\n%s' % (cir, p.stdout[-3000:] + p.stderr[-3000:]))
    head = open(dat).readline().split()
    a = np.loadtxt(dat, skiprows=1)
    return {k: a[:, i] for i, k in enumerate(head)}


def driver(prefix, vset, out, ref, rpu, rpd, ipu, ipd):
    """DRV8300 output stage: pulls `out` toward `vset`.

    Up to its peak current it looks like its on-resistance (rpu up, rpd down,
    from the datasheet's output drop at 100 mA); beyond, it holds the peak
    current (ipu source, ipd sink).  I = Ipk tanh(dV / (R Ipk)) does both
    smoothly; the up and down halves are blended over about 0.1 V so the
    solver sees no corner."""
    d = 'V(%s,%s)-V(%s,%s)' % (vset, ref, out, ref)
    up = '%g*tanh((%s)/%g)' % (ipu, d, rpu * ipu)
    dn = '%g*tanh((%s)/%g)' % (ipd, d, rpd * ipd)
    return 'B%s %s %s I = 0.5*(1+tanh(20*(%s)))*%s + 0.5*(1-tanh(20*(%s)))*%s\n' % (
        prefix, ref, out, d, up, d, dn)


def half_bridge(p):
    """One phase leg switching an inductive load: HS turn-on and turn-off.

    p: V (bus), I (phase current out of the leg), T (C), Lloop (H, the
    commutation loop, split drain 40 % / mid 20 % / source 40 %), Rg (ohm),
    rpu/rpd, ipu/ipd (driver), gvdd, vboot, dead (s), Cb/ESRb/ESLb (bridge
    capacitor), Cext/ESRext/ESLext, Llead/Rbat, Lplane/Rplane, Lg (gate
    loop), lm (body diode, see _fet_variant), snub (R, C across each FET).
    """
    lib = _fet_variant(p.get('lm'))
    t_off_ls = 0.5e-6
    t_on_hs = t_off_ls + p['dead']
    t_off_hs = t_on_hs + 2.0e-6
    t_on_ls = t_off_hs + p['dead']
    tr = 5e-9
    L = p['Lloop']
    n = """* half-bridge edge test
.include %(lib)s
.options temp=%(T)g reltol=1e-3 abstol=1e-6 vntol=1e-4 chgtol=1e-12
Vbat bat 0 %(V)g
Rbat bat b1 %(Rbat)g
Lbat b1 pad %(Llead)g
Cext pad cx %(Cext)g
Rext cx cx2 %(ESRext)g
Lext cx2 0 %(ESLext)g
Rpl pad p1 %(Rplane)g
Lpl p1 vb %(Lplane)g
* this leg's bridge capacitor, VBAT to the sense node
Cb vb cb1 %(Cb)g
Rcb cb1 cb2 %(ESRb)g
Lcb cb2 src %(ESLb)g
* the channel's other two bridge capacitors, a little further away
Cb2 vb cc1 %(Cb2)g
Rcb2 cc1 cc2 %(ESRb2)g
Lcb2 cc2 src %(ESLb2)g
* shunt and ground plane back to the battery pad
Rsh src sh1 0.5m
Lsh sh1 gb 0.6n
Rgp gb g1 %(Rplane)g
Lgp g1 0 %(Lplane)g
* commutation loop
Ld vb dH0 %(Ld)g
VidH dH0 dH 0
XH dH gH sH %(fet)s
Lm sH dL %(Lm)g
VidL dL dL0 0
XL dL0 gL sL %(fet)s
Ls sL src %(Ls)g
* motor: the phase current leaves the leg and returns through the other phase's low side
Iload dL src %(I)g
%(snub)s
* gate drive: DRV8300 low side referenced to board ground, high side to SHx
VsL vsL gb PWL(0 %(gvdd)g %(t_off_ls)g %(gvdd)g %(t1)g 0 %(t_on_ls)g 0 %(t2)g %(gvdd)g)
%(drvL)sRgL goL gL1 %(Rg)g
LgL gL1 gL %(Lg)g
VsH vsH sH PWL(0 0 %(t_on_hs)g 0 %(t3)g %(vboot)g %(t_off_hs)g %(vboot)g %(t4)g 0)
%(drvH)sRgH goH gH1 %(Rg)g
LgH gH1 gH %(Lg)g
CgLo goL gb 10p
CgHo goH sH 10p
.tran 0.02n %(tend)g 0 0.05n
""" % dict(p, lib=lib, fet=FET_NAME, Ld=0.4 * L, Lm=0.2 * L, Ls=0.4 * L,
           t_off_ls=t_off_ls, t_on_hs=t_on_hs, t_off_hs=t_off_hs, t_on_ls=t_on_ls,
           t1=t_off_ls + tr, t2=t_on_ls + tr, t3=t_on_hs + tr, t4=t_off_hs + tr,
           drvL=driver('L', 'vsL', 'goL', 'gb', p['rpu'], p['rpd'], p['ipu'], p['ipd']),
           drvH=driver('H', 'vsH', 'goH', 'sH', p['rpu'], p['rpd'], p['ipu'], p['ipd']),
           tend=t_on_ls + 1.0e-6,
           snub=('* RC snubber across each FET\nRsnL dL0 sn1 %g\nCsnL sn1 sL %g\nRsnH dH sn2 %g\nCsnH sn2 sH %g'
                 % (p['snub'][0], p['snub'][1], p['snub'][0], p['snub'][1])) if p.get('snub') else '')
    w = run('hb_%(tag)s' % p, n, ['v(dH)', 'v(sH)', 'v(dL0)', 'v(sL)', 'v(gH)', 'v(gL)',
                                  'v(xh.22)', 'v(xl.22)', 'v(vb)', 'v(src)', 'v(gb)', 'v(pad)',
                                  'i(vidh)', 'i(vidl)'])
    t = w['time']
    vdsH = w['v(dH)'] - w['v(sH)']
    vdsL = w['v(dL0)'] - w['v(sL)']
    vgsL = w['v(xl.22)'] - w['v(sL)']
    vgsH = w['v(xh.22)'] - w['v(sH)']
    sh = w['v(sH)'] - w['v(gb)']
    iH, iL = w['i(vidh)'], w['i(vidl)']
    win = lambda a, b: (t >= a) & (t <= b)
    on = win(t_on_hs - 20e-9, t_on_hs + 400e-9)
    off = win(t_off_hs - 20e-9, t_off_hs + 400e-9)
    E = lambda m, v, i: float(np.trapz((v * i)[m], t[m]))
    def edge_rate(m, rising):
        # 10-90 % of the bus swing on the switch node, as a slew-rate spec is read
        v = sh[m]; tt = t[m]; V = p['V']
        a, b = (0.1 * V, 0.9 * V) if rising else (0.9 * V, 0.1 * V)
        pa = v > a if rising else v < a
        pb = v > b if rising else v < b
        if not (pa.any() and pb.any()):
            return float('nan')            # the edge is slower than the window
        return 0.8 * V / max(tt[np.argmax(pb)] - tt[np.argmax(pa)], 1e-12) * 1e-9
    return dict(
        vds_hs_peak=float(vdsH.max()), vds_ls_peak=float(vdsL.max()),
        sh_min=float(sh[win(t_off_hs - 20e-9, t_on_ls)].min()),
        slew_rise=edge_rate(on, True), slew_fall=edge_rate(off, False),
        vgs_ls_miller=float(vgsL[on].max()), vgs_hs_miller=float(vgsH[win(t_on_ls - 20e-9, t_on_ls + 400e-9)].max()),
        ih_peak=float(iH[on].max()), irr=float(iH[on].max() - p['I']),
        e_on=E(on, vdsH, iH), e_off=E(off, vdsH, iH),
        e_ls_on=E(on, vdsL, iL), e_ls_off=E(off, vdsL, iL),
        wave=w,
        edges=(t_off_ls, t_on_hs, t_off_hs, t_on_ls))


# ----------------------------------------------------------------- model checks
LM_DIODE = """
* Body diode with reverse recovery by charge control (Lauritzen and Ma,
* IEEE Trans. Power Electronics 6(2), 1991): q_M, the stored charge, is the
* voltage on a 1 nF capacitor (1 V = 1 nC).
.subckt lmdiode a k params: is=6.34e-11 n=1.1519 tau=10n tm=5n rs=0.6m
Rs a ai {rs}
Cq qm 0 1n
Rq qm 0 1e9
Bq 0 qm I = ({is}*{tau}*(exp(min(V(ai,k)/({n}*0.025865),60))-1) - 1n*V(qm))/{tm} - 1n*V(qm)/{tau}
Bd ai k I = ({is}*{tau}*(exp(min(V(ai,k)/({n}*0.025865),60))-1) - 1n*V(qm))/{tm}
.ends
"""


def _fet_variant(lm=None):
    """The model file, or with its body diode changed: lm = (tau, tm) replaces
    the two conduction diodes by one charge-control diode (Lauritzen-Ma) of
    lifetime tau and transit time tm; Toshiba's junction capacitance and 40 V
    breakdown stay, on a diode that carries no forward current of its own.
    """
    if lm is None:
        return fet_lib()
    tau, tm = lm
    path = os.path.join(OUT, 'TPN2R304PL_G0_lm%.3g_%.3g.lib' % (tau * 1e9, tm * 1e9))
    text = open(fet_lib()).read()
    for a, b in (('D0 3 1 DDS1', 'D0 3 1 DDSJ\nXLM 3 1 lmdiode params: tau=%g tm=%g' % (tau, tm)),
                 ('D1 3 1 DDS2\n', ''),
                 ('.MODEL DDS1 D', '.MODEL DDSJ D\n+ IS=1e-30 CJO=2.05e-09 VJ=0.9 M=0.45 BV=40 IBV=0.01\n.MODEL DDS1 D')):
        assert a in text, a
        text = text.replace(a, b)
    open(path, 'w').write(LM_DIODE + text)
    return path


def recovery_charge(lm=None, IF=20.0, didt=100e6, VR=20.0, T=25):
    """The datasheet's Qrr test (IF, -di/dt, VR) on the model: charge of the
    reverse lobe, from the current's zero crossing to its return to zero."""
    L = VR / didt
    lib = _fet_variant(lm)
    n = """* Qrr test
.include %s
.options temp=%g reltol=1e-3 abstol=1e-6 vntol=1e-4
X1 d 0 0 %s
Vr n1 0 PWL(0 0 1u 0 1.001u %g)
L1 n1 dd %g ic=%g
Vm dd d 0
.tran 0.02n 1.6u uic
""" % (lib, T, FET_NAME, VR, L, -IF)
    w = run('qrr', n, ['i(vm)'])
    t, i = w['time'], w['i(vm)']
    m = t > 1e-6
    z = np.where(m[:-1] & (i[:-1] <= 0) & (i[1:] > 0))[0][0]
    k = z + 1 + np.argmax(i[z + 1:] <= 0)
    ip = z + np.argmax(i[z:k])
    j = ip + np.argmax(i[ip:k] < 0.25 * i[ip])
    return float(np.trapz(i[z:k], t[z:k])), float(i[ip]), float(t[j] - t[z])


def capacitances(VDS=20.0, T=25):
    """Ciss, Crss, Coss (F) of the model at VDS, 1 MHz, as the datasheet measures them."""
    n = """* capacitances
.include %s
.options temp=%g
X1 d1 g1 0 %s
Vd1 d1 0 %g
Vg1 g1 0 dc 0 ac 1
X2 d2 g2 0 %s
Vd2 d2 0 dc %g ac 1
Vg2 g2 0 0
X3 d3 g3 0 %s
Vd3 d3 0 dc %g ac 1
Vg3 g3 0 0
.ac lin 1 1e6 1e6
""" % (fet_lib(), T, FET_NAME, VDS, FET_NAME, VDS, FET_NAME, VDS)
    os.makedirs(OUT, exist_ok=True)
    cir = os.path.join(OUT, 'caps.cir')
    open(cir, 'w').write(n + '.control\nrun\nprint mag(i(vg1)) mag(i(vg2)) mag(i(vd3))\n.endc\n.end\n')
    out = subprocess.run(['ngspice', '-b', cir], capture_output=True, text=True).stdout
    vals = [float(re.search(r'mag\(i\(%s\)\)\s*=\s*([0-9.eE+-]+)' % v, out).group(1)) for v in ('vg1', 'vg2', 'vd3')]
    w = 2 * np.pi * 1e6
    return tuple(v / w for v in vals)


def rds_on(T, VGS=10.0, ID=40.0):
    n = """* rds
.include %s
.options temp=%g
X1 d g 0 %s
Vg g 0 %g
Id 0 d %g
.op
""" % (fet_lib(), T, FET_NAME, VGS, ID)
    cir = os.path.join(OUT, 'rds.cir')
    open(cir, 'w').write(n + '.control\nrun\nprint v(d)\n.endc\n.end\n')
    out = subprocess.run(['ngspice', '-b', cir], capture_output=True, text=True).stdout
    return float(re.search(r'v\(d\)\s*=\s*([0-9.eE+-]+)', out).group(1)) / ID


def gate_charge(VDD=20.0, ID=40.0, IG=1e-3):
    """Qg to 10 V and the Miller plateau (Qgd), the datasheet's test: a clamped
    current load of ID on a VDD rail, the gate charged by a constant IG."""
    n = """* gate charge
.include %s
X1 d g 0 %s
Vdd vdd 0 %g
Iload vdd d %g
Dcl d vdd dclamp
.model dclamp d(is=1e-12 n=0.05)
Ig 0 g PWL(0 0 10n %g)
.tran 1n 60u
""" % (fet_lib(), FET_NAME, VDD, ID, IG)
    w = run('qg', n, ['v(g)', 'v(d)'])
    t, vg, vd = w['time'], w['v(g)'], w['v(d)']
    q = IG * t
    qg = float(np.interp(10.0, vg, q))
    # Qgd: charge while the drain swings from 90 % to 10 % of VDD
    i90 = np.argmax(vd < 0.9 * VDD); i10 = np.argmax(vd < 0.1 * VDD)
    return qg, float(q[i10] - q[i90])


# ----------------------------------------------------------------- battery bus
def bus(p, name):
    """The battery line from the pack to both boards.

    Pack (EMF, internal resistance) -> leads (inductance, resistance) -> the
    ESC's battery pads, where the external capacitors sit -> the ESC's planes
    to its bridge capacitors (lumped) and its load (current source) -> the
    stack lead (one VBAT wire, one GND wire) -> the FC's input: TVS, ceramics
    and the two bucks (a constant-current load).

    p['plug'] True: the pack is connected at t = 0.1 us through a closing
    contact (a hot plug); otherwise it is connected throughout.  p['iesc'] is
    a PWL list [(t, amps)] of the ESC's battery-side current.
    """
    pwl = ' '.join('%g %g' % tv for tv in p['iesc'])
    n = """* battery bus
.options reltol=1e-3 abstol=1e-6 vntol=1e-4 chgtol=1e-12 method=gear
Vemf emf 0 %(Vpack)g
%(contact)s
Rbat b1 b2 %(Rbat)g
Lbat b2 pad %(Llead)g
* external capacitors at the ESC's battery pads
%(ext)s
* ESC: planes to the bridge capacitors, and the load
Rpl pad vb %(Rplane)g
Vbm vb bm 0
Cbr bm cb1 %(Cbridge)g
Rbr cb1 cb2 %(ESRbridge)g
Lbr cb2 0 %(ESLbridge)g
Cmisc vb 0 %(Cmisc)g
Iesc vb 0 PWL(%(pwl)s)
* stack lead to the FC: VBAT wire and GND wire
Rst vb s1 %(Rstack)g
Lst s1 fc %(Lstack)g
* FC input: two 10 uF 1210 (at bias), 2 x 100 nF, SMF33A, bucks as a current load
Cfc fc cf1 %(Cfc)g
Rfc cf1 0 %(ESRfc)g
Vtv fc tvk 0
Dtvs 0 tvk tvs
.model tvs d(bv=%(tvs_bv)g ibv=1m rs=%(tvs_rs)g cjo=%(tvs_c)g is=1e-12 n=1)
Ifc fc 0 PWL(0 0 %(tfc)g %(Ifc)g)
.tran %(step)g %(tend)g 0 %(maxstep)g %(uic)s
""" % dict(p, pwl=pwl,
           contact=('Sw emf b1 ctl 0 plug\nVctl ctl 0 PWL(0 0 %g 0 %g 1)\n.model plug sw(ron=%g roff=1e6 vt=0.5)'
                    % (p['t_plug'], p['t_plug'] + 1e-9, p['Rcontact']) if p.get('plug') else 'Rc emf b1 %g' % p['Rcontact']),
           ext=('Vxm pad xm 0\nCx xm x1 %g\nRx x1 x2 %g\nLx x2 0 %g' % (p['Cext'], p['ESRext'], p['ESLext'])
                if p.get('Cext') else '* none fitted'),
           uic='uic' if p.get('plug') else '', tfc=p.get('tfc', 1e-6))
    vec = ['v(pad)', 'v(vb)', 'v(fc)', 'i(vemf)', 'i(vtv)', 'i(vbm)']
    if p.get('Cext'):
        vec.append('i(vxm)')
    w = run(name, n, vec)
    return w
