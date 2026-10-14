# Ridge 3: reliability review

What the simulations say about running the rev 2 stack hard, hot, high and
crashed, the choices that trade one kind of margin for another, and what
only the bench can settle.  Nothing here is measured: no board has been
built.  Every figure comes from the tools in `sim/` run on the committed
boards, and each section names the tool and its report (committed in
`sim/results/`; commands run from `ridge-3/`).

## The variants

`sim/stress.py --variant=NAME` runs the whole of `STRESS.md` on rev 2 with
one change (`sim/data.py`, `VARIANTS`); `sim/variants.py` puts them side by
side ([`sim/results/VARIANTS.md`](../sim/results/VARIANTS.md)).  The flight
is the hard 3-minute one of `STRESS.md`: 20 s cycles of 2 s at full
throttle, 4 s at 60 % and 14 s at 40 % (7.3 A per motor on average).

| | As built | IDRIVE 30/60 mA | AM32 limit 120 °C | LiHV 26.1 V | 2,250 m | BSZ040 FETs | BSZ040 + IDRIVE 30/60 |
|---|---|---|---|---|---|---|---|
| SHx at 30 A, 5 nH (3-8 nH) | -10.3 V (-14.2) | -6.2 V (-8.5) | -10.3 V | -10.3 V | -10.3 V | -11.8 V (-15.9) | -6.7 V (-9.0) |
| FET peaks, high / low side (60 V parts) | 39.6 / 42.5 V | 32.3 / 26.8 V | same | 40.5 / 43.8 V | same | 42.1 / 57.4 V | 33.4 / 27.4 V |
| Held all day before AM32 cuts, 50 °C, 5 m/s | 52 % (7.5 A) | 48 % (6.3 A) | 54 % (8.4 A) | 50 % (7.3 A) | 58 % (7.9 A) | 48 % (6.3 A) | 44 % (5.3 A) |
| The same, 60 °C, 2 m/s | 40 % (4.4 A) | 30 % (2.9 A) | 44 % (5.3 A) | 35 % (3.9 A) | 47 % (4.7 A) | 32 % (3.2 A) | 28 % (2.5 A) |
| Hard flight at 50 °C: AM32 cuts a motor | 10 % of it, from 62 s | 18 %, from 26 s | 2.5 %, from 106 s | 15 %, from 42 s | never | 19 %, from 25 s | 24 %, from 22 s |
| Hard flight: hottest FET / ESC processor | 128 / 111 °C | 128 / 111 °C | 136 / 117 °C | 130 / 111 °C | 118 / 104 °C | 134 / 112 °C (150 °C part) | 134 / 112 °C |
| Parts past their rating in the hard flight | none | none | the X7R bridge capacitor, 128 °C (125 °C) | none | none | none | none |

Hover is 27 % throttle at sea level (32 % at 2,250 m).  The amps are each
motor's battery current at that throttle.

What they say:

- **IDRIVE (the gate drivers' speed).**  As built (60 / 120 mA, 75 kΩ) the
  high side's turn-off pulls SHx to -10.3 V at 30 A in the 5 nH loop, past
  the DRV8320H's -7 V for 200 ns.  At 30 / 60 mA (18 kΩ) it is -6.2 V, and
  the FETs' own peaks fall from 39.6 / 42.5 V to 32.3 / 26.8 V.  The cost
  is heat: on a 50 °C day the throttle AM32 lets a motor hold falls from
  52 to 48 % (7.5 to 6.3 A), and in the hard flight AM32 cuts a motor for
  18 % of it instead of 10 %.  At a punch's current the dip is deeper for
  both settings (see the punch, below).
- **AM32's temperature limit.**  110 °C keeps every part in its rating.
  120 °C nearly removes the cuts in the hard flight (2.5 % of it) but puts
  the ESC's X7R bridge capacitor at 128 °C, past its 125 °C (and the
  current amplifiers past theirs with IDRIVE 30).  Keep 110 °C.
- **LiHV (26.1 V full).**  The same verdicts as 6S LiPo; the FETs peak at
  40.5 / 43.8 V against 60 V, and the hard flight is cut for 15 % of it.
