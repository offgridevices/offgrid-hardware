"""layercam-setup: the camera's settings over the USB-C cable.

Plugged into a computer, the camera is a USB serial port (CDC-ACM, made by
/etc/init.d/S50usbdevice: /dev/ttyACM0 on Linux, /dev/cu.usbmodem* on
macOS, a COM port on Windows; any baud rate).  Open it with a terminal
(screen, picocom, PuTTY), press Enter, and type commands:

    help                         this list
    status                       version, network, service, problems
    ap                           the setup access point's name and passphrase
    wifi SSID PASSWORD           join this network (quote names with spaces)
    wifi SSID --open             a network without a password
    reset-wifi                   forget the network, open the setup access point
    show [SECTION]               the settings (secrets only as set / not set)
    get SECTION.KEY
    set SECTION.KEY VALUE        checked like the setup page; empty "" clears
    update FILE [--allow-downgrade]   install a signed package already on the camera
    update --status | --factory  update state; or go back to the factory version
    ssh on PUBLIC-KEY            turn SSH on for this key (paste the .pub line); keys only
    ssh off                      SSH off, every key deleted, open sessions closed
    ssh [status]                 on or off, the keys' and the camera's fingerprints
    reboot                       restart the camera
    reboot-loader                restart into the USB loader, for upgrade_tool /
                                 rkdeveloptool (a full image; no BOOT pads needed)

It is a fixed set of commands, not a shell.  Whoever holds the camera can
use it (the same trust as the power-cycle gesture), so it can also set a
forgotten web.password; it never prints a secret.  A change is saved to
/userdata/layercam/layercam.ini and the service is told (SIGHUP) to start
again with it.  The same program runs on the serial console pads.

The init script runs it as `layercam-setup --serve /dev/ttyGS0`; it can
also be run once with a command, e.g. `layercam-setup status`.
"""
import argparse, base64, contextlib, hashlib, os, re, shlex, signal, subprocess, sys

from . import HARDWARE, VERSION, config as config_mod, gesture, net, update

CONFIG = '/userdata/layercam/layercam.ini'
PROMPT = 'layercam> '


def reboot_system(mode=None):
    """Restart; mode 'loader' asks U-Boot for its USB download mode (the
    kernel's reboot-mode driver, rv1106.dtsi: mode-loader = BOOT_BL_DOWNLOAD)."""
    os.sync()
    if mode is None:
        return subprocess.call(['reboot']) == 0
    import ctypes, platform
    nr = {'armv7l': 88, 'armv6l': 88, 'arm': 88, 'aarch64': 142, 'x86_64': 169}.get(platform.machine())
    if nr is None:
        return False
    libc = ctypes.CDLL(None, use_errno=True)
    # reboot(LINUX_REBOOT_MAGIC1, MAGIC2, LINUX_REBOOT_CMD_RESTART2, "loader")
    libc.syscall(ctypes.c_long(nr), ctypes.c_uint(0xfee1dead), ctypes.c_uint(672274793),
                 ctypes.c_uint(0xA1B2C3D4), ctypes.c_char_p(mode.encode()))
    return False                     # only reached when it did not work (not root, not Linux)


class Env:
    """Where things are, and the actions with effects outside the folder;
    the tests point it at a temporary folder and fakes."""

    def __init__(self, config=CONFIG, root='', kill=os.kill, reboot=reboot_system, factory=update.FACTORY_DIR,
                 sshd=None):
        self.config = config
        self.cfg_dir = os.path.dirname(os.path.abspath(config))
        self.root = root
        self.run_dir = root + net.RUN_DIR
        self.kill, self.reboot = kill, reboot
        self.apps = update.AppStore(os.path.join(self.cfg_dir, 'app'), factory)
        self.ssh_dir = os.path.join(self.cfg_dir, 'ssh')
        self.sshd = sshd or (lambda action: subprocess.call([root + '/etc/init.d/S50sshd', action],
                                                            stdout=subprocess.DEVNULL) == 0)

    def service_pid(self):
        try:
            with open(os.path.join(self.run_dir, 'service.pid')) as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            return None

    def notify(self):
        """Tell the running service to start again with the saved settings."""
        pid = self.service_pid()
        if pid is None:
            return False
        try:
            self.kill(pid, signal.SIGHUP)
            return True
        except OSError:
            return False

    def serial(self):
        return net.cpu_serial(self.root + '/proc/cpuinfo')


