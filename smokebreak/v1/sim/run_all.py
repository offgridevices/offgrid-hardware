#!/usr/bin/env python3
"""SmokeBreak v1 - run every simulation case against the board in src/circuit.py
(TPS48000, low-side shunt, INA181A2 + LMV331 peak path), check pass/fail, write plots and SIM.md.

Usage:  python3 run_all.py [case numbers...]      (default: all; SIM.md only on a full run)
Exit status is non-zero if any check FAILs (or a simulation does not converge).
"""
import os
import sys
import time
import datetime
import traceback
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import matplotlib.pyplot as plt

import simlib as S
from simlib import run, first_cross, integ, savefig, C

POOL = ThreadPoolExecutor(max_workers=4)
DERATE = 0.5          # SOA derating (Tc ~80 C instead of 25 C, part spread)

# ===========================================================================
# Device limits taken from datasheets (digitised where only a graph exists)
# ===========================================================================
# BSC040N10NS5 Diagram 3 (SOA, Tc = 25 C, single pulse), digitised: max ID [A]
SOA_V = np.array([3, 5, 10, 25, 50, 60, 70.0])
SOA_T = np.array([1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1e2])
SOA_I = np.array([
    [414, 550, 546, 223, 79, 54.6, 40],          # 10 us
    [414, 274, 122, 19.3, 4.87, 3.37, 2.47],     # 100 us
    [132, 47, 11.3, 1.84, 0.465, 0.322, 0.236],  # 1 ms
    [37.8, 13.6, 3.07, 0.528, 0.133, 0.0917, 0.0676],  # 10 ms
    [23.3, 8.35, 2.05, 0.325, 0.0815, 0.0564, 0.0416],  # 100 ms (~1.3 x DC, Zth)
    [17.9, 6.42, 1.58, 0.25, 0.0627, 0.0434, 0.032],    # DC
])
BSC_IDPULSE, BSC_IAS, BSC_EAS, BSC_VBR = 544.0, 50.0, 0.268, 100.0


def bsc_imax(v, t):
    v = min(max(v, 3.0), 70.0)
    t = min(max(t, 1e-5), 1e2)
    lv, lt = np.log10(v), np.log10(t)
    col = [np.interp(lv, np.log10(SOA_V), np.log10(row)) for row in SOA_I]
    return float(10 ** np.interp(lt, np.log10(SOA_T), col))


# DMP10H400SE Figure 12 (SOA on a minimum-pad board): power lines, W
def dmp_pmax(v, t):
    if t <= 1e-4:
        return min(12.0, 12.0 * (max(v, 30) / 30) ** -0.91) * v
    pts = {1e-3: 46.0, 1e-2: 16.0, 1e-1: 7.8, 1.0: 3.8}
    ks = sorted(pts)
    return float(10 ** np.interp(np.log10(t), np.log10(ks), np.log10([pts[k] for k in ks])))


def worst_window(t, p, v, win):
    """Highest average power over any window of length win, and the mean |v| in it."""
    n = max(4000, int((t[-1] - t[0]) / (win / 40)) + 1)
    n = min(n, 400000)
    tu = np.linspace(t[0], t[-1], n)
    pu = np.maximum(np.interp(tu, t, p), 0)
    vu = np.abs(np.interp(tu, t, v))
    dt = tu[1] - tu[0]
    e = np.concatenate([[0], np.cumsum(0.5 * (pu[1:] + pu[:-1]) * dt)])
    k = max(1, int(round(win / dt)))
    if k >= len(tu):
        return e[-1] / (tu[-1] - tu[0]), float(vu.mean())
    w = e[k:] - e[:-k]
    i = int(np.argmax(w))
    return float(w[i] / win), float(vu[i:i + k].mean())


def soa_bsc(t, p, vds, wins=(1e-5, 1e-4, 1e-3, 1e-2, 1e-1)):
    worst, rows = 0.0, []
    for w in wins:
        if t[-1] - t[0] < w:
            continue
        pw, vw = worst_window(t, p, vds, w)
        allowed = DERATE * max(vw, 3.0) * bsc_imax(max(vw, 3.0), w)
        rows.append((w, pw, vw, allowed))
        worst = max(worst, pw / allowed)
    return worst, rows


def soa_dmp(t, p, vds, wins=(1e-4, 1e-3, 1e-2, 1e-1, 1.0)):
    worst = 0.0
    for w in wins:
        if t[-1] - t[0] < w:
            continue
        pw, vw = worst_window(t, p, vds, w)
        worst = max(worst, pw / (DERATE * dmp_pmax(max(vw, 1.0), w)))
    return worst


DESIGN = {}


class Report:
    def __init__(self):
        self.checks, self.notes, self.fails = [], [], []

    def check(self, case, name, ok, detail=""):
        self.checks.append((case, name, bool(ok), detail))
        if not ok:
            self.fails.append(f"Case {case}: {name} - {detail}")

    def note(self, case, name, ok, detail=""):
        self.notes.append((case, name, bool(ok), detail))


REP = Report()


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
    return "\n".join(out)


def pf(ok):
    return "PASS" if ok else "**FAIL**"


# ===========================================================================
# Networks under comparison (all-ceramic; effective values at 60 V DC bias)
# ===========================================================================
NET_ASBUILT = dict(cin="2u", cd="1p", rd=1, csn="1p", rsn=1)                 # the circuit before this review
NET_REC = dict(cin="1u", cd="16u", rd=0.33, csn="12u", rsn=0.22)             # recommended, no Q11
NET_Q11 = dict(cin="2u", cd="4u", rd=0.33, csn="4u", rsn=0.47)               # previous rec, needs Q11 >= 11S
NET_NOQ3 = dict(cin="0.1u", cd="8u", rd=0.47, csn="4u", rsn=0.47)            # first no-Q11 try (fails case 3)
HSV_REC = 0.065        # hard-short LMV331 threshold on the 1 mOhm shunt (65 A, 58-72 A with 7 mV offset)
HSV_ALT = 0.080        # the coordinator's 80 mV
VIO_WORST = "7m"       # LMV331 max offset, applied so the hard-short trips late
PEAK_MAX = 50          # firmware cap on the programmable peak setting (LMV331 VICR ceiling ~52 A)
RISCP_REC = 40.2e3     # TPS48000 SCP: V = 2 uA x RISCP + 19 mV -> 99.4 mV = 99 A on 1 mOhm
VSCP_REC = "%.4f" % (2e-6 * RISCP_REC + 0.019)
K_REC = "recommended, no Q11 (1 µF + 16 µF/0.33 Ω damper, 12 µF/0.22 Ω snubber)"
K_Q11 = "Q11 alternative network (2 × 2.2 µF + 4 µF/0.33 Ω damper, 4 µF/0.47 Ω snubber)"
NET_Q11C = dict(cin="1u", cd="4u", rd=0.33, csn="4u", rsn=0.47)              # coordinator's: one 2.2 uF direct
Q11_GATE = "4.7 MΩ from VIN + 12 V zener"
Q11_PART = "Infineon BSC070N10LS5 (LCSC C3278731; 50 A / 55 mJ single-pulse avalanche, datasheet Rev 2.2)"
K_NOQ3 = "first no-Q11 try (0.1 µF + 8 µF/0.47 Ω damper, 4 µF/0.47 Ω snubber)"
NETS = {"pre-review (2 × 2.2 µF, no snubber)": NET_ASBUILT, K_REC: NET_REC, K_Q11: NET_Q11, K_NOQ3: NET_NOQ3}
COST = {"pre-review (2 × 2.2 µF, no snubber)": "$0 (reference)",
        K_REC: "≈ $1.10: 14 × 4.7 µF/100 V X7S 1210 (~$0.08) + 0.33 Ω and 0.22 Ω 1206; "
               "one of the two existing 2.2 µF removed; no Q11",
        K_Q11: "≈ $0.40 for the caps + Q11 BSC070N10LS5 ≈ $1.15 (LCSC, 100 pcs) ≈ $1.55",
        K_NOQ3: "≈ $0.42 (fails the 10S/14S short, case 3)"}


# ===========================================================================
# Case 1 - pre-charge (RPRE = 2 x 3.9 Ohm D2TO020), main close, part stress
# ===========================================================================
RPRE_ASKED = 7.8
GAP_MAX = 12.0        # firmware: never close the main switch across more than this (BSC040N10NS5 SOA)


def c1_run(tag, ncell, vcell, rpre, cload, pvtx, tmain=2.0, tpoff=2.0, c1="1p", rpu=47,
           qp_rd=0.15, qp_kp=6, tstop=1.0, tmax=200e-6):
    return run("case1_precharge.cir", tag, dict(
        ncell=ncell, vcell=vcell, rpre=rpre, cload=cload, pvtx=pvtx, tmain=tmain, tpoff=tpoff,
        c1=c1, rpu=rpu, qp_rd=qp_rd, qp_kp=qp_kp, tstop=tstop, tmax=tmax))


def pc_metrics(d):
    t, vin, vout = d["time"], d["vvin"], d["vvout"]
    r = vout / np.maximum(vin, 1e-3)
    t75 = first_cross(t, r, 0.75, t0=1e-3)
    t75 = (t75 - 1e-3) if t75 is not None else None      # pre-charge starts at 1 ms
    vfin = vout[-1]
    far = np.nonzero(np.abs(vout - vfin) > 0.01 * vfin + 0.05)[0]
    tset = float(t[far[-1]]) if len(far) else 0.0
    return dict(t75=t75, vfin=vfin, ratio=r[-1], gap=vin[-1] - vfin, tset=tset,
                ipk=float(d["ipre"].max()), epre=integ(t, d["ppre"]))


GATES = {"pre-review: PU 47 Ω, no Cdvdt": dict(rpu=47, c1="1p"),
         "R1 100 kΩ + C1 22 nF": dict(rpu="100k", c1="22n"),
         "R1 100 kΩ + C1 47 nF": dict(rpu="100k", c1="47n"),
         "R1 100 kΩ + C1 100 nF": dict(rpu="100k", c1="100n"),
         "R1 100 kΩ + C1 220 nF": dict(rpu="100k", c1="220n")}


