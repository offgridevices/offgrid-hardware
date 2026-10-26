"""Prusa Connect: the camera's snapshots and its description.

Prusa's Camera Service API (https://camera-service.prusa3d.com/docs/,
openapi.yaml read 26 Oct 2026).  The older https://connect.prusa3d.com/c/info
and /c/snapshot paths still work but are marked deprecated in Connect's own
camera API docs (connect.prusa3d.com/docs/cameras/openapi/openapi.yaml), so
this uses the current ones:

    PUT /v1/camera-info   JSON {config, features, device}; unknown keys -> 422
    PUT /v1/snapshot      raw JPEG, Content-Length required (chunked -> 411),
                          at most 1 000 000 bytes (413), 6 uploads a minute
                          per camera (429/503 from the gateway)

Every request carries Token (20 letters/digits, from Connect: Camera > Add
new camera > other camera), Fingerprint (16-64 characters, made by the
camera, bound to the token by the first call, which must come within
15 minutes of creating the camera) and a User-Agent.
"""
import json, logging, time, urllib.error, urllib.request

from . import HARDWARE, VERSION

log = logging.getLogger('connect')

MAX_SNAPSHOT = 1000000         # bytes (Camera Service: 1 MB; Connect's old /c/snapshot allowed 16 MB)
MIN_INTERVAL = 10.0            # s: 6 uploads per minute per camera
SCHEMES = {10: 'TEN_SEC', 30: 'THIRTY_SEC', 60: 'SIXTY_SEC'}
USER_AGENT = 'LayerCam/%s' % VERSION


class ConnectError(Exception):
    def __init__(self, status, message, retry_after=None, fatal=False):
        Exception.__init__(self, '%s %s' % (status, message))
        self.status, self.retry_after, self.fatal = status, retry_after, fatal


def camera_info(cfg, resolution, network_info=None):
    """The body of PUT /v1/camera-info.  Only documented keys: the service
    rejects anything else with 422."""
    conf = {'name': cfg.get('device', 'name'),
            'trigger_scheme': SCHEMES[cfg.get('connect', 'interval')],
            'rotation': cfg.get('camera', 'rotation'),
            'resolution': {'width': resolution[0], 'height': resolution[1]},
            'driver': 'rkmpi' if cfg.get('camera', 'backend') == 'rkmpi' else cfg.get('camera', 'backend')}
    if network_info:
        conf['network_info'] = {k: v for k, v in network_info.items()
                                if k in ('wifi_mac', 'wifi_ipv4', 'wifi_ipv6', 'wifi_ssid') and v}
    # device.type must be one of Buddy3D, ESP32, WEB, LINK, INTERNAL (anything
    # else is a 422).  This board sits in a Buddy3D housing and fills that role;
    # manufacturer/model say what it really is.
    return {'config': conf,
            'features': ['snapshot'],
            'device': {'type': 'Buddy3D', 'manufacturer': 'OffGrid', 'model': HARDWARE,
                       'firmware_version': VERSION, 'hardware_version': HARDWARE}}


def snapshot_request(url, token, fingerprint, jpeg):
    """The PUT /v1/snapshot request, checked before it is sent."""
    if not jpeg or jpeg[:2] != b'\xff\xd8':
        raise ValueError('not a JPEG')
    if len(jpeg) > MAX_SNAPSHOT:
        raise ValueError('snapshot is %d bytes, the limit is %d' % (len(jpeg), MAX_SNAPSHOT))
    return _request(url.rstrip('/') + '/v1/snapshot', 'PUT', token, fingerprint, jpeg, 'image/jpeg')


def info_request(url, token, fingerprint, body):
    data = json.dumps(body, separators=(',', ':')).encode()
    return _request(url.rstrip('/') + '/v1/camera-info', 'PUT', token, fingerprint, data, 'application/json')


