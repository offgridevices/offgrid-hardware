#!/usr/bin/env python3
"""Shared B-roll design system (1080p output variant for the Canary product video;
same design coordinates, palette, type and background as the 4K original).

Original: shared 4K B-roll design system for the 'Building Beacon 2' explainer clips.

All scenes import this so fonts, colours, background and drawing helpers stay
consistent.  Design coordinate space == final 4K pixels (3840x2160).  An
internal supersample factor SS gives smooth anti-aliased edges.
"""
import os, sys, math, importlib
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ----------------------------------------------------------------- config
DW, DH = 3840, 2160        # design coordinate space (4K)
W, H = 1920, 1080          # final output (1080p)
FPS  = 30
SS   = 0.7                 # buffer = design x 0.7 = 1.4x the 1080p output
BW, BH = int(DW*SS), int(DH*SS)
OUTDIR = os.path.dirname(os.path.abspath(__file__))

def S(v):  # design px -> buffer px
    return v*SS
def Si(v):
    return int(round(v*SS))

# ----------------------------------------------------------------- palette (OffGrid brand)
# Warm dark background, cream text, orange signature accent (#FF6A00).
BG_TOP   = (46, 39, 30)     # lifted warm dark for depth
BG_BOT   = (22, 19, 15)     # brand #1B1813
TEAL     = (255, 106, 0)    # PRIMARY / hero / motion  -> brand orange #FF6A00
TEAL_DK  = (150, 62, 0)
AMBER    = (242, 169, 60)   # secondary / energy / mid state (warm gold)
AMBER_DK = (150, 95, 20)
RED      = (229, 83, 61)    # alert / bad verdict (warm rust)
GREEN    = (140, 196, 96)   # good verdict (warm outdoors green)
SLATE    = (158, 148, 132)  # neutral warm stone (parts / links)
SLATE_DK = (112, 103, 90)
WHITE    = (241, 236, 224)  # brand cream #F1ECE0
SOFTWHITE= (198, 190, 175)  # dim cream (secondary text)
INK      = (26, 22, 17)     # dark text on light chips
CHIP_BG  = (32, 27, 21)     # warm dark chip background
PLASTIC  = (188, 180, 165)  # device shell in cross-sections (warm)
PLASTIC_DK=(134, 126, 112)
PCB      = (58, 120, 96)    # circuit board green (slightly warmed)
COPPER   = (214, 150, 84)   # fits brand warmth
MAGNET   = (192, 185, 172)  # metallic warm
MAGNET_HI= (233, 227, 214)

# ----------------------------------------------------------------- fonts (OffGrid brand)
# Brand type is Archivo (display) + JetBrains Mono. Archivo may not be installed in every
# environment and can't always be downloaded, so we bundle fonts next to this file in a
# `fonts/` dir and resolve with graceful fallback: real Archivo if present -> Work Sans
# (bundled grotesque stand-in) -> Poppins (system). Drop Archivo-*.ttf into fonts/ for an
# exact brand match and it will be picked up automatically.
FG = "/usr/share/fonts/truetype/google-fonts"
FONT_DIRS = [os.path.join(OUTDIR, "fonts"),
             os.path.join(OUTDIR, "..", "assets", "fonts"),
             FG]
def _find(*names):
    for n in names:
        for d in FONT_DIRS:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return p
    return None
def _pick(cands, fallback):
    return _find(*cands) or fallback
BOLD_FILE  = _pick(["Archivo-Bold.ttf","Archivo-ExtraBold.ttf","WorkSans-Bold.ttf"],
                   os.path.join(FG,"Poppins-Bold.ttf"))
MED_FILE   = _pick(["Archivo-Medium.ttf","Archivo-SemiBold.ttf","WorkSans-Medium.ttf","WorkSans-Regular.ttf"],
                   os.path.join(FG,"Poppins-Medium.ttf"))
REG_FILE   = _pick(["Archivo-Regular.ttf","WorkSans-Regular.ttf"],
                   os.path.join(FG,"Poppins-Regular.ttf"))
LIGHT_FILE = _pick(["Archivo-Light.ttf","Archivo-Regular.ttf","WorkSans-Regular.ttf"],
                   os.path.join(FG,"Poppins-Light.ttf"))
MONO_FILE  = _pick(["JetBrainsMono-Bold.ttf","JetBrainsMono-Regular.ttf"],
                   "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf")
_FONT_CACHE = {}
def _f(path, size):
    key=(path,int(size))
    if key not in _FONT_CACHE:
        _FONT_CACHE[key]=ImageFont.truetype(path, int(size))
    return _FONT_CACHE[key]
