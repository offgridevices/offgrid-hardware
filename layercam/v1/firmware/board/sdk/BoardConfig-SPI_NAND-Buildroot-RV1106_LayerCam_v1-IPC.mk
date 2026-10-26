#!/bin/bash
# LayerCam v1 board config for the Luckfox Pico SDK, made from
# BoardConfig-SPI_NAND-Buildroot-RV1106_Luckfox_Pico_Pro_Max-IPC.mk (SDK commit
# 824b817f).  Copy to project/cfg/BoardConfig_IPC/ and run ./build.sh lunch.
# Lines changed from the Pro Max file are marked "LayerCam".  Not yet built.

export LF_ORIGIN_BOARD_CONFIG=BoardConfig-SPI_NAND-Buildroot-RV1106_LayerCam_v1-IPC.mk
export RK_CHIP=rv1106

# LayerCam: no rkipc; the camera software (S99layercam) owns the sensor.
# If the SDK insists on an app type, keep RKIPC_RV1106: S99layercam stops it
# (RkLunch-stop.sh) before starting.
# export RK_APP_TYPE=RKIPC_RV1106

export RK_BOOTARGS_CMA_SIZE="66M"

# LayerCam: our device tree (dts/rv1106g-layercam-v1.dts)
export RK_KERNEL_DTS=rv1106g-layercam-v1.dts

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
# LayerCam: Wi-Fi, rfkill, CIFS (board/sdk/layercam.config)
export RK_KERNEL_DEFCONFIG_FRAGMENT=layercam.config

# LayerCam: only the SC3336 IQ file (the Pro Max file lists three sensors)
export RK_CAMERA_SENSOR_IQFILES="sc3336_CMK-OT2119-PC1_30IRC-F16.json"

export RK_BUILD_APP_TO_OEM_PARTITION=y

# LayerCam: the AP6256 (bcmdhd, firmware fw_bcm43456c5_ag.bin + nvram_ap6256.txt)
export RK_ENABLE_WIFI=y
export RK_ENABLE_WIFI_CHIP=AP6XXX
# Wi-Fi credentials come from the setup page, not the image
export LF_WIFI_SSID=""
export LF_WIFI_PSK=""

export RK_PRE_BUILD_OEM_SCRIPT=luckfox-buildroot-oem-pre.sh
export RK_PRE_BUILD_USERDATA_SCRIPT=luckfox-userdata-pre.sh
# LayerCam: our files (board/rootfs) as one more overlay, after Luckfox's
export RK_POST_OVERLAY="overlay-luckfox-config overlay-luckfox-buildroot-init overlay-luckfox-buildroot-shadow overlay-luckfox-wifibt-firmware overlay-layercam"
