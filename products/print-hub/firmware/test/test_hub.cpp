// Host tests of the port logic and the command language, with a fake board.
//   make -C firmware/test        (g++, no Arduino needed)
#include <stdio.h>
#include <string.h>

#include <string>

#include "../lib/hub/src/cmd.h"
#include "../lib/hub/src/hub.h"

using namespace hub;

static int fails = 0, checks = 0;
#define CHECK(c)                                                    \
  do {                                                              \
    checks++;                                                       \
    if (!(c)) { fails++; printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #c); } \
  } while (0)

struct Fake : Hal {
  bool en[NPORTS] = {};
  bool flt[NPORTS] = {};
  uint16_t draw[NPORTS] = {};   // what the device on each port would draw
  uint16_t budget = 3000;
  int16_t temp = 250;           // board temperature, tenths of a degree C
  int enables = 0;
  void set_enable(int p, bool on) override { if (on && !en[p]) enables++; en[p] = on; }
  bool fault(int p) override { return flt[p]; }
  uint16_t port_ma(int p) override { return en[p] ? draw[p] : 0; }
  uint16_t input_budget_ma() override { return budget; }
  int16_t board_temp_c10() override { return temp; }
};

static int n_on(const Fake &f) {
  int n = 0;
  for (int p = 0; p < NPORTS; p++) n += f.en[p];
  return n;
}

static void run_for(Hub &h, uint32_t &now, uint32_t ms) {
  for (uint32_t t = 0; t < ms; t += 10) { now += 10; h.tick(now); }
}

static std::string cmd(Hub &h, const char *line, uint32_t now, bool *ch = nullptr) {
  bool c;
  Extra x;
  x.version = "test";
  return run(h, line, now, x, ch ? ch : &c);
}

static bool ok(const std::string &r) { return r.rfind("{\"ok\":true", 0) == 0; }

int main() {
  // power-up: everything off
  {
    Fake f;
    Hub h(f);
    for (int p = 0; p < NPORTS; p++) CHECK(!f.en[p]);
  }
  // on / off by number and name, staggered switch-on
  {
    Fake f; Hub h(f); uint32_t now = 1000;
    for (int p = 0; p < NPORTS; p++) f.draw[p] = 400;
    CHECK(ok(cmd(h, "name 1 fan", now)));
    CHECK(ok(cmd(h, "name 2 light", now)));
    CHECK(h.find("FAN") == 0 && h.find("2") == 1 && h.find("usb3") == 2 && h.find("x") < 0);
    CHECK(ok(cmd(h, "on fan light 3", now)));
    // only one comes on at once
    int n = 0; for (int p = 0; p < NPORTS; p++) n += f.en[p];
    CHECK(n == 1);
    run_for(h, now, STAGGER_MS * 3);
    CHECK(f.en[0] && f.en[1] && f.en[2] && !f.en[3]);
    CHECK(ok(cmd(h, "off all", now)));
    for (int p = 0; p < NPORTS; p++) CHECK(!f.en[p]);
  }
  // timers: on for, off after
  {
    Fake f; Hub h(f); uint32_t now = 5;
    f.draw[0] = 300;
    CHECK(ok(cmd(h, "on 1 for 2s", now)));
    run_for(h, now, 1900);
    CHECK(f.en[0]);
    run_for(h, now, 200);
    CHECK(!f.en[0] && h.state(0).last_off == Why::timer);
    CHECK(ok(cmd(h, "on 1", now)));
    run_for(h, now, 100);
    CHECK(ok(cmd(h, "off 1 after 10m", now)));
    run_for(h, now, 9 * 60000);
    CHECK(f.en[0]);
    run_for(h, now, 61000);
    CHECK(!f.en[0]);
    CHECK(!ok(cmd(h, "on 1 for banana", now)));
    CHECK(!ok(cmd(h, "off 1 for 1m", now)));       // off takes "after", not "for"
  }
  // the timer survives millis() wrapping round
  {
    Fake f; Hub h(f); uint32_t now = 0xFFFFFF00u;
    f.draw[0] = 100;
    CHECK(ok(cmd(h, "on 1 for 1s", now)));
    run_for(h, now, 500);
    CHECK(f.en[0]);
    run_for(h, now, 600);
    CHECK(!f.en[0]);
  }
  // a port over its own limit is switched off, not during the switch-on surge
  {
    Fake f; Hub h(f); uint32_t now = 100;
    CHECK(ok(cmd(h, "limit 1 1000", now)));
    f.draw[0] = 1200;
    CHECK(ok(cmd(h, "on 1", now)));
    run_for(h, now, SETTLE_MS - 20);
    CHECK(f.en[0]);
    run_for(h, now, TRIP_MS + 50);
    CHECK(!f.en[0] && h.state(0).last_off == Why::overcurrent);
    CHECK(ok(cmd(h, "limit 1 1500", now)));
    CHECK(ok(cmd(h, "on 1", now)));
    run_for(h, now, 3000);
    CHECK(f.en[0]);
    CHECK(!ok(cmd(h, "limit 1 1600", now)));      // over the USB-A receptacle's 1.5 A
  }
  // a short spike over the limit does not trip
  {
    Fake f; Hub h(f); uint32_t now = 100;
    f.draw[0] = 500;
    cmd(h, "on 1", now);
    run_for(h, now, 1000);
    f.draw[0] = 2500; run_for(h, now, TRIP_MS - 100);
    f.draw[0] = 500; run_for(h, now, 1000);
    CHECK(f.en[0]);
  }
  // the switch's FAULT line
  {
    Fake f; Hub h(f); uint32_t now = 100;
    cmd(h, "on 2", now);
    run_for(h, now, 50);
    f.flt[1] = true;
    run_for(h, now, 20);
    CHECK(!f.en[1] && h.state(1).last_off == Why::fault);
  }
  // budget: refuse a port with no room, shed the lowest priority when over
  {
    Fake f; Hub h(f); uint32_t now = 100;
    f.budget = 1500;
    for (int p = 0; p < NPORTS; p++) f.draw[p] = 600;
    cmd(h, "priority 1 1", now);
    cmd(h, "priority 2 9", now);
    CHECK(ok(cmd(h, "on 1", now))); run_for(h, now, 1000);
    CHECK(ok(cmd(h, "on 2", now))); run_for(h, now, 1000);
    CHECK(f.en[0] && f.en[1]);
    std::string r = cmd(h, "on 3", now);       // 1200 used + 500 assumed > 1500
    CHECK(!ok(r) && r.find("not enough power") != std::string::npos);
    CHECK(!f.en[2]);
    f.draw[0] = 1000;                         // the fan speeds up: 1600 > 1500
    run_for(h, now, SHED_MS + 100);
    CHECK(f.en[0] && !f.en[1] && h.state(1).last_off == Why::shed);
    // no charger at all: refused, and what was on goes off
    f.budget = 0;
    CHECK(!ok(cmd(h, "on 4", now)));
    run_for(h, now, 20);
    CHECK(!f.en[0] && h.state(0).last_off == Why::no_power);
    // manual budget override: only on top of a working supply, 3 A at most
    CHECK(ok(cmd(h, "budget 2500", now)));
    CHECK(h.budget_ma() == 0);
    f.budget = 1500;
    CHECK(h.budget_ma() == 2500);
    CHECK(ok(cmd(h, "on 4", now)));
    CHECK(!ok(cmd(h, "budget 3001", now)));
    CHECK(!ok(cmd(h, "budget 6000", now)));
    CHECK(ok(cmd(h, "budget auto", now)));
    // the charger's own figure is capped at 3 A too (the case's heat)
    f.budget = 4100;
    CHECK(h.budget_ma() == MAX_BUDGET_MA && MAX_BUDGET_MA == 3000);
  }
  // boot_on ports come up after power-up, staggered, once there is a supply
  {
    Fake f; Hub h(f); uint32_t now = 0;
    Config c = default_config();
    c.port[0].boot_on = true; c.port[3].boot_on = true;
    f.budget = 0;                              // only the DATA cable
    h.load(c);
    run_for(h, now, 1000);
    for (int p = 0; p < NPORTS; p++) CHECK(!f.en[p]);
    f.budget = 3000;                           // the charger is plugged in
    run_for(h, now, 20);
    int n = 0; for (int p = 0; p < NPORTS; p++) n += f.en[p];
    CHECK(n == 1);                             // one at a time
    run_for(h, now, 1000);
    CHECK(f.en[0] && f.en[3] && !f.en[1]);
    // a port switched on by hand; then the charger is unplugged: all off
    CHECK(ok(cmd(h, "on 2", now)));
    run_for(h, now, 1000);
    CHECK(f.en[1]);
    f.budget = 0;
    run_for(h, now, 20);
    for (int p = 0; p < NPORTS; p++) CHECK(!f.en[p]);
    CHECK(h.state(1).last_off == Why::no_power);
    // plugged in again: the boot_on ports come back, port 2 stays off
    f.budget = 3000;
    run_for(h, now, 1000);
    CHECK(f.en[0] && f.en[3] && !f.en[1]);
  }
  // heat: the budget falls linearly from DERATE_C10 to DERATE_FULL_C10
  {
    Fake f; Hub h(f);
    f.budget = 4100;                           // a 30 W charger
    f.temp = 250;  CHECK(h.budget_ma() == 3000 && h.heat() == Heat::ok);
    f.temp = 740;  CHECK(h.budget_ma() == 3000 && h.heat() == Heat::ok);
    f.temp = 741;  CHECK(h.budget_ma() == 2934 && h.heat() == Heat::derating);
    f.temp = 755;  CHECK(h.budget_ma() == 2000 && h.heat() == Heat::derating);
    f.temp = 770;  CHECK(h.budget_ma() == 1000);
    f.temp = 799;  CHECK(h.budget_ma() == HOT_BUDGET_MA && h.heat() == Heat::derating);
    // never more than the charger gives
    f.budget = 1500;
    f.temp = 250;  CHECK(h.budget_ma() == 1500);
    f.temp = 755;  CHECK(h.budget_ma() == 1500);
    f.temp = 764;  CHECK(h.budget_ma() == 1400);
    // the status reports it
    f.temp = 755;
    std::string s = cmd(h, "status", 0);
    CHECK(s.find("\"temp_c\":75.5,\"heat\":\"derating\"") != std::string::npos);
    CHECK(s.find("\"budget_ma\":1500") != std::string::npos);
  }
  // heat: when the budget falls under what is on, the lowest priority goes first
  {
    Fake f; Hub h(f); uint32_t now = 100;
    f.budget = 4100;
    for (int p = 0; p < NPORTS; p++) f.draw[p] = 700;
    cmd(h, "priority 1 1", now);
    cmd(h, "priority 2 3", now);
    cmd(h, "priority 3 9", now);
    CHECK(ok(cmd(h, "on 1 2 3", now)));
    run_for(h, now, 2000);
    CHECK(n_on(f) == 3 && h.total_ma() == 2100);
    f.temp = 755;                              // 2000 mA left: one too many
    run_for(h, now, SHED_MS - 100);
    CHECK(n_on(f) == 3);                       // not at once
    run_for(h, now, 200);
    CHECK(f.en[0] && f.en[1] && !f.en[2] && h.state(2).last_off == Why::shed);
    run_for(h, now, 3 * SHED_MS);
    CHECK(f.en[0] && f.en[1]);                 // 1400 of 2000: nothing more to shed
    f.temp = 770;                              // 1000 mA left
    run_for(h, now, SHED_MS + 100);
    CHECK(f.en[0] && !f.en[1] && h.state(1).last_off == Why::shed);
    run_for(h, now, 3 * SHED_MS);
    CHECK(f.en[0]);                            // 700 of 1000
    std::string r = cmd(h, "on 4", now);       // 700 + 500 assumed > 1000
    CHECK(!ok(r) && r.find("not enough power") != std::string::npos);
  }
  // heat: at TRIP_C10 every port goes off as "hot"; back below RESUME_C10
  // only, and then the boot_on ones come back, staggered
  {
    Fake f; Hub h(f); uint32_t now = 0;
    Config c = default_config();
    c.port[0].boot_on = true; c.port[3].boot_on = true;
    for (int p = 0; p < NPORTS; p++) { c.port[p].priority = 5; f.draw[p] = 200; }
    h.load(c);
    run_for(h, now, 1000);
    CHECK(f.en[0] && f.en[3]);
    CHECK(ok(cmd(h, "on 2", now)));            // by hand, not boot_on
    CHECK(ok(cmd(h, "on 5 for 1h", now)));
    run_for(h, now, 1000);
    CHECK(n_on(f) == 4);
    f.temp = 799;
    run_for(h, now, 100);
    CHECK(n_on(f) == 4);                       // derated to 1000: 800 is on, all stay
    f.temp = 800;
    run_for(h, now, 10);
    CHECK(n_on(f) == 0 && h.heat() == Heat::hot && h.budget_ma() == 0);
    for (int p : {0, 1, 3, 4}) CHECK(h.state(p).last_off == Why::hot);
    CHECK(h.state(2).last_off == Why::none);   // was off already
    std::string r = cmd(h, "on 3", now);
    CHECK(!ok(r) && r.find("too hot") != std::string::npos);
    CHECK(cmd(h, "status", now).find("\"heat\":\"hot\"") != std::string::npos);
    // cooling, but not yet below RESUME_C10: still off
    f.temp = 770; run_for(h, now, 2000);
    f.temp = RESUME_C10; run_for(h, now, 2000);
    CHECK(n_on(f) == 0 && h.heat() == Heat::hot);
    CHECK(!ok(cmd(h, "on 3", now)));
    // the sensor lost while hot: stays off
    f.temp = NO_TEMP; run_for(h, now, 1000);
    CHECK(n_on(f) == 0 && h.heat() == Heat::hot);
    // below RESUME_C10: the boot_on ports come back, one at a time
    f.temp = RESUME_C10 - 1;
    run_for(h, now, 10);
    CHECK(n_on(f) == 1 && h.heat() == Heat::ok);
    run_for(h, now, 1000);
    CHECK(f.en[0] && f.en[3] && !f.en[1] && !f.en[4]);
    CHECK(h.state(1).last_off == Why::hot && h.state(4).last_off == Why::hot);
    CHECK(h.budget_ma() == 3000);              // 69.9 C: under DERATE_C10, the full budget
    CHECK(ok(cmd(h, "on 2", now)));            // and ports switch on by hand again
  }
  // heat: no reading, or one out of range, is a sensor fault: HOT_BUDGET_MA, no trip
  {
    Fake f; Hub h(f); uint32_t now = 100;
    f.budget = 4100;
    for (int16_t t : {NO_TEMP, (int16_t)-301, (int16_t)1501, (int16_t)32767}) {
      f.temp = t;
      CHECK(h.heat() == Heat::sensor_fault && h.budget_ma() == HOT_BUDGET_MA);
    }
    f.temp = -300; CHECK(h.heat() == Heat::ok && h.budget_ma() == 3000);
    f.draw[0] = 600; f.draw[1] = 600;
    f.temp = NO_TEMP;
    CHECK(ok(cmd(h, "on 1", now)));
    run_for(h, now, 1000);
    CHECK(f.en[0]);                            // not tripped
    std::string r = cmd(h, "on 2", now);       // 600 + 500 assumed > 1000
    CHECK(!ok(r));
    f.temp = 1600;                             // a shorted sensor reads hot: not a trip
    run_for(h, now, 1000);
    CHECK(f.en[0] && h.heat() == Heat::sensor_fault);
    std::string s = cmd(h, "status", now);
    CHECK(s.find("\"heat\":\"sensor_fault\"") != std::string::npos);
    f.temp = NO_TEMP;
    s = cmd(h, "status", now);
    CHECK(s.find("\"temp_c\":null,\"heat\":\"sensor_fault\"") != std::string::npos);
    f.temp = -55;
    CHECK(cmd(h, "status", now).find("\"temp_c\":-5.5,") != std::string::npos);
  }
  // heat: a budget override never goes above what the heat allows
  {
    Fake f; Hub h(f);
    f.budget = 1500;
    CHECK(ok(cmd(h, "budget 2500", 0)));
    f.temp = 250;  CHECK(h.budget_ma() == 2500);
    f.temp = 755;  CHECK(h.budget_ma() == 2000);
    f.temp = 770;  CHECK(h.budget_ma() == HOT_BUDGET_MA);
    f.temp = NO_TEMP; CHECK(h.budget_ma() == HOT_BUDGET_MA);
    f.temp = 800; h.tick(10);
    CHECK(h.budget_ma() == 0 && h.heat() == Heat::hot);
    f.temp = 300; h.tick(20);
    CHECK(h.budget_ma() == 2500 && h.heat() == Heat::ok);
  }
  // names and settings
  {
    Fake f; Hub h(f); uint32_t now = 0; bool ch = false;
    CHECK(ok(cmd(h, "name 1 exhaust-fan", now, &ch)) && ch);
    CHECK(!ok(cmd(h, "name 2 exhaust-fan", now)));     // duplicate
    CHECK(!ok(cmd(h, "name 2 has space", now)));
    CHECK(!ok(cmd(h, "name 2 9lives", now)));
    CHECK(!ok(cmd(h, "name 2 all", now)));
    CHECK(!ok(cmd(h, "name 2 abcdefghijklmnop", now)));  // 16 chars
    CHECK(ok(cmd(h, "boot exhaust-fan on", now)));
    CHECK(h.config().port[0].boot_on);
    CHECK(!ok(cmd(h, "frobnicate", now)));
    CHECK(!ok(cmd(h, "on", now)));
    CHECK(!ok(cmd(h, "on 6", now)));
    std::string s = cmd(h, "status", now);
    CHECK(s.find("\"name\":\"exhaust-fan\"") != std::string::npos && s.find("\"port\":5") != std::string::npos);
  }
  // durations
  {
    uint32_t ms;
    CHECK(parse_duration("90", &ms) && ms == 90000);
    CHECK(parse_duration("10m", &ms) && ms == 600000);
    CHECK(parse_duration("1.5h", &ms) && ms == 5400000);
    CHECK(!parse_duration("-1", &ms) && !parse_duration("3d", &ms) && !parse_duration("", &ms));
  }
  // the fallback gets the rest of the line, spaces kept
  {
    Fake f; Hub h(f); bool ch; Extra x;
    std::string got;
    std::string r = run(h, "wifi  My Net  pass word", 0, x, &ch,
                        [&](const std::string &v, const std::string &rest, bool *handled) {
                          got = v + "|" + rest; *handled = true; return std::string("{\"ok\":true}");
                        });
    CHECK(got == "wifi|My Net  pass word");
    CHECK(json_escape("a\"b\\c\n") == "a\\\"b\\\\c\\u000a");
  }
  printf("%d checks, %d failed\n", checks, fails);
  return fails ? 1 : 0;
}
