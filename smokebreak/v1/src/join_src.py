"""Hand route: U1's SRC sense pin under the controller body to a via, along the
bottom layer's south edge, up into the FETs' source copper."""
import sys
import pcbnew
import board as B

b = pcbnew.LoadBoard(sys.argv[1])
u1 = b.FindFootprintByReference('U1')
p13 = [p for p in u1.Pads() if p.GetNumber() == '13'][0].GetPosition()
x13, y13 = pcbnew.ToMM(p13.x) - B.OX, pcbnew.ToMM(p13.y) - B.OY
vx = x13 - 1.45                                  # under the body, clear of the pad row
B.track(b, [(x13, y13), (vx, y13)], 0.15, pcbnew.F_Cu, 'SRC')
B.via(b, vx, y13, 'SRC', d=0.45, drill=0.2)
B.track(b, [(vx, y13), (vx, 51.2), (75.0, 51.2), (75.0, 47.2)], 0.25, pcbnew.B_Cu, 'SRC')
B.via(b, 75.0, 47.2, 'SRC', d=0.45, drill=0.2)
b.Save(sys.argv[2])
print('via at', round(vx, 2), round(y13, 2))
