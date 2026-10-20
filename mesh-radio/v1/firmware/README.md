# Mesh Radio v1: firmware

The Meshtastic board variant for Mesh Radio v1, plus the Adafruit bootloader
board definition it needs. It lives here until it goes upstream.

> **Status (19 Oct 2026): it compiles, and nothing has run on hardware.**
> No board exists yet. The variant builds against Meshtastic **v2.7.26.54e0d8d**
> (the latest stable release and the version Cairn pins), with and without the
> core patch. The bootloader builds against Adafruit_nRF52_Bootloader 0.11.0.
> **The transmit power table, the power caps and the antenna-detector
> thresholds come from models and simulations, not measurements.** Nothing
> above 1 W is used until they have been measured on the bench.
>
> 19 Oct: pins follow the power-path rework (P0.02 = PA_SRC_SYS, SOLAR_OK /
> DRONE_OK analog, P0.30 = REFL_DET, P0.31 = CHG_TS, header IO3/IO4 gone);
> new: power caps by temperature and by the cell, the missing-antenna cut-off,
> the 0–45 °C charging window, the no-cell check, and the 32.768 kHz crystal
> declared as 250 ppm.
>
> 20 Oct: the missing-antenna detector is a **ratio detector** (a forward-wave
> detector on P0.02/AIN0 joins the reflected-wave one; the trip is
> REFL/FWD, no longer a fixed voltage per power); every packet above 1 W
> **soft-starts** at 1 W and is raised only after that check passes;
> PA_SRC_SYS moved to P1.09; GPS_RESET is no longer wired to the processor.
> **The ratio threshold and the FWD_DET minimum are provisional** until the
> RF sim gives the new coupler's levels.

| Path | What it is |
|---|---|
| `variant/variant.h` | Pin map, radio and front-end settings, the **provisional** gain table, battery and charger settings |
| `variant/variant.cpp` | Board start-up and amplifier power: the TPS63810 supply, licensed/unlicensed levels, power caps (temperature, cell), the ratio missing-antenna check, the soft start above 1 W, amplifier source, charging window, shutdown |
| `variant/platformio.ini` | The `offgrid_mesh_radio_v1` build environment |
| `patches/0001-offgrid-mesh-radio-core-backports.patch` | A three-part change to Meshtastic core. **Part 1 is required before any US field use** (see *The US 1 W rule*). **Part 3 is required for the power caps and the antenna cut-off** (see *Transmit hooks*). |
| `bootloader/offgrid_mesh_radio_v1/` | `board.h`, `board.mk`, `board.cmake` and `pinconfig.c` for Adafruit_nRF52_Bootloader |
| `tools/pa_gain_table.py` | Builds the gain table from the amplifier model, and checks the soft-start supply against it. Replace the model with bench data later. |

## Build

These steps use a PlatformIO install inside the project, not a global one.

```sh
python3 -m venv .venv && .venv/bin/pip install platformio
git clone --depth 1 --branch v2.7.26.54e0d8d https://github.com/meshtastic/firmware meshfw
mkdir meshfw/variants/nrf52840/offgrid_mesh_radio_v1
cp mesh-radio/v1/firmware/variant/* meshfw/variants/nrf52840/offgrid_mesh_radio_v1/
cd meshfw
git apply ../mesh-radio/v1/firmware/patches/0001-offgrid-mesh-radio-core-backports.patch
../.venv/bin/pio run -e offgrid_mesh_radio_v1
# -> .pio/build/offgrid_mesh_radio_v1/firmware-offgrid_mesh_radio_v1-2.7.26.54e0d8d.uf2 (and .hex, -ota.zip)
```

**Result on 20 Oct 2026** (ratio detector, soft start, pin changes):
`pio run -e offgrid_mesh_radio_v1` gave SUCCESS both on unpatched v2.7.26
and with the patch applied. The `.uf2` is 1,470,976 bytes with the patch
(1,465,856 without); flash 90.2 % (735,408 of 815,104 bytes), RAM 41.1 %
(102,332 of 248,832). The 19 Oct variant, rebuilt the same day as a
reference, gave its 1,467,392 bytes again, so the change costs ~1.8 kB of
flash. The variant adds no compiler warnings (51 in the build, the same as
the reference). The 250 ppm check below was not repeated (nothing it
depends on changed).

**Checking the 250 ppm crystal setting.** Take the compile line for
`Bluefruit52Lib/bluefruit.cpp` from `pio run -v`, swap `-o …bluefruit.cpp.o`
for `-E -o -`, and look at `clock_cfg`: it must read `.accuracy = (0)`
(`NRF_CLOCK_LF_ACCURACY_250_PPM`), not `(7)`. It did on 19 Oct.

**One snag in the build environment (not needed on a normal machine).** The
session's proxy blocked GitHub's `/archive/*.zip` downloads, so PlatformIO
could not fetch the `lib_deps` that point at them. Each one was `git clone`d
at the same tag or commit instead, and those URLs were rewritten to `file://`
paths in the scratch checkout only.

The board JSON is `wiscore_rak4631`. It fits because the chip, the S140 6.1.1
SoftDevice, the flash layout and the bootloader are all the same. The catch:
the app's USB descriptor then carries RAK's VID/PID. A production build needs
its own PID and board JSON. The build sets `PRIVATE_HW` as the Meshtastic
hardware model, because there is no Meshtastic hardware-model number for this
board yet.

Build options go in `build_flags`:

