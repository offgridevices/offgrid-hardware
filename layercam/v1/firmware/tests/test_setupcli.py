"""layercam-setup, the USB console: argument parsing, each command against a
settings file in a temporary folder (the service and reboot are fakes), and
the console loop as /dev/ttyGS0 would feed it."""
import io, os, signal, tempfile, unittest
from contextlib import redirect_stdout

from layercam import config, gesture, net, setupcli


class Fake:
    def __init__(self):
        self.signals, self.reboots = [], []

    def kill(self, pid, sig):
        self.signals.append((pid, sig))

    def reboot(self, mode):
        self.reboots.append(mode)
        return True


class Parse(unittest.TestCase):
    def ok(self, *argv):
        return setupcli.parse(list(argv))

    def bad(self, *argv):
        with self.assertRaises(setupcli.Refused) as e:
            setupcli.parse(list(argv))
        return str(e.exception)

    def test_commands(self):
        a = self.ok('wifi', 'My Lab 2.4', 'pass word "x"')
        self.assertEqual((a.cmd, a.ssid, a.password, a.open), ('wifi', 'My Lab 2.4', 'pass word "x"', False))
        a = self.ok('wifi', 'Cafe', '--open')
        self.assertTrue(a.open and a.password is None)
        a = self.ok('set', 'connect.interval', '10')
        self.assertEqual((a.key, a.value), ('connect.interval', '10'))
        self.assertEqual(self.ok('set', 'web.password', '').value, '')
        self.assertEqual(self.ok('set', 'web.password', '--', '-starts-with-dash').value, '-starts-with-dash')
        self.assertTrue(self.ok('update', '/userdata/x.lcup', '--allow-downgrade').allow_downgrade)
        self.assertTrue(self.ok('update', '--status').status)
        self.assertEqual(self.ok('--serve', '/dev/ttyGS0').serve, '/dev/ttyGS0')
        self.assertIsNone(self.ok().cmd)
        for c in ('help', 'status', 'ap', 'version', 'reset-wifi', 'reboot', 'reboot-loader', 'show'):
            self.assertEqual(self.ok(c).cmd, c)

    def test_refused(self):
        self.assertIn('password', self.bad('wifi', 'Lab'))              # no silent open network
        self.assertIn('one or the other', self.bad('wifi', 'Lab', 'pw', '--open'))
        self.assertIn('invalid choice', self.bad('sh'))                  # not a shell
        self.assertIn('section.key', self.bad('get', 'ssid'))
        self.assertIn('section.key', self.bad('set', '../etc/passwd', 'x'))
        self.assertIn('update FILE', self.bad('update'))
        self.assertIn('update FILE', self.bad('update', 'x.lcup', '--factory'))
        self.bad('set', 'wifi.ssid')                                     # value missing
        self.bad('status', 'extra')

    def test_help_lists_every_command(self):
        for c in ('status', 'ap', 'wifi SSID PASSWORD', 'reset-wifi', 'show', 'get', 'set', 'update FILE',
                  'reboot-loader'):
            self.assertIn(c, setupcli.HELP)


