/*
 * OffGrid Devices Mesh Radio v1 (working name) - Meshtastic board variant.
 *
 * nRF52840-QIAA (bare chip, normal-voltage mode: VDD = VDDH = 3.3 V rail,
 * REG1 DC/DC fitted) + SX1262 (TCXO on DIO3, DIO2 drives the antenna switch)
 * + 15.9 dB pad + Qorvo QPA9510 amplifier (up to ~3 W) + BGA7L1BN6 LNA.
 *
 * Pin map source: mesh-radio/v1/src/circuit.py, mcu() (aQFN73 balls -> nets).
 * The SX1262 bus, I2C, LEDs and the drone UART pins are the RAK4631's, so
 * RAK4631 habits (and MeshCore's RAK port) carry over.
 *
 * Arduino pin numbers: P0.x = x, P1.x = 32 + x (identity g_ADigitalPinMap).
 *
 * Structure follows variants/nrf52840/rak4631 (Meshtastic v2.7.26).
 *
 * RF POWER - READ BEFORE CHANGING ANYTHING BELOW "LoRa":
 *  - US (unlicensed) mode is capped at 30 dBm conducted by the region limit
 *    plus the TX_GAIN_LORA table below.  The table is PROVISIONAL (a model,
 *    not a measurement) and errs towards too little power.
 *  - Temperature, the cell and the antenna detector can lower that further
 *    (or switch the amplifier off) per packet: variant.cpp, patch part 3.
 *  - Meshtastic v2.7.26 applies the table only at radio init, not after a
 *    settings change (SX126xInterface::reconfigure); until the board reboots
 *    the SX1262 then runs at SX126X_MAX_POWER.  Apply
 *    firmware/patches/0001-offgrid-mesh-radio-core-backports.patch before
 *    any US field use (see firmware/README.md).
 */

#ifndef _VARIANT_OFFGRID_MESH_RADIO_V1_
#define _VARIANT_OFFGRID_MESH_RADIO_V1_

/** Master clock frequency */
#define VARIANT_MCK (64000000ul)

#define USE_LFXO // 32.768 kHz crystal fitted (XL1/XL2)

/*
 * 32.768 kHz crystal accuracy, as declared to the SoftDevice.
 *
 * The Adafruit core hard-codes NRF_CLOCK_LF_ACCURACY_20_PPM for USE_LFXO in
 * AdafruitBluefruit::begin() (libraries/Bluefruit52Lib/src/bluefruit.cpp)
 * and has no option for it.  This crystal drifts about -150 ppm at -40 C and
 * -130 ppm at +85 C (sim/thermal, study 3), so declared as 20 ppm the
 * SoftDevice opens its receive windows too narrowly and Bluetooth
 * connections drop when the node is cold or hot.  Declare 250 ppm instead
 * (the SoftDevice then widens its windows; costs a little current in a
 * connection).
 *
 * How: every file that includes Arduino.h includes this header, bluefruit.cpp
 * included.  nrf_sdm.h is pulled in here first (its include guard then keeps
 * it from being read again), and the name the core uses is redefined to the
 * 250 ppm value.  Check with the -E output of bluefruit.cpp (firmware/README.md).
 */
#define OFFGRID_LFXO_ACCURACY_PPM 250
#ifndef __ASSEMBLER__
#include "nrf_sdm.h"
#undef NRF_CLOCK_LF_ACCURACY_20_PPM
#define NRF_CLOCK_LF_ACCURACY_20_PPM NRF_CLOCK_LF_ACCURACY_250_PPM // see above: the crystal is a 250 ppm one here
#endif

/*----------------------------------------------------------------------------
 *        Headers
 *----------------------------------------------------------------------------*/

#include "WVariant.h"

