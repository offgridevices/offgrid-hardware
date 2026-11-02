"""The timelapse state machine: start, layers, finish, cancel, missed and
duplicate triggers, the Z fallback, the idle timeout."""
import unittest

from layercam.metrics import Trigger
from layercam.prusalink import PrinterStatus
from layercam.timelapse import Timelapse, ZLayers


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def layer(n, age=100):
    return Trigger('LAYER', str(n), age, '192.0.2.10')


def kinds(actions):
    return [a[0] for a in actions]


PRINTING = PrinterStatus('PRINTING', 7, 'Benchy.bgcode', 10.0, 0.2)


class T(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.tl = Timelapse('auto', dwell_ms=1600, settle_ms=150, clock=self.clock)

    def test_normal_print(self):
        self.assertEqual(self.tl.printer(PRINTING), [('start', 'Benchy.bgcode')])
        self.assertEqual(self.tl.printer(PRINTING), [])        # same job again: nothing
        a = self.tl.trigger(layer(1, age=100))
        self.assertEqual(a, [('frame', 1, 0.05)])                # 150 ms settle, 100 already gone
        self.assertEqual(self.tl.trigger(layer(2, age=400)), [('frame', 2, 0.0)])
        a = self.tl.trigger(Trigger('END', None, 0, ''))
        self.assertEqual(kinds(a), ['frame'])
        self.assertEqual(self.tl.frames, 3)
        a = self.tl.printer(PrinterStatus('FINISHED', 7, 'Benchy.bgcode'))
        self.assertEqual(a, [('finish', 'finished')])
        self.assertFalse(self.tl.recording)

    def test_duplicates_ignored(self):
        self.tl.printer(PRINTING)
        self.tl.trigger(layer(5))
        self.assertEqual(self.tl.trigger(layer(5)), [])         # the snippet's repeat
        self.assertEqual(self.tl.trigger(layer(4)), [])         # late, out of order
        self.assertEqual(self.tl.duplicates, 2)
        self.assertEqual(self.tl.frames, 1)

    def test_missed_triggers_counted(self):
        self.tl.printer(PRINTING)
        self.tl.trigger(layer(1))
        a = self.tl.trigger(layer(4))
        self.assertEqual(kinds(a), ['frame'])
        self.assertEqual(self.tl.missed, 2)

    def test_late_trigger_warns(self):
        self.tl.printer(PRINTING)
        a = self.tl.trigger(layer(1, age=1500))
        self.assertEqual(kinds(a), ['warn', 'frame'])

    def test_cancel(self):
        self.tl.printer(PRINTING)
        self.tl.trigger(layer(1))
        self.assertEqual(self.tl.printer(PrinterStatus('STOPPED', 7)), [('finish', 'stopped')])
        tl = Timelapse('auto', keep_cancelled=False, clock=self.clock)
        tl.printer(PRINTING)
        tl.trigger(layer(1))
        self.assertEqual(tl.printer(PrinterStatus('STOPPED', 7)), [('discard', 'print cancelled')])

    def test_no_frames_discarded(self):
        self.tl.printer(PRINTING)
        self.assertEqual(self.tl.printer(PrinterStatus('FINISHED', 7)), [('discard', 'no frames')])

    def test_trigger_before_prusalink(self):
        a = self.tl.trigger(layer(1))
        self.assertEqual(kinds(a), ['start', 'frame'])
        self.assertIsNone(self.tl.job_id)
        self.assertEqual(self.tl.printer(PRINTING), [('rename', 'Benchy.bgcode')])
        self.assertEqual(self.tl.job_id, 7)

    def test_new_job_without_end(self):
        self.tl.printer(PRINTING)
        self.tl.trigger(layer(1))
        a = self.tl.printer(PrinterStatus('PRINTING', 8, 'Next.bgcode', z=0.2))
        self.assertEqual(a, [('finish', 'ended'), ('start', 'Next.bgcode')])

    def test_idle_after_job_vanished(self):
        self.tl.printer(PRINTING)
        self.tl.trigger(layer(1))
        self.assertEqual(self.tl.printer(PrinterStatus('IDLE')), [('finish', 'ended')])

    def test_pause_keeps_recording(self):
        self.tl.printer(PRINTING)
        self.tl.trigger(layer(1))
        self.assertEqual(self.tl.printer(PrinterStatus('PAUSED', 7)), [])
        self.assertEqual(self.tl.printer(PrinterStatus('ATTENTION', 7)), [])
        self.assertTrue(self.tl.recording)

    def test_z_fallback_in_auto(self):
        self.tl.printer(PrinterStatus('PRINTING', 7, 'a.gcode', z=0.2))
        out = []
        for z in (0.2, 0.4, 0.4, 0.6, 0.6, 0.8, 0.8):
            out += self.tl.printer(PrinterStatus('PRINTING', 7, 'a.gcode', z=z))
        self.assertIn('warn', kinds(out))
        self.assertTrue(self.tl.poll_active)
        self.assertEqual(kinds(out).count('frame'), 2)    # layers 3 and 4; 1-2 were the grace period
        # a UDP trigger takes over again
        self.tl.trigger(layer(5))
        self.assertFalse(self.tl.poll_active)
        self.assertEqual(self.tl.printer(PrinterStatus('PRINTING', 7, 'a.gcode', z=1.0)), [])
        self.assertEqual(self.tl.printer(PrinterStatus('PRINTING', 7, 'a.gcode', z=1.0)), [])

    def test_udp_mode_never_polls(self):
        tl = Timelapse('udp', clock=self.clock)
        out = []
        for z in (0.2, 0.2, 0.4, 0.4, 0.6, 0.6, 0.8, 0.8, 1.0, 1.0):
            out += tl.printer(PrinterStatus('PRINTING', 7, 'a.gcode', z=z))
        self.assertEqual(kinds(out), ['start'])

    def test_poll_mode_ignores_udp(self):
        tl = Timelapse('poll', clock=self.clock)
        self.assertEqual(tl.trigger(layer(1)), [])
        out = []
        for z in (0.2, 0.2, 0.4, 0.4):
            out += tl.printer(PrinterStatus('PRINTING', 7, 'a.gcode', z=z))
        self.assertEqual(kinds(out), ['start', 'frame', 'frame'])

    def test_stride(self):
        self.tl.printer(PRINTING)
        self.tl.stride = 2
        frames = [a for n in range(1, 9) for a in self.tl.trigger(layer(n)) if a[0] == 'frame']
        self.assertEqual([f[1] for f in frames], [1, 3, 5, 7])

    def test_no_printer_idle_timeout(self):
        tl = Timelapse('udp', have_printer=False, idle_timeout_s=600, clock=self.clock)
        tl.trigger(layer(1))
        self.clock.t += 599
        self.assertEqual(tl.tick(), [])
        self.clock.t += 2
        self.assertEqual(tl.tick(), [('finish', 'timeout')])

    def test_no_printer_end_finishes(self):
        tl = Timelapse('udp', have_printer=False, clock=self.clock)
        tl.trigger(layer(1))
        a = tl.trigger(Trigger('END', None, 0, ''))
        self.assertEqual(kinds(a), ['frame', 'finish'])
        self.assertEqual(tl.trigger(Trigger('END', None, 0, '')), [])    # repeated END: nothing

    def test_bad_layer(self):
        self.assertEqual(kinds(self.tl.trigger(Trigger('LAYER', 'x', 0, ''))), ['warn'])


class Z(unittest.TestCase):
    def test_hop_filtered(self):
        z = ZLayers()
        seq = [0.2, 0.2, 0.4, 0.2, 0.4, 0.4, 0.6, 0.4, 0.6, 0.6]   # hops of 0.2 seen once each
        out = [z.feed(v) for v in seq]
        self.assertEqual([o for o in out if o], [1, 2, 3])

    def test_new_print_resets(self):
        z = ZLayers()
        for v in (20.0, 20.0, 0.2, 0.2):
            r = z.feed(v)
        self.assertEqual(r, 1)
        self.assertIsNone(z.feed(None))


if __name__ == '__main__':
    unittest.main()
