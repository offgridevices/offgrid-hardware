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

# A board may add routing-only constraints (keepouts) to the copy exported
# for Freerouting: PRE_EXPORT(board) is called before the DSN is written.
PRE_EXPORT = None

# Freerouting's router costs, written into the DSN's structure scope (the
# same autoroute_settings block Freerouting saves in its own .rules files).
# Freerouting is deterministic for a given input; different costs give
# genuinely different routings.  None: Freerouting's defaults.
#   dict(via_costs=50, plane_via_costs=5, start_ripup_costs=100, fanout=False,
#        directions={'F.Cu': 'horizontal', ...}, against=2.0)
# fanout=True runs Freerouting's fan-out pass first: an escape via at each
# SMD pin before general routing, so dense QFN pins keep a way out.
AUTOROUTE = None

# Vias in SMD pads.  KiCad's DSN export forbids them (every via padstack
# "(attach off)", no via_at_smd control); where both sides of a board are
# packed, a pad is often the only spot left for its net's via.  Set to a
# via's (diameter, drill) in mm: Freerouting may then drop that via onto a
# same-net SMD pad (Specctra "(control (via_at_smd on))" plus "(attach on)"
# on its padstack).  Such vias must be ordered filled and capped (POFV),
# and the via's ring must already meet the fab's hole-to-copper rule, as
# Freerouting keeps only copper clearances.  None: no vias in pads.
VIA_IN_PAD = None

# Freerouting keeps copper clearances only.  A via whose ring is thinner
# than VIA_RING (mm) goes to it with that ring, so its copper keeps the
# fab's hole-to-copper distance from the hole.  Only locked vias can be
# shown larger: KiCad's session import keeps the board's own locked tracks
# and vias (they go out as fixed wiring) instead of taking them back from
# Freerouting.  None: vias as they are.
VIA_RING = None


def _autoroute_block(a, layers):
    lines = ['    (autoroute_settings', '      (fanout %s)' % ('on' if a.get('fanout') else 'off'),
             '      (autoroute on)', '      (postroute on)',
             '      (vias on)', '      (via_costs %d)' % a.get('via_costs', 50),
             '      (plane_via_costs %d)' % a.get('plane_via_costs', 5),
             '      (start_ripup_costs %d)' % a.get('start_ripup_costs', 100),
             '      (start_pass_no 1)']
    dirs = a.get('directions', {})
    for i, l in enumerate(layers):
        d = dirs.get(l, 'horizontal' if i % 2 == 0 else 'vertical')
        lines += ['      (layer_rule %s' % l, '        (active on)', '        (preferred_direction %s)' % d,
                  '        (preferred_direction_trace_costs 1.0)',
                  '        (against_preferred_direction_trace_costs %.1f)' % a.get('against', 2.0), '      )']
    lines.append('    )')
    return '\n'.join(lines) + '\n'


def export_dsn(pcb_path, dsn_path):
    b = pcbnew.LoadBoard(pcb_path)
    if PRE_EXPORT:
        PRE_EXPORT(b)
    if VIA_RING:
        for t in b.GetTracks():
            if t.GetClass() == 'PCB_VIA' and t.IsLocked():
                d = t.GetDrillValue() + 2 * int(round(VIA_RING * 1e6))
                if t.GetWidth(pcbnew.F_Cu) < d:
                    t.SetWidth(d)
    ok = pcbnew.ExportSpecctraDSN(b, dsn_path)
    if not ok:
        raise SystemExit('DSN export failed')
    if VIA_IN_PAD:
        allow_via_in_pad(dsn_path, *VIA_IN_PAD)
    if AUTOROUTE:
        import re
        txt = open(dsn_path).read()
        sig = [m.group(1) for m in re.finditer(r'\(layer (\S+)\s+\(type signal\)', txt)]
        # right after the layer definitions (its layer_rules name layers that
        # must already be defined), before the boundary
        j = txt.index('\n    (boundary') + 1
        txt = txt[:j] + _autoroute_block(AUTOROUTE, sig) + txt[j:]
        open(dsn_path, 'w').write(txt)

def allow_via_in_pad(dsn_path, d, drill):
    import re
    txt = open(dsn_path).read()
    name = '_%d:%d_um"' % (round(d * 1000), round(drill * 1000))
    m = re.search(r'\(padstack "Via\[\d+-\d+\]' + re.escape(name) + r'.*?\(attach off\)', txt, re.S)
    if not m:
        raise SystemExit('VIA_IN_PAD: no %.2f / %.2f mm via padstack in %s' % (d, drill, dsn_path))
    txt = txt[:m.end() - len('(attach off)')] + '(attach on)' + txt[m.end():]
    # the control scope sits in the structure, after its via list
    j = txt.index('\n', re.search(r'\n    \(via "', txt).end()) + 1
    txt = txt[:j] + '    (control\n      (via_at_smd on)\n    )\n' + txt[j:]
    open(dsn_path, 'w').write(txt)


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
        if r > 0:
            # Freerouting hangs ("normalization of net ... failed") on its own
            # near-degenerate wiring when that is fed back to it
            import pcb
            pcb.tidy_tracks(src)
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
