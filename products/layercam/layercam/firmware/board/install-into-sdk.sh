#!/bin/sh
# Copy LayerCam's board files into a Luckfox Pico SDK checkout:
#
#   [UPDATE_PUBKEY=update.pub] [USB_ID=vvvv:pppp] board/install-into-sdk.sh ~/luckfox-pico [path/to/layercam-media]
#
# UPDATE_PUBKEY: the public key (tools/layercam-sign.py keygen) whose
# signatures the cameras accept on app updates; without it they refuse all.
# USB_ID: the USB vendor:product id of the setup console.  The default,
# 1d6b:0104 (Linux Foundation, multifunction composite gadget), is for
# development only: a camera that is sold needs its own id.
# then in the SDK: ./build.sh lunch (pick LayerCam_v1), ./build.sh.
# The C helper is built separately (native/Makefile); without it the image
# boots but the camera software has no camera.  Not yet run.
set -e
SDK=${1:?usage: $0 SDK_PATH [layercam-media binary]}
HELPER=${2:-}
HERE=$(cd "$(dirname "$0")/.." && pwd)
CFG=$SDK/project/cfg/BoardConfig_IPC
OVL=$CFG/overlay/overlay-layercam

cp "$HERE/dts/rv1106g-layercam-v1.dts" "$SDK/sysdrv/source/kernel/arch/arm/boot/dts/"
cp "$HERE/board/sdk/layercam.config" "$SDK/sysdrv/source/kernel/arch/arm/configs/"
cp "$HERE/board/sdk/BoardConfig-SPI_NAND-Buildroot-RV1106_LayerCam_v1-IPC.mk" "$CFG/"

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
echo "LayerCam files installed into $SDK"
