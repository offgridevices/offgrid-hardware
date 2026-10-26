"""Wi-Fi: join the home network, or open the setup access point.

The Python side only writes the configuration files; board/rootfs/usr/bin/
layercam-net starts wpa_supplicant + udhcpc, or hostapd + dnsmasq, from
them.  The network name is written as hex and the passphrase as the derived
256-bit PSK (what wpa_passphrase prints), so no character in either can
break the file, and the password itself is not stored in it.
"""
import hashlib, hmac, os, socket, struct, subprocess

RUN_DIR = '/tmp/layercam'
AP_ADDRESS = '192.168.4.1'
# 2.4 GHz channels 1-13: wifi.band = 2.4 keeps the camera off 5 GHz, where the
# AP6256 draws more (sim/thermal.md asks for 2.4 GHz at low power)
FREQ_2G4 = ' '.join(str(2412 + 5 * i) for i in range(13))

# The setup access point's name and passphrase come from the SoC's serial
# number (the RV1106's OTP id, which the kernel's rockchip-cpuinfo driver
# shows as "Serial" in /proc/cpuinfo), so every camera has its own and
# tools/layercam-ap.py can print them from the serial.  The key only makes
# the result specific to this use; the secret is the serial, which never
# leaves the camera except over its USB cable or serial console.
AP_KEY = b'OffGrid LayerCam v1 setup access point'
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
        'interface=wlan0', 'driver=nl80211', 'ssid2=%s' % ssid.encode().hex(), 'hw_mode=g',
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
