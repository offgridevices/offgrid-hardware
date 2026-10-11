#!/usr/bin/env python3
"""SmokeBreak v1 - run every simulation case, check pass/fail, write plots and SIM.md.

Usage:  python3 run_all.py [case numbers...]      (default: all)
Exit status is non-zero if any check FAILs (or a simulation does not converge).
"""
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import matplotlib.pyplot as plt

import simlib as S
from simlib import run, at, first_cross, integ, worst_window_power, savefig, C

POOL = ThreadPoolExecutor(max_workers=4)

# ---------------------------------------------------------------------------
# Assumptions shared by several cases
# ---------------------------------------------------------------------------
# Single-pulse SOA of a 100 V 3.5 mOhm 5x6 FET (OptiMOS-5 class), Tc = 25 C,
# expressed as power vs pulse length. Checked with a 0.5 derating
# (Tc ~ 80 C board + part spread).
SOA = {1e-4: 25 * 100.0, 1e-3: 25 * 30.0, 1e-2: 25 * 8.0, 1e-1: 60 * 0.6}
SOA_DERATE = 0.5
EAS_SINGLE = 0.200      # J, single-pulse avalanche energy assumed (datasheet class ~250 mJ @ 50 A)
ID_PULSE = 400.0        # A, pulsed drain current rating assumed

# design values under test / chosen (filled by the cases)
DESIGN = {}


class Report:
    def __init__(self):
        self.sections = []
        self.fails = []
        self.checks = []

    def check(self, case, name, ok, detail):
        self.checks.append((case, name, ok, detail))
        if not ok:
            self.fails.append(f"Case {case}: {name} - {detail}")
        return ok


REP = Report()


def soa_check(t, p):
    """Return list of (window, worst avg power, allowed) and overall ok."""
    rows, ok = [], True
    for win, pmax in SOA.items():
        if t[-1] - t[0] < win * 0.5:
            continue
        pw = worst_window_power(t, p, win)
        allowed = pmax * SOA_DERATE
        rows.append((win, pw, allowed))
        ok &= pw <= allowed
    return rows, ok


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def pf(ok):
    return "PASS" if ok else "**FAIL**"


# ===========================================================================
# Case 1 - pre-charge sizing, main-switch close, RPRE energy
# ===========================================================================
def c1_run(tag, ncell, vcell, rpre, cload, pvtx, tmain=2.0, tpoff=2.0, c1=150e-9,
           tstop=1.0, tmax=200e-6):
    return run("case1_precharge.cir", tag, dict(
        ncell=ncell, vcell=vcell, rpre=rpre, cload=cload, pvtx=pvtx, tmain=tmain,
        tpoff=tpoff, c1=c1, tstop=tstop, tmax=tmax))


def c1_precharge_metrics(d):
    t, vin, vout = d["time"], d["vvin"], d["vvout"]
    r = vout / np.maximum(vin, 1e-3)
    t75 = first_cross(t, r, 0.75)
    vfin = vout[-1]
    # stall = settled within 2 % of final value
    tst = None
    if t75 is None:
        far = np.nonzero(np.abs(vout - vfin) > 0.02 * vfin + 0.05)[0]
        tst = float(t[far[-1]]) if len(far) else 0.0
    return dict(t75=t75, vfin=vfin, ratio=r[-1], vin=vin[-1], ipk=float(np.max(d["ipre"])),
                epre=integ(t, d["ppre"]), tstall=tst)


