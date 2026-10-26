# LayerCam v1 — camera software

**What the camera does once it is in the printer.** It sends a picture to
Prusa Connect every 10-60 seconds, so the Prusa app shows the print. During
a print it takes one frame per layer, with the head parked out of the way,
makes them into an MP4 video named after the print, and uploads the video
to S3 (or MinIO, Backblaze B2, a NAS), a WebDAV/HTTP folder, an SMB share or
an NFS export. It switches to infrared at night, and is set up from a phone.

> **Status: written, tested on a PC, not yet run on the board.** No board
> exists yet. The Python service passes its 130 host tests, including a
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
| First-boot Wi-Fi setup, one settings file, button, status LED | ✅ setup access point and page; `layercam.ini`; long press = forget Wi-Fi; LED patterns below |
| Runs on the Luckfox SDK's Buildroot | ✅ Python 3.8+ standard library only (Buildroot's `python3` is already in `luckfox_pico_defconfig`), one small C helper |

## What runs where

```
 PrusaSlicer snippet ──► CORE One (Buddy firmware)
                          │  UDP 8514: metrics stream, "M118 OGCAM:LAYER:n"
                          │  HTTP: PrusaLink /api/v1/status, /api/v1/job
                          ▼
 LayerCam (RV1106, Linux)
   S99layercam ─► python3 -m layercam        (the service, layercam/)
                    ├─ metrics listener      triggers from the printer
                    ├─ PrusaLink poller      job name, start/finish/cancel, Z
                    ├─ timelapse logic       when to start, shoot, finish
                    ├─ Connect sender        snapshots to Prusa Connect
                    ├─ uploader              finished videos
                    ├─ panel                 button, light sensor, IR, LED
                    ├─ web                   setup page, live picture
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
   board/install-into-sdk.sh ~/luckfox-pico native/layercam-media
   ```
   This copies the device tree, the kernel option fragment and the board
   config, adds two packages to `luckfox_pico_defconfig`, and makes the
   overlay `overlay-layercam` (the init script, the network script, the
   Python package in `/usr/share/layercam`, the helper in `/usr/bin`).
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
SARADC, gpio-leds, PWM, tmpfs and NFS are already in the defconfig.

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
| button | SARADC_IN0 | `&saradc` (1.8 V reference); the evb's `adc-keys` node removed |
| light sensor | SARADC_IN1 | `&saradc` |
| status LED | GPIO1_C0 | `gpio-leds`, `/sys/class/leds/status` |
| Wi-Fi SDIO, 3.3 V | SDMMC0 | `&sdmmc`, `no-1-8-v`, `non-removable`, `mmc-pwrseq` |
| WL_REG_ON | GPIO1_A2 | `sdio-pwrseq` `reset-gpios`, active low (as the Ultra W) |
| WL_HOST_WAKE | GPIO0_A3 | `wlan-platdata` `WIFI,host_wake_irq` (bcmdhd is built out-of-band) |
| 32.768 kHz sleep clock | | the board's own oscillator, always on: nothing in the tree |
| Bluetooth (wired, unused) | UART1_M0 + GPIO0_A1/A2/A4 | `wireless-bluetooth`, disabled |
| console | UART2_M1, 115200 | `fiq_debugger` (rv1106.dtsi default) |
| not fitted | | `gmac`, `i2s0_8ch`, `acodec` disabled (`acodec`'s amplifier GPIO on the Pro Max is our IRCUT_B) |

## Flashing (USB-C, MaskROM)

1. Hold the side button, plug the camera into the computer with USB-C,
   release. The button pulls SARADC_IN0 low while the SoC starts, which
   puts it in MaskROM mode (`src/circuit.py`).
2. In the SDK: `./rkflash.sh update` (it runs Rockchip's
   `tools/linux/Linux_Upgrade_Tool/upgrade_tool uf output/image/update.img`).
   On Windows, use the flashing tool Luckfox's documentation gives for the
   Pico boards with the same file (not checked here).
3. The kernel console is on test pads TP1 (TX), TP2 (RX), TP3 (ground),
   115200 baud, 3.3 V.

## Setting it up

1. **Read the camera's setup passphrase first.** Every camera has its
   own access point name and passphrase, made from its SoC's serial number
   (the RV1106's one-time-programmable id, which the kernel shows as
   `Serial` in `/proc/cpuinfo`). Either:
   - plug the camera into a computer by USB-C (it boots from the port) and
     run `python3 tools/layercam-ap.py`, which reads the serial over adb and
     prints the name and passphrase (`python3 tools/layercam-ap.py SERIAL`
     does the same from a serial number you already have, for a label); or
   - watch the serial console (TP1/TP2, 115200): the camera prints
     `LayerCam setup: Wi-Fi LayerCam-XXXX, passphrase xxxx-xxxx-xxxx` each
     time the access point opens.

   A camera whose SoC shows no serial falls back to its random
   fingerprint, and then only the console shows the passphrase.
   `wifi.ap_password` replaces it with your own.
2. **First boot:** with no Wi-Fi configured the camera opens the setup
   access point **LayerCam-XXXX** and the status LED blinks slowly. Join
   it with a phone and open `http://192.168.4.1` (any web name resolves to
   the camera there, so most phones offer the page by themselves).
3. On the page, fill in at least:
   - **wifi**: your network and password (WPA2; empty for an open network).
   - **connect.token**: in Prusa Connect, open the printer, *Camera* > *Add
     new camera* > *other camera*, copy the token. **Use it within 15
     minutes** or Connect forgets the camera; the camera's first call binds
     its fingerprint to the token for good.
   - **prusalink**: the printer's address and its PrusaLink password (on
     the printer: Settings > Network > PrusaLink).
   - **upload**: a target, or `none` to keep the videos on the camera
     (download them from the page).
   - **web.password**: without it anyone on your network can open the page.
