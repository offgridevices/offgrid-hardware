# Canary v1 — decisions and trade-offs

**Why this board.** Lithium battery fires in homes start at the charger,
often overnight. A cell's first vent (electrolyte solvent vapour, CO₂, H₂)
comes before thermal runaway; commercial off-gas detectors for grid storage
and EV packs exploit exactly that. Nothing similar exists as a cheap, open,
order-it-assembled device for the battery in a hallway. Canary is that.

**Evidence fusion, not one sensor.** A MOX VOC sensor alone would alarm on
cleaning spray; CO₂ alone on a person leaning over it; temperature alone
is late. A vent produces solvent and CO₂ together, then heat. Requiring two
kinds of evidence (or one at an extreme: strong heat) is what makes it
livable in a home. Single evidence gives amber, never the siren.

**SGP40 + SCD41 + SHT40.** SGP40 is the cheapest sensitive MOX part with a
clean I²C interface and humidity compensation (fed from the SHT40). SCD41 is
a true photoacoustic CO₂ sensor (not eCO₂ estimated from VOCs), which keeps
the two kinds of evidence independent. SCD41 is the most expensive part; it
is also what separates "smells" from "venting".

**ATmega328P.** In production, cheap, and — the deciding reason — simavr
models it well, so the *real* firmware binary is verified in a
hardware-in-the-loop simulation with virtual Sensirion sensors. A Wi-Fi MCU
(notifications to a phone) is the obvious v2 feature, at the cost of that
verification path and of radio certification.

**Thermal tab and sensor head isolated by slots.** The board itself warms a
few degrees (LDO, SCD41, MCU, ~120 mW). Routed slots put the gas/RH head and
the NTC tab on islands joined by narrow necks, so they read the air and the
pack rather than the board. Rate-of-rise detection is insensitive to a fixed
offset anyway; the slots protect the absolute 50/65 °C thresholds.

**Sounder from VBUS, low side.** The CMT-8504 (100 dB at 10 cm) is driven at
5 V by an AO3400A with a B5819W clamp, from Timer1 toggling at 4 kHz, in the
temporal-three pattern smoke alarms use so people recognise it.

**Power only USB-C.** Every home has a USB charger; 5.1 kΩ Rd on CC gives
5 V from any USB-C source. No battery backup in v1 (if the outlet is dead,
the charger is too).

**Two layers, all parts on top.** One assembly pass, cheapest PCBWay
service; the board is not dense. Ground is not routed: every ground pad has
its own via into solid pours on both layers (`board.py: fanout`), and
Freerouting routes only signals.

**Corners and track widths.** At Canary's speeds (100 kHz I²C, 38400 baud,
4 kHz sounder) a corner does nothing electrically: a signal's rise time is
thousands of times longer than the trace. Corners are kept to 45° anyway, for
etching (an inside right angle can trap etchant and an outside one etches
thin): Freerouting left six right-angle corners where tracks turn onto pads,
and `src/miter.py` cuts each into two 45° turns after routing. Widths are
set by heat, not by geometry: by IPC-2221 (outer layer, 1 oz, 10 °C rise)
VBUS needs 0.12 mm for its 0.52 A worst-case peak and has 0.30 mm; the
sounder drain needs 0.07 mm for 0.33 A and has 0.30 mm; +3V3 needs 0.03 mm
for 0.2 A and has 0.25 mm. `src/check_geometry.py` gates both.

**Yellow mask, black silk.** A canary. Also high-contrast for the labels a
user needs (OK / WARN / ALARM, TEST / HUSH, NTC TAB, AIR IN).

**Thresholds** live in `firmware/src/detect.h`, with the reasons. They are
the part of this design least proven — see the README's Limits.

**Tool notes (KiCad 10.0.6, Freerouting 1.9.0, simavr):**
- KiCad's single-pin `unconnected-(…)` nets (names with parentheses and
  `{slash}`) stall Freerouting 1.9.0's DSN reader; `src/dsn_tweak.py` drops them.
- Freerouting does not see internal routed slots: rule areas around each slot
  (`board.py: slot_keepouts`) keep it at the fab's edge clearance.
- Freerouting leaves the last few connections; `make.py` gives the routed
  board back to it for another round until DRC has nothing unconnected.
- The SHT4x footprint keeps copper from under the sensor; its pads are
  entered by fixed stubs from outside the body.
- pcbnew's Python API does not expose the board stackup; `finish.py` writes
  it into the file (mask/silk colours, ENIG).
- simavr 1.6 (Ubuntu 24.04 package) answers SLA+W ACK with status 0x28
  instead of 0x18, so a polled TWI master fails; upstream master fixes it.
