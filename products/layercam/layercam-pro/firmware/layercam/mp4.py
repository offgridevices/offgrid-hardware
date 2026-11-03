"""H.264 elementary stream -> MP4, streamed, without writing the MP4 to disk.

The encoder appends one access unit (Annex B: start codes before each NAL)
per frame to a .h264 file, and the service keeps an index of where each one
starts (.idx, one "offset size" line per frame).  At the end this module
builds the MP4 boxes (ISO/IEC 14496-12 and -15) from the index and the
parameter sets, works out the exact length, and yields the bytes in order:

    ftyp  moov (the sample table: moov first, "faststart", plays while it downloads)
    mdat  each frame with its start codes replaced by 4-byte lengths

so an upload of a 100 MB video needs no second 100 MB on the 256 MB NAND.
SPS/PPS go into the avcC box (and are dropped from the samples), access unit
delimiters are dropped; the RV1106 encoder makes no B-frames, so decode order
is display order and no ctts box is needed.
"""
import os, struct

NAL_SLICE, NAL_IDR, NAL_SEI, NAL_SPS, NAL_PPS, NAL_AUD = 1, 5, 6, 7, 8, 9


def split_nals(au):
    """The NAL units of one Annex B access unit (start codes removed)."""
    out, i, n = [], 0, len(au)
    starts = []
    while i + 3 <= n:
        if au[i] == 0 and au[i + 1] == 0 and au[i + 2] == 1:
            starts.append(i + 3)
            i += 3
        else:
            i += 1
    for k, s in enumerate(starts):
        e = starts[k + 1] - 3 if k + 1 < len(starts) else n
        nal = au[s:e]
        # a 4-byte start code leaves a 0 at the end of the previous NAL
        # (trailing zero bytes are never part of a NAL: H.264 7.4.1)
        while nal and nal[-1] == 0:
            nal = nal[:-1]
        if nal:
            out.append(bytes(nal))
    return out


class BitReader:
    def __init__(self, data):
        # remove emulation prevention bytes (00 00 03 -> 00 00)
        rbsp, zeros = bytearray(), 0
        for b in data:
            if zeros >= 2 and b == 3:
                zeros = 0
                continue
            rbsp.append(b)
            zeros = zeros + 1 if b == 0 else 0
        self.d, self.pos = bytes(rbsp), 0

    def u(self, n):
        v = 0
        for _ in range(n):
            byte = self.d[self.pos >> 3]
            v = (v << 1) | ((byte >> (7 - (self.pos & 7))) & 1)
            self.pos += 1
        return v

    def ue(self):
        z = 0
        while self.u(1) == 0:
            z += 1
        return (1 << z) - 1 + self.u(z)

    def se(self):
        k = self.ue()
        return (k + 1) // 2 if k & 1 else -(k // 2)


def sps_size(sps):
    """Width and height in pixels from a sequence parameter set (H.264 7.3.2.1.1)."""
    r = BitReader(sps[1:])
    profile = r.u(8)
    r.u(16)                       # constraint flags, level
    r.ue()                        # seq_parameter_set_id
    chroma = 1
    if profile in (100, 110, 122, 244, 44, 83, 86, 118, 128, 138, 139, 134, 135):
        chroma = r.ue()
        if chroma == 3:
            r.u(1)
        r.ue(); r.ue(); r.u(1)    # bit depths, qpprime bypass
        if r.u(1):                # scaling matrices present
            for i in range(8 if chroma != 3 else 12):
                if r.u(1):
                    last, nxt = 8, 8
                    for _ in range(16 if i < 6 else 64):
                        if nxt:
                            nxt = (last + r.se() + 256) % 256
                        last = nxt or last
    r.ue()                        # log2_max_frame_num
    poc = r.ue()
    if poc == 0:
        r.ue()
    elif poc == 1:
        r.u(1); r.se(); r.se()
        for _ in range(r.ue()):
            r.se()
    r.ue(); r.u(1)                # max_num_ref_frames, gaps
    w_mbs = r.ue() + 1
    h_map = r.ue() + 1
    frame_mbs_only = r.u(1)
    if not frame_mbs_only:
        r.u(1)
    r.u(1)                        # direct_8x8_inference
    w, h = w_mbs * 16, h_map * 16 * (2 - frame_mbs_only)
    if r.u(1):                    # frame cropping
        cl, cr, ct, cb = r.ue(), r.ue(), r.ue(), r.ue()
        cx = 1 if chroma == 0 else (2 if chroma in (1, 2) else 1)
        cy = (1 if chroma == 0 else (2 if chroma == 1 else 1)) * (2 - frame_mbs_only)
        w -= (cl + cr) * cx
        h -= (ct + cb) * cy
    return w, h


def box(kind, *payload):
    body = b''.join(payload)
    return struct.pack('>I', 8 + len(body)) + kind + body


def full(kind, version, flags, *payload):
    return box(kind, struct.pack('>I', (version << 24) | flags), *payload)


MATRIX = struct.pack('>9I', 0x10000, 0, 0, 0, 0x10000, 0, 0, 0, 0x40000000)


