# -*- coding: utf-8 -*-
"""The whole Mesh Radio v1 power path as one ngspice netlist, assembled from
powerlib.py and switched by a configuration dict, for the burst, shorts,
solar and reverse studies.

The circuit as changed on 19 Oct (src/circuit.py):

  USB-C -- 1 m cable -- TVS2200 + snubber -- TPS259470A -- USB_5V --RB060MM--+
  solar panel -- lead -- SMF33CA -- MAX17608 --------------------------------+-- VIN_CHG
                                                                              |
                                                         BQ25185 (IN, SYS = VSYS, BAT = BAT_P), 300 mA
  cell -- leads -- JST -- CSD25310Q2 -- BAT_P --TPS22950--RB060MM-- VSYS -- TPS62840 (EN = switch) -- 3V3
     (gate: off unless the SSM3K56ACT polarity check sees the cell the right way round;
      - side: BQ29700 + SSM10N954L + 22 mOhm to GND)
  BAT_P --IN1-- TPS2121 --IN2-- VSYS   (PR1 562 k / 374 k; a GPIO FET can pull PR1 low)
                  OUT = PA_IN -- TPS63810 -- VPA (2 x 47 uF 1206 X7S) -- QPA9510

PCB parasitics (TRACE_*, SENSE_TRACE) are extracted from the routed board
(../mesh-radio.kicad_pcb, 3 Nov 2026) by extract.py, which prints them next
to the pre-routing estimates; re-run it after any change to the copper and
copy its values here.  The simulation's BAT_P node is the reverse FET's
source pins (Q1), its VSYS node the charger's SYS pins (U4).  Track
resistance follows copper's +0.393 %/C from 25 C (build()).
"""
import powerlib as P

# --- PCB parasitics, extracted (sim/extract.py; R at 25 C includes the GND return
# where noted; L is the loop over the nearest GND copper) ------------------------
#               R (Ohm)  L (H)        pre-routing estimate (R, L): path
TRACE_BAT = (0.0202, 11.5e-9)    # (6 mOhm, 6 nH): J3 -> Q1 (BATT_PLUS) + J3 <- Q3 (CELL_MINUS) + GND U14 -> R34, outside the sense loop
TRACE_MUX1 = (0.0826, 8.1e-9)   # (5, 5): Q1 source -> TPS2121 IN1 (BAT_P: In2/In3/In4, 0.5 oz; 15 mm since the battery plug moved right, 5 Nov)
TRACE_PAIN = (0.0119, 7.4e-9)   # (3, 3): TPS2121 OUT -> TPS63810 VIN (PA_IN)
TRACE_VPA = (0.0082, 3.9e-9)    # (5, 5): TPS63810 VOUT -> L14 collector choke (VPA) + GND QPA9510 -> TPS63810
TRACE_USB = (0.0087, 3.3e-9)    # (5, 5): USB-C VBUS -> TPS259470A IN + GND charger -> USB-C
TRACE_5V = (0.0171, 8.6e-9)     # (none): TPS259470A OUT -> RB060MM -> BQ25185 IN (USB_5V + VIN_CHG)
TRACE_CHG = (0.1493, 29.4e-9)   # (none): Q1 source -> BQ25185 BAT (BAT_P, 50 mm across the board)
TRACE_BYP = (0.1629, 26.5e-9)   # (none): Q1 source -> TPS22950 VIN (BAT_P)
TRACE_SYS2 = (0.1154, 26.1e-9)  # (none): BQ25185 SYS -> TPS2121 IN2 (VSYS)
TRACE_SOLAR = (0.0018, 0.8e-9)  # (5, 5 in hotplug): solar JST -> MAX17608 IN + GND charger -> JST
TRACE_DRONE = (0.0356, 7.4e-9) # (5, 5 in hotplug): drone JST-GH -> MAX17608 IN + GND charger -> JST-GH
# in the BQ29700's sense loop, in series with the 15 mOhm sense resistor (V- through
# 2.2 k to GND at R33, VSS on CELL_MINUS at U5): since 5 Nov the FETs' source pins
# run straight into R34 beside them on B.Cu, 0.6 mm wide and poured (until then
# 18.1 mOhm: PROT_S2 dropped to In1 for 5 mm, 16.9 mOhm of it)
SENSE_TRACE = 0.0004            # (none: the README asked for it to be added here)
CU_TC = 0.00393                 # copper, 1/K
CABLE_USB = (0.200, 1.0e-6)    # 1 m USB cable, both conductors
LEAD_PANEL = (0.10, 1.0e-6)    # 1 m solar lead

