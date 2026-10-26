"""The camera helper's protocol (against tests/fake_media_helper.py), a whole
H.264 timelapse from first frame to MP4, a helper crash mid-print, the JPEG
fallback with thinning, recovery after a reboot, pruning."""
import os, sys, tempfile, unittest

from layercam import capture, recording
from tests import h264util

FAKE = os.path.join(os.path.dirname(__file__), 'fake_media_helper.py')


@unittest.skipUnless(h264util.have_ffmpeg(), 'needs ffmpeg and ffprobe with libx264')
class Helper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.aus = h264util.make_aus(320, 180, 30, gop=10)

    def setUp(self):
        self.cam = capture.MediaHelper([sys.executable, FAKE, self.aus])

    def tearDown(self):
        self.cam.close()

    def test_snapshot_and_commands(self):
        self.assertEqual(self.cam.snapshot(80), capture.TINY_JPEG)
        self.assertEqual(self.cam.resolution(), (2304, 1296))
        self.cam.night(True)
        with self.assertRaises(capture.CameraError):
            self.cam.video_frame()              # no VSTART: the helper says ERR

    def test_timelapse_to_mp4(self):
        folder = os.path.join(tempfile.mkdtemp(), 'rec-1')
        rec = recording.H264Recording(self.cam, folder, 'Benchy', 274, fps=30)
        for _ in range(25):
            rec.add_frame()
        rec.finish()
        meta = recording.load_meta(folder)
        self.assertEqual((meta['state'], meta['frames'], meta['kind']), ('done', 25, 'h264'))
        body = recording.body_for(folder)
        self.assertEqual(body.name, 'Benchy.mp4')
        out = os.path.join(folder, 'out.mp4')
        body.write(out)
        p = h264util.probe(out)
        self.assertEqual((int(p['nb_read_frames']), int(p['width']), int(p['height'])), (25, 320, 180))
        self.assertEqual(p['decode_errors'], '')

    def test_helper_crash_mid_print(self):
        folder = os.path.join(tempfile.mkdtemp(), 'rec-2')
        rec = recording.H264Recording(self.cam, folder, 'x', fps=30)
        for _ in range(10):
            rec.add_frame()
        with self.assertRaises(capture.CameraError):
            self.cam.command('DIE')
        self.cam.next_start = 0                 # skip the 5 s restart pause
        rec.add_frame()                         # restarts the helper and the stream, then takes the frame
        rec.finish()
        self.assertEqual(rec.frames, 11)
        # the helper's new stream begins on its first access unit again (an IDR with SPS/PPS)
        body = recording.body_for(folder)
        out = os.path.join(folder, 'out.mp4')
        body.write(out)
        self.assertEqual(int(h264util.probe(out)['nb_read_frames']), 11)


class Jpeg(unittest.TestCase):
    def test_thin_and_meta(self):
        folder = os.path.join(tempfile.mkdtemp(), 'rec-3')
        rec = recording.JpegRecording(capture.FakeCamera(), folder, 'x')
        for _ in range(7):
            rec.add_frame()
        self.assertEqual(rec.thin(), 3)
        self.assertEqual(sorted(os.listdir(rec.dir)), ['%06d.jpg' % i for i in range(4)])
        self.assertEqual(recording.load_meta(folder)['frames'], 4)

    def test_no_video_support_means_jpeg(self):
        with self.assertRaises(capture.NotSupported):
            capture.FakeCamera().video_start('x', 30, 28, 30)

    def test_ffmpeg_cmd(self):
        cmd = recording.ffmpeg_cmd('/f', 30, 28, '/o.mp4')
        self.assertEqual(cmd[0], 'ffmpeg')
        self.assertIn('+faststart', cmd)
        self.assertEqual(cmd[cmd.index('-crf') + 1], '28')

    @unittest.skipUnless(h264util.have_ffmpeg(), 'needs ffmpeg')
    def test_jpeg_to_mp4(self):
        import subprocess
        folder = os.path.join(tempfile.mkdtemp(), 'rec-4')
        jpg = os.path.join(folder, 'one.jpg')
        os.makedirs(folder)
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc=size=320x180', '-frames:v', '1',
                        '-y', jpg], check=True)
        with open(jpg, 'rb') as f:
            rec = recording.JpegRecording(capture.FakeCamera(f.read()), folder, 'J')
        for _ in range(5):
            rec.add_frame()
        rec.finish()
        body = recording.body_for(folder)
        self.assertEqual(int(h264util.probe(body.path)['nb_read_frames']), 5)
        self.assertFalse(os.path.exists(rec.dir))      # frames gone once the video is made


class Storage(unittest.TestCase):
    def test_list_mark_prune(self):
        st = tempfile.mkdtemp()
        for i in range(4):
            r = recording.JpegRecording(capture.FakeCamera(), os.path.join(st, 'rec-%d' % i), 'n%d' % i)
            r.meta['started'] = i
            r.add_frame()
            r.finish()
            recording.mark(r.folder, 'uploaded' if i < 3 else 'done')
        recording.prune(st, keep=1)
        left = [(os.path.basename(f), m['state']) for f, m in recording.list_recordings(st)]
        self.assertEqual(left, [('rec-2', 'uploaded'), ('rec-3', 'done')])      # unsent videos are never pruned

    def test_empty_recording_has_no_body(self):
        r = recording.JpegRecording(capture.FakeCamera(), os.path.join(tempfile.mkdtemp(), 'r'), 'n')
        r.finish()
        self.assertIsNone(recording.body_for(r.folder))


if __name__ == '__main__':
    unittest.main()
