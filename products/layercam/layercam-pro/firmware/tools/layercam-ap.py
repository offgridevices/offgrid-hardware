#!/usr/bin/env python3
"""Print a LayerCam's setup access point name and passphrase.

    python3 tools/layercam-ap.py SERIAL          from its serial number (/proc/cpuinfo "Serial"),
                                                 e.g. for a label
    python3 tools/layercam-ap.py --port DEV      ask the camera over its USB console: plugged into
                                                 this computer and started; DEV is /dev/ttyACM0
                                                 (Linux) or /dev/cu.usbmodem... (macOS)

The camera derives both from its SoC's serial number (layercam/net.py,
ap_credentials), so the serial gives the same answer without the camera.
On Windows, open the camera's COM port in any terminal and type `ap`.  The
camera also prints them on its serial console (test pads TP1/TP2, 115200)
whenever the access point opens.  A camera whose wifi.ap_password is set
uses that instead (never shown; the power-cycle gesture or `reset-wifi`
on the USB console clears it).
"""
import os, select, sys, time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from layercam import net  # noqa: E402


def ask_console(port, timeout=5.0):
    """Send `ap` to the USB console, return its answer lines (POSIX only)."""
    import termios, tty
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY)
    try:
        tty.setraw(fd)
        termios.tcflush(fd, termios.TCIOFLUSH)
        os.write(fd, b'\rap\r')
        buf, end = b'', time.time() + timeout
        while time.time() < end and b'page ' not in buf:
            r, _, _ = select.select([fd], [], [], 0.2)
            if r:
                buf += os.read(fd, 4096)
    finally:
        os.close(fd)
    keep = ('serial ', 'access point ', 'passphrase ', 'page ')
    return [ln.strip() for ln in buf.decode('utf-8', 'replace').splitlines() if ln.strip().startswith(keep)]


def main(argv):
    if len(argv) == 3 and argv[1] == '--port':
        lines = ask_console(argv[2])
        if not lines:
            sys.exit('no answer from %s (is it the camera, and has it started?)' % argv[2])
        print('\n'.join(lines))
        return
    if len(argv) != 2 or argv[1].startswith('-'):
        sys.exit(__doc__)
    ssid, pw = net.ap_credentials(argv[1])
    print('serial        %s' % argv[1].lower())
    print('access point  %s' % ssid)
    print('passphrase    %s' % pw)


if __name__ == '__main__':
    main(sys.argv)
