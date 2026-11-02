# Firmware for the Ridge 3 Lite v1

Both halves run stock, unmodified firmware:

* **Flight controller** (STM32G473CEU6): Betaflight, target **TAKERG4AIO** (GEPR), pin for pin.
* **ESCs** (4 x STM32G071GBU6): AM32, target **GEN_64K_G071**, bootloader **G071 PB4 64K**.

All paths below are relative to the board folder (the one holding `firmware/`).

**Power on USB alone.**  USB-C 5 V feeds the 5 V rail, and from it both 3.3 V LDOs: the flight
controller and all four ESC MCUs (and the receiver) run with no battery.  Flashing Betaflight, the
SWD flash of the ESCs and ESC-configurator all work on USB.  The motors cannot spin on USB: the
gate-drive supply comes only from the battery, so the ESCs can be configured but not driven.

**No blackbox flash.**  Ridge 3 Lite has no on-board flash chip (TAKERG4AIO's SPI2 flash pins
PB13/PB14/PB15/PC6 are unconnected).  For blackbox logs fit an external serial logger such as an
OpenLager on pads T1/R1 (UART1); the lines are in `firmware/betaflight/cli-setup.txt`.  Stock
TAKERG4AIO still works as-is: it probes SPI2, finds no flash and simply logs nothing (it also finds
no OSD chip, barometer or compass, none of which are fitted).

```
firmware/
  README.md                       this file
  gyro-orientation.md             why the IMU sits at 135 deg, and what alignment to expect
  gyro_orientation_check.py       independent check of that (ports Betaflight's alignment math)
  betaflight/
    betaflight_2026.6.2_STM32G474_TAKERG4AIO.hex   stock target, built locally
    betaflight_2026.6.2_STM32G474_RIDGE3LITE.hex   this board's own config (board alignment 0)
    RIDGE3LITE/config.h                            that config
    cli-setup.txt                                  CLI lines to paste after flashing
  am32/
    AM32_G071_BOOTLOADER_PB4_64K_V19.hex           official AM32 bootloader v19
    AM32_GEN_64K_G071_2.21.hex                     official AM32 v2.21 firmware
    flash_esc.sh                                   one-time SWD flash, ESC 1..4
    esc-settings.md                                settings for XING2 1404 3800KV on 4S
```

## 1. Flight controller: Betaflight

**Primary path: Betaflight Configurator, cloud build.**  TAKERG4AIO is in betaflight/config and
the build server lists it with cloud builds for 2026.6.2, 2026.6.1 and 2025.12.x
(`https://build.betaflight.com/api/targets/TAKERG4AIO`, checked 2 Oct 2026).

1. Hold the **BOOT** button and plug in USB-C (no battery needed); the board enumerates as
   "STM32 BOOTLOADER" (DFU).  Release the button.
2. Configurator > Firmware Flasher: board **TAKERG4AIO**, latest stable (2026.6.2).  In the build
   options make sure the radio protocol includes **CRSF** (ELRS/Crossfire) and telemetry CRSF.
   Tick "Full chip erase", Load Firmware [Online], Flash.
3. Connect, CLI tab, paste `firmware/betaflight/cli-setup.txt`, `save`.
4. Setup tab, props off: roll right, nose up, turn clockwise; the 3D model must follow.  Board
   alignment shows **yaw 45: that is correct for this board** (see `firmware/gyro-orientation.md`).

**Offline / local files:** the same DFU steps with "Load Firmware [Local]" and one of:

* `betaflight_2026.6.2_STM32G474_TAKERG4AIO.hex`: the stock target built from the tag below with the
  full default feature set (CRSF included).  Then paste `firmware/betaflight/cli-setup.txt`.