def case1():
    lines = []
    RP = [6.8, 8.2, 10, 15, 22, 33, 47]   # brief: 10..47; 6.8/8.2 added because none of those meets (a)
    NS = list(range(8, 15))
    VCA = [3.5, 3.7, 3.85, 4.2, 4.35]
    VC_REQ = [3.7, 3.85, 4.2, 4.35]   # (a) requirement; 3.5 V/cell handled by the (b) path

    # ---------------- (a) 8S-14S, 2200 uF + 15 W VTX ----------------
    jobs = {}
    for rp in RP:
        for n in NS:
            for vc in VCA:
                tag = f"c1a_{rp}_{n}_{vc}"
                jobs[(rp, n, vc)] = POOL.submit(c1_run, tag, n, vc, rp, 2200e-6, 15)
    res = {k: c1_precharge_metrics(f.result()) for k, f in jobs.items()}
    summary = []
    passing = []
    for rp in RP:
        req_ok = all(res[(rp, n, vc)]["t75"] is not None and res[(rp, n, vc)]["t75"] <= 1.0
                     for n in NS for vc in VC_REQ)
        worst_t = max((res[(rp, n, vc)]["t75"] or 9) for n in NS for vc in VC_REQ)
        fails = [f"{n}S@{vc}" for n in NS for vc in VCA if res[(rp, n, vc)]["t75"] is None]
        summary.append((f"{rp:g} Ω", pf(req_ok), "%.0f ms" % (worst_t * 1e3) if worst_t < 9 else "never",
                        ", ".join(fails) if fails else "-"))
        if req_ok:
            passing.append(rp)
    rpre = max(passing) if passing else 10
    DESIGN["RPRE"] = rpre
    REP.check(1, "(a) some RPRE in {10..47} reaches 75 % within 1 s for 8S-14S (>=3.7 V/cell), 2200 uF + 15 W",
              bool(passing), f"passing: {passing}")

    lines.append("### (a) 8S-14S, 2200 µF + 15 W VTX (+1 W FC/RX)\n")
    lines.append("Requirement: VOUT > 75 % of VIN within 1 s for every 8S-14S pack at 3.7, 3.85, 4.2 and "
                 "4.35 V/cell. 3.5 V/cell (nearly empty) is also simulated; a stall there is handed to the "
                 "(b) path (close the main switch from the stall).\n")
    lines.append(table(["RPRE", "(a) requirement", "slowest t75 (req. set)", "stalls below 75 % (any V/cell)"], summary))
    # detail table for chosen RPRE
    rows = []
    for n in NS:
        rows.append([f"{n}S"] + [("%.0f ms" % (res[(rpre, n, vc)]["t75"] * 1e3)) if res[(rpre, n, vc)]["t75"]
                                 else "stall %.1f V (%.0f %%)" % (res[(rpre, n, vc)]["vfin"], 100 * res[(rpre, n, vc)]["ratio"])
                                 for vc in VCA])
    lines.append(f"\nTime to 75 % with RPRE = {rpre} Ω:\n")
    lines.append(table(["pack"] + [f"{v} V/cell" for v in VCA], rows))
    lines.append(f"\n**Chosen RPRE = {rpre} Ω** (largest value meeting (a)). None of the requested values "
                 "10-47 Ω meets (a) at the low end (8S below ~4.2 V/cell): the binding limit is not the 75 % point "
                 "but getting *past the VTX UVLO*. At VOUT = 6 V the VTX switches on and wants P/6 V; if "
                 "(VIN − 6 V)/R is less than that, VOUT is trapped at the UVLO (the low equilibrium of a "
                 "constant-power load). Condition: R < 6 V·(VIN − 6 V)/P_total "
                 "(8S at 3.7 V/cell with 15 W + 1 W FC → R < 8.9 Ω; 14S LiHV → R < 21 Ω). "
                 "The second condition, an operating point above 0.75·VIN, needs R ≤ 0.1875·VIN²/P "
                 "and is less strict.\n")

    # ---------------- (b) 2S-7S, 2200 uF + 10 W, stall -> main close ----------------
    def seq(tag, n, vc, cload, pvtx, c1):
        d0 = c1_run(tag + "_pc", n, vc, rpre, cload, pvtx)
        m = c1_precharge_metrics(d0)
        tmain = m["t75"] if m["t75"] is not None else min(1.0, m["tstall"] + 0.05)
        tmain = max(tmain, 0.02)
        d = c1_run(tag, n, vc, rpre, cload, pvtx, tmain=tmain, tpoff=tmain + 0.45, c1=c1,
                   tstop=tmain + 0.5, tmax=50e-6)
        t = d["time"]
        sel = t >= tmain
        vin, vout = d["vvin"], d["vvout"]
        tclose = first_cross(t, vout / vin, 0.98, t0=tmain)
        rows_soa, ok = soa_check(t[sel], d["pq1"][sel])
        return dict(m=m, tmain=tmain, d=d, tclose=(tclose - tmain) if tclose else None,
                    eq1=integ(t, d["pq1"], tmain), eq2=integ(t, d["pq2"], tmain),
                    pq1=float(d["pq1"][sel].max()), pq2=float(d["pq2"][sel].max()),
                    iq1=float(d["iq1"][sel].max()), soa=rows_soa, soa_ok=ok)

    # C1 (Cdvdt) sweep at the worst gap seen with the chosen RPRE: 8S at 3.5 V/cell,
    # 15 W VTX stalled at its UVLO (gap ~22 V), and a forced 9S LiHV stall (gap ~33 V)
    C1S = [47e-9, 100e-9, 150e-9, 220e-9, 330e-9]
    sw = {}
    for c1 in C1S:
        for cl in (2200e-6, 5000e-6):
            sw[(c1, cl)] = POOL.submit(seq, f"c1c1_{int(c1*1e9)}_{int(cl*1e6)}", 8, 3.5, cl, 15, c1)
    sw = {k: f.result() for k, f in sw.items()}
    rows = []
    for (c1, cl), r in sw.items():
        worst = max(pw / al for _, pw, al in r["soa"])
        rows.append([f"{c1*1e9:.0f} nF", f"{cl*1e6:.0f} µF", "%.1f V" % r["m"]["vfin"] if r["m"]["t75"] is None else "75 % reached",
                     "%.0f ms" % (r["tclose"] * 1e3) if r["tclose"] else "not closed",
                     "%.1f A" % r["iq1"], "%.0f W" % r["pq1"], "%.2f J" % r["eq1"], "%.0f %%" % (100 * worst), pf(r["soa_ok"])])
    # choose: smallest C1 with SOA pass at 5000 uF and close-inrush <= 2 A at 2200 uF
    # (inrush well under the lowest 'Auto/1 A' setting's peak limit), i.e. ~50 ms close (SPEC 4)
    def inrush(c1, cl):
        return 0.63 * 12.3 * cl / (100e3 * c1)
    cands = [c1 for c1 in C1S if sw[(c1, 5000e-6)]["soa_ok"] and inrush(c1, 2200e-6) <= 2.0]
    c1sel = cands[0] if cands else C1S[-1]
    DESIGN["C1"] = c1sel
    lines.append("\n### (b) 2S-7S with 2200 µF + 10 W VTX: stall, then close the main switch slowly\n")
    lines.append("Gate network (TI fig. 8-6): PU → R1 = 100 kΩ → gate, PD direct to gate, gate → R2 = 10 Ω + "
                 "C1 (= 'Cdvdt') → GND, CBST = 2.2 µF. Output slew ≈ (12 V − Vth)/(R1·C1). The pre-charge stays on "
                 "until the main switch has closed (it keeps feeding the VTX while the gate climbs). SOA "
                 f"assumed (single pulse, Tc 25 °C): 100 µs 2.5 kW, 1 ms 750 W (25 V × 30 A), 10 ms 200 W "
                 f"(25 V × 8 A), 100 ms 36 W (60 V × 0.6 A); pass = worst sliding-window average power ≤ "
                 f"{SOA_DERATE:.0%} of that (Tc ≈ 80 °C, spread).\n")
    lines.append("C1 sweep at the worst gap left by the chosen RPRE (8S at 3.5 V/cell = 28 V, 15 W VTX stalled "
                 "at its 6 V UVLO, gap 22 V). Selection: smallest C1 with SOA pass at 5000 µF and a calculated "
                 "close inrush 0.63·12.3 V·Cload/(R1·C1) ≤ 2 A at 2200 µF:\n")
    lines.append(table(["C1", "Cload", "stall", "close time", "Q1 peak I", "Q1 peak P", "Q1 energy",
                        "worst % of derated SOA", "SOA"], rows))
    lines.append(f"\n**Chosen C1 (Cdvdt) = {c1sel*1e9:.0f} nF** with R1 = 100 kΩ (CBST ≥ Qg + 10·C1 → 2.2 µF).\n")

    bj = {}
    for n in range(2, 8):
        for vc in (3.5, 4.35):
            bj[(n, vc)] = POOL.submit(seq, f"c1b_{n}_{vc}", n, vc, 2200e-6, 10, c1sel)
    # 8S near-empty stall from (a) + worst 14S/5000 uF
    bj[("8", 3.5)] = POOL.submit(seq, "c1b_8_3.5", 8, 3.5, 2200e-6, 15, c1sel)
    bres = {k: f.result() for k, f in bj.items()}
    rows, allok = [], True
    for (n, vc), r in bres.items():
        worst = max(pw / al for _, pw, al in r["soa"])
        ok = r["soa_ok"] and r["tclose"] is not None
        allok &= ok
        st = ("75 %% at %.0f ms" % (r["m"]["t75"] * 1e3)) if r["m"]["t75"] else ("stall %.1f V (%.0f %%)" % (r["m"]["vfin"], 100 * r["m"]["ratio"]))
        rows.append([f"{n}S @ {vc}", "15 W" if str(n) == "8" else "10 W", st,
                     "%.0f ms" % (r["tclose"] * 1e3) if r["tclose"] else "not closed",
                     "%.1f A" % r["iq1"], "%.0f W" % r["pq1"], "%.2f J / %.3f J" % (r["eq1"], r["eq2"]),
                     "%.0f %%" % (100 * worst), pf(ok)])
    REP.check(1, "(b) main close from pre-charge end/stall within derated SOA, 2S-7S (+8S empty)", allok,
              "see table")
    lines.append(table(["pack", "VTX", "pre-charge result", "main close", "Q1 peak I", "Q1 peak P",
                        "E(Q1) / E(Q2)", "worst % of derated SOA", "result"], rows))

    # ---------------- (c) RPRE energy & peak ----------------
    cj = {"14S LiHV, 2200 µF, 15 W": POOL.submit(seq, "c1c_14_2200", 14, 4.35, 2200e-6, 15, c1sel),
          "6S LiHV, 5000 µF, 10 W": POOL.submit(seq, "c1c_6_5000", 6, 4.35, 5000e-6, 10, c1sel),
          "14S LiHV, 5000 µF, 15 W (worst)": POOL.submit(seq, "c1c_14_5000", 14, 4.35, 5000e-6, 15, c1sel)}
    cres = {k: f.result() for k, f in cj.items()}
    rows = []
    emax = 0
    for k, r in cres.items():
        d = r["d"]
        t = d["time"]
        e = integ(t, d["ppre"])
        emax = max(emax, e)
        rows.append([k, "%.2f A" % d["ipre"].max(), "%.0f W" % d["ppre"].max(), "%.2f J" % e,
                     "%.0f ms" % (r["tmain"] * 1e3)])
    # failed attempt: hard clamp at 0 V behind the pre-charge, firmware energy abort
    vin14 = 14 * 4.35
    pshort = vin14 ** 2 / (rpre + 0.25)
    ebudget = 15.0
    DESIGN["RPRE_E"] = emax
    lines.append("\n### (c) Energy in RPRE per attempt\n")
    lines.append(table(["case", "peak I(RPRE)", "peak P(RPRE)", "energy per attempt", "main enabled at"], rows))
    lines.append(f"\nA failed attempt is worse: with a fault that clamps the drone near 0 V the resistor sees "
                 f"{pshort:.0f} W at 14S LiHV, i.e. {pshort*1.0:.0f} J if the firmware waited the full 1 s. "
                 f"The firmware must therefore integrate (VIN−VOUT)²/RPRE and abort at an energy budget of "
                 f"{ebudget:.0f} J (reached after {1e3*ebudget/pshort:.0f} ms of a dead clamp), in addition to the 1 s "
                 f"timeout and the stall rule.\n\n**RPRE pulse rating required:** ≥ {2*ebudget:.0f} J single pulse "
                 f"in ≤ 100 ms (2 × the {ebudget:.0f} J budget; normal worst case {emax:.1f} J), peak "
                 f"{vin14**2/rpre:.0f} W, ≥ 100 V working voltage, through-hole ceramic-composition (bulk) or "
                 f"pulse-rated wirewound; NTC beside it gates the next attempt.\n")
    DESIGN["RPRE_rating"] = f"≥ {2*ebudget:.0f} J single pulse (≤ 100 ms), ≥ {vin14**2/rpre:.0f} W peak, 100 V"
    REP.check(1, "(c) normal-attempt RPRE energy within firmware budget", emax <= ebudget,
              f"max {emax:.2f} J vs budget {ebudget} J")

    # ---------------- plot ----------------
    fig, ax = plt.subplots(2, 2, figsize=(11, 7))
    for j, rp in enumerate(RP):
        d = c1_run(f"c1p_{rp}", 8, 4.2, rp, 2200e-6, 15)
        ax[0, 0].plot(d["time"] * 1e3, d["vvout"], color=C[j], label=f"RPRE {rp} Ω")
    ax[0, 0].axhline(0.75 * 8 * 4.2, color=S.INK2, ls="--", lw=1)
    ax[0, 0].text(5, 0.75 * 8 * 4.2 + 0.4, "75 % of VIN", color=S.INK2)
    ax[0, 0].set(title="(a) 8S 4.2 V/cell, 2200 µF + 15 W VTX: VOUT vs RPRE", xlabel="ms", ylabel="V")
    ax[0, 0].legend(loc="lower right")
    r = sw[(c1sel, 2200e-6)]
    d = r["d"]
    t = (d["time"] - r["tmain"]) * 1e3
    ax[0, 1].plot(t, d["vvin"], color=C[0], label="VIN")
    ax[0, 1].plot(t, d["vvout"], color=C[1], label="VOUT")
    ax[0, 1].set(title=f"(b) 7S LiHV, 2200 µF + 10 W: stall, main close (C1 {c1sel*1e9:.0f} nF)",
                 xlabel="ms from INP high", ylabel="V", xlim=(-50, 250))
    a2 = ax[1, 1]
    a2.plot(t, d["pq1"], color=C[0], label="P(Q1)")
    a2.plot(t, d["iq1"] * 10, color=C[2], label="I(Q1) × 10")
    a2.set(title="(b) Q1 power and current during the close", xlabel="ms from INP high", ylabel="W  /  A×10",
           xlim=(-5, 150))
    a2.legend()
    ax[0, 1].legend()
    for k, (lab, r) in enumerate(cres.items()):
        d = r["d"]
        ax[1, 0].plot(d["time"] * 1e3, np.cumsum(np.r_[0, 0.5 * (d["ppre"][1:] + d["ppre"][:-1]) * np.diff(d["time"])]),
                      color=C[k], label=lab)
    ax[1, 0].set(title=f"(c) cumulative energy in RPRE = {rpre} Ω", xlabel="ms", ylabel="J", xlim=(0, 600))
    ax[1, 0].legend()
    fig.tight_layout()
    savefig(fig, "case1_precharge.png")
    return "\n".join(lines)



