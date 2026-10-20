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
 *   - power caps by board temperature (TMP1075) and by the cell (sim/burst),
 *     applied to the SX1262 setting of each packet and to the supply;
 *   - missing-antenna cut-off: the ratio REFL_DET / FWD_DET sampled in every
 *     transmission of 27 dBm or more;
 *   - soft start: a packet above 1 W starts with the amplifier supply at the
 *     1 W level and is raised only once the antenna check has passed;
 *   - amplifier source: battery first, charger SYS (PA_SRC_SYS) when no cell
 *     is fitted or the cell is too weak and USB is in;
 *   - charging held to 0-45 C cell temperature (the charger's NTC on CHG_TS),
 *     and the no-cell /CE pulse that clears the reverse-FET latch;
 *   - shutdown: everything off before system-off.
 *
 * Hooks used:
 *   initVariant()               Adafruit core, before setup() and the RTOS
 *   lateInitVariant()           main.cpp, after the radio and NodeDB are up
 *   variant_nrf52LoopHook()     main-nrf52.cpp, every main-loop pass
 *   variant_shutdown()          main-nrf52.cpp, before system-off
 *   variantDefaultModuleConfig  NodeDB.cpp (only effective with patch 0001 part 2)
 *   variantLimitTxPower()       SX126xInterface::configHardwareForSend   } patch 0001
 *   variantTxStarted()          RadioLibInterface::startSend             } part 3
 *   variantTxDone()             RadioLibInterface::completeSending       }
 * Without patch part 3 the last three are never called: the caps then act
 * on the amplifier supply only (every OFFGRID_PA_CHECK_MS), the amplifier-off
 * states still work (PA_EN released to its pull-down), and there is no
 * missing-antenna detection, no soft start and no battery reading under
 * load.  Without the hooks the supply stays at the full level between
 * packets (paIdleMv() only lowers it after a soft-started packet).
 *
 * Every fallback state is a safe one: if the TPS63810 is not programmed it
 * sits at its 3.3 V reset value, which is below the licensed set point, and
 * the US gain table never exceeds a request at any supply up to 4.0 V.
 *
 * Everything here runs in the Arduino loop task (Meshtastic's OSThreads,
 * the radio thread included), so the SAADC, I2C and pin work below never
 * races with itself.
 */

#include "variant.h"
#include "nrf.h"
#include "wiring_constants.h"
#include "wiring_digital.h"

#include "MeshService.h"
#include "configuration.h"
#include "mesh/NodeDB.h"
#include <Wire.h>
#include <math.h>

const uint32_t g_ADigitalPinMap[] = {
    // P0
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,

    // P1
    32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47};

// Board hooks called from Meshtastic core (patch 0001 part 3; weak no-ops there)
int8_t variantLimitTxPower(int8_t power);
void variantTxStarted();
void variantTxDone();

