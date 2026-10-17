"""Tests for printhub.py against a fake board on localhost (no hardware).

    python3 host/test_printhub.py
"""
import contextlib, io, json, os, sys, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import printhub

STATUS = {"ok": True, "version": "1.0.0", "input": {"mv": 9020, "contract": "9V 3A USB-PD"}, "rail_mv": 5150,
          "budget_ma": 4100, "budget": "auto", "total_ma": 1050, "ip": "192.168.1.50",
          "ports": [{"port": 1, "name": "fan", "on": True, "pending": False, "ma": 450, "limit_ma": 1500,
                     "priority": 1, "boot_on": False, "off_in_s": 600, "last_off": ""},
                    {"port": 2, "name": "light", "on": False, "pending": False, "ma": 0, "limit_ma": 1500,
                     "priority": 5, "boot_on": False, "off_in_s": -1, "last_off": "overcurrent"}]}


class Fake(BaseHTTPRequestHandler):
    seen = []
    token = None

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        line = self.rfile.read(int(self.headers['Content-Length'])).decode()
        Fake.seen.append((line, self.headers.get('Authorization')))
        if Fake.token and self.headers.get('Authorization') != 'Bearer ' + Fake.token:
            return self._send(401, {"ok": False, "error": "token required"})
        if line == 'status':
            return self._send(200, STATUS)
        if line.startswith('on nosuch'):
            return self._send(400, {"ok": False, "error": "no such port: nosuch"})
        return self._send(200, {"ok": True})


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(('127.0.0.1', 0), Fake)
        cls.host = '127.0.0.1:%d' % cls.srv.server_port
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = printhub.main(['--host', self.host] + list(args))
        return rc, out.getvalue()

    def setUp(self):
        Fake.seen.clear()
        Fake.token = None

    def test_on_sends_the_command_line(self):
        rc, out = self.run_cli('on', 'fan', 'light', 'for', '10m')
        self.assertEqual(rc, 0)
        self.assertEqual(Fake.seen[0][0], 'on fan light for 10m')
        self.assertEqual(json.loads(out), {"ok": True})

    def test_board_says_no_exit_1(self):
        rc, out = self.run_cli('on', 'nosuch')
        self.assertEqual(rc, 1)
        self.assertIn('no such port', out)

    def test_status_table(self):
        rc, out = self.run_cli('status')
        self.assertEqual(rc, 0)
        self.assertIn('9V 3A USB-PD', out)
        self.assertIn('fan', out)
        self.assertIn('off in 10m00s', out)
        self.assertIn('drew more than its limit', out)

    def test_status_json(self):
        rc, out = self.run_cli('--json', 'status')
        self.assertEqual(json.loads(out)['budget_ma'], 4100)

    def test_token_header(self):
        Fake.token = 's3cret'
        rc, _ = self.run_cli('status')
        self.assertEqual(rc, 1)
        rc, _ = self.run_cli('--token', 's3cret', 'status')
        self.assertEqual(rc, 0)
        self.assertEqual(Fake.seen[-1][1], 'Bearer s3cret')

    def test_wifi_name_with_spaces_is_quoted(self):
        self.run_cli('wifi', 'My Home Net', 'pa ss')
        self.assertEqual(Fake.seen[0][0], "wifi 'My Home Net' 'pa ss'")

    def test_unreachable_exit_2(self):
        out = io.StringIO()
        with contextlib.redirect_stderr(out):
            rc = printhub.main(['--host', '127.0.0.1:1', 'status'])
        self.assertEqual(rc, 2)


if __name__ == '__main__':
    unittest.main(verbosity=1)
