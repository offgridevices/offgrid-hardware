# -*- coding: utf-8 -*-
"""Study 6: derating table (E4: every part at <= ~70 % of its rated
current, voltage and power in the worst case).

Reads the worst-case stresses the other studies wrote (<study>/stress.json)
and adds the rows that come straight from datasheets and the operating
points (dissipation and junction temperature at 60 C ambient, the sealed-
box case of E2).  Run the other studies first (sim/run_all.sh does).

Rules, fixed before running:
  'derate'  (continuous current / voltage / power of a part)  <= 70 % PASS,
            70-100 % FAIL (E4), > 100 % FAIL (over rating)
  'absmax'  (transient peaks against an absolute-maximum rating, where E4's
            70 % cannot apply - e.g. a supply pin's own operating voltage)
            < 95 % PASS, 95-100 % MARGINAL, > 100 % FAIL
  'rec'     (steady voltage on an IC pin against its recommended maximum)
            <= 100 % PASS, else FAIL
  'pulse'   (peak power for a short pulse against a continuous rating)
            reported only (pulse ratings are not published)

Outputs: results.txt, derating.png.   Run: python3 run.py
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import simlib as S

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(HERE, '..')
TA = 60.0


def tj(p, rth):
    return TA + p * rth


def datasheet_rows():
    st = []
    s = S.stress
    # thermal: dissipation -> Tj at 60 C ambient, against Tj max (125 C) - expressed as power vs (125-60)/RthJA
    p_bb = 4.0 * 2.3 / 0.92 - 4.0 * 2.3          # 3 W burst: PIN - POUT at 92 %
    st.append(s('TPS63810', 'U (buck-boost)', 'dissipation during a 3 W burst (92 %)', p_bb, 'W', (125 - TA) / 80.5,
                'derate', 'RthJA 80.5 C/W JEDEC -> Tj %.0f C at 60 C if continuous; bursts only (E2 thermal sim)' % tj(p_bb, 80.5)))
    p_bb1 = 2.7 * 1.0 / 0.92 - 2.7
    st.append(s('TPS63810', 'U (buck-boost)', 'dissipation at 1 W (92 %)', p_bb1, 'W', (125 - TA) / 80.5, 'derate',
                'Tj %.0f C at 60 C, continuous' % tj(p_bb1, 80.5)))
    p_pa = 4.0 * 2.3 - 3.16
    st.append(s('QPA9510', 'U (PA)', 'dissipation at 35 dBm (9.2 W DC, 3.2 W RF)', p_pa, 'W', (175 - 85) / 12.5, 'derate',
                'theta_jc 12.5 C/W: Tj = Tcase + %.0f C; Tj 175 C for 1e6 h MTTF, case <= 85 C' % (p_pa * 12.5)))
    p_pa1 = 2.7 * 1.0 - 1.0
    st.append(s('QPA9510', 'U (PA)', 'dissipation at 30 dBm', p_pa1, 'W', (175 - 85) / 12.5, 'derate',
                'Tj = Tcase + %.0f C' % (p_pa1 * 12.5)))
    st.append(s('TPS259470A', 'U (USB eFuse)', 'current at the charger input limit', 1.1, 'A', 5.5, 'derate', '5.5 A continuous'))
    st.append(s('TPS259470A', 'U (USB eFuse)', 'dissipation at 1.1 A', 1.1 ** 2 * 0.045, 'W', (125 - TA) / 74.5, 'derate',
                'RON 45 mOhm max, RthJA 74.5 C/W'))
    st.append(s('RB060MM-30', 'D (USB into charger)', 'forward current', 1.1, 'A', 2.0, 'derate', 'Io 2 A'))
    p_chg = (4.6 - 3.0) * 0.497 + (4.6 - 4.5) * 0.05
    st.append(s('BQ25185', 'U (charger)', 'dissipation, USB, 3.0 V cell at 497 mA', p_chg, 'W', (125 - TA) / 68.3, 'derate',
                'RthJA 68.3 C/W: Tj %.0f C at 60 C, above TREG 100 C: thermal regulation cuts the charge current'
                % tj(p_chg, 68.3)))
    st.append(s('TPS62840', 'U (3.3 V buck)', 'output current, transmit (130 mA)', 0.130, 'A', 0.75, 'derate', '750 mA rated'))
    st.append(s('TPS62840', 'U (3.3 V buck)', 'VIN at SYS regulation + SYS-OVP (4.5 V x 1.06)', 4.77, 'V', 6.5, 'rec',
                '6.5 V recommended, 7 V abs max'))
    st.append(s('TPS22965', 'U (main switch)', 'current, transmit + idle', 0.17, 'A', 6.0, 'derate', '6 A continuous'))
    st.append(s('TPS22965', 'U (main switch)', 'VIN/VBIAS at SYS-OVP', 4.77, 'V', 5.7, 'rec', '5.7 V recommended'))
    st.append(s('LM66100', 'U (cell-to-SYS)', 'VIN / VOUT at SYS-OVP', 4.77, 'V', 5.5, 'rec', '5.5 V recommended'))
    st.append(s('C10u 0603 10 V', 'C (VSYS_SW, 3V3)', 'voltage', 4.77, 'V', 10.0, 'derate', ''))
    st.append(s('C22u16 0805 16 V', 'C (PA_IN)', 'voltage', 4.77, 'V', 16.0, 'derate', 'IN2 = VSYS up to 4.77 V'))
    st.append(s('C10u25 0805 25 V', 'C (BAT_P, VSYS)', 'voltage', 4.77, 'V', 25.0, 'derate', ''))
    st.append(s('TPS2121', 'U (mux)', 'IN / OUT voltage', 4.77, 'V', 22.0, 'derate', ''))
    st.append(s('TPS2121', 'U (mux)', 'OV1/OV2 pins (1 M to BAT_P)', 4.4, 'V', 5.5, 'rec', '5.5 V recommended, 6 V abs'))
    st.append(s('BQ29700', 'U (protector)', 'BAT - VSS, 4.35 V HV cell + 330 R', 4.4, 'V', 8.0, 'rec', '8 V recommended'))
    st.append(s('SSM10N954L', 'Q (protector)', 'VSS, charging at SYS 4.5 V', 4.5, 'V', 12.0, 'derate', ''))
    st.append(s('TVS2200', 'D (USB clamp)', 'standoff, 5.5 V USB', 5.5, 'V', 22.0, 'derate', ''))
    return st


def main():
    rows = []
    for study in ('hotplug', 'reverse', 'shorts', 'burst', 'solar'):
        p = os.path.join(SIM, study, 'stress.json')
        if not os.path.exists(p):
            print('missing %s: run that study first' % p)
            continue
        for r in json.load(open(p)):
            r['study'] = study
            rows.append(r)
    for r in datasheet_rows():
        r['study'] = 'datasheet'
        rows.append(r)
    out = []
    for r in rows:
        pct = 100.0 * r['value'] / r['rating']
        k = r['kind']
        if k == 'derate':
            v = 'PASS' if pct <= 70 else 'FAIL'
        elif k == 'absmax':
            v = 'PASS' if pct < 95 else ('MARGINAL' if pct <= 100 else 'FAIL')
        elif k == 'rec':
            v = 'PASS' if pct <= 100 else 'FAIL'
        else:
            v = 'info'
        r['pct'] = pct
        r['verdict'] = v
        out.append(r)
    out.sort(key=lambda r: (r['part'], -r['pct']))
    L = ['Study 6: derating (E4).  derate: <= 70 % of rating; absmax: < 95 % of the absolute maximum (transients);',
         'rec: steady pin voltage within the recommended maximum; pulse: reported.  60 C ambient for the thermal rows.', '']
    L.append(S.table([[r['part'], r['ref'], r['qty'], '%.3g %s' % (r['value'], r['unit']), '%.3g %s' % (r['rating'], r['unit']),
                       '%.0f %%' % r['pct'], r['kind'], r['verdict'], r['study'], r['case']] for r in out],
                     ['part', 'where', 'quantity', 'worst case', 'rating', '%', 'rule', 'verdict', 'from', 'case / note']))
    L.append('')
    nf = sum(1 for r in out if r['verdict'] == 'FAIL')
    nm = sum(1 for r in out if r['verdict'] == 'MARGINAL')
    L.append('%d rows: %d FAIL, %d MARGINAL.' % (len(out), nf, nm))
    S.write_results(HERE, L)

    plt = S.style()
    sel = [r for r in out if r['kind'] in ('derate', 'absmax', 'rec')]
    fig, ax = plt.subplots(figsize=(11, 0.24 * len(sel) + 1.5))
    y = np.arange(len(sel))
    col = {'PASS': '#2b8a3e', 'MARGINAL': '#f59f00', 'FAIL': '#c2255c'}
    ax.barh(y, [min(r['pct'], 200) for r in sel], color=[col[r['verdict']] for r in sel])
    ax.axvline(70, color='0.3', lw=0.8, ls='--')
    ax.axvline(100, color='0.3', lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(['%s - %s' % (r['part'], r['qty'][:48]) for r in sel], fontsize=6)
    ax.invert_yaxis()
    ax.set_xlabel('% of rating (bars clipped at 200 %)')
    ax.set_title('E4 derating: green pass, amber marginal (abs max), red fail; dashed 70 %')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'derating.png'))


if __name__ == '__main__':
    main()
