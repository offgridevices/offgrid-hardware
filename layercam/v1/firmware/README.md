# LayerCam v1 — camera software

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
> exists yet. The Python service passes its 180 host tests, including a
> whole print from PrusaLink and layer triggers to an uploaded MP4 (against
> fakes). The C camera helper, the device tree, the SDK board config and the
> init scripts have been checked as far as a PC can (the C against the real
> rkmpi/rkaiq headers, the device tree parsed with Luckfox's includes) but
> never built for or run on an RV1106. See *Limits*.

## Requirements

As the owner set them, and where v1 stands. ✅ here means written and
tested on a PC; none of it has run on the board yet.

| Requirement | v1 |
|---|---|
| Snapshots in Prusa Connect / the Prusa app | ✅ Prusa's current Camera Service API (`camera-service.prusa3d.com`), every 10, 30 or 60 s; the layer frames (head parked) go to Connect too; under 1 MB and at most 6 a minute, as the service requires |
| Per-layer timelapse, frame taken with the head parked | ✅ PrusaSlicer snippet ([`slicer/`](slicer/README.md)) parks the head and sends a trigger over the printer's metrics stream; the camera shoots during a 1.2 s hold |
| Know the print: name, start, finish, cancel; fallback trigger | ✅ PrusaLink `/api/v1/status` and `/api/v1/job` (Digest auth, user `maker`); without the snippet, frames on Z changes (head not parked) |
| MP4 (H.264), hardware encoder, little storage | ✅ each frame encoded by the RV1106's encoder as it is taken and appended to one H.264 file; MP4 made on the fly at upload; ffmpeg path for a PC |
| Upload to SMB, NFS, S3 (+ compatible), HTTP/WebDAV | ✅ all five; S3 signing (SigV4) in plain Python, tested against AWS's test suite |
| Live picture for setup; day/night with IR | ✅ live view on request (2 minutes, refused when hot); IR-cut from the light sensor with hysteresis, IR LEDs lit only around each night picture |
| Works in a 65 C chamber | ⚠️ the firmware does all it can (below: sensor asleep between pictures, 1080p, lowest CPU speed, Wi-Fi power save on 2.4 GHz, IR LEDs flashed, a thermal governor that throttles, skips uploads, then stops the camera); sim/thermal.md shows the sealed housing still runs hot while streaming, so the hardware has to change too |
| 1080p timelapse | ✅ 1920 x 1080 by default (`timelapse.resolution`), the full 2304 x 1296 sensor selectable |
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
                    ├─ Wi-Fi                 the network, or the setup access point
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

sim/thermal.md: streaming 3 MP at 30 fps all the time puts the RV1106 at
about 126 C in the sealed housing in a 65 C chamber (limit 125 C), with
most other parts past their 85 C. So the camera does as little as it can
(`layercam/thermal.py`):

| | What the camera does | Why |
|---|---|---|
| no print | sensor and ISP **asleep** (VI channel stopped, the sensor driver puts the SC3336 in standby); woken for each Connect snapshot with `camera.wake_ms` (1 s) for the exposure, then asleep again | a picture every 10-60 s needs the sensor about 5 % of the time |
| printing | sensor streaming at **10 fps** (`camera.print_fps`), not 30 | a layer trigger must be answered inside the 1.2 s hold, and rkaiq's auto exposure and white balance need frames to settle after a cold start (some hundreds of ms to a second: to measure on the board); at 10 fps a fresh frame is at most 0.3 s away |
| video size | 1920 x 1080 (the ISP scales the 2304 x 1296 sensor; same 16:9) | fewer pixels through the ISP, encoder and DDR |
| CPU | held at its lowest speed (`scaling_max_freq`) except while uploading (TLS, SHA-256) | the encoders are hardware; the CPU has little to do |
| Wi-Fi | 2.4 GHz only (`wifi.band`), power save on, transmit power capped at 10 dBm (`iw`) | the AP6256 is the second-largest heat source (sim/thermal.md) |
| IR LEDs | lit only around a night picture (ramped over 150 ms, `ir.flash_settle_ms` 500 ms before the frame) and during live view; never continuously | lit continuously the ring is the hottest part at night (sim/thermal.md) |
| IR-cut | the coil is pulsed only when day/night changes | |
| live view | only when asked for (setup page button, `POST /api/live`), at most `camera.live_max_s` (120 s), refused or stopped from 90 C | streaming 10 fps JPEG is the heaviest thing the camera can do |

The **thermal governor** reads the SoC's own sensor (TSADC,
`/sys/class/thermal/thermal_zone0/temp`) once a second:

