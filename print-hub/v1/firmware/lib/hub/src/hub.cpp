#include "hub.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

namespace hub {

// millis() wraps after 49 days: compare times by their difference
static bool reached(uint32_t now, uint32_t t) { return (int32_t)(now - t) >= 0; }
static uint32_t nonzero(uint32_t t) { return t ? t : 1; }

const char *why_str(Why w) {
  switch (w) {
    case Why::overcurrent: return "overcurrent";
    case Why::fault: return "fault";
    case Why::shed: return "shed";
    case Why::no_power: return "no_power";
    case Why::timer: return "timer";
    default: return "";
  }
}

const char *err_str(Err e) {
  switch (e) {
    case Err::bad_port: return "no such port";
    case Err::no_power: return "not enough power left from the charger";
    case Err::no_input: return "no charger on POWER IN";
    default: return "ok";
  }
}

Config default_config() {
  Config c{};
  for (int p = 0; p < NPORTS; p++) {
    snprintf(c.port[p].name, sizeof c.port[p].name, "usb%d", p + 1);
    c.port[p].limit_ma = DEFAULT_LIMIT_MA;
    c.port[p].priority = 5;
    c.port[p].boot_on = false;
  }
  return c;
}

Hub::Hub(Hal &hal) : hal_(hal), cfg_(default_config()) {
  for (int p = 0; p < NPORTS; p++) hal_.set_enable(p, false);
}

void Hub::load(const Config &c) {
  cfg_ = c;
  for (int p = 0; p < NPORTS; p++) {
    if (cfg_.port[p].limit_ma == 0 || cfg_.port[p].limit_ma > MAX_LIMIT_MA) cfg_.port[p].limit_ma = DEFAULT_LIMIT_MA;
    if (cfg_.port[p].priority < 1 || cfg_.port[p].priority > 9) cfg_.port[p].priority = 5;
    cfg_.port[p].name[NAME_LEN] = 0;
    if (cfg_.port[p].boot_on) st_[p].pending = true;   // tick() brings them up, staggered
  }
}

int Hub::find(const std::string &s) const {
  for (int p = 0; p < NPORTS; p++)
    if (strcasecmp(s.c_str(), cfg_.port[p].name) == 0) return p;
  char *end;
  long n = strtol(s.c_str(), &end, 10);
  if (!s.empty() && *end == 0 && n >= 1 && n <= NPORTS) return (int)n - 1;
  if (s.size() == 4 && strncasecmp(s.c_str(), "usb", 3) == 0 && s[3] >= '1' && s[3] < '1' + NPORTS)
    return s[3] - '1';
  return -1;
}

uint16_t Hub::total_ma() const {
  uint32_t t = 0;
  for (int p = 0; p < NPORTS; p++) t += st_[p].on ? st_[p].ma : 0;
  return t > 0xffff ? 0xffff : (uint16_t)t;
}

uint16_t Hub::budget_ma() const {
  return cfg_.budget_override_ma ? cfg_.budget_override_ma : hal_.input_budget_ma();
}

void Hub::enable(int p, uint32_t now) {
  PortState &s = st_[p];
  s.on = true;
  s.pending = false;
  s.on_since = now;
  s.over_since = 0;
  s.last_off = Why::none;
  hal_.set_enable(p, true);
}

void Hub::disable(int p, Why why) {
  PortState &s = st_[p];
  hal_.set_enable(p, false);
  s.on = false;
  s.pending = false;
  s.off_at = 0;
  s.over_since = 0;
  s.ma = 0;
  s.last_off = why;
}

Err Hub::set(int p, bool on, uint32_t now, uint32_t for_ms) {
  if (p < 0 || p >= NPORTS) return Err::bad_port;
  PortState &s = st_[p];
  if (!on) {
    if (s.on || s.pending) disable(p, Why::none);
    return Err::ok;
  }
  if (!s.on && !s.pending) {
    uint16_t budget = budget_ma();
    if (budget == 0) return Err::no_input;
    // room for what this port drew last time, counting the ports already
    // queued to come on at what they drew last time
    uint32_t want = s.learned_ma ? s.learned_ma : DEFAULT_EXPECT_MA;
    uint32_t committed = total_ma();
    for (int q = 0; q < NPORTS; q++)
      if (st_[q].pending) committed += st_[q].learned_ma ? st_[q].learned_ma : DEFAULT_EXPECT_MA;
    if (committed + want > budget) {
      s.last_off = Why::no_power;
      return Err::no_power;
    }
    s.pending = true;
  }
  s.off_at = for_ms ? nonzero(now + for_ms) : 0;
  tick(now);
  return Err::ok;
}

Err Hub::off_after(int p, uint32_t now, uint32_t after_ms) {
  if (p < 0 || p >= NPORTS) return Err::bad_port;
  if (!st_[p].on && !st_[p].pending) return Err::ok;
  if (after_ms == 0) return set(p, false, now);
  st_[p].off_at = nonzero(now + after_ms);
  return Err::ok;
}

void Hub::tick(uint32_t now) {
  // 1. bring up one queued port per stagger slot, highest priority first
  if (reached(now, next_stagger_)) {
    int best = -1;
    for (int p = 0; p < NPORTS; p++)
      if (st_[p].pending && (best < 0 || cfg_.port[p].priority < cfg_.port[best].priority)) best = p;
    if (best >= 0) {
      enable(best, now);
      next_stagger_ = now + STAGGER_MS;
    }
  }

  // 2. measure, then protect each port
  for (int p = 0; p < NPORTS; p++) {
    PortState &s = st_[p];
    if (!s.on) continue;
    s.ma = hal_.port_ma(p);
    if (hal_.fault(p)) {
      disable(p, Why::fault);
      continue;
    }
    if (s.off_at && reached(now, s.off_at)) {
      disable(p, Why::timer);
      continue;
    }
    if (!reached(now, s.on_since + SETTLE_MS)) continue;   // switch-on surge: the chip limits it
    if (s.ma > cfg_.port[p].limit_ma) {
      if (!s.over_since) s.over_since = nonzero(now);
      else if (reached(now, s.over_since + TRIP_MS)) {
        disable(p, Why::overcurrent);
        continue;
      }
    } else {
      s.over_since = 0;
    }
    // running average of what the port draws (1/8 per sample)
    s.learned_ma = s.learned_ma ? (uint16_t)((7u * s.learned_ma + s.ma) / 8u) : s.ma;
  }

  // 3. the charger's budget: shed the lowest-priority port if over too long
  uint16_t budget = budget_ma();
  if (budget && total_ma() > budget) {
    if (!over_budget_since_) over_budget_since_ = nonzero(now);
    else if (reached(now, over_budget_since_ + SHED_MS)) {
      int worst = -1;
      for (int p = 0; p < NPORTS; p++)
        if (st_[p].on && (worst < 0 || cfg_.port[p].priority >= cfg_.port[worst].priority)) worst = p;
      if (worst >= 0) disable(worst, Why::shed);
      over_budget_since_ = 0;
    }
  } else {
    over_budget_since_ = 0;
  }
}

}  // namespace hub