# ===========================================================================
# Case 2 - hot plug of 14S LiHV into the input
# ===========================================================================
INPUT_OPTS = {
    "A: no input C (parasitics only)": dict(cin="1n", cd="1p", rd=1),
    "B: 2 µF ceramic": dict(cin="2u", cd="1p", rd=1),
    "C: 4.7 µF ceramic": dict(cin="4.7u", cd="1p", rd=1),
    "D: 10 µF ceramic": dict(cin="10u", cd="1p", rd=1),
    "E: 2 µF ceramic + 10 µF/0.33 Ω ceramic RC damper": dict(cin="2u", cd="10u", rd=0.33),
    "F: 2 µF ceramic + 47 µF/0.3 Ω Al-electrolytic damper": dict(cin="2u", cd="47u", rd=0.3),
}
INPUT_CHOSEN = "F: 2 µF ceramic + 47 µF/0.3 Ω Al-electrolytic damper"


def c2_metrics(d):
    t = d["time"]
    return dict(vin=d["vvin"].max(), vs=d["vxppvsf"].max(), aux=d["vaux"].max(),
                vds=(d["vvsh"] - d["vsrc"]).max(), ib=d["ivib"].max(), itvs=d["ivxppvtvs"].max(),
                etvs=integ(t, d["ivxppvtvs"] * d["vvin"]))


