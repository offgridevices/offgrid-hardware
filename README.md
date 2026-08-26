# offgrid-hardware

Open hardware from [OffGrid Devices](https://github.com/offgridevices). One folder per board.

| Board | What it is | Status |
|---|---|---|
| [`packet-logger-carrier/`](packet-logger-carrier/) | 86 × 58 mm carrier for a LoRa mesh packet logger — RAK19003 + XIAO ESP32-C6 + microSD | v1 ordered, not yet bench-verified |

The firmware and analysis tooling these boards run with live in
[`mesh-fieldlab`](https://github.com/offgridevices/mesh-fieldlab).

---

## How to build one

Every board folder is self-contained and follows the same layout. To get a
board made, you need two things from it:

1. **`*-gerbers.zip`** — upload this to any fab (JLCPCB, PCBWay, OSH Park).
2. **`bom.csv`** — what to buy.

The board's own `README.md` has the fab settings to select, the assembly
order, and the bench sequence that proves it works. Start there, not here.

You do **not** need KiCad, Python, or any of this repository's tooling to
order a board. The manufacturing files are committed, ready to upload.

## How to change one

The design files are the **Python scripts in each board's `src/`**, not the
Gerbers. Nobody modifies a board by hand-editing Gerbers, so the scripts are
what this project publishes as its source — in the words of the open hardware
definition, the preferred format for making modifications.

Each board is generated end to end: placement, routing, copper pours,
silkscreen, Gerbers, drill files and a 3D model, with verification gates that
fail the build rather than warn. One command rebuilds everything:

```bash
cd <board>/src && python3 make.py
```

If it finishes, every check passed. If a check fails, it stops.

## Layout

```
<board-name>/
  README.md          what it is, how to order it, how to build it
  bom.csv            what to buy
  *-gerbers.zip      upload this to a fab
  *.kicad_pcb        open in KiCad to look around
  netlist.csv        every pad, its net and its position
  mechanical/        STEP models for enclosure design
  src/               the generator and its verification scripts
```

Generated outputs are committed alongside the scripts that produce them, so a
stranger can order a board without a toolchain. They are expected to agree: a
script change without regenerated outputs is a defect, not untidiness.

---

## Licence

**[CERN-OHL-S v2](LICENSE)** — the strongly reciprocal CERN Open Hardware
Licence. Use it, build it, sell it, modify it. If you distribute a modified
board, publish your design files under the same terms.

Copyright © OffGrid Devices.

A note on why this differs from `mesh-fieldlab`, which is GPL-3.0: that
licence is inherited from the Meshtastic libraries the firmware and tooling
depend on. A PCB has no such dependency, and GPL's language — source code,
object code, installation information — does not map cleanly onto Gerbers and
drill files. CERN-OHL-S is written for hardware and carries the same
reciprocal intent.
