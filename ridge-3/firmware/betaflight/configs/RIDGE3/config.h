/*
 * Betaflight target for the OffGrid Ridge 3 flight controller (ridge-3/fc).
 *
 * This file is part of Betaflight and is distributed under the terms of the
 * GNU General Public License v3 or later, like the rest of Betaflight.
 *
 * The pin map is the GEPRC TAKER G4 AIO's (Betaflight target GEPR/TAKERG4AIO),
 * minus the baro and magnetometer, plus a switch for the video transmitter's
 * 9 V rail.  The stock TAKERG4AIO firmware has no BMI270 driver, so it finds
 * no gyro on a BMI270 board.  This target exists for the things the stock
 * one gets wrong on this hardware:
 *
 *   1. Board alignment.  TAKERG4AIO ships DEFAULT_ALIGN_BOARD_YAW 45 because
 *      GEPRC mounted its gyro at 45 degrees.  Here the gyro is mounted square
 *      and there is no board rotation.  (A wrong default here cost Phase 1
 *      three crashes.)  The IMU pads take either an ICM-42688-P or a Bosch
 *      BMI270, and the two chips do NOT share an axis frame on those pads:
 *      see GYRO_1_ALIGN below.  This build's default is for the BMI270.
 *   2. Receiver on UART2 (the pads labelled 5V G R2 T2), CRSF.
 *   3. DShot300 with bidirectional DShot on, to suit the AM32 ESC board.
 *   4. Video: analog OSD (AT7456E) on SPI2 with the flash, HD VTX (MSP
 *      DisplayPort) on UART1, and PINIO1 on PB5 to switch the 9 V VTX rail.
 *   5. Battery: 30k/2k divider (vbat_scale 160) and the ESC's summed
 *      current-sense output on CUR (12.5 mV/A, ibata_scale 125).
 */

#pragma once

#define FC_TARGET_MCU       STM32G47X      // STM32G473CEU6, the Betaflight 2025.12 G47x target

#define BOARD_NAME          RIDGE3
#define MANUFACTURER_ID     OFFG

#define USE_ACC
#define USE_GYRO
#define USE_ACCGYRO_BMI270                  // BMI270 ONLY: an ICM-42688-P board finds no gyro and will not arm
#define USE_FLASH
#define USE_FLASH_W25Q128FV                 // m25p16 driver: W25Q128JV-IM (EF 70 18), -IQ (EF 40 18), PY25Q128HA (85 20 18)
#define USE_MAX7456                         // AT7456E; a CONFIG= build does not get this from common_pre.h

#define BEEPER_PIN          PA15
#define BEEPER_INVERTED

#define MOTOR1_PIN          PA0
#define MOTOR2_PIN          PA1
#define MOTOR3_PIN          PA2
#define MOTOR4_PIN          PA3

#define LED0_PIN            PB7
#define LED_STRIP_PIN       PB6

#define UART1_TX_PIN        PA9             // HD VTX connector (MSP DisplayPort), or analog VTX control
#define UART1_RX_PIN        PA10
#define UART2_TX_PIN        PB3             // receiver
#define UART2_RX_PIN        PB4
#define UART4_TX_PIN        PC10            // spare (GPS)
#define UART4_RX_PIN        PC11
#define LPUART1_TX_PIN      PB10
#define LPUART1_RX_PIN      PB11            // ESC lead TLM pin

#define SPI1_SCK_PIN        PA5
#define SPI1_SDI_PIN        PA6
#define SPI1_SDO_PIN        PA7
#define SPI2_SCK_PIN        PB13            // SPI2: blackbox flash and OSD
#define SPI2_SDI_PIN        PB14
#define SPI2_SDO_PIN        PB15

