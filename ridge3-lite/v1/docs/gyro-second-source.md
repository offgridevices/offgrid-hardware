# Gyro second source: Bosch BMI270 on the ICM-42688-P land (U_IMU)

Checked 3 Oct 2026 against primary sources:

* TDK DS-000347 ICM-42688-P **rev 1.9** (from TDK's product page).
* Bosch BST-BMI270-DS000-08, **rev 1.6, March 2026**.
* Betaflight `master` @ 22fe2df84 (3 Oct 2026), and tags 2026.6.2 and 2025.12.5.
* betaflight/config, betaflight.com docs, and Betaflight PR #15484.

## Answer

* **Hardware: it works as wired. No net has to change.**
  * Pins 2, 3, 10 and 11 are left open. That is the only state both makers allow.
  * Pins 6 and 7 go to GND, and both parts allow that.
  * Pin 9 goes to GND. TDK requires that. Bosch asks for "DNC", but INT2's output is off at reset and Betaflight never turns it on, so GND is safe.
  * Supply and decoupling meet both datasheets.
* **Firmware: one auto-detecting hex cannot fly both parts the right way up.**
  * On these pads the BMI270's axes are turned 90 deg from the ICM's.
  * Betaflight has one alignment per gyro slot. On U_IMU at 135 deg:

    | Part | Custom yaw (board yaw 0) | Define |
    |---|---|---|
    | ICM-42688-P | 315 deg | `GYRO_1_ALIGN_YAW 3150` |
    | BMI270 | 225 deg | `GYRO_1_ALIGN_YAW 2250` |

  * Upstream's new `ENABLE_BMI270_ALIGN_AS_ICM` turns the BMI270 data by **CW90**. Both datasheets say the remap needs **CW270**. On this board the flag would therefore leave a BMI270 **180 deg off**, with roll and pitch reversed (details below).
  * Build **two targets, each with only one gyro driver**. If the wrong hex is flashed, no gyro is detected and the board will not arm. It cannot fly with the wrong orientation.

## 1. Pin maps

The two parts are wired to the same pads:

| Pin | ICM-42688-P (DS-000347 table 10) | BMI270 (DS000 table 22, 4-wire SPI column) | U_IMU net (circuit.py) | Both OK? |
|---|---|---|---|---|
| 1 | AP_SDO / AD0 | SDO | SPI1_MISO | yes |
| 2 | RESV: "No Connect or Connect to GND" | ASDx (aux SDA): "VDDIO or DNC". Note `**`: "**Do not connect to GND**" | open | yes, only while open |
| 3 | RESV: NC or GND | ASCx (aux SCL): VDDIO or DNC, not GND | open | yes, only while open |
| 4 | INT1 | INT1 | GYRO_INT (PA4) | yes |
| 5 | VDDIO | VDDIO | +3V3_GYRO | yes |
| 6 | GND | GNDIO | GND | yes |
| 7 | RESV: "Connect to GND" | GND | GND | yes |
| 8 | VDD | VDD | +3V3_GYRO | yes |
| 9 | INT2 / FSYNC / CLKIN: "Connect to GND if FSYNC not used" | INT2. Note `*`: unused, so "do not connect" | GND | see below |
| 10 | RESV: NC or GND | OCSB (OIS CS): "DNC" (may go to GND only if `IF_CONF.ois_en = 0`) | open | yes |
| 11 | RESV: NC or GND | OSDO (OIS SDO, output): DNC | open | yes |
| 12 | AP_CS | CSB | GYRO_CS (PB0) | yes |
| 13 | AP_SCLK | SCx | SPI1_SCK | yes |
| 14 | AP_SDI | SDx | SPI1_MOSI | yes |

**Pin 9 is the only pin where the two makers ask for different things.**

* The BMI270's `INT2_IO_CTRL` resets to 0x00: output off, input off (DS000 sect. 5.2.59).
* Betaflight's `accgyro_spi_bmi270.c` names `INT2_IO_CTRL` but never writes to it. It only writes INT1 (`INT1_IO_CTRL = 0x0A`, `INT_MAP_DATA` on INT1).
* So, in practice, GND on INT2 is a disabled pin tied low. Leave it as it is.
* If the next spin wants to meet both datasheets to the letter: pin 9 to GND through 10 kOhm (0201). That still holds FSYNC low, and it limits the current to 0.33 mA if INT2 were ever enabled.

**Rules for anyone editing circuit.py.**

* Do **not** tidy pins 2 and 3 to GND. TDK allows it, but Bosch forbids it.
* Do not tie pin 11 to anything.

**Package and land.**

* Both parts are LGA-14, 2.5 x 3.0 mm at 0.5 mm pitch, 14 pads, 0.25 x 0.475 mm pads.
  * ICM: D 2.5, E 3.0, L 0.475, W 0.25, 0.91 mm thick.
  * BMI270: 0.83 mm thick.
* The pin layout matches. In the top view, pin 1 is at the top-left corner, pads 1-4 run down a 2.5 mm side, and numbering runs counter-clockwise.
* The pin-1 mark is a dot on the ICM and a small rectangle on the BMI270. Both sit on the same corner.
* Bosch's recommended land (sect. 8.3): side pads start 0.925 mm from the centre, and end pads start 0.675 mm from the centre.
* `og.pretty/LGA-14_L3.0-W2.5-P0.50-TL` has 0.675 x 0.28 pads at +/-1.26 mm (sides) and +/-1.01 mm (ends). Their inner edges are at 0.9225 mm and 0.6725 mm, which is Bosch's land plus about 0.2 mm of toe. **The same footprint suits both.**
* **Assembly:** at JLC the two LCSC part numbers can carry different tape-rotation corrections. Check the pin-1 corner in the DFM/CPL preview for C2836813 on its own. Do not reuse the ICM's rotation offset.

## 2. SPI

The pins are identical: CS PB0, SCK PA5, MISO PA6, MOSI PA7, INT1 PA4.

| | ICM-42688-P | BMI270 |
|---|---|---|
| SPI modes | 0 and 3 (`DEVICE_CONFIG.SPI_MODE` = 0, the default; sect. 14.1) | 00 and 11, picked automatically from SCK at CSB falling (sect. 6.4) |
| Max SCK | 24 MHz | 10 MHz |
| Betaflight limit | `ICM426XX_MAX_SPI_CLK_HZ 24000000` | `BMI270_MAX_SPI_CLK_HZ 10000000` |
| Power-up interface | SPI | **I2C until CSB sees a rising edge** ("switches to SPI after 200 us", sect. 6.3). Reads start with a dummy byte |

Clocks and power-up:

* Betaflight sets each part's own SPI divider after detection.
* The STM32's power-of-two divider will put the BMI270 somewhat below 10 MHz. A 3.2 kHz read of about 14 bytes still takes only a small part of the 312 us period.
* For the BMI270's start in I2C mode, Betaflight's `bmi270EnableSPI()` pulses CS low for 1 ms, then high, then waits 10 ms before reading `CHIP_ID` (0x24). Nothing else is needed.
* SPI1 carries only the gyro (no flash), so nothing else on the bus can be upset while the BMI270 is still in I2C mode.

## 3. Betaflight

### Drivers

* `src/main/drivers/accgyro/accgyro_spi_bmi270.c` and `accgyro_spi_icm426xx.c` are both in master, 2026.6.2 and 2025.12.5.
* Betaflight probes every driver compiled into the build and keeps the first chip that answers (`mpuDetect`), so listing both drivers gives auto-detection.

### Alignment (the real problem)

Chip axes, top view, pin 1 top-left:

* **ICM-42688-P** (DS-000347 fig. 5 and fig. 16): +X points toward pins 8-11, +Y toward pins 12-14.
* **BMI270** (DS000 sect. 8.2): +X points toward pins 12-14, +Y toward pins 1-4. The output table confirms it: with the dot top-left, X reads +1 g.
* So `x_bmi = y_icm` and `y_bmi = -x_icm`. To get ICM axes from BMI data you need `(-y, x, z)`, which is Betaflight's **CW270** (`boardalignment.c`).

Independent evidence from hardware:

* ArduPilot's `TMotorH743/hwdef.dat` has both parts on one CS. It gives `bmi270 ROTATION_PITCH_180` and `icm42688 ROTATION_PITCH_180_YAW_90`.
* ArduPilot's drivers pass the raw axes through unchanged. Those two rotations work out to exactly the same relation.

`firmware/gyro_orientation_check.py` (pads taken from the footprint, Betaflight's maths ported) gives these yaws for U_IMU at 135 deg:

| Fitted part | Custom yaw that flies right (board yaw 0) |
|---|---|
| ICM-42688-P | **315** (`GYRO_1_ALIGN_YAW 3150`, current RIDGE3LITE) |
| BMI270, no remap | **225** (`GYRO_1_ALIGN_YAW 2250`), or stock-style CW180 + board yaw 45 |
| BMI270 with upstream `ENABLE_BMI270_ALIGN_AS_ICM 1` (CW90) | 135, which is **180 deg away from the ICM's 315** |
| BMI270 with a CW270 remap | 315 (would match the ICM) |

What upstream has done:

* PR #15484, merged 28 Jul 2026, is in 2026.6.1 and later. It is opt-in and global to the build.
* Its own description says: "CW90 vs CW270 still wants bench confirmation". The Betaflight docs (manufacturer guidelines 4.2.1.1) say the same.
* DAKE (9 boards, betaflight/config #1181) and `HDZERO_AIO15` already set the flag. The DAKE PR shows no bench evidence (the HDZERO PR was not checked).
* The docs also say the BMI270 is "no longer recommended due to calibration issues (drift)". It is accepted only as a second source on an ICM-42688-P footprint.

Real config targets that list both drivers on one `GYRO_1_CS` (one alignment):

* `BEFH/BETAFPVG473`: G474, `GYRO_1_ALIGN CW180_DEG`, no flag.
* `JHEF/JHEG474`: `CW90_DEG`, no flag.
* `GEPR/GEPRCF405`: `CW180_DEG`.
* `HDZO/HDZERO_AIO15`: `CW90_DEG_FLIP`, board yaw 135, and `ENABLE_BMI270_ALIGN_AS_ICM 1`.

117 configs in betaflight/config list both drivers. The usual practice is one alignment, with users fixing the second population in the CLI. That is not acceptable for a shipped RTF.

### Recommendation

Keep `RIDGE3LITE` as it is (ICM only, yaw 315). Add a second target, `RIDGE3LITEB`, for boards built from BMI270 reels:

```c
#define USE_ACC
#define USE_GYRO
#define USE_ACCGYRO_BMI270          // and NOT USE_*_SPI_ICM42688P
#define GYRO_1_ALIGN_YAW             2250   // BMI270 at U_IMU 135 deg, board yaw 0
#define DEFAULT_PID_PROCESS_DENOM    1      // 3.2 kHz gyro -> 3.2 kHz PID (denom 2 would give 1.6 kHz)
```

How this works out:

* Each hex compiles in one driver, so a mismatched flash shows "no gyro" and refuses to arm.
* Factory test still has to run the props-off Setup-tab check in `firmware/gyro-orientation.md`.

A single hex is possible only in one of two ways:

* (a) Patch the BMI270 remap to CW270 in our build and add `ENABLE_BMI270_ALIGN_AS_ICM 1`, then keep yaw 3150.
* (b) Fix it upstream after a bench test, then use the flag.

**Do not** add `USE_ACCGYRO_BMI270` to the current RIDGE3LITE, with or without the flag.

`docs/sourcing-10k.md` says "one hex covers both parts". That statement is wrong and should point here.

### Rate

| | BMI270 | ICM-42688-P |
|---|---|---|
| Gyro rate (`gyro_sync.c`) | 3.2 kHz (6.4 kHz only with the experimental unfiltered DLPF mode) | 8 kHz |
| Accelerometer rate | 800 Hz | — |
| PID loop | 3.2 kHz | 4 kHz (denom 2) |
| Gyro Nyquist | 1.6 kHz | 4 kHz |

What the lower rate means on a 3-inch:

* Motor fundamentals at up to about 40k RPM are around 670 Hz, so the RPM filter and dynamic notch still work.
* Higher harmonics and prop and frame resonances near or above 1.6 kHz alias down into the band, where the chip's own low-pass can only partly stop them.
* Expect slightly more filter delay and somewhat softer tune limits. It flies fine, as most mid-range quads have done, but it is a step down, not an equal part.
* Re-check the filter sliders and the blackbox on the BMI270 build before release.

## 4. Supply

`+3V3_GYRO` comes from TLV76733 3.3 V through 10 Ohm, with 4.7 uF + 100 nF + 100 nF. VDD and VDDIO are tied together.

| | ICM-42688-P | BMI270 | Board |
|---|---|---|---|
| VDD range | 1.71-3.6 V | 1.71-3.6 V | 3.3 V (about 10 mV drop at about 1 mA) |
| VDDIO range | 1.71-3.6 V | 1.2-3.6 V | 3.3 V |
| VDD caps | 0.1 uF + 2.2 uF X7R (table 11) | 100 nF (sect. 7.2) | 4.7 uF + 100 nF: met |
| VDDIO cap | 10 nF X7R | 100 nF | 100 nF: met. It is larger than TDK's 10 nF, which is fine on a shared node |
| Ramp | 0.01-3 ms monotonic | no slew-rate limit; 450 us POR | LDO soft start: OK |

Both parts are met.

## 5. Lifecycle and stock

* **Bosch's product page (read 3 Oct 2026):**
  * The BMI270 is listed as a current product, with datasheet, application notes and drivers.
  * It has no NRND, EOL or successor notice. The BMI323 is listed as a separate product, not as a replacement.
  * Bosch's own web shop shows "Out of Stock". Buy through distributors.
* **The datasheet** (rev 1.6, March 2026) is still being revised.
* **LCSC C2836813 (BMI270, Bosch, LGA-14 2.5x3):**
  * 1,122 in stock (`tools/lcsc.py`, 3 Oct 2026).
  * Price: US$2.87 @1, $1.50 @100, $1.38 @1k.
* **For comparison, C1850418 ICM-42688-P:**
  * 4,362 in stock.
  * LCSC now quotes it at $19.64 @1 and $15.60 @100. That price is far above the roughly $3 figure in `lifecycle.md`. Re-check the price before the next order.
* DigiKey and Mouser stock for the BMI270 is in `sourcing-10k.md`. I could not re-read DigiKey today (HTTP 403).