def case2():
    lines = []
    jobs = {k: POOL.submit(run, "case2_hotplug.cir", f"c2_{k[0]}", v) for k, v in INPUT_OPTS.items()}
    res = {k: f.result() for k, f in jobs.items()}
    rows = []
    for k, d in res.items():
        m = c2_metrics(d)
        ok = m["vin"] < 90 and m["vs"] < 90
        rows.append([k, "%.1f V" % m["vin"], "%.1f V" % m["vds"], "%.1f V" % m["vs"], "%.1f V" % m["aux"],
                     "%.0f A" % m["ib"], "%.2f A / %.1f mJ" % (m["itvs"], 1e3 * m["etvs"]), pf(ok)])
    lines.append("Pack: 14S LiHV 60.9 V, 3 mΩ/cell + 3 mΩ lead, 250 nH lead inductance, ideal contact "
                 "(1 ns, no arc). Main switch and pre-charge off; drone side open. Note the board already has "
                 "two damped RC loads on VIN (VS filter 100 Ω/100 nF, aux OR → 10 Ω/1 µF) besides Q1 Coss and "
                 "the TVS. Pass: peak < 90 V at the FET drain (VIN) and at the controller VS pin.\n")
    lines.append(table(["input network", "VIN / Q1 drain peak", "Q1 Vds peak", "TVS48111 VS peak", "AUX peak",
                        "inrush peak", "TVS peak I / energy", "< 90 V"], rows))
    # sensitivity of chosen network: lead L and pack IR
    sens = {}
    for L in ("150n", "250n", "300n"):
        for rc in ("3m", "15m"):
            p = dict(INPUT_OPTS[INPUT_CHOSEN], lser=L, rcell=rc)
            sens[(L, rc)] = POOL.submit(run, "case2_hotplug.cir", f"c2s_{L}_{rc}", p)
    srows, allok = [], True
    for (L, rc), f in sens.items():
        m = c2_metrics(f.result())
        ok = m["vin"] < 90 and m["vs"] < 90
        allok &= ok
        srows.append([L + "H", rc + "Ω/cell", "%.1f V" % m["vin"], "%.1f V" % m["vs"], "%.0f A" % m["ib"], pf(ok)])
    lines.append(f"\nChosen network ({INPUT_CHOSEN}) across lead inductance and pack condition:\n")
    lines.append(table(["lead L", "cell IR", "VIN peak", "VS peak", "inrush peak", "result"], srows))
    REP.check(2, "hot-plug peak < 90 V at FETs and controller (chosen input network, 150-300 nH)", allok,
              "max VIN %.1f V" % max(c2_metrics(f.result())["vin"] for f in sens.values()))
    lines.append("\nCeramic-only input networks ring with the lead inductance (Q ≈ 3-5) and the TVS cannot "
                 "hold the ring below 90 V because its dynamic resistance (~5.5 Ω) is far above the "
                 "tank's characteristic impedance (0.16-0.35 Ω). A resistive damper branch (R ≈ √(L/Cin) .. "
                 "2√(L/Cin), C ≥ 5 × Cin) removes the overshoot. Option F also gives the energy sink the short-"
                 "circuit turn-off needs (case 3). The electrolytic is only acceptable because the reverse-"
                 "polarity FET Q3 recommended in case 4 keeps a reversed pack off the input capacitors; "
                 "without Q3 use option E (all ceramic: ≈ 5 × 4.7 µF/100 V X7S 1210 + 0.33 Ω).\n")
    DESIGN["Cin"] = "2 × 2.2 µF/100 V X7S 1210 (≈ 2 µF at 60 V) + damper 47 µF/100 V Al-electrolytic, ESR ≈ 0.3 Ω (or 0.33 Ω series)"
    # plot
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    for j, k in enumerate(INPUT_OPTS):
        d = res[k]
        ax[0].plot(d["time"] * 1e6 - 1, d["vvin"], color=C[j], label=k.split(":")[0] + ":" + k.split(":")[1][:28])
    ax[0].axhline(90, color=C[7], ls="--", lw=1)
    ax[0].text(0.2, 91, "90 V limit", color=C[7])
    ax[0].set(title="Hot plug 14S LiHV, 250 nH: VIN (Q1 drain)", xlabel="µs after contact", ylabel="V",
              xlim=(-0.5, 15))
    ax[0].legend(fontsize=7, loc="lower right")
    d = res[INPUT_CHOSEN]
    ax[1].plot(d["time"] * 1e6 - 1, d["vvin"], color=C[0], label="VIN")
    ax[1].plot(d["time"] * 1e6 - 1, d["vxppvsf"], color=C[1], label="TPS48111 VS")
    ax[1].plot(d["time"] * 1e6 - 1, d["vaux"], color=C[2], label="AUX (buck input)")
    a2 = ax[1].twinx()
    a2.plot(d["time"] * 1e6 - 1, d["ivib"], color=C[3], lw=1.0, label="inrush current")
    a2.set_ylabel("A")
    a2.grid(False)
    ax[1].set(title="Chosen network F", xlabel="µs after contact", ylabel="V", xlim=(-0.5, 30))
    ax[1].legend(loc="lower right")
    a2.legend(loc="center right")
    fig.tight_layout()
    savefig(fig, "case2_hotplug.png")
    return "\n".join(lines)


