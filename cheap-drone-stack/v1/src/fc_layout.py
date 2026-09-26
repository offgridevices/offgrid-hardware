# -*- coding: utf-8 -*-
"""Flight controller board: placement, planes and silkscreen.

Every part is on the top side, so the board is single-sided assembly.
Front of the quad is -y (top of every plot).  USB-C faces LEFT, as the
TAKER G4's did in the Phase 1 frame; the ESC lead leaves from the rear.

Stackup (4 layers): F.Cu signals, In1 solid GND, In2 power (VBAT / 5 V /
3.3 V areas) + signals, B.Cu signals + GND fill.
"""
import pcbnew
import pcb, circuit
from pcb import MM

T, Bo = 'T', 'B'

# ref: (x, y, rotation, side)
PLACE = {
    # MCU at 0 deg.  Its pins, by side:
    #   rear  (1-12)  VBAT, crystal, NRST, MOTOR1-4, gyro INT -> ESC lead
    #   right (13-24) SPI1 gyro, ADC, VDDA/VREF, TLM          -> gyro, dividers
    #   front (25-36) SPI2 flash, UART1, USB, SWDIO           -> flash, USB, pads
    #   left  (37-48) SWCLK, beeper, UART4, UART2, LED strip,
    #                 LED0, BOOT0                              -> left-side pads
    'U_FC':   (0.0, -1.5, 0, T),
    # Decoupling caps sit radially, in line with their own supply pin, so
    # each blocks only that pin's escape and leaves its neighbours free.
    'C10':    (-2.75, 3.2, 270, T),    # pin 1 VBAT
    'C13':    (-4.68, 1.25, 180, T),   # pin 48 VDD
    'C12':    (-3.7, -6.3, 180, T),    # pin 35 VDD (no room radially under the flash)
    'C11':    (4.68, -3.75, 0, T),     # pin 23 VDD
    'C14':    (4.68, -2.75, 0, T),     # pin 21 VDDA (pin 20 VREF+ beside it)
    'C15':    (6.7, -2.75, 0, T),      # VDDA bulk, in line behind C14
    'C16':    (4.3, 4.6, 90, T),       # bulk, clear of the motor lines
    'C17':    (-6.4, -11.2, 90, T),    # NRST, by its test point
    'Y1':     (-3.3, 5.3, 0, T),
    'C18':    (-6.0, 5.6, 90, T),
    'C19':    (-3.3, 7.6, 0, T),
    # --- gyro right of the MCU (rotation fixed at 90: see circuit.py)
    'U_IMU':  (6.8, 1.8, 90, T),
    'R8':     (9.6, -0.6, 90, T),
    'C20':    (9.6, 1.5, 90, T),
    'C21':    (9.6, 3.6, 90, T),
    'C22':    (6.8, 4.7, 0, T),
    # --- flash in front of the MCU, pushed to the front edge so the SPI2 and
    #     UART1 lines have a 3 mm corridor between the two packages
    'U_FLASH': (0.0, -12.3, 0, T),
    'C23':    (-3.3, -14.0, 90, T),    # by VCC (pin 8, front row)
    'R9':     (-3.3, -9.9, 90, T),     # CS pull-up, by pin 1
    # --- USB-C on the left edge
    'J_USB':  (-12.21, 0.0, 270, T),
    # ESD array and CC resistors hug the connector, leaving a 2 mm corridor
    # beside the MCU's left pins (SWCLK, beeper, UART4, UART2, LEDs, BOOT0)
    'U_ESD':  (-7.4, -3.0, 0, T),
    'D_USB':  (-7.6, -6.4, 0, T),
    'R10':    (-7.6, 0.2, 0, T),
    'R11':    (-7.6, 1.3, 0, T),
    # --- rear-left: status LED and beeper driver, kept 2.6 mm clear of the
    #     left-edge pads so their labels fit
    'R7':     (-5.3, 6.6, 90, T),      # BOOT0 pulldown
    'LED_STAT': (-7.9, 6.2, 0, T),
    'R13':    (-7.9, 7.5, 0, T),
    'Q_BZ':   (-10.9, 7.3, 90, T),
    # DFU button on the free right-rear edge: hold while plugging in USB
    'SW_BOOT': (14.8, 7.4, 90, T),
    'R14':    (-6.2, 9.4, 90, T),
    'R15':    (-7.3, 9.4, 90, T),
    # --- 5 V BEC, front-right (VBAT comes forward from the ESC lead).
    #     Buck at 90 deg: GND/SW/VIN on its right, CB/EN/FB on its left.
    'U_BUCK': (6.8, -8.0, 90, T),
    'L1':     (10.3, -6.4, 0, T),
    'C3':     (7.0, -11.2, 0, T),
    'C4':     (9.3, -10.2, 90, T),
    'C5':     (6.8, -5.7, 0, T),
    'C6':     (11.8, -3.0, 90, T),
    'C7':     (13.9, -3.0, 90, T),
    'R5':     (4.2, -9.6, 90, T),
    'R6':     (4.2, -11.6, 90, T),
    # --- 3.3 V LDO, rear-right
    'U_LDO':  (6.4, 7.6, 0, T),
    'C8':     (6.4, 10.0, 0, T),
    'C9':     (9.2, 7.4, 90, T),
    # --- battery voltage and current inputs, beside the ESC lead
    'R3':     (-6.4, 11.8, 90, T),
    'R4':     (-7.5, 11.8, 90, T),
    'C2':     (-8.6, 11.8, 90, T),
    'R1':     (6.4, 12.0, 90, T),
    'R2':     (7.5, 12.0, 90, T),
    'C1':     (8.6, 12.0, 90, T),
    # --- ESC lead at the rear edge, opening outwards
    'J_ESC':  (0.0, 13.5, 0, T),
    'LED_PWR':  (11.2, 4.6, 90, T),
    'R12':      (12.3, 4.6, 90, T),
    # --- solder pads.  Left edge, front: receiver (5 V, G, UART2).
    #     Front edge: UART4 left of the flash, UART1 right of it.
    'P_RX5V': (-15.8, -10.0, 90, T), 'P_RXG': (-15.8, -8.6, 90, T),
    'P_R2':   (-15.8, -7.2, 90, T),  'P_T2':  (-15.8, -5.8, 90, T),
    'P_T4':   (-7.0, -15.8, 0, T),  'P_R4':  (-5.6, -15.8, 0, T),
    'P_R1':   (4.4, -15.8, 0, T),   'P_T1':  (5.8, -15.8, 0, T),
    # right edge: 3.3 V / GND / 5 V for accessories, SWD
    'P_3V3':  (15.8, -1.4, 90, T), 'P_G3':  (15.8, 0.0, 90, T), 'P_5V': (15.8, 1.4, 90, T),
    'TP_SWDIO': (-5.0, -8.4, 0, T), 'TP_SWCLK': (-5.0, -9.8, 0, T), 'TP_NRST': (-5.0, -11.2, 0, T),
    # left edge, rear: LED strip, buzzer, ground
    'P_LED':  (-15.8, 5.8, 90, T), 'P_BZ+': (-15.8, 7.2, 90, T),
    'P_BZ-':  (-15.8, 8.6, 90, T), 'P_G1':  (-15.8, 10.0, 90, T),
    'P_VBAT': (-8.4, 15.8, 0, T),  'P_G2':  (-7.0, 15.8, 0, T),
    # --- mounting
    'H1': (-pcb.HOLE, -pcb.HOLE, 0, T), 'H2': (pcb.HOLE, -pcb.HOLE, 0, T),
    'H3': (pcb.HOLE, pcb.HOLE, 0, T),   'H4': (-pcb.HOLE, pcb.HOLE, 0, T),
}
# Routed first, by the in-house maze router, shortest first.
# The flash's rear-row lines go first (straight across the corridor), then
# the nets whose pins they box in (UART1) or that others would wall off
# (the beeper among the left-side UARTs), so their vias land at the pin.
PREROUTE = ['HSE_IN', 'HSE_OUT', 'FLASH_CS', 'SPI2_MISO', 'UART1_TX', 'UART1_RX', 'BEEPER', 'LED0',
            'SPI2_MOSI', 'SPI2_SCK', 'GYRO_INT', 'SPI1_SCK', 'SPI1_MISO', 'SPI1_MOSI', 'GYRO_CS',
            'USB_DP', 'USB_DM', 'M1_SIG', 'M2_SIG', 'M3_SIG', 'M4_SIG']
