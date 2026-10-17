#include "cmd.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <sstream>
#include <vector>

namespace hub {

std::string json_escape(const std::string &s) {
  std::string o;
  for (char c : s) {
    if (c == '"' || c == '\\') { o += '\\'; o += c; }
    else if ((unsigned char)c < 0x20) { char b[8]; snprintf(b, sizeof b, "\\u%04x", c); o += b; }
    else o += c;
  }
  return o;
}

static std::string err(const std::string &e) { return "{\"ok\":false,\"error\":\"" + json_escape(e) + "\"}"; }
static std::string ok() { return "{\"ok\":true}"; }

bool parse_duration(const std::string &s, uint32_t *ms) {
  if (s.empty()) return false;
  char *end;
  double v = strtod(s.c_str(), &end);
  if (end == s.c_str() || v < 0) return false;
  double mul = 1000;
  std::string u(end);
  if (u == "" || u == "s") mul = 1000;
  else if (u == "m" || u == "min") mul = 60e3;
  else if (u == "h") mul = 3600e3;
  else if (u == "ms") mul = 1;
  else return false;
  double r = v * mul;
  if (r > 7 * 24 * 3600e3) return false;   // a week at most: millis() arithmetic stays safe
  *ms = (uint32_t)r;
  return true;
}

static bool valid_name(const std::string &n) {
  if (n.empty() || n.size() > NAME_LEN || n == "all") return false;
  if (isdigit((unsigned char)n[0])) return false;   // would read as a port number
  for (char c : n)
    if (!isalnum((unsigned char)c) && c != '-' && c != '_') return false;
  return true;
}

std::string status_json(const Hub &h, uint32_t now, const Extra &x) {
  std::ostringstream o;
  o << "{\"ok\":true,\"version\":\"" << json_escape(x.version) << "\",\"input\":{\"mv\":" << x.input_mv
    << ",\"contract\":\"" << json_escape(x.contract) << "\"},\"rail_mv\":" << x.rail_mv
    << ",\"budget_ma\":" << h.budget_ma() << ",\"budget\":\"" << (h.config().budget_override_ma ? "manual" : "auto")
    << "\",\"total_ma\":" << h.total_ma() << ",\"ip\":\"" << json_escape(x.ip) << "\",\"ports\":[";
  for (int p = 0; p < NPORTS; p++) {
    const PortState &s = h.state(p);
    const PortConfig &c = h.config().port[p];
    long left = s.off_at ? (long)(int32_t)(s.off_at - now) : -1;
    if (left < -1) left = 0;
    o << (p ? "," : "") << "{\"port\":" << p + 1 << ",\"name\":\"" << json_escape(c.name) << "\",\"on\":"
      << (s.on ? "true" : "false") << ",\"pending\":" << (s.pending ? "true" : "false") << ",\"ma\":" << s.ma
      << ",\"limit_ma\":" << c.limit_ma << ",\"priority\":" << (int)c.priority << ",\"boot_on\":"
      << (c.boot_on ? "true" : "false") << ",\"off_in_s\":" << (left < 0 ? -1 : (left + 999) / 1000)
      << ",\"last_off\":\"" << why_str(s.last_off) << "\"}";
  }
  o << "]}";
  return o.str();
}

static std::vector<std::string> words(const std::string &line) {
  std::vector<std::string> w;
  std::istringstream in(line);
  std::string t;
  while (in >> t) w.push_back(t);
  return w;
}

static std::string lower(std::string s) {
  for (auto &c : s) c = (char)tolower((unsigned char)c);
  return s;
}

std::string run(Hub &h, const std::string &line, uint32_t now, const Extra &x, bool *changed,
                const Fallback &fallback) {
  *changed = false;
  std::vector<std::string> w = words(line);
  if (w.empty()) return err("empty command");
  std::string verb = lower(w[0]);

  if (verb == "status") return status_json(h, now, x);

  if (verb == "on" || verb == "off") {
    // on PORT... [for DUR]   off PORT... [after DUR]
    std::vector<int> ports;
    uint32_t dur = 0;
    bool timed = false;
    for (size_t i = 1; i < w.size(); i++) {
      std::string a = lower(w[i]);
      if ((a == "for" && verb == "on") || (a == "after" && verb == "off")) {
        if (i + 2 != w.size() || !parse_duration(w[i + 1], &dur)) return err("bad time: use e.g. 90s, 10m, 2h");
        timed = true;
        break;
      }
      if (a == "all") {
        for (int p = 0; p < NPORTS; p++) ports.push_back(p);
        continue;
      }
      int p = h.find(w[i]);
      if (p < 0) return err("no such port: " + w[i]);
      ports.push_back(p);
    }
    if (ports.empty()) return err("which port? e.g. '" + verb + " fan' or '" + verb + " 1'");
    std::string fails;
    for (int p : ports) {
      Err e = verb == "on" ? h.set(p, true, now, timed ? dur : 0)
                           : (timed ? h.off_after(p, now, dur) : h.set(p, false, now));
      if (e != Err::ok) fails += std::string(fails.empty() ? "" : "; ") + h.config().port[p].name + ": " + err_str(e);
    }
    if (!fails.empty()) return err(fails);
    return ok();
  }

  if ((verb == "name" || verb == "limit" || verb == "priority" || verb == "boot") && w.size() == 3) {
    int p = h.find(w[1]);
    if (p < 0) return err("no such port: " + w[1]);
    PortConfig &c = h.config_mut().port[p];
    if (verb == "name") {
      if (!valid_name(w[2])) return err("names: 1-15 letters, digits, - or _, not starting with a digit");
      for (int q = 0; q < NPORTS; q++)
        if (q != p && strcasecmp(h.config().port[q].name, w[2].c_str()) == 0) return err("name already used");
      snprintf(c.name, sizeof c.name, "%s", w[2].c_str());
    } else if (verb == "limit") {
      long v = strtol(w[2].c_str(), nullptr, 10);
      if (v < 100 || v > MAX_LIMIT_MA) return err("limit: 100 to 2000 mA");
      c.limit_ma = (uint16_t)v;
    } else if (verb == "priority") {
      long v = strtol(w[2].c_str(), nullptr, 10);
      if (v < 1 || v > 9) return err("priority: 1 (kept longest) to 9");
      c.priority = (uint8_t)v;
    } else {
      std::string a = lower(w[2]);
      if (a != "on" && a != "off") return err("boot: on or off");
      c.boot_on = a == "on";
    }
    *changed = true;
    return ok();
  }

  if (verb == "budget" && w.size() == 2) {
    if (lower(w[1]) == "auto") h.config_mut().budget_override_ma = 0;
    else {
      long v = strtol(w[1].c_str(), nullptr, 10);
      if (v < 100 || v > 6000) return err("budget: 100 to 6000 mA, or auto");
      h.config_mut().budget_override_ma = (uint16_t)v;
    }
    *changed = true;
    return ok();
  }

  if (fallback) {
    bool handled = false;
    // everything after the verb, spaces kept (a Wi-Fi password may have them)
    std::string rest;
    size_t i = line.find_first_of(" \t", line.find_first_not_of(" \t"));
    if (i != std::string::npos) i = line.find_first_not_of(" \t", i);
    if (i != std::string::npos) rest = line.substr(i);
    std::string r = fallback(verb, rest, &handled);
    if (handled) return r;
  }
  return err("unknown command '" + w[0] + "' (try: status, on, off, name, limit, priority, boot, budget, help)");
}

}  // namespace hub
