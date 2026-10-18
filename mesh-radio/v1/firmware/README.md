# Mesh Radio v1: firmware

The Meshtastic board variant for Mesh Radio v1, plus the Adafruit bootloader
board definition it needs. It lives here until it goes upstream.

> **Status (18 Oct 2026): it compiles, and nothing has run on hardware.**
> No board exists yet. The variant builds against Meshtastic **v2.7.26.54e0d8d**
> (the latest stable release and the version Cairn pins), with and without the
> core patch. The bootloader builds against Adafruit_nRF52_Bootloader 0.11.0.
> **The transmit power table is a model, not a measurement.** Nothing above
> 1 W is used until it has been measured on the bench.

| Path | What it is |
|---|---|
| `variant/variant.h` | Pin map, radio and front-end settings, the **provisional** gain table, battery and charger settings |
| `variant/variant.cpp` | Board start-up and amplifier power: the TPS63810 supply, licensed/unlicensed levels, thermal back-off, shutdown |
| `variant/platformio.ini` | The `offgrid_mesh_radio_v1` build environment |
| `patches/0001-offgrid-mesh-radio-core-backports.patch` | A two-part change to Meshtastic core. **Part 1 is required before any US field use** (see *The US 1 W rule*). |
| `bootloader/offgrid_mesh_radio_v1/` | `board.h`, `board.mk`, `board.cmake` and `pinconfig.c` for Adafruit_nRF52_Bootloader |
| `tools/pa_gain_table.py` | Builds the gain table from the amplifier model. Replace the model with bench data later. |

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

**Result on 18 Oct 2026:** `pio run -e offgrid_mesh_radio_v1` gave SUCCESS
both on unpatched v2.7.26 and with the patch applied. The `.uf2` is 1,456,640
bytes. The variant adds no compiler warnings beyond those the stock `rak4631`
build already shows.

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
| PA_VSEL | P0.02 | 2 | Held low: VOUT1 |
| I2C SDA / SCL | P0.13 / P0.14 | 13 / 14 | TMP1075 at 0x48, TPS63810 at 0x75 |
| TEMP_ALERT | P0.06 | 6 | TMP1075 ALERT, active low |
| Drone RX / TX (Serial2) | P0.15 / P0.16 | 15 / 16 | The RAK4631's Serial1 pins |
| Drone CTS / RTS | P0.21 / P0.22 | 21 / 22 | RTS held low (ready); CTS not used |
| GPS RX / TX (Serial1) | P0.19 / P0.20 | 19 / 20 | |
| GPS_EN / PPS / RESET | P0.23 / P0.17 / P1.09 | 23 / 17 / 41 | EN active high; RESET left as an input |
| LED green / blue | P1.03 / P1.04 | 35 / 36 | Active high |
| User button | P1.00 | 32 | Active low, internal pull-up |
| Battery sense | P0.05 / AIN3 | 5 | 1 M / 1.5 M divider, multiplier 1.667 |
| CHG_CE_N / STAT1 / STAT2 | P0.09 / P0.24 / P0.25 | 9 / 24 / 25 | /CE driven low (charging on). STAT2 low = charging. |
| SOLAR_OK / DRONE_OK | P0.04 / P0.03 | 4 / 3 | eFuse "input good" |
| Display SPI1 (header) | SCK P0.07, MOSI P0.08, MISO P0.11, CS P0.12, DC P0.26, RST P0.27, BL P1.08 | | Defined, but no display is turned on |
| Expansion IO1–IO6 | P0.28–P0.31 (AIN4–7), P1.02, P0.10 | | |

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
pad into the QPA9510, which has fixed gain. The net gain from the SX1262 pin
to the antenna port is about 18 dB.

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
  - The amplifier supply sets the ceiling: 3.6 V gives about 34 dBm. With
    `OFFGRID_PA_ALLOW_4V0=1`, 4.0 V gives about 35 dBm.
  - The variant switches the supply within 2 s of the licence setting
    changing.
- **Thermal back-off.** The TMP1075 beside the amplifier raises ALERT at
  80 °C and clears it below 70 °C. While ALERT is active, the supply drops to
  the US level (2.7 V). That lowers the licensed-mode ceiling to about
  31.5 dBm. In US mode the board is already at that level, so back-off
  changes nothing there; see *Not done yet*.

**Supply sequencing.** All of this is in `variant.cpp`.

1. `initVariant()` (before `setup()`) turns PA_PWR_EN on, waits 5 ms and
   programs the TPS63810 to 2.7 V: CONTROL = 0x24 (enabled, ramp-PWM), and
   VOUT1 = (V − 1.8 V) / 25 mV, which is 0x24 for 2.7 V, 0x48 for 3.6 V and
   0x58 for 4.0 V.
2. `lateInitVariant()` (once the config is loaded) sets the licensed or
   unlicensed level and the TMP1075 limits.
3. The main loop re-reads the TPS63810 every 2 s and writes it again if it
   has reset. It resets to its 3.3 V default whenever the power mux drops its
   input.
4. `variant_shutdown()` turns everything off before system-off.

