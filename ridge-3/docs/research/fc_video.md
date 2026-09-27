> Research notes written while designing Ridge 3 (September 2026; the working name was OG3).
> Prices and stock are as found on the dates given and will have moved. The design decisions they led to
> are in `src/circuit.py` and `src/parts.py`; where the two disagree, the code is current.

# OG3 FC: HD/analog video and 6S power (research notes)

Date: 27 Sep 2026. Nothing was ordered. No repo files were edited.

**How the numbers were collected**
- **LCSC stock and prices** come from the JSON embedded in each `lcsc.com/product-detail/Cxxxx.html` page, fetched on this date. Where a JLC-only part has no LCSC page ("Page Not Found"), I say so.
- **DigiKey stock and prices** were read through a web-fetch tool that summarises the page. They are accurate to the page but not machine-exact, and they move daily.
- **Not reachable:** Mouser (HTTP 503) and analog.com (503 / empty reply). Anything that depends on them is marked **UNVERIFIED**.
- **Betaflight facts** are from the `2025.12.5` tag, the version the v1 firmware is built on.
- **Repo files read:** `README.md`, `VERIFICATION.md`, `src/circuit.py`, `src/parts.py`, `src/fc_layout.py`, `firmware/README.md`, `firmware/betaflight/configs/*/config.h`.

---

## 0. Headline findings (read these first)

1. **HD VTX connector:** use a **JST-SH 1.0 mm 6-pin** with the Betaflight Connector Standard pinout: `1 V+ · 2 GND · 3 FC-TX · 4 FC-RX · 5 GND · 6 SBUS`. This matches DJI's own O3/O4 cable pin numbering 1:1.
   - JST GH 1.25 is not used for this anywhere.
   - At LCSC only the vertical header (`BM06B-SRSS-TB`) is in stock. The right-angle `SM06B` has 0.
2. **Never feed the VTX connector from VBAT on this stack.**
   - A 6S pack (25.2 V) is above the O4 (Lite) rating of 3.7-13.2 V, above the HDZero Race V3 rating of 4-12 V, and at 95-100 % of the O3, O4 Pro and Walksnail V2 ratings.
   - Fit a **regulated 9 V rail** (10 V with one resistor change), rated for **2 A continuous**. Betaflight's standard asks for ~18 W and "at least 9 V/2 A, 8-12 V, preferably 10 V".
3. **The 60 % rule fails at the connector itself.** JST rates an SH contact at **1 A**.
   - An O3 or Walksnail Moonlight at 9 V draws about 1.8-2 A through pin 1: about 3× the 60 % limit.
   - Every FC and DJI's own cable do this anyway. To honour the rule, add `VTX+`/`G` solder pads beside the connector for high-power VTXs.
4. **The FC needs its own battery input.** With an 18 W VTX rail plus about 5 W on 5 V, at about 88 % efficiency, FC input current is about 1.3 A at 6S, 2 A at 4S, 2.7 A at 3S and about 4 A at 2S (estimate).
   - The single 1 A VBAT contact on the 8-pin ESC lead cannot carry this.
   - Add solder pads for a 20-22 AWG pair from the battery pads.
5. **The analog OSD chip is a forced exception to the non-Chinese rule.**
   - The AT7456E (Hangzhou Zhongke Microelectronics, China) is the only live MAX7456-compatible part. The MAX7456 is **Obsolete** at DigiKey.
   - The AT7456E is stocked at LCSC (35,480). DigiKey sells only a DFRobot breakout board, not the bare IC.
   - Betaflight's connector standard now says an FC-side analog OSD chip is **"no longer recommended"**.
6. **Run the AT7456E at 3.3 V, not 5 V.**
   - The SPI2 MISO pin (PB14) is a `TT_a` pin with a **4.0 V absolute maximum** (STM32G473 datasheet, DS12712).
   - The pin is shared with the flash, whose I/O limit is VCC + 0.4 V.
   - The AT7456E is specified from 3.15 V to 5.25 V. The MAX7456 cannot run at 3.3 V (4.75 V minimum).
7. **Regulators (non-Chinese, ≥ 42 V, stocked at both LCSC and DigiKey):**
   - **5 V:** TI **LMR38020FDDAR** (80 V, 2 A, synchronous).
   - **9 V:** TI **LM76003** (60 V, 3.5 A, synchronous).
   - **Inductor for both rails:** Vishay **IHLP-2525CZ-01 6.8 µH**.
   - **Catches:** DigiKey stock of the LMR38020F is thin (155). The LM76003 is stocked at LCSC as RNPR (3,000/reel) and at DigiKey as RNPT (250/reel), which is the same die and package.
8. **The v1 battery divider (10k/1k) breaks the rule at 6S.**
   - The top 10k 0402 would dissipate 52 mW, which is 84 % of its 1/16 W rating.
   - At a 53 V TVS clamp it would put 4.85 V on PB2 (`TT_a`, 4.0 V max).
   - Change to **30k/2k, `vbat_scale` 160**.
9. **Flash:** Winbond is right, but **W25Q128JVPIQ (C190862) is at 0 at LCSC today**.
   - The same-package **W25Q128JVPIM (C2441427)** is in stock at both distributors.
   - Betaflight's m25p16 table already has its JEDEC ID `EF7018`, so the current firmware reads it.
10. **Chinese-made parts in the v1 FC:** LDO (Microne), 8 MHz crystal, BEC inductor, both LEDs, USB Schottky, USB-C, BOOT button, and the 12 pF caps.
    - The crystal is made by 雅晶鑫 (Yajingxin, Shenzhen), not TAI-TIEN as its `TAXM…` part number suggests.
    - The ME6211 LDO also breaks the 60 % rule on its input voltage.
    - Replacements are in §7.
11. **Out of scope, but it blocks 6S:** the v1 ESC is 4S-only (30 V FETs, 35 V bulk capacitor).

---

## 1. Digital HD VTX connector

### 1.1 Connector and pinout

