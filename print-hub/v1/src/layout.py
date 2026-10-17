# -*- coding: utf-8 -*-
"""Where every part goes, and the power copper drawn before routing.

Board 104 x 66 mm, every part on the top side.  Millimetres from the board
centre, y towards the FRONT edge (the bottom of every plot).

    back edge   POWER IN (USB-C)    DATA (USB-C)          ESP32 antenna
                PD chip, buck        ESD, OR diodes, LDO   ESP32-S3 module
                inductor, caps                              buttons, status LED
                -------------- signal routing band --------------
                port blocks: switch, shunt, amplifier, LED (x5)
    front edge  USB1    USB2    USB3    USB4    USB5

Parts are found by (block, note) from circuit.py, so a reference
designator can change without touching this file.
"""
import circuit, pcb

PITCH = 18.0                         # between USB-A ports (the receptacle's courtyard is 17.4 mm)
PORT_X = [-36.0 + PITCH * i for i in range(circuit.NPORTS)]
USBA_Y = pcb.HY - 11.0               # mouth 0.6 mm past the front edge, flush with the enclosure wall
USBC_Y = -pcb.HY + 4.6               # rotated 180: mouth 0.6 mm past the back edge
J1_X, J2_X = -38.0, -8.0
ESP = (33.0, -16.4)                  # module origin: antenna flush with the back edge
BUCK = (-38.0, -15.0)


def port_parts(n):
    """(note, k) -> (dx, dy, rot) for port n, relative to its USB-A centre x
    and the port block's datum line y = 0 at USBA_Y."""
    return {
        ('USB-A port', 0): (0.0, 0.0, 0),
        # the current path, right to left: rail via -> switch -> shunt -> port pad 1
        ('port switch', 0): (-1.0, -11.0, 0),
        ('switch input', 0): (1.8, -12.0, 90),         # 100 nF right by IN
        ('rail bulk at the port', 0): (4.2, -11.0, 90),
        ('current shunt', 0): (-4.4, -8.0, 270),
        ('port output', 0): (-7.4, -5.6, 90),
        ('current sense', 0): (1.2, -7.4, 0),
        ('amplifier supply', 0): (3.6, -7.0, 90),
        ('current limit 2.07 A', 0): (-3.4, -12.4, 0),
        ('enable pull-down', 0): (6.4, -13.5, 0),
        ('fault pull-up', 0): (6.4, -12.4, 0),
        ('ADC filter R', 0): (6.6, -9.0, 90),
        ('ADC filter C', 0): (7.8, -9.0, 90),
        ('port LED', 0): (5.5, -4.5, 0),
    }


