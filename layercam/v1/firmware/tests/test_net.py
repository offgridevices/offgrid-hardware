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
        files = net.write_files(c, d)
        self.assertEqual(set(os.listdir(d)), set(files))
        self.assertEqual(os.stat(os.path.join(d, 'wpa_supplicant.conf')).st_mode & 0o777, 0o600)
        self.assertIn('ssid2=%s' % 'LayerCam-ABCD'.encode().hex(), files['hostapd.conf'])
        self.assertIn('wpa_psk=' + net.wpa_psk('layercam-setup', 'LayerCam-ABCD'), files['hostapd.conf'])
        self.assertIn('address=/#/192.168.4.1', files['dnsmasq.conf'])


if __name__ == '__main__':
    unittest.main()
