#!/bin/sh
# Flash the Ridge 3 ESC's (revision 2) four Artery AT32F421 MCUs over SWD:
# the AM32 bootloader and the AM32 firmware.
#
#   ./flash_esc.sh            all four MCUs, one after the other
#   ./flash_esc.sh 3          only ESC 3 (any list of 1..4)
#
# UNTESTED ON HARDWARE, and not run at all: no AT32F421 or Artery OpenOCD
# was available when this was written.
#
# Needs: Artery's OpenOCD (github.com/ArteryTek/openocd: upstream OpenOCD has
# no AT32F421 flash driver; this is the target/at32f421xx.cfg AM32's own
# tools/openocd-at32f421.cfg uses) and an ST-Link V2 or clone (the default,
# interface/stlink.cfg), or Artery's AT-Link: then run it as
# OPENOCD_INTERFACE=interface/atlink.cfg ./flash_esc.sh (Artery's OpenOCD's
# config for it).  Artery's ISP Programmer (Windows) with an AT-Link does
# the same from a GUI: erase all, then write the two .hex files below.
#
# Power: the four MCUs run from the flight controller's 3.3 V, which comes
# down the stack lead's pin 4 (the ESC has no 3.3 V regulator of its own).
# Solder the stack lead to the ESC, plug it into the flight controller (the
# two boards side by side, not stacked, no motors), and power them from a
# current-limited bench supply (12 V, 0.3 A) on the ESC's battery pads.  The
# gate drivers' inputs have pull-downs: the FETs stay off while an MCU is
# blank or halted.
#
# Wiring: one probe (ST-Link or AT-Link), moved from MCU to MCU.  Pads on the ESC board's top
# (the side that faces the flight controller):
#   ST-Link GND   -> the battery pad marked "-"
#   ST-Link SWCLK -> "Cn"    of the MCU being flashed (n = 1..4)
#   ST-Link SWDIO -> "Dn"    of the same MCU
#   ST-Link 3.3V  -> NOT connected (the MCU runs from the flight controller's
#                    3.3 V on the stack lead, which a probe's 3.3 V output
#                    would back-feed.  A probe that needs a target voltage
#                    reference reads it on VAPP: connect that to the ESC's
#                    3V3 lead pad only if your probe asks for it)
# NRST is not on a pad: every reset here is a software (SYSRESETREQ) reset.
#
# Per MCU this does: erase the whole flash (this also erases AM32's settings
# page; AM32 does not write defaults over an erased page, it reads it as 3D
# mode and car-type reversing on with both limits off: click "Send default
# config" in the AM32 Configurator before anything spins, ../README.md),
# write and verify the bootloader (0x08000000) and the firmware (0x08001000,
# the addresses are in the .hex files), and start it.  BOOT0 is tied low on the
# board, so the MCU boots from its flash: no option bytes to set.
set -e
cd "$(dirname "$0")"

BL=AM32_F421_BOOTLOADER_PB4_V19.hex
FW=AM32_RIDGE3_F421_2.21.hex

flash_one() {
    openocd -f "${OPENOCD_INTERFACE:-interface/stlink.cfg}" -f target/at32f421xx.cfg \
        -c "init" -c "reset halt" \
        -c "flash erase_sector 0 0 last" \
        -c "flash write_image $BL" -c "verify_image $BL" \
        -c "flash write_image $FW" -c "verify_image $FW" \
        -c "reset run" -c "shutdown"
}

ESCS=${*:-1 2 3 4}
for n in $ESCS; do
    case "$n" in
    1|2|3|4) ;;
    *) echo "ESC number must be 1..4, not '$n'" >&2; exit 2 ;;
    esac
    printf 'ESC %s: SWCLK to pad C%s, SWDIO to pad D%s (GND stays on the battery pad). Enter to flash, Ctrl-C to stop: ' "$n" "$n" "$n"
    read -r _
    flash_one
    echo "ESC $n done."
done
echo "All requested ESC MCUs flashed."
