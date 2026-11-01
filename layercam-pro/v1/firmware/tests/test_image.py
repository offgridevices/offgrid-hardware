"""What goes into the image: no default password, no service the owner did
not turn on (pincheck.image_results, which the board build runs too); the
install script on a stand-in SDK; the page refusing to be open on the home
network."""
import base64, json, os, shutil, subprocess, tempfile, unittest
from unittest import mock

import pincheck
from layercam import board, config, web

FIRMWARE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
I2C = 'sysdrv/source/kernel/drivers/media/i2c'
# the lines of the SDK's sc4336.c, Kconfig and Makefile (824b817f) that
# tools/sc4336h-port.py relies on (tests/test_sensor_port.py has more)
SENSOR_FILES = {
    'sc4336.c': ('// SPDX-License-Identifier: GPL-2.0\n/*\n * sc4336 driver\n */\n'
                 '#define CHIP_ID\t\t\t\t0xdc42\n#define SC4336_REG_CHIP_ID\t\t0x3107\n'
                 '#define SC4336_NAME\t\t\t"sc4336"\n'
                 'static const struct of_device_id sc4336_of_match[] = {\n\t{ .compatible = "smartsens,sc4336" },\n'
                 '\t{},\n};\n'),
    'Kconfig': ('config VIDEO_SC3336\n\ttristate "SmartSens SC3336 sensor support"\n\n'
                'config VIDEO_SC4336\n\ttristate "SmartSens SC4336 sensor support"\n\n'
                'config VIDEO_SC4336P\n\ttristate "SmartSens SC4336P sensor support"\n'),
    'Makefile': ('obj-$(CONFIG_VIDEO_SC3336) += sc3336.o\nobj-$(CONFIG_VIDEO_SC4336) += sc4336.o\n'
                 'obj-$(CONFIG_VIDEO_SC4336P) += sc4336p.o\n'),
}


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
        mk = 'board/sdk/' + pincheck.BOARD_CONFIG
        cases = [
            (mk, '"overlay-layercam"', '"overlay-luckfox-buildroot-shadow overlay-layercam"',
             None, 'buildroot-shadow not used'),
            (mk, '"overlay-layercam"', '"overlay-layercam overlay-other"', None, 'applied last'),
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
    IQDIR = 'media/isp/release_camera_engine_rkaiq_rv1106_arm-rockchip830-linux-uclibcgnueabihf/isp_iqfiles'

    def sdk(self):
        d = tempfile.mkdtemp()
        for p in ('sysdrv/source/kernel/arch/arm/boot/dts', 'sysdrv/source/kernel/arch/arm/configs',
                  'project/cfg/BoardConfig_IPC', 'sysdrv/tools/board/buildroot', I2C, self.IQDIR):
            os.makedirs(os.path.join(d, p))
        with open(os.path.join(d, 'sysdrv/tools/board/buildroot/luckfox_pico_defconfig'), 'w') as f:
            f.write('BR2_TARGET_GENERIC_ROOT_PASSWD="luckfox"\nBR2_PACKAGE_DHCPCD=y\nBR2_PACKAGE_OPENSSH=y\n')
        for name, text in SENSOR_FILES.items():
            with open(os.path.join(d, I2C, name), 'w') as f:
                f.write(text)
        with open(os.path.join(d, self.IQDIR, 'sc4336_CMK-OT2117-PC1_30IRC-F16.json'), 'w') as f:
            f.write('{"sensor_calib": {}}\n')
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
        # the Pro's parts: the sensor driver ported once, its IQ file, the C6 flasher
        with open(os.path.join(sdk, I2C, 'sc4336h.c')) as f:
            drv = f.read()
        self.assertIn('{ .compatible = "smartsens,sc4336h" }', drv)
        self.assertIn('#define CHIP_ID\t\t\t\t0x10000', drv)                # not read yet: probe only logs it
        with open(os.path.join(sdk, I2C, 'Makefile')) as f:
            self.assertEqual(f.read().count('sc4336h.o'), 1)
        with open(os.path.join(sdk, I2C, 'Kconfig')) as f:
            self.assertEqual(f.read().count('config VIDEO_SC4336H\n'), 1)
        self.assertTrue(os.path.isfile(os.path.join(sdk, self.IQDIR, board.IQ_FILE)))
        self.assertTrue(os.access(os.path.join(ovl, 'usr/bin/layercam-c6-flash'), os.X_OK))
        self.assertTrue(os.path.isfile(os.path.join(sdk, 'sysdrv/source/kernel/arch/arm/boot/dts', pincheck.DTS)))
        self.assertTrue(os.path.isfile(os.path.join(sdk, 'project/cfg/BoardConfig_IPC', pincheck.BOARD_CONFIG)))
        self.assertIn('no ESP_HOSTED_KO', r.stdout)

    def test_install_wifi_and_chip_id(self):
        sdk = self.sdk()
        ko = os.path.join(sdk, 'esp32_sdio.ko')
        with open(ko, 'wb') as f:
            f.write(b'\x7fELF')
        fw = os.path.join(sdk, 'c6build')
        os.makedirs(os.path.join(fw, 'bootloader'))
        files = {'0x0': 'bootloader/bootloader.bin', '0x10000': 'network_adapter.bin'}
        for rel in files.values():
            with open(os.path.join(fw, rel), 'wb') as f:
                f.write(b'\xe9' * 100)
        with open(os.path.join(fw, 'flasher_args.json'), 'w') as f:
            json.dump({'flash_files': files}, f)
        r = self.install(sdk, ESP_HOSTED_KO=ko, C6_FW=fw, SC4336H_CHIP_ID='0x1234')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        ovl = os.path.join(sdk, 'project/cfg/BoardConfig_IPC/overlay/overlay-layercam')
        self.assertTrue(os.path.isfile(os.path.join(ovl, 'lib/modules/esp32_sdio.ko')))
        for rel in ['flasher_args.json'] + list(files.values()):
            self.assertTrue(os.path.isfile(os.path.join(ovl, 'usr/share/layercam-c6', rel)), rel)
        with open(os.path.join(sdk, I2C, 'sc4336h.c')) as f:
            self.assertIn('#define CHIP_ID\t\t\t\t0x1234', f.read())
        # an IQ file already in the SDK (a tuned one) is kept
        iq = os.path.join(sdk, self.IQDIR, board.IQ_FILE)
        with open(iq, 'w') as f:
            f.write('tuned')
        r = self.install(sdk)
        with open(iq) as f:
            self.assertEqual(f.read(), 'tuned')
        # an SDK without sc4336.c cannot make the sensor driver
        os.unlink(os.path.join(sdk, I2C, 'sc4336.c'))
        self.assertNotEqual(self.install(sdk).returncode, 0)

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