# PA operating points (QPA9510 datasheet + EVB, interpolated between them)
PA_LEVELS = [
    ('30 dBm (1 W)', 2.7, 1.00),
    ('32 dBm (1.6 W)', 3.1, 1.30),
    ('33 dBm (2 W)', 3.35, 1.55),
    ('34 dBm (2.5 W)', 3.6, 2.00),
    ('35 dBm (3 W)', 4.0, 2.30),
]


def default_cfg():
    return dict(
        temp=25.0,                      # ambient = component temperature (powerlib.set_temp)
        cell=dict(ocv=3.7, rint=0.15, reverse=False, plug_t=None, present=True),   # rint at 25 C
        lm='tps',                       # cell-to-SYS: 'tps' TPS22950 (since 19 Oct); old: 'gnd'/'vout' LM66100, 'diode'
        rev='v2',                       # reverse FET drive: 'v2' polarity-checked (since 19 Oct), 'v1' gate to CELL_MINUS
        usb=None,                       # source voltage, or None
        usb_step=None,                  # (t, v2): USB source steps to v2 at t
        solar=None,                     # dict(voc, isc, ncell, temp_c)
        chg={},                         # BQ25185 overrides
        mux={}, bb={}, prot={},
        pr_force_low=False,             # firmware sets PA_SRC_SYS: its FET pulls PR1 low (no cell fitted)
        pa=dict(vset=4.0, inom=2.3, t_en=1e-3, t_apc=4e-3, t_rf=4.2e-3, burst=1.0, on=True, n=1, period=1.0),
        sw_on=None,                     # slide switch closes at this time (None: already on)
        i3v3_idle=0.013, i3v3_tx=0.130,
        extra='',                       # extra netlist lines (shorts, loads)
        tstop=None, tmax=10e-6, uic=False,
        save=[], meas=[], lin_step=50e-6,
    )


def _win(t0, t1, n, per, edge=5e-6):
    """Sum of n smooth 0..1 windows [t0, t1] repeating every per."""
    return '(' + ' + '.join(P.sat('min(time - %g, %g - time)/%g' % (t0 + k * per, t1 + k * per, edge))
                            for k in range(n)) + ')'


def _any(t0, t1, n, per):
    return '(' + ' || '.join('(time > %g && time < %g)' % (t0 + k * per, t1 + k * per) for k in range(n)) + ')'