CLMAP = {k: 0.15 for k in ('VBAT', '+5V', 'USB_VBUS', 'BUCK_SW', '+3V3_GYRO', 'BUCK_CB')}

FIXED = {'U_FC', 'J_USB', 'J_ESC', 'U_IMU', 'U_FLASH'} | {k for k in PLACE if k.startswith(('P_', 'H'))}
EDGE_OK = {'J_USB'}

def build(out_path):
    b = pcb.new_board(4)
    pcb.outline(b)
    comps = circuit.build('fc')
    import legalize
    place, left = legalize.legalize(comps, PLACE, FIXED, edge_ok=EDGE_OK)
    fps = pcb.place_components(b, comps, place)
    pcb.usb_c_tie(b, fps['J_USB'])
    # USBLC6-2SC6 is flow-through: pins 1/6 and 3/4 are the same line.
    # Join each pair straight under the package.
    esd = {p.GetNumber(): p for p in fps['U_ESD'].Pads()}
    for a, c in (('1', '6'), ('3', '4')):
        pa, pc = esd[a].GetPosition(), esd[c].GetPosition()
        pcb.track(b, [(pa.x / 1e6 - pcb.CX, pa.y / 1e6 - pcb.CY), (pc.x / 1e6 - pcb.CX, pc.y / 1e6 - pcb.CY)],
                  0.2, pcbnew.F_Cu, esd[a].GetNetname())
    cu = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
    pcb.hole_keepouts(b, cu)
    e = pcb.HALF - 0.35
    full = [(-e, -e), (e, -e), (e, e), (-e, e)]
    # In1: unbroken ground under everything
    pcb.zone(b, 'GND', pcbnew.In1_Cu, full, name='GND plane')
    b.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    b.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_POWER)
    # In2: unbroken 3.3 V under everything
    pcb.zone(b, '+3V3', pcbnew.In2_Cu, full, name='3V3 plane')
    # VBAT and 5 V are short, few-pin runs: wide tracks, not planes.
    pcb.netclass(b, 'PWR', ['VBAT', '+5V', 'USB_VBUS', 'BUCK_SW'], width=0.4, clearance=0.15)
    pcb.netclass(b, 'PWR_LO', ['+3V3_GYRO', 'BUCK_CB'], width=0.25, clearance=0.15)
    import fanout, finish
    e2 = pcb.HALF - 0.4
    n, failed = fanout.fanout(b, {'GND', '+3V3'}, (pcb.CX - e2, pcb.CY - e2, pcb.CX + e2, pcb.CY + e2))
    print('fanout: %d plane vias, %d pads without one: %s' % (n, len(failed), failed))
    # Pre-route the short, critical nets while their area is still open,
    # and lock them so the autorouter works around them.
    left = {}
    for net in PREROUTE:
        left[net] = finish.route_net(b, net, clmap=CLMAP)
    print('pre-routed %d nets, unfinished: %s' % (len(PREROUTE), {k: v for k, v in left.items() if v}))
    b.Save(out_path)
    return b