class Commands(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.dir = d
        self.root = os.path.join(d, 'root')
        self.path = os.path.join(d, 'layercam.ini')
        config.Config({('device', 'fingerprint'): 'a' * 32, ('wifi', 'ssid'): 'Workshop',
                       ('wifi', 'password'): 'correct horse', ('connect', 'token'): 'T0nSPU2v05v0pJeKYFYV'},
                      path=self.path).save()
        os.makedirs(self.root + net.RUN_DIR)
        with open(self.root + net.RUN_DIR + '/service.pid', 'w') as f:
            f.write('4242\n')
        os.makedirs(self.root + '/proc')
        with open(self.root + '/proc/cpuinfo', 'w') as f:
            f.write('Serial\t\t: 3A7C0E1D5B2F4A99\n')
        self.fake = Fake()
        self.env = setupcli.Env(self.path, root=self.root, kill=self.fake.kill, reboot=self.fake.reboot,
                                factory=os.path.join(d, 'factory'))

    def cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = setupcli.main(list(argv), self.env)
        return code, out.getvalue()

    def cfg(self):
        return config.load(self.path)

    def test_wifi(self):
        code, out = self.cli('wifi', 'Lab Net', 'new password')
        self.assertEqual(code, 0, out)
        self.assertEqual((self.cfg().get('wifi', 'ssid'), self.cfg().get('wifi', 'password')),
                         ('Lab Net', 'new password'))
        self.assertEqual(self.fake.signals, [(4242, signal.SIGHUP)])   # the service starts again with it
        self.assertTrue(net.take_new_network(self.root + net.RUN_DIR))  # and gives it the short fallback
        code, out = self.cli('wifi', 'Lab', 'short')
        self.assertEqual(code, 1)
        self.assertIn('wifi.password must be 8-63', out)
        self.assertEqual(self.cfg().get('wifi', 'ssid'), 'Lab Net')     # nothing saved
        self.assertEqual(self.cli('wifi', 'Cafe', '--open')[0], 0)
        self.assertEqual(self.cfg().get('wifi', 'password'), '')

    def test_set_get_show_never_print_secrets(self):
        self.assertEqual(self.cli('set', 'connect.interval', '10')[0], 0)
        self.assertEqual(self.cfg().get('connect', 'interval'), 10)
        self.assertEqual(self.cli('get', 'connect.interval'), (0, '10\n'))
        self.assertEqual(self.cli('get', 'wifi.password'), (0, '(set)\n'))
        self.assertEqual(self.cli('get', 'web.password'), (0, '(not set)\n'))
        self.assertEqual(self.cli('set', 'web.password', 'a new page password')[0], 0)  # a forgotten one, reset
        code, out = self.cli('show')
        for secret in ('correct horse', 'T0nSPU2v05v0pJeKYFYV', 'a new page password'):
            self.assertNotIn(secret, out)
        self.assertIn('ssid = Workshop', out)
        self.assertIn('[thermal]', out)
        self.assertNotIn('[wifi]', self.cli('show', 'web')[1])
        self.assertEqual(self.cli('set', 'connect.interval', '15')[0], 1)     # validated as on the page
        self.assertEqual(self.cli('set', 'connect.nosuch', '1')[0], 1)
        self.assertEqual(self.cli('set', 'device.fingerprint', 'b' * 32)[0], 1)
        self.assertEqual(self.cfg().get('device', 'fingerprint'), 'a' * 32)

    def test_unknown_keys_survive(self):
        with open(self.path, 'a') as f:
            f.write('[future]\nsetting = 1\n')
        self.assertEqual(self.cli('set', 'connect.interval', '60')[0], 0)
        with open(self.path) as f:
            self.assertIn('setting = 1', f.read())           # a newer version's setting, kept
        self.assertIn('unknown setting future.setting', self.cli('status')[1])

    def test_reset_wifi(self):
        code, out = self.cli('reset-wifi')
        self.assertEqual(code, 0)
        self.assertTrue(gesture.FileStore(self.dir).reset_requested())   # the same request as the gesture
        self.assertEqual(self.fake.signals, [(4242, signal.SIGHUP)])

    def test_ap(self):
        code, out = self.cli('ap')
        ssid, pw = net.ap_credentials('3a7c0e1d5b2f4a99')
        self.assertIn('access point  %s' % ssid, out)
        self.assertIn('passphrase    %s' % pw, out)
        self.cli('set', 'wifi.ap_password', 'my own phrase')
        self.assertNotIn('my own phrase', self.cli('ap')[1])

    def test_status_and_service_down(self):
        os.unlink(self.root + net.RUN_DIR + '/service.pid')
        code, out = self.cli('status')
        self.assertIn('service       not running', out)
        self.assertIn('software', out)
        code, out = self.cli('set', 'connect.interval', '10')
        self.assertIn('used at its next start', out)
        self.assertEqual(self.fake.signals, [])

    def test_reboot_loader(self):
        self.assertEqual(self.cli('reboot-loader')[0], 0)
        self.assertEqual(self.cli('reboot')[0], 0)
        self.assertEqual(self.fake.reboots, ['loader', None])
        self.fake.reboot = lambda mode: False
        self.env.reboot = self.fake.reboot
        self.assertEqual(self.cli('reboot')[0], 1)

    def test_update_refused_without_keys(self):
        p = os.path.join(self.dir, 'x.lcup')
        with open(p, 'wb') as f:
            f.write(b'not a package')
        code, out = self.cli('update', p)
        self.assertEqual(code, 1)
        self.assertIn('no update keys', out)
        self.assertEqual(self.cli('update', '--status')[0], 0)


class Console(unittest.TestCase):
    def test_serve_stream(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, 'layercam.ini')
        config.Config({('wifi', 'password'): 'correct horse', ('wifi', 'ssid'): 'Old'}, path=path).save()
        fake = Fake()
        env = setupcli.Env(path, root=os.path.join(d, 'root'), kill=fake.kill, reboot=fake.reboot)
        lines = ['', 'help', 'wifi "Lab Net" "pass word 1"', 'wifi unbalanced "quote', '/bin/sh',
                 '--serve /dev/ttyGS0', 'set connect.interval 15', 'exit', 'get wifi.ssid']
        out = io.StringIO()
        setupcli.serve_stream(io.StringIO('\n'.join(lines) + '\n'), out, env)
        text = out.getvalue()
        self.assertTrue(text.startswith('\nLayerCam setup console'))
        self.assertEqual(text.count(setupcli.PROMPT), len(lines) + 1)
        self.assertIn('reset-wifi', text)                                   # help
        self.assertIn('No closing quotation', text)
        self.assertIn("invalid choice: '/bin/sh'", text)                    # no shell
        self.assertIn('options only after a command', text)                 # no --serve from inside
        self.assertIn('connect.interval must be one of', text)
        self.assertIn('close the terminal', text)
        self.assertIn('Lab Net\n', text)
        self.assertNotIn('pass word 1', text)                               # no command prints it back
        self.assertEqual(config.load(path).get('wifi', 'password'), 'pass word 1')

    def test_serve_on_a_pty(self):
        """The real loop on a pseudo-terminal, as on /dev/ttyGS0."""
        import pty, threading, select
        master, slave = pty.openpty()
        d = tempfile.mkdtemp()
        env = setupcli.Env(os.path.join(d, 'layercam.ini'), root=os.path.join(d, 'root'))
        t = threading.Thread(target=setupcli.serve, args=(os.ttyname(slave), env), daemon=True)
        t.start()
        os.write(master, b'version\r')
        buf = b''
        while b'software' not in buf:
            r, _, _ = select.select([master], [], [], 5)
            self.assertTrue(r, buf)
            buf += os.read(master, 4096)
        self.assertIn(b'LayerCam v1, software', buf)
        self.assertIn(b'\r\n', buf)                                         # terminal line endings
        os.close(master)
        os.close(slave)


if __name__ == '__main__':
    unittest.main()


def ssh_blob(*fields):
    return b''.join(len(x).to_bytes(4, 'big') + x for x in fields)


def ed25519_line(seed=b'\x07' * 32, comment='me@laptop'):
    from layercam import ed25519
    import base64
    blob = ssh_blob(b'ssh-ed25519', ed25519.public_key(seed))
    return 'ssh-ed25519 %s %s' % (base64.b64encode(blob).decode(), comment), blob


class Ssh(unittest.TestCase):
    """SSH is off until turned on here, with a key; off deletes the keys."""

    def setUp(self):
        d = tempfile.mkdtemp()
        self.path = os.path.join(d, 'layercam.ini')
        config.Config(path=self.path).save()
        self.calls = []
        self.env = setupcli.Env(self.path, root=os.path.join(d, 'root'),
                                sshd=lambda action: self.calls.append(action) or True)
        self.keys = os.path.join(d, 'ssh', 'authorized_keys')

    def cli(self, line):
        import shlex
        out = io.StringIO()
        with redirect_stdout(out):
            code = setupcli.main(shlex.split(line), self.env)
        return code, out.getvalue()

    def test_off_by_default(self):
        self.assertEqual(self.cli('ssh'), (0, 'ssh           off\n'))
        self.assertIn('ssh           off', self.cli('status')[1])

    def test_on_and_off(self):
        line, blob = ed25519_line()
        code, out = self.cli('ssh on ' + line)                  # pasted unquoted: three words
        self.assertEqual(code, 0, out)
        self.assertIn(setupcli.fingerprint(blob), out)
        self.assertIn('ssh           on (keys only)', out)
        self.assertEqual(self.calls, ['restart'])
        self.assertEqual(os.stat(self.keys).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(os.path.dirname(self.keys)).st_mode & 0o777, 0o700)
        with open(self.keys) as f:
            self.assertEqual(f.read(), line + '\n')
        self.cli('ssh on ' + line)                               # the same key twice: once in the file
        other, _ = ed25519_line(b'\x08' * 32, 'phone')
        self.cli('ssh on "%s"' % other)
        with open(self.keys) as f:
            self.assertEqual(f.read().splitlines(), [line, other])
        code, out = self.cli('ssh off')
        self.assertEqual(code, 0)
        self.assertFalse(os.path.exists(self.keys))
        self.assertEqual(self.calls[-1], 'stop')
        self.assertEqual(self.cli('ssh status')[1], 'ssh           off\n')

    def test_refused_keys(self):
        import base64
        line, blob = ed25519_line()
        rsa_1024 = 'ssh-rsa ' + base64.b64encode(ssh_blob(b'ssh-rsa', b'\x01\x00\x01', b'\x00' + b'\xff' * 128)).decode()
        rsa_3072 = 'ssh-rsa ' + base64.b64encode(ssh_blob(b'ssh-rsa', b'\x01\x00\x01', b'\x00' + b'\xff' * 384)).decode()
        wrong_type = 'ssh-rsa ' + line.split()[1]
        bad = {
            'ssh on': 'paste the line',
            'ssh on -----BEGIN OPENSSH PRIVATE KEY----- abc': 'private key',
            'ssh on command="/bin/sh" ' + line: 'paste a public key',
            'ssh on ssh-ed25519 notbase64!!': 'damaged',
            'ssh on ' + wrong_type: 'damaged',
            'ssh on ' + rsa_1024: '2048 bits',
            'ssh off ' + line: 'only goes with',
            'ssh maybe': 'invalid choice',
        }
        for cmd, why in bad.items():
            code, out = self.cli(cmd)
            self.assertNotEqual(code, 0, cmd)
            self.assertIn(why, out, cmd)
        self.assertEqual(self.calls, [])
        self.assertFalse(os.path.exists(self.keys))
        self.assertEqual(self.cli('ssh on ' + rsa_3072)[0], 0)
        self.cli("ssh on %s 'evil\"; rm -rf /'" % line)        # a comment cannot carry anything
        with open(self.keys) as f:
            self.assertTrue(all(set(ln) <= set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/=@._- ')
                                for ln in f.read().splitlines()))

    def test_fingerprint_as_ssh_keygen(self):
        import shutil, subprocess
        if not shutil.which('ssh-keygen'):
            self.skipTest('no ssh-keygen')
        line, blob = ed25519_line()
        p = os.path.join(tempfile.mkdtemp(), 'k.pub')
        with open(p, 'w') as f:
            f.write(line + '\n')
        out = subprocess.run(['ssh-keygen', '-lf', p], capture_output=True, text=True).stdout
        self.assertIn(setupcli.fingerprint(blob), out)
