"""Wi-Fi without a button: when the setup access point opens and closes
(net.WifiSupervisor, on a fake clock), the phones-on-the-AP count, and the
service driving layercam-net (a stand-in script that records its calls)."""
import os, stat, tempfile, unittest
from unittest import mock

from layercam import config, net, service

MIN = 60.0


def run(sup, start, end, link=lambda t: False, clients=lambda t: 0, step=1.0):
    """Feed the supervisor once a second from start to end; -> [(t, mode)] at each change."""
    changes, t, last = [], start, None
    while t <= end:
        m = sup.feed(t, link(t) if last == 'sta' or last is None else False, clients(t))
        if m != last:
            changes.append((t, m))
            last = m
        t += step
    return changes


class Supervisor(unittest.TestCase):
    def test_first_boot_is_the_access_point(self):
        s = net.WifiSupervisor(have_network=False)
        self.assertEqual(run(s, 0, 3600), [(0, 'ap')])                    # until a network is saved
        self.assertEqual(s.reason, 'setup')

    def test_connected_stays_on_the_network(self):
        s = net.WifiSupervisor(True)
        self.assertEqual(run(s, 0, 3 * 3600, link=lambda t: t >= 8), [(0, 'sta')])
        self.assertTrue(s.connected)

    def test_unreachable_for_ten_minutes_opens_the_access_point(self):
        s = net.WifiSupervisor(True, fallback_s=10 * MIN, retry_s=120)
        ch = run(s, 0, 10 * MIN + 30)
        self.assertEqual(ch, [(0, 'sta'), (10 * MIN, 'ap')])               # not a second earlier
        self.assertEqual(s.reason, 'fallback')

    def test_retries_alongside_the_access_point(self):
        s = net.WifiSupervisor(True, fallback_s=10 * MIN, retry_s=120)
        ch = run(s, 0, 10 * MIN + 400)
        w = net.WifiSupervisor.RETRY_WINDOW_S
        self.assertEqual(ch, [(0, 'sta'), (600, 'ap'), (720, 'sta'), (720 + w, 'ap'),
                              (720 + w + 120, 'sta'), (720 + 2 * w + 120, 'ap')])

    def test_connected_on_a_retry_closes_the_access_point(self):
        s = net.WifiSupervisor(True, fallback_s=10 * MIN, retry_s=120)
        router_back = 700
        ch = run(s, 0, 3 * 3600, link=lambda t: t >= router_back + 100)    # the router needed a while
        self.assertEqual(ch[-1][1], 'sta')
        self.assertEqual([m for _, m in ch], ['sta', 'ap', 'sta', 'ap', 'sta'])
        self.assertTrue(s.connected and s.reason is None)
        # it drops again later: the full ten minutes again before the access point
        ch = run(s, 4 * 3600, 4 * 3600 + 11 * MIN)
        self.assertEqual(ch, [(4 * 3600, 'sta'), (4 * 3600 + 10 * MIN, 'ap')])

    def test_a_phone_on_the_access_point_is_not_cut_off(self):
        s = net.WifiSupervisor(True, fallback_s=10 * MIN, retry_s=120)
        on_page = lambda t: 1 if t < 1500 else 0                           # someone setting it up
        ch = run(s, 0, 1600, clients=on_page)
        self.assertEqual(ch[:2], [(0, 'sta'), (600, 'ap')])
        self.assertTrue(all(t >= 1500 for t, m in ch[2:]))                # no retry while they are on it
        self.assertEqual(ch[2][1], 'sta')
        self.assertLessEqual(ch[2][0], 1500 + net.WifiSupervisor.BUSY_RECHECK_S)

    def test_new_network_gets_two_minutes(self):
        s = net.WifiSupervisor(True, fallback_s=10 * MIN, new_network=True)
        self.assertEqual(run(s, 0, 130), [(0, 'sta'), (120, 'ap')])        # mistyped password: back soon

    def test_new_network_that_works_gets_the_full_time_later(self):
        s = net.WifiSupervisor(True, fallback_s=10 * MIN, new_network=True)
        run(s, 0, 60, link=lambda t: t >= 20)
        ch = run(s, 1000, 1000 + 9 * MIN)
        self.assertEqual(ch, [(1000, 'sta')])

    def test_fallback_off(self):
        s = net.WifiSupervisor(True, fallback_s=0)
        self.assertEqual(run(s, 0, 24 * 3600, step=10), [(0, 'sta')])

    def test_settings(self):
        c = config.Config()
        self.assertEqual((c.get('wifi', 'fallback_ap_min'), c.get('wifi', 'retry_s')), (10, 120))
        c.set('wifi', 'retry_s', 5)
        self.assertTrue(any('wifi.retry_s' in e for e in c.errors()))
        c = config.Config({('wifi', 'fallback_ap_min'): -1})
        self.assertTrue(any('fallback_ap_min' in e for e in c.errors()))