4. Save. The camera joins your network, and its address appears in Prusa
   Connect (camera info) and on the router. Put that address in the slicer
   snippet's `start.gcode` ([`slicer/README.md`](slicer/README.md)).
5. Every setting is in one file, `/userdata/layercam/layercam.ini`;
   [`board/layercam.ini.example`](board/layercam.ini.example) lists them
   all with their defaults and what they do. It can be copied there over
   USB instead of using the page.

**Upload targets:** `s3` signs requests with SigV4 (keys need `PutObject`
on the bucket; `s3_addressing = path` for MinIO and NAS stores); `http`
PUTs into a folder URL (WebDAV works; Basic authentication); `smb` mounts
`//server/share` with the kernel's CIFS client (password passed in a
0600 file, not on the command line), writes `name.part`, renames it, and
unmounts; `nfs` mounts `server:/path` the same way (`nolock`). A failed
upload is retried after 10 s, 1, 5, 15 and 60 minutes, and the video stays
on the camera if all fail. The camera keeps the last `keep_local` uploaded
videos.

### Button and status LED

| Button | Does |
|---|---|
| held at power-up | MaskROM (flashing), in the SoC's boot ROM |
| short press | send a snapshot to Connect now |
| held 5 s | forget Wi-Fi and open the setup access point |

| LED | Means |
|---|---|
| steady on | on the network, idle |
| double blink | recording a timelapse |
| fast blink | joining Wi-Fi |
| slow blink (1 s) | setup access point is on (closes after 30 minutes if Wi-Fi is set) |
| three blinks, pause | something needs attention: see the setup page (Connect refused the token, PrusaLink unreachable, a frame lost, storage low) |
| long on, short off | hot: the thermal governor is throttling or has stopped the camera (the page says how hot) |