**Why a failure stays safe.** Every way this can fail leaves the board safe.
An unprogrammed TPS63810 sits at 3.3 V: that is below the licensed level,
and the US table holds at any supply.

This needed no change to Meshtastic core: it uses the existing
`initVariant`, `lateInitVariant`, `variant_nrf52LoopHook` and
`variant_shutdown` hooks.

### The power table (PROVISIONAL: a model, to be replaced by bench measurements)

`TX_GAIN_LORA = 18 ×16, 17, 17, 16, 16, 15, 14`. Entry *i* is the gain with
the SX1262 at *i* dBm.

**The model.**

- Gain: 33.8 dB (QPA9510) − 15.9 dB (pad) = 18 dB small-signal. The ~1 dB of
  filter and switch loss is deliberately *not* subtracted.
- Compression: Rapp, p = 2, towards a saturated output of about 35 dBm at
  4.0 V. That ceiling scales as 20·log(V): about 34 dBm at 3.6 V and
  31.5 dBm at 2.7 V.
- Rounding: computed on the 4.0 V curve and rounded up. So, in the model, a
  request is never exceeded at any amplifier supply.

| Requested (US mode) | SX1262 set to | Antenna, VPA 2.7 V | 3.3 V | 4.0 V |
|---|---|---|---|---|
| ≤ 8 dBm | −9 (its minimum) | 9.0 | 9.0 | 9.0 |
| 20 dBm | 2 | 20.0 | 20.0 | 20.0 |
| 24 dBm | 6 | 23.9 | 24.0 | 24.0 |
| 27 dBm | 9 | 26.7 | 26.9 | 26.9 |
| **30 dBm (US maximum)** | **12** | **29.1** | 29.6 | 29.8 |

| Licensed mode: SX1262 set to | VPA 3.6 V (default ceiling) | 4.0 V (opt-in) |
|---|---|---|
| 10 dBm | 27.9 | 27.9 |
| 14 dBm | 31.3 | 31.5 |
| 16 dBm | 32.5 | 32.9 |
| 20 dBm (the cap; `tx_power` 0 or ≥ 20) | 33.8 | 34.5 |

`python3 tools/pa_gain_table.py` reprints both tables.

**Replacing the model with measurements.**

1. Measure the antenna-port power for SX1262 settings 0–20 dBm at 2.7 V and
   at the licensed ceiling. Use the Meshtastic licensed mode so that
   `tx_power` maps directly to the SX1262 setting.
2. Take gain[i] = ceil(max over supplies of (P_out − i)).
3. Paste the result into `variant.h`.
4. Then set `OFFGRID_PA_VOUT_US_MV` to the lowest supply that still reaches
   30 dBm. The model's 2.7 V reaches only about 29.1 dBm.

## The US 1 W rule

FCC Part 15.247 limits 902–928 MHz to **1 W (30 dBm) conducted**, with up to
6 dBi of antenna gain (36 dBm EIRP). Above 6 dBi, the conducted power must
drop dB for dB.

**How the firmware enforces it.** In unlicensed mode:

- Meshtastic's US region limit caps any request at 30 dBm;
- the gain table turns that into an SX1262 setting that, in the model, gives
  ≤ 30 dBm at any amplifier supply;
- the supply is held at 2.7 V, so even a full +20 dBm drive saturates near
  31.5 dBm, not 34–35 dBm.

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
- Whether the TPS2121 + TPS63810 come up within the 5 ms that `initVariant()`
  waits. Retries cover about 15 ms; after that the main-loop check takes
  over.
- Whether the TPS63810 keeps its registers while EN stays high and the mux
  only dips. The 2 s re-check covers it if not.
- TCXO start-up at 2.2 V; RX sensitivity with the LNA on and off.
- The battery ADC multiplier (1.667 from the divider; RAK uses an empirical
  1.73). Calibrate with `power.adc_multiplier_override`.
- The TX ramp. The TLV75528 control-voltage LDO starts when TXEN rises, and
  the SX1262 ramps in 200 µs. If the first symbols come out low on the
  spectrum analyser, add `SX126X_PA_RAMP_US` (as the T-Beam 1W does).

**Known limitations in this version:**

- **The amplifier supply stays on whenever the board is on.** This costs about
  0.3 mA for the power mux plus 13 µA for the TPS63810. Switching it per
  transmission needs a hook in `SX126xInterface::configHardwareForSend()`,
  which is a core change and is not in the patch. The plan's "mux only while
  transmitting" saving is therefore not realised yet.
- **GPS pins.** They float until the GPS starts, and again at shutdown, and
  GPS_RESET is never driven. However, while Meshtastic switches GPS power off
  between fixes, its UART still holds GPS_TX high into the unpowered module
  (through 470 Ω). The Adafruit UART cannot be ended safely behind the GPS
  code's back, so fixing this needs a small core hook in `GPS::writePinEN()`.
- **Thermal back-off only lowers the licensed ceiling.** Cutting power in US
  mode, or holding the 0–45 °C charging window through CHG_CE_N, is not
  implemented.
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
