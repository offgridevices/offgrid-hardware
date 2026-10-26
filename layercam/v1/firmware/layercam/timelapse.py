"""When to start a timelapse, when to take a frame, when it is finished.

Pure logic, no camera, no network, the clock passed in, so every path is
tested on the host (tests/test_timelapse.py).  The service feeds it three
kinds of events and carries out the actions it returns:

    printer(status)   PrusaLink poll: job started, finished, cancelled, Z
    trigger(t)        the slicer snippet's OGCAM:LAYER:<n> / OGCAM:END (UDP)
    tick()            time passing (the no-PrusaLink idle timeout)

Actions: ('start', name), ('rename', name), ('frame', layer, delay_s),
('finish', reason), ('discard', reason), ('warn', text).
"""
import time

POLL_GRACE_LAYERS = 3   # auto mode: layers seen by Z with no UDP trigger before the Z fallback takes over


class ZLayers:
    """Layer changes from PrusaLink's axis_z, polled every few seconds.

    A Z hop on travel (0.2 mm on Prusa's CORE One profile) looks like a new
    layer for one sample, so a height counts only once it is seen twice in a
    row, and only if it is above the last layer by min_step.  A drop by more
    than drop_mm is a new print."""

    def __init__(self, min_step=0.05, drop_mm=5.0):
        self.min_step, self.drop = min_step, drop_mm
        self.reset()

    def reset(self):
        self.layer_z = None
        self.candidate = None
        self.count = 0

    def feed(self, z):
        if z is None:
            return None
        if self.layer_z is not None and z < self.layer_z - self.drop:
            self.reset()
        if self.candidate is not None and abs(z - self.candidate) < 0.005:
            stable = True
        else:
            self.candidate, stable = z, False
        if not stable:
            return None
        if self.layer_z is None or z >= self.layer_z + self.min_step:
            self.layer_z = z
            self.count += 1
            return self.count
        return None


class Timelapse:
    def __init__(self, trigger='auto', dwell_ms=1600, settle_ms=150, capture_ms=250,
                 keep_cancelled=True, idle_timeout_s=1800, have_printer=True, clock=time.monotonic):
        self.mode = trigger
        self.dwell, self.settle, self.capture = dwell_ms, settle_ms, capture_ms
        self.keep_cancelled = keep_cancelled
        self.idle_timeout = idle_timeout_s
        self.have_printer = have_printer
        self.clock = clock
        self.stride = 1
        self._idle()

    def _idle(self):
        self.recording = False
        self.job_id = None
        self.name = None
        self.last_layer = -1
        self.frames = 0
        self.accepted = 0
        self.missed = 0
        self.duplicates = 0
        self.udp_seen = False
        self.poll_active = self.mode == 'poll'
        self.zl = ZLayers()
        self.last_frame_at = None
        self.end_seen = False

    # ------------------------------------------------------------ helpers
    def _start(self, job_id, name):
        self._idle()
        self.recording = True
        self.job_id, self.name = job_id, name
        self.started_at = self.clock()
        return [('start', name)]

    def _finish(self, reason):
        frames, cancelled = self.frames, reason == 'stopped'
        self._idle()
        if frames == 0:
            return [('discard', 'no frames')]
        if cancelled and not self.keep_cancelled:
            return [('discard', 'print cancelled')]
        return [('finish', reason)]

    def _frame(self, layer, delay_s):
        self.accepted += 1
        # thinning (set by the service when space runs low): keep every stride-th layer
        if (self.accepted - 1) % self.stride:
            return []
        self.frames += 1
        self.last_frame_at = self.clock()
        return [('frame', layer, delay_s)]

    # ------------------------------------------------------------ events
    def printer(self, st):
        """A PrusaLink status (prusalink.PrinterStatus)."""
        out = []
        if st.printing:
            if not self.recording:
                out += self._start(st.job_id, st.name)
            elif self.job_id is None:
                # started by a UDP trigger before PrusaLink saw the job
                self.job_id = st.job_id
                if st.name and st.name != self.name:
                    self.name = st.name
                    out.append(('rename', st.name))
            elif st.job_id != self.job_id:
                # a new job without us seeing the old one end
                out += self._finish('ended')
                out += self._start(st.job_id, st.name)
            if st.state == 'PRINTING' and self.poll_active:
                n = self.zl.feed(st.z)
                if n is not None:
                    out += self._frame(n, 0.0)
            elif st.state == 'PRINTING' and self.mode == 'auto' and not self.udp_seen:
                n = self.zl.feed(st.z)
                if n is not None and n >= POLL_GRACE_LAYERS:
                    self.poll_active = True
                    out.append(('warn', 'no layer trigger from the printer: taking frames on Z changes '
                                        '(head not parked; add the slicer snippet for clean frames)'))
                    out += self._frame(n, 0.0)
        elif self.recording:
            if st.state == 'FINISHED':
                out += self._finish('finished')
            elif st.state == 'STOPPED':
                out += self._finish('stopped')
            elif st.state in ('IDLE', 'READY', 'ERROR', 'UNKNOWN') and (self.job_id is not None or st.job_id is None):
                out += self._finish('ended')
        return out

    def trigger(self, t):
        """A metrics.Trigger."""
        out = []
        if self.mode == 'poll':
            return out
        if t.kind == 'LAYER':
            try:
                layer = int(t.arg)
            except (TypeError, ValueError):
                return [('warn', 'bad layer trigger %r' % t.arg)]
            if not self.recording:
                out += self._start(None, None)
            if not self.udp_seen:
                self.udp_seen = True
                self.poll_active = False
            if layer <= self.last_layer:
                # the snippet sends each trigger twice in case a datagram is lost
                self.duplicates += 1
                return out
            if self.last_layer >= 0 and layer > self.last_layer + 1:
                self.missed += layer - self.last_layer - 1
            self.last_layer = layer
            # the line ran after M400, so the head was parked age_ms ago;
            # wait out the settle time, and say so if the dwell is too short
            left = self.dwell - t.age_ms
            if left < self.settle + self.capture:
                out.append(('warn', 'layer %d trigger arrived %d ms late: the %d ms dwell leaves too little time; '
                                    'lengthen G4 in the slicer snippet' % (layer, t.age_ms, self.dwell)))
            out += self._frame(layer, max(0, self.settle - t.age_ms) / 1000.0)
        elif t.kind == 'END':
            if self.recording and not self.end_seen:
                self.end_seen = True
                self.last_layer += 1
                out += self._frame(self.last_layer, max(0, self.settle - t.age_ms) / 1000.0)
                if not self.have_printer:
                    out += self._finish('finished')
        return out

    def tick(self):
        """Without PrusaLink nothing says the print is over but the frames stopping."""
        if self.recording and not self.have_printer and self.last_frame_at is not None:
            if self.clock() - self.last_frame_at > self.idle_timeout:
                return self._finish('timeout')
        return []
