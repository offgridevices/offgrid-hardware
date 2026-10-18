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
 * A0 = battery sense.  A1-A4 = expansion header IO1-IO4.
 */
#define PIN_A0 (5)  // P0.05 / AIN3  VBAT_SENSE
#define PIN_A1 (28) // P0.28 / AIN4  IO1 (expansion)
#define PIN_A2 (29) // P0.29 / AIN5  IO2 (expansion)
#define PIN_A3 (30) // P0.30 / AIN6  IO3 (expansion)
#define PIN_A4 (31) // P0.31 / AIN7  IO4 (expansion)
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

// P0.02/AIN0 is PA_VSEL here, so there is no usable external reference pin.
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
 * Derived from a model (firmware/tools/pa_gain_table.py): 18 dB small-signal
 * gain from the SX1262 pin to the antenna (QPA9510 33.8 dB - 15.9 dB pad),
 * Rapp compression towards ~35 dBm (the 4.0 V amplifier supply, the least
 * compressed case), rounded up.  So in the model a request is never exceeded
 * at any amplifier supply, and the US maximum (30 dBm) sets the SX1262 to
 * +12 dBm: ~29.1 dBm at 2.7 V, ~29.8 dBm at 4.0 V.  The lowest possible
 * output is ~9 dBm (SX1262 minimum -9 dBm).
 */
#define NUM_PA_POINTS 22
#define TX_GAIN_LORA 18, 18, 18, 18, 18, 18, 18, 18, 18, 18, 18, 18, 18, 18, 18, 18, 17, 17, 16, 16, 15, 14

/*
 * Amplifier power (see variant.cpp for the sequence)
 *
 * PA_PWR_EN (P1.01) high: TPS2121 power mux on (battery first, charger SYS
 *   when there is no cell) and TPS63810 buck-boost enabled.  1 M pull-down:
 *   off until firmware wants it.  The TPS63810 starts at 3.3 V (VOUT1 reset
 *   value) and loses its registers whenever its input goes away, so the
 *   variant writes VOUT1 after every enable and re-checks it every
 *   OFFGRID_PA_CHECK_MS.
 * PA_VSEL (P0.02): selects VOUT1 (low) / VOUT2 (high).  Held low.
 *
 * Amplifier supply (VPA) set points, mV.  VOUT1 code = (V - 1.8 V) / 25 mV.
 */
#define PIN_PA_PWR_EN (32 + 1) // P1.01 PA_PWR_EN
#define PIN_PA_VSEL (2)        // P0.02 PA_VSEL
#define PIN_PA_EN SX126X_TXEN  // P1.07 PA_EN (amplifier control-voltage LDO)

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
#ifndef OFFGRID_PA_VOUT_HOT_MV
#define OFFGRID_PA_VOUT_HOT_MV OFFGRID_PA_VOUT_US_MV // supply while TEMP_ALERT is active
#endif
#ifndef OFFGRID_PA_CHECK_MS
#define OFFGRID_PA_CHECK_MS 2000 // how often the main loop re-checks the TPS63810 and TMP1075
#endif

// TMP1075 beside the amplifier: ALERT (open drain, active low, comparator
// mode) asserts at OFFGRID_PA_TEMP_HIGH_C and clears below OFFGRID_PA_TEMP_LOW_C.
#define PIN_TEMP_ALERT (6) // P0.06 TEMP_ALERT, 100 k pull-up
#ifndef OFFGRID_PA_TEMP_HIGH_C
#define OFFGRID_PA_TEMP_HIGH_C 80
#endif
#ifndef OFFGRID_PA_TEMP_LOW_C
#define OFFGRID_PA_TEMP_LOW_C 70
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
#define PIN_SOLAR_OK (4)     // P0.04 solar eFuse AUXOFF ("input good"), 1 M pull-up
#define PIN_DRONE_OK (3)     // P0.03 drone 5 V eFuse AUXOFF, 1 M pull-up

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
 * Expansion header spare pins
 */
#define PIN_IO1 (28)      // P0.28 / AIN4
#define PIN_IO2 (29)      // P0.29 / AIN5
#define PIN_IO3 (30)      // P0.30 / AIN6
#define PIN_IO4 (31)      // P0.31 / AIN7
#define PIN_IO5 (32 + 2)  // P1.02
#define PIN_IO6 (10)      // P0.10 (NFC2)

#ifdef __cplusplus
}
#endif

/*----------------------------------------------------------------------------
 *        Arduino objects - C++ only
 *----------------------------------------------------------------------------*/

#endif
