#!/bin/bash
# LayerCam Pro v1 board config for the Luckfox Pico SDK, made from
# BoardConfig-SPI_NAND-Buildroot-RV1106_Luckfox_Pico_Pro_Max-IPC.mk (SDK commit
# 824b817f) by way of LayerCam v1's.  Copy to project/cfg/BoardConfig_IPC/ and
# run ./build.sh lunch.  Lines changed from the Pro Max file are marked
# "LayerCam".  Not yet built.

export LF_ORIGIN_BOARD_CONFIG=BoardConfig-SPI_NAND-Buildroot-RV1106_LayerCam_Pro_v1-IPC.mk
export RK_CHIP=rv1106

# LayerCam: no rkipc; the camera software (S99layercam) owns the sensor.
# If the SDK insists on an app type, RKIPC_RV1106 can be built: LayerCam's
# S21appinit only loads the media drivers and never starts rkipc (an
# unauthenticated RTSP stream and web server).
# export RK_APP_TYPE=RKIPC_RV1106

export RK_BOOTARGS_CMA_SIZE="66M"

# LayerCam: our device tree (dts/rv1106g-layercam-pro-v1.dts)
export RK_KERNEL_DTS=rv1106g-layercam-pro-v1.dts

export RK_BOOT_MEDIUM=spi_nand
export RK_UBOOT_DEFCONFIG_FRAGMENT=rk-sfc.config

# LayerCam: rootfs 210M -> 130M, userdata 10M -> 90M.  The timelapses live on
# userdata (tens of MB for a 1000-layer print: an estimate, README.md).  Check
# that the built rootfs fits (output/image/rootfs.img) before flashing.
export RK_PARTITION_CMD_IN_ENV="256K(env),256K@256K(idblock),512K(uboot),4M(boot),30M(oem),90M(userdata),130M(rootfs)"
export RK_PARTITION_FS_TYPE_CFG=rootfs@IGNORE@ubifs,oem@/oem@ubifs,userdata@/userdata@ubifs

export LF_TARGET_ROOTFS=buildroot
export RK_BUILDROOT_DEFCONFIG=luckfox_pico_defconfig

export RK_ARCH=arm
export RK_TOOLCHAIN_CROSS=arm-rockchip830-linux-uclibcgnueabihf
export RK_MISC=wipe_all-misc.img
export RK_UBOOT_DEFCONFIG=luckfox_rv1106_uboot_defconfig
export RK_KERNEL_DEFCONFIG=luckfox_rv1106_linux_defconfig
# LayerCam: cfg80211 and the Bluetooth core for esp-hosted, the SC4336H
# driver, CIFS (board/sdk/layercam.config)
export RK_KERNEL_DEFCONFIG_FRAGMENT=layercam.config

# LayerCam: only the SC4336H's IQ file (the Pro Max file lists three
# sensors).  The SDK has none for the SC4336H: install-into-sdk.sh puts one
# into media/isp_iqfiles, a copy of the SDK's
# sc4336_CMK-OT2117-PC1_30IRC-F16.json under our module and lens names
# (layercam/board.py), untuned for this lens (README.md, Limits)
export RK_CAMERA_SENSOR_IQFILES="sc4336h_LayerCamPro_LCP-F16.json"

export RK_BUILD_APP_TO_OEM_PARTITION=y

# LayerCam: the Wi-Fi tools (project/app/wifi_app: wpa_supplicant, hostapd,
# dnsmasq) but no chip: RK_ENABLE_WIFI_CHIP is left unset, so no AP6256
# firmware is installed.  The ESP32-C6's host driver, esp32_sdio.ko, comes
# from esp-hosted-linux, built against this kernel (README.md, Building the
# image) and put into the overlay by install-into-sdk.sh
export RK_ENABLE_WIFI=y
# Wi-Fi credentials come from the setup page, not the image
export LF_WIFI_SSID=""
export LF_WIFI_PSK=""

export RK_PRE_BUILD_OEM_SCRIPT=luckfox-buildroot-oem-pre.sh
export RK_PRE_BUILD_USERDATA_SCRIPT=luckfox-userdata-pre.sh
# LayerCam: our files (board/rootfs) as the only overlay.  Luckfox's Wi-Fi
# firmware overlay is not needed (no Broadcom or Realtek chip), and
# overlay-luckfox-buildroot-shadow sets root's
# password to "luckfox" and shares / read-write over Samba, -buildroot-init
# starts sshd with root password login and runs /root/main.py at boot, and
# -config loads pin settings from a block device that on this partition
# table is not its own (README.md, Security).
export RK_POST_OVERLAY="overlay-layercam"
