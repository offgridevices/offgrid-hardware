;BEFORE_LAYER_CHANGE
G92 E0.0
;[layer_z]
{if layer_z > 150}
M201 X{interpolate_table(layer_z, (0,7000), (150,7000), (200,4000), (270,2000))} Y{interpolate_table(layer_z, (0,7000), (150,7000), (200,4000), (270,2000))}
{endif}
; ---- LayerCam: nothing to add here.  This is Prusa's own CORE One
; "Before layer change" G-code (PrusaSlicer 2.9.6 profile), unchanged:
; the camera snippet goes in "After layer change", once the head is on the
; new layer and retracted.
