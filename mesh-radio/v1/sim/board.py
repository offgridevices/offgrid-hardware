# -*- coding: utf-8 -*-
"""The whole Mesh Radio v1 power path as one ngspice netlist, assembled from
powerlib.py and switched by a configuration dict, for the burst, shorts,
solar and reverse studies.

  USB-C -- 1 m cable -- TVS2200 -- TPS259470A -- USB_5V --RB060MM--+
  solar panel -- lead -- RB060MM -- TVS2200 -- TPS259470A ---------+-- VIN_CHG
                                                                    |
                                                         BQ25185 (IN, SYS = VSYS, BAT = BAT_P)
  cell -- leads -- JST -- CSD25485F5 -- BAT_P ----LM66100----------- VSYS -- TPS22965 -- VSYS_SW -- TPS62840 -- 3V3
     (- side: BQ29700 + SSM10N954L + 22 mOhm to GND)                 |
  BAT_P --IN1-- TPS2121 --IN2-- VSYS                                 |
                  OUT = PA_IN -- TPS63810 -- VPA -- QPA9510

PCB parasitics are estimates for a board that is not routed yet (README):
they are the TRACE_* values below and are replaced by extracted values when
the studies are re-run on the routed board.
"""
import powerlib as P

# --- PCB estimates (R includes the ground return; L ~1 nH/mm of loop) -------
TRACE_BAT = (0.006, 6e-9)      # JST pads -> reverse FET -> BAT_P node (~6 mm, 1 mm wide, 1 oz, + return)
TRACE_MUX1 = (0.005, 5e-9)     # BAT_P -> TPS2121 IN1
TRACE_PAIN = (0.003, 3e-9)     # TPS2121 OUT -> TPS63810 VIN (its caps)
TRACE_VPA = (0.005, 5e-9)      # TPS63810 VOUT -> QPA9510 VCC
TRACE_USB = (0.005, 5e-9)      # USB-C VBUS -> TVS / eFuse
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
        cell=dict(ocv=3.7, rint=0.15, reverse=False, plug_t=None, present=True),
        lm='gnd',                       # 'gnd' as drawn, 'vout' = CE to VSYS
        usb=None,                       # source voltage, or None
        usb_step=None,                  # (t, v2): USB source steps to v2 at t
        solar=None,                     # dict(voc, isc, ncell, temp_c)
        chg={},                         # BQ25185 overrides
        mux={}, bb={}, prot={},
        pr_force_low=False,             # proposed fix: a GPIO FET pulls PR1 low
        pa=dict(vset=4.0, inom=2.3, t_en=1e-3, t_apc=4e-3, t_rf=4.2e-3, burst=1.0, on=True),
        i3v3_idle=0.013, i3v3_tx=0.130,
        extra='',                       # extra netlist lines (shorts, loads)
        tstop=None, tmax=10e-6, uic=False,
        save=[], meas=[], lin_step=50e-6,
    )