class Refused(Exception):
    pass


# ------------------------------------------------------------------ SSH (off unless turned on here)
KEY_TYPES = ('ssh-ed25519', 'ecdsa-sha2-nistp256', 'ecdsa-sha2-nistp384', 'ecdsa-sha2-nistp521', 'ssh-rsa',
             'sk-ssh-ed25519@openssh.com', 'sk-ecdsa-sha2-nistp256@openssh.com')


def _ssh_string(blob, pos):
    n = int.from_bytes(blob[pos:pos + 4], 'big')
    if pos + 4 + n > len(blob):
        raise ValueError('truncated')
    return blob[pos + 4:pos + 4 + n], pos + 4 + n


def fingerprint(blob):
    """OpenSSH's SHA256 fingerprint of a key blob."""
    return 'SHA256:' + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip('=')


def parse_public_key(text):
    """One authorized_keys line from a pasted public key -> (line, fingerprint).
    Only a bare key (no options such as command= or from=), of a known type,
    whose base64 really is a key of that type; RSA from 2048 bits."""
    if 'PRIVATE KEY' in text:
        raise Refused('that is a private key: never paste it anywhere; paste the .pub file')
    parts = text.split()
    if len(parts) < 2 or parts[0] not in KEY_TYPES:
        raise Refused('paste a public key, the one line of the .pub file: ssh-ed25519 AAAA... name')
    try:
        blob = base64.b64decode(parts[1], validate=True)
        kind, pos = _ssh_string(blob, 0)
        if kind.decode() != parts[0]:
            raise ValueError('type')
        if parts[0] == 'ssh-rsa':
            _e, pos = _ssh_string(blob, pos)
            n, pos = _ssh_string(blob, pos)
            if int.from_bytes(n, 'big').bit_length() < 2048:
                raise Refused('RSA keys shorter than 2048 bits are refused (ssh-ed25519 is best)')
    except (ValueError, UnicodeDecodeError):
        raise Refused('that key is damaged (copy the whole line again)')
    comment = re.sub(r'[^A-Za-z0-9@._+-]', '', ' '.join(parts[2:]))[:64]
    return ' '.join(p for p in (parts[0], parts[1], comment) if p), fingerprint(blob)


def _read_keys(path):
    try:
        with open(path) as f:
            return [ln.strip() for ln in f if ln.strip() and not ln.startswith('#')]
    except OSError:
        return []


def _write_private(path, text):
    tmp = path + '.tmp'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def ssh_command(a, env):
    d = env.ssh_dir
    keys_path, flag = os.path.join(d, 'authorized_keys'), os.path.join(d, 'enabled')
    if a.action == 'on':
        if not a.key:
            raise Refused('ssh on PUBLIC-KEY: paste the line of your .pub file after "ssh on"')
        line, fp = parse_public_key(' '.join(a.key))
        os.makedirs(d, mode=0o700, exist_ok=True)
        os.chmod(d, 0o700)
        keys = [k for k in _read_keys(keys_path) if k.split()[:2] != line.split()[:2]] + [line]
        _write_private(keys_path, '\n'.join(keys) + '\n')
        _write_private(flag, 'on\n')
        ok = env.sshd('restart')
        print('SSH on for key %s (%d key%s); passwords are never accepted%s'
              % (fp, len(keys), '' if len(keys) == 1 else 's', '' if ok else ': but sshd did not start'))
        ssh_status(env)
        return
    if a.action == 'off':
        for p in (flag, keys_path):
            try:
                os.unlink(p)
            except FileNotFoundError:
                pass
        env.sshd('stop')
        print('SSH off: keys deleted, sshd stopped')
        return
    ssh_status(env)