class Track:
    """What the MP4 needs to know, gathered from the stream and the index."""

    def __init__(self, h264_path, index, fps):
        self.path, self.fps = h264_path, int(fps)
        self.frames = []          # (offset, size, mp4 size, keyframe)
        self.sps = self.pps = None
        with open(h264_path, 'rb') as f:
            for off, size in index:
                f.seek(off)
                au = f.read(size)
                if len(au) != size:
                    break         # a frame cut off by a power loss: stop there
                nals = split_nals(au)
                key = False
                body = 0
                for nal in nals:
                    t = nal[0] & 0x1f
                    if t == NAL_SPS:
                        self.sps = self.sps or nal
                    elif t == NAL_PPS:
                        self.pps = self.pps or nal
                    elif t == NAL_AUD:
                        pass
                    else:
                        key = key or t == NAL_IDR
                        body += 4 + len(nal)
                if body:
                    self.frames.append((off, size, body, key))
        if not self.sps or not self.pps:
            raise ValueError('%s has no SPS/PPS' % h264_path)
        self.width, self.height = sps_size(self.sps)

    def moov(self, mdat_offset):
        n = len(self.frames)
        ts = self.fps                     # one tick per frame
        dur_ms = n * 1000 // max(ts, 1)
        mvhd = full(b'mvhd', 0, 0, struct.pack('>IIII', 0, 0, 1000, dur_ms), struct.pack('>IH', 0x10000, 0x100),
                    b'\0' * 10, MATRIX, b'\0' * 24, struct.pack('>I', 2))
        tkhd = full(b'tkhd', 0, 3, struct.pack('>IIIII', 0, 0, 1, 0, dur_ms), b'\0' * 8,
                    struct.pack('>hhhH', 0, 0, 0, 0), MATRIX,
                    struct.pack('>II', self.width << 16, self.height << 16))
        mdhd = full(b'mdhd', 0, 0, struct.pack('>IIII', 0, 0, ts, n), struct.pack('>HH', 0x55c4, 0))  # 'und'
        hdlr = full(b'hdlr', 0, 0, b'\0' * 4, b'vide', b'\0' * 12, b'LayerCam\0')
        avcc = box(b'avcC', bytes([1, self.sps[1], self.sps[2], self.sps[3], 0xff, 0xe1]),
                   struct.pack('>H', len(self.sps)), self.sps, b'\x01', struct.pack('>H', len(self.pps)), self.pps)
        avc1 = box(b'avc1', b'\0' * 6, struct.pack('>H', 1), b'\0' * 16,
                   struct.pack('>HHIIIH', self.width, self.height, 0x480000, 0x480000, 0, 1),
                   b'\0' * 32, struct.pack('>Hh', 0x18, -1), avcc)
        stsd = full(b'stsd', 0, 0, struct.pack('>I', 1), avc1)
        stts = full(b'stts', 0, 0, struct.pack('>III', 1, n, 1))
        keys = [i + 1 for i, fr in enumerate(self.frames) if fr[3]]
        stss = full(b'stss', 0, 0, struct.pack('>I', len(keys)), struct.pack('>%dI' % len(keys), *keys))
        # every sample in one chunk, right after the mdat header
        stsc = full(b'stsc', 0, 0, struct.pack('>IIII', 1, 1, n, 1))
        stsz = full(b'stsz', 0, 0, struct.pack('>II', 0, n), struct.pack('>%dI' % n, *[fr[2] for fr in self.frames]))
        if mdat_offset < 1 << 32:
            stco = full(b'stco', 0, 0, struct.pack('>II', 1, mdat_offset))
        else:
            stco = full(b'co64', 0, 0, struct.pack('>IQ', 1, mdat_offset))
        stbl = box(b'stbl', stsd, stts, stss, stsc, stsz, stco)
        minf = box(b'minf', full(b'vmhd', 0, 1, b'\0' * 8),
                   box(b'dinf', full(b'dref', 0, 0, struct.pack('>I', 1), full(b'url ', 0, 1))), stbl)
        trak = box(b'trak', tkhd, box(b'mdia', mdhd, hdlr, minf))
        return box(b'moov', mvhd, trak)


FTYP = box(b'ftyp', b'isom', struct.pack('>I', 0x200), b'isom', b'iso2', b'avc1', b'mp41')


class Mp4Body:
    """The finished video as an upload body: .size, .chunks()."""
    content_type = 'video/mp4'

    def __init__(self, h264_path, index_path, fps, name):
        self.name = name
        self.track = Track(h264_path, read_index(index_path), fps)
        payload = sum(fr[2] for fr in self.track.frames)
        big = payload + 8 >= 1 << 32
        mdat_hdr = 16 if big else 8
        # the moov's length does not depend on the offset's value, only on
        # stco vs co64, so measure it with a placeholder first
        moov_len = len(self.track.moov(0 if not big else 1 << 32))
        self.mdat_offset = len(FTYP) + moov_len + mdat_hdr
        self.moov = self.track.moov(self.mdat_offset)
        assert len(self.moov) == moov_len
        self.mdat_hdr = (struct.pack('>I4sQ', 1, b'mdat', payload + 16) if big
                         else struct.pack('>I4s', payload + 8, b'mdat'))
        self.size = len(FTYP) + len(self.moov) + len(self.mdat_hdr) + payload
        self.frames = len(self.track.frames)

    def chunks(self):
        yield FTYP + self.moov + self.mdat_hdr
        with open(self.track.path, 'rb') as f:
            for off, size, body, key in self.track.frames:
                f.seek(off)
                out = []
                for nal in split_nals(f.read(size)):
                    if nal[0] & 0x1f not in (NAL_SPS, NAL_PPS, NAL_AUD):
                        out.append(struct.pack('>I', len(nal)) + nal)
                data = b''.join(out)
                assert len(data) == body
                yield data

    def write(self, path):
        with open(path, 'wb') as f:
            for c in self.chunks():
                f.write(c)


def read_index(path):
    out = []
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                p = line.split()
                if len(p) >= 2:
                    out.append((int(p[0]), int(p[1])))
    return out