class Clients(unittest.TestCase):
    def test_station_dump(self):
        class R:
            stdout = ('Station 4a:11:22:33:44:55 (on wlan0)\n\tinactive time:\t30 ms\n'
                      'Station 02:aa:bb:cc:dd:ee (on wlan0)\n\tsignal:  -40 dBm\n')
        self.assertEqual(net.ap_clients(run=lambda *a, **k: R), 2)

        def missing(*a, **k):
            raise OSError('no iw')
        self.assertEqual(net.ap_clients(run=missing), 0)

    def test_new_network_marker(self):
        d = tempfile.mkdtemp()
        self.assertFalse(net.take_new_network(d))
        net.mark_new_network(d)
        self.assertTrue(net.take_new_network(d))
        self.assertFalse(net.take_new_network(d))           # once: a reboot or the next start forgets it


class ServiceDrivesTheScript(unittest.TestCase):
    def test_start_ap_and_sta(self):
        d = tempfile.mkdtemp()
        root = os.path.join(d, 'root')
        os.makedirs(root + '/usr/bin')
        calls = os.path.join(d, 'calls')
        script = root + '/usr/bin/layercam-net'
        with open(script, 'w') as f:
            f.write('#!/bin/sh\necho "$1" >> %s\n' % calls)
        os.chmod(script, os.stat(script).st_mode | stat.S_IXUSR)
        cfg = config.Config({('timelapse', 'storage'): os.path.join(d, 'tl'), ('wifi', 'ssid'): 'Workshop',
                             ('wifi', 'password'): 'correct horse', ('device', 'fingerprint'): 'f' * 32},
                            path=os.path.join(d, 'layercam.ini'))
        cfg.save()
        svc = service.Service(cfg.path, port=0, hw_root=root)
        self.assertTrue(svc.start_ap())
        self.assertTrue(svc.start_sta())
        with open(calls) as f:
            self.assertEqual(f.read().split(), ['ap', 'sta'])
        files = os.listdir(root + net.RUN_DIR)
        self.assertIn('hostapd.conf', files)
        self.assertIn('wpa_supplicant.conf', files)
        # a restart for other settings: already on this network with the same files, so left alone
        with mock.patch('layercam.net.interface_info', return_value={'wifi_ipv4': '192.0.2.40'}):
            self.assertTrue(svc.start_sta(keep=True))
            self.assertTrue(svc.start_ap(keep=True))           # on the network, not the AP: switched
        with mock.patch('layercam.net.interface_info', return_value={'wifi_ipv4': net.AP_ADDRESS}):
            self.assertTrue(svc.start_ap(keep=True))           # the AP already up: a phone on it stays
            self.assertTrue(svc.start_sta(keep=True))          # leaving the AP always switches
            svc.cfg.set('wifi', 'ssid', 'Other')
            self.assertTrue(svc.start_ap(keep=True))           # files changed: switched
        with open(calls) as f:
            self.assertEqual(f.read().split(), ['ap', 'sta', 'ap', 'sta', 'ap'])
        os.unlink(script)
        self.assertFalse(svc.start_ap())                     # no script: reported, not raised


if __name__ == '__main__':
    unittest.main()