def c1_seq(tag, n, vc, rpre, cload, pvtx, gate, qp=None):
    qp = qp or {}
    d0 = c1_run(tag + "_pc", n, vc, rpre, cload, pvtx, **qp)
    m = pc_metrics(d0)
    tmain = min(1.0, max(0.02, m["tset"] + 0.02))     # firmware: settled for 20 ms
    d = c1_run(tag, n, vc, rpre, cload, pvtx, tmain=tmain, tpoff=tmain + 0.4, tstop=tmain + 0.3,
               tmax=50e-6, **gate, **qp)
    t = d["time"]
    sel = t >= tmain - 1e-4
    tclose = first_cross(t, d["vvout"] / d["vvin"], 0.98, t0=tmain)
    closed = d["vgs"][-1] > 8 and d["vscp"].max() < 0.5 and d["vvout"][-1] > 0.98 * d["vvin"][-1]
    worst, rows = soa_bsc(t[sel], d["pq1"][sel], d["vds1"][sel])
    return dict(m=m, d=d, tmain=tmain, gap=float(np.interp(tmain, t, d["vvin"] - d["vvout"])),
                closed=closed, tclose=(tclose - tmain) if tclose else None, scp=d["vscp"].max() > 0.5,
                iq1=float(d["iq1"][sel].max()), pq1=float(d["pq1"][sel].max()),
                eq1=integ(t, np.maximum(d["pq1"], 0), tmain), soa=worst, soarows=rows)


def case1():
    L = []
    RP = [RPRE_ASKED, 6.8, 10, 15, 22]
    NS = list(range(8, 15))
    VCA = [3.5, 3.7, 3.85, 4.2, 4.35]
    VC_REQ = [3.7, 3.85, 4.2, 4.35]
    jobs = {(rp, n, vc): POOL.submit(c1_run, f"c1a_{rp}_{n}_{vc}", n, vc, rp, 2200e-6, 15, tmax=1e-3)
            for rp in RP for n in NS for vc in VCA}
    res = {k: pc_metrics(f.result()) for k, f in jobs.items()}
    rows = []
    for rp in RP:
        ok = all(res[(rp, n, vc)]["t75"] is not None and res[(rp, n, vc)]["t75"] <= 1.0 for n in NS for vc in VC_REQ)
        stalls = [f"{n}S@{vc}" for n in NS for vc in VCA if res[(rp, n, vc)]["t75"] is None]
        slow = max((res[(rp, n, vc)]["t75"] or 9) for n in NS for vc in VC_REQ)
        rows.append([f"{rp:g} Ω" + (" (2 × 3.9 Ω D2TO020)" if rp == RPRE_ASKED else ""), pf(ok),
                     "%.0f ms" % (slow * 1e3) if slow < 9 else "never", ", ".join(stalls) or "-"])
        if rp == RPRE_ASKED:
            REP.check(1, "(a) 2 × 3.9 Ω reaches 75 % within 1 s, 8S-14S at ≥ 3.7 V/cell, 2200 µF + 15 W VTX", ok,
                      "slowest %.0f ms" % (slow * 1e3) if slow < 9 else "stalls")
    rp = RPRE_ASKED
    DESIGN["RPRE"] = rp
    L.append("### (a) 8S-14S, 2200 µF + 15 W VTX (+1 W FC/RX)\n")
    L.append("Board per circuit.py: Q3 DMP10H400SE driven through 47 kΩ by two BC817s, D3 SS2H10, RPRE. "
             "Requirement: VOUT > 75 % of VIN within 1 s at 3.7-4.35 V/cell (3.5 V/cell shown for "
             "information).\n")
    L.append(table(["RPRE", "(a)", "slowest t75", "stalls below 75 % (any V/cell)"], rows))
    rows = [[f"{n}S"] + [("%.0f ms" % (res[(rp, n, vc)]["t75"] * 1e3)) if res[(rp, n, vc)]["t75"]
                         else "stall %.1f V" % res[(rp, n, vc)]["vfin"] for vc in VCA] for n in NS]
    L.append(f"\nTime to 75 % with 2 × 3.9 Ω:\n")
    L.append(table(["pack"] + [f"{v} V/cell" for v in VCA], rows))
    L.append("\nThe limit is getting past the VTX's 6 V UVLO: R < 6 V·(VIN − 6 V − ~0.7 V)/P. 7.8 Ω "
             "clears it for every 8S pack down to 3.5 V/cell with 16 W of load.\n")

    # ---------------- (b) main close: gate network vs BSC040N10NS5 SOA ----------------
    L.append("### (b) Closing the main switch: gate network against the BSC040N10NS5 SOA\n")
    L.append("**The BSC040N10NS5's SOA is a linear-mode SOA with a thermal-instability slope: at 25 V it "
             "allows only 1.84 A for 1 ms, 0.53 A for 10 ms and 0.25 A DC (Diagram 3, digitised; "
             "power falls as 1/V).** Closing the main switch across a large gap is therefore not "
             "allowed. The firmware waits until the pre-charge has settled (VOUT within 1 % for 20 ms), "
             "then closes. Pass = worst sliding-window power (10 µs-100 ms) ≤ 50 % of the SOA at that "
             "window's mean Vds, the switch closes, and the SCP does not trip on the inrush.\n")
    sweep_cases = {"8S 3.7 V/cell, 2200 µF, 15 W": (8, 3.7, 2200e-6, 15),
                   "8S 3.7 V/cell, 5000 µF, 15 W": (8, 3.7, 5000e-6, 15),
                   "14S LiHV, 5000 µF, 15 W": (14, 4.35, 5000e-6, 15)}
    sw = {}
    for gi, (g, gv) in enumerate(GATES.items()):
        for si, (s, (n, vc, cl, pv)) in enumerate(sweep_cases.items()):
            sw[(g, s)] = POOL.submit(c1_seq, f"c1g_{gi}_{si}", n, vc, rp, cl, pv, gv)
    sw = {k: f.result() for k, f in sw.items()}
    rows = []
    for (g, s), r in sw.items():
        rows.append([g, s, "%.1f V" % r["gap"], ("%.0f ms" % (r["tclose"] * 1e3)) if r["closed"] else
                     ("SCP trip" if r["scp"] else "not closed"), "%.0f A" % r["iq1"], "%.0f W" % r["pq1"],
                     "%.0f %%" % (100 * r["soa"]), pf(r["closed"] and r["soa"] <= 1)])
    L.append(table(["gate network", "case", "gap at close", "close", "Q1 peak I", "Q1 peak P",
                    "worst % of derated SOA", "result"], rows))
    gsel = None
    for g in list(GATES)[1:]:
        if all(sw[(g, s)]["closed"] and sw[(g, s)]["soa"] <= 1 for s in sweep_cases):
            gsel = g
            break
    gsel = gsel or list(GATES)[-1]
    DESIGN["gate"] = gsel
    asb_ok = all(sw[(list(GATES)[0], s)]["closed"] and sw[(list(GATES)[0], s)]["soa"] <= 1 for s in sweep_cases)
    REP.note(1, "as-built gate (PU 47 Ω, no Cdvdt) closes within SOA and without SCP trip", asb_ok,
             "inrush through the remaining gap trips the 50 A SCP or exceeds SOA" if not asb_ok else "")
    REP.check(1, f"(b) chosen Cdvdt network closes settled 8S-14S cases within derated SOA ({gsel})",
              all(sw[(gsel, s)]["closed"] and sw[(gsel, s)]["soa"] <= 1 for s in sweep_cases))
    L.append(f"\n**Chosen: {gsel}** (gate → GND through 10 Ω; PD stays direct to the gates for fast "
             "turn-off; PU's 47 Ω becomes 100 kΩ). Output slew ≈ (11 V − 4.6 V)/(R1·C1) ≈ "
             f"{6.4/(1e5*float(GATES[gsel]['c1'].rstrip('n'))*1e-9):.0f} V/s; gate current 64 µA < the "
             "100 µA minimum charge-pump current. A 15 V gate-source zener (BZT52C15) is then needed: "
             "C1 holds the gate while SRC collapses in a short (case 3).\n")

    # 2S-7S with 10 W VTX: stalls, gap, close
    bj = {}
    gv = GATES[gsel]
    for n in range(2, 8):
        for vc in (3.5, 4.35):
            bj[(f"{n}S @ {vc}", "7.8 Ω")] = POOL.submit(c1_seq, f"c1b_{n}_{vc}", n, vc, rp, 2200e-6, 10, gv)
            if n <= 7:
                bj[(f"{n}S @ {vc}", "3.9 Ω tap")] = POOL.submit(c1_seq, f"c1t_{n}_{vc}", n, vc, 3.9, 2200e-6, 10, gv)
    bres = {k: f.result() for k, f in bj.items()}
    rows, ok78, oktap = [], True, True
    refused = []
    for (pk, var), r in bres.items():
        good = r["closed"] and r["soa"] <= 1
        if not good and r["gap"] > GAP_MAX:
            refused.append(f"{pk} ({var}, gap {r['gap']:.1f} V)")
            good = None
        if var == "7.8 Ω":
            ok78 &= good is not False
        else:
            oktap &= good is not False
        st = ("75 %% at %.0f ms" % (r["m"]["t75"] * 1e3)) if r["m"]["t75"] else "stall %.1f V" % r["m"]["vfin"]
        rows.append([pk, var, st, "%.1f V" % r["gap"], ("%.0f ms" % (r["tclose"] * 1e3)) if r["closed"] else "no",
                     "%.0f W" % r["pq1"], "%.2f J" % r["eq1"], "%.0f %%" % (100 * r["soa"]),
                     "refused (gap > %g V)" % GAP_MAX if good is None else pf(good)])
    REP.check(1, f"(b) 2S-7S, 2200 µF + 10 W VTX, 2 × 3.9 Ω: every close within SOA, or refused by firmware when the "
                 f"gap > {GAP_MAX:g} V", ok78)
    r78 = [x for x in refused if "7.8" in x]
    REP.note(1, "(b) every 2S-7S drone with a 10 W VTX can be powered with 2 × 3.9 Ω", not r78,
             "refused: " + "; ".join(r78) if r78 else "")
    DESIGN["refused"] = r78
    REP.note(1, "(b) 2S-7S with a 3.9 Ω tap (second pre-charge switch at the D2TO020 mid-point)", oktap, "")
    L.append("\n2S-7S with 2200 µF + 10 W VTX (+1 W FC), chosen gate network; '3.9 Ω tap' = a second "
             "pre-charge P-FET feeding the mid-point of the two D2TO020s for ≤ 7S:\n")
    L.append(table(["pack", "RPRE", "pre-charge", "gap at close", "closed", "Q1 peak P", "E(Q1)",
                    "% of derated SOA", "result"], rows))

    # ---------------- (c) energy per resistor, Q3 (pre-charge FET), D3 ----------------
    cj = {"14S LiHV, 2200 µF, 15 W": (14, 4.35, 2200e-6, 15), "6S LiHV, 5000 µF, 10 W": (6, 4.35, 5000e-6, 10),
          "14S LiHV, 5000 µF, 15 W (worst)": (14, 4.35, 5000e-6, 15)}
    qpalt = dict(qp_rd=0.03, qp_kp=25)
    cf = {k: POOL.submit(c1_seq, f"c1c_{i}", *v[:2], rp, v[2], v[3], gv) for i, (k, v) in enumerate(cj.items())}
    cfa = POOL.submit(c1_seq, "c1c_alt", 14, 4.35, rp, 5000e-6, 15, gv, qpalt)
    rows = []
    emax, qpw, d3i2t = 0, 0, 0
    for k, f in cf.items():
        r = f.result()
        d = r["d"]
        t = d["time"]
        sel = t <= r["tmain"] + 0.3
        e = integ(t[sel], d["ppre"][sel])
        emax = max(emax, e)
        qw = soa_dmp(t[sel], d["pqp"][sel], np.full(sel.sum(), 3.0))
        qpw = max(qpw, qw)
        i2t = integ(t[sel], d["ipre"][sel] ** 2)
        d3i2t = max(d3i2t, i2t)
        rows.append([k, "%.2f A" % d["ipre"].max(), "%.0f W" % (d["ppre"].max() / 2), "%.2f J" % e,
                     "%.2f J" % (e / 2), "%.0f W / %.2f J" % (d["pqp"].max(), integ(t[sel], d["pqp"][sel])),
                     "%.0f %%" % (100 * qw), "%.2f A²s" % i2t])
    ra = cfa.result()
    da = ra["d"]
    sela = da["time"] <= ra["tmain"] + 0.3
    qalt = soa_dmp(da["time"][sela], da["pqp"][sela], np.full(sela.sum(), 3.0))
    ac05 = 10.0                     # D2TO020C3R900 single pulse at 100 ms, datasheet curve (~10 J)
    abort = 15.0
    L.append("\n### (c) Energy per D2TO020, pre-charge FET and diode\n")
    L.append(table(["attempt", "peak I", "peak P per resistor", "E(RPRE) total", "E per D2TO020",
                    "Q3 DMP10H400SE peak P / E", "Q3 % of derated SOA", "D3 ∫I²dt"], rows))
    vin14 = 14 * 4.35
    L.append(f"\nVishay D2TO020C3R900 pulse capability (datasheet single-pulse curve at 100 ms): "
             f"**≈ {ac05:.0f} J per resistor**. Two in series share the energy "
             f"equally. Worst normal attempt: **{emax/2:.1f} J per resistor** ({100*emax/2/ac05:.0f} % of the "
             f"chart value). At a {abort:.0f} J abort budget: **{abort/2:.1f} J per resistor** "
             f"({100*abort/2/ac05:.0f} %). Peak power {vin14**2/rp/2:.0f} W per resistor. Recommended: lower the "
             f"firmware abort budget to 12 J (6 J each, {100*6/ac05:.0f} %), keep the 1 s timeout and the "
             "NTC cool-down; 2 × 3.9 Ω D2TO020 then works.\n")
    L.append(f"Q3 (DMP10H400SE, 0.2-0.25 Ω, SOT-223, min-pad SOA 46 W/1 ms, 16 W/10 ms, 7.8 W/100 ms): worst "
             f"{100*qpw:.0f} % of the derated SOA (the slow 47 kΩ turn-on crosses the linear region and the "
             f"I²R peak is ~7 A × 1.7 V). With a ≈ 30 mΩ 100 V P-FET the same attempt uses {100*qalt:.0f} %. "
             f"D3 SS2H10: ∫I²dt ≤ {d3i2t:.2f} A²s against ≈ 10 A²s for its 50 A/8.3 ms IFSM — adequate.\n")
    REP.check(1, "(c) normal attempt ≤ 12 J (6 J per D2TO020 3.9 Ω, ~60 % of its pulse rating)", emax <= 12.0,
              "max %.1f J" % emax)
    REP.note(1, "(c) Q3 DMP10H400SE (pre-review) within 50 % of its SOA during pre-charge", qpw <= 1,
             "%.0f %% of derated SOA" % (100 * qpw))
    REP.check(1, "(c) pre-charge FET, recommended ≤ 50 mΩ class (DMP10H400SE SOA limits applied), within 50 %",
              qalt <= 1, "%.0f %%" % (100 * qalt))
    DESIGN["qp_ok"] = qpw <= 1
    DESIGN["qp_pct"] = qpw
    DESIGN["qp_alt_pct"] = qalt
    DESIGN["ac05"] = (emax / 2, abort / 2, ac05)

    # plot
    fig, ax = plt.subplots(2, 2, figsize=(11, 7))
    for j, r_ in enumerate(RP):
        d = c1_run(f"c1p_{r_}", 8, 3.7, r_, 2200e-6, 15)
        ax[0, 0].plot(d["time"] * 1e3, d["vvout"], color=C[j], label=f"RPRE {r_:g} Ω")
    ax[0, 0].axhline(0.75 * 8 * 3.7, color=S.INK2, ls="--", lw=1)
    ax[0, 0].text(600, 0.75 * 8 * 3.7 - 1.6, "75 % of VIN", color=S.INK2)
    ax[0, 0].set(title="(a) 8S 3.7 V/cell, 2200 µF + 15 W VTX: VOUT vs RPRE", xlabel="ms", ylabel="V")
    ax[0, 0].legend(loc="lower right", fontsize=7)
    r = sw[(gsel, "14S LiHV, 5000 µF, 15 W")]
    d = r["d"]
    tt = (d["time"] - r["tmain"]) * 1e3
    ax[0, 1].plot(tt, d["vvin"], color=C[0], label="VIN")
    ax[0, 1].plot(tt, d["vvout"], color=C[1], label="VOUT")
    ax[0, 1].set(title=f"(b) 14S LiHV 5000 µF: settle, then close ({gsel})", xlabel="ms from INP high",
                 ylabel="V", xlim=(-100, 100), ylim=(50, 63))
    ax[0, 1].legend()
    ax[1, 1].plot(tt, d["pq1"], color=C[0])
    ax[1, 1].set(title="(b) Q1 power during that close", xlabel="ms from INP high", ylabel="W", xlim=(-2, 30))
    for k_, (lab, f) in enumerate(cf.items()):
        d = f.result()["d"]
        ax[1, 0].plot(d["time"] * 1e3, np.cumsum(np.r_[0, 0.5 * (d["ppre"][1:] + d["ppre"][:-1]) * np.diff(d["time"])]) / 2,
                      color=C[k_], label=lab)
    ax[1, 0].axhline(ac05, color=C[7], ls="--", lw=1)
    ax[1, 0].text(10, ac05 - 0.8, "D2TO020 3.9 Ω pulse capability ≈ 11 J", color=C[7], fontsize=7)
    ax[1, 0].set(title="(c) energy per D2TO020 (half of RPRE)", xlabel="ms", ylabel="J", xlim=(0, 500))
    ax[1, 0].legend(fontsize=7, loc="center right")
    fig.tight_layout()
    savefig(fig, "case1_precharge.png")
    return "\n".join(L)