namespace
{
// ---------------------------------------------------------------------------
// TPS63810 buck-boost (datasheet SLVSEK4C, section 8.6)
// ---------------------------------------------------------------------------
constexpr uint8_t TPS_REG_CONTROL = 0x01;
constexpr uint8_t TPS_REG_STATUS = 0x02;
constexpr uint8_t TPS_REG_DEVID = 0x03;
constexpr uint8_t TPS_REG_VOUT1 = 0x04;
// CONTROL: RANGE=0 (1.800-4.975 V), ENABLE=1, FPWM=0 (power save),
// RPWM=1 (forced PWM while ramping, so a step down is actively driven),
// SLEW=00 (1 V/ms)
constexpr uint8_t TPS_CONTROL_VALUE = 0x20 | 0x04;
// DVS ramp, SLEW = 00: 1 V/ms = 1 mV/us, up and down (datasheet 7.7, "SR")
constexpr uint32_t TPS_SLEW_MV_PER_MS = 1000;
// One I2C register write at the core's default 100 kHz: START, 3 x 9 bits,
// STOP (~290 us) plus driver overhead, rounded up
constexpr uint32_t TPS_WRITE_US = 400;
// One two-channel saadcRead2Mv(): 2 x (40 us acquisition + 2 us conversion)
// + start/stop, rounded up
constexpr uint32_t SAADC_READ2_US = 110;

// Hard firmware ceiling on the amplifier supply, whatever the build flags say.
constexpr uint16_t PA_VOUT_ABS_MAX_MV = 4000;
constexpr uint16_t PA_VOUT_MIN_MV = 1800; // also the "amplifier off" supply

static_assert(OFFGRID_PA_VOUT_US_MV <= 3600, "unlicensed amplifier supply above 3.6 V");
static_assert(OFFGRID_PA_VOUT_LICENSED_MV <= PA_VOUT_ABS_MAX_MV, "amplifier supply above 4.0 V");
static_assert(OFFGRID_PA_VOUT_US_MV <= OFFGRID_PA_VOUT_LICENSED_MV, "licensed supply below the unlicensed one");
static_assert(PIN_PA_EN == 32 + 7, "paEnDrivenHigh() reads P1.07");
static_assert(REFL_DET_AIN == SAADC_CH_PSELP_PSELP_AnalogInput6, "REFL_DET is AIN6");
static_assert(FWD_DET_AIN == SAADC_CH_PSELP_PSELP_AnalogInput0, "FWD_DET is AIN0");
static_assert(PIN_PA_SRC_SYS == 32 + 9, "PA_SRC_SYS is P1.09");
static_assert(OFFGRID_SOFTSTART_VPA_MV >= PA_VOUT_MIN_MV && OFFGRID_SOFTSTART_VPA_MV <= OFFGRID_PA_VOUT_US_MV,
              "soft-start supply outside 1.8 V .. the US level");
static_assert(OFFGRID_ANT_RATIO_MAX_PCT > 0 && OFFGRID_ANT_RATIO_MAX_PCT < 100, "antenna ratio threshold");
static_assert(CHG_TS_AIN == SAADC_CH_PSELP_PSELP_AnalogInput7, "CHG_TS is AIN7");

// TMP1075 (datasheet SBOS854, section 7.5)
constexpr uint8_t TMP_REG_TEMP = 0x00;
constexpr uint8_t TMP_REG_LLIM = 0x02;
constexpr uint8_t TMP_REG_HLIM = 0x03;
constexpr uint8_t TMP_REG_DIEID = 0x0F;

// Model of the transmit chain, the same as firmware/tools/pa_gain_table.py
constexpr float MODEL_G0_DB = 16.8f;     // SX1262 pin -> U.FL, small signal
constexpr float MODEL_PSAT_4V0 = 35.0f;  // dBm at the U.FL, VPA 4.0 V
const uint16_t TX_GAIN[NUM_PA_POINTS] = {TX_GAIN_LORA};

constexpr int8_t CAP_NONE = 127;
constexpr int8_t CAP_PA_OFF = -128;

// --- amplifier supply and state ---
uint16_t paSetMv = 0;       // what the TPS63810 was last programmed to (0 = unknown)
int8_t paInitResult = -1;   // initVariant() programming result, logged later (-1 = not tried)
uint32_t paLastCheckMs = 0; // slow main-loop work timer
bool paReleased = false;    // PA_EN given to its pull-down (amplifier held off)
bool paSrcSys = false;      // PA_SRC_SYS driven high (amplifier from charger SYS)
int8_t txDrive = SX126X_MAX_POWER; // SX1262 setting of the current/last packet
int8_t lastCapLogged = CAP_NONE;

// --- temperature (TMP1075 beside the amplifier) ---
int32_t boardCentiC = 2500;
bool boardTempValid = false;
uint8_t tmpFailCount = 0;
bool tempAlert = false;  // TMP1075 ALERT pin
uint8_t tempLevel = 0;   // 0 none, 1 warm cap, 2 hot cap, 3 amplifier off

// --- cell and external power ---
uint16_t vIdleMv = 0;          // cell voltage between packets (0 = not read yet)
float rint25 = 0.150f;         // estimated cell R_int at 25 C, ohm (sim/burst's mid cell until measured)
bool rintMeasured = false;
int8_t battCap = CAP_NONE;     // from the sim/burst table
bool extPower = false;         // USB, solar or drone input present
bool usbPower = false;
bool noCell = false;           // cell test says no cell fitted
bool cellTestActive = false;   // /CE held high for the cell test
uint32_t cellTestStartMs = 0;
uint32_t cellTestNextMs = 0;   // 0 = none scheduled
uint8_t stat2Edges = 0;
bool stat2Last = true;
uint32_t stat2WindowMs = 0;

// --- charging window (CHG_TS) ---
bool chgInhibit = false;       // /CE high: cell outside 0-45 C
int32_t cellCentiC = 2500;
bool cellTempValid = false;
uint32_t tsToggleMs = 0;

// --- supply ramp (TPS63810 DVS) ---
uint32_t paRampFromMs = 0;     // millis() when the last ramp was commanded
uint32_t paRampUs = 0;         // how long it takes (0 = none pending)

// --- transmission and antenna ---
bool txActive = false;
uint32_t txStartMs = 0;
uint32_t lastTxEndMs = 0;
float txPest = -99;            // modelled U.FL power of the current packet, dBm
bool txSoft = false;           // this packet starts at the soft-start supply
bool txRaised = false;         // ... and has been raised to its own level
uint16_t txTargetMv = 0;       // this packet's own supply (the caps' level)
uint32_t txPreambleUs = 0;     // its preamble, us
enum AntState : uint8_t { ANT_OK, ANT_BLOCKED, ANT_PROBE };
AntState antState = ANT_OK;
uint32_t antRetryAtMs = 0;
uint32_t antBackoffMs = OFFGRID_ANT_RETRY_MS;
enum AntVerdict : uint8_t { AV_OK, AV_FAULT, AV_UNSURE };
uint16_t antLastFwdMv = 0, antLastReflMv = 0, antLastThrMv = 0;
bool antLastByRatio = false;   // the last verdict came from the ratio (else the REFL_DET-only fallback)
bool antNotifyPending = false;
bool antLogPending = false;
bool antFwdLowPending = false; // a soft start was held at 1 W: FWD_DET too low to trust
bool softLatePending = false;  // a soft start was held at 1 W: the raise would end after the preamble
bool softFailPending = false;  // the soft-start supply could not be set: drive held to the 1 W setting

// ---------------------------------------------------------------------------
// I2C helpers
// ---------------------------------------------------------------------------
uint8_t voutCode(uint16_t mv)
{
    if (mv > PA_VOUT_ABS_MAX_MV)
        mv = PA_VOUT_ABS_MAX_MV;
    if (mv < PA_VOUT_MIN_MV)
        mv = PA_VOUT_MIN_MV;
    return (uint8_t)((mv - PA_VOUT_MIN_MV + 24) / 25); // VOUT = 1.800 V + code x 25 mV, rounded up
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

// The TPS63810 ramps to a new VOUT at TPS_SLEW_MV_PER_MS.  Remember how long
// the ramp just commanded takes, so a packet that must not start on the way
// down (a soft start) can wait for it.  From an unknown level (0), assume the
// whole 1.8-4.0 V range.
void noteRamp(uint16_t fromMv, uint16_t toMv)
{
    const uint32_t d = fromMv == 0 ? (PA_VOUT_ABS_MAX_MV - PA_VOUT_MIN_MV) : (fromMv > toMv ? fromMv - toMv : toMv - fromMv);
    paRampFromMs = millis();
    paRampUs = d * 1000 / TPS_SLEW_MV_PER_MS + 50;
}

// Busy-wait for the rest of the last ramp.  millis() ticks at ~1 ms, so
// "n ms since" only proves n - 1 ms have passed.
void waitForRamp()
{
    if (paRampUs == 0)
        return;
    const uint32_t since = millis() - paRampFromMs;
    const uint32_t doneUs = since >= 1 ? (since - 1) * 1000 : 0;
    if (doneUs < paRampUs)
        delayMicroseconds(paRampUs - doneUs);
    paRampUs = 0;
}

// Write CONTROL and VOUT1, read both back.  VSEL is low (tied low on the
// reworked board, held low on the committed one), so VOUT1 is the active register.
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
    const uint16_t mvSet = PA_VOUT_MIN_MV + code * 25;
    noteRamp(paSetMv, mvSet);
    paSetMv = mvSet;
    return true;
}

// VOUT1 only: one register write, for a change while CONTROL is known good
// (tpsProgram() verified it before this packet).  Used in the middle of a
// packet, where the read-backs would cost another ~0.8 ms.
bool tpsSetVout(uint16_t mv)
{
    const uint8_t code = voutCode(mv);
    if (!i2cWrite8(TPS63810_ADDR, TPS_REG_VOUT1, code))
        return false;
    const uint16_t mvSet = PA_VOUT_MIN_MV + code * 25;
    noteRamp(paSetMv, mvSet);
    paSetMv = mvSet;
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

// ---------------------------------------------------------------------------
// SAADC, one sample, 12 bit, internal 0.6 V reference.  The same register
// sequence as the core's analogRead(), which leaves the SAADC disabled; it
// is done here because analogRead() has no acquisition-time setting and
// shares its gain/reference with the battery code.
// gain: SAADC_CH_CONFIG_GAIN_Gain1_6 (3.6 V full scale) or _Gain1_2 (1.2 V).
// ---------------------------------------------------------------------------
uint16_t saadcReadMv(uint32_t psel, uint32_t gain)
{
    volatile int16_t value = 0;
    const uint32_t fullScaleMv = (gain == SAADC_CH_CONFIG_GAIN_Gain1_2) ? 1200 : 3600;
    NRF_SAADC->RESOLUTION = SAADC_RESOLUTION_VAL_12bit;
    NRF_SAADC->OVERSAMPLE = 0;
    NRF_SAADC->ENABLE = SAADC_ENABLE_ENABLE_Enabled << SAADC_ENABLE_ENABLE_Pos;
    for (int i = 0; i < 8; i++) {
        NRF_SAADC->CH[i].PSELN = SAADC_CH_PSELP_PSELP_NC;
        NRF_SAADC->CH[i].PSELP = SAADC_CH_PSELP_PSELP_NC;
    }
    NRF_SAADC->CH[0].CONFIG = (SAADC_CH_CONFIG_RESP_Bypass << SAADC_CH_CONFIG_RESP_Pos) |
                              (SAADC_CH_CONFIG_RESN_Bypass << SAADC_CH_CONFIG_RESN_Pos) |
                              (gain << SAADC_CH_CONFIG_GAIN_Pos) |
                              (SAADC_CH_CONFIG_REFSEL_Internal << SAADC_CH_CONFIG_REFSEL_Pos) |
                              (SAADC_CH_CONFIG_TACQ_40us << SAADC_CH_CONFIG_TACQ_Pos) |
                              (SAADC_CH_CONFIG_MODE_SE << SAADC_CH_CONFIG_MODE_Pos) |
                              (SAADC_CH_CONFIG_BURST_Disabled << SAADC_CH_CONFIG_BURST_Pos);
    NRF_SAADC->CH[0].PSELP = psel;
    NRF_SAADC->RESULT.PTR = (uint32_t)&value;
    NRF_SAADC->RESULT.MAXCNT = 1;
    NRF_SAADC->TASKS_START = 1;
    while (!NRF_SAADC->EVENTS_STARTED)
        ;
    NRF_SAADC->EVENTS_STARTED = 0;
    NRF_SAADC->TASKS_SAMPLE = 1;
    while (!NRF_SAADC->EVENTS_END)
        ;
    NRF_SAADC->EVENTS_END = 0;
    NRF_SAADC->TASKS_STOP = 1;
    while (!NRF_SAADC->EVENTS_STOPPED)
        ;
    NRF_SAADC->EVENTS_STOPPED = 0;
    NRF_SAADC->CH[0].PSELP = SAADC_CH_PSELP_PSELP_NC;
    NRF_SAADC->ENABLE = SAADC_ENABLE_ENABLE_Disabled << SAADC_ENABLE_ENABLE_Pos;
    int32_t v = value < 0 ? 0 : value;
    return (uint16_t)((v * fullScaleMv) / 4096);
}

// Two pins in one SAADC scan (CH[0], CH[1], converted back to back on one
// SAMPLE task), same gain: two readings ~45 us apart, so a level still
// moving moves both nearly alike.
void saadcRead2Mv(uint32_t pselA, uint32_t pselB, uint32_t gain, uint16_t *mvA, uint16_t *mvB)
{
    volatile int16_t value[2] = {0, 0};
    const uint32_t fullScaleMv = (gain == SAADC_CH_CONFIG_GAIN_Gain1_2) ? 1200 : 3600;
    const uint32_t cfg = (SAADC_CH_CONFIG_RESP_Bypass << SAADC_CH_CONFIG_RESP_Pos) |
                         (SAADC_CH_CONFIG_RESN_Bypass << SAADC_CH_CONFIG_RESN_Pos) | (gain << SAADC_CH_CONFIG_GAIN_Pos) |
                         (SAADC_CH_CONFIG_REFSEL_Internal << SAADC_CH_CONFIG_REFSEL_Pos) |
                         (SAADC_CH_CONFIG_TACQ_40us << SAADC_CH_CONFIG_TACQ_Pos) |
                         (SAADC_CH_CONFIG_MODE_SE << SAADC_CH_CONFIG_MODE_Pos) |
                         (SAADC_CH_CONFIG_BURST_Disabled << SAADC_CH_CONFIG_BURST_Pos);
    NRF_SAADC->RESOLUTION = SAADC_RESOLUTION_VAL_12bit;
    NRF_SAADC->OVERSAMPLE = 0;
    NRF_SAADC->ENABLE = SAADC_ENABLE_ENABLE_Enabled << SAADC_ENABLE_ENABLE_Pos;
    for (int i = 0; i < 8; i++) {
        NRF_SAADC->CH[i].PSELN = SAADC_CH_PSELP_PSELP_NC;
        NRF_SAADC->CH[i].PSELP = SAADC_CH_PSELP_PSELP_NC;
    }
    NRF_SAADC->CH[0].CONFIG = cfg;
    NRF_SAADC->CH[1].CONFIG = cfg;
    NRF_SAADC->CH[0].PSELP = pselA;
    NRF_SAADC->CH[1].PSELP = pselB;
    NRF_SAADC->RESULT.PTR = (uint32_t)value;
    NRF_SAADC->RESULT.MAXCNT = 2;
    NRF_SAADC->TASKS_START = 1;
    while (!NRF_SAADC->EVENTS_STARTED)
        ;
    NRF_SAADC->EVENTS_STARTED = 0;
    NRF_SAADC->TASKS_SAMPLE = 1; // one task scans every enabled channel
    while (!NRF_SAADC->EVENTS_END)
        ;
    NRF_SAADC->EVENTS_END = 0;
    NRF_SAADC->TASKS_STOP = 1;
    while (!NRF_SAADC->EVENTS_STOPPED)
        ;
    NRF_SAADC->EVENTS_STOPPED = 0;
    NRF_SAADC->CH[0].PSELP = SAADC_CH_PSELP_PSELP_NC;
    NRF_SAADC->CH[1].PSELP = SAADC_CH_PSELP_PSELP_NC;
    NRF_SAADC->ENABLE = SAADC_ENABLE_ENABLE_Disabled << SAADC_ENABLE_ENABLE_Pos;
    const int32_t a = value[0] < 0 ? 0 : value[0], b = value[1] < 0 ? 0 : value[1];
    *mvA = (uint16_t)((a * fullScaleMv) / 4096);
    *mvB = (uint16_t)((b * fullScaleMv) / 4096);
}

uint16_t readVbatMv()
{
    const float mult = config.power.adc_multiplier_override > 0 ? config.power.adc_multiplier_override : ADC_MULTIPLIER;
    return (uint16_t)(saadcReadMv(SAADC_CH_PSELP_PSELP_AnalogInput3, SAADC_CH_CONFIG_GAIN_Gain1_6) * mult);
}

// Solar / drone input voltage: 1.5 M / 100 k = 1/16 (power-path rework)
uint16_t readInputMv(uint32_t psel)
{
    return (uint16_t)(saadcReadMv(psel, SAADC_CH_CONFIG_GAIN_Gain1_6) * 16);
}

// ---------------------------------------------------------------------------
// Transmit-chain model (firmware/tools/pa_gain_table.py)
// ---------------------------------------------------------------------------
float psatDbm(uint16_t vpaMv)
{
    return MODEL_PSAT_4V0 + 20.0f * log10f(vpaMv / 4000.0f);
}

// Modelled power at the U.FL for an SX1262 setting and amplifier supply
float modelUflDbm(int8_t drive, uint16_t vpaMv)
{
    if (vpaMv < PA_VOUT_MIN_MV)
        vpaMv = PA_VOUT_MIN_MV;
    const float ps = psatDbm(vpaMv);
    const float a = powf(10.0f, (drive + MODEL_G0_DB - ps) / 20.0f);
    return ps + 20.0f * log10f(a / powf(1.0f + a * a * a * a, 0.25f)); // Rapp, p = 2
}

// Highest SX1262 setting whose table power does not pass the cap (the same
// rule as RadioInterface::limitPower)
int8_t driveForCapDbm(int8_t capDbm)
{
    for (int i = 0; i < NUM_PA_POINTS; i++) {
        if (i + TX_GAIN[i] > capDbm || i == NUM_PA_POINTS - 1)
            return (int8_t)max(-9, min((int)SX126X_MAX_POWER, capDbm - (int)TX_GAIN[i]));
    }
    return -9;
}

// Supply for a cap: Psat(VPA) = cap, not below the unlicensed level
uint16_t vpaForCapMv(int8_t capDbm, uint16_t ceilingMv)
{
    float mv = 4000.0f * powf(10.0f, (capDbm - MODEL_PSAT_4V0) / 20.0f);
    uint16_t v = (uint16_t)(ceilf(mv / 25.0f) * 25.0f);
    if (v < OFFGRID_PA_VOUT_US_MV)
        v = OFFGRID_PA_VOUT_US_MV;
    return v < ceilingMv ? v : ceilingMv;
}

// ---------------------------------------------------------------------------
// Battery cap: sim/burst/results.txt, "Highest PA level that passes, battery
// only".  dBm at the U.FL, 0 = not even 1 W.  Rows: OCV 4.2 / 3.7 / 3.3 /
// 3.1 V; columns: R_int at 25 C 50 / 150 / 300 mOhm.  60 C and 85 C are
// the same as 25 C or better, so 25 C stands for everything above.
// ---------------------------------------------------------------------------
const uint16_t BURST_OCV_MV[4] = {4200, 3700, 3300, 3100};
const int8_t BURST_CAP[4][4][3] = {
    {{33, 0, 0}, {32, 0, 0}, {0, 0, 0}, {0, 0, 0}},          // -40 C
    {{35, 32, 0}, {33, 0, 0}, {30, 0, 0}, {0, 0, 0}},        // -20 C
    {{35, 34, 32}, {35, 33, 30}, {33, 30, 0}, {32, 0, 0}},   // 0 C
    {{35, 35, 34}, {35, 35, 33}, {35, 33, 30}, {33, 30, 0}}, // 25 C and above
};

// R_int over temperature, as sim/burst scales it (powerlib.rint_k)
float rintK(float c)
{
    static const float T[6] = {-40, -20, 0, 25, 60, 85};
    static const float K[6] = {9, 5, 2, 1, 0.8f, 0.75f};
    if (c <= T[0])
        return K[0];
    for (int i = 1; i < 6; i++)
        if (c <= T[i])
            return K[i - 1] + (K[i] - K[i - 1]) * (c - T[i - 1]) / (T[i] - T[i - 1]);
    return K[5];
}

// The cell's temperature as well as the board can tell: the NTC beside the
// plug when the charger biases it, else the TMP1075 (beside the amplifier,
// so it reads warm after a transmission), else 0 C.
int32_t cellTempCentiC()
{
    if (cellTempValid && boardTempValid)
        return min(cellCentiC, boardCentiC);
    if (cellTempValid)
        return cellCentiC;
    if (boardTempValid)
        return boardCentiC;
    return 0;
}

int8_t burstCapLookup(uint16_t ocvMv, int32_t centiC, float r25)
{
    // colder band and higher-resistance column: the conservative neighbours
    const int band = centiC < -2000 ? 0 : centiC < 0 ? 1 : centiC < 2500 ? 2 : 3;
    const int col = r25 <= 0.050f ? 0 : r25 <= 0.150f ? 1 : 2;
    if (ocvMv >= BURST_OCV_MV[0])
        return BURST_CAP[band][0][col];
    for (int r = 1; r < 4; r++) {
        if (ocvMv >= BURST_OCV_MV[r]) {
            const int8_t lo = BURST_CAP[band][r][col], hi = BURST_CAP[band][r - 1][col];
            if (lo == 0)
                return 0; // between a passing and a failing row: take the failing one
            return (int8_t)(lo + (hi - lo) * (int)(ocvMv - BURST_OCV_MV[r]) / (int)(BURST_OCV_MV[r - 1] - BURST_OCV_MV[r]));
        }
    }
    return 0;
}

// ---------------------------------------------------------------------------
// Caps
// ---------------------------------------------------------------------------
uint16_t paCeilingMv()
{
    return devicestate.owner.is_licensed ? OFFGRID_PA_VOUT_LICENSED_MV : OFFGRID_PA_VOUT_US_MV;
}

int8_t tempCapDbm()
{
    if (tempAlert || tempLevel >= 3)
        return CAP_PA_OFF;
    if (!boardTempValid)
        return OFFGRID_TCAP_HOT_DBM; // no reading: 1 W
    if (tempLevel == 2)
        return OFFGRID_TCAP_HOT_DBM;
    if (tempLevel == 1)
        return OFFGRID_TCAP_WARM_DBM;
    return CAP_NONE;
}

int8_t capDbm()
{
    int8_t cap = tempCapDbm();
    int8_t b = paSrcSys ? OFFGRID_SYS_CAP_DBM : battCap; // from SYS: the charger's 1.05 A input sets it
    if (b < cap)
        cap = b;
    if (antState == ANT_BLOCKED)
        cap = CAP_PA_OFF;
    else if (antState == ANT_PROBE && cap > OFFGRID_ANT_PROBE_DBM)
        cap = OFFGRID_ANT_PROBE_DBM;
    return cap;
}

uint16_t paWantedMv()
{
    const int8_t cap = capDbm();
    if (cap == CAP_PA_OFF)
        return PA_VOUT_MIN_MV;
    const uint16_t ceiling = paCeilingMv();
    return cap == CAP_NONE ? ceiling : vpaForCapMv(cap, ceiling);
}

// ---------------------------------------------------------------------------
// Soft start (variant.h, OFFGRID_SOFTSTART_*): a packet above 1 W starts at
// the soft-start supply and is raised only after the antenna check.
// ---------------------------------------------------------------------------
// Above the US supply and, in the model, above 30 dBm less the model's
// uncertainty.  US mode (2.7 V, the gain table's +13 dBm) never soft-starts.
bool softStartWanted(int8_t drive, uint16_t targetMv)
{
    return targetMv > OFFGRID_PA_VOUT_US_MV &&
           modelUflDbm(drive, targetMv) > (float)(OFFGRID_SOFTSTART_ABOVE_DBM - OFFGRID_SOFTSTART_MODEL_DB);
}

uint16_t softStartMv(uint16_t targetMv)
{
    return targetMv < OFFGRID_SOFTSTART_VPA_MV ? targetMv : OFFGRID_SOFTSTART_VPA_MV;
}

// The supply between packets: the caps' level, or the soft-start level when
// the last packet's drive would need a soft start (so the next one does not
// have to wait for the TPS63810 to ramp down before it starts).
uint16_t paIdleMv()
{
    const uint16_t want = paWantedMv();
    return softStartWanted(txDrive, want) ? softStartMv(want) : want;
}

// The 16-symbol preamble of the current LoRa settings, us (0 = unknown).
// 902-928 MHz is never "wide LoRa" (that is 2.4 GHz).
uint32_t preambleUs()
{
    float bwKHz = 0;
    uint8_t sf = 0, cr = 0;
    if (config.lora.use_preset) {
        modemPresetToParams(config.lora.modem_preset, false, bwKHz, sf, cr);
    } else {
        sf = config.lora.spread_factor;
        bwKHz = bwCodeToKHz(config.lora.bandwidth);
    }
    if (bwKHz <= 0 || sf < 5 || sf > 12)
        return 0;
    return (uint32_t)(OFFGRID_LORA_PREAMBLE_SYMBOLS * (float)(1u << sf) * 1000.0f / bwKHz);
}

// ---------------------------------------------------------------------------
// Amplifier on/off.  RadioLib drives PA_EN (its TXEN) with digitalWrite()
// only, which sets the OUT register; with the pin made an input the 100 k
// pull-down holds the amplifier in standby whatever RadioLib writes.
// ---------------------------------------------------------------------------
bool paEnDrivenHigh()
{
    return (NRF_P1->OUT >> 7) & 1;
}

void paRelease()
{
    digitalWrite(PIN_PA_EN, LOW);
    pinMode(PIN_PA_EN, INPUT);
    paReleased = true;
}

// Give PA_EN back to RadioLib, but only while it is not transmitting
// (OUT low), so a packet that started with the amplifier off stays off.
void paRestoreIfIdle()
{
    if (paReleased && capDbm() != CAP_PA_OFF && !paEnDrivenHigh()) {
        pinMode(PIN_PA_EN, OUTPUT);
        paReleased = false;
    }
}

// Bring the supply to mv (programmed and read back); false if that failed,
// and the level is then unknown (paSetMv = 0, retried later).
bool supplyTo(uint16_t mv)
{
    if (paSetMv != 0 && voutCode(mv) == voutCode(paSetMv))
        return true;
    if (tpsProgram(mv))
        return true;
    paSetMv = 0;
    return false;
}

void antennaFault()
{
    paRelease(); // amplifier standby now, mid-packet
    const AntState was = antState;
    antState = ANT_BLOCKED;
    if (!tpsProgram(PA_VOUT_MIN_MV))
        paSetMv = 0;
    if (was == ANT_PROBE)
        antBackoffMs = min((uint32_t)OFFGRID_ANT_RETRY_MAX_MS, antBackoffMs * 2);
    else
        antBackoffMs = OFFGRID_ANT_RETRY_MS;
    antRetryAtMs = millis() + antBackoffMs;
    antLogPending = true;
    if (was == ANT_OK)
        antNotifyPending = true;
}

// The antenna check, once the sample time has passed.  Reads FWD_DET and
// REFL_DET; while FWD_DET is below OFFGRID_FWD_MIN_MV (RF not up yet), reads
// them again every OFFGRID_FWD_POLL_US for up to OFFGRID_FWD_WAIT_MAX_US.
//   AV_OK      FWD_DET trusted and REFL/FWD within OFFGRID_ANT_RATIO_MAX_PCT
//   AV_FAULT   the ratio is above it, or (fallback, FWD_DET too low) REFL_DET
//              is above the old absolute threshold for this power
//   AV_UNSURE  FWD_DET too low and REFL_DET below the fallback threshold: no
//              fault seen, but nothing proves the antenna is there either
// *elapsedUs grows by the time spent here (an estimate: micros() on this core
// has only RTOS-tick resolution unless DWT is on).
AntVerdict antennaCheck(float pDbm, uint32_t *elapsedUs)
{
    uint16_t fwd = 0, refl = 0;
    saadcRead2Mv(FWD_DET_AIN, REFL_DET_AIN, SAADC_CH_CONFIG_GAIN_Gain1_6, &fwd, &refl);
    *elapsedUs += SAADC_READ2_US;
    for (uint32_t waited = 0; fwd < OFFGRID_FWD_MIN_MV && waited < OFFGRID_FWD_WAIT_MAX_US; waited += OFFGRID_FWD_POLL_US) {
        delayMicroseconds(OFFGRID_FWD_POLL_US);
        saadcRead2Mv(FWD_DET_AIN, REFL_DET_AIN, SAADC_CH_CONFIG_GAIN_Gain1_6, &fwd, &refl);
        *elapsedUs += OFFGRID_FWD_POLL_US + SAADC_READ2_US;
    }
    antLastFwdMv = fwd;
    antLastReflMv = refl;
    if (fwd >= OFFGRID_FWD_MIN_MV) {
        // Ratio: independent of the cable length and of the power; the two
        // diodes' temperature drift largely cancels, so no correction.
        antLastByRatio = true;
        return (uint32_t)refl * 100 > (uint32_t)OFFGRID_ANT_RATIO_MAX_PCT * fwd ? AV_FAULT : AV_OK;
    }
    // Fallback: the old single-detector threshold, V30 at 30 dBm, V35 at
    // 35 dBm, straight line in dB(V) against dBm, plus the diode's drift
    antLastByRatio = false;
    const float thr = OFFGRID_REFL_V30_MV * powf((float)OFFGRID_REFL_V35_MV / OFFGRID_REFL_V30_MV, (pDbm - 30.0f) / 5.0f) +
                      (boardTempValid ? OFFGRID_REFL_TC_UV_PER_C * (boardCentiC - 2500) / 100000.0f : 0.0f);
    antLastThrMv = (uint16_t)thr;
    return refl > thr ? AV_FAULT : AV_UNSURE;
}

void gpsPinsFloating()
{
    pinMode(PIN_SERIAL1_RX, INPUT);
    pinMode(PIN_SERIAL1_TX, INPUT);
    pinMode(PIN_GPS_PPS, INPUT);
}

// ---------------------------------------------------------------------------
// Slow checks (every OFFGRID_PA_CHECK_MS)
// ---------------------------------------------------------------------------
void updateTemperature()
{
    int32_t cc = 0;
    if (tmpReadCentiC(&cc)) {
        boardCentiC = cc;
        boardTempValid = true;
        tmpFailCount = 0;
    } else if (++tmpFailCount >= 3) {
        boardTempValid = false;
    }
    const bool alert = digitalRead(PIN_TEMP_ALERT) == LOW;
    const int c = (int)(boardCentiC / 100);
    uint8_t up = 0;
    if (boardTempValid) {
        if (boardCentiC > OFFGRID_PA_TEMP_HIGH_C * 100)
            up = 3;
        else if (boardCentiC > OFFGRID_TCAP_HOT_C * 100)
            up = 2;
        else if (boardCentiC > OFFGRID_TCAP_WARM_C * 100)
            up = 1;
    }
    if (alert)
        up = 3;
    uint8_t level = tempLevel;
    if (up > level) {
        level = up;
    } else {
        // step down one level at a time, after cooling past the hysteresis
        if (level == 3 && !alert && (!boardTempValid || boardCentiC < OFFGRID_PA_TEMP_LOW_C * 100))
            level = 2;
        if (level == 2 && boardTempValid && boardCentiC < (OFFGRID_TCAP_HOT_C - OFFGRID_TCAP_HYST_C) * 100)
            level = 1;
        if (level == 1 && boardTempValid && boardCentiC < (OFFGRID_TCAP_WARM_C - OFFGRID_TCAP_HYST_C) * 100)
            level = 0;
    }
    if (level != tempLevel || alert != tempAlert) {
        static const char *const what[] = {"no cap", "33 dBm cap", "30 dBm cap", "amplifier OFF"};
        LOG_WARN("PA temperature %d C%s: %s", boardTempValid ? c : -999, alert ? " (TEMP_ALERT)" : "", what[level]);
    }
    tempLevel = level;
    tempAlert = alert;
}

void updateExternalPower()
{
    usbPower = NRF_POWER->USBREGSTATUS & POWER_USBREGSTATUS_VBUSDETECT_Msk;
    const uint16_t sol = readInputMv(SAADC_CH_PSELP_PSELP_AnalogInput2); // P0.04 SOLAR_OK
    const uint16_t drn = readInputMv(SAADC_CH_PSELP_PSELP_AnalogInput1); // P0.03 DRONE_OK
    const bool ext = usbPower || sol >= OFFGRID_EXT_IN_MIN_MV || drn >= OFFGRID_EXT_IN_MIN_MV;
    if (ext && !extPower) {
        LOG_INFO("External power in (USB %d, solar %u mV, drone %u mV)", usbPower, sol, drn);
        cellTestNextMs = millis() + 3000; // check for a cell once the input has settled
    }
    if (!ext && extPower) {
        LOG_INFO("External power out");
        if (noCell) {
            noCell = false; // the board is running, so something powers it: a cell
            LOG_INFO("Running on the cell: cell present");
        }
    }
    extPower = ext;
}

// Cell test (sim/README.md, residual risk): with external power in, hold /CE
// high for ~1 s.  With no cell, BAT_P then decays (below the reverse FET's
// polarity-check threshold, which clears its latch); with a cell it stays.
void cellTestStep(uint32_t now)
{
    if (!cellTestActive) {
        if (cellTestNextMs && (int32_t)(now - cellTestNextMs) >= 0 && extPower && !txActive) {
            cellTestActive = true;
            cellTestStartMs = now;
            cellTestNextMs = 0;
            digitalWrite(PIN_CHG_CE_N, HIGH);
        }
        return;
    }
    if (now - cellTestStartMs < OFFGRID_CELL_TEST_MS)
        return;
    const uint16_t v = readVbatMv();
    cellTestActive = false;
    digitalWrite(PIN_CHG_CE_N, chgInhibit ? HIGH : LOW);
    const bool none = v < OFFGRID_NOCELL_MV;
    if (none != noCell)
        LOG_WARN("Cell test: BAT_P %u mV after %u ms with charging off: %s", v, OFFGRID_CELL_TEST_MS,
                 none ? "NO CELL (amplifier from SYS, 1 W)" : "cell present");
    noCell = none;
    if (noCell && extPower)
        cellTestNextMs = now + OFFGRID_NOCELL_RETEST_MS; // notice a cell plugged in later
}

// STAT2 toggling with STAT1 high is the charger's no-battery signature
// (BQ25185 6.3.10): run the cell test when it is seen.
void watchStat2(uint32_t now)
{
    const bool s2 = digitalRead(PIN_CHG_STAT2);
    if (s2 != stat2Last) {
        stat2Last = s2;
        if (stat2Edges < 255)
            stat2Edges++;
    }
    if (now - stat2WindowMs >= 10000) {
        if (stat2Edges >= 4 && extPower && !noCell && !cellTestActive && !cellTestNextMs)
            cellTestNextMs = now;
        stat2Edges = 0;
        stat2WindowMs = now;
    }
}

void updateCharging(uint32_t now)
{
    if (!extPower) {
        cellTempValid = false; // ITSMR is only on with an input present
        return;
    }
    const uint16_t ts = saadcReadMv(CHG_TS_AIN, SAADC_CH_CONFIG_GAIN_Gain1_2);
    if (ts >= OFFGRID_TS_VALID_MIN_MV && ts < 1190) {
        const float r = ts * 1000.0f / OFFGRID_TS_BIAS_UA; // mV / uA = kOhm -> ohm
        const float invT = 1.0f / 298.15f + logf(r / OFFGRID_NTC_R25) / OFFGRID_NTC_BETA;
        cellCentiC = (int32_t)((1.0f / invT - 273.15f) * 100.0f);
        cellTempValid = true;
    } else if (ts >= 1190) {
        cellCentiC = -2000; // at or past the 1.2 V range: colder than about -10 C (or the NTC is open)
        cellTempValid = true;
    } else {
        cellTempValid = false; // under ~50 mV: no bias, or the cell is above ~80 C (charger's TS stops it)
    }
    if (cellTempValid) {
        const bool out = cellCentiC < OFFGRID_CHG_MIN_C * 100 || cellCentiC > OFFGRID_CHG_MAX_C * 100;
        const bool in = cellCentiC >= (OFFGRID_CHG_MIN_C + OFFGRID_CHG_HYST_C) * 100 &&
                        cellCentiC <= (OFFGRID_CHG_MAX_C - OFFGRID_CHG_HYST_C) * 100;
        bool inhibit = chgInhibit;
        if (out)
            inhibit = true;
        else if (in)
            inhibit = false;
        if (inhibit != chgInhibit)
            LOG_WARN("Cell %d C (NTC %u mV): charging %s", (int)(cellCentiC / 100), ts, inhibit ? "OFF" : "on");
        chgInhibit = inhibit;
    }
    if (!cellTestActive)
        digitalWrite(PIN_CHG_CE_N, chgInhibit ? HIGH : LOW);
    // TS/MR below VTSMR (90 mV, a cell above ~67 C) reads as a held button,
    // which after 10 s arms ship mode at the next input loss; toggling /CE
    // restarts that timer (circuit.py charger()).
    if (ts < 100 && !cellTestActive && now - tsToggleMs >= 5000) {
        tsToggleMs = now;
        digitalWrite(PIN_CHG_CE_N, chgInhibit ? LOW : HIGH);
        delay(20);
        digitalWrite(PIN_CHG_CE_N, chgInhibit ? HIGH : LOW);
    }
}

void updateBatteryCap(uint32_t now)
{
    if (!txActive && !cellTestActive && now - lastTxEndMs > 500) {
        vIdleMv = readVbatMv();
    }
    const int8_t was = battCap;
    if (noCell || vIdleMv == 0) {
        battCap = CAP_NONE; // no cell: the SYS cap applies instead
    } else {
        const int8_t c = burstCapLookup(vIdleMv, cellTempCentiC(), rint25);
        battCap = c == 0 ? CAP_PA_OFF : (c >= 35 ? CAP_NONE : c);
    }
    // Amplifier from SYS: no cell, or the cell cannot do 1 W and USB can
    const bool wantSys = noCell || (usbPower && battCap != CAP_NONE && battCap < 30);
    if (wantSys != paSrcSys && !paEnDrivenHigh()) {
        paSrcSys = wantSys;
        digitalWrite(PIN_PA_SRC_SYS, paSrcSys ? HIGH : LOW);
        paSetMv = 0; // the mux gap can reset the TPS63810: re-program below
        LOG_WARN("PA source: %s", paSrcSys ? "charger SYS (PA_SRC_SYS high)" : "battery");
    }
    if (battCap != was)
        LOG_INFO("Cell %u mV idle, %d C, R_int(25 C) %d mOhm%s: battery cap %d dBm", vIdleMv, (int)(cellTempCentiC() / 100),
                 (int)(rint25 * 1000), rintMeasured ? "" : " (assumed)", battCap == CAP_PA_OFF ? -1 : battCap);
}

// DC power drawn by the amplifier + buck-boost for a U.FL power (sim/thermal
// follow-up table A, nominal), W
float paDcWatts(float dbm)
{
    static const float P[5] = {30, 31.5f, 33, 34, 35};
    static const float W[5] = {2.65f, 3.25f, 4.59f, 5.78f, 7.20f};
    if (dbm <= P[0])
        return max(0.6f, W[0] * powf(10.0f, (dbm - 30.0f) / 10.0f));
    for (int i = 1; i < 5; i++)
        if (dbm <= P[i])
            return W[i - 1] + (W[i] - W[i - 1]) * (dbm - P[i - 1]) / (P[i] - P[i - 1]);
    return W[4];
}
} // namespace

// ---------------------------------------------------------------------------
// Transmit hooks (patch 0001 part 3)
// ---------------------------------------------------------------------------

// Before each packet, radio in standby: the SX1262 setting for this packet,
// and the supply it starts at.
int8_t variantLimitTxPower(int8_t power)
{
    paRestoreIfIdle();
    txSoft = false;
    txRaised = false;
    const int8_t cap = capDbm();
    if (cap == CAP_PA_OFF) {
        supplyTo(PA_VOUT_MIN_MV);
        paRelease();
        txDrive = -9;
        return -9;
    }
    int8_t d = power;
    if (cap != CAP_NONE) {
        const int8_t m = driveForCapDbm(cap);
        if (m < d)
            d = m;
    }
    txDrive = d;
    txTargetMv = paWantedMv();
    txSoft = softStartWanted(d, txTargetMv);
    if (!supplyTo(txSoft ? softStartMv(txTargetMv) : txTargetMv) && txSoft) {
        // The soft-start level could not be set, so the supply is unknown
        // (up to the licensed ceiling).  Hold the drive to the 1 W setting
        // instead: the gain table keeps that at or under 30 dBm at any supply.
        txSoft = false;
        const int8_t m = driveForCapDbm(OFFGRID_ANT_PROBE_DBM);
        if (m < d)
            txDrive = d = m;
        softFailPending = true;
    }
    // Let the TPS63810 finish ramping (at 1 V/ms) first: a rise, or the drop
    // to the soft-start level, which must not still be under way when the RF
    // starts.  Usually there is nothing left: variantTxDone() already brought
    // the supply back down after the last packet.
    waitForRamp();
    txPreambleUs = txSoft ? preambleUs() : 0;
    return d;
}

// Right after the SX1262 was told to transmit.  RadioLib (7.6.0,
// SX126x::launchMode) raises PA_EN, sends SetTx and then waits for BUSY to
// fall, which the SX1262 does only after its oscillator start, PLL lock and
// 200 us PA ramp: here the SX1262 is at full drive, the preamble has just
// begun and PA_EN has been high for at least ~0.25 ms.  The QPA9510's 2.8 V
// control supply (TLV75528, PA_EN) takes 550 us typical (no maximum given)
// to start, the QPA9510 ramps in ~40 us, and the detectors then settle in
// ~0.15 ms (FWD_DET) to ~0.46 ms (REFL_DET, antenna missing, 27 dBm, -40 C;
// sim/rf study 8).  OFFGRID_REFL_SAMPLE_US (750 us, >= 1 ms after PA_EN)
// covers the typical case with little to spare, so it is not shortened; the
// FWD_DET poll in antennaCheck() covers a late RF.
void variantTxStarted()
{
    txActive = true;
    txStartMs = millis();
    txRaised = false;
    if (paReleased || capDbm() == CAP_PA_OFF) {
        paRelease();
        txPest = -99;
        txSoft = false;
        return;
    }
    // An unknown supply (I2C failed) is taken as the highest it can be, so
    // the packet is checked rather than waved through
    txPest = modelUflDbm(txDrive, paSetMv != 0 ? paSetMv : PA_VOUT_ABS_MAX_MV);
    if (!txSoft && txPest < OFFGRID_REFL_MIN_DBM)
        return; // a missing antenna harms nothing down here
    uint32_t elapsedUs = OFFGRID_REFL_SAMPLE_US;
    delayMicroseconds(OFFGRID_REFL_SAMPLE_US);
    const AntVerdict v = antennaCheck(txPest, &elapsedUs);
    if (v == AV_FAULT) {
        antennaFault(); // amplifier off now; for a soft start that is from <= 1 W
        txSoft = false;
        return;
    }
    if (antState == ANT_PROBE) {
        // the 1 W retry found no fault (as before: the fallback alone may clear it)
        antState = ANT_OK;
        antBackoffMs = OFFGRID_ANT_RETRY_MS;
        antLogPending = true;
    }
    if (!txSoft)
        return;
    if (v != AV_OK) {
        antFwdLowPending = true; // only a trusted ratio clears a packet for more than 1 W
        return;
    }
    // Raise to the packet's own level: one VOUT1 write, then the TPS63810
    // slews at 1 V/ms (2.25 -> 3.6 V: 1.35 ms; -> 4.0 V: 1.75 ms).  LoRa
    // chirps are constant-envelope, so the receiver takes this amplitude step
    // in its stride as long as it lands inside the preamble (it only shifts
    // the level the receiver's gain settles on over a few preamble symbols);
    // if it would not, the packet stays at the soft-start level.
    const uint32_t rampUs = TPS_WRITE_US + (uint32_t)(txTargetMv - paSetMv) * 1000 / TPS_SLEW_MV_PER_MS;
    if (txPreambleUs == 0 || elapsedUs + rampUs + OFFGRID_SOFTSTART_PREAMBLE_MARGIN_US > txPreambleUs) {
        softLatePending = true;
        return;
    }
    if (tpsSetVout(txTargetMv)) {
        txRaised = true;
        txPest = modelUflDbm(txDrive, paSetMv);
    } else {
        paSetMv = 0; // unknown: the main loop re-programs it after the packet
    }
}

// The packet has gone (TX done interrupt handled).
void variantTxDone()
{
    if (!txActive)
        return;
    txActive = false;
    const uint32_t now = millis();
    const uint32_t dur = now - txStartMs;
    lastTxEndMs = now;
    // Soft start: back to the soft-start level now, so the TPS63810's ramp
    // down (1 V/ms) is over before the next packet starts.
    if (txRaised && !paReleased && paSetMv != 0 && !tpsSetVout(paIdleMv()))
        paSetMv = 0;
    txRaised = false;
    txSoft = false;
    // The cell's sag under this packet, read through VBAT_SENSE (0.6 M x
    // 100 nF = 60 ms, so scaled up for the part not yet reached), gives the
    // cell's resistance with the modelled amplifier current.
    if (txPest < 29.0f || dur < 40 || paSrcSys || noCell || vIdleMv == 0 || paReleased)
        return;
    const uint16_t vLoad = readVbatMv();
    if (vLoad >= vIdleMv || vLoad < 2000)
        return;
    const float sag = (vIdleMv - vLoad) / 1000.0f / (1.0f - expf(-(float)dur / 60.0f));
    const float amps = (paDcWatts(txPest) / 0.90f + 0.45f) / (vLoad / 1000.0f);
    float r = sag / amps - OFFGRID_BATT_PATH_MOHM / 1000.0f; // minus plug, reverse FET, protector, sense
    if (r < 0.01f)
        r = 0.01f;
    const float r25 = r / rintK(cellTempCentiC() / 100.0f);
    rint25 = rintMeasured ? 0.5f * rint25 + 0.5f * r25 : r25;
    rintMeasured = true;
}

// ---------------------------------------------------------------------------
// Meshtastic / Adafruit hooks
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