if __name__ == '__main__':
    import sys
    build(sys.argv[1] if len(sys.argv) > 1 else '/tmp/fc.kicad_pcb')

# ---------------------------------------------------------------- artwork
LABELS = [
    ('P_T4', 'T4'), ('P_R4', 'R4'), ('P_R1', 'R1'), ('P_T1', 'T1'),
    ('P_RX5V', '5V'), ('P_RXG', 'G'), ('P_R2', 'R2'), ('P_T2', 'T2'),
    ('P_3V3', '3V3'), ('P_G3', 'G'), ('P_5V', '5V'),
    ('P_LED', 'LED'), ('P_BZ+', 'BZ+'), ('P_BZ-', 'BZ-'), ('P_G1', 'G'),
    ('P_VBAT', 'VB'), ('P_G2', 'G'),
    ('TP_SWDIO', 'DIO'), ('TP_SWCLK', 'CLK'), ('TP_NRST', 'RST'),
]

def artwork(b):
    import artwork as A
    A.hide_fields(b)
    top = A.SilkPlacer(b, 'T')
    for ref, s in LABELS:
        top.label(ref, s)
    top.label('J_ESC', '1', pad='1', dist=0.8)
    top.label('SW_BOOT', 'BOOT', pad='1')
    # which way is forward
    def front(x, y):
        return A.arrow(b, x, y, length=2.4) + [pcb.text(b, 'FRONT', x + 0.4, y + 2.1, size=0.8)]
    top.shape(front, [(x, y) for y in (-14.4, -13.9, -13.4) for x in (9.0, 8.5, 9.5, -9.5, 0.0)])
    bot = A.SilkPlacer(b, 'B')
    bot.text('ESC', [(x, 12.0, 0, None) for x in (0.0, 1.0, -1.0)])
    def big(x, y):
        return A.arrow(b, x, y, length=7.0, layer=pcbnew.B_SilkS, width=0.3, head=1.0) + \
               [pcb.text(b, 'FRONT', x, y - 4.8, size=1.2, layer=pcbnew.B_SilkS, thick=0.2)]
    bot.shape(big, [(x, y) for x in (0.0, -1.0, 1.0, -2.0, 2.0) for y in (-4.0, -3.0, -5.0)])
    for s, size, ys in (('OFFGRID CHEAP DRONE FC v1', 1.0, (3.2, 3.8, 2.6, 4.4)),
                        ('STM32G473  ICM-42688-P  16MB', 0.8, (5.0, 5.6, 4.6, 6.0)),
                        ('ESC lead 1 VBAT 2 GND 3 CUR 4 TLM 5-8 M1-M4', 0.8, (6.6, 7.2, 7.8)),
                        ('Betaflight CHEAPDRONE_G473', 0.8, (8.2, 8.8, 9.4, 10.0))):
        bot.text(s, [(x, y, 0, None) for y in ys for x in (0.0, -0.5, 0.5, -1.0, 1.0)], size=size,
                 thick=0.18 if size >= 1.0 else 0.15)