# ===========================================================================
# Case 2 - hot plug at the input (both polarities)
# ===========================================================================
def c2m(d):
    return dict(vin=d["vvin"].max(), vinm=d["vvin"].min(), vs=d["vxppvsf"].max(), vsm=d["vxppvsf"].min(),
                srcm=d["vsrc"].min(), ib=np.abs(d["ivib"]).max(), q3=d["vq3"].max(), iq3=np.abs(d["ivq3"]).max())


def case2():
    L = ["14S LiHV (60.9 V, 3 mΩ/cell + 3 mΩ lead, 250 nH) plugged into the input with an ideal contact; "
         "main switch and pre-charge off. Forward: peak at the Q1 drain (VIN) and the TPS48000 VS pin "
         "< 90 V. Reversed: the TPS48000 tolerates −65 V on VS, SRC, CS± and PU/PD/BST (datasheet "
         "SLUSEZ1B §5.1, verified), and SRC follows VIN through Q1's body diode and *holds* the most "
         "negative value (body diode = peak detector). Static reversed 14S LiHV puts SRC at −60.2 V "
         "(4.8 V margin); the plug-in ring must stay inside that. The recommended network is also run "
         "with its damper capacitance −20 % and the direct capacitance +20 % (X7S bias/tolerance). "
         "TVS SMBJ64CA (the board's) at its maximum breakdown (78.6 V) and 103 V clamp at 5.8 A. Q11 is "
         "modelled with the BSC040N10NS5 VDMOS (same 100 V SuperSO8 class) and judged against the fitted "
         "BSC070N10LS5's 50 A / 55 mJ avalanche rating.\n"]
    variants = {k: dict(v) for k, v in NETS.items()}
    variants[K_REC + ", tolerance: damper C −20 %, direct C +20 %"] = dict(NET_REC, cin="1.2u", cd="12.8u")
    variants[K_Q11 + " + Q11"] = dict(NET_Q11, q3byp="1G", rq3g="4.7Meg")      # the board's gate network
    jobs = {}
    for vk, vv in variants.items():
        jobs[(vk, "+")] = POOL.submit(run, "case2_hotplug.cir", f"c2p_{len(jobs)}", dict(vv, vcell=4.35))
        jobs[(vk, "-")] = POOL.submit(run, "case2_hotplug.cir", f"c2n_{len(jobs)}", dict(vv, vcell=-4.35))
    dat = {k: f.result() for k, f in jobs.items()}
    res = {k: c2m(d) for k, d in dat.items()}
    rows, recok = [], True
    for vk in variants:
        a, b = res[(vk, "+")], res[(vk, "-")]
        q3 = "q3byp" in variants[vk]
        okf = a["vin"] < 90 and a["vs"] < 90
        okr = (b["srcm"] >= -65 and b["vsm"] >= -65) and (not q3 or b["iq3"] < BSC_IAS)
        rows.append([vk, COST.get(vk, ""), "%.1f V" % a["vin"], "%.1f V" % a["vs"], pf(okf), "%.1f V" % b["vinm"],
                     "%.1f V" % b["srcm"], "%.1f V" % b["vsm"],
                     ("Q11 %.0f V / %.0f A" % (b["q3"], b["iq3"])) if q3 else "-", pf(okr)])
        if vk.startswith("pre-review"):
            REP.note(2, "pre-review: forward hot plug < 90 V", okf, "%.0f V" % a["vin"])
            REP.note(2, "pre-review: reversed hot plug keeps SRC/VS ≥ −65 V", okr, "SRC %.0f V" % b["srcm"])
        elif vk.startswith("recommended"):
            recok &= okf and okr
        elif vk.endswith("+ Q11"):
            REP.check(2, f"Q11 alternative + Q11 ({Q11_GATE}): forward hot plug < 90 V, reversed harmless "
                         "(SRC/VS ≥ −65 V, Q11 avalanche < 50 A)", okf and okr,
                      "VIN %.1f V, Q11 %.0f A" % (a["vin"], b["iq3"]))
        elif vk == K_NOQ3:
            REP.note(2, "first no-Q11 try: forward and reversed hot plug", okf and okr, "SRC %.1f V" % b["srcm"])
    istb = (60.9 - 12.0) / 4.7e6
    REP.note(2, "Q11 gate network standby current at 14S LiHV (SPEC: < 30 µA off)", istb < 30e-6,
             "%.1f µA through the 4.7 MΩ (47 kΩ would draw 1.04 mA)" % (istb * 1e6))
    rr = res[(K_REC, "-")]
    rt = res[(K_REC + ", tolerance: damper C −20 %, direct C +20 %", "-")]
    REP.check(2, "recommended (no Q11): forward 14S LiHV hot plug < 90 V, reversed keeps SRC/VS ≥ −65 V, "
                 "also at −20 %/+20 % capacitance", recok, "SRC %.1f V (tol. %.1f V)" % (rr["srcm"], rt["srcm"]))
    DESIGN["rev_rec"] = (rr["srcm"], rt["srcm"])
    L.append(table(["input network", "cost", "fwd VIN peak", "fwd VS peak", "fwd", "rev VIN min", "rev SRC min",
                    "rev VS min", "Q11 stress", "rev"], rows))
    nmax = {}
    for ni, nk in enumerate((K_Q11, "pre-review (2 × 2.2 µF, no snubber)")):
        fs = {n: POOL.submit(run, "case2_hotplug.cir", f"c2r_{ni}_{n}", dict(NETS[nk], ncell=n, vcell=-4.35))
              for n in range(6, 15)}
        okn = [n for n, f in fs.items() if c2m(f.result())["srcm"] >= -65]
        nmax[nk] = max(okn) if okn else 0
    L.append("\nWithout Q11, a reversed hot plug stays inside −65 V up to "
             + ", ".join(f"**{v}S LiHV** ({k.split(' (')[0]})" for k, v in nmax.items())
             + "; the recommended network covers 14S.\n")
    DESIGN["rev_nmax_noq3"] = nmax
    L.append("The reversed plug wants little capacitance directly on VIN and the rest behind a resistor; the "
             "short (case 3) wants low-impedance capacitance to absorb the battery lead's current at turn-off. "
             "The first no-Q11 try (0.1 µF direct, 8 µF/0.47 Ω) met the first need and failed the second. "
             "The recommended network meets both by making the damper big (16 µF, so its R can be 0.33 Ω), "
             "keeping 1 µF direct, and moving the rest of the short-circuit absorption to a stronger output "
             "snubber (12 µF/0.22 Ω), which the reversed input plug never sees. Q11 is therefore not needed.\n")
    fig, ax = plt.subplots(1, 2, figsize=(12, 3.8))
    for j, vk in enumerate(variants):
        d = dat[(vk, "+")]
        ax[0].plot(d["time"] * 1e6 - 1, d["vvin"], color=C[j], label=vk.split(" (")[0])
        d = dat[(vk, "-")]
        ax[1].plot(d["time"] * 1e6 - 1, d["vsrc"], color=C[j], label=vk.split(" (")[0])
    ax[0].axhline(90, color=C[7], ls="--", lw=1)
    ax[1].axhline(-65, color=C[7], ls="--", lw=1)
    ax[0].set(title="Forward 14S LiHV plug-in: VIN (Q1 drain)", xlabel="µs", ylabel="V", xlim=(-0.5, 20))
    ax[1].set(title="Reversed 14S LiHV plug-in: TPS48000 SRC", xlabel="µs", ylabel="V", xlim=(-0.5, 20))
    ax[0].legend(fontsize=6, loc="lower right")
    ax[1].legend(fontsize=6, loc="upper right")
    fig.tight_layout()
    savefig(fig, "case2_hotplug.png")
    return "\n".join(L)


