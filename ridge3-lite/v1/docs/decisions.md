# Ridge 3 Lite v1: decisions and trade-offs

What we chose, what it cost, and why. Numbers are from this board's own
checks and simulations (README, `sim/`).

| Decision | Why | Cost |
|---|---|---|
| **One board: flight controller + 4-in-1 ESC** | Smallest and cheapest for a 3" quad; one part to fit | A fault in either half means replacing the whole board |
| **No FPV parts** (no OSD, video, camera) | Phase 1 does not fly FPV | Needs another board to add video |
| **Stock firmware: Betaflight TAKERG4AIO, AM32 GEN_64K_G071** | Flash and fly; the pin maps match the stock targets exactly | Pins fixed by those targets |
| **One MCU per ESC (STM32G071, AM32)** | Each motor limits its own current and temperature | Four extra MCUs to flash once over SWD |
| **Per-motor current shunt + amplifier** | Per-motor current limit, the stated requirement | Board area and heat by each channel |
| **40 V FETs (TPN2R304PL)** | Low loss, 175 °C rating | Limits the battery to 2–4S |
| **Slow gate drive (22 Ω high side / 10 Ω low side)** | Simulated spikes stay under the FETs' 40 V | More switching loss: +0.15 W per motor at 24 kHz, +0.29 W at 48 kHz (15 A) |
| **38 × 38 mm** (35 asked) | 35 mm could not be routed; 40 mm would not help (the crowding is round the centre) | 3 mm larger than the old board; same 25.5 mm mount |
| **8 layers, 0.09 mm track and gap, vias down to 0.37 / 0.15 mm** | Needed to route 260 parts at this size | Fab's pricier fine-line and small-via tiers |
| **1 oz copper on every layer** | 2 oz inner layers cannot carry 0.09 mm tracks | Less copper for heat than 2 oz |
| **Battery supply on In3, In4 and In6** (leftover copper flooded with the supply net) | The single supply plane overheated by the battery pad; this took 10 °C off the hottest FET | Those layers' leftover copper is no longer ground |
| **Heat handled by the ESC's own 100 °C limit**, no heat sink | Normal flying stays cool; on a 50 °C day in sun the ESC throttles back before damage | Sustained full throttle in desert sun is throttled |
| **Bulk capacitor fitted by hand** at the battery pads (`docs/bulk-capacitor.md`) | A through-hole electrolytic soldered with the battery lead; required to keep ripple and hot-plug spikes in limits | One manual step per board |
| **No blackbox flash** | Space and cost | Logging needs an external logger on UART1 |
| **Silk-only (subdued) flag; small logo in a corner** | No ground-only copper was left after routing for the gold flag | Plainer than the gold flag; reserve the space at placement next time |
| **Routed board file is the design of record** | The router left one connection, finished by hand | `make.py --reroute` is a starting point for v2, not a rebuild of v1 |

## Known limits (also in the README)

2–4S only · keep the battery connected while the motors spin · per-motor
current limit 26 A or lower · the bulk capacitor must be fitted · the gyro
runs warm in direct desert sun (a canopy fixes it).

## Ideas for a v2

- Reserve a ground-only area for the gold flag during placement.
- Place the battery pads so the current reaches all four channels evenly
  (channel 1, next to the pads, runs hottest).
- Add a canopy or top plate to the frame design to keep sun off the board.