| Flag | Effect |
|---|---|
| `-D OFFGRID_PA_ALLOW_4V0=1` | Licensed mode runs the amplifier at 4.0 V (about 35 dBm) instead of 3.6 V. **Use only with a known-good antenna.** The QPA9510 is rated for a 10:1 mismatch (a missing antenna) at 3.6 V only. |
| `-D OFFGRID_LNA_BYPASS=1` | The receive amplifier is always in bypass. This is the battery saver: about 5 mA less, and about 7 dB less sensitive. |
| `-D OFFGRID_PA_VOUT_US_MV=…` | Amplifier supply in unlicensed mode (default 2700). Set it from the bench measurements. |
| `-D OFFGRID_TCAP_…`, `OFFGRID_REFL_…`, `OFFGRID_FWD_…`, `OFFGRID_ANT_…`, `OFFGRID_CHG_…`, `OFFGRID_CELL_TEST_MS`, … | Every threshold below is an `#ifndef` default in `variant.h`; set it from bench data here. |
| `-D OFFGRID_ANT_RATIO_MAX_PCT=…`, `-D OFFGRID_FWD_MIN_MV=…` | The antenna trip (REFL/FWD, default 35 %) and the FWD_DET level that proves the RF is on (default 50 mV). **Provisional**: set them from the RF sim, then the bench. |
| `-D OFFGRID_SOFTSTART_VPA_MV=…` | The supply a packet above 1 W starts at (default 2250: Psat = 30 dBm in the model). 2700 starts at the US level instead, which the model puts at ~31.4 dBm at the full +20 dBm drive. |
| `-D OFFGRID_DRONE_SERIAL_DEFAULT=0` | Stops the drone-port serial module from being turned on by default. This only matters with patch part 2. |

## Flash

**1. Bootloader, once per board, over SWD.** Use the SWD test pads with a
J-Link, an nRF52-DK or a CMSIS-DAP probe.

```sh
git clone --branch 0.11.0 --recurse-submodules https://github.com/adafruit/Adafruit_nRF52_Bootloader
cp -r mesh-radio/v1/firmware/bootloader/offgrid_mesh_radio_v1 Adafruit_nRF52_Bootloader/src/boards/
cd Adafruit_nRF52_Bootloader
make BOARD=offgrid_mesh_radio_v1 all        # needs arm-none-eabi-gcc, python intelhex, adafruit-nrfutil
nrfjprog --program _build/build-offgrid_mesh_radio_v1/offgrid_mesh_radio_v1_bootloader-0.11.0_s140_6.1.1.hex --chiperase --reset
#   (or: make BOARD=offgrid_mesh_radio_v1 flash-sd flash, or pyocd/openocd with the same .hex)
```

That `.hex` holds the S140 6.1.1 SoftDevice and the bootloader together. It
built cleanly here, with PlatformIO's GCC 9.3.1.

**2. Firmware, over USB, as a UF2.**

1. Double-press reset, or hold the user button while you press reset.
2. A drive called `OGMESHBOOT` appears.
3. Copy `firmware-offgrid_mesh_radio_v1-*.uf2` onto it. The board reboots
   into Meshtastic.

You can also run `pio run -e offgrid_mesh_radio_v1 -t upload` (nrfutil DFU
over the USB serial port), or send the `-ota.zip` over Bluetooth.

### What the bootloader board file sets, and why

- **`ENABLE_DCDC_1 = 1`.** The REG1 DC/DC inductors (10 µH + 15 nH) are
  fitted, and the DC/DC saves current against the LDO.
  - `ENABLE_DCDC_0` stays 0: REG0 has no inductor.
  - The app sets `NRF_POWER->DCDCEN` again in `initVariant()`, so an image
    flashed over SWD gets it too.
- **No `UICR_REGOUT0_VALUE`.** The chip runs in normal-voltage mode: VDD and
  VDDH are both on the 3.3 V rail, and REG0 is unused. REGOUT0 only sets
  REG0's output when the chip runs from VDDH alone (high-voltage mode, as on
  the nice!nano), so writing it here would do nothing useful.
