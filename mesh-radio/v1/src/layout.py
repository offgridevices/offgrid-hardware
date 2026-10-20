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
import pcbnew
import pcb, circuit, parts, place

HX, HY = pcb.HX, pcb.HY
HDR_X0 = -7.0                      # expansion header: pin 1 / pin 11 x
NRF_RING = 1.0                     # mm kept free round the nRF52840's courtyard on the top (its pin escape)
NRF_X, SX_X = -12.6, -5.4          # the nRF52840 and the SX1262 (the TX line grows right from the SX1262)
ANT_BOX = (-HX + 8.4, 8.9, -HX + 19.1, HY)  # Bluetooth antenna keepout (x0, y0, x1, y1)


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
        # the user button on top; reset (rarely needed) under the same corner,
        # where the Bluetooth antenna leaves no room for a second one on top
        (R('SKRP', 'user'), -HX + 2.2, HY - 3.2, 90, 'T'),
        (R('SKRP', 'reset'), -HX + 2.2, HY - 3.2, 90, 'B'),
        # ---- processor and Bluetooth
        (R('NRF52840'), NRF_X, 0.3, 180, 'T'),              # SPI side towards the SX1262, USB side towards USB-C
        (R('ANT2450'), -HX + 11.6, HY - 1.35, 180, 'T'),         # feed end towards the nRF52840
        (R('HDR_2x10'), HDR_X0, 0.0, 0, 'T'),
        # ---- LoRa radio: RF pins face +x (top to bottom VR_PA, RFO, RFI_N, RFI_P)
        (R('SX1262'), SX_X, -4.4, 180, 'T'),
        (R('TCXO32'), 2.0, -4.5, 0, 'B'),                   # beside the SX1262, underneath (no room on top)
        # ---- bottom: connectors
        # JST side-entry plugs: the opening is on the fitting-nail side (JST
        # PH / SH / GH drawings, "end face of wafer on the mating side"), so
        # the nails face the edge, their copper 0.35 mm inside it
        (R('JST_PH2'), -12.4, -HY + 4.98, 0, 'B'),          # battery, opening at the upper long edge
        (R('JST_SH2'), -HX + 5.6, -HY + 3.19, 0, 'B'),          # solar, between the slide switch's pegs
        (R('JST_GH6'), HX - 6.4, HY - 3.65, 180, 'B'),          # drone port, opening at the lower long edge
        (R('JST_SH6'), HX - 3.29, 0.0, 270, 'B'),           # GPS, on the antenna end's short edge
        # ---- bottom: inputs.  USB: behind the USB-C, under the board's left
        # end; solar beside its plug; drone beside the drone plug
        (R('TVS2200', 'USB surge clamp'), -HX + 11.2, 0.6, 0, 'B'),
        (R('TPS259470A', 'USB eFuse'), -HX + 11.4, 3.8, 0, 'B'),
        (R('RB060MM', 'USB into the charger'), -HX + 8.8, 7.6, 90, 'B'),
        (R('TPD4E05U06', 'USB ESD'), -HX + 12.2, -6.0, 90, 'T'),
        (R('SMF33CA', 'SOL surge clamp'), -HX + 11.5, -10.0, 90, 'T'),    # beside the slide switch, on top
        (R('MAX17608', 'SOL 60 V current limiter'), -HX + 10.5, -6.0, 0, 'B'),
        (R('SMF33CA', 'DRN surge clamp'), 12.4, 4.6, 0, 'B'),
        (R('MAX17608', 'DRN 60 V current limiter'), 8.6, 1.6, 0, 'B'),
        (R('TPD4E05U06', 'drone ESD'), HX - 9.2, 5.3, 0, 'B'),
        # ---- bottom: charger and battery protection, by the battery plug
        (R('CSD25310Q2'), -3.8, -5.6, 0, 'B'),
        (R('BQ29700'), -6.6, -5.6, 0, 'B'),
        (R('SSM10N954L'), -5.6, -8.4, 0, 'B'),
        (R('R15m'), 0.6, -7.4, 0, 'B'),
        # the charger away from the battery plug (sim/thermal: its heat reached
        # the NTC and the cell); the NTC right by the plug, reading the cell
        (R('BQ25185'), -12.6, 5.6, 0, 'B'),
        (R('NTC10K'), -7.65, -2.6, 90, 'B'),
        (R('TPS22950'), -6.4, -2.5, 0, 'B'),
        (R('RB060MM', 'bypass: no charging from SYS'), -3.0, -2.4, 0, 'B'),
        # ---- bottom: 3.3 V
        (R('TPS62840'), -5.6, 3.0, 0, 'B'),
        (R('L2u2'), -5.6, 5.0, 0, 'B'),
        # ---- bottom: the amplifier's power, under the amplifier
        (R('TPS2121'), 9.6, -4.0, 0, 'B'),
        (R('NMOS', 'mux on with the amplifier'), 9.6, -1.6, 0, 'B'),
        (R('TPS63810'), 13.8, -3.4, 90, 'B'),
        (R('L470n'), 13.8, -0.4, 90, 'B'),
        (R('TMP1075'), HX - 10.4, -9.6, 0, 'B'),
        # ---- bottom: GPS power switch and ESD by its plug
        (R('TPS22916'), HX - 7.6, -6.6, 0, 'B'),
        (R('TPD4E05U06', 'GPS ESD'), HX - 4.4, -6.5, 0, 'B'),
        # ---- top: indicators, the amplifier's control-voltage LDO
        # LEDs in a row between the slide switch and the USB-C
        (R('LED_R'), -HX + 1.8, -5.95, 0, 'T'),
        (R('LED_G'), -HX + 4.6, -5.95, 0, 'T'),
        (R('LED_B'), -HX + 7.4, -5.95, 0, 'T'),
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
RX_Y = 8.1          # the receive line's run along the board, clear of the header holes (y 9.3)
SW_Y = 6.0          # the antenna switch's row


