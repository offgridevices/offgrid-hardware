"""Which products CI builds, for .github/workflows/ci.yml.

A product is a folder under products/ with a tools/ci.json (its pinned image
and timeout); its CI is that folder's tools/ci-setup.sh, then tools/ci.sh.
On a pull request only the products whose folder changed are built, and all
of them when a shared file changes (SHARED); every other event (a push to
main, the weekly run, a manual run) builds them all.  A change to docs/ or
the top-level README builds no product: the repo-checks job covers it.

    python3 tools/ci/matrix.py              print the matrix and why
    EVENT=pull_request python3 tools/ci/matrix.py

With GITHUB_OUTPUT set (in CI) it also writes `matrix` (for strategy.matrix)
and `any` (whether there is anything to build).  On a pull request it reads
the change from the checkout: HEAD is GitHub's merge commit, so HEAD^1 is
the base branch it merges into (the checkout needs fetch-depth: 2).
"""
import glob, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SHARED = ('.github/', 'tools/', '.gitignore')


def products():
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'products', '**', 'tools', 'ci.json'), recursive=True)):
        path = os.path.relpath(os.path.dirname(os.path.dirname(f)), ROOT)
        cfg = json.load(open(f))
        out.append({'name': os.path.basename(path), 'path': path,
                    'image': cfg['image'], 'timeout': int(cfg['timeout'])})
    names = [p['name'] for p in out]
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        sys.exit('two products share a folder name, so their CI jobs would too: %s' % ', '.join(dup))
    return out


def changed():
    """The files a pull request changes, or None when that cannot be read."""
    r = subprocess.run(['git', '-C', ROOT, 'diff', '--name-only', 'HEAD^1', 'HEAD'],
                       capture_output=True, text=True)
    return r.stdout.split('\n') if r.returncode == 0 else None


def main():
    every = products()
    event = os.environ.get('EVENT', '')
    files = changed() if event == 'pull_request' else None
    if event != 'pull_request':
        pick, why = every, 'event %r builds every product' % (event or 'local')
    elif files is None:
        pick, why = every, 'could not read the change, so every product'
    elif any(f.startswith(SHARED) for f in files if f):
        pick, why = every, 'a shared file changed, so every product'
    else:
        pick = [p for p in every if any(f.startswith(p['path'] + '/') for f in files)]
        why = '%d of %d products changed' % (len(pick), len(every))
    print(why + ': ' + (', '.join(p['name'] for p in pick) or 'none'))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as o:
            o.write('matrix=%s\n' % json.dumps({'include': pick}))
            o.write('any=%s\n' % ('true' if pick else 'false'))


if __name__ == '__main__':
    main()
