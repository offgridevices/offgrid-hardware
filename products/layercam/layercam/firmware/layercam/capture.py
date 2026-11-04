"""Getting pictures: the C helper on the camera, any command on a PC, or a fake.

The rkmpi backend runs native/layercam-media, which owns the sensor, the ISP
and the hardware encoders, and answers one command per line on its stdin:

    SNAP <quality>                 -> JPEG <n>\\n then n bytes
    VSTART <path> <fps> <qp> <gop> -> OK            (appends to the .h264 at path)
    VFRAME                         -> FRAME <offset> <size> <key>
    VSTOP                          -> OK
    NIGHT <0|1>                    -> OK            (ISP grey mode for IR light)
    WAKE <fps>                     -> OK            (start ISP and sensor stream at fps)
    FPS <fps>                      -> OK            (change the rate while awake)
    SLEEP                          -> OK            (stop them: sensor in standby)
    PING                           -> OK <width> <height>
    any failure                    -> ERR <text>

The helper starts asleep and only takes pictures awake; the service decides
when (thermal.Policy).

Frames are taken fresh: the helper drops what the VI channel had queued
before the command arrived, so a frame never predates the head stopping.
"""
import base64, logging, os, shlex, subprocess, tempfile, threading, time

log = logging.getLogger('camera')

# a 16 x 16 grey JPEG, for the fake camera and the tests
TINY_JPEG = base64.b64decode(
    '/9j/4AAQSkZJRgABAgAAAQABAAD//gAQTGF2YzYwLjMxLjEwMgD/2wBDAAgUFBcUFxsbGxsbGyAeICEhISAgICAhISEkJCQqKiok'
    'JCQhISQkKCgqKi4vLisrKisvLzIyMjw8OTlGRkhWVmf/xABKAAEAAAAAAAAAAAAAAAAAAAAAAQEAAAAAAAAAAAAAAAAAAAAAEAEA'
    'AAAAAAAAAAAAAAAAAAAAEQEAAAAAAAAAAAAAAAAAAAAA/8AAEQgAEAAQAwEiAAIRAAMRAP/aAAwDAQACEQMRAD8AAA//2Q==')


class CameraError(Exception):
    pass


class NotSupported(CameraError):
    pass