| SoC | Level | Effect |
|---|---|---|
| under 90 C | normal | as above |
| from 90 C | throttle | frame rate 5 fps, JPEG quality at most 70, IR LED duty at most 50 %, no live view, CPU never boosted |
| from 105 C | hot | as throttle, and **no Connect uploads**; timelapse frames continue (the print only happens once) |
| from 115 C | stop | camera pipeline stopped, IR LEDs off, frames lost (counted on the page) |
| back under 95 C | | from stop to the level the temperature calls for |

Every level is left 5 K under where it was entered (`thermal.hysteresis_k`),
so it does not flap. The level and the temperature are on the setup page,
the change is logged, and the status LED shows *hot* (long on, short off)
at any level above normal. All thresholds are settings (`[thermal]`).
These numbers follow sim/thermal.md and sim/power.md; measure the board in
a 65 C oven before trusting either.

**Storage.** There is no SD card: 256 MB of SPI NAND for everything. A
JPEG per layer at 2304 x 1296 is 300-500 kB, so a 1000-layer print would
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
(Buildroot 2023.02.6, kernel 5.10, rockit/rkaiq media stack), the same SDK
as the Luckfox Pico Pro/Max, which uses the same RV1106G3, SPI NAND and
SC3336 camera. Checked against SDK commit `824b817f` (22 Mar 2026).

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
3. **Copy LayerCam's files into the SDK:**
   ```
   UPDATE_PUBKEY=update.pub USB_ID=vvvv:pppp board/install-into-sdk.sh ~/luckfox-pico native/layercam-media
   ```
   This copies the device tree, the kernel option fragment and the board
   config, appends `board/sdk/buildroot.fragment` to `luckfox_pico_defconfig`
   (three packages; root login off, dhcpcd out: *Security*), and makes the
   overlay `overlay-layercam`, the only one besides Luckfox's Wi-Fi
   firmware: the init scripts (`S21-layercam-gesture`, `S50usbdevice`,
   `S50sshd`, `S21appinit`, `S99layercam` and the empty ones),
   `/etc/shadow` and `/etc/ssh/sshd_config`, `layercam-net` and
   `layercam-setup`, the Python package in `/usr/share/layercam`, the
   helper in `/usr/bin`, and `/etc/layercam/` (the update key,
   `rootfs-version`, `usb-id`). `update.pub` is the public half of the key
   that signs app updates (*Updates*); without it the cameras refuse every
   update. `USB_ID` is the product's USB vendor:product id; without it the
   development placeholder 1d6b:0104 is used (*Limits*).
4. **Build:** `./build.sh lunch` (choose `RV1106_LayerCam_v1`), then `./build.sh`.
   The image is `output/image/update.img`.

What the board config changes from Luckfox's Pro Max SPI NAND config
(`board/sdk/BoardConfig-SPI_NAND-Buildroot-RV1106_LayerCam_v1-IPC.mk`, each
change marked):

| Setting | Pro Max | LayerCam |
|---|---|---|
| `RK_KERNEL_DTS` | `rv1106g-luckfox-pico-pro-max.dts` | `rv1106g-layercam-v1.dts` |
| partitions | userdata 10M, rootfs 210M | userdata 90M (timelapses), rootfs 130M |
| `RK_KERNEL_DEFCONFIG_FRAGMENT` | none | `layercam.config` |
| `RK_ENABLE_WIFI_CHIP` | none | `AP6XXX` (AP6256: `fw_bcm43456c5_ag.bin`, `nvram_ap6256.txt`) |
| `RK_CAMERA_SENSOR_IQFILES` | three sensors | `sc3336_CMK-OT2119-PC1_30IRC-F16.json` |
| `RK_APP_TYPE` | `RKIPC_RV1106` | not set (our service owns the camera) |