#ifdef __cplusplus
extern "C" {
#endif // __cplusplus

// Number of pins defined in PinDescription array
#define PINS_COUNT (48)
#define NUM_DIGITAL_PINS (48)
#define NUM_ANALOG_INPUTS (5)
#define NUM_ANALOG_OUTPUTS (0)

/*
 * LEDs (active high, as on the RAK4631)
 */
#define PIN_LED1 (32 + 3) // P1.03 LED_GREEN
#define LED_BLUE (32 + 4) // P1.04 LED_BLUE
#define LED_GREEN PIN_LED1
#define LED_NOTIFICATION LED_BLUE
#define LED_STATE_ON 1

/*
 * Buttons: user button P1.00 to ground, internal pull-up.  Reset button is on
 * nRESET (P0.18, pin reset set by the bootloader).
 */
#define PIN_BUTTON1 (32 + 0) // P1.00 BTN_USER, active low
#define BUTTON_NEED_PULLUP

/*
 * Analog pins.  analogRead() takes the GPIO number; the core maps it to AINx.
 * A0 = battery sense.  A1-A2 = expansion header IO1-IO2.  A3 = the
 * missing-antenna detector, A4 = the charger's battery NTC (both on the
 * board only; header pins 14 and 15, which were IO3/IO4, are not connected).
 */
#define PIN_A0 (5)  // P0.05 / AIN3  VBAT_SENSE
#define PIN_A1 (28) // P0.28 / AIN4  IO1 (expansion)
#define PIN_A2 (29) // P0.29 / AIN5  IO2 (expansion)
#define PIN_A3 (30) // P0.30 / AIN6  REFL_DET (missing-antenna detector)
#define PIN_A4 (31) // P0.31 / AIN7  CHG_TS (charger TS/MR pin, battery NTC)
#define PIN_A5 (0xff)
#define PIN_A6 (0xff)
#define PIN_A7 (0xff)

static const uint8_t A0 = PIN_A0;
static const uint8_t A1 = PIN_A1;
static const uint8_t A2 = PIN_A2;
static const uint8_t A3 = PIN_A3;
static const uint8_t A4 = PIN_A4;
static const uint8_t A5 = PIN_A5;
static const uint8_t A6 = PIN_A6;
static const uint8_t A7 = PIN_A7;
#define ADC_RESOLUTION 14

// P0.02/AIN0 is PA_SRC_SYS here, so there is no usable external reference pin.
#define PIN_AREF (0xff)
static const uint8_t AREF = PIN_AREF;

// NFC pins: the bootloader configures them as GPIO (UICR NFCPINS).
#define PIN_NFC1 (9)  // P0.09 CHG_CE_N
#define PIN_NFC2 (10) // P0.10 IO6 (expansion)

/*
 * Serial interfaces.
 *
 * Meshtastic's nRF52 code fixes the roles of the two hardware UARTs:
 *  - the GPS always uses Serial1 (GPS_SERIAL_PORT default, UARTE0);
 *  - the Serial module (Meshtastic API / text over a UART) always uses
 *    Serial2 (UARTE1), on the pins set in moduleConfig.serial.rxd/txd.
 * So the GPS add-on is Serial1 and the drone port is Serial2, although the
 * drone port sits on the RAK4631's Serial1 pins (P0.15 RX / P0.16 TX).
 * Drone-port settings: serial.enabled, rxd 15, txd 16, mode PROTO (README).
 */
#define PIN_SERIAL1_RX (19) // P0.19 GPS_RX  (from GPS TX)
#define PIN_SERIAL1_TX (20) // P0.20 GPS_TX  (to GPS RX)

#define PIN_SERIAL2_RX (15) // P0.15 DRONE_RX (from autopilot TELEM TX, JST-GH pin 2)
#define PIN_SERIAL2_TX (16) // P0.16 DRONE_TX (to autopilot TELEM RX, JST-GH pin 3)

// Drone port flow control (Pixhawk TELEM).  Meshtastic does not use hardware
// flow control; the variant holds RTS low ("ready") so an autopilot with
// RTS/CTS enabled still sends, and leaves CTS as an input.
#define PIN_DRONE_CTS (21) // P0.21 input  (autopilot RTS, JST-GH pin 5)
#define PIN_DRONE_RTS (22) // P0.22 output (autopilot CTS, JST-GH pin 4)

/*
 * SPI interfaces
 * SPI  = SX1262 (same pins as the RAK4631)
 * SPI1 = generic SPI display on the expansion header (optional, not enabled)
 */
#define SPI_INTERFACES_COUNT 2

#define PIN_SPI_MISO (32 + 13) // P1.13 LORA_MISO
#define PIN_SPI_MOSI (32 + 12) // P1.12 LORA_MOSI
#define PIN_SPI_SCK (32 + 11)  // P1.11 LORA_SCK

#define PIN_SPI1_MISO (11) // P0.11 DISP_MISO
#define PIN_SPI1_MOSI (8)  // P0.08 DISP_MOSI
#define PIN_SPI1_SCK (7)   // P0.07 DISP_SCK

static const uint8_t SS = (32 + 10); // P1.10 LORA_NSS
static const uint8_t MOSI = PIN_SPI_MOSI;
static const uint8_t MISO = PIN_SPI_MISO;
static const uint8_t SCK = PIN_SPI_SCK;

// Expansion-header display pins (for a future display env; nothing uses them yet)
#define PIN_DISP_CS (12)        // P0.12
#define PIN_DISP_DC (26)        // P0.26
#define PIN_DISP_RST (27)       // P0.27
#define PIN_DISP_BL (32 + 8)    // P1.08

/*
 * Wire interface: one shared bus, 4.7 k pull-ups on the board.
 *   0x48 TMP1075 (temperature beside the amplifier)
 *   0x75 TPS63810 (amplifier buck-boost)
 *   + anything plugged into the expansion header
 * Note: Meshtastic's I2C scanner logs 0x48 as "FT6336U touchscreen" (its
 * fallback for that address); nothing on nRF52 uses that driver, so it is
 * harmless.
 */
#define WIRE_INTERFACES_COUNT 1

#define PIN_WIRE_SDA (13) // P0.13 I2C_SDA
#define PIN_WIRE_SCL (14) // P0.14 I2C_SCL

/*
 * LoRa: SX1262, wired as on the RAK4631
 *
 * P1.10 NSS, P1.11 SCK, P1.12 MOSI, P1.13 MISO, P1.14 BUSY, P1.15 DIO1,
 * P1.06 NRESET.  DIO2 drives the SKY13330 antenna switch (high = transmit),
 * DIO3 powers the TCXO.
 *
 * External front end, through RadioLib's RF-switch pins:
 *   TXEN = PA_EN  (P1.07): enables the TLV75528 that makes the QPA9510's
 *                          2.8 V control voltage; amplifier in standby when low.
 *   RXEN = LNA_EN (P1.05): BGA7L1BN6 high = gain (~5 mA), low = bypass.
 * RadioLib drives TXEN high / RXEN low in transmit, TXEN low / RXEN high in
 * receive, both low in standby and sleep.
 *
 * Build with -D OFFGRID_LNA_BYPASS=1 for the battery-saver receive mode
 * (LNA always in bypass, about 5 mA less, about 7 dB less sensitive).
 */
#define USE_SX1262
#define SX126X_CS (32 + 10)    // P1.10 LORA_NSS
#define SX126X_DIO1 (32 + 15)  // P1.15 LORA_DIO1
#define SX126X_BUSY (32 + 14)  // P1.14 LORA_BUSY
#define SX126X_RESET (32 + 6)  // P1.06 LORA_NRESET
#define SX126X_TXEN (32 + 7)   // P1.07 PA_EN
#define PIN_LNA_EN (32 + 5)    // P1.05 LNA_EN
#if !defined(OFFGRID_LNA_BYPASS) || (OFFGRID_LNA_BYPASS == 0)
#define SX126X_RXEN PIN_LNA_EN
#endif

#define SX126X_DIO2_AS_RF_SWITCH
// TCXO rated 1.7-3.6 V: 2.2 V keeps margin above its minimum (1.8 V would not)
#define SX126X_DIO3_TCXO_VOLTAGE 2.2

// SX1262 drive cap.  The amplifier input is behind a 15.9 dB pad
// (68/150/68 R, 0805): at +20 dBm the first 68 R dissipates 73 mW (58 % of
// 0.125 W) and the QPA9510 sees about +4 dBm (abs. max +13 dBm).
#define SX126X_MAX_POWER 20

/*
 * PROVISIONAL TX gain table - replace with bench measurements.
 *
 * Entry i = antenna-port power minus SX1262 setting (dB) with the SX1262 at
 * i dBm, i = 0..21.  Used by RadioInterface::limitPower() in UNLICENSED mode
 * only; licensed (ham) mode skips it and the configured tx_power goes to the
 * SX1262 directly (capped at SX126X_MAX_POWER).
 *
 * Derived from a model (firmware/tools/pa_gain_table.py): 16.8 dB small-signal
 * gain from the SX1262 pin to the U.FL (QPA9510 33.8 dB - 15.9 dB pad -
 * 1.1 dB amplifier-to-U.FL loss from sim/rf), Rapp compression towards
 * ~35 dBm (the 4.0 V amplifier supply, the least compressed case), rounded
 * up.  So in the model a request is never exceeded at any amplifier supply,
 * and the US maximum (30 dBm) sets the SX1262 to +13 dBm: ~29.0 dBm at
 * 2.7 V, ~29.6 dBm at 4.0 V.  The lowest possible output is ~8 dBm (SX1262
 * minimum -9 dBm).  variant.cpp uses the same table to turn a power cap into
 * a highest SX1262 setting.
 */
#define NUM_PA_POINTS 22
#define TX_GAIN_LORA 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 16, 16, 15, 15, 14

/*
 * Amplifier power (see variant.cpp for the sequence)
 *
 * PA_PWR_EN (P1.01) high: TPS2121 power mux on and TPS63810 buck-boost
 *   enabled.  1 M pull-down: off until firmware wants it.  The TPS63810
 *   starts at 3.3 V (VOUT1 reset value) and loses its registers whenever its
 *   input goes away, so the variant writes VOUT1 after every enable and
 *   re-checks it every OFFGRID_PA_CHECK_MS.  Its VSEL is tied to GND: VOUT1.
 * PA_SRC_SYS (P0.02, 1 M pull-down): low = the mux takes the battery first
 *   (down to 2.60 V); high = an N-FET pulls the mux's PR1 low and it takes
 *   charger SYS.  Driven high with no cell fitted, or with USB in and a cell
 *   too weak for 1 W (sim/burst).
 *
 * Amplifier supply (VPA) set points, mV.  VOUT1 code = (V - 1.8 V) / 25 mV.
 */
#define PIN_PA_PWR_EN (32 + 1) // P1.01 PA_PWR_EN
#define PIN_PA_EN SX126X_TXEN  // P1.07 PA_EN (amplifier control-voltage LDO), 100 k pull-down
#define PIN_PA_SRC_SYS (2)     // P0.02 PA_SRC_SYS (was PA_VSEL before the 19 Oct power-path rework)

#define TPS63810_ADDR 0x75
#define TMP1075_ADDR 0x48

#ifndef OFFGRID_PA_VOUT_US_MV
#define OFFGRID_PA_VOUT_US_MV 2700 // unlicensed: enough for 30 dBm, less current
#endif
#ifndef OFFGRID_PA_VOUT_LICENSED_MV
#define OFFGRID_PA_VOUT_LICENSED_MV 3600 // licensed: ~34 dBm; QPA9510 10:1 VSWR rating holds at 3.6 V
#endif
// Opt-in 4.0 V (~35 dBm) for a known-good antenna only: build with
// -D OFFGRID_PA_ALLOW_4V0=1.  Licensed mode then runs the amplifier at 4.0 V.
#if defined(OFFGRID_PA_ALLOW_4V0) && (OFFGRID_PA_ALLOW_4V0 == 1)
#undef OFFGRID_PA_VOUT_LICENSED_MV
#define OFFGRID_PA_VOUT_LICENSED_MV 4000
#endif
#ifndef OFFGRID_PA_CHECK_MS
#define OFFGRID_PA_CHECK_MS 2000 // how often the main loop re-checks the TPS63810, TMP1075 and charger NTC
#endif

/*
 * Power caps (variant.cpp).  Each is a ceiling on the power at the U.FL in
 * dBm; the lowest one in force wins.  A cap lowers both the SX1262 setting
 * for each packet (through the TX_GAIN_LORA table, needs patch 0001 part 3)
 * and the amplifier supply (Psat(VPA) = cap, never below 2.7 V).  In US mode
 * the request is already 30 dBm at most, so only "amplifier off" changes it.
 *
 * Board temperature (TMP1075 beside the amplifier), from sim/thermal's
 * follow-up table for the 6-layer board with the heat fixes and the gap pad.
 * Going back up needs OFFGRID_TCAP_HYST_C of cooling.
 *   up to 45 C   the configured maximum
 *   45-60 C      33 dBm (2 W)
 *   60-75 C      30 dBm (1 W)
 *   above 75 C   amplifier off: supply at its minimum, PA_EN held low; packets
 *                still go out, but only what leaks through the switched-off
 *                amplifier (there is no bypass path).  Back on below 70 C.
 * The TMP1075's own ALERT output (comparator, 75 C / 70 C) does the same,
 * so the cut-off holds even if the I2C reading fails.  No reading at all:
 * 30 dBm.
 */
#ifndef OFFGRID_TCAP_WARM_C
#define OFFGRID_TCAP_WARM_C 45
#endif
#ifndef OFFGRID_TCAP_WARM_DBM
#define OFFGRID_TCAP_WARM_DBM 33
#endif
#ifndef OFFGRID_TCAP_HOT_C
#define OFFGRID_TCAP_HOT_C 60
#endif
#ifndef OFFGRID_TCAP_HOT_DBM
#define OFFGRID_TCAP_HOT_DBM 30
#endif
#ifndef OFFGRID_TCAP_HYST_C
#define OFFGRID_TCAP_HYST_C 3
#endif

// TMP1075 beside the amplifier: ALERT (open drain, active low, comparator
// mode) asserts at OFFGRID_PA_TEMP_HIGH_C and clears below
// OFFGRID_PA_TEMP_LOW_C.  While it is asserted the amplifier is off.
#define PIN_TEMP_ALERT (6) // P0.06 TEMP_ALERT, 100 k pull-up
#ifndef OFFGRID_PA_TEMP_HIGH_C
#define OFFGRID_PA_TEMP_HIGH_C 75
#endif
#ifndef OFFGRID_PA_TEMP_LOW_C
#define OFFGRID_PA_TEMP_LOW_C 70
#endif

/*
 * Battery caps (variant.cpp): sim/burst/results.txt, the highest level that
 * runs without a brown-out, a protector trip or a TPS63810 reset, by cell
 * voltage (idle, between packets), cell temperature and the cell's R_int at
 * 25 C (estimated from the sag under each packet of 40 ms or more at 29 dBm or
 * more; 150 mOhm assumed until then).  Where the table says not even 1 W, the
 * amplifier is off - unless USB is in, when PA_SRC_SYS moves it to charger
 * SYS at OFFGRID_SYS_CAP_DBM (1.6 W and up exceed the charger's 1.05 A input).
 */
#ifndef OFFGRID_SYS_CAP_DBM
#define OFFGRID_SYS_CAP_DBM 30
#endif
#ifndef OFFGRID_BATT_PATH_MOHM
#define OFFGRID_BATT_PATH_MOHM 90 // plug + leads, reverse FET, protector FETs and sense: not part of the table's R_int
#endif

/*
 * No-cell detection and the reverse-FET latch (sim/README.md, residual risk).
 * With external power in, /CE is held high for OFFGRID_CELL_TEST_MS; with no
 * cell, BAT_P falls (below OFFGRID_NOCELL_MV) and the latch clears.  Run when
 * external power appears, when STAT2 toggles (the charger's no-battery
 * signature), and every OFFGRID_NOCELL_RETEST_MS while there is no cell.
 */
#ifndef OFFGRID_CELL_TEST_MS
#define OFFGRID_CELL_TEST_MS 1000
#endif
#ifndef OFFGRID_NOCELL_MV
#define OFFGRID_NOCELL_MV 2000
#endif
#ifndef OFFGRID_NOCELL_RETEST_MS
#define OFFGRID_NOCELL_RETEST_MS 60000
#endif
#ifndef OFFGRID_EXT_IN_MIN_MV
#define OFFGRID_EXT_IN_MIN_MV 4000 // solar / drone input counts as present above this (MAX17608 UVLO 4.0 V)
#endif

/*
 * Missing-antenna detector (sim/rf/coupler.txt): a printed coupler beside the
 * U.FL feed, a BAT15 diode, 1 nF || 100 k, into P0.30/AIN6.  It reads the
 * reflected wave, so the threshold scales with the power sent.
 * The SAADC samples it OFFGRID_REFL_SAMPLE_US after the transmission starts
 * (it settles ~0.3 ms after PA_EN; sample at 0.5-1 ms), 40 us acquisition.
 * Threshold at the U.FL power P (dBm): V30 at 30 dBm, V35 at 35 dBm,
 * interpolated in dB (log of the voltage, linear in dBm), plus
 * OFFGRID_REFL_TC_UV_PER_C per degree C of board temperature above 25 C.
 * Worst cases (-40..85 C, 902-928 MHz, every phase): VSWR-2 antenna 0.24 V,
 * missing 0.52 V at 30 dBm; 0.47 / 1.12 V at 35 dBm.
 * Not checked below OFFGRID_REFL_MIN_DBM, where a missing antenna harms nothing.
 * Above the threshold: amplifier off at once, for this packet and the ones
 * after; one try at 1 W after OFFGRID_ANT_RETRY_MS, doubling up to
 * OFFGRID_ANT_RETRY_MAX_MS while the fault stays.
 */
#define PIN_REFL_DET (30) // P0.30 / AIN6 REFL_DET
#define REFL_DET_AIN 7     // SAADC PSELP value for AIN6 (AINx = x + 1)
#ifndef OFFGRID_REFL_SAMPLE_US
#define OFFGRID_REFL_SAMPLE_US 750
#endif
#ifndef OFFGRID_REFL_V30_MV
#define OFFGRID_REFL_V30_MV 350
#endif
#ifndef OFFGRID_REFL_V35_MV
#define OFFGRID_REFL_V35_MV 730
#endif
#ifndef OFFGRID_REFL_TC_UV_PER_C
#define OFFGRID_REFL_TC_UV_PER_C 1400
#endif
#ifndef OFFGRID_REFL_MIN_DBM
#define OFFGRID_REFL_MIN_DBM 27
#endif
#ifndef OFFGRID_ANT_RETRY_MS
#define OFFGRID_ANT_RETRY_MS 30000
#endif
#ifndef OFFGRID_ANT_RETRY_MAX_MS
#define OFFGRID_ANT_RETRY_MAX_MS 600000
#endif
#ifndef OFFGRID_ANT_PROBE_DBM
#define OFFGRID_ANT_PROBE_DBM 30 // the retry runs at 1 W
#endif

/*
 * GPS add-on (JST-SH 6): switched 3.3 V (TPS22916, active high), UART, PPS,
 * RESET.  The variant leaves GPS_RESET as an input (not given to Meshtastic)
 * so the processor never drives it into an unpowered module.
 */
#define PIN_GPS_EN (23)        // P0.23 GPS_EN, active high
#define GPS_EN_ACTIVE 1
#define PIN_GPS_PPS (17)       // P0.17 GPS_PPS
#define PIN_GPS_RESET_OFFGRID (32 + 9) // P1.09 GPS_RESET (deliberately not PIN_GPS_RESET)
#define GPS_RX_PIN PIN_SERIAL1_RX
#define GPS_TX_PIN PIN_SERIAL1_TX
#define GPS_SERIAL_PORT Serial1

/*
 * Charger (BQ25185) and inputs
 */
#define PIN_CHG_CE_N (9)     // P0.09 /CE: low = charging on (100 k pull-down too)
#define PIN_CHG_STAT1 (24)   // P0.24 STAT1, 10 k pull-up
#define PIN_CHG_STAT2 (25)   // P0.25 STAT2, 10 k pull-up
// STAT1 high + STAT2 low = charging (BQ25185 table 6-2).  Both low is a
// latched fault, which this simple test also reads as "charging".
#define EXT_CHRG_DETECT PIN_CHG_STAT2
#define EXT_CHRG_DETECT_VALUE LOW
// SOLAR_OK / DRONE_OK: the input voltage / 16 (1.5 M / 100 k) for the ADC,
// read to tell whether external power is in (5 V -> 0.31 V, 10 V -> 0.63 V)
#define PIN_SOLAR_OK (4)     // P0.04 / AIN2 SOLAR_OK
#define PIN_DRONE_OK (3)     // P0.03 / AIN1 DRONE_OK

/*
 * Charging window (variant.cpp).  The NTC (10 k, B 3380, beside the battery
 * plug) sits on the charger's TS/MR pin, which the BQ25185 biases with
 * ITSMR = 38 uA while an input is present: V = 38 uA x R_NTC, so 1.07 V at
 * 0 C, 0.38 V at 25 C, 0.19 V at 45 C, 0.12 V at 60 C.  P0.31/AIN7 reads it.
 * Firmware holds /CE high (charging off) below OFFGRID_CHG_MIN_C and above
 * OFFGRID_CHG_MAX_C, and lets it go again OFFGRID_CHG_HYST_C inside the
 * window.  The charger's own window (about 1-60 C) stays as the backstop,
 * and is all there is while the processor is off.
 */
#define PIN_CHG_TS (31)   // P0.31 / AIN7 CHG_TS
#define CHG_TS_AIN 8      // SAADC PSELP value for AIN7
#ifndef OFFGRID_TS_VALID_MIN_MV
#define OFFGRID_TS_VALID_MIN_MV 50 // below: no TS bias (no input), or a cell above ~80 C
#endif
#ifndef OFFGRID_CHG_MIN_C
#define OFFGRID_CHG_MIN_C 0
#endif
#ifndef OFFGRID_CHG_MAX_C
#define OFFGRID_CHG_MAX_C 45
#endif
#ifndef OFFGRID_CHG_HYST_C
#define OFFGRID_CHG_HYST_C 3
#endif
#define OFFGRID_NTC_R25 10000.0f  // ohm
#define OFFGRID_NTC_BETA 3380.0f  // K (Murata NCP15XH103F03RC, B25/50)
#define OFFGRID_TS_BIAS_UA 38.0f  // BQ25185 ITSMR, adapter present (36.5-39.5 uA)

// USB VBUS detection through the nRF52840 POWER peripheral (VBUS = USB_5V)
#define NRF_APM

/*
 * Battery: 1 M / 1.5 M divider from BAT_P to P0.05/AIN3 (100 nF at the pin),
 * as on the RAK4631.  Multiplier 2.5 / 1.5 = 1.667 (RAK uses an empirical
 * 1.73; calibrate on built boards with power.adc_multiplier_override).
 */
#define BATTERY_PIN PIN_A0
#define BATTERY_SENSE_RESOLUTION_BITS 12
#define BATTERY_SENSE_RESOLUTION 4096.0
#undef AREF_VOLTAGE
#define AREF_VOLTAGE 3.0
#define VBAT_AR_INTERNAL AR_INTERNAL_3_0
#define ADC_MULTIPLIER 1.667

// Wake from low-battery system-off when AIN3 rises above 11/16 VDD
// (VBAT ~3.76 V), same divider and threshold as the RAK4631.
#define BATTERY_LPCOMP_INPUT NRF_LPCOMP_INPUT_3
#define BATTERY_LPCOMP_THRESHOLD NRF_LPCOMP_REF_SUPPLY_11_16

/*
 * Expansion header spare pins: IO1 (pin 12), IO2 (13), IO5 (16), IO6 (17).
 * Pins 14 and 15 (IO3/IO4 before) are not connected: P0.30 and P0.31 now
 * read the antenna detector and the charger's NTC on the board.
 */
#define PIN_IO1 (28)      // P0.28 / AIN4
#define PIN_IO2 (29)      // P0.29 / AIN5
#define PIN_IO5 (32 + 2)  // P1.02
#define PIN_IO6 (10)      // P0.10 (NFC2)

#ifdef __cplusplus
}
#endif

/*----------------------------------------------------------------------------
 *        Arduino objects - C++ only
 *----------------------------------------------------------------------------*/

#endif
