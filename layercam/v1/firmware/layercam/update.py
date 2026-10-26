"""App updates over the air: signed packages, a trial start, rollback.

The camera software (this package) is the part that changes most, so it
can be replaced without a computer: from the setup page (POST /api/update)
or over the USB console (layercam-setup update).  The kernel, the rootfs and
the C helper change only with a full image (README.md, Updates).

A package (.lcup) is an uncompressed tar of three members:

    manifest.json   {"format", "product", "version", "min_rootfs",
                     "payload_sha256", "payload_size", "files": {path: sha256}}
    manifest.sig    Ed25519 signature of manifest.json's exact bytes, hex
    app.tar         the layercam/ package (plain tar: the board's Python
                    may have no zlib)

It is accepted only when the signature is from a key in
/etc/layercam/update-keys (on the rootfs, so an app update cannot change
who may sign the next one), the product matches, the version is newer than
the running one, the image is new enough (min_rootfs against
/etc/layercam/rootfs-version), the payload's hash and every file's hash
match the manifest, nothing else is in it, and the new code imports.

Where it goes (on /userdata, beside the timelapses):

    app/slots/<version>/layercam/   installed versions
    app/state.json                  {"good", "pending", "tries", "failed", "last"}

The factory copy in /usr/share/layercam (the rootfs) is never touched.  At
every start the init script asks this module (always the factory copy of
it) which copy to run: a pending update gets MAX_TRIES starts to stay up
for GOOD_AFTER_S; the service then marks it good.  If it does not, the last
good version (or the factory copy) runs again and the update is recorded as
failed.  State is written only when something changes (install, a trial
start, marked good): no NAND writes in normal running.
"""
import hashlib, io, json, os, re, shutil, subprocess, sys, tarfile

from . import HARDWARE, ed25519

FORMAT = 1
MAX_PACKAGE = 16 * 1024 * 1024
MAX_FILE = 2 * 1024 * 1024
MAX_TRIES = 3                  # starts a new version gets to prove itself
GOOD_AFTER_S = 90              # up this long (web page and main loop running) = good
KEYS_FILE = '/etc/layercam/update-keys'
ROOTFS_VERSION_FILE = '/etc/layercam/rootfs-version'
FACTORY_DIR = '/usr/share/layercam'


class UpdateError(Exception):
    pass


def parse_version(v):
    try:
        parts = tuple(int(x) for x in str(v).split('.'))
    except ValueError:
        raise UpdateError('bad version %r' % (v,))
    if not 1 <= len(parts) <= 4 or any(x < 0 for x in parts):
        raise UpdateError('bad version %r' % (v,))
    return parts


def version_of(app_dir):
    """VERSION of the copy of the software in app_dir, read as text (not imported)."""
    try:
        with open(os.path.join(app_dir, 'layercam', '__init__.py')) as f:
            m = re.search(r"^VERSION\s*=\s*['\"]([^'\"]+)['\"]", f.read(), re.M)
        return m.group(1) if m else None
    except OSError:
        return None


def load_keys(path=KEYS_FILE):
    """Public keys, one hex key per line ('#' starts a comment)."""
    keys = []
    try:
        with open(path) as f:
            for line in f:
                line = line.split('#', 1)[0].strip()
                if line:
                    k = bytes.fromhex(line)
                    if len(k) == 32:
                        keys.append(k)
    except (OSError, ValueError):
        pass
    return keys


def rootfs_version(path=ROOTFS_VERSION_FILE):
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 1


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _add(tar, name, data):
    ti = tarfile.TarInfo(name)
    ti.size, ti.mode, ti.mtime = len(data), 0o644, 0
    tar.addfile(ti, io.BytesIO(data))


# ------------------------------------------------------------------ making a package (a PC)
def build_package(src_dir, version, seed, out_path, min_rootfs=1, product=HARDWARE):
    """Package src_dir/layercam/ (sources only) as version, signed with seed."""
    files = {}
    pkg = os.path.join(src_dir, 'layercam')
    for dirpath, dirnames, names in os.walk(pkg):
        dirnames[:] = sorted(d for d in dirnames if d != '__pycache__')
        for n in sorted(names):
            if n.endswith(('.pyc', '.pyo')) or n.startswith('.'):
                continue
            full = os.path.join(dirpath, n)
            with open(full, 'rb') as f:
                files[os.path.relpath(full, src_dir).replace(os.sep, '/')] = f.read()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w', format=tarfile.USTAR_FORMAT) as t:
        for name in sorted(files):
            _add(t, name, files[name])
    payload = buf.getvalue()
    manifest = {'format': FORMAT, 'product': product, 'version': version, 'min_rootfs': min_rootfs,
                'payload_sha256': _sha(payload), 'payload_size': len(payload),
                'files': {n: _sha(d) for n, d in files.items()}}
    mbytes = json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()
    sig = ed25519.sign(seed, mbytes).hex().encode()
    with open(out_path + '.tmp', 'wb') as f:
        with tarfile.open(fileobj=f, mode='w', format=tarfile.USTAR_FORMAT) as t:
            _add(t, 'manifest.json', mbytes)
            _add(t, 'manifest.sig', sig)
            _add(t, 'app.tar', payload)
    os.replace(out_path + '.tmp', out_path)
    return manifest


