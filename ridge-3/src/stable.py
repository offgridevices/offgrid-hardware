# -*- coding: utf-8 -*-
"""Outputs that change only when what they hold changes.

KiCad stamps every Gerber, drill file, job file and STEP with the time it
ran and the build of KiCad that ran it, numbers a STEP's entities
differently each run, and its raytracer never draws the same noise twice;
a zip entry keeps its file's time.  Left alone, every rebuild rewrites
every output and git cannot tell a changed board from a re-run.  So:

  keep_if_same(path, old)   after an export: if the new file (or each file
                            in a new zip) differs from the committed one
                            only in its stamps, put the committed bytes
                            back (the Gerber zips, the panel's files)
  zip_files(zp, files)      a zip whose bytes depend only on its contents
  zip_one(raw, zp)          zip one file, keeping the committed zip if it
                            holds the same file but for its stamps
  render(...), exported_zip(...)
                            a kicad-cli render or STEP, made only when the
                            board, a 3D model it uses, KiCad or the options
                            changed: the hash of those (inputs_key) is kept
                            in the PNG, or in the zip's comment
  files_key(paths, opts)    the same for a picture made in Python from files
                            (the silkscreen read back from the Gerbers, the
                            stack sheet): kept in the PNG by save_png
  save_png(im, png, text)   a picture as a 256-colour PNG, with its key
"""
import functools, hashlib, io, os, re, subprocess, zipfile

# Lines that carry only when a tool ran and which build of it: Gerber X2
# (and Excellon's copy of it) and the G04 comment, Excellon's header, the
# Gerber job file, the STEP header.  The build string ("10.0.6-10.0.6~
# ubuntu24.04.1" from Ubuntu's package) differs between packagings of the
# same KiCad release, e.g. the CI image's.
STAMPS = re.compile(rb'^(?:.*TF\.CreationDate,.*'
                    rb'|.*TF\.GenerationSoftware,.*'
                    rb'|G04 Created by .* date .*'
                    rb'|; DRILL file .* date .*'
                    rb'|\s*"CreationDate":.*'
                    rb'|\s*"Version":.*'
                    rb"|FILE_NAME\('.*)\r?$", re.M)
ZIP_TIME = (1980, 1, 1, 0, 0, 0)      # the earliest a zip can hold
KEY = 'ridge3-inputs'                 # PNG text chunk / zip comment prefix


def unstamped(data):
    return STAMPS.sub(b'', data)


def read(path):
    """The file's bytes, or None."""
    try:
        with open(path, 'rb') as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def _contents(data, name):
    """What a file holds without its stamps (a zip: each entry's)."""
    if not name.endswith('.zip'):
        return unstamped(data)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return sorted((n, unstamped(z.read(n))) for n in z.namelist())
    except zipfile.BadZipFile:
        return data


def keep_if_same(path, old):
    """old: the committed bytes of path (None if it had none).  Returns True
    if the new file was the same but for its stamps and old is back."""
    if old is None:
        return False
    new = read(path)
    if new is None or new == old or _contents(new, path) != _contents(old, path):
        return False
    with open(path, 'wb') as fh:
        fh.write(old)
    return True


def snapshot(folder):
    """{name: bytes} of the files in folder, for keep_if_same after the
    folder is regenerated."""
    if not os.path.isdir(folder):
        return {}
    return {f: read(os.path.join(folder, f)) for f in os.listdir(folder)
            if os.path.isfile(os.path.join(folder, f))}


def zip_files(zp, files, comment=''):
    """files: [(path, name in the zip)].  Fixed times and modes, deflate 9."""
    with zipfile.ZipFile(zp, 'w') as z:
        z.comment = comment.encode()
        for path, arc in files:
            zi = zipfile.ZipInfo(arc, date_time=ZIP_TIME)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, read(path), compresslevel=9)


def zip_one(raw, zp):
    """Zip raw (then delete it) unless the committed zip holds the same file
    but for its stamps; True if the committed zip was kept."""
    old = read(zp)
    zip_files(zp, [(raw, os.path.basename(raw))])
    os.remove(raw)
    return keep_if_same(zp, old)


# ------------------------------------------- made only when inputs change
@functools.lru_cache()
def kicad_version():
    return subprocess.run(['kicad-cli', '--version'], capture_output=True, text=True).stdout.strip()


