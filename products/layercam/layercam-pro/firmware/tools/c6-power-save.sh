#!/bin/sh
# Turn the ESP32-C6's Wi-Fi power save on in esp-hosted's C6 firmware,
# before building it with ESP-IDF (README.md, "Heat and power").
#
#   tools/c6-power-save.sh path/to/esp-hosted/esp/esp_driver/network_adapter
#
# esp-hosted's C6 firmware starts with modem sleep off
# (esp_wifi_set_ps(WIFI_PS_NONE) in main/cmd.c, "line-powered adapter"), and
# its Linux driver cannot change that.  LayerCam Pro is rated for a 65 C
# chamber with modem sleep on (sim/thermal.md): this changes the call to
# WIFI_PS_MIN_MODEM.  It stops, changing nothing, if the call is not there
# exactly once (a newer esp-hosted: look at main/cmd.c by hand).
set -eu
dir=${1:?usage: $0 path/to/network_adapter}
f="$dir/main/cmd.c"
[ -f "$f" ] || { echo "error: no $f"; exit 1; }
n=$(grep -c 'esp_wifi_set_ps(WIFI_PS_NONE)' "$f" || true)
if [ "$n" != 1 ]; then
	grep -q 'esp_wifi_set_ps(WIFI_PS_MIN_MODEM)' "$f" && { echo "already on: $f"; exit 0; }
	echo "error: esp_wifi_set_ps(WIFI_PS_NONE) appears $n times in $f, not once: change it by hand"
	exit 1
fi
sed -i 's/esp_wifi_set_ps(WIFI_PS_NONE)/esp_wifi_set_ps(WIFI_PS_MIN_MODEM)/' "$f"
echo "power save on: $f (now build with idf.py)"
