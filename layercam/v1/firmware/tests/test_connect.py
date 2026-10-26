"""Prusa Connect (Camera Service) requests: headers, size limit, rate limit,
what each answer does."""
import io, json, unittest, urllib.error

from layercam import config, connect
from layercam.capture import TINY_JPEG

TOKEN = 'T0nSPU2v05v0pJeKYFYV'          # the example token shape from Prusa's docs
FP = '3f9a1c0e7b2d4a6f3f9a1c0e7b2d4a6f'


class Clock:
    t = 0.0

    def __call__(self):
        return self.t


class Resp(io.BytesIO):
    def __init__(self, status, body=b''):
        io.BytesIO.__init__(self, body)
        self.status = status


def cfg(**kw):
    c = config.Config({('connect', 'token'): TOKEN, ('device', 'fingerprint'): FP})
    for k, v in kw.items():
        s, key = k.split('__')
        c.set(s, key, v)
    return c


class Requests(unittest.TestCase):
    def test_snapshot_request(self):
        r = connect.snapshot_request('https://camera-service.prusa3d.com', TOKEN, FP, TINY_JPEG)
        self.assertEqual(r.full_url, 'https://camera-service.prusa3d.com/v1/snapshot')
        self.assertEqual(r.get_method(), 'PUT')
        h = {k.lower(): v for k, v in r.header_items()}
        self.assertEqual(h['token'], TOKEN)
        self.assertEqual(h['fingerprint'], FP)
        self.assertEqual(h['content-type'], 'image/jpeg')
        self.assertEqual(h['content-length'], str(len(TINY_JPEG)))
        self.assertTrue(h['user-agent'].startswith('LayerCam/'))
        self.assertIs(r.data, TINY_JPEG)

    def test_limits(self):
        big = b'\xff\xd8' + b'\0' * connect.MAX_SNAPSHOT
        with self.assertRaises(ValueError):
            connect.snapshot_request('https://x', TOKEN, FP, big)
        ok = b'\xff\xd8' + b'\0' * (connect.MAX_SNAPSHOT - 2)
        connect.snapshot_request('https://x', TOKEN, FP, ok)      # exactly 1 000 000 bytes is allowed
        with self.assertRaises(ValueError):
            connect.snapshot_request('https://x', TOKEN, FP, b'GIF89a')
        with self.assertRaises(ValueError):
            connect.snapshot_request('https://x', 'short', FP, TINY_JPEG)
        with self.assertRaises(ValueError):
            connect.snapshot_request('https://x', TOKEN, 'f' * 15, TINY_JPEG)
        with self.assertRaises(ValueError):
            connect.snapshot_request('https://x', TOKEN, 'f' * 65, TINY_JPEG)

    def test_camera_info_only_documented_keys(self):
        body = connect.camera_info(cfg(), (2304, 1296), {'wifi_ipv4': '192.0.2.40', 'wifi_mac': '0a:bc:12:34:56:7f',
                                                         'lan_ipv4': '', 'bogus': 1})
        self.assertEqual(set(body), {'config', 'features', 'device'})
        self.assertLessEqual(set(body['config']), {'name', 'path', 'driver', 'trigger_scheme', 'rotation',
                                                   'resolution', 'network_info'})
        self.assertEqual(body['config']['trigger_scheme'], 'THIRTY_SEC')
        self.assertEqual(body['config']['resolution'], {'width': 2304, 'height': 1296})
        self.assertEqual(set(body['config']['network_info']), {'wifi_ipv4', 'wifi_mac'})
        d = body['device']
        self.assertIn(d['type'], ('Buddy3D', 'ESP32', 'WEB', 'LINK', 'INTERNAL'))
        self.assertTrue(1 <= len(d['firmware_version']) <= 16 and 1 <= len(d['hardware_version']) <= 32)
        r = connect.info_request('https://camera-service.prusa3d.com/', TOKEN, FP, body)
        self.assertEqual(r.full_url, 'https://camera-service.prusa3d.com/v1/camera-info')
        self.assertEqual(json.loads(r.data), body)


class RateAndAnswers(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.sent = []
        self.answer = (200, b'{"status":"OK"}')

        def opener(req):
            self.sent.append(req)
            if isinstance(self.answer, Exception):
                raise self.answer
            return Resp(*self.answer)
        self.c = connect.Connect(cfg(connect__interval=10), self.clock, opener)

    def test_rate_limit(self):
        self.assertTrue(self.c.send_snapshot(lambda q: TINY_JPEG))
        self.clock.t = 9.9
        self.assertFalse(self.c.send_snapshot(lambda q: TINY_JPEG))     # 6 a minute at most
        self.clock.t = 10.0
        self.assertTrue(self.c.send_snapshot(lambda q: TINY_JPEG))
        self.assertEqual(len(self.sent), 2)

    def test_interval_never_below_10s(self):
        self.assertEqual(connect.RateLimit(1).interval, 10.0)

    def test_429_backs_off(self):
        self.answer = urllib.error.HTTPError('u', 429, 'Too Many', {}, io.BytesIO(b''))
        self.assertFalse(self.c.send_snapshot(lambda q: TINY_JPEG))
        self.clock.t = 30
        self.assertFalse(self.c.limit.ready())
        self.clock.t = 61
        self.assertTrue(self.c.limit.ready())
        self.assertFalse(self.c.disabled)

    def test_403_stops(self):
        self.answer = urllib.error.HTTPError('u', 403, 'Forbidden', {},
                                             io.BytesIO(b'{"statusCode":403,"message":"Camera access denied"}'))
        self.assertFalse(self.c.send_snapshot(lambda q: TINY_JPEG))
        self.assertTrue(self.c.disabled)
        self.assertIn('Camera access denied', self.c.last_error)
        self.clock.t = 1000
        self.assertFalse(self.c.send_snapshot(lambda q: TINY_JPEG))
        self.assertEqual(len(self.sent), 1)

    def test_quality_lowered_for_size(self):
        asked = []

        def take(q):
            asked.append(q)
            return b'\xff\xd8' + b'\0' * (1200000 if q > 60 else 500000)
        self.assertTrue(self.c.send_snapshot(take))
        self.assertEqual(asked, [80, 65, 50])
        self.assertEqual(len(self.sent[0].data), 500002)

    def test_413_lowers_quality(self):
        self.answer = urllib.error.HTTPError('u', 413, 'Too Large', {}, io.BytesIO(b''))
        self.c.send_snapshot(lambda q: TINY_JPEG)
        self.assertEqual(self.c.quality, 70)
        self.assertFalse(self.c.disabled)

    def test_classify(self):
        for code, fatal, retry in ((400, True, None), (401, True, None), (411, True, None), (415, True, None),
                                   (422, True, None), (429, False, 60), (503, False, 60), (500, False, 120)):
            e = connect.classify(code)
            self.assertEqual((e.fatal, e.retry_after), (fatal, retry), code)
        self.assertIsNone(connect.classify(200))


if __name__ == '__main__':
    unittest.main()