def bold(sz):  return _f(BOLD_FILE,  Si(sz))
def med(sz):   return _f(MED_FILE,   Si(sz))
def reg(sz):   return _f(REG_FILE,   Si(sz))
def light(sz): return _f(LIGHT_FILE, Si(sz))
def mono(sz):  return _f(MONO_FILE,  Si(sz))

# ----------------------------------------------------------------- easing / math
def clamp01(t): return 0.0 if t<0 else (1.0 if t>1 else t)
def smooth(t):  t=clamp01(t); return t*t*(3-2*t)
def smoother(t):t=clamp01(t); return t*t*t*(t*(t*6-15)+10)
def ease_out(t):t=clamp01(t); return 1-(1-t)*(1-t)
def ease_in(t): t=clamp01(t); return t*t
def lerp(a,b,t): return a+(b-a)*t
def lerpc(c1,c2,t):
    t=clamp01(t)
    return tuple(int(round(lerp(c1[i],c2[i],t))) for i in range(3))
def pulse(t, spd=2.0, lo=0.7, hi=1.0, ph=0.0):
    return lo+(hi-lo)*(0.5+0.5*math.sin(t*spd+ph))

# ----------------------------------------------------------------- background (cached per process)
_BG=None
def _build_bg():
    top=np.array(BG_TOP,np.float32); bot=np.array(BG_BOT,np.float32)
    ramp=np.linspace(0,1,BH,dtype=np.float32)[:,None,None]
    col=top[None,None,:]*(1-ramp)+bot[None,None,:]*ramp
    arr=np.repeat(col,BW,axis=1)
    img=Image.fromarray(arr.astype(np.uint8),'RGB')
    d=ImageDraw.Draw(img,'RGBA')
    step=Si(92); r=max(1,Si(2.2))
    for yy in range(0,BH,step):
        for xx in range(0,BW,step):
            d.ellipse([xx-r,yy-r,xx+r,yy+r],fill=(255,255,255,10))
    # gentle vignette for depth (keeps overall mid-tone)
    vig=Image.new('L',(BW,BH),0); vd=ImageDraw.Draw(vig)
    m=Si(40)
    vd.ellipse([-BW*0.15,-BH*0.15,BW*1.15,BH*1.15],fill=46)
    vig=vig.filter(ImageFilter.GaussianBlur(Si(120)))
    dark=Image.new('RGB',(BW,BH),(0,0,0))
    img=Image.composite(img,Image.blend(img,dark,0.16),vig)
    return np.asarray(img,np.float32)
def bg_float():
    global _BG
    if _BG is None: _BG=_build_bg()
    return _BG.copy()

