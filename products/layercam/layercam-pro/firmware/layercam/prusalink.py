"""PrusaLink on the printer: what is printing, and how far it has got.

On the CORE One, PrusaLink is served by the Buddy firmware itself
(Prusa-Firmware-Buddy 6.10.1, lib/WUI/link_content/prusa_link_api_v1.cpp,
basic_gets.cpp, nhttp/status_renderer.cpp; the PrusaLink OpenAPI spec is
Prusa-Link-Web spec/openapi.yaml):

    GET /api/v1/status  {"job": {id, progress, time_remaining, time_printing}   (only with a job)
                         "printer": {state, temp_*, axis_z, ...}}                axis_x/y only when not printing
    GET /api/v1/job     200 {id, state, progress, ..., file: {name, display_name, path, refs}}, 204 without a job

printer.state: IDLE BUSY PRINTING PAUSED FINISHED STOPPED ERROR ATTENTION READY.

Authentication (lib/WUI/nhttp/req_parser.cpp, status_page.cpp): HTTP Digest,
user "maker", realm "Printer API", MD5, *no qop* (RFC 2069 form:
response = MD5(HA1:nonce:HA2)); a nonce lives 300 s, after which the printer
answers 401 with stale=true.  Or X-Api-Key where the firmware has one.  The
qop=auth form (RFC 2617) is handled too, for other PrusaLink hosts.
"""
import hashlib, json, os, re, urllib.error, urllib.request

ACTIVE = ('PRINTING', 'PAUSED', 'ATTENTION', 'BUSY')


class LinkError(Exception):
    pass


def parse_challenge(header):
    """'Digest realm="Printer API", nonce="..", stale=false' -> dict."""
    if not header or not header.lower().startswith('digest '):
        return None
    out = {}
    for k, v in re.findall(r'(\w+)=("(?:[^"\\]|\\.)*"|[^,\s]+)', header[7:]):
        out[k.lower()] = v[1:-1] if v.startswith('"') else v
    return out


def _md5(s):
    return hashlib.md5(s.encode()).hexdigest()


def digest_header(user, password, method, uri, ch, nc=1, cnonce=None):
    """The Authorization header for one challenge (RFC 2617 section 3.2.2)."""
    realm, nonce = ch.get('realm', ''), ch['nonce']
    ha1 = _md5('%s:%s:%s' % (user, realm, password))
    ha2 = _md5('%s:%s' % (method, uri))
    qops = [q.strip() for q in ch.get('qop', '').split(',') if q.strip()]
    parts = ['username="%s"' % user, 'realm="%s"' % realm, 'nonce="%s"' % nonce, 'uri="%s"' % uri]
    if 'auth' in qops:
        cnonce = cnonce or os.urandom(8).hex()
        ncs = '%08x' % nc
        resp = _md5('%s:%s:%s:%s:auth:%s' % (ha1, nonce, ncs, cnonce, ha2))
        parts += ['qop=auth', 'nc=%s' % ncs, 'cnonce="%s"' % cnonce]
    else:
        # RFC 2069, what the Buddy firmware checks
        resp = _md5('%s:%s:%s' % (ha1, nonce, ha2))
    parts.append('response="%s"' % resp)
    if 'opaque' in ch:
        parts.append('opaque="%s"' % ch['opaque'])
    parts.append('algorithm=MD5')
    return 'Digest ' + ', '.join(parts)


class PrusaLink:
    def __init__(self, host, user='maker', password='', api_key='', timeout=5.0, opener=None):
        host = host.strip()
        self.base = host.rstrip('/') if '://' in host else 'http://' + host.rstrip('/')
        self.user, self.password, self.api_key = user, password, api_key
        self.timeout = timeout
        self.open = opener or (lambda req: urllib.request.urlopen(req, timeout=self.timeout))
        self.challenge = None
        self.nc = 0

    def _auth(self, req, path):
        if self.api_key:
            req.add_header('X-Api-Key', self.api_key)
        elif self.challenge:
            self.nc += 1
            req.add_header('Authorization', digest_header(self.user, self.password, req.get_method(),
                                                          path, self.challenge, self.nc))

    def get(self, path):
        """(status, parsed JSON or None).  Retries once on a fresh or stale nonce."""
        for attempt in range(3):
            req = urllib.request.Request(self.base + path, method='GET', headers={'Accept': 'application/json'})
            self._auth(req, path)
            try:
                with self.open(req) as r:
                    body = r.read()
                    return r.status, (json.loads(body) if body else None)
            except urllib.error.HTTPError as e:
                if e.code != 401 or self.api_key:
                    if e.code == 401:
                        raise LinkError('PrusaLink refused the API key')
                    raise LinkError('PrusaLink %s %s' % (path, e.code))
                ch = parse_challenge(e.headers.get('WWW-Authenticate', ''))
                if not ch or 'nonce' not in ch:
                    raise LinkError('PrusaLink asked for an unknown authentication')
                # a first challenge, or stale=true (the nonce expired, the
                # password was right): try again with the new nonce
                had = self.challenge is not None
                self.challenge, self.nc = ch, 0
                if had and ch.get('stale', 'false').lower() != 'true':
                    raise LinkError('PrusaLink refused the user name or password')
            except (urllib.error.URLError, OSError) as e:
                raise LinkError('PrusaLink unreachable: %s' % getattr(e, 'reason', e))
        raise LinkError('PrusaLink authentication failed')

    def snapshot(self):
        """One PrinterStatus from /api/v1/status, plus /api/v1/job when a job is on."""
        st, status = self.get('/api/v1/status')
        job = None
        if status and 'job' in status:
            code, job = self.get('/api/v1/job')
            if code == 204:
                job = None
        return parse(status or {}, job)


class PrinterStatus:
    __slots__ = ('state', 'job_id', 'name', 'progress', 'z', 'job_state')

    def __init__(self, state, job_id=None, name=None, progress=None, z=None, job_state=None):
        self.state, self.job_id, self.name = state, job_id, name
        self.progress, self.z, self.job_state = progress, z, job_state

    @property
    def printing(self):
        return self.state in ACTIVE and self.job_id is not None

    def __repr__(self):
        return 'PrinterStatus(%s, job=%s, %r, z=%s)' % (self.state, self.job_id, self.name, self.z)


def parse(status, job=None):
    printer = status.get('printer') or {}
    sj = status.get('job') or {}
    name = None
    jstate = None
    if job:
        f = job.get('file') or {}
        # display_name is the long file name; name is the 8.3 one on the USB stick
        name = f.get('display_name') or f.get('name')
        jstate = job.get('state')
    job_id = sj.get('id', job.get('id') if job else None)
    return PrinterStatus(printer.get('state', 'UNKNOWN'), job_id, name, sj.get('progress'),
                         printer.get('axis_z'), jstate)


def video_name(job_name, when):
    """'Benchy 0.2mm PLA.bgcode', time.struct_time -> '2026-10-26_1432_Benchy_0.2mm_PLA'."""
    stem = (job_name or 'print').rsplit('/', 1)[-1]
    stem = re.sub(r'\.(bgcode|gcode|gco|g)$', '', stem, flags=re.I)
    stem = re.sub(r'[^A-Za-z0-9._-]+', '_', stem).strip('._-')[:80] or 'print'
    return '%04d-%02d-%02d_%02d%02d_%s' % (when.tm_year, when.tm_mon, when.tm_mday, when.tm_hour, when.tm_min, stem)