**Connector:** JST **SH** (1.0 mm), 6 positions.
- Vertical: `BM06B-SRSS-TB(LF)(SN)`, LCSC **C160392**, 33,830 in stock; DigiKey 30,798 in stock ($0.69 each).
- Right-angle: `SM06B-SRSS-TB(LF)(SN)`, LCSC C160405, **0** in stock.
- JST ratings: SH is **1 A per contact (AWG 28), 50 V** ([JST SH](https://www.jst-mfg.com/product/index.php?series=231)). GH is also 1 A, but at AWG 26 ([JST GH](https://www.jst-mfg.com/product/index.php?series=105)).
- GH is not used for HD VTXs.

**Pinout (FC side):** from the [Betaflight Connector Standard v2.2](https://betaflight.com/docs/development/manufacturer/connector-standard), "Digital Video Transmitter Pin Configuration":

| Pin | Signal | Betaflight note | DJI 3-in-1 cable, same pin ([O3 manual p.5](https://dl.djicdn.com/downloads/DJI_O3_Air_Unit/20230329/DJI_O3_Air_Unit_User_Manual_v1.0_EN.pdf), [O4 manual p.10](https://dl.djicdn.com/downloads/DJI_O4_Air_Unit_Series/UM/DJI_O4_Air_Unit_Series_User_Manual_v1.0_en.pdf)) |
|---|---|---|---|
| 1 | V+ | 8-26 V, "10V for V+ is preferred" | Red, power |
| 2 | GND | | Black, power GND |
| 3 | FC TX | | White, air-unit UART RX ("connects to FC OSD TX, 0-3.3 V") |
| 4 | FC RX | | Grey, air-unit UART TX ("connects to FC OSD RX") |
| 5 | GND | "(DJI)" | Brown, signal GND |
| 6 | SBUS | "(DJI)" | Yellow, DJI HDL ("connects to FC S.Bus, 0-3.3 V") |

The DJI cable is pin 1 to pin 1.

**Other notes from the standard:**
- It recommends a VTX regulator for "~18W, … at least a 9V/2A part, … 8-12V, preferably 10V".
- Version 2.0 (Aug 2026) **deprecated the 6-pin GPS connector**, because a GPS plugged into this VTX socket gets 8-26 V. Do not fit any other 6-pin SH socket on OG3.

### 1.2 Per system: cable, pin order, input range, power

| System | VTX input range | Power draw | Cable in the box, and fit | Sources |
|---|---|---|---|---|
| DJI O3 Air Unit | **7.4-26.4 V** | ~16 W max, "1.6 A at 10 V"; build for 17-18 W | "3-in-1 cable", 6-pin, pinout as above. Oscar Liang: "plug and play with flight controllers with the DJI 6-pin connector" (DJI's manual says to solder the other end) | [DJI O3 UM](https://dl.djicdn.com/downloads/DJI_O3_Air_Unit/20230329/DJI_O3_Air_Unit_User_Manual_v1.0_EN.pdf), [Oscar Liang O3](https://oscarliang.com/dji-o3-air-unit-fpv-goggles-2/) |
| DJI O4 Air Unit **Pro** | **7.4-26.4 V** | DJI: BEC ≥ **13.5 W (9 V/1.5 A)**; measured 1.16 A at 9 V (1.2 W RF) | 3-in-1 cable, 100 mm, same pinout as O3 ("unplug the O3 and plug in the O4") | [DJI O4 UM p.10-11](https://dl.djicdn.com/downloads/DJI_O4_Air_Unit_Series/UM/DJI_O4_Air_Unit_Series_User_Manual_v1.0_en.pdf), [DJI specs](https://www.dji.com/o4-air-unit/specs), [Oscar Liang O4 Pro](https://oscarliang.com/dji-o4-air-unit-pro/) |
| DJI O4 Air Unit (Lite) | **3.7-13.2 V** (VBAT on 4S-6S destroys it) | DJI: BEC ≥ **10 W (5 V/2 A)**; ~6 W measured (0.67 A at 9 V) | 3-in-1 cable, 50 mm, same pinout | same DJI UM, [Oscar Liang O4 Lite](https://oscarliang.com/dji-o4-air-unit-lite/) |
| Walksnail Avatar HD Pro / VTX V2 | **6-25.2 V** | not published | VTX has a **JST 1.0 4-pin** power/UART socket. The kit has a "4 Pin cable" (solder). CaddxFPV sells a separate **"VTX Connecting FC Cable 4PIN to 6PIN"** (5.6 cm) for V2/GT/Moonlight. **UNVERIFIED:** that cable's 6-pin order; the page gives no text pinout, and the community assumes DJI order | [Caddx Pro kit](https://www.caddxfpv.com/products/walksnail-avatar-hd-pro-kit), [VTX V2](https://www.caddxfpv.com/products/walksnail-avatar-hd-vtx-v2-only), [4-to-6 cable](https://www.caddxfpv.com/products/walksnail-vtx-connecting-fc-cable), [Oscar Liang](https://oscarliang.com/walksnail-avatar-hd-pro-v2-kit/) |
| Walksnail Moonlight | **7.4-25.2 V** | **1.4 A at 12 V, 2.2 A at 8 V (~17-18 W)**, the largest draw found | as V2 (4-pin socket) | [Caddx Moonlight](https://www.caddxfpv.com/products/walksnail-moonlight-kit) |
| Walksnail Mini 1S / "V3" VTX | 3.1-5 V / **3.1-13 V** | – | – | [Oscar Liang setup](https://oscarliang.com/setup-avatar-fpv-system/) |
| HDZero Race V3 | **4-12 V** ("up to 12V for FC's that include a HD VTX plug") | ~9 W at 200 mW. **UNVERIFIED:** from a search snippet of [Oscar Liang's review](https://oscarliang.com/hdzero-race-v3-vtx/); the page itself would not load | Pre-soldered harness for a "HD-ready FC": red BEC 4-12 V, black GND, white VTX TX → FC RX, yellow VTX RX → FC TX. HDZero: "**previous batches of VTX-R3 have different signal definitions** … requiring users to re-pin it"; the newest batch matches the Halo FC, which also takes O3/O4 | [HDZero Race V3](https://docs.hd-zero.com/race-v3), [product page](https://www.hd-zero.com/product-page/hdzero-race-v3-vtx), [Halo manual v1.4 p.6-8](https://cdn2.mantisfpv.com.au/wp-content/uploads/2025/08/HDZero_Halo_User_Manual_v1.4.pdf) (third-party host) |
| HDZero Freestyle V2 | **7-25 V** | **up to 15 W**. (The VTX manual says of Freestyle V1, same 15 W: "if the BEC provides 10V, it needs a minimum of 1.5A") | 7-pin socket on the VTX. Harness: black GND, red power, yellow RX → FC TX, white TX → FC RX, blue SmartAudio (optional). **UNVERIFIED:** whether the harness end is DJI-order SH-6 | [HDZero Freestyle V2](https://docs.hd-zero.com/freestyle-v2), [HDZero VTX manual v0.7](https://m.xcopter.com/download/HDZero_VTX_UserManual_v0.7.pdf) (third-party host) |

HDZero's manual adds: "All the FCs that include an integrated BEC for DJI VTXes should also work for HDZero VTXes", and "All HDZero VTXes, except Freestyle V1 Batch 2 or later and Freestyle V2, do not support 6S VBAT."

### 1.3 VBAT or a regulated rail: regulated 9 V (10 V option)

**Why not VBAT at 6S (25.2 V max)?**
- It exceeds the O4 Lite (13.2 V), HDZero Race V3 (12 V) and Walksnail V3 (13 V) ratings.
- It is 95 % of the O3 and O4 Pro rating (26.4 V) and 100 % of the Walksnail V2 rating (25.2 V), before any motor transients.
- Betaflight's standard: "the use of VBAT direct to VTXs or cameras is discouraged".

**9 V or 10 V?**
- **9 V** is inside every range above. It is DJI's own example ("9 V/1.5 A"), and HDZero's own FC uses a "switchable 9V/3A BEC" ([Halo manual](https://cdn2.mantisfpv.com.au/wp-content/uploads/2025/08/HDZero_Halo_User_Manual_v1.4.pdf)).
- 9 V keeps regulating on 3S down to about 9.5-10 V input. A 10 V rail drops out through most of a 3S flight.
- **10 V** is Betaflight's preference, and gives lower current and more margin above the 7.4 V minimum of the O3, O4 Pro and Moonlight. On OG3 it is one feedback resistor away (§3).

**If the 60 % rule is applied to the VTX ratings too:**
- 9 V is 34-36 % of the rating for the O3, O4 Pro, Walksnail V2/Moonlight and Freestyle V2.
- It is 68 % for the O4 Lite, 69 % for the Walksnail V3 and 75 % for the HDZero Race V3. 10 V gives 76 %, 77 % and 83 %.
- No single rail can be both ≤ 60 % of 12 V (7.2 V) and above the 7.4 V minimum of the O3/O4 Pro. 9 V is the best compromise. This is my judgement.

**On 2S:** a buck cannot make 9 V. The rail runs in dropout at about VBAT minus a few hundred mV; the LM76003 can run up to 95 % duty. That can fall below the 7.4 V minimum of the O3 and O4 Pro late in a 2S pack. Recommend low-voltage VTXs (O4 Lite, Race V3, Walksnail V3) for 2S builds.

---

## 2. Analog video: camera in, VTX out, OSD

### 2.1 The chip

**AT7456E:** maker **杭州中科微电子有限公司, Hangzhou Zhongke Microelectronics Co., Ltd., China**. This is from the datasheet header, AT7456E-S402-V1.1, served by LCSC. LCSC lists the brand as "ZHONGKEWEI".
- The datasheet says it is MAX7456-compatible "but applications need some adjustments" (512 characters and the CA[8] bit).
- **Betaflight detects the AT7456E itself**: `max7456Init()` writes CMAL bit 6 and reads it back to tell AT7456E from MAX7456 ([drivers/max7456.c](https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/drivers/max7456.c)).

| Part | LCSC | LCSC stock | LCSC price 1 / 100 / 1000 | DigiKey | Mouser |
|---|---|---|---|---|---|
| AT7456E, HTSSOP-28-EP | [**C82351**](https://www.lcsc.com/product-detail/C82351.html) | **35,480** | $3.46 / $1.86 / $1.71 | Bare IC **not listed**. Only a DFRobot breakout, DFR0515 (1738-1390-ND, 37 in stock, $9.90) ([search](https://www.digikey.com/en/products/result?keywords=AT7456E)) | **UNVERIFIED** (503). [Findchips](https://www.findchips.com/search/AT7456E) shows only brokers (Win Source, Chip Stock) |
| AT7456ELAH, LGA-16 4×6.8 | [C42388749](https://www.lcsc.com/product-detail/C42388749.html) | 116 | $3.14 / $2.06 / $1.88 | – | – |
| MAX7456EUI+(T) (ADI/Maxim) | not on LCSC (JLC lists MAX7456EUI, C5346361, stock 0) | 0 | – | **MAX7456EUI+T: "Product Status: Obsolete", "no longer manufactured"** ([DigiKey](https://www.digikey.com/en/products/detail/analog-devices-inc-maxim-integrated/MAX7456EUI-T/1703848)). EUI+: "Not Available", 0 | [Findchips](https://www.findchips.com/search/MAX7456EUI): DigiKey 0, brokers only (Win Source $75-89) |

**MAX7456 status:** EOL/obsolete per DigiKey. ADI's own lifecycle page was **not reachable** (analog.com 503), so ADI's exact wording (Obsolete or Last Time Buy) is **UNVERIFIED**.

### 2.2 Reference circuit

Sources: MAX7456 datasheet Fig. 1 and Fig. 2 ([mirror](https://cdn.sparkfun.com/assets/6/d/7/b/a/MAX7456.pdf); [ADI URL](https://www.analog.com/media/en/technical-documentation/data-sheets/max7456.pdf)) and the AT7456E datasheet. The HTSSOP-28 pin numbers are the same on both chips.

**Supplies: DVDD (3), AVDD (21), PVDD (24).**
- Use **3.3 V**, from `+3V3` through a 0402 ferrite bead (about 600 Ω at 100 MHz) with 10 µF of bulk after it.
- Put 100 nF at each supply pin (both datasheets: "Bypass to DGND/AGND/PGND with a 0.1 µF capacitor").
- Solder the exposed pad to GND.
- Why 3.3 V:
  - (a) PB14 is `TT_a` with a 4.0 V absolute maximum (STM32G473 DS12712 Rev 3, Table 12 and the voltage table). A 5 V SDOUT would overdrive it.
  - (b) SPI2 MISO is shared with the flash, whose I/O limit is VCC + 0.4 V.
  - (c) 60 % rule: 3.3 V is 55 % of the chip's 6 V absolute maximum; 5 V would be 83 %.
  - (d) The AT7456E is specified from 3.15 V to 5.25 V on all three supplies.
- Catch: the datasheet's typical video figures (PSRR and others) are quoted at 5 V. Check output amplitude and sync on the bench (bring-up item). The MAX7456 fallback is lost at 3.3 V (it needs 4.75-5.25 V), but it is obsolete anyway.

**Clock:** a **27 MHz parallel-resonant fundamental crystal** between CLKIN (5) and XFB (6).
- MAX7456 datasheet: "No external load capacitors are needed. All capacitors required for the Pierce oscillator are included on-chip."
- The AT7456E datasheet does not say. Place two DNP 0402 load-cap footprints to be safe.
- Or drive CLKIN from a 27 MHz clock and leave XFB open.
- Non-Chinese option: **Epson X1E0000210158**, 27 MHz, 10 pF, 40 Ω, 3225. LCSC [C91748](https://www.lcsc.com/product-detail/C91748.html), 4,565 in stock, $0.27 / $0.16 (500). **DigiKey: UNVERIFIED**; this Epson internal code does not search at DigiKey.
- Alternative: NDK NX3225GA-27MHz-STD-CRG-2, LCSC C481398, 2,505 in stock, 8 pF. Not found at DigiKey.

**Video in (VIN, 22):** camera → **75 Ω to GND** (termination) → **0.1 µF series** → VIN.
- "Must be AC-coupled with a 0.1 µF capacitor … internally clamped"; 0.1 µF sets the specified line-time distortion.

**Video out (VOUT 26 / SAG 25):**
- Simplest, per the datasheet's "one standard video load, DC-coupled" test circuit: **tie SAG to VOUT** ("connect to VOUT if not used") and feed the VTX video pad through a **75 Ω series back-termination resistor**.
- Datasheet Fig. 2 alternative: a series output capacitor with SAG correction, COUT/CSAG = 47 µF/47 µF or 22 µF/22 µF (Table 2). Not needed for FPV VTX inputs.

**Other pins:**
- RESET (19): 10k to 3.3 V.
- HSYNC, VSYNC, LOS (open-drain) and CLKOUT: leave unconnected. Betaflight does not use them.

**SPI:**
- SCK = PB13, SDIN ← PB15 (MOSI), SDOUT → PB14 (MISO), CS = **PA8**.
- Put a 10k pull-up on CS so the OSD stays off the shared MISO while the MCU boots.
- The AT7456E runs SPI up to **10 MHz**. Betaflight's driver uses `MAX7456_MAX_SPI_CLK_HZ 10000000` and gives each device on the bus its own divider, so sharing SPI2 with the flash is fine.
- The stock `TAKERG4AIO` does exactly this: `MAX7456_SPI_INSTANCE SPI2`, `MAX7456_SPI_CS_PIN PA8` ([config.h](https://github.com/betaflight/config/blob/master/configs/GEPR/TAKERG4AIO/config.h)).

**Connectors (Betaflight standard, all JST-SH):**
- **Camera:** 3-pin `5V · GND · Video` (4-pin adds TX for camera control).
- **Analog VTX:** 5-pin `V+ (8-12 V, 10 V preferred) · GND · Video · RX · TX`. Feed V+ from the same 9-10 V rail.
- JST SH 5-pin: `SM05B-SRSS-TB(LF)(SN)`, C136657, 3,155 in stock. 3-pin: `SM03B`, C160403, 24,745 in stock.

### 2.3 Betaflight configuration (G47x custom config)

In a `CONFIG=` build, `USE_MAX7456` is **not** added by `common_pre.h` (that default sits inside `#if !defined(USE_CONFIG)`), so the config must define it. `USE_OSD`, `USE_OSD_SD`, `USE_OSD_HD`, `USE_VTX`, `USE_PINIO` and `USE_MSP_DISPLAYPORT` come in automatically for a non-cloud build ([common_pre.h](https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/target/common_pre.h)).

Proposed additions to `configs/CHEAPDRONE_G473/config.h`. **This has not been compiled.**

```c
// Analog OSD: AT7456E (MAX7456-compatible) on SPI2, shared with the blackbox flash
#define USE_MAX7456
#define MAX7456_SPI_INSTANCE    SPI2
#define MAX7456_SPI_CS_PIN      PA8          // same as stock TAKERG4AIO

// HD VTX on UART1 (6-pin HD connector). Sets functionMask = FUNCTION_VTX_MSP | FUNCTION_MSP (io/serial.c)
#define MSP_DISPLAYPORT_UART    SERIAL_PORT_USART1

// VTX 9 V rail on/off: PB5 drives an N-FET that pulls the LM76003 EN low. Output low = VTX on (default).
#define PINIO1_PIN              PB5
#define PINIO1_CONFIG           1            // PINIO_CONFIG_MODE_OUT_PP (129 = inverted)
#define PINIO1_BOX              40           // permanent ID of BOXUSER1: USER1 switch = VTX power OFF

// Analog camera OSD-menu control (TIM4_CH4). USE_CAMERA_CONTROL turns on automatically (common_post.h)
#define CAMERA_CONTROL_PIN      PB9
// add to TIMER_PIN_MAPPING:   TIMER_PIN_MAP( 5, PB9 , 2, -1)   // PB9 occurrence 2 = TIM4_CH4

// 6S battery divider 30k / 2k (ratio 16)
#define DEFAULT_VOLTAGE_METER_SCALE 160
```

**Where each line comes from:**
- `pg/max7456.c` takes `MAX7456_SPI_CS_PIN` and `MAX7456_SPI_INSTANCE`.
- `pg/pinio.c` and `pg/piniobox.c` take `PINIOx_PIN`, `_CONFIG` and `_BOX`. `PINIO_CONFIG_OUT_INVERTED` is `0x80` and `PINIO_CONFIG_MODE_OUT_PP` is `0x01` (`drivers/pinio.h`). `BOXUSER1` has `permanentId = 40` (`msp/msp_box.c`).
- `drivers/camera_control.c` takes `CAMERA_CONTROL_PIN`. `common_post.h` turns `USE_CAMERA_CONTROL` on when `CAMERA_CONTROL_PIN` and `USE_VTX` are both defined.
- `sensors/voltage.c` takes `DEFAULT_VOLTAGE_METER_SCALE` (default 110).
- **Timer check:** in Betaflight's G4 timer table, PB9's entries in order are TIM17_CH1, **TIM4_CH4**, TIM8_CH3, TIM1_CH3N, so occurrence 2 is TIM4_CH4. Motors use TIM2/TIM5 and the LED strip uses TIM8_CH1 (PB6, occurrence 3), so TIM4 is free ([timer_stm32g4xx.c](https://github.com/betaflight/betaflight/blob/2025.12.5/src/platform/STM32/timer_stm32g4xx.c)).

**Runtime note for HD users.** With `osd_displayport_device = AUTO`, `fc/init.c` tries the MAX7456/AT7456E first, so a board with the chip fitted would drive the analog OSD, not the DJI.
- `vcd_video_system = HD` forces MSP DisplayPort (`if (vcdProfile()->video_system == VIDEO_SYSTEM_HD) device = OSD_DISPLAYPORT_DEVICE_MSP`, [init.c](https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/fc/init.c)).
- Put `set vcd_video_system = HD` in the HD section of `cli-setup.txt`.

---

## 3. Power rails under the 60 % rule (6S, 25.2 V)

**Rejected:**
- TI LMR51420 (v1, **36 V**) and Diodes AP64350 (**40 V**): below 42 V.
- TI LMR36520 (65 V, 2 A): fixed **400 kHz** only (datasheet orderable table), which needs a 15-22 µH inductor. Too large for this board.
- Diodes AP66300 and AP66200: LCSC 0 and 7 in stock.
- ADI MAX17504 (60 V, 3.5 A, sync): LCSC 12,000, but **DigiKey 0** (2,500 due 20 Nov 2026). A good second source once back.
- MPS MP4572/MP4576: not on LCSC.

### 3.1 Recommendation summary

| Rail | Part (maker, country) | Vin rating (25.2 V = %) | Iout rating (load = %) | LCSC (stock; $1 / 100 / 1000) | DigiKey (stock; $1 / 100 / 1000) |
|---|---|---|---|---|---|
| **5 V** | **TI LMR38020FDDAR** (US). F = forced PWM (constant frequency, good for analog video) | 80 V op / 85 V abs max (**31 %**) | 2 A. Allowed load is **1.2 A** at 60 % | [**C5149193**](https://www.lcsc.com/product-detail/C5149193.html): 7,701; $1.20 / $0.75 / $0.67 | 296-LMR38020FDDARCT-ND: **155**; $4.02 / $2.51 / $2.22 ([DigiKey](https://www.digikey.com/en/products/result?keywords=LMR38020FDDAR)) |
| **9 V** (10 V option) | **TI LM76003** (US), WQFN-30 4×6 | 60 V op / 65 V abs max (**42 %**) | 3.5 A. **2.0 A = 57 %** | RNPR [**C470958**](https://www.lcsc.com/product-detail/C470958.html): 3,452; $3.14 / $2.04 / $1.84. (RNPT C2071132: 2) | **RNPT** 296-…: **938**; $6.26 / $4.04 / – ([DigiKey](https://www.digikey.com/en/products/result?keywords=LM76003RNPT)). RNPR 296-49740-1-ND: 0 (3,000 due 17 Dec 2026); $5.31 / $3.39 / $3.25 |
| Inductor (both rails) | **Vishay IHLP2525CZER6R8M01** (US), 6.8 µH, 6.47 × 6.86 mm | – | Isat **8 A**, heat-rating current **4.5 A**, DCR 54/60 mΩ ([datasheet](https://www.lcsc.com/product-detail/C506575.html)) | [**C506575**](https://www.lcsc.com/product-detail/C506575.html): 3,070; $0.53 / $0.32 / $0.25 | **541-1011-1-ND: 27,790**; $1.13 / $0.77 / $0.63 |

**Stocked fallbacks at both distributors** (asynchronous, so each needs an external 60 V Schottky; less efficient and more area):
- Richtek **RT6363GSP** (Taiwan), 60 V, 3.5 A. LCSC [C3020076](https://www.lcsc.com/product-detail/C3020076.html): 23,538; $0.89 / $0.58 / $0.44. DigiKey 1028-RT6363GSPCT-ND: 2,570; $4.23 / $2.66.
- ST **L7987TR**, 61 V, 3 A. LCSC [C2832776](https://www.lcsc.com/product-detail/C2832776.html): 2,771; $1.83 / $1.21 / $1.10. DigiKey 497-18710-1-ND: 3,322; $3.50 / $2.17.
- TI **TPS54360BDDAR**, 60 V, 3.5 A. LCSC [C524806](https://www.lcsc.com/product-detail/C524806.html): 59,975; $0.76 / $0.47 / $0.44. DigiKey: 136.

**Smaller 5 V inductor option:** TDK **SPM5030T-4R7M-HZ** (Japan), 5.2 × 5.0 mm, 4.7 µH.
- TDK datasheet: Isat 4.0 A. DigiKey lists "Saturation Current 3 A".
- The LMR38020's high-side current limit is up to 3.8 A, so this part is marginal.
- LCSC [C435271](https://www.lcsc.com/product-detail/C435271.html): 1,051; $0.46 / $0.28 / $0.23. DigiKey 445-180097-1-ND: 500; $1.49 / $1.01.

**Why these two ICs:**
- Both are synchronous with integrated FETs, adjustable to about 1 MHz, and made by TI.
- The LMR38020's **80 V** rating leaves the 53 V TVS clamp at 63 % of its absolute maximum.
- The LM76003 is the only synchronous ≥ 3 A, ≥ 42 V buck found in stock at both distributors. Its 3.5 A rating keeps the 18 W VTX load at 57 %.

### 3.2 5 V reference design: LMR38020FDDAR

Source: [datasheet SNVSC40E](https://www.ti.com/lit/ds/symlink/lmr38020.pdf), Tables 8-1 and 9-1.

- **VIN (pin 3):**
  - 1× **10 µF 50 V X7R 1210**, Taiyo Yuden **UMK325AB7106KM-T**. LCSC [C386167](https://www.lcsc.com/product-detail/C386167.html): 6,801; $0.50 / $0.31 / $0.28. DigiKey 587-3167-1-ND: 180,329 ($0.95).
  - Plus **100 nF 100 V X7R 0603**, Murata **GRM188R72A104KA35D**. LCSC [C77058](https://www.lcsc.com/product-detail/C77058.html): 61,032. DigiKey 490-3285-1-ND: 735,979.
  - Rule check: 25.2 V is 50 % of 50 V. TI asks for "at least the maximum input voltage … preferably twice", which is met at 50 V.
  - Do not use the Samsung CL31B106KBHNNNE: DigiKey is out of stock and backordered.
  - Do not use the v1's 0805 part (C2932476): LCSC has 0 today.
- **EN (pin 2):**
  - Tie to VIN (allowed: "Can be connected directly to VIN").
  - Or use a UVLO divider for about 5.5 V, so the buck stays off while USB back-feeds VBAT (§7 note).
- **RT (pin 4):** **25.5 kΩ → 1.0 MHz** (Table 8-1).
  - Minimum on-time is 131 ns max. At 25.2 V the on-time is 198 ns, so no foldback in normal flight.
- **FB (pin 5):** RFBT **100 kΩ**, RFBB **24.9 kΩ** → **5.02 V** (VREF = 1.000 V ±1.5 %). This matches TI's own 5 V entry.
  - 24.9k: 0402WGF2492TCE, C25874.
  - 100k: C25741, already in the BOM.
- **BOOT to SW (pins 7-8):** 100 nF (C307331 in the BOM, 50 V).
- **L:** 6.8 µH IHLP-2525CZ.
  - Ripple at 25.2 V in: (25.2 − 5) × (5 / 25.2) / (6.8 µH × 1 MHz) = **0.59 A**, which is 30 % of 2 A.
  - Isat 8 A is above the 3.8 A maximum high-side limit, as TI asks.
- **COUT:** 3× 22 µF 25 V X5R 0805 (CL21A226MAQNNNE, C45783, in the BOM). TI's 1 MHz / 5 V row gives 2 × 22 µF nominal and 2 × 15 µF minimum effective. 5 V is 20 % of 25 V.
- **Estimated loss at 1.2 A** (my calculation, not measured): about 0.4-0.5 W, a junction rise of about 20 °C at RθJA 42.9 °C/W.

### 3.3 9 V reference design: LM76003

Source: [datasheet SNVSAK0A](https://www.ti.com/lit/ds/symlink/lm76003.pdf), §8.2.2 and Table 2.

- **PVIN (pins 20-22):** 2× UMK325AB7106KM-T (10 µF 50 V 1210), plus 100 nF 100 V 0603 at the pins. TI: "10 μF to 22 μF … plus 47 nF" high-frequency.
- **EN (18), UVLO plus switch:**
  - RENT **100 kΩ** from VIN, RENB **24.9 kΩ** to GND → turns on at 1.204 × (1 + 100/24.9) = **6.04 V**.
  - The EN node sits at 5.0 V at 25.2 V in (EN absolute maximum is VIN + 0.3 V).
  - An **AO3400A** (AOS, US; C20917, the same part as the beeper switch) from EN to GND, gate from **PB5** through 100 Ω, with 100k gate pull-down. The VTX is on by default; USER1 turns it off.
  - The UVLO also stops the VTX starting on USB power, when VBAT is back-fed to about 4 V.
- **RT (10):** RT = 38400 / f − 14.33 kΩ. **24.3 kΩ → 994 kHz** (0402WGF2432TCE, C26969).
  - At 25.2 V the on-time is 357 ns; the minimum is 95 ns max.
- **FB (12):**
  - RFBT **100 kΩ**, RFBB **12.4 kΩ** (C11692) → **9.1 V** (VFB 1.006 V typ).
  - **10 V option:** RFBB **11.0 kΩ** (C25749, in the BOM) → 10.1 V.
  - Keep a footprint for CFF across RFBT (TI's example used 47 pF C0G).
- **Small parts:**
  - CBOOT (6 to SW): **470 nF ≥ 6.3 V X7R**.
  - VCC (8): **2.2 µF 10 V**.
  - BIAS (9): **to VOUT**, which TI recommends for 3.3-18 V outputs, with **1 µF**.
  - SS/TRK (11): open (6.3 ms soft start).
  - **SYNC/MODE (17): to VCC** for forced PWM, "constant switching frequency over load". This keeps ripple at a fixed 1 MHz for analog video.
  - PGOOD (16): 100k to 3.3 V; optionally route it to PC4.
  - EP: GND with thermal vias.
- **L:** 6.8 µH IHLP-2525CZ.
  - Ripple at 25.2 V in: (25.2 − 9) × 0.357 / 6.8 = **0.85 A**, which is 24 % of 3.5 A.
  - Peak at 2 A load is 2.43 A, 30 % of the 8 A Isat. TI: "inductor current rating should be higher than the HS current limit" (6.8 A max): met.
- **COUT:** 3-4× 22 µF 25 V 0805 (9 V is 36 % of 25 V). TI's table gives 22 µF effective at 12 V / 1 MHz and 66 µF at 5 V / 1 MHz; about 30 µF effective suits 9 V. **Check with WEBENCH or on the bench.**
- **Estimated loss at 18 W** (my calculation): about 0.5-0.7 W in the IC plus 0.22 W in the inductor. Junction rise about 20 °C at RθJA 29.6 °C/W.

### 3.4 Budget

**5 V rail** (≤ 1.2 A under the rule): MCU and sensors through the LDO (about 0.2 A), receiver (about 0.1-0.15 A), analog camera (about 0.2 A), LED strip, buzzer and GPS.
- That is about 1 A worst case, so the 2 A LMR38020 fits.
- If the 5 V load must reach 2 A, use a second LM76003 at 5 V: RFBB **25 kΩ** (TI table; use 24.9k), L 3.3-4.7 µH.

**9 V rail:** 2 A continuous (Moonlight about 2 A, O3 about 1.8 A, Freestyle V2 about 1.7 A at 9 V).

---

## 4. Robust input: TVS, capacitance, battery divider

**TVS on VBAT:** Littelfuse (US) **SMAJ33A** (SMA, 400 W).
- VRWM 33 V, VBR min **36.7 V**, VC **53.3 V at 7.5 A**.
- LCSC [**C223988**](https://www.lcsc.com/product-detail/C223988.html): 11,565; $0.13 / ~$0.09 (500) / $0.08 (2,500).
- DigiKey **SMAJ33ALFCT-ND: 45,107**; $0.47 / $0.18 (100).
- Larger option: SMBJ33A, 600 W, VC 53.3 V at 11.3 A. LCSC [C224019](https://www.lcsc.com/product-detail/C224019.html): 5,310. DigiKey 4,968 ($0.50).
- Against the 60 % rule:
  - At 25.2 V the TVS is at 76 % of its standoff and 69 % of its minimum breakdown. It does not conduct; that is a leakage figure, not a stress rating.
  - A 43 V-standoff part (SMAJ43A) would meet 60 % of standoff, but it clamps at about 69 V, above the LM76003's 65 V absolute maximum. The 33 V part is the right trade.
  - The clamp at 53.3 V is **63 %** of the LMR38020's 85 V absolute maximum and **82 %** of the LM76003's 65 V, for microseconds only. My judgement; it is the one place the 60 % rule cannot hold with a 60 V converter.
  - An 80 V 3 A-class 9 V part would remove the exception. None was found in stock at both distributors.

**Input capacitance on the FC:**
- 3× 10 µF 50 V X7R 1210 (UMK325AB7106KM-T) and 2× 100 nF 100 V 0603 (GRM188R72A104KA35D), as in §3.2-3.3.
- 50 V ceramics at 25.2 V lose about half their capacitance to DC bias; expect about 5 µF effective each. This is an estimate; check the Taiyo Yuden curve.
- **Bulk capacitance belongs at the battery pads (ESC side).** README's "470 µF **35 V**" is only 72 % loaded at 6S (fails the rule). A 6S stack needs **≥ 50 V** low-ESR, e.g. 470 µF 50 V. This also means a 6S ESC.

**Power entry:**
- The ESC lead's VBAT contact (JST SH, 1 A) cannot feed an 18 W VTX rail. Estimated FC input (23 W load, 88 % efficiency, sagged pack) is 1.3 A at 6S, 2 A at 4S, 2.7 A at 3S and about 4 A at 2S.
- Add **VBAT/GND solder pads** for 20-22 AWG from the battery pads.
- Consider leaving stack pin 1 off the power net, as a sense connection only, so the SH contact never carries the rail current. This is a design choice.
- Betaflight v2.1 also allows a JST-**PH** 2-pin "ext. power" socket, rated about 2 A, which is still too little at 2S.

**Battery divider:** top **30 kΩ**, bottom **2 kΩ**, ratio 16. Keep the 100 nF filter; τ = 1.875 kΩ × 100 nF = 0.19 ms.
- At 25.2 V: 1.575 V at PB2, which is 48 % of the 3.3 V reference and 39 % of PB2's `TT_a` 4.0 V absolute maximum.
- At the 53.3 V clamp: 3.33 V, below 4.0 V.
- The 30k dissipates 23.6² / 30k = **18.6 mW**, 30 % of 1/16 W, with 23.6 V across it (47 % of the 50 V 0402 working voltage).
- **Firmware:** `vbat_scale = 160`, i.e. `#define DEFAULT_VOLTAGE_METER_SCALE 160`. Betaflight's result is ADC × vbatscale × Vref / … / `vbat_divider` (default 10), so the scale is 10 × the ratio ([voltage.c](https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/sensors/voltage.c)). `vbat_scale` is a uint8 with a maximum of 255 (`VBAT_SCALE_MAX`).
- **Parts:**
  - 30k: 0402WGF3002TCE, C25776, 41,500 at LCSC. Or Yageo RC0402FR-0730KL, DigiKey 311-30.0KLRCT-ND, 1,197,319.
  - 2k: C4109, in the BOM.
- **Why the v1 10k/1k divider fails at 6S:** the 10k dissipates 22.9² / 10k = **52 mW = 84 %** of 1/16 W. It would also put 4.85 V on PB2 at a 53 V clamp, above the 4.0 V absolute maximum.

---

## 5. STM32G473CEU6 pins

**How the pins were checked:**
1. **KiCad symbol library** at `/usr/share/kicad/symbols/MCU_ST_STM32G4.kicad_sym` (KiCad 10). `STM32G473CEUx` extends `STM32G473C_B-C-E_Ux`, whose pins list each pin's alternate functions. `verify.py` already uses this library for v1. Full dump: `research/g473_pins.txt`.
2. **ST datasheet DS12712 Rev 3** (via LCSC): Table 12 (UFQFPN48 column; PC4 exists only in this package, pin 16, which matches `circuit.py`), I/O structure, and Table 13 (alternate functions, e.g. PB9 AF2 = TIM4_CH4, PB5 AF2 = TIM3_CH2).
3. **Betaflight 2025.12.5** UART and timer tables.

**Free pins in v1:** PC13, PC14, PC15, PC4, PB10 (LPUART1_TX is defined in config but not wired), PB12, PA8, PB5, PB9.

| Function | Pin (UFQFPN48 #) | Checked against | Notes |
|---|---|---|---|
| OSD SPI | **SPI2**: PB13 SCK (26), PB14 MISO (27), PB15 MOSI (28) | KiCad: SPI2_SCK/MISO/MOSI | Shared with the flash, as on stock TAKERG4AIO. SPI3 is not usable: its pins are UART2 and UART4. PB14 is `TT_a`, so the OSD runs at 3.3 V |
| OSD CS | **PA8** (30) | GPIO; `FT_a` | Stock TAKERG4AIO's `MAX7456_SPI_CS_PIN`. Alternative: PB12 (25, SPI2_NSS, `TT_a`) |
| VTX 9 V on/off (PINIO1) | **PB5** (43) | GPIO; `FT_f`; alternates SPI1/3_MOSI, TIM3_CH2, TIM17_CH1, TIM8_CH3N (all unused) | Drives the AO3400A on LM76003 EN. Not PC13-15: DS12712 note 2 says they "sink a limited amount of current (3 mA) … speed should not exceed 2 MHz … must not be used as current sources" |
| Camera control | **PB9** (47) | TIM4_CH4 (AF2), `FT_f`; Betaflight timer occurrence 2 | TIM4 is otherwise unused |
| HD VTX UART (MSP DisplayPort) | **UART1: PA9 TX (31), PA10 RX (32)** | USART1 native in the KiCad list and Betaflight's G4 table | The v1 "spare" UART1 pads move to the HD connector. The analog VTX connector's RX/TX (SmartAudio/Tramp) share UART1; you fit one VTX or the other. **UART4 (PC10/PC11)** stays for GPS |
| DJI SBUS/HDL (pin 6) | Solder jumper (default **open**) to **R2 = PB4** (UART2 RX) | – | UART2 is the ELRS receiver. Close only when using a DJI radio instead |
| Spare | PC4 (16, ADC2_IN5, `FT_fa`), PB10 (22), PB12 (25), PC13-15 | – | Optional: PC4 to LM76003 PGOOD or a 9 V rail monitor |

**Checked on the way, not a bug:** v1 defines `LPUART1_TX_PIN PB10` / `LPUART1_RX_PIN PB11`, but on G4 LPUART1's native RX is PB10 and TX is PB11 (KiCad; Betaflight `serial_uart_stm32g4xx.c`). It still works: Betaflight 2025.12.5 sets `UART_TRAIT_PINSWAP` for G4 and swaps the pins when a configured TX pin matches a hardware RX pin ([serial_uart_pinconfig.c](https://github.com/betaflight/betaflight/blob/2025.12.5/src/platform/common/stm32/serial_uart_pinconfig.c), `platform.h`). The ESC telemetry line on PB11 is fine. It is also USART3_RX (AF7), should that ever be preferred.

---

## 6. Flash

Winbond Electronics Corp. is headquartered in Taiwan.

| Part | JEDEC ID | Betaflight | LCSC | DigiKey |
|---|---|---|---|---|
| W25Q128JV**PIQ** (WSON-8 6×5) | EF 40 18 | in the m25p16 table (104 MHz) | [C190862](https://www.lcsc.com/product-detail/C190862.html): **0 in stock**; $3.60 / $2.66 / $2.19 | 256-W25Q128JVPIQ-TUBE-ND: **13,187**; $3.93 / $3.40 / $3.13 ([DigiKey](https://www.digikey.com/en/products/detail/winbond-electronics/W25Q128JVPIQ/6819668)). The TR version is out |
| **W25Q128JVPIM** (WSON-8 6×5, "JV-DTR") | **EF 70 18** (datasheet Rev C, from LCSC) | in the m25p16 table as "Winbond W25Q128_DTR" (66 MHz) | [**C2441427**](https://www.lcsc.com/product-detail/C2441427.html): **25,120**; $2.83 (10) / $2.55 / $2.21 | 256-W25Q128JVPIM-TUBE-ND: **18,536**; $4.24 / $3.66 / $3.37 ([DigiKey](https://www.digikey.com/en/products/detail/winbond-electronics/W25Q128JVPIM/6819719)) |

**Recommendation:** make **W25Q128JVPIM (C2441427)** the BOM default, with W25Q128JVPIQ as an equal second source on the same pads.
- The existing `#define USE_FLASH_W25Q128FV` pulls in the m25p16 driver (`common_post.h`), whose table has both 0xEF4018 and 0xEF7018 ([flash_m25p16.c](https://github.com/betaflight/betaflight/blob/2025.12.5/src/main/drivers/flash/flash_m25p16.c)). No firmware change is needed.
- Drop `USE_FLASH_PY25Q128HA` and the Puya part.
- Update the `README.md` second-source table: it names C190862, which is now at 0.

---

## 7. Other Chinese-made parts in the v1 FC, and replacements

The maker is as LCSC shows it; country is by headquarters.
- **UNI-ROYAL** (all 0402 resistors) is headquartered in Hsinchu, Taiwan, with plants in Kunshan (China) and Thailand ([LCSC brand page](https://www.lcsc.com/brand-detail/99.html); [company profile](https://www.uni-royal.cn/en/article.php?id=14)). It passes a headquarters test but is probably made in China. Yageo (Taiwan) is the drop-in if that matters.
- **Samsung** (Korea), **AOS** AO3400A (US), **ST**, **Bosch**, **TDK**, **JST** and **TI** parts are fine.

| v1 part (C#) | Maker, country | Replacement | LCSC (stock) | DigiKey (stock) | Changes |
|---|---|---|---|---|---|
| ME6211C33M5G-N LDO (C82942) | MICRONE (Nanjing), CN. **Also fails the rule:** 5.1 V in against its ~6 V limit | **TI TLV76733** (16 V in, 1 A, WSON-6 2×2): 5.1/16 = 32 %, 0.2/1 A = 20 % | DRVR [C2848334](https://www.lcsc.com/product-detail/C2848334.html): 16,465 ($0.27 / $0.17 at 500) | DRVR 0 (3,000 due 14 Dec 2026). **DRVT: 1,023** ($1.24). DRVT at LCSC is C2867572: 557 | Footprint (SOT-23-5 to WSON-6). About 0.36 W at 200 mA: check copper |
| TAXM8M4RDBCCT2T 8 MHz crystal (C400090) | **雅晶鑫 / Yajingxin (Shenzhen), CN** (datasheet header) | **KDS 1C208000CE0Q** (Japan), 8 MHz, **10 pF**, drop-in | [C133366](https://www.lcsc.com/product-detail/C133366.html): 5,200 | **not at DigiKey** | None |
| same | – | Both distributors: **Abracon ABM8AIG-8.000MHZ-1Z-T** (US), 8 MHz, **18 pF**, 4-pad 3225 | [C5140594](https://www.lcsc.com/product-detail/C5140594.html): 10,483 ($1.08 / $0.65 / $0.56) | listed ($1.21); **stock UNVERIFIED** | Load caps become 2 × (18 − 3) ≈ 27-30 pF. Check STM32 HSE gm margin (my estimate 1.1 mA/V with ESR 250 Ω, which is **UNVERIFIED**) |
| FXL0530-4R7-M BEC inductor (C177246) | cjiang (Changjiang), CN | **Vishay IHLP2525CZER6R8M01** (§3) | C506575: 3,070 | 541-1011-1-ND: 27,790 | New 6.9 × 6.5 footprint |
| KT-0603R red LED (C2286) | Hubei KENTO, CN | **Lite-On LTST-C191KRKT** (Taiwan) | [C125099](https://www.lcsc.com/product-detail/C125099.html): 202,580 | 160-1447-1-ND: 1,501,040 | None (0603) |
| XL-1608UBC-04 blue LED (C965807) | XINGLIGHT, CN | **Lite-On LTST-C191TBKT** | [C99290](https://www.lcsc.com/product-detail/C99290.html): 376,650 | 353,663 ($0.25) | None |
| 1N5819WS Schottky (C191023) | Guangdong Hottech, CN | **ROHM RB160VAM-40TR** (Japan), 40 V, 1 A, SOD-323HE | [C703624](https://www.lcsc.com/product-detail/C703624.html): 29,250 | RB160VAM-40CT-ND: 9,541 | SOD-323HE pads (near SOD-323). Or onsemi MBR0540T1G (0.5 A, SOD-123): C21353, 92,860; not checked at DigiKey |
| TYPE-C-31-M-12 USB-C (C165948) | "Korean Hroparts Elec" (a Shenzhen company), CN | **GCT USB4105-GF-A-120** (UK/US), 16 + 8 dummy, USB 2.0 | [C5184243](https://www.lcsc.com/product-detail/C5184243.html): 3,794 ($0.92 / $0.53) | 2073-USB4105-GF-A-120CT-ND: 50,551 ($0.80 / $0.57 / $0.42) | New footprint. Do **not** use Molex 2171750001: it is power-only (no D+/D−) |
| TS-1088-AR02016 button (C720477) | XUNPU, CN | **Omron B3U-1000P** (Japan), 3.0 × 2.5 mm | [C231329](https://www.lcsc.com/product-detail/C231329.html): 148,775 | SW1020CT-ND: 129,510 ($1.17 / $0.83 / $0.69) | New, smaller footprint. C&K PTS810 is out at LCSC |
| 0402CG120J500NT 12 pF (C1547) | FH (Fenghua), CN | **Samsung CL05C120JB5NNNC** | [C26406](https://www.lcsc.com/product-detail/C26406.html): 184,100 | 1276-1178-1-ND: 10,228 | None. Value changes if the 18 pF crystal is used |
| 2N7002 (C8545), listed in `parts.py` | CJ, CN | – | – | – | **Unused**: `circuit.py` uses the AO3400A. Remove it from `parts.py` |

**USB back-feed.** On USB alone, the synchronous 5 V buck's high-side body diode back-feeds VBAT (the v1 README notes this for the LMR51420). The LMR38020 has the same diode, so VBAT sits at about 4 V on USB. The 6.0 V EN-UVLO in §3.3 keeps the 9 V VTX rail off in this case.

---

## 8. Open items and risks (not verified here)

- **Board area.** OG3 adds two converters with 6.9 mm inductors, the AT7456E (HTSSOP-28, 9.7 × 6.4 mm), a 27 MHz crystal, the SMA TVS, three 1210 caps, and SH-6, SH-5 and SH-3 connectors. On a 33.8 mm board with parts on top only, that is unlikely to fit without bottom-side parts or a bigger board. Not measured.
- **Walksnail 4-to-6 cable and HDZero harness pin orders:** published only as pictures. Check with a meter before plugging in.
- **AT7456E at 3.3 V:** inside its datasheet range, but video typicals are quoted at 5 V. Scope VOUT at bring-up.
- **The AT7456E is the one remaining Chinese, single-source part**, and DigiKey and Mouser do not stock the bare IC. Betaflight's own standard now recommends putting the OSD on the VTX, not the FC. Consider shipping OG3 with the OSD as a DNP option.
- **Thermal and efficiency numbers** above are estimates from datasheet RDS(on), DCR and RθJA, not WEBENCH runs or measurements.
- **Mouser stock and ADI's own lifecycle status for the MAX7456:** not reachable (HTTP 503).
- **Not re-verified here:** the v1 stack's ESC side (4S only), including the 35 V bulk cap and 30 V FETs. OG3 on 6S needs a new ESC.

Working files (not deliverables): `research/lcsc.py` and `research/jlc.py` (stock lookups), `research/ds/*.txt` (datasheet text), `research/g473_pins.txt` (KiCad alternate-function dump).
