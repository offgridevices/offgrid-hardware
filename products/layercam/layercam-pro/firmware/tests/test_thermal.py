"""Heat: the governor's levels and hysteresis, what each level allows, the
IR LED duty cap and ramp, the camera power policy, and the service obeying
them (live view refused, Connect skipped, frames lost only at 'stop')."""
import os, tempfile, unittest
from unittest import mock

from layercam import capture, config, hw, service, thermal


class Governor(unittest.TestCase):
    def test_levels_up_and_down(self):
        g = thermal.Governor(90, 105, 115, 95, 5)
        seq = [(60, 'normal'), (89.9, 'normal'), (90, 'throttle'), (104, 'throttle'), (105, 'hot'),
               (114, 'hot'), (115, 'stop'), (110, 'stop'), (95.5, 'stop'),     # stop holds until under 95
               (94.9, 'throttle'),                                            # 94.9 is still over 90
               (86, 'throttle'), (84.9, 'normal')]
        for t, want in seq:
            self.assertEqual(g.feed(t), want, t)

    def test_hysteresis_no_flapping(self):
        g = thermal.Governor(90, 105, 115, 95, 5)
        g.feed(91)
        for t in (89, 90.5, 88, 89.9, 86):
            self.assertEqual(g.feed(t), 'throttle')
        g.feed(106)
        for t in (104, 102, 100.5):
            self.assertEqual(g.feed(t), 'hot')
        self.assertEqual(g.feed(99.9), 'throttle')

    def test_jump_straight_to_stop_and_unreadable(self):
        g = thermal.Governor()
        self.assertEqual(g.feed(120), 'stop')
        self.assertEqual(g.feed(None), 'stop')           # a failed read changes nothing
        self.assertEqual(g.feed(30), 'normal')           # cold: all the way down at once
        self.assertEqual(g.temp, 30)

    def test_bad_thresholds(self):
        with self.assertRaises(AssertionError):
            thermal.Governor(100, 95, 115)
        with self.assertRaises(AssertionError):
            thermal.Governor(87, 105, 110, warm_c=90)            # warm must come before throttle

    def test_warm_level(self):
        # config.py's defaults: warm 84, throttle 87 (sim/thermal.md, Firmware rules 2 and 3)
        g = thermal.Governor(87, 105, 110, 95, 5, warm_c=84)
        seq = [(83.9, 'normal'), (84, 'warm'), (86.9, 'warm'), (82.1, 'warm'),   # warm left only under 82
               (81.9, 'normal'), (88, 'throttle'), (82.5, 'throttle'),          # throttle left only under 82
               (81.9, 'normal'), (85, 'warm'), (111, 'stop'), (94, 'throttle')]
        for t, want in seq:
            self.assertEqual(g.feed(t), want, t)

    def test_defaults_are_the_configs(self):
        th = config.Config().section('thermal')
        self.assertEqual((th['warm_c'], th['throttle_c'], th['stop_c']), (84.0, 87.0, 110.0))


class Limits(unittest.TestCase):
    def setUp(self):
        self.cfg = config.Config()

    def test_each_level(self):
        n, w, t, h, s = (thermal.limits(lv, self.cfg) for lv in thermal.LEVELS)
        self.assertTrue(n['live'] and n['connect'] and n['camera'] and n['cpu_boost'])
        self.assertEqual((n['led_cap'], n['fps_cap'], n['snap_min_s'], n['flash_settle_ms']), (100, 30, 0, None))
        # warm: only the pictures spaced out and the flash shortened
        self.assertEqual(dict(w, snap_min_s=0, flash_settle_ms=None), n)
        self.assertEqual((w['snap_min_s'], w['flash_settle_ms']), (30, 200))
        self.assertEqual((t['snap_min_s'], h['snap_min_s']), (30, 30))                # and every hotter level
        self.assertEqual((t['live'], t['connect'], t['camera'], t['cpu_boost']), (False, True, True, False))
        self.assertEqual((t['fps_cap'], t['quality_cap'], t['led_cap']), (5, 70, 50))
        self.assertEqual((h['live'], h['connect'], h['camera']), (False, False, True))     # frames, no uploads
        self.assertEqual((s['camera'], s['connect'], s['led_cap']), (False, False, 0))

    def test_led_duty_limit(self):
        self.assertEqual(thermal.led_duty(100, 100), 100)
        self.assertEqual(thermal.led_duty(100, 50), 50)
        self.assertEqual(thermal.led_duty(30, 50), 30)
        self.assertEqual(thermal.led_duty(80, 0), 0)
        self.assertEqual(thermal.led_duty(150, 100), 100)
        self.assertEqual(thermal.led_duty(-5, 100), 0)

    def test_policy(self):
        P, c = thermal.Policy, self.cfg
        lim = thermal.limits
        self.assertEqual(P.camera(lim('normal', c), False, False, c), ('standby', 0))
        self.assertEqual(P.camera(lim('normal', c), True, False, c), ('stream', 10))
        self.assertEqual(P.camera(lim('normal', c), False, True, c), ('stream', 10))
        self.assertEqual(P.camera(lim('throttle', c), True, False, c), ('stream', 5))
        self.assertEqual(P.camera(lim('throttle', c), False, True, c), ('standby', 0))     # no live view when hot
        self.assertEqual(P.camera(lim('stop', c), True, True, c), ('off', 0))
        c.set('camera', 'idle', 'stream')
        self.assertEqual(P.camera(lim('normal', c), False, False, c), ('stream', 2))


