# LayerCam Pro v1 — camera software

**What the camera does once it is in the printer.** It sends a picture to
Prusa Connect every 10-60 seconds, so the Prusa app shows the print. During
a print it takes one frame per layer, with the head parked out of the way,
makes them into an MP4 video named after the print, and uploads the video
to S3 (or MinIO, Backblaze B2, a NAS), a WebDAV/HTTP folder, an SMB share or
an NFS export. It switches to infrared at night, and is set up from a phone.
It has no button: Wi-Fi setup and reset, updates and recovery all work
without one (a switch's plastic is rated 70-85 C; in the chamber it would
sit at about 90 C).

> **Status: written, tested on a PC, not yet run on the board.** No board
> exists yet. This is LayerCam v1's software (`products/layercam/layercam/firmware/`)
> moved to the Pro's parts: an **ESP32-C6-MINI-1U-H4 running esp-hosted**
> in place of the AP6256, a **bare SmartSens SC4336H** in place of the
> SC3336 module, and one board (the IR LEDs, light sensor and IR-cut driver
> on the same SoC pins as v1). The Python service and the tools pass their
> 212 host tests (all run in CI; some skip themselves on a PC without ffmpeg or `ssh-keygen`), including a whole
> print from PrusaLink and layer triggers to an uploaded MP4, and flashing
> a simulated ESP32-C6 ROM. The device tree, the SDK board config, the init
> scripts and the C helper are checked as far as a PC can, never built for
> or run on an RV1106. **The SC4336H has no driver anywhere**: its chip ID
> and register table are under SmartSens NDA, so its driver here is the
> SDK's SC4336 driver renamed (*The sensor driver*). See *Bringing up a
> board* and *Limits*.

### What changed from LayerCam v1

