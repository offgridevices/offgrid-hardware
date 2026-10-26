"""The setup page and the live picture, on port 80.

    GET  /                 the page: live picture, status, settings
    GET  /snapshot.jpg     one fresh frame
    POST /api/live         {"seconds": N}: live view for up to camera.live_max_s;
                           refused when the SoC is hot (thermal.py)
    POST /api/live/stop
    GET  /stream.mjpg      multipart MJPEG, about 2 frames a second, while live view is on
    GET  /api/status       JSON
    GET  /api/config       JSON, secrets shown only as set / not set
    POST /api/config       JSON {"section.key": value, ...}; an empty secret keeps the old one
    POST /api/connect-test send one snapshot to Connect now
    GET  /api/update       the running version and the update state
    POST /api/update       a signed update package (.lcup, the request body): checked,
                           installed, and the camera restarts into it on trial (update.py)
    GET  /videos/          the recordings kept on the camera; /videos/<folder>.mp4 streams one

With web.password set, everything asks for it (HTTP Basic, user "admin").
On the setup access point it is open until a password is set, so the first
setup needs nothing but a phone.
"""
import base64, hmac, json, logging, os, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import VERSION, config as config_mod, recording, update

log = logging.getLogger('web')

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>LayerCam</title>
<style>
body{font-family:system-ui,sans-serif;margin:0 auto;max-width:860px;padding:12px;background:#f6f6f4;color:#222}
img{width:100%;background:#000;border-radius:6px}fieldset{border:1px solid #ccc;border-radius:6px;margin:10px 0}
label{display:flex;justify-content:space-between;gap:8px;margin:4px 0}input,select{width:55%}
button{padding:8px 14px;margin:4px 4px 4px 0}#msg{white-space:pre-wrap;color:#a40}code{font-size:90%}
</style></head><body>
<h2>LayerCam</h2><img id="live" src="/snapshot.jpg" alt="picture">
<button onclick="live()">Live view (2 min)</button><button onclick="still()">Still picture</button>
<p id="status">...</p><div id="msg"></div>
<form id="f"></form>
<button onclick="save()">Save and apply</button><button onclick="test()">Send a snapshot to Connect</button>
<p><a href="/videos/">Timelapses on the camera</a></p>
<fieldset><legend>software</legend><p id="ver"></p>
<input type="file" id="pkg" accept=".lcup"> <button onclick="upd()">Install update</button></fieldset>
<script>
const secretNote='(set; leave empty to keep)';
async function load(){
 const c=await (await fetch('/api/config')).json(); const f=document.getElementById('f'); f.innerHTML='';
 for(const [s,keys] of Object.entries(c.values)){
  const fs=document.createElement('fieldset'); fs.innerHTML='<legend>'+s+'</legend>';
  for(const [k,v] of Object.entries(keys)){
   const id=s+'.'+k, secret=c.secrets.includes(id), ch=c.choices[id];
   let inp; if(ch){inp=document.createElement('select'); for(const o of ch){const op=document.createElement('option');op.value=o;op.text=o;if(String(o)===String(v))op.selected=true;inp.add(op);}}
   else{inp=document.createElement('input'); if(secret){inp.type='password';inp.placeholder=v?secretNote:'';}
        else if(typeof v==='boolean'){inp.type='checkbox';inp.checked=v;} else inp.value=v;}
   inp.name=id; const l=document.createElement('label'); l.textContent=k; l.appendChild(inp); fs.appendChild(l);}
  f.appendChild(fs);}
}
async function status(){try{const s=await (await fetch('/api/status')).json();
 document.getElementById('status').textContent=JSON.stringify(s);}catch(e){}}
async function save(){const body={}; for(const el of document.getElementById('f').elements){
  if(el.type==='password'&&!el.value)continue; body[el.name]=el.type==='checkbox'?el.checked:el.value;}
 const r=await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const j=await r.json(); document.getElementById('msg').textContent=j.ok?'Saved. Applying...':j.errors.join('\\n'); load();}
async function live(){const r=await fetch('/api/live',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"seconds":120}'});
 const j=await r.json(); if(j.ok){document.getElementById('live').src='/stream.mjpg?'+Date.now();}
 else document.getElementById('msg').textContent=j.error;}
function still(){fetch('/api/live/stop',{method:'POST'}); document.getElementById('live').src='/snapshot.jpg?'+Date.now();}
async function upd(){const f=document.getElementById('pkg').files[0]; const m=document.getElementById('msg');
 if(!f){m.textContent='Choose a .lcup update package first';return;} m.textContent='Checking '+f.name+'...';
 try{const r=await fetch('/api/update',{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:f});
  const j=await r.json(); m.textContent=j.ok?j.message:'Update refused: '+j.error;}catch(e){m.textContent='Update: '+e;}}
async function ver(){try{const u=await (await fetch('/api/update')).json();
 document.getElementById('ver').textContent='Version '+u.running+(u.trial?' (on trial)':'')+(u.last?': '+u.last:'');}catch(e){}}
async function test(){const j=await (await fetch('/api/connect-test',{method:'POST'})).json();
 document.getElementById('msg').textContent=j.ok?'Snapshot sent':'Connect: '+j.error;}
load(); status(); ver(); setInterval(status,3000);
</script></body></html>"""


def apply_form(cfg, form):
    """Copy submitted fields into a copy of cfg.  -> (new Config, errors)."""
    new = config_mod.Config(path=cfg.path)
    new.values = {s: dict(v) for s, v in cfg.values.items()}
    new.extra = dict(cfg.extra)       # settings this version does not know stay in the file
    errors = []
    for name, value in form.items():
        if '.' not in name:
            errors.append('bad field %s' % name)
            continue
        s, k = name.split('.', 1)
        if (s, k) == ('device', 'fingerprint'):
            continue           # bound to the Connect token: never changed from the page
        if (s, k) in config_mod.SECRETS and value in ('', None):
            continue
        try:
            new.set(s, k, value)
        except config_mod.ConfigError as e:
            errors.append(str(e))
    return new, errors + new.errors()


class Handler(BaseHTTPRequestHandler):
    server_version = 'LayerCam'
    app = None                  # the service.Service, set by serve()

    def log_message(self, fmt, *a):
        log.debug(fmt, *a)

    def _authorised(self):
        pw = self.app.cfg.get('web', 'password')
        if not pw:
            return True
        h = self.headers.get('Authorization', '')
        if h.startswith('Basic '):
            try:
                user, _, given = base64.b64decode(h[6:]).decode().partition(':')
            except (ValueError, UnicodeDecodeError):
                return False
            if user == 'admin' and hmac.compare_digest(given.encode(), pw.encode()):
                return True
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="LayerCam"')
        self.send_header('Content-Length', '0')
        self.end_headers()
        return False

    def _send(self, code, body, ctype='application/json'):
        if not isinstance(body, (bytes, bytearray)):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._authorised():
            return
        p = self.path.split('?')[0]
        try:
            if p == '/':
                return self._send(200, PAGE.encode(), 'text/html; charset=utf-8')
            if p == '/api/status':
                return self._send(200, self.app.status())
            if p == '/api/update':
                st = self.app.apps.state()
                return self._send(200, {'running': VERSION, 'trial': bool(st['pending']), 'good': st['good'],
                                        'failed': st['failed'], 'last': st['last']})
            if p == '/api/config':
                cfg = self.app.cfg
                return self._send(200, {'values': cfg.public(),
                                        'secrets': ['%s.%s' % sk for sk in config_mod.SECRETS],
                                        'choices': {'%s.%s' % sk: list(v) for sk, v in config_mod.CHOICES.items()}})
            if p == '/snapshot.jpg':
                return self._send(200, self.app.snapshot(85), 'image/jpeg')
            if p == '/stream.mjpg' and not self.app.live_active():
                return self._send(409, {'error': 'live view is off: POST /api/live first'})
            if p == '/stream.mjpg':
                return self._stream()
            if p == '/videos/':
                return self._videos()
            if p.startswith('/videos/') and p.endswith('.mp4'):
                return self._video(p[8:-4])
            self._send(404, {'error': 'not found'})
        except Exception as e:      # a page error must not take the camera down
            log.exception('GET %s', p)
            try:
                self._send(500, {'error': str(e)})
            except OSError:
                pass

    def do_POST(self):
        if not self._authorised():
            return
        p = self.path
        try:
            n = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            return self._send(400, {'error': 'Content-Length'})
        if p == '/api/update':
            return self._update(n)
        if n > 65536:
            return self._send(413, {'error': 'too large'})
        raw = self.rfile.read(n) if n else b''
        if p == '/api/config':
            try:
                form = json.loads(raw or b'{}')
            except ValueError:
                return self._send(400, {'ok': False, 'errors': ['not JSON']})
            new, errors = apply_form(self.app.cfg, form)
            if errors:
                return self._send(400, {'ok': False, 'errors': errors})
            self._send(200, {'ok': True})
            threading.Thread(target=self.app.apply_config, args=(new,), daemon=True).start()
            return
        if p == '/api/connect-test':
            ok, err = self.app.connect_test()
            return self._send(200 if ok else 502, {'ok': ok, 'error': err})
        if p == '/api/live':
            try:
                seconds = int(json.loads(raw or b'{}').get('seconds', 120))
            except (ValueError, AttributeError):
                return self._send(400, {'ok': False, 'error': 'seconds'})
            ok, err = self.app.start_live(seconds)
            return self._send(200 if ok else 409, {'ok': ok, 'error': err})
        if p == '/api/live/stop':
            self.app.stop_live()
            return self._send(200, {'ok': True})
        self._send(404, {'error': 'not found'})

    def _update(self, n):
        if not 0 < n <= update.MAX_PACKAGE:
            return self._send(413, {'ok': False, 'error': 'a package is 1 byte to %d MB' % (update.MAX_PACKAGE >> 20)})
        folder = os.path.join(self.app.cfg_dir, 'app')
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, 'incoming.lcup')
        try:
            with open(path, 'wb') as f:
                left = n
                while left:
                    chunk = self.rfile.read(min(65536, left))
                    if not chunk:
                        return self._send(400, {'ok': False, 'error': 'upload cut off'})
                    f.write(chunk)
                    left -= len(chunk)
            ok, msg = self.app.install_update(path)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        if not ok:
            return self._send(400, {'ok': False, 'error': msg})
        self._send(200, {'ok': True, 'message': msg})

        def later():
            time.sleep(1.0)              # the answer reaches the page first
            self.app.restart(reselect=self.app.on_camera_layout())
        threading.Thread(target=later, daemon=True).start()

    def _stream(self):
        self.send_response(200)
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        if not self.app.stream_slot.acquire(blocking=False):
            return              # two viewers at most: the camera has other work
        try:
            # only while live view is on (POST /api/live): it ends by itself,
            # and when the SoC gets hot
            while self.app.live_active():
                jpg = self.app.snapshot(70)
                self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n' % len(jpg))
                self.wfile.write(jpg + b'\r\n')
                time.sleep(0.5)
        except (OSError, ConnectionError):
            pass
        finally:
            self.app.stream_slot.release()

    def _videos(self):
        rows = []
        for folder, m in recording.list_recordings(self.app.storage):
            rows.append('<li><a href="/videos/%s.mp4">%s</a> - %d frames, %s</li>'
                        % (os.path.basename(folder), m['name'], m.get('frames', 0), m.get('state')))
        html = '<!doctype html><meta charset="utf-8"><h3>Timelapses</h3><ul>%s</ul>' % ''.join(rows)
        self._send(200, html.encode(), 'text/html; charset=utf-8')

    def _video(self, folder_name):
        if '/' in folder_name or folder_name.startswith('.'):
            return self._send(400, {'error': 'bad name'})
        folder = os.path.join(self.app.storage, folder_name)
        meta = recording.load_meta(folder)
        if not meta or meta.get('state') == 'recording':
            return self._send(404, {'error': 'no finished video'})
        body = recording.body_for(folder, self.app.cfg.get('camera', 'helper'))
        if body is None:
            return self._send(404, {'error': 'empty'})
        self.send_response(200)
        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Content-Length', str(body.size))
        self.send_header('Content-Disposition', 'attachment; filename="%s"' % body.name.replace('"', ''))
        self.end_headers()
        for c in body.chunks():
            self.wfile.write(c)


def serve(app, port):
    Handler.app = app
    srv = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    srv.daemon_threads = True
    t = threading.Thread(target=srv.serve_forever, name='web', daemon=True)
    t.start()
    return srv