Starting points: Buildroot `luckfox_pico_defconfig`, kernel
`luckfox_rv1106_linux_defconfig`, U-Boot `luckfox_rv1106_uboot_defconfig`.

**Buildroot packages** (`board/sdk/buildroot.fragment`): `python3`,
`python3-ssl`, `ca-certificates` and `ntp` are already in
`luckfox_pico_defconfig`; added are `BR2_PACKAGE_CIFS_UTILS` (mount.cifs,
SMB upload), `BR2_PACKAGE_NFS_UTILS` (mount.nfs, NFS upload) and
`BR2_PACKAGE_IW` (Wi-Fi power save and transmit power).
`BR2_PACKAGE_FFMPEG` is optional (only for `camera.backend = command`).

**Kernel options** (`board/sdk/layercam.config`): `CONFIG_WIRELESS`,
`CONFIG_CFG80211` (the SDK's bcmdhd builds its cfg80211 interface only with
it), `CONFIG_RFKILL` and `CONFIG_RFKILL_RK` (Rockchip's `wlan-platdata`
driver, which hands bcmdhd its GPIOs), `CONFIG_CIFS`. GPIO sysfs, the
SARADC, gpio-leds, PWM, tmpfs and NFS are already in the defconfig, and so
is what the no-button parts need: the USB gadget with configfs and its
CDC-ACM function (`CONFIG_USB_GADGET`, `CONFIG_USB_CONFIGFS`,
`CONFIG_USB_CONFIGFS_ACM`) for the USB console, and
`CONFIG_SYSCON_REBOOT_MODE` (rv1106.dtsi's `reboot-mode` node has
`mode-loader`) for `reboot-loader`.

### The device tree

[`dts/rv1106g-layercam-v1.dts`](dts/rv1106g-layercam-v1.dts): Luckfox's
`rv1106.dtsi` + `rv1106-evb.dtsi` like their boards, the camera and flash
as the Pro Max, the SDIO Wi-Fi as the Pico Ultra W. Every pin is the one
`src/circuit.py` gives (`tests/test_pins.py` checks it):

