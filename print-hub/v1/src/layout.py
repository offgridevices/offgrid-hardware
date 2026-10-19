# -*- coding: utf-8 -*-
"""Where every part goes, and the power copper drawn before routing.

Board 86 x 50 mm, every part on the top side.  Millimetres from the board
centre, y towards the FRONT edge (the bottom of every plot).

    back edge   POWER IN (USB-C)    DATA (USB-C)          ESP32 antenna
                PD chip, buck        ESD, OR diodes, LDO   ESP32-S3 module
                inductor, caps       buttons, status LED
                port blocks: switch, shunt, amplifier, LED (x5)
    front edge  USB1    USB2    USB3    USB4    USB5

The ports are 17 mm apart (the receptacles' shield legs, all ground, nearly
touch; a wide plug still fits beside its neighbour).  The board's depth is
the receptacle (13.6 mm) + its port block (9.2 mm) + the ESP32 module
(26.4 mm, antenna at the back edge, over port 5's block).

Parts are found by (block, note) from circuit.py, so a reference
designator can change without touching this file.
"""
import circuit, pcb

PITCH = 17.0                         # between USB-A ports (courtyard cut to 16.9 mm, footprints.py)
PORT_X = [-2 * PITCH + PITCH * i for i in range(circuit.NPORTS)]
USBA_Y = pcb.HY - 11.0               # mouth 0.6 mm past the front edge, flush with the enclosure wall
USBC_Y = -pcb.HY + 4.6               # rotated 180: mouth 0.6 mm past the back edge
J1_X, J2_X = -30.0, -2.0
ESP = (33.0, -8.4)                   # module origin: antenna flush with the back edge, at the right
# the power stage and the logic keep the arrangement of the first (104 x 66)
# layout, moved as blocks: the numbers below are that layout's, plus these
PWR_DX, PWR_DY = 8.0, 7.7
LOG_DX, LOG_DY = 6.0, 8.0
BUCK = (-38.0 + PWR_DX, -15.0 + PWR_DY)


