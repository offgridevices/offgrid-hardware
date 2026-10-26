"""Wi-Fi: join the home network, or open the setup access point.

The Python side only writes the configuration files; board/rootfs/usr/bin/
layercam-net starts wpa_supplicant + udhcpc, or hostapd + dnsmasq, from
them.  The network name is written as hex and the passphrase as the derived
256-bit PSK (what wpa_passphrase prints), so no character in either can
break the file, and the password itself is not stored in it.
"""
import hashlib, os, socket, struct, subprocess

RUN_DIR = '/tmp/layercam'
AP_ADDRESS = '192.168.4.1'


def wpa_psk(passphrase, ssid):
    """IEEE 802.11i: PBKDF2-HMAC-SHA1(passphrase, ssid, 4096 rounds, 32 bytes)."""
    return hashlib.pbkdf2_hmac('sha1', passphrase.encode(), ssid.encode(), 4096, 32).hex()


def wpa_supplicant_conf(ssid, password):
    lines = ['ctrl_interface=/var/run/wpa_supplicant', 'update_config=0', '', 'network={',
             '    ssid=%s' % ssid.encode().hex(), '    scan_ssid=1']
    if password:
        lines += ['    key_mgmt=WPA-PSK', '    psk=%s' % wpa_psk(password, ssid)]
    else:
        lines += ['    key_mgmt=NONE']
    lines += ['}', '']
    return '\n'.join(lines)


def ap_ssid(fingerprint):
    return 'LayerCam-%s' % (fingerprint[-4:].upper() if fingerprint else 'SETUP')


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


def write_files(cfg, run_dir=RUN_DIR):
    os.makedirs(run_dir, exist_ok=True)
    files = {
        'wpa_supplicant.conf': wpa_supplicant_conf(cfg.get('wifi', 'ssid'), cfg.get('wifi', 'password')),
        'hostapd.conf': hostapd_conf(ap_ssid(cfg.get('device', 'fingerprint')), cfg.get('wifi', 'ap_password')),
        'dnsmasq.conf': dnsmasq_conf(),
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
    return subprocess.run([script, mode], timeout=60).returncode == 0


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
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # SIOCGIFADDR
        res = fcntl.ioctl(s.fileno(), 0x8915, struct.pack('256s', ifname.encode()[:15]))
        out['wifi_ipv4'] = socket.inet_ntoa(res[20:24])
        s.close()
    except (OSError, ImportError):
        pass
    return out


def link_up(ifname='wlan0'):
    return 'wifi_ipv4' in interface_info(ifname)
