"""Copy the case build's outputs (out/, git-ignored) to the committed places.

    python3 package.py        after enclosure.py, check.py and render.py

  print/<part>.stl                    what the printer needs, one file per part
  print/fit_check.txt                 the fit check's report
  ../mechanical/smokebreak-enclosure-step.zip   every part and the assembly as STEP
  ../images/case-*.png                the previews (256-colour PNG)

Needs only Pillow, so it runs outside the CadQuery and Blender environments."""
import os
import shutil
import zipfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
PRINT = os.path.join(HERE, 'print')
V1 = os.path.dirname(HERE)
PARTS = ('top', 'bottom', 'guard', 'rocker', 'ring_inlay', 'text_inlay')
PREVIEWS = {'preview_iso': 'case-iso', 'preview_open': 'case-guard-open', 'preview_top': 'case-top',
            'preview_battery_end': 'case-battery-end', 'preview_top_underside': 'case-top-underside',
            'preview_floor': 'case-floor'}


def main():
    os.makedirs(PRINT, exist_ok=True)
    for p in PARTS:
        shutil.copyfile(os.path.join(OUT, p + '.stl'), os.path.join(PRINT, p + '.stl'))
    shutil.copyfile(os.path.join(OUT, 'fit_check.txt'), os.path.join(PRINT, 'fit_check.txt'))
    zp = os.path.join(V1, 'mechanical', 'smokebreak-enclosure-step.zip')
    os.makedirs(os.path.dirname(zp), exist_ok=True)
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in PARTS + ('assembly',):
            z.write(os.path.join(OUT, p + '.step'), 'smokebreak-%s.step' % p.replace('_', '-'))
    for src, dst in PREVIEWS.items():
        im = Image.open(os.path.join(OUT, src + '.png')).convert('RGB')
        if im.width > 1600:
            im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
        im.quantize(256, method=Image.Quantize.MEDIANCUT).save(os.path.join(V1, 'images', dst + '.png'), optimize=True)
    print('print/: %d STL + fit_check.txt; mechanical/smokebreak-enclosure-step.zip; images/case-*.png' % len(PARTS))


if __name__ == '__main__':
    main()
