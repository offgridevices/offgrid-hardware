"""Settings: one INI file, every key with a default, checked before use.

The file lives on the userdata partition (/userdata/layercam/layercam.ini)
and is written by the setup page or by hand; board/layercam.ini.example has
every key with a comment.  Secrets (tokens, passwords) are never logged and
the setup page never sends them back, it only says whether one is set.
"""
import configparser, os, re, secrets

# section -> key -> default (the type comes from the default)
DEFAULTS = {
    'device': {
        'name': 'LayerCam',            # shown in Prusa Connect, 1-32 characters
        'fingerprint': '',             # made on first boot; never change it (Connect binds it to the token)
    },
    'wifi': {
        'ssid': '',
        'password': '',
        'ap_password': 'layercam-setup',   # the setup access point's WPA2 passphrase
    },
    'connect': {
        'enabled': True,
        'token': '',                   # 20 characters, from Connect: Camera > Add new other camera
        'url': 'https://camera-service.prusa3d.com',
        'interval': 30,                # seconds between snapshots: 10, 30 or 60
        'quality': 80,                 # JPEG quality; lowered automatically to stay under 1 MB
    },
    'prusalink': {
        'host': '',                    # the printer's address, e.g. 192.0.2.10
        'user': 'maker',
        'password': '',
        'api_key': '',                 # instead of the password, on firmware that offers one
        'poll_interval': 5,
    },
    'timelapse': {
        'enabled': True,
        'trigger': 'auto',             # udp (slicer snippet), poll (PrusaLink Z), auto (udp, else poll)
        'udp_port': 8514,
        'dwell_ms': 1600,              # the total G4 hold in the slicer snippet
        'settle_ms': 150,              # wait this long after the head stops before the frame
        'fps': 30,
        'quality': 28,                 # H.264 QP (rkmpi) or CRF (ffmpeg): lower is better and bigger
        'keep_cancelled': True,        # upload the video of a cancelled print too
        'storage': '/userdata/layercam/timelapse',
        'min_free_mb': 8,
        'idle_timeout_min': 30,        # without PrusaLink: end a timelapse after this long without frames
    },
    'upload': {
        'target': 'none',              # none, s3, http, smb, nfs
        'keep_local': 2,               # finished videos kept on the camera after upload
        's3_endpoint': 'https://s3.us-east-1.amazonaws.com',
        's3_region': 'us-east-1',
        's3_bucket': '',
        's3_prefix': 'layercam/',
        's3_access_key': '',
        's3_secret_key': '',
        's3_addressing': 'auto',       # auto, path, virtual
        'http_url': '',                # a folder URL ending in /; files are PUT into it (WebDAV works)
        'http_user': '',
        'http_password': '',
        'smb_share': '',               # //192.0.2.20/prints
        'smb_user': '',
        'smb_password': '',
        'smb_dir': 'timelapse',
        'smb_version': '3.0',
        'nfs_export': '',              # 192.0.2.20:/volume1/prints
        'nfs_dir': 'timelapse',
    },
    'camera': {
        'backend': 'rkmpi',            # rkmpi (the C helper), command (any program that writes a JPEG), fake
        'helper': '/usr/bin/layercam-media',
        'iq_dir': '/etc/iqfiles',
        'command': 'ffmpeg -loglevel error -f v4l2 -i /dev/video0 -frames:v 1 -q:v 3 -y {out}',
        'flip': 'none',                # none, h, v, both
        'rotation': 0,                 # reported to Connect only
    },
    'ir': {
        'mode': 'auto',                # auto (LEDs whenever dark), printing (dark and printing), day, night, off
        'dark_v': 0.10,                # light sensor below this for hold_s: night
        'light_v': 0.25,               # above this for hold_s: day
        'hold_s': 5.0,
        'led_duty': 100,               # IR LED brightness, percent
    },
    'web': {
        'port': 80,
        'password': '',                # setup page password (user "admin"); empty = open on the LAN
    },
}

SECRETS = {('wifi', 'password'), ('wifi', 'ap_password'), ('connect', 'token'), ('prusalink', 'password'),
           ('prusalink', 'api_key'), ('upload', 's3_secret_key'), ('upload', 'http_password'),
           ('upload', 'smb_password'), ('web', 'password')}

CHOICES = {
    ('timelapse', 'trigger'): ('udp', 'poll', 'auto'),
    ('upload', 'target'): ('none', 's3', 'http', 'smb', 'nfs'),
    ('upload', 's3_addressing'): ('auto', 'path', 'virtual'),
    ('camera', 'backend'): ('rkmpi', 'command', 'fake'),
    ('camera', 'flip'): ('none', 'h', 'v', 'both'),
    ('ir', 'mode'): ('auto', 'printing', 'day', 'night', 'off'),
    ('connect', 'interval'): (10, 30, 60),
    ('camera', 'rotation'): (0, 90, 180, 270),
}


class ConfigError(ValueError):
    pass


class Config:
    """Typed view of the INI file: cfg.get('connect', 'token')."""

    def __init__(self, values=None, path=None):
        self.path = path
        self.values = {s: dict(keys) for s, keys in DEFAULTS.items()}
        for (s, k), v in (values or {}).items():
            self.set(s, k, v)

    def get(self, section, key):
        return self.values[section][key]

    def set(self, section, key, value):
        if section not in DEFAULTS or key not in DEFAULTS[section]:
            raise ConfigError('unknown setting %s.%s' % (section, key))
        self.values[section][key] = _coerce(DEFAULTS[section][key], value, '%s.%s' % (section, key))

    def section(self, section):
        return dict(self.values[section])

    def public(self):
        """Everything except secrets, which show as set or not (for the setup page)."""
        out = {}
        for s, keys in self.values.items():
            out[s] = {k: (bool(v) if (s, k) in SECRETS else v) for k, v in keys.items()}
        return out

    def errors(self):
        return validate(self)

    def save(self, path=None):
        path = path or self.path
        cp = configparser.ConfigParser(interpolation=None)
        for s, keys in self.values.items():
            cp[s] = {k: _text(v) for k, v in keys.items()}
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        tmp = path + '.tmp'
        # 0600: the file holds the Wi-Fi password and the upload keys
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            cp.write(f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)


