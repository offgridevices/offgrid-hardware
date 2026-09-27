# Firmware for the Ridge 3 stack

Everything here was built from source; the hashes below are of the files as
committed.  None of it has run on this hardware yet: see "Bring-up" in
`../README.md`.

| File | What | Built from |
|---|---|---|
| `betaflight/betaflight_2025.12.5_STM32G47X_RIDGE3.hex` | Flight controller, **BMI270** gyro (the BOM part) | Betaflight `2025.12.5` (commit `7348054`) + `betaflight/configs/RIDGE3/config.h` |
| `betaflight/betaflight_2025.12.5_STM32G47X_RIDGE3_ICM.hex` | Flight controller, **ICM-42688-P** gyro (alternative part) | same, + `betaflight/configs/RIDGE3_ICM/config.h` |
| `am32/AM32_G071_BOOTLOADER_PB4_64K_V19.hex` | ESC bootloader, all four ESC MCUs | AM32-bootloader `578ff29`, target `AM32_G071_BOOTLOADER_PB4_64K` |
| `am32/AM32_RIDGE3_G071_2.21.hex` | ESC firmware, all four ESC MCUs | AM32 `55c9684` (v2.21) + `am32/AM32_55c9684_RIDGE3_G071_targets.patch`, target `RIDGE3_G071` |
| `am32/flash_esc.sh` | Writes both to each ESC MCU over SWD, plus the option bytes | – |

```
a3e75f033409a6429b14e49da10283c96fbad3a13b3cfb50ad5082bf2e18e724  betaflight/betaflight_2025.12.5_STM32G47X_RIDGE3.hex
55debb36b1cd24b0856424306d606517e0c45fc48902e83a6ff8f65d415b6bc7  betaflight/betaflight_2025.12.5_STM32G47X_RIDGE3_ICM.hex
05f7109c5f5a0a8a8d4505e311b99599b6ca6ac7f5ea8e8c83c47c1089423f2d  am32/AM32_G071_BOOTLOADER_PB4_64K_V19.hex
5d6558599c7e5e22c4787e2f06c030cc602f5667bf2db5540bfa4fc32d170087  am32/AM32_RIDGE3_G071_2.21.hex
ff237ad28e60315feec38c1327ab1ec172fb0ebea7ce1a89433fa89451f2a6da  am32/AM32_55c9684_RIDGE3_G071_targets.patch
```

## Flight controller (Betaflight)

### Which image

The gyro pads take either a Bosch **BMI270** (the BOM part: cheaper, and
stocked in the tens of thousands) or a TDK **ICM-42688-P**.  The two chips
have the same pinout, but not the same axes: relative to pin 1, the BMI270's
axes are the ICM's turned 90 degrees (BMI270 datasheet BST-BMI270-DS000-08
sec. 8.2, p.144; ICM-42688-P DS-000347 fig. 15, p.53).  Betaflight 2025.12
applies one alignment whichever chip it finds, and that alignment cannot be
changed from the CLI.  So there is one image per chip:

| Gyro fitted (read the marking, or the assembly order) | Flash | `GYRO_1_ALIGN` | PID loop |
|---|---|---|---|
| BMI270 | `..._RIDGE3.hex` | `CW270_DEG` | 3.2 kHz (denom 1) |
| ICM-42688-P | `..._RIDGE3_ICM.hex` | `CW0_DEG` | 4 kHz (8 kHz gyro, denom 2) |

Each image has only its own chip's driver.  The wrong image on a board finds
**no gyro** and refuses to arm.  It cannot fly with the axes 90 degrees off.

Stock Betaflight targets are not a substitute.  `TAKERG4AIO` (whose pin
map this board copies) has no BMI270 driver.  On an ICM board it would need
`align_board_yaw = 90`, not 0, because its chip alignment is fixed at CW270.

Both configs also set these defaults for this board (see the top of
`config.h`):

