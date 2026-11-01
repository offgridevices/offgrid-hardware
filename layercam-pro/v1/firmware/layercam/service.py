"""The running camera: ties the parts together.

Threads: the metrics listener (UDP triggers), the PrusaLink poller, the
panel (light sensor, IR and temperature once a second, the BOOT pad once a
minute), Wi-Fi (join the network or open the setup access point:
net.WifiSupervisor), Connect snapshots, the uploader, the web server, the
status LED.  They talk to the main loop through one queue; only the main
loop changes the timelapse.

There is no button.  Wi-Fi is set up from the setup access point or the USB
console (setupcli.py), forgotten with the power-cycle gesture (gesture.py:
it leaves a request file that run() acts on), and the software is updated
from the page or the console (update.py).  SIGHUP (sent by the USB console
after a change) restarts the service with the new settings.

Heat sets how it runs (sim/thermal.md; thermal.py): the sensor sleeps
between pictures unless a print is on, the IR LEDs light only around a
night picture, the CPU stays at its lowest speed except while uploading,
live view is asked for and ends by itself, and the SoC's temperature
throttles, then stops, all of it.
"""
import logging, os, queue, shutil, signal, sys, threading, time
from contextlib import contextmanager

from . import (HARDWARE, VERSION, capture, config as config_mod, connect as connect_mod, gesture, hw, metrics,
               net, prusalink, recording, thermal, timelapse, update, upload, web)

log = logging.getLogger('layercam')

# the folder this copy of the software runs from: /usr/share/layercam (the
# factory copy) or /userdata/layercam/app/slots/<version> (an update)
RUNNING_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXIT_RESELECT = 3            # S99layercam: start whichever version update.select() picks


