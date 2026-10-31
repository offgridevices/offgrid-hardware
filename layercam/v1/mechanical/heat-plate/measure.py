# -*- coding: utf-8 -*-
"""Measure the case above the main board's back face: for each point on a 0.5 mm grid round the SoC,
the Z of the first plastic above Z 21.0 (the ceiling) and how thick that plastic is there (until the ray
leaves it).  Writes housing_ceiling.json, which plate.py reads.

    HOUSING_DIR=<folder with asm_bottom.stl, asm_top.stl, asm_lid.stl> python3 measure.py

The asm_*.stl files are Prusa's buddy-camera-bottom-r2 / -top-r1 / -lid-r1 (Printables 1343977) moved to
their assembled positions in the lens frame (docs/housing.md).  Needs trimesh with an rtree backend.
"""
import json, os, sys
import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
hd = os.environ['HOUSING_DIR']
A = trimesh.util.concatenate([trimesh.load(os.path.join(hd, 'asm_%s.stl' % n)) for n in ('bottom', 'top', 'lid')])
xs = np.arange(-12.0, 12.01, 0.5)
ys = np.arange(-30.0, 10.01, 0.5)
X, Y = np.meshgrid(xs, ys)
O = np.c_[X.ravel(), Y.ravel(), np.full(X.size, 21.0)]
D = np.tile([0, 0, 1.0], (X.size, 1))
loc, ri, _ = A.ray.intersects_location(O, D, multiple_hits=True)
ceil = np.full(X.size, np.nan)
thick = np.full(X.size, np.nan)
for k in range(X.size):
    z = np.sort(loc[ri == k][:, 2])
    if len(z):
        ceil[k] = z[0]
        thick[k] = (z[1] - z[0]) if len(z) > 1 else np.nan
json.dump(dict(xs=xs.tolist(), ys=ys.tolist(), ceil=np.round(ceil.reshape(X.shape), 3).tolist(),
               thick=np.round(thick.reshape(X.shape), 3).tolist(),
               source='Printables 1343977 STLs, assembled (docs/housing.md); rays up from Z 21.0'),
          open(os.path.join(HERE, 'housing_ceiling.json'), 'w'))
print('ceiling %.2f-%.2f, plastic %.2f-%.2f mm' % (np.nanmin(ceil), np.nanmax(ceil), np.nanmin(thick), np.nanmax(thick)))