- **Pin reset and NFC pins as GPIO.** The bootloader `Makefile` always defines
  `CONFIG_GPIO_AS_PINRESET` and `CONFIG_NFCT_PINS_AS_GPIOS`.
  - P0.18 becomes the reset button.
  - P0.09 (the charger's /CE) and P0.10 work as GPIO.
- **LEDs and button.** Green P1.03 is the primary LED and blue P1.04 the
  secondary; both are active high. The DFU button is P1.00 with the internal
  pull-up. There is no second button, so there is no button entry to
  Bluetooth OTA mode.
- **USB VID/PID.** It is 0x1209:0x0001, the pid.codes *test* PID, for
  prototypes only. **Get a real PID before production.**

## Pin map (from `src/circuit.py`, `mcu()`)

| Function | nRF52840 | Arduino # | Notes |
|---|---|---|---|
| SX1262 NSS / SCK / MOSI / MISO | P1.10 / P1.11 / P1.12 / P1.13 | 42 / 43 / 44 / 45 | Same as the RAK4631 |
| SX1262 BUSY / DIO1 / NRESET | P1.14 / P1.15 / P1.06 | 46 / 47 / 38 | Same as the RAK4631 |
| PA_EN → `SX126X_TXEN` | P1.07 | 39 | Enables the amplifier's 2.8 V control-voltage LDO |
| LNA_EN → `SX126X_RXEN` | P1.05 | 37 | High = LNA gain, low = bypass |
| DIO2 (on the SX1262) | — | — | Antenna switch (`SX126X_DIO2_AS_RF_SWITCH`) |
| DIO3 (on the SX1262) | — | — | TCXO at 2.2 V |
| PA_PWR_EN | P1.01 | 33 | Power mux + TPS63810 on. 1 M pull-down. |
| PA_SRC_SYS | P1.09 | 41 | High = amplifier from charger SYS (no cell, or USB in and a cell too weak for 1 W); low = battery first. 1 M pull-down. P0.02 until 20 Oct; PA_VSEL before 19 Oct (the TPS63810 VSEL is tied to GND). |
| I2C SDA / SCL | P0.13 / P0.14 | 13 / 14 | TMP1075 at 0x48, TPS63810 at 0x75 |
| TEMP_ALERT | P0.06 | 6 | TMP1075 ALERT, active low |
| Drone RX / TX (Serial2) | P0.15 / P0.16 | 15 / 16 | The RAK4631's Serial1 pins |
| Drone CTS / RTS | P0.21 / P0.22 | 21 / 22 | RTS held low (ready); CTS not used |
| GPS RX / TX (Serial1) | P0.19 / P0.20 | 19 / 20 | |
| GPS_EN / PPS | P0.23 / P0.17 | 23 / 17 | EN active high. The module's RESET is not wired to the processor (20 Oct): cycling GPS_EN resets it. |
| LED green / blue | P1.03 / P1.04 | 35 / 36 | Active high |
| User button | P1.00 | 32 | Active low, internal pull-up |
| Battery sense | P0.05 / AIN3 | 5 | 1 M / 1.5 M divider, multiplier 1.667 |
| CHG_CE_N / STAT1 / STAT2 | P0.09 / P0.24 / P0.25 | 9 / 24 / 25 | /CE driven low (charging on). STAT2 low = charging. |
| SOLAR_OK / DRONE_OK | P0.04 / P0.03 (AIN2 / AIN1) | 4 / 3 | Analog: input voltage / 16 (1.5 M / 100 k). Read to tell whether external power is in. |
| REFL_DET | P0.30 / AIN6 | 30 (A3) | Antenna detector, reflected wave (diode into 1 nF ∥ 100 k) |
| FWD_DET | P0.02 / AIN0 | 2 (A5) | Antenna detector, forward wave (diode into 1 nF ∥ 100 k). New 20 Oct. |
| CHG_TS | P0.31 / AIN7 | 31 (A4) | The charger's TS/MR pin: battery NTC, 38 µA bias while an input is present |
| USB VBUS | — | — | Read through the POWER peripheral (`NRF_APM`); the VBUS pin is fed through 22 R (net NRF_VBUS) |
| Display SPI1 (header) | SCK P0.07, MOSI P0.08, MISO P0.11, CS P0.12, DC P0.26, RST P0.27, BL P1.08 | | Defined, but no display is turned on |
| Expansion IO1, IO2, IO5, IO6 | P0.28 (AIN4), P0.29 (AIN5), P1.02, P0.10 | 28, 29, 34, 10 | Header pins 12, 13, 16, 17. Pins 14 and 15 (IO3/IO4 before) are not connected. |

**Why the GPS is on Serial1 and the drone on Serial2.** Meshtastic's nRF52
code fixes which serial port does which job:

- the GPS always uses `Serial1`;
- the Serial module, which carries the Meshtastic API to the drone, always
  uses `Serial2`, on whatever pins `serial.rxd`/`serial.txd` name.

So the drone port is `Serial2`, even though it sits on the RAK4631's
`Serial1` pins.

**Drone port settings.** These are the Cairn field-logger settings. With
patch part 2 they are the factory default. Without it, set them once:

```sh
meshtastic --set serial.enabled true --set serial.rxd 15 --set serial.txd 16 \
           --set serial.mode PROTO --set serial.baud BAUD_38400
```


## Transmit power

Power is set by the SX1262's drive level. The drive goes through a 15.9 dB
pad into the QPA9510, which has fixed gain, then 1.1 dB of harmonic-filter, switch
and antenna-filter loss to the U.FL (sim/rf study 1). The net gain from the SX1262 pin to
the U.FL is about 16.8 dB.

- **`SX126X_MAX_POWER 20`.** The SX1262 is never driven above +20 dBm.
  - At that drive the first resistor of the pad dissipates 73 mW, 58 % of
    its rating.
  - The amplifier input sees about +4 dBm, against an absolute maximum of
    +13 dBm.
- **Unlicensed mode (Meshtastic's default).**
  - Meshtastic caps the request at the region limit: 30 dBm for US.
  - `TX_GAIN_LORA` turns the request into an SX1262 setting.
  - The amplifier supply is 2.7 V (`OFFGRID_PA_VOUT_US_MV`).
- **Licensed (ham) mode.**
  - Meshtastic skips both the region limit and the gain table: the configured
    `tx_power` goes to the SX1262 as-is, capped at +20 dBm.
  - The amplifier supply sets the ceiling: 3.6 V gives about 33.5–34 dBm.
    With `OFFGRID_PA_ALLOW_4V0=1`, 4.0 V gives about 34–35 dBm.
  - The variant switches the supply within 2 s of the licence setting
    changing.
- **Power caps** (next section) lower the SX1262 setting of each packet and
  the supply, by board temperature, by the cell, and after a missing-antenna
  detection. A cap never raises anything.

**Supply sequencing.** All of this is in `variant.cpp`.

1. `initVariant()` (before `setup()`) turns PA_PWR_EN on, waits 5 ms and
   programs the TPS63810 to 2.7 V: CONTROL = 0x24 (enabled, ramp-PWM), and
   VOUT1 = (V − 1.8 V) / 25 mV, which is 0x24 for 2.7 V, 0x48 for 3.6 V and
   0x58 for 4.0 V. VSEL is tied to GND, so VOUT1 is always the active
   register.
2. `lateInitVariant()` (once the config is loaded) reads the temperature,
   the inputs and the cell, sets the TMP1075 limits and the supply.
3. The main loop re-checks everything every 2 s (`OFFGRID_PA_CHECK_MS`) and
   re-writes the TPS63810 if it has reset. It resets to its 3.3 V default
   whenever the power mux drops its input. A raise of the supply waits until
   no packet is going out.
4. Before each packet (patch part 3) the supply is brought to the level the
   caps want, or to the soft-start level for a packet above 1 W (see
   *Soft start*), and the radio waits for the TPS63810's ramp (1 V/ms) to
   finish.
5. `variant_shutdown()` turns everything off before system-off.

**Why a failure stays safe.** An unprogrammed TPS63810 sits at 3.3 V: that
is below the licensed level, and the US table holds at any supply. The
amplifier-off states do not depend on the patch or on I2C: PA_EN is handed
to its 100 k pull-down, and the TMP1075's own ALERT pin is read directly.

### Power caps

Every cap is a ceiling on the power at the U.FL. The lowest one in force
wins, and is applied two ways:

- **SX1262 setting**, per packet: the highest setting whose `TX_GAIN_LORA`
  power is within the cap (the same rule as Meshtastic's `limitPower()`).
  This needs patch part 3.
- **Amplifier supply**: Psat(VPA) = cap, that is VPA = 4.0 V × 10^((cap −
  35)/20), never below 2.7 V nor above the licence ceiling. 33 dBm → 3.2 V,
  32 dBm → 2.85 V, 30 dBm → 2.7 V. Without patch part 3 this is the only
  limit, and it is applied within 2 s.

In US mode the request is already 30 dBm or less, so only the "amplifier
off" states change anything there: **US stays 1 W at the antenna**.

**"Amplifier off"** means VPA at its 1.8 V minimum and PA_EN released to its
pull-down (RadioLib only ever writes the pin's output latch, so it cannot
turn the amplifier on). The SX1262 is set to −9 dBm. There is no path
around the amplifier, so packets still "go out" but only as leakage through
the switched-off amplifier: in practice the node is not heard. Meshtastic's
queue keeps moving.

**By board temperature** (TMP1075 at 0x48, beside the amplifier). From the
sim/thermal follow-up table for the 6-layer board with the heat fixes and the
gap pad (35 dBm passes up to 45 °C ambient for 1 s a minute, 33 dBm at 60 °C,
31.5 dBm in a 60 °C storm):

| Board temperature | Cap | Back up when |
|---|---|---|
| up to 45 °C | none: the configured maximum (licensed 3.6 V ≈ 34 dBm; 35 dBm only with `OFFGRID_PA_ALLOW_4V0=1`) | — |
| 45–60 °C | 33 dBm (2 W) | below 42 °C |
| 60–75 °C | 30 dBm (1 W) | below 57 °C |
| above 75 °C, or TEMP_ALERT | amplifier off | ALERT clear and below 70 °C |
| no reading (3 failed reads) | 30 dBm | the next good read |

**TEMP_ALERT.** The TMP1075's limits are now 75 °C (HLIM) and 70 °C (LLIM),
comparator mode. ALERT means amplifier off, the same as the top row, so the
cut-off holds even if the I2C reading fails. (Before 19 Oct it lowered the
supply to 2.7 V at 80 °C.) The sensor sees only the slow average, up to
36 °C behind the amplifier case at 1 W (sim/thermal): it limits duty, it
cannot protect a single burst.

**By the cell** (sim/burst/results.txt, "Highest PA level that passes,
battery only": no brown-out, no protector trip, no TPS63810 reset). The table
is indexed by:

- **cell voltage**, read between packets (at least 0.5 s after one), and
  interpolated between the table's 4.2 / 3.7 / 3.3 / 3.1 V rows; between a
  passing row and a failing one the failing one is used;
- **cell temperature**: the charger NTC when it is biased (an input is
  present), the TMP1075, the lower of the two, or 0 °C with neither. The
  table's colder band is used (−40 / −20 / 0 / 25 °C; 60 and 85 °C are the
  same as 25 °C or better);
- **R_int at 25 °C**: 150 mΩ (the table's mid cell) until measured, then
  estimated from the sag under each packet of 40 ms or more at 29 dBm or
  more: (V_idle − V_load) scaled up for the 60 ms VBAT_SENSE filter, over the
  modelled current (sim/thermal follow-up table A plus 0.45 W for the
  board), minus 90 mΩ of plug, reverse FET, protector and sense resistor,
  and scaled to 25 °C as sim/burst does (×9 / ×5 / ×2 / ×1 at −40 / −20 / 0 /
  25 °C). The column is the next one up (50 / 150 / 300 mΩ).

Where the table says not even 1 W, the amplifier is off, unless USB is in
(below).

**After a missing-antenna detection**: amplifier off, then 30 dBm for the
retry (*Missing-antenna cut-off*).

**Soft start**: not a cap. Every packet above 1 W *starts* at 1 W, whatever
the caps allow, until the antenna check has passed (*Soft start*).

### Amplifier source: battery first, SYS without a cell

P1.09 is PA_SRC_SYS (P0.02 until 20 Oct, PA_VSEL before). Low, the TPS2121
mux takes the battery first, down to 2.60 V. High, it takes charger SYS. The variant drives it
high:

- **with no cell fitted** (the cell test below says so), cap 30 dBm: the
  USB-only case passes at 1 W, and 1.6 W and up exceed the charger's 1.05 A
  input (sim/burst);
- **with USB in and a cell the table puts below 1 W**, cap 30 dBm
  (`u_31_300_1W_sys` passes; without it the weak cell trips UVP).

The source is only switched while no packet is going out, and the TPS63810
is re-programmed after it (the mux gap can reset it).

**Cell test, and the reverse-FET latch** (sim/README.md, the one FAIL: with
external power in, pulling a right-way cell leaves the reverse FET latched
on, so a reversed cell plugged in next sees live pads). With external power
in, the variant holds /CE high for 1 s (`OFFGRID_CELL_TEST_MS`) and then
reads VBAT_SENSE. With no cell, BAT_P decays (which also clears the latch)
and reads below 2.0 V: "no cell". It runs:

- 3 s after external power appears, and at boot on external power;
- when STAT2 toggles (4 edges in 10 s) with STAT1 high, the BQ25185's
  no-battery signature;
- every 60 s while there is no cell, to notice one being plugged in.

External power = USB VBUS (POWER peripheral), or SOLAR_OK / DRONE_OK
(input / 16) reading 4.0 V or more.

## Transmit hooks (patch part 3)

Meshtastic v2.7.26 drives PA_EN and LNA_EN through RadioLib's RF-switch pins
and gives a variant no call per packet. Part 3 of the patch adds three weak
hooks (no-ops for every other board):

| Hook | Called from | Used for |
|---|---|---|
| `variantLimitTxPower(power)` | `SX126xInterface::configHardwareForSend()`, radio in standby, before each packet | Returns the SX1262 setting for this packet (can only lower it). Written to the chip only when it changes. The variant also brings the supply to the caps' level (or the soft-start level) here, waits out the ramp, and hands PA_EN back to RadioLib when the amplifier may run. |
| `variantTxStarted()` | `RadioLibInterface::startSend()`, right after `startTransmit()` | The antenna check; for a soft-started packet, the raise to full power |
| `variantTxDone()` | `RadioLibInterface::completeSending()` | Supply back to the soft-start level; the cell voltage under load |

The patch did not change for the ratio detector or the soft start: the
three hooks already run at the right moments.

## Missing-antenna cut-off: the ratio detector

A printed coupler between the antenna filter and the U.FL feeds two diode
detectors, each into 1 nF ∥ 100 k: a DC level that settles within ~0.15 ms
(FWD_DET) to ~0.46 ms (REFL_DET, antenna missing, 27 dBm, −40 °C) of the RF
reaching full power (`sim/rf/results.txt` study 8, still being worked on
when this was written):

- **REFL_DET**, P0.30/AIN6: the reflected wave (as before);
- **FWD_DET**, P0.02/AIN0: the forward wave (new, 20 Oct).

The firmware trips on the **ratio REFL/FWD**. It is near 0 with a matched
antenna and near 1 with the antenna missing, whatever the cable length and
the power. At these levels the diodes are partly square-law, which squeezes
the cases in between: study 8 (20 Oct) has a VSWR-2 antenna at 0.00–0.29
(0.33 over mismatched diode pairs) and a missing one at 0.27 and up with
typical diodes (0.43 and up at 30 dBm, 0.69 and up from 33 dBm). The single detector before it compared
REFL_DET with a fixed threshold per power, and with the antenna missing its
reading could fall below that threshold at some cable lengths. The two
diodes drift alike with temperature, so the ratio needs no temperature term.

- **When:** 750 µs after the SX1262 is told to transmit
  (`OFFGRID_REFL_SAMPLE_US`, kept; see the timing below), FWD_DET and
  REFL_DET in one two-channel SAADC scan (40 µs acquisition each, back to
  back, so a level still moving moves both nearly alike), 3.6 V full scale.
  Every packet whose modelled U.FL power is 27 dBm or more
  (`OFFGRID_REFL_MIN_DBM`), and every soft-started packet. If FWD_DET is
  still below its minimum, both are read again every 50 µs for up to 750 µs
  more (`OFFGRID_FWD_POLL_US`, `OFFGRID_FWD_WAIT_MAX_US`): the RF can come up
  late.
- **Trip (PROVISIONAL):** FWD_DET ≥ 50 mV (`OFFGRID_FWD_MIN_MV`: the RF is
  on and the reading is clear of the SAADC's offset) and REFL/FWD > 0.35
  (`OFFGRID_ANT_RATIO_MAX_PCT`). Both are placeholders until the RF sim's
  ratio study is final. As study 8 stood on 20 Oct, 0.35 is above every
  VSWR-2 case (0.33, worst diode pair: no false trips) and below every
  missing-antenna case with typical diodes from 30 dBm up (0.43), which is
  where the soft start decides. The obvious 0.6 would miss a missing antenna
  at 30 dBm in the cold. It still misses one at 27 dBm and −40 °C (0.27)
  and with badly mismatched diodes; both are at ≤ 1 W. A matched antenna's
  FWD_DET is only ~0.13 V at 30 dBm and −40 °C, so a minimum of 150 mV would
  stop the soft start from ever raising in the cold.
- **Fallback, only while FWD_DET reads too low to trust** (RF late, the
  forward detector broken, or an open U.FL at a phase that puts FWD_DET near
  0): the old absolute test on REFL_DET alone, 0.35 V at 30 dBm and 0.73 V
  at 35 dBm, interpolated in dB, plus 1.4 mV/°C above 25 °C
  (`OFFGRID_REFL_V30_MV` / `_V35_MV` / `_TC_UV_PER_C`). It can trip the
  cut-off and can pass the 1 W retry, as before, but it never clears a
  packet for more than 1 W: a soft-started packet whose FWD_DET stays low
  stays at the soft-start level (logged `Soft start held at 1 W: FWD_DET …`).
  **These thresholds belong to the old detector.** Study 8 shows the new
  REFL_DET staying below them even with the antenna missing (e.g. 75 mV
  against 350 mV at 30 dBm, 25 °C), so in practice the fallback never trips;
  it needs new numbers, or removing, once the sim is final.
- **On a trip:** PA_EN is dropped at once (mid-packet), the supply goes to
  1.8 V, and the amplifier stays off for the following packets. It is logged
  (`ANTENNA MISSING? REFL_DET … / FWD_DET … = …%`) and the phone app gets a
  warning notification. After 30 s the next packet goes at 1 W
  (`OFFGRID_ANT_PROBE_DBM`) and is checked; if it passes, full power is back;
  if not, the wait doubles, up to 10 minutes (`OFFGRID_ANT_RETRY_MS`,
  `OFFGRID_ANT_RETRY_MAX_MS`).

**Why 750 µs is kept.** RadioLib 7.6.0 (`SX126x::launchMode()`) raises
PA_EN, sends SetTx and then waits for the SX1262's BUSY to fall, which comes
only after its oscillator start, PLL lock and 200 µs PA ramp. So when the
hook runs, the SX1262 is at full drive, the preamble has just begun and
PA_EN has been high for at least ~0.25 ms. What is left is the QPA9510's
2.8 V control supply: the TLV75528 starts in 550 µs *typical* with no
maximum in its data sheet, then the QPA9510 ramps in ~40 µs and the
detectors settle: ~20 µs was the expectation, but study 8 gives ~0.15 ms
for FWD_DET and up to ~0.46 ms for REFL_DET (antenna missing, 27 dBm,
−40 °C). So 750 µs (≥ 1 ms after PA_EN) covers the typical case with little
to spare and is not shortened; the FWD_DET poll covers a later RF. A
REFL_DET not quite settled reads low, so the ratio errs towards "antenna
present"; at 30 dBm a missing antenna (≥ 0.43) still has room above 0.35.

## Soft start above 1 W

The RF sim found that above ~1 W with the antenna missing the antenna switch
is overstressed from the first RF cycle, so a check once the packet is at
full power is too late. Every packet that would go out above 1 W therefore
starts at 1 W:

1. **Which packets.** The packet's supply (the caps' level) is above the US
   level (2.7 V) and its modelled U.FL power is above 30 dBm less 1 dB for
   the model's uncertainty (`OFFGRID_SOFTSTART_ABOVE_DBM`,
   `OFFGRID_SOFTSTART_MODEL_DB`). In practice: licensed mode at a drive of
   +13 dBm or more, at the 3.6/4.0 V ceiling or a 33/32 dBm cap. US mode
   (2.7 V) and every 30 dBm cap never soft-start: those packets are as
   before, with the ratio check.
2. **Before the packet** (`variantLimitTxPower`): the SX1262 gets the
   packet's own drive, and the TPS63810 the soft-start supply,
   **2.25 V** (`OFFGRID_SOFTSTART_VPA_MV`). The radio waits for the ramp
   down to finish, so no RF goes out above it; usually there is nothing to
   wait for, because the supply went back down right after the last packet.
3. **At the sample** (750 µs): the ratio check above.
   - Antenna present (a trusted ratio): one I2C write of VOUT1 raises the
     supply to the packet's own level. The TPS63810 then slews at 1 V/ms
     (SLEW = 00, data sheet SR): 2.25 → 3.6 V in 1.35 ms, → 4.0 V in
     1.75 ms. The rest of the packet goes at full power.
   - Antenna missing: the cut-off above, from ≤ 1 W.
   - FWD_DET too low to trust: no raise; the packet finishes at ≤ 1 W.
4. **After the packet** (`variantTxDone`): the supply goes back to 2.25 V
   (one VOUT1 write), so its ramp down is over before the next packet.

**Why 2.25 V and not the US level (2.7 V).** In US mode the gain table holds
the SX1262 to +13 dBm, which gives ~29 dBm at 2.7 V. A licensed packet runs
the SX1262 at up to +20 dBm, and the model puts that at ~31.4 dBm (1.4 W) at
2.7 V. 2.25 V is the highest TPS63810 step at which the saturated output is
30 dBm (model 29.9 dBm at +20 dBm drive; `tools/pa_gain_table.py` prints the
table and asserts it). `-D OFFGRID_SOFTSTART_VPA_MV=2700` gives the literal
US level instead.

**LoRa and the step.** LoRa chirps have a constant envelope, so an amplitude
step does not corrupt the symbols; early in the preamble it only moves the
level the receiver's gain settles on over a few preamble symbols. It must
land inside the preamble, though, before the sync word and the header. With
Meshtastic's 16-symbol preamble:

| Preset | Preamble | Raise to 4.0 V ends at |
|---|---|---|
| SHORT_TURBO (SF7, 500 kHz), the shortest | 4.10 ms | ~3.0 ms |
| SHORT_FAST (SF7, 250 kHz) | 8.19 ms | ~3.0 ms |
| LONG_FAST (SF11, 250 kHz), the default | 131 ms | ~3.0 ms |
| LONG_SLOW (SF12, 125 kHz), the longest | 524 ms | ~3.0 ms |

~3.0 ms = 0.75 ms to the sample, ~0.1 ms for the two-channel reading, ~0.4 ms for
the I2C write at the core's default 100 kHz, 1.75 ms of slew. The variant
works the preamble out from the LoRa settings for every soft-started packet
and skips the raise (the packet stays at 1 W, logged `Soft start held at 1 W:
the raise would end after the … us preamble`) if the raise would end less
than 0.5 ms (`OFFGRID_SOFTSTART_PREAMBLE_MARGIN_US`) before the end of the
preamble: a late FWD_DET at SHORT_TURBO, or a custom setting with a very
short preamble (SF5/SF6 at 500 kHz).

**If the TPS63810 cannot be set** to the soft-start level before a packet
above 1 W (I2C failure), the supply is unknown, so that packet's SX1262
drive is held to the 1 W setting instead (+13 dBm, which the gain table
keeps at or under 30 dBm at any supply).

## Charging window (CHG_TS)

The NTC (10 k, B 3380, beside the battery plug) is on the BQ25185's TS/MR
pin, which the charger biases with 38 µA (ITSMR) while an input is present:
1.07 V at 0 °C, 0.38 V at 25 °C, 0.19 V at 45 °C, 0.12 V at 60 °C. P0.31/AIN7
reads it every 2 s (1.2 V full scale) and converts it with the B equation.

- **Window:** /CE high (charging off) below 0 °C or above 45 °C; back on
  between 3 and 42 °C. Charge current is 300 mA (ISET 1 k).
- **Only with an input present.** With no input there is no bias and the
  pin reads near 0 V; the state is left as it was (there is nothing to
  charge from anyway). Below 50 mV with an input (a cell above ~80 °C) the
  reading is ignored and the charger's own TS stops it.
- **The ship-mode trap.** Below 90 mV (VTSMR, a cell above ~67 °C) the
  charger sees a held button, and after 10 s would arm ship mode at the next
  input loss. While the pin reads under 100 mV the variant toggles /CE for
  20 ms every 5 s, which restarts that timer (circuit.py, `charger()`).
- **Backstop:** the charger's own window (about 1–60 °C) is unchanged, and
  is all there is while the processor is off: `variant_shutdown()` leaves
  /CE to its 100 k pull-down (charging on).

## 32.768 kHz crystal: 250 ppm

The crystal drifts about −150 ppm at −40 °C and −130 ppm at +85 °C
(sim/thermal, study 3). The Adafruit core hard-codes
`NRF_CLOCK_LF_ACCURACY_20_PPM` for `USE_LFXO` in `AdafruitBluefruit::begin()`
and has no option for it, so declared as 20 ppm the SoftDevice's receive
windows are too narrow when the node is cold or hot, and Bluetooth
connections drop. `variant.h` includes `nrf_sdm.h` first and redefines
`NRF_CLOCK_LF_ACCURACY_20_PPM` to the 250 ppm value; every file that includes
`Arduino.h` sees it, `bluefruit.cpp` included (checked with `-E`, see
*Build*). It costs a little current in a connection. The bootloader's own
BLE DFU still declares 20 ppm, but this board has no button entry to BLE DFU.

## The power table (PROVISIONAL: a model, to be replaced by bench measurements)

`TX_GAIN_LORA = 17 ×17, 16, 16, 15, 15, 14`. Entry *i* is the gain with
the SX1262 at *i* dBm.

**The model.**

- Gain: 33.8 dB (QPA9510) − 15.9 dB (pad) − 1.1 dB (amplifier to U.FL,
  sim/rf) = 16.8 dB small-signal. Before sim/rf put a number on that loss,
  the table left it out (18 dB), which erred towards too little output.
- Compression: Rapp, p = 2, towards a saturated output of about 35 dBm at
  the U.FL at 4.0 V (sim/rf Monte Carlo: 34.8–35.2 dBm). That ceiling scales
  as 20·log(V): about 34 dBm at 3.6 V and 31.5 dBm at 2.7 V.
- Rounding: computed on the 4.0 V curve and rounded up. So, in the model, a
  request is never exceeded at any amplifier supply. At the US supply
  (2.7 V) a 30 dBm request stays at or under ~29.7 dBm even if the QPA9510
  has 1 dB more gain than typical.

| Requested (US mode) | SX1262 set to | U.FL, VPA 2.7 V | 3.3 V | 4.0 V |
|---|---|---|---|---|
| ≤ 8 dBm | −9 (its minimum) | 7.8 | 7.8 | 7.8 |
| 20 dBm | 3 | 19.8 | 19.8 | 19.8 |
| 24 dBm | 7 | 23.7 | 23.8 | 23.8 |
| 28 dBm | 11 | 27.4 | 27.6 | 27.7 |
| **30 dBm (US maximum)** | **13** | **29.0** | 29.4 | 29.6 |

| Licensed mode: SX1262 set to | VPA 3.6 V (default ceiling) | 4.0 V (opt-in) |
|---|---|---|
| 10 dBm | 26.7 | 26.8 |
| 14 dBm | 30.4 | 30.5 |
| 16 dBm | 31.8 | 32.1 |
| 20 dBm (the cap; `tx_power` 0 or ≥ 20) | 33.5 | 34.2 |

| Cap | Highest SX1262 setting | Supply | Model output |
|---|---|---|---|
| 30 dBm | 13 | 2.7 V | 29.0 |
| 32 dBm | 15 | 2.85 V | 30.4 |
| 33 dBm | 17 | 3.2 V | 31.9 |
| 34 dBm | 19 | 3.575 V | 33.2 |

`python3 tools/pa_gain_table.py` reprints all three tables. `variant.cpp`
carries the same model (`modelUflDbm()`) to estimate each packet's power for
the antenna-detector threshold and the battery estimate.

**Replacing the model with measurements.**

1. Measure the U.FL power for SX1262 settings 0–20 dBm at 2.7 V and at the
   licensed ceiling. Use the Meshtastic licensed mode so that `tx_power`
   maps directly to the SX1262 setting.
2. Take gain[i] = ceil(max over supplies of (P_out − i)).
3. Paste the result into `variant.h`, and update `MODEL_G0_DB` /
   `MODEL_PSAT_4V0` in `variant.cpp` and `tools/pa_gain_table.py`.
4. Then set `OFFGRID_PA_VOUT_US_MV` to the lowest supply that still reaches
   30 dBm. The model's 2.7 V reaches only about 29.0 dBm.

## The US 1 W rule

FCC Part 15.247 limits 902–928 MHz to **1 W (30 dBm) conducted**, with up to
6 dBi of antenna gain (36 dBm EIRP). Above 6 dBi, the conducted power must
drop dB for dB.

**How the firmware enforces it.** In unlicensed mode:

- Meshtastic's US region limit caps any request at 30 dBm;
- the gain table turns that into an SX1262 setting that, in the model, gives
  ≤ 30 dBm at any amplifier supply;
- the supply is held at 2.7 V, so even a full +20 dBm drive saturates near
  31.5 dBm, not 34–35 dBm;
- the caps can only lower it.

**Meshtastic v2.7.26 has a hole here, and patch part 1 closes it.** After any
saved settings change, `SX126xInterface::reconfigure()` re-applies the raw
`tx_power` without the region limit or the gain table. The SX1262 then runs
at +20 dBm until the next reboot. On this board that is about 31.5 dBm.

Patch part 1 calls `limitPower()` there, as `init()` does. The same fix is
already on Meshtastic develop (checked at a12618f), so the patch can be
dropped once a release includes it.

**Antenna choice is still the operator's job.** With an antenna above 6 dBi,
lower `tx_power` to match. The board itself still needs FCC certification
before it is sold; that is separate from this firmware.

**Above 1 W is for licensed amateurs only (Part 97).**

- Use Meshtastic's licensed mode (`meshtastic --set-ham CALLSIGN`). It sets
  `is_licensed`, puts the callsign in the node name and turns off encryption,
  which Part 97 requires.
- Per the owner's decision, the boards stay in US mode until the owner holds
  a licence.

## Not done yet, and what is unverified

**Provisional or unverified (needs a built board and RF test gear):**

- The gain table and the 2.7 / 3.6 / 4.0 V supply levels. These are the
  model above, not measurements.
- That 30 dBm is reached, and not exceeded, in US mode.
- The QPA9510's real gain and saturation at 902–928 MHz. Qorvo's evaluation
  board is tuned 2 % lower.
- **The antenna detector** (ratio, 20 Oct): the trip ratio (0.35) and the
  FWD_DET minimum (50 mV) are **provisional**, picked from the RF sim's
  study 8 while it was still being worked on; the fallback's absolute
  thresholds are the old single-detector ones and do not fit the new
  detector (see *Missing-antenna cut-off*). On the bench: FWD_DET and REFL_DET with a good
  antenna, a VSWR-2 load and an open U.FL, at 27, 30 and 35 dBm, hot and
  cold, over several cable lengths; set `OFFGRID_ANT_RATIO_MAX_PCT`,
  `OFFGRID_FWD_MIN_MV` (and the fallback's `OFFGRID_REFL_V30_MV` / `_V35_MV`
  / `_TC_UV_PER_C`) from that. Also check the 750 µs sample point against
  the real PA_EN-to-RF delay (the TLV75528's start-up), and that dropping
  PA_EN mid-packet is clean.
- **The soft start**:
  - that the QPA9510 behaves at 2.25 V (stable, no oscillation, ≤ 30 dBm at
    +20 dBm drive). Its data sheet was not at hand here: the model only
    scales Psat by 20·log(VPA), and every earlier use of the amplifier was at
    2.7 V or more. If 2.25 V is outside its range, either raise
    `OFFGRID_SOFTSTART_VPA_MV` and accept more than 1 W at full drive, or
    lower the drive of high-power packets;
  - that a receiver at the edge of range still decodes a packet whose level
    rises by ~4–5 dB during the preamble (SHORT_TURBO first: the step ends
    ~1 ms before the preamble does);
  - the timing estimates: the I2C write (~0.4 ms at 100 kHz), the TPS63810's
    1 V/ms slew under the amplifier's load, the SAADC readings;
  - the antenna switch's stress during the first ~0.9 ms at ≤ 1 W into an
    open U.FL, which this design assumes is safe (the RF sim's finding).
- **The power caps**: the temperature table is sim/thermal (6-layer board,
  heat fixes, gap pad), and the TMP1075 lags the amplifier case; the battery
  table is sim/burst with an ohmic cell model, and the firmware's R_int
  estimate uses a modelled, not measured, current. Bench: bursts from worn
  and cold cells.
- **The BQ25185's TS bias** (38 µA, adapter present only) and whether it
  stays on with /CE high; whether a 20 ms /CE toggle restarts the TS/MR
  button timer; the NTC's B value (the charger is specified for 3435 K, the
  part is 3380 K).
- **The cell test**: how fast BAT_P really decays with /CE high and no cell
  (the 2.0 V threshold after 1 s), how often STAT2 toggles with no cell, and
  the latch-clearing sequence itself (sim/README.md asks for a bench test).
- Whether the TPS2121 + TPS63810 come up within the 5 ms that `initVariant()`
  waits. Retries cover about 15 ms; after that the main-loop check takes
  over.
- Whether the TPS63810 keeps its registers while EN stays high and the mux
  only dips, and through a PA_SRC_SYS switch-over. The 2 s re-check covers
  it if not.
- TCXO start-up at 2.2 V; RX sensitivity with the LNA on and off.
- The battery ADC multiplier (1.667 from the divider; RAK uses an empirical
  1.73). Calibrate with `power.adc_multiplier_override`; the variant's own
  cell readings use the same multiplier.
- The TX ramp. The TLV75528 control-voltage LDO starts when TXEN rises, and
  the SX1262 ramps in 200 µs. If the first symbols come out low on the
  spectrum analyser, add `SX126X_PA_RAMP_US` (as the T-Beam 1W does).

**Known limitations in this version:**

- **The amplifier supply stays on whenever the board is on.** This costs about
  0.3 mA for the power mux plus 13 µA for the TPS63810. The patch's hooks
  could now switch PA_PWR_EN per packet, but the TPS63810 then needs
  re-programming and settling before every packet; not done.
- **No-cell on solar or drone power only**: the amplifier goes to SYS at
  1 W, but the MAX17608's 0.71 A limit was not simulated for a 1 W burst.
- **"Amplifier off" is not "low power":** there is no path around the
  amplifier, so the >75 °C, no-1-W-cell and antenna-fault states make the
  node practically silent until they clear.
- **A broken FWD_DET limits the node to 1 W.** Soft-started packets then
  never get a trusted ratio and stay at the soft-start level; the fallback
  still catches a missing antenna at the old (cable-length-dependent)
  thresholds.
- **GPS pins.** They float until the GPS starts, and again at shutdown
  (GPS_RESET is no longer wired to the processor; cycling GPS_EN resets the
  module). However, while Meshtastic switches GPS power off
  between fixes, its UART still holds GPS_TX high into the unpowered module
  (through 470 Ω). The Adafruit UART cannot be ended safely behind the GPS
  code's back, so fixing this needs a small core hook in `GPS::writePinEN()`.
- **The charge test reads STAT2 only.** A latched charger fault (both pins
  low) also reads as "charging".
- **The drone-port defaults need patch part 2.** Meshtastic wipes variant
  module defaults on first boot.
- **The I2C scan mislabels the TMP1075.** It logs 0x48 as an "FT6336U
  touchscreen". Nothing uses that driver on nRF52, so this is harmless.
- **The LNA battery saver is build-time only.** Meshtastic's run-time LNA
  switch (`fem_lna_mode`) exists only for its built-in FEM types.
- **USB IDs are placeholders.** Both the app (RAK's) and the bootloader
  (pid.codes test) need a real VID/PID.
