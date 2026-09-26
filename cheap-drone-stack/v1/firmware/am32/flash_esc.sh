#!/bin/sh
# Flash one of the four ESC MCUs over SWD: AM32 bootloader + AM32 firmware.
#
#   ./flash_esc.sh            (OpenOCD + ST-Link V2 or clone)
#
# Wire the ST-Link to the pads on the ESC board's BOTTOM side:
#   ST-Link GND   -> TP "GND"          (one pad, shared by all four MCUs)
#   ST-Link 3.3V  -> TP "3V3"          (powers the MCUs; battery NOT connected)
#   ST-Link SWDIO -> "Dn" of the ESC you are flashing   (n = 1..4)
#   ST-Link SWCLK -> "Cn" of the same ESC
# Run once per ESC, moving SWDIO/SWCLK between pad pairs.
#
# Needs openocd >= 0.11 (apt install openocd / brew install open-ocd).
# STM32CubeProgrammer works too:
#   STM32_Programmer_CLI -c port=SWD -w AM32_F051_BOOTLOADER_PA2_V19.hex -v
#   STM32_Programmer_CLI -c port=SWD -w AM32_FD6288_F051_2.21.hex -v -rst
set -e
cd "$(dirname "$0")"
openocd -f interface/stlink.cfg -f target/stm32f0x.cfg \
    -c "init" -c "reset halt" \
    -c "flash erase_sector 0 0 last" \
    -c "program AM32_F051_BOOTLOADER_PA2_V19.hex verify" \
    -c "program AM32_FD6288_F051_2.21.hex verify" \
    -c "reset run" -c "exit"
echo "done - move the SWDIO/SWCLK clips to the next ESC's pads"