#define GYRO_1_SPI_INSTANCE SPI1
#define GYRO_1_CS_PIN       PB0
#define GYRO_1_EXTI_PIN     PA4
// Alignment is for the BMI270, the default part.  On these pads the ICM-42688-P
// has +X to the front and +Y to the left (pin 1 rear-left): CW0.  The BMI270's
// axes sit 90 degrees counter-clockwise from the ICM's relative to pin 1
// (Bosch BST-BMI270-DS000-08 sec. 8.2 p.144 vs TDK DS-000347 fig. 15 p.53), so
// on the same pads its +X points left and +Y to the rear: CW270.
// This variant has no ICM-42688-P driver on purpose: flashed onto an ICM board it
// reports no gyro and refuses to arm, instead of flying with a 90-degree error.
// ICM boards run configs/RIDGE3_ICM (GYRO_1_ALIGN CW0).  Bench-check in the
// Setup tab before every first flight.
#define GYRO_1_ALIGN        CW270_DEG

#define FLASH_SPI_INSTANCE  SPI2
#define FLASH_CS_PIN        PC6

// Analog OSD: AT7456E (MAX7456-compatible; Betaflight tells the two apart
// itself) at 3.3 V, sharing SPI2 with the flash.  Same CS pin as TAKERG4AIO.
#define MAX7456_SPI_INSTANCE    SPI2
#define MAX7456_SPI_CS_PIN      PA8

// HD VTX (DJI O3/O4, Walksnail, HDZero) on UART1: this sets UART1's default
// function to VTX (MSP + DisplayPort), 131073.
#define MSP_DISPLAYPORT_UART    SERIAL_PORT_USART1

// VTX 9 V rail switch.  PB5 drives an N-FET that pulls the 9 V regulator's
// EN low: PB5 high = VTX rail OFF, PB5 low = ON.  PINIO1 is a plain
// (non-inverted) push-pull output, low at boot and whenever the USER1 mode
// is inactive, so the VTX is on by default; a switch assigned to USER1
// (permanent box id 40) turns it off.  Before Betaflight claims the pin the
// FET's gate pull-down holds it off, so the VTX also powers up at reset.
#define PINIO1_PIN          PB5
#define PINIO1_CONFIG       1               // PINIO_CONFIG_MODE_OUT_PP, not inverted (129 would invert it)
#define PINIO1_BOX          40              // BOXUSER1

#define ADC_VBAT_PIN        PB2
#define ADC_CURR_PIN        PB1

#define TIMER_PIN_MAPPING   TIMER_PIN_MAP( 0, PB6 , 3,  9) \
                            TIMER_PIN_MAP( 1, PA0 , 1,  1) \
                            TIMER_PIN_MAP( 2, PA1 , 1,  2) \
                            TIMER_PIN_MAP( 3, PA2 , 2,  3) \
                            TIMER_PIN_MAP( 4, PA3 , 2,  4)

#define ADC1_DMA_OPT        10
#define ADC2_DMA_OPT        11
#define ADC_INSTANCE        ADC2

#define SYSTEM_HSE_MHZ      8

#define DEFAULT_PID_PROCESS_DENOM       1     // BMI270 3.2 kHz gyro -> 3.2 kHz PID (2 would halve it)
#define DEFAULT_BLACKBOX_DEVICE         BLACKBOX_DEVICE_FLASH
#define DEFAULT_VOLTAGE_METER_SOURCE    VOLTAGE_METER_ADC
#define DEFAULT_VOLTAGE_METER_SCALE     160   // 30k / 2k divider: ratio 16 x 10
#define DEFAULT_CURRENT_METER_SOURCE    CURRENT_METER_ADC     // CUR on the ESC lead
#define DEFAULT_CURRENT_METER_SCALE     125   // mV per 10 A: the ESC's CUR is 12.5 mV/A (4 x 50 mV/A, averaged)
#define DEFAULT_CURRENT_METER_OFFSET    0     // mA: 0 A reads 0 V
#define SERIALRX_UART                   SERIAL_PORT_USART2
#define SERIALRX_PROVIDER               SERIALRX_CRSF
#define DEFAULT_MOTOR_DSHOT_SPEED       MOTOR_PROTOCOL_DSHOT300
#define DEFAULT_DSHOT_TELEMETRY         DSHOT_TELEMETRY_ON
