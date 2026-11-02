"""Repository-wide checks, the repo-checks job of .github/workflows/ci.yml.

    python3 tools/ci/check_repo.py

  * every relative link in every Markdown file points at a file or folder
    that is in the repository (committed, or new and not ignored), so a
    moved or renamed file cannot leave a dead link behind;
  * every Python file parses;
  * every product (a folder under products/ with a src/) has the three CI
    files tools/ci.sh, tools/ci-setup.sh and tools/ci.json, so a new product
    cannot be merged without CI building it.

Exits 1 on any failure, listing every one.
"""
import ast, glob, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LINK = re.compile(r'\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)')


def git_files():
    r = subprocess.run(['git', '-C', ROOT, 'ls-files', '--cached', '--others', '--exclude-standard'],
                       capture_output=True, text=True, check=True)
    files = {f for f in r.stdout.split('\n') if f and os.path.exists(os.path.join(ROOT, f))}
    dirs = {os.path.dirname(f) for f in files}
    for d in list(dirs):
        while d:
            d = os.path.dirname(d)
            dirs.add(d)
    return files, dirs


def links(files, dirs):
    bad, n = [], 0
    for f in sorted(x for x in files if x.endswith('.md')):
        text = open(os.path.join(ROOT, f), encoding='utf-8').read()
        text = re.sub(r'```.*?```', '', text, flags=re.S)       # code blocks are not links
        text = re.sub(r'`[^`\n]*`', '', text)                     # nor is inline code
        for m in LINK.finditer(text):
            url = m.group(1)
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', url) or url.startswith('#'):
                continue
            target = url.split('#')[0].split('?')[0]
            if not target:
                continue
            n += 1
            p = os.path.normpath(os.path.join(os.path.dirname(f), target)).rstrip('/')
            if p.startswith('..') or (p not in files and p not in dirs):
                bad.append('%s: link to %s, which is not in the repository' % (f, url))
    print('links: %d relative links checked, %d broken' % (n, len(bad)))
    return bad


def python(files):
    bad = []
    py = sorted(x for x in files if x.endswith('.py'))
    for f in py:
        try:
            ast.parse(open(os.path.join(ROOT, f), 'rb').read(), f)
        except SyntaxError as e:
            bad.append('%s:%s: %s' % (f, e.lineno, e.msg))
    print('python: %d files parsed, %d failed' % (len(py), len(bad)))
    return bad


def products():
    """products/<x>/ is a product when it has a src/; otherwise it is a family
    folder, and its subfolders with a src/ are the products."""
    bad, found = [], []
    for d in sorted(glob.glob(os.path.join(ROOT, 'products', '*', ''))):
        kids = [d] if os.path.isdir(os.path.join(d, 'src')) else sorted(glob.glob(os.path.join(d, '*', '')))
        found += [os.path.relpath(k, ROOT) for k in kids if os.path.isdir(os.path.join(k, 'src'))]
    for p in found:
        for f in ('ci.sh', 'ci-setup.sh', 'ci.json'):
            if not os.path.isfile(os.path.join(ROOT, p, 'tools', f)):
                bad.append('%s has no tools/%s: CI would not build it' % (p, f))
        cfg = os.path.join(ROOT, p, 'tools', 'ci.json')
        if os.path.isfile(cfg):
            c = json.load(open(cfg))
            if '@sha256:' not in c.get('image', ''):
                bad.append('%s: tools/ci.json image is not pinned by digest' % p)
            if not isinstance(c.get('timeout'), int):
                bad.append('%s: tools/ci.json has no whole-minute timeout' % p)
    print('products: %d found (%s)' % (len(found), ', '.join(os.path.basename(p) for p in found)))
    return bad


def main():
    files, dirs = git_files()
    bad = links(files, dirs) + python(files) + products()
    for b in bad:
        print('::error::' + b)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