def rx_corridor(B, comps):
    """The receive line from the LNA output to the balun's series capacitor,
    as segments: left along RX_Y, then up to the balun."""
    lna = ref(comps, 'BGA7L1BN6')
    c = [c for c in comps if c.part == 'RF2.4pF'][0].ref
    ao = B.pad_xy(lna, '3')
    cp = B.pad_xy(c, [p for p, n in B.comps[c].pins.items() if n == 'LNA_OUT'][0])
    xc = cp[0] + 0.9
    pts = [ao, (ao[0], RX_Y), (xc, RX_Y), (xc, cp[1]), cp]
    return [(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]) for i in range(len(pts) - 1)]


NODES = {}           # RF chain node points, saved with the placement (rf_tracks joins pads to them)


def place_all(log=print):
    NODES.clear()
    comps = circuit.build()
    place.PATH_NETS = set(TX + PA_OUT + RX_IN + BLE + ['LORA_RFI_N', 'LNA_OUT'])
    B = place.Board(comps)
    x0, y0, x1, y1 = ANT_BOX
    B.keep_out((x0, y0, x1, y1), ('T', 'B'))
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
    # the nRF52840's outer ball ring leaves on F.Cu, straight out between
    # its neighbours' balls: a ring round it on the top stays free of
    # other parts (and of their ground vias, board.py), or those pins are
    # walled in (32 of the 130 connections Freerouting could not make)
    nrf = ref(comps, 'NRF52840')
    (cx0, cy0, cx1, cy1), _ = B.geom(nrf, *B.pl[nrf])
    g = NRF_RING
    for box in ((cx0 - g, cy0 - g, cx1 + g, cy0), (cx0 - g, cy1, cx1 + g, cy1 + g),
                (cx0 - g, cy0, cx0, cy1), (cx1, cy0, cx1 + g, cy1)):
        B.keep_out(box, ('T',))
    # ---- RF chains (top), a U: transmit along the top to the amplifier,
    # its output down the right end to the antenna switch, the antenna
    # through the filter to the U.FL, receive back along the bottom
    sx = ref(comps, 'SX1262')
    # the receive balun first: its inductor stands across the RFI_N line just
    # out of the pins (RFI_N on top, RFI_P below, level with pin 21's escape),
    # the RFI_P capacitor under it, then the line on through its series cap
    rfin = B.pad_xy(sx, '22')
    xe = escape(B, sx, '22')[0]
    lb = [c.ref for c in comps if c.part == 'L15nH' and set(c.pins.values()) == {'LORA_RFI_N', 'LORA_RFI_P'}][0]
    put_pad(B, lb, 'LORA_RFI_N', (xe + 0.5, rfin[1]), (0.1, 0), 'LORA_RFI_P', (0, 1))
    cb = [c.ref for c in comps if c.part == 'RF1.8pF' and 'LORA_RFI_P' in c.pins.values()][0]
    lp = B.pad_xy(lb, [p for p, n in B.comps[lb].pins.items() if n == 'LORA_RFI_P'][0])
    put_pad(B, cb, 'LORA_RFI_P', (lp[0], lp[1] + 0.9), (0, 0.1), 'GND', (0, 1))
    NODES.update(place.chain(B, comps, (B.pad_xy(lb, [p for p, n in B.comps[lb].pins.items()
                                                      if n == 'LORA_RFI_N'][0])[0], rfin[1]),
                             ['LORA_RFI_N', 'LNA_OUT'], 0, shunt_side=1))
    # transmit: out of RFO, up to the line, along the top to the amplifier
    rfo = B.pad_xy(sx, '23')
    nodes = place.chain(B, comps, (escape(B, sx, '23')[0], rfo[1] - 1.3), TX, 0, shunt_side=1, pitch_gap=0.25)
    NODES.update(nodes)
    pa = ref(comps, 'QPA9510')
    end = nodes['PA_RFIN']
    B.put(pa, 0, 0, 0, 'T', check=False)
    pin3 = B.pad_xy(pa, '3')
    B.pl.pop(pa); B.taken['T'].pop()
    B.put(pa, end[0] + 0.7 - pin3[0], end[1] - pin3[1], 0, 'T', check=False)
    # the output line runs down the right of the amplifier's four output
    # pins: they join it square, the choke goes up from its top, the match
    # starts below the lowest pin
    outs = [escape(B, pa, p) for p in ('9', '10', '11', '12')]
    xo = outs[0][0] + 2.0
    # the collector choke straight up from the output line's top, its supply
    # end's 47 pF (the RF ground the choke needs) and 1 nF beside it (the
    # 4.7 uF bulk goes with the other decoupling, by the supply pins)
    ck = ref(comps, 'L8.1nH_PA')
    top = min(e[1] for e in outs)
    put_pad(B, ck, 'PA_OUT', (xo, top - 0.9), (-0.1, 0), 'VPA', (0, -1), tries=9)   # its pad is 2 mm wide
    vp = B.pad_xy(ck, [p for p, n in B.comps[ck].pins.items() if n == 'VPA'][0])
    i = [c.ref for c in comps].index(ck)
    for k, c in enumerate(comps[i + 2:i + 4][::-1]):          # 47 pF nearest
        assert c.pins.get('1') == 'VPA' or 'VPA' in c.pins.values(), c.ref
        put_pad(B, c.ref, 'VPA', (vp[0] - 1.9 - 1.1 * k, vp[1]), (-0.1, 0), 'GND', (0, -1))
    down = place.chain(B, comps, (xo, max(e[1] for e in outs) + 0.9), PA_OUT[:3], 270, shunt_side=1,
                       alternate=True, pitch_gap=0.25)
    NODES.update(down)
    # the line turns left below PA_M2's shunts
    m2 = down['PA_M2']
    low = max(B.rect(c.ref, *B.pl[c.ref])[3] for c in comps
              if c.ref in B.pl and set(c.pins.values()) == {'PA_M2', 'GND'})
    left = place.chain(B, comps, (m2[0] - 0.4, max(low + 0.35, SW_Y)), PA_OUT[2:], 180, shunt_side=-1,
                       pitch_gap=0.25)
    NODES['PA_M2b'] = left['PA_M2']
    NODES.update({k: v for k, v in left.items() if k != 'PA_M2'})
    sw = ref(comps, 'SKY13330')
    B.put(sw, 0, 0, 180, 'T', check=False)
    p11 = B.pad_xy(sw, '11')
    B.pl.pop(sw); B.taken['T'].pop()
    tx_end = left['PA_TX']
    put_fit(B, sw, tx_end[0] - 1.1 - p11[0], tx_end[1] - p11[1], 180, (-0.1, 0))
    # the antenna: up from the switch through the filter to the U.FL
    fl = ref(comps, 'LFCG1000')
    B.put(fl, 0, 0, 90, 'T', check=False)
    f1 = B.pad_xy(fl, '8')
    B.pl.pop(fl); B.taken['T'].pop()
    p2 = B.pad_xy(sw, '2')
    put_fit(B, fl, p2[0] - f1[0], p2[1] - 2.1 - f1[1], 90, (0, -0.1))
    fl3 = B.pad_xy(fl, '4')
    uf = ref(comps, 'UFL')
    # the antenna line runs straight out of the filter's top end to the U.FL,
    # its signal pad facing the filter; along it the missing-antenna
    # detector's coupled line (sim/rf/coupler.py: 5.5 mm, 0.10 mm gap), its
    # 49.9 R at the filter end, the diode at the U.FL end; the 47 nH ESD
    # shunt stands on the other side, by the U.FL
    # (towards +x, into the strip between the amplifier and its harmonic
    # filter; the receive line's corridor is to the left)
    ya = fl3[1]
    xa = fl3[0] + 0.9                                   # the coupled run starts clear of the filter pad
    xb = xa + CPL_LEN
    B.put(uf, 0, 0, 270, 'T', check=False)
    sig = B.pad_xy(uf, '1')
    B.pl.pop(uf); B.taken['T'].pop()
    put_fit(B, uf, xb + 1.6 - sig[0], ya - sig[1], 270, (0.1, 0), tries=40)
    NODES['ANT'] = (fl3[0], ya, 0)
    yc = ya - RF_PITCH_CPL                               # the coupled line, above the antenna line
    term = ref(comps, 'R49.9R')
    put_pad(B, term, 'REFL_CPL', (xa, yc - 1.0), (0, -0.1), 'GND', (0, -1), tries=5)
    det = ref(comps, 'BAT15')
    put_pad(B, det, 'REFL_CPL', (xb, yc - 1.0), (0, -0.1), 'REFL_DET', (0, -1), tries=5)
    ta = B.pad_xy(term, [p for p, n in B.comps[term].pins.items() if n == 'REFL_CPL'][0])
    da = B.pad_xy(det, [p for p, n in B.comps[det].pins.items() if n == 'REFL_CPL'][0])
    NODES['_cpl'] = [ta, (ta[0], yc), (da[0], yc), da]
    esd = [c.ref for c in comps if c.part == 'L47nH' and set(c.pins.values()) == {'ANT', 'GND'}][0]
    put_pad(B, esd, 'ANT', (xb - 0.6, ya + 0.55), (-0.1, 0), 'GND', (0, 1), tries=10)
    # receive: from the switch's RX port (down) left along the board, the
    # LNA there; its output line runs on along the corridor to the balun
    rx = B.pad_xy(sw, '5')
    rxn = place.chain(B, comps, (rx[0] - 0.6, rx[1]), RX_IN, 180, shunt_side=1)
    NODES.update(rxn)
    lna = ref(comps, 'BGA7L1BN6')
    ai = rxn['LNA_AI']
    B.put(lna, 0, 0, 270, 'T', check=False)        # input (pin 5) facing the chain, between its ground pins
    p5 = B.pad_xy(lna, '5')
    B.pl.pop(lna); B.taken['T'].pop()
    put_fit(B, lna, ai[0] - 0.5 - p5[0], ai[1] - p5[1], 270, (-0.1, 0))
    # the receive balun at the SX1262's RFI pins
    # keep the receive line's corridor free for its track
    for (a0, b0, a1, b1) in rx_corridor(B, comps):
        B.keep_out((min(a0, a1) - 0.6, min(b0, b1) - 0.6, max(a0, a1) + 0.6, max(b0, b1) + 0.6), ('T',))
    # Bluetooth: Nordic's match then Johanson's tee, down to the antenna
    nrf = ref(comps, 'NRF52840')
    # the line starts square under the ANT pin's escape; the antenna then
    # moves along so its feed sits square under the line's end
    e = escape(B, nrf, 'H23')
    stub = (e[0] - 0.3, e[1], e[0] + 0.3, ANT_BOX[1] - 1.0)      # the pin's line down to the chain
    B.keep_out(stub, ('T',))
    ble = place.chain(B, comps, (e[0], ANT_BOX[1] - 1.0), BLE, 180, shunt_side=1)
    B.keepouts['T'].remove(stub)
    NODES.update(ble)
    ae = ref(comps, 'ANT2450')
    feed = B.pad_xy(ae, '1')
    x, y, rot, side = B.pl[ae]
    B.remove(ae)
    B.put(ae, x + ble['BLE_FEED'][0] - feed[0], y, rot, side, check=False)   # inside its own keepout
    # ---- the RF lines, kept clear of everything placed from here on
    track_keepouts(B)
    # ---- each inner ball of a ball-grid chip takes a via in the ball
    # (pipeline.ball_escapes): the spot under it on the other side stays free
    ball_keepouts(B, comps)
    # ---- everything else, beside the pin it serves
    todo = [c.ref for c in comps if c.ref not in B.pl]
    # decoupling first (a capacitor from a supply to ground), then the rest
    def key(r_):
        c = B.comps[r_]
        return (0 if c.ref.startswith('C') and 'GND' in c.pins.values() else 1, r_)
    # test pads go underneath, where a probe reaches them with the board in a case
    prefer = {r_: 'B' for r_ in todo if r_.startswith('TP')}
    gnd_tp = [c.ref for c in comps if c.part == 'TP' and c.pins['1'] == 'GND']
    for k, r_ in enumerate(gnd_tp):
        put_fit(B, r_, -HX + 1.4, 1.4 + 1.6 * k, 0, (0, 0.2), side='B')
    todo = [r_ for r_ in todo if r_ not in gnd_tp]
    left = place.pack(B, sorted(todo, key=key), prefer=prefer)
    left = place.pack(B, left)                 # parts whose anchor was placed after them
    if left:
        log('no room for: %s' % left)
    B.pl['_nodes'] = {k: ([[round(p[0], 3), round(p[1], 3)] for p in v] if k == '_cpl'
                          else [round(v[0], 3), round(v[1], 3), v[2]]) for k, v in NODES.items()}
    clashes = overlaps(B)
    for a_, b_ in clashes:
        log('overlap: %s %s' % (a_, b_))
    return B.pl