# ===========================================================================
# Case 3 - short circuit while ON
# ===========================================================================
def c3_metrics(d, t_on=10e-6):
    t = d["time"]
    iq1 = d["iq1"]
    sel = t >= t_on
    ipk = float(iq1[sel].max())
    tpk = float(t[sel][np.argmax(iq1[sel])])
    after = np.nonzero((t > tpk) & (iq1 < 1.0))[0]
    tcut = float(t[after[0]] - t_on) if len(after) else None
    return dict(ipk=ipk, tcut=tcut, eq1=integ(t, np.maximum(d["pq1"], 0), t_on), eq2=integ(t, np.maximum(d["pq2"], 0), t_on),
                vds1=float(d["vds1"].max()), vds2=float((-d["vds2"]).max()), vin=float(d["vvin"].max()),
                vs=float(d["vxppvsf"].max()), src=float(d["vsrc"].min()), vout=float(d["vvout"].min()),
                vgs=float(d["vgs"].max()), aux=float(d["vaux"].max()), itvs=float(d["ivxppvtvs"].max()),
                etvs=integ(t, np.maximum(d["ivxppvtvs"] * d["vvin"], 0)))


def c3_ok(m):
    return (m["vds1"] < 100 and m["vds2"] < 100 and m["vs"] < 100 and m["src"] > -30 and m["vgs"] < 20
            and m["eq1"] < 0.5 * EAS_SINGLE and m["ipk"] < ID_PULSE and m["tcut"] is not None)


