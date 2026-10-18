// Print Hub v1: the pins and the hardware behind lib/hub's Hal.
//
// The pin numbers are ESP32-S3 GPIOs and must match the board
// (src/circuit.py): src/verify.py reads this file and checks every one.
#pragma once
#include <Adafruit_NeoPixel.h>
#include <Arduino.h>
#include <Wire.h>

#include "hub.h"

namespace pins {
// per port, USB1..USB5
constexpr uint8_t EN[hub::NPORTS] = {21, 10, 11, 12, 13};     // power switch enable, high = on
constexpr uint8_t FLT[hub::NPORTS] = {14, 15, 16, 17, 18};    // power switch fault, low = fault
constexpr uint8_t ISENSE[hub::NPORTS] = {1, 2, 4, 5, 6};      // current-sense amplifier out (ADC1)
constexpr uint8_t VIN_SENSE = 7;    // POWER IN voltage through a divider (ADC1)
constexpr uint8_t RAIL_SENSE = 8;   // the 5 V port rail through a divider (ADC1)
constexpr uint8_t NTC = 9;          // board temperature: NTC to ground, 10k up to 3.3 V (ADC1)
constexpr uint8_t LED_DATA = 38;    // WS2812B chain: status, then USB5 ... USB1
constexpr uint8_t I2C_SDA = 39;     // USB-PD sink controller
constexpr uint8_t I2C_SCL = 40;
constexpr uint8_t BUTTON = 0;       // BOOT button, low = pressed
}  // namespace pins

// the analogue scaling, from src/circuit.py's parts
namespace scale {
// current sense: shunt (ohm) x amplifier gain (V/V) -> volts per amp
constexpr float SHUNT_OHM = 0.020f;
constexpr float AMP_GAIN = 50.0f;
constexpr float MV_PER_MA = SHUNT_OHM * AMP_GAIN;   // 1.0 mV per mA
// dividers: (top + bottom) / bottom
constexpr float VIN_DIV = (100.0f + 15.0f) / 15.0f;
constexpr float RAIL_DIV = (100.0f + 100.0f) / 100.0f;
// board temperature: Murata NCP15XH103F03RC (10k at 25 C) under a 10k
// pull-up from the 3.3 V rail.  B25/85 = 3434 K: the curve is fitted where
// the thermal protection acts (75-100 C); at 25 C it reads ~0.3 K low
constexpr float NTC_R0_OHM = 10000.0f;
constexpr float NTC_B = 3434.0f;
constexpr float NTC_PULLUP_OHM = 10000.0f;
constexpr float NTC_SUPPLY_MV = 3300.0f;
}  // namespace scale

class Board : public hub::Hal {
 public:
  void begin();
  void poll(uint32_t now);
  void set_enable(int port, bool on) override;
  bool fault(int port) override;
  uint16_t port_ma(int port) override { return ma_[port]; }
  uint16_t input_budget_ma() override;
  int16_t board_temp_c10() override { return temp_c10_; }
  uint16_t input_mv() const { return vin_mv_; }
  uint16_t rail_mv() const { return rail_mv_; }
  std::string contract() const { return contract_; }
  void set_led(int i, uint32_t rgb) { leds_.setPixelColor(i, rgb); }
  void show_leds() { leds_.show(); }
  bool button_pressed();

 private:
  void read_pd();
  void read_ntc();
  Adafruit_NeoPixel leds_{hub::NPORTS + 1, pins::LED_DATA, NEO_GRB + NEO_KHZ800};
  uint16_t ma_[hub::NPORTS] = {};
  uint16_t vin_mv_ = 0, rail_mv_ = 0;
  uint16_t pd_mv_ = 0, pd_ma_ = 0;   // the charger's contract: volts and amps it offers
  std::string contract_ = "none";
  uint32_t pd_at_ = 0;
  int16_t temp_c10_ = hub::NO_TEMP;  // tenths of a degree C, NO_TEMP: open or shorted
  uint32_t ntc_at_ = 0;
  bool asked_ = false;               // asked for the 9 V offer since plug-in
  bool button_was_ = false;
  uint32_t button_at_ = 0;
};
