/*
 * OffGrid Devices Mesh Radio v1 (working name) - Meshtastic board variant.
 *
 * Board bring-up that Meshtastic's core does not know about:
 *   - nRF52840 REG1 DC/DC on (the inductors are fitted);
 *   - safe pin states before anything else runs (amplifier off, GPS off and
 *     its pins floating, charging on, LEDs off);
 *   - the amplifier supply: PA_PWR_EN on, TPS63810 programmed over I2C, and
 *     kept programmed (it forgets its registers when its input drops);
 *   - amplifier supply follows the licence state: 2.7 V unlicensed (US 1 W),
 *     3.6 V licensed (4.0 V only with -D OFFGRID_PA_ALLOW_4V0=1);
 *   - thermal back-off: TMP1075 ALERT drops the supply to the US level;
 *   - shutdown: everything off before system-off.
 *
 * Hooks used (all exist in Meshtastic v2.7.26, no core change needed):
 *   initVariant()               Adafruit core, before setup() and the RTOS
 *   lateInitVariant()           main.cpp, after the radio and NodeDB are up
 *   variant_nrf52LoopHook()     main-nrf52.cpp, every main-loop pass
 *   variant_shutdown()          main-nrf52.cpp, before system-off
 *   variantDefaultModuleConfig  NodeDB.cpp (only effective with patch 0001)
 *
 * Every fallback state is a safe one: if the TPS63810 is not programmed it
 * sits at its 3.3 V reset value, which is below the licensed set point, and
 * the US gain table never exceeds a request at any supply up to 4.0 V.
 */

#include "variant.h"
#include "nrf.h"
#include "wiring_constants.h"
#include "wiring_digital.h"

#include "configuration.h"
#include "mesh/NodeDB.h"
#include <Wire.h>

const uint32_t g_ADigitalPinMap[] = {
    // P0
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,

    // P1
    32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47};

// ---------------------------------------------------------------------------
// TPS63810 buck-boost (datasheet SLVSEK4C, section 8.6)
// ---------------------------------------------------------------------------
namespace
{
constexpr uint8_t TPS_REG_CONTROL = 0x01;
constexpr uint8_t TPS_REG_STATUS = 0x02;
constexpr uint8_t TPS_REG_DEVID = 0x03;
constexpr uint8_t TPS_REG_VOUT1 = 0x04;
// CONTROL: RANGE=0 (1.800-4.975 V), ENABLE=1, FPWM=0 (power save),
// RPWM=1 (forced PWM while ramping, so a step down is actively driven),
// SLEW=00 (1 V/ms)
constexpr uint8_t TPS_CONTROL_VALUE = 0x20 | 0x04;

// Hard firmware ceiling on the amplifier supply, whatever the build flags say.
constexpr uint16_t PA_VOUT_ABS_MAX_MV = 4000;
constexpr uint16_t PA_VOUT_MIN_MV = 1800;

static_assert(OFFGRID_PA_VOUT_US_MV <= 3600, "unlicensed amplifier supply above 3.6 V");
static_assert(OFFGRID_PA_VOUT_LICENSED_MV <= PA_VOUT_ABS_MAX_MV, "amplifier supply above 4.0 V");
static_assert(OFFGRID_PA_VOUT_HOT_MV <= OFFGRID_PA_VOUT_LICENSED_MV, "thermal back-off must lower the supply");

// TMP1075 (datasheet SBOS854, section 7.5)
constexpr uint8_t TMP_REG_TEMP = 0x00;
constexpr uint8_t TMP_REG_LLIM = 0x02;
constexpr uint8_t TMP_REG_HLIM = 0x03;
constexpr uint8_t TMP_REG_DIEID = 0x0F;

uint16_t paSetMv = 0;       // what the TPS63810 was last programmed to (0 = unknown)
bool paHot = false;         // TEMP_ALERT asserted
uint32_t paLastCheckMs = 0; // main-loop re-check timer
int8_t paInitResult = -1;   // initVariant() programming result, logged later (-1 = not tried)

uint8_t voutCode(uint16_t mv)
{
    if (mv > PA_VOUT_ABS_MAX_MV)
        mv = PA_VOUT_ABS_MAX_MV;
    if (mv < PA_VOUT_MIN_MV)
        mv = PA_VOUT_MIN_MV;
    return (uint8_t)((mv - PA_VOUT_MIN_MV) / 25); // VOUT = 1.800 V + code x 25 mV
}

bool i2cWrite8(uint8_t addr, uint8_t reg, uint8_t val)
{
    Wire.beginTransmission(addr);
    Wire.write(reg);
    Wire.write(val);
    return Wire.endTransmission() == 0;
}

bool i2cWrite16(uint8_t addr, uint8_t reg, uint16_t val)
{
    Wire.beginTransmission(addr);
    Wire.write(reg);
    Wire.write((uint8_t)(val >> 8));
    Wire.write((uint8_t)(val & 0xff));
    return Wire.endTransmission() == 0;
}

bool i2cRead(uint8_t addr, uint8_t reg, uint8_t *buf, uint8_t len)
{
    Wire.beginTransmission(addr);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0)
        return false;
    if (Wire.requestFrom(addr, len) != len)
        return false;
    for (uint8_t i = 0; i < len; i++)
        buf[i] = Wire.read();
    return true;
}

