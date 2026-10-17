// The command language, the same over USB serial and over Wi-Fi (HTTP
// POST /api/cmd).  One command per line; every reply is one line of JSON,
// {"ok":true,...} or {"ok":false,"error":"..."}.
//
//   status                         every port, the charger, the budget
//   on fan light [for 10m]         switch on (optionally for a time)
//   off fan [after 10m]            switch off (optionally later)
//   on all / off all
//   name 1 fan                     name port 1 "fan" (letters, digits, - _)
//   limit fan 1200                 software current limit, mA (100..1800)
//   priority fan 1                 1 = switched off last when power runs short
//   boot fan on|off                switch on at power-up
//   budget 2500 | budget auto      override what the charger reports
//
// Ports are named or numbered 1..5 (or usb1..usb5).  Times: 90, 90s, 10m,
// 2h (a bare number is seconds).  Commands the port logic does not know
// (wifi, token, reboot ...) go to the firmware's own handler.
#pragma once
#include <functional>
#include <string>

#include "hub.h"

namespace hub {

struct Extra {
  // input-side readings the firmware adds to "status"
  uint16_t input_mv = 0;       // POWER IN voltage
  uint16_t rail_mv = 0;        // the 5 V port rail
  std::string contract;        // e.g. "9V 3A PD", "5V 1.5A Type-C", "none"
  std::string ip;              // Wi-Fi address, "" if not joined
  std::string version;
};

// returns the JSON reply; sets *changed when the saved settings changed
using Fallback = std::function<std::string(const std::string &verb, const std::string &rest, bool *handled)>;
std::string run(Hub &hub, const std::string &line, uint32_t now, const Extra &extra, bool *changed,
                const Fallback &fallback = nullptr);

std::string status_json(const Hub &hub, uint32_t now, const Extra &extra);
bool parse_duration(const std::string &s, uint32_t *ms);
std::string json_escape(const std::string &s);

}  // namespace hub
