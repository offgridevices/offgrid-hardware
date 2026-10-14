#!/usr/bin/env bash
# One-time SWD flash of the four AM32 ESC MCUs (STM32G071GBU6) on the
# OffGrid Ridge 3 Lite v1, with an ST-Link V2 (genuine or clone).
#
# What goes where (AM32 layout, Inc/targets.h MCU_G071):
#   0x08000000  AM32 bootloader, DShot/signal input on PB4, 64K layout  (4 KB)
#   0x08001000  AM32 application GEN_64K_G071 (APPLICATION_ADDRESS)
#   0x0800F7E0  firmware tag "GEN_64K_G071" (part of the application hex)
#   0x0800F800  settings EEPROM page (written by the firmware / ESC-configurator)
#
# Recommended (default): flash ONLY the bootloader here, then flash the
# firmware and write default settings with ESC-configurator through
# Betaflight passthrough (see ../README.md).  That way the settings page is
# written by the tool that understands it.
#   --with-app  also writes the application hex over SWD (useful if you have
#               no flight-controller firmware yet).  The settings page stays
#               blank; open ESC-configurator afterwards, read the ESCs, check
#               the settings and press "Write setup" (or "Restore defaults")
#               before the first flight.
#   --erase     full-chip erase first (an ESC that was programmed before, or
#               that refuses to write).  Safe on a blank chip too.
#   --tool st-flash   use stlink-tools' st-flash instead of openocd.
#
# Wiring for each ESC n (pads on the board; n = 1..4):
#   ST-Link SWDIO -> TP_Dn      ST-Link SWCLK -> TP_Cn      ST-Link GND -> TP_GND
#   Power: plug the board's USB-C into a computer or USB charger (no battery).
#   USB 5 V feeds the ESC 3.3 V LDO, so all four ESC MCUs are powered.
#   Do NOT also connect the ST-Link 3.3 V output to TP_3V3 while USB is in.
#   (Without USB: ST-Link 3.3 V -> TP_3V3 also works, it powers the ESC rail
#   directly; never connect a battery while flashing.)
#   NRST of the ESC MCUs is not brought out: the script connects without a
#   reset line (software reset over SWD), which works on blank chips and on
#   AM32, which leaves PA13/PA14 as SWD.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
BL="$HERE/AM32_G071_BOOTLOADER_PB4_64K_V19.hex"
APP="$HERE/AM32_GEN_64K_G071_2.21.hex"
BL_SHA=780a052748cd7214bca96f93b506b068f5e426b7fb18db836cee1ec56f113e48
APP_SHA=a6f3765c077c14f2ab25e84f38b249c5edc9bbc95fda5955d58448e1e1185200

TOOL=openocd; WITH_APP=0; ERASE=0; ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --with-app) WITH_APP=1 ;;
    --erase) ERASE=1 ;;
    --tool) TOOL="$2"; shift ;;
    --esc) ONLY="$2"; shift ;;
    -h|--help) sed -n '2,36p' "$0"; exit 0 ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
  shift
done

check() {  # file sha
  local got; got=$(sha256sum "$1" | cut -d' ' -f1)
  [ "$got" = "$2" ] || { echo "sha256 mismatch for $1"; echo " got  $got"; echo " want $2"; exit 1; }
}
check "$BL" "$BL_SHA"
[ "$WITH_APP" = 1 ] && check "$APP" "$APP_SHA"

case "$TOOL" in
  openocd)  command -v openocd >/dev/null || { echo "openocd not found (apt install openocd / brew install open-ocd)"; exit 1; } ;;
  st-flash) command -v st-flash >/dev/null || { echo "st-flash not found (apt install stlink-tools / brew install stlink)"; exit 1; } ;;
  *) echo "--tool must be openocd or st-flash"; exit 2 ;;
esac

flash_openocd() {
  local cmds=(-f interface/stlink.cfg -f target/stm32g0x.cfg
              -c "adapter speed 1000" -c "reset_config none" -c "init" -c "reset halt")
  if [ "$ERASE" = 1 ]; then
    cmds+=(-c "stm32l4x mass_erase 0")
  fi
  cmds+=(-c "flash write_image erase \"$BL\"" -c "verify_image \"$BL\"")
  if [ "$WITH_APP" = 1 ]; then
    cmds+=(-c "flash write_image erase \"$APP\"" -c "verify_image \"$APP\"")
  fi
  cmds+=(-c "reset run" -c "shutdown")
  openocd "${cmds[@]}"
}

flash_stflash() {
  if [ "$ERASE" = 1 ]; then st-flash erase; fi
  st-flash --reset --format ihex write "$BL"
  if [ "$WITH_APP" = 1 ]; then st-flash --reset --format ihex write "$APP"; fi
}

echo "AM32 bootloader : $(basename "$BL")"
[ "$WITH_APP" = 1 ] && echo "AM32 firmware   : $(basename "$APP")"
echo "Tool            : $TOOL"
echo
echo "Board on USB power only, no battery.  ST-Link GND -> TP_GND."
for n in 1 2 3 4; do
  if [ -n "$ONLY" ] && [ "$ONLY" != "$n" ]; then continue; fi
  while true; do
    echo
    echo "=== ESC $n ===  SWDIO -> TP_D$n   SWCLK -> TP_C$n   (GND -> TP_GND)"
    read -r -p "Press Enter to flash ESC $n, 's' to skip: " ans
    [ "$ans" = "s" ] && { echo "ESC $n skipped"; break; }
    if [ "$TOOL" = openocd ]; then flash_openocd && ok=1 || ok=0; else flash_stflash && ok=1 || ok=0; fi
    if [ "$ok" = 1 ]; then echo "ESC $n: OK"; break; fi
    echo "ESC $n: FAILED.  Check the three wires and that USB power is in."
    echo "      A previously-programmed or read-protected chip may need --erase."
    read -r -p "Retry ESC $n? [Y/n] " r; [ "$r" = "n" ] && break
  done
done
echo
echo "Done.  Next: flash the flight controller, then open https://esc-configurator.com,"
echo "connect through Betaflight passthrough and flash/configure all four ESCs (firmware/README.md)."
