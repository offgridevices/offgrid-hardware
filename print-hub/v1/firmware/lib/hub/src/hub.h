// Print Hub: the port logic, with no Arduino or ESP-IDF in it, so the same
// code runs on the board and in the host tests (firmware/test).
//
// Five switched USB-A ports.  Each has a name ("fan", "light" ...), a
// software current limit below the switch chip's own hardware limit, a
// priority for load shedding, and whether it comes on at power-up.
//
// What protects what:
//   hardware   each port's power switch limits its current and shuts down
//              on a short or overheat (its FAULT line tells us)
//   heat       the closed case sheds the heat of about 3 A (MAX_BUDGET_MA);
//              an NTC beside the buck reads the board's hottest corner:
//              from DERATE_C10 the budget falls, down to HOT_BUDGET_MA at
//              DERATE_FULL_C10 (load shedding then switches ports off);
//              at TRIP_C10 every port goes off as "hot", and the boot_on
//              ones come back, staggered, once it is below RESUME_C10.
//              No reading (sensor open or shorted) or one outside
//              -30..150 C: HOT_BUDGET_MA, reported as "sensor_fault"
//   tick()     no 9 V supply (no charger, a 5 V one, or unplugged): every
//              port off as "no_power"; when it returns, the ports set to
//              come on at power-up come back, staggered
//              a port over its own limit for TRIP_MS is switched off and
//              marked "overcurrent"; a FAULT line switches it off as
//              "fault"; when all the ports together draw more than the
//              budget (charger, heat) for SHED_MS, the lowest-priority
//              port that is on is switched off and marked "shed"
//   set()      a port is not switched on when the budget has no room left
//              for what it drew last time ("no_power"), nor at all while
//              too hot; several ports
//              switched on together come on STAGGER_MS apart, so their
//              switch-on surges do not add up
#pragma once
#include <stdint.h>
#include <string>

namespace hub {

constexpr int NPORTS = 5;
constexpr int NAME_LEN = 15;

constexpr uint32_t TRIP_MS = 500;      // over a port's limit this long: off
constexpr uint32_t SHED_MS = 1000;     // over the input budget this long: shed one port
constexpr uint32_t STAGGER_MS = 250;   // between ports switched on together
constexpr uint32_t SETTLE_MS = 300;    // ignore a port's current this long after switch-on (surge)
constexpr uint16_t DEFAULT_LIMIT_MA = 1500;
constexpr uint16_t MAX_LIMIT_MA = 1500;     // the USB-A receptacle's rating (1.5 A per contact);
                                            // the switch chip's own limit is 1.92-2.21 A above it
constexpr uint16_t MAX_BUDGET_MA = 3000;    // all the ports together: the buck is rated 5 A, but the
                                            // closed case only sheds about 3 A's heat (sim/thermal/board_heat.md)
constexpr uint16_t DEFAULT_EXPECT_MA = 500; // a port never seen on is assumed to draw this

// board temperature, tenths of a degree C (the NTC beside the buck)
constexpr int16_t NO_TEMP = INT16_MIN;      // no reading: sensor open, shorted or not read yet
constexpr int16_t TEMP_MIN_C10 = -300;      // readings outside -30..150 C are a sensor fault
constexpr int16_t TEMP_MAX_C10 = 1500;
constexpr int16_t DERATE_C10 = 750;         // from here the budget falls ...
constexpr int16_t DERATE_FULL_C10 = 900;    // ... linearly, to HOT_BUDGET_MA here
constexpr int16_t TRIP_C10 = 1000;          // every port off ("hot")
constexpr int16_t RESUME_C10 = 850;         // below this, after a trip, the boot_on ports come back
constexpr uint16_t HOT_BUDGET_MA = 1000;    // the budget when hot, or with no reading

struct PortConfig {
  char name[NAME_LEN + 1];
  uint16_t limit_ma;   // software trip
  uint8_t priority;    // 1 = shed last ... 9 = shed first
  bool boot_on;        // switch on at power-up
};

struct Config {
  PortConfig port[NPORTS];
  uint16_t budget_override_ma;  // 0: use what the charger reports
};

enum class Why : uint8_t { none, overcurrent, fault, shed, no_power, timer, hot };
const char *why_str(Why w);

enum class Heat : uint8_t { ok, derating, hot, sensor_fault };
const char *heat_str(Heat h);

struct PortState {
  bool on = false;          // switch enabled
  bool pending = false;     // queued to come on (stagger)
  uint32_t on_since = 0;
  uint32_t off_at = 0;      // 0: no timer
  uint32_t over_since = 0;  // first sample over the limit, 0: not over
  uint16_t ma = 0;          // last measured current
  uint16_t learned_ma = 0;  // running average while on, for the budget
  Why last_off = Why::none; // why it last went off (none: by command)
};

// What the board gives the logic.  The firmware implements it on the pins;
// the tests implement it with a fake.
struct Hal {
  virtual void set_enable(int port, bool on) = 0;
  virtual bool fault(int port) = 0;          // switch FAULT line active
  virtual uint16_t port_ma(int port) = 0;    // measured current
  virtual uint16_t input_budget_ma() = 0;    // what the charger can give at 5 V, 0 if no charger
  virtual int16_t board_temp_c10() = 0;      // board temperature, tenths of a degree C, NO_TEMP if none
  virtual ~Hal() {}
};

enum class Err { ok, bad_port, no_power, no_input, hot };
const char *err_str(Err e);

class Hub {
 public:
  explicit Hub(Hal &hal);
  void load(const Config &c);               // after power-up: applies boot_on
  const Config &config() const { return cfg_; }
  Config &config_mut() { return cfg_; }

  // port: 0..NPORTS-1.  for_ms > 0: switch off again after that long.
  Err set(int port, bool on, uint32_t now, uint32_t for_ms = 0);
  Err off_after(int port, uint32_t now, uint32_t after_ms);
  void tick(uint32_t now);

  int find(const std::string &name_or_number) const;  // -1: none
  const PortState &state(int p) const { return st_[p]; }
  uint16_t total_ma() const;
  uint16_t budget_ma() const;                // min(charger or override, heat, MAX_BUDGET_MA)
  uint16_t heat_budget_ma() const;           // what the board's temperature allows
  int16_t temp_c10() const { return hal_.board_temp_c10(); }
  Heat heat() const;

 private:
  void enable(int p, uint32_t now);
  void disable(int p, Why why);
  Hal &hal_;
  Config cfg_;
  PortState st_[NPORTS];
  uint32_t over_budget_since_ = 0;
  bool had_power_ = false;
  bool hot_ = false;          // tripped at TRIP_C10, not yet below RESUME_C10
  uint32_t next_stagger_ = 0;
};

Config default_config();

}  // namespace hub
