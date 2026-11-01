"""Wi-Fi: join the home network, or open the setup access point.

The Python side decides (WifiSupervisor) and writes the configuration
files; board/rootfs/usr/bin/layercam-net starts wpa_supplicant + udhcpc, or
hostapd + dnsmasq, from them.  The network name is written as hex and the passphrase as the derived
256-bit PSK (what wpa_passphrase prints), so no character in either can
break the file, and the password itself is not stored in it.
"""
import hashlib, hmac, os, socket, struct, subprocess

RUN_DIR = '/tmp/layercam'
AP_ADDRESS = '192.168.4.1'
# 2.4 GHz channels 1-13 (wifi.band = 2.4).  The ESP32-C6 is a 2.4 GHz-only
# radio, so on the Pro the setting changes nothing; kept from LayerCam v1,
# where it kept the AP6256 off 5 GHz
FREQ_2G4 = ' '.join(str(2412 + 5 * i) for i in range(13))
# setup access point: hostapd's control socket, where ap_clients() asks for
# the phones joined (esp-hosted's driver has no station dump for iw)
HOSTAPD_CTRL = '/var/run/hostapd'

# The setup access point's name and passphrase come from the SoC's serial
# number (the RV1106's OTP id, which the kernel's rockchip-cpuinfo driver
# shows as "Serial" in /proc/cpuinfo), so every camera has its own and
# tools/layercam-ap.py can print them from the serial.  The key only makes
# the result specific to this use; the secret is the serial, which never
# leaves the camera except over its USB cable or serial console.
AP_KEY = b'OffGrid LayerCam Pro v1 setup access point'
AP_ALPHABET = '23456789abcdefghjkmnpqrstuvwxyz'      # no 0/o, 1/l/i: read off a screen


def cpu_serial(cpuinfo='/proc/cpuinfo'):
    try:
        with open(cpuinfo) as f:
            for line in f:
                k, _, v = line.partition(':')
                if k.strip() == 'Serial' and v.strip().strip('0'):
                    return v.strip().lower()
    except OSError:
        pass
    return None


def ap_credentials(device_id):
    """-> (SSID, passphrase): LayerCam-XXXX, xxxx-xxxx-xxxx (12 characters
    from 31: 59 bits)."""
    d = hmac.new(AP_KEY, device_id.strip().lower().encode(), hashlib.sha256).digest()
    n = int.from_bytes(d, 'big')
    chars = []
    for _ in range(12):
        n, r = divmod(n, len(AP_ALPHABET))
        chars.append(AP_ALPHABET[r])
    pw = '-'.join(''.join(chars[i:i + 4]) for i in (0, 4, 8))
    return 'LayerCam-%s' % d[-2:].hex().upper(), pw


def wpa_psk(passphrase, ssid):
    """IEEE 802.11i: PBKDF2-HMAC-SHA1(passphrase, ssid, 4096 rounds, 32 bytes)."""
    return hashlib.pbkdf2_hmac('sha1', passphrase.encode(), ssid.encode(), 4096, 32).hex()


def wpa_supplicant_conf(ssid, password, band='any'):
    lines = ['ctrl_interface=/var/run/wpa_supplicant', 'update_config=0', '', 'network={',
             '    ssid=%s' % ssid.encode().hex(), '    scan_ssid=1']
    if band == '2.4':
        lines.append('    freq_list=%s' % FREQ_2G4)
    if password:
        lines += ['    key_mgmt=WPA-PSK', '    psk=%s' % wpa_psk(password, ssid)]
    else:
        lines += ['    key_mgmt=NONE']
    lines += ['}', '']
    return '\n'.join(lines)


def hostapd_conf(ssid, passphrase, channel=6):
    return '\n'.join([
        'interface=wlan0', 'driver=nl80211', 'ctrl_interface=%s' % HOSTAPD_CTRL,
        'ssid2=%s' % ssid.encode().hex(), 'hw_mode=g',
        'channel=%d' % channel, 'ieee80211n=1', 'wmm_enabled=1', 'auth_algs=1',
        'wpa=2', 'wpa_key_mgmt=WPA-PSK', 'rsn_pairwise=CCMP',
        'wpa_psk=%s' % wpa_psk(passphrase, ssid), ''])