- **Board alignment 0/0/0.** The gyro sits square with the board, and the
  front arrow on the silkscreen points forward.  TAKERG4AIO's default 45°
  board yaw is wrong here.
- **Receiver on UART2, CRSF.**  UART4 is spare (GPS).  LPUART1 RX (PB11) is
  on the stack lead's TLM pin, which this stack's ESC does not drive.
- **DShot300 with bidirectional DShot on.** This is what the AM32 ESC board
  expects.
- **Video.**  The AT7456E analog OSD is on SPI2 (shared with the blackbox
  flash), chip select PA8 (`USE_MAX7456`; Betaflight tells the AT7456E from a
  MAX7456 itself).  The HD VTX connector is UART1, which defaults to
  *VTX (MSP + DisplayPort)* (`MSP_DISPLAYPORT_UART`).  No camera-control pin.
- **VTX power switch.**  PINIO1 on PB5, driving the N-FET that pulls the
  9 V regulator's enable low: PB5 high = VTX off.  PINIO1 is a plain
  output tied to the USER1 mode (`PINIO1_BOX 40`), so it is low, and the
  VTX **on**, at boot and until a USER1 switch turns it off.
- **Battery.**  Voltage from the 30k/2k divider: `vbat_scale` 160 (2S-6S).
  Current from the ESC's CUR output, the average of its four 50 mV/A
  channel sensors, i.e. 12.5 mV per amp of battery current: `ibata_scale`
  125 (Betaflight's unit is mV per 10 A), offset 0, meter source ADC.  The
  FC's 100k pull-down on CUR loads the ESC's averaging resistors (2.5 kΩ
  together), so the reading comes out about 2.4 % low; 122 would be exact
  with today's circuit (`VERIFICATION.md`, *Firmware scales*).

The 16 MB blackbox flash is a Winbond W25Q128JV (-IM, JEDEC `EF 70 18`, or
-IQ, `EF 40 18`).  Betaflight's `m25p16` driver knows both (and the Puya
PY25Q128HA, `85 20 18`).

### Flashing

1. Hold **BOOT** (right-rear edge of the FC) and plug in USB-C. The board
   comes up in DFU mode.
2. In Betaflight Configurator, open *Firmware Flasher*, click **Load Firmware
   [Local]**, pick the `.hex` for the gyro that is fitted, and flash with
   *Full chip erase* on.
3. Connect, then paste `betaflight/cli-setup.txt` into the CLI and `save`.
   It has two video blocks: keep the HD block for a DJI, Walksnail or HDZero
   system (`vcd_video_system = HD`, without which the OSD goes to the analog
   chip), or swap to the analog block.  Assign the USER1 mode (named
   `VTX_OFF`) to a switch if you want to turn the VTX off from the radio.
4. **Props off, in the Setup tab:** tilt the nose down, and the model must pitch
   nose down.  Tilt the right side down, and it must roll right.  Turn it
   clockwise seen from above, and it must yaw right.  With the board level, the
   accelerometer reads about 0, 0, +1 g.  If any of these is wrong, do not fly.

### Building it yourself

In a Betaflight 2025.12.5 checkout:

```
make arm_sdk_install
SOURCE_DATE_EPOCH=1790412014 make CONFIG=RIDGE3 \
  CONFIG_DIR=<this repo>/ridge-3/firmware/betaflight CONFIG_REVISION_DEFINE=
# and CONFIG=RIDGE3_ICM for the ICM image
```

With that build date, and with no git revision stamped in, the build
reproduces the committed images bit for bit (Arm GNU 13.3.rel1, which is what
`make arm_sdk_install` fetches for 2025.12.5).  The defaults above were read
back out of the built ELF files, not only from `config.h`.

## ESC (AM32, four times)

The four STM32G071 on the ESC board (G071GBU6, 128 KB, or G071G8U6, 64 KB:
same die and pads, and the same images) come blank from the assembler.  Each
one needs the AM32 bootloader and firmware once, over SWD.  After that, all
firmware updates and settings go through the flight controller in the usual
way.