    // Charging on (the 100 k pull-down does the same with the pin floating);
    // the loop applies the 0-45 C window once it has a reading
    pinMode(PIN_CHG_CE_N, OUTPUT);
    digitalWrite(PIN_CHG_CE_N, LOW);
    pinMode(PIN_CHG_STAT1, INPUT);
    pinMode(PIN_CHG_STAT2, INPUT);
    pinMode(PIN_SOLAR_OK, INPUT); // analog (input voltage / 16)
    pinMode(PIN_DRONE_OK, INPUT);
    pinMode(PIN_TEMP_ALERT, INPUT);
    pinMode(PIN_REFL_DET, INPUT); // analog only
    pinMode(PIN_FWD_DET, INPUT);  // analog only
    pinMode(PIN_CHG_TS, INPUT);   // analog only

    // RF front end quiet until RadioLib takes TXEN/RXEN: amplifier control
    // voltage off (standby), LNA in bypass, amplifier source = battery first
    pinMode(PIN_PA_EN, OUTPUT);
    digitalWrite(PIN_PA_EN, LOW);
    pinMode(PIN_LNA_EN, OUTPUT);
    digitalWrite(PIN_LNA_EN, LOW);
    pinMode(PIN_PA_SRC_SYS, OUTPUT);
    digitalWrite(PIN_PA_SRC_SYS, LOW);

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
    // licensed level and the caps are applied from lateInitVariant().)
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