class MediaHelper:
    """The C helper as a child process.  One command at a time (the lock);
    if it dies it is started again on the next command, at most every 5 s."""

    def __init__(self, argv, timeout=10.0):
        self.argv = argv
        self.timeout = timeout
        self.proc = None
        self.lock = threading.Lock()
        self.size = None
        self.next_start = 0.0
        self.video_on = False
        self.awake_fps = 0             # 0: asleep

    def _start(self):
        if time.monotonic() < self.next_start:
            raise CameraError('camera helper restarting')
        self.next_start = time.monotonic() + 5
        log.info('starting %s', ' '.join(self.argv))
        try:
            self.proc = subprocess.Popen(self.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
        except OSError as e:
            raise CameraError('cannot start the camera helper: %s' % e)
        self.awake_fps = 0                      # a new helper starts asleep
        line = self._readline(timeout=30)       # the ISP takes a few seconds to start
        if not line.startswith('READY'):
            self._kill()
            raise CameraError('camera helper did not start: %s' % line)
        p = line.split()
        if len(p) >= 3:
            self.size = (int(p[1]), int(p[2]))

    def _kill(self):
        if self.proc:
            try:
                self.proc.kill()
                self.proc.wait(2)
            except Exception:
                pass
            for pipe in (self.proc.stdin, self.proc.stdout):
                try:
                    pipe.close()
                except Exception:
                    pass
        self.proc = None
        self.video_on = False

    def _readline(self, timeout=None):
        # the helper writes whole lines; a watchdog kills it if it hangs
        timer = threading.Timer(timeout or self.timeout, self._kill)
        timer.start()
        try:
            line = self.proc.stdout.readline() if self.proc else b''
        finally:
            timer.cancel()
        if not line:
            self._kill()
            raise CameraError('camera helper stopped')
        return line.decode('ascii', 'replace').strip()

    def _read(self, n):
        buf = b''
        while len(buf) < n:
            b = self.proc.stdout.read(n - len(buf)) if self.proc else b''
            if not b:
                self._kill()
                raise CameraError('camera helper stopped mid-image')
            buf += b
        return buf

    def command(self, cmd):
        """-> (reply line, binary payload or None)."""
        with self.lock:
            if self.proc is None or self.proc.poll() is not None:
                want = self.awake_fps
                self._start()
                # a restarted helper starts asleep with no video: wake it as it
                # was; a VFRAME then fails once and the recording opens the
                # stream again (recording.H264Recording.add_frame)
                if want and not cmd.startswith(('WAKE', 'SLEEP')):
                    self._send('WAKE %d' % want)
                    self.awake_fps = want
            return self._send(cmd)

    def _send(self, cmd):
        try:
            self.proc.stdin.write((cmd + '\n').encode())
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            self._kill()
            raise CameraError('camera helper stopped')
        line = self._readline()
        if line.startswith('ERR'):
            raise CameraError(line[4:] or 'helper error')
        if line.startswith('JPEG '):
            return line, self._read(int(line.split()[1]))
        return line, None

    def snapshot(self, quality=80):
        line, data = self.command('SNAP %d' % quality)
        if data is None:
            raise CameraError('unexpected reply %r' % line)
        return data

    def night(self, on):
        self.command('NIGHT %d' % (1 if on else 0))

    def wake(self, fps):
        if self.awake and self.awake_fps == fps:
            return
        self.command(('FPS %d' if self.awake else 'WAKE %d') % fps)
        self.awake_fps = fps

    def sleep(self):
        if self.awake:
            self.command('SLEEP')
        self.awake_fps = 0

    @property
    def awake(self):
        return bool(self.awake_fps) and self.proc is not None and self.proc.poll() is None

    def video_start(self, path, fps, qp, gop):
        self.command('VSTART %s %d %d %d' % (path, fps, qp, gop))
        self.video_on = True

    def video_frame(self):
        line, _ = self.command('VFRAME')
        p = line.split()
        if p[0] != 'FRAME' or len(p) < 4:
            raise CameraError('unexpected reply %r' % line)
        return int(p[1]), int(p[2]), p[3] == '1'

    def video_stop(self):
        try:
            self.command('VSTOP')
        finally:
            self.video_on = False

    def resolution(self):
        if self.size is None:
            line, _ = self.command('PING')
            p = line.split()
            self.size = (int(p[1]), int(p[2]))
        return self.size

    def close(self):
        with self.lock:
            if self.proc:
                try:
                    self.proc.stdin.write(b'QUIT\n')
                    self.proc.stdin.flush()
                    self.proc.wait(5)
                except Exception:
                    pass
            self._kill()


class CommandCamera:
    """Any program that writes one JPEG to {out}: ffmpeg from a USB webcam on
    a PC, libcamera-still, ...  No video: timelapses keep JPEG frames and
    ffmpeg makes the video at the end."""

    def __init__(self, command, size=(1920, 1080)):
        self.command, self.size = command, size

    def snapshot(self, quality=80):
        fd, out = tempfile.mkstemp(suffix='.jpg')
        os.close(fd)
        try:
            argv = [a.replace('{out}', out).replace('{q}', str(quality)) for a in shlex.split(self.command)]
            subprocess.run(argv, check=True, timeout=30, capture_output=True)
            with open(out, 'rb') as f:
                return f.read()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
            raise CameraError('capture command failed: %s' % e)
        finally:
            os.unlink(out)

    def night(self, on):
        pass

    awake = True

    def wake(self, fps):
        pass

    def sleep(self):
        pass

    def video_start(self, *a):
        raise NotSupported('no hardware encoder')

    video_frame = video_stop = video_start

    def resolution(self):
        return self.size

    def close(self):
        pass


class FakeCamera(CommandCamera):
    def __init__(self, jpeg=TINY_JPEG):
        CommandCamera.__init__(self, '', (16, 16))
        self.jpeg = jpeg
        self.shots = 0
        self.night_mode = False

    def snapshot(self, quality=80):
        self.shots += 1
        return self.jpeg

    def night(self, on):
        self.night_mode = on


def from_config(cfg):
    c = cfg.section('camera')
    if c['backend'] == 'rkmpi':
        flip = {'none': 0, 'h': 1, 'v': 2, 'both': 3}[c['flip']]
        w, h = cfg.get('timelapse', 'resolution').split('x')
        return MediaHelper([c['helper'], '--iq', c['iq_dir'], '--flip', str(flip), '--width', w, '--height', h])
    if c['backend'] == 'command':
        return CommandCamera(c['command'])
    return FakeCamera()