# ------------------------------------------------------------------ checking one (the camera)
def read_package(path, keys, product=HARDWARE):
    """-> (manifest, payload bytes), or UpdateError saying what is wrong."""
    if not keys:
        raise UpdateError('no update keys on this camera (%s): updates are refused' % KEYS_FILE)
    try:
        if os.path.getsize(path) > MAX_PACKAGE:
            raise UpdateError('package larger than %d MB' % (MAX_PACKAGE >> 20))
        parts = {}
        with tarfile.open(path, 'r:') as t:
            for m in t.getmembers():
                if m.name not in ('manifest.json', 'manifest.sig', 'app.tar') or not m.isfile() \
                        or m.name in parts or m.size > MAX_PACKAGE:
                    raise UpdateError('not a LayerCam package (unexpected %s)' % m.name)
                parts[m.name] = t.extractfile(m).read()
    except (OSError, tarfile.TarError) as e:
        raise UpdateError('not a LayerCam package (%s)' % e)
    if set(parts) != {'manifest.json', 'manifest.sig', 'app.tar'}:
        raise UpdateError('not a LayerCam package (missing parts)')
    try:
        sig = bytes.fromhex(parts['manifest.sig'].decode().strip())
    except (ValueError, UnicodeDecodeError):
        raise UpdateError('bad signature file')
    if not any(ed25519.verify(k, parts['manifest.json'], sig) for k in keys):
        raise UpdateError('not signed by a key this camera trusts')
    try:
        m = json.loads(parts['manifest.json'])
        files = m['files']
        ok = m['format'] == FORMAT and isinstance(files, dict) and files
    except (ValueError, KeyError, TypeError):
        ok = False
    if not ok:
        raise UpdateError('unknown manifest format')
    if m.get('product') != product:
        raise UpdateError('package is for %r, this is %r' % (m.get('product'), product))
    parse_version(m.get('version'))
    p = parts['app.tar']
    if len(p) != m.get('payload_size') or _sha(p) != m.get('payload_sha256'):
        raise UpdateError('payload does not match its manifest')
    return m, p


def check_compatible(manifest, current, rootfs, allow_downgrade=False):
    new, cur = parse_version(manifest['version']), parse_version(current)
    if new == cur:
        raise UpdateError('version %s is already running' % manifest['version'])
    if new < cur and not allow_downgrade:
        raise UpdateError('version %s is older than %s (older signed versions are refused)'
                          % (manifest['version'], current))
    if int(manifest.get('min_rootfs', 1)) > rootfs:
        raise UpdateError('version %s needs a newer system image (rootfs %s, this camera has %d): '
                          'flash a full image over USB' % (manifest['version'], manifest.get('min_rootfs'), rootfs))


def _safe_name(name):
    parts = name.split('/')
    return (name.startswith('layercam/') and not name.startswith('/') and '\\' not in name
            and all(p not in ('', '.', '..') for p in parts))


def extract_payload(payload, manifest, dest):
    """Write the payload's files under dest, each checked against the manifest."""
    want = manifest['files']
    seen = set()
    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode='r:') as t:
            for m in t.getmembers():
                if m.isdir():
                    continue
                if not m.isfile() or not _safe_name(m.name) or m.name not in want or m.name in seen \
                        or m.size > MAX_FILE:
                    raise UpdateError('unexpected file in package: %s' % m.name)
                data = t.extractfile(m).read()
                if _sha(data) != want[m.name]:
                    raise UpdateError('%s does not match its manifest' % m.name)
                out = os.path.join(dest, *m.name.split('/'))
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with open(out, 'wb') as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
                seen.add(m.name)
    except tarfile.TarError as e:
        raise UpdateError('broken payload: %s' % e)
    missing = set(want) - seen
    if missing:
        raise UpdateError('package is missing %s' % ', '.join(sorted(missing)))
    if 'layercam/__init__.py' not in seen or 'layercam/__main__.py' not in seen:
        raise UpdateError('package has no layercam program')