| | v1 | Pro v1 |
|---|---|---|
| Wi-Fi | AMPAK AP6256 (bcmdhd, SDIO, UART Bluetooth), 2.4/5 GHz | ESP32-C6 on the same SDMMC0 pins, esp-hosted firmware, `esp32_sdio.ko` from esp-hosted-linux (a cfg80211 FullMAC driver: `wlan0`, wpa_supplicant, hostapd); 2.4 GHz only; no Bluetooth |
| Wi-Fi control | WL_REG_ON (GPIO1_A2), WL_HOST_WAKE (GPIO0_A3), BT_* | WIFI_EN on GPIO1_A2 (mmc-pwrseq, **1500 ms**), WIFI_BOOT on GPIO0_A2 (the C6's GPIO9 strap), UART1_M0 to the C6's UART0 (flashing it from Linux: `tools/layercam-c6-flash.py`), WIFI_HOST_WAKE on GPIO0_A3 (wired, unused) |
| Sensor | SC3336 module, 27 MHz, 2304 x 1296, `pwdn-gpios` on GPIO3_C5 | bare SC4336H, 24 MHz, 2560 x 1440, 2-lane MIPI, I2C4_M2 at 0x30; XSHUTDN on GPIO3_C5 (`reset-gpios`), PWDNB on GPIO3_C6 (`pwdn-gpios`); driver `sc4336h` ported from `sc4336.c` (`tools/sc4336h-port.py`) |
| IQ file | `sc3336_CMK-OT2119-PC1_30IRC-F16.json` | `sc4336h_LayerCamPro_LCP-F16.json`: a copy of the SDK's SC4336 file, untuned |
| Boards | main, LED ring, USB | one board; IR_PWM (pin 77), ALS (SARADC_IN1), IRCUT_A/B (pins 72/73) unchanged |
| Names | `rv1106g-layercam-v1.dts`, `RV1106_LayerCam_v1`, product `LayerCam v1` | `rv1106g-layercam-pro-v1.dts`, `RV1106_LayerCam_Pro_v1`, product `LayerCam Pro v1` (v1's update packages are refused) |
| Setup access point | | `hostapd` gets a control socket and the camera counts the phones on it there (esp-hosted's driver has no station dump for `iw`) |

## Requirements

As the owner set them, and where Pro v1 stands. ✅ here means written and
tested on a PC; none of it has run on the board yet.

| Requirement | Pro v1 |
|---|---|
| Snapshots in Prusa Connect / the Prusa app | ✅ Prusa's current Camera Service API (`camera-service.prusa3d.com`), every 10, 30 or 60 s; the layer frames (head parked) go to Connect too; under 1 MB and at most 6 a minute, as the service requires |
| Per-layer timelapse, frame taken with the head parked | ✅ PrusaSlicer snippet ([`slicer/`](slicer/README.md)) parks the head and sends a trigger over the printer's metrics stream; the camera shoots during a 1.2 s hold |
| Know the print: name, start, finish, cancel; fallback trigger | ✅ PrusaLink `/api/v1/status` and `/api/v1/job` (Digest auth, user `maker`); without the snippet, frames on Z changes (head not parked) |
| MP4 (H.264), hardware encoder, little storage | ✅ each frame encoded by the RV1106's encoder as it is taken and appended to one H.264 file; MP4 made on the fly at upload; ffmpeg path for a PC |
| Upload to SMB, NFS, S3 (+ compatible), HTTP/WebDAV | ✅ all five; S3 signing (SigV4) in plain Python, tested against AWS's test suite |
| Live picture for setup; day/night with IR | ✅ live view on request (2 minutes, refused when hot); IR-cut from the light sensor with hysteresis, IR LEDs lit only around each night picture |
| Works in a 65 C chamber (the Pro's rating, `sim/thermal.md`) | ⚠️ the firmware does all it can (below: sensor asleep between pictures, 1080p, lowest CPU speed, transmit power capped, IR LEDs flashed, a thermal governor that throttles, skips uploads, then stops the camera); the Pro's own thermal model (`sim/thermal.py`) decides whether that is enough. Wi-Fi power save is up to the C6's firmware now (*Heat and power*) |
| 1080p timelapse | ✅ 1920 x 1080 by default (`timelapse.resolution`), the full 2560 x 1440 sensor selectable |
| Wi-Fi setup, reset and updates with no button; one settings file; status LED | ✅ setup access point and page at first boot and when the saved network stays unreachable; three short power-ups forget the Wi-Fi; a USB serial console (`layercam-setup`) when plugged into a computer; signed app updates from the page, started on trial and rolled back if they do not stay up; full images over USB without opening the camera; `layercam.ini`; LED patterns below |
| Runs on the Luckfox SDK's Buildroot | ✅ Python 3.8+ standard library only (Buildroot's `python3` is already in `luckfox_pico_defconfig`), one small C helper |

## What runs where

```
 PrusaSlicer snippet ──► CORE One (Buddy firmware)
                          │  UDP 8514: metrics stream, "M118 OGCAM:LAYER:n"
                          │  HTTP: PrusaLink /api/v1/status, /api/v1/job
                          ▼
 LayerCam (RV1106, Linux)
   S21-layercam-gesture ─► counts short power-ups (gesture.py)
   S50usbdevice ─► USB serial console: layercam-setup (setupcli.py)
   S99layercam ─► picks the version (update.py) ─► python3 -m layercam
                    ├─ metrics listener      triggers from the printer
                    ├─ PrusaLink poller      job name, start/finish/cancel, Z
                    ├─ timelapse logic       when to start, shoot, finish
                    ├─ Connect sender        snapshots to Prusa Connect
                    ├─ uploader              finished videos
                    ├─ Wi-Fi                 the network or the setup access point, on
                    │                        the ESP32-C6 (esp-hosted: esp32_sdio.ko, wlan0)
                    ├─ panel                 light sensor, IR, temperature, BOOT pad
                    ├─ web                   setup page, live picture, updates
                    ├─ status LED
                    └─ layercam-media        C helper (native/): sensor, ISP,
                                             JPEG and H.264 hardware encoders
```

Why Python: the work is network glue (HTTP, UDP, signing, a small web
page), Buildroot's python3 is already in the Luckfox image, and it can be
tested on any PC. The camera itself (ISP, encoders) is the C helper's job,
the only part that needs the SDK's libraries. C for everything would mean
writing HTTP, TLS and S3 by hand with no gain in what the camera can do.

**One layer frame, in time:** the head reaches the corner (`M400` waits for
it), the printer runs `M118 OGCAM:LAYER:12` and the padding lines fill its
metrics buffer, so the datagram leaves within milliseconds. The camera
reads from the datagram how long ago the line ran, waits out the rest of a
150 ms settle, drops the frames the sensor had queued from before, and
encodes the next one into the video (about 70 ms of dropped frames plus the
encode). At night the IR LEDs ramp up first and the exposure gets 500 ms
to follow them, then they go off again. The head holds for 1.2 s in all;
the trigger is sent twice in case a datagram is lost. Details:
[`slicer/README.md`](slicer/README.md).

## Heat and power

LayerCam v1's sim/thermal.md: streaming 3 MP at 30 fps all the time put
the RV1106 at about 126 C in v1's sealed housing in a 65 C chamber (limit
125 C). The Pro keeps v1's policy unchanged: the camera does as little as
it can (`layercam/thermal.py`):

| | What the camera does | Why |
|---|---|---|
| no print | sensor and ISP **asleep** (VI channel stopped, the sensor driver puts the SC4336H in standby); woken for each Connect snapshot with `camera.wake_ms` (1 s) for the exposure, then asleep again | a picture every 10-60 s needs the sensor about 5 % of the time |
| printing | sensor streaming at **10 fps** (`camera.print_fps`), not 30 | a layer trigger must be answered inside the 1.2 s hold, and rkaiq's auto exposure and white balance need frames to settle after a cold start (some hundreds of ms to a second: to measure on the board); at 10 fps a fresh frame is at most 0.3 s away |
| video size | 1920 x 1080 (the ISP scales the 2560 x 1440 sensor; same 16:9) | fewer pixels through the ISP, encoder and DDR |
| CPU | held at its lowest speed (`scaling_max_freq`) except while uploading (TLS, SHA-256) | the encoders are hardware; the CPU has little to do |
| Wi-Fi | 2.4 GHz (the C6 has no other band), transmit power capped at 10 dBm (`iw`; esp-hosted's driver implements `set_tx_power`). **Power save: not from Linux.** esp-hosted's driver has no `set_power_mgmt`, so `iw ... set power_save on` (still sent) is refused, and its C6 firmware turns modem sleep off at start (`esp_wifi_set_ps(WIFI_PS_NONE)` in `network_adapter/main/cmd.c`, "line-powered adapter"). **The camera is rated for a 65 C chamber with power save on** (`sim/thermal.md`): run `tools/c6-power-save.sh` on esp-hosted's `network_adapter` folder before building the C6 firmware; it changes that call to `WIFI_PS_MIN_MODEM` (not yet measured on a camera) | v1's AP6256 was its second-largest heat source; the C6's share is to measure (Espressif: 382 mA peak at 20.5 dBm 802.11b) |
| IR LEDs | lit only around a night picture (ramped over 150 ms, `ir.flash_settle_ms` 500 ms before the frame) and during live view; never continuously | lit continuously v1's ring was the hottest part at night (v1's sim/thermal.md); the Pro's six LEDs are on the main board |
| IR-cut | the coil is pulsed only when day/night changes | |
| live view | only when asked for (setup page button, `POST /api/live`), at most `camera.live_max_s` (120 s), refused or stopped from 87 C | streaming 10 fps JPEG is the heaviest thing the camera can do |

The **thermal governor** reads the SoC's own sensor (TSADC,
`/sys/class/thermal/thermal_zone0/temp`) once a second:

| SoC | Level | Effect |
|---|---|---|
| under 84 C | normal | as above |
| from 84 C | warm | Prusa Connect pictures at most every 30 s, the IR flash's settle cut to 200 ms (`sim/thermal.md`, *Firmware rules* 3: the lowest snapshot-mode limit); everything else as normal |
| from 87 C | throttle | frame rate 5 fps, JPEG quality at most 70, IR LED duty at most 50 %, no live view, CPU never boosted |
| from 105 C | hot | as throttle, and **no Connect uploads**; timelapse frames continue (the print only happens once) |
| from 110 C | stop | camera pipeline stopped, IR LEDs off, frames lost (counted on the page) |
| back under 95 C | | from stop to the level the temperature calls for |

Every level is left 5 K under where it was entered (`thermal.hysteresis_k`;
warm 2 K), so it does not flap. The level and the temperature are on the
setup page, the change is logged, and the status LED shows *hot* (long on,
short off) from throttle up. All thresholds are settings (`[thermal]`).
These numbers follow LayerCam v1's sim/thermal.md and sim/power.md, not yet
the Pro's `sim/thermal.py`; measure the board in
a 65 C oven before trusting either.

**Storage.** There is no SD card: 256 MB of SPI NAND for everything. A
JPEG per layer at 2560 x 1440 is about 370-620 kB (v1's unmeasured
300-500 kB at 2304 x 1296, scaled by the pixels), so a 1000-layer print would
need more than the whole NAND. Instead each frame goes straight into the
H.264 encoder and onto the end of one file (`video.h264`, plus an index of
frame offsets); consecutive layers differ little, so most frames are small
P-frames. Our estimate is 20-60 kB a frame, tens of MB for a long print
(to be measured on the board). The MP4 is never written: at upload the
service streams the MP4 boxes from the index and the H.264 file
(`layercam/mp4.py`, moov first so the video plays while it downloads). The
board config gives the timelapse partition (`/userdata`) 90 MB. When free
space runs low the camera keeps every second layer, then every fourth, so
the video still covers the whole print; before a new print it deletes the
oldest uploaded videos, then the oldest unsent ones, to make room.

## Building the image

Everything builds in the [Luckfox Pico SDK](https://github.com/LuckfoxTECH/luckfox-pico)
(Buildroot 2023.02.6, kernel 5.10.160, rockit/rkaiq media stack), as for
LayerCam v1 and the Luckfox Pico Pro/Max (same RV1106G3 and SPI NAND).
Checked against SDK commit `824b817f` (22 Mar 2026). Two parts come from
outside the SDK: the Wi-Fi driver and the C6's firmware, both from
[esp-hosted-linux](https://github.com/espressif/esp-hosted-linux)
(checked at v1.0.6.0.7, commit `54d5367`). Not esp-hosted-ng (legacy,
replaced by esp-hosted-linux) and not esp-hosted-mcu (an RPC API with no
cfg80211).

1. **Get the SDK** and its toolchain, as Luckfox's own instructions say.
2. **Build the C helper** (`native/`): it needs the rockit/rkaiq headers and
   libraries, which [luckfox_pico_rkmpi_example](https://github.com/LuckfoxTECH/luckfox_pico_rkmpi_example)
   ships in `include/` and `lib/uclibc/`:
   ```
   cd native
   make LUCKFOX_SDK_PATH=~/luckfox-pico RKMPI=~/luckfox_pico_rkmpi_example
   ```
   Add `HAVE_LIBJPEG=1 JPEG_INC=... JPEG_LIB=...` for `--encode-jpegs`
   (only needed when frames were stored as JPEGs; the SDK has libjpeg9
   headers in `project/app/component/third_libs/include/libjpeg9`).
3. **Build the C6's firmware** (esp-hosted-linux `esp/esp_driver/`): its
   `setup.sh` fetches the ESP-IDF revision it pins, then
   ```
   cd esp/esp_driver && ./setup.sh && . ./esp-idf/export.sh
   cd network_adapter && idf.py set-target esp32c6 && idf.py menuconfig && idf.py build
   ```
   In menuconfig: *Example Configuration → Transport layer → SDIO* (the
   default where the chip has an SDIO slave); `HOST_WAKEUP_GPIO` 4 (the
   default for the C6, our IO4); Bluetooth off (`CONFIG_BT_ENABLED`: the
   C6 defaults have it on, and nothing here uses it). `build/` then holds
   `flasher_args.json` with `bootloader/bootloader.bin` (0x0),
   `partition_table/partition-table.bin` (0x8000), `ota_data_initial.bin`
   and `network_adapter.bin` (0x10000: `partitions.esp32c6.csv`). For Wi-Fi
   power save, see *Heat and power* first.
4. **Build the Wi-Fi driver** (esp-hosted-linux `host/`) against the SDK's
   kernel once it has been built (`./build.sh kernel`), with the access
   point compiled in (the setup access point needs it):
   ```
   make -C host target=sdio CONFIG_AP_SUPPORT=y ARCH=arm \
     CROSS_COMPILE=~/luckfox-pico/tools/linux/toolchain/arm-rockchip830-linux-uclibcgnueabihf/bin/arm-rockchip830-linux-uclibcgnueabihf- \
     KERNEL=~/luckfox-pico/sysdrv/source/objs_kernel   # the SDK's kernel build folder
   ```
   This gives `host/esp32_sdio.ko`. It needs `CONFIG_CFG80211=y` and the
   Bluetooth core `CONFIG_BT=y` in the kernel (its `esp.h` includes the HCI
   core, and `esp_bt.c` calls it whatever the C6 runs), both in
   `board/sdk/layercam.config`. The toolchain and kernel-build paths are
   the SDK's (`build.sh`, `sysdrv/Makefile.param`); this has not been
   built.
5. **Copy LayerCam's files into the SDK:**
   ```
   UPDATE_PUBKEY=update.pub USB_ID=vvvv:pppp ESP_HOSTED_KO=host/esp32_sdio.ko \
   C6_FW=network_adapter/build [SC4336H_CHIP_ID=0x....] \
   board/install-into-sdk.sh ~/luckfox-pico native/layercam-media
   ```
   This copies the device tree, the kernel option fragment and the board
   config; makes the SC4336H driver (*The sensor driver*) in the SDK's
   kernel; adds the SC4336H's IQ file to rkaiq's `isp_iqfiles` (a copy of
   the SDK's `sc4336_CMK-OT2117-PC1_30IRC-F16.json`, unless one is there);
   appends `board/sdk/buildroot.fragment` to `luckfox_pico_defconfig`
   (four packages; root login off, dhcpcd out: *Security*); and makes the
   overlay `overlay-layercam`, the only one: the init scripts
   (`S21-layercam-gesture`, `S50usbdevice`, `S50sshd`, `S21appinit`,
   `S99layercam` and the empty ones), `/etc/shadow` and
   `/etc/ssh/sshd_config`, `layercam-net`, `layercam-setup` and
   `layercam-c6-flash`, the Python package in `/usr/share/layercam`, the
   helper in `/usr/bin`, `esp32_sdio.ko` in `/lib/modules`, the C6 firmware
   in `/usr/share/layercam-c6/`, and `/etc/layercam/` (the update key,
   `rootfs-version`, `usb-id`). `update.pub` is the public half of the key
   that signs app updates (*Updates*); without it the cameras refuse every
   update. `USB_ID` is the product's USB vendor:product id; without it the
   development placeholder 1d6b:0104 is used (*Limits*). Without
   `ESP_HOSTED_KO` the image has no Wi-Fi; without `C6_FW` the C6 firmware
   has to be copied onto the camera to flash it.
6. **Build:** `./build.sh lunch` (choose `RV1106_LayerCam_Pro_v1`), then `./build.sh`.
   The image is `output/image/update.img`.

What the board config changes from Luckfox's Pro Max SPI NAND config
(`board/sdk/BoardConfig-SPI_NAND-Buildroot-RV1106_LayerCam_Pro_v1-IPC.mk`,
each change marked):

| Setting | Pro Max | LayerCam Pro |
|---|---|---|
| `RK_KERNEL_DTS` | `rv1106g-luckfox-pico-pro-max.dts` | `rv1106g-layercam-pro-v1.dts` |
| partitions | userdata 10M, rootfs 210M | userdata 90M (timelapses), rootfs 130M |
| `RK_KERNEL_DEFCONFIG_FRAGMENT` | none | `layercam.config` |
| `RK_ENABLE_WIFI` / `RK_ENABLE_WIFI_CHIP` | none | `y` / not set: the SDK's wpa_supplicant, hostapd and dnsmasq, and no chip's driver or firmware (v1 had `AP6XXX`). The SDK's `drv_ko/wifi` may still build its other vendors' SDIO modules (unused, harmless; bcmdhd only with `CONFIG_RFKILL=y`, which is gone) |
| `RK_CAMERA_SENSOR_IQFILES` | three sensors | `sc4336h_LayerCamPro_LCP-F16.json` |
| `RK_POST_OVERLAY` | Luckfox's four | `overlay-layercam` only (no Broadcom/Realtek firmware needed) |
| `RK_APP_TYPE` | `RKIPC_RV1106` | not set (our service owns the camera) |

Starting points: Buildroot `luckfox_pico_defconfig`, kernel
`luckfox_rv1106_linux_defconfig`, U-Boot `luckfox_rv1106_uboot_defconfig`.

**Buildroot packages** (`board/sdk/buildroot.fragment`): `python3`,
`python3-ssl`, `ca-certificates` and `ntp` are already in
`luckfox_pico_defconfig`; added are `BR2_PACKAGE_CIFS_UTILS` (mount.cifs,
SMB upload), `BR2_PACKAGE_NFS_UTILS` (mount.nfs, NFS upload),
`BR2_PACKAGE_IW` (transmit power) and `BR2_PACKAGE_I2C_TOOLS`
(`i2ctransfer`, bring-up). `BR2_PACKAGE_FFMPEG` is optional (only for
`camera.backend = command`).

**Kernel options** (`board/sdk/layercam.config`): `CONFIG_WIRELESS`,
`CONFIG_CFG80211` and `CONFIG_BT` (the Bluetooth core only, for
`esp32_sdio.ko`'s symbols), `CONFIG_VIDEO_SC4336H=m` (the port below),
`CONFIG_CIFS`. v1's `CONFIG_RFKILL`/`CONFIG_RFKILL_RK` (bcmdhd's
`wlan-platdata`) are gone. GPIO sysfs, I2C char devices, the 8250 UARTs,
the DW MMC host and its `mmc-pwrseq-simple`, the SARADC, gpio-leds, PWM,
tmpfs and NFS are already in the defconfig, and so is what the no-button
parts need: the USB gadget with configfs and its CDC-ACM function
(`CONFIG_USB_GADGET`, `CONFIG_USB_CONFIGFS`, `CONFIG_USB_CONFIGFS_ACM`)
for the USB console, and `CONFIG_SYSCON_REBOOT_MODE` (rv1106.dtsi's
`reboot-mode` node has `mode-loader`) for `reboot-loader`.

**Module loading.** `S21appinit` loads `sc4336h.ko` first, then the SDK's
`insmod_ko.sh` (whose fixed list has no `sc4336h.ko`, and which reads the
bound sensor's height for `rockit.ko`). `S99layercam` loads
`esp32_sdio.ko` before the service starts.

### The sensor driver

No SC4336H driver exists: not in the Luckfox SDK (`sc4336.c` accepts only
chip ID 0xdc42, `sc4336p.c` only 0x9c42), not in Rockchip's develop-5.10
or develop-6.1 kernels, not in Ingenic's or OpenIPC's tables. SmartSens
keeps the chip ID and the register table under NDA. What the family shares
and the SDK's `sc4336.c` already does: the 24 MHz `xvclk`, XSHUTDN then
PWDNB at power-up (6-8 ms, then 8192 clocks before the first I2C), the
16-bit ID at 0x3107/0x3108, and one mode, 2560 x 1440 RAW10, 2 lanes,
630 Mbit/s a lane, 25 fps.

`tools/sc4336h-port.py SDK/sysdrv/source/kernel` copies `sc4336.c` to
`sc4336h.c` with every name changed (compatible `smartsens,sc4336h`, driver
and sensor name `sc4336h`, which also makes rkaiq look for
`sc4336h_*.json`), adds `VIDEO_SC4336H` to the Kconfig and the Makefile,
and changes nothing else: **no register value is made up, and the
register table, mode timing and gain/exposure limits stay the SC4336's**
(marked `TODO(SC4336H)` in the file). `install-into-sdk.sh` runs it.

- Without `SC4336H_CHIP_ID` the driver's `CHIP_ID` is 0x10000, which no
  16-bit read matches: at boot it powers the sensor, reads the ID, logs
  `Unexpected sensor id(00xxxx), ret(0)` and does not bind. That is the
  first ID read (*Bringing up a board*).
- With `SC4336H_CHIP_ID=0x....` (what it read) the driver binds. Whether
  the SC4336's register table then gives a picture on an SC4336H is not
  known; SmartSens calls the SC4336H pin-to-pin with its predecessor, a
  new process (DSI-3) suggests its own analog settings. Ask SmartSens (or
  their agent) for the SC4336H's Rockchip driver patch or init sequence and
  put it into `sc4336h.c` before trusting the picture.
- The IQ file is the SDK's SC4336 one (CMK-OT2117-PC1 module, 30IRC-F16
  lens) under our names, `sc4336h_LayerCamPro_LCP-F16.json`: a starting
  point for tuning this lens, nothing more. There is no `CAC_` folder for
  it (rkaiq's lens correction then has nothing to load).

### The device tree

[`dts/rv1106g-layercam-pro-v1.dts`](dts/rv1106g-layercam-pro-v1.dts):
Luckfox's `rv1106.dtsi` + `rv1106-evb.dtsi` like their boards, the flash
and the camera pipeline as the Pro Max, the SDIO as the Pico Ultra W, the
Wi-Fi power sequence as esp-hosted-linux's own overlay
(`host/overlays/esp32-sdio-pwrseq.dts`). Every pin is the one
`src/circuit.py` gives (`tests/test_pins.py` checks it):

| Function | Pin | Device tree |
|---|---|---|
| SC4336H, 2-lane MIPI | CSI D0/D1/CK | `csi2_dphy0` → `mipi0_csi2` → `rkcif` → `rkisp` (as the Pro Max) |
| sensor I2C | I2C4_M2 | `&i2c4`, `i2c4m2_xfer`, 400 kHz, `sc4336h@30` (SID low) |
| sensor clock, 24 MHz | GPIO3_C4 (MIPI_REFCLK_OUT0) | `mipi_refclk_out0`, `MCLK_REF_MIPI0` |
| sensor XSHUTDN / PWDNB | GPIO3_C5 / GPIO3_C6 | `reset-gpios` / `pwdn-gpios`, both `GPIO_ACTIVE_HIGH` (1 = run, as Rockchip's evb) |
| IQ file | | module `LayerCamPro`, lens `LCP-F16` |
| IR-cut H-bridge IN1 / IN2 | GPIO1_A0 / GPIO1_A1 | plain GPIOs, held low with pull-downs (pinctrl hog) |
| IR LED switch | PWM3_IR_M1 (GPIO1_B0) | `&pwm3` on `pwm3m1_pins` (its default `pwm3m0` would take GPIO0_A2, the C6's boot strap) |
| BOOT pad TP5 (MaskROM strap; no button) | SARADC_IN0 | `&saradc` (1.8 V reference): read only to warn if it leaks towards ground (`hw.boot_pad_problem`); the evb's `adc-keys` node removed, it would poll this pin as volume keys |
| light sensor | SARADC_IN1 | `&saradc` |
| status LED | GPIO1_C0 | `gpio-leds`, `/sys/class/leds/status` |
| Wi-Fi SDIO, 3.3 V | SDMMC0 | `&sdmmc`, `no-1-8-v`, `non-removable`, `mmc-pwrseq`, `espressif,full-chip-reset` (the pwrseq really resets the C6), 25 MHz for bring-up (the C6 does 50) |
| WIFI_EN (the C6's EN) | GPIO1_A2 | `sdio-pwrseq` `reset-gpios`, active low, **`post-power-on-delay-ms = <1500>`** (esp-hosted: the C6 is not reliably CMD52-ready after v1's 200 ms) |
| WIFI_BOOT (the C6's GPIO9) | GPIO0_A2 | plain GPIO with pull-up (pinctrl hog; 10k up on the board): free for `layercam-c6-flash` |
| C6 UART0 | UART1_M0 (GPIO1_A3 TX, GPIO1_A4 RX) | `&uart1` on `uart1m0_xfer` only (no RTS/CTS), `/dev/ttyS1` |
| WIFI_HOST_WAKE (the C6's IO4) | GPIO0_A3 | pull-down, unused (the camera never suspends) |
| no bcmdhd, no Bluetooth | | v1's `wlan-platdata` and `bluetooth-platdata` nodes removed |
| console | UART2_M1, 115200 | `fiq_debugger` (rv1106.dtsi default) |
| USB-C, USB 2.0 | OTG controller | `&usbdrd_dwc3` `dr_mode = "peripheral"`: the board is a USB device only (Rd on CC, no VBUS switch, no ID pin), which `otg` would have to guess; the setup console is a configfs gadget on it; MaskROM and the U-Boot loader flash over the same port without Linux |
| not fitted | | `gmac`, `i2s0_8ch`, `acodec` disabled (`acodec`'s amplifier GPIO on the Pro Max is our IRCUT_B) |

## Flashing a new board (BOOT pads, MaskROM)

The test pads (`src/circuit.py`): **TP4** 5 V, **TP1** console TX, **TP2**
console RX, **TP3** ground (those three in a row along the bottom edge,
below the heatsink), and left of the SoC, in one row: **TP6**/**TP7** the
C6's own USB D-/D+, **TP8** ground, **TP5** BOOT. BOOT is the SoC's MaskROM strap (SARADC_IN0, 10k up to 1.8 V,
1 nF, 100R to the pad), so shorting it to ground is harmless.

1. Bridge **TP5 BOOT** and **TP8 G** (side by side) with tweezers, plug the USB-C into the
   computer, keep the bridge for a second, then lift it. The boot ROM
   finds BOOT low and waits for flashing over USB (`upgrade_tool ld`, or
   `lsusb`, shows a Rockchip device in *Maskrom*). Only a blank board, or
   one whose loader is broken, needs this.
2. In the SDK: `./rkflash.sh update` (`upgrade_tool uf output/image/update.img`):
   the loader, the partition table and every partition, `/userdata` empty.
   On Windows, the flashing tool Luckfox's documentation gives for the
   Pico boards with the same file (not checked here).
3. It starts by itself: the computer finds a USB serial port (the setup
   console), and the kernel console is on TP1 (TX), TP2 (RX), TP3
   (ground), 115200 baud, 3.3 V. **On a new board the C6 is blank**, so
   there is no Wi-Fi yet: flash it next (below).

## Bringing up a board

In this order, on the kernel console or the USB console's `ssh on` shell.
Nothing here has been done on a real board.

1. **Flash the C6 first** (no Wi-Fi, so no setup access point, until it
   has esp-hosted's firmware). With the firmware in the image
   (`C6_FW` at build time):
   ```
   /etc/init.d/S99layercam stop
   layercam-c6-flash --flasher-args /usr/share/layercam-c6/flasher_args.json
   ```
   It unloads `esp32_sdio`, unbinds the SDIO controller (`ffaa0000.mmc`)
   and its `sdio-pwrseq` so GPIO1_A2 is free, holds GPIO9 low (GPIO0_A2)
   and pulses EN, speaks the C6 ROM's serial protocol on `/dev/ttyS1`
   (sync at 115200, then 460800; `--baud 115200` if that fails), writes
   each image and compares the MD5 the C6 reads back from its flash, then
   lets GPIO9 go, binds the controller again (the pwrseq pulses EN, 1.5 s)
   and reloads `esp32_sdio`. Plain Python, no esptool. If the C6 does not
   answer: TP6/TP7 are its USB, and `esptool --chip esp32c6 write_flash
   ...` from a computer works without Linux. Later updates can go over
   SDIO: `insmod esp32_sdio.ko ota_file=/path/network_adapter.bin`.
2. **Check Wi-Fi:** `dmesg | grep -i esp` (the SDIO card found, the C6's
   boot-up exchange), `iw dev` shows `wlan0`, `iw list` shows 2.4 GHz only.
   Then `/etc/init.d/S99layercam start`: the status LED blinks slowly and
   the setup access point opens (*Setting it up*). If the SDIO card is not
   found: the 1500 ms delay, the pull-ups, 25 MHz; esp-hosted on Rockchip's
   dw_mmc has not been shown by anyone yet.
3. **Read the sensor's chip ID.** With the first image (no
   `SC4336H_CHIP_ID`) the driver reads it at boot and stops:
   `dmesg | grep sc4336h` shows `Unexpected sensor id(00xxxx), ret(0)`;
   `ret(0)` means the sensor answered on I2C, the number is its ID. A
   nonzero `ret` (no answer): check the 24 MHz clock on GPIO3_C4, the 2.8 V
   and 1.8 V rails, XSHUTDN/PWDNB going high, and that the SID ball is low
   (0x30). Rebuild with `SC4336H_CHIP_ID=0x....` (*The sensor driver*).
   Once the driver binds, confirm the ID with `i2ctransfer` while the
   sensor is powered (live view on the page, or the helper streaming); `-f`
   because the driver owns the address:
   ```
   i2ctransfer -f -y 4 w2@0x30 0x31 0x07 r2
   ```
   Two bytes, 0x3107 then 0x3108 (the SC4336 reads `0xdc 0x42`). With no
   driver holding the sensor powered and clocked it will not answer: its
   I2C needs the clock and XSHUTDN/PWDNB high, which only the driver sets.
4. **The picture:** live view on the setup page. With the SC4336's
   registers expect anything from a good picture to none (*The sensor
   driver*); then the IQ file's tuning for this lens and the IR-cut.
5. **The rest as v1:** `netstat -tuln` (*Security*), the gesture timing,
   the USB console on three systems, `reboot-loader` (*Limits*).

## Updates

**The camera software, over the air.** The Python package changes most,
so it updates without a computer (`layercam/update.py`):

1. Once: make a signing key, `python3 tools/layercam-sign.py keygen update.key`,
   keep `update.key` off the cameras, and build the image with its public
   half (`UPDATE_PUBKEY=update.pub board/install-into-sdk.sh ...`), which
   lands in `/etc/layercam/update-keys` on the rootfs.
2. Each release: raise `VERSION` in `layercam/__init__.py`, then
   `python3 tools/layercam-sign.py pack update.key layercam-0.2.1.lcup`.
3. Install: on the setup page, *software* > *Install update*; or, with the
   package already on the camera, `update FILE` on the USB console. The
   LED flickers while it is checked.

The camera takes a package only if: Ed25519-signed (in plain Python,
checked against RFC 8032's vectors and OpenSSL) by a key in
`/etc/layercam/update-keys`, which an app update cannot change; made for
`LayerCam Pro v1` (a LayerCam v1 package is refused: other pins, other
sensor); newer than what runs (an older signed version could bring
an old bug back; `--allow-downgrade` on the USB console overrides);
`min_rootfs` no newer than the image's `/etc/layercam/rootfs-version`; the
payload's SHA-256 and every file's SHA-256 match the signed manifest, with
no other file and no path outside `layercam/`; and the new code imports.
It is unpacked to `/userdata/layercam/app/slots/<version>/`; the factory
copy in `/usr/share/layercam` is never touched.

Before every start, `S99layercam` asks the factory copy of `update.py`
which copy to run. A new version is on trial: it has 3 starts to stay up
for 90 s, then it is kept and older ones are deleted; if it does not, the
last good version (or the factory one) runs again and the page says so.
`layercam-setup update --status` shows the state, `update --factory` goes
back to the rootfs's own version.

**A full image (kernel, rootfs, C helper), over USB without opening the
camera.** On the USB console, `reboot-loader` restarts into U-Boot's USB
download mode (*Loader* in `upgrade_tool ld`); then, in the SDK,
`./rkflash.sh rootfs`, `./rkflash.sh oem` and `./rkflash.sh boot` (last:
it restarts the camera) write those partitions and keep `/userdata`, so
the settings, the Connect token and fingerprint, and the videos stay.
`./rkflash.sh update` would write an empty `/userdata`. rkdeveloptool
speaks the same protocol (not tried with these SPI NAND images). If the
camera no longer starts far enough for the console, the BOOT pads (above)
always work.

**Why no A/B system or recovery partition.** The 256 MB NAND is full:
env 256K, idblock 256K, U-Boot 512K, boot 4M, oem 30M, userdata 90M,
rootfs 130M. A second rootfs would need 130M more. The SDK's recovery
(`RK_ENABLE_RECOVERY`: a kernel and BusyBox ramdisk in a `recovery`
partition, a `misc` partition, an `update_ota.tar` written with
`flash_eraseall`/`nandwrite`) would fit in about 8M taken from userdata,
but its `RkLunch-recovery.sh` looks for the package on an SD card, so it
needs adapting to read it from `/userdata`, and a new partition table
means flashing once with `update` (settings lost). Writing the rootfs over
the air without a second copy risks a camera that only the BOOT pads can
bring back after a power cut, so the camera updates the software over the
air and the image over USB. The C6's firmware is a third part: from the
camera with `layercam-c6-flash`, or over SDIO with esp-hosted's
`ota_file=` (*Bringing up a board*); the app update does not carry it.

## Setting it up

The camera's own setup access point is **LayerCam-XXXX**, with a
passphrase made from its SoC's serial number (the RV1106's
one-time-programmable id, `Serial` in `/proc/cpuinfo`), so every camera
has its own. To read it, any of:

- plug the camera into a computer by USB-C and type `ap` on its USB
  console (below), or run `python3 tools/layercam-ap.py --port /dev/ttyACM0`;
- `python3 tools/layercam-ap.py SERIAL` from a serial number you already
  have (for a label);
- the serial console (TP1/TP2, 115200) prints `LayerCam setup: Wi-Fi
  LayerCam-XXXX, passphrase xxxx-xxxx-xxxx` each time the access point opens.

A camera whose SoC shows no serial falls back to its random fingerprint,
and then the USB and serial consoles show the passphrase.
`wifi.ap_password` replaces it with your own.

1. **First boot** (or no network saved): the setup access point opens and
   the status LED blinks slowly. Join it with a phone and open
   `http://192.168.4.1` (any web name resolves to the camera there, so most
   phones offer the page by themselves).
2. On the page, fill in at least:
   - **wifi**: your network and password (WPA2; empty for an open network).
   - **connect.token**: in Prusa Connect, open the printer, *Camera* > *Add
     new camera* > *other camera*, copy the token. **Use it within 15
     minutes** or Connect forgets the camera; the camera's first call binds
     its fingerprint to the token for good.
   - **prusalink**: the printer's address and its PrusaLink password (on
     the printer: Settings > Network > PrusaLink).
   - **upload**: a target, or `none` to keep the videos on the camera
     (download them from the page).
   - **web.password** (8 characters or more): required before a network can
     be saved; from then on the page always asks for it (user `admin`).
3. Save. The camera joins your network, and its address appears in Prusa
   Connect (camera info) and on the router. Put that address in the slicer
   snippet's `start.gcode` ([`slicer/README.md`](slicer/README.md)). If the
   password was mistyped, the access point is back after 2 minutes.
4. Every setting is in one file, `/userdata/layercam/layercam.ini`;
   [`board/layercam.ini.example`](board/layercam.ini.example) lists them
   all with their defaults and what they do. A setting the camera cannot
   use falls back to its default and is listed on the page: a mistake in
   the file never stops the camera.

### Wi-Fi without a button

| | When | What happens |
|---|---|---|
| a. setup access point | first boot, or no network saved | the access point and the page, until a network is saved; LED slow blink |
| b. network unreachable | the saved network not joined for `wifi.fallback_ap_min` (10 minutes; 2 for a network just entered) | the access point opens too. Every `wifi.retry_s` (2 minutes), while no phone is joined to it, the camera tries the saved network for up to 45 s; once connected the access point closes. One radio, so the two take turns (`net.WifiSupervisor`) |
| c. power-cycle gesture | three short power-ups in a row | the network, its password and any own access point passphrase are forgotten; the access point opens (a) |
| d. USB console | plugged into a computer | `wifi`, `reset-wifi`, `set`, `ap`, `status`, `update`, `reboot-loader` on a USB serial port |

**The gesture (c).** Plug in; after a few seconds (the boot, to measure on
the board) the LED flashes quickly once: that power-up is counted. Unplug
within 5 s. Plug in again: two flashes; unplug. Plug in a third time and
leave it: three flashes, then the slow blink of the setup access point. A
power-up that stays on 5 s past its flashes sets the count back to 0, so
ordinary use, a printer switched off and on, or a power cut never adds up
to it. The time *between* power-ups cannot be measured (the RTC has no
battery), so there is no strict 30-second window: what matters is that
the three come in a row. The count is one tiny file on `/userdata`
(`bootcount`), written when the power-up is counted and again 5 s later,
nothing after; UBIFS spreads those writes over the whole volume, and the
NAND's 100 000 erases per block are far beyond any number of boots
(`layercam/gesture.py`). The Connect token, PrusaLink, upload settings and
`web.password` stay.

**The USB console (d).** Plugged into a computer, the camera is a USB
serial port (CDC-ACM: `/dev/ttyACM0` on Linux, `/dev/cu.usbmodem*` on
macOS, a COM port on Windows 10 and later; no driver needed). Open it with
any terminal (`screen /dev/ttyACM0`, picocom, PuTTY), press Enter, type
`help`:

```
status                       version, network, service, problems
ap                           the setup access point's name and passphrase
wifi "My Network" "password" join this network (wifi NAME --open: no password)
reset-wifi                   as the gesture
show / get / set KEY VALUE   any setting, checked as on the page; secrets never shown
update FILE | --status | --factory
ssh on PUBLIC-KEY | off      SSH for this key only (Security); off deletes the keys
reboot, reboot-loader        restart; restart into the USB loader (Updates)
```

It is a fixed set of commands, not a shell, and replaces the Luckfox
image's adb and USB network (an unauthenticated root shell on the cable).
Whoever holds the camera can use it, as they could the gesture; it can set
a forgotten `web.password`. On the printer's USB port, which only gives
power, nothing enumerates it and it waits. The same commands work on the
serial console pads as `layercam-setup ...`.

**Upload targets:** `s3` signs requests with SigV4 (keys need `PutObject`
on the bucket; `s3_addressing = path` for MinIO and NAS stores); `http`
PUTs into a folder URL (WebDAV works; Basic authentication); `smb` mounts
`//server/share` with the kernel's CIFS client (password passed in a
0600 file, not on the command line), writes `name.part`, renames it, and
unmounts; `nfs` mounts `server:/path` the same way (`nolock`). A failed
upload is retried after 10 s, 1, 5, 15 and 60 minutes, and the video stays
on the camera if all fail. The camera keeps the last `keep_local` uploaded
videos.

### Status LED

| LED | Means |
|---|---|
| a few quick flashes right after power-up | the power-cycle gesture counted this power-up (1, 2 or 3 flashes) |
| flicker | installing an update: leave the power on |
| slow blink (1 s) | setup access point is on (a, b or c above) |
| long on, short off | hot: the thermal governor is throttling or has stopped the camera (the page says how hot) |
| fast blink | joining Wi-Fi, or trying the saved network again |
| three blinks, pause | something needs attention: see the page or `status` on the USB console (Connect refused the token, PrusaLink unreachable, a frame lost, storage low, the BOOT pad leaking) |
| double blink | recording a timelapse |
| steady on | on the network, idle |

Most urgent first: only the first that applies shows.

**Night:** below 0.10 V on the light sensor for 5 s (around 10 lux; about
0.5 V is 50 lux) the IR-cut filter opens and the picture turns grey; above
0.25 V for 5 s it switches back. Between the two nothing changes, so a
flicker or a passing hand does not toggle it. At night each picture lights
the IR LEDs briefly (ramped up, 500 ms for the exposure, the frame, ramped
down), and live view keeps them on while it runs; `ir.mode = printing`
does this only during prints.

## Security

What the camera offers on the network is its page (port 80), the printer's
metrics stream (UDP 8514, in), and, only while it is on, the setup access
point's DHCP and DNS. Nothing else, unless the owner turns SSH on.

| | LayerCam | Why |
|---|---|---|
| root account | no password at all (`*` in `/etc/shadow`; `# BR2_TARGET_ENABLE_ROOT_LOGIN is not set` in `buildroot.fragment`) | Luckfox's image gives every board root password `luckfox`. A per-camera password derived from the serial (as the access point's) would be no secret: the serial is on the USB console, in the USB serial number, on the kernel console, and the code is public. With no password nothing can be guessed; shell access is SSH with a key |
| SSH | off. `ssh on KEY` on the USB console (paste the `.pub` line) turns it on for that key, keys only, root by key only, no passwords, no forwarding (`/etc/ssh/sshd_config`); keys and host key on `/userdata/layercam/ssh`; `ssh off` deletes the keys and stops sshd, sessions included; `ssh` shows the key and host fingerprints | Luckfox's overlay started sshd on every boot with `PermitRootLogin yes` and password login |
| the page | always needs `web.password` (8+ characters; HTTP Basic, user `admin`; a wrong one costs a second). Until one is set it answers only on the setup access point (WPA2, the camera's own passphrase) and to the camera itself; a network cannot be saved from the page without one. A forgotten one: `set web.password "..."` on the USB console | before, an empty `web.password` left the page, the settings and the update upload open to anyone on the network |
| Luckfox overlays | only `overlay-luckfox-wifibt-firmware` is kept (`RK_POST_OVERLAY`) | `-buildroot-shadow`: root's password and a Samba share of `/`, read-write as root; `-buildroot-init`: sshd as above, `/root/main.py` run at boot; `-config`: pin settings loaded from a partition that is not its own here |
| rkipc | never started: LayerCam's `S21appinit` only loads the media drivers (the SDK's own one runs `RkLunch.sh`) | RTSP and a web server with no password, if it is ever in the image |
| adb | not started (`S50usbdevice` replaced), `/usr/bin/adbd` replaced by a stub | an unauthenticated root shell, over USB and, in Luckfox's build, TCP 5555 |
| ntpd, dhcpcd, telnet | `S49ntp`, `S41dhcpcd`, `S50telnet` empty; dhcpcd also out of the build | ntpd would answer NTP on the Wi-Fi (the clock is set once per connection by `layercam-net` instead); dhcpcd would fight `udhcpc` for wlan0; telnetd is not in Buildroot's BusyBox config, the stub makes sure |

`pincheck.py` checks all of this in the board config, the fragment and the
overlay (21 checks, also run by the board build through
`src/check_firmware.py`), and `tests/test_image.py` shows each check fails
when its file is put back the way Luckfox has it. What it cannot see is
the built image itself: on the first board, check `netstat -tuln` (only
80 and 8514, plus 53/67 with the access point on), that the kernel console
asks for a login nobody has, and that `ssh` is refused until turned on.

## On a PC

The service runs on any Linux or macOS machine with Python 3.8+, for
development:

```
python3 -m layercam --config dev.ini --port 8080
```

with `camera.backend = command` (any program that writes one JPEG, e.g.
ffmpeg from a USB webcam, the default command) or `fake`; the board's
GPIO, ADC and PWM are skipped when their files are missing.

## Tests

```
python3 -m unittest            # from this folder; 212 tests, about 15 s
```

| File | What it checks |
|---|---|
| `test_connect.py` | snapshot and camera-info requests: URL, headers (Token, Fingerprint, User-Agent, Content-Type, Content-Length), 1 MB limit, token and fingerprint lengths, only documented camera-info keys; rate limit (10 s, back-off after 429/503), stop after 401/403/422, quality lowered for size, a test from the page never beats the 10 s minimum |
| `test_prusalink.py` | Digest auth against a fake printer that checks it as Buddy does (no qop, stale nonce), RFC 2617's own example, API key, unreachable printer; status/job parsing for printing, finished, stopped, idle, no job (204); video names |
| `test_metrics.py` | line protocol (floats, integers, strings with spaces and escapes, events, tags, errors), Buddy's syslog header, trigger age from the datagram's timestamps, MeatPack-style missing space, a real UDP socket |
| `test_timelapse.py` | start/layer/finish/cancel, duplicate and out-of-order triggers, missed triggers counted, late triggers warned, trigger before PrusaLink sees the job, a new job without an end, pause, the Z fallback (Z hops filtered), UDP-only and poll-only modes, thinning, no-PrusaLink timeout |
| `test_sigv4.py` | AWS's SigV4 test suite (23 cases: canonical request, string to sign, Authorization header) and three S3 PUTs signed by botocore |
| `test_upload.py` | S3 path and virtual-host addressing, what the server receives is what was signed, no chunked encoding; HTTP PUT; SMB and NFS mount commands, credentials file mode and clean-up, mount failure; retries |
| `test_mp4.py` | SPS parsing (hand-built SPS, with cropping), NAL splitting, and MP4s at 2560 x 1440 and 320 x 180 checked by ffprobe and decoded by ffmpeg, including a frame cut off by a power loss |
| `test_recording.py` | the C helper's protocol against a stand-in (asleep until woken, rate changes), a whole H.264 timelapse to MP4, the helper crashing mid-print, JPEG frames with thinning, ffmpeg and hardware-encoder paths, pruning (unsent videos never deleted) |
| `test_service.py` | the whole service: fake printer, five layers (one sent twice), print finishes, the MP4 arrives at the upload server with five frames, named after the job; the page's password and hidden secrets; a missing camera helper does not stop the service |
| `test_config.py` | types, validation of every rule, the example file lists exactly the real settings, file written 0600, typos rejected, secrets never sent back, the page form; the service's lenient load: a bad value keeps its default, an unknown key (a typo, a newer version's) is kept in the file, a section given twice is read, an unreadable file is moved aside, the page can still save |
| `test_hw.py` | day/night hysteresis and hold time, flicker, IR plan per mode, LED priorities (updating, setup, hot, offline, error, recording, ok; every pattern distinct; no `Button` left), the BOOT pad warning, sysfs writes (ADC, IR-cut pulse order, PWM) against a fake `/sys` |
| `test_gesture.py` | the power-cycle gesture on a fake clock with fake flash that keeps what was written when the plug is pulled: three short power-ups reset (the third at once), ordinary power-ups never add up and write twice each, one long power-up cancels, the 5 s edge, a power-up cut before it is counted; the count file (torn or garbage reads 0), the init script's call, and the service forgetting network, password and own AP passphrase but keeping `web.password` |
| `test_wifi.py` | when the setup access point opens and closes, on a fake clock: first boot, connected, exactly 10 minutes unreachable, retries every 2 minutes for 45 s, connected on a retry (and the full 10 minutes again after), never cut off while a phone is on it, 2 minutes for a network just entered, fallback off; the phones on the access point from hostapd's control socket (STA-FIRST/STA-NEXT against a stand-in hostapd, `iw` not asked) and from `iw`'s station dump; the service driving a stand-in `layercam-net` |
| `test_setupcli.py` | the USB console: argument parsing (quoted names, `--open`, `--`, refused commands, no shell), each command against a settings file (validated like the page, SIGHUP to the service, the short fallback for a new network, secrets never printed, a forgotten `web.password` set, unknown keys kept, `reset-wifi` as the gesture, `reboot-loader`), the console loop fed line by line, and the real loop on a pseudo-terminal; `ssh on/off/status`: off by default, a pasted key (unquoted too), files 0600 in a 0700 folder, the same key once, sshd restarted and stopped, keys deleted on off; refused: no key, a private key, options such as `command=`, damaged base64, a type that does not match, RSA under 2048 bits; comments cleaned; fingerprints as `ssh-keygen -l` |
| `test_image.py` | `pincheck.image_results`: root locked, no password in `/etc/shadow` or the fragment, Luckfox's shadow/init/config overlays out, sshd keys only and off unless turned on, no ntpd/dhcpcd/telnet/USB network/adb/rkipc, the USB id file; each check shown to fail with Luckfox's version of its file; the board build runs them; `install-into-sdk.sh` on a stand-in SDK (fragment block replaced on a second run and later than Luckfox's lines, USB id and update key written, a bad USB id refused, the placeholder warned about; the SC4336H driver made once, its IQ file, a tuned IQ file kept, `esp32_sdio.ko`, the C6 firmware and `layercam-c6-flash` in the overlay, `SC4336H_CHIP_ID` reaching the driver, an SDK without `sc4336.c` refused); the page: no password = only the setup access point and the camera itself (403 elsewhere), wrong password = 401 after a second, a network cannot be saved without a password |
| `test_update.py` | Ed25519 against RFC 8032's vectors and OpenSSL; packages: good, wrong key, no keys, same/older version, needs a newer image, wrong product, a changed manifest, payload or extra member, junk, unsafe paths even when signed; the signing tool; the keys file; trial start, kept after it stays up, rollback after 3 failed starts (to the last good version or the factory one), code that does not import never installed, a missing slot, factory reset, the init script's question with a broken state file; an upload to the setup page |
| `test_net.py` | WPA PSK against the IEEE 802.11i test vector, wpa_supplicant/hostapd/dnsmasq files, 2.4 GHz channel list, power settings; the setup access point's name and passphrase per device (stable, different per serial, readable alphabet), `/proc/cpuinfo` serial parsing, the host tool |
| `test_pins.py` | `pincheck.py`: `layercam/board.py` and the device tree against `src/circuit.py` (46 checks: the C6's EN in the pwrseq with 1500 ms and `espressif,full-chip-reset`, its GPIO9 pulled up and free, UART1_M0 TX/RX only, no bcmdhd/Bluetooth nodes; the SC4336H node, address, XSHUTDN = `reset-gpios`, PWDNB = `pwdn-gpios`, module/lens = the IQ file, 2 lanes; also no button, TP5 through 100R to SARADC_IN0, the evb's ADC keys removed, the USB controller a device) and 8 SDK checks (device tree, IQ file, no `RK_ENABLE_WIFI_CHIP`, no wifibt overlay, `CONFIG_VIDEO_SC4336H`, `CONFIG_CFG80211` + `CONFIG_BT`, no bcmdhd options); proved to catch a moved LED, a wrong PWM pin, a swapped IR-cut pin, a button put back, the ADC keys back, a host-mode USB port, v1's 200 ms delay, the reset flag gone, a bcmdhd node back, XSHUTDN/PWDNB swapped, v1's sensor, GPIO9 without its pull-up, flow control on UART1, the C6's EN moved; `src/check_firmware.run()` as the board build calls it (75 checks) |
| `test_c6flash.py` | `tools/layercam-c6-flash.py` against a simulated ESP32-C6 ROM loader on a pseudo-terminal (boot text, eight SYNC answers, SLIP escapes, (failed, error) status bytes) and a fake `/sys`: three images written in 1 KiB blocks with checksums and read back by MD5, the sync, chip check, SPI attach, baud change and FLASH_END in order; `esp32_sdio` unloaded, the controller and pwrseq unbound and bound again in the right order, GPIO9 low before EN rises and let go after, the GPIOs unexported; a flash that reads back wrong, another chip, a C6 that does not answer and a refused command each reported with the board put back; images from `flasher_args.json` and refused when overlapping, off a sector or past 4 MB; the tool's pins = `layercam/board.py` |
| `test_sensor_port.py` | `tools/sc4336h-port.py`: every name changed and nothing else (the file mapped back is the SC4336's but for `CHIP_ID`; the register table value for value; `sc4336p` untouched), `CHIP_ID` 0x10000 or the one given, refused on another file or one already ported, the Kconfig and Makefile entries once after two runs, the SDK's own `sc4336.c` left alone, a bad chip ID refused |
| `test_thermal.py` | the governor's levels, hysteresis, jumps and unreadable sensor; what each level allows; IR LED duty capping and the ramp's steps; the camera power policy; temperature and CPU speed through a fake `/sys`; the service under heat: asleep between pictures, live view time-limited and refused when hot, quality capped, Connect pictures spaced to 30 s and a shorter IR flash from 84 C, Connect skipped from 105 C, frames lost only at 110 C and the camera back under 95 C, LEDs lit only around a night picture and capped at 50 % when throttled, IR-cut pulsed once |
| `test_slicer.py` | the snippets use only G-codes checked in Buddy's source, the park position (PrusaSlicer local variables) inside the CORE One's limits, lines under 96 characters, hold = `dwell_ms`, metric on only around the trigger, and an emulation of Buddy's metrics buffer showing the padding sends the trigger at once |

The MP4, recording and whole-service tests need `ffmpeg` and `ffprobe`
with libx264 on the PC (they make the test video); without them they are
skipped, and the SSH fingerprint cross-check needs `ssh-keygen`. CI
(`ci / layercam-pro-v1`: ffmpeg installed, `ssh-keygen` in its image)
runs all 212; on 2 Nov 2026 on a PC with ffmpeg and without `ssh-keygen`
(Python 3.13): **212 run, 211 pass, 1 skipped** (the `ssh-keygen` one).

Checked on a PC but not as tests (1 Nov 2026): the device tree, run
through `cpp` with the SDK's includes (824b817f) and parsed with Zephyr's
`dtlib` (devicetree 0.0.2): every label and reference resolves; the
pwrseq's EN is gpio1 pin 2 active low with 1500 ms; `&sdmmc` (mmc@ffaa0000)
uses it; `&uart1` (serial@ff4b0000) has only `uart1m0_xfer` (GPIO1_A3/A4);
`sc4336h@30` on i2c@ff470000 has reset gpio3 pin 21 (C5) and pwdn gpio3
pin 22 (C6), its endpoint goes to `csi_dphy_input0`; the pin-controller
hog holds the IR-cut pins, GPIO9's pull-up and IO4's pull-down; no
`wlan-platdata`, `bluetooth-platdata` or `adc-keys` node. Not compiled with
`dtc`. The shell scripts, `sh -n`. `tools/sc4336h-port.py` run on the
SDK's real `sc4336.c`: the result, names mapped back, differs from it only
in the header and `CHIP_ID` (not compiled). The C helper changed only in
comments since v1's `make check`.

## Facts checked against their sources (v1: 26 Oct 2026; the Pro's parts: 1 Nov 2026)

| Fact | Source |
|---|---|
| Connect camera API: `PUT /v1/snapshot` and `PUT /v1/camera-info` on `https://camera-service.prusa3d.com`; `Token` (20 letters/digits), `Fingerprint` (16-64), `User-Agent` required; JPEG ≤ 1 000 000 bytes, `Content-Length` required, 6 uploads a minute; 15-minute registration window; `device.type` one of Buddy3D, ESP32, WEB, LINK, INTERNAL | Prusa Camera Service docs and `openapi.yaml` (camera-service.prusa3d.com/docs/) |
| `connect.prusa3d.com/c/snapshot` and `/c/info` (PUT, same headers, 16 MB) still work but are deprecated | Connect's camera API docs, `connect.prusa3d.com/docs/cameras/openapi/openapi.yaml`; Prusa-Connect-SDK-Printer `prusa/connect/printer/camera.py` (PUT, `Content-Type: image/jpg`) |
| `M334 host port [syslog port]` sets and enables metrics, asks on the screen when the setting changes; `M331`/`M332 <metric>`; `gcode` metric records each executed line; 1 kB buffer, sent when full or after 1 s; line protocol format | Prusa-Firmware-Buddy 6.10.1: `src/marlin_stubs/M330.cpp`, `src/marlin_stubs/gcode.cpp`, `src/common/metric_handlers.cpp`, `src/common/metric.cpp`, `doc/metrics.md` |
| `G90`/`G91` also set E absolute/relative; no `G10`/`G11`/`M240`; `G4 P` in ms; `M118` string argument; 96-character commands; CORE One limits X -2..252, Y -19..221 | Buddy: `lib/Marlin/Marlin/src/gcode/gcode.h`, `gcode.cpp`, `motion/G4.cpp`, `parser.cpp`, `include/marlin/Configuration_COREONE*.h` |
| PrusaLink: Digest, user `maker`, realm `Printer API`, no qop, nonce valid 300 s with `stale`; or `X-Api-Key`; `/api/v1/status` and `/api/v1/job` fields and states; 204 without a job; `axis_x/y` only when not printing | Buddy: `lib/WUI/nhttp/req_parser.cpp`, `status_page.cpp`, `status_renderer.cpp`, `lib/WUI/link_content/basic_gets.cpp`, `prusa_link_api_v1.cpp`, `src/state/printer_state.cpp`; Prusa-Link-Web `spec/openapi.yaml` |
| PrusaSlicer: "After layer change" runs after the travel to the new layer (`layer_num`, `layer_z`, `position` available); CORE One profile retracts on layer change, park X242 Y211 at the end | PrusaSlicer 2.9.6 `src/libslic3r/GCode.cpp`, `resources/profiles/PrusaResearch.ini` |
| SC4336 family: chip ID 0xdc42 (SC4336) / 0x9c42 (SC4336P) at 0x3107/0x3108, 24 MHz xvclk, 2 lanes, 2560 x 1440 RAW10 at 25 fps, 315 MHz link; power-up XSHUTDN (`reset`) then PWDNB (`pwdn`), 6-8 ms, 8192 clocks; no SC4336H driver; IQ files only for the SC4336 | SDK `drivers/media/i2c/sc4336.c`, `sc4336p.c`, `Kconfig`, `Makefile`, `rv1106-evb-cam.dtsi`, rkaiq `isp_iqfiles/`; Rockchip kernel develop-5.10 / develop-6.1 `drivers/media/i2c`; SmartSens SC4336H flyer V1.0 (2560x1440, 1/2-lane MIPI) |
| esp-hosted-linux: cfg80211 FullMAC (`wlanX`), SDIO on the ESP32-C6, Linux 4.9-7.2; `CONFIG_AP_SUPPORT=y` for hostapd; `ARCH`/`CROSS_COMPILE`/`KERNEL` for another kernel; the C6's SDIO needs 1500 ms after EN; `espressif,full-chip-reset`; no `set_power_mgmt` or `dump_station` in its cfg80211 ops, `set_tx_power` present; the C6 firmware sets `WIFI_PS_NONE`; `HOST_WAKEUP_GPIO` 4 on the C6; C6 partitions; `ota_file=`; the host includes the Bluetooth HCI core; esp-hosted-ng and -fg legacy | esp-hosted-linux v1.0.6.0.7 (54d5367): `README.md`, `docs/porting.md`, `docs/guides/{wifi-access-point,host-sleep,ota}.md`, `docs/getting-started/build-and-flash.md`, `host/Makefile`, `host/esp_cfg80211.c`, `host/include/esp.h`, `host/sdio/esp_sdio.c`, `host/overlays/esp32-sdio-pwrseq.dts`, `esp/esp_driver/network_adapter/{main/cmd.c,main/Kconfig.projbuild,partitions.esp32c6.csv,sdkconfig.defaults.esp32c6}`; esp-hosted `README.md` (a042292) |
| ESP32-C6 ROM loader: SLIP, commands (SYNC 0x08, READ_REG 0x0a, SPI_SET_PARAMS 0x0b, SPI_ATTACH 0x0d, CHANGE_BAUDRATE 0x0f, FLASH_BEGIN/DATA/END 0x02-0x04 with the encryption word, SPI_FLASH_MD5 0x13: 32 hex characters from the ROM), 2 status bytes, checksum seed 0xEF, chip magic 0x2CE0806F at 0x40001000, GPIO9 strap | esp-serial-flasher `private_include/protocol.h`, `src/protocol_uart.c`, `src/esp_targets.c`, `port/linux_port.h`; ESP32-C6-MINI-1 datasheet v1.5 |
| SDK: `RK_ENABLE_WIFI` builds wpa_supplicant, hostapd (no hostapd_cli installed on RV1106) and dnsmasq; `RK_ENABLE_WIFI_CHIP` picks the vendor driver and AP6256 firmware; bcmdhd only with `CONFIG_RFKILL=y`; IQ files copied from `media_out/isp_iqfiles` by name; `insmod_ko.sh`'s fixed sensor list and `isp_max_h`; the kernel build in `sysdrv/source/objs_kernel` | SDK `project/app/wifi_app/Makefile`, `sysdrv/drv_ko/wifi/Makefile`, `project/build.sh` (`__PACKAGE_RESOURCES`), `media/isp/Makefile`, `sysdrv/drv_ko/insmod_ko.sh`, `sysdrv/Makefile.param` |
| Pro Max camera/flash tree, Ultra W SDIO tree, pin groups (`pwm3m1_pins` = GPIO1_B0, `uart1m0_xfer` = GPIO1_A3/A4, `i2c4m2_xfer`), `serial1 = &uart1`, `sdmmc` = mmc@ffaa0000, the `dwmmc_rockchip` and `pwrseq_simple` driver names | SDK: `rv1106g-luckfox-pico-pro-max.dts`, `rv1106-luckfox-pico-pro-max-ipc.dtsi`, `rv1106g-luckfox-pico-ultra.dts`, `rv1106.dtsi`, `rv1106-pinctrl.dtsi`, `drivers/mmc/host/dw_mmc-rockchip.c`, `drivers/mmc/core/pwrseq_simple.c` |
| Board config, partitions, Buildroot packages, flashing script | SDK: `BoardConfig-SPI_NAND-Buildroot-RV1106_Luckfox_Pico_Pro_Max-IPC.mk`, `luckfox_pico_defconfig`, `rkflash.sh` |
| rockit MPI and rkaiq calls (VI, VENC JPEG/H.264 fixed QP, `SetJpegParam`, `setGrayMode`, `setMirrorFlip`, ISP init order) | luckfox_pico_rkmpi_example `include/` and `luckfox_mpi.cc`; SDK `simple_vi_bind_venc_jpeg.c`, `sample_comm_isp.c` |
| SigV4 | AWS SigV4 test suite (from botocore); botocore 1.43.119 `S3SigV4Auth` |
| Sensor frame rate through rkaiq's AE attributes (`stFrmRate.isFpsFix/FpsValue`); stop/prepare/start to sleep and wake the ISP | SDK `sample_comm_isp.c` (`SAMPLE_COMM_ISP_SetFrameRate`), rkaiq `rk_aiq_user_api2_ae.h`, `rk_aiq_user_api2_sysctl.h` |
| SoC serial: `cpuinfo` node reads the OTP `id` cell (`CONFIG_ROCKCHIP_CPUINFO=y`); TSADC thermal zone (`CONFIG_ROCKCHIP_THERMAL=y`); cpufreq with `ondemand` as the default governor | SDK `rv1106.dtsi`, `luckfox_rv1106_linux_defconfig` |
| PrusaSlicer `{local name = value}` variables in custom G-code | PrusaSlicer 2.9.6 `src/libslic3r/PlaceholderParser.cpp` |
| Heat: the housing's temperatures streaming, the IR LED strings' current | LayerCam v1's `sim/thermal.md`, `sim/power.md` (the thresholds are v1's) |
| USB: the OTG controller's `dr_mode` (`otg` in rv1106.dtsi, `peripheral` on Luckfox's boards); gadget, configfs and CDC-ACM built in; Luckfox's `S50usbdevice` (adb + RNDIS, gadget `rockchip`) and `S99usb0config`, and where they are installed; overlays applied last, with rsync | SDK `rv1106.dtsi`, `rv1106g-luckfox-pico-pro-max.dts`, `luckfox_rv1106_linux_defconfig`, `sysdrv/tools/board/android-tools/S50usbdevice` and `Makefile`, `sysdrv/Makefile`, `project/build.sh` (`post_overlay`) |
| Loader mode: `reboot-mode` with `mode-loader = BOOT_BL_DOWNLOAD`, `CONFIG_SYSCON_REBOOT_MODE=y`; `rkflash.sh` `update` = `upgrade_tool uf` (all partitions, userdata included), `rootfs`/`oem`/`boot` = `upgrade_tool di` one partition; the SDK's recovery and `update_ota.tar` | SDK `rv1106.dtsi`, `luckfox_rv1106_linux_defconfig`, `project/rkflash.sh`, `project/build.sh` (`build_recovery`, `build_ota`), `project/scripts/RkLunch-recovery.sh` |
| Buildroot's python3 always has ctypes (selects libffi); its zlib module is optional and not in `luckfox_pico_defconfig`, so update packages are plain tar | Buildroot 2023.02.6 `package/python3/Config.in` |
| Ed25519 | RFC 8032 (section 6 code, section 7.1 vectors); OpenSSL 3.0 |
| Luckfox overlays: `-buildroot-shadow` (root `$1$` hash of "luckfox", `smb.conf` sharing `/` read-write as root), `-buildroot-init` (`S50sshd` on every boot, `sshd_config` `PermitRootLogin yes`, `S99python` runs `/root/main.py`), `-config` (`luckfox-config load` at boot); `S21appinit` written by build.sh to run `RkLunch.sh` (rkipc, which also loads the drivers with `insmod_ko.sh`); `post_overlay` after the OEM packaging | SDK `project/cfg/BoardConfig_IPC/overlay/`, `project/build.sh` (`__PACKAGE_OEM`, `build_firmware`), rkipc `src/rv1106_ipc/RkLunch.sh` |
| Buildroot services: `S50sshd` (openssh), `S49ntp` (ntp with ntpd, the default), `S41dhcpcd`, `S50telnet` only with BusyBox's standalone telnetd (off in the default BusyBox config); `BR2_TARGET_GENERIC_ROOT_PASSWD` depends on `BR2_TARGET_ENABLE_ROOT_LOGIN`; the ntp package's ntpd takes servers from `/etc/ntp.conf`, `-p` is a pid file, `-g` for the first big step | Buildroot 2023.02.6 `package/openssh`, `package/ntp`, `package/dhcpcd`, `package/busybox/busybox.mk` and `busybox.config`, `system/Config.in`, `package/skeleton-init-common/skeleton-init-common.mk` (root login off: `*` in `/etc/shadow`) |

## Limits

- **Nothing here has run on LayerCam hardware**, and the C helper, the
  device tree (`dtc`), `esp32_sdio.ko` and the SC4336H driver have not been
  compiled. Expect bring-up work: the helper's rockit calls, the ISP
  start-up, the partition sizes against the real rootfs, and the board
  config's `RK_APP_TYPE` left unset.
- **The SC4336H driver is the SC4336's, renamed.** Its chip ID is unknown
  until read from a board (*Bringing up a board*); its register table,
  mode timing and gain limits are the SC4336's (`TODO(SC4336H)`), and
  whether they work on an SC4336H is unknown: get SmartSens' (NDA) init
  table. Its ball map in `src/circuit.py` is the SC4336P's, also to
  confirm. The IQ file is the SC4336's, untuned for this lens; no CAC
  (lens shading) file. The mode is 25 fps; `timelapse.fps` is the video's
  playback rate, not the sensor's.
- **The ESP32-C6 path is untried on any RV1106.** Nobody has shown
  esp-hosted-linux on Rockchip's dw_mmc yet (the SDIO card found, the
  1500 ms enough, 25 then 50 MHz); `layercam-c6-flash` has only met a
  simulated ROM (the real ROM's timing, the strap sampling, a blank
  module's first boot); `esp32_sdio.ko` needs `CONFIG_BT=y` in the kernel
  (from its source, not from a failed load); the SDK's `drv_ko/wifi` with
  no chip set may build its other vendors' modules. The SDK installs no
  `hostapd_cli`, so the camera talks to hostapd's control socket itself.
- **No Wi-Fi power save from Linux** on the C6 (*Heat and power*):
  `wifi.power_save` is sent with `iw` and refused by the driver; the C6
  firmware is built with power save on instead (`tools/c6-power-save.sh`),
  which the 65 C rating depends on; not yet measured on a camera.
- **WIFI_HOST_WAKE is wired and unused**: the camera never suspends, so
  esp-hosted's host-sleep wake (a GPIO interrupt node, the C6's
  `HOST_WAKEUP_GPIO` 4) is not set up.
- **Not tried on a printer.** The trigger path (M331/M118 over the metrics
  stream, the buffer padding, the on-screen M334 prompt) is read from the
  Buddy source, not watched on a CORE One. The datagrams and PrusaLink
  answers in the tests are built from the source's formats, not captured.
- **Video size per frame is an estimate** (20-60 kB): measure it, and the
  rootfs size, before trusting the 90/130 MB userdata/rootfs split (kept
  until measured).
- **The heat measures are not measured.** How long rkaiq needs to settle
  after a wake (`camera.wake_ms`, 1 s) and after the IR LEDs come on
  (`ir.flash_settle_ms`, 500 ms), what 10 fps saves over 30, whether the
  sensor really sits in standby with its stream off, and whether the C6
  keeps to the `iw` transmit power cap: all to measure on the board, with
  the SoC temperature read back from the page. v1's housing failed its
  sim/thermal.md 65 C case while streaming; whether the Pro's does is for
  its own `sim/thermal.py`, not the firmware.
- **device.type is reported as `Buddy3D`**: the Camera Service accepts only
  Buddy3D, ESP32, WEB, LINK or INTERNAL and none is exactly this board;
  manufacturer and model say OffGrid LayerCam. Whether Connect treats a
  Buddy3D camera differently (firmware offers, the camera protocol) is
  not documented; change it in `layercam/connect.py` if it does.
- **Snapshots and video share one size** (one VI channel, to keep the ISP
  idle): 1920 x 1080 by default, or both at the full 2560 x 1440 (H.264
  level 5.0 or higher; JPEG quality lowered as needed for Connect's 1 MB).
- **Night pictures are grey** (ISP grey mode under IR), as any IR camera.
- **The setup passphrase is derived, not random**: anyone who knows the
  SoC's serial number (on the consoles, in the USB serial number) and this
  code can work it out. The access point is on only with no network saved
  or while the saved one is unreachable (a-c above); set `web.password`
  once the camera is on your network.
- **The no-button parts have run on a PC only.** Still to see on the
  board: how long the boot takes to the gesture's flashes (the 5 s window
  starts there); the configfs gadget enumerating on Linux, macOS and
  Windows (the composite class codes are there for Windows' usbser), and
  staying quiet on the printer's port; `reboot-loader` (ctypes `reboot(2)`
  with "loader") landing in U-Boot's Rockusb; `rkflash.sh rootfs/oem/boot`
  in that mode; the update's import check and trial start on the board's
  Python; hostapd's control socket listing the access point's stations;
  sshd turned on and off from the console.
- **One radio for two jobs**: while the saved network is unreachable the
  access point and the retries take turns (the access point is off for up
  to 45 s every 2 minutes, never while a phone is on it). Whether
  esp-hosted can do both at once is not tried.
- **The USB id 1d6b:0104 is a placeholder and needs a real ID before
  selling.** It is the Linux Foundation's id for a multifunction composite
  gadget, fine for development. Set the product's own vendor:product id at
  build time: `USB_ID=vvvv:pppp board/install-into-sdk.sh ...` (written to
  `/etc/layercam/usb-id`, read by `S50usbdevice`; the script warns while
  the placeholder is used).
- **The page is plain HTTP** on the home network: `web.password` and the
  settings cross it unencrypted (Basic authentication), as with most
  printers' own pages.
- **Updates over the air are the camera software only**; the kernel,
  rootfs and C helper come with a full image over USB (*Updates*). No A/B
  system, no recovery partition (no room in 256 MB).
- **The clock comes from NTP after Wi-Fi is up** (the RTC has no battery);
  until then TLS to Connect and S3 signatures fail and are retried.
- **Z fallback frames show the head** wherever it is; only the slicer
  snippet gives clean frames. Vase mode (continuous Z) gives few frames.
- **WPA2-Personal only, 2.4 GHz only** (the C6's one band; `wifi.band`
  stays from v1 and changes nothing); no WPA3-only networks, no enterprise
  Wi-Fi. No IPv6 shown to Connect.
- **No Bluetooth** on the board; the kernel's Bluetooth core is there only
  for `esp32_sdio.ko`.

## Files

```
README.md                  this file
layercam/                  the service (Python, standard library only)
  service.py                 threads and glue        config.py     settings, validation
  connect.py                 Prusa Connect           prusalink.py  printer status, Digest auth
  metrics.py                 printer's UDP metrics   timelapse.py  when to shoot (pure logic)
  capture.py                 camera backends         recording.py  frames on disk, video bodies
  mp4.py                     H.264 -> MP4, streamed  upload.py     S3, HTTP, SMB, NFS
  sigv4.py                   AWS SigV4               hw.py         light, IR, LED, BOOT pad
  net.py                     Wi-Fi files, setup AP,  web.py        setup page, live view,
                             when to open it                       update upload
  thermal.py                 heat governor, policy   board.py      pins (from circuit.py)
  gesture.py                 power-cycle gesture     setupcli.py   layercam-setup (USB console)
  update.py                  signed app updates,     ed25519.py    signatures (RFC 8032)
                             trial, rollback
pincheck.py                pins against src/circuit.py (tests and the board build: src/check_firmware.py)
tools/layercam-ap.py       prints a camera's setup access point name and passphrase (serial or USB console)
tools/layercam-sign.py     update signing key; makes and checks .lcup packages
tools/layercam-c6-flash.py flashes the ESP32-C6 from the camera (UART1, GPIO9 strap, EN); /usr/bin/layercam-c6-flash
tools/sc4336h-port.py      makes the SC4336H driver from the SDK's sc4336.c (install-into-sdk.sh runs it)
native/                    layercam-media (C): sensor, ISP, JPEG and H.264 encoders; Makefile
dts/                       the board's device tree (rv1106g-layercam-pro-v1.dts)
board/
  layercam.ini.example     every setting with its default
  install-into-sdk.sh      copies all of this into a Luckfox SDK checkout
  sdk/                     board config, kernel options, Buildroot packages
  rootfs/                  /etc/init.d/: S21-layercam-gesture, S21appinit (drivers only),
                           S50usbdevice (USB console), S50sshd (off unless turned on),
                           S41dhcpcd, S49ntp, S50telnet, S99usb0config (empty), S99layercam;
                           /etc/shadow (root locked), /etc/ssh/sshd_config (keys only);
                           /usr/bin/: layercam-net, layercam-setup, adbd (stub);
                           /etc/layercam/: update-keys, rootfs-version, usb-id
slicer/                    PrusaSlicer custom G-code and how it works
tests/                     host tests (python3 -m unittest), test data, a stand-in helper
```
