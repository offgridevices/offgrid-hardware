"""The running camera: ties the parts together.

Threads: the metrics listener (UDP triggers), the PrusaLink poller, the
panel (button, light sensor, IR, 20 times a second), Connect snapshots, the
uploader, the web server, the status LED.  They talk to the main loop
through one queue; only the main loop changes the timelapse.
"""
import logging, os, queue, shutil, sys, threading, time

from . import (HARDWARE, VERSION, capture, config as config_mod, connect as connect_mod, hw, metrics, net,
               prusalink, recording, timelapse, upload, web)

log = logging.getLogger('layercam')


class Service:
    def __init__(self, cfg_path, port=None):
        self.cfg_path = cfg_path
        self.cfg = config_mod.load(cfg_path)
        if config_mod.ensure_fingerprint(self.cfg):
            self.cfg.save()
        for e in self.cfg.errors():
            log.warning('setting: %s', e)
        self.port = port or self.cfg.get('web', 'port')
        self.events = queue.Queue()
        self.storage = self.cfg.get('timelapse', 'storage')
        os.makedirs(self.storage, exist_ok=True)
        self.hw = hw.Sysfs()
        self.camera = capture.from_config(self.cfg)
        self.connect = None
        if self.cfg.get('connect', 'enabled') and self.cfg.get('connect', 'token'):
            self.connect = connect_mod.Connect(self.cfg)
        self.link = None
        if self.cfg.get('prusalink', 'host'):
            p = self.cfg.section('prusalink')
            self.link = prusalink.PrusaLink(p['host'], p['user'], p['password'], p['api_key'])
        t = self.cfg.section('timelapse')
        self.tl = timelapse.Timelapse(t['trigger'], t['dwell_ms'], t['settle_ms'],
                                      keep_cancelled=t['keep_cancelled'], idle_timeout_s=t['idle_timeout_min'] * 60,
                                      have_printer=self.link is not None)
        self.rec = None
        self.printer = None
        self.printer_error = None
        self.last_trigger = None
        self.warning = None
        self.setup_ap = False
        self.uploads = queue.Queue()
        self.upload_state = None
        self.stream_slot = threading.BoundedSemaphore(2)
        self.parked_jpeg = None
        self.daynight = hw.DayNight(self.cfg.get('ir', 'dark_v'), self.cfg.get('ir', 'light_v'),
                                    self.cfg.get('ir', 'hold_s'))
        self.ir = (None, None)
        self.running = True

    # ------------------------------------------------------------ for the web page
    def status(self):
        r = self.rec
        return {'version': VERSION, 'hardware': HARDWARE, 'net': net.interface_info(), 'setup_ap': self.setup_ap,
                'printer': repr(self.printer) if self.printer else None, 'printer_error': self.printer_error,
                'recording': {'name': r.meta['name'], 'frames': r.frames, 'missed': self.tl.missed,
                              'duplicates': self.tl.duplicates, 'stride': self.tl.stride} if r else None,
                'last_trigger': repr(self.last_trigger) if self.last_trigger else None,
                'connect_error': self.connect.last_error if self.connect else 'not set up',
                'upload': self.upload_state, 'ir': {'light': self.daynight.state, 'filter': self.ir[0],
                                                    'leds': self.ir[1]}, 'warning': self.warning}

    def snapshot(self, quality):
        return self.camera.snapshot(quality)

    def connect_test(self):
        if not self.connect:
            return False, 'set connect.token first'
        self.connect.disabled = False
        self.connect.limit.next_ok = 0
        try:
            ok = self.connect.send_snapshot(self.camera.snapshot)
            return ok, self.connect.last_error
        except Exception as e:
            return False, str(e)

    def apply_config(self, new):
        """Save, then start again with the new settings (simplest way to be sure
        every part uses them)."""
        wifi_changed = (new.get('wifi', 'ssid'), new.get('wifi', 'password')) != \
                       (self.cfg.get('wifi', 'ssid'), self.cfg.get('wifi', 'password'))
        new.save(self.cfg_path)
        time.sleep(0.5)          # let the page get its answer
        if wifi_changed and new.get('wifi', 'ssid'):
            net.write_files(new)
            net.switch('sta')
        self.restart()

    def restart(self):
        self.running = False
        self.camera.close()
        os.execv(sys.executable, [sys.executable, '-m', 'layercam'] + sys.argv[1:])

    # ------------------------------------------------------------ threads
    def poll_printer(self):
        every = self.cfg.get('prusalink', 'poll_interval')
        while self.running:
            try:
                st = self.link.snapshot()
                self.printer_error = None
                self.events.put(('printer', st))
            except prusalink.LinkError as e:
                self.printer_error = str(e)
            time.sleep(every)

    def panel(self):
        button = hw.Button()
        n = 0
        while self.running:
            ev = button.feed(self.hw.button_pressed(), time.monotonic())
            if ev:
                self.events.put(('button', ev))
            if n % 20 == 0:
                self.update_ir()
            n += 1
            time.sleep(0.05)

    def update_ir(self):
        v = self.hw.light_volts()
        if v is not None:
            self.daynight.feed(v, time.monotonic())
        printing = bool(self.printer and self.printer.printing) or self.rec is not None
        plan = hw.ir_plan(self.cfg.get('ir', 'mode'), self.daynight.state, printing)
        if plan[0] != self.ir[0]:
            self.hw.ircut(plan[0])
            try:
                self.camera.night(plan[0] == 'night')
            except capture.CameraError as e:
                log.warning('night mode: %s', e)
        if plan[1] != self.ir[1]:
            self.hw.ir_leds(self.cfg.get('ir', 'led_duty') if plan[1] else 0)
        self.ir = plan

    def connect_loop(self):
        res = None
        info_due = 0.0
        while self.running:
            now = time.monotonic()
            try:
                if info_due is not None and now >= info_due:
                    res = res or self.camera.resolution()
                    self.connect.send_info(connect_mod.camera_info(self.cfg, res, net.interface_info()))
                    info_due = None
                parked, self.parked_jpeg = self.parked_jpeg, None
                if parked is not None:
                    # a frame from a parked head beats a timed one; it waits for the rate limit
                    if not self.connect.limit.ready():
                        time.sleep(self.connect.limit.wait_s())
                    self.connect.send_snapshot(lambda q: parked if q == self.connect.quality
                                               else self.camera.snapshot(q))
                elif self.connect.limit.ready():
                    self.connect.send_snapshot(self.camera.snapshot)
            except connect_mod.ConnectError as e:
                log.warning('connect: %s', e)
                if not e.fatal:
                    info_due = time.monotonic() + 300
            except (capture.CameraError, OSError) as e:
                self.connect.last_error = str(e)
                if info_due is not None:
                    info_due = time.monotonic() + 60
            time.sleep(1)

    def uploader(self):
        target = upload.from_config(self.cfg)
        while self.running:
            folder = self.uploads.get()
            try:
                body = recording.body_for(folder)
                if body is None:
                    continue
                if target is None:
                    self.upload_state = 'kept on the camera: %s' % body.name
                    continue
                self.upload_state = 'uploading %s' % body.name
                where = upload.send_with_retry(target, body, stop=lambda: not self.running)
                recording.mark(folder, 'uploaded')
                self.upload_state = 'uploaded %s to %s' % (body.name, where)
                recording.prune(self.storage, self.cfg.get('upload', 'keep_local'))
            except Exception as e:
                self.upload_state = 'upload failed: %s' % e
                log.error('upload %s: %s', folder, e)

    # ------------------------------------------------------------ timelapse actions
    def new_recording(self, name):
        rid = time.strftime('rec-%Y%m%d-%H%M%S')
        folder = os.path.join(self.storage, rid)
        nm = prusalink.video_name(name, time.localtime())
        t = self.cfg.section('timelapse')
        try:
            return recording.H264Recording(self.camera, folder, nm, self.tl.job_id, t['fps'], t['quality'])
        except capture.NotSupported:
            return recording.JpegRecording(self.camera, folder, nm, self.tl.job_id, t['fps'], t['quality'])

    def act(self, actions):
        for a in actions:
            kind = a[0]
            if kind == 'start':
                self.ensure_space()
                self.rec = self.new_recording(a[1])
                self.warning = None
                log.info('timelapse started: %s', self.rec.meta['name'])
            elif kind == 'rename' and self.rec:
                self.rec.rename(prusalink.video_name(a[1], time.localtime(self.rec.meta['started'])))
            elif kind == 'frame' and self.rec:
                if a[2]:
                    time.sleep(a[2])
                try:
                    self.rec.add_frame()
                    if self.connect and self.tl.udp_seen:
                        self.parked_jpeg = self.camera.snapshot(self.connect.quality)
                except (capture.CameraError, OSError) as e:
                    self.warning = 'frame %s lost: %s' % (a[1], e)
                    log.error(self.warning)
                self.check_space()
            elif kind in ('finish', 'discard') and self.rec:
                rec, self.rec = self.rec, None
                rec.finish()
                if kind == 'finish':
                    log.info('timelapse finished (%s): %d frames', a[1], rec.frames)
                    self.uploads.put(rec.folder)
                else:
                    log.info('timelapse discarded: %s', a[1])
                    recording.mark(rec.folder, 'uploaded')     # nothing to send; pruned like a sent one
                    recording.prune(self.storage, self.cfg.get('upload', 'keep_local'))
                self.tl.stride = 1
            elif kind == 'warn':
                self.warning = a[1]
                log.warning(a[1])

    def check_space(self):
        free = upload.free_bytes(self.storage)
        low = self.cfg.get('timelapse', 'min_free_mb') * 1024 * 1024
        if free < low and self.tl.stride < 64:
            self.tl.stride *= 2
            if isinstance(self.rec, recording.JpegRecording):
                self.rec.thin()
            self.warning = 'storage low: keeping every %d. layer from now on' % self.tl.stride
            log.warning(self.warning)

    def ensure_space(self):
        """Before a new timelapse: delete the oldest sent videos, then the oldest
        unsent ones, until there is room for a long print."""
        need = 4 * self.cfg.get('timelapse', 'min_free_mb') * 1024 * 1024
        for state in ('uploaded', 'done'):
            for folder, m in sorted(recording.list_recordings(self.storage), key=lambda fm: fm[1].get('started', 0)):
                if upload.free_bytes(self.storage) >= need:
                    return
                if m.get('state') == state:
                    log.warning('deleting %s (%s) to make room', m['name'], state)
                    shutil.rmtree(folder, ignore_errors=True)

    def on_button(self, ev):
        if ev == 'short' and self.connect:
            self.connect.limit.next_ok = 0
            self.parked_jpeg = None
        elif ev == 'long':
            log.warning('button held: forgetting Wi-Fi, starting the setup access point')
            self.cfg.set('wifi', 'ssid', '')
            self.cfg.set('wifi', 'password', '')
            self.cfg.save()
            self.start_ap()

    def start_ap(self):
        net.write_files(self.cfg)
        self.setup_ap = net.switch('ap')
        self.ap_until = time.monotonic() + 1800

    # ------------------------------------------------------------ main
    def recover(self):
        """Recordings left by a reboot mid-print are finished and sent as they are."""
        for folder, m in recording.list_recordings(self.storage):
            if m.get('state') == 'recording':
                recording.mark(folder, 'done')
                m['state'] = 'done'
            if m.get('state') == 'done':
                self.uploads.put(folder)

    def run(self):
        blink = hw.LedBlinker(self.hw)
        blink.start()
        if not self.cfg.get('wifi', 'ssid'):
            self.start_ap()
        web.serve(self, self.port)
        self.recover()
        threading.Thread(target=self.uploader, name='upload', daemon=True).start()
        threading.Thread(target=self.panel, name='panel', daemon=True).start()
        if self.link:
            threading.Thread(target=self.poll_printer, name='prusalink', daemon=True).start()
        if self.connect:
            threading.Thread(target=self.connect_loop, name='connect', daemon=True).start()
        if self.cfg.get('timelapse', 'enabled') and self.cfg.get('timelapse', 'trigger') != 'poll':
            metrics.Listener(self.cfg.get('timelapse', 'udp_port'),
                             lambda t: self.events.put(('trigger', t))).start()
        while self.running:
            try:
                kind, ev = self.events.get(timeout=1.0)
            except queue.Empty:
                kind, ev = None, None
            if kind == 'printer':
                self.printer = ev
                if self.cfg.get('timelapse', 'enabled'):
                    self.act(self.tl.printer(ev))
            elif kind == 'trigger':
                self.last_trigger = ev
                if self.cfg.get('timelapse', 'enabled'):
                    self.act(self.tl.trigger(ev))
            elif kind == 'button':
                self.on_button(ev)
            self.act(self.tl.tick())
            if self.setup_ap and time.monotonic() > getattr(self, 'ap_until', 0) and self.cfg.get('wifi', 'ssid'):
                self.setup_ap = not net.switch('sta')
            blink.state = hw.led_state(self.setup_ap, self.setup_ap or net.link_up(),
                                       bool(self.warning or self.printer_error or
                                            (self.connect and self.connect.disabled)), self.rec is not None)
