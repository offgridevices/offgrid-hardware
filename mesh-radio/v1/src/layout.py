# -*- coding: utf-8 -*-
"""The floor plan: where every part goes.

Board: 25.4 mm wide (the Heltec V4's), pcb.LEN long, coordinates in mm from
the board centre, x along the length (USB-C end at -x, antenna end at +x),
y across it, down the screen (KiCad's).

  TOP, left to right
    USB-C on the short edge, the power slide switch above it (lever over
    the long edge), the reset and user buttons below it;
    the nRF52840 between the two rows of expansion-header holes, its
    Bluetooth chip antenna on the lower long edge beside them (a copper
    keepout through every layer round it);
    the SX1262 with its TCXO;
    the transmit chain in one line to the QPA9510 amplifier, the
    amplifier's output chain down the right end to the antenna switch,
    the LFCN-1000+ filter and the U.FL connector in the corner; the
    receive amplifier beside the switch, its 50 ohm line back to the
    SX1262's receive balun.
  BOTTOM
    the battery plug on the upper long edge, the solar plug at the left
    end, the drone (JST-GH) and GPS (JST-SH) plugs on the long edges at
    the right end;
    the input protection, charger and battery protection under the left
    half, the 3.3 V supply in the middle, the amplifier's power (mux,
    buck-boost, bulk capacitors) under the amplifier.

The RF chains are laid out by place.chain(); every other small part is
packed beside the pin it serves by place.pack().
"""
import pcb, circuit, parts, place

HX, HY = pcb.HX, pcb.HY
HDR_X0 = -10.0                     # expansion header: pin 1 / pin 11 x
ANT_BOX = (-20.6, 8.9, -11.9, HY)  # Bluetooth antenna keepout (x0, y0, x1, y1)


def ref(comps, part, note=None):
    """The one part of this kind (and note): placement names parts by what
    they are, so a renumbering in circuit.py cannot move the wrong one."""
    m = [c.ref for c in comps if c.part == part and (note is None or c.note == note)]
    if len(m) != 1:
        raise KeyError('%s %r: %d matches' % (part, note, len(m)))
    return m[0]


def anchors(comps):
    """(ref, x, y, rot, side) for the parts that set the floor plan."""
    R = lambda p, n=None: ref(comps, p, n)
    return [
        # ---- left end
        (R('USBC'), -HX + 5.48, 0.0, 270, 'T'),           # shell front 0.84 mm past the edge (Amphenol drawing)
        (R('SLIDE'), -HX + 5.6, -HY + 4.55, 180, 'T'),      # body edge on the board edge, lever over it
        (R('B3U', 'reset'), -24.4, HY - 2.0, 90, 'T'),
        (R('B3U', 'user'), -21.5, HY - 2.0, 90, 'T'),
        # ---- processor and Bluetooth
        (R('NRF52840'), -12.0, 0.3, 180, 'T'),              # SPI side towards the SX1262, USB side towards USB-C
        (R('ANT2450'), -16.3, HY - 1.35, 180, 'T'),         # feed end towards the nRF52840
        (R('HDR_2x10'), HDR_X0, 0.0, 0, 'T'),
        # ---- LoRa radio: RF pins face +x (top to bottom VR_PA, RFO, RFI_N, RFI_P)
        (R('SX1262'), -3.4, -4.4, 180, 'T'),
        (R('TCXO32'), -4.6, -7.9, 0, 'T'),
        # ---- bottom: connectors
        (R('JST_PH2'), -15.6, -HY + 4.9, 180, 'B'),         # battery, opening at the upper long edge
        (R('JST_SH2'), -HX + 3.1, -HY + 3.0, 180, 'B'),     # solar
        (R('JST_GH6'), 22.0, HY - 3.1, 0, 'B'),             # drone port, opening at the lower long edge
        (R('JST_SH6'), 18.4, -HY + 3.0, 180, 'B'),          # GPS, upper long edge
    ]


def keepouts():
    """(polygon, layers, name) copper keepouts the board carries."""
    x0, y0, x1, y1 = ANT_BOX
    box = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    inner = [n for n in pcb.CU_NAMES if n != 'F.Cu']
    return [(box, inner, 'Bluetooth antenna keepout')]


