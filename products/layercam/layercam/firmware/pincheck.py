"""The camera software's pins against the schematic, as (ok, description) pairs.

src/circuit.py is the source of truth: main_soc() names each SoC pin's net
and, in its comment, the pin's function (GPIO1_A0, SARADC_IN1, PWM3_IR_M1,
I2C4_SCL_M2...).  This reads that file as text (no import, nothing
installed: it runs in the board build's Python too) and checks
layercam/board.py and dts/rv1106g-layercam-v1.dts against it.

Used by tests/test_pins.py and by the board build (src/verify.py through
src/check_firmware.py).  Standard library only.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def soc_pins(text):
    """net -> the function named in its comment, from main_soc()'s pin map."""
    body = text[text.index('def main_soc'):text.index("add('U', 'RV1106G3'")]
    out = {}
    for pin, net, comment in re.findall(r"'(\d+)':\s*'([A-Z0-9_]+)',\s*#\s*([^\n]*)", body):
        out[net] = comment
    return out


def gpio_ref(gpio):
    """'GPIO1_A0' -> ('1', 'RK_PA0') as the device tree writes it."""
    bank, pin = gpio[4:].split('_')
    return bank, 'RK_P' + pin


def board_module(firmware_dir=HERE):
    if firmware_dir not in sys.path:
        sys.path.insert(0, firmware_dir)
    from layercam import board
    return board


def results(circuit_text, dts_text, board):
    """[(ok, description)], one per check."""
    out = []
    pins = soc_pins(circuit_text)

    def comment_gpio(net):
        m = re.search(r'GPIO\d_[A-D]\d', pins.get(net, ''))
        return m.group(0) if m else None

    def item(ok, what):
        out.append((bool(ok), what))

    # board.py's GPIOs are the ones circuit.py names
    for net, gpio in sorted(board.PINS.items()):
        if net == 'IR_PWM':
            item('PWM3_IR_M1' in pins.get(net, ''), 'firmware IR_PWM on PWM3_IR_M1 (circuit.py: %s)' % pins.get(net))
            continue
        item(comment_gpio(net) == gpio, 'firmware %s on %s (circuit.py: %s)' % (net, gpio, comment_gpio(net)))

    def has(pattern, what):
        item(re.search(pattern, dts_text), 'device tree: ' + what)

    def gref(net):
        b, p = gpio_ref(board.PINS[net])
        return r'<&gpio%s %s ' % (b, p)

    has(r'status_led: status \{[^}]*gpios = ' + re.escape(gref('LED_STATUS')), 'status LED on LED_STATUS')
    has(r'reset-gpios = ' + re.escape(gref('WL_REG_ON')) + 'GPIO_ACTIVE_LOW', 'WL_REG_ON drives the SDIO power sequence')
    has(r'WIFI,host_wake_irq = ' + re.escape(gref('WL_HOST_WAKE')), 'WL_HOST_WAKE is the Wi-Fi interrupt')
    has(r'pwdn-gpios = ' + re.escape(gref('CAM_RST')), 'CAM_RST is the sensor power-down')
    has(r'BT,reset_gpio = ' + re.escape(gref('BT_REG_ON')), 'BT_REG_ON in the Bluetooth node')
    has(r'BT,wake_gpio = ' + re.escape(gref('BT_WAKE')), 'BT_WAKE in the Bluetooth node')
    has(r'BT,wake_host_irq = ' + re.escape(gref('BT_HOST_WAKE')), 'BT_HOST_WAKE in the Bluetooth node')
    for net in ('IRCUT_A', 'IRCUT_B'):
        b, p = gpio_ref(board.PINS[net])
        has(r'<%s %s RK_FUNC_GPIO &pcfg_pull_down>' % (b, p), '%s held low as a GPIO' % net)
    has(r'&pwm3 \{[^}]*pinctrl-0 = <&pwm3m1_pins>', 'PWM3 on its M1 pin')
    mclk = pins.get('CAM_MCLK_SOC', '')
    item('MIPI_CLK0_OUT' in mclk and 'GPIO3_C4' in mclk, 'circuit.py: sensor clock on MIPI_CLK0_OUT (GPIO3_C4)')
    has(r'pinctrl-0 = <&mipi_refclk_out0>', 'sensor clock on mipi_refclk_out0')
    item('I2C4_SCL_M2' in pins.get('CAM_SCL', '') and 'I2C4_SDA_M2' in pins.get('CAM_SDA', ''),
         'circuit.py: camera I2C on I2C4_M2')
    has(r'&i2c4 \{[^}]*pinctrl-0 = <&i2c4m2_xfer>', 'I2C4 on its M2 pins')
    item('UART1_TX_M0' in pins.get('BT_TXD', '') and 'UART1_RTS_M0' in pins.get('BT_RTS', ''),
         'circuit.py: Bluetooth UART is UART1_M0')
    item('SARADC_IN%d' % board.ADC_LIGHT in pins.get('ALS', ''),
         'light sensor on SARADC channel %d (circuit.py: %s)' % (board.ADC_LIGHT, pins.get('ALS')))
    item('SARADC_IN%d' % board.ADC_BOOT_PAD in pins.get('BOOT_KEY', ''),
         'BOOT pad on SARADC channel %d (circuit.py: %s)' % (board.ADC_BOOT_PAD, pins.get('BOOT_KEY')))
    has(r'&saradc \{[^}]*status = "okay"', 'SARADC enabled')
    # no button: the firmware relies on none, and the evb's ADC keys must not claim the BOOT pad
    item(not re.search(r"add\('SW'", circuit_text), 'circuit.py: no button (the firmware needs none)')
    item(re.search(r"add\('TP', 'TP', \{'1': 'BOOT_SW'\}", circuit_text) and
         re.search(r"res\('R100R', 'BOOT_KEY', 'BOOT_SW'", circuit_text),
         'circuit.py: BOOT pad TP5 through 100R to SARADC_IN0')
    has(r'/delete-node/ adc-keys;', 'evb ADC keys removed (SARADC_IN0 is the BOOT pad)')
    has(r'&usbdrd_dwc3 \{[^}]*dr_mode = "peripheral"', 'USB controller is a device (setup console)')
    has(r'&sdmmc \{[^}]*no-1-8-v;', 'SDIO kept at 3.3 V')
    item('VCCIO4 = 3.3 V' in circuit_text, 'circuit.py: VCCIO4 (SDIO) at 3.3 V')
    return out


