"""Re-route the driver's gate side alone: rip GATE / SRC / PU / BST / CDVDT copper
round the FETs and route them again, SRC first, fine grid, small vias.  IN OUT"""
import sys
import pcbnew
import board as B
import finish, finish_run

NETS = ('TPS_BST', 'TPS_PU', 'SRC', 'GATE', 'CDVDT')     # the inner pins first


def reroute(b):
    x0, y0, x1, y1 = 66.0 + B.OX, 37.0 + B.OY, 87.0 + B.OX, 51.8 + B.OY
    n = 0
    for t in list(b.GetTracks()):
        if t.GetNetname() in NETS:
            bb = t.GetBoundingBox()
            if pcbnew.ToMM(bb.GetRight()) > x0 and pcbnew.ToMM(bb.GetLeft()) < x1 and \
               pcbnew.ToMM(bb.GetBottom()) > y0 and pcbnew.ToMM(bb.GetTop()) < y1:
                w = pcbnew.ToMM(t.GetWidth()) if t.GetClass() == 'PCB_TRACK' else 0
                if t.GetClass() == 'PCB_TRACK' and w >= 0.55 and t.GetNetname() == 'SRC':
                    continue                                   # the FETs' own source straps stay
                t.SetLocked(False)
                B.remove(b, t)
                n += 1
    print('ripped', n)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    finish.ROUTE_LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu]
    finish.VIA_D, finish.VIA_DRILL, finish.RES = 0.45, 0.2, 0.025
    w, cl = finish_run.rules()
    for net in NETS:
        print(net, 'islands left', finish.route_net(b, net, track_w=0.15, clmap=cl))
    return b


if __name__ == '__main__':
    b = pcbnew.LoadBoard(sys.argv[1])
    reroute(b)
    b.Save(sys.argv[2])
