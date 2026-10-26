#!/usr/bin/env python3
"""Print a LayerCam's setup access point name and passphrase.

    python3 tools/layercam-ap.py              ask the camera over USB (adb), plugged in and booted
    python3 tools/layercam-ap.py SERIAL       from its serial number (/proc/cpuinfo "Serial")

The camera derives both from its SoC's serial number (layercam/net.py,
ap_credentials), so this gives the same answer without the camera on Wi-Fi.
The camera also prints them on its serial console (test pads TP1/TP2,
115200) whenever the access point opens.  A camera whose
wifi.ap_password is set uses that instead.
"""
import os, subprocess, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from layercam import net  # noqa: E402


def serial_over_adb():
    try:
        out = subprocess.run(['adb', 'shell', 'cat', '/proc/cpuinfo'], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as e:
        sys.exit('adb not available (%s): give the serial number instead' % e)
    path = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'layercam-cpuinfo.txt')
    with open(path, 'w') as f:
        f.write(out.stdout)
    s = net.cpu_serial(path)
    os.unlink(path)
    if not s:
        sys.exit('no Serial in the camera\'s /proc/cpuinfo (is it connected? adb devices)')
    return s


def main(argv):
    serial = argv[1] if len(argv) > 1 else serial_over_adb()
    ssid, pw = net.ap_credentials(serial)
    print('serial        %s' % serial.lower())
    print('access point  %s' % ssid)
    print('passphrase    %s' % pw)


if __name__ == '__main__':
    main(sys.argv)
