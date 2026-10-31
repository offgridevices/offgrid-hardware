"""The power-cycle gesture: three short power-ups in a row forget the Wi-Fi
settings and open the setup access point.  The camera has no button.

Run once per boot, as early as the init scripts allow (S21-layercam-gesture,
right after /userdata is mounted), from the factory copy:

    python3 -S -m layercam.gesture /userdata/layercam

1. It adds one to a counter in /userdata/layercam/bootcount and writes it
   to the flash at once (fsync), then flashes the status LED once per count.
2. If the camera stays powered for SHORT_S after that, the counter goes back
   to 0: an ordinary power-up never counts towards the gesture.
3. When the counter reaches NEEDED, it writes /userdata/layercam/wifi-reset
   (the service forgets the network, opens the setup access point and
   deletes the file) and starts the count again.

So the gesture is: plug in, wait for the quick flashes, unplug; twice; the
third time leave it plugged in.  How long it is off in between cannot be
measured (the RTC has no battery), so there is no 30-second window as
such; what keeps it from happening by accident is that every power-up that
lasts SHORT_S after the flashes cancels it.

Flash wear: two writes of a few bytes per boot (the count, then 0), on
UBIFS, which appends them to its journal (a few 2 kB pages each time) and
spreads the erases over the whole 90 MB userdata volume (UBI wear
levelling).  One 128 kB erase block takes dozens of boots, and the
W25N02KV's ~700 userdata blocks take 100 000 erases each: far more boots
than a camera will ever see.  Nothing is written after the first 5 s.
"""
import os, sys, time

NEEDED = 3            # short power-ups in a row
SHORT_S = 5.0         # a power-up is short when the power goes within this long of the flashes
COUNT_FILE = 'bootcount'
REQUEST_FILE = 'wifi-reset'
LED = '/sys/class/leds/status/brightness'


def _durable_write(path, text):
    tmp = path + '.tmp'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, text.encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
    dfd = os.open(os.path.dirname(path) or '.', os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


class FileStore:
    """The counter and the reset request, as two tiny files in one folder."""

    def __init__(self, folder):
        self.folder = folder
        self.count_path = os.path.join(folder, COUNT_FILE)
        self.request_path = os.path.join(folder, REQUEST_FILE)

    def read(self):
        try:
            with open(self.count_path) as f:
                n = int(f.read().strip() or 0)
            return n if 0 <= n < 100 else 0
        except (OSError, ValueError):
            return 0

    def write(self, n):
        _durable_write(self.count_path, '%d\n' % n)

    def request_reset(self):
        _durable_write(self.request_path, 'power-cycle gesture\n')

    def reset_requested(self):
        return os.path.exists(self.request_path)

    def clear_request(self):
        try:
            os.unlink(self.request_path)
        except FileNotFoundError:
            pass


def on_power_up(store, sleep=time.sleep, ack=None, needed=NEEDED, short_s=SHORT_S):
    """Count this power-up.  -> 'reset' (gesture complete) or 'counted' (it
    lasted SHORT_S, so the count is back at 0).  If the power goes during
    the wait, this never returns, and the count stays for the next boot."""
    n = store.read() + 1
    if n >= needed:
        store.request_reset()
        store.write(0)
        if ack:
            ack(n)
        return 'reset'
    store.write(n)
    if ack:
        ack(n)
    sleep(short_s)
    store.write(0)
    return 'counted'


def led_ack(n, led=LED, sleep=time.sleep):
    """n quick flashes, then on (the service takes the LED over later)."""
    try:
        for _ in range(n):
            for v, t in ((1, 0.08), (0, 0.15)):
                with open(led, 'w') as f:
                    f.write(str(v))
                sleep(t)
        with open(led, 'w') as f:
            f.write('1')
    except OSError:
        pass


def main(argv):
    folder = argv[1] if len(argv) > 1 else '/userdata/layercam'
    try:
        os.makedirs(folder, exist_ok=True)
        res = on_power_up(FileStore(folder), ack=led_ack)
    except OSError as e:
        sys.stderr.write('layercam gesture: %s\n' % e)
        return 1
    if res == 'reset':
        sys.stderr.write('LayerCam: power-cycle gesture: Wi-Fi settings will be cleared\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
