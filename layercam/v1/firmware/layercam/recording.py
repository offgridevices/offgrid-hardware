"""A timelapse on disk, from the first frame to the video that is uploaded.

Two ways, chosen by what the camera can do:

H264Recording (the camera's hardware encoder, the default on LayerCam):
each frame is encoded into H.264 the moment it is taken and appended to
video.h264; video.idx gets one "offset size" line per frame.  No frames are
stored: consecutive layer frames differ little, so most are small P-frames
(an estimate of 20-60 kB each at 2304 x 1296 until measured on the board,
so tens of MB for a 1000-layer print), where 1000 JPEGs of 300-500 kB would
need more than the whole 256 MB NAND.  At the end
mp4.Mp4Body streams it out as an MP4.  A power cut loses at most the frame
being written: the index is flushed after every frame.

JpegRecording (a PC, or no hardware encoder): JPEG frames in frames/, made
into an MP4 by ffmpeg at the end.  When space runs short every other frame
is dropped, so the video still covers the whole print, at half the rate.

Each recording is a folder in the storage directory with meta.json:
{"name", "job_id", "kind", "state": recording|done|uploaded, "frames"}.
"""
import json, logging, os, shutil, subprocess, time

from . import mp4
from .capture import CameraError
from .upload import FileBody

log = logging.getLogger('recording')
GOP = 30           # an IDR every 30 frames: seekable, and a damaged frame spoils at most one second


def _save_meta(folder, meta):
    tmp = os.path.join(folder, 'meta.json.tmp')
    with open(tmp, 'w') as f:
        json.dump(meta, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, os.path.join(folder, 'meta.json'))


def load_meta(folder):
    try:
        with open(os.path.join(folder, 'meta.json')) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


class Recording:
    kind = None

    def __init__(self, folder, name, job_id=None, fps=30, quality=28):
        self.folder, self.fps, self.quality = folder, fps, quality
        os.makedirs(folder, exist_ok=True)
        self.meta = {'name': name, 'job_id': job_id, 'kind': self.kind, 'state': 'recording', 'frames': 0,
                     'fps': fps, 'quality': quality, 'started': int(time.time())}
        _save_meta(folder, self.meta)

    @property
    def frames(self):
        return self.meta['frames']

    def rename(self, name):
        self.meta['name'] = name
        _save_meta(self.folder, self.meta)

    def _count(self):
        self.meta['frames'] += 1
        _save_meta(self.folder, self.meta)

    def finish(self):
        self.meta['state'] = 'done'
        _save_meta(self.folder, self.meta)


class H264Recording(Recording):
    kind = 'h264'

    def __init__(self, camera, folder, name, job_id=None, fps=30, quality=28):
        Recording.__init__(self, folder, name, job_id, fps, quality)
        self.camera = camera
        self.h264 = os.path.join(folder, 'video.h264')
        self.idx = os.path.join(folder, 'video.idx')
        self.camera.video_start(self.h264, fps, quality, GOP)

    def add_frame(self):
        try:
            off, size, key = self.camera.video_frame()
        except CameraError:
            # the helper restarted: open the stream again (it appends, and starts on an IDR)
            self.camera.video_start(self.h264, self.fps, self.quality, GOP)
            off, size, key = self.camera.video_frame()
        with open(self.idx, 'a') as f:
            f.write('%d %d %d\n' % (off, size, 1 if key else 0))
            f.flush()
            os.fsync(f.fileno())
        self._count()
        return size

    def finish(self):
        try:
            self.camera.video_stop()
        except CameraError as e:
            log.warning('video stop: %s', e)
        Recording.finish(self)


class JpegRecording(Recording):
    kind = 'jpeg'

    def __init__(self, camera, folder, name, job_id=None, fps=30, quality=28):
        Recording.__init__(self, folder, name, job_id, fps, quality)
        self.camera = camera
        self.dir = os.path.join(folder, 'frames')
        os.makedirs(self.dir, exist_ok=True)

    def add_frame(self):
        data = self.camera.snapshot(90)
        path = os.path.join(self.dir, '%06d.jpg' % self.meta['frames'])
        with open(path, 'wb') as f:
            f.write(data)
        self._count()
        return len(data)

    def thin(self):
        """Drop every other frame (keep 0, 2, 4, ...) and number the rest
        again from 0, as ffmpeg's %06d input needs."""
        names = sorted(n for n in os.listdir(self.dir) if n.endswith('.jpg'))
        keep = names[::2]
        for n in names[1::2]:
            os.unlink(os.path.join(self.dir, n))
        for i, n in enumerate(keep):
            os.replace(os.path.join(self.dir, n), os.path.join(self.dir, '%06d.jpg' % i))
        self.meta['frames'] = len(keep)
        _save_meta(self.folder, self.meta)
        return len(names) - len(keep)


