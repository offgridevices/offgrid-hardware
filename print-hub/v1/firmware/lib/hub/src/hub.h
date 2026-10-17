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
//   tick()     a port over its own limit for TRIP_MS is switched off and
//              marked "overcurrent"; a FAULT line switches it off as
//              "fault"; when all the ports together draw more than the
//              charger can give for SHED_MS, the lowest-priority port that
//              is on is switched off and marked "shed"
//   set()      a port is not switched on when the charger has no room left
//              for what it drew last time ("no_power"); several ports
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
constexpr uint16_t MAX_LIMIT_MA = 1800;     // the switch chip's own limit is 1.92 A at least
constexpr uint16_t DEFAULT_EXPECT_MA = 500; // a port never seen on is assumed to draw this

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

enum class Why : uint8_t { none, overcurrent, fault, shed, no_power, timer };
const char *why_str(Why w);

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
  virtual ~Hal() {}
};

enum class Err { ok, bad_port, no_power, no_input };
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
  uint16_t budget_ma() const;

 private:
  void enable(int p, uint32_t now);
  void disable(int p, Why why);
  Hal &hal_;
  Config cfg_;
  PortState st_[NPORTS];
  uint32_t over_budget_since_ = 0;
  uint32_t next_stagger_ = 0;
};

Config default_config();

}  // namespace hub