def _text(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    return str(v)


def _coerce(default, value, name):
    try:
        if isinstance(default, bool):
            if isinstance(value, bool):
                return value
            s = str(value).strip().lower()
            if s in ('1', 'true', 'yes', 'on'):
                return True
            if s in ('0', 'false', 'no', 'off', ''):
                return False
            raise ValueError(value)
        if isinstance(default, int):
            return int(str(value).strip())
        if isinstance(default, float):
            return float(str(value).strip())
        return str(value).strip()
    except ValueError:
        raise ConfigError('%s: %r is not a %s' % (name, value, type(default).__name__))


def load(path):
    """Read the file; unknown keys are an error (a typo would otherwise be silently ignored)."""
    cfg = Config(path=path)
    if os.path.exists(path):
        cp = configparser.ConfigParser(interpolation=None)
        with open(path) as f:
            cp.read_file(f)
        for s in cp.sections():
            for k, v in cp[s].items():
                cfg.set(s, k, v)
    return cfg


def ensure_fingerprint(cfg):
    """Connect binds the token to the first fingerprint it sees, so it is made
    once, kept in the config file, and never regenerated (Camera Service
    docs, guide/authentication: 16-64 characters, unique and stable)."""
    if not cfg.get('device', 'fingerprint'):
        cfg.set('device', 'fingerprint', secrets.token_hex(16))
        return True
    return False


TOKEN_RE = re.compile(r'^[A-Za-z0-9]{20}$')


def validate(cfg):
    """A list of problems, empty when the settings can be used."""
    e = []
    for (s, k), allowed in CHOICES.items():
        if cfg.get(s, k) not in allowed:
            e.append('%s.%s must be one of %s' % (s, k, ', '.join(str(a) for a in allowed)))
    name = cfg.get('device', 'name')
    if not 1 <= len(name) <= 32:
        e.append('device.name must be 1-32 characters (Connect limit)')
    fp = cfg.get('device', 'fingerprint')
    if fp and not 16 <= len(fp) <= 64:
        e.append('device.fingerprint must be 16-64 characters')
    if cfg.get('connect', 'enabled') and cfg.get('connect', 'token') and not TOKEN_RE.match(cfg.get('connect', 'token')):
        e.append('connect.token must be the 20 letters and digits Connect shows')
    if not 30 <= cfg.get('connect', 'quality') <= 95:
        e.append('connect.quality must be 30-95')
    if cfg.get('wifi', 'password') and not 8 <= len(cfg.get('wifi', 'password')) <= 63:
        e.append('wifi.password must be 8-63 characters (WPA2), or empty for an open network')
    if not 8 <= len(cfg.get('wifi', 'ap_password')) <= 63:
        e.append('wifi.ap_password must be 8-63 characters')
    if len(cfg.get('wifi', 'ssid').encode()) > 32:
        e.append('wifi.ssid is longer than 32 bytes')
    if not 1 <= cfg.get('timelapse', 'udp_port') <= 65535:
        e.append('timelapse.udp_port must be 1-65535')
    if not 1 <= cfg.get('timelapse', 'fps') <= 60:
        e.append('timelapse.fps must be 1-60')
    if not 10 <= cfg.get('timelapse', 'quality') <= 45:
        e.append('timelapse.quality must be 10-45')
    if cfg.get('timelapse', 'settle_ms') >= cfg.get('timelapse', 'dwell_ms'):
        e.append('timelapse.settle_ms must be shorter than timelapse.dwell_ms')
    if cfg.get('timelapse', 'trigger') == 'poll' and not cfg.get('prusalink', 'host'):
        e.append('timelapse.trigger = poll needs prusalink.host')
    if cfg.get('prusalink', 'poll_interval') < 1:
        e.append('prusalink.poll_interval must be at least 1 s')
    if not 0 < cfg.get('ir', 'dark_v') < cfg.get('ir', 'light_v') <= 1.8:
        e.append('ir.dark_v must be below ir.light_v, both within 0-1.8 V')
    if not 0 <= cfg.get('ir', 'led_duty') <= 100:
        e.append('ir.led_duty must be 0-100')
    t = cfg.get('upload', 'target')
    need = {'s3': ('s3_endpoint', 's3_region', 's3_bucket', 's3_access_key', 's3_secret_key'),
            'http': ('http_url',), 'smb': ('smb_share',), 'nfs': ('nfs_export',)}.get(t, ())
    for k in need:
        if not cfg.get('upload', k):
            e.append('upload.%s is needed for upload.target = %s' % (k, t))
    if t == 's3' and not cfg.get('upload', 's3_endpoint').startswith(('https://', 'http://')):
        e.append('upload.s3_endpoint must start with https://')
    if t == 'http' and not cfg.get('upload', 'http_url').startswith(('https://', 'http://')):
        e.append('upload.http_url must start with https:// or http://')
    if t == 'smb' and not re.match(r'^//[^/]+/[^/]+$', cfg.get('upload', 'smb_share')):
        e.append('upload.smb_share must look like //server/share')
    if t == 'nfs' and not re.match(r'^[^:\s]+:/\S*$', cfg.get('upload', 'nfs_export')):
        e.append('upload.nfs_export must look like server:/path')
    if cfg.get('upload', 'keep_local') < 0:
        e.append('upload.keep_local must be 0 or more')
    return e