def ssh_enabled(env):
    return os.path.exists(os.path.join(env.ssh_dir, 'enabled')) and bool(
        _read_keys(os.path.join(env.ssh_dir, 'authorized_keys')))


def ssh_status(env):
    print('ssh           %s' % ('on (keys only)' if ssh_enabled(env) else 'off'))
    if not ssh_enabled(env):
        return
    for k in _read_keys(os.path.join(env.ssh_dir, 'authorized_keys')):
        p = k.split()
        try:
            print('  key         %s %s' % (fingerprint(base64.b64decode(p[1])), ' '.join(p[2:])))
        except (ValueError, IndexError):
            print('  key         (unreadable line)')
    host = _read_keys(os.path.join(env.ssh_dir, 'ssh_host_ed25519_key.pub'))
    if host:
        print('  camera      %s (check this when ssh asks the first time)'
              % fingerprint(base64.b64decode(host[0].split()[1])))


class _Parser(argparse.ArgumentParser):
    """argparse that raises Refused instead of exiting: the console must keep running."""

    def error(self, message):
        raise Refused(message)

    def exit(self, status=0, message=None):
        raise Refused((message or 'bad command').strip())


def build_parser():
    ap = _Parser(prog='layercam-setup', description='LayerCam settings over the USB console.', add_help=False)
    ap.add_argument('--config', default=None, help=argparse.SUPPRESS)
    ap.add_argument('--serve', metavar='TTY', help='answer commands on this terminal (the init script uses it)')
    sub = ap.add_subparsers(dest='cmd')

    def cmd(name):
        return sub.add_parser(name, add_help=False)
    for name in ('help', 'status', 'ap', 'version', 'reset-wifi', 'reboot', 'reboot-loader'):
        cmd(name)
    w = cmd('wifi')
    w.add_argument('ssid')
    w.add_argument('password', nargs='?')
    w.add_argument('--open', action='store_true', help='a network without a password')
    sh = cmd('ssh')
    sh.add_argument('action', nargs='?', choices=['on', 'off', 'status'], default='status')
    sh.add_argument('key', nargs='*')
    cmd('show').add_argument('section', nargs='?')
    cmd('get').add_argument('key')
    s = cmd('set')
    s.add_argument('key')
    s.add_argument('value')
    u = cmd('update')
    u.add_argument('file', nargs='?')
    u.add_argument('--allow-downgrade', action='store_true')
    u.add_argument('--status', action='store_true')
    u.add_argument('--factory', action='store_true')
    return ap


HELP = __doc__.split('\n\n')[2].rstrip()


def parse(argv):
    """-> argparse namespace; Refused (with argparse's message) on bad input."""
    if argv[:2] == ['ssh', 'on']:
        # whatever is pasted after "ssh on" is the key, even text starting with "-"
        # (a private key's first line), which parse_public_key then refuses
        return argparse.Namespace(cmd='ssh', action='on', key=argv[2:], config=None, serve=None)
    a = build_parser().parse_args(argv)
    if a.cmd == 'update' and sum((bool(a.file), a.status, a.factory)) != 1:
        raise Refused('update FILE, update --status or update --factory')
    if a.cmd == 'wifi' and not a.open and a.password is None:
        raise Refused('give the password: wifi SSID PASSWORD (or wifi SSID --open for a network without one)')
    if a.cmd == 'ssh' and a.action != 'on' and a.key:
        raise Refused('a key only goes with "ssh on"')
    if a.cmd == 'wifi' and a.open and a.password is not None:
        raise Refused('--open and a password: one or the other')
    if a.cmd in ('get', 'set') and not re.match(r'^[a-z_0-9]+\.[a-z_0-9]+$', a.key):
        raise Refused('settings are named section.key, e.g. wifi.ssid')
    return a


