"""Sending a finished video somewhere: S3 (and S3-compatible), HTTP/WebDAV
PUT, an SMB share or an NFS export.

A body is anything with .name, .size, .content_type and .chunks() (an
mp4.Mp4Body streamed from the H.264 file, or FileBody).  Nothing is copied
to a temporary file first: the camera's 256 MB of NAND has no room for a
second copy of a long timelapse.

SMB and NFS use the kernel's mount (mount.cifs from Buildroot's cifs-utils,
mount.nfs from nfs-utils; README.md lists the packages and kernel options),
write NAME.part, rename it to NAME, and unmount.  smbclient is not used: it
can only upload a file that already exists on disk.
"""
import base64, hashlib, http.client, logging, os, subprocess, tempfile, time
from urllib.parse import quote, urlsplit

from . import sigv4, VERSION

log = logging.getLogger('upload')
USER_AGENT = 'LayerCam/%s' % VERSION


class UploadError(Exception):
    pass


class FileBody:
    def __init__(self, path, name=None, content_type='video/mp4'):
        self.path, self.name = path, name or os.path.basename(path)
        self.size = os.path.getsize(path)
        self.content_type = content_type

    def chunks(self, size=256 * 1024):
        with open(self.path, 'rb') as f:
            while True:
                b = f.read(size)
                if not b:
                    return
                yield b


class BytesBody:
    def __init__(self, data, name, content_type='application/octet-stream'):
        self.data, self.name, self.size, self.content_type = data, name, len(data), content_type

    def chunks(self):
        yield self.data


def sha256_of(body):
    h = hashlib.sha256()
    for c in body.chunks():
        h.update(c)
    return h.hexdigest()


def _connection(scheme, netloc, timeout=60):
    if scheme == 'https':
        return http.client.HTTPSConnection(netloc, timeout=timeout)
    return http.client.HTTPConnection(netloc, timeout=timeout)


def _put(url, body, headers, conn_factory=_connection):
    u = urlsplit(url)
    conn = conn_factory(u.scheme, u.netloc)
    try:
        path = u.path + ('?' + u.query if u.query else '')
        # Content-Length is set, so http.client sends the iterator as is, not chunked
        conn.request('PUT', path, body=body.chunks(), headers=headers)
        r = conn.getresponse()
        data = r.read()
        return r.status, data
    finally:
        conn.close()


# ------------------------------------------------------------------ S3
def s3_url(endpoint, bucket, key, addressing='auto'):
    """-> (url, host, canonical path).  Path style (https://host/bucket/key)
    works everywhere (MinIO and NAS stores need it); virtual-hosted style
    (https://bucket.host/key) is what AWS prefers.  'auto' uses virtual style
    for amazonaws.com and a DNS-safe bucket name, path style otherwise."""
    u = urlsplit(endpoint)
    host = u.netloc
    dns_safe = bucket == bucket.lower() and '.' not in bucket and '_' not in bucket
    if addressing == 'virtual' or (addressing == 'auto' and host.endswith('amazonaws.com') and dns_safe):
        host = '%s.%s' % (bucket, host)
        path = '/' + key
    else:
        path = '/%s/%s' % (bucket, key)
    return '%s://%s%s' % (u.scheme, host, quote(path, safe='/-_.~')), host, path


def s3_headers(method, host, path, payload_hash, size, ctype, access_key, secret_key, region, amz_date):
    headers = [('Host', host), ('X-Amz-Date', amz_date), ('X-Amz-Content-Sha256', payload_hash),
               ('Content-Type', ctype), ('Content-Length', str(size))]
    auth, _, _ = sigv4.sign(method, path, [], headers, payload_hash, access_key, secret_key, region, 's3', amz_date)
    out = dict(headers)
    out['Authorization'] = auth
    out['User-Agent'] = USER_AGENT
    return out


class S3:
    def __init__(self, endpoint, region, bucket, access_key, secret_key, prefix='', addressing='auto',
                 clock=time.gmtime, conn_factory=_connection):
        self.endpoint, self.region, self.bucket = endpoint, region, bucket
        self.access_key, self.secret_key = access_key, secret_key
        self.prefix, self.addressing = prefix, addressing
        self.clock, self.conn_factory = clock, conn_factory

    def describe(self):
        return 's3 %s/%s/%s' % (self.endpoint, self.bucket, self.prefix)

    def send(self, body):
        key = self.prefix + body.name
        url, host, path = s3_url(self.endpoint, self.bucket, key, self.addressing)
        # the payload hash costs one extra read of the body but keeps the
        # request fully signed (UNSIGNED-PAYLOAD is not accepted everywhere)
        h = sha256_of(body)
        amz_date = time.strftime('%Y%m%dT%H%M%SZ', self.clock())
        headers = s3_headers('PUT', host, path, h, body.size, body.content_type, self.access_key,
                             self.secret_key, self.region, amz_date)
        status, data = _put(url, body, headers, self.conn_factory)
        if status not in (200, 201):
            raise UploadError('S3 PUT %s: %d %s' % (key, status, data[:300].decode('utf-8', 'replace')))
        return url


