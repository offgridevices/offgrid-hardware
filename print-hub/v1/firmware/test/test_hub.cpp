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
  int enables = 0;
  void set_enable(int p, bool on) override { if (on && !en[p]) enables++; en[p] = on; }
  bool fault(int p) override { return flt[p]; }
  uint16_t port_ma(int p) override { return en[p] ? draw[p] : 0; }
  uint16_t input_budget_ma() override { return budget; }
};

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
    f.draw[0] = 1600;                       // over the 1500 default
    CHECK(ok(cmd(h, "on 1", now)));
    run_for(h, now, SETTLE_MS - 20);
    CHECK(f.en[0]);
    run_for(h, now, TRIP_MS + 50);
    CHECK(!f.en[0] && h.state(0).last_off == Why::overcurrent);
    CHECK(ok(cmd(h, "limit 1 1800", now)));
    CHECK(ok(cmd(h, "on 1", now)));
    run_for(h, now, 3000);
    CHECK(f.en[0]);
    CHECK(!ok(cmd(h, "limit 1 1900", now)));
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
    // no charger at all
    f.budget = 0;
    CHECK(!ok(cmd(h, "on 4", now)));
    // manual budget override
    CHECK(ok(cmd(h, "budget 4000", now)));
    CHECK(h.budget_ma() == 4000);
    CHECK(ok(cmd(h, "on 4", now)));
    CHECK(ok(cmd(h, "budget auto", now)));
  }
  // boot_on ports come up after power-up, staggered
  {
    Fake f; Hub h(f); uint32_t now = 0;
    Config c = default_config();
    c.port[0].boot_on = true; c.port[3].boot_on = true;
    h.load(c);
    run_for(h, now, 1000);
    CHECK(f.en[0] && f.en[3] && !f.en[1]);
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