**First flash (ST-Link V2 or a clone; a few minutes for all four):**

1. Flash the ESC while it is bare: **no battery**, no capacitors on the
   battery pads, not stacked.  The ST-Link's 3.3 V powers the four MCUs and
   the current amplifiers.
2. Wire the ST-Link to the pads on the ESC's top (the side that faces the
   flight controller): `GND` to `GND`, `3.3V` to `3V3`, `SWCLK` to `CLK`
   (one pad, shared by all four MCUs), and `SWDIO` to `Dn`, where *n* is the
   ESC being flashed.  `3V3`, `CLK`, `D1` and `GND` sit in a row along the
   rear edge, between the battery pads; `D2`, `D3` and `D4` are at the
   right, left and front edges, each beside its motor's pads.  NRST is not on a pad;
   resets are software resets.  An MCU whose SWDIO pad is not connected
   sees only ones on its SWDIO line, which is never a valid SWD request, so
   it ignores the shared clock.
3. Run `am32/flash_esc.sh`.  It asks for each ESC in turn (move `SWDIO` to
   `D1`, `D2`, ...), or takes the numbers to flash as
   arguments (`./flash_esc.sh 3`).  It uses OpenOCD (`target/stm32g0x.cfg`);
   `TOOL=cubeprog ./flash_esc.sh` uses STM32CubeProgrammer instead.  For each
   MCU it:
   - mass-erases the flash;
   - writes and reads back the bootloader (at `0x08000000`) and the firmware
     (at `0x08001000`);
   - **checks the option bytes**.  On this 28-pin package PA14 is both SWCLK
     and BOOT0.  The G0 boots from its flash, whatever that pin does, when
     `nBOOT_SEL = 1` (BOOT0 comes from the option bit, not the pin) and
     `nBOOT0 = 1`.  ST ships parts that way; the script writes the two bits
     only if a part arrives otherwise, then reloads the option bytes;
   - clears `FLASH_ACR.EMPTY`.  A G0 decides at power-on whether its flash is
     blank, and if so starts ST's ROM bootloader, not the flash.  Right after
     programming a blank part that flag is still set, so without this a
     reset would not start AM32 (a power cycle also clears it).

   With STM32CubeProgrammer, power-cycle the board after flashing for the
   same reason.

**Then, with the stack assembled and the battery on:**

1. Open the AM32 Configurator (<https://am32.ca>, AM32's own tool) in Chrome,
   connect to the flight controller (Betaflight passthrough) and read the
   ESCs.  All four should show AM32 2.21 with the target name `RIDGE3_G071`.
2. **Click "Send default config" before anything spins.**  An MCU flashed
   over SWD starts with an erased settings page.  On its first boot AM32
   writes only its version bytes there, and reads the other erased bytes
   (0xFF) as *on*: 3D mode, car-type reversing and stall boost among them.
   The configurator fills in defaults by itself only when the page is
   entirely blank, which it no longer is by then.
3. Set these on all four, then **Save config**:

   | AM32 Configurator setting | Value | Why |
   |---|---|---|
   | *Motor KV*, *Motor poles* | your motor (XING2 1404: 3800, 12) | RPM telemetry |
   | *3D mode* | **off** | Bidirectional DShot needs no ESC setting: AM32 detects the inverted DShot signal itself.  This switch is 3D flight |
   | *Car type reverse braking* | off | A car mode |
   | *30ms interval telemetry* | off | The TLM line is not wired on this ESC |
   | *Stuck rotor protection* | **on** (the default) | Cuts a motor whose back-EMF disappears: a stalled or jammed rotor |
   | *Stall protection* | off (the default) | A crawler feature that *adds* power at stall; AM32 says not for multirotors |
   | *Limits* → *Low voltage cut off* | Off | Betaflight does battery warnings |
   | *Limits* → *Temperature limit* | **110** °C | See below.  70-140; the slider's end (141) is off, the default |
   | *Limits* → *Current limit* | **20** A | See below.  2 A steps; the slider's end (202) is off, the default |

   esc-configurator.com also works (AM32 lists it as an alternative).  Its
   names differ: *Restore Default Settings*, *Forward/Reverse (3D mode)*,
   and *Temperature Limit* / *Current Limit [A]* under *Safety Settings*.
4. Use Betaflight's *Motors* tab (props off!) to check the motor order and
   direction. Motor 1 is rear-right, 2 front-right, 3 rear-left, and 4
   front-left. Reverse any motor that spins the wrong way with the
   *Reversed* switch in the configurator, not by swapping wires (either
   works).
5. Check the current reading: with the quad on a bench supply, Betaflight's
   current should match the supply's ammeter within a few percent (trim
   `ibata_scale` if not).  The same sensors feed AM32's current limit, so
   this also checks the limit.

