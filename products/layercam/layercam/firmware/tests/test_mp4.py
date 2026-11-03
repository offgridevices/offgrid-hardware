"""The MP4 muxer: SPS parsing against hand-built parameter sets, and whole
videos checked by ffprobe/ffmpeg (skipped where the host has no ffmpeg with
libx264)."""
import os, struct, tempfile, unittest

from layercam import mp4
from tests import h264util


class Bits:
    def __init__(self):
        self.bits = []

    def u(self, n, v):
        self.bits += [(v >> (n - 1 - i)) & 1 for i in range(n)]

    def ue(self, v):
        v += 1
        n = v.bit_length()
        self.u(n - 1, 0)
        self.u(n, v)

    def data(self):
        b = self.bits + [1]                      # rbsp stop bit
        b += [0] * (-len(b) % 8)
        return bytes(int(''.join(map(str, b[i:i + 8])), 2) for i in range(0, len(b), 8))


def sps(profile, w_mbs, h_mbs, crop_bottom=0, high=False):
    b = Bits()
    b.u(8, profile); b.u(8, 0); b.u(8, 51); b.ue(0)
    if high:
        b.ue(1); b.ue(0); b.ue(0); b.u(1, 0); b.u(1, 0)     # 4:2:0, 8 bit, no scaling matrices
    b.ue(0); b.ue(0); b.ue(4)                               # log2_max_frame_num, poc type 0, its log2
    b.ue(1); b.u(1, 0)
    b.ue(w_mbs - 1); b.ue(h_mbs - 1)
    b.u(1, 1); b.u(1, 1)                                    # frame_mbs_only, direct_8x8
    if crop_bottom:
        b.u(1, 1); b.ue(0); b.ue(0); b.ue(0); b.ue(crop_bottom)
    else:
        b.u(1, 0)
    b.u(1, 0)                                               # no VUI
    return b'\x67' + b.data()


class Sps(unittest.TestCase):
    def test_sizes(self):
        self.assertEqual(mp4.sps_size(sps(77, 144, 81)), (2304, 1296))           # SC3336, main profile
        self.assertEqual(mp4.sps_size(sps(100, 120, 68, 4, high=True)), (1920, 1080))   # 1088 cropped by 8

    def test_emulation_prevention(self):
        r = mp4.BitReader(b'\x00\x00\x03\x01')
        self.assertEqual(r.u(24), 1)

    def test_split(self):
        au = b'\x00\x00\x00\x01\x09\xf0\x00\x00\x01\x67\x42\x00\x00\x00\x01\x65\x88\x80'
        self.assertEqual(mp4.split_nals(au), [b'\x09\xf0', b'\x67\x42', b'\x65\x88\x80'])


@unittest.skipUnless(h264util.have_ffmpeg(), 'needs ffmpeg and ffprobe with libx264')
class Videos(unittest.TestCase):
    def check(self, w, h, frames, gop=30):
        aus = h264util.make_aus(w, h, frames, gop)
        folder = tempfile.mkdtemp()
        h264, idx = h264util.write_stream(aus, folder)
        body = mp4.Mp4Body(h264, idx, 30, 'x.mp4')
        out = os.path.join(folder, 'x.mp4')
        body.write(out)
        self.assertEqual(os.path.getsize(out), body.size)
        p = h264util.probe(out)
        self.assertEqual((p['codec_name'], int(p['width']), int(p['height'])), ('h264', w, h))
        self.assertEqual(int(p['nb_read_frames']), frames)
        self.assertEqual(p['avg_frame_rate'], '30/1')
        self.assertEqual(p['decode_errors'], '')
        with open(out, 'rb') as f:
            head = f.read(64)
        # ftyp, then moov before mdat: plays while it downloads
        self.assertEqual(head[4:8], b'ftyp')
        n = struct.unpack('>I', head[:4])[0]
        self.assertEqual(head[n + 4:n + 8], b'moov')
        keys = [i for i, fr in enumerate(body.track.frames) if fr[3]]
        self.assertEqual(keys, list(range(0, frames, gop)))
        return body

    def test_sensor_size(self):
        self.check(2304, 1296, 8, gop=4)

    def test_cropped_size(self):
        self.check(320, 180, 65)

    def test_cut_off_last_frame(self):
        aus = h264util.make_aus(320, 180, 10)
        folder = tempfile.mkdtemp()
        h264, idx = h264util.write_stream(aus, folder)
        with open(h264, 'r+b') as f:                 # power lost while the last frame was written
            f.truncate(os.path.getsize(h264) - 10)
        body = mp4.Mp4Body(h264, idx, 30, 'x.mp4')
        self.assertEqual(body.frames, 9)
        out = os.path.join(folder, 'x.mp4')
        body.write(out)
        self.assertEqual(int(h264util.probe(out)['nb_read_frames']), 9)


if __name__ == '__main__':
    unittest.main()
