# Print Hub v1: tests and simulations

Every test and simulation for this revision, why it exists, how to run it,
and its v1 result. Results are for this revision only
([`docs/versioning.md`](../../docs/versioning.md)). The build gates run in
CI on every push (`ci / print-hub-v1`); the rest were run by hand on the
dates given, on the commit that adds this file's results.

## Build gates (`src/make.py`; CI)

| Gate | Why | Result (17 Oct 2026) |
|---|---|---|
| Every part has a footprint and an LCSC number; no single-pin net; every pin on its footprint, every pad in `circuit.py` | a wrong or missing pad is a dead board | pass, 135 parts |
| KiCad 10.0.6 DRC with JLCPCB's limits | the fab rejects or mis-builds what breaks its rules | 0 errors, 0 warnings, 0 unconnected |
| Every pad's net on the routed board equals `src/circuit.py` | the copper is the circuit | pass |
| BOM and CPL list exactly the assembled parts | nothing missing or extra on the assembly line | pass, 129 parts |
| Committed Gerbers, drills, BOM, CPL, netlist, rules equal what `make.py` builds (`tools/check_outputs.py`) | someone orders from the committed files | pass |

## Design checks (`src/verify.py` -> `VERIFICATION.md`; CI)

| Check | Why | Result |
|---|---|---|
| Firmware pin map (`firmware/src/board.h`) against the circuit: 5 enables, 5 faults, 5 current inputs, both voltage senses, LED data, I2C, BOOT, native USB | a pin mismatch is a port that never switches or a reading of the wrong port | pass |
| Firmware scaling (shunt, gain, both dividers) against the parts | wrong scaling is a wrong current limit | pass |
| LED chain order against the firmware's LED index | the right LED for the right port | pass |
| Analogue inputs on ADC1 only; strapping pins left open | ADC2 stops while Wi-Fi is on; a strapping pin can stop the board booting | pass |
| Every port: switch from the rail, enable pull-down, fault pull-up, 47k ILIM, amplifier across the shunt, D+ joined to D- | the same protection on every port | pass |
| The server's USB reaches the logic only through a diode, never a port | the server's 5 V never powers an accessory | pass |
| Proved to catch errors: two enable pins swapped and a wrong divider in `board.h` | a check that cannot fail is no check | caught all 3 |
| Total | | **65 pass, 0 fail** |

## Simulations (`sim/`)

| Simulation | Why | Result (17 Oct 2026) |
|---|---|---|
| `power_budget.py`: buck ripple, peak current against the inductor's saturation, efficiency, junction temperature at 45 C air; port voltage at 1, 1.5 and 2.2 A worst case; switch and shunt heat; current-sense range and error; logic supply from the server's USB alone; budget per charger | every rating with its margin, from the datasheets | **20 pass, 0 fail**: 5.00-5.33 V rail; 95.8 % at 5 A; buck 68 C, switch 82 C at its limit (with 0.12 W of output clamp at the rail's highest corner); 4.81 V at a port at 1.5 A worst case; +-52 mA at 1.5 A |
| `port_events.py` (ngspice): all five ports switched on together into real loads; then one port shorted while the others run | "never browns out" | **3 pass**: rail dips to 5.13 V at switch-on; the short pulls the other ports to 4.77 V for 2 us, then they hold 5.05 V |

## Independent design review (17 Oct 2026)

A second reviewer went through `src/circuit.py`, the parts, the footprints
and the firmware against the datasheets. Every IC's pins, every resistor
value (VSET, ISET, feedback, ILIM, dividers) and the ESP32-S3 pin use
checked out. What it found, and what was done:

| Finding | Done |
|---|---|
| Ports set to come on at power-up came on with no charger or a 5 V one; ports stayed on when the charger was unplugged; a saved budget override applied to any charger | firmware: no 9 V supply, no ports (all off as "no_power", the power-up ones queued again when it returns); override only on top of a 9 V supply, 5 A at most; host tests added |
| The buck's switch node left the chip through a 0.4 mm, 2.9 mm track | a pour instead: the whole gap between the ground pads (about 0.45 mm, 1.3 mm long), then full width to the inductor |
| Software current limit up to 1.8 A, over the USB-A receptacle's 1.5 A | capped at 1.5 A |
| Firmware update over Wi-Fi would trip the 8 s watchdog | the watchdog is fed during the download |
| The rail's highest corner (5.33 V) is above the port switch's minimum output clamp (5.25 V) | harmless (the switch drops 0.08 V linearly, 0.12 W); now counted in `power_budget.py` |
| "USB-PD contract made" read from the wrong register field | read from PD_STATUS0's voltage field |
| No capacitor on the DATA port's VBUS | 10 uF added |
| Unsure, to check on the bench: the HUSB238 with its I2C pulled up while unpowered (DATA only); 21 uF on POWER IN against USB-C's 10 uF at attach | hardware rows below |

## Software

| Test | Why | Result |
|---|---|---|
| `make -C firmware/test`: port logic and command language on the host (ASan, UBSan) | timers, limits, shedding, budget, no ports without a 9 V supply (boot, unplug, re-plug), names, durations, millis() wrap | **87 checks pass** |
| `pio run` (Arduino core 3.3.12, pioarduino 55.03.312-1) | the firmware builds | pass: flash 38 %, RAM 17 % |
| `python3 host/test_printhub.py`: the CLI against a fake board | commands, JSON, tokens, quoting, exit codes | **7 pass** |

## Enclosure (`mechanical/enclosure/enclosure.py`)

| Check | Result |
|---|---|
| Fit: board, connectors, module, buttons, inductor inside the case with clearance; USB-A mouths within 0.5 mm of the outer face; screws clear of the antenna; walls 2 mm; printable without supports | **74 pass, 0 fail**; both STLs watertight |

## Hardware (to fill in from built boards)

| Test | How | Result |
|---|---|---|
| Rail voltage, no load and 5 A | meter at TP4 | not yet built |
| Each port's voltage at 0.5 / 1.5 A | USB load + meter | not yet built |
| Current reading against a USB meter, each port | `printhub status` | not yet built |
| Short on a port: others keep running, firmware shows "fault" | short a USB-A with a 1 ohm load or a shorting plug | not yet built |
| Chargers: 20 W, 30 W, 5 V-only | `printhub status` contract and budget | not yet built |
| Buck temperature at 5 A, case closed | thermocouple on L1 / U2 | not yet built |
| Wi-Fi range inside the case, beside the printer | RSSI in `status` | not yet built |
| DATA only: current through the I2C pull-ups into the unpowered HUSB238; then plug POWER IN and check it negotiates 9 V | meter, `printhub status` | not yet built |
| Plug-in with several chargers: no charger trips on the 21 uF input | plug in 10 times each | not yet built |
