"""What goes into the image: no default password, no service the owner did
not turn on (pincheck.image_results, which the board build runs too); the
install script on a stand-in SDK; the page refusing to be open on the home
network."""
import base64, os, shutil, subprocess, tempfile, unittest
from unittest import mock

import pincheck
from layercam import config, web

FIRMWARE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def problems(d):
    return [w for ok, w in pincheck.image_results(d) if not ok]


class Image(unittest.TestCase):
    def test_shipped_image_is_clean(self):
        res = pincheck.image_results(FIRMWARE)
        self.assertGreaterEqual(len(res), 20)
        self.assertEqual(problems(FIRMWARE), [])

    def copy(self):
        d = tempfile.mkdtemp()
        shutil.copytree(os.path.join(FIRMWARE, 'board'), os.path.join(d, 'board'))
        return d

    def edit(self, d, path, old, new=None, append=None):
        p = os.path.join(d, path)
        with open(p) as f:
            s = f.read()
        if old is not None:
            self.assertIn(old, s, path)
            s = s.replace(old, new)
        if append:
            s += append
        with open(p, 'w') as f:
            f.write(s)

    def test_check_can_fail(self):
        mk = 'board/sdk/BoardConfig-SPI_NAND-Buildroot-RV1106_LayerCam_v1-IPC.mk'
        cases = [
            (mk, '"overlay-luckfox-wifibt-firmware', '"overlay-luckfox-buildroot-shadow overlay-luckfox-wifibt-firmware',
             None, 'buildroot-shadow not used'),
            (mk, 'firmware overlay-layercam"', 'firmware overlay-layercam overlay-other"', None, 'applied last'),
            ('board/sdk/buildroot.fragment', '# BR2_TARGET_ENABLE_ROOT_LOGIN is not set\n', '', None,
             'Buildroot gives root no password'),
            ('board/sdk/buildroot.fragment', None, None, 'BR2_TARGET_GENERIC_ROOT_PASSWD="luckfox"\n',
             'no root password in the Buildroot fragment'),
            ('board/sdk/buildroot.fragment', None, None, 'BR2_PACKAGE_SAMBA4=y\n', 'no extra servers'),
            ('board/rootfs/etc/shadow', 'root:*:', 'root:$1$dXmV8ZLO$eNAQzSYOgRkYMJRdsHwLS1:', None, '/etc/shadow'),
            ('board/rootfs/etc/ssh/sshd_config', 'PasswordAuthentication no', 'PasswordAuthentication yes', None,
             'passwords refused'),
            ('board/rootfs/etc/ssh/sshd_config', 'PermitRootLogin prohibit-password', 'PermitRootLogin yes', None,
             'root by key only'),
            ('board/rootfs/etc/init.d/S50sshd', '\tif ! enabled; then', '\tif false; then', None,
             'only when turned on'),
            ('board/rootfs/etc/init.d/S49ntp', 'exit 0', '/usr/sbin/ntpd -g', None, 'no ntpd server'),
            ('board/rootfs/etc/init.d/S21appinit', '\tstop) ;;', '\tstop) ;;\n\trun) sh /oem/usr/bin/RkLunch.sh ;;',
             None, 'does not start rkipc'),
            ('board/rootfs/etc/init.d/S50usbdevice', 'mkdir -p $G/functions/acm.usb0',
             'mkdir -p $G/functions/acm.usb0 $G/functions/ffs.adb', None, 'no adb or USB network'),
        ]
        for path, old, new, append, expect in cases:
            d = self.copy()
            self.edit(d, path, old, new, append)
            got = problems(d)
            self.assertTrue(got and all(expect in w for w in got), (path, expect, got))
        d = self.copy()
        os.unlink(os.path.join(d, 'board/rootfs/etc/init.d/S50telnet'))
        self.assertEqual(len(problems(d)), 1)
        d = self.copy()
        os.unlink(os.path.join(d, 'board/rootfs/etc/layercam/usb-id'))
        self.assertTrue(any('USB id' in w for w in problems(d)))

    def test_board_build_gate_includes_it(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('cf', os.path.join(FIRMWARE, '..', 'src', 'check_firmware.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        names = [w for ok, w in mod.run(FIRMWARE)]
        self.assertTrue(any(w.startswith('image: root locked') for w in names))


class InstallScript(unittest.TestCase):
    def sdk(self):
        d = tempfile.mkdtemp()
        for p in ('sysdrv/source/kernel/arch/arm/boot/dts', 'sysdrv/source/kernel/arch/arm/configs',
                  'project/cfg/BoardConfig_IPC', 'sysdrv/tools/board/buildroot'):
            os.makedirs(os.path.join(d, p))
        with open(os.path.join(d, 'sysdrv/tools/board/buildroot/luckfox_pico_defconfig'), 'w') as f:
            f.write('BR2_TARGET_GENERIC_ROOT_PASSWD="luckfox"\nBR2_PACKAGE_DHCPCD=y\nBR2_PACKAGE_OPENSSH=y\n')
        return d

    def install(self, sdk, **env):
        e = dict(os.environ, **env)
        return subprocess.run(['sh', os.path.join(FIRMWARE, 'board', 'install-into-sdk.sh'), sdk],
                              capture_output=True, text=True, env=e)

    def test_install(self):
        sdk = self.sdk()
        pub = os.path.join(sdk, 'update.pub')
        with open(pub, 'w') as f:
            f.write('ab' * 32 + '\n')
        for _ in range(2):                                       # a second run replaces, not appends
            r = self.install(sdk, UPDATE_PUBKEY=pub, USB_ID='1209:abcd')
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(sdk, 'sysdrv/tools/board/buildroot/luckfox_pico_defconfig')) as f:
            dc = f.read()
        self.assertEqual(dc.count('# >>> LayerCam'), 1)
        # the later lines win in a defconfig: root login off, dhcpcd out, the packages in
        self.assertGreater(dc.index('# BR2_TARGET_ENABLE_ROOT_LOGIN is not set'), dc.index('ROOT_PASSWD'))
        self.assertGreater(dc.index('# BR2_PACKAGE_DHCPCD is not set'), dc.index('BR2_PACKAGE_DHCPCD=y'))
        self.assertIn('BR2_PACKAGE_IW=y', dc)
        ovl = os.path.join(sdk, 'project/cfg/BoardConfig_IPC/overlay/overlay-layercam')
        with open(os.path.join(ovl, 'etc/layercam/usb-id')) as f:
            self.assertEqual(f.read().strip(), '1209:abcd')
        with open(os.path.join(ovl, 'etc/layercam/update-keys')) as f:
            self.assertEqual(f.read().count('ab' * 32), 1)
        with open(os.path.join(ovl, 'etc/shadow')) as f:
            self.assertTrue(f.read().startswith('root:*:'))
        self.assertTrue(os.path.isfile(os.path.join(ovl, 'usr/share/layercam/layercam/service.py')))

    def test_usb_id_placeholder_and_bad_id(self):
        sdk = self.sdk()
        r = self.install(sdk)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('1d6b:0104 is a development placeholder', r.stdout)
        self.assertNotEqual(self.install(sdk, USB_ID='12345').returncode, 0)


class PagePassword(unittest.TestCase):
    def handler(self, ip, setup_ap=False, pw=''):
        h = web.Handler.__new__(web.Handler)
        h.client_address = (ip, 50000)
        h.app = mock.Mock(setup_ap=setup_ap, cfg=config.Config({('web', 'password'): pw}))
        h.sent = []
        h._send = lambda code, body, ctype=None: h.sent.append((code, body))
        return h

    def test_open_only_on_the_setup_access_point(self):
        self.assertTrue(self.handler('192.168.4.23', setup_ap=True)._authorised())
        self.assertTrue(self.handler('127.0.0.1')._authorised())
        for h in (self.handler('192.168.1.50'), self.handler('192.168.4.23', setup_ap=False),
                  self.handler('10.0.0.9', setup_ap=True)):
            self.assertFalse(h._authorised())
            self.assertEqual(h.sent[0][0], 403)
            self.assertIn(b'set web.password', h.sent[0][1])

    def test_password_always_asked_once_set(self):
        h = self.handler('192.168.4.23', setup_ap=True, pw='page password')
        h.headers = {'Authorization': 'Basic ' + base64.b64encode(b'admin:page password').decode()}
        self.assertTrue(h._authorised())
        for given in ('admin:wrong', 'not base64 at all!!'):
            h = self.handler('127.0.0.1', pw='page password')
            h.headers = {'Authorization': 'Basic ' + (base64.b64encode(given.encode()).decode()
                                                      if ':' in given else given)}
            codes = []
            h.send_response = codes.append
            h.send_header = h.end_headers = lambda *a: None
            with mock.patch('layercam.web.time.sleep') as slept:
                self.assertFalse(h._authorised())
            self.assertEqual(codes, [401])                       # an answer, even for a broken header
            slept.assert_called_once_with(1.0)

    def test_saving_a_network_needs_a_password(self):
        c = config.Config()
        _, errs = web.apply_form(c, {'wifi.ssid': 'Workshop', 'wifi.password': 'correct horse'})
        self.assertTrue(any(e.startswith('web.password') for e in errs))
        _, errs = web.apply_form(c, {'wifi.ssid': 'Workshop', 'wifi.password': 'correct horse',
                                     'web.password': 'short'})
        self.assertTrue(any('8-128' in e for e in errs))
        _, errs = web.apply_form(c, {'wifi.ssid': 'Workshop', 'wifi.password': 'correct horse',
                                     'web.password': 'a good password'})
        self.assertEqual(errs, [])


if __name__ == '__main__':
    unittest.main()