def port_parts(n):
    """(note, k) -> (dx, dy, rot) for port n, relative to its USB-A centre x
    and the port block's datum line y = 0 at USBA_Y."""
    return {
        ('USB-A port', 0): (0.0, 0.0, 0),
        # the switch turned round: OUT and IN on its bottom row, ILIM and
        # FAULT on its right, EN top left.  OUT drops straight onto the
        # shunt below it; the shunt's lower end feeds the output capacitor
        # and the port's VBUS pin (power.py draws both).
        ('port switch', 0): (-1.0, -9.6, 180),
        ('switch input', 0): (-3.1, -9.9, 90),           # 100 nF by IN
        ('rail bulk at the port', 0): (-5.0, -8.4, 90),
        ('current shunt', 0): (0.0, -6.1, 270),
        ('port output', 0): (-4.2, -4.2, 180),
        ('current sense', 0): (2.9, -6.2, 180),          # IN+ / IN- face the shunt's two ends
        ('amplifier supply', 0): (5.6, -6.6, 90),
        ('current limit 2.07 A', 0): (2.2, -9.6, 90),
        ('enable pull-down', 0): (-1.0, -11.3, 0),
        ('fault pull-up', 0): (3.4, -9.6, 90),
        ('ADC filter R', 0): (4.6, -9.6, 90),
        ('ADC filter C', 0): (5.8, -9.6, 90),
        ('port LED', 0): (6.4, -4.0, 0),
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
        ('input TVS', 0): (-34.0 + PWR_DX, -21.0 + PWR_DY, 0),
        ('USB-PD sink', 0): (-26.5 + PWR_DX, -22.0 + PWR_DY, 180),     # VIN and CC on top, VSET / ISET / I2C below
        ('HUSB238 VIN', 0): (-24.0 + PWR_DX, -24.6 + PWR_DY, 0),
        ('VSET 9 V (5.1k of 6.1k)', 0): (-25.6 + PWR_DX, -18.8 + PWR_DY, 0),
        ('VSET 9 V (1k of 6.1k)', 0): (-25.6 + PWR_DX, -17.7 + PWR_DY, 0),
        ('ISET 2 A (10k of 10.47k)', 0): (-27.6 + PWR_DX, -18.8 + PWR_DY, 0),
        ('ISET 2 A (470R of 10.47k)', 0): (-27.6 + PWR_DX, -17.7 + PWR_DY, 0),
        ('I2C SDA pull-up', 0): (-22.8 + PWR_DX, -21.4 + PWR_DY, 90),
        ('I2C SCL pull-up', 0): (-21.6 + PWR_DX, -21.4 + PWR_DY, 90),
        ('buck', 0): (BUCK[0], BUCK[1], 0),
        ('buck input', 0): (-34.3 + PWR_DX, -14.4 + PWR_DY, 270),
        ('buck input', 1): (-31.9 + PWR_DX, -14.4 + PWR_DY, 270),
        ('buck input HF', 0): (-33.0 + PWR_DX, -17.4 + PWR_DY, 0),
        ('buck enable', 0): (-39.6 + PWR_DX, -18.8 + PWR_DY, 0),
        ('buck bootstrap', 0): (-41.0 + PWR_DX, -17.6 + PWR_DY, 270),
        ('buck VCC', 0): (-37.0 + PWR_DX, -18.2 + PWR_DY, 90),
        ('buck inductor', 0): (-46.0 + PWR_DX, -14.8 + PWR_DY, 180),
        ('feedback top (75k of 76k)', 0): (-39.8 + PWR_DX, -11.8 + PWR_DY, 90),
        ('feedback top (1k of 76k)', 0): (-38.7 + PWR_DX, -11.8 + PWR_DY, 90),
        ('feedback bottom', 0): (-37.6 + PWR_DX, -11.8 + PWR_DY, 90),
        ('feed-forward', 0): (-40.9 + PWR_DX, -11.8 + PWR_DY, 90),
        ('buck output', 0): (-49.6 + PWR_DX, -8.0 + PWR_DY, 270),
        ('buck output', 1): (-47.2 + PWR_DX, -8.0 + PWR_DY, 270),
        ('buck output', 2): (-44.8 + PWR_DX, -8.0 + PWR_DY, 270),
        ('buck output', 3): (-42.4 + PWR_DX, -8.0 + PWR_DY, 270),
        ('input sense top', 0): (-28.0 + PWR_DX, -14.0 + PWR_DY, 90),
        ('input sense bottom', 0): (-26.8 + PWR_DX, -14.0 + PWR_DY, 90),
        ('input sense filter', 0): (-25.6 + PWR_DX, -14.0 + PWR_DY, 90),
        # the rail divider anywhere over the 5 V plane: beside the LDO
        ('rail sense top', 0): (-6.0, -2.0, 90),
        ('rail sense bottom', 0): (-4.8, -2.0, 90),
        ('rail sense filter', 0): (-3.6, -2.0, 90),
        # the thermistor between the inductor and the buck, above both
        ('board temperature NTC', 0): (-36.0, -11.6, 0),
        ('NTC pull-up', 0): (-36.0, -12.8, 0),
        ('NTC filter', 0): (-38.2, -11.6, 0),
    }
    ex, ey = ESP
    rel_logic = {
        ('DATA', 0): (J2_X, USBC_Y, 180),
        ('DATA VBUS', 0): (-12.6 + LOG_DX, -21.4 + LOG_DY, 90),
        ('DATA CC1 Rd', 0): (-3.2 + LOG_DX, -24.0 + LOG_DY, 90),
        ('DATA CC2 Rd', 0): (-12.8 + LOG_DX, -24.0 + LOG_DY, 90),
        ('USB ESD', 0): (-8.0 + LOG_DX, -20.6 + LOG_DY, 0),
        ('logic OR from the rail', 0): (-16.0 + LOG_DX, -9.0 + LOG_DY, 0),
        ('logic OR from DATA', 0): (-16.0 + LOG_DX, -20.0 + LOG_DY, 0),
        ('logic 5 V', 0): (-11.6 + LOG_DX, -16.0 + LOG_DY, 90),
        ('3.3 V LDO', 0): (-7.6 + LOG_DX, -15.2 + LOG_DY, 0),
        ('LDO output', 0): (-4.0 + LOG_DX, -15.6 + LOG_DY, 90),
        ('ESP32 bulk (Wi-Fi bursts)', 0): (ex - 12.0, ey - 8.4, 90),
        ('ESP32 3V3', 0): (ex - 12.0, ey - 5.8, 90),
        ('ESP32-S3 module', 0): (ex, ey, 0),
        ('EN pull-up', 0): (ex - 12.0, ey - 3.2, 90),
        ('EN delay', 0): (ex - 13.2, ey - 3.2, 90),
        ('RESET', 0): (ex - 18.0, ey - 2.0, 0),
        ('BOOT pull-up', 0): (ex - 12.0, ey + 5.4, 90),
        ('BOOT', 0): (ex - 18.0, ey + 5.0, 0),
        ('UART TX', 0): (ex - 14.0, -pcb.HY + 2.4, 0),
        ('UART RX', 0): (ex - 11.4, -pcb.HY + 2.4, 0),
        ('ground', 0): (ex - 16.6, -pcb.HY + 2.4, 0),
        ('5 V rail', 0): (12.0, 0.3, 0),
        # the status LED left of the module, under the lid's window
        ('LED data series', 0): (ex - 12.0, ey + 2.4, 0),
        ('status LED', 0): (ex - 12.0, ey + 8.1, 0),
    }
    rel_logic[('status LED', 1)] = (ex - 12.0, ey + 3.8, 0)     # its 100 nF
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
                dx, dy, rot = 7.6, -6.6, 90
            else:
                dx, dy, rot = rel[k]
            out[c.ref] = (PORT_X[n - 1] + dx, USBA_Y + dy, rot)
        elif c.block == 'mounting':
            x, y = pcb.HOLES[int(c.ref[1:]) - 1]
            out[c.ref] = (x, y, 0)
        else:
            raise KeyError('no placement rule for %s (%s)' % (c.ref, c.block))
    return out
