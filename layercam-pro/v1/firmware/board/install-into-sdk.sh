#!/bin/sh
# Copy LayerCam Pro's board files into a Luckfox Pico SDK checkout:
#
#   [UPDATE_PUBKEY=update.pub] [USB_ID=vvvv:pppp] [ESP_HOSTED_KO=esp32_sdio.ko] [C6_FW=network_adapter/build] \
#   [SC4336H_CHIP_ID=0xNNNN] board/install-into-sdk.sh ~/luckfox-pico [path/to/layercam-media]
#
# UPDATE_PUBKEY: the public key (tools/layercam-sign.py keygen) whose
# signatures the cameras accept on app updates; without it they refuse all.
# USB_ID: the USB vendor:product id of the setup console.  The default,
# 1d6b:0104 (Linux Foundation, multifunction composite gadget), is for
# development only: a camera that is sold needs its own id.
# ESP_HOSTED_KO: esp-hosted-linux's host driver built against this SDK's
# kernel (README.md); without it the image has no Wi-Fi.
# C6_FW: the ESP32-C6 firmware's ESP-IDF build folder (flasher_args.json and
# the images it names), put on the camera for layercam-c6-flash.
# SC4336H_CHIP_ID: the sensor's chip ID once read from a board; without it
# the SC4336H driver (tools/sc4336h-port.py) only logs the ID it reads.
# then in the SDK: ./build.sh lunch (pick LayerCam_Pro_v1), ./build.sh.
# The C helper is built separately (native/Makefile); without it the image
# boots but the camera software has no camera.  Not yet run.
set -e
SDK=${1:?usage: $0 SDK_PATH [layercam-media binary]}
HELPER=${2:-}
HERE=$(cd "$(dirname "$0")/.." && pwd)
CFG=$SDK/project/cfg/BoardConfig_IPC
OVL=$CFG/overlay/overlay-layercam

cp "$HERE/dts/rv1106g-layercam-pro-v1.dts" "$SDK/sysdrv/source/kernel/arch/arm/boot/dts/"
cp "$HERE/board/sdk/layercam.config" "$SDK/sysdrv/source/kernel/arch/arm/configs/"
cp "$HERE/board/sdk/BoardConfig-SPI_NAND-Buildroot-RV1106_LayerCam_Pro_v1-IPC.mk" "$CFG/"

# the SC4336H driver: a port of the SDK's sc4336.c (drivers/media/i2c/sc4336h.c,
# Kconfig, Makefile); the register table stays the SC4336's (README.md)
python3 "$HERE/tools/sc4336h-port.py" "$SDK/sysdrv/source/kernel" ${SC4336H_CHIP_ID:+--chip-id "$SC4336H_CHIP_ID"}

# its IQ file: none exists for the SC4336H, so the SDK's SC4336 file (CMK
# module, 30IRC-F16 lens) under our names, untuned, unless one is there
IQDIR=$(ls -d "$SDK"/media/isp/release_camera_engine_rkaiq_rv1106_*/isp_iqfiles 2>/dev/null | head -n 1)
IQ=sc4336h_LayerCamPro_LCP-F16.json
if [ -n "$IQDIR" ] && [ -f "$IQDIR/$IQ" ]; then
	echo "note: keeping the IQ file already in the SDK: $IQDIR/$IQ"
elif [ -n "$IQDIR" ] && [ -f "$IQDIR/sc4336_CMK-OT2117-PC1_30IRC-F16.json" ]; then
	cp "$IQDIR/sc4336_CMK-OT2117-PC1_30IRC-F16.json" "$IQDIR/$IQ"
	echo "note: $IQ is the SC4336's sc4336_CMK-OT2117-PC1_30IRC-F16.json, not tuned for this sensor and lens"
else
	echo "warning: no rkaiq isp_iqfiles folder with sc4336_CMK-OT2117-PC1_30IRC-F16.json: put $IQ there by hand"
fi

# (no dtb list to edit: the SDK builds $(RK_KERNEL_DTS:dts=img) by name,
# as it does for Luckfox's own device trees, which are not in that list either)

# Buildroot packages and options: the fragment's settings, "# X is not set"
# lines included (the later line wins in a defconfig), between markers so a
# second run replaces them
BR=$SDK/sysdrv/tools/board/buildroot/luckfox_pico_defconfig
sed -i '/^# >>> LayerCam/,/^# <<< LayerCam/d' "$BR"
{
	echo "# >>> LayerCam (board/sdk/buildroot.fragment)"
	grep -E '^BR2_|^# BR2_[A-Z0-9_]+ is not set$' "$HERE/board/sdk/buildroot.fragment"
	echo "# <<< LayerCam"
} >> "$BR"

# the overlay: scripts, the Python package, the helper
rm -rf "$OVL"
mkdir -p "$OVL/usr/share/layercam"
cp -a "$HERE/board/rootfs/." "$OVL/"
cp -a "$HERE/layercam" "$OVL/usr/share/layercam/"
find "$OVL" -name __pycache__ -prune -exec rm -rf {} +
cp "$HERE/board/layercam.ini.example" "$OVL/usr/share/layercam/"
install -m 755 "$HERE/tools/layercam-c6-flash.py" "$OVL/usr/bin/layercam-c6-flash"
if [ -n "${ESP_HOSTED_KO:-}" ]; then
	mkdir -p "$OVL/lib/modules"
	install -m 644 "$ESP_HOSTED_KO" "$OVL/lib/modules/esp32_sdio.ko"
else
	echo "note: no ESP_HOSTED_KO: the image has no Wi-Fi driver (build esp-hosted-linux's host/, README.md)"
fi
if [ -n "${C6_FW:-}" ]; then
	[ -f "$C6_FW/flasher_args.json" ] || { echo "error: $C6_FW has no flasher_args.json (an ESP-IDF build folder)"; exit 1; }
	python3 - "$C6_FW" "$OVL/usr/share/layercam-c6" <<'PY'
import json, os, shutil, sys
src, dst = sys.argv[1:]
files = json.load(open(os.path.join(src, 'flasher_args.json')))['flash_files']
for rel in ['flasher_args.json'] + list(files.values()):
    os.makedirs(os.path.dirname(os.path.join(dst, rel)), exist_ok=True)
    shutil.copyfile(os.path.join(src, rel), os.path.join(dst, rel))
PY
else
	echo "note: no C6_FW: the ESP32-C6 firmware is not in the image (flash it with layercam-c6-flash from a copy)"
fi
if [ -n "${UPDATE_PUBKEY:-}" ]; then
	grep -E '^[0-9a-fA-F]{64}$' "$UPDATE_PUBKEY" >> "$OVL/etc/layercam/update-keys" \
		|| { echo "error: $UPDATE_PUBKEY holds no 64-hex-digit public key"; exit 1; }
else
	echo "note: no UPDATE_PUBKEY: these cameras will refuse every app update (README.md, Updates)"
fi
USB_ID=${USB_ID:-1d6b:0104}
echo "$USB_ID" | grep -qE '^[0-9a-fA-F]{4}:[0-9a-fA-F]{4}$' || { echo "error: USB_ID must be vvvv:pppp"; exit 1; }
echo "$USB_ID" > "$OVL/etc/layercam/usb-id"
[ "$USB_ID" = 1d6b:0104 ] && echo "note: USB id 1d6b:0104 is a development placeholder: set USB_ID before selling cameras"
if [ -n "$HELPER" ]; then
	install -m 755 "$HELPER" "$OVL/usr/bin/layercam-media"
else
	echo "note: no layercam-media given; build native/ and run this again with its path"
fi
echo "LayerCam Pro files installed into $SDK"