class Service:
    def __init__(self, cfg_path, port=None, hw_root=''):
        self.cfg_path = cfg_path
        self.cfg_dir = os.path.dirname(os.path.abspath(cfg_path))
        # lenient: a typo or a setting from another version must not stop the camera
        self.cfg = config_mod.load(cfg_path, strict=False)
        if config_mod.ensure_fingerprint(self.cfg):
            self.cfg.save()
        self.root = hw_root
        self.run_dir = hw_root + net.RUN_DIR
        self.net_script = hw_root + '/usr/bin/layercam-net'
        self.apps = update.AppStore(os.path.join(self.cfg_dir, 'app'), update.FACTORY_DIR)
        self.updating = False
        self.boot_pad = None
        self.wifi_sup = None
        self.wifi_up = False
        self.reload_requested = False
        self.good_after_s = update.GOOD_AFTER_S
        self.started = time.monotonic()
        for e in self.cfg.errors():
            log.warning('setting: %s', e)
        self.port = port or self.cfg.get('web', 'port')
        self.events = queue.Queue()
        self.storage = self.cfg.get('timelapse', 'storage')
        os.makedirs(self.storage, exist_ok=True)
        self.hw = hw.Sysfs(hw_root)
        self.camera = capture.from_config(self.cfg)
        self.cam_lock = threading.RLock()       # wake, light, take, sleep: one picture at a time
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
        th = self.cfg.section('thermal')
        self.gov = thermal.Governor(th['throttle_c'], th['no_upload_c'], th['stop_c'], th['resume_c'],
                                    th['hysteresis_k'])
        self.lim = thermal.limits('normal', self.cfg)
        self.rec = None
        self.printer = None
        self.printer_error = None
        self.last_trigger = None
        self.warning = None
        self.frames_lost_hot = 0
        self.setup_ap = False
        self.uploads = queue.Queue()
        self.upload_state = None
        self.stream_slot = threading.BoundedSemaphore(2)
        self.live_until = 0.0
        self.parked_jpeg = None
        self.daynight = hw.DayNight(self.cfg.get('ir', 'dark_v'), self.cfg.get('ir', 'light_v'),
                                    self.cfg.get('ir', 'hold_s'))
        self.ir = (None, None)
        self.cam_state = None
        self.running = True

    # ------------------------------------------------------------ state
    def printing(self):
        return self.rec is not None or bool(self.printer and self.printer.printing)

    def live_active(self):
        return time.monotonic() < self.live_until and self.lim['live']

    def apply_camera_state(self):
        """Sleep or stream the sensor as thermal.Policy says."""
        state = thermal.Policy.camera(self.lim, self.printing(), self.live_active(), self.cfg)
        with self.cam_lock:
            try:
                if state[0] == 'stream':
                    self.camera.wake(state[1])
                else:
                    self.camera.sleep()
                if state != self.cam_state:
                    log.info('camera: %s %s', *state)
                self.cam_state = state
            except capture.CameraError as e:
                log.warning('camera %s: %s', state[0], e)
        if not self.live_active() and self.live_until:
            self.live_until = 0.0
            self.lights(False)

    def lights(self, on):
        """IR LEDs for a night picture or live view, ramped, duty capped by heat."""
        duty = thermal.led_duty(self.cfg.get('ir', 'led_duty'), self.lim['led_cap']) if on else 0
        now = getattr(self, 'led_now', 0)
        if duty != now:
            self.hw.ir_ramp(now, duty, self.cfg.get('ir', 'ramp_ms'))
            self.led_now = duty

    def night_flash(self):
        return self.ir[0] == 'night' and bool(self.ir[1]) and self.lim['led_cap'] > 0

    @contextmanager
    def picture(self, settle_s=0.0):
        """Everything a picture needs: the sensor awake (with time for the
        exposure if it was asleep), the IR LEDs at night, then back to
        what the policy wants."""
        if not self.lim['camera']:
            raise capture.CameraError('camera stopped: SoC at %.0f C' % (self.gov.temp or 0))
        with self.cam_lock:
            t0 = time.monotonic()
            woke = not self.camera.awake
            if woke:
                self.camera.wake(min(self.cfg.get('camera', 'print_fps'), self.lim['fps_cap']))
            wait = max(settle_s, self.cfg.get('camera', 'wake_ms') / 1000.0 if woke else 0)
            flash = self.night_flash()
            if flash:
                self.lights(True)
                wait = max(wait, self.cfg.get('ir', 'flash_settle_ms') / 1000.0)
            left = wait - (time.monotonic() - t0)
            if left > 0:
                time.sleep(left)
            try:
                yield
            finally:
                if flash and not self.live_active():
                    self.lights(False)
                if woke:
                    self.apply_camera_state()

    def take_jpeg(self, quality):
        """One JPEG for Connect or the page, quality capped by heat."""
        with self.picture():
            return self.camera.snapshot(min(quality, self.lim['quality_cap']))

    # ------------------------------------------------------------ for the web page
    def status(self):
        r = self.rec
        sup = self.wifi_sup
        app = self.apps.state()
        return {'version': VERSION, 'hardware': HARDWARE, 'net': net.interface_info(), 'setup_ap': self.setup_ap,
                'wifi': {'network': self.cfg.get('wifi', 'ssid'), 'connected': self.wifi_up,
                         'access_point': self.setup_ap and (sup.reason if sup else 'setup')},
                'app': {'running': VERSION, 'trial': bool(app['pending']), 'last': app['last']},
                'boot_pad': self.boot_pad,
                'ssh': os.path.exists(os.path.join(self.cfg_dir, 'ssh', 'enabled')),
                'printer': repr(self.printer) if self.printer else None, 'printer_error': self.printer_error,
                'recording': {'name': r.meta['name'], 'frames': r.frames, 'missed': self.tl.missed,
                              'duplicates': self.tl.duplicates, 'stride': self.tl.stride,
                              'lost_to_heat': self.frames_lost_hot} if r else None,
                'last_trigger': repr(self.last_trigger) if self.last_trigger else None,
                'connect_error': self.connect.last_error if self.connect else 'not set up',
                'upload': self.upload_state, 'ir': {'light': self.daynight.state, 'filter': self.ir[0],
                                                    'leds_at_night': self.ir[1]},
                'thermal': {'soc_c': self.gov.temp, 'level': self.gov.level},
                'camera': self.cam_state, 'live_s': max(0, int(self.live_until - time.monotonic())),
                'warning': self.warning}

    def snapshot(self, quality):
        return self.take_jpeg(quality)

    def start_live(self, seconds):
        """Live view on request, for a while; refused when the SoC is hot."""
        if not self.lim['live']:
            return False, 'too hot for live view (SoC %.0f C, %s)' % (self.gov.temp or 0, self.gov.level)
        self.live_until = time.monotonic() + max(5, min(int(seconds), self.cfg.get('camera', 'live_max_s')))
        self.apply_camera_state()
        if self.night_flash():
            self.lights(True)
        return True, None

    def stop_live(self):
        self.live_until = 0.0
        self.apply_camera_state()

    def connect_test(self):
        if not self.connect:
            return False, 'set connect.token first'
        if not self.lim['connect']:
            return False, 'no Connect uploads while the SoC is this hot (%s)' % self.gov.level
        self.connect.disabled = False
        self.connect.limit.hurry()
        if not self.connect.limit.ready():
            return False, 'wait %d s: Connect takes at most 6 snapshots a minute' % self.connect.limit.wait_s()
        try:
            ok = self.connect.send_snapshot(self.take_jpeg)
            return ok, self.connect.last_error
        except Exception as e:
            return False, str(e)

    def apply_config(self, new):
        """Save, then start again with the new settings (simplest way to be sure
        every part uses them)."""
        if any(new.get('wifi', k) != self.cfg.get('wifi', k) for k in ('ssid', 'password')):
            net.mark_new_network(self.run_dir)      # it may be mistyped: the access point comes back sooner
        new.save(self.cfg_path)
        time.sleep(0.5)          # let the page get its answer
        self.restart()           # the new service joins the new network (wifi_loop)

    def install_update(self, path, allow_downgrade=False):
        """A package from the page: checked, unpacked, started on trial (update.py)."""
        self.updating = True
        try:
            v = self.apps.install(path, update.load_keys(self.root + update.KEYS_FILE), VERSION,
                                  update.rootfs_version(self.root + update.ROOTFS_VERSION_FILE), allow_downgrade)
            log.warning('update %s installed, restarting into it', v)
            return True, 'version %s installed: the camera restarts into it now' % v
        except (update.UpdateError, OSError) as e:
            log.warning('update refused: %s', e)
            return False, str(e)
        finally:
            self.updating = False

    def on_camera_layout(self):
        """Running from the factory copy or an installed slot (not a checkout on a PC)."""
        here = os.path.realpath(RUNNING_DIR)
        return here == os.path.realpath(self.apps.factory) or here.startswith(os.path.realpath(self.apps.root) + os.sep)

    def restart(self, reselect=False):
        """Start again with the settings in the file.  reselect: exit instead,
        so S99layercam starts the version update.select() picks."""
        self.running = False
        self.lights(False)
        self.camera.close()
        if reselect:
            log.warning('exiting for the init script to start the selected version')
            logging.shutdown()
            os._exit(EXIT_RESELECT)
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
        n = 0
        while self.running:
            self.update_thermal()
            self.update_ir()
            self.apply_camera_state()
            if n % 60 == 0:
                self.check_boot_pad()
            n += 1
            time.sleep(1.0)

    def check_boot_pad(self):
        v = self.hw.boot_pad_volts()
        problem = hw.boot_pad_problem(v)
        if problem and problem != self.boot_pad:
            log.warning(problem)
        self.boot_pad = problem

    # ------------------------------------------------------------ Wi-Fi
    def take_wifi_reset(self):
        """The power-cycle gesture (or layercam-setup reset-wifi) asked to forget the network."""
        store = gesture.FileStore(self.cfg_dir)
        if not store.reset_requested():
            return False
        log.warning('Wi-Fi reset requested: forgetting the network, opening the setup access point')
        self.forget_wifi()
        store.clear_request()            # after the save: a power cut in between only repeats it
        return True

    def forget_wifi(self):
        # the access point's own passphrase too, so the one from the SoC serial
        # (label, USB console, tools/layercam-ap.py) always works after a reset
        for k in ('ssid', 'password', 'ap_password'):
            self.cfg.set('wifi', k, '')
        self.cfg.save()

    def _net_files(self):
        out = {}
        for name in ('wpa_supplicant.conf', 'hostapd.conf', 'dnsmasq.conf', 'net.env'):
            try:
                with open(os.path.join(self.run_dir, name)) as f:
                    out[name] = f.read()
            except OSError:
                out[name] = None
        return out

    def _write_net(self, mode, keep):
        """Write the files; True when the radio is already in this mode with
        the same files (keep: the first switch after a restart for other
        settings, which must not drop the network or a phone on the page)."""
        before = self._net_files()
        net.write_files(self.cfg, self.run_dir)
        if not keep or before != self._net_files():
            return False
        ip = net.interface_info().get('wifi_ipv4')
        return ip == net.AP_ADDRESS if mode == 'ap' else bool(ip) and ip != net.AP_ADDRESS

    def start_sta(self, keep=False):
        return self._write_net('sta', keep) or net.switch('sta', self.net_script)

    def wifi_loop(self):
        """Keeps the Wi-Fi in the mode the supervisor asks for."""
        sup = self.wifi_sup
        applied, failed_at = None, None
        while self.running:
            now = time.monotonic()
            clients = net.ap_clients() if applied == 'ap' else 0
            self.wifi_up = applied == 'sta' and net.link_up()
            want = sup.feed(now, self.wifi_up, clients)
            if want != applied and (failed_at is None or now - failed_at >= 10):
                keep = applied is None
                if (self.start_ap(keep) if want == 'ap' else self.start_sta(keep)):
                    if want == 'sta' and applied == 'ap':
                        log.info('setup access point closed: trying %s', self.cfg.get('wifi', 'ssid'))
                    applied, failed_at = want, None
                else:
                    if failed_at is None:
                        log.warning('Wi-Fi: could not switch to %s (layercam-net)', want)
                    failed_at = now
            self.setup_ap = applied == 'ap'
            time.sleep(1.0)

    def update_thermal(self, temp=None):
        before = self.gov.level
        level = self.gov.feed(temp if temp is not None else self.hw.temperature(self.cfg.get('thermal', 'zone')))
        if level == before:
            return
        self.lim = thermal.limits(level, self.cfg)
        msg = 'SoC %.0f C: %s' % (self.gov.temp, level)
        (log.info if level == 'normal' else log.warning)(msg)
        self.warning = None if level == 'normal' else msg
        if not self.lim['live']:
            self.live_until = 0.0
        self.hw.cpu_speed(False)
        if getattr(self, 'led_now', 0) > self.lim['led_cap']:
            self.lights(True)                    # down to the new cap (0 when stopped)
        self.apply_camera_state()

    def update_ir(self):
        """The IR-cut coil is pulsed only when day/night changes."""
        v = self.hw.light_volts()
        if v is not None:
            self.daynight.feed(v, time.monotonic())
        plan = hw.ir_plan(self.cfg.get('ir', 'mode'), self.daynight.state, self.printing())
        if plan[0] != self.ir[0]:
            self.hw.ircut(plan[0])
            try:
                with self.cam_lock:
                    self.camera.night(plan[0] == 'night')
            except capture.CameraError as e:
                log.warning('night mode: %s', e)
        self.ir = plan

    def connect_loop(self):
        res = None
        info_due = 0.0
        while self.running:
            now = time.monotonic()
            try:
                if info_due is not None and now >= info_due:
                    res = res or self.camera_resolution()
                    self.connect.send_info(connect_mod.camera_info(self.cfg, res, net.interface_info()))
                    info_due = None
                parked, self.parked_jpeg = self.parked_jpeg, None
                if not self.lim['connect']:
                    pass                          # too hot: frames for the timelapse only
                elif parked is not None:
                    # a frame from a parked head beats a timed one; it waits for the rate limit
                    if not self.connect.limit.ready():
                        time.sleep(self.connect.limit.wait_s())
                    self.connect.send_snapshot(lambda q: parked if q == self.connect.quality else self.take_jpeg(q))
                elif self.connect.limit.ready():
                    self.connect.send_snapshot(self.take_jpeg)
            except connect_mod.ConnectError as e:
                log.warning('connect: %s', e)
                # a refused token stays refused until the settings change (and the service restarts)
                info_due = None if e.fatal else time.monotonic() + 300
            except (capture.CameraError, OSError) as e:
                self.connect.last_error = str(e)
                if info_due is not None:
                    info_due = time.monotonic() + 60
            time.sleep(1)

    def camera_resolution(self):
        with self.cam_lock:
            return self.camera.resolution()

    def uploader(self):
        target = upload.from_config(self.cfg)
        while self.running:
            folder = self.uploads.get()
            try:
                # TLS and the S3 payload hash are the CPU's heaviest work: full speed for them only
                self.hw.cpu_speed(self.lim['cpu_boost'])
                body = recording.body_for(folder, self.cfg.get('camera', 'helper'))
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
            finally:
                self.hw.cpu_speed(False)

    # ------------------------------------------------------------ timelapse actions
    def new_recording(self, name):
        rid = time.strftime('rec-%Y%m%d-%H%M%S')
        folder = os.path.join(self.storage, rid)
        nm = prusalink.video_name(name, time.localtime())
        t = self.cfg.section('timelapse')
        with self.cam_lock:
            try:
                return recording.H264Recording(self.camera, folder, nm, self.tl.job_id, t['fps'], t['quality'])
            except capture.NotSupported:
                return recording.JpegRecording(self.camera, folder, nm, self.tl.job_id, t['fps'], t['quality'])

    def act(self, actions):
        for a in actions:
            kind = a[0]
            if kind == 'start':
                self.ensure_space()
                try:
                    self.rec = self.new_recording(a[1])
                except (capture.CameraError, OSError) as e:
                    self.rec = None
                    self.warning = 'timelapse not started: %s' % e
                    log.error(self.warning)
                    continue
                self.warning = None
                self.frames_lost_hot = 0
                log.info('timelapse started: %s', self.rec.meta['name'])
                self.apply_camera_state()             # stream at print_fps from now on
            elif kind == 'rename' and self.rec:
                self.rec.rename(prusalink.video_name(a[1], time.localtime(self.rec.meta['started'])))
            elif kind == 'frame' and self.rec:
                if not self.lim['camera']:
                    self.frames_lost_hot += 1
                    continue
                try:
                    with self.picture(a[2]):
                        self.rec.add_frame()
                        if self.connect and self.tl.udp_seen and self.lim['connect']:
                            # the head is parked: the best picture Connect will get
                            self.parked_jpeg = self.camera.snapshot(min(self.connect.quality, self.lim['quality_cap']))
                except (capture.CameraError, OSError) as e:
                    self.warning = 'frame %s lost: %s' % (a[1], e)
                    log.error(self.warning)
                self.check_space()
            elif kind in ('finish', 'discard') and self.rec:
                rec, self.rec = self.rec, None
                with self.cam_lock:
                    rec.finish()
                if kind == 'finish':
                    log.info('timelapse finished (%s): %d frames', a[1], rec.frames)
                    self.uploads.put(rec.folder)
                else:
                    log.info('timelapse discarded: %s', a[1])
                    recording.mark(rec.folder, 'uploaded')     # nothing to send; pruned like a sent one
                    recording.prune(self.storage, self.cfg.get('upload', 'keep_local'))
                self.tl.stride = 1
                self.apply_camera_state()             # back to standby
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

    def start_ap(self, keep=False):
        if not self._write_net('ap', keep) and not net.switch('ap', self.net_script):
            return False
        ssid, pw = net.setup_ap(self.cfg)
        msg = 'LayerCam setup: Wi-Fi %s, passphrase %s, then http://%s' % (ssid, pw, net.AP_ADDRESS)
        # on the serial console (TP1/TP2, 115200), not in the log file
        try:
            with open(self.root + '/dev/console', 'w') as c:
                c.write('\n' + msg + '\n')
        except OSError:
            pass
        log.info('setup access point %s open (%s)', ssid, self.wifi_sup.reason if self.wifi_sup else 'setup')
        return True

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
        self.hw.cpu_speed(False)
        self.hw.ir_leds(0)
        try:
            os.makedirs(self.run_dir, exist_ok=True)
            with open(os.path.join(self.run_dir, 'service.pid'), 'w') as f:
                f.write('%d\n' % os.getpid())
        except OSError:
            pass
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGHUP, lambda *a: setattr(self, 'reload_requested', True))
        self.take_wifi_reset()
        w = self.cfg.section('wifi')
        self.wifi_sup = net.WifiSupervisor(bool(w['ssid']), w['fallback_ap_min'] * 60, w['retry_s'],
                                           new_network=net.take_new_network(self.run_dir))
        threading.Thread(target=self.wifi_loop, name='wifi', daemon=True).start()
        self.web = web.serve(self, self.port)
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
            try:
                if kind == 'printer':
                    was = self.printing()
                    self.printer = ev
                    if self.cfg.get('timelapse', 'enabled'):
                        self.act(self.tl.printer(ev))
                    if self.printing() != was:
                        self.apply_camera_state()
                elif kind == 'trigger':
                    self.last_trigger = ev
                    if self.cfg.get('timelapse', 'enabled'):
                        self.act(self.tl.trigger(ev))
                self.act(self.tl.tick())
            except Exception as e:      # one bad event must not stop the camera
                self.warning = 'internal error: %s' % e
                log.exception('main loop')
            self.housekeeping()
            blink.state = hw.led_state(self.setup_ap, self.setup_ap or self.wifi_up,
                                       bool(self.warning or self.printer_error or self.boot_pad or
                                            (self.connect and self.connect.disabled)), self.rec is not None,
                                       self.gov.level, self.updating)

    def housekeeping(self):
        """Once a loop: keep an update that has stayed up; restart when asked (SIGHUP)."""
        if self.good_after_s is not None and time.monotonic() - self.started >= self.good_after_s:
            self.good_after_s = None
            try:
                if self.apps.mark_good(RUNNING_DIR):
                    log.warning('update %s stayed up: kept', VERSION)
            except OSError as e:
                log.warning('update state: %s', e)
        if self.reload_requested:
            log.info('SIGHUP: starting again with the saved settings')
            want = self.apps.would_run()
            self.restart(reselect=self.on_camera_layout() and
                         os.path.realpath(want) != os.path.realpath(RUNNING_DIR))
