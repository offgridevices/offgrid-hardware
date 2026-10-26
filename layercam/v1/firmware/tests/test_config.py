"""Settings: defaults, types, validation, the file, secrets kept back."""
import os, stat, tempfile, unittest

from layercam import config, web


def good():
    return config.Config({('device', 'fingerprint'): 'a' * 32, ('connect', 'token'): 'T0nSPU2v05v0pJeKYFYV',
                          ('wifi', 'ssid'): 'Workshop', ('wifi', 'password'): 'correct horse'})


class T(unittest.TestCase):
    def test_defaults_valid(self):
        self.assertEqual(config.Config().errors(), [])
        self.assertEqual(good().errors(), [])

    def test_example_file_matches_defaults(self):
        # board/layercam.ini.example must list every setting, and only real ones
        ex = os.path.join(os.path.dirname(__file__), '..', 'board', 'layercam.ini.example')
        c = config.load(ex)
        import configparser
        cp = configparser.ConfigParser(interpolation=None)
        cp.read(ex)
        listed = {(s, k) for s in cp.sections() for k in cp[s]}
        every = {(s, k) for s, keys in config.DEFAULTS.items() for k in keys}
        self.assertEqual(listed, every)
        self.assertEqual(c.errors(), [])

    def test_types(self):
        c = config.Config()
        c.set('connect', 'interval', '60')
        self.assertEqual(c.get('connect', 'interval'), 60)
        c.set('connect', 'enabled', 'no')
        self.assertIs(c.get('connect', 'enabled'), False)
        c.set('ir', 'dark_v', '0.05')
        self.assertEqual(c.get('ir', 'dark_v'), 0.05)
        with self.assertRaises(config.ConfigError):
            c.set('connect', 'interval', 'often')
        with self.assertRaises(config.ConfigError):
            c.set('connect', 'nosuch', '1')

    def test_validation(self):
        cases = [
            (('connect', 'token'), 'short', 'connect.token'),
            (('connect', 'interval'), 15, 'connect.interval'),
            (('device', 'name'), 'x' * 33, 'device.name'),
            (('wifi', 'password'), 'short', 'wifi.password'),
            (('wifi', 'ssid'), 'x' * 33, 'wifi.ssid'),
            (('timelapse', 'settle_ms'), 5000, 'settle_ms'),
            (('timelapse', 'trigger'), 'poll', 'prusalink.host'),
            (('ir', 'dark_v'), 0.5, 'ir.dark_v'),
            (('upload', 'target'), 's3', 'upload.s3_bucket'),
            (('upload', 'target'), 'ftp', 'upload.target'),
            (('camera', 'rotation'), 45, 'camera.rotation'),
        ]
        for (s, k), v, expect in cases:
            c = good()
            c.set(s, k, v)
            errs = c.errors()
            self.assertTrue(any(expect in e for e in errs), (s, k, v, errs))

    def test_upload_targets(self):
        c = good()
        c.set('upload', 'target', 'smb')
        c.set('upload', 'smb_share', '192.0.2.20/prints')
        self.assertTrue(any('smb_share' in e for e in c.errors()))
        c.set('upload', 'smb_share', '//192.0.2.20/prints')
        self.assertEqual(c.errors(), [])
        c.set('upload', 'target', 'nfs')
        c.set('upload', 'nfs_export', '192.0.2.20:/volume1/prints')
        self.assertEqual(c.errors(), [])
        c.set('upload', 'target', 'http')
        c.set('upload', 'http_url', 'nas.example/dav/')
        self.assertTrue(any('http_url' in e for e in c.errors()))

    def test_save_load_and_mode(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'sub', 'layercam.ini')
        c = good()
        c.path = p
        c.save()
        self.assertEqual(stat.S_IMODE(os.stat(p).st_mode), 0o600)
        c2 = config.load(p)
        self.assertEqual(c2.values, c.values)
        with open(p, 'a') as f:
            f.write('\n[connect]\ntypo_key = 1\n')
        with self.assertRaises(Exception):
            config.load(p)

    def test_fingerprint_made_once(self):
        c = config.Config()
        self.assertTrue(config.ensure_fingerprint(c))
        fp = c.get('device', 'fingerprint')
        self.assertTrue(16 <= len(fp) <= 64)
        self.assertFalse(config.ensure_fingerprint(c))
        self.assertEqual(c.get('device', 'fingerprint'), fp)

    def test_public_hides_secrets(self):
        p = good().public()
        self.assertIs(p['connect']['token'], True)
        self.assertIs(p['wifi']['password'], True)
        self.assertIs(p['upload']['s3_secret_key'], False)
        self.assertEqual(p['wifi']['ssid'], 'Workshop')

    def test_form(self):
        c = good()
        new, errs = web.apply_form(c, {'wifi.password': '', 'connect.interval': '10', 'device.fingerprint': 'x' * 20})
        self.assertEqual(errs, [])
        self.assertEqual(new.get('wifi', 'password'), 'correct horse')    # empty secret: kept
        self.assertEqual(new.get('connect', 'interval'), 10)
        self.assertEqual(new.get('device', 'fingerprint'), 'a' * 32)       # never from the page
        self.assertEqual(c.get('connect', 'interval'), 30)                 # the old one untouched
        new, errs = web.apply_form(c, {'connect.token': 'bad', 'nosuch': 1})
        self.assertEqual(len(errs), 2)


if __name__ == '__main__':
    unittest.main()
