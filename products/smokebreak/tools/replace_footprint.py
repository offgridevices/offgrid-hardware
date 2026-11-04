"""Put the footprint parts.py now names under a placed part on the routed
board, keeping its position, rotation, side and nets.

    cd src && python3 ../tools/replace_footprint.py REF [REF...]

The copper is not touched: check DRC afterwards (a larger pad can crowd a
track) and route again locally where it does."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
import pcbnew  # noqa: E402

import board as B  # noqa: E402
import circuit  # noqa: E402
import make  # noqa: E402
import parts  # noqa: E402

b = pcbnew.LoadBoard(make.OUT)
keep = []
for ref in sys.argv[1:]:
    old = b.FindFootprintByReference(ref)
    c = circuit.COMPONENTS[ref]
    pd = parts.PARTS[c['part']]
    new = B.load_fp(pd['fp'])
    new.SetReference(ref)
    new.SetValue(old.GetValue())
    for k, v in (('MPN', pd['mpn']), ('Manufacturer', pd['mfr']), ('LCSC', pd['lcsc'])):
        if v:
            new.SetField(k, v)
    for fld in new.GetFields():
        if not (fld.IsReference() or fld.IsValue()):
            fld.SetVisible(False)
    b.Add(new)
    new.Reference().SetLayer(pcbnew.F_Fab)
    new.Reference().SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.6), pcbnew.FromMM(0.6)))
    new.Reference().SetTextThickness(pcbnew.FromMM(0.1))
    new.Value().SetLayer(pcbnew.F_Fab)
    new.Value().SetVisible(False)
    for it in new.GraphicalItems():
        if it.GetLayer() == pcbnew.F_SilkS:
            it.SetLayer(pcbnew.F_Fab)
    for pad in new.Pads():
        net = c['pins'].get(pad.GetNumber())
        if net:
            pad.SetNet(b.FindNet(net))
    if old.IsFlipped():
        new.Flip(new.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
    new.SetPosition(old.GetPosition())
    new.SetOrientation(old.GetOrientation())
    keep.append(old)
    b.Remove(old)
    print(ref, '->', pd['fp'])
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(make.OUT, b)
B.set_stackup(make.OUT, inner_oz=1.0)