TX = ['LORA_RFO', 'LORA_TXA', 'LORA_TXB', 'LORA_TXC', 'LORA_TX50', 'PA_DRIVE', 'PA_RFIN']
PA_OUT = ['PA_OUT', 'PA_M1', 'PA_M2', 'PA_M3', 'PA_TX']
RX_IN = ['RX_SW', 'LNA_INM', 'LNA_AI']
BLE = ['NRF_ANT', 'BLE_50R', 'BLE_T', 'BLE_FEED']


def place_all(log=print):
    comps = circuit.build()
    B = place.Board(comps)
    x0, y0, x1, y1 = ANT_BOX
    B.keep_out((x0, y0, x1, y1), ('B',))
    B.keep_out((x0, y0, x1 , y1 - 2.5 + 2.5), ())
    for (hx, hy) in pcb.HOLES:
        r = pcb.HOLE_KEEPOUT_R
        B.keep_out((hx - r, hy - r, hx + r, hy + r))
    for r_, x, y, rot, side in anchors(comps):
        B.put(r_, x, y, rot, side, check=False)
    # header holes block both sides (each hole's pad, not the space between the rows)
    hdr = ref(comps, 'HDR_2x10')
    hx, hy, hrot, _ = B.pl[hdr]
    hbox, hp = B.geom(hdr, hx, hy, hrot, 'T')
    B.taken['T'].remove(hbox)
    for (px, py) in hp.values():
        B.keep_out((px - 0.95, py - 0.95, px + 0.95, py + 0.95))
    # ---- RF chains (top), a U: transmit along the top to the amplifier,
    # its output down the right end to the antenna switch, the antenna
    # through the filter to the U.FL, receive back along the bottom
    sx = ref(comps, 'SX1262')
    rfo = B.pad_xy(sx, '23')
    nodes = place.chain(B, comps, (rfo[0] + 0.7, rfo[1] - 1.6), TX[:-1], 0, shunt_side=-1, pitch_gap=0.25)
    pa = ref(comps, 'QPA9510')
    end = nodes['PA_DRIVE']
    B.put(pa, 0, 0, 0, 'T', check=False)
    pin3 = B.pad_xy(pa, '3')
    B.pl.pop(pa); B.taken['T'].pop()
    B.put(pa, end[0] + 2.2 - pin3[0], end[1] - pin3[1], 0, 'T', check=False)
    paout = B.pad_xy(pa, '10')
    xo = paout[0] + 3.2
    out = place.chain(B, comps, (xo, paout[1]), PA_OUT, 270, shunt_side=1, alternate=True, pitch_gap=0.25)
    # the antenna switch under the chain's end, transmit port up; its
    # antenna port then faces left (filter, U.FL), receive port down
    sw = ref(comps, 'SKY13330')
    B.put(sw, 0, 0, 270, 'T', check=False)
    p11 = B.pad_xy(sw, '11')
    B.pl.pop(sw); B.taken['T'].pop()
    tx_end = out['PA_TX']
    swx, swy = tx_end[0] - p11[0], tx_end[1] + 1.1 - p11[1]
    B.put(sw, swx, swy, 270, 'T', check=False)
    fl = ref(comps, 'LFCN1000')
    p2 = B.pad_xy(sw, '2')
    B.put(fl, p2[0] - 3.3, p2[1], 180, 'T', check=False)
    fl3 = B.pad_xy(fl, '3')
    B.put(ref(comps, 'UFL'), fl3[0] - 3.0, fl3[1] - 0.76, 0, 'T', check=False)
    rx = B.pad_xy(sw, '5')
    rxn = place.chain(B, comps, (rx[0], rx[1] + 0.9), RX_IN, 270, shunt_side=-1)
    lna = ref(comps, 'BGA7L1BN6')
    ai = rxn['LNA_AI']
    B.put(lna, ai[0], ai[1] + 0.9, 270, 'T', check=False)
    # the receive balun at the SX1262's RFI pins
    rfin = B.pad_xy(sx, '22')
    place.chain(B, comps, (rfin[0] + 0.9, rfin[1] + 0.4), ['LORA_RFI_N', 'LNA_OUT'], 0, shunt_side=1)
    # Bluetooth: Nordic's match then Johanson's tee, down to the antenna
    nrf = ref(comps, 'NRF52840')
    ant = B.pad_xy(nrf, 'H23')
    place.chain(B, comps, (ant[0], ant[1] + 0.9), BLE, 270, shunt_side=1)
    # ---- everything else, beside the pin it serves
    todo = [c.ref for c in comps if c.ref not in B.pl]
    # decoupling first (a capacitor from a supply to ground), then the rest
    def key(r_):
        c = B.comps[r_]
        return (0 if c.ref.startswith('C') and 'GND' in c.pins.values() else 1, r_)
    left = place.pack(B, sorted(todo, key=key))
    if left:
        log('no room for: %s' % left)
    return B.pl