def dnsmasq_conf():
    # every name resolves to the camera, so a phone's "sign in to network"
    # check lands on the setup page
    return '\n'.join(['interface=wlan0', 'bind-interfaces', 'dhcp-range=192.168.4.10,192.168.4.60,255.255.255.0,1h',
                      'dhcp-option=3,%s' % AP_ADDRESS, 'address=/#/%s' % AP_ADDRESS, 'no-resolv', ''])


def setup_ap(cfg, serial=None):
    """(SSID, passphrase) of this camera's setup access point.  Without a
    readable serial the fingerprint (random, made on the first boot) stands
    in: then only the serial console shows the passphrase."""
    device_id = serial or cpu_serial() or cfg.get('device', 'fingerprint') or 'layercam'
    ssid, pw = ap_credentials(device_id)
    return ssid, cfg.get('wifi', 'ap_password') or pw


def net_env(cfg):
    """Settings layercam-net applies once associated (iw)."""
    return 'POWER_SAVE=%s\nTX_POWER_MBM=%d\n' % ('on' if cfg.get('wifi', 'power_save') else 'off',
                                                   cfg.get('wifi', 'tx_power_dbm') * 100)


def write_files(cfg, run_dir=RUN_DIR, serial=None):
    os.makedirs(run_dir, exist_ok=True)
    ap_name, ap_pw = setup_ap(cfg, serial)
    files = {
        'wpa_supplicant.conf': wpa_supplicant_conf(cfg.get('wifi', 'ssid'), cfg.get('wifi', 'password'),
                                                   cfg.get('wifi', 'band')),
        'hostapd.conf': hostapd_conf(ap_name, ap_pw),
        'dnsmasq.conf': dnsmasq_conf(),
        'net.env': net_env(cfg),
    }
    for name, text in files.items():
        p = os.path.join(run_dir, name)
        fd = os.open(p + '.tmp', os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(text)
        os.replace(p + '.tmp', p)
    return files


def switch(mode, script='/usr/bin/layercam-net'):
    """mode: 'sta' (join the network) or 'ap' (setup access point)."""
    try:
        return subprocess.run([script, mode], timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def hostapd_stations(ifname='wlan0', ctrl_dir=HOSTAPD_CTRL, timeout=1.0, limit=64):
    """Stations hostapd has associated, from its control socket (STA-FIRST,
    STA-NEXT: what hostapd_cli list_sta asks, the SDK installs no
    hostapd_cli); None when there is no socket to ask."""
    import tempfile
    path = os.path.join(ctrl_dir, ifname)
    if not os.path.exists(path):
        return None
    d = tempfile.mkdtemp(prefix='layercam-hostapd-')
    s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        s.bind(os.path.join(d, 'c'))
        s.settimeout(timeout)
        s.connect(path)
        n, cmd = 0, b'STA-FIRST'
        while n < limit:
            s.send(cmd)
            reply = s.recv(4096)
            mac = reply.split(b'\n', 1)[0].strip()
            if not mac or reply.startswith((b'FAIL', b'UNKNOWN')):
                break
            n += 1
            cmd = b'STA-NEXT ' + mac
        return n
    except OSError:
        return None
    finally:
        s.close()
        try:
            os.unlink(os.path.join(d, 'c'))
        except OSError:
            pass
        os.rmdir(d)


def ap_clients(ifname='wlan0', run=subprocess.run, ctrl_dir=HOSTAPD_CTRL):
    """Phones joined to the setup access point: hostapd's own list, else iw's
    station dump (which esp-hosted's cfg80211 driver does not implement); 0
    when unknown."""
    n = hostapd_stations(ifname, ctrl_dir)
    if n is not None:
        return n
    try:
        out = run(['iw', 'dev', ifname, 'station', 'dump'], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return 0
    return sum(1 for line in out.splitlines() if line.startswith('Station '))


NEW_NETWORK = 'new-network'


def mark_new_network(run_dir=RUN_DIR):
    """The network was just changed (page, USB console): give it a shorter
    time to prove itself before the setup access point comes back.  In
    /tmp: survives the service's restart, not a reboot."""
    try:
        os.makedirs(run_dir, exist_ok=True)
        with open(os.path.join(run_dir, NEW_NETWORK), 'w') as f:
            f.write('1\n')
    except OSError:
        pass


def take_new_network(run_dir=RUN_DIR):
    p = os.path.join(run_dir, NEW_NETWORK)
    try:
        os.unlink(p)
        return True
    except OSError:
        return False


class WifiSupervisor:
    """Which mode the Wi-Fi should be in: 'sta' (join the saved network) or
    'ap' (the setup access point).  Pure: the caller passes the time and
    what it sees, so the timing is tested on a PC.

    - No network saved (first boot, after the power-cycle gesture or
      layercam-setup reset-wifi): the access point, until one is saved.
    - Network saved: join it.  Not connected for fallback_s (wifi.
      fallback_ap_min; new_fallback_s for a network just entered, which may
      be mistyped): the access point opens, and every retry_s, while no
      phone is on it, the camera tries the saved network again for
      RETRY_WINDOW_S.  Connected: the access point stays off.

    One radio, so "alongside" means taking turns: whether esp-hosted can be
    an access point and a station at once is not tried."""
    RETRY_WINDOW_S = 45          # association, DHCP (udhcpc tries for 30 s)
    BUSY_RECHECK_S = 30          # a phone is on the access point: look again this soon

    def __init__(self, have_network, fallback_s=600, retry_s=120, new_network=False, new_fallback_s=120):
        self.have_network = have_network
        self.fallback_s, self.retry_s = fallback_s, retry_s
        self.limit = min(new_fallback_s, fallback_s) if new_network and fallback_s else fallback_s
        self.mode = 'sta' if have_network else 'ap'
        self.reason = None if have_network else 'setup'
        self.offline_since = None
        self.next_retry = None
        self.retry_until = None
        self.connected = False

    def feed(self, now, link_up, ap_clients=0):
        if not self.have_network:
            return 'ap'
        if self.mode == 'sta':
            if link_up:
                self.connected = True
                self.offline_since = self.retry_until = self.reason = None
                self.limit = self.fallback_s        # this network works: the full time from now on
                return 'sta'
            self.connected = False
            if self.retry_until is not None:          # a turn away from the access point
                if now >= self.retry_until:
                    self.mode, self.retry_until, self.next_retry = 'ap', None, now + self.retry_s
                return self.mode
            if self.offline_since is None:
                self.offline_since = now
            if self.limit > 0 and now - self.offline_since >= self.limit:
                self.mode, self.reason, self.next_retry = 'ap', 'fallback', now + self.retry_s
            return self.mode
        # the access point is on, a network is saved: try it now and then
        if now >= self.next_retry:
            if ap_clients:
                self.next_retry = now + self.BUSY_RECHECK_S   # someone is on the setup page
            else:
                self.mode, self.retry_until = 'sta', now + self.RETRY_WINDOW_S
        return self.mode


def interface_info(ifname='wlan0'):
    """{'wifi_ipv4', 'wifi_mac'} as far as they can be read; for Connect's camera info."""
    out = {}
    try:
        with open('/sys/class/net/%s/address' % ifname) as f:
            out['wifi_mac'] = f.read().strip()
    except OSError:
        pass
    try:
        import fcntl
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # SIOCGIFADDR
            res = fcntl.ioctl(s.fileno(), 0x8915, struct.pack('256s', ifname.encode()[:15]))
            out['wifi_ipv4'] = socket.inet_ntoa(res[20:24])
    except (OSError, ImportError):
        pass
    return out


def link_up(ifname='wlan0'):
    return 'wifi_ipv4' in interface_info(ifname)