def ball_keepouts(B, comps, half=0.35):
    """A small box on the far side of the board under every inner signal
    ball of every placed chip, for its via (pipeline.ball_escapes)."""
    import board as BD
    n, bad = 0, []
    for c in comps:
        if c.ref not in B.pl or not (c.ref[0] == 'U' or c.ref.startswith('Q')):
            continue
        fp = B.footprint_at(c.ref)
        pads = [p for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
        if len(pads) < 4:
            continue
        bbs = [p.GetBoundingBox() for p in pads]
        L_, T_ = min(q.GetLeft() for q in bbs), min(q.GetTop() for q in bbs)
        R_, B_ = max(q.GetRight() for q in bbs), max(q.GetBottom() for q in bbs)
        far = 'B' if B.pl[c.ref][3] == 'T' else 'T'
        for p, bb in zip(pads, bbs):
            net = c.pins.get(p.GetNumber())
            if not net or bb.GetWidth() * bb.GetHeight() / 1e12 > 0.8:
                continue
            outer = lambda b_: min(b_.GetLeft() - L_, R_ - b_.GetRight(), b_.GetTop() - T_, B_ - b_.GetBottom()) / 1e6 < 0.05
            if outer(bb) or net in BD.RF_NETS + BD.RF_EXTRA:
                continue
            q = p.GetPosition()
            # beside an outer ball of its own net it joins on the surface, no via
            # (the same rule as pipeline.ball_escapes)
            if any(c.pins.get(o.GetNumber()) == net and outer(ob) and (o.GetPosition() - q).EuclideanNorm() / 1e6 < 0.6
                   for o, ob in zip(pads, bbs) if o is not p):
                continue
            x, y = q.x / 1e6 - pcb.CX, q.y / 1e6 - pcb.CY
            box = (x - half, y - half, x + half, y + half)
            B.keep_out(box, (far,))
            # a pad of an anchored part already there, on the far side's copper,
            # is a floor-plan error (a part body over the via is fine)
            lay = pcbnew.B_Cu if far == 'B' else pcbnew.F_Cu
            for r_ in B.pl:
                if r_.startswith('_') or r_ == c.ref:
                    continue
                for q_ in B.footprint_at(r_).Pads():
                    if not q_.IsOnLayer(lay):
                        continue
                    qb = q_.GetBoundingBox()
                    qq = (qb.GetLeft() / 1e6 - pcb.CX, qb.GetTop() / 1e6 - pcb.CY,
                          qb.GetRight() / 1e6 - pcb.CX, qb.GetBottom() / 1e6 - pcb.CY)
                    if place.overlap(qq, (x - 0.3, y - 0.3, x + 0.3, y + 0.3)):
                        bad.append('%s pad %s under %s ball %s' % (r_, q_.GetNumber(), c.ref, p.GetNumber()))
            n += 1
    if bad:
        raise ValueError('parts sit on ball vias (move them): ' + '; '.join(bad))
    return n


def escape(B, r_, pad):
    """A chip pin's escape point (see _rf_pads)."""
    fp = B.footprint_at(r_)
    pt = B.pad_xy(r_, pad)
    # (any RF net name marks the one pad wanted)
    for n, c, e in _rf_pads([(r_, fp)], lambda rr, p: 'ANT' if p.GetNumber() == pad else ''):
        if e and abs(c[0] - pt[0]) < 1e-3 and abs(c[1] - pt[1]) < 1e-3:
            return e[-1]
    raise ValueError('no escape for %s pin %s' % (r_, pad))


def put_pad(B, r_, net, at, step, far_net, far_dir, side='T', tries=60):
    """Place two-pad part r_ with its `net` pad at `at` (or the first free
    spot stepping by `step`), turned so its `far_net` pad lies toward
    far_dir (a unit (dx, dy))."""
    pn = [p for p, n in B.comps[r_].pins.items() if n == net][0]
    pf = [p for p, n in B.comps[r_].pins.items() if n == far_net and p != pn][0]
    for rot in (0, 90, 180, 270):
        _, pads = B.geom(r_, 0, 0, rot, side)
        dx, dy = pads[pf][0] - pads[pn][0], pads[pf][1] - pads[pn][1]
        if dx * far_dir[0] + dy * far_dir[1] > 0.3:
            break
    else:
        raise ValueError('cannot turn %s' % r_)
    _, pads = B.geom(r_, 0, 0, rot, side)
    put_fit(B, r_, at[0] - pads[pn][0], at[1] - pads[pn][1], rot, step, side, tries)


def put_fit(B, r_, x, y, rot, step, side='T', tries=60):
    """Place r_ at (x, y), or the first free spot stepping by `step`."""
    for k in range(tries):
        if B.fits(r_, x + step[0] * k, y + step[1] * k, rot, side):
            B.put(r_, x + step[0] * k, y + step[1] * k, rot, side)
            return
    r = B.rect(r_, x, y, rot, side)
    hits = [o for o in B.taken[side] + B.keepouts[side] if place.overlap(r, o, place.GAP)]
    edge = r[0] < -pcb.HX + 0.25 or r[2] > pcb.HX - 0.25 or r[1] < -pcb.HY + 0.25 or r[3] > pcb.HY - 0.25
    raise ValueError('no room for %s near (%.2f, %.2f): %s%s' % (r_, x, y, place.who(B, hits[:4]),
                                                            ' (and the board edge)' if edge else ''))


def overlaps(B):
    """Pairs of parts on the same side whose courtyards overlap."""
    out = []
    items = [(r_, B.rect(r_, *B.pl[r_][:3], B.pl[r_][3]), B.pl[r_][3]) for r_ in B.pl
             if not r_.startswith(('J7', '_'))]
    # through-hole pads and holes (the header's, the USB-C's legs, the
    # amplifier's thermal vias) against parts on either side
    for r_ in [k for k in B.pl if not k.startswith('_')]:
        for p in B.footprint_at(r_).Pads():
            if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                bb = p.GetBoundingBox()
                bx = (bb.GetLeft() / 1e6 - pcb.CX, bb.GetTop() / 1e6 - pcb.CY,
                      bb.GetRight() / 1e6 - pcb.CX, bb.GetBottom() / 1e6 - pcb.CY)
                for s_ in ('T', 'B'):
                    items.append(('%s:hole' % r_, bx, s_))
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a_, ra, sa = items[i]; b_, rb, sb = items[j]
            if a_.split(':')[0] == b_.split(':')[0] or (a_.endswith(':hole') and b_.endswith(':hole')):
                continue
            if sa == sb and place.overlap(ra, rb, 0.0):
                # how much: ignore touching boxes
                w = min(ra[2], rb[2]) - max(ra[0], rb[0]); h = min(ra[3], rb[3]) - max(ra[1], rb[1])
                if w > 0.02 and h > 0.02:
                    out.append((a_, b_))
    return out


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
        for r_, v in pl.items():
            if r_.startswith('_'):
                continue
            x, y, rot, s = v
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


ESCAPE = 0.25   # mm past a chip pad's outer end: the line's edge then clears the pin row by ~0.17 mm
CPL_LEN = 5.5   # the missing-antenna detector's coupled run (sim/rf/coupler.py)
RF_PITCH_CPL = 0.27   # centre to centre: 0.17 mm lines, 0.10 mm gap


def _rf_pads(fps, net_of):
    """[(net, centre, escape path or None)] for every top pad on an RF net.
    fps: (ref, footprint) pairs already at their place; net_of(ref, pad).
    A chip pin's escape path runs straight out through the nearest side of
    the chip's pad outline to ESCAPE past it.  An inner ball (the nRF52840's
    ANT) first steps to the middle of the gap between the two outer-row
    balls beside it, then runs out through that gap."""
    import board as BD
    cx, cy = pcb.CX, pcb.CY
    out = []
    mm = lambda v: v / 1e6
    for ref_, fp in fps:
        ic = ref_[0] == 'U'
        if ic:
            bbs = [p.GetBoundingBox() for p in fp.Pads()]
            L_, T_ = min(q.GetLeft() for q in bbs), min(q.GetTop() for q in bbs)
            R_, B_ = max(q.GetRight() for q in bbs), max(q.GetBottom() for q in bbs)
        for p in fp.Pads():
            n = net_of(ref_, p)
            if n not in BD.RF_NETS or not p.IsOnLayer(pcbnew.F_Cu):
                continue
            q = p.GetPosition()
            pt = (round(mm(q.x) - cx, 4), round(mm(q.y) - cy, 4))
            e = None
            if ic:
                bb = p.GetBoundingBox()
                side = min([(bb.GetLeft() - L_, (-1, 0), q.x - L_),
                            (R_ - bb.GetRight(), (1, 0), R_ - q.x),
                            (bb.GetTop() - T_, (0, -1), q.y - T_),
                            (B_ - bb.GetBottom(), (0, 1), B_ - q.y)])
                (dx, dy) = side[1]
                d = mm(side[2]) + ESCAPE
                e = [(round(pt[0] + dx * d, 4), round(pt[1] + dy * d, 4))]
                if mm(side[0]) > 0.02:                 # an inner ball: through the outer row's gap
                    edge = {(-1, 0): lambda b: b.GetLeft() - L_ < 20000, (1, 0): lambda b: R_ - b.GetRight() < 20000,
                            (0, -1): lambda b: b.GetTop() - T_ < 20000, (0, 1): lambda b: B_ - b.GetBottom() < 20000}
                    row = [o.GetPosition() for o in fp.Pads() if edge[side[1]](o.GetBoundingBox())]
                    along = (lambda v: mm(v.y) - cy) if dx else (lambda v: mm(v.x) - cx)
                    a0 = pt[1] if dx else pt[0]
                    lo = max(along(v) for v in row if along(v) < a0)
                    hi = min(along(v) for v in row if along(v) > a0)
                    m = (lo + hi) / 2
                    across = mm(row[0].x) - cx if dx else mm(row[0].y) - cy
                    way = (across, m) if dx else (m, across)
                    end = (e[0][0], m) if dx else (m, e[0][1])
                    e = [tuple(round(v, 4) for v in way), end]
            out.append((n, pt, e))
    return out


def rf_paths(pads, nodes):
    """(net, points, width) for the RF lines, all square to the chain.

    A chain net (one with a node, place.chain saved it with the chain's
    direction) is a straight line along the chain through the node; every
    pad on the net drops square onto it, so a series part's pad sits on the
    line and a shunt's pad joins it by a short stub.  A net with two nodes
    (the amplifier output's corner) runs along both lines to their meeting
    point.  A chip pin first runs ESCAPE straight out of its pin row, 0.2 mm
    wide, so nothing full width passes a neighbouring pin.  Nets with no
    node join their pads by a shortest tree.  The receive line runs from
    the LNA along its corridor to its node."""
    import board as BD, math
    out = []
    by = {}
    for n, pt, e in pads:
        by.setdefault(n, []).append((pt, e))

    def add(n, a_, b_, w=None):
        if math.hypot(b_[0] - a_[0], b_[1] - a_[1]) > 1e-3:
            out.append((n, [a_, b_], w or BD.RF_W))

    def proj(h, p):
        ux, uy = math.cos(math.radians(h[2])), -math.sin(math.radians(h[2]))
        t = (p[0] - h[0]) * ux + (p[1] - h[1]) * uy
        return t, (round(h[0] + ux * t, 4), round(h[1] + uy * t, 4))

    if '_cpl' in nodes:                                  # the detector's coupled line, as drawn
        cp = [tuple(p) for p in nodes['_cpl']]
        for a_, b_ in zip(cp, cp[1:]):
            add('REFL_CPL', a_, b_)
    for n, pp in sorted(by.items()):
        starts = []
        for pt, e in pp:
            if e:
                for a_, b_ in zip([pt] + e, e):          # the narrow escape
                    add(n, a_, b_, min(0.2, BD.RF_W))
            starts.append(e[-1] if e else pt)
        hubs = [tuple(nodes[k]) for k in (n, n + 'b') if k in nodes]
        if n == 'LNA_OUT' and hubs:
            hub = hubs[0]
            for (pt, e), s_ in zip(pp, starts):
                if e:                                    # the LNA's output: along the corridor
                    path = [s_, (s_[0], RX_Y), (hub[0], RX_Y), hub[:2]]
                    for i in range(len(path) - 1):
                        add(n, path[i], path[i + 1])
            hubs_pp = [s_ for (pt, e), s_ in zip(pp, starts) if not e]
            pp, starts = [(None, None)] * len(hubs_pp), hubs_pp
        if hubs:
            ts = {h: [0.0] for h in hubs}
            if len(hubs) == 2:                           # the corner where the two lines meet
                h1, h2 = hubs
                a1, a2 = math.radians(h1[2]), math.radians(h2[2])
                d1, d2 = (math.cos(a1), -math.sin(a1)), (math.cos(a2), -math.sin(a2))
                den = d1[0] * d2[1] - d1[1] * d2[0]
                t1 = ((h2[0] - h1[0]) * d2[1] - (h2[1] - h1[1]) * d2[0]) / den
                corner = (h1[0] + d1[0] * t1, h1[1] + d1[1] * t1)
                for h in hubs:
                    ts[h].append(proj(h, corner)[0])
            for s_ in starts:
                h = min(hubs, key=lambda h: abs(proj(h, s_)[0]) + 3 * math.hypot(*(
                    a - b for a, b in zip(proj(h, s_)[1], s_))))
                t, q = proj(h, s_)
                add(n, s_, q)
                ts[h].append(t)
            for h in hubs:                               # the line itself
                u = (math.cos(math.radians(h[2])), -math.sin(math.radians(h[2])))
                end = lambda t: (round(h[0] + u[0] * t, 4), round(h[1] + u[1] * t, 4))
                add(n, end(min(ts[h])), end(max(ts[h])))
            continue
        # no node: a shortest tree over the pads (Prim)
        done, rest = [starts[0]], starts[1:]
        while rest:
            best = min(((d, r) for d in done for r in rest),
                       key=lambda t: (t[0][0] - t[1][0]) ** 2 + (t[0][1] - t[1][1]) ** 2)
            add(n, best[0], best[1])
            done.append(best[1]); rest.remove(best[1])
    return out


def rf_tracks(b, nodes):
    """The RF lines of a built board (board.py draws them, locked)."""
    return rf_paths(_rf_pads([(fp.GetReference(), fp) for fp in b.GetFootprints()],
                             lambda r_, p: p.GetNetname()), nodes)


def track_keepouts(B):
    """Keep the packer's parts off the RF lines: each line's box (they are
    square to the board) grown by half its width and a clearance."""
    fps = []
    for r_, (x, y, rot, side) in B.pl.items():
        if r_.startswith('_') or side != 'T':
            continue
        fps.append((r_, B.footprint_at(r_)))
    paths = rf_paths(_rf_pads(fps, lambda r_, p: B.comps[r_].pins.get(p.GetNumber()) or ''), NODES)
    for n, (a_, b_), w in paths:
        m = w / 2 + 0.12
        B.keep_out((min(a_[0], b_[0]) - m, min(a_[1], b_[1]) - m, max(a_[0], b_[0]) + m, max(a_[1], b_[1]) + m), ('T',))
    return paths


if __name__ == '__main__':
    import sys, json
    pl = place_all()
    out = sys.argv[1] if len(sys.argv) > 1 else '/w/out/placement.png'
    plot(pl, out)
    print('placed %d parts -> %s' % (len(pl), out))