def _text(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return None


def _stub(text):
    """An init script that does nothing: only comments and exit 0."""
    if text is None:
        return False
    body = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith('#')]
    return body == ['exit 0']


def image_results(firmware_dir=HERE):
    """[(ok, description)]: no default password, no network service the owner
    did not turn on, in what the build puts into the image (README.md,
    Security).  Checks the board config, the Buildroot fragment and the
    rootfs overlay, the files LayerCam controls."""
    out = []
    root = os.path.join(firmware_dir, 'board', 'rootfs')

    def item(ok, what):
        out.append((bool(ok), 'image: ' + what))

    def rootfs(p):
        return _text(os.path.join(root, p))

    mk = _text(os.path.join(firmware_dir, 'board', 'sdk', 'BoardConfig-SPI_NAND-Buildroot-RV1106_LayerCam_v1-IPC.mk')) or ''
    m = re.search(r'^export RK_POST_OVERLAY="([^"]*)"', mk, re.M)
    overlays = m.group(1).split() if m else []
    item(overlays and overlays[-1] == 'overlay-layercam', "LayerCam's overlay is applied last")
    for bad in ('overlay-luckfox-buildroot-shadow', 'overlay-luckfox-buildroot-init', 'overlay-luckfox-config'):
        item(m and bad not in overlays, '%s not used (root password, sshd with passwords, Samba share of /, '
                                        'autostart scripts)' % bad)
    frag = _text(os.path.join(firmware_dir, 'board', 'sdk', 'buildroot.fragment')) or ''
    settings = [ln for ln in frag.splitlines() if re.match(r'^(BR2_|# BR2_\w+ is not set$)', ln)]
    item('# BR2_TARGET_ENABLE_ROOT_LOGIN is not set' in settings, 'Buildroot gives root no password')
    item(not any(ln.startswith(('BR2_TARGET_GENERIC_ROOT_PASSWD', 'BR2_TARGET_ENABLE_ROOT_LOGIN=y')) for ln in settings),
         'no root password in the Buildroot fragment')
    item(not any(re.match(r'^BR2_PACKAGE_(SAMBA4|DROPBEAR|LIGHTTPD|NGINX|BOA|THTTPD|VSFTPD|PROFTPD|TFTPD|'
                          r'ANDROID_TOOLS_ADBD|BUSYBOX_SHOW_OTHERS_TELNETD)\b=y', ln) for ln in settings),
         'no extra servers added in the Buildroot fragment')
    shadow = rootfs('etc/shadow')
    entries = [ln.split(':') for ln in (shadow or '').splitlines() if ln.strip()]
    item(shadow is not None and any(e[0] == 'root' and e[1] in ('*', '!', '!*') for e in entries),
         'root locked in /etc/shadow (no password)')
    item(shadow is not None and all(len(e) > 1 and e[1] in ('*', '!', '!*', '!!') for e in entries),
         'no account in /etc/shadow has a password')
    cfg = rootfs('etc/ssh/sshd_config') or ''

    def opt(name):
        found = re.findall(r'^\s*%s\s+(\S+)' % name, cfg, re.M | re.I)
        return found[0].lower() if found else None
    item(opt('PasswordAuthentication') == 'no' and opt('KbdInteractiveAuthentication') == 'no'
         and opt('PermitEmptyPasswords') == 'no', 'sshd: passwords refused')
    item(opt('PermitRootLogin') in ('prohibit-password', 'without-password'), 'sshd: root by key only')
    item((opt('AuthorizedKeysFile') or '').startswith('/userdata/layercam/ssh/'),
         'sshd: keys only from the USB console (/userdata/layercam/ssh)')
    s50 = rootfs('etc/init.d/S50sshd') or ''
    gate, launch = s50.find('if ! enabled; then'), s50.find('/usr/sbin/sshd &&')
    item('DIR=/userdata/layercam/ssh' in s50 and '[ -f $DIR/enabled ]' in s50 and 0 <= gate < launch,
         'S50sshd starts sshd only when turned on from the USB console')
    for name, why in (('S49ntp', 'ntpd server'), ('S41dhcpcd', 'dhcpcd'), ('S50telnet', 'telnet server'),
                      ('S99usb0config', 'USB network')):
        item(_stub(rootfs('etc/init.d/' + name)), 'no %s (%s is empty)' % (why, name))
    app = rootfs('etc/init.d/S21appinit') or ''
    item(app and 'RkLunch.sh' not in re.sub(r'#.*', '', app), 'S21appinit does not start rkipc (RTSP, web server)')
    usb = rootfs('etc/init.d/S50usbdevice') or ''
    code = re.sub(r'#.*', '', usb)
    item(usb and 'acm.' in code and not re.search(r'adbd|ffs\.adb|rndis|ecm|ncm', code),
         'USB: the setup console only, no adb or USB network')
    adbd = rootfs('usr/bin/adbd') or ''
    item('exit 1' in adbd and 'adbd' not in re.sub(r'#.*|echo.*', '', adbd), '/usr/bin/adbd replaced by a stub')
    uid = (rootfs('etc/layercam/usb-id') or '').strip()
    item(re.match(r'^[0-9a-f]{4}:[0-9a-f]{4}$', uid, re.I) and '/etc/layercam/usb-id' in usb,
         'USB id set at build time (/etc/layercam/usb-id: %s)' % uid)
    return out


def run(firmware_dir=HERE, circuit_path=None):
    circuit_path = circuit_path or os.path.join(firmware_dir, '..', 'src', 'circuit.py')
    with open(circuit_path) as f:
        circuit_text = f.read()
    with open(os.path.join(firmware_dir, 'dts', 'rv1106g-layercam-v1.dts')) as f:
        dts_text = f.read()
    return results(circuit_text, dts_text, board_module(firmware_dir)) + image_results(firmware_dir)


if __name__ == '__main__':
    res = run()
    for ok, what in res:
        print('  [%s] %s' % ('ok' if ok else 'FAIL', what))
    sys.exit(0 if all(ok for ok, _ in res) else 1)