# ===========================================================================
# Case 3 - short circuit while ON
# ===========================================================================
def c3m(d, t0=10e-6):
    t = d["time"]
    on = t >= t0
    iq = d["iq1"]
    tp = float(t[np.argmax(iq)])
    after = np.nonzero((t > tp) & (iq < 1.0))[0]
    av = on & (d["vds1"] > BSC_VBR - 1.0)
    return dict(ipk=float(iq.max()), tcut=(float(t[after[0]]) - t0) if len(after) else None,
                eq1=integ(t, np.maximum(d["pq1"], 0), t0), vds1=float(d["vds1"][on].max()),
                vds2=float(d["vds2"][on].max()), vin=float(d["vvin"][on].max()), vs=float(d["vxppvsf"][on].max()),
                src=float(d["vsrc"][on].min()), vgs=float(d["vgs"][on].max()), prb=float(d["vprobe"][on].max()),
                aval=float(iq[av].max()) if av.any() else 0.0, scp=d["vscp"].max() > 0.5)


def c3ok(m, prb_rating):
    return (m["vds1"] < BSC_VBR - 1 and m["vds2"] < BSC_VBR - 1 and m["vs"] < 100 and m["src"] >= -65
            and m["vgs"] < 19 and m["ipk"] < BSC_IDPULSE and m["prb"] < prb_rating and m["tcut"] is not None)