**Night:** below 0.10 V on the light sensor for 5 s (around 10 lux; about
0.5 V is 50 lux) the IR-cut filter opens and the picture turns grey; above
0.25 V for 5 s it switches back. Between the two nothing changes, so a
flicker or a passing hand does not toggle it. At night each picture lights
the IR LEDs briefly (ramped up, 500 ms for the exposure, the frame, ramped
down), and live view keeps them on while it runs; `ir.mode = printing`
does this only during prints.

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
python3 -m unittest            # from this folder; 130 tests, about 7 s
```

| File | What it checks |
|---|---|
| `test_connect.py` | snapshot and camera-info requests: URL, headers (Token, Fingerprint, User-Agent, Content-Type, Content-Length), 1 MB limit, token and fingerprint lengths, only documented camera-info keys; rate limit (10 s, back-off after 429/503), stop after 401/403/422, quality lowered for size, a button press never beats the 10 s minimum |
| `test_prusalink.py` | Digest auth against a fake printer that checks it as Buddy does (no qop, stale nonce), RFC 2617's own example, API key, unreachable printer; status/job parsing for printing, finished, stopped, idle, no job (204); video names |
| `test_metrics.py` | line protocol (floats, integers, strings with spaces and escapes, events, tags, errors), Buddy's syslog header, trigger age from the datagram's timestamps, MeatPack-style missing space, a real UDP socket |
| `test_timelapse.py` | start/layer/finish/cancel, duplicate and out-of-order triggers, missed triggers counted, late triggers warned, trigger before PrusaLink sees the job, a new job without an end, pause, the Z fallback (Z hops filtered), UDP-only and poll-only modes, thinning, no-PrusaLink timeout |
| `test_sigv4.py` | AWS's SigV4 test suite (23 cases: canonical request, string to sign, Authorization header) and three S3 PUTs signed by botocore |
| `test_upload.py` | S3 path and virtual-host addressing, what the server receives is what was signed, no chunked encoding; HTTP PUT; SMB and NFS mount commands, credentials file mode and clean-up, mount failure; retries |
| `test_mp4.py` | SPS parsing (hand-built SPS, with cropping), NAL splitting, and MP4s at 2304 x 1296 and 320 x 180 checked by ffprobe and decoded by ffmpeg, including a frame cut off by a power loss |
| `test_recording.py` | the C helper's protocol against a stand-in (asleep until woken, rate changes), a whole H.264 timelapse to MP4, the helper crashing mid-print, JPEG frames with thinning, ffmpeg and hardware-encoder paths, pruning (unsent videos never deleted) |
| `test_service.py` | the whole service: fake printer, five layers (one sent twice), print finishes, the MP4 arrives at the upload server with five frames, named after the job; the page's password and hidden secrets; a missing camera helper does not stop the service |
| `test_config.py` | types, validation of every rule, the example file lists exactly the real settings, file written 0600, typos rejected, secrets never sent back, the page form |
| `test_hw.py` | day/night hysteresis and hold time, flicker, IR plan per mode, button short/long, LED priorities, sysfs writes (ADC, IR-cut pulse order, PWM) against a fake `/sys` |
| `test_net.py` | WPA PSK against the IEEE 802.11i test vector, wpa_supplicant/hostapd/dnsmasq files, 2.4 GHz channel list, power settings; the setup access point's name and passphrase per device (stable, different per serial, readable alphabet), `/proc/cpuinfo` serial parsing, the host tool |
| `test_pins.py` | `pincheck.py`: `layercam/board.py` and the device tree against `src/circuit.py` (30 checks); proved to catch a moved LED, a wrong PWM pin and a swapped IR-cut pin; `src/check_firmware.run()` as the board build calls it |
| `test_thermal.py` | the governor's levels, hysteresis, jumps and unreadable sensor; what each level allows; IR LED duty capping and the ramp's steps; the camera power policy; temperature and CPU speed through a fake `/sys`; the service under heat: asleep between pictures, live view time-limited and refused when hot, quality capped, Connect skipped from 105 C, frames lost only at 115 C and the camera back under 95 C, LEDs lit only around a night picture and capped at 50 % when throttled, IR-cut pulsed once |
| `test_slicer.py` | the snippets use only G-codes checked in Buddy's source, the park position (PrusaSlicer local variables) inside the CORE One's limits, lines under 96 characters, hold = `dwell_ms`, metric on only around the trigger, and an emulation of Buddy's metrics buffer showing the padding sends the trigger at once |

The MP4, recording and whole-service tests need `ffmpeg` and `ffprobe`
with libx264 on the PC (they make the test video); without them they are
skipped. Result on 26 Oct 2026, Python 3.13 and 3.11: **130 pass, 0 skipped**.

Checked on a PC but not as tests: the device tree, run through `cpp` with
the SDK's includes and parsed with Zephyr's `dtlib` (every label and
reference resolves; the LED, Wi-Fi and sensor GPIO cells are the right
pins); the C helper, `gcc -fsyntax-only -Wall -Wextra` against
luckfox_pico_rkmpi_example's headers and the SDK's libjpeg9 headers, with
and without `HAVE_LIBJPEG` (`make check`); the shell scripts, `sh -n`.

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
  SoC's serial number (on the console, over adb on the USB-C cable) and
  this code can work it out. The access point is only on at first boot or
  after a 5-second press; set `web.password` once the camera is on your
  network. adb over the USB-C port is what the Luckfox image offers;
  not checked on this board.
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
  sigv4.py                   AWS SigV4               hw.py         button, light, IR, LED
  net.py                     Wi-Fi files, setup AP   web.py        setup page, live view
  thermal.py                 heat governor, policy   board.py      pins (from circuit.py)
pincheck.py                pins against src/circuit.py (tests and the board build: src/check_firmware.py)
tools/layercam-ap.py       prints a camera's setup access point name and passphrase
native/                    layercam-media (C): sensor, ISP, JPEG and H.264 encoders; Makefile
dts/                       the board's device tree
board/
  layercam.ini.example     every setting with its default
  install-into-sdk.sh      copies all of this into a Luckfox SDK checkout
  sdk/                     board config, kernel options, Buildroot packages
  rootfs/                  /etc/init.d/S99layercam, /usr/bin/layercam-net
slicer/                    PrusaSlicer custom G-code and how it works
tests/                     host tests (python3 -m unittest), test data, a stand-in helper
```