**The limits.**  The ESC's current rating has not been measured.  The design
estimate is about 20 A per motor in bursts, and a sustained 9-12 A per motor
with airflow (5 A in still air) before the board passes 100 °C.

- *Current limit* acts on each motor's own battery-side current, averaged
  over 50 ms, through a PID loop that lowers the duty.  20 A caps punch-outs
  at the burst figure and still leaves the XING2 1404's 15.8 A.  It is not a
  thermal limit: a long full-throttle run under 20 A still overheats the
  board.  That is the temperature limit's job.
- *Temperature limit* uses each MCU's own die sensor, so it reads the
  board near that MCU, not the FETs themselves.  Above the limit AM32 cuts
  that motor's maximum duty to about a quarter, falling to zero 10 °C above
  it.  In the heat test of the bring-up, compare the hottest FET with the
  ESC temperature Betaflight shows (`dshot_edt`) and move the limit if the
  two differ by much.
- *Stuck rotor protection* works without current sensing.  A stalled motor
  at low throttle draws little battery current (the shunt sees duty ×
  phase current), so the current limit alone would not catch it.

### The target: `RIDGE3_G071`

The ESC schematic (`src/circuit.py`, `esc()`) is wired to AM32's hardware
group `G0_A`, the pin map of the stock `GEN_64K_G071` and `TBS_4IN1_G071`
targets.  Pin numbers are the STM32G071's UFQFPN28 "GP" pinout (DS12232,
table 12):