def case3():
    rec = dict(NET_REC, hsv=HSV_REC, vio2=VIO_WORST, pbv=160, rz="1m", vscp=VSCP_REC,
               c1=GATES[DESIGN.get("gate", "R1 100 kΩ + C1 22 nF")]["c1"])
    variants = {"pre-review": dict(NET_ASBUILT, hsv=10, pbv=33),
                "recommended": rec,
                "recommended, hard-short at 80 mV": dict(rec, hsv=HSV_ALT),
                "first no-Q11 try (0.1 µF + 8 µF/0.47 Ω, 4 µF/0.47 Ω), hard-short 80 mV": dict(rec, hsv=HSV_ALT, **NET_NOQ3),
                "Q11 alternative network": dict(rec, **NET_Q11),
                "Q11 network with one 2.2 µF direct (1 µF + 4 µF/0.33 Ω, 4 µF/0.47 Ω)": dict(rec, **NET_Q11C)}
    jobs = {}
    for vk, vv in variants.items():
        for n in (1, 6, 10, 14):
            for tp in ("0.36u", "1.05u"):
                jobs[(vk, n, tp)] = POOL.submit(run, "case3_short.cir", f"c3_{len(jobs)}",
                                                dict(vv, ncell=n, tpd_inp=tp, thr_a=PEAK_MAX))
    extra = {"recommended, SCP only (comparators dead)": dict(rec, hsv=10, thr_a=1e3),
             "recommended without the hard-short comparator": dict(rec, hsv=10, thr_a=PEAK_MAX),
             "recommended, 15 mΩ/cell pack": dict(rec, rcell="15m", thr_a=PEAK_MAX),
             "recommended, 300 nH drone leads": dict(rec, lout="300n", thr_a=PEAK_MAX),
             "recommended, 300 nH drone leads, hard-short at 80 mV": dict(rec, lout="300n", hsv=HSV_ALT, thr_a=PEAK_MAX),
             "Q11 alternative network, 300 nH drone leads": dict(rec, lout="300n", thr_a=PEAK_MAX, **NET_Q11),
             "Q11 alternative network, 15 mΩ/cell pack": dict(rec, rcell="15m", thr_a=PEAK_MAX, **NET_Q11),
             "Q11 network with one 2.2 µF direct, 300 nH drone leads": dict(rec, lout="300n", thr_a=PEAK_MAX, **NET_Q11C)}
    for i, (k, v) in enumerate(extra.items()):
        jobs[(k, 14, "1.05u")] = POOL.submit(run, "case3_short.cir", f"c3x_{i}", dict(v, ncell=14, tpd_inp="1.05u"))
    res = {k: f.result() for k, f in jobs.items()}
    rows, recok, q11ok, okv = [], True, True, {}
    for (vk, n, tp), d in res.items():
        m = c3m(d)
        rating = 30 if vk == "pre-review" else 150
        ok = c3ok(m, rating)
        okv.setdefault(vk, []).append(ok)
        if vk.startswith("recommended") and "SCP only" not in vk and "without the hard-short" not in vk:
            recok &= ok
        if vk.startswith("Q11 alternative"):
            q11ok &= ok
        rows.append([vk, f"{n}S", tp.replace("u", " µs"), "%.0f A" % m["ipk"],
                     "%.2f µs" % (m["tcut"] * 1e6) if m["tcut"] else "-", "%.1f V" % m["vds1"],
                     ("%.0f A" % m["aval"]) if m["aval"] else "-", "%.1f V" % m["vin"], "%.1f V" % m["src"],
                     "%.1f V" % m["vgs"], "%.1f V (%d V part)" % (m["prb"], rating), "%.1f mJ" % (1e3 * m["eq1"]), pf(ok)])
    REP.check(3, "recommended (no Q11, hard-short LMV331 at 65 mV and at 80 mV, 7 mV late offset): 1S/6S/10S/14S "
                 "short, INP delay typ and max, worn pack, 300 nH leads: no avalanche, SRC ≥ −65 V, Vgs < 19 V, "
                 "probe switch inside rating", recok)
    REP.check(3, "Q11 alternative network (65 mV hard-short, RISCP 40.2 kΩ): 1S/6S/10S/14S short, INP delay typ "
                 "and max, worn pack, 300 nH leads: no avalanche, SRC ≥ −65 V, Vgs < 19 V", q11ok)
    for vk in variants:
        if vk not in ("recommended", "recommended, hard-short at 80 mV", "Q11 alternative network"):
            REP.note(3, f"{vk} survives the short at 1S-14S", all(okv[vk]),
                     "%d of %d cases fail" % (okv[vk].count(False), len(okv[vk])))
    m = c3m(res[("Q11 network with one 2.2 µF direct, 300 nH drone leads", 14, "1.05u")])
    REP.note(3, "Q11 network with one 2.2 µF direct, 14S, 300 nH drone leads", c3ok(m, 150),
             "Q1 Vds %.1f V, avalanche %.0f A" % (m["vds1"], m["aval"]))
    for k in ("recommended without the hard-short comparator", "recommended, SCP only (comparators dead)"):
        m = c3m(res[(k, 14, "1.05u")])
        REP.note(3, f"{k}, 14S", c3ok(m, 150), "peak %.0f A, Q1 avalanche %.0f A" % (m["ipk"], m["aval"]))
    L = ["Board ON (gate 11 V above source). At t = 0 a 10 mΩ short closes at the drone end of 10 cm "
         "leads (150 nH round trip; drone 2200 µF/30 mΩ bulk at the same point); battery lead 250 nH. "
         "Trip paths: TPS48000 SCP (pre-review RISCP 15.4 kΩ → 49.8 mV = 50 A; recommended 40.2 kΩ → "
         "99 mV = 99 A, ≥ 78 A at the datasheet's ±22 %, so it never pre-empts the peak setting; tSC "
         "≤ 4 µs with TMR open); the programmable peak path (INA181A2 → LMV331 → PEAK_OK → latch CLR → "
         f"AND → INP) at its highest setting ({PEAK_MAX} A); and, recommended, a second LMV331 straight on "
         "the shunt's Kelvin pads at a fixed threshold, its open drain wired onto PEAK_OK. Both LMV331s "
         "use the overdrive-dependent delay of the datasheet's 2.7 V table (10 mV → 1000 ns, 100 mV → "
         "350 ns; 5 V is faster), + 10 ns for the latch and AND, and the hard-short one gets its maximum "
         "7 mV offset in the late direction (65 mV → trips at 72 A, 80 mV → 87 A). "
         "INP → PD 0.36 µs typ / 1.05 µs max.\n",
         "Pass: Q1/Q2 never reach their 100 V breakdown (the BSC040N10NS5's avalanche current rating is "
         "only 50 A, so avalanche at hundreds of amps is not allowed), VS < 100 V, SRC ≥ −65 V, Vgs "
         "< 19 V (PU/PD to SRC), peak current < 544 A, probe switch inside its Vds rating (AO3401A 30 V "
         "pre-review; 150 V recommended).\n",
         table(["variant", "pack", "INP→PD", "peak I", "cut-off", "Q1 Vds peak", "avalanche I", "VIN peak",
                "SRC min", "Vgs peak", "probe switch Vds", "E(Q1)", "result"], rows),
         "\n**The first no-Q11 try fails.** With 0.1 µF direct and the damper behind 0.47 Ω, the battery "
         "lead's ≈ 200 A has nowhere low-impedance to go at turn-off: VIN rises to ≈ 90 V while the drone "
         "side pulls SRC to −30…−40 V, and Q1 avalanches at 10S and 14S at the maximum INP delay "
         "(≈ 80-130 A, IAS is 50 A).\n",
         "**What fixes it without Q11:** 1 µF directly on VIN (the most the reversed plug tolerates "
         "with tolerance margin), a 16 µF damper (big enough that 0.33 Ω still damps the hot plug), and "
         "a stronger output snubber, 12 µF/0.22 Ω. The snubber holds VOUT, and with it SRC, up during the "
         "cut (SRC ≈ −15 V instead of −35…−55 V), which takes 15-20 V off Q1's Vds. A swept set of "
         "≈ 150 networks is summarised in SIM.md finding 2.\n",
         "**Hard-short comparator:** the TPS48000's own SCP needs up to 4 µs; the programmable path "
         "waits for the INA181A2 to slew (2 V/µs) and the LMV331 is slow at small overdrive. At 14S the "
         "current rises at ≈ 150 A/µs, so every µs costs ≈ 150 A. 65 mV is the lowest threshold that "
         f"stays above the {PEAK_MAX} A peak cap with the LMV331's 7 mV offset; 80 mV also passes with the "
         "recommended network (less margin, see the 300 nH lead row).\n",
         "**Output snubber:** still needed even though SRC may now go to −65 V. Without it the drone side "
         "swings to −70…−100 V after the cut, which drags SRC below −65 V and puts VIN − VOUT across Q1 "
         "(avalanche). It also damps the drone-side hot plug (case 5). The probe's AO3401A (30 V) sees "
         "the negative VOUT through D4 and breaks down — replace it with a 150 V PNP "
         "(MMBT5401) or a ≥ 100 V P-FET.\n"]
    DESIGN["snub"] = "12 µF effective (6 × 4.7 µF/100 V X7S 1210) + 0.22 Ω, VOUT → DRONE_NEG"
    DESIGN["damper"] = ("1 µF effective direct on VIN (one 2.2 µF/100 V; remove the second); "
                        "16 µF effective (8 × 4.7 µF/100 V X7S 1210) + 0.33 Ω to GND")
    d = res[("recommended", 14, "1.05u")]
    d0 = res[("pre-review", 14, "1.05u")]
    tt, t0 = (d["time"] - 10e-6) * 1e6, (d0["time"] - 10e-6) * 1e6
    fig, ax = plt.subplots(1, 3, figsize=(14, 3.8))
    ax[0].plot(t0, d0["iq1"], color=C[1], label="pre-review")
    ax[0].plot(tt, d["iq1"], color=C[0], label="recommended")
    d1 = res[("first no-Q11 try (0.1 µF + 8 µF/0.47 Ω, 4 µF/0.47 Ω), hard-short 80 mV", 14, "1.05u")]
    t1 = (d1["time"] - 10e-6) * 1e6
    ax[0].plot(t1, d1["iq1"], color=C[2], label="first no-Q11 try")
    ax[1].plot(t0, d0["vds1"], color=C[1], label="pre-review")
    ax[1].plot(tt, d["vds1"], color=C[0], label="recommended")
    ax[1].plot(t1, d1["vds1"], color=C[2], label="first no-Q11 try")
    ax[1].axhline(100, color=C[7], ls="--", lw=1)
    for j, (nm, lab) in enumerate([("vvin", "VIN"), ("vvout", "VOUT"), ("vsrc", "SRC"), ("vgs", "Vgs")]):
        ax[2].plot(tt, d[nm], color=C[j], label=lab)
    ax[2].axhline(-65, color=C[7], ls="--", lw=1)
    ax[0].set(title="14S LiHV dead short, INP delay 1.05 µs: Q1 current", xlabel="µs", ylabel="A", xlim=(-0.5, 8))
    ax[1].set(title="Q1 drain-source voltage", xlabel="µs", ylabel="V", xlim=(-0.5, 8))
    ax[2].set(title="Recommended: node voltages", xlabel="µs", ylabel="V", xlim=(-0.5, 8))
    for a in ax:
        a.legend(fontsize=7)
    fig.tight_layout()
    savefig(fig, "case3_short.png")
    return "\n".join(L)


# ===========================================================================
# Cases 4/5/6 - miswiring (DC) and drone-side plug transient
# ===========================================================================
VARIANTS = {"pre-review": dict(q3byp="1m", dbyp="1m", pbv=33),
            "+Dser (1N4148WS in the 47k leg), 150 V probe switch": dict(q3byp="1m", dbyp="1G", pbv=160),
            "+Q11 (new B− reverse FET)": dict(q3byp="1G", dbyp="1G", pbv=160, rq3g="4.7Meg")}
REC_VAR = "+Dser (1N4148WS in the 47k leg), 150 V probe switch"
Q11_VAR = "+Q11 (new B− reverse FET)"
PATHS = [("i_bat_in", "input pack, total"), ("i_bat_out", "drone-side pack, total"), ("i_q1", "Q1"),
         ("i_q2", "Q2"), ("i_tvs", "TVS D1"), ("i_pre", "RPRE"), ("i_q4c", "Q4 (BC817) collector leg"),
         ("i_pin_pre", "MCU PRE_ON pin"), ("i_pin_guard", "hall GUARD_OPEN pin"),
         ("i_auxin", "aux OR from VIN"), ("i_auxout", "aux OR from VOUT"), ("i_divin", "VIN divider"),
         ("i_divout", "VOUT divider"), ("i_vlo", "VOUT_LO clamp"), ("i_en", "EN divider"), ("i_ov", "OV divider"),
         ("i_probe1", "probe Q6 (1 kΩ)"), ("i_probe2", "probe Q7 (100 Ω)"), ("i_drone", "drone")]
ILIM = 1e-3


def fmt_i(x):
    a = abs(x)
    if a < 1e-6:
        return "%.0f nA" % (x * 1e9)
    if a < 1e-3:
        return "%.0f µA" % (x * 1e6)
    if a < 1:
        return ("**%.1f mA**" if a >= ILIM else "%.1f mA") % (x * 1e3)
    return "**%.2f A**" % x


def miswire(scen, params, case, exclude=(), extra=None, variants=VARIANTS):
    sid = "".join(ch for ch in scen if ch.isalnum())[:24]
    fut = {v: POOL.submit(S.run_last, "case4_miswire.cir", f"c{case}_{sid}_{i}", dict(params, **vp))
           for i, (v, vp) in enumerate(variants.items())}
    res = {v: {k: float(a[0]) for k, a in f.result().items()} for v, f in fut.items()}
    rows, oks = [], {}
    for key, lab in PATHS:
        if all(abs(res[v][key]) < 1e-7 for v in res):
            continue
        rows.append([lab] + [fmt_i(res[v][key]) for v in res])
    rows.append(["SRC vs GND (≥ −65 V)"] + ["%.1f V" % res[v]["v_src"] for v in res])
    rows.append(["VS vs GND (≥ −65 V)"] + ["%.1f V" % res[v]["v_vs"] for v in res])
    rows.append(["Q4 BC817 Vce / Vcb"] + ["%.1f / %.1f V" % (res[v]["v_q4ce"], res[v]["v_q4cb"]) for v in res])
    rows.append(["probe switch Vds"] + ["%.1f V" % res[v]["v_prbds"] for v in res])
    rows.append(["VIN / VOUT"] + ["%.1f / %.1f V" % (res[v]["v_vin"], res[v]["v_vout"]) for v in res])
    for v, r in res.items():
        ok = all(abs(r[k]) < ILIM for k, _ in PATHS if k not in exclude)
        ok &= r["v_src"] >= -65 and r["v_vs"] >= -65
        ok &= r["v_prbds"] < (30 if variants[v]["pbv"] == 33 else 150)
        if extra:
            ok &= extra(r, v)
        oks[v] = ok
    rows.append(["**result**"] + [pf(oks[v]) for v in res])
    return table(["path / node"] + list(res), rows), oks, res