def _key(name):
    s, k = name.split('.', 1)
    if s not in config_mod.DEFAULTS or k not in config_mod.DEFAULTS[s]:
        raise Refused('unknown setting %s' % name)
    return s, k


def _shown(s, k, v):
    if (s, k) in config_mod.SECRETS:
        return '(set)' if v else '(not set)'
    return config_mod._text(v)


def change(env, updates):
    """Apply {(section, key): value}, check, save, tell the service."""
    cfg = config_mod.load(env.config, strict=False)
    before = set(config_mod.validate(cfg))
    for (s, k), v in updates.items():
        if (s, k) == ('device', 'fingerprint'):
            raise Refused('device.fingerprint is bound to the Connect token: never changed')
        try:
            cfg.set(s, k, v)
        except config_mod.ConfigError as e:
            raise Refused(str(e))
    new_errors = [e for e in config_mod.validate(cfg) if e not in before]
    if new_errors:
        raise Refused('; '.join(new_errors))
    if any(sk in updates for sk in (('wifi', 'ssid'), ('wifi', 'password'))):
        net.mark_new_network(env.run_dir)
    cfg.save()
    print('saved' + (': the camera starts again with it' if env.notify() else
                     ' (the service is not running: used at its next start)'))


def run(a, env):
    c = a.cmd
    if c in (None, 'help'):
        print(HELP)
        return
    if c == 'version':
        print('%s, software %s' % (HARDWARE, update.version_of(env.apps.would_run()) or VERSION))
        return
    if c == 'ap':
        cfg = config_mod.load(env.config, strict=False)
        serial = env.serial()
        ssid, pw = net.setup_ap(cfg, serial)
        print('serial        %s' % (serial or '(none: derived from the fingerprint)'))
        print('access point  %s' % ssid)
        print('passphrase    %s' % ('(your own wifi.ap_password: reset-wifi goes back to the camera\'s)'
                                    if cfg.get('wifi', 'ap_password') else pw))
        print('page          http://%s' % net.AP_ADDRESS)
        return
    if c == 'status':
        cfg = config_mod.load(env.config, strict=False)
        st = env.apps.state()
        running = env.apps.would_run()
        print('%s, software %s (%s%s)' % (HARDWARE, update.version_of(running) or VERSION,
                                          'factory' if running == env.apps.factory else 'update',
                                          ', on trial' if st['pending'] else ''))
        ssid = cfg.get('wifi', 'ssid')
        info = net.interface_info()
        print('network       %s' % ((ssid + (' (connected, %s)' % info['wifi_ipv4'] if 'wifi_ipv4' in info
                                             else ' (not connected)')) if ssid else 'none saved: setup access point'))
        pid = env.service_pid()
        print('service       %s' % ('running (pid %d)' % pid if pid else 'not running'))
        print('ssh           %s' % ('on (keys only)' if ssh_enabled(env) else 'off'))
        if not cfg.get('web', 'password'):
            print('problem       web.password is not set: the page answers only on the setup access point')
        if st['last']:
            print('update        %s' % st['last'])
        for e in cfg.errors():
            print('problem       %s' % e)
        return
    if c == 'ssh':
        ssh_command(a, env)
        return
    if c == 'show':
        cfg = config_mod.load(env.config, strict=False)
        if a.section and a.section not in config_mod.DEFAULTS:
            raise Refused('no section %s (%s)' % (a.section, ', '.join(config_mod.DEFAULTS)))
        for s in config_mod.DEFAULTS:
            if a.section in (None, s):
                print('[%s]' % s)
                for k, v in cfg.section(s).items():
                    print('%s = %s' % (k, _shown(s, k, v)))
        return
    if c == 'get':
        s, k = _key(a.key)
        print(_shown(s, k, config_mod.load(env.config, strict=False).get(s, k)))
        return
    if c == 'set':
        change(env, {_key(a.key): a.value})
        return
    if c == 'wifi':
        if len(a.ssid.encode()) > 32 or not a.ssid:
            raise Refused('a network name is 1-32 bytes')
        change(env, {('wifi', 'ssid'): a.ssid, ('wifi', 'password'): '' if a.open else a.password})
        if not config_mod.load(env.config, strict=False).get('web', 'password'):
            print('note: set web.password too (set web.password "..."): without it the page does not '
                  'answer on your network')
        return
    if c == 'reset-wifi':
        gesture.FileStore(env.cfg_dir).request_reset()
        print('the network is forgotten when the service starts again' +
              (': now' if env.notify() else ' (it is not running)'))
        return
    if c == 'update':
        store = env.apps
        if a.status:
            st = store.state()
            for k in ('good', 'pending', 'tries', 'failed', 'last'):
                print('%-8s %s' % (k, st[k]))
            return
        if a.factory:
            store.factory_reset()
            print('back to the factory version' + (': restarting' if env.notify() else ''))
            return
        current = update.version_of(store.would_run()) or VERSION
        try:
            v = store.install(a.file, update.load_keys(env.root + update.KEYS_FILE), current,
                              update.rootfs_version(env.root + update.ROOTFS_VERSION_FILE), a.allow_downgrade)
        except (update.UpdateError, OSError) as e:
            raise Refused(str(e))
        print('version %s installed' % v + (': restarting into it' if env.notify() else ''))
        return
    if c in ('reboot', 'reboot-loader'):
        print('restarting%s' % (' into the USB loader: flash with upgrade_tool or rkdeveloptool'
                                if c == 'reboot-loader' else ''))
        sys.stdout.flush()
        if not env.reboot('loader' if c == 'reboot-loader' else None):
            raise Refused('could not restart (not root?)')
        return


