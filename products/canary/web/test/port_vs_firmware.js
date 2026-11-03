/* ---------------------------------------------------------- detect.c port */
const K = { WARMUP_S: 90, GAS_WEAK: 700, GAS_STRONG: 2500, CO2_RATE_WEAK: 250, CO2_RATE_STRONG: 1200,
  CO2_EXCESS_STRONG: 4000, T_WEAK: 500, T_STRONG: 650, DTDT_WEAK: 10, DTDT_STRONG: 30, DTDT_MIN_T: 350,
  DTDT_STRONG_MIN: 300, PERSIST_S: 3, ALARM_HOLD_S: 60, HUSH_S: 120 };
const ST = { WARMUP: 0, NORMAL: 1, WARN: 2, ALARM: 3 };
const NAMES = ["WARM-UP", "NORMAL", "WARN", "ALARM"];
const LV = ["NONE", "WEAK", "STRONG"];
const tdiv = (a, b) => Math.trunc(a / b);
function detInit() {
  return { t: 0, state: 0, gasBase: 0, gasInit: false, gasDev: 0, co2: new Array(13).fill(0), co2n: 0, co2i: 0,
    co2Base: 0, co2Rate: 0, co2Ex: 0, th: new Array(7).fill(0), tn: 0, ti: 0, dtdt: 0, eg: 0, ec: 0, eh: 0,
    persist: 0, alarmSince: 0, clearAt: 0, hushUntil: 0, hushed: false, atHush: 0 };
}
function gasUpdate(d, sraw) {
  const s = sraw << 8;
  if (!d.gasInit) { d.gasBase = s; d.gasInit = true; }
  else if (d.t < K.WARMUP_S) d.gasBase += (s - d.gasBase) >> 2;
  else if (s > d.gasBase) d.gasBase += (s - d.gasBase) >> 3;
  else if (d.gasDev < K.GAS_WEAK) d.gasBase -= (d.gasBase - s) >> 11;
  const dev = (d.gasBase >> 8) - sraw;
  d.gasDev = dev < 0 ? 0 : Math.min(dev, 60000);
}
function co2Update(d, ppm) {
  d.co2[d.co2i] = ppm; d.co2i = (d.co2i + 1) % 13; if (d.co2n < 13) d.co2n++;
  if (d.co2n === 1) d.co2Base = ppm << 4;
  const oldest = d.co2n < 13 ? 0 : d.co2i, span = (d.co2n - 1) * 5;
  d.co2Rate = span ? tdiv((ppm - d.co2[oldest]) * 60, span) : 0;
  const p = ppm << 4;
  if (p < d.co2Base) d.co2Base += (p - d.co2Base) >> 2;
  else if (d.co2Ex < 1000) d.co2Base += (p - d.co2Base) >> 9;
  const ex = ppm - (d.co2Base >> 4);
  d.co2Ex = ex < 0 ? 0 : Math.min(ex, 30000);
}
function heatUpdate(d, t) {
  if (d.t % 10 !== 0 && d.tn) return;
  d.th[d.ti] = t; d.ti = (d.ti + 1) % 7; if (d.tn < 7) d.tn++;
  const oldest = d.tn < 7 ? 0 : d.ti, span = (d.tn - 1) * 10;
  d.dtdt = span ? tdiv((t - d.th[oldest]) * 60, span) : 0;
}
const grade = (v, w, s) => v >= s ? 2 : v >= w ? 1 : 0;
function detStep(d, inp) {
  d.t++;
  gasUpdate(d, inp.sraw);
  if (inp.co2New) co2Update(d, inp.co2);
  heatUpdate(d, inp.tp);
  const tp = inp.tp;
  d.eg = d.t < K.WARMUP_S ? 0 : grade(d.gasDev, K.GAS_WEAK, K.GAS_STRONG);
  d.ec = Math.max(grade(d.co2Rate, K.CO2_RATE_WEAK, K.CO2_RATE_STRONG), grade(d.co2Ex, 1500, K.CO2_EXCESS_STRONG));
  let b = grade(d.dtdt, K.DTDT_WEAK, K.DTDT_STRONG);
  if (b === 2 && tp < K.DTDT_STRONG_MIN) b = 1;
  if (b === 1 && tp < K.DTDT_MIN_T) b = 0;
  d.eh = Math.max(grade(tp, K.T_WEAK, K.T_STRONG), b);
  const g = d.eg, c = d.ec, h = d.eh;
  const alarm = (g && c && (g === 2 || c === 2)) || h === 2 || (h && (g || c)) || (g === 2 && c === 2);
  const warn = g || c || h, sum = g + c + h;
  d.persist = alarm ? Math.min(d.persist + 1, 255) : 0;
  if (d.state === ST.ALARM) {
    if (alarm) d.clearAt = d.t + K.ALARM_HOLD_S;
    if (inp.button && !d.hushed) { d.hushed = true; d.hushUntil = d.t + K.HUSH_S; d.atHush = sum; }
    else if (d.hushed && (d.t >= d.hushUntil || sum > d.atHush)) d.hushed = false;
    if (!alarm && d.t >= d.clearAt) { d.hushed = false; d.state = warn ? ST.WARN : ST.NORMAL; }
    return;
  }
  if (d.persist >= K.PERSIST_S) { d.state = ST.ALARM; d.alarmSince = d.t; d.clearAt = d.t + K.ALARM_HOLD_S; d.hushed = false; return; }
  d.state = d.t < K.WARMUP_S ? ST.WARMUP : warn ? ST.WARN : ST.NORMAL;
}


const fs=require('fs');
let bad=0, total=0;
for (const name of process.argv.slice(2)) {
  const lines=fs.readFileSync(name,'utf8').split('\n').filter(l=>l.includes(' t='));
  const d=detInit(); let prevCo2=null; let mism=0;
  for (const l of lines) {
    const kv=Object.fromEntries(l.split(' ').slice(1).map(x=>x.split('=')));
    const co2=+kv.co2, co2New = kv.cn==='1';
    const f=parseInt(kv.f,16);
    if (f) { continue; }
    detStep(d,{sraw:+kv.sraw,co2,co2New,tp:+kv.tp,button:false});
    total++;
    if (d.state!==+kv.st || d.gasDev!==+kv.gdev || d.co2Rate!==+kv.rate || d.dtdt!==+kv.dtdt) { if(mism<3) console.log(name.split('/').pop(), 't', kv.t, 'js', d.state, d.gasDev, d.co2Rate, d.dtdt, 'fw', kv.st, kv.gdev, kv.rate, kv.dtdt); mism++; }
  }
  console.log(name.split('/').pop(), 'seconds', lines.length, 'mismatches', mism); bad+=mism;
}
process.exit(bad?1:0);
