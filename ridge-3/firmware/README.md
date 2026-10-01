# Firmware for the Ridge 3 stack (revision 2)

Everything here was built from source; the hashes below are of the files as
committed.  None of it has run on this hardware yet: see "Bring-up" in
`../README.md`.

| File | What | Built from |
|---|---|---|
| `betaflight/betaflight_2025.12.5_STM32G47X_RIDGE3.hex` | Flight controller (IIM-42652 gyro, or the ICM-42688-P on the same pads) | Betaflight `2025.12.5` (commit `7348054`) + `betaflight/patches/betaflight_2025.12.5_iim42652_scale_and_aaf.patch` + `betaflight/configs/RIDGE3/config.h` |
| `am32/AM32_F421_BOOTLOADER_PB4_V19.hex` | ESC bootloader, all four ESC MCUs | AM32-bootloader `578ff29`, target `AM32_F421_BOOTLOADER_PB4` |
| `am32/AM32_RIDGE3_F421_2.21.hex` | ESC firmware, all four ESC MCUs | AM32 `2738df3` (v2.21) + `am32/AM32_2738df3_RIDGE3_F421_target.patch`, target `RIDGE3_F421` |
| `am32/flash_esc.sh` | Writes both to each ESC MCU over SWD | – |

```
1de5aae29180c3d3ac26d998e678f2c5b2eb2b228632fc935901acc217ecd626  betaflight/betaflight_2025.12.5_STM32G47X_RIDGE3.hex
5265b0c388e604d380f7bb1b00cc2a2d96f47b65393e38532cca0b72dd8d3b6e  betaflight/patches/betaflight_2025.12.5_iim42652_scale_and_aaf.patch
c6ce4d235f18b0c3d6067ac1ec4c57ee7616ece91efe47e8495c0704731161df  am32/AM32_F421_BOOTLOADER_PB4_V19.hex
1af8ace717d2be0a5154513c691d63bcb82617c3ceb3ad67dbac40a67c80f12a  am32/AM32_RIDGE3_F421_2.21.hex
a9b4edaa27eebeba1e8915a2d6426e6a7cced42740a7d7ee9ba2c5b10a929f00  am32/AM32_2738df3_RIDGE3_F421_target.patch
```

## Flight controller (Betaflight)

### One image, two gyros

The gyro pads take a TDK **IIM-42652** (the BOM part: industrial,
-40..+105 °C) or its consumer sibling, the **ICM-42688-P** (85 °C).  The two
have the same pins and the same axes (IIM-42652 DS-000440 fig. 15), and
Betaflight's `icm426xx` driver reads both, so one image runs either:
`GYRO_1_ALIGN CW0_DEG`, an 8 kHz gyro and a 4 kHz PID loop (denom 2, what
bidirectional DShot300 allows).

**The image carries a fix to Betaflight.**  Betaflight 2025.12.5 detects the
IIM-42652 (WHO_AM_I `0x6F`) but treats it as its big brother, the IIM-42653:
it scales the gyro as ±4000 °/s and the accelerometer as ±32 g, and
programs its anti-alias filter from the ICM-42605's table.  The IIM-42652's
datasheet (DS-000440 tables 1-2 and section 5.3) gives ±2000 °/s at
16.4 LSB/(°/s), ±16 g at 2048 LSB/g, and the ICM-42688-P's filter table
(258 Hz = DELT 6, DELTSQR 36, BITSHIFT 10).  Unpatched, the gyro would read
every rotation at twice its rate and the filter would sit near 1 kHz instead
of 258 Hz.  `patches/betaflight_2025.12.5_iim42652_scale_and_aaf.patch`
changes those three cases in `accgyro_spi_icm426xx.c` and nothing else.  It
should go upstream; until then, **never flash a stock Betaflight build onto
this board with the IIM-42652 fitted.**

Stock targets are not a substitute either.  `TAKERG4AIO` (whose pin map this
board copies) fixes its chip alignment at CW270 and sets a 45° board yaw,
both wrong here.

The config also sets these defaults for this board (see the top of
`config.h`):

- **Board alignment 0/0/0.** The gyro sits square with the board, and the
  front arrow on the silkscreen points forward.