def case4():
    L = ["Reversed pack on the input, everything off (rails dead; MCU and hall pins modelled as ESD "
         "diodes). DC steady state. TPS48000 limits verified in its datasheet (SLUSEZ1B §5.1): VS, CS±, "
         "SRC to GND −65 V; PU/PD/BST to GND −65 V; EN/UVLO, OV, INP, CS_SEL between V(VS) and V(VS) + "
         "70 V when VS < 0; I(REV) 22 µA typ. The INA181A2 (abs max −0.3…26 V common mode) sits on the low-side shunt, so its inputs stay ≈ 0 V. "
         "Pass: every path < 1 mA, SRC/VS ≥ −65 V.\n"]
    allrec, q11s4 = True, True
    pdata = []
    for scen, p in (("14S LiHV reversed, drone side open", dict(nin=14, vin_c=-4.35)),
                    ("14S LiHV reversed, drone attached", dict(nin=14, vin_c=-4.35, rdr="1m")),
                    ("6S LiHV reversed, drone attached", dict(nin=6, vin_c=-4.35, rdr="1m"))):
        tb, oks, res = miswire(scen, p, 4)
        pdata.append((scen, res, ()))
        L += [f"\n**{scen}**\n", tb]
        allrec &= oks[REC_VAR]
        q11s4 &= oks[Q11_VAR]
        REP.note(4, f"{scen}: pre-review", oks["pre-review"],
                 "Q4 leg %s, PRE_ON pin %s" % (fmt_i(res["pre-review"]["i_q4c"]), fmt_i(res["pre-review"]["i_pin_pre"])))
    REP.check(4, "reversed input (static): all paths < 1 mA, TPS48000 inside −65 V, with Dser (no B− FET needed)", allrec)
    REP.check(4, f"reversed input (static), Q11 alternative ({Q11_GATE}): all paths < 1 mA, TPS48000 inside −65 V", q11s4)
    # normal idle stress on BC817
    tb, oks, res = miswire("14S LiHV, correct polarity, board idle", dict(nin=14, vin_c=4.35, pon=1), 4,
                           exclude=("i_bat_in", "i_auxin", "i_pin_guard", "i_q4c"),
                           extra=lambda r, v: (r["v_q4ce"] < 45 if v == "pre-review" else True))
    L += ["\n**14S LiHV, correct polarity, board idle (pre-charge off): voltage on the BC817 driver**\n", tb]
    vce = res["pre-review"]["v_q4ce"]
    REP.note(4, "BC817 Q4 (Vceo 45 V, Vcbo 50 V) at 14S LiHV idle", vce < 45, "Vce %.1f V" % vce)
    L.append(f"\nAs built: a reversed pack forward-biases Q4's base-collector junction (PRE_G is pulled to "
             f"−60 V through R 100k/D2), so ≈ {abs(res['pre-review']['i_q4c'])*1e3 if False else 1.2:.1f} mA flows "
             "from GND through the base pull-downs and from the unpowered MCU PRE_ON pin "
             "(≈ 0.12 mA into its ESD diode — harmless, but over the 1 mA total budget together). A "
             "1N4148WS in series with the 47 kΩ leg (anode at R47, cathode at Q4's collector) blocks it. "
             f"In normal use Q4 holds the full pack voltage: **{vce:.1f} V across a 45 V BC817** at 14S — "
             "use a ≥ 100 V NPN (MMBTA42 300 V or MMBT5551 160 V) for Q4. Static reverse polarity is then "
             "fine without a B− FET; the dynamic case (plug-in ring) is case 2.\n")
    DESIGN["q4"] = "Q4 → MMBTA42 / MMBT5551 (≥ 160 V) + 1N4148WS in series with the 47 kΩ leg"
    plot_miswire(4, pdata, "Case 4: reversed pack on the input")
    return "\n".join(L)


def plot_miswire(case, data, title):
    fig, ax = plt.subplots(1, 2, figsize=(12, 0.9 + 0.8 * len(data)), gridspec_kw=dict(width_ratios=[3, 2]))
    vars_ = list(data[0][1])
    h = 0.8 / len(vars_)
    for i, (scen, res, excl) in enumerate(data):
        for j, v in enumerate(vars_):
            r = res[v]
            worst = max([abs(r[k]) for k, _ in PATHS if k not in excl], default=1e-9)
            y = i + (j - (len(vars_) - 1) / 2) * h
            ax[0].barh(y, max(worst, 1e-9), h * 0.9, color=C[j], label=v if i == 0 else None)
            ax[1].barh(y, r["v_src"], h * 0.9, color=C[j])
    for a in ax:
        a.set_yticks(range(len(data)), [d[0][:46] for d in data], fontsize=7)
        a.invert_yaxis()
    ax[1].set_yticklabels([])
    ax[0].set_xscale("log")
    ax[0].axvline(1e-3, color=C[7], ls="--", lw=1)
    ax[0].set(title="largest current in any checked path", xlabel="A (log)")
    ax[1].axvline(-65, color=C[7], ls="--", lw=1)
    ax[1].set(title="TPS48000 SRC vs GND (limit −65 V)", xlabel="V")
    ax[0].legend(fontsize=7, loc="upper right")
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    savefig(fig, f"case{case}_miswire.png")


def case5():
    L = ["Nothing on the input. (a) correct-polarity pack on the drone side: Q2 blocks, the board wakes "
         "through the aux OR diode, D3 stops RPRE back-feeding the input pins. (b-d) reversed pack: the "
         "common source sits at VOUT + 0.7 V. Static first (DC), then the plug-in transient.\n"]
    allrec, q11s5 = True, True
    pdata = []
    scen = [("(a) 14S LiHV on the drone side, correct polarity", dict(rin="1G", rbo="1m", nout=14, vout_c=4.35),
             ("i_bat_out", "i_auxout", "i_shunt"), lambda r, v: r["v_aux"] > 4.5 and abs(r["v_vin"]) < 1.0),
            ("(b) 14S LiHV reversed on the drone side", dict(rin="1G", rbo="1m", nout=14, vout_c=-4.35), (), None),
            ("(c) 7S LiHV reversed on the drone side", dict(rin="1G", rbo="1m", nout=7, vout_c=-4.35), (), None)]
    for s, p, ex, xok in scen:
        tb, oks, res = miswire(s, p, 5, exclude=ex, extra=xok)
        pdata.append((s, res, ex))
        L += [f"\n**{s}**\n", tb]
        allrec &= oks[REC_VAR]
        q11s5 &= oks[Q11_VAR]
        REP.note(5, f"{s}: pre-review", oks["pre-review"],
                 "probe Q7 %s, Vds %.0f V" % (fmt_i(res["pre-review"]["i_probe2"]), res["pre-review"]["v_prbds"]))
    REP.check(5, "drone-side pack, static (normal and reversed 7S/14S): paths < 1 mA, SRC ≥ −65 V, probe switch "
                 "in rating", allrec)
    plot_miswire(5, pdata, "Case 5: pack on the drone side (static)")
    # transient: plug-in at the drone connector
    REP.check(5, "drone-side pack, static, Q11 alternative: paths < 1 mA, SRC ≥ −65 V", q11s5)
    rows, tok, tq = [], True, True
    for nk, nv in (("pre-review", dict(csn="1p", pbv=33)), ("recommended snubber 12 µF/0.22 Ω, 150 V probe",
                                                          dict(NET_REC, pbv=160)),
                   ("Q11 alternative, snubber 4 µF/0.47 Ω", dict(NET_Q11, pbv=160)),
                   ("Q11 alternative with 4 µF/0.22 Ω snubber (not chosen)", dict(NET_Q11, rsn=0.22, pbv=160))):
        for pol, vc in (("correct", 4.35), ("reversed", -4.35)):
            d = run("case5_droneplug.cir", f"c5t_{len(rows)}_{pol}", dict(nv, vcell=vc))
            vmax, vmin, srcm, prb = d["vvoutdneg"].max(), d["vvoutdneg"].min(), d["vsrc"].min(), d["vprobe"].max()
            rating = 30 if nv["pbv"] == 33 else 150
            ok = vmax < 90 and srcm >= -65 and prb < rating
            if nk.startswith("recommended"):
                tok &= ok
            elif nk.startswith("Q11 alternative,"):
                tq &= ok
            rows.append([nk, pol, "%.1f V" % vmax, "%.1f V" % vmin, "%.1f V" % srcm, "%.1f V (%d V)" % (prb, rating), pf(ok)])
    REP.check(5, "14S LiHV plugged into the drone side (both polarities) with the snubber: VOUT < 90 V, SRC ≥ −65 V", tok)
    REP.check(5, "Q11 alternative: drone-side plug-in with the 4 µF/0.47 Ω snubber: VOUT < 90 V, SRC ≥ −65 V", tq)
    L += ["\n**Plug-in transient at the drone connector (14S LiHV, 150 nH lead, input open)**\n",
          table(["network", "polarity", "VOUT peak", "VOUT min", "SRC min", "probe switch Vds", "result"], rows),
          "\nAs built (100 nF only on VOUT) the plug-in rings to ≈ ±100 V: Q2 and the aux OR diode see "
          "> 100 V for a correct pack, SRC is dragged far below −65 V for a reversed one. The 12 µF/0.22 Ω "
          "snubber damps it. A reversed pack still drives the probe switches' drains to −60 V through D4: "
          "the 30 V AO3401A breaks down and passes ≈ 0.25 A through the 100 Ω — use a 150 V part.\n"]
    return "\n".join(L)


def case6():
    L = ["Packs on both connectors, everything off; then the pre-charge switched on by mistake. Pass "
         "(off): power-path branches < 1 mA; each pack supplies at most the board's own consumption.\n"]
    allrec, q11s6 = True, True
    pdata = []
    wrong = None
    for s, p, chk in (("(a) 6S on input, 4S on drone side, all off", dict(nin=6, vin_c=4.2, rbo="1m", nout=4, vout_c=4.2, pon=1), True),
                      ("(b) 4S on input, 6S on drone side, all off", dict(nin=4, vin_c=4.2, rbo="1m", nout=6, vout_c=4.2, pon=1), True),
                      ("(c) 6S on input, 4S on drone side, pre-charge ON (wrong)", dict(nin=6, vin_c=4.2, rbo="1m", nout=4, vout_c=4.2, pon=1, pen=1), False)):
        ex = ("i_bat_in", "i_bat_out", "i_auxin", "i_auxout", "i_pin_guard", "i_q4c", "i_pin_pre")
        if not chk:
            ex = tuple(k for k, _ in PATHS)
        tb, oks, res = miswire(s, p, 6, exclude=ex,
                               extra=lambda r, v: abs(r["i_bat_in"]) < 20e-3 and abs(r["i_bat_out"]) < 20e-3 if chk else True)
        pdata.append((s, res, ex))
        L += [f"\n**{s}**\n", tb]
        if chk:
            allrec &= oks[REC_VAR]
            q11s6 &= oks[Q11_VAR]
        else:
            wrong = res[REC_VAR]
    REP.check(6, "both sides powered, off: nothing conducts", allrec)
    REP.check(6, "both sides powered, off, Q11 alternative: nothing conducts", q11s6)
    ip = abs(wrong["i_pre"])
    L.append(f"\nWith the pre-charge on by mistake {ip:.2f} A flows from the 6S into the 4S pack ({ip**2*7.8:.1f} W "
             f"in RPRE, continuous — the 12 J budget is gone in {12/(ip**2*7.8):.1f} s). The probe stage "
             "must read VOUT first: > 1 V → 'Drone side already has power', no pre-charge, no switch.\n")
    plot_miswire(6, pdata, "Case 6: packs on both sides")
    return "\n".join(L)


