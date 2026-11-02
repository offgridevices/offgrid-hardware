"""The power-cycle gesture (gesture.py) against a fake clock and fake storage
that keeps what was written when the power goes, and the service acting on
the request it leaves."""
import os, tempfile, unittest

from layercam import config, gesture, service


class PowerLost(Exception):
    """The plug is pulled: the process stops wherever it is."""


class Flash:
    """Fake storage: what survives a power cut is what was written."""

    def __init__(self):
        self.count, self.requested, self.writes = 0, False, 0

    def read(self):
        return self.count

    def write(self, n):
        self.count = n
        self.writes += 1

    def request_reset(self):
        self.requested = True
        self.writes += 1


class Camera:
    """Power-ups on a fake clock.  power_up(on_s): plugged in for on_s
    seconds after the count (the flashes); None = left plugged in."""

    def __init__(self):
        self.flash = Flash()
        self.now = 0.0
        self.flashes = []

    def power_up(self, on_s, off_s=3.0, boot_s=3.0):
        self.now += boot_s                         # kernel, init up to S21
        unplug = None if on_s is None else self.now + on_s

        def sleep(s):
            if unplug is not None and self.now + s > unplug:
                self.now = unplug
                raise PowerLost()
            self.now += s
        try:
            res = gesture.on_power_up(self.flash, sleep=sleep, ack=self.flashes.append)
        except PowerLost:
            res = 'power lost'
        if unplug is not None:
            self.now = max(self.now, unplug) + off_s
        return res


class Gesture(unittest.TestCase):
    def test_three_short_power_ups(self):
        c = Camera()
        self.assertEqual(c.power_up(1.0), 'power lost')
        self.assertEqual(c.power_up(2.0), 'power lost')
        self.assertFalse(c.flash.requested)
        self.assertEqual(c.power_up(None), 'reset')      # the third: left plugged in, acts at once
        self.assertTrue(c.flash.requested)
        self.assertEqual(c.flash.count, 0)               # and the count starts again
        self.assertEqual(c.flashes, [1, 2, 3])            # the LED says which power-up it counted
        self.assertLess(c.now, 30)                        # the whole gesture, as the README describes it

    def test_ordinary_power_up_counts_nothing(self):
        c = Camera()
        for _ in range(5):
            self.assertEqual(c.power_up(None), 'counted')
        self.assertEqual(c.flash.count, 0)
        self.assertFalse(c.flash.requested)
        self.assertEqual(c.flash.writes, 10)              # two tiny writes a boot, none after

    def test_one_long_power_up_cancels(self):
        c = Camera()
        c.power_up(1.0)
        c.power_up(gesture.SHORT_S + 0.5)                  # stayed on past the window: count cleared
        self.assertEqual(c.flash.count, 0)
        c.power_up(1.0)
        c.power_up(1.0)
        self.assertFalse(c.flash.requested)                # short, long, short, short: not three in a row
        self.assertEqual(c.flash.count, 2)
        c.power_up(None)
        self.assertTrue(c.flash.requested)

    def test_window_edge(self):
        c = Camera()
        c.power_up(gesture.SHORT_S - 0.1)                  # just inside: still counts
        self.assertEqual(c.flash.count, 1)
        c.power_up(gesture.SHORT_S)                        # the clear is written as the window ends
        self.assertEqual(c.flash.count, 0)

    def test_unplugged_before_counting_is_not_seen(self):
        c = Camera()
        c.power_up(1.0)
        # a power-up cut before S21 never reaches on_power_up: nothing changes
        c.now += 2.0
        c.power_up(1.0)
        self.assertEqual(c.flash.count, 2)
        c.power_up(None)
        self.assertTrue(c.flash.requested)


class Files(unittest.TestCase):
    def test_file_store(self):
        d = tempfile.mkdtemp()
        st = gesture.FileStore(d)
        self.assertEqual(st.read(), 0)                     # no file yet
        st.write(2)
        self.assertEqual(gesture.FileStore(d).read(), 2)   # as the next boot reads it
        with open(st.count_path, 'w') as f:
            f.write('\x00\x00')                              # torn or garbage: counts as 0
        self.assertEqual(st.read(), 0)
        self.assertFalse(st.reset_requested())
        st.request_reset()
        self.assertTrue(st.reset_requested())
        st.clear_request()
        st.clear_request()                                 # twice is fine
        self.assertFalse(st.reset_requested())
        self.assertEqual(sorted(os.listdir(d)), ['bootcount'])

    def test_main_on_a_folder(self):
        d = tempfile.mkdtemp()
        st = gesture.FileStore(d)
        st.write(gesture.NEEDED - 1)
        self.assertEqual(gesture.main(['gesture', d]), 0)  # the init script's call; the LED file is absent
        self.assertTrue(st.reset_requested())
        self.assertEqual(st.read(), 0)

    def test_service_acts_on_the_request(self):
        d = tempfile.mkdtemp()
        cfg = config.Config({('wifi', 'ssid'): 'Workshop', ('wifi', 'password'): 'correct horse',
                             ('wifi', 'ap_password'): 'forgotten one', ('web', 'password'): 'pagepass',
                             ('timelapse', 'storage'): os.path.join(d, 'tl')}, path=os.path.join(d, 'layercam.ini'))
        cfg.save()
        svc = service.Service(cfg.path, port=0, hw_root=os.path.join(d, 'root'))
        self.assertFalse(svc.take_wifi_reset())            # nothing asked
        gesture.FileStore(d).request_reset()
        self.assertTrue(svc.take_wifi_reset())
        saved = config.load(cfg.path)
        self.assertEqual((saved.get('wifi', 'ssid'), saved.get('wifi', 'password'), saved.get('wifi', 'ap_password')),
                         ('', '', ''))
        self.assertEqual(saved.get('web', 'password'), 'pagepass')     # the page password stays
        self.assertFalse(gesture.FileStore(d).reset_requested())


if __name__ == '__main__':
    unittest.main()