- **Altitude (2,250 m).**  Thinner air loads the props less and cools the
  boards less; the hard flight is never cut.  On the ground at 60 °C one
  more part passes its rating.
- **The second-source FET, Infineon BSZ040N06LS5** (JLC stock; 4.0 mΩ,
  rated 150 °C instead of 175 °C): no.  Its body-diode recovery takes the
  low-side FET to 57.4 V of its 60 V and SHx to -11.8 V, and it runs
  hotter (AM32 cuts the hard flight for 19 % of it) with 25 °C less
  rating.  With IDRIVE 30/60 the voltages are fine but the heat is worse
  again (24 %).  In a crash its higher resistance makes the driver's trip
  act sooner (131 °C from a cool board), but from a hot one it reaches
  258 °C against its 150 °C ([`sim/results/crash/bsz040/CRASH.md`](../sim/results/crash/bsz040/CRASH.md)).  Keep the
  ISZ023N06LM6 and buy it ahead; qualify a second FET on the bench before
  relying on one.

## A crash: a motor stopped dead at full throttle

`sim/crash.py` ([`sim/results/crash/CRASH.md`](../sim/results/crash/CRASH.md)):
the prop hits something and the rotor stops at once while the duty is at
full.  AM32 reacts in about 22.5 ms
(its back-EMF timeout), ramps the duty down to its startup clamp at 2 % per
ms, and cuts the motor after about 248 ms.  Its current limit, on a 50 ms
average, barely moves in that time.  The DRV8320H's overcurrent monitor
measures each FET with board copper in series: up to 0.68 mΩ on the low
side and 0.91 mΩ on the high side (0.99 mΩ with all four motors drawing);
as built (VDS pin open) it trips at 0.6 V, a typical figure with no limits
in the datasheet.

The low-side FET's junction (rated 175 °C) and how long it stays above
that, the FET's case taken as its drain copper with all its heat in it:

| Start | Driver's trip | AM32 cuts the stalled motor after | FET peak | Above 175 °C |
|---|---|---|---|---|
| cool board (25 °C) | none (a bound) | 248 ms (as it ships) | over 300 °C | 243 ms |
| cool board | 0.6 V (as built) | 248 ms | 182 °C | 11 ms |
| cool board | 0.6 V | 68 ms (target change) | 182 °C | 11 ms |
| cool board | 0.26 V (75 kΩ) | 248 ms | 70 °C | 0 |
| hot (128 °C, after the hard flight at 50 °C) | none (a bound) | 248 ms | over 300 °C | 249 ms |
| hot | 0.6 V (as built) | 248 ms | 221 °C | 198 ms |
| hot | 0.6 V | 68 ms | 195 °C | 21 ms |
| hot | 0.26 V | 248 ms | 193 °C | 67 ms |
| hot | 0.26 V | 68 ms | 141 °C | 0 |

- The trip as built does most of the work: it acts in the first
  milliseconds once the FET is warm, because the FET's resistance rises
  with its temperature and the monitor reads it through the board's copper
  (0.68 mΩ on the worst phase).  Without it the FET is lost in any crash
  like this, hot or cool.
- On a hot board the damage is done after AM32's back-EMF timeout: its
  startup clamp keeps about 35 A in the stalled motor for a quarter of a
  second.  AM32 cuts after 11 timeouts (`bemf_timeout` 10, a variable in
  `main.c`, not a setting); after 3 the hot crash's time over the rating
  falls from 198 to 21 ms.  The cost is a motor cut in flight if three
  timeouts ever come in a row without a crash: a bench and flight test.
- 0.26 V would protect the FET outright with the shorter cut, but it trips
  at 51-62 A on a hot FET, under the 64-68 A of a full-throttle punch (see
  below), and the VDS pin has no footprint for the resistor.
- The funnel via under Q1AL peaks at 166 °C (cool) and 171 °C (hot, with
  the trip): below the 288 °C where pads lift.  More vias there are not
  needed for this.
