; ---- LayerCam: add at the END of the printer profile's Start G-code ----
; Where the printer sends its metrics: the camera's address and port 8514.
; Replace 192.0.2.40 with your camera's address (its setup page shows it;
; give it a fixed one in your router).  The first print with a new address
; stops on the printer's screen to ask "allow metrics change?": tap Yes once.
M334 192.0.2.40 8514
; keep the G-code line metric off; the layer snippet turns it on briefly
M332 gcode