// Write CONTROL and VOUT1, read both back.  VSEL is held low, so VOUT1 is the
// active register.
bool tpsProgram(uint16_t mv)
{
    const uint8_t code = voutCode(mv);
    if (!i2cWrite8(TPS63810_ADDR, TPS_REG_CONTROL, TPS_CONTROL_VALUE))
        return false;
    if (!i2cWrite8(TPS63810_ADDR, TPS_REG_VOUT1, code))
        return false;
    uint8_t ctrl = 0, vout = 0;
    if (!i2cRead(TPS63810_ADDR, TPS_REG_CONTROL, &ctrl, 1) || !i2cRead(TPS63810_ADDR, TPS_REG_VOUT1, &vout, 1))
        return false;
    if (ctrl != TPS_CONTROL_VALUE || (vout & 0x7f) != code)
        return false;
    paSetMv = PA_VOUT_MIN_MV + code * 25;
    return true;
}

// True when the TPS63810 still holds what we last wrote (it resets to 3.3 V
// if the power mux drops its input, e.g. cell removed while on USB).
bool tpsStillProgrammed()
{
    if (paSetMv == 0)
        return false;
    uint8_t ctrl = 0, vout = 0;
    if (!i2cRead(TPS63810_ADDR, TPS_REG_CONTROL, &ctrl, 1) || !i2cRead(TPS63810_ADDR, TPS_REG_VOUT1, &vout, 1))
        return false;
    return ctrl == TPS_CONTROL_VALUE && (vout & 0x7f) == voutCode(paSetMv);
}

uint16_t paWantedMv()
{
    uint16_t mv = devicestate.owner.is_licensed ? OFFGRID_PA_VOUT_LICENSED_MV : OFFGRID_PA_VOUT_US_MV;
    if (paHot && mv > OFFGRID_PA_VOUT_HOT_MV)
        mv = OFFGRID_PA_VOUT_HOT_MV;
    return mv;
}

int16_t tmpLimitReg(int celsius)
{
    return (int16_t)(celsius * 16) << 4; // 12-bit, 0.0625 C/LSB, left-justified
}

bool tmpReadCentiC(int32_t *centiC)
{
    uint8_t b[2];
    if (!i2cRead(TMP1075_ADDR, TMP_REG_TEMP, b, 2))
        return false;
    int16_t raw = (int16_t)((b[0] << 8) | b[1]) >> 4;
    *centiC = (int32_t)raw * 625 / 100;
    return true;
}

void gpsPinsFloating()
{
    pinMode(PIN_SERIAL1_RX, INPUT);
    pinMode(PIN_SERIAL1_TX, INPUT);
    pinMode(PIN_GPS_PPS, INPUT);
    pinMode(PIN_GPS_RESET_OFFGRID, INPUT);
}
} // namespace

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