- **Receiver on UART2, CRSF.**  UART4 is spare (GPS).  LPUART1 RX (PB11) is
  on the stack lead's TLM pin, which this stack's ESC does not drive.
- **DShot300 with bidirectional DShot on.** This is what the AM32 ESC board
  expects.
- **No beeper.**  The board has none; `cli-setup.txt` turns the DShot beacon
  on (the motors beep on a lost receiver link and on the beeper switch).
- **Video.**  The AT7456E analog OSD is on SPI2 (shared with the blackbox
  flash), chip select PA8 (`USE_MAX7456`).  The HD VTX connector is UART1,
  which defaults to *VTX (MSP + DisplayPort)*.  No camera-control pin.
- **VTX power switch.**  PINIO1 on PB5, driving the N-FET that pulls the
  9 V regulator's enable low: PB5 high = VTX off.  PINIO1 is a plain
  output tied to the USER1 mode (`PINIO1_BOX 40`), so it is low, and the
  VTX **on**, at boot and until a USER1 switch turns it off.  The 9 V
  regulator runs from its own battery pads, and a thermostat beside it turns
  it off above 96 °C (back on at 76 °C) whatever the firmware does.
- **Battery.**  Voltage from the 30k/2k divider: `vbat_scale` 160 (2S-6S).
  Current from the ESC's CUR output, the average of its four 50 mV/A
  channel sensors, i.e. 12.5 mV per amp of battery current: `ibata_scale`
  125 (Betaflight's unit is mV per 10 A), offset 0, meter source ADC.

The 16 MB blackbox flash is an Infineon S25FL128L (JEDEC `01 60 18`,
-40..+125 °C), which Betaflight's `m25p16` driver lists.  The board runs
without it: Betaflight then finds no flash, and `blackbox_device = NONE`.

The processor is the STM32G473CEU6 (suffix 6: 105 °C junction).  The
suffix-3 part (STM32G473CEU3, 130 °C junction) fits the same pads and runs
the same image; it was not stocked anywhere when this was written.

### Flashing

1. Hold **BOOT** (right edge of the FC, rear half) and plug in USB-C. The
   board comes up in DFU mode.
2. In Betaflight Configurator, open *Firmware Flasher*, click **Load Firmware
   [Local]**, pick `betaflight_2025.12.5_STM32G47X_RIDGE3.hex`, and flash with
   *Full chip erase* on.
3. Connect, then paste `betaflight/cli-setup.txt` into the CLI and `save`.
   It has two video blocks: keep the HD block for a DJI, Walksnail or HDZero
   system (`vcd_video_system = HD`, without which the OSD goes to the analog
   chip), or swap to the analog block.  Assign the USER1 mode (named
   `VTX_OFF`) to a switch if you want to turn the VTX off from the radio.
4. **Props off, in the Setup tab:** tilt the nose down, and the model must pitch
   nose down.  Tilt the right side down, and it must roll right.  Turn it
   clockwise seen from above, and it must yaw right.  With the board level, the
   accelerometer reads about 0, 0, +1 g (not +2 g: that would be the
   unpatched driver).  If any of these is wrong, do not fly.

### Building it yourself

In a Betaflight 2025.12.5 checkout:

```
git apply <this repo>/ridge-3/firmware/betaflight/patches/betaflight_2025.12.5_iim42652_scale_and_aaf.patch
make arm_sdk_install
SOURCE_DATE_EPOCH=1790412014 make CONFIG=RIDGE3 \
  CONFIG_DIR=<this repo>/ridge-3/firmware/betaflight CONFIG_REVISION_DEFINE=
```

With that build date, and with no git revision stamped in, the build
reproduces the committed image bit for bit (Arm GNU 13.3.rel1, which is what
`make arm_sdk_install` fetches for 2025.12.5).

## ESC (AM32, four times)

The four Artery AT32F421G8U7 on the ESC board come blank from the
assembler.  Each one needs the AM32 bootloader and firmware once, over SWD.
After that, all firmware updates and settings go through the flight
controller in the usual way.

**First flash** (an ST-Link V2 or Artery AT-Link, and Artery's OpenOCD;
`am32/flash_esc.sh` has the details):

1. Each MCU runs from its own gate driver's 3.3 V, which is on whenever the
   board has a battery.  Power the bare ESC (not stacked, no motors) from a
   **current-limited bench supply, 12 V, 0.3 A**, on its battery pads.  The
   drivers' inputs have pull-downs, so the FETs stay off while an MCU is
   blank or halted.
2. Wire the probe's `GND` to the battery pad marked `-`, and `SWCLK` to `Cn`
   and `SWDIO` to `Dn`, where *n* is the ESC being flashed (the pads sit over
   each MCU on the board's top).  Do not connect the probe's 3.3 V output.
3. Run `am32/flash_esc.sh` (all four, asking before each) or
   `./flash_esc.sh 3` for one.  For each MCU it erases the flash, writes and
   verifies the bootloader (`0x08000000`) and the firmware (`0x08001000`),
   and starts it.  The board ties BOOT0 low, so there are no option bytes to
   set.  Artery's ISP Programmer with an AT-Link does the same from a GUI.

**Then, with the stack assembled and the battery on:**

1. Open the AM32 Configurator (<https://am32.ca>) in Chrome, connect to the
   flight controller (Betaflight passthrough) and read the ESCs.  All four
   should show AM32 2.21 with the target name `RIDGE3_F421`.
2. **Click "Send default config" before anything spins.**  An MCU flashed
   over SWD starts with an erased settings page, which AM32 would read as 3D
   mode, car-type reversing and stall boost *on*.
3. Set these on all four, then **Save config**:

   | AM32 Configurator setting | Value | Why |
   |---|---|---|
   | *Motor KV*, *Motor poles* | your motor | RPM telemetry |
   | *3D mode* | **off** | Bidirectional DShot needs no ESC setting |
   | *Car type reverse braking* | off | A car mode |
   | *30ms interval telemetry* | off | The TLM line is not wired on this ESC |
   | *Stuck rotor protection* | **on** (the default) | Cuts a motor whose back-EMF disappears |
   | *Stall protection* | off (the default) | A crawler feature that *adds* power at stall |
   | *Limits* → *Low voltage cut off* | Off | Betaflight does battery warnings |
   | *Limits* → *Temperature limit* | **110** °C | Read at the FET thermistor; see below |
   | *Limits* → *Current limit* | **20** A | See below |

4. Use Betaflight's *Motors* tab (props off!) to check the motor order and
   direction. Motor 1 is rear-right, 2 front-right, 3 rear-left, and 4
   front-left.  Reverse a motor with the *Reversed* switch in the
   configurator.
5. Check the current reading against a bench supply's ammeter (trim
   `ibata_scale` if needed).  The same sensors feed AM32's current limit.

**The limits.**  The ESC's ratings have not been measured; `../STRESS.md`
has the simulated ones.

- *Temperature limit* reads a 10 kΩ thermistor beside each channel's FETs
  (rev 1 read the processor's own die, a few millimetres away, which lagged
  the FETs in a burst).  Above the limit AM32 cuts that motor's maximum duty
  to about a quarter, falling to zero 10 °C above it.  In the heat test of
  the bring-up, compare the hottest FET with the ESC temperature Betaflight
  shows (`dshot_edt`).
- *Current limit* acts on each motor's own battery-side current, averaged
  over 50 ms.  It caps bursts; it is not a thermal limit.
- *Stuck rotor protection* works without current sensing.

### The target: `RIDGE3_F421`

The ESC schematic (`src/circuit.py`, `esc()`) is wired to AM32's hardware
groups `AT_B` + `AT_045`, the pin map of stock AT32F421 targets such as
`SKYSTARS_F80_F421`.  Pin numbers are the AT32F421's QFN-28 (datasheet
figure 5, table 5):

| Function | Port | QFN28 pin | Net (ESC *n*) |
|---|---|---|---|
| DShot input (also the bootloader's pin) | PB4 | 25 | `Mn_SIG` |
| Phase A high / low (TMR1_CH3 / CH3C) | PA10 / PB1 | 20 / 15 | `Mn_HA` / `Mn_LA` |
| Phase B high / low (TMR1_CH2 / CH2C) | PA9 / PB0 | 19 / 14 | `Mn_HB` / `Mn_LB` |
| Phase C high / low (TMR1_CH1 / CH1C) | PA8 / PA7 | 18 / 13 | `Mn_HC` / `Mn_LC` |
| Back-EMF A / B / C (comparator −) | PA0 / PA4 / PA5 | 6 / 10 / 11 | `Mn_CMP_A` / `_B` / `_C` |
| Virtual neutral (comparator +) | PA1 | 7 | `Mn_NEUTRAL` |
| FET thermistor (ADC_IN2) | PA2 | 8 | `Mn_NTC` |
| Battery voltage, 100k/10k (ADC_IN3) | PA3 | 9 | `ESC_VSENSE` |
| Current, 50 mV/A (ADC_IN6) | PA6 | 12 | `Mn_ISENSE` |
| SWDIO / SWCLK | PA13 / PA14 | 21 / 22 | `Mn_SWDIO` / `Mn_SWCLK` |
| BOOT0 | – | 1 | ground |

`RIDGE3_F421` (`AM32_2738df3_RIDGE3_F421_target.patch`):

- `MILLIVOLT_PER_AMP 50`, `CURRENT_OFFSET 0`: 0.5 mΩ shunt × INA186A3
  (100 V/V), 0 A = 0 V.
- `TARGET_VOLTAGE_DIVIDER 110`: the 100k/10k divider (ratio 11).  Voltage
  on PA3 and current on PA6 are AM32's `MCU_AT421` defaults.
- `USE_NTC` on PA2 with its own `NTC_table`: Murata NCU15XH103F60RC (10 kΩ,
  B25/50 3380 K) under a 10 kΩ pull-up from the channel's 3.3 V, computed
  from the B equation (entry *i* is the temperature at ADC count 64 *i*).
  At 110 °C the divider gives about 0.25 V; the table's 64-count steps
  there are about 10 °C, interpolated linearly.
- `DEAD_TIME 15`: 15 counts of TMR1's 120 MHz clock = 125 ns.  The
  DRV8320H itself holds a gate off until it sees the other one discharged,
  then adds ~100 ns, so AM32's dead time is a floor here, not the
  protection.  (AM32 also uses DEAD_TIME as its minimum duty.)
- No `USE_SERIAL_TELEMETRY`: the ESC's TLM line is not wired.
  Bidirectional DShot carries eRPM, and, with `dshot_edt = ON` in
  Betaflight, the ESCs' temperature, voltage and current.
- `FIRMWARE_NAME "OffGrid Rd3 "` (12 characters).  The configurators show
  `FILE_NAME`, `RIDGE3_F421`.

No official AM32 release is built for `RIDGE3_F421`, so update from a local
`.hex`.

### Building it yourself

AM32 releases are built with xPack GCC 10.3.  These images were built with
Arm GNU 13.3.rel1, which needs `-Wno-array-bounds` for one false positive in
`main.c` (a pointer into the device-info flash block).  The code is
unchanged.

```
# bootloader (repo am32-firmware/AM32-bootloader, commit 578ff29)
make ARM_SDK_PREFIX=<gcc>/bin/arm-none-eabi- AM32_F421_BOOTLOADER_PB4
# firmware (repo am32-firmware/AM32, commit 2738df3)
git apply <this repo>/ridge-3/firmware/am32/AM32_2738df3_RIDGE3_F421_target.patch
make ARM_SDK_PREFIX=<gcc>/bin/arm-none-eabi- RIDGE3_F421 \
  CFLAGS_BASE="-fsingle-precision-constant -fomit-frame-pointer -ffast-math -IInc -g3 -O3 \
  -ffunction-sections --specs=nosys.specs -Wall -Wundef -Wextra -Werror \
  -Wno-unused-parameter -Wno-stringop-truncation -Wno-array-bounds"
```

### Not yet verified

- Nothing here has run on an AT32F421, on this ESC or on this FC.
  `flash_esc.sh` has not been run (no Artery OpenOCD or part was at hand).
- `DEAD_TIME 15` with the DRV8320H's hold-off: scope the gate drive.
- The NTC table against a thermometer at the FETs, and the 50 mV/A and
  12.5 mV/A current scales against a bench ammeter.
- The Betaflight gyro patch: on the bench, the Setup tab's model must follow
  the board one for one (a 90° turn reads 90°), and the accelerometer reads
  1 g level.
- The 110 °C / 20 A limits are design estimates from the simulations, not
  measurements.
