"""The printer's metrics datagrams, in the format of Prusa-Firmware-Buddy
6.10.1 src/common/metric_handlers.cpp:

    header  "<%i>1 - %s %s - - - msg=%u,tm=%lld,v=4 "  (facility 1 * 8 + severity 6 = 14,
            the printer's MAC, app "buddy")
    points  "%s v=\\"%s\\" %i\\n" (string), "%s v=%f %i\\n" (float),
            "%s v=%ii %i\\n" (integer), "%s v=T %i\\n" (event),
            "%s error=\\"...\\" %i\\n", custom "%s%s %i\\n"
"""
import socket, time, unittest

from layercam import metrics

HDR = '<14>1 - 0a:bc:12:34:56:7f buddy - - - msg=%d,tm=81234567,v=4 '


def datagram(*points, msg=7):
    return (HDR % msg + ''.join(points)).encode()


class LineProtocol(unittest.TestCase):
    def test_types(self):
        p = metrics.parse_line('temp_noz v=215.000000 30051')
        self.assertEqual((p.name, p.fields['v'], p.ts), ('temp_noz', 215.0, 30051))
        p = metrics.parse_line('cmdcnt v=1234i 101')
        self.assertEqual(p.fields['v'], 1234)
        p = metrics.parse_line('home v=T 5')
        self.assertIs(p.fields['v'], True)
        p = metrics.parse_line('heap,some_tag=tag_value free=82i,total=102i 102')     # doc/metrics.md example
        self.assertEqual((p.name, p.tags, p.fields), ('heap', {'some_tag': 'tag_value'}, {'free': 82, 'total': 102}))
        p = metrics.parse_line('pos_z error="invalid type" 77')
        self.assertEqual(p.fields['error'], 'invalid type')

    def test_string_with_spaces_and_escapes(self):
        p = metrics.parse_line(r'gcode v="M118 say \"hi\" a\\b" 9')
        self.assertEqual(p.fields['v'], 'M118 say "hi" a\\b')
        self.assertEqual(p.ts, 9)

    def test_garbage(self):
        for line in ('', 'just_a_name', 'x v=1 notanumber'):
            self.assertIsNone(metrics.parse_line(line), line)

    def test_datagram(self):
        h, pts = metrics.parse_datagram(datagram('gcode v="G1 X10 Y20 F3000" 12\n', 'temp_bed v=60.000000 900\n'))
        self.assertEqual((h['host'], h['app'], h['msg'], h['tm'], h['v']), ('0a:bc:12:34:56:7f', 'buddy', 7, 81234567, 4))
        self.assertEqual([p.name for p in pts], ['gcode', 'temp_bed'])


class Triggers(unittest.TestCase):
    def test_layer_and_age(self):
        # the trigger ran at +1000 us; the buffer went out after a point at +641000 us
        ts = metrics.triggers(datagram('gcode v="M118 OGCAM:LAYER:12" 1000\n', 'gcode v="G4 P800" 1500\n',
                                       'temp_noz v=215.100006 641000\n'))
        self.assertEqual(len(ts), 1)
        self.assertEqual((ts[0].kind, ts[0].arg, ts[0].age_ms), ('LAYER', '12', 640))

    def test_meatpack_without_space(self):
        # binary G-code (MeatPack) can drop the space after M118
        ts = metrics.triggers(datagram('gcode v="M118OGCAM:LAYER:3" 10\n'))
        self.assertEqual((ts[0].kind, ts[0].arg), ('LAYER', '3'))

    def test_end_and_unrelated(self):
        ts = metrics.triggers(datagram('gcode v="M118 OGCAM:END" 10\n', 'gcode v="M118 hello" 20\n',
                                       'print_filename v="OGCAM:LAYER:9.gcode" 30\n'))
        self.assertEqual([(t.kind, t.arg) for t in ts], [('END', None)])

    def test_no_header(self):
        ts = metrics.triggers(b'gcode v="M118 OGCAM:LAYER:5" 10\n')
        self.assertEqual(ts[0].arg, '5')

    def test_udp_listener(self):
        got = []
        lst = metrics.Listener(0, got.append, bind='127.0.0.1')
        port = lst.sock.getsockname()[1]
        lst.start()
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(datagram('gcode v="G1 X1" 1\n'), ('127.0.0.1', port))
        s.sendto(datagram('gcode v="M118 OGCAM:LAYER:42" 1\n', msg=8), ('127.0.0.1', port))
        end = time.time() + 3
        while not got and time.time() < end:
            time.sleep(0.02)
        lst.stop()
        s.close()
        self.assertEqual([(t.kind, t.arg, t.source) for t in got], [('LAYER', '42', '127.0.0.1')])
        self.assertEqual(lst.datagrams, 2)


if __name__ == '__main__':
    unittest.main()