- The model leans hot: the copper gives heat only to the FR-4 against it,
  not to the planes of other nets or the heatsink, over 250 ms; and the
  jam is instant and stays on one FET.  A prop that breaks, a rotor that
  slows over a few milliseconds (AM32's low-rpm limit then cuts the duty
  as it slows) or a throttle off the stick are all far easier on the ESC.

## A punch: full throttle from hover

`sim/punch.py` ([`sim/results/punch/PUNCH.md`](../sim/results/punch/PUNCH.md)): all four motors from hover to
full at AM32's 16 % per ms.

The motor is fitted to its maker's load test; the rotor and prop's inertia
is not published (1.5-4 × 10<sup>-6</sup> kg m<sup>2</sup> assumed).  Each
motor's phase current peaks at **64-68 A** about 4 ms in (68-72 A on a full
LiHV pack), then AM32's current limit brings it down over the next tens of
milliseconds.

The overcurrent monitor, with the copper it measures through (on the high
side the four motors' current in the shared battery plane adds to it):

| FET at | 0.6 V (as built) trips at | 0.26 V trips at |
|---|---|---|
| 25 °C | 181-221 A | 79-96 A (15 % over the punch) |
| 128 °C (after the hard flight at 50 °C) | 118-143 A | 51-62 A: **under the punch** |

The switching edge at the punch's current, against the DRV8320H's -7 V
(200 ns) on SHx and the FETs' 60 V:

| IDRIVE | 68 A, loop 3 / 5 / 8 nH: SHx lowest | FET peaks, 8 nH (high / low side) |
|---|---|---|
| 60 / 120 mA (as built) | -11.0 / -15.5 / -21.6 V | 55.6 / 57.2 V |
| 30 / 60 mA | -6.3 / -8.9 / -12.4 V | 39.5 / 32.4 V |

(FET at 25 °C, the worse case; [`sim/results/punch/PUNCH.md`](../sim/results/punch/PUNCH.md) has 30 A and 150 °C.)
Neither setting keeps SHx inside -7 V at a punch's current in the 5 nH
loop the layout is estimated at.  30 / 60 mA roughly halves the overshoot
and keeps the FETs 20 V clear of their rating; at 60 / 120 mA in the 8 nH
bracket they come within 3 V of it.  How long the dip lasts, and how the
layout's real loop compares with 5 nH, only a scope will say.

## On the ground

`sim/ground.py` ([`sim/results/variants/rev2/GROUND.md`](../sim/results/variants/rev2/GROUND.md)), still air, video on:

| Air | HD unit on the 9 V pads (9 V 1.5 A, 5 V 1 A) | HD unit on the battery (5 V 1 A) |
|---|---|---|
| 25 °C | video on 69 % of the time | 100 % |
| 35 °C | 46 % | 100 % |
| 50 °C | 8 % | 100 % |
| 60 °C | 0 %, the FC's processor at 107 °C (105 °C rated) | 100 %, the processor at 107 °C |

The thermostat keeps the parts in their ratings by cutting video; it is not
a fault.  Both rails at their 2 A rating, on the ground in still air, put
parts past their ratings even at 25 °C: rate the 5 V rail at about 1 A
continuous on the ground (0.5 A at 60 °C), 2 A with airflow.

## What only the bench can settle

- How deep and how long SHx dips below -7 V, at each IDRIVE, at punch
  currents (a scope on SHx).
- Whether the overcurrent monitor trips in hard hot punches (nFAULT has no
  pad: probe the driver's pin 17).
- The locked-rotor behaviour at reduced voltage: AM32's cut, false
  zero-crosses, a latched gate-driver fault that clears only by unplugging.
- The ESC temperature Betaflight shows against the hottest FET.
- Vibration, crash shock, thermal cycling, water, EMC: none are simulated.

## Recommendations

In order.  None of them needs a part ordered today.

1. **Build a few and have them measured before any volume.**  One FC panel,
   two ESC panels on the same Gerbers (one with the 75 kΩ IDRIVE resistor,
   one with 18 kΩ), and an engineer with a scope, current probe,
   thermocouples and a logic analyser for the list above.  Keep a third of
   the ESCs for destructive tests (locked rotor at reduced voltage first).
2. **Program every ESC at the factory from one image** (bootloader,
   firmware and the settings page: 110 °C, 20 A, stuck-rotor protection
   on, 3D and car-reverse off, a fixed 24 kHz PWM with variable PWM off)
   and read it back over SWD on a pogo fixture.  An erased settings page
   reads as car-reverse mode with both limits off; a forgotten "Send
   default config" is the most likely way to ship an unprotected ESC.  Make the target fall back to 110 °C / 20 A
   whenever a stored limit reads as disabled.
3. **IDRIVE: decide on the bench.**  Put the 18 kΩ (30 / 60 mA) on one
   prototype ESC panel and the 75 kΩ (60 / 120 mA) on the other, and scope
   SHx and the FETs in hot full-throttle punches.  Unless the scope shows
   60 / 120 mA inside the driver's limits, ship 30 / 60 mA: at a punch's
   current it halves the dip and keeps the FETs well clear of 60 V, and its
   cost is heat headroom (52 to 48 % throttle held on a 50 °C day; AM32
   cuts a motor in 18 % of the hard flight instead of 10 %), which is the
   firmware protecting the board, not the board failing.  Neither setting
   holds SHx inside -7 V at 68 A: with the scope's numbers, evaluate a
   clamp or series resistor at the SHx pins, or an RC snubber, in the next
   ESC revision.
4. **Keep AM32 at 110 °C / 20 A.**  120 °C takes the bridge capacitor past
   its rating.  Add Betaflight's ESC temperature warning about 10 °C below
   (the pilot sees it before a motor drops to a quarter).
5. **A shorter stuck-rotor cut in the AM32 target** (`bemf_timeout` 2: the
   cut after about 68 ms instead of 248 ms) cuts a hot crash's time over
   the FET's rating from 198 to 21 ms.  Bench- and flight-test it for
   false cuts before shipping it.
6. **Leave the overcurrent trip at 0.6 V.**  0.26 V trips under a hard
   punch on a hot day.  In the next ESC revision add, per driver, a VDS
   resistor footprint left unfitted, a test pad on nFAULT, and SLx and
   VDRAIN routed as their own traces to the FETs.
7. **Parts for volume.**  Keep the ISZ023N06LM6 (DigiKey only, 52-week
   factory lead time) and buy a year ahead from authorised sources; do not
   use the BSZ040N06LS5.  Buy ahead, with quantities, from authorised
   sources: the STM32G473 (ST quotes 52 weeks for the family), the
   AT32F421 (JLC/LCSC only), the DRV8320H (TI store), the IIM-42652, the
   LMR38020F, the bus capacitors and the shunts.  The FC's 3.3 V inductor
   (TDK TFM252012ALMAR47MTAA) is out at JLC: buy it at DigiKey, or use
   Bourns SRP2512TMA-R47M (150 °C, same size); not a 125 °C part.  Keep
   the TPS628501DRLR.
8. **Rate it plainly** (open: [`STATUS.md`](STATUS.md), D8): 3S-6S LiPo
   and 6S LiHV; 50 °C air in flight (AM32 trims power in the hardest
   flying at that heat); the 5 V rail 1 A continuous on the ground (0.5 A
   at 60 °C), 2 A with airflow; HD video on the 9 V pads (the thermostat may pause it on the
   ground in heat).  Sell the HD build first: the analog build's OSD is an
   85 °C part.
9. **Ship the ESC on its heatsink**, gap pad fitted and checked, and test
   every stack before it ships: the four ESC temperatures read sensibly,
   each current sensor against a known load, each motor spins, the gyro,
   the rails, the heatsink isolated from battery and ground.
10. **Before selling:** an EMC pre-scan on the prototypes, the marks for
    each market, vibration, crash shock, thermal cycling and water tests on
    a few units, and the Betaflight gyro fix and the AM32 target sent
    upstream so customers who update get the right firmware.