class Ramp(unittest.TestCase):
    def test_ramp_steps_and_cap(self):
        h = hw.Sysfs(tempfile.mkdtemp())
        seen = []
        with mock.patch.object(h, 'ir_leds', side_effect=seen.append), mock.patch('layercam.hw.time.sleep') as sl:
            h.ir_ramp(0, 50, 100, step_ms=20)
        self.assertEqual(seen, [10, 20, 30, 40, 50])
        self.assertEqual(sl.call_count, 4)
        seen.clear()
        with mock.patch.object(h, 'ir_leds', side_effect=seen.append), mock.patch('layercam.hw.time.sleep'):
            h.ir_ramp(50, 0, 0)
        self.assertEqual(seen, [0])

    def test_temperature_and_cpu(self):
        root = tempfile.mkdtemp()
        os.makedirs(root + '/sys/class/thermal/thermal_zone0')
        with open(root + '/sys/class/thermal/thermal_zone0/temp', 'w') as f:
            f.write('91250\n')
        cpu = root + '/sys/devices/system/cpu/cpu0/cpufreq'
        os.makedirs(cpu)
        with open(cpu + '/scaling_available_frequencies', 'w') as f:
            f.write('408000 600000 816000 1104000 1200000 \n')
        h = hw.Sysfs(root)
        self.assertEqual(h.temperature('/sys/class/thermal/thermal_zone0/temp'), 91.25)
        self.assertIsNone(h.temperature('/nope'))
        h.cpu_speed(False)
        with open(cpu + '/scaling_max_freq') as f:
            self.assertEqual(f.read(), '408000')
        h.cpu_speed(True)
        with open(cpu + '/scaling_max_freq') as f:
            self.assertEqual(f.read(), '1200000')


class RecordingCamera(capture.FakeCamera):
    """A fake that sleeps and wakes, and remembers how."""

    def __init__(self):
        capture.FakeCamera.__init__(self)
        self.state, self.calls = 0, []

    @property
    def awake(self):
        return bool(self.state)

    def wake(self, fps):
        self.state = fps
        self.calls.append(('wake', fps))

    def sleep(self):
        self.state = 0
        self.calls.append(('sleep',))

    def snapshot(self, quality=80):
        assert self.state, 'picture while asleep'
        self.calls.append(('snap', quality))
        return capture.FakeCamera.snapshot(self, quality)


