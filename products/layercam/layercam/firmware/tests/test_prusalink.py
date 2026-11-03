"""PrusaLink: digest authentication against a fake printer that checks it
the way the Buddy firmware does, and the status/job parsing."""
import hashlib, json, os, threading, time, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from layercam import prusalink

DATA = os.path.join(os.path.dirname(__file__), 'data')


def load(name):
    with open(os.path.join(DATA, name)) as f:
        return json.load(f)


def md5(s):
    return hashlib.md5(s.encode()).hexdigest()


class Printer(BaseHTTPRequestHandler):
    """Buddy's check (lib/WUI/nhttp/req_parser.cpp check_digest_auth):
    MD5(MD5(maker:Printer API:pw):nonce:MD5(method:uri)), 16-hex-digit nonce,
    stale=true when an old nonce comes with the right digest."""
    password = 'secret12'
    nonce = '0123456789abcdef'
    old_nonces = set()
    status = 'prusalink_status_printing.json'
    job = 'prusalink_job_printing.json'
    seen = []

    def log_message(self, *a):
        pass

    def _challenge(self, stale=False):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Digest realm="Printer API", nonce="%s", stale=%s'
                         % (Printer.nonce, 'true' if stale else 'false'))
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        auth = self.headers.get('Authorization', '')
        Printer.seen.append(auth)
        if not auth:
            return self._challenge()
        ch = prusalink.parse_challenge(auth)
        ha1 = md5('maker:Printer API:%s' % Printer.password)
        ha2 = md5('GET:%s' % self.path)
        good = ch.get('response') == md5('%s:%s:%s' % (ha1, ch.get('nonce'), ha2))
        if ch.get('nonce') != Printer.nonce:
            return self._challenge(stale=good)
        if not good:
            return self._challenge()
        if self.path == '/api/v1/job' and Printer.job is None:
            self.send_response(204)
            self.end_headers()
            return
        body = json.dumps(load(Printer.status if self.path == '/api/v1/status' else Printer.job)).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(('127.0.0.1', 0), Printer)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.host = '127.0.0.1:%d' % cls.srv.server_port

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        Printer.nonce, Printer.seen = '0123456789abcdef', []
        Printer.status, Printer.job = 'prusalink_status_printing.json', 'prusalink_job_printing.json'

    def test_rfc2617_example(self):
        # RFC 2617 section 3.5: Mufasa / Circle Of Life, qop=auth
        ch = {'realm': 'testrealm@host.com', 'nonce': 'dcd98b7102dd2f0e8b11d0f600bfb0c093', 'qop': 'auth,auth-int',
              'opaque': '5ccc069c403ebaf9f0171e9517f40e41'}
        h = prusalink.digest_header('Mufasa', 'Circle Of Life', 'GET', '/dir/index.html', ch, 1, '0a4f113b')
        self.assertIn('response="6629fae49393a05397450978507c4ef1"', h)
        self.assertIn('nc=00000001', h)

    def test_digest_and_parse(self):
        link = prusalink.PrusaLink(self.host, 'maker', Printer.password)
        st = link.snapshot()
        self.assertEqual(st.state, 'PRINTING')
        self.assertTrue(st.printing)
        self.assertEqual(st.job_id, 274)
        self.assertEqual(st.name, 'Benchy_0.4n_0.2mm_PLA_COREONE_45m.bgcode')
        self.assertAlmostEqual(st.z, 4.2)
        # one unauthenticated try, then everything with the cached nonce
        self.assertEqual(Printer.seen[0], '')
        self.assertTrue(all(s.startswith('Digest ') for s in Printer.seen[1:]))
        self.assertEqual(len(Printer.seen), 3)
        self.assertNotIn('qop', Printer.seen[1])      # Buddy offers no qop

    def test_stale_nonce(self):
        link = prusalink.PrusaLink(self.host, 'maker', Printer.password)
        link.get('/api/v1/status')
        Printer.nonce = 'fedcba9876543210'                # the printer's 300 s nonce ran out
        code, body = link.get('/api/v1/status')
        self.assertEqual(code, 200)
        self.assertEqual(link.challenge['nonce'], 'fedcba9876543210')

    def test_wrong_password(self):
        link = prusalink.PrusaLink(self.host, 'maker', 'nope')
        with self.assertRaises(prusalink.LinkError):
            link.get('/api/v1/status')

    def test_unreachable(self):
        link = prusalink.PrusaLink('127.0.0.1:1', timeout=0.5)
        with self.assertRaises(prusalink.LinkError):
            link.snapshot()

    def test_finished_stopped_idle(self):
        st = prusalink.parse(load('prusalink_status_finished.json'), load('prusalink_job_finished.json'))
        self.assertEqual((st.state, st.job_id, st.printing), ('FINISHED', 274, False))
        st = prusalink.parse(load('prusalink_status_stopped.json'))
        self.assertEqual((st.state, st.job_id, st.printing), ('STOPPED', 275, False))
        st = prusalink.parse(load('prusalink_status_idle.json'))
        self.assertEqual((st.state, st.job_id, st.name), ('IDLE', None, None))

    def test_no_job_204(self):
        Printer.status, Printer.job = 'prusalink_status_idle.json', None
        st = prusalink.PrusaLink(self.host, 'maker', Printer.password).snapshot()
        self.assertEqual(st.state, 'IDLE')
        self.assertIsNone(st.job_id)

    def test_video_name(self):
        when = time.struct_time((2026, 10, 26, 14, 32, 0, 0, 299, 0))
        self.assertEqual(prusalink.video_name('Benchy_0.4n_0.2mm_PLA_COREONE_45m.bgcode', when),
                         '2026-10-26_1432_Benchy_0.4n_0.2mm_PLA_COREONE_45m')
        self.assertEqual(prusalink.video_name('/usb/My part (v2) ü.gcode', when), '2026-10-26_1432_My_part_v2')
        self.assertEqual(prusalink.video_name(None, when), '2026-10-26_1432_print')
        self.assertEqual(prusalink.video_name('../../etc/passwd', when), '2026-10-26_1432_passwd')


if __name__ == '__main__':
    unittest.main()
