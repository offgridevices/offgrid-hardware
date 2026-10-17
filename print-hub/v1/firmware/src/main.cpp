// Print Hub v1 firmware: five switched USB ports for a resin printer's
// accessories, controlled over Wi-Fi (HTTP) or the USB-C DATA port (serial).
//
// The port logic (limits, timers, power budget) is lib/hub, tested on the
// host (test/).  This file is the glue: pins, settings in flash, Wi-Fi, the
// web page and API, the serial console, the LEDs.
//
// HTTP API (port 80)
//   GET  /                 a small control page
//   GET  /api/status       JSON, as the "status" command
//   POST /api/cmd          body: one command line (see lib/hub/src/cmd.h); JSON reply
// With a token set ("token SECRET" over USB), /api/* needs the header
// "Authorization: Bearer SECRET".  The token is never sent back.
//
// Board-only commands (here, on top of cmd.h's):
//   wifi "SSID" "password"   join a network (saved); wifi off  forget it
//   hostname printhub        mDNS name (printhub.local)
//   token SECRET | token off
//   ota http://host/firmware.bin   update over Wi-Fi, then restart
//   reboot | help
#include <Arduino.h>
#include <ESPmDNS.h>
#include <HTTPClient.h>
#include <HTTPUpdate.h>
#include <Preferences.h>
#include <WebServer.h>
#include <WiFi.h>
#include <esp_task_wdt.h>

#include "board.h"
#include "cmd.h"
#include "hub.h"
#include "page.h"

#ifndef PRINTHUB_VERSION
#define PRINTHUB_VERSION "dev"
#endif

static Board board;
static hub::Hub hubv(board);
static Preferences prefs;
static WebServer web(80);
static String wifi_ssid, wifi_pass, token, hostname_ = "printhub";
static bool ap_mode = false;
static uint32_t wifi_retry_at = 0;

// ------------------------------------------------------------ settings
static void save_config() {
  prefs.putBytes("cfg", &hubv.config(), sizeof(hub::Config));
}

static void load_settings() {
  prefs.begin("printhub", false);
  hub::Config c = hub::default_config();
  if (prefs.getBytesLength("cfg") == sizeof(hub::Config)) prefs.getBytes("cfg", &c, sizeof c);
  hubv.load(c);
  wifi_ssid = prefs.getString("ssid", "");
  wifi_pass = prefs.getString("pass", "");
  token = prefs.getString("token", "");
  hostname_ = prefs.getString("host", "printhub");
}

// ------------------------------------------------------------ commands
// "a b" 'c d' e  ->  [a b, c d, e]
static std::vector<std::string> shell_words(const std::string &s) {
  std::vector<std::string> out;
  std::string cur;
  char q = 0;
  bool any = false;
  for (char c : s) {
    if (q) {
      if (c == q) q = 0;
      else cur += c;
    } else if (c == '"' || c == '\'') {
      q = c; any = true;
    } else if (c == ' ' || c == '\t') {
      if (any || !cur.empty()) out.push_back(cur);
      cur.clear(); any = false;
    } else {
      cur += c;
    }
  }
  if (any || !cur.empty()) out.push_back(cur);
  return out;
}

static hub::Extra extra() {
  hub::Extra x;
  x.input_mv = board.input_mv();
  x.rail_mv = board.rail_mv();
  x.contract = board.contract();
  x.ip = WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString().c_str() : (ap_mode ? "192.168.4.1 (setup)" : "");
  x.version = PRINTHUB_VERSION;
  return x;
}

static std::string ok() { return "{\"ok\":true}"; }
static std::string err(const char *e) { return std::string("{\"ok\":false,\"error\":\"") + e + "\"}"; }

static void start_wifi();
static bool reboot_pending = false;