* `betaflight_2026.6.2_STM32G474_RIDGE3LITE.hex`: this board's own config
  (`firmware/betaflight/RIDGE3LITE/config.h`, BOARD_NAME RIDGE3LITE, MANUFACTURER_ID OFFG: a copy of
  TAKERG4AIO trimmed to the parts fitted).  Defaults already set: ICM-42688-P only, sensor
  alignment custom yaw 315 with **board alignment 0/0/0**, CRSF on UART2, DShot600 with
  bidirectional DShot on, no flash / blackbox device NONE, no OSD/baro/mag, vbat_scale 110,
  ibata_scale 120.  Then paste cli-setup.txt **without its three align_board_* lines**.  (Not on the build server: it is not in
  betaflight/config, so Configurator's cloud build cannot make it.)

Never mix the two: settings saved under TAKERG4AIO (board yaw 45) on top of RIDGE3LITE's custom
gyro alignment would rotate attitude 45 deg.  Use "Full chip erase" when switching.

## 2. ESCs: AM32, once over SWD, then ESC-configurator

The G071s arrive blank.  Each needs the AM32 bootloader once over SWD; after that everything
(firmware and settings) goes over the motor signal wire from the flight controller.

1. Board on **USB power only** (no battery needed): USB 5 V feeds the ESC 3.3 V LDO, so all four
   ESC MCUs run.  ST-Link V2 GND to **TP_GND**.
2. `firmware/am32/flash_esc.sh` (openocd; `--tool st-flash` for stlink-tools).  It prompts for ESC 1..4:
   move **SWDIO to TP_Dn** and **SWCLK to TP_Cn**, press Enter.  Default writes only the bootloader
   at 0x08000000 (4 KB); `--with-app` also writes the firmware at 0x08001000; `--erase` mass-erases
   first (re-flashing a used chip).
3. Flash Betaflight (section 1).  Open https://esc-configurator.com (Chrome/Edge), Connect to the
   flight controller's port, "Read setup": it talks to the four ESC bootloaders through Betaflight's
   passthrough.  "Flash all" with **GEN_64K_G071** (Configurator's list), latest release (v2.21).
   USB power is enough (the bootloaders only need the 3.3 V rail); a battery is needed only to
   test-spin motors afterwards.
4. Apply `firmware/am32/esc-settings.md`, "Write setup".

**Why bootloader-only over SWD is the recommended route.**  AM32 is laid out as bootloader
0x08000000-0x08000FFF, application from 0x08001000 (`APPLICATION_ADDRESS`), and a 2 KB settings page
at 0x0800F800 (`EEPROM_START_ADD`, 64K layout).  The two hex files do not overlap (bootloader
0x08000000-0x08000FFB, app 0x08001000-0x0800F7FF including the "GEN_64K_G071" tag at 0x0800F7E0), so
writing both over SWD is valid; but neither contains the settings page, and a blank (0xFF) page gives
the firmware nonsense values (e.g. KV 10220) until ESC-configurator writes real settings.  Flashing
the app through ESC-configurator writes the firmware and the settings together, and is also how every
later update is done.  If you do use `--with-app`, write the settings in ESC-configurator before
the first arm.

## 3. What was verified (2 Oct 2026)

| Source | Revision |
|---|---|
| betaflight/config, `configs/GEPR/TAKERG4AIO/config.h` | master `15d8c3fa076e9f43e2135050c90265f7f3e92166` (identical to the copy in out/up) |
| betaflight/betaflight (build + alignment/timer/DMA/CLI source) | tag **2026.6.2**, `e0b7bb01b17b21351057e9ead2d1ab39dd44fa16` (latest stable; 2025.12.5 is `7348054f`) |
| arm-none-eabi-gcc | Arm GNU Toolchain 13.3.rel1 (the version Betaflight's mk/tools.mk requires) |
| libcanard (Betaflight submodule) | `601ed35467e0ac38819df17cd7c918de19f62d58` |
| am32-firmware/AM32 (`Inc/targets.h`, `Mcu/g071/Src/*.c`, `Src/main.c`) | main `2738df3240baa5bd4295b460cf0c5cfe0bd49d97` (VERSION 2.21; identical to out/up copies) |
| AM32 release | **v2.21**, https://github.com/am32-firmware/AM32/releases/download/v2.21/AM32_GEN_64K_G071_2.21.hex |
| AM32 bootloader release | **v19.0.0**, https://github.com/am32-firmware/AM32-bootloader/releases/download/v19.0.0/AM32_G071_BOOTLOADER_PB4_64K_V19.hex |
| ST LL COMP header (COMP2 IO mapping) | STMicroelectronics/stm32g0xx_hal_driver master, `Inc/stm32g0xx_ll_comp.h` |

Pin maps checked: every TAKERG4AIO pin used on this board against the UFQFPN-48 pin numbers of
KiCad's `STM32G473C_B-C-E_Ux` symbol and LCSC's STM32G473CEU6 symbol (they agree); every AM32 G0_A
pin and GEN_64K_G071 default against DS12232's "GP" UFQFPN-28 pinout and LCSC's STM32G071GBU6
symbol.  No mismatches.  Motor timers PA0/PA1 = TIM2 CH1/CH2, PA2/PA3 = TIM5 CH3/CH4 (occurrence 2),
DMA opt 1-4 = DMA1 channels 2-5, LED strip PB6 = TIM8 CH1 on DMA2 channel 2, ADC on DMA2 channels 3
and 4: no clashes, no N-channels, so bidirectional DShot is allowed in both bit-bang and timer mode.

## 4. SHA-256 (paths relative to `firmware/`)

```
fc66d976207412fbd75e4b3e087a355720bd4e359fd174117c893684e0df284a  betaflight/betaflight_2026.6.2_STM32G474_TAKERG4AIO.hex
1bad11995c05187992ba51bf41f2e0686d2270f56aa497a05865f1df50c6e0d3  betaflight/betaflight_2026.6.2_STM32G474_RIDGE3LITE.hex
483f605d9601fa56b01ff1a27ed614d6514474c25498c9db73e566bbac5e00cf  betaflight/RIDGE3LITE/config.h
780a052748cd7214bca96f93b506b068f5e426b7fb18db836cee1ec56f113e48  am32/AM32_G071_BOOTLOADER_PB4_64K_V19.hex
a6f3765c077c14f2ab25e84f38b249c5edc9bbc95fda5955d58448e1e1185200  am32/AM32_GEN_64K_G071_2.21.hex
```

The AM32 files are the release assets byte for byte.  The Betaflight hexes were built with
`make CONFIG=<name> REVISION=e0b7bb01b` from the release tarball inside the ogkicad:10 container; a
build from a tarball embeds the given revision string, so a cloud build of the same target will not
be byte-identical (it differs in build options and date), only functionally equivalent.
