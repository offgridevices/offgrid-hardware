/*
 * Betaflight target for the OffGrid Cheap Drone flight controller
 * (cheap-drone-stack/v1/fc).
 *
 * This file is part of Betaflight and is distributed under the terms of the
 * GNU General Public License v3 or later, like the rest of Betaflight.
 *
 * The pin map is the GEPRC TAKER G4 AIO's (Betaflight target GEPR/TAKERG4AIO),
 * minus the parts this board does not fit (OSD, baro, magnetometer).  The
 * stock TAKERG4AIO firmware ran the ICM-42688-P build of this board; it has
 * no BMI270 driver, so it finds no gyro on a BMI270 board.  This target
 * exists for the things the stock one gets wrong on this hardware:
 *
 *   1. Board alignment.  TAKERG4AIO ships DEFAULT_ALIGN_BOARD_YAW 45 because
 *      GEPRC mounted its gyro at 45 degrees.  Here the gyro is mounted square
 *      and there is no board rotation.  (A wrong default here cost Phase 1
 *      three crashes.)  The IMU pads take either an ICM-42688-P or a Bosch
 *      BMI270, and the two chips do NOT share an axis frame on those pads:
 *      see GYRO_1_ALIGN below.  This build's default is for the BMI270.
 *   2. Receiver on UART2 (the pads labelled 5V G R2 T2), CRSF.
 *   3. DShot300 with bidirectional DShot on, to suit the AM32 ESC board.
 */

#pragma once

#define FC_TARGET_MCU       STM32G47X      // STM32G473CEU6, the Betaflight 2025.12 G47x target

#define BOARD_NAME          CHEAPDRONE_G473
#define MANUFACTURER_ID     OFFG

#define USE_ACC
#define USE_GYRO
#define USE_ACCGYRO_BMI270                  // BMI270 ONLY: an ICM-42688-P board finds no gyro and will not arm
#define USE_FLASH
#define USE_FLASH_W25Q128FV
#define USE_FLASH_PY25Q128HA                // Puya PY25Q128HA, JEDEC 85 20 18 (m25p16 driver table)

#define BEEPER_PIN          PA15
#define BEEPER_INVERTED

#define MOTOR1_PIN          PA0
#define MOTOR2_PIN          PA1
#define MOTOR3_PIN          PA2
#define MOTOR4_PIN          PA3

#define LED0_PIN            PB7
#define LED_STRIP_PIN       PB6

#define UART1_TX_PIN        PA9
#define UART1_RX_PIN        PA10
#define UART2_TX_PIN        PB3
#define UART2_RX_PIN        PB4
#define UART4_TX_PIN        PC10
#define UART4_RX_PIN        PC11
#define LPUART1_TX_PIN      PB10
#define LPUART1_RX_PIN      PB11            // ESC lead TLM pin

#define SPI1_SCK_PIN        PA5
#define SPI1_SDI_PIN        PA6
#define SPI1_SDO_PIN        PA7
#define SPI2_SCK_PIN        PB13
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
// ICM boards run configs/CHEAPDRONE_G473_ICM (GYRO_1_ALIGN CW0).  Bench-check in the
// Setup tab before every first flight.
#define GYRO_1_ALIGN        CW270_DEG

#define FLASH_SPI_INSTANCE  SPI2
#define FLASH_CS_PIN        PC6

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
#define DEFAULT_VOLTAGE_METER_SOURCE    VOLTAGE_METER_ADC     // 10k / 1k divider: vbat_scale 110 (the default)
#define DEFAULT_CURRENT_METER_SOURCE    CURRENT_METER_ADC     // CUR pin on the ESC lead; reads 0 A with this stack's ESC
#define SERIALRX_UART                   SERIAL_PORT_USART2
#define SERIALRX_PROVIDER               SERIALRX_CRSF
#define DEFAULT_MOTOR_DSHOT_SPEED       MOTOR_PROTOCOL_DSHOT300
#define DEFAULT_DSHOT_TELEMETRY         DSHOT_TELEMETRY_ON
