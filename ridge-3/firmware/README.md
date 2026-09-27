# Firmware for the Cheap Drone stack v1

Everything here was built from source; the hashes below are of the files as
committed.  None of it has run on this hardware yet: see "Before the first
flight" in `../README.md`.

| File | What | Built from |
|---|---|---|
| `betaflight/betaflight_2025.12.5_STM32G47X_CHEAPDRONE_G473.hex` | Flight controller, **BMI270** gyro (the BOM part) | Betaflight `2025.12.5` (commit `7348054`) + `betaflight/configs/CHEAPDRONE_G473/config.h` |
| `betaflight/betaflight_2025.12.5_STM32G47X_CHEAPDRONE_G473_ICM.hex` | Flight controller, **ICM-42688-P** gyro (alternative part) | same, + `betaflight/configs/CHEAPDRONE_G473_ICM/config.h` |
| `am32/AM32_F051_BOOTLOADER_PA2_V19.hex` | ESC bootloader, all four ESC MCUs | AM32-bootloader `578ff29`, target `AM32_F051_BOOTLOADER_PA2` |
| `am32/AM32_FD6288_F051_2.21.hex` | ESC firmware, all four ESC MCUs | AM32 `55c9684` (v2.21), target `FD6288_F051` |
| `am32/at32f421/AM32_F421_BOOTLOADER_PA2_V19.hex` | ESC bootloader if the ESC is built with the AT32F421 (untested) | AM32-bootloader `578ff29`, target `AM32_F421_BOOTLOADER_PA2` |
| `am32/at32f421/AM32_CHEAPDRONE_F421_2.21.hex` | ESC firmware if the ESC is built with the AT32F421 (untested) | AM32 `55c9684` + `am32/at32f421/AM32_55c9684_CHEAPDRONE_F421_targets.patch`, target `CHEAPDRONE_F421` |

```
df975d226e8ea1c748748a4ab18f2a3538a10d50c202555711b840b9330a5728  betaflight/betaflight_2025.12.5_STM32G47X_CHEAPDRONE_G473.hex
cdd59c48c8d69981c2ffc7809f023ee943a335c165f2d448c3784b8e815e7606  betaflight/betaflight_2025.12.5_STM32G47X_CHEAPDRONE_G473_ICM.hex
b7e8835d78965d7b16dcca88c68eeee44573829877fd2b0721c79d16a199c087  am32/AM32_F051_BOOTLOADER_PA2_V19.hex
4ae86f626636288fb394579c1c7cbacf43b74e0ce64e66c240cfe5ba57366ceb  am32/AM32_FD6288_F051_2.21.hex
ce3f240e136c7ec8d041566a165b589b704accd05f25d52fa3ee062460219cba  am32/at32f421/AM32_F421_BOOTLOADER_PA2_V19.hex
537c4cd8fa66030c11ae22b9a0c5a3a2236620b336663243e409019a8a201e7e  am32/at32f421/AM32_CHEAPDRONE_F421_2.21.hex
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
| BMI270 | `..._CHEAPDRONE_G473.hex` | `CW270_DEG` | 3.2 kHz (denom 1) |
| ICM-42688-P | `..._CHEAPDRONE_G473_ICM.hex` | `CW0_DEG` | 4 kHz (8 kHz gyro, denom 2) |

Each image has only its own chip's driver.  The wrong image on a board finds
**no gyro** and refuses to arm.  It cannot fly with the axes 90 degrees off.

Stock Betaflight targets are not a substitute.  `TAKERG4AIO` (whose pin
map this board copies) has no BMI270 driver.  On an ICM board it would need
`align_board_yaw = 90`, not 0, because its chip alignment is fixed at CW270.

Both configs also fix these defaults for this board (see the top of
`config.h`):

- **Board alignment 0/0/0.** The gyro sits square with the board, and the
  front arrow on the silkscreen points forward.  TAKERG4AIO's default 45°
  board yaw is wrong here.
- **Receiver on UART2, CRSF.**
- **DShot300 with bidirectional DShot on.** This is what the AM32 ESC board
  expects.

The 16 MB blackbox flash may be a Winbond W25Q128 or a Puya PY25Q128HA
(JEDEC `85 20 18`).  Betaflight's `m25p16` driver knows both, so either one
works with both images.

### Flashing

1. Hold **BOOT** (right-rear edge of the FC) and plug in USB-C. The board
   comes up in DFU mode.
2. In Betaflight Configurator, open *Firmware Flasher*, click **Load Firmware
   [Local]**, pick the `.hex` for the gyro that is fitted, and flash with
   *Full chip erase* on.
3. Connect, then paste `betaflight/cli-setup.txt` into the CLI and `save`.
4. **Props off, in the Setup tab:** tilt the nose down, and the model must pitch
   nose down.  Tilt the right side down, and it must roll right.  Turn it
   clockwise seen from above, and it must yaw right.  With the board level, the
   accelerometer reads about 0, 0, +1 g.  If any of these is wrong, do not fly.

### Building it yourself

In a Betaflight 2025.12.5 checkout:

```
make arm_sdk_install
SOURCE_DATE_EPOCH=1790412014 make CONFIG=CHEAPDRONE_G473 \
  CONFIG_DIR=<this repo>/cheap-drone-stack/v1/firmware/betaflight CONFIG_REVISION_DEFINE=