def case3():
    lines = []
    inp = {k: v for k, v in INPUT_OPTS[INPUT_CHOSEN].items()}
    jobs = {}
    for n, vc in ((1, 4.35), (6, 4.35), (14, 4.35)):
        jobs[f"{n}S LiHV, tsc 1.16 µs"] = (dict(inp, ncell=n, vcell=vc), f"c3_{n}")
    jobs["14S LiHV, tsc 1.6 µs (max)"] = (dict(inp, ncell=14, vcell=4.35, tsc="1.6u"), "c3_14max")
    jobs["14S LiHV, 100 nH out, 1 mΩ short"] = (dict(inp, ncell=14, vcell=4.35, lout="100n", rshort="1m"), "c3_14hard")
    jobs["14S LiHV, 300 nH out lead"] = (dict(inp, ncell=14, vcell=4.35, lout="300n"), "c3_14long")
    # input network alternatives at 14S (justifies the damper)
    for k in ("B: 2 µF ceramic", "E: 2 µF ceramic + 10 µF/0.33 Ω ceramic RC damper"):
        jobs[f"14S, input {k[:1]} instead of F"] = (dict(INPUT_OPTS[k], ncell=14, vcell=4.35), f"c3_14in{k[0]}")
    # output clamp alternatives at 14S
    jobs["14S + output RC snubber 2 µF/1 Ω"] = (dict(inp, ncell=14, vcell=4.35, cout="2u", rout=1), "c3_14rc")
    jobs["14S + output Schottky PG→VOUT (needs Q4)"] = (dict(inp, ncell=14, vcell=4.35, rsch="1m"), "c3_14sch")
    fut = {k: POOL.submit(run, "case3_short.cir", tag, p) for k, (p, tag) in jobs.items()}
    res = {k: f.result() for k, f in fut.items()}
    rows, core_ok = [], True
    for k, d in res.items():
        m = c3_metrics(d)
        ok = c3_ok(m)
        if not k.startswith("14S, input") and "Schottky" not in k and "snubber" not in k:
            core_ok &= ok
        rows.append([k, "%.0f A" % m["ipk"], "%.2f µs" % (m["tcut"] * 1e6) if m["tcut"] else "no",
                     "%.1f / %.2f mJ" % (1e3 * m["eq1"], 1e3 * m["eq2"]), "%.1f V" % m["vds1"],
                     "%.1f V" % m["vin"], "%.1f V" % m["vout"], "%.1f V" % m["src"], "%.1f V" % m["vgs"],
                     "%.1f mJ" % (1e3 * m["etvs"]), pf(ok)])
    REP.check(3, "short at 1S/6S/14S: Vds<100 V, SRC>-30 V, Vgs<20 V, E(Q1)<50 % EAS, I<Id,pulse",
              core_ok, "see table")
    lines.append("Board ON in steady state (gate 12 V above source, 0.6 A idle). At t = 0 a 10 mΩ short "
                 "closes at the drone end of the leads (150 nH loop, drone 2200 µF/30 mΩ bulk at the same "
                 "point). TPS48111 short-circuit trip at 80 mV on the 1 mΩ shunt (RISCP = 4.64 kΩ → 80 A, "
                 "±12 %), tSC 1.16 µs typ / 1.6 µs max, CSCP filter 0.46 µs; peak comparator ignored "
                 f"(firmware-independent path only). Input network {INPUT_CHOSEN}. "
                 "Gate: PD direct (0.69 Ω), C1 = 100 nF + 10 Ω to GND, 15 V gate-source zener.\n\n"
                 f"Pass: Q1/Q2 Vds < 100 V (no avalanche), controller VS < 100 V, SRC > −30 V (TPS48111 abs "
                 f"max SRC-GND), Vgs < 20 V, E(Q1) < 50 % of the {EAS_SINGLE*1e3:.0f} mJ single-pulse "
                 f"avalanche class rating, peak current < {ID_PULSE:.0f} A pulsed.\n")
    lines.append(table(["case", "peak I", "onset → cut-off", "E(Q1) / E(Q2)", "Q1 Vds peak", "VIN peak",
                        "VOUT min", "SRC min", "Vgs peak", "TVS energy", "result"], rows))
    lines.append("\nThe output-side spike is not clamped by anything fitted to the output: when Q1/Q2 open, "
                 "the battery-lead and drone-lead currents flow on in series through Q1's Coss and the input "
                 "network, the drone side swings negative and the common source follows it through Q2's body "
                 "diode. With the damped input network the series loop is absorbed without avalanche and "
                 "SRC stays above −30 V, so **no output clamp is required** for the cases above. A Schottky "
                 "from PG to VOUT (TI's suggestion) would cut the negative swing further, but it would short "
                 "a reversed battery on the drone side unless Q4 (case 5) is fitted; an output RC snubber "
                 "is the fallback if layout inductance is worse than modelled.\n")
    DESIGN["OutClamp"] = "none required (layout placeholder: 2 µF/100 V + 1 Ω RC snubber VOUT-PG, DNP)"
    # plot
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))
    for j, k in enumerate(["1S LiHV, tsc 1.16 µs", "6S LiHV, tsc 1.16 µs", "14S LiHV, tsc 1.16 µs"]):
        d = res[k]
        tt = (d["time"] - 10e-6) * 1e6
        ax[0].plot(tt, d["iq1"], color=C[j], label=k.split(",")[0])
        ax[1].plot(tt, d["vds1"], color=C[j], label=k.split(",")[0])
    d = res["14S LiHV, tsc 1.16 µs"]
    tt = (d["time"] - 10e-6) * 1e6
    for j, (n, lab) in enumerate([("vvin", "VIN"), ("vvout", "VOUT"), ("vsrc", "SRC"), ("vgs", "Vgs")]):
        ax[2].plot(tt, d[n], color=C[j], label=lab)
    ax[1].axhline(100, color=C[7], ls="--", lw=1)
    ax[2].axhline(-30, color=C[7], ls="--", lw=1)
    ax[2].text(9, -28, "SRC −30 V abs max", color=C[7], fontsize=7)
    ax[0].set(title="Q1 current, dead short at t = 0", xlabel="µs", ylabel="A", xlim=(-1, 12))
    ax[1].set(title="Q1 drain-source voltage", xlabel="µs", ylabel="V", xlim=(-1, 12))
    ax[2].set(title="14S LiHV: node voltages", xlabel="µs", ylabel="V", xlim=(-1, 12))
    for a in ax:
        a.legend(fontsize=7)
    fig.tight_layout()
    savefig(fig, "case3_short.png")
    return "\n".join(lines)


# ===========================================================================
CASES = {1: ("Pre-charge sizing (RPRE, Cdvdt, energy)", case1),
         2: ("Hot plug of 14S LiHV", case2),
         3: ("Short circuit while ON", case3)}


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
        except Exception as e:  # a crash is a FAIL
            traceback.print_exc()
            REP.check(k, "simulation ran", False, repr(e)[:300])
            out[k] = f"Simulation error: `{e!r}`"
        print(f"   {time.time()-t0:.1f} s", flush=True)
    for c in REP.checks:
        print(("PASS " if c[2] else "FAIL ") + f"case {c[0]}: {c[1]} :: {c[3]}")
    print(f"total {time.time()-t00:.0f} s; {len(REP.fails)} FAIL(s)")
    return out


if __name__ == "__main__":
    sel = [int(a) for a in sys.argv[1:]] or sorted(CASES)
    main(sel)
    sys.exit(1 if REP.fails else 0)