class ServiceUnderHeat(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        cfg = config.Config({('camera', 'backend'): 'fake', ('timelapse', 'storage'): os.path.join(d, 'tl'),
                             ('camera', 'wake_ms'): 0, ('ir', 'flash_settle_ms'): 0, ('ir', 'ramp_ms'): 0},
                            path=os.path.join(d, 'c.ini'))
        cfg.save()
        self.svc = service.Service(cfg.path, port=0, hw_root=os.path.join(d, 'root'))
        self.cam = self.svc.camera = RecordingCamera()
        self.leds = []
        self.svc.hw.ir_leds = self.leds.append

    def test_standby_between_pictures(self):
        self.svc.apply_camera_state()
        self.assertFalse(self.cam.awake)
        self.svc.snapshot(80)
        self.assertEqual(self.cam.calls[-3:], [('wake', 10), ('snap', 80), ('sleep',)])

    def test_live_view_time_limited_and_refused_hot(self):
        ok, _ = self.svc.start_live(9999)
        self.assertTrue(ok)
        self.assertTrue(self.cam.awake)
        self.assertLessEqual(self.svc.status()['live_s'], 120)
        self.svc.update_thermal(91)
        self.assertFalse(self.svc.live_active())                 # stopped when it got hot
        ok, err = self.svc.start_live(60)
        self.assertFalse(ok)
        self.assertIn('too hot', err)
        self.svc.update_thermal(70)
        self.assertTrue(self.svc.start_live(60)[0])

    def test_quality_capped_and_connect_skipped(self):
        self.svc.update_thermal(95)
        self.svc.snapshot(85)
        self.assertEqual([c for c in self.cam.calls if c[0] == 'snap'][-1], ('snap', 70))
        self.svc.update_thermal(106)
        self.assertFalse(self.svc.lim['connect'])
        self.svc.connect = object()                              # set up, but must not be used
        ok, err = self.svc.connect_test()
        self.assertFalse(ok)
        self.assertIn('hot', err)

    def test_stop_loses_frames_resumes_below_95(self):
        self.svc.act([('start', 'a.gcode')])
        self.assertIsNotNone(self.svc.rec)
        self.svc.act([('frame', 1, 0)])
        self.svc.update_thermal(116)
        self.assertFalse(self.cam.awake)                          # pipeline stopped
        self.svc.act([('frame', 2, 0), ('frame', 3, 0)])
        self.assertEqual((self.svc.rec.frames, self.svc.frames_lost_hot), (1, 2))
        self.assertEqual(self.svc.status()['thermal']['level'], 'stop')
        self.svc.update_thermal(96)
        self.assertFalse(self.svc.lim['camera'])
        self.svc.update_thermal(94)
        self.assertTrue(self.cam.awake)                           # printing: streaming again (throttled)
        self.assertEqual(self.cam.state, 5)
        self.svc.act([('frame', 4, 0)])
        self.assertEqual(self.svc.rec.frames, 2)

    def test_night_flash_only_around_the_picture(self):
        self.svc.ir = ('night', True)
        self.svc.snapshot(80)
        self.assertEqual(self.leds[0], 100)                       # ramp_ms 0: one step up
        self.assertEqual(self.leds[-1], 0)                        # and off again
        self.leds.clear()
        self.svc.update_thermal(92)                               # throttled: duty capped at 50 %
        self.svc.snapshot(80)
        self.assertEqual(max(self.leds), 50)
        self.assertEqual(self.leds[-1], 0)
        self.leds.clear()
        self.svc.update_thermal(120)
        with self.assertRaises(capture.CameraError):
            self.svc.snapshot(80)
        self.assertEqual(self.leds, [])

    def test_warm_spaces_connect_pictures_and_shortens_the_flash(self):
        self.svc.update_thermal(85)
        self.assertEqual(self.svc.gov.level, 'warm')
        self.assertTrue(self.svc.lim['live'] and self.svc.lim['connect'])
        self.assertFalse(self.svc.too_soon_when_warm(100.0))     # no picture yet
        self.svc.last_connect_shot = 100.0
        self.assertTrue(self.svc.too_soon_when_warm(129.9))
        self.assertFalse(self.svc.too_soon_when_warm(130.0))
        self.svc.update_thermal(70)
        self.assertFalse(self.svc.too_soon_when_warm(101.0))     # cool: Connect's own rate only
        # the flash: 500 ms set, 200 ms when warm
        self.svc.cfg.set('ir', 'flash_settle_ms', 500)
        self.svc.ir = ('night', True)
        slept = []
        with mock.patch.object(service.time, 'sleep', slept.append):
            self.svc.snapshot(80)
            self.svc.update_thermal(85)
            self.svc.snapshot(80)
        self.assertGreater(slept[0], 0.4)
        self.assertLessEqual(slept[-1], 0.2)
        self.assertEqual(hw.led_state(False, True, None, False, 'warm'), 'ok')    # warm is not a fault

    def test_ircut_pulsed_only_on_change(self):
        pulses = []
        self.svc.hw.ircut = pulses.append
        self.svc.hw.light_volts = lambda: 0.5
        for _ in range(5):
            self.svc.update_ir()
        self.assertEqual(pulses, ['day'])

    def test_hot_led_pattern(self):
        self.assertEqual(hw.led_state(False, True, False, True, 'throttle'), 'hot')
        self.assertEqual(hw.led_state(True, True, False, True, 'stop'), 'setup')


if __name__ == '__main__':
    unittest.main()
