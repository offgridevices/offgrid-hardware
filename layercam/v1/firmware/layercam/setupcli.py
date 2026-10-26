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
import argparse, contextlib, os, re, shlex, signal, subprocess, sys

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

    def __init__(self, config=CONFIG, root='', kill=os.kill, reboot=reboot_system, factory=update.FACTORY_DIR):
        self.config = config
        self.cfg_dir = os.path.dirname(os.path.abspath(config))
        self.root = root
        self.run_dir = root + net.RUN_DIR
        self.kill, self.reboot = kill, reboot
        self.apps = update.AppStore(os.path.join(self.cfg_dir, 'app'), factory)

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
    a = build_parser().parse_args(argv)
    if a.cmd == 'update' and sum((bool(a.file), a.status, a.factory)) != 1:
        raise Refused('update FILE, update --status or update --factory')
    if a.cmd == 'wifi' and not a.open and a.password is None:
        raise Refused('give the password: wifi SSID PASSWORD (or wifi SSID --open for a network without one)')
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
        if st['last']:
            print('update        %s' % st['last'])
        for e in cfg.errors():
            print('problem       %s' % e)
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