// Runs from the Adafruit core's main() before setup() and before FreeRTOS
// starts: no delay(), no logging, only register-level work and busy waits.
void initVariant()
{
    // REG1 DC/DC (10 uH + 15 nH fitted).  The bootloader sets this too
    // (ENABLE_DCDC_1); repeated here so an SWD-flashed app gets it as well.
    NRF_POWER->DCDCEN = 1;

    // LEDs off
    pinMode(PIN_LED1, OUTPUT);
    ledOff(PIN_LED1);
    pinMode(LED_BLUE, OUTPUT);
    ledOff(LED_BLUE);

    // Charging on (the 100 k pull-down does the same with the pin floating)
    pinMode(PIN_CHG_CE_N, OUTPUT);
    digitalWrite(PIN_CHG_CE_N, LOW);
    pinMode(PIN_CHG_STAT1, INPUT);
    pinMode(PIN_CHG_STAT2, INPUT);
    pinMode(PIN_SOLAR_OK, INPUT);
    pinMode(PIN_DRONE_OK, INPUT);
    pinMode(PIN_TEMP_ALERT, INPUT);

    // RF front end quiet until RadioLib takes TXEN/RXEN: amplifier control
    // voltage off (standby), LNA in bypass, VOUT1 selected
    pinMode(PIN_PA_EN, OUTPUT);
    digitalWrite(PIN_PA_EN, LOW);
    pinMode(PIN_LNA_EN, OUTPUT);
    digitalWrite(PIN_LNA_EN, LOW);
    pinMode(PIN_PA_VSEL, OUTPUT);
    digitalWrite(PIN_PA_VSEL, LOW);

    // GPS off, and every GPS signal floating so nothing is fed into an
    // unpowered module.  Meshtastic's GPS code takes GPS_EN and the UART later.
    pinMode(PIN_GPS_EN, OUTPUT);
    digitalWrite(PIN_GPS_EN, LOW);
    gpsPinsFloating();

    // Drone port: RTS held low (= ready to receive) for autopilots with
    // RTS/CTS flow control on; CTS is an input nobody reads.
    pinMode(PIN_DRONE_RTS, OUTPUT);
    digitalWrite(PIN_DRONE_RTS, LOW);
    pinMode(PIN_DRONE_CTS, INPUT);

    // Amplifier power: mux + TPS63810 on.  The TPS63810 starts at 3.3 V;
    // set the unlicensed level now so the first transmission never sees more.
    // (The licence state is not known yet: NodeDB loads in setup().  The
    // licensed level is applied in lateInitVariant().)
    pinMode(PIN_PA_PWR_EN, OUTPUT);
    digitalWrite(PIN_PA_PWR_EN, HIGH);
    delayMicroseconds(5000); // mux soft start + TPS63810 UVLO release (2.1 V)
    Wire.begin();
    paInitResult = 0;
    for (int attempt = 0; attempt < 5; attempt++) {
        if (tpsProgram(OFFGRID_PA_VOUT_US_MV)) {
            paInitResult = 1;
            break;
        }
        delayMicroseconds(2000);
    }
    // Meshtastic calls Wire.begin() again in setup(); harmless.
}

// After the radio is initialised and the config is loaded.
void lateInitVariant()
{
    LOG_INFO("OffGrid Mesh Radio v1: PA supply %s at boot (%u mV)", paInitResult == 1 ? "programmed" : "NOT programmed",
             paSetMv);

    uint8_t devid = 0;
    if (i2cRead(TPS63810_ADDR, TPS_REG_DEVID, &devid, 1))
        LOG_INFO("TPS63810 DEVID 0x%02x", devid);
    else
        LOG_WARN("TPS63810 not answering at 0x%02x: amplifier supply stays at its 3.3 V default", TPS63810_ADDR);

    paHot = digitalRead(PIN_TEMP_ALERT) == LOW;
    const uint16_t want = paWantedMv();
    if (tpsProgram(want))
        LOG_INFO("PA supply %u mV (%s%s)", paSetMv, devicestate.owner.is_licensed ? "licensed" : "unlicensed, 30 dBm cap",
                 paHot ? ", thermal back-off" : "");
    else
        LOG_WARN("PA supply: could not program %u mV", want);

    // TMP1075: set the ALERT window explicitly (comparator mode, active low
    // are the power-on defaults).  Re-written here because the I2C scan in
    // setup() probes 0x48 with an unrelated chip's command sequence.
    uint8_t id[2];
    if (i2cRead(TMP1075_ADDR, TMP_REG_DIEID, id, 2)) {
        i2cWrite16(TMP1075_ADDR, TMP_REG_LLIM, (uint16_t)tmpLimitReg(OFFGRID_PA_TEMP_LOW_C));
        i2cWrite16(TMP1075_ADDR, TMP_REG_HLIM, (uint16_t)tmpLimitReg(OFFGRID_PA_TEMP_HIGH_C));
        int32_t cc = 0;
        if (tmpReadCentiC(&cc))
            LOG_INFO("TMP1075 id 0x%02x%02x, PA area %d.%02d C, back-off at %d C", id[0], id[1], (int)(cc / 100),
                     (int)(abs(cc) % 100), OFFGRID_PA_TEMP_HIGH_C);
    } else {
        LOG_WARN("TMP1075 not answering at 0x%02x", TMP1075_ADDR);
    }
    paLastCheckMs = millis();
}