def _model_file(name, proj):
    """A board's 3D model path with KiCad's variables resolved."""
    name = name.replace('${KIPRJMOD}', proj)
    return re.sub(r'\$\{(KICAD\d+_3DMODEL_DIR)\}',
                  lambda v: os.environ.get(v.group(1), '/usr/share/kicad/3dmodels'), name)


def inputs_key(board, opts):
    """Hash of what a kicad-cli render or STEP of board is made from: the
    board file, each 3D model it names (and its .step/.wrl twin, which
    --subst-models may use), the KiCad version and the options."""
    h = hashlib.sha256()
    text = read(board)
    h.update(text)
    proj = os.path.dirname(os.path.abspath(board))
    for m in sorted(set(re.findall(rb'\(model "([^"]+)"', text))):
        p = _model_file(m.decode(), proj)
        stem = os.path.splitext(p)[0]
        h.update(m)
        for f in (p, stem + '.step', stem + '.wrl'):
            if os.path.isfile(f):
                h.update(os.path.basename(f).encode() + read(f))
    h.update(kicad_version().encode())
    h.update(repr(opts).encode())
    return '%s %s' % (KEY, h.hexdigest()[:16])


def files_key(paths, opts):
    """Hash of what a picture made in Python is made from: the files
    (without KiCad's stamps) and opts (the code that draws it and its
    options)."""
    h = hashlib.sha256()
    for p in paths:
        h.update(os.path.basename(p).encode() + unstamped(read(p) or b''))
    h.update(repr(opts).encode())
    return '%s %s' % (KEY, h.hexdigest()[:16])


def png_key(png):
    """The inputs key a PNG carries, or None."""
    try:
        from PIL import Image
        with Image.open(png) as im:
            return im.text.get(KEY)
    except (FileNotFoundError, OSError):
        return None


def save_png(im, png, text=None):
    """A picture (PIL image) as a 256-colour PNG: a fifth to half the size.
    An opaque picture by median cut refined by one k-means pass (a heat
    map's colour bar keeps its steps small); one with transparency (the
    renders) by fast octree, the way Pillow keeps alpha.  text: the PNG's
    text chunks (the inputs key)."""
    from PIL import Image, PngImagePlugin
    info = PngImagePlugin.PngInfo()
    for k, v in (text or {}).items():
        info.add_text(k, v)
    src = im.convert('RGBA')
    if src.getchannel('A').getextrema() == (255, 255):
        src = src.convert('RGB')
    q = (src.quantize(256, method=Image.Quantize.MEDIANCUT, kmeans=1) if src.mode == 'RGB'
         else src.quantize(256, method=Image.Quantize.FASTOCTREE))
    extra = {'dpi': im.info['dpi']} if 'dpi' in im.info else {}
    q.save(png, pnginfo=info, optimize=True, **extra)


def compact(png):
    """Save a full-colour PNG file again as 256 colours (save_png), its text
    chunks kept."""
    from PIL import Image
    with Image.open(png) as im:
        im.load()
        save_png(im, png, dict(im.text))


def _zip_key(zp):
    try:
        with zipfile.ZipFile(zp) as z:
            return z.comment.decode()
    except (FileNotFoundError, zipfile.BadZipFile):
        return None


def render(cmd, png, board, run):
    """Run cmd (a kicad-cli render of board into png) unless png already
    carries this key; then store the key in it.  run: the caller's
    subprocess wrapper.  True if it rendered."""
    key = inputs_key(board, [c for c in cmd if c not in (png, board)])
    if png_key(png) == key:
        return False
    run(cmd)
    from PIL import Image
    with Image.open(png) as im:
        im.load()
        save_png(im, png, {KEY: key})
    return True


def exported_zip(cmd, raw, zp, board, run):
    """Run cmd (a kicad-cli export of board into raw) and zip raw into zp,
    unless zp's comment already holds this key.  True if it exported."""
    key = inputs_key(board, [c for c in cmd if c not in (raw, board)])
    if _zip_key(zp) == key:
        return False
    run(cmd)
    zip_files(zp, [(raw, os.path.basename(raw))], comment=key)
    os.remove(raw)
    return True