static std::string board_command(const std::string &verb, const std::string &rest, bool *handled, bool from_usb) {
  *handled = true;
  std::vector<std::string> a = shell_words(rest);
  if (verb == "help")
    return "{\"ok\":true,\"help\":\"status | on PORT.. [for 10m] | off PORT..|all [after 10m] | name N NAME | "
           "limit PORT MA | priority PORT 1-9 | boot PORT on|off | budget MA|auto | wifi \\\"SSID\\\" \\\"PASS\\\" | "
           "wifi off | hostname NAME | token SECRET|off | ota URL | reboot\"}";
  if (verb == "reboot") { reboot_pending = true; return ok(); }
  // network settings only over the USB cable: someone on Wi-Fi with the
  // token can switch ports, not move the board to another network
  if ((verb == "wifi" || verb == "token" || verb == "hostname") && !from_usb)
    return err("change this over the USB cable");
  if (verb == "wifi") {
    if (a.size() == 1 && a[0] == "off") {
      prefs.remove("ssid"); prefs.remove("pass"); wifi_ssid = ""; wifi_pass = "";
      WiFi.disconnect(true);
      return ok();
    }
    if (a.empty() || a.size() > 2 || a[0].empty() || a[0].size() > 32) return err("wifi \"SSID\" \"password\"");
    wifi_ssid = a[0].c_str();
    wifi_pass = a.size() > 1 ? a[1].c_str() : "";
    prefs.putString("ssid", wifi_ssid); prefs.putString("pass", wifi_pass);
    start_wifi();
    return ok();
  }
  if (verb == "token") {
    if (a.size() != 1) return err("token SECRET  or  token off");
    token = a[0] == "off" ? "" : a[0].c_str();
    prefs.putString("token", token);
    return ok();
  }
  if (verb == "hostname") {
    if (a.size() != 1 || a[0].empty() || a[0].size() > 24) return err("hostname NAME");
    hostname_ = a[0].c_str();
    prefs.putString("host", hostname_);
    MDNS.end(); MDNS.begin(hostname_.c_str()); MDNS.addService("http", "tcp", 80);
    return ok();
  }
  if (verb == "ota") {
    if (a.size() != 1 || a[0].rfind("http", 0) != 0) return err("ota http://host/firmware.bin");
    if (WiFi.status() != WL_CONNECTED) return err("not on Wi-Fi");
    for (int p = 0; p < hub::NPORTS; p++) hubv.set(p, false, millis());   // ports off while flashing
    WiFiClient client;
    httpUpdate.rebootOnUpdate(false);
    t_httpUpdate_return r = httpUpdate.update(client, a[0].c_str());
    if (r != HTTP_UPDATE_OK) return err(httpUpdate.getLastErrorString().c_str());
    reboot_pending = true;
    return ok();
  }
  *handled = false;
  return "";
}

static std::string command(const std::string &line, bool from_usb) {
  bool changed = false;
  std::string r = hub::run(hubv, line, millis(), extra(), &changed,
                           [&](const std::string &v, const std::string &rest, bool *handled) {
                             return board_command(v, rest, handled, from_usb);
                           });
  if (changed) save_config();
  return r;
}

// ------------------------------------------------------------ Wi-Fi + web
static void start_wifi() {
  WiFi.persistent(false);
  WiFi.setHostname(hostname_.c_str());
  if (wifi_ssid.length()) {
    ap_mode = false;
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.begin(wifi_ssid.c_str(), wifi_pass.c_str());
  } else {
    // no network yet: an open setup network, join it and open 192.168.4.1
    ap_mode = true;
    WiFi.mode(WIFI_AP);
    char name[32];
    snprintf(name, sizeof name, "PrintHub-%04X", (unsigned)(ESP.getEfuseMac() & 0xffff));
    WiFi.softAP(name);
  }
  MDNS.end();
  if (MDNS.begin(hostname_.c_str())) MDNS.addService("http", "tcp", 80);
}

static bool authorised() {
  if (!token.length()) return true;
  return web.header("Authorization") == "Bearer " + token;
}

static void send_json(int code, const std::string &body) {
  web.sendHeader("Cache-Control", "no-store");
  web.send(code, "application/json", body.c_str());
}

