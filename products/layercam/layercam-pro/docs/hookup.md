# LayerCam Pro v1: hookup spec (RV1106G3 + bare SC4336H + ESP32-C6-MINI-1U-H4)

Research notes, 1 Nov 2026. Each value names its source (list at the end, keyed [S#]).
Every value has a confidence mark:

- **[C] confirmed** in a primary source: a maker datasheet, the Rockchip/Luckfox SDK source, Espressif source or docs.
- **[2] secondary**: a third-party summary of a datasheet that could not be read directly, or a sibling part.
- **[?] not confirmed**: a design choice or an inference. Check it before layout.

---

## 0. Findings that change the plan

| # | Finding | Source |
|---|---|---|
| F1 | **v1's Wi-Fi rail is 3.60 V (VWIFI, U4 TLV62569, 100k/20k). That is the ESP32-C6 module's absolute maximum** (VDD33 −0.3..3.6 V abs max; 3.0/3.3/3.6 V recommended). Re-set U4 to 3.25 V with 100k / 22.6k, the same divider as VCC_3V3 and already in the BOM, or run the C6 from VCC_3V3. Peak TX current is 382 mA (802.11b at 20.5 dBm); the supply must deliver ≥ 0.5 A. | [S10] Table 6-1, 6-2, 6-4; circuit.py `main_power()` |
| F2 | **The -1U's antenna socket is not U.FL.** It is the "third generation" connector (Hirose W.FL / I-PEX MHF III / Amphenol AMMC), so a U.FL (MHF I) pigtail will not mate. Buy an MHF III/W.FL to RP-SMA pigtail. The certified antenna is a 2.33 dBi monopole (TFPD08H10060011); a different type or more gain needs more testing. The -1U has **no copper keep-out** ("the latter has no keepout zone"). | [S10] §3.1, §10.2 |
| F3 | **v1 does not use SDMMC1.** Its Wi-Fi is on **SDMMC0**: `&sdmmc` = `mmc@ffaa0000`, pins GPIO3_A1..A7 on VCCIO4. That is the same controller and pins as the Luckfox Pico Ultra W. SDMMC1 (`&sdio`, `mmc@ff9a0000`; M0 on GPIO2_A0..A5, M1 on GPIO1_C0..C5) is unused. Keep SDMMC0 for the C6. | v1 dts; [S5] rv1106.dtsi:1184, 1403; rv1106-pinctrl.dtsi:700-828; rv1106g-luckfox-pico-ultra.dts:80-95 |
| F4 | **esp-hosted-ng is now legacy.** Its successor is **esp-hosted-linux** (Espressif, v1.0.6.0.7, commit 54d5367, 1 Nov 2026): a FullMAC driver giving cfg80211/nl80211 and `wlanX`, with SDIO support for the C6 and host source compatibility for Linux 4.9 to 7.2, so the SDK's 5.10.160 is covered. esp-hosted-fg became esp-hosted-mcu, an RPC API with no cfg80211, so it is the wrong one. | [S13] README.md; [S14] README, supported-hardware.md:99 |
| F5 | **The C6 needs a 1500 ms power-on delay in mmc-pwrseq, not v1's 200 ms.** Espressif's own overlay says "The ESP32-C6 SDIO function is not reliably CMD52-ready with the historical 200 ms EN-release delay … qualified with a 1500 ms power-on settling interval." | [S14] host/overlays/esp32-sdio-pwrseq.dts:24-31 |
| F6 | **The SDK cannot run the SC4336H as-is.** Its `sc4336.c` accepts only chip ID 0xdc42, and `sc4336p.c` only 0x9c42. No SC4336H driver exists in the Luckfox SDK, in Rockchip's develop-5.10 or develop-6.1 kernels, in Ingenic/thingino, or in OpenIPC ipctool's ID table. The Luckfox defconfig does not even build `sc4336` (only `CONFIG_VIDEO_SC3336=m`). | [S5][S6][S7][S8] |
| F7 | **The SC4336 family's MCLK is 24 MHz** (`SC4336_XVCLK_FREQ 24000000`); the SC3336 was 27 MHz. The RV1106's MIPI_REFCLK_OUT0 provides it. | [S5] sc4336.c:46, sc3336.c:47 |
| F8 | **Package size.** The SC4336 and SC4336H are both **5.750 x 3.872 mm** CSP-35. The SC3336 is 6.199 x 4.139 mm. The Pro's `docs/decisions.md` uses the SC3336's 6.2 x 4.14 for its thermal spacing (slightly pessimistic, fine), but its README says the SC4336H "is said to fit the same pads" as the SC3336. SmartSens' press release only says it is pin-to-pin with **its** CSP-35 predecessor (SC4336/SC4336P). Use the SC4336P footprint, not the SC3336's. | [S1][S2][S3]; [S4] |
| F9 | **Flashing the C6 from Linux** works with esptool (`--before no_reset --after no_reset`, with EN and GPIO9 driven by `gpioset`) or Espressif's **esp-serial-flasher** Linux port (libgpiod). The serial-flasher port wants EN and BOOT on **one gpiochip**; see §3.3. After the first flash, esp-hosted-linux can update the C6 over SDIO (`insmod esp32_sdio.ko ota_file=…`). | [S15]; [S14] docs/guides/ota.md |

---

## 1. Image sensor: SmartSens SC4336H (CSP-35), ball by ball

The SC4336H datasheet is under NDA and was not found. Here is what each part of this section rests on:

- **Ball names:** the EasyEDA SC4336P library you supplied (C9900187041). Its footprint is checked in the repo at `products/layercam/layercam-pro/src/easyeda_raw/CSP-35_L5.7-W3.7-P0.64-R5-C7-S0.58-TL.kicad_mod`: 35 round pads, 0.20 mm, columns 1-7 at 0.64 mm pitch, rows A-E at 0.58 mm, A1 at top-left (−1.92, −1.16).
- **Electrical values:** SmartSens flyers [S1][S2][S3] (rails only); a third-party summary of the **SC4336 datasheet V0.3** [S9]; Rockchip/Luckfox driver source and EVB DTS [S5]; the RT-Thread EVB board file [S5b]; and an SC2336 design note [S11] for VREFN and DVDD.
- **Mapping assumption:** SmartSens says the SC4336H is pin-to-pin with its CSP-35 predecessor, so the SC4336/SC4336P ball map is assumed. **[?] Confirm against the SC4336H datasheet.**

### 1.1 Rails

| Rail | Value | Feed | Confidence / source |
|---|---|---|---|
| AVDD (analog) | **2.8 V ±0.1 V** | Dedicated low-noise LDO: TLV75528 (Pro parts-check) from VCC_3V3. TI: CIN ≥ 1 µF, COUT 1 µF nominal (≥ 0.47 µF effective, ≤ 200 µF). Not from a DC/DC directly, and not shared with DOVDD | [C] SC4336H flyer "Analog = 2.8±0.1V" [S3]; [2] "use a high-PSRR LDO, not a DC/DC" [S9][S11]; [C] TLV755P SBVS320D Table 6.3 [S12] |
| DOVDD (I/O) | **1.8 V ±0.1 V** | VCC_1V8. Same domain as the RV1106's VCCIO7, where the camera's I2C/MCLK/GPIOs sit, so no level shifting. A 1R + 1 µF or a bead filter as v1's VCC_1V8_MIPI is suggested [?] | [C] flyer "Digital = 1.8±0.1V" [S3]; [2] "DOVDD = 1.8V" [S9]; v1 circuit.py pin 1 "1.8 V only" |
| DVDD (core) | **Internal LDO, default. Do not feed it.** Capacitors only | Caps to ground at the DVDD balls | [2] "DVDD default internal LDO (external supply: ask FAE)… the DVDD balls can't float, cap them" [S9]; same for SC3336 and SC2336 [S9b][S11]. The Rockchip driver lists a "dvdd" regulator, but it is optional and not used by any RV1106 DTS [S5] |
| Current | IAVDD ≈ 20.9 mA, IDOVDD ≈ 50.1 mA (SC4336, 2-lane 30 fps); SC4336H "< 120 mW at 30 fps" | | [2] [S9]; [C] SmartSens PR [S4] |

### 1.2 Ball → net → value

| Ball | Name (EasyEDA) | Pro net | Connect / value | Confidence |
|---|---|---|---|---|
| A1 | AGND | GND (sensor ground island) | to the ground plane under the sensor | [C] name |
| C7 | AGND | GND | same | [C] name |
| B2 | DOGND | GND | same | [C] name |
| D6 | DOGND | GND | same | [C] name |
| B1 | AVDD | CAM_AVDD (2.8 V) | **1 µF + 100 nF** at the ball | rail [C]; values [2] "100 nF–1 µF MLCC at each supply ball" [S9] |
| B7 | AVDD | CAM_AVDD | **100 nF** at the ball (the 1 µF at B1 and the LDO's 1 µF output cap are on the same short net) | [2]/[?] |
| C2 | DOVDD | CAM_DOVDD (1.8 V) | **1 µF + 100 nF** shared by C2/C3 | rail [C]; values [2] |
| C3 | DOVDD | CAM_DOVDD | (with C2) | |
| B4 | DVDD | CAM_DVDD (internal, no source) | **4.7 µF + 100 nF** on the DVDD net, plus **100 nF** at the far DVDD ball | [2] SC2336 note: DVDD side shows 4.7 µF + 0.1 µF [S11]. **[?] Confirm in the SC4336H datasheet** |
| B6 | DVDD | CAM_DVDD | join to B4/C1/E4 | |
| C1 | DVDD | CAM_DVDD | | |
| E4 | DVDD | CAM_DVDD | 100 nF here | |
| E7 | VREFN | CAM_VREFN | **2.2 µF to AGND**, at the ball, away from EXTCLK/MIPI | [2] SC2336 design note "VREFN external 2.2 µF to ground, close to the pin" [S11]. **[?]** |
| D7 | VREFN2 | CAM_VREFN2 | **2.2 µF to AGND** (assumed the same as VREFN) | **[?] no source for VREFN2** |
| A3 | EXTCLK | CAM_MCLK | from RV1106 MIPI_REFCLK_OUT0 (GPIO3_C4, U1 pin 2) via **22 Ω series at the SoC** (as v1). **24 MHz** | [C] sc4336.c:46 `SC4336_XVCLK_FREQ 24000000`, and the driver warns "modes are based on 24MHz" (:965-969) [S5]; [2] valid range 6-40 MHz, duty 45-55 % [S9] |
| A4 | SDA | CAM_SDA | RV1106 I2C4_SDA_M2 (GPIO3_D0, U1 pin 7); **4.7 kΩ to 1.8 V** (v1 R) | [C] rv1106-pinctrl.dtsi:268-273; v1 circuit.py |
| A5 | SCL | CAM_SCL | RV1106 I2C4_SCL_M2 (GPIO3_C7, U1 pin 5); **4.7 kΩ to 1.8 V** | same |
| B5 | SID | GND | **tie to DOGND → 7-bit address 0x30** (SID high = 0x32) | [C] 0x30 in every RV1106 DTS (`sc4336@30`, `reg = <0x30>`, rv1106-evb-cam.dtsi:160-163) and the RT-Thread EVB board (`.i2c_addr = 0x30`, board.c:24) [S5][S5b]; [2] "SID=L 0x30 / SID=H 0x32", internal pull-down [S9][S9b] |
| A6 | XSHUTDN | CAM_RST | RV1106 GPIO3_C5 (U1 pin 3, v1's CAM_RST). **Active low** (low = shut down). Optional 100 kΩ pull-down so the sensor stays off until Linux [?] | [C] the RT-Thread EVB drives XSHUTDN from GPIO3_C5 with `.rst_active = 0` (board.c:25-35) [S5b]; the Linux driver sets reset-gpio 0, enables the supplies, then sets it to 1 (sc4336.c:981-991), with DT `reset-gpios = <&gpio3 RK_PC5 GPIO_ACTIVE_HIGH>` (rv1106-evb-cam.dtsi:166) = physical high to run |
| C6 | PWDNB | CAM_PWDN | **Recommended:** RV1106 GPIO3_C6 (U1 pin 4, free in v1, 1.8 V domain) as `pwdn-gpios`. **Alternative:** 10 kΩ to DOVDD. Active low: low = hard standby, no I2C | [C] driver sets pwdn 1 to run, 0 to stop (sc4336.c:994-995, 1029-1030), and the EVB has `pwdn-gpios … GPIO_ACTIVE_HIGH` (rv1106-evb-cam.dtsi:167, on GPIO3_D2 there); [2] "PWDNB (C6) internal pull-up, active low" [S9]. GPIO3_C6 is a **[?]** choice |
| C4 | MCP | CSI_CKP | RV1106 U1 pin 126 | [C] v1 circuit.py; naming [?] |
| D4 | MCN | CSI_CKN | U1 pin 125 | |
| E5 | MD0P | CSI_D0P | U1 pin 128 | |
| D5 | MD0N | CSI_D0N | U1 pin 127 | |
| D3 | MD1P | CSI_D1P | U1 pin 124 | |
| D2 | MD1N | CSI_D1N | U1 pin 123 | |
| C5, E6, D1, E1 | MD2N_NC, MD2P_NC, MD3P_NC, MD3N_NC | — | **NC** (2-lane part; the "_NC" balls are reserved) | [C] driver `SC4336_LANES 2` (sc4336.c:40); flyer "1/2 lane MIPI" [S3] |
| B3 | FSYNC | — | NC (frame-sync output, unused); a test pad is optional | [?] |
| A7 | EFSYNC | — | NC (external frame-sync input, only for slave mode) | [2] [S11]. **[?] whether it needs a defined level** |
| A2, E2, E3 | NC | — | NC | name |

MIPI routing: 100 Ω differential, intra-pair matched to about 10 mil, no series parts on the pairs ([2] [S9]). RV1106 data-lanes `<1 2>`, with MD0 on D0 and MD1 on D1 as on the Luckfox module.

### 1.3 Power-up / power-down (what the SDK driver does)

1. pinctrl → MCLK 24 MHz on (`clk_set_rate` + `clk_prepare_enable`), sc4336.c:963-975.
2. XSHUTDN low → supplies on (AVDD, DOVDD; regulators optional) → XSHUTDN high, :981-991.
3. 0.5–1 ms → PWDNB high, :993-995.
4. 6–8 ms if reset-gpios exists, otherwise 12–16 ms, :997-1000. Then 8192 MCLK cycles (342 µs at 24 MHz) before the first I2C, :1002-1004.
5. Power-off: MCLK off → PWDNB low → XSHUTDN low → supplies off, :1015-1039.

The datasheet's own timing ([2] SC4336 datasheet V0.3 §1.4.1 [S9]): T1..T4 ≥ 0 ms between rails (no strict order; DOVDD first or together is suggested), and **T5 ≥ 4 ms after XSHUTDN/PWDNB release before I2C**. The driver's 6–8 ms meets this. On v1's board, VCC_1V8 comes up before VCC_3V3, so DOVDD comes before the 2.8 V LDO's input; that order is allowed.

### 1.4 RV1106 device tree for the sensor (Pro)

```dts
&i2c4 {
	status = "okay";
	clock-frequency = <400000>;
	pinctrl-names = "default";
	pinctrl-0 = <&i2c4m2_xfer>;

	sc4336h: sc4336h@30 {
		compatible = "smartsens,sc4336h";       /* new driver; "smartsens,sc4336" for a first ID test */
		reg = <0x30>;                            /* SID tied low */
		clocks = <&cru MCLK_REF_MIPI0>;
		clock-names = "xvclk";                   /* 24 MHz */
		reset-gpios = <&gpio3 RK_PC5 GPIO_ACTIVE_HIGH>;   /* XSHUTDN, ball A6 */
		pwdn-gpios  = <&gpio3 RK_PC6 GPIO_ACTIVE_HIGH>;   /* PWDNB, ball C6 */
		pinctrl-names = "default";
		pinctrl-0 = <&mipi_refclk_out0>;
		rockchip,camera-module-index = <0>;
		rockchip,camera-module-facing = "back";
		rockchip,camera-module-name = "...";      /* picks the IQ json */
		rockchip,camera-module-lens-name = "...";
		port { sc4336h_out: endpoint { remote-endpoint = <&csi_dphy_input0>; data-lanes = <1 2>; }; };
	};
};
```

(`GPIO_ACTIVE_HIGH` on both lines is how the Rockchip EVB writes them: the driver's logical 1 means "run" [S5].)

### 1.5 What the SDK needs for the SC4336H

- **Kernel config:** add `CONFIG_VIDEO_SC4336=m` (or the new `SC4336H`) to `firmware/board/sdk/layercam.config`. The Luckfox defconfig has only `CONFIG_VIDEO_SC3336=m` (luckfox_rv1106_linux_defconfig:338) [S5].
- **Chip ID: unknown [?].** The family reads a 16-bit ID at 0x3107/0x3108: SC3336/SC3338 0xcc41, SC3336P 0x9c41, SC4336 0xdc42, SC4336P 0x9c42 [S5][S7][S8]. Read the real part at bring-up with `i2ctransfer -y 4 w2@0x30 0x31 0x07 r2` while the driver holds the sensor powered. If it reads 0xdc42 or 0x9c42, the existing `sc4336.c`/`sc4336p.c` will at least probe.
- **Register table:** `sc4336.c` and `sc4336p.c` share the mode (2560x1440, RAW10 SBGGR10, 2 lanes, 315 MHz link = 630 Mbps/lane, 25 fps; sc4336.c:40-46, 324-335) but differ in about a dozen analog registers (0x301f, 0x3314, 0x3334, 0x33f9, …; see the diff of the two tables). The SC4336H is a new process (DSI-3), so expect its own init table. **Ask SmartSens or the agent for the SC4336H Rockchip driver patch or init sequence.** Porting = copy `sc4336.c` → `sc4336h.c`, change CHIP_ID, the compatible string and the register list, and add Kconfig and Makefile entries.
- **ISP tuning:** the SDK ships SC4336 IQ files (`sc4336_OT01_40IRC_F16.json`, `sc4336_CMK-OT2117-PC1_30IRC-F16.json`) and none for the SC4336P or SC4336H. Start from an SC4336 file; it needs real tuning for the new lens.
- `firmware/layercam/board.py`: `SENSOR_WIDTH, SENSOR_HEIGHT = 2304, 1296` becomes 2560, 1440.

---

## 2. ESP32-C6-MINI-1U-H4

Source: ESP32-C6-MINI-1 & MINI-1U Datasheet **v1.5** [S10] unless stated otherwise. -H4 = 4 MB flash, −40..105 °C, 13.2 x 12.5 x 2.4 mm.

### 2.1 Module pin → net → value

| Module pin | Name | Pro net | Connect / value | Source |
|---|---|---|---|---|
| 3 | 3V3 | VWIFI (3.25 V) | **22 µF + 100 nF** at pin 3 (Espressif fig. 9-1 C1 22 µF, C2 0.1 µF). v1's 22 µF X6S 0603 6.3 V is fine. 3.0–3.6 V, ≥ 0.5 A | Fig. 9-1 p.40; Table 6-2 |
| 1, 2, 11, 14, 36–48, 49 (EPAD), 50–53 | GND | GND | all to ground. EasyEDA also numbers the EPAD's 3x3 segments **54–61**: all GND. Vias in the EPAD for heat (Espressif: soldering the EPAD is optional but better thermally) | Table 3-1; fig. 9-1 notes |
| 8 | EN (CHIP_PU) | WIFI_EN | RV1106 **GPIO1_A2** (U1 pin 74, v1's WL_REG_ON) via mmc-pwrseq. **100 kΩ to GND** (off until Linux, as v1). Optional 100 nF to GND [?]. Espressif's 10 kΩ pull-up + 1 µF RC is for a free-running EN; with EN driven by a GPIO it is not used. Hold ≥ 50 µs low to reset; rails stable ≥ 50 µs before release. "Do not leave EN floating" | Table 3-1; §4.5 Table 4-8; fig. 9-1 note "R = 10 kΩ, C = 1 µF" |
| 23 | IO9 (BOOT strap) | WIFI_BOOT | RV1106 **GPIO0_A2** (U1 pin 60, v1's BT_WAKE). **10 kΩ to VWIFI** (SPI boot by default) and RV1106 pinctrl `pcfg_pull_up` on that pin. Linux drives it low only to flash. GPIO9 = 0 with GPIO8 = 1 → joint download (UART/USB/SDIO); GPIO9 = 1 → SPI boot. Internal weak pull-up 45 kΩ. Hold ≥ 3 ms after EN rises | Tables 4-1, 4-2, 4-3; Table 6-3 RPU |
| 22 | IO8 (strap) | — | **10 kΩ to VWIFI.** GPIO8 floats by default, and download mode needs GPIO8 = 1. It also gates UART0 ROM printing (prints with default eFuse either way) | Tables 4-1, 4-3, 4-5 |
| 20 | IO15 (JTAG-source strap) | — | NC. Ignored while EFUSE_JTAG_SEL_ENABLE = 0 (the default) | Table 4-7 |
| 9 | IO4 (MTMS strap) | WIFI_HOST_WAKE (optional) | RV1106 **GPIO0_A3** (U1 pin 62, v1's WL_HOST_WAKE). IO4 is esp-hosted's default `HOST_WAKEUP_GPIO` for the C6. v1's pinctrl pull-down on GPIO0_A3 makes MTMS = 0 at reset; that strap only sets the ROM's SDIO edge, and esp-hosted sets the timing in software (`SDIO_SLAVE_TIMING_NSEND_PSAMPLE` for the C6), so it is harmless. Unneeded unless host suspend is used | [S14] Kconfig.projbuild:232-240, host-sleep.md:25, sdio_slave_api.c:554-556; Table 4-4 |
| 10 | IO5 (MTDI strap) | — | NC | Table 4-4 |
| 24 | IO18 | SD_CMD | RV1106 SDMMC0_CMD (GPIO3_A5, U1 pin 16). **10 kΩ to VCC_3V3** | Table 3-1 "GPIO18, SDIO_CMD"; [S14] hardware-setup.md:11, :31-39 |
| 25 | IO19 | SD_CLK | RV1106 SDMMC0_CLK (GPIO3_A4, U1 pin 15) via **22 Ω at the SoC** (v1). No pull-up | Table 3-1 "GPIO19, SDIO_CLK" |
| 26 | IO20 | SD_D0 | SDMMC0_D0 (GPIO3_A3, U1 pin 14). **10 kΩ to VCC_3V3** | Table 3-1 |
| 27 | IO21 | SD_D1 | SDMMC0_D1 (GPIO3_A2, U1 pin 12). **10 kΩ** | Table 3-1 |
| 28 | IO22 | SD_D2 | SDMMC0_D2 (GPIO3_A7, U1 pin 18). **10 kΩ** | Table 3-1 |
| 29 | IO23 | SD_D3 | SDMMC0_D3 (GPIO3_A6, U1 pin 17). **10 kΩ** | Table 3-1 |
| 30 | RXD0 (GPIO17) | WIFI_RXD | ← RV1106 **UART1_TX_M0** (GPIO1_A3, U1 pin 75, v1's BT_TXD) | Table 3-1; [S5] pinctrl:930-935 |
| 31 | TXD0 (GPIO16) | WIFI_TXD | → RV1106 **UART1_RX_M0** (GPIO1_A4, U1 pin 76, v1's BT_RXD). 115200 for ROM logs; esptool/esp-serial-flasher raise the baud | same |
| 17 / 18 | IO12 / IO13 (USB D− / D+) | — | **Test pads** (recovery flashing through the C6's USB-Serial-JTAG) [?] optional | Table 3-1 |
| 5, 6, 12, 13, 15, 16, 19 | IO2, IO3, IO0, IO1, IO6, IO7, IO14 | — | NC | |
| 4, 7, 21, 32–35 | NC | — | NC | Table 3-1 |
| (connector) | MHF III / W.FL | — | 50 Ω antenna pigtail to the case wall. No keep-out on the -1U | §3.1, §10.2 |

Notes:

- **Levels.** Every C6 I/O is at VDD33: VIH = 0.75 x VDD (2.48 V at 3.3 V), VIL = 0.25 x VDD (Table 6-3). The RV1106's VCCIO4 (SDIO), VCCIO1 (UART1, GPIO1_A2) and PMU domain (GPIO0) are all 3.25 V in v1, so they match directly. Keep VWIFI within about 0.1 V of VCC_3V3 (F1).
- **Pull-ups.** esp-hosted: "CMD and DAT0-DAT3 require pull-ups … including unused data lines"; its wiring diagram uses 10 kΩ. The firmware's internal pull-up flag is commented out ("not sufficient and not reliable") [S14] sdio_slave_api.c:540-544. v1's five 10 kΩ to VCC_3V3 are exactly right; keep them, and keep v1's 1 kΩ SD_DET to ground.
- **Bus speed.** esp-hosted's C6 numbers (55.6 Mbps TCP) were measured at up to 50 MHz on a Raspberry Pi. Start bring-up at `max-frequency = <25000000>`, then go to v1's 50 MHz with `cap-sd-highspeed` once transfers are clean ([S14] porting checklist 7-9).
- **No handshake or data-ready lines for SDIO.** Those are SPI-only. SDIO uses the in-band SDIO interrupt (`cap-sdio-irq`) and in-band reboot; reset/EN is only for enumeration and full-chip recovery ([S14] supported-hardware.md "Additional required GPIOs: None … after enumeration").

### 2.2 Land pattern

| Item | Espressif (fig. 11-2) | EasyEDA lib in repo (`WIFIM-SMD_61P-L13.2-W12.5-P0.80`, 61 pads) |
|---|---|---|
| Body | 13.20 x 12.50 mm | 13.2 x 12.5 ✓ |
| Edge pads | 48 x 0.40 x 0.80 mm, 0.80 pitch; left 1–11, bottom 12–24, right 25–35, top 36–48 (top row is GND) | 48 pads 0.5 x 1.0 mm (larger than Espressif's 0.4 x 0.8), rows at x = ±5.90, y = ±5.00; numbering and positions ✓ |
| Corner pads | 4 x 0.70 mm (50 TR, 51 BR, 52 BL, 53 TL) | 4 x 0.70 at (±5.95, ±4.95) ✓ |
| EPAD | pin 49, about 5.4 mm square as a 3 x 3 grid | 9 x 1.45 mm squares at 1.97 pitch, numbered 49 (centre) + 54–61 → **all GND** |

Why 61 = 53 + 8: the extra 8 are EPAD segments. Consider trimming the edge pads to Espressif's 0.4 x 0.8 [?]; at 0.5 wide and 0.8 pitch the copper gap is 0.30 mm.

---

## 3. RV1106G3 side

### 3.1 v1 as built (circuit.py `main_soc()` / `main_wifi()` / `main_camera()`, dts `rv1106g-layercam-v1.dts`)

| U1 pin | Function (GPIO) | v1 net | Goes to |
|---|---|---|---|
| 11 | SDMMC0_DET (GPIO3_A1) | SD_DET | 1 kΩ to GND |
| 12 | SDMMC0_D1 (GPIO3_A2) | SD_D1 | AP6256 19, 10 k pull-up |
| 13 | VCCIO4 | VCC_3V3 | SDIO at 3.3 V |
| 14 | SDMMC0_D0 (GPIO3_A3) | SD_D0 | AP6256 18 |
| 15 | SDMMC0_CLK (GPIO3_A4) | SD_CLK_SOC → 22 Ω → SD_CLK | AP6256 17 |
| 16 | SDMMC0_CMD (GPIO3_A5) | SD_CMD | AP6256 16 |
| 17 | SDMMC0_D3 (GPIO3_A6) | SD_D3 | AP6256 15 |
| 18 | SDMMC0_D2 (GPIO3_A7) | SD_D2 | AP6256 14 |
| 74 | GPIO1_A2 | WL_REG_ON | AP6256 12; 100 k pull-down; `sdio_pwrseq reset-gpios` active low, 200 ms |
| 62 | GPIO0_A3 | WL_HOST_WAKE | AP6256 13 (OOB IRQ) |
| 59 | GPIO0_A1 | BT_REG_ON | AP6256 34 (100 k pull-down) |
| 60 | GPIO0_A2 | BT_WAKE | AP6256 6 |
| 63 | GPIO0_A4 | BT_HOST_WAKE | AP6256 7 |
| 64 / 65 | UART1_RTS_M0 (GPIO0_A5) / UART1_CTS_M0 (GPIO0_A6) | BT_RTS / BT_CTS | AP6256 44 / 41 |
| 75 / 76 | UART1_TX_M0 (GPIO1_A3) / UART1_RX_M0 (GPIO1_A4) | BT_TXD / BT_RXD | AP6256 43 / 42 |
| 1 | MIPI_AVDD1V8 / VCCIO7 | VCC_1V8_MIPI | 1 R + 100 nF + 1 µF |
| 2 | MIPI_REFCLK_OUT0 (GPIO3_C4) | CAM_MCLK_SOC → 22 Ω → CAM_MCLK | FFC 2 |
| 3 | GPIO3_C5 | CAM_RST | FFC 16 (`pwdn-gpios` active high) |
| 4 | GPIO3_C6 (1.8 V) | — | unused |
| 5 / 7 | I2C4_SCL_M2 (GPIO3_C7) / I2C4_SDA_M2 (GPIO3_D0) | CAM_SCL / CAM_SDA | FFC 13 / 14; 4.7 k to 1.8 V |
| 123 / 124 | CSI D1N / D1P | | FFC 11 / 10 |
| 125 / 126 | CSI CKN / CKP | | FFC 8 / 7 |
| 127 / 128 | CSI D0N / D0P | | FFC 5 / 4 |
| 117–122 | lanes 2/3, CK1 | — | unused |

(Physical pin numbers and the GPIO names in parentheses come from circuit.py, which says it was checked against the RV1106 datasheet Rev 2.2; `docs/rv1106_pins.md`, which it cites, is not in the repo. The function ↔ GPIO pairs were checked against the SDK's rv1106-pinctrl.dtsi [S5].)

### 3.2 Proposed Pro mapping

| U1 pin | GPIO / function | Pro net | Pro destination | Change from v1 |
|---|---|---|---|---|
| 12, 14, 15, 16, 17, 18 | SDMMC0 D1, D0, CLK, CMD, D3, D2 | SD_* | C6 pins 27, 26, 25 (via 22 Ω), 24, 29, 28 | AP6256 → C6; pull-ups and 22 Ω kept |
| 11 | SDMMC0_DET | SD_DET | 1 kΩ to GND | same |
| 13 | VCCIO4 | VCC_3V3 | | same |
| 74 | GPIO1_A2 | WIFI_EN | C6 pin 8 (EN); 100 kΩ to GND | rename only; pwrseq delay 200 → **1500 ms** |
| 60 | GPIO0_A2 | WIFI_BOOT | C6 pin 23 (IO9); 10 kΩ to VWIFI; pinctrl pull-up | was BT_WAKE |
| 62 | GPIO0_A3 | WIFI_HOST_WAKE | C6 pin 9 (IO4), optional | was WL_HOST_WAKE |
| 75 | UART1_TX_M0 (GPIO1_A3) | WIFI_RXD | C6 pin 30 (RXD0) | was BT_TXD |
| 76 | UART1_RX_M0 (GPIO1_A4) | WIFI_TXD | C6 pin 31 (TXD0) | was BT_RXD |
| 59, 63, 64, 65 | GPIO0_A1, A4, A5, A6 | — | **free** (see 3.3 for GPIO0_A1) | Bluetooth control gone |
| 1, 2, 5, 7, 123–128 | MIPI / MCLK / I2C4_M2 | as v1 | SC4336H balls (§1.2) direct, no FFC | FFC → sensor |
| 3 | GPIO3_C5 | CAM_RST | SC4336H A6 XSHUTDN (DT `reset-gpios`) | was `pwdn-gpios` |
| 4 | GPIO3_C6 | CAM_PWDN | SC4336H C6 PWDNB (DT `pwdn-gpios`) | new; was unused |

The console stays on UART2_M1 (pins 79/80), so UART1 (`/dev/ttyS1`; alias `serial1 = &uart1`, rv1106.dtsi:56) is free for the C6.

### 3.3 One alternative worth taking: put EN and BOOT on the same GPIO bank

esp-serial-flasher's Linux port takes **one** `gpio_chip_path` for both `reset_pin` and `boot_pin` (port/linux_port.h:65-78) [S15]. With EN on gpio1 and BOOT on gpio0, that port cannot drive both. esptool + `gpioset` doesn't care. If you want esp-serial-flasher, move EN to **GPIO0_A1 (U1 pin 59, v1's BT_REG_ON, 100 kΩ pull-down already there)**, so EN, BOOT and HOST_WAKE are all on gpiochip0 (PMU domain, 3.3 V). This frees GPIO1_A2. Either works electrically.

### 3.4 Device tree (Pro, Wi-Fi part)

```dts
/ {
	sdio_pwrseq: sdio-pwrseq {
		compatible = "mmc-pwrseq-simple";
		pinctrl-names = "default";
		pinctrl-0 = <&wifi_enable_h>;
		reset-gpios = <&gpio1 RK_PA2 GPIO_ACTIVE_LOW>;   /* C6 EN */
		post-power-on-delay-ms = <1500>;                  /* esp-hosted's C6 value */
	};
	/* delete v1's wireless-wlan (bcmdhd) and wireless-bluetooth nodes */
};

&sdmmc {
	max-frequency = <25000000>;        /* bring-up; 50000000 once stable */
	bus-width = <4>;
	cap-sd-highspeed;
	cap-sdio-irq;
	keep-power-in-suspend;
	non-removable;
	no-1-8-v;
	supports-sdio;
	rockchip,default-sample-phase = <90>;
	mmc-pwrseq = <&sdio_pwrseq>;
	espressif,full-chip-reset;         /* esp_sdio.c:52: pwrseq really toggles EN */
	pinctrl-names = "default";
	pinctrl-0 = <&sdmmc0_clk &sdmmc0_cmd &sdmmc0_bus4 &sdmmc0_det>;
	status = "okay";
};

&uart1 {                               /* C6 UART0, 2-wire, for flashing */
	pinctrl-names = "default";
	pinctrl-0 = <&uart1m0_xfer>;
	status = "okay";
};

&pinctrl {
	wifi {
		wifi_enable_h: wifi-enable-h { rockchip,pins = <1 RK_PA2 RK_FUNC_GPIO &pcfg_pull_none>; };
		wifi_boot:     wifi-boot     { rockchip,pins = <0 RK_PA2 RK_FUNC_GPIO &pcfg_pull_up>; };
		wifi_host_wake: wifi-host-wake { rockchip,pins = <0 RK_PA3 RK_FUNC_GPIO &pcfg_pull_down>; };
	};
};
```

Kernel/software: remove `RK_ENABLE_WIFI_CHIP=AP6XXX` and bcmdhd. Keep `CONFIG_CFG80211=y` (already in layercam.config). Build `esp32_sdio.ko` from esp-hosted-linux `host/` with `ARCH=arm CROSS_COMPILE=… KERNEL=<sdk kernel>` ([S14] porting.md:113-128). The C6 firmware is `esp/esp_driver/network_adapter`, built with `idf.py set-target esp32c6`.

### 3.5 Flashing the C6 from Linux (first time; later use `ota_file=`)

```sh
echo ffaa0000.mmc > /sys/bus/platform/drivers/dwmmc_rockchip/unbind   # driver name: dw_mmc-rockchip.c:508
echo sdio-pwrseq  > /sys/bus/platform/drivers/pwrseq_simple/unbind    # frees GPIO1_A2 (pwrseq_simple.c:158)
gpioset gpiochip0 2=0          # GPIO0_A2 → IO9 low (download); GPIO8 is pulled up on the board
gpioset gpiochip1 2=0; sleep 0.01; gpioset gpiochip1 2=1   # EN pulse (≥50 µs low); keep IO9 low ≥3 ms after
esptool --chip esp32c6 -p /dev/ttyS1 -b 460800 --before no_reset --after no_reset write_flash 0x0 bootloader.bin 0x8000 partition-table.bin 0x10000 network_adapter.bin
gpioset gpiochip0 2=1          # IO9 high → SPI boot
echo sdio-pwrseq  > /sys/bus/platform/drivers/pwrseq_simple/bind
echo ffaa0000.mmc > /sys/bus/platform/drivers/dwmmc_rockchip/bind
```

(esptool v5 spells these `no-reset`; underscores are still accepted. A libgpiod v1 `gpioset` holds the line only while it runs, so use `--mode=signal` or libgpiod v2 `gpioset -z`. The flash offsets are the ESP-IDF defaults; check against the build's `flasher_args.json`.)

---

## 4. Not confirmed (and how to close each)

| Item | Status | How to close |
|---|---|---|
| SC4336H ball map = SC4336P EasyEDA map | inferred from SmartSens' "pin-to-pin with predecessor" | SC4336H datasheet (SmartSens / agent, NDA) |
| VREFN / VREFN2 capacitor (2.2 µF) | from an SC2336 note only; nothing for VREFN2 | same datasheet, or a reference module schematic |
| DVDD capacitor (4.7 µF + 100 nF) | from the SC2336 note; the internal LDO is confirmed only by summaries | same |
| SID internal pull-down; PWDNB/XSHUTDN internal pull-ups | third-party summaries | same; tie SID hard to ground regardless |
| EFSYNC: OK to leave open? | unknown | same |
| SC4336H chip ID and init registers | not public anywhere searched (Luckfox SDK 824b817f, Rockchip kernel develop-5.10 95a3ad8 / develop-6.1 77168c8, ingenic-sdk, OpenIPC ipctool) | read 0x3107/0x3108 on a sample; ask SmartSens for the Rockchip driver patch |
| T5 ≥ 4 ms, EXTCLK 6–40 MHz | SC4336 datasheet V0.3 as summarised by pdapply.com (not read directly) | datasheet |
| RV1106 GPIO0_A2 reset-state pull | not found; matters only if Linux is not driving IO9 when EN rises | RV1106 TRM GRF pull reset values; the 10 kΩ pull-up + pinctrl pull-up covers it |
| RV1106 physical pin numbers | from circuit.py (which cites RV1106 datasheet Rev 2.2); `docs/rv1106_pins.md` it names is missing | RV1106 datasheet |
| esp-hosted-linux on RV1106 dw_mmc | not shown by anyone (the Pro README already plans a bench test) | Luckfox Pico Max + C6 devkit bench test |
| C6 EN 100 nF filter | design choice | bench |
| EasyEDA C20627095 = the footprint in `easyeda_raw/` | assumed from the name; pad count 61 confirmed | re-pull with easyeda2kicad |

---

## Sources

- [S1] SmartSens SC4336 Product Flyer V2.0: https://smartsens.oss-cn-beijing.aliyuncs.com/web/products/SC4336_V2.0.pdf (Analog 2.8 V, Digital 1.8 V, 35-pin CSP 5.75 x 3.872 mm, −30..85 °C, 1/2-lane MIPI)
- [S2] SmartSens SC3336 Product Flyer V2.0: https://smartsens.oss-cn-beijing.aliyuncs.com/web/products/SC3336_V2.0.pdf (I/O 1.8 V, 6.199 x 4.139 mm)
- [S3] SmartSens SC4336H Product Flyer V1.0: https://smartsens.oss-cn-beijing.aliyuncs.com/web/img/1754466597655083783.pdf (Analog 2.8±0.1 V, Digital 1.8±0.1 V, 35-pin CSP 5.750 x 3.872 mm, 8/10-bit 1/2-lane MIPI, 2560x1440 at 30 fps)
- [S4] SmartSens press release (SC4336H, May 2025): https://www.smartsenstech.com/en/page?id=323 ("pin-to-pin compatible with its predecessor", < 120 mW at 30 fps)
- [S5] Luckfox Pico SDK, github.com/LuckfoxTECH/luckfox-pico @ 824b817f (22 Mar 2026), kernel 5.10.160:
  `sysdrv/source/kernel/drivers/media/i2c/sc4336.c` (:40 lanes, :42 link 315 MHz, :46 XVCLK 24 MHz, :48-49 ID 0xdc42 at 0x3107, :105-107 supply names, :963-1004 power-on, :1015-1039 power-off, :1566 compatible); `sc4336p.c` (:43 24 MHz, :45 ID 0x9c42); `sc3336.c` (:47 27 MHz, :49 ID 0xcc41); `arch/arm/boot/dts/rv1106-evb-cam.dtsi:160-180` (sc4336@30, reset GPIO3_C5, pwdn GPIO3_D2, both ACTIVE_HIGH); `rv1106-luckfox-pico-pro-max-ipc.dtsi:149-168`; `rv1106g-luckfox-pico-ultra.dts:80-95`; `rv1106.dtsi:56, 1184, 1403`; `rv1106-pinctrl.dtsi:268-273, 700-828, 930-948, 1248-1251`; `arch/arm/configs/luckfox_rv1106_linux_defconfig:338`; `drivers/mmc/host/dw_mmc-rockchip.c:508`; `drivers/mmc/core/pwrseq_simple.c:124-158`
- [S5b] same SDK, RT-Thread MCU: `sysdrv/source/mcu/rt-thread/bsp/rockchip/rv1106-mcu/board/rv1106_evb-SC4336-ADC/board.c:22-38` (i2c_addr 0x30, rst GPIO3_C5, rst_active 0, i2c4, CLK_REF_MIPI0); `iomux.c:21` (GPIO3_C4 = MIPI_REFCLK_OUT0); `common/drivers/camera/drv_sc4336p.c:40-42`
- [S6] Rockchip kernel github.com/rockchip-linux/kernel, develop-6.1 @ 77168c8 and develop-5.10 @ 95a3ad8: drivers/media/i2c has sc4336.c and sc4336p.c, no sc4336h
- [S7] OpenIPC ipctool `src/sensors.c:638-709` (0xcc41 SC3336, 0x9c41 SC3336P, 0xdc42 SC4336, 0x9c42 SC4336P)
- [S8] themactep/ingenic-sdk `common/sensor/t31/sc4336.c:22-25` (ID 0xdc42, I2C 0x30); there is no sc4336h file
- [S9] pdapply.com summary of the SC4336 datasheet V0.3: https://pdapply.com/archives/sc4336 (rails, internal DVDD LDO, SID 0x30/0x32, EXTCLK 6-40 MHz, T5 ≥ 4 ms, PWDNB C6 / XSHUTDN A6). [S9b] the same site's SC3336 page: https://pdapply.com/archives/sc3336. Third-party, partly machine-written; treat as secondary
- [S10] Espressif ESP32-C6-MINI-1 & MINI-1U Datasheet v1.5: https://www.espressif.com/sites/default/files/documentation/esp32-c6-mini-1_mini-1u_datasheet_en.pdf (Table 3-1 pp.10-11; Tables 4-1..4-8 pp.12-16; Tables 6-1..6-4 pp.26-27; fig. 9-1 p.40; fig. 10-2 p.41; §10.2 pp.42-43; fig. 11-2 p.45)
- [S11] SC2336 design note (CSDN, weixin_42006477/130380968), via search summary only; the page itself was blocked (HTTP 521)
- [S12] TI TLV755P datasheet SBVS320D: https://www.ti.com/lit/ds/symlink/tlv755p.pdf (CIN 1 µF, COUT 1–200 µF, effective ≥ 0.47 µF)
- [S13] github.com/espressif/esp-hosted @ a042292 README (NG → esp-hosted-linux, FG → esp-hosted-mcu, both legacy)
- [S14] github.com/espressif/esp-hosted-linux @ 54d5367, v1.0.6.0.7: `docs/getting-started/hardware-setup.md:11-39, 131`; `docs/reference/supported-hardware.md` (SDIO targets incl. C6; :99 Linux 4.9–7.2); `docs/porting.md` (SDIO DT, no resetpin=); `host/overlays/esp32-sdio-pwrseq.dts:20-41` (1500 ms); `host/sdio/esp_sdio.c:52`; `esp/esp_driver/network_adapter/main/sdio_slave_api.c:540-556`; `main/Kconfig.projbuild:232-240`; `docs/guides/host-sleep.md:25`; `docs/guides/ota.md`
- [S15] github.com/espressif/esp-serial-flasher: README (Linux host via libgpiod, ESP32-C6 target), `port/linux_port.h:41-87`
- Repo: `products/layercam/layercam/src/circuit.py`, `products/layercam/layercam/firmware/dts/rv1106g-layercam-v1.dts`, `products/layercam/layercam/firmware/board/sdk/layercam.config`, `products/layercam/layercam-pro/README.md`, `products/layercam/layercam-pro/docs/{decisions,parts-check-2026-10-31}.md`, `products/layercam/layercam-pro/src/easyeda_raw/{CSP-35_…,WIFIM-SMD_61P_…}.kicad_mod`

Clones used (scratchpad): `src/luckfox-pico` (sparse), `src/rk-develop-6.1`, `src/rk-develop-5.10`, `src/ingenic-sdk`, `src/ipctool`, `src/esp-hosted`, `src/esp-hosted-linux`, `src/esp-serial-flasher`. Downloads: `dl2/`.