def fast_blur(img, radius):
    f=3
    s=img.resize((max(1,img.width//f),max(1,img.height//f)),Image.BILINEAR)
    s=s.filter(ImageFilter.GaussianBlur(max(0.5,radius/f)))
    return s.resize(img.size,Image.BILINEAR)

def screen(base_f, layer_img):
    # in-place to keep peak memory low: out = 255 - (255-base)*(255-layer)/255
    layer=np.asarray(layer_img.convert('RGB'),np.float32)
    np.subtract(255.0, base_f, out=base_f)      # base = 255-base
    np.subtract(255.0, layer, out=layer)        # layer = 255-layer
    layer*=base_f
    layer*=(1.0/255.0)
    np.subtract(255.0, layer, out=layer)
    return layer

# ----------------------------------------------------------------- Canvas
class Canvas:
    """Two-stage canvas: accumulate additive glow, composite, then draw crisp."""
    def __init__(self):
        self.base=bg_float()
        self.glow=Image.new('RGB',(BW,BH),(0,0,0))
        self.g=ImageDraw.Draw(self.glow)
        self.img=None; self.d=None; self._glow_radius=Si(22)

    # ---- glow stage ----
    def glow_disk(self,x,y,r,color,inten=1.0):
        c=tuple(min(255,int(ch*inten)) for ch in color)
        self.g.ellipse([S(x)-S(r),S(y)-S(r),S(x)+S(r),S(y)+S(r)],fill=c)
    def glow_line(self,x1,y1,x2,y2,color,inten=1.0,width=4):
        c=tuple(min(255,int(ch*inten)) for ch in color)
        self.g.line([S(x1),S(y1),S(x2),S(y2)],fill=c,width=Si(width))
    def glow_rect(self,x0,y0,x1,y1,color,inten=1.0,radius=0):
        c=tuple(min(255,int(ch*inten)) for ch in color)
        if radius>0:
            self.g.rounded_rectangle([S(x0),S(y0),S(x1),S(y1)],radius=S(radius),fill=c)
        else:
            self.g.rectangle([S(x0),S(y0),S(x1),S(y1)],fill=c)

    def composite(self, glow_radius=None):
        gr=self._glow_radius if glow_radius is None else Si(glow_radius)
        gb=fast_blur(self.glow,gr)
        self.base=screen(self.base,gb)
        self.img=Image.fromarray(np.clip(self.base,0,255).astype(np.uint8),'RGB')
        self.d=ImageDraw.Draw(self.img,'RGBA')

    # ---- crisp stage helpers (auto-scale design coords) ----
    def _col(self,c,a):
        return (c[0],c[1],c[2],int(a)) if len(c)==3 else c
    def disk(self,x,y,r,color,a=255):
        self.d.ellipse([S(x)-S(r),S(y)-S(r),S(x)+S(r),S(y)+S(r)],fill=self._col(color,a))
    def ring(self,x,y,r,color,a=255,width=4):
        self.d.ellipse([S(x)-S(r),S(y)-S(r),S(x)+S(r),S(y)+S(r)],outline=self._col(color,a),width=Si(width))
    def line(self,x1,y1,x2,y2,color,a=255,width=4):
        self.d.line([S(x1),S(y1),S(x2),S(y2)],fill=self._col(color,a),width=Si(width))
    def rect(self,x0,y0,x1,y1,color,a=255,width=0,outline=None,oa=255):
        fill=self._col(color,a) if color is not None else None
        out=self._col(outline,oa) if outline is not None else None
        self.d.rectangle([S(x0),S(y0),S(x1),S(y1)],fill=fill,outline=out,width=Si(width))
    def rrect(self,x0,y0,x1,y1,color,a=255,radius=20,width=0,outline=None,oa=255):
        fill=self._col(color,a) if color is not None else None
        out=self._col(outline,oa) if outline is not None else None
        self.d.rounded_rectangle([S(x0),S(y0),S(x1),S(y1)],radius=S(radius),
                                 fill=fill,outline=out,width=Si(width))
    def poly(self,pts,color,a=255,width=0,outline=None,oa=255):
        sp=[(S(x),S(y)) for (x,y) in pts]
        fill=self._col(color,a) if color is not None else None
        out=self._col(outline,oa) if outline is not None else None
        self.d.polygon(sp,fill=fill,outline=out,width=Si(width) if width else 0)
    def arc(self,x0,y0,x1,y1,start,end,color,a=255,width=4):
        self.d.arc([S(x0),S(y0),S(x1),S(y1)],start=start,end=end,
                   fill=self._col(color,a),width=Si(width))

    def text(self,cx,cy,s,font,color,a=255,ls=0,anchor='mm'):
        """anchor: mm=center, lm=left-mid, rm=right-mid, ma=top-center."""
        col=self._col(color,a)
        if ls==0:
            self.d.text((S(cx),S(cy)),s,font=font,fill=col,anchor=anchor)
            return
        # letter-spaced, centered horizontally
        widths=[self.d.textlength(ch,font=font) for ch in s]
        total=sum(widths)+S(ls)*(len(s)-1)
        x=S(cx)-total/2
        for ch,w in zip(s,widths):
            self.d.text((x,S(cy)),ch,font=font,fill=col,anchor='lm')
            x+=w+S(ls)

    def image(self, im, cx, cy, width, a=1.0):
        """Paste an RGBA image centred at design (cx, cy), scaled to design width."""
        w = Si(width); h = int(round(im.height * w / im.width))
        im2 = im.resize((w, h), Image.LANCZOS)
        if a < 0.999:
            al = im2.getchannel('A').point(lambda v: int(v * a))
            im2.putalpha(al)
        self.img.paste(im2, (int(S(cx) - w / 2), int(S(cy) - h / 2)), im2)

    def finish(self):
        return self.img.resize((W,H),Image.LANCZOS)

# ----------------------------------------------------------------- shared motifs
def node(cv,x,y,r,color,appear=1.0,core=True,glow=0.8):
    if appear<=0.01: return
    cv.glow_disk(x,y,r*2.4,color,glow*appear)
def node_core(cv,x,y,r,color,appear=1.0,core=True,ring_c=None):
    if appear<=0.01: return
    rr=r*smooth(appear)
    cv.disk(x,y,rr,color)
    cv.ring(x,y,rr,ring_c or lerpc(color,WHITE,0.4),width=3)
    if core:
        cv.disk(x,y,rr*0.26,WHITE)

def chip(cv,cx,cy,text,font,fg,bg=CHIP_BG,pad=26,a=255,radius=18,border=None):
    """rounded pill label with centered text."""
    w=cv.d.textlength(text,font=font)/SS
    asc,desc=font.getmetrics(); th=(asc+desc)/SS
    hw=w/2+pad; hh=th/2+pad*0.72
    cv.rrect(cx-hw,cy-hh,cx+hw,cy+hh,bg,a=int(a*0.92),radius=radius,
             width=3 if border else 0,outline=border,oa=a)
    cv.text(cx,cy,text,font,fg,a=a)
    return hw,hh

def dim_h(cv,x0,x1,y,label,font,color=WHITE,a=255,tick=22):
    """horizontal dimension line with arrows + label above."""
    cv.line(x0,y,x1,y,color,a=a,width=3)
    cv.line(x0,y-tick,x0,y+tick,color,a=a,width=3)
    cv.line(x1,y-tick,x1,y+tick,color,a=a,width=3)
    cv.text((x0+x1)/2,y-tick-S(2)/SS-44,label,font,color,a=a)

def dim_v(cv,x,y0,y1,label,font,color=WHITE,a=255,tick=22,side='left'):
    cv.line(x,y0,x,y1,color,a=a,width=3)
    cv.line(x-tick,y0,x+tick,y0,color,a=a,width=3)
    cv.line(x-tick,y1,x+tick,y1,color,a=a,width=3)
    if side=='left':
        cv.text(x-tick-70,(y0+y1)/2,label,font,color,a=a,anchor='rm')
    else:
        cv.text(x+tick+70,(y0+y1)/2,label,font,color,a=a,anchor='lm')

def checkmark(cv,cx,cy,sz,color,a=255,width=10):
    cv.line(cx-sz*0.5,cy+sz*0.05,cx-sz*0.12,cy+sz*0.42,color,a=a,width=width)
    cv.line(cx-sz*0.12,cy+sz*0.42,cx+sz*0.55,cy-sz*0.45,color,a=a,width=width)
def xmark(cv,cx,cy,sz,color,a=255,width=10):
    cv.line(cx-sz*0.45,cy-sz*0.45,cx+sz*0.45,cy+sz*0.45,color,a=a,width=width)
    cv.line(cx+sz*0.45,cy-sz*0.45,cx-sz*0.45,cy+sz*0.45,color,a=a,width=width)

def phone(cv,cx,cy,w,h,a=255,fill=(34,42,58),outline=SLATE):
    """simple rounded phone body centred at cx,cy."""
    cv.rrect(cx-w/2,cy-h/2,cx+w/2,cy+h/2,fill,a=a,radius=w*0.13,width=5,outline=outline,oa=a)
    # camera bump
    cv.rrect(cx-w/2+w*0.10,cy-h/2+h*0.045,cx-w/2+w*0.42,cy-h/2+h*0.30,(24,30,44),a=a,radius=w*0.07)

# ----------------------------------------------------------------- render driver
def render_frames(scene, a, b, fps=FPS):
    name=scene.NAME
    fdir=os.path.join(OUTDIR,"fr_"+name)
    os.makedirs(fdir,exist_ok=True)
    for i in range(a,b):
        t=i/fps
        scene.render(t).save(os.path.join(fdir,f"f{i:04d}.png"))
    return fdir

def _worker(args):
    modname,i=args
    scene=importlib.import_module(modname)
    t=i/FPS
    fdir=os.path.join(OUTDIR,"fr_"+scene.NAME)
    scene.render(t).save(os.path.join(fdir,f"f{i:04d}.png"))
    return i

def main_driver():
    """Usage:
       python3 -m broll_lib <scene_module> test <t>
       python3 -m broll_lib <scene_module> range <a> <b>   (parallel)
    """
    modname=sys.argv[1]; mode=sys.argv[2]
    scene=importlib.import_module(modname)
    if mode=='test':
        t=float(sys.argv[3])
        p=os.path.join(OUTDIR,f"test_{scene.NAME}_{t:0.1f}.png")
        scene.render(t).save(p); print("wrote",p); return
    if mode=='range':
        import multiprocessing as mp
        a=int(sys.argv[3]); b=min(int(sys.argv[4]),int(scene.DURATION*FPS))
        fdir=os.path.join(OUTDIR,"fr_"+scene.NAME); os.makedirs(fdir,exist_ok=True)
        tasks=[(modname,i) for i in range(a,b)]
        nproc=int(os.environ.get("NPROC","4"))
        with mp.Pool(nproc) as pool:
            for _ in pool.imap_unordered(_worker,tasks,chunksize=2):
                pass
        print(f"DONE {scene.NAME} {a}-{b}")
        return

if __name__=='__main__':
    main_driver()