def placement(comps):
    """ref -> (x, y, rot) for every part in circuit.build()."""
    seen = {}
    out = {}

    def key(c):
        k = (c.block, c.note)
        i = seen.get(k, 0)
        seen[k] = i + 1
        return c.note, i

    rel_power = {
        ('POWER IN', 0): (J1_X, USBC_Y, 180),
        ('input TVS', 0): (-34.0, -21.0, 0),
        ('USB-PD sink', 0): (-26.5, -22.0, 0),
        ('HUSB238 VIN', 0): (-29.4, -22.4, 270),
        ('VSET 9 V (5.1k of 6.1k)', 0): (-25.6, -18.8, 0),
        ('VSET 9 V (1k of 6.1k)', 0): (-25.6, -17.7, 0),
        ('ISET 2 A (10k of 10.47k)', 0): (-27.6, -18.8, 0),
        ('ISET 2 A (470R of 10.47k)', 0): (-27.6, -17.7, 0),
        ('I2C SDA pull-up', 0): (-22.8, -21.4, 90),
        ('I2C SCL pull-up', 0): (-21.6, -21.4, 90),
        ('buck', 0): (BUCK[0], BUCK[1], 0),
        ('buck input', 0): (-34.3, -14.4, 270),
        ('buck input', 1): (-31.9, -14.4, 270),
        ('buck input HF', 0): (-33.0, -17.4, 0),
        ('buck enable', 0): (-39.6, -18.8, 0),
        ('buck bootstrap', 0): (-41.0, -17.6, 270),
        ('buck VCC', 0): (-37.0, -18.2, 90),
        ('buck inductor', 0): (-46.0, -14.8, 180),
        ('feedback top (75k of 76k)', 0): (-39.8, -11.8, 90),
        ('feedback top (1k of 76k)', 0): (-38.7, -11.8, 90),
        ('feedback bottom', 0): (-37.6, -11.8, 90),
        ('feed-forward', 0): (-40.9, -11.8, 90),
        ('buck output', 0): (-49.6, -8.0, 270),
        ('buck output', 1): (-47.2, -8.0, 270),
        ('buck output', 2): (-44.8, -8.0, 270),
        ('buck output', 3): (-42.4, -8.0, 270),
        ('input sense top', 0): (-28.0, -14.0, 90),
        ('input sense bottom', 0): (-26.8, -14.0, 90),
        ('input sense filter', 0): (-25.6, -14.0, 90),
        ('rail sense top', 0): (-42.4, -3.6, 90),
        ('rail sense bottom', 0): (-41.2, -3.6, 90),
        ('rail sense filter', 0): (-40.0, -3.6, 90),
    }
    ex, ey = ESP
    rel_logic = {
        ('DATA', 0): (J2_X, USBC_Y, 180),
        ('DATA CC1 Rd', 0): (-3.2, -24.0, 90),
        ('DATA CC2 Rd', 0): (-12.8, -24.0, 90),
        ('USB ESD', 0): (-8.0, -20.6, 0),
        ('logic OR from the rail', 0): (-16.0, -9.0, 0),
        ('logic OR from DATA', 0): (-16.0, -20.0, 0),
        ('logic 5 V', 0): (-11.6, -16.0, 90),
        ('3.3 V LDO', 0): (-7.6, -15.2, 0),
        ('LDO output', 0): (-4.0, -15.6, 90),
        ('ESP32 bulk (Wi-Fi bursts)', 0): (ex - 12.0, ey - 8.4, 90),
        ('ESP32 3V3', 0): (ex - 12.0, ey - 5.8, 90),
        ('ESP32-S3 module', 0): (ex, ey, 0),
        ('EN pull-up', 0): (ex - 12.0, ey - 3.2, 90),
        ('EN delay', 0): (ex - 13.2, ey - 3.2, 90),
        ('RESET', 0): (ex - 18.0, ey - 2.0, 0),
        ('BOOT pull-up', 0): (ex - 12.0, ey + 5.4, 90),
        ('BOOT', 0): (ex - 18.0, ey + 5.0, 0),
        ('UART TX', 0): (ex - 14.0, -30.6, 0),
        ('UART RX', 0): (ex - 11.4, -30.6, 0),
        ('ground', 0): (ex - 16.6, -30.6, 0),
        ('5 V rail', 0): (-46.0, -1.0, 0),
        ('LED data series', 0): (ex + 12.4, ey + 2.6, 90),
        ('status LED', 0): (ex + 13.0, ey + 6.4, 0),
    }
    rel_logic[('status LED', 1)] = (ex + 15.6, ey + 6.4, 90)     # its 100 nF
    for c in comps:
        note, i = key(c)
        if c.block == 'power in':
            out[c.ref] = rel_power[(note, i)]
        elif c.block == 'logic':
            if c.note == 'status LED' and c.part != 'WS2812B':
                out[c.ref] = rel_logic[('status LED', 1)]
            else:
                out[c.ref] = rel_logic[(note, i)]
        elif c.block.startswith('USB'):
            n = int(c.block[3:])
            rel = port_parts(n)
            k = (note, i)
            if c.note == 'port LED' and c.part != 'WS2812B':
                dx, dy, rot = 7.6, -4.5, 90
            else:
                dx, dy, rot = rel[k]
            out[c.ref] = (PORT_X[n - 1] + dx, USBA_Y + dy, rot)
        elif c.block == 'mounting':
            x, y = pcb.HOLES[int(c.ref[1:]) - 1]
            out[c.ref] = (x, y, 0)
        else:
            raise KeyError('no placement rule for %s (%s)' % (c.ref, c.block))
    return out
