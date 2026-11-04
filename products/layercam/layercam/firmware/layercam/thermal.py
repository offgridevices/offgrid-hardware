"""Heat: what the camera may do at the SoC's temperature, and how hard it runs.

sim/thermal.md: streaming 3 MP at 30 fps in the sealed housing in a 65 C
chamber puts the RV1106 at about 126 C (limit 125) and most parts past
85 C.  So the camera does as little as it can by default (Policy below) and
backs off further as the SoC's own sensor (TSADC, the kernel's thermal zone)
climbs:

    normal    below throttle_c (90 C)
    throttle  >= 90 C: lower frame rate and JPEG quality, no live view,
              IR LED duty capped, CPU held at its lowest speed
    hot       >= 105 C: as throttle, and no Prusa Connect uploads
              (timelapse frames continue: the print only happens once)
    stop      >= 115 C: camera pipeline stopped, no frames at all,
              until the SoC is back under resume_c (95 C)

Each level is left only hysteresis_k below where it was entered, so the
camera does not flap at a threshold.  Pure logic, tested in tests/test_thermal.py.
"""

LEVELS = ('normal', 'throttle', 'hot', 'stop')


class Governor:
    def __init__(self, throttle_c=90.0, no_upload_c=105.0, stop_c=115.0, resume_c=95.0, hysteresis_k=5.0):
        assert throttle_c < no_upload_c < stop_c and resume_c < stop_c
        self.enter = {'throttle': throttle_c, 'hot': no_upload_c, 'stop': stop_c}
        self.leave = {'throttle': throttle_c - hysteresis_k, 'hot': no_upload_c - hysteresis_k, 'stop': resume_c}
        self.level = 'normal'
        self.temp = None

    def feed(self, temp_c):
        """A reading in degrees C (None: unreadable, keep the level)."""
        if temp_c is None:
            return self.level
        self.temp = temp_c
        # up: straight to the highest level reached
        target = 'normal'
        for lv in ('throttle', 'hot', 'stop'):
            if temp_c >= self.enter[lv]:
                target = lv
        if LEVELS.index(target) > LEVELS.index(self.level):
            self.level = target
            return self.level
        # down: one level at a time, each below its own leave threshold
        while self.level != 'normal' and temp_c < self.leave[self.level]:
            self.level = LEVELS[LEVELS.index(self.level) - 1]
            if self.level != 'normal' and temp_c >= self.leave[self.level]:
                break
        return self.level


def limits(level, cfg):
    """What the camera may do at a level: frame rate cap, JPEG quality cap,
    IR LED duty cap (percent), live view, Connect uploads, camera on."""
    t = cfg.section('thermal')
    full = {'fps_cap': 30, 'quality_cap': 95, 'led_cap': 100, 'live': True, 'connect': True, 'camera': True,
            'cpu_boost': True}
    if level == 'normal':
        return full
    out = dict(full, fps_cap=t['throttle_fps'], quality_cap=t['throttle_quality'], led_cap=t['throttle_led_duty'],
               live=False, cpu_boost=False)
    if level in ('hot', 'stop'):
        out['connect'] = False
    if level == 'stop':
        out.update(camera=False, led_cap=0)
    return out


def led_duty(wanted, cap):
    """The IR LED duty actually used: the setting, never above the thermal cap."""
    return max(0, min(100, int(wanted), int(cap)))


class Policy:
    """How the camera runs between shots.

    'standby' stops the ISP and the VI channel (the sensor driver powers the
    SC3336 down when its stream stops); 'stream' keeps it streaming at a
    low frame rate.  During a print a layer trigger must be answered inside
    the slicer snippet's 1.2 s hold, and the ISP's auto exposure and white
    balance need frames to settle after a cold start (some hundreds of ms
    to a second with rkaiq: to measure on the board), so it streams at
    print_fps (10 by default: a fresh frame within 0.3 s).  Idle, a picture
    is needed only every 10-60 s for Connect, so it sleeps and wakes for
    each one, wake_ms ahead.  Live view streams at live_fps, for a limited
    time.  All rates are capped by the thermal level."""

    @staticmethod
    def camera(level_limits, printing, live, cfg):
        """-> ('off' | 'standby' | 'stream', fps)."""
        if not level_limits['camera']:
            return 'off', 0
        cap = level_limits['fps_cap']
        if live and level_limits['live']:
            return 'stream', min(cfg.get('camera', 'live_fps'), cap)
        if printing:
            return 'stream', min(cfg.get('camera', 'print_fps'), cap)
        if cfg.get('camera', 'idle') == 'stream':
            return 'stream', min(2, cap)
        return 'standby', 0
