"""LayerCam camera software: Prusa Connect snapshots and per-layer timelapses.

Python 3.8 or newer, standard library only, so it runs on the Luckfox SDK's
Buildroot python3 with nothing else installed.  The camera itself (ISP,
JPEG and H.264 encoders) is driven by the small C helper in ../native/.
"""
VERSION = '0.1.0'
HARDWARE = 'LayerCam v1'