def build(cfg, datfile):
    c = cfg
    pa = c['pa']
    t_off = pa['t_rf'] + pa['burst']
    s = ['* Mesh Radio v1 power path (sim/board.py)', P.MODELS]
    # ---------------------------------------------------------------- battery
    cl = c['cell']
    if cl['present']:
        s.append(P.cell('BT', 'BATT_PLUS', 'CELL_MINUS', cl['ocv'], cl['rint'], plug_t=cl['plug_t'],
                        reverse=cl['reverse'], llead=cl.get('llead', 0.1e-6)))
    else:
        s.append('Rnob1 BATT_PLUS 0 10Meg\nRnob2 CELL_MINUS 0 10Meg\n')
    s.append(P.battery_block('PB', lm=c['lm'], prot=c['prot'], trace_bat=TRACE_BAT))
    s.append(P.cap('cbat1', 'BAT_P', '0', 7e-6))      # C10u25 at BAT (charger)
    s.append(P.cap('cbat2', 'BAT_P', '0', 0.8e-6))    # C1u25 at mux IN1
    # ---------------------------------------------------------------- inputs
    if c['usb'] is not None:
        if c['usb_step']:
            t2, v2 = c['usb_step']
            s.append('Vusb usb_src 0 pwl(0 %g %g %g %g %g)' % (c['usb'], t2, c['usb'], t2 + 1e-6, v2))
        else:
            s.append('Vusb usb_src 0 %g' % c['usb'])
        s.append(P.rl('cab', 'usb_src', 'usb_conn', *CABLE_USB))
        s.append(P.rl('tusb', 'usb_conn', 'USB_VBUS', *TRACE_USB))
        s.append(P.tvs2200('tvsu', 'USB_VBUS'))
        s.append(P.cap('cvb', 'USB_VBUS', '0', 0.9e-6))
        s.append(P.efuse('FU', 'USB_VBUS', 'USB_5V', 1e6, 383e3, 1e6, 287e3, 2210))
        s.append(P.cap('c5v', 'USB_5V', '0', 2.5e-6) + 'R5vb USB_5V 0 47k\n')
        s.append(P.schottky('dusb', 'USB_5V', 'VIN_CHG'))
    if c['solar']:
        so = c['solar']
        s.append(P.panel('PV', 'pv_p0', '0', so['voc'], so['isc'], so['ncell'], so.get('temp_c', 25.0)))
        s.append('Vpvam pv_p0 pv_p 0\n')
        s.append(P.rl('pvl', 'pv_p', 'SOLAR_CONN', *LEAD_PANEL))
        s.append(P.schottky('dsol', 'SOLAR_CONN', 'SOLAR_RAW'))
        s.append(P.tvs2200('tvss', 'SOLAR_RAW'))
        s.append(P.cap('csr', 'SOLAR_RAW', '0', 0.8e-6))
        s.append(P.efuse('FS', 'SOLAR_RAW', 'VIN_CHG', 1e6, 510e3, 1e6, 137e3, 2490))
    s.append(P.cap('cvc1', 'VIN_CHG', '0', 0.9e-6) + P.cap('cvc2', 'VIN_CHG', '0', 8e-6) + 'Rvcl VIN_CHG 0 1Meg\n')
    s.append(P.bq25185('CH', 'VIN_CHG', 'VSYS', 'BAT_P', c['chg']))
    # ---------------------------------------------------------------- system rail
    tx = P.sat('min(time - %g, %g - time)/5e-6' % (pa['t_apc'], t_off + 0.1e-3)) if pa['on'] else '0'
    s.append(P.system_rail('SR', iload='(%g + %s*%g)' % (c['i3v3_idle'], tx, c['i3v3_tx'] - c['i3v3_idle'])))
    # ---------------------------------------------------------------- amplifier supply
    en = '(time > %g && time < %g)' % (pa['t_en'], t_off + 1e-3) if pa['on'] else '0'
    s.append(P.rl('tm1', 'BAT_P', 'MUX_IN1', *TRACE_MUX1))
    mux = dict(c['mux'])
    if c['pr_force_low']:
        mux['pr_ratio'] = 0.0
    s.append(P.tps2121('MX', 'MUX_IN1', 'VSYS', 'PA_IN', en=en, cfg=mux))
    s.append(P.cap('cpa1', 'PA_IN', '0', 14e-6) + P.cap('cpa2', 'PA_IN', '0', 14e-6))
    s.append(P.rl('tpi', 'PA_IN', 'BB_IN', *TRACE_PAIN))
    s.append(P.cap('cpa3', 'BB_IN', '0', 7e-6))
    s.append(P.tps63810('BB', 'BB_IN', 'BB_OUT', en, pa['vset'], c['bb']))
    s.append(P.cap('cvp1', 'BB_OUT', '0', 19e-6) + P.cap('cvp2', 'BB_OUT', '0', 19e-6))
    s.append(P.rl('tvp', 'BB_OUT', 'VPA', *TRACE_VPA))
    s.append(P.cap('cvp3', 'VPA', '0', 2.8e-6) + P.cap('cvp4', 'VPA', '0', 2.8e-6))
    apc = P.sat('min(time - %g, %g - time)/5e-6' % (pa['t_apc'], t_off + 0.1e-3)) if pa['on'] else '0'
    rf = 'max(0, min(1, (time - %g)/40e-6)) * (time < %g ? 1 : 0)' % (pa['t_rf'], t_off) if pa['on'] else '0'
    s.append(P.qpa9510('PA', 'VPA', apc, rf, pa['vset'], pa['inom']))
    # DC paths for nodes that only see caps and B current sources (10 Meg: < 0.5 uA)
    s.append(''.join('Rdc%d %s 0 10Meg\n' % (i, n) for i, n in enumerate(
        ['PA_IN', 'BB_IN', 'BB_OUT', 'VPA', 'VSYS', 'VSYS_SW', '3V3', 'BAT_P'])))
    s.append(c['extra'])
    # ---------------------------------------------------------------- analysis
    tstop = c['tstop'] or (t_off + 0.05)
    vecs = ['v(bat_p)', 'v(vsys)', 'v(vsys_sw)', 'v(3v3)', 'v(pa_in)', 'v(vpa)', 'v(vin_chg)',
            'i(vbt_am)' if cl['present'] else 'v(batt_plus)', 'v(pblm_i)', 'v(ch_isup)', 'v(ch_ichg)', 'v(ch_iin)',
            'v(mx_i1)', 'v(mx_i2)', 'v(mx_sel)', 'v(bb_iin)', 'v(pa_i)', 'v(pbocd)', 'v(pbuvp)', 'v(chbuvf)',
            'v(bbrst)', 'v(prot_vm,cell_minus)', 'v(prot_bat,cell_minus)', 'v(cell_minus)'] + c['save']
    # initial guesses: the protector on, charger and system as at rest (the
    # protector's off state is also a valid DC solution, see README)
    v0 = cl['ocv'] if (cl['present'] and not cl['reverse'] and cl['plug_t'] is None) else 0.0
    vs0 = 4.5 if c['usb'] else v0
    ns = dict(BATT_PLUS=v0, BAT_P_C=v0, BAT_P=v0, MUX_IN1=v0, PROT_BAT=v0, CELL_MINUS=0, PROT_DOUT=v0,
              PROT_COUT=v0, PBval=1 if v0 > 1.5 else 0, VSYS=vs0, VSYS_SW=vs0, CHbuv=1 if v0 > 3.15 else 0,
              PROT_D=0, PROT_S2=0)
    ns['3V3'] = max(0.0, min(3.3, vs0 - 0.02))
    ns['SRbon'] = 1 if vs0 > 1.8 else 0
    ns['CHok'] = 1 if c['usb'] else 0
    ns.update(c.get('nodeset', {}))
    ctl = ['.nodeset ' + ' '.join('v(%s)=%g' % kv for kv in ns.items())]
    ctl += [c.get('opt', '.option method=gear reltol=2e-3 abstol=1e-9 vntol=1e-5 itl4=200'),
           '.tran 1u %g 0 %g%s' % (tstop, c['tmax'], ' uic' if c['uic'] else ''),
           '.control', 'set filetype=binary', 'run', 'write %s %s' % (datfile, ' '.join(vecs)), '.endc', '.end']
    return '\n'.join(s + [l for l in ctl if l]) + '\n'
