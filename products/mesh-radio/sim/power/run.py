"""Listening-current budget and battery life, Mesh Radio v1 (2 Nov 2026).

A spreadsheet in code: every load on the battery while the board listens,
from datasheets (sources in README.md), summed for each firmware/hardware
option.  Writes results.txt and power.png next to this file.

    python3 sim/power/run.py      # from products/mesh-radio; needs numpy-free Python 3 + matplotlib
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

VBAT = 3.7          # mid-charge cell
V3 = 3.3            # buck output
EFF = 0.925         # TPS62840 at 3.7 V in, 5-20 mA (SLVSEC6D fig. 19)
K = V3 / (EFF * VBAT)   # 3V3-rail mA -> battery mA (0.964)

# ---- loads on the 3V3 rail (mA) --------------------------------------
SX_RX_BOOST = 5.3   # SX1262 RX, DC-DC, boosted gain (DS table 3-5)
SX_RX_SAVE = 4.6    # power-saving gain (same table)
TCXO = 1.5          # ECS-TXO-20CSMV4, on DIO3 for the whole RX window (estimate)
LNA_ON = 4.9        # BGA7L1BN6 gain mode (DS rev 3.1 table 3)
LNA_BYP = 0.087     # bypass: VCC is never switched off
RFSW = 0.037 + 0.006  # SKY13330 enabled + its ENABLE divider
NRF_BASE = 0.45     # nRF52840: sleep + RTC + Meshtastic loop, packet decode (estimate 0.4-1.0)
NRF_UART = 0.40     # drone serial port left listening keeps the fast clock on (estimate 0.3-0.5)
BLE_ADV = 0.10      # advertising forever at 417.5 ms (estimate)
TMP = 0.005         # TMP1075 continuous

# ---- loads straight on the battery (mA) ------------------------------
BAT_SIDE = (0.041   # TPS22950 cell bypass, on
            + 0.004 + 0.004   # BQ25185, BQ29700
            + 0.004 + 0.0015 + 0.0037 + 0.0037 + 0.003  # PR1, VBAT_SENSE, REV_G, plug 1 M, zener
            + 0.0037)  # PWR_ON 1 M
PA_IDLE = 0.34      # TPS2121 + TPS63810 + QPA9510 standby, left on by today's firmware

# ---- duty-cycled receive (SX1262 SetRxDutyCycle), LongFast -----------
# SF11 / 250 kHz: symbol 8.192 ms, 16-symbol preamble.  Window 91 ms, sleep
# 49 ms (detect in 5 symbols, header fits in 2*rx + sleep: datasheet 13.1.7),
# plus 5 ms TCXO start and 1 ms context save per wake.
TS = 8.192
RX_WIN, SLEEP, WAKE = 91.0, 49.0, 6.0
DUTY = (RX_WIN + WAKE) / (RX_WIN + SLEEP)   # 0.69 of the time awake


def budget(gain='boost', lna='on', duty=False, lna_gated=False, pa_idle=True,
           uart=True, ble=True):
    """Battery mA by group while listening (no traffic)."""
    d = DUTY if duty else 1.0
    sx = (SX_RX_BOOST if gain == 'boost' else SX_RX_SAVE) + TCXO
    if lna == 'on':
        lna_ma = LNA_ON * (d if lna_gated else 1.0)
    else:
        lna_ma = LNA_BYP
    g = {
        'Radio chip + clock': sx * d * K,
        'Receive amp': lna_ma * K,
        'Processor + serial port': (NRF_BASE + (NRF_UART if uart else 0)) * K,
        'Bluetooth': (BLE_ADV if ble else 0) * K,
        'Amplifier supply (idle)': PA_IDLE if pa_idle else 0.0,
        'Everything else': (RFSW + TMP) * K + BAT_SIDE,
    }
    return g


# name, short label, kwargs, what it costs, effort
OPTIONS = [
    ('today', 'Today (firmware as written)',
     dict(), 'none', '-'),
    ('fw_free', '1. Firmware fixes, no range lost',
     dict(pa_idle=False, uart=False), 'none',
     'firmware: amplifier supply off between messages; drone serial port wakes on its first byte'),
    ('fw_gain', '2. + radio chip on low-power gain',
     dict(pa_idle=False, uart=False, gain='save'), 'about 0.3-0.5 dB',
     'firmware setting (boosted gain only when the receive amp is off)'),
    ('fw_duty', '3. + listen in short windows',
     dict(pa_idle=False, uart=False, gain='save', duty=True), 'a little: busy meshes collide more',
     'firmware feature (not in Meshtastic today); receive amp stays on between windows'),
    ('hw_gate', '4. + receive amp follows the windows',
     dict(pa_idle=False, uart=False, gain='save', duty=True, lna_gated=True), 'same as 3',
     'board change: one small logic chip (radio clock-enable AND not-transmitting AND firmware enable)'),
    ('saver', 'Battery saver (receive amp off) + 1-3',
     dict(pa_idle=False, uart=False, gain='boost', duty=True, lna='off'), 'about 7 dB less hearing (0.45x range)',
     'firmware setting'),
]

CELL_MAH = 1800 * 0.9       # plan.md: 1,800 mAh or larger; 90 % usable
TX_A, TX_S = 1.0, 0.48      # 1 W burst at the battery, 30-byte LongFast packet on air
OFF_UA = (34, 41)           # switched off, from the per-part budget


def life_days(listen_ma, sent_per_day):
    tx_mah = sent_per_day * TX_A * 1000 * TX_S / 3600
    return CELL_MAH / (listen_ma * 24 + tx_mah)


def main():
    rows = []
    for key, label, kw, cost, effort in OPTIONS:
        g = budget(**kw)
        rows.append((key, label, g, sum(g.values()), cost, effort))
    L = []
    L.append('Mesh Radio v1 listening current at the battery (3.7 V cell, 25 C, no traffic)')
    L.append(f'buck efficiency {EFF:.3f}; receive duty when windowed {DUTY:.2f}')
    L.append('')
    groups = list(rows[0][2])
    for key, label, g, tot, cost, effort in rows:
        L.append(f'{label}: {tot:.2f} mA   (range cost: {cost})')
        for k in groups:
            L.append(f'    {k:26s} {g[k]:6.2f} mA')
        L.append(f'    how: {effort}')
        L.append('')
    L.append(f'Battery life, {CELL_MAH:.0f} mAh usable, 1 W messages ({TX_S} s on air each):')
    L.append(f'{"option":42s} {"0/day":>7s} {"100/day":>8s} {"500/day":>8s}')
    for key, label, g, tot, cost, effort in rows:
        d = [life_days(tot, n) for n in (0, 100, 500)]
        L.append(f'{label:42s} {d[0]:6.1f}d {d[1]:7.1f}d {d[2]:7.1f}d')
    L.append('')
    L.append(f'Switched off: about {OFF_UA[0]}-{OFF_UA[1]} uA -> '
             f'{CELL_MAH / (OFF_UA[1] / 1000) / 24 / 365:.1f}-{CELL_MAH / (OFF_UA[0] / 1000) / 24 / 365:.1f} years on the shelf at 25 C')
    txt = '\n'.join(L) + '\n'
    open(os.path.join(HERE, 'results.txt'), 'w').write(txt)
    print(txt)
    plot(rows, groups)


def plot(rows, groups):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300']
    ink, muted, grid = '#1f1f1e', '#6b6a64', '#e4e3dc'
    fig, ax = plt.subplots(figsize=(10, 4.6), dpi=150)
    fig.patch.set_facecolor('white')
    ys = list(range(len(rows)))[::-1]
    for y, (key, label, g, tot, cost, effort) in zip(ys, rows):
        x = 0
        for k, c in zip(groups, colors):
            w = g[k]
            if w > 0:
                ax.barh(y, w, left=x, height=0.56, color=c, edgecolor='white', linewidth=1.5,
                        label=k if y == ys[0] else None)
            x += w
        ax.text(tot + 0.15, y, f'{tot:.1f} mA', va='center', fontsize=10, color=ink, fontweight='bold')
    ax.axvline(10, color=muted, ls=(0, (4, 3)), lw=1.2)
    ax.text(10.1, len(rows) - 0.45, 'target: 10 mA', color=muted, fontsize=9, va='bottom')
    ax.set_yticks(ys)
    ax.set_yticklabels([r[1] for r in rows], fontsize=10, color=ink)
    ax.set_xlabel('current from the battery while listening (mA)', color=muted, fontsize=9)
    ax.set_xlim(0, 15)
    ax.set_ylim(-0.6, len(rows) - 0.1)
    ax.grid(axis='x', color=grid, lw=0.8)
    ax.set_axisbelow(True)
    for s in ('top', 'right', 'left'):
        ax.spines[s].set_visible(False)
    ax.spines['bottom'].set_color(grid)
    ax.tick_params(colors=muted, length=0)
    ax.legend(loc='upper center', bbox_to_anchor=(0.42, -0.14), ncol=3, frameon=False, fontsize=9)
    ax.set_title('Where the listening current goes, and what each option saves', loc='left',
                 fontsize=12, color=ink)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'power.png'), facecolor='white')


if __name__ == '__main__':
    main()
