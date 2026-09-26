# -*- coding: utf-8 -*-
"""Autoroute a placed board with Freerouting, then pour and check it.

  export Specctra DSN (KiCad) -> Freerouting 1.9 -> import SES (KiCad)

Freerouting 1.9.0 is used, not 2.x: 2.1 ignores its pass limit and never
writes a session file in batch mode.  1.9 needs a display even in batch
mode, so it runs under xvfb-run.  Set FREEROUTING_JAR to the jar's path.
"""
import os, sys, subprocess, shutil
import pcbnew

JAR = os.environ.get('FREEROUTING_JAR', os.path.expanduser('~/freerouting-1.9.0.jar'))

def export_dsn(pcb_path, dsn_path):
    b = pcbnew.LoadBoard(pcb_path)
    ok = pcbnew.ExportSpecctraDSN(b, dsn_path)
    if not ok:
        raise SystemExit('DSN export failed')

def freeroute(dsn_path, ses_path, passes=20, timeout=None, log=None):
    timeout = timeout or int(os.environ.get('FREEROUTING_TIMEOUT', 1800))
    cmd = ['xvfb-run', '-a', 'java', '-jar', JAR, '-de', dsn_path, '-do', ses_path, '-mp', str(passes)]
    with open(log or os.devnull, 'w') as f:
        p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, start_new_session=True,
                             cwd=os.path.dirname(os.path.abspath(dsn_path)))
        try:
            rc = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, 9)          # java and Xvfb too, not just xvfb-run
            p.wait()
            raise SystemExit('Freerouting did not finish in %d s' % timeout)
    if rc != 0 or not os.path.exists(ses_path):
        raise SystemExit('Freerouting failed (rc=%s), see %s' % (rc, log))

def import_ses(pcb_path, ses_path, out_path):
    b = pcbnew.LoadBoard(pcb_path)
    if not pcbnew.ImportSpecctraSES(b, ses_path):
        raise SystemExit('SES import failed')
    b.Save(out_path)

def unrouted(pcb_path):
    b = pcbnew.LoadBoard(pcb_path)
    filler = pcbnew.ZONE_FILLER(b)
    filler.Fill(b.Zones())
    b.BuildConnectivity()
    c = b.GetConnectivity()
    n = c.GetUnconnectedCount(False)
    return n, b

def route(pcb_in, pcb_out, passes=60, rounds=4):
    """Route, then keep re-routing the partly routed board (Freerouting
    carries the existing wiring over and works on what is left) until every
    connection is made or `rounds` runs out.  Returns the unrouted count."""
    work = os.path.dirname(os.path.abspath(pcb_out))
    src = pcb_in
    best = None
    for r in range(rounds):
        dsn = os.path.join(work, 'route%d.dsn' % r); ses = os.path.join(work, 'route%d.ses' % r)
        export_dsn(src, dsn)
        freeroute(dsn, ses, passes=passes, log=os.path.join(work, 'freerouting%d.log' % r))
        import_ses(src, ses, pcb_out)
        n, _ = unrouted(pcb_out)
        print('  routing round %d: %d unrouted' % (r + 1, n))
        if best is None or n < best[0]:
            best = (n, r)
            shutil.copy(pcb_out, pcb_out + '.best')
        if n == 0:
            break
        src = pcb_out
    shutil.copy(pcb_out + '.best', pcb_out); os.remove(pcb_out + '.best')
    return best[0]

if __name__ == '__main__':
    n = route(sys.argv[1], sys.argv[2], passes=int(os.environ.get('PASSES', 60)))
    print('unrouted connections after autoroute + fill: %d' % n)
