# Firmware for the Cheap Drone stack v1

Everything here was built from source in this repo's toolchain setup; the
hashes below are of the files as committed.

| File | What | Built from |
|---|---|---|
| `betaflight/betaflight_2025.12.5_STM32G47X_CHEAPDRONE_G473.hex` | Flight controller | Betaflight `2025.12.5` (commit `7348054`) + `betaflight/configs/CHEAPDRONE_G473/config.h` |
| `am32/AM32_F051_BOOTLOADER_PA2_V19.hex` | ESC bootloader, all four ESC MCUs | AM32-bootloader `578ff29`, target `AM32_F051_BOOTLOADER_PA2` |
| `am32/AM32_FD6288_F051_2.21.hex` | ESC firmware, all four ESC MCUs | AM32 `55c9684` (v2.21), target `FD6288_F051` |

```
e0b644e91eed04d96b2685ea03a1e7475ba1515f13c78ad5a63f53a4ba6d7e61  betaflight/betaflight_2025.12.5_STM32G47X_CHEAPDRONE_G473.hex
b7e8835d78965d7b16dcca88c68eeee44573829877fd2b0721c79d16a199c087  am32/AM32_F051_BOOTLOADER_PA2_V19.hex
4ae86f626636288fb394579c1c7cbacf43b74e0ce64e66c240cfe5ba57366ceb  am32/AM32_FD6288_F051_2.21.hex
```

## Flight controller (Betaflight)

The board's pin map is the GEPRC TAKER G4 AIO's (Betaflight target
`GEPR/TAKERG4AIO`), which Phase 1 flew. Stock TAKERG4AIO firmware runs this
board as well. Use the `CHEAPDRONE_G473` build here anyway, because it
fixes three defaults for this hardware (see the top of `config.h`):

- **Board alignment.** The gyro is mounted square with the board, so the
  default alignment is right. TAKERG4AIO's default 45° yaw is wrong on this
  board.
- **Receiver on UART2, CRSF.**
- **DShot300 with bidirectional DShot on.** This is what the AM32 ESC board
  expects.

Flashing:

1. Hold **BOOT** (right-rear edge of the FC) and plug in USB-C. The board
   comes up in DFU mode.
2. In Betaflight Configurator, open *Firmware Flasher*, click **Load Firmware
   [Local]**, pick the `.hex`, and flash with *Full chip erase* on.
3. Connect, then paste `betaflight/cli-setup.txt` into the CLI and `save`.

To build it yourself, in a Betaflight 2025.12.5 checkout:

```
make arm_sdk_install
make CONFIG=CHEAPDRONE_G473 CONFIG_DIR=<this repo>/cheap-drone-stack/v1/firmware/betaflight
```

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
