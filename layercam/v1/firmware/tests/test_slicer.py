"""The PrusaSlicer snippets: only G-codes checked in the Buddy source, inside
the CORE One's limits, lines the printer accepts, and the metrics buffer
flushed by the padding (an emulation of metric_handlers.cpp)."""
import os, re, unittest

from layercam import config, metrics

SLICER = os.path.join(os.path.dirname(__file__), '..', 'slicer')

# every command the snippets use, and where it was checked
# (Prusa-Firmware-Buddy 6.10.1, commit 1ce23f33)
VERIFIED = {
    'G1': 'lib/Marlin/Marlin/src/gcode/gcode.cpp (G0_G1)',
    'G4': 'lib/Marlin/Marlin/src/gcode/motion/G4.cpp: P milliseconds, waits for moves first',
    'G92': "Prusa's own CORE One profile (unchanged lines)",
    'M201': "Prusa's own CORE One profile (unchanged lines)",
    'M118': 'lib/Marlin/Marlin/src/gcode/host/M118.cpp; parser.cpp takes its text as a string',
    'M331': 'src/marlin_stubs/M330.cpp: enable a metric',
    'M332': 'src/marlin_stubs/M330.cpp: disable a metric',
    'M334': 'src/marlin_stubs/M330.cpp: "%20s %i %i" host, metrics port, syslog port',
    'M400': 'lib/Marlin/Marlin/src/gcode/gcode.cpp: finish all moves',
}
# G90/G91 set E relative/absolute too on Buddy (gcode.h set_relative_mode),
# undoing M83; G10/G11 and M240 are not in Buddy's G-code table at all
FORBIDDEN = {'G90', 'G91', 'G10', 'G11', 'M240', 'M82', 'M83'}

# CORE One travel limits (include/marlin/Configuration_COREONE.h, not INDX)
X_MIN, X_MAX, Y_MIN, Y_MAX = -2, 252, -19, 221
MAX_CMD_SIZE = 96                     # include/marlin/Configuration_COREONE_adv.h
METRIC_STR = 47                       # src/common/metric.h: value_str[48]


def read(name):
    with open(os.path.join(SLICER, name)) as f:
        return f.read()


def commands(text):
    for line in text.splitlines():
        line = line.split(';', 1)[0].strip()
        if line and not line.startswith('{'):
            yield line


class Snippets(unittest.TestCase):
    def test_only_verified_codes(self):
        for name in ('start.gcode', 'after_layer_change.gcode', 'end.gcode', 'before_layer_change.gcode'):
            for c in commands(read(name)):
                code = c.split()[0]
                self.assertNotIn(code, FORBIDDEN, (name, c))
                self.assertIn(code, VERIFIED, (name, c))

    def test_park_inside_limits(self):
        # the park position is set once, as PrusaSlicer local variables (2.6 and
        # later; PlaceholderParser.cpp "local"), and used by the park move
        text = read('after_layer_change.gcode')
        x = float(re.search(r'\{local park_x = (-?[\d.]+)\}', text).group(1))
        y = float(re.search(r'\{local park_y = (-?[\d.]+)\}', text).group(1))
        self.assertEqual((x, y), (2, 218))
        self.assertTrue(X_MIN <= x <= X_MAX and Y_MIN <= y <= Y_MAX)
        self.assertIn('G1 X{park_x} Y{park_y} F18000', list(commands(text)))

    def test_line_lengths(self):
        for name in ('start.gcode', 'after_layer_change.gcode', 'end.gcode'):
            for c in commands(read(name)):
                # the return move with both coordinates expanded is the longest
                expanded = c.replace('{position[0]}', '252.000000').replace('{position[1]}', '221.000000')
                expanded = expanded.replace('{park_x}', '252.000').replace('{park_y}', '221.000')
                self.assertLessEqual(len(expanded), MAX_CMD_SIZE, c)

    def test_dwell_matches_default(self):
        hold = sum(int(m) for m in re.findall(r'^G4 P(\d+)', read('after_layer_change.gcode'), re.M))
        self.assertEqual(hold, config.DEFAULTS['timelapse']['dwell_ms'])

    def test_metric_on_only_around_trigger(self):
        lines = list(commands(read('after_layer_change.gcode')))
        on, off = lines.index('M331 gcode'), lines.index('M332 gcode')
        self.assertLess(lines.index('M400'), on)                  # parked before the trigger exists
        trig = [i for i, c in enumerate(lines) if 'OGCAM:LAYER' in c]
        self.assertEqual(len(trig), 2)
        self.assertTrue(all(on < i < off for i in trig))
        self.assertIn('M334 192.0.2.40 8514', read('start.gcode'))

    def test_padding_flushes_at_once(self):
        """Emulate src/common/metric_handlers.cpp: points go into a 1024-byte
        buffer after the syslog header; it is sent when the next point would
        leave fewer than 63 bytes (TEXTPROTOCOL_POINT_MAXLEN), or when a point
        arrives once it is a second old.  With the snippet's padding the
        trigger must go out with no second-long wait, and must parse."""
        header = '<14>1 - 0a:bc:12:34:56:7f buddy - - - msg=4294967295,tm=9223372036854775807,v=4 '
        lines = list(commands(read('after_layer_change.gcode')))
        start = lines.index('M331 gcode') + 1
        sent, buf, t = [], header, 999999       # worst case: long header, 6-7 digit offsets
        for c in lines[start:]:
            if c.startswith('G4'):
                break
            v = c.replace('{layer_num}', '1234')[:METRIC_STR]
            point = 'gcode v="%s" %d\n' % (v, t)
            buf += point
            if len(buf) + 63 > 1024:
                sent.append(buf)
                buf = header
        self.assertTrue(sent, 'the padding did not fill the buffer')
        trig = metrics.triggers(sent[0].encode())
        self.assertEqual([(x.kind, x.arg) for x in trig], [('LAYER', '1234')])
        # and the shortest case (short header, small offsets) still fills it
        buf = '<14>1 - 0a:bc:12:34:56:7f buddy - - - msg=1,tm=1,v=4 '
        for c in lines[start:]:
            if c.startswith('G4'):
                break
            buf += 'gcode v="%s" %d\n' % (c.replace('{layer_num}', '1')[:METRIC_STR], 1)
        self.assertGreater(len(buf) + 63, 1024)


if __name__ == '__main__':
    unittest.main()