def ffmpeg_cmd(frames_dir, fps, crf, out):
    return ['ffmpeg', '-loglevel', 'error', '-y', '-framerate', str(fps), '-i', os.path.join(frames_dir, '%06d.jpg'),
            '-c:v', 'libx264', '-crf', str(crf), '-pix_fmt', 'yuv420p',
            # odd sizes are not allowed in yuv420p
            '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', '-movflags', '+faststart', out]


def encode_with_helper(helper, folder, meta, run=subprocess.run):
    """JPEG frames -> video.h264 + video.idx with the camera's hardware
    encoder (layercam-media --encode-jpegs), where there is no ffmpeg."""
    frames = os.path.join(folder, 'frames')
    lst = os.path.join(folder, 'frames.txt')
    with open(lst, 'w') as f:
        for n in sorted(os.listdir(frames)):
            if n.endswith('.jpg'):
                f.write(os.path.join(frames, n) + '\n')
    h264 = os.path.join(folder, 'video.h264')
    if os.path.exists(h264):
        os.unlink(h264)
    r = run([helper, '--encode-jpegs', lst, h264, '--fps', str(meta['fps']), '--qp', str(meta['quality'])],
            capture_output=True, timeout=3600, check=True)
    with open(os.path.join(folder, 'video.idx'), 'w') as idx:
        for line in r.stdout.decode('ascii', 'replace').splitlines():
            p = line.split()
            if len(p) == 4 and p[0] == 'FRAME':
                idx.write('%s %s %s\n' % (p[1], p[2], p[3]))
    meta['kind'] = 'h264'
    _save_meta(folder, meta)
    shutil.rmtree(frames, ignore_errors=True)
    os.unlink(lst)


def body_for(folder, helper=None, run=subprocess.run):
    """The upload body for a finished recording folder, or None if it has no frames."""
    meta = load_meta(folder)
    if not meta or not meta.get('frames'):
        return None
    name = meta['name'] + '.mp4'
    if meta['kind'] == 'jpeg' and not os.path.exists(os.path.join(folder, 'video.mp4')):
        if shutil.which('ffmpeg'):
            out = os.path.join(folder, 'video.mp4')
            run(ffmpeg_cmd(os.path.join(folder, 'frames'), meta['fps'], meta['quality'], out + '.tmp.mp4'), check=True)
            os.replace(out + '.tmp.mp4', out)
            shutil.rmtree(os.path.join(folder, 'frames'), ignore_errors=True)
        elif helper and os.path.exists(helper):
            encode_with_helper(helper, folder, meta, run)
        else:
            raise RuntimeError('no ffmpeg and no layercam-media to make the video from JPEG frames')
    if meta['kind'] == 'h264':
        b = mp4.Mp4Body(os.path.join(folder, 'video.h264'), os.path.join(folder, 'video.idx'), meta['fps'], name)
        return b if b.frames else None
    return FileBody(os.path.join(folder, 'video.mp4'), name)


def list_recordings(storage):
    out = []
    if os.path.isdir(storage):
        for n in sorted(os.listdir(storage)):
            f = os.path.join(storage, n)
            m = load_meta(f) if os.path.isdir(f) else None
            if m:
                out.append((f, m))
    return out


def mark(folder, state):
    meta = load_meta(folder)
    if meta:
        meta['state'] = state
        _save_meta(folder, meta)


def prune(storage, keep):
    """Delete uploaded recordings beyond the newest `keep`."""
    done = [(f, m) for f, m in list_recordings(storage) if m.get('state') == 'uploaded']
    done.sort(key=lambda fm: fm[1].get('started', 0))
    for f, _ in done[:max(0, len(done) - keep)]:
        shutil.rmtree(f, ignore_errors=True)