def _request(url, method, token, fingerprint, data, ctype):
    if not (len(token) == 20 and token.isalnum()):
        raise ValueError('the Connect token is 20 letters and digits')
    if not 16 <= len(fingerprint) <= 64:
        raise ValueError('the fingerprint must be 16-64 characters')
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Token', token)
    req.add_header('Fingerprint', fingerprint)
    req.add_header('User-Agent', USER_AGENT)
    req.add_header('Content-Type', ctype)
    # bytes body: urllib sends Content-Length, never chunked (411 otherwise)
    req.add_header('Content-Length', str(len(data)))
    return req


class RateLimit:
    """At most one upload per MIN_INTERVAL, and a pause after the gateway says
    'too many'.  The clock is passed in so the tests can drive it."""

    def __init__(self, interval=MIN_INTERVAL, clock=time.monotonic):
        self.interval = max(interval, MIN_INTERVAL)
        self.clock = clock
        self.next_ok = 0.0

    def ready(self):
        return self.clock() >= self.next_ok

    def wait_s(self):
        return max(0.0, self.next_ok - self.clock())

    def sent(self):
        self.last = self.clock()
        self.next_ok = self.last + self.interval

    def hurry(self):
        """Next upload as soon as the service allows (a button press, a test),
        not at the configured interval; never sooner than 10 s after the last."""
        last = getattr(self, 'last', None)
        self.next_ok = min(self.next_ok, last + MIN_INTERVAL) if last is not None else 0.0

    def back_off(self, seconds):
        self.next_ok = max(self.next_ok, self.clock() + seconds)


def classify(status, body=b''):
    """What a response means for the next attempt (Camera Service docs,
    guide/errors): wrong requests are not retried, limits and 5xx are."""
    if 200 <= status < 300:
        return None
    msg = body[:200].decode('utf-8', 'replace') if body else ''
    if status in (429, 503):
        return ConnectError(status, msg or 'rate limited', retry_after=60)
    if status == 413:
        return ConnectError(status, 'image too large')
    if status >= 500:
        return ConnectError(status, msg or 'server error', retry_after=120)
    # 400, 401, 403, 411, 415, 422: the request or the token is wrong;
    # 403 after the 15-minute window or a fingerprint change needs a new camera
    return ConnectError(status, msg or 'rejected', fatal=True)


class Connect:
    def __init__(self, cfg, clock=time.monotonic, opener=None):
        self.url = cfg.get('connect', 'url')
        self.token = cfg.get('connect', 'token')
        self.fingerprint = cfg.get('device', 'fingerprint')
        self.quality = cfg.get('connect', 'quality')
        self.limit = RateLimit(cfg.get('connect', 'interval'), clock)
        self.open = opener or (lambda req: urllib.request.urlopen(req, timeout=30))
        self.last_error = None
        self.disabled = False      # set after a fatal answer, until the settings change

    def _send(self, req):
        try:
            with self.open(req) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def send_info(self, body):
        status, data = self._send(info_request(self.url, self.token, self.fingerprint, body))
        err = classify(status, data)
        if err:
            self.last_error = str(err)
            self.disabled = err.fatal
            raise err
        return json.loads(data or b'{}')

    def send_snapshot(self, take_jpeg):
        """take_jpeg(quality) -> bytes.  Lowers the quality until the frame
        fits under 1 MB rather than letting the service answer 413."""
        if self.disabled or not self.limit.ready():
            return False
        q = self.quality
        jpeg = take_jpeg(q)
        while len(jpeg) > MAX_SNAPSHOT and q > 40:
            q -= 15
            jpeg = take_jpeg(q)
        if len(jpeg) > MAX_SNAPSHOT:
            self.last_error = 'snapshot over 1 MB even at quality %d' % q
            return False
        self.limit.sent()
        status, data = self._send(snapshot_request(self.url, self.token, self.fingerprint, jpeg))
        err = classify(status, data)
        if err:
            self.last_error = str(err)
            log.warning('snapshot: %s', err)
            if err.retry_after:
                self.limit.back_off(err.retry_after)
            if err.status == 413:
                self.quality = max(40, self.quality - 10)
            self.disabled = err.fatal
            return False
        self.last_error = None
        return True