def smoke_test(app_dir, python=None):
    """The new code must at least import, with this Python, before it is started."""
    try:
        r = subprocess.run([python or sys.executable, '-c',
                            'import layercam, layercam.service, layercam.web, layercam.update;'
                            'print(layercam.VERSION)'], cwd=app_dir, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise UpdateError('new version does not start: %s' % e)
    if r.returncode != 0:
        raise UpdateError('new version does not start: %s' % (r.stderr.strip().splitlines() or ['?'])[-1])
    return r.stdout.strip()


def _write_json(path, obj):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(obj, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    try:
        fd = os.open(os.path.dirname(path) or '.', os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


class AppStore:
    """The installed versions and which one runs."""

    def __init__(self, root, factory_dir=FACTORY_DIR, max_tries=MAX_TRIES):
        self.root, self.factory, self.max_tries = root, factory_dir, max_tries
        self.state_path = os.path.join(root, 'state.json')

    def slot(self, version):
        return os.path.join(self.root, 'slots', version)

    def state(self):
        st = {'good': None, 'pending': None, 'tries': 0, 'failed': [], 'last': None}
        try:
            with open(self.state_path) as f:
                got = json.load(f)
            if isinstance(got, dict):
                st.update({k: got[k] for k in st if k in got})
        except (OSError, ValueError):
            pass
        return st

    def save(self, st):
        os.makedirs(self.root, exist_ok=True)
        _write_json(self.state_path, st)

    def install(self, package, keys, current, rootfs=1, allow_downgrade=False, check=smoke_test):
        """Check and unpack a package; it runs from the next start, on trial."""
        m, payload = read_package(package, keys)
        check_compatible(m, current, rootfs, allow_downgrade)
        v = m['version']
        slot = self.slot(v)
        tmp = slot + '.new'
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        try:
            extract_payload(payload, m, tmp)
            if check:
                got = check(tmp)
                if got and got != v:
                    raise UpdateError('package says %s but its code says %s' % (v, got))
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        shutil.rmtree(slot, ignore_errors=True)
        os.rename(tmp, slot)
        st = self.state()
        st.update(pending=v, tries=0, failed=[x for x in st['failed'] if x != v][-5:],
                  last='%s installed: starting it on trial' % v)
        self.save(st)
        return v

    def select(self):
        """Called before every start (by the factory copy): the folder to run."""
        st = self.state()
        changed = False
        if st['pending']:
            v = st['pending']
            if not os.path.isfile(os.path.join(self.slot(v), 'layercam', '__main__.py')):
                st.update(pending=None, tries=0, last='%s is missing: not started' % v)
                changed = True
            elif st['tries'] >= self.max_tries:
                back = st['good'] or 'the factory version'
                st['failed'] = (st['failed'] + [v])[-5:]
                st.update(pending=None, tries=0,
                          last='%s did not stay up in %d starts: back to %s' % (v, self.max_tries, back))
                changed = True
            else:
                st['tries'] += 1
                self.save(st)
                return self.slot(v)
        run = self.factory
        if st['good']:
            if os.path.isfile(os.path.join(self.slot(st['good']), 'layercam', '__main__.py')):
                run = self.slot(st['good'])
            else:
                st.update(good=None, last='%s is missing: factory version' % st['good'])
                changed = True
        if changed:
            self.save(st)
        return run

    def would_run(self):
        """What select() would start, without counting a start."""
        st = self.state()
        for v in (st['pending'], st['good']):
            if v and os.path.isfile(os.path.join(self.slot(v), 'layercam', '__main__.py')):
                return self.slot(v)
        return self.factory

    def running_trial(self, running_dir):
        st = self.state()
        return bool(st['pending']) and os.path.realpath(running_dir) == os.path.realpath(self.slot(st['pending']))

    def mark_good(self, running_dir):
        """The running copy has stayed up: keep it, drop older ones."""
        if not self.running_trial(running_dir):
            return False
        st = self.state()
        v = st['pending']
        st.update(good=v, pending=None, tries=0, last='%s running' % v)
        self.save(st)
        slots = os.path.join(self.root, 'slots')
        for name in os.listdir(slots):
            if name != v:
                shutil.rmtree(os.path.join(slots, name), ignore_errors=True)
        return True

    def factory_reset(self):
        """Run the rootfs's own version again (installed ones are deleted)."""
        st = self.state()
        st.update(good=None, pending=None, tries=0, last='back to the factory version')
        self.save(st)
        shutil.rmtree(os.path.join(self.root, 'slots'), ignore_errors=True)


def main(argv=None):
    """python3 -m layercam.update select [--root R] [--factory F]: print the
    folder to run (the init script's question).  Never fails: anything wrong
    means the factory copy."""
    import argparse
    ap = argparse.ArgumentParser(prog='layercam.update')
    ap.add_argument('action', choices=['select', 'status'])
    ap.add_argument('--root', default='/userdata/layercam/app')
    ap.add_argument('--factory', default=FACTORY_DIR)
    a = ap.parse_args(argv)
    store = AppStore(a.root, a.factory)
    if a.action == 'status':
        print(json.dumps(store.state(), indent=1))
        return 0
    try:
        print(store.select())
    except Exception as e:          # the camera must start whatever happens here
        sys.stderr.write('layercam.update: %s\n' % e)
        print(a.factory)
    return 0


if __name__ == '__main__':
    sys.exit(main())