def plot(pl, path, comps=None):
    """Both sides of the placement, for checking by eye."""
    from PIL import Image, ImageDraw
    import place as P
    comps = comps or circuit.build()
    B = P.Board(comps)
    S = 22
    W, H = int(pcb.LEN * S) + 40, int(pcb.WID * S) + 40
    img = Image.new('RGB', (W, 2 * H + 20), 'white')
    d = ImageDraw.Draw(img)
    for k, side in enumerate(('T', 'B')):
        oy = k * (H + 20)
        X = lambda x: 20 + (x + HX) * S
        Y = lambda y: oy + 20 + (y + HY) * S
        d.rectangle([X(-HX), Y(-HY), X(HX), Y(HY)], outline='black', width=2)
        d.text((24, oy + 2), 'TOP' if side == 'T' else 'BOTTOM (seen from the top)', fill='black')
        for r_, (x, y, rot, s) in pl.items():
            if s != side and not r_.startswith(('J7', 'H')):
                continue
            bx = B.rect(r_, x, y, rot, s)
            col = {'U': (60, 110, 200), 'J': (40, 150, 60), 'C': (210, 160, 60), 'R': (200, 90, 90),
                   'L': (150, 90, 200)}.get(r_[0], (120, 120, 120))
            d.rectangle([X(bx[0]), Y(bx[1]), X(bx[2]), Y(bx[3])], outline=col, width=1)
            if r_[0] in 'UJYQ' or r_.startswith(('SW', 'AE', 'FL')):
                d.text((X(bx[0]) + 2, Y(bx[1]) + 1), r_, fill=col)
        x0, y0, x1, y1 = ANT_BOX
        d.rectangle([X(x0), Y(y0), X(x1), Y(y1)], outline=(255, 0, 255))
        for hx, hy in pcb.HOLES:
            d.ellipse([X(hx - 1.1), Y(hy - 1.1), X(hx + 1.1), Y(hy + 1.1)], outline='black')
    img.save(path)


def rf_tracks(b):
    """(net, points, width) for the RF lines: each RF net's pads joined in
    order along the chain, straight."""
    import board as BD
    out = []
    pads = {}
    for fp in b.GetFootprints():
        for p in fp.Pads():
            n = p.GetNetname()
            if n in BD.RF_NETS and p.IsOnLayer(pcb.layer_id('F.Cu')):
                q = p.GetPosition()
                pads.setdefault(n, []).append((q.x / 1e6 - pcb.CX, q.y / 1e6 - pcb.CY))
    for n, pts in pads.items():
        pts = list(dict.fromkeys(pts))
        if len(pts) < 2:
            continue
        # a path through the pads: nearest neighbour from the extreme one
        rest = pts[:]
        cur = min(rest, key=lambda p: (p[0], p[1]))
        rest.remove(cur)
        path = [cur]
        while rest:
            nxt = min(rest, key=lambda p: (p[0] - cur[0]) ** 2 + (p[1] - cur[1]) ** 2)
            rest.remove(nxt); path.append(nxt); cur = nxt
        out.append((n, path, BD.RF_W))
    return out


if __name__ == '__main__':
    import sys, json
    pl = place_all()
    out = sys.argv[1] if len(sys.argv) > 1 else '/w/out/placement.png'
    plot(pl, out)
    print('placed %d parts -> %s' % (len(pl), out))
