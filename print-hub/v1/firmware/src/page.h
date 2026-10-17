// The control page at http://printhub.local/ : the ports with on/off
// buttons, their current, and the Wi-Fi form in setup mode.  It only uses
// /api/status and /api/cmd, the same API the printhub CLI uses.
#pragma once
static const char PAGE[] PROGMEM = R"HTML(<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Print Hub</title>
<style>
:root{--bg:#1B1813;--fg:#F1ECE0;--dim:#9A9082;--on:#4caf50;--bad:#e5533d;--line:#3a352c}
body{margin:0;background:var(--bg);color:var(--fg);font:16px system-ui,sans-serif}
main{max-width:640px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:0 0 4px}.dim{color:var(--dim);font-size:14px}
.port{display:flex;align-items:center;gap:12px;border-bottom:1px solid var(--line);padding:12px 0}
.port .n{flex:1}.port b{display:block}.dot{width:12px;height:12px;border-radius:50%;background:var(--line)}
.dot.on{background:var(--on)}.dot.bad{background:var(--bad)}
button{background:transparent;color:var(--fg);border:1px solid var(--dim);border-radius:6px;padding:8px 14px;font:inherit}
button.on{border-color:var(--on)}input{background:#000;color:var(--fg);border:1px solid var(--dim);padding:8px;border-radius:6px;width:100%;box-sizing:border-box;margin:4px 0}
#msg{color:var(--bad);min-height:20px}
</style></head><body><main>
<h1>Print Hub</h1><div class="dim" id="sum">…</div><div id="msg"></div>
<div id="ports"></div>
<div id="setup" hidden><h2>Join Wi-Fi</h2>
<input id="ssid" placeholder="Network name"><input id="pass" placeholder="Password" type="password">
<button onclick="joinWifi()">Join</button></div>
<p class="dim">Token (if set): <input id="tok" type="password" onchange="localStorage.tok=this.value"></p>
</main><script>
const $=id=>document.getElementById(id);try{$('tok').value=localStorage.tok||''}catch(e){}
const why={overcurrent:'drew more than its limit',fault:'short circuit or overheating',shed:'charger ran out of power',no_power:'not enough power',timer:'timer ended'};
function hdr(){const t=$('tok').value;return t?{Authorization:'Bearer '+t}:{}}
async function cmd(line){const r=await fetch('/api/cmd',{method:'POST',headers:hdr(),body:line});const j=await r.json();$('msg').textContent=j.ok?'':j.error;refresh()}
function q(s){return '"'+s.replace(/"/g,'')+'"'}
function joinWifi(){cmd('wifi '+q($('ssid').value)+' '+q($('pass').value))}
async function refresh(){try{const r=await fetch('/api/status',{headers:hdr()});const s=await r.json();
if(!s.ok){$('msg').textContent=s.error;return}
$('sum').textContent=`Charger: ${s.input.contract||'none'} · using ${s.total_ma} of ${s.budget_ma} mA · ${s.ip||''}`;
$('setup').hidden=!(s.ip||'').includes('setup');
$('ports').innerHTML=s.ports.map(p=>{const bad=!p.on&&(p.last_off=='overcurrent'||p.last_off=='fault');
const note=p.on?(p.ma+' mA'+(p.off_in_s>=0?` · off in ${Math.ceil(p.off_in_s/60)} min`:'')):(why[p.last_off]||'off');
return `<div class="port"><span class="dot ${p.on?'on':bad?'bad':''}"></span><div class="n"><b>${p.port}. ${p.name}</b><span class="dim">${note}</span></div>
<button class="${p.on?'on':''}" onclick="cmd('${p.on?'off':'on'} ${p.port}')">${p.on?'Turn off':'Turn on'}</button></div>`}).join('')
}catch(e){$('sum').textContent='Cannot reach the board'}}
refresh();setInterval(refresh,2000);
</script></body></html>)HTML";
