"""App updates: Ed25519 (RFC 8032 vectors, OpenSSL), the package checks
(signature, product, version, hashes, unexpected files), the trial start and
rollback, the init script's question, and an upload to the setup page."""
import io, json, os, shutil, subprocess, tarfile, tempfile, threading, unittest, urllib.request

from layercam import VERSION, config, ed25519, update, web

HERE = os.path.dirname(os.path.abspath(__file__))
FIRMWARE = os.path.join(HERE, '..')
SEED = bytes(range(32))
PUB = ed25519.public_key(SEED)
OTHER = ed25519.public_key(b'\x01' * 32)

# RFC 8032, 7.1: TEST 1, 2, 3 (secret key, public key, message, signature)
RFC8032 = [
    ('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60',
     'd75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a', '',
     'e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b'),
    ('4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb',
     '3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c', '72',
     '92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00'),
    ('c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7',
     'fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025', 'af82',
     '6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a'),
]


def source(version, broken=False):
    """A copy of this layercam/ calling itself version (optionally one that does not import)."""
    d = tempfile.mkdtemp()
    shutil.copytree(os.path.join(FIRMWARE, 'layercam'), os.path.join(d, 'layercam'),
                    ignore=shutil.ignore_patterns('__pycache__'))
    p = os.path.join(d, 'layercam', '__init__.py')
    with open(p) as f:
        s = f.read().replace("VERSION = '%s'" % VERSION, "VERSION = '%s'" % version)
    with open(p, 'w') as f:
        f.write(s)
    if broken:
        with open(os.path.join(d, 'layercam', 'web.py'), 'a') as f:
            f.write('\nthis is not python\n')
    return d


def package(version, seed=SEED, **kw):
    out = os.path.join(tempfile.mkdtemp(), 'layercam-%s.lcup' % version)
    update.build_package(source(version, kw.pop('broken', False)), version, seed, out, **kw)
    return out


def repack(path, change):
    """Rewrite a package's members (dict name -> bytes) through change(); signature not renewed."""
    with tarfile.open(path) as t:
        parts = {m.name: t.extractfile(m).read() for m in t.getmembers()}
    parts = change(parts)
    out = path + '.x.lcup'
    with tarfile.open(out, 'w') as t:
        for name, data in parts.items():
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            t.addfile(ti, io.BytesIO(data))
    return out