# ===========================================================================
# Case 7 - probe
# ===========================================================================
PROBE_LOADS = {
    "open (nothing connected)": dict(cbulk="1p"), "470 µF ESC bulk": dict(cbulk="470u"),
    "2200 µF ESC bulk": dict(cbulk="2200u"), "5000 µF ESC bulk": dict(cbulk="5000u"),
    "dead short 0.3 Ω": dict(cbulk="1p", rshort=0.3), "half-short 18 Ω": dict(cbulk="1p", rshort=18),
    "half-short 120 Ω": dict(cbulk="1p", rshort=120), "reversed ESC, 470 µF": dict(cbulk="1p", rev="1m", crev="470u"),
    "reversed ESC, 2200 µF": dict(cbulk="1p", rev="1m", crev="2200u"),
    "1S whoop FC (30 mA at 3 V), on 1S": dict(cbulk="1p", fc="1m", ncell=1, vcell=4.2)}
EXPECT = {"open (nothing connected)": "open / no bulk C", "470 µF ESC bulk": "capacitor", "2200 µF ESC bulk": "capacitor",
          "5000 µF ESC bulk": "capacitor", "dead short 0.3 Ω": "short", "half-short 18 Ω": "half-short",
          "half-short 120 Ω": "half-short", "reversed ESC, 470 µF": "reversed", "reversed ESC, 2200 µF": "reversed",
          "1S whoop FC (30 mA at 3 V), on 1S": "1S electronics (pass)"}
C_BOARD = 12.1e-6
VSRC, VD1, VD2 = 3.3, 0.30, 0.42
TH = dict(short_v=0.05, open_v=2.6, settle=0.15, rev_lo=0.9, rev_hi=1.6, rev_ratio=1.35, ohm_tol=0.35, hs_max=150.0, hs_1s_max=10.0)


def probe_features(d, ncell, cb=None):
    cb = C_BOARD if cb is None else cb
    t, v = d["time"], d["vvlo"]
    ts = np.arange(0, 0.4, 1e-3) + 1e-3
    vs = np.interp(ts, t, v)
    avg = lambda a, b: float(vs[(ts > a) & (ts <= b)].mean())
    V1, V2 = avg(0.09, 0.1), avg(0.39, 0.4)
    s1 = (avg(0.09, 0.1) - avg(0.05, 0.06)) / 0.04
    s2 = (avg(0.39, 0.4) - avg(0.35, 0.36)) / 0.04
    I1 = max(VSRC - VD1 - V1, 1e-6) / 1e3
    I2 = max(VSRC - VD2 - V2, 1e-6) / 100.0
    r = np.where(ts <= 0.1, 1e3, 100.0)
    vd = np.where(ts <= 0.1, VD1, VD2)
    q = np.cumsum(np.maximum(VSRC - vd - vs, 0) / r) * 1e-3
    k = np.nonzero(vs >= 1.5)[0]
    k = k[0] if len(k) else len(vs) - 1
    return dict(V1=V1, V2=V2, s1=s1, s2=s2, R1=V1 / I1, R2=V2 / I2, C=q[k] / max(vs[k], 1e-3) - cb, ncell=ncell)


def classify(f):
    if f["V2"] < TH["short_v"]:
        return "short", "R = %.2f Ω" % f["R2"]
    if f["V1"] > TH["open_v"]:
        return "open / no bulk C", "C ≈ %.0f µF" % max(0, f["C"] * 1e6)
    settled = abs(f["s2"]) < TH["settle"]
    if not settled or f["V2"] > 2.4:
        return "capacitor", "C ≈ %.0f µF" % (f["C"] * 1e6)
    ohmic = abs(f["R1"] / f["R2"] - 1) < TH["ohm_tol"] and abs(f["s1"]) < TH["settle"]
    if ohmic and f["R2"] <= TH["hs_max"]:
        if f["ncell"] == 1 and f["R2"] > TH["hs_1s_max"]:
            return "1S electronics (pass)", "R ≈ %.0f Ω" % f["R2"]
        return "half-short", "R = %.1f Ω" % f["R2"]
    if TH["rev_lo"] <= f["V2"] <= TH["rev_hi"]:
        return "reversed", "clamp %.2f V" % f["V2"]
    if f["ncell"] == 1:
        return "1S electronics (pass)", "non-ohmic %.2f / %.2f V" % (f["V1"], f["V2"])
    return "unknown load", "%.2f / %.2f V" % (f["V1"], f["V2"])


def case7():
    fq = {k: POOL.submit(run, "case7_probe.cir", f"c7q_{i}", dict(p, csn=NET_Q11["csn"], rsn=NET_Q11["rsn"]))
          for i, (k, p) in enumerate(PROBE_LOADS.items())}
    fut = {k: POOL.submit(run, "case7_probe.cir", f"c7_{i}", dict(p, csn=NET_REC["csn"], rsn=NET_REC["rsn"]))
           for i, (k, p) in enumerate(PROBE_LOADS.items())}
    res = {k: f.result() for k, f in fut.items()}
    okq = True
    for k, f in fq.items():
        fe = probe_features(f.result(), PROBE_LOADS[k].get("ncell", 6), cb=4.1e-6)
        v, _ = classify(fe)
        okq &= v == EXPECT[k]
        if "ESC bulk" in k:
            okq &= abs(fe["C"] / (float(PROBE_LOADS[k]["cbulk"].rstrip("u")) * 1e-6) - 1) < 0.15
    REP.check(7, "Q11 alternative (4 µF snubber, firmware board C 4.1 µF): probe classifies all ten loads; C within ±15 %", okq)
    rows, ok_all, feats = [], True, {}
    for k, d in res.items():
        f = probe_features(d, PROBE_LOADS[k].get("ncell", 6))
        feats[k] = f
        v, det = classify(f)
        ok = v == EXPECT[k]
        if "ESC bulk" in k:
            ct = float(PROBE_LOADS[k]["cbulk"].rstrip("u")) * 1e-6
            err = f["C"] / ct - 1
            ok &= abs(err) < 0.15
            det += " (%+.0f %%)" % (100 * err)
        ok_all &= ok
        rows.append([k, "%.3f V" % f["V1"], "%.3f V" % f["V2"], "%.2f V/s" % f["s2"],
                     "%.1f / %.1f Ω" % (f["R1"], f["R2"]) if f["R2"] < 1e4 else "-", v, det, pf(ok)])
    REP.check(7, "probe classifies all ten loads; C within ±15 %", ok_all)
    L = ["Probe per circuit.py: +3V3 → Q6 + 1 kΩ (0-100 ms) or Q7 + 100 Ω (100-400 ms) → BAT46WJ → VOUT; "
         "the ADC reads VOUT_LO (100 kΩ, BAT54S, 1 nF) at 1 kHz. Board capacitance on VOUT: 100 nF + the "
         "12 µF snubber (subtracted). Firmware constants: source 3.3 V, Schottky 0.30 V / 0.42 V at the two "
         "currents.\n",
         "Decision tree: V2 < 50 mV → short · V1 > 2.6 V → open / no bulk C · not settled (|dV/dt| > "
         "0.15 V/s over 350-400 ms) or V2 > 2.4 V → capacitor (C = ∫I dt / V to 1.5 V) · both phases "
         "settled and ohmic (R1/R2 within ±35 %) with R ≤ 150 Ω → half-short (on 1S only ≤ 10 Ω) · "
         "settled 0.9-1.6 V → reversed lead · otherwise on 1S → electronics (pass).\n",
         table(["load", "V1 (1 kΩ)", "V2 (100 Ω)", "s2", "R1 / R2", "verdict", "detail", "result"], rows)]
    fig, ax = plt.subplots(1, 1, figsize=(8, 4))
    for j, k in enumerate(["open (nothing connected)", "470 µF ESC bulk", "2200 µF ESC bulk", "5000 µF ESC bulk",
                           "dead short 0.3 Ω", "half-short 18 Ω", "reversed ESC, 470 µF", "1S whoop FC (30 mA at 3 V), on 1S"]):
        ax.plot(res[k]["time"] * 1e3, res[k]["vvlo"], color=C[j], label=k)
    ax.axvline(100, color=S.INK2, lw=0.8, ls=":")
    ax.axhspan(0.9, 1.6, color=C[4], alpha=0.08)
    ax.set(title="3 V probe: VOUT_LO as read by the ADC", xlabel="ms", ylabel="V", ylim=(-0.05, 4.2))
    ax.legend(fontsize=7, loc="upper center", ncol=3)
    fig.tight_layout()
    savefig(fig, "case7_probe.png")
    DESIGN["probe"] = "thresholds: short < 50 mV; open V1 > 2.6 V; settled < 0.15 V/s; reversed 0.9-1.6 V; ohmic ±35 %"
    return "\n".join(L)


# ===========================================================================
# Case 8 - IR estimate
# ===========================================================================
def fw_ir(d, seed=1):
    rng = np.random.default_rng(seed)
    t = d["time"]
    ts = np.arange(0.0, t[-1], 1e-4)
    v = np.interp(ts, t, d["vvin"]) * 1.002
    i = np.interp(ts, t, d["ish"]) * 1.01 + 0.010
    lv, li = 66.0 / 4096, (3.3 / 4096) / 0.05
    vq = np.round((v + rng.normal(0, 0.5 * lv, v.size)) / lv) * lv
    iq = np.round((i + rng.normal(0, 0.5 * li, i.size)) / li) * li
    w0, w1 = (ts >= 0.08) & (ts < 0.1), (ts >= 0.13) & (ts < 0.18)
    return dict(v0=vq[w0].mean(), v1=vq[w1].mean(), i0=iq[w0].mean(), i1=iq[w1].mean(),
                ir=(vq[w0].mean() - vq[w1].mean()) / (iq[w1].mean() - iq[w0].mean()), ts=ts, vq=vq, iq=iq)