def build(cfg, datfile):
    c = cfg
    pa = c['pa']
    nb, per = pa.get('n', 1), pa.get('period', 1.0)
    t_off = pa['t_rf'] + pa['burst']
    P.set_temp(c.get('temp', 25.0))
    kcu = 1 + CU_TC * (P.TEMP - 25.0)

    def tr(t):
        return (t[0] * kcu, t[1])

    def tr_r(t):
        # the low-current branches (charger BAT, cell bypass, mux IN2, USB 5 V): R only.  Their 6-28 nH
        # changes nothing these studies measure, and in series with the parts' switched sources it made
        # the solver stiff (timestep too small at the cell plug-in; trapezoidal ringing)
        return (t[0] * kcu,)
    s = ['* Mesh Radio v1 power path (sim/board.py), %g C' % P.TEMP, P.models()]
    # ---------------------------------------------------------------- battery
    cl = c['cell']
    if cl['present']:
        s.append(P.cell('BT', 'BATT_PLUS', 'CELL_MINUS', cl['ocv'], cl['rint'] * P.rint_k(), plug_t=cl['plug_t'],
                        reverse=cl['reverse'], llead=cl.get('llead', 0.1e-6)))
    else:
        s.append('Rnob1 BATT_PLUS 0 10Meg\nRnob2 CELL_MINUS 0 10Meg\n')
    sw = 'time > %g' % c['sw_on'] if c.get('sw_on') is not None else '1'
    prot = dict(rsense=P.PROT['rsense'] + SENSE_TRACE * kcu)
    prot.update(c['prot'])
    s.append(P.battery_block('PB', lm=c['lm'], prot=prot, trace_bat=tr(TRACE_BAT), rev=c.get('rev', 'v2'), on=sw,
                             byp_in='BAT_BYP'))
    s.append(P.rl('tbyp', 'BAT_P', 'BAT_BYP', *tr_r(TRACE_BYP)))
    s.append(P.rl('tchg', 'BAT_P', 'BAT_CHG', *tr_r(TRACE_CHG)))
    s.append(P.cap('cbat1', 'BAT_CHG', '0', 7e-6))    # C10u25 at BAT (charger)
    s.append(P.cap('cbat2', 'BAT_P', '0', 0.8e-6))    # C1u25 at mux IN1
    # ---------------------------------------------------------------- inputs
    if c['usb'] is not None:
        if c['usb_step']:
            t2, v2 = c['usb_step']
            s.append('Vusb usb_src 0 pwl(0 %g %g %g %g %g)' % (c['usb'], t2, c['usb'], t2 + 1e-6, v2))
        else:
            s.append('Vusb usb_src 0 %g' % c['usb'])
        s.append(P.rl('cab', 'usb_src', 'usb_conn', *CABLE_USB))
        s.append(P.rl('tusb', 'usb_conn', 'USB_VBUS', *tr(TRACE_USB)))
        s.append(P.tvs2200('tvsu', 'USB_VBUS'))
        s.append(P.cap('cvb', 'USB_VBUS', '0', 0.9e-6))                    # C1u50 (1 uF 50 V X5R) at 5 V
        s.append(P.cap('csnb', 'USB_VBUS', 'usb_snb', 4.4e-6) + 'Rsnb usb_snb 0 1\n')   # 4.7 uF 50 V X7R + 1 R
        s.append(P.efuse('FU', 'USB_VBUS', 'USB_5V', 20e3, 7.68e3, 1e6, 287e3, 2210, cov=100e-12))
        s.append('R5vb USB_5V 0 2.2k\nC5vs USB_5V 0 1n\nR22v USB_5V NRF_VBUS 22\n' + P.cap('c5v', 'NRF_VBUS', '0', 5.0e-6))
        s.append(P.schottky('dusb', 'USB_5V', 'VIN_USB') + P.rl('t5v', 'VIN_USB', 'VIN_CHG', *tr_r(TRACE_5V)))
    if c['solar']:
        so = c['solar']
        s.append(P.panel('PV', 'pv_p0', '0', so['voc'], so['isc'], so['ncell'], so.get('temp_c', 25.0)))
        s.append('Vpvam pv_p0 pv_p 0\n')
        s.append(P.rl('pvl', 'pv_p', 'pv_c', *LEAD_PANEL) + P.rl('tsol', 'pv_c', 'SOLAR_CONN', *tr(TRACE_SOLAR)))
        s.append(P.smf33ca('tvss', 'SOLAR_CONN'))
        s.append(P.cap('csr', 'SOLAR_CONN', '0', 0.9e-6))
        s.append(P.max17608('FS', 'SOLAR_CONN', 'VIN_CHG', ok='SOLAR_OK'))
    s.append(P.cap('cvc1', 'VIN_CHG', '0', 0.9e-6) + 'Rvcl VIN_CHG 0 1Meg\n')     # 1 uF only since 19 Oct (was 1 + 10 uF)
    s.append(P.bq25185('CH', 'VIN_CHG', 'VSYS', 'BAT_CHG', c['chg']))
    # ---------------------------------------------------------------- system rail
    tx = _win(pa['t_apc'], t_off + 0.1e-3, nb, per) if pa['on'] else '0'
    s.append(P.system_rail('SR', iload='(%g + %s*%g)' % (c['i3v3_idle'], tx, c['i3v3_tx'] - c['i3v3_idle']),
                           t_on=c.get('sw_on'), loadsw=c.get('loadsw', False)))
    # ---------------------------------------------------------------- amplifier supply
    en = _any(pa['t_en'], t_off + 1e-3, nb, per) if pa['on'] else '0'
    s.append(P.rl('tm1', 'BAT_P', 'MUX_IN1', *tr(TRACE_MUX1)))
    s.append(P.rl('tm2', 'VSYS', 'MUX_IN2', *tr_r(TRACE_SYS2)))
    mux = dict(c['mux'])
    if c['pr_force_low']:
        mux['pr_ratio'] = 0.0
    s.append(P.tps2121('MX', 'MUX_IN1', 'MUX_IN2', 'PA_IN', en=en, cfg=mux))
    s.append(P.cap('cpa1', 'PA_IN', '0', 14e-6) + P.cap('cpa2', 'PA_IN', '0', 14e-6))
    s.append(P.rl('tpi', 'PA_IN', 'BB_IN', *tr(TRACE_PAIN)))
    s.append(P.cap('cpa3', 'BB_IN', '0', 7e-6))
    s.append(P.tps63810('BB', 'BB_IN', 'BB_OUT', en, pa['vset'], c['bb']))
    # 2 x 47 uF 1206 X7S (C3216X7S0J476M160AC): ~25 uF each left at 4 V (TDK DC-bias curve, read roughly)
    s.append(P.cap('cvp1', 'BB_OUT', '0', 25e-6) + P.cap('cvp2', 'BB_OUT', '0', 25e-6))
    s.append(P.rl('tvp', 'BB_OUT', 'VPA', *tr(TRACE_VPA)))
    s.append(P.cap('cvp3', 'VPA', '0', 2.8e-6) + P.cap('cvp4', 'VPA', '0', 2.8e-6))
    apc = _win(pa['t_apc'], t_off + 0.1e-3, nb, per) if pa['on'] else '0'
    rf = _win(pa['t_rf'], t_off, nb, per, 40e-6) if pa['on'] else '0'
    s.append(P.qpa9510('PA', 'VPA', apc, rf, pa['vset'], pa['inom']))
    # DC paths for nodes that only see caps and B current sources (10 Meg: < 0.5 uA)
    s.append(''.join('Rdc%d %s 0 10Meg\n' % (i, n) for i, n in enumerate(
        ['PA_IN', 'BB_IN', 'BB_OUT', 'VPA', 'VSYS', '3V3', 'BAT_P'] + (['VSYS_SW'] if c.get('loadsw') else []))))
    s.append(c['extra'])
    # ---------------------------------------------------------------- analysis
    tstop = c['tstop'] or (t_off + (nb - 1) * per + 0.05)
    vecs = ['v(bat_p)', 'v(vsys)', 'v(3v3)', 'v(pa_in)', 'v(vpa)', 'v(vin_chg)',
            'i(vbt_am)' if cl['present'] else 'v(batt_plus)', 'v(pblm_i)', 'v(ch_isup)', 'v(ch_ichg)', 'v(ch_iin)',
            'v(mx_i1)', 'v(mx_i2)', 'v(mx_sel)', 'v(bb_iin)', 'v(pa_i)', 'v(pbocd)', 'v(pbuvp)', 'v(chbuvf)',
            'v(bbrst)', 'v(prot_vm,cell_minus)', 'v(prot_bat,cell_minus)', 'v(cell_minus)'] + c['save']
    # initial guesses: the protector on, charger and system as at rest (the
    # protector's off state is also a valid DC solution, see README)
    v0 = cl['ocv'] if (cl['present'] and not cl['reverse'] and cl['plug_t'] is None) else 0.0
    vs0 = 4.5 if c['usb'] else v0
    ns = dict(BATT_PLUS=v0, BAT_P_C=v0, BAT_P=v0, BAT_CHG=v0, BAT_BYP=v0, MUX_IN1=v0, MUX_IN2=vs0, PROT_BAT=v0, CELL_MINUS=0, PROT_DOUT=v0,
              PROT_COUT=v0, PBval=1 if v0 > 1.5 else 0, VSYS=vs0, CHbuv=1 if v0 > 3.0 else 0,
              PROT_D=0, PROT_S2=0, REV_G=0 if v0 > 1.5 else max(v0, 4.2 if c['usb'] else 0.0))
    if c.get('loadsw'):
        ns['VSYS_SW'] = vs0
    ns['3V3'] = max(0.0, min(3.3, vs0 - 0.02)) if c.get('sw_on') is None else 0.0
    ns['SRbon'] = 1 if (vs0 > 1.8 and c.get('sw_on') is None) else 0
    if c.get('sw_on') is not None and c.get('loadsw'):
        ns['VSYS_SW'] = 0.0
    ns['CHok'] = 1 if c['usb'] else 0
    if c['usb']:
        u = c['usb']
        ns.update(FUramp=u, USB_VBUS=u, usb_conn=u, USB_5V=u - 0.05, VIN_USB=u - 0.45, VIN_CHG=u - 0.45, FUuv=1, FUuvp=1, FUovl=0,
                  FUtov=0)
    ns.update(c.get('nodeset', {}))
    # nodes that only a board trace separates from their parent start where it does (a study's
    # nodeset for BAT_P, e.g. the live-pad reverse case, must not be pulled back by them)
    for k, parent in (('BAT_CHG', 'BAT_P'), ('BAT_BYP', 'BAT_P'), ('MUX_IN2', 'VSYS'), ('VIN_USB', 'VIN_CHG')):
        if k in ns and k not in c.get('nodeset', {}):
            ns[k] = ns[parent]
    ctl = ['.nodeset ' + ' '.join('v(%s)=%g' % kv for kv in ns.items())]
    ctl += [c.get('opt', '.option method=gear reltol=2e-3 abstol=1e-9 vntol=1e-5 itl4=200'),
           '.tran 1u %g 0 %g%s' % (tstop, c['tmax'], ' uic' if c['uic'] else ''),
           '.control', 'set filetype=binary'] + ['stop when %s' % x for x in c.get('stop_on', [])] + ['run', 'write %s %s' % (datfile, ' '.join(vecs)), '.endc', '.end']
    return '\n'.join(s + [l for l in ctl if l]) + '\n'