    // TMP1075: set the ALERT window explicitly (comparator mode, active low
    // are the power-on defaults).  Re-written here because the I2C scan in
    // setup() probes 0x48 with an unrelated chip's command sequence.
    uint8_t id[2];
    if (i2cRead(TMP1075_ADDR, TMP_REG_DIEID, id, 2)) {
        i2cWrite16(TMP1075_ADDR, TMP_REG_LLIM, (uint16_t)tmpLimitReg(OFFGRID_PA_TEMP_LOW_C));
        i2cWrite16(TMP1075_ADDR, TMP_REG_HLIM, (uint16_t)tmpLimitReg(OFFGRID_PA_TEMP_HIGH_C));
        LOG_INFO("TMP1075 id 0x%02x%02x, amplifier off at %d C (ALERT), back on below %d C", id[0], id[1],
                 OFFGRID_PA_TEMP_HIGH_C, OFFGRID_PA_TEMP_LOW_C);
    } else {
        LOG_WARN("TMP1075 not answering at 0x%02x: power capped at %d dBm", TMP1075_ADDR, OFFGRID_TCAP_HOT_DBM);
    }

    const uint32_t now = millis();
    updateTemperature();
    updateExternalPower();
    if (extPower)
        cellTestNextMs = now + 3000;
    updateCharging(now);
    updateBatteryCap(now);
    if (capDbm() == CAP_PA_OFF)
        paRelease();
    supplyTo(paIdleMv());
    LOG_INFO("PA supply %u mV (%s), cap %d dBm", paSetMv, devicestate.owner.is_licensed ? "licensed" : "unlicensed, 30 dBm",
             capDbm() == CAP_NONE ? 99 : capDbm());
    LOG_INFO("Antenna check: REFL/FWD > %d%% trips (FWD_DET >= %d mV); packets above %d dBm soft-start at %u mV (provisional)",
             OFFGRID_ANT_RATIO_MAX_PCT, OFFGRID_FWD_MIN_MV, OFFGRID_SOFTSTART_ABOVE_DBM, (unsigned)OFFGRID_SOFTSTART_VPA_MV);
    stat2WindowMs = now;
    paLastCheckMs = now;
}