static void setup_web() {
  const char *keys[] = {"Authorization"};
  web.collectHeaders(keys, 1);
  web.on("/", HTTP_GET, [] { web.send_P(200, "text/html", PAGE); });
  web.on("/api/status", HTTP_GET, [] {
    if (!authorised()) return send_json(401, err("token required"));
    send_json(200, hub::status_json(hubv, millis(), extra()));
  });
  web.on("/api/cmd", HTTP_POST, [] {
    if (!authorised()) return send_json(401, err("token required"));
    std::string line = web.arg("plain").c_str();
    if (line.size() > 200) return send_json(400, err("too long"));
    for (auto &c : line)
      if (c == '\r' || c == '\n') c = ' ';
    // the setup network has no password: there, only joining Wi-Fi and
    // reading the status are allowed
    std::string r;
    if (ap_mode && line.rfind("wifi ", 0) == 0) {
      bool h;
      r = board_command("wifi", line.substr(5), &h, true);
    } else if (ap_mode && line != "status") {
      r = err("setup mode: join Wi-Fi first");
    } else {
      r = command(line, false);
    }
    send_json(r.rfind("{\"ok\":true", 0) == 0 ? 200 : 400, r);
  });
  web.onNotFound([] { web.send(404, "text/plain", "not found"); });
  web.begin();
}

// ------------------------------------------------------------ LEDs
static void update_leds(uint32_t now) {
  for (int p = 0; p < hub::NPORTS; p++) {
    const hub::PortState &s = hubv.state(p);
    uint32_t c;
    if (s.on) c = 0x002000;                                   // green: on
    else if (s.pending) c = 0x000020;                         // blue: about to come on
    else if (s.last_off == hub::Why::overcurrent || s.last_off == hub::Why::fault)
      c = ((now / 250) & 1) ? 0x200000 : 0;                   // red blink: tripped
    else if (s.last_off == hub::Why::shed || s.last_off == hub::Why::no_power) c = 0x201000;  // amber
    else c = 0;
    board.set_led(hub::NPORTS - p, c);   // the chain runs status, USB5 ... USB1
  }
  // the status LED: green on Wi-Fi, blue blink in setup mode, red when no charger
  uint32_t st;
  if (board.input_budget_ma() == 0) st = ((now / 500) & 1) ? 0x200000 : 0;
  else if (WiFi.status() == WL_CONNECTED) st = 0x002000;
  else if (ap_mode) st = ((now / 500) & 1) ? 0x000030 : 0;
  else st = 0x101000;
  board.set_led(0, st);
  board.show_leds();
}

// ------------------------------------------------------------ main
static std::string serial_line;

void setup() {
  board.begin();                    // every port switch off first
  Serial.begin(115200);
  load_settings();
  start_wifi();
  setup_web();
  esp_task_wdt_config_t wdt = {.timeout_ms = 8000, .idle_core_mask = 0, .trigger_panic = true};
  esp_task_wdt_reconfigure(&wdt);
  esp_task_wdt_add(nullptr);
}

void loop() {
  uint32_t now = millis();
  esp_task_wdt_reset();
  board.poll(now);
  hubv.tick(now);
  web.handleClient();

  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (!serial_line.empty()) Serial.println(command(serial_line, true).c_str());
      serial_line.clear();
    } else if (serial_line.size() < 200) {
      serial_line += c;
    }
  }

  // the BOOT button: a short press switches every port off
  if (board.button_pressed()) {
    for (int p = 0; p < hub::NPORTS; p++) hubv.set(p, false, now);
  }

  if (!ap_mode && wifi_ssid.length() && WiFi.status() != WL_CONNECTED && (int32_t)(now - wifi_retry_at) >= 0) {
    WiFi.reconnect();
    wifi_retry_at = now + 30000;
  }

  static uint32_t led_at = 0;
  if ((int32_t)(now - led_at) >= 0) {
    update_leds(now);
    led_at = now + 50;
  }
  if (reboot_pending) {
    delay(200);
    ESP.restart();
  }
  delay(10);
}
