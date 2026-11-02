"""Gate: the firmware's pin map (firmware/src/board.h) matches the circuit
(circuit.FIRMWARE_PINS) and the routed board (MCU pad -> net)."""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import circuit, libsym

# firmware: '#define PIN_X  PD3   /* NET ... */'
fw = {}
for m in re.finditer(r'#define\s+PIN_\w+\s+(P[B-D]\d)\s+/\*\s*(\w+)', open(os.path.join(ROOT, 'firmware', 'src', 'board.h')).read()):
    fw[m.group(2)] = m.group(1)

# symbol: pin number -> port name (ATmega328P-A pin names carry the port)
sym = libsym.load('MCU_Microchip_ATmega:ATmega328P-A')
num2port = {}
for num, name, *_ in libsym.pins(sym):
    m = re.search(r'P[B-D]\d', name)
    if m:
        num2port[num] = m.group(0)
mcu = next(p for p in circuit.PARTS if p['ref'] == circuit.MCU)
circ = {net: num2port[num] for num, net in mcu['pins'].items() if net and num in num2port}

bad = 0
for net, port in circuit.FIRMWARE_PINS.items():
    f, c = fw.get(net), circ.get(net)
    ok = f == port == c
    bad += not ok
    print(f"{'ok ' if ok else 'BAD'} {net:10s} circuit={c} FIRMWARE_PINS={port} board.h={f}")
# the routed board: same pads carry the same nets
brd = open(os.path.join(ROOT, 'production', 'canary-netlist.csv')).read()
for net in circuit.FIRMWARE_PINS:
    num = next(n for n, v in mcu['pins'].items() if v == net)
    if not re.search(r'^/?%s,.*\bU2\.%s\b' % (re.escape(net), num), brd, re.M):
        print('BAD board netlist: U2.%s not on %s' % (num, net)); bad += 1
print(f'pin check: {len(circuit.FIRMWARE_PINS)} pins, {bad} mismatches')
sys.exit(1 if bad else 0)
