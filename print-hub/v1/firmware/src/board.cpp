#include "board.h"

#include <stdio.h>

// The USB-PD sink controller (Hynetek HUSB238) on I2C: it asks the charger
// for 9 V by itself (its VSET resistor) and reports the contract here
// (register map: Hynetek "HUSB238 Register Information" rev 1.1).
namespace husb238 {
constexpr uint8_t ADDR = 0x08;
constexpr uint8_t PD_STATUS0 = 0x00;   // [7:4] contract volts, [3:0] contract amps
constexpr uint8_t PD_STATUS1 = 0x01;   // [6] attached, [5:3] PD response, [2] 5 V, [1:0] Type-C 5 V current
constexpr uint8_t SRC_PDO_9V = 0x03;   // [7] the charger offers 9 V, [3:0] at this current
constexpr uint8_t SRC_PDO = 0x08;      // [7:4] which offer to request
constexpr uint8_t GO_COMMAND = 0x09;
constexpr uint8_t SELECT_9V = 0x20;
constexpr uint8_t GO_REQUEST = 0x01;
const uint16_t VOLTS_MV[16] = {0, 5000, 9000, 12000, 15000, 18000, 20000};
const uint16_t AMPS_MA[16] = {500, 700, 1000, 1250, 1500, 1750, 2000, 2250,
                              2500, 2750, 3000, 3250, 3500, 4000, 4500, 5000};
const uint16_t TYPEC_MA[4] = {500, 1500, 2400, 3000};   // default USB, 1.5 A, 2.4 A, 3 A
}  // namespace husb238

// the buck's own rating, and what the board itself uses from the rail
constexpr uint16_t BUCK_MAX_MA = 5000;
constexpr uint16_t BOARD_MA = 150;
constexpr float BUCK_EFF = 0.90f;
constexpr float RAIL_V = 5.15f;

void Board::begin() {
  // ports off before anything else (each enable also has a pull-down, so
  // they are off during reset and flashing too)
  for (int p = 0; p < hub::NPORTS; p++) {
    digitalWrite(pins::EN[p], LOW);
    pinMode(pins::EN[p], OUTPUT);
    pinMode(pins::FLT[p], INPUT_PULLUP);
    analogSetPinAttenuation(pins::ISENSE[p], ADC_11db);
  }
  analogSetPinAttenuation(pins::VIN_SENSE, ADC_11db);
  analogSetPinAttenuation(pins::RAIL_SENSE, ADC_11db);
  pinMode(pins::BUTTON, INPUT_PULLUP);
  Wire.begin(pins::I2C_SDA, pins::I2C_SCL, 100000);
  leds_.begin();
  leds_.clear();
  leds_.show();
}

void Board::set_enable(int port, bool on) { digitalWrite(pins::EN[port], on ? HIGH : LOW); }

bool Board::fault(int port) { return digitalRead(pins::FLT[port]) == LOW; }

static uint16_t clamp16(float v) { return v < 0 ? 0 : v > 65535 ? 65535 : (uint16_t)(v + 0.5f); }

void Board::poll(uint32_t now) {
  for (int p = 0; p < hub::NPORTS; p++)
    ma_[p] = clamp16(analogReadMilliVolts(pins::ISENSE[p]) / scale::MV_PER_MA);
  vin_mv_ = clamp16(analogReadMilliVolts(pins::VIN_SENSE) * scale::VIN_DIV);
  rail_mv_ = clamp16(analogReadMilliVolts(pins::RAIL_SENSE) * scale::RAIL_DIV);
  if ((int32_t)(now - pd_at_) >= 0) {
    read_pd();
    pd_at_ = now + 1000;
  }
}

static bool read_reg(uint8_t reg, uint8_t *v) {
  Wire.beginTransmission(husb238::ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(husb238::ADDR, (uint8_t)1) != 1) return false;
  *v = Wire.read();
  return true;
}

static bool write_reg(uint8_t reg, uint8_t v) {
  Wire.beginTransmission(husb238::ADDR);
  Wire.write(reg);
  Wire.write(v);
  return Wire.endTransmission() == 0;
}

void Board::read_pd() {
  uint8_t s0, s1, pdo9;
  char buf[48];
  if (vin_mv_ < 4000) {                      // nothing on POWER IN
    pd_mv_ = pd_ma_ = 0;
    asked_ = false;
    contract_ = "none";
    return;
  }
  if (!read_reg(husb238::PD_STATUS0, &s0) || !read_reg(husb238::PD_STATUS1, &s1)) {
    pd_mv_ = pd_ma_ = 0;
    contract_ = "unknown (USB-PD chip not answering)";
    return;
  }
  // The VSET/ISET resistors ask for 9 V at 2 A, so a 20 W charger still
  // gives 9 V.  Once, after each plug-in, ask over I2C for the charger's
  // 9 V offer itself, which the chip then requests at its full current.
  if (!asked_ && read_reg(husb238::SRC_PDO_9V, &pdo9) && (pdo9 & 0x80)) {
    write_reg(husb238::SRC_PDO, husb238::SELECT_9V);
    write_reg(husb238::GO_COMMAND, husb238::GO_REQUEST);
    asked_ = true;
  }
  uint16_t mv = husb238::VOLTS_MV[s0 >> 4];
  if (((s1 >> 3) & 7) == 1 && mv) {          // USB-PD contract made
    pd_mv_ = mv;
    pd_ma_ = husb238::AMPS_MA[s0 & 15];
    snprintf(buf, sizeof buf, "%uV %.3gA USB-PD", mv / 1000, pd_ma_ / 1000.0);
  } else {                                   // a plain Type-C source: 5 V only
    pd_mv_ = 5000;
    pd_ma_ = husb238::TYPEC_MA[s1 & 3];
    snprintf(buf, sizeof buf, "5V %.3gA (no USB-PD)", pd_ma_ / 1000.0);
  }
  contract_ = buf;
  if (pd_mv_ < 9000) contract_ += ": needs a USB-PD charger with 9 V";
}

uint16_t Board::input_budget_ma() {
  // The buck needs 9 V or more to make 5.16 V: below that the ports get
  // nothing (a 5 V source would leave about 4.3 V on them).
  if (pd_mv_ < 9000 || vin_mv_ < 8000) return 0;
  // power in from the charger, through the buck at its efficiency, less
  // what the board uses, less 10 % margin, never over the buck's rating
  float watts = (pd_mv_ / 1000.0f) * (pd_ma_ / 1000.0f) * BUCK_EFF;
  float ma = (watts / RAIL_V * 1000.0f - BOARD_MA) * 0.9f;
  if (ma > BUCK_MAX_MA) ma = BUCK_MAX_MA;
  return clamp16(ma);
}

bool Board::button_pressed() {
  bool down = digitalRead(pins::BUTTON) == LOW;
  uint32_t now = millis();
  bool fired = false;
  if (down && !button_was_) button_at_ = now;
  if (!down && button_was_ && now - button_at_ > 30 && now - button_at_ < 2000) fired = true;
  button_was_ = down;
  return fired;
}
