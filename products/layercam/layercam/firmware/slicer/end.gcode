; ---- LayerCam: add at the END of the printer profile's End G-code ----
; Prusa's end code has already lifted the head and parked it (G1 X242 Y211):
; one last frame of the finished print.
M400
M331 gcode
; the trigger, then 15 lines that fill the printer's 1 kB metrics buffer so it goes out now
M118 OGCAM:END
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
G4 P1000
M332 gcode