// Every main-loop pass; the slow work runs once per OFFGRID_PA_CHECK_MS.
void variant_nrf52LoopHook(void)
{
    const uint32_t now = millis();
    if (txActive && now - txStartMs > 15000)
        txActive = false; // no TX-done seen (longest LoRa packet is ~5 s): stop waiting for it
    watchStat2(now);
    cellTestStep(now);

    if (antLogPending) {
        antLogPending = false;
        if (antState == ANT_BLOCKED && antLastByRatio)
            LOG_WARN("ANTENNA MISSING? REFL_DET %u mV / FWD_DET %u mV = %u%% > %d%% at ~%d dBm: amplifier off, retry at 1 W in %u s",
                     antLastReflMv, antLastFwdMv, (unsigned)(antLastReflMv * 100u / antLastFwdMv), OFFGRID_ANT_RATIO_MAX_PCT,
                     (int)txPest, (unsigned)(antBackoffMs / 1000));
        else if (antState == ANT_BLOCKED)
            LOG_WARN("ANTENNA MISSING? REFL_DET %u mV > %u mV (fallback: FWD_DET %u mV, too low for the ratio) at ~%d dBm: "
                     "amplifier off, retry at 1 W in %u s",
                     antLastReflMv, antLastThrMv, antLastFwdMv, (int)txPest, (unsigned)(antBackoffMs / 1000));
        else
            LOG_INFO("Antenna OK again (REFL_DET %u mV, FWD_DET %u mV%s): full power", antLastReflMv, antLastFwdMv,
                     antLastByRatio ? "" : ", fallback check only");
    }
    if (antFwdLowPending) {
        antFwdLowPending = false;
        LOG_WARN("Soft start held at 1 W: FWD_DET %u mV (< %d mV) at ~%d dBm, REFL_DET %u mV: RF late or forward detector fault",
                 antLastFwdMv, OFFGRID_FWD_MIN_MV, (int)txPest, antLastReflMv);
    }
    if (softLatePending) {
        softLatePending = false;
        LOG_WARN("Soft start held at 1 W: the raise would end after the %u us preamble", (unsigned)txPreambleUs);
    }
    if (softFailPending) {
        softFailPending = false;
        LOG_WARN("Soft start: TPS63810 not set, packet sent at the 1 W drive setting instead");
    }
    if (antNotifyPending && service) {
        antNotifyPending = false;
        meshtastic_ClientNotification *cn = clientNotificationPool.allocZeroed();
        if (cn) {
            cn->level = meshtastic_LogRecord_Level_WARNING;
            snprintf(cn->message, sizeof(cn->message), "LoRa antenna missing or damaged: amplifier off, retrying at 1 W");
            service->sendClientNotification(cn);
        }
    }
    if (antState == ANT_BLOCKED && (int32_t)(now - antRetryAtMs) >= 0)
        antState = ANT_PROBE; // the next packet goes at 1 W and is checked

    if (now - paLastCheckMs < OFFGRID_PA_CHECK_MS)
        return;
    paLastCheckMs = now;

    updateTemperature();
    updateExternalPower();
    updateCharging(now);
    updateBatteryCap(now);

    const int8_t cap = capDbm();
    if (cap != lastCapLogged) {
        LOG_INFO("TX cap now %d dBm at the U.FL (temperature %d, battery %d, antenna %d)", cap == CAP_NONE ? 99 : cap,
                 tempCapDbm(), paSrcSys ? OFFGRID_SYS_CAP_DBM : battCap, (int)antState);
        lastCapLogged = cap;
    }
    if (cap == CAP_PA_OFF)
        paRelease();
    else if (!txActive)
        paRestoreIfIdle();

    // Supply: not changed in the middle of a packet (a soft start raises it
    // there on purpose, and variantTxDone() brings it back down), except down
    // to "amplifier off", which PA_EN already enforces anyway.
    const uint16_t want = paIdleMv();
    if (voutCode(want) == voutCode(paSetMv) && tpsStillProgrammed())
        return;
    if ((txActive || paEnDrivenHigh()) && want != PA_VOUT_MIN_MV)
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
    digitalWrite(PIN_PA_SRC_SYS, LOW);
    paSetMv = 0;

    digitalWrite(PIN_GPS_EN, LOW);
    gpsPinsFloating();

    ledOff(PIN_LED1);
    ledOff(LED_BLUE);

    pinMode(PIN_DRONE_RTS, INPUT);
    // Charging falls back to the 100 k pull-down on /CE (on) and the
    // charger's own TS window (about 1-60 C).
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
