"""Static analyses for Canary v1: NTC measurement chain, power budget,
LDO dissipation, I2C rise time, USB current. Writes results.json and
ntc.png; exits non-zero if a limit is broken."""
import json, math, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
R25, RTOP, VCC = 10e3, 10e3, 3.3

def r_ntc(t, b=3380.0, r25=R25):
    return r25 * math.exp(b * (1 / (t + 273.15) - 1 / 298.15))

def adc(t, b=3380.0, r25=R25, rtop=RTOP):
    r = r_ntc(t, b, r25)
    return 1023 * r / (rtop + r)

def firmware_t(code, b=3380.0):          # same formula as main.c ntc_c10()
    r = R25 * code / (1023 - code)
    return 1 / (1 / 298.15 + math.log(r / R25) / b) - 273.15

T = np.arange(-10, 101, 1.0)
res, err = [], []
for t in T:
    c = adc(t)
    res.append(abs(firmware_t(c + 1) - firmware_t(c)))          # C per LSB
    worst = 0
    for dr in (-0.01, 0.01):                                     # NTC R25 1 %
        for db in (-0.01, 0.01):                                 # B 1 %
            for dt in (-0.001, 0.001):                           # 10k 0.1 %
                for dl in (-2, 2):                               # ADC +-2 LSB
                    c2 = adc(t, 3380 * (1 + db), R25 * (1 + dr), RTOP * (1 + dt)) + dl
                    worst = max(worst, abs(firmware_t(c2) - t))
    err.append(worst)
res, err = np.array(res), np.array(err)
band = (T >= 20) & (T <= 80)
p_self = max((VCC / (RTOP + r_ntc(t))) ** 2 * r_ntc(t) for t in T)   # W in the NTC
ntc = dict(resolution_C_per_LSB_20_80=[round(float(res[band].min()), 3), round(float(res[band].max()), 3)],
           worst_error_C_20_80=round(float(err[band].max()), 2),
           worst_error_C_at_50=round(float(err[T == 50][0]), 2),
           worst_error_C_at_65=round(float(err[T == 65][0]), 2),
           # one ADC step across the 60 s rate window, as a rate (C/min)
           rate_quantum_C_per_min_at_65=round(float(res[T == 65][0]), 3),
           self_heating_mW_max=round(p_self * 1e3, 3),
           self_heating_C_est=round(p_self * 1e3 / 1.0, 2))   # ~1 mW/C dissipation constant, 0603 in still air

# power budget at 3.3 V (datasheet typicals) and from VBUS
loads_mA = {'ATmega328P 8 MHz active/idle avg': 3.0, 'SGP40 measuring (1 Hz)': 3.5,
            'SHT40 avg': 0.01, 'SCD41 periodic avg': 15.0, 'LED (one lit, avg)': 1.5,
            'pull-ups, dividers': 0.5}
i33 = sum(loads_mA.values())
scd_peak = 175.0
ldo = dict(i_avg_mA=round(i33, 1), p_ldo_avg_mW=round((5.0 - 3.3) * i33, 1),
           p_ldo_peak_mW=round((5.0 - 3.3) * (i33 + scd_peak), 0),
           tj_rise_avg_C=round((5.0 - 3.3) * i33 * 1e-3 * 250, 1))  # SOT-23-5 ~250 C/W
spice = json.load(open(os.path.join(HERE, '..', 'spice', 'results.json')))
buz_avg = max(r['supply_avg_A'] for r in spice['results'].values()) * 1e3
usb = dict(normal_mA=round(i33, 1), alarm_avg_mA=round(i33 + buz_avg * 0.375, 1),
           alarm_peak_mA=round(i33 + scd_peak + max(r['supply_peak_A'] for r in spice['results'].values()) * 1e3, 0))
# I2C: 4.7k pull-ups, bus ~ 3 devices + traces ~ 60 pF
i2c = dict(rise_time_ns=round(0.8473 * 4700 * 60e-12 * 1e9, 0), limit_ns_100k=1000)
checks = {
    # the absolute thresholds are 50 C (warn) and 65 C (alarm); 2 C of worst-case
    # tolerance stack-up shifts them by less than the margin to the ~130 C onset
    'worst-case error < 2 C at the 50 and 65 C thresholds':
        ntc['worst_error_C_at_50'] < 2 and ntc['worst_error_C_at_65'] < 2,
    # rate is measured over 60 s: one ADC step must be well below the
    # 1 C/min weak-rate threshold (< 30 %)
    'rate quantum < 0.3 C/min at 65 C': ntc['rate_quantum_C_per_min_at_65'] < 0.3,
    'NTC self-heating < 0.5 C': ntc['self_heating_C_est'] < 0.5,
    'LDO average junction rise < 20 C': ldo['tj_rise_avg_C'] < 20,
    'USB alarm peak < 900 mA (USB 3 default)': usb['alarm_peak_mA'] < 900,
    'I2C rise time < 1000 ns': i2c['rise_time_ns'] < 1000,
}
out = dict(ntc=ntc, power=dict(loads_mA=loads_mA, ldo=ldo, usb=usb), i2c=i2c, checks=checks)
json.dump(out, open(os.path.join(HERE, 'results.json'), 'w'), indent=1)
print(json.dumps(out, indent=1))
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
ax[0].plot(T, res); ax[0].set_title('resolution (°C per ADC step)'); ax[0].set_xlabel('°C')
ax[1].plot(T, err, color='#c0392b'); ax[1].set_title('worst-case error (°C)'); ax[1].set_xlabel('°C')
fig.tight_layout(); fig.savefig(os.path.join(HERE, 'ntc.png'), dpi=100)
raise SystemExit(0 if all(checks.values()) else 1)
