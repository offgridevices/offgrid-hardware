#!/bin/sh
# Flash the Ridge 3 ESC's four STM32G071 MCUs over SWD: AM32 bootloader,
# AM32 firmware, and the option bytes a G0 needs to boot from its flash.
#
#   ./flash_esc.sh            all four MCUs, one after the other
#   ./flash_esc.sh 3          only ESC 3 (any list of 1..4)
#   TOOL=cubeprog ./flash_esc.sh    use STM32CubeProgrammer instead of OpenOCD
#
# UNTESTED ON HARDWARE.  The OpenOCD commands were run against OpenOCD built
# from upstream commit e5888bda with the hardware commands stubbed out; no
# G071 was attached.
#
# Needs: OpenOCD >= 0.12 (apt install openocd / brew install open-ocd) and an
# ST-Link V2 or clone, or STM32CubeProgrammer (STM32_Programmer_CLI on PATH).
# If OpenOCD cannot see the chip, update the ST-Link's firmware (old clone
# firmware predates the STM32G0).
#
# Wiring: one ST-Link, moved from MCU to MCU.  Bare ESC board, battery NOT
# connected (see firmware/README.md).  Pads on the ESC board's bottom:
#   ST-Link GND   -> "GND"   (one pad, shared by all four MCUs)
#   ST-Link 3.3V  -> "3V3"   (powers the four MCUs and current amplifiers)
#   ST-Link SWDIO -> "Dn"    of the MCU being flashed (n = 1..4)
#   ST-Link SWCLK -> "Cn"    of the same MCU
# NRST is not on a pad: every reset here is a software (SYSRESETREQ) reset.
#
# Per MCU this does:
#   1. Mass erase.  This also clears AM32's settings page, so the firmware
#      writes its defaults on first boot.
#   2. Write and read back the bootloader (0x08000000) and the firmware
#      (0x08001000).
#   3. Option bytes.  On this package PA14 is both SWCLK and BOOT0.  With
#      nBOOT_SEL = 1 the chip takes BOOT0 from the nBOOT0 option bit and
#      ignores the pin, and with nBOOT0 = 1 it boots from its main flash.
#      Both are 1 on parts from ST's factory; the script sets them only if a
#      part arrives otherwise, and then reloads the option bytes (which
#      resets the MCU).
#   4. FLASH_ACR.EMPTY.  A G0 checks at power-on whether its flash is blank,
#      and if it is, boots ST's ROM bootloader instead.  After programming
#      over SWD that flag is still set, so a plain reset would not start
#      AM32.  The script clears it before the final reset.  (Any power cycle
#      also clears it.)
#
# STM32CubeProgrammer does steps 1 to 3 with
#   STM32_Programmer_CLI -c port=SWD mode=Normal reset=SWrst -e all \
#       -w AM32_G071_BOOTLOADER_PB4_64K_V19.hex -v -w AM32_RIDGE3_G071_2.21.hex -v \
#       -ob nBOOT_SEL=1 nBOOT0=1
# (TOOL=cubeprog runs exactly that); power-cycle the board afterwards.
#
# A part that reports read protection (RDP level 1) must be unlocked first,
# which erases it:
#   openocd -f interface/stlink.cfg -f target/stm32g0x.cfg \
#       -c init -c "reset halt" -c "stm32l4x unlock 0" -c shutdown
# then power-cycle it and run this script again.
set -e
cd "$(dirname "$0")"

BL=AM32_G071_BOOTLOADER_PB4_64K_V19.hex
FW=AM32_RIDGE3_G071_2.21.hex
TOOL=${TOOL:-openocd}

# FLASH registers at 0x40022000 (RM0444; bit names as in ST's CMSIS header
# stm32g071xx.h): FLASH_OPTR at +0x20, nBOOT_SEL bit 24, nBOOT0 bit 26;
# FLASH_ACR at +0x00, EMPTY (FLASH_ACR_PROGEMPTY) bit 16.
OCD_PROC='
proc ridge3_flash {bl fw} {
    stm32l4x mass_erase 0
    flash write_image $bl
    verify_image $bl
    flash write_image $fw
    verify_image $fw
    set want 0x05000000
    set optr [stm32l4x option_read 0 0x20]
    echo "FLASH_OPTR = $optr"
    if {($optr & $want) != $want} {
        echo "setting nBOOT_SEL = 1, nBOOT0 = 1: boot from main flash, PA14 is SWCLK only"
        stm32l4x option_write 0 0x20 $want $want
        # OBL_LAUNCH resets the MCU; option load also re-reads EMPTY
        catch {stm32l4x option_load 0}
    } else {
        mmw 0x40022000 0 0x00010000
        reset run
    }
}'

flash_one() {
    case "$TOOL" in
    openocd)
        openocd -f interface/stlink.cfg -f target/stm32g0x.cfg \
            -c "$OCD_PROC" \
            -c "init" -c "reset halt" \
            -c "ridge3_flash $BL $FW" \
            -c "shutdown"
        ;;
    cubeprog)
        STM32_Programmer_CLI -c port=SWD mode=Normal reset=SWrst -e all \
            -w "$BL" -v -w "$FW" -v -ob nBOOT_SEL=1 nBOOT0=1
        ;;
    *)
        echo "TOOL must be openocd or cubeprog" >&2
        exit 2
        ;;
    esac
}

ESCS=${*:-1 2 3 4}
for n in $ESCS; do
    case "$n" in
    1|2|3|4) ;;
    *) echo "ESC number must be 1..4, not '$n'" >&2; exit 2 ;;
    esac
    printf 'ESC %s: SWDIO to pad D%s, SWCLK to pad C%s (GND and 3V3 stay). Enter to flash, Ctrl-C to stop: ' "$n" "$n" "$n"
    read -r _
    flash_one
    echo "ESC $n done."
done
if [ "$TOOL" = cubeprog ]; then
    echo "Power-cycle the board (unplug the ST-Link's 3.3 V) so each MCU starts AM32."
fi
echo "All requested ESC MCUs flashed."