class Ed25519(unittest.TestCase):
    def test_rfc8032(self):
        for sk, pk, msg, sig in RFC8032:
            sk, pk, msg, sig = (bytes.fromhex(x) for x in (sk, pk, msg, sig))
            self.assertEqual(ed25519.public_key(sk), pk)
            self.assertEqual(ed25519.sign(sk, msg), sig)
            self.assertTrue(ed25519.verify(pk, msg, sig))
            self.assertFalse(ed25519.verify(pk, msg + b'!', sig))
            bad = bytearray(sig)
            bad[5] ^= 1
            self.assertFalse(ed25519.verify(pk, msg, bytes(bad)))
            self.assertFalse(ed25519.verify(pk, msg, sig[:32] + (int.from_bytes(sig[32:], 'little')
                                                                  + ed25519.L).to_bytes(32, 'little')))  # s >= L
        self.assertFalse(ed25519.verify(b'\x00' * 31, b'', b'\x00' * 64))

    def test_against_openssl(self):
        d = tempfile.mkdtemp()
        key, msg, sig = (os.path.join(d, n) for n in ('k.pem', 'msg', 'sig'))
        try:
            subprocess.run(['openssl', 'genpkey', '-algorithm', 'ed25519', '-out', key], check=True,
                           capture_output=True)
            der = subprocess.run(['openssl', 'pkey', '-in', key, '-outform', 'DER'], check=True,
                                 capture_output=True).stdout
            with open(msg, 'wb') as f:
                f.write(b'LayerCam manifest bytes')
            subprocess.run(['openssl', 'pkeyutl', '-sign', '-inkey', key, '-rawin', '-in', msg, '-out', sig],
                           check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest('openssl with Ed25519 not available')
        seed = der[-32:]
        with open(sig, 'rb') as f:
            theirs = f.read()
        self.assertEqual(ed25519.sign(seed, b'LayerCam manifest bytes'), theirs)
        self.assertTrue(ed25519.verify(ed25519.public_key(seed), b'LayerCam manifest bytes', theirs))


class Package(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.good = package('0.3.0')

    def refused(self, path, why, keys=(PUB,), current='0.2.0', **kw):
        with self.assertRaises(update.UpdateError) as e:
            m, p = update.read_package(path, list(keys))
            update.check_compatible(m, current, kw.get('rootfs', 1), kw.get('allow_downgrade', False))
            update.extract_payload(p, m, tempfile.mkdtemp())
        self.assertIn(why, str(e.exception))

    def test_good(self):
        m, payload = update.read_package(self.good, [OTHER, PUB])
        self.assertEqual((m['version'], m['product'], m['min_rootfs']), ('0.3.0', 'LayerCam v1', 1))
        self.assertIn('layercam/service.py', m['files'])
        self.assertFalse(any('__pycache__' in n or n.endswith('.pyc') for n in m['files']))
        update.check_compatible(m, '0.2.0', 1)
        d = tempfile.mkdtemp()
        update.extract_payload(payload, m, d)
        self.assertEqual(update.version_of(d), '0.3.0')

    def test_refused(self):
        self.refused(self.good, 'no update keys', keys=())
        self.refused(self.good, 'not signed by a key this camera trusts', keys=(OTHER,))
        self.refused(package('0.3.0', seed=b'\x01' * 32), 'not signed by a key this camera trusts')
        self.refused(self.good, 'already running', current='0.3.0')
        self.refused(self.good, 'older', current='0.10.0')                       # 0.10 > 0.3, numerically
        self.refused(package('0.4.0', min_rootfs=2), 'newer system image')
        self.refused(package('0.3.0', product='LayerCam v2'), "for 'LayerCam v2'")

    def test_downgrade_when_asked(self):
        m, _ = update.read_package(self.good, [PUB])
        update.check_compatible(m, '0.4.0', 1, allow_downgrade=True)

    def test_tampering(self):
        def manifest(parts):
            m = json.loads(parts['manifest.json'])
            m['min_rootfs'] = 0
            parts['manifest.json'] = json.dumps(m, sort_keys=True, separators=(',', ':')).encode()
            return parts
        self.refused(repack(self.good, manifest), 'not signed')

        def payload(parts):
            parts['app.tar'] = parts['app.tar'].replace(b'LayerCam', b'LayerCan', 1)
            return parts
        self.refused(repack(self.good, payload), 'payload does not match')

        def extra(parts):
            parts['install.sh'] = b'rm -rf /'
            return parts
        self.refused(repack(self.good, extra), 'unexpected install.sh')
        self.refused(repack(self.good, lambda p: {k: v for k, v in p.items() if k != 'manifest.sig'}),
                     'missing parts')
        junk = os.path.join(tempfile.mkdtemp(), 'junk.lcup')
        with open(junk, 'wb') as f:
            f.write(os.urandom(5000))
        self.refused(junk, 'not a LayerCam package')

    def test_signed_but_unsafe_payload(self):
        """Even a package signed with the right key cannot write outside its folder."""
        for name in ('layercam/../../etc/evil.py', '/etc/evil.py', 'other/x.py'):
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode='w') as t:
                ti = tarfile.TarInfo(name)
                ti.size = 1
                t.addfile(ti, io.BytesIO(b'x'))
            payload = buf.getvalue()
            m = {'files': {name: update._sha(b'x')}}
            with self.assertRaises(update.UpdateError):
                update.extract_payload(payload, m, tempfile.mkdtemp())

    def test_sign_tool(self):
        d = tempfile.mkdtemp()
        tool = os.path.join(FIRMWARE, 'tools', 'layercam-sign.py')
        key, out = os.path.join(d, 'update.key'), os.path.join(d, 'u.lcup')
        r = subprocess.run(['python3', tool, 'keygen', key], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.stat(key).st_mode & 0o777, 0o600)
        r = subprocess.run(['python3', tool, 'pack', key, out], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run(['python3', tool, 'verify', os.path.join(d, 'update.pub'), out],
                           capture_output=True, text=True)
        self.assertIn('good: LayerCam v1 version %s' % VERSION, r.stdout)
        self.assertEqual(len(update.load_keys(os.path.join(d, 'update.pub'))), 1)
        r = subprocess.run(['python3', tool, 'keygen', key], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)                                     # never overwrites a key

    def test_keys_file(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'update-keys')
        with open(p, 'w') as f:
            f.write('# comment\n%s  # release key\nnot hex\n%s\n\n%s\n' % (PUB.hex(), 'ab' * 16, OTHER.hex()))
        self.assertEqual(update.load_keys(p), [PUB, OTHER])     # broken and short lines add nothing
        self.assertEqual(update.load_keys(os.path.join(d, 'missing')), [])
        shipped = os.path.join(FIRMWARE, 'board', 'rootfs', 'etc', 'layercam', 'update-keys')
        self.assertEqual(update.load_keys(shipped), [])          # no key in the repository
        self.assertEqual(update.rootfs_version(os.path.join(FIRMWARE, 'board', 'rootfs', 'etc', 'layercam',
                                                            'rootfs-version')), 1)


class Store(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.factory = os.path.join(d, 'factory')
        self.store = update.AppStore(os.path.join(d, 'app'), self.factory)

    def install(self, version, current='0.2.0', **kw):
        return self.store.install(package(version, broken=kw.pop('broken', False)), [PUB], current, **kw)

    def test_trial_then_kept(self):
        self.assertEqual(self.store.select(), self.factory)                  # nothing installed
        self.assertEqual(self.install('0.3.0'), '0.3.0')
        slot = self.store.slot('0.3.0')
        self.assertEqual(self.store.would_run(), slot)
        self.assertEqual(self.store.select(), slot)
        self.assertEqual(self.store.state()['tries'], 1)
        self.assertTrue(self.store.running_trial(slot))
        self.assertFalse(self.store.mark_good(self.factory))                 # only the copy on trial
        self.assertTrue(self.store.mark_good(slot))
        st = self.store.state()
        self.assertEqual((st['good'], st['pending'], st['tries']), ('0.3.0', None, 0))
        self.assertEqual(self.store.select(), slot)
        self.assertEqual(self.store.state()['tries'], 0)                     # no writes once kept

    def test_rollback_after_failed_starts(self):
        self.install('0.3.0')
        self.store.mark_good(self.store.select())
        self.install('0.4.0', current='0.3.0')
        new = self.store.slot('0.4.0')
        for _ in range(update.MAX_TRIES):                                     # it crashes every time
            self.assertEqual(self.store.select(), new)
        self.assertEqual(self.store.select(), self.store.slot('0.3.0'))      # back to the last good one
        st = self.store.state()
        self.assertEqual(st['failed'], ['0.4.0'])
        self.assertIn('did not stay up', st['last'])
        self.assertEqual(self.store.select(), self.store.slot('0.3.0'))

    def test_first_update_fails_back_to_factory(self):
        self.install('0.3.0')
        for _ in range(update.MAX_TRIES + 1):
            run = self.store.select()
        self.assertEqual(run, self.factory)

    def test_broken_code_never_installed(self):
        with self.assertRaises(update.UpdateError) as e:
            self.install('0.3.0', broken=True)
        self.assertIn('does not start', str(e.exception))
        self.assertEqual(self.store.state()['pending'], None)
        self.assertFalse(os.path.exists(self.store.slot('0.3.0')))
        self.assertFalse(os.path.exists(self.store.slot('0.3.0') + '.new'))

    def test_missing_slot_and_factory_reset(self):
        self.install('0.3.0')
        self.store.mark_good(self.store.select())
        shutil.rmtree(self.store.slot('0.3.0'))
        self.assertEqual(self.store.select(), self.factory)
        self.install('0.3.1')
        self.store.factory_reset()
        self.assertEqual(self.store.select(), self.factory)

    def test_init_script_question(self):
        out = subprocess.run(['python3', '-m', 'layercam.update', 'select', '--root', self.store.root,
                              '--factory', self.factory], cwd=FIRMWARE, capture_output=True, text=True).stdout
        self.assertEqual(out.strip(), self.factory)
        os.makedirs(self.store.root, exist_ok=True)
        with open(self.store.state_path, 'w') as f:
            f.write('{broken')                                               # whatever is there, it starts
        out = subprocess.run(['python3', '-m', 'layercam.update', 'select', '--root', self.store.root,
                              '--factory', self.factory], cwd=FIRMWARE, capture_output=True, text=True).stdout
        self.assertEqual(out.strip(), self.factory)


class FakeApp:
    """What web.py needs of the service for /api/update."""

    def __init__(self, d):
        self.cfg = config.Config()
        self.cfg_dir = d
        self.apps = update.AppStore(os.path.join(d, 'app'), os.path.join(d, 'factory'))
        self.restarted = threading.Event()

    def install_update(self, path):
        try:
            return True, 'version %s installed' % self.apps.install(path, [PUB], '0.2.0')
        except update.UpdateError as e:
            return False, str(e)

    def on_camera_layout(self):
        return True

    def restart(self, reselect=False):
        self.reselect = reselect
        self.restarted.set()


class Upload(unittest.TestCase):
    def test_page_upload(self):
        d = tempfile.mkdtemp()
        app = FakeApp(d)
        srv = web.serve(app, 0)
        base = 'http://127.0.0.1:%d' % srv.server_port
        try:
            def post(body):
                req = urllib.request.Request(base + '/api/update', data=body, method='POST',
                                             headers={'Content-Type': 'application/octet-stream'})
                try:
                    r = urllib.request.urlopen(req, timeout=60)
                    return r.status, json.loads(r.read())
                except urllib.error.HTTPError as e:
                    return e.code, json.loads(e.read())
            code, j = post(b'rubbish')
            self.assertEqual((code, j['ok']), (400, False))
            self.assertIn('not a LayerCam package', j['error'])
            with open(package('0.3.0'), 'rb') as f:
                code, j = post(f.read())
            self.assertEqual((code, j['ok']), (200, True), j)
            self.assertTrue(app.restarted.wait(5))
            self.assertTrue(app.reselect)                                     # exits for the launcher
            st = json.loads(urllib.request.urlopen(base + '/api/update', timeout=5).read())
            self.assertEqual((st['running'], st['trial']), (VERSION, True))
            self.assertFalse(os.path.exists(os.path.join(d, 'app', 'incoming.lcup')))
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == '__main__':
    unittest.main()