// Every main-loop pass; does real work once per OFFGRID_PA_CHECK_MS.
void variant_nrf52LoopHook(void)
{
    const uint32_t now = millis();
    if (now - paLastCheckMs < OFFGRID_PA_CHECK_MS)
        return;
    paLastCheckMs = now;

    const bool hot = digitalRead(PIN_TEMP_ALERT) == LOW;
    if (hot != paHot) {
        paHot = hot;
        int32_t cc = 0;
        bool haveT = tmpReadCentiC(&cc);
        LOG_WARN("PA temperature alert %s (%d C)", hot ? "ON: amplifier supply lowered" : "cleared",
                 haveT ? (int)(cc / 100) : -999);
    }

    const uint16_t want = paWantedMv();
    if (voutCode(want) == voutCode(paSetMv) && tpsStillProgrammed())
        return;
    const uint16_t before = paSetMv;
    if (tpsProgram(want)) {
        if (before == 0 || voutCode(before) == voutCode(want))
            LOG_WARN("PA supply re-programmed to %u mV (TPS63810 had reset)", paSetMv);
        else
            LOG_INFO("PA supply %u -> %u mV", before, paSetMv);
    } else {
        paSetMv = 0; // unknown: try again next time
    }
}

// Before system-off (deep sleep or shutdown): everything off.
void variant_shutdown()
{
    digitalWrite(PIN_PA_EN, LOW);
    digitalWrite(PIN_LNA_EN, LOW);
    digitalWrite(PIN_PA_PWR_EN, LOW); // mux and buck-boost off (1 M pull-down keeps them off)
    digitalWrite(PIN_PA_VSEL, LOW);
    paSetMv = 0;

    digitalWrite(PIN_GPS_EN, LOW);
    gpsPinsFloating();

    ledOff(PIN_LED1);
    ledOff(LED_BLUE);

    pinMode(PIN_DRONE_RTS, INPUT);
    // Charging stays on through the 100 k pull-down on /CE.
    pinMode(PIN_CHG_CE_N, INPUT);
}

// Drone port defaults (Cairn field-logger settings: Meshtastic serial module,
// PROTO mode, 38400 baud).  Meshtastic v2.7.26 calls this from
// installDefaultConfig() and then wipes moduleConfig in
// installDefaultModuleConfig(), so it only takes effect with patch 0001.
void variantDefaultModuleConfig()
{
#if !defined(OFFGRID_DRONE_SERIAL_DEFAULT) || (OFFGRID_DRONE_SERIAL_DEFAULT == 1)
    moduleConfig.has_serial = true;
    moduleConfig.serial.enabled = true;
    moduleConfig.serial.rxd = PIN_SERIAL2_RX;
    moduleConfig.serial.txd = PIN_SERIAL2_TX;
    moduleConfig.serial.mode = meshtastic_ModuleConfig_SerialConfig_Serial_Mode_PROTO;
    moduleConfig.serial.baud = meshtastic_ModuleConfig_SerialConfig_Serial_Baud_BAUD_38400;
#endif
}
