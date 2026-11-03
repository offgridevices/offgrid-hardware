;AFTER_LAYER_CHANGE
;[layer_z]
; ---- LayerCam: everything below goes AFTER the two lines above (Prusa's own) ----
; Park the head, tell the camera, hold still, come back.  The slicer has
; already retracted for the layer change (retract_layer_change = 1 in Prusa's
; CORE One profiles), so nothing oozes while it waits.
; Park position: change it here.  X2 Y218 is the back-left corner; the CORE
; One's head can go X -2..252, Y -19..221.  Pick the corner where the head
; hides least of the print from the camera.
{local park_x = 2}{local park_y = 218}
G1 X{park_x} Y{park_y} F18000
M400
M331 gcode
; the trigger, then 15 lines that fill the printer's 1 kB metrics buffer so it goes out now
M118 OGCAM:LAYER:{layer_num}
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
G4 P600
; the trigger, then 15 lines that fill the printer's 1 kB metrics buffer so it goes out now
M118 OGCAM:LAYER:{layer_num}
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
M118 _xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
G4 P600
M332 gcode
G1 X{position[0]} Y{position[1]} F18000
