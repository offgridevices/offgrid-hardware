"""Canary v1 product video: narration, one entry per segment.
Every number spoken here is checked against the design or a test result
(see the comment after each segment)."""

SEGMENTS = [
    ('title',
     "This is Canary. A small yellow board that sits beside a lithium battery while it charges, "
     "and notices trouble before there is any smoke."),
    ('problem',
     "E-bike and scooter batteries get charged in hallways and bedrooms, often overnight. "
     "When a cell fails, it does not start with smoke. It starts with a vent: "
     "the electrolyte boils off as solvent vapour and carbon dioxide. "
     "Then the cell heats itself, runs away, and burns. "
     "A smoke alarm only reacts at the very end of that chain, "
     "when the fire may already be between you and the door."),
    ('gap',
     "Grid storage batteries and electric car packs already carry off-gas detectors for exactly this. "
     "The battery in your hallway has nothing. "
     "So I designed one you can order fully assembled."),
    ('turntable',
     "Here it is. Sixty by forty millimetres, two copper layers, and every part on the top side, "
     "so the factory assembles it in a single pass. "
     "Power comes in over USB-C, from any phone charger."),
    # 60 x 40 mm: board.py W,H; 2 layers; all parts F.Cu (CPL is top only)
    ('tour',
     "An At-mega three twenty-eight P runs the firmware. "
     "On the right, behind a slot that keeps the board's own warmth away, is the sensor head: "
     "a Sensirion SGP40 metal-oxide gas sensor, which reacts to solvent vapour, "
     "and an SHT40 for humidity and air temperature. "
     "In the middle sits a Sensirion SCD41, a photoacoustic carbon dioxide sensor. "
     "Bottom left is the thermal tab, another island cut free by slots, "
     "with copper on both faces and a one percent thermistor. "
     "Lay the board on the pack, and the tab reads the pack's skin temperature. "
     "If the pack charges inside the frame, a remote probe plugs into the connector beside it. "
     "Up top: a one hundred decibel sounder, three status lights, and a test and hush button."),
    # SGP40/SHT40/SCD41/ATmega328P: circuit.py; NTC NCU18XH103F60RB 1 %; CMT-8504 100 dB @10 cm
    ('fusion',
     "The firmware never trusts a single sensor. "
     "Cleaning spray trips the gas sensor. Someone breathing nearby raises carbon dioxide. "
     "A warm room warms the pack. Each of those is one kind of evidence, "
     "and earns an amber warning at most. "
     "A venting cell is different. Solvent vapour and carbon dioxide arrive together, "
     "and then the pack starts to heat. "
     "Two kinds of evidence at once, or a pack heating faster than three degrees a minute, "
     "and Canary goes to full alarm."),
    # detect.c: alarm = (g && c && one STRONG) || h STRONG || (h && (g||c)) || ...
    ('sim',
     "To prove the firmware, I ran the real compiled binary on a simulated At-mega chip, "
     "with virtual Sensirion sensors on its I2C bus, speaking their datasheet commands, "
     "and played scenarios into it. "
     "Here a cell vents at the four hundred second mark. "
     "The gas signal plunges, carbon dioxide climbs, "
     "and seven and a half seconds later the red light flashes, "
     "and the sounder starts the three-pulse pattern that smoke alarms use, at four kilohertz."),
    # sim/hil results.json: vent latency 7.6 s; buz_hz 3997; T3 pattern
    ('verify',
     "Everything is generated from code, and checked. "
     "The schematic passes the electrical rules check with zero violations. "
     "The board passes design rules with zero errors, zero warnings and zero unconnected pads, "
     "against P C B Way's own limits. "
     "Fifty-six hardware-in-the-loop checks pass across eight scenarios, "
     "and a SPICE model shows the sounder driver stays clamped just above the supply."),
    ('order',
     "To get one, upload the Gerber zip, the bill of materials and the placement file to P C B Way, "
     "ask them to flash the included firmware, and plug it into a USB charger. "
     "One honest caveat. The thresholds follow how venting cells are known to behave, "
     "but they have not yet been tested against a real cell venting beside this board. "
     "That test comes next. Until then, Canary is an early warning, not a certified alarm. "
     "Keep your smoke alarm."),
    ('end',
     "Canary. Hear the battery, before you smell the smoke."),
]