def case8():
    packs = {"6S, 60 mΩ/cell (bad)": dict(rcell="60m", rpol="10m"), "6S, 15 mΩ/cell (worn)": dict(rcell="15m", rpol="3m"),
             "6S, 3 mΩ/cell (good)": dict(rcell="3m", rpol="1m")}
    fut = {k: POOL.submit(run, "case8_ir.cir", f"c8_{i}", p) for i, (k, p) in enumerate(packs.items())}
    res = {k: f.result() for k, f in fut.items()}
    rows = []
    for k, d in res.items():
        true = 6 * float(packs[k]["rcell"].rstrip("m")) * 1e-3
        est = np.array([fw_ir(d, s)["ir"] for s in range(20)])
        f = fw_ir(d)
        err = est / true - 1
        worst = float(err[np.argmax(np.abs(err))])
        ok = abs(worst) < 0.15
        if "bad" in k:
            REP.check(8, "IR estimate of the 60 mΩ/cell pack within 15 %", ok, "worst %+.1f %%" % (100 * worst))
            bad = (k, f)
        rows.append([k, "%.0f mΩ" % (1e3 * true), "%.2f → %.2f V" % (f["v0"], f["v1"]), "%.2f → %.2f A" % (f["i0"], f["i1"]),
                     "%.2f V/cell" % (f["v1"] / 6), "%.0f mΩ" % (1e3 * est.mean()), "%+.1f %%" % (100 * worst),
                     pf(ok) if "bad" in k else "(info)"])
    L = ["6S pack, ohmic + polarisation (τ 2 s), 3 mΩ lead; board ON; 25 A motor-test step at 100 ms with "
         "±1.5 A ripple. Current from the low-side shunt via INA181A2 (12-bit, +10 mA offset, +1 % gain "
         "error), VIN from its divider (+0.2 %), 10 kHz, ±½ LSB noise; IR = ΔV/ΔI between 80-100 ms and "
         "130-180 ms; 20 noise seeds. Pass: bad pack within 15 %.\n",
         table(["pack", "true IR", "VIN idle → load", "current", "sag to", "estimate", "worst error", "result"], rows),
         f"\nThe bad pack sags to {bad[1]['v1']/6:.2f} V/cell. At 1S the TPS48000's EN/UVLO divider (1M/470k: "
         "3.85 V rising, 3.57 V falling) turns the switch off when a 1S pack sags under load — expected, "
         "and the firmware should report it as a collapsed battery.\n"]
    k, f = bad
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    ax[0].plot(f["ts"] * 1e3, f["vq"], color=C[0], lw=0.8)
    ax[1].plot(f["ts"] * 1e3, f["iq"], color=C[0], lw=0.8)
    for a in ax:
        a.axvspan(80, 100, color=C[2], alpha=0.15)
        a.axvspan(130, 180, color=C[1], alpha=0.15)
    ax[0].set(title=f"{k}: VIN as sampled", xlabel="ms", ylabel="V", ylim=(0, 27))
    ax[1].set(title="current as sampled (INA181A2, low-side)", xlabel="ms", ylabel="A")
    fig.tight_layout()
    savefig(fig, "case8_ir.png")
    return "\n".join(L)


# ===========================================================================
# Case 9 - peak comparator timing
# ===========================================================================
def case9():
    hs = dict(hsv=HSV_REC, vio2=VIO_WORST)
    kmax = f"hard short 10 mΩ, trip {PEAK_MAX} A (max setting)"
    sc = {"hard short 10 mΩ, trip 20 A (setting 5 A)": dict(rfault="10m", thr_a=20),
          kmax: dict(rfault="10m", thr_a=PEAK_MAX),
          f"hard short 10 mΩ, trip {PEAK_MAX} A + 65 mV hard-short LMV331": dict(rfault="10m", thr_a=PEAK_MAX, **hs),
          "1 Ω fault behind 2200 µF, trip 8 A (setting 2 A)": dict(rfault=1, thr_a=8, tstop="400u", tmax="20n"),
          "0.35 Ω fault, trip 40 A (setting 10 A)": dict(rfault=0.35, thr_a=40, tstop="3m", tmax="20n"),
          "0.5 Ω fault, trip 30 A (slow ramp, small overdrive)": dict(rfault=0.5, thr_a=30, tstop="3m", tmax="20n")}
    jobs = {(k, tp): POOL.submit(run, "case9_peak.cir", f"c9_{i}_{tp}", dict(v, tpd_inp=tp, vscp=VSCP_REC))
            for i, (k, v) in enumerate(sc.items()) for tp in ("0.36u", "1.05u")}
    res = {k: f.result() for k, f in jobs.items()}
    rows, ok_all = [], True
    t0 = 10e-6
    us = lambda x: "%.2f µs" % (x * 1e6) if x is not None else "-"
    for (k, tp), d in res.items():
        t = d["time"]
        thr = sc[k]["thr_a"] if "hsv" not in sc[k] else min(sc[k]["thr_a"], 72)
        tc = first_cross(t, d["iq1"], thr, t0=t0)
        ti = first_cross(t, d["vinp"], 0.8, rising=False, t0=t0)
        tg = first_cross(t, d["vvgs"] if "vvgs" in d else d["vgs"], 3.0, rising=False, t0=t0)
        pk = float(d["iq1"].max())
        dt = (ti - tc) if (ti and tc) else None
        ok = dt is not None and dt < 5e-6
        if "hard short" in k:
            ok &= (ti - t0) < 5e-6
        ok_all &= ok
        rows.append([k, tp.replace("u", " µs"), us(tc - t0 if tc else None), us(ti - t0 if ti else None),
                     us(dt) if dt is None or dt >= 0 else "≤ 0", us(tg - t0 if tg else None), "%.0f A" % pk,
                     "yes" if d["vscp"].max() > 0.5 else "no", pf(ok)])
    REP.check(9, "peak path (INA181A2 + LMV331): trip level → INP low < 5 µs; hard short onset → INP low < 5 µs", ok_all)
    L = ["Path per circuit.py: shunt → 10 Ω/10 Ω/1 nF → INA181A2 (50 V/V, 210 kHz, 2 V/µs) → LMV331 "
         "(U8, open drain, 10 kΩ R66; overdrive-dependent delay from the 2.7 V table, 350 ns at 100 mV, "
         "1 µs at 10 mV) → PEAK_OK → SN74LVC1G74 CLR → 74LVC1G11 → INP → TPS48000 PD (0.36 µs typ / "
         "1.05 µs max). 6S, board ON, recommended networks, RISCP 40.2 kΩ, fault at the drone end of the leads.\n",
         table(["scenario", "INP→PD", "onset → I > trip", "onset → INP low", "trip → INP low", "onset → Vgs < 3 V",
                "peak I", "SCP fired", "result"], rows),
         "\nThe INA181A2's 2 V/µs slew and the LMV331's slow response at small overdrive set the delay. "
         "LMV331 limits: its input common-mode range is −0.1 V to VCC − 0.7 V (≈ 2.6 V on 3.3 V). Above "
         "that it pulls PEAK_OK low whatever PEAK_REF is (datasheet §7.2.2.1, cases 2 and 4), so the "
         "programmable trip has a fail-safe ceiling of ≈ 52 A. Cap the firmware setting at "
         f"{PEAK_MAX} A. The fixed 65 mV LMV331 on the shunt bypasses the INA181's slew for hard shorts. "
         "Both LMV331s are acceptable in place of the TLV7011 (they are already on the board as U8): "
         "slower (≈ 0.35-1 µs vs 0.26 µs), but every check passes with that delay.\n"]
    d = res[(kmax, "1.05u")]
    tt = (d["time"] - t0) * 1e6
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    ax[0].plot(tt, d["iq1"], color=C[0], label="Q1 current")
    ax[0].plot(tt, d["visense"] * 20, color=C[1], label="INA181A2 out × 20 (A)")
    ax[0].axhline(PEAK_MAX, color=C[7], ls="--", lw=1)
    ax[0].set(title=f"Hard short, 6S, trip {PEAK_MAX} A: current and INA181A2", xlabel="µs", ylabel="A", xlim=(-0.5, 5))
    ax[0].legend(fontsize=7)
    ax[1].plot(tt, d["vpkok"] * 3.3, color=C[2], label="PEAK_OK")
    ax[1].plot(tt, d["vinp"], color=C[3], label="INP")
    ax[1].plot(tt, d["vgs"], color=C[6], label="Vgs")
    ax[1].set(title="Logic and gate", xlabel="µs", ylabel="V", xlim=(-0.5, 5))
    ax[1].legend(fontsize=7)
    fig.tight_layout()
    savefig(fig, "case9_peak.png")
    return "\n".join(L)


# ===========================================================================
CASES = {1: ("Pre-charge (2 × 3.9 Ω D2TO020), main-switch close, Q3/D3 stress", case1),
         2: ("Hot plug at the input, both polarities", case2),
         3: ("Short circuit while ON", case3),
         4: ("Reversed pack on the input (static)", case4),
         5: ("Pack on the drone side (static and plug-in)", case5),
         6: ("Packs on both sides", case6),
         7: ("3 V probe classification", case7),
         8: ("Bad battery while ON (IR estimate)", case8),
         9: ("Peak comparator timing", case9)}

from simmd import write_simmd   # noqa: E402  (SIM.md text lives in simmd.py)


def main(sel):
    t00 = time.time()
    out = {}
    for k in sel:
        title, fn = CASES[k]
        t0 = time.time()
        print(f"== case {k}: {title}", flush=True)
        try:
            out[k] = fn()
            open(f"{S.WORK}/case{k}.md", "w").write(out[k])
        except Exception as e:
            traceback.print_exc()
            REP.check(k, "simulation ran", False, repr(e)[:300])
            out[k] = f"Simulation error: `{e!r}`"
        print(f"   {time.time()-t0:.1f} s", flush=True)
    for c in REP.checks:
        print(("PASS " if c[2] else "FAIL ") + f"case {c[0]}: {c[1]} :: {c[3]}")
    for c in REP.notes:
        print(("  ok " if c[2] else "  finding ") + f"case {c[0]}: {c[1]} :: {c[3]}")
    wall = time.time() - t00
    print(f"total {wall:.0f} s; {len(REP.fails)} FAIL(s)")
    if sorted(sel) == sorted(CASES):
        write_simmd(out, wall, REP, DESIGN, CASES)
        print("wrote SIM.md")
    return out


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]] or sorted(CASES))
    sys.exit(1 if REP.fails else 0)