| Function | Port | QFN28 pin | Net (ESC *n*) |
|---|---|---|---|
| DShot input (TIM3_CH1; also the bootloader's pin) | PB4 | 24 | `Mn_SIG` |
| Phase A high / low (TIM1_CH3 / CH3N) | PA10 / PB1 | 19 / 15 | `Mn_HA` / `Mn_LA` |
| Phase B high / low (TIM1_CH2 / CH2N) | PA9 / PB0 | 18 / 14 | `Mn_HB` / `Mn_LB` |
| Phase C high / low (TIM1_CH1 / CH1N) | PA8 / PA7 | 16 / 13 | `Mn_HC` / `Mn_LC` |
| Back-EMF A / B / C (COMP2 −) | PB7 / PB3 / PA2 | 27 / 23 / 8 | `Mn_CMP_A` / `_B` / `_C` |
| Virtual neutral (COMP2 +) | PA3 | 9 | `Mn_NEUTRAL` |
| Current, 50 mV/A (ADC_IN5) | PA5 | 11 | `Mn_ISENSE` |
| Battery voltage, 100k/10k (ADC_IN6) | PA6 | 12 | `ESC_VSENSE` |
| SWDIO / SWCLK (BOOT0) | PA13 / PA14 | 20 / 21 | `Mn_SWDIO` / `ESC_SWCLK` (shared) |

Pins 18 and 19 are PA11 and PA12 until the firmware remaps them to PA9 and
PA10.  AM32's G071 code does that at start-up unless a target defines
`NO_PA11_PA12_REMAP`, which this one does not.  Until then (and in the
bootloader) the DRV8300's inputs sit on their internal pull-downs, so the
gates stay off.

`RIDGE3_G071` is `GEN_64K_G071` with this board's numbers
(`AM32_55c9684_RIDGE3_G071_targets.patch`):

- `MILLIVOLT_PER_AMP 50`, `CURRENT_OFFSET 0`: 0.5 mΩ shunt × INA180A3
  (100 V/V), 0 A = 0 V.  Stock is 20 mV/A.
- `TARGET_VOLTAGE_DIVIDER 110`: the 100k/10k divider (ratio 11), AM32's
  default.
- `DEAD_TIME 40`: 40 counts of TIM1's 64 MHz clock = 625 ns, on top of
  which the DRV8300 inserts its own ~215 ns (DT pin open; 150-280 ns).
  That is conservative for this driver and these FETs, yet shorter than
  stock `GEN_64K_G071`'s 60 (938 ns), which is safe but spends more time
  in body-diode conduction (about 0.4 W per motor more at 6S, 20 A,
  48 kHz, by the design's loss estimate).  Scope
  the gate drive on the first board before shortening it further.  (AM32
  also uses DEAD_TIME as its minimum duty.)
- No `USE_SERIAL_TELEMETRY`: the ESC's TLM line is not wired.  Bidirectional
  DShot carries eRPM, and, with `dshot_edt = ON` in Betaflight, the ESCs'
  temperature, voltage and current.
- `SIXTY_FOUR_KB_MEMORY`: settings at `0x0800F800`, so one image (and the
  `G071_64K` bootloader) runs on both the 64 KB and the 128 KB part.
- `FIRMWARE_NAME "OffGrid Rdg3"`: AM32 allows 12 characters, so not "OffGrid
  Ridge3".  Only DroneCAN builds use it; the configurators show `FILE_NAME`,
  `RIDGE3_G071`.

No official AM32 release is built for `RIDGE3_G071`, so the configurators'
online firmware lists have nothing for it; update from a local `.hex`.  The
stock `GEN_64K_G071` release would also run this board (same pins), but it
reads current 2.5 times too high (the limit trips early) and uses the longer
dead time.

### Building it yourself

AM32 releases are built with xPack GCC 10.3.  These images were built with
Arm GNU 13.3.rel1, which needs `-Wno-array-bounds` for one false positive in
`main.c` (a pointer into the device-info flash block).  The code is
unchanged.  Both builds reproduce the committed files bit for bit.

```
# bootloader (repo am32-firmware/AM32-bootloader, commit 578ff29)
make ARM_SDK_PREFIX=<gcc>/bin/arm-none-eabi- AM32_G071_BOOTLOADER_PB4_64K
# firmware (repo am32-firmware/AM32, commit 55c9684)
git apply <this repo>/ridge-3/firmware/am32/AM32_55c9684_RIDGE3_G071_targets.patch
make ARM_SDK_PREFIX=<gcc>/bin/arm-none-eabi- RIDGE3_G071 \
  CFLAGS_BASE="-fsingle-precision-constant -fomit-frame-pointer -ffast-math -IInc -g3 -O3 \
  -ffunction-sections --specs=nosys.specs -Wall -Wundef -Wextra -Werror \
  -Wno-unused-parameter -Wno-stringop-truncation -Wno-array-bounds"
```

### Not yet verified

- Nothing here has run on a G071 or on this ESC.  `flash_esc.sh`'s OpenOCD
  commands were run with the hardware commands stubbed out, against OpenOCD
  built from upstream `e5888bda`.  The STM32CubeProgrammer line (in
  particular the `-ob nBOOT_SEL=1 nBOOT0=1` names) was not run at all.
- `DEAD_TIME 40` against the DRV8300 and these FETs: scope it.
- The 50 mV/A and 12.5 mV/A current scales: check against a bench ammeter.
- The 110 °C / 20 A limits are design estimates, not measurements.