# and CONFIG=CHEAPDRONE_G473_ICM for the ICM image
```

With that build date, and with no git revision stamped in, the build
reproduces the committed images bit for bit (Arm GNU 13.3.rel1, which is what
`make arm_sdk_install` fetches for 2025.12.5).

## ESC (AM32, four times)

The four STM32F051 on the ESC board come blank from the assembler. Each one
needs the AM32 bootloader once, over SWD. After that, all firmware updates
and settings go through the flight controller in the usual way.

**First flash, per ESC MCU (ST-Link V2 or a clone, about 5 minutes for all four):**

1. The battery must be **disconnected**. The ST-Link's 3.3 V powers the MCUs.
2. Wire the ST-Link: `GND` to the ESC's `GND` test pad, `3.3V` to `3V3`,
   `SWDIO` to `Dn`, and `SWCLK` to `Cn`, where *n* is the ESC being flashed.
   The pads are labelled on the silkscreen next to each ESC's MCU.
3. Run `am32/flash_esc.sh`. It uses OpenOCD and writes both the bootloader
   and the firmware. STM32CubeProgrammer commands are in the script's header
   if you prefer that tool.
4. Move `SWDIO`/`SWCLK` to the next pad pair and repeat for all four.

**Then, with the stack assembled and the battery on:**

1. Open <https://esc-configurator.com> in Chrome, connect to the flight
   controller (Betaflight passthrough), and click **Read settings**. All four
   ESCs should show *AM32 2.21, FD6288_F051*.
2. Set these on all four: *Motor KV* `3800`, *Motor poles* `12` (the XING2
   1404 is 9N12P; count the magnets in one bell to be sure), *Bi-directional DShot* **on**, *Low voltage cutoff*
   **off** (Betaflight does battery warnings).
3. Use Betaflight's *Motors* tab (props off!) to check the motor order and
   direction. Motor 1 is rear-right, 2 front-right, 3 rear-left, and 4
   front-left. Reverse any motor that spins the wrong way with the
   *Reversed* toggle in ESC-configurator, not by swapping wires (either
   works).

To build it yourself: AM32 releases are built with xPack GCC 10.3. These
images were built with Arm GNU 13.3, which needs `-Wno-array-bounds` for one
false positive in `main.c` (a pointer into the device-info flash block). The
code is unchanged. To get the official release build instead, flash the
bootloader here and then use ESC-configurator's *Flash* button, which
downloads the AM32 `FD6288_F051` release.

```
# bootloader (repo am32-firmware/AM32-bootloader)
make ARM_SDK_PREFIX=<gcc>/bin/arm-none-eabi- AM32_F051_BOOTLOADER_PA2
# firmware (repo am32-firmware/AM32)
make ARM_SDK_PREFIX=<gcc>/bin/arm-none-eabi- FD6288_F051 \
  CFLAGS_BASE="-fsingle-precision-constant -fomit-frame-pointer -ffast-math -IInc -g3 -O3 \
  -ffunction-sections --specs=nosys.specs -Wall -Wundef -Wextra -Werror \
  -Wno-unused-parameter -Wno-stringop-truncation -Wno-array-bounds"
```

### Why `FD6288_F051`

The ESC schematic (`src/circuit.py`, `esc()`) is wired to AM32's hardware group
`F0_A`:

- **Input:** PA2 (TIM15).
- **High-side gates:** PA10, PA9 and PA8. **Low-side gates:** PB1, PB0 and PA7.
- **Comparator inputs:** PA5, PA4 and PA0 for the three phases, with the
  virtual neutral on PA1.
- **Battery voltage:** PA3, through an 11k/2k divider, which is AM32's
  `TARGET_VOLTAGE_DIVIDER 65`.

`FD6288_F051` is the stock AM32 target for that group with an FD6288-type
driver. The JSM6288Q on this board is a pin-for-pin FD6288Q.

### If the ESC is built with the Artery AT32F421 (bulk option, untested)

The BOM fits the STM32F051K6U6.  For volume, the Artery **AT32F421K8U7** is
the usual cheaper drop-in.  Order exactly that part (QFN32 **5 x 5 mm**); the
`AT32F421K8U7-4` is the 4 x 4 mm package and does not fit.  Every pin this
ESC uses has the same number and function on both chips (AT32F421 datasheet
V2.03, Table 5, against the STM32F051 datasheet).  AM32 supports the AT32F421,
so no board change is needed.  What changes is the firmware and the programmer:

- **Firmware:** `am32/at32f421/`.  This is AM32 2.21 with one added target,
  `CHEAPDRONE_F421` (the patch is next to the images).  It uses the same pins
  and voltage divider as `FD6288_F051`, and the dead time is rescaled for the
  AT32's 120 MHz timer (113 counts = 942 ns, against 45 counts = 938 ns on the
  F051).  No stock AM32 release has these exact settings.  `XROTOR45_F421`
  has the same pins but a shorter dead time (667 ns) and the wrong
  voltage scale.
- **Programmer:** plain OpenOCD 0.12.0 (apt/brew) and STM32CubeProgrammer
  cannot write an AT32.  `am32/at32f421/flash_esc_at32.sh` needs an OpenOCD
  with the upstream `artery` driver, such as xPack OpenOCD v0.12.0-7 or later.
  Artery's own AT-Link with ICP Programmer, or Keil with the Artery pack, also
  work.  The wiring is the same as above.
- **ESC-configurator** will show `CHEAPDRONE_F421`.  Update it from the local
  file, not the online *Flash* button.

**None of this has been run on an AT32 yet.** Before switching a production
run, build one ESC with AT32s: flash it with the script, scope the gate
drive to confirm the dead time, and spin all four motors on a current-limited
supply.