# ------------------------------------------------------------------ HTTP PUT / WebDAV
class HttpPut:
    def __init__(self, url, user='', password='', conn_factory=_connection):
        self.url = url if url.endswith('/') else url + '/'
        self.user, self.password, self.conn_factory = user, password, conn_factory

    def describe(self):
        return 'http %s' % self.url

    def send(self, body):
        url = self.url + quote(body.name)
        headers = {'Content-Type': body.content_type, 'Content-Length': str(body.size), 'User-Agent': USER_AGENT}
        if self.user:
            tok = base64.b64encode(('%s:%s' % (self.user, self.password)).encode()).decode()
            headers['Authorization'] = 'Basic ' + tok
        status, data = _put(url, body, headers, self.conn_factory)
        if status not in (200, 201, 204):
            raise UploadError('PUT %s: %d %s' % (url, status, data[:300].decode('utf-8', 'replace')))
        return url


# ------------------------------------------------------------------ SMB / NFS
def smb_mount_cmd(share, mountpoint, credentials_file, version):
    return ['mount', '-t', 'cifs', share, mountpoint,
            '-o', 'credentials=%s,vers=%s,noserverino,file_mode=0644,dir_mode=0755' % (credentials_file, version)]


def nfs_mount_cmd(export, mountpoint):
    # nolock: no rpc.statd on the camera; the file is written once by one writer
    return ['mount', '-t', 'nfs', '-o', 'nolock,soft,timeo=100,retrans=3', export, mountpoint]


def write_into(directory, body):
    os.makedirs(directory, exist_ok=True)
    final = os.path.join(directory, body.name)
    part = final + '.part'
    with open(part, 'wb') as f:
        for c in body.chunks():
            f.write(c)
        f.flush()
        os.fsync(f.fileno())
    os.replace(part, final)
    return final


class Mounted:
    """Mount, write, unmount.  run(cmd) is subprocess.run by default; the tests
    pass a fake that records the commands and mounts nothing."""

    def __init__(self, kind, remote, subdir, user='', password='', version='3.0', run=None, workdir='/tmp'):
        self.kind, self.remote, self.subdir = kind, remote, subdir.strip('/')
        self.user, self.password, self.version = user, password, version
        self.run = run or (lambda cmd: subprocess.run(cmd, check=True, capture_output=True, timeout=60))
        self.workdir = workdir

    def describe(self):
        return '%s %s/%s' % (self.kind, self.remote, self.subdir)

    def send(self, body):
        mnt = tempfile.mkdtemp(prefix='layercam-mnt-', dir=self.workdir)
        cred = None
        try:
            if self.kind == 'smb':
                # the password goes in a 0600 file, not on the command line (ps would show it)
                fd, cred = tempfile.mkstemp(prefix='layercam-cred-', dir=self.workdir)
                with os.fdopen(fd, 'w') as f:
                    f.write('username=%s\npassword=%s\n' % (self.user or 'guest', self.password))
                cmd = smb_mount_cmd(self.remote, mnt, cred, self.version)
            else:
                cmd = nfs_mount_cmd(self.remote, mnt)
            try:
                self.run(cmd)
            except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as e:
                err = getattr(e, 'stderr', b'') or b''
                raise UploadError('%s mount failed: %s %s' % (self.kind, e, err[:200].decode('utf-8', 'replace')))
            try:
                return write_into(os.path.join(mnt, self.subdir), body)
            finally:
                try:
                    self.run(['umount', mnt])
                except Exception as e:      # an unmount failure must not hide the result
                    log.warning('umount %s: %s', mnt, e)
        finally:
            if cred:
                os.unlink(cred)
            try:
                os.rmdir(mnt)
            except OSError:
                pass


def from_config(cfg, **kw):
    u = cfg.section('upload')
    t = u['target']
    if t == 's3':
        return S3(u['s3_endpoint'], u['s3_region'], u['s3_bucket'], u['s3_access_key'], u['s3_secret_key'],
                  u['s3_prefix'], u['s3_addressing'])
    if t == 'http':
        return HttpPut(u['http_url'], u['http_user'], u['http_password'])
    if t == 'smb':
        return Mounted('smb', u['smb_share'], u['smb_dir'], u['smb_user'], u['smb_password'], u['smb_version'], **kw)
    if t == 'nfs':
        return Mounted('nfs', u['nfs_export'], u['nfs_dir'], **kw)
    return None


RETRY_S = (10, 60, 300, 900, 3600)


def send_with_retry(target, body, sleep=time.sleep, stop=lambda: False):
    """Try a few times with growing pauses; the video stays on the camera if all fail."""
    last = None
    for i, pause in enumerate((0,) + RETRY_S):
        if stop():
            break
        if pause:
            sleep(pause)
        try:
            return target.send(body)
        except (UploadError, OSError, http.client.HTTPException) as e:
            last = e
            log.warning('upload %s to %s failed (try %d): %s', body.name, target.describe(), i + 1, e)
    raise UploadError(str(last))


def free_bytes(path):
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize

