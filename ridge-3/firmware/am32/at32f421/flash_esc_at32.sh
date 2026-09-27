#!/bin/sh
# Flash one AT32F421K8U7 ESC MCU over SWD: AM32 bootloader + AM32 firmware.
#
# UNTESTED ON HARDWARE.  The command syntax and the target config were checked
# against OpenOCD built from upstream commit e5888bda (the commit xPack OpenOCD
# v0.12.0-7 is built from), with a dummy adapter; no AT32 was attached.
#
# Needs an OpenOCD with the upstream "artery" flash driver: upstream git after
# 2024-11-30 (commit ef188a30), e.g. xPack OpenOCD v0.12.0-7 or later.
# OpenOCD 0.12.0 releases and distro packages (apt/brew "openocd") do NOT have
# it, and target/stm32f0x.cfg / STM32CubeProgrammer cannot program an AT32.
#
# Wiring is the same as flash_esc.sh (battery disconnected, ST-Link 3.3 V
# powers the MCUs, SWDIO -> Dn, SWCLK -> Cn).  NRST is not on the pads, so the
# reset is a software (SYSRESETREQ) reset.
#
# If OpenOCD reports FAP / read protection (a part that was protected before):
#   openocd -f interface/stlink.cfg -f target/artery/at32f4x.cfg \
#       -c "init" -c "artery fap disable 0" -c "shutdown"
# then power-cycle the MCU and run this script again (disabling FAP erases it).
# If it stops on an unexpected IDCODE, add  -c "set CPUTAPID 0"  before the
# target file.
set -e
cd "$(dirname "$0")"
openocd -f interface/stlink.cfg -f target/artery/at32f4x.cfg \
    -c "init" -c "reset halt" \
    -c "artery mass_erase 0" \
    -c "program AM32_F421_BOOTLOADER_PA2_V19.hex verify" \
    -c "program AM32_CHEAPDRONE_F421_2.21.hex verify reset exit"
echo "done - move the SWDIO/SWCLK clips to the next ESC's pads"
