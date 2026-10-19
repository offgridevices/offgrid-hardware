# Print Hub v1: Home Assistant

Home Assistant can switch the hub's ports and show what they draw, using the
same local HTTP API as the `printhub` command. Nothing to install on the
hub; everything below is YAML for Home Assistant's `configuration.yaml`.

## The API, in short

| | |
|---|---|
| `GET http://printhub.local/api/status` | JSON: every port, the charger, the budget, the board's temperature |
| `POST http://printhub.local/api/cmd` | the body is one command line (`on 1`, `off all`, `on 3 for 2h` ...); JSON back |
| Token | if one is set (`printhub token SECRET`, over USB), every request needs `Authorization: Bearer SECRET` |
| Replies | `200` with `{"ok":true,...}`; `400` with `{"ok":false,"error":"..."}` (for example "not enough power left from the charger"); `401` with a wrong or missing token |

Send the command with `Content-Type: text/plain`: the board reads a
form-encoded body (what `curl -d` sends by default) as no command at all.

The parts of `/api/status` used here:

```
{"ok":true, "budget_ma":3000, "total_ma":1050, "temp_c":41.5, "heat":"ok",
 "ports":[{"port":1, "name":"fan", "on":true, "pending":false, "ma":450, "last_off":""}, ...]}
```

- `ports[0]` is port 1, `ports[4]` port 5. `pending` is true for a moment
  while a port waits its turn to come on (ports switched on together come
  up a quarter of a second apart).
- `temp_c` is the board's temperature beside the power converter, `null`
  with no reading. `heat` is `ok`, `derating` (warm: the hub gives the ports
  less power), `hot` (too hot: every port is off until it cools) or
  `sensor_fault` (no reading: the hub gives the ports less power, to be safe).
- `last_off` says why a port last went off: `overcurrent`, `fault`, `shed`,
  `no_power`, `timer`, `hot`, or empty when switched off by a command.

Try it from any computer on the network first:

```
curl http://printhub.local/api/status
curl -H 'Content-Type: text/plain' --data 'on 1' http://printhub.local/api/cmd
```

## The token

If the hub has a token, put it in `secrets.yaml` once:

```yaml
printhub_auth: "Bearer SECRET"
```

With no token set on the hub, the header is ignored, so the YAML below works
either way (keep `printhub_auth: "Bearer none"` then).

## A switch per port

One RESTful switch per port. Use the port numbers, not names: they stay the
same if a port is renamed.

```yaml
switch:
  - platform: rest
    name: Print Hub fan
    unique_id: printhub_port_1
    resource: http://printhub.local/api/cmd
    state_resource: http://printhub.local/api/status
    method: post
    body_on: "on 1"
    body_off: "off 1"
    is_on_template: "{{ value_json.ports[0].on or value_json.ports[0].pending }}"
    headers:
      Content-Type: text/plain
      Authorization: !secret printhub_auth
  - platform: rest
    name: Print Hub light
    unique_id: printhub_port_2
    resource: http://printhub.local/api/cmd
    state_resource: http://printhub.local/api/status
    method: post
    body_on: "on 2"
    body_off: "off 2"
    is_on_template: "{{ value_json.ports[1].on or value_json.ports[1].pending }}"
    headers:
      Content-Type: text/plain
      Authorization: !secret printhub_auth
  # ports 3, 4 and 5 the same: "on 3" / "off 3" and value_json.ports[2], and so on
```

When the hub refuses (not enough power, too hot), Home Assistant logs the
error and the switch shows off again at its next poll.

## Timers and other commands

The hub runs its own timers, so they still happen if Home Assistant restarts.
One `rest_command` sends any command line:

```yaml
rest_command:
  printhub:
    url: http://printhub.local/api/cmd
    method: post
    content_type: text/plain
    headers:
      Authorization: !secret printhub_auth
    payload: "{{ command }}"
```

and in an automation or script:

```yaml
- action: rest_command.printhub
  data:
    command: "off 1 after 15m"
```

(`on 1 2 3 for 2h`, `off all`, `off 3 4 after 30m` ...: `firmware/lib/hub/src/cmd.h`
lists every command.)

## Current and temperature sensors

One poll of `/api/status` feeds every sensor:

```yaml
rest:
  - resource: http://printhub.local/api/status
    scan_interval: 10
    headers:
      Authorization: !secret printhub_auth
    sensor:
      - name: Print Hub port 1 current
        unique_id: printhub_port_1_ma
        value_template: "{{ value_json.ports[0].ma }}"
        unit_of_measurement: mA
        device_class: current
        state_class: measurement
      - name: Print Hub port 2 current
        unique_id: printhub_port_2_ma
        value_template: "{{ value_json.ports[1].ma }}"
        unit_of_measurement: mA
        device_class: current
        state_class: measurement
      # ports 3, 4 and 5 the same, with ports[2], ports[3], ports[4]
      - name: Print Hub total current
        unique_id: printhub_total_ma
        value_template: "{{ value_json.total_ma }}"
        unit_of_measurement: mA
        device_class: current
        state_class: measurement
      - name: Print Hub power available
        unique_id: printhub_budget_ma
        value_template: "{{ value_json.budget_ma }}"
        unit_of_measurement: mA
        device_class: current
      - name: Print Hub board temperature
        unique_id: printhub_temp
        value_template: "{{ value_json.temp_c }}"
        availability: "{{ value_json.temp_c is not none }}"   # no reading: unavailable
        unit_of_measurement: "°C"
        device_class: temperature
        state_class: measurement
      - name: Print Hub heat
        unique_id: printhub_heat
        value_template: "{{ value_json.heat }}"
```

A notification when the hub gets warm is then an ordinary automation on
`sensor.print_hub_heat` changing from `ok`.

## Plain HTTP, on the local network only

The hub talks plain HTTP, not HTTPS. HTTPS needs a certificate that the
browser or Home Assistant trusts, and a small device on a home network has
no public name to get one for; a certificate it made itself would only give
warnings, or be turned off in every client. So:

- **Keep the hub off the open internet.** No port forwarding to it. To reach
  it from outside, go through Home Assistant's own remote access or a VPN.
- **Set a token** (`printhub token SECRET` over USB) if others share the
  network. The token goes over the network unencrypted, so it keeps out
  casual use, not someone who can watch the Wi-Fi traffic.
- Network settings (Wi-Fi, token, hostname) can only be changed over the USB
  cable, never over HTTP.

## If `printhub.local` does not resolve

Some Home Assistant installs do not resolve `.local` names (mDNS). Give the
hub a fixed address in the router (a DHCP reservation) and use that address
in place of `printhub.local`. `printhub status` shows the address.

## Later: MQTT discovery

Not implemented. An MQTT client in the firmware with Home Assistant's MQTT
discovery would make the ports and sensors appear by themselves, with no
YAML, and update at once rather than at each poll. It would need an MQTT
broker on the network (Home Assistant's Mosquitto add-on) and the broker's
address and login set over USB.