| Function | Pin | Device tree |
|---|---|---|
| SC3336 camera, 2-lane MIPI | CSI D0/D1/CK | `csi2_dphy0` → `mipi0_csi2` → `rkcif` → `rkisp` (as the Pro Max) |
| camera I2C | I2C4_M2 | `&i2c4`, `i2c4m2_xfer`, 400 kHz, sensor at 0x30 |
| camera clock, 24 MHz | GPIO3_C4 (MIPI_CLK0_OUT) | `mipi_refclk_out0`, `MCLK_REF_MIPI0` |
| camera power-down/reset | GPIO3_C5 | `pwdn-gpios` (as the Pro Max) |
| IQ file | | module `CMK-OT2119-PC1`, lens `30IRC-F16` |
| IR-cut H-bridge IN1 / IN2 | GPIO1_A0 / GPIO1_A1 | plain GPIOs, held low with pull-downs (pinctrl hog) |
| IR LED switch | PWM3_IR_M1 (GPIO1_B0) | `&pwm3` on `pwm3m1_pins` (its default `pwm3m0` would take BT_WAKE) |
| BOOT pad TP5 (MaskROM strap; no button) | SARADC_IN0 | `&saradc` (1.8 V reference): read only to warn if it leaks towards ground (`hw.boot_pad_problem`); the evb's `adc-keys` node removed, it would poll this pin as volume keys |
| light sensor | SARADC_IN1 | `&saradc` |
| status LED | GPIO1_C0 | `gpio-leds`, `/sys/class/leds/status` |
| Wi-Fi SDIO, 3.3 V | SDMMC0 | `&sdmmc`, `no-1-8-v`, `non-removable`, `mmc-pwrseq` |
| WL_REG_ON | GPIO1_A2 | `sdio-pwrseq` `reset-gpios`, active low (as the Ultra W) |
| WL_HOST_WAKE | GPIO0_A3 | `wlan-platdata` `WIFI,host_wake_irq` (bcmdhd is built out-of-band) |
| 32.768 kHz sleep clock | | the board's own oscillator, always on: nothing in the tree |
| Bluetooth (wired, unused) | UART1_M0 + GPIO0_A1/A2/A4 | `wireless-bluetooth`, disabled |
| console | UART2_M1, 115200 | `fiq_debugger` (rv1106.dtsi default) |
| USB-C, USB 2.0 | OTG controller | `&usbdrd_dwc3` `dr_mode = "peripheral"`: the board is a USB device only (Rd on CC, no VBUS switch, no ID pin), which `otg` would have to guess; the setup console is a configfs gadget on it; MaskROM and the U-Boot loader flash over the same port without Linux |
| not fitted | | `gmac`, `i2s0_8ch`, `acodec` disabled (`acodec`'s amplifier GPIO on the Pro Max is our IRCUT_B) |

## Flashing a new board (BOOT pads, MaskROM)

The test pads sit in a row on the board's round edge: **TP4** 5 V, **TP1**
console TX, **TP2** console RX, **TP3** ground, **TP5** BOOT. BOOT is the
SoC's MaskROM strap (SARADC_IN0, 10k up to 1.8 V, 1 nF, 100R to the pad),
so shorting it to ground is harmless.

1. Bridge **TP5 BOOT** and **TP3 G** with tweezers, plug the USB-C into the
   computer, keep the bridge for a second, then lift it. The boot ROM
   finds BOOT low and waits for flashing over USB (`upgrade_tool ld`, or
   `lsusb`, shows a Rockchip device in *Maskrom*). Only a blank board, or
   one whose loader is broken, needs this.
2. In the SDK: `./rkflash.sh update` (`upgrade_tool uf output/image/update.img`):
   the loader, the partition table and every partition, `/userdata` empty.
   On Windows, the flashing tool Luckfox's documentation gives for the
   Pico boards with the same file (not checked here).
3. It starts by itself: the status LED blinks slowly (setup access point),
   the computer finds a USB serial port (the setup console), and the kernel
   console is on TP1 (TX), TP2 (RX), TP3 (ground), 115200 baud, 3.3 V,
   where the camera also prints its access point name and passphrase.

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
`LayerCam v1`; newer than what runs (an older signed version could bring
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
bring back after a power cut, so v1 updates the software over the air and
the image over USB.

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
python3 -m unittest            # from this folder; 192 tests, about 10 s
```

| File | What it checks |
|---|---|
| `test_connect.py` | snapshot and camera-info requests: URL, headers (Token, Fingerprint, User-Agent, Content-Type, Content-Length), 1 MB limit, token and fingerprint lengths, only documented camera-info keys; rate limit (10 s, back-off after 429/503), stop after 401/403/422, quality lowered for size, a test from the page never beats the 10 s minimum |
| `test_prusalink.py` | Digest auth against a fake printer that checks it as Buddy does (no qop, stale nonce), RFC 2617's own example, API key, unreachable printer; status/job parsing for printing, finished, stopped, idle, no job (204); video names |
| `test_metrics.py` | line protocol (floats, integers, strings with spaces and escapes, events, tags, errors), Buddy's syslog header, trigger age from the datagram's timestamps, MeatPack-style missing space, a real UDP socket |
| `test_timelapse.py` | start/layer/finish/cancel, duplicate and out-of-order triggers, missed triggers counted, late triggers warned, trigger before PrusaLink sees the job, a new job without an end, pause, the Z fallback (Z hops filtered), UDP-only and poll-only modes, thinning, no-PrusaLink timeout |
| `test_sigv4.py` | AWS's SigV4 test suite (23 cases: canonical request, string to sign, Authorization header) and three S3 PUTs signed by botocore |
| `test_upload.py` | S3 path and virtual-host addressing, what the server receives is what was signed, no chunked encoding; HTTP PUT; SMB and NFS mount commands, credentials file mode and clean-up, mount failure; retries |
| `test_mp4.py` | SPS parsing (hand-built SPS, with cropping), NAL splitting, and MP4s at 2304 x 1296 and 320 x 180 checked by ffprobe and decoded by ffmpeg, including a frame cut off by a power loss |
| `test_recording.py` | the C helper's protocol against a stand-in (asleep until woken, rate changes), a whole H.264 timelapse to MP4, the helper crashing mid-print, JPEG frames with thinning, ffmpeg and hardware-encoder paths, pruning (unsent videos never deleted) |
| `test_service.py` | the whole service: fake printer, five layers (one sent twice), print finishes, the MP4 arrives at the upload server with five frames, named after the job; the page's password and hidden secrets; a missing camera helper does not stop the service |
| `test_config.py` | types, validation of every rule, the example file lists exactly the real settings, file written 0600, typos rejected, secrets never sent back, the page form; the service's lenient load: a bad value keeps its default, an unknown key (a typo, a newer version's) is kept in the file, a section given twice is read, an unreadable file is moved aside, the page can still save |
| `test_hw.py` | day/night hysteresis and hold time, flicker, IR plan per mode, LED priorities (updating, setup, hot, offline, error, recording, ok; every pattern distinct; no `Button` left), the BOOT pad warning, sysfs writes (ADC, IR-cut pulse order, PWM) against a fake `/sys` |
| `test_gesture.py` | the power-cycle gesture on a fake clock with fake flash that keeps what was written when the plug is pulled: three short power-ups reset (the third at once), ordinary power-ups never add up and write twice each, one long power-up cancels, the 5 s edge, a power-up cut before it is counted; the count file (torn or garbage reads 0), the init script's call, and the service forgetting network, password and own AP passphrase but keeping `web.password` |
| `test_wifi.py` | when the setup access point opens and closes, on a fake clock: first boot, connected, exactly 10 minutes unreachable, retries every 2 minutes for 45 s, connected on a retry (and the full 10 minutes again after), never cut off while a phone is on it, 2 minutes for a network just entered, fallback off; `iw` station count; the service driving a stand-in `layercam-net` |
| `test_setupcli.py` | the USB console: argument parsing (quoted names, `--open`, `--`, refused commands, no shell), each command against a settings file (validated like the page, SIGHUP to the service, the short fallback for a new network, secrets never printed, a forgotten `web.password` set, unknown keys kept, `reset-wifi` as the gesture, `reboot-loader`), the console loop fed line by line, and the real loop on a pseudo-terminal; `ssh on/off/status`: off by default, a pasted key (unquoted too), files 0600 in a 0700 folder, the same key once, sshd restarted and stopped, keys deleted on off; refused: no key, a private key, options such as `command=`, damaged base64, a type that does not match, RSA under 2048 bits; comments cleaned; fingerprints as `ssh-keygen -l` |
| `test_image.py` | `pincheck.image_results`: root locked, no password in `/etc/shadow` or the fragment, Luckfox's shadow/init/config overlays out, sshd keys only and off unless turned on, no ntpd/dhcpcd/telnet/USB network/adb/rkipc, the USB id file; each check shown to fail with Luckfox's version of its file; the board build runs them; `install-into-sdk.sh` on a stand-in SDK (fragment block replaced on a second run and later than Luckfox's lines, USB id and update key written, a bad USB id refused, the placeholder warned about); the page: no password = only the setup access point and the camera itself (403 elsewhere), wrong password = 401 after a second, a network cannot be saved without a password |
| `test_update.py` | Ed25519 against RFC 8032's vectors and OpenSSL; packages: good, wrong key, no keys, same/older version, needs a newer image, wrong product, a changed manifest, payload or extra member, junk, unsafe paths even when signed; the signing tool; the keys file; trial start, kept after it stays up, rollback after 3 failed starts (to the last good version or the factory one), code that does not import never installed, a missing slot, factory reset, the init script's question with a broken state file; an upload to the setup page |
| `test_net.py` | WPA PSK against the IEEE 802.11i test vector, wpa_supplicant/hostapd/dnsmasq files, 2.4 GHz channel list, power settings; the setup access point's name and passphrase per device (stable, different per serial, readable alphabet), `/proc/cpuinfo` serial parsing, the host tool |
| `test_pins.py` | `pincheck.py`: `layercam/board.py` and the device tree against `src/circuit.py` (34 checks: also no button in the circuit, TP5 through 100R to SARADC_IN0, the evb's ADC keys removed, the USB controller a device); proved to catch a moved LED, a wrong PWM pin, a swapped IR-cut pin, a button put back, the ADC keys back and a host-mode USB port; `src/check_firmware.run()` as the board build calls it |
| `test_thermal.py` | the governor's levels, hysteresis, jumps and unreadable sensor; what each level allows; IR LED duty capping and the ramp's steps; the camera power policy; temperature and CPU speed through a fake `/sys`; the service under heat: asleep between pictures, live view time-limited and refused when hot, quality capped, Connect skipped from 105 C, frames lost only at 115 C and the camera back under 95 C, LEDs lit only around a night picture and capped at 50 % when throttled, IR-cut pulsed once |
| `test_slicer.py` | the snippets use only G-codes checked in Buddy's source, the park position (PrusaSlicer local variables) inside the CORE One's limits, lines under 96 characters, hold = `dwell_ms`, metric on only around the trigger, and an emulation of Buddy's metrics buffer showing the padding sends the trigger at once |

The MP4, recording and whole-service tests need `ffmpeg` and `ffprobe`
with libx264 on the PC (they make the test video); without them they are
skipped, and the SSH fingerprint cross-check needs `ssh-keygen`. Result
on 26 Oct 2026, Python 3.13 and 3.11: **191 pass, 1 skipped** (no
`ssh-keygen` on that PC);
pyflakes finds nothing.

Checked on a PC but not as tests: the device tree, run through `cpp` with
the SDK's includes and parsed with Zephyr's `dtlib` (every label and
reference resolves; the LED, Wi-Fi and sensor GPIO cells are the right
pins); the C helper, `gcc -fsyntax-only -Wall -Wextra` against
luckfox_pico_rkmpi_example's headers and the SDK's libjpeg9 headers, with
and without `HAVE_LIBJPEG` (`make check`); the shell scripts, `sh -n`.
After the no-button change the device tree was parsed again the same way:
no `adc-keys` node, `dr_mode = "peripheral"`, the `reboot-mode` node's
`mode-loader` present.

## Facts checked against their sources (26 Oct 2026)

| Fact | Source |
|---|---|
| Connect camera API: `PUT /v1/snapshot` and `PUT /v1/camera-info` on `https://camera-service.prusa3d.com`; `Token` (20 letters/digits), `Fingerprint` (16-64), `User-Agent` required; JPEG ≤ 1 000 000 bytes, `Content-Length` required, 6 uploads a minute; 15-minute registration window; `device.type` one of Buddy3D, ESP32, WEB, LINK, INTERNAL | Prusa Camera Service docs and `openapi.yaml` (camera-service.prusa3d.com/docs/) |
| `connect.prusa3d.com/c/snapshot` and `/c/info` (PUT, same headers, 16 MB) still work but are deprecated | Connect's camera API docs, `connect.prusa3d.com/docs/cameras/openapi/openapi.yaml`; Prusa-Connect-SDK-Printer `prusa/connect/printer/camera.py` (PUT, `Content-Type: image/jpg`) |
| `M334 host port [syslog port]` sets and enables metrics, asks on the screen when the setting changes; `M331`/`M332 <metric>`; `gcode` metric records each executed line; 1 kB buffer, sent when full or after 1 s; line protocol format | Prusa-Firmware-Buddy 6.10.1: `src/marlin_stubs/M330.cpp`, `src/marlin_stubs/gcode.cpp`, `src/common/metric_handlers.cpp`, `src/common/metric.cpp`, `doc/metrics.md` |
| `G90`/`G91` also set E absolute/relative; no `G10`/`G11`/`M240`; `G4 P` in ms; `M118` string argument; 96-character commands; CORE One limits X -2..252, Y -19..221 | Buddy: `lib/Marlin/Marlin/src/gcode/gcode.h`, `gcode.cpp`, `motion/G4.cpp`, `parser.cpp`, `include/marlin/Configuration_COREONE*.h` |
| PrusaLink: Digest, user `maker`, realm `Printer API`, no qop, nonce valid 300 s with `stale`; or `X-Api-Key`; `/api/v1/status` and `/api/v1/job` fields and states; 204 without a job; `axis_x/y` only when not printing | Buddy: `lib/WUI/nhttp/req_parser.cpp`, `status_page.cpp`, `status_renderer.cpp`, `lib/WUI/link_content/basic_gets.cpp`, `prusa_link_api_v1.cpp`, `src/state/printer_state.cpp`; Prusa-Link-Web `spec/openapi.yaml` |
| PrusaSlicer: "After layer change" runs after the travel to the new layer (`layer_num`, `layer_z`, `position` available); CORE One profile retracts on layer change, park X242 Y211 at the end | PrusaSlicer 2.9.6 `src/libslic3r/GCode.cpp`, `resources/profiles/PrusaResearch.ini` |
| SC3336: 2304 x 1296 at 30/25 fps, 2 lanes; `pwdn`/`reset` GPIO names | SDK `drivers/media/i2c/sc3336.c` |
| Pro Max camera/flash tree, Ultra W SDIO Wi-Fi tree, pin groups (`pwm3m1_pins` = GPIO1_B0, `uart1m0_*`, `i2c4m2_xfer`), `wlan-platdata` properties, bcmdhd options (OOB, cfg80211, Rockchip platform) | SDK: `rv1106g-luckfox-pico-pro-max.dts`, `rv1106-luckfox-pico-pro-max-ipc.dtsi`, `rv1106g-luckfox-pico-ultra.dts`, `rv1106-pinctrl.dtsi`, `net/rfkill/rfkill-wlan.c`, `sysdrv/drv_ko/wifi/bcmdhd/Makefile` |
| Board config, partitions, IQ file name, AP6256 firmware files, Buildroot packages, flashing script | SDK: `BoardConfig-SPI_NAND-Buildroot-RV1106_Luckfox_Pico_Pro_Max-IPC.mk`, `project/app/wifi_app/Makefile`, `luckfox_pico_defconfig`, `rkflash.sh` |
| rockit MPI and rkaiq calls (VI, VENC JPEG/H.264 fixed QP, `SetJpegParam`, `setGrayMode`, `setMirrorFlip`, ISP init order) | luckfox_pico_rkmpi_example `include/` and `luckfox_mpi.cc`; SDK `simple_vi_bind_venc_jpeg.c`, `sample_comm_isp.c` |
| SigV4 | AWS SigV4 test suite (from botocore); botocore 1.43.119 `S3SigV4Auth` |
| Sensor frame rate through rkaiq's AE attributes (`stFrmRate.isFpsFix/FpsValue`); stop/prepare/start to sleep and wake the ISP | SDK `sample_comm_isp.c` (`SAMPLE_COMM_ISP_SetFrameRate`), rkaiq `rk_aiq_user_api2_ae.h`, `rk_aiq_user_api2_sysctl.h` |
| SoC serial: `cpuinfo` node reads the OTP `id` cell (`CONFIG_ROCKCHIP_CPUINFO=y`); TSADC thermal zone (`CONFIG_ROCKCHIP_THERMAL=y`); cpufreq with `ondemand` as the default governor | SDK `rv1106.dtsi`, `luckfox_rv1106_linux_defconfig` |
| PrusaSlicer `{local name = value}` variables in custom G-code | PrusaSlicer 2.9.6 `src/libslic3r/PlaceholderParser.cpp` |
| Heat: the housing's temperatures streaming, the IR LED strings' current | `sim/thermal.md`, `sim/power.md` (this revision) |
| USB: the OTG controller's `dr_mode` (`otg` in rv1106.dtsi, `peripheral` on Luckfox's boards); gadget, configfs and CDC-ACM built in; Luckfox's `S50usbdevice` (adb + RNDIS, gadget `rockchip`) and `S99usb0config`, and where they are installed; overlays applied last, with rsync | SDK `rv1106.dtsi`, `rv1106g-luckfox-pico-pro-max.dts`, `luckfox_rv1106_linux_defconfig`, `sysdrv/tools/board/android-tools/S50usbdevice` and `Makefile`, `sysdrv/Makefile`, `project/build.sh` (`post_overlay`) |
| Loader mode: `reboot-mode` with `mode-loader = BOOT_BL_DOWNLOAD`, `CONFIG_SYSCON_REBOOT_MODE=y`; `rkflash.sh` `update` = `upgrade_tool uf` (all partitions, userdata included), `rootfs`/`oem`/`boot` = `upgrade_tool di` one partition; the SDK's recovery and `update_ota.tar` | SDK `rv1106.dtsi`, `luckfox_rv1106_linux_defconfig`, `project/rkflash.sh`, `project/build.sh` (`build_recovery`, `build_ota`), `project/scripts/RkLunch-recovery.sh` |
| Buildroot's python3 always has ctypes (selects libffi); its zlib module is optional and not in `luckfox_pico_defconfig`, so update packages are plain tar | Buildroot 2023.02.6 `package/python3/Config.in` |
| Ed25519 | RFC 8032 (section 6 code, section 7.1 vectors); OpenSSL 3.0 |
| Luckfox overlays: `-buildroot-shadow` (root `$1$` hash of "luckfox", `smb.conf` sharing `/` read-write as root), `-buildroot-init` (`S50sshd` on every boot, `sshd_config` `PermitRootLogin yes`, `S99python` runs `/root/main.py`), `-config` (`luckfox-config load` at boot); `S21appinit` written by build.sh to run `RkLunch.sh` (rkipc, which also loads the drivers with `insmod_ko.sh`); `post_overlay` after the OEM packaging | SDK `project/cfg/BoardConfig_IPC/overlay/`, `project/build.sh` (`__PACKAGE_OEM`, `build_firmware`), rkipc `src/rv1106_ipc/RkLunch.sh` |
| Buildroot services: `S50sshd` (openssh), `S49ntp` (ntp with ntpd, the default), `S41dhcpcd`, `S50telnet` only with BusyBox's standalone telnetd (off in the default BusyBox config); `BR2_TARGET_GENERIC_ROOT_PASSWD` depends on `BR2_TARGET_ENABLE_ROOT_LOGIN`; the ntp package's ntpd takes servers from `/etc/ntp.conf`, `-p` is a pid file, `-g` for the first big step | Buildroot 2023.02.6 `package/openssh`, `package/ntp`, `package/dhcpcd`, `package/busybox/busybox.mk` and `busybox.config`, `system/Config.in`, `package/skeleton-init-common/skeleton-init-common.mk` (root login off: `*` in `/etc/shadow`) |

## Limits

- **Nothing here has run on LayerCam hardware**, and the C helper has not
  been compiled for ARM. Expect bring-up work: the helper's rockit calls,
  the ISP start-up, the bcmdhd firmware path (the SDK installs the AP6256
  files in `/vendor/etc/firmware`; bcmdhd's built-in default is
  `/system/etc/firmware`, so `insmod` may need `firmware_path=` and
  `nvram_path=`), the partition sizes against the real rootfs, and the
  board config's `RK_APP_TYPE` left unset.
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
  sensor really sits in standby with its stream off, and whether bcmdhd
  honours `iw` power save and the transmit power cap: all to measure on
  the board, with the SoC temperature read back from the page. The housing
  still fails sim/thermal.md's 65 C case while streaming; the firmware
  cannot fix that alone.
- **device.type is reported as `Buddy3D`**: the Camera Service accepts only
  Buddy3D, ESP32, WEB, LINK or INTERNAL and none is exactly this board;
  manufacturer and model say OffGrid LayerCam. Whether Connect treats a
  Buddy3D camera differently (firmware offers, the camera protocol) is
  not documented; change it in `layercam/connect.py` if it does.
- **Snapshots and video share one size** (one VI channel, to keep the ISP
  idle): 1920 x 1080 by default, or both at the full 2304 x 1296 (H.264
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
  Python; `iw` listing the access point's stations; sshd turned on and
  off from the console.
- **One radio for two jobs**: while the saved network is unreachable the
  access point and the retries take turns (the access point is off for up
  to 45 s every 2 minutes, never while a phone is on it). bcmdhd may do
  both at once (AP+STA), not tried.
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
- **WPA2-Personal only, 2.4 GHz by default** (`wifi.band = any` allows
  5 GHz); no WPA3-only networks, no enterprise Wi-Fi. No IPv6 shown to
  Connect.
- **Bluetooth is wired but unused.**

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
native/                    layercam-media (C): sensor, ISP, JPEG and H.264 encoders; Makefile
dts/                       the board's device tree
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
