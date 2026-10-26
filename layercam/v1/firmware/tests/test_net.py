"""Wi-Fi configuration files."""
import os, tempfile, unittest

from layercam import config, net


class T(unittest.TestCase):
    def test_psk_ieee_vector(self):
        # IEEE 802.11i-2004 Annex H.4 test vector: passphrase "password", SSID "IEEE"
        self.assertEqual(net.wpa_psk('password', 'IEEE'),
                         'f42c6fc52df0ebef9ebb4b90b38a5f902e83fe1b135a70e23aed762e9710a12e')

    def test_supplicant_conf(self):
        t = net.wpa_supplicant_conf('My "Lab" ;#', 'pass word "x"')
        self.assertIn('ssid=%s' % 'My "Lab" ;#'.encode().hex(), t)
        self.assertIn('psk=' + net.wpa_psk('pass word "x"', 'My "Lab" ;#'), t)
        self.assertNotIn('pass word', t)                 # the password itself is not stored
        self.assertIn('key_mgmt=NONE', net.wpa_supplicant_conf('Open', ''))

    def test_files(self):
        c = config.Config({('device', 'fingerprint'): 'abcdef0123456789abcd', ('wifi', 'ssid'): 'Workshop',
                           ('wifi', 'password'): 'correct horse'})
        d = tempfile.mkdtemp()
        files = net.write_files(c, d, serial='3a7c0e1d5b2f4a99')
        self.assertEqual(set(os.listdir(d)), set(files))
        self.assertEqual(os.stat(os.path.join(d, 'wpa_supplicant.conf')).st_mode & 0o777, 0o600)
        ssid, pw = net.ap_credentials('3a7c0e1d5b2f4a99')
        self.assertIn('ssid2=%s' % ssid.encode().hex(), files['hostapd.conf'])
        self.assertIn('wpa_psk=' + net.wpa_psk(pw, ssid), files['hostapd.conf'])
        self.assertIn('address=/#/192.168.4.1', files['dnsmasq.conf'])
        self.assertIn('freq_list=2412 ', files['wpa_supplicant.conf'])        # band 2.4 by default
        self.assertEqual(files['net.env'], 'POWER_SAVE=on\nTX_POWER_MBM=1000\n')

    def test_band_any(self):
        self.assertNotIn('freq_list', net.wpa_supplicant_conf('Lab', 'password1', 'any'))
        self.assertIn('2472', net.wpa_supplicant_conf('Lab', 'password1', '2.4'))
        self.assertNotIn('2484', net.wpa_supplicant_conf('Lab', 'password1', '2.4'))   # channel 14: Japan only

    def test_ap_per_device(self):
        a = net.ap_credentials('3a7c0e1d5b2f4a99')
        self.assertEqual(a, net.ap_credentials('3A7C0E1D5B2F4A99 '))           # same camera, same answer
        self.assertNotEqual(a, net.ap_credentials('3a7c0e1d5b2f4a98'))
        self.assertRegex(a[0], r'^LayerCam-[0-9A-F]{4}$')
        self.assertRegex(a[1], r'^[2-9a-z]{4}-[2-9a-z]{4}-[2-9a-z]{4}$')
        self.assertTrue(8 <= len(a[1]) <= 63)
        self.assertFalse(set(a[1]) & set('01ilo'))
        c = config.Config({('device', 'fingerprint'): 'f' * 32})
        self.assertEqual(net.setup_ap(c, serial='3a7c0e1d5b2f4a99'), a)
        c.set('wifi', 'ap_password', 'my own phrase')
        self.assertEqual(net.setup_ap(c, serial='3a7c0e1d5b2f4a99')[1], 'my own phrase')

    def test_cpu_serial(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'cpuinfo')
        with open(p, 'w') as f:
            f.write('processor\t: 0\nHardware\t: Generic DT based system\nSerial\t\t: 3A7C0E1D5B2F4A99\n')
        self.assertEqual(net.cpu_serial(p), '3a7c0e1d5b2f4a99')
        with open(p, 'w') as f:
            f.write('Serial\t\t: 0000000000000000\n')
        self.assertIsNone(net.cpu_serial(p))                                # an unprogrammed id
        self.assertIsNone(net.cpu_serial(os.path.join(d, 'missing')))

    def test_host_tool(self):
        import subprocess, sys
        tool = os.path.join(os.path.dirname(__file__), '..', 'tools', 'layercam-ap.py')
        out = subprocess.run([sys.executable, tool, '3a7c0e1d5b2f4a99'], capture_output=True, text=True).stdout
        ssid, pw = net.ap_credentials('3a7c0e1d5b2f4a99')
        self.assertIn(ssid, out)
        self.assertIn(pw, out)


if __name__ == '__main__':
    unittest.main()
