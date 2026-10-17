# -*- coding: utf-8 -*-
"""Design checks that tie the firmware, the circuit and the parts together.
Writes ../VERIFICATION.md; exits 1 if any check fails.

    python3 src/verify.py

  * firmware pin map (firmware/src/board.h) against circuit.py: every pin
    the firmware drives or reads is wired to the net it means
  * the firmware's scaling (shunt, gain, dividers) against the parts
  * the LED chain order against the firmware's LED index
  * ESP32-S3 rules: analogue inputs on ADC1 only (ADC2 stops while Wi-Fi
    is on), strapping pins left alone, native USB on GPIO19/20
  * every port: switch, enable pull-down, fault pull-up, shunt, amplifier,
    DCP short on the USB-A
  * the simulations' own verdicts (sim/*.md)
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import circuit, parts

# ESP32-S3-WROOM-1 module pin -> GPIO (Espressif datasheet, pin layout)
MODULE_GPIO = {4: 4, 5: 5, 6: 6, 7: 7, 8: 15, 9: 16, 10: 17, 11: 18, 12: 8, 13: 19, 14: 20, 15: 3, 16: 46,
               17: 9, 18: 10, 19: 11, 20: 12, 21: 13, 22: 14, 23: 21, 24: 47, 25: 48, 26: 45, 27: 0,
               28: 35, 29: 36, 30: 37, 31: 38, 32: 39, 33: 40, 34: 41, 35: 42, 36: 44, 37: 43, 38: 2, 39: 1}
ADC1 = set(range(1, 11))
STRAPPING = {3, 45, 46}

results = []


def check(ok, what):
    results.append((bool(ok), what))
    return ok


def firmware_pins():
    src = open(os.path.join(V1, 'firmware', 'src', 'board.h')).read()
    pins = {}
    for m in re.finditer(r'constexpr uint8_t (\w+)(\[[^\]]*\])? = (\{[^}]*\}|\d+);', src):
        name, val = m.group(1), m.group(3)
        pins[name] = [int(v) for v in re.findall(r'\d+', val)] if val.startswith('{') else int(val)
    scale = {}
    for m in re.finditer(r'constexpr float (\w+) = ([^;]+);', src):
        scale[m.group(1)] = m.group(2)
    return pins, scale


def value_ohms(v):
    m = re.match(r'([\d.]+)\s*(m|k|R)?', v.replace('mR', 'm').replace('Ohm', ''))
    x = float(m.group(1))
    return x * {'m': 1e-3, 'k': 1e3, 'R': 1, None: 1}[m.group(2)]


def main():
    comps = circuit.build()
    by_ref = {c.ref: c for c in comps}
    esp = next(c for c in comps if c.part == 'ESP32S3')
    gpio_net = {MODULE_GPIO[int(p)]: n for p, n in esp.pins.items() if int(p) in MODULE_GPIO}
    pins, scale = firmware_pins()
    n = circuit.NPORTS

    # ---- pin map
    for i in range(n):
        check(gpio_net.get(pins['EN'][i]) == 'EN%d' % (i + 1), 'USB%d enable: firmware GPIO%d is %s' % (i + 1, pins['EN'][i], gpio_net.get(pins['EN'][i])))
        check(gpio_net.get(pins['FLT'][i]) == 'FLT%d' % (i + 1), 'USB%d fault: firmware GPIO%d is %s' % (i + 1, pins['FLT'][i], gpio_net.get(pins['FLT'][i])))
        check(gpio_net.get(pins['ISENSE'][i]) == 'IS%d' % (i + 1), 'USB%d current: firmware GPIO%d is %s' % (i + 1, pins['ISENSE'][i], gpio_net.get(pins['ISENSE'][i])))
    for name, net in (('VIN_SENSE', 'VIN_SENSE'), ('RAIL_SENSE', 'RAIL_SENSE'), ('LED_DATA', 'LED_DIN0'),
                      ('I2C_SDA', 'SDA'), ('I2C_SCL', 'SCL'), ('BUTTON', 'BOOT')):
        check(gpio_net.get(pins[name]) == net, '%s: firmware GPIO%d is %s' % (name, pins[name], gpio_net.get(pins[name])))
    check(gpio_net.get(19) == 'USB_DN' and gpio_net.get(20) == 'USB_DP', 'native USB: GPIO19 = D-, GPIO20 = D+')
    adc = list(pins['ISENSE']) + [pins['VIN_SENSE'], pins['RAIL_SENSE']]
    check(all(g in ADC1 for g in adc), 'every analogue input on ADC1 (GPIO1-10): %s' % adc)
    check(all(gpio_net.get(g) is None for g in STRAPPING), 'strapping pins GPIO3, 45, 46 left open')
    check(len(set(gpio_net[g] for g in gpio_net if gpio_net[g])) == len([g for g in gpio_net if gpio_net[g]]),
          'no two GPIOs on one net')

    # ---- scaling
    shunt = next(c for c in comps if c.part == 'SHUNT20M')
    rs = value_ohms(parts.PARTS[shunt.part]['value'])
    check(abs(eval(scale['SHUNT_OHM'].rstrip('f')) - rs) < 1e-9, 'shunt: firmware %s, part %g ohm' % (scale['SHUNT_OHM'], rs))
    check(parts.PARTS['INA180A2']['mpn'].startswith('INA180A2') and scale['AMP_GAIN'].startswith('50'),
          'amplifier gain: INA180A2 is 50 V/V, firmware %s' % scale['AMP_GAIN'])

    def divider(net):
        top = [c for c in comps if c.part.startswith('R') and net in c.pins.values() and
               any(v in ('VBUS_IN', 'VRAIL') for v in c.pins.values())]
        bot = [c for c in comps if c.part.startswith('R') and net in c.pins.values() and 'GND' in c.pins.values()]
        t, b_ = value_ohms(parts.PARTS[top[0].part]['value']), value_ohms(parts.PARTS[bot[0].part]['value'])
        return (t + b_) / b_
    for name, net in (('VIN_DIV', 'VIN_SENSE'), ('RAIL_DIV', 'RAIL_SENSE')):
        fw = eval(scale[name].replace('f', ''))
        check(abs(fw - divider(net)) < 1e-6, '%s: firmware %.4f, circuit %.4f' % (name, fw, divider(net)))

    # ---- LED chain: index k in the firmware is the k-th LED from the ESP32
    chain, net = [], 'LED_D0'
    while True:
        nxt = [c for c in comps if c.part == 'WS2812B' and c.pins.get('3') == net]
        if not nxt:
            break
        c = nxt[0]
        chain.append(c.block)
        net = c.pins.get('1')
        if not net:
            break
    want = ['logic'] + ['USB%d' % (n - k) for k in range(n)]
    check(chain == want, 'LED chain from the ESP32: %s (firmware: status, then USB%d .. USB1)' % (' > '.join(chain), n))
    mainsrc = open(os.path.join(V1, 'firmware', 'src', 'main.cpp')).read()
    check('board.set_led(hub::NPORTS - p' in mainsrc and 'board.set_led(0, st)' in mainsrc,
          'firmware LED index: status 0, port p at NPORTS - p')

    # ---- each port has its parts
    for i in range(1, n + 1):
        blk = [c for c in comps if c.block == 'USB%d' % i]
        has = lambda pred: any(pred(c) for c in blk)
        check(has(lambda c: c.part == 'TPS25200' and c.pins['6'] == 'VRAIL' and c.pins['4'] == 'EN%d' % i), 'USB%d: switch from the 5 V rail, enabled by EN%d' % (i, i))
        check(has(lambda c: c.part == 'R100K' and set(c.pins.values()) == {'EN%d' % i, 'GND'}), 'USB%d: enable pulled down (off during reset and flashing)' % i)
        check(has(lambda c: c.part == 'R10K' and set(c.pins.values()) == {'FLT%d' % i, '+3V3'}), 'USB%d: fault line pulled up to 3.3 V' % i)
        check(has(lambda c: c.part == 'R47K' and set(c.pins.values()) == {'ILIM%d' % i, 'GND'}), 'USB%d: 47k on ILIM (2.07 A)' % i)
        check(has(lambda c: c.part == 'USBA' and c.pins['2'] == c.pins['3'] and c.pins['1'] == 'VBUS%d' % i), 'USB%d: D+ joined to D- (BC1.2 charging port), VBUS from the shunt' % i)
        check(has(lambda c: c.part == 'INA180A2' and c.pins['3'] == 'PORT%d_SW' % i and c.pins['4'] == 'VBUS%d' % i and c.pins['5'] == '+3V3'),
              'USB%d: amplifier across the shunt, IN+ on the switch side, supplied from 3.3 V' % i)
    # the logic never feeds a port: VBUS_DATA reaches VLOGIC only through a diode
    d = [c for c in comps if c.part == 'B5819W']
    check(sorted((c.pins['2'], c.pins['1']) for c in d) == [('VBUS_DATA', 'VLOGIC'), ('VRAIL', 'VLOGIC')],
          'logic supply: VRAIL and VBUS_DATA each through a Schottky (anode) into VLOGIC (cathode)')
    check(not any('VBUS_DATA' in c.pins.values() and 'VRAIL' in c.pins.values() for c in comps),
          'nothing joins the print server\'s VBUS to the port rail')

    # ---- simulation verdicts
    for md in ('power_budget.md', 'port_events.md'):
        p = os.path.join(V1, 'sim', md)
        txt = open(p).read() if os.path.exists(p) else ''
        check(txt and 'FAIL' not in txt and 'PASS' in txt, 'simulation %s: all its checks pass' % md)

    out = ['# Print Hub v1: design checks', '', 'Written by `src/verify.py`. %d passed, %d failed.' %
           (sum(r[0] for r in results), sum(not r[0] for r in results)), '']
    out += ['- %s %s' % ('PASS' if ok else 'FAIL', w) for ok, w in results]
    open(os.path.join(V1, 'VERIFICATION.md'), 'w').write('\n'.join(out) + '\n')
    bad = [w for ok, w in results if not ok]
    print('%d checks, %d failed' % (len(results), len(bad)))
    for w in bad:
        print('  FAIL', w)
    return not bad


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
