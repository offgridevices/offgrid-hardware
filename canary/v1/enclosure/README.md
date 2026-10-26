# Canary v1 bumper

An optional 3D-printed frame that protects the board's edges (PLA or PETG,
no supports, 64.3 × 44.3 × 5.0 mm). Open top and bottom: the board presses
in from below, a 0.8 mm lip stops it at the top face, and its underside
stays flush with the frame's so the thermal tab still lies on the pack.
Cut-outs for the USB-C, the probe connector and the sensor head's air path.

```sh
openscad -o print/canary-v1-bumper.stl bumper.scad
```

`print/canary-v1-bumper.stl` is one watertight body (checked with trimesh).