def main(argv=None, env=None):
    """One command.  -> 0 done, 1 refused, 2 bad command."""
    try:
        a = parse(list(sys.argv[1:] if argv is None else argv))
    except Refused as e:
        print('error: %s (type help)' % e)
        return 2
    env = env or Env(a.config or CONFIG)
    if a.serve:
        return serve(a.serve, env)
    try:
        run(a, env)
    except Refused as e:
        print('refused: %s' % e)
        return 1
    return 0


def serve_stream(rf, wf, env):
    """Read command lines from rf, answer on wf, until rf ends."""
    def out(text):
        wf.write(text)
        wf.flush()
    out('\nLayerCam setup console (%s, %s). Type help.\n%s' % (HARDWARE, VERSION, PROMPT))
    for line in rf:
        line = line.strip()
        if line:
            try:
                argv = shlex.split(line)
            except ValueError as e:
                out('error: %s\n' % e)
                argv = None
            if argv and argv[0] in ('exit', 'quit', 'logout'):
                out('(close the terminal to leave)\n')
            elif argv and argv[0].startswith('--'):
                out('error: options only after a command (type help)\n')
            elif argv:
                with contextlib.redirect_stdout(wf), contextlib.redirect_stderr(wf):
                    try:
                        main(argv, env)
                    except Exception as e:      # the console stays up whatever a command does
                        print('error: %s' % e)
        out(PROMPT)


def serve(tty, env):
    import termios
    fd = os.open(tty, os.O_RDWR | os.O_NOCTTY)
    try:
        t = termios.tcgetattr(fd)
        t[0] |= termios.ICRNL                                  # Enter sends CR
        t[1] |= termios.OPOST | termios.ONLCR
        t[3] |= termios.ICANON | termios.ECHO | termios.ECHOE
        t[3] &= ~termios.ISIG                                  # Ctrl-C is just a character
        termios.tcsetattr(fd, termios.TCSANOW, t)
    except termios.error:
        pass
    rf = os.fdopen(fd, 'r', encoding='utf-8', errors='replace')
    wf = os.fdopen(os.dup(fd), 'w', encoding='utf-8', errors='replace')
    try:
        with rf, wf:
            serve_stream(rf, wf, env)
    except OSError:
        pass                # the host went away (EIO): the init script's loop starts it again
    return 0


if __name__ == '__main__':
    sys.exit(main())
