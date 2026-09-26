/*
 * Betaflight target for the OffGrid Cheap Drone flight controller
 * (cheap-drone-stack/v1/fc).
 *
 * This file is part of Betaflight and is distributed under the terms of the
 * GNU General Public License v3 or later, like the rest of Betaflight.
 *
 * The pin map is the GEPRC TAKER G4 AIO's (Betaflight target GEPR/TAKERG4AIO),
 * minus the parts this board does not fit (OSD, baro, magnetometer).  That
 * means the stock TAKERG4AIO firmware also runs this board.  This target
 * exists for the three things the stock one gets wrong on this hardware:
 *
 *   1. Board alignment.  TAKERG4AIO ships DEFAULT_ALIGN_BOARD_YAW 45 because
 *      GEPRC mounted its gyro at 45 degrees.  Here the gyro is mounted square,
 *      rotated so its axes ARE the board's axes: GYRO_1_ALIGN CW0 and no
 *      board rotation.  With the arrow on the board pointing forward, the
 *      default is right.  (A wrong default here cost Phase 1 three crashes.)
 *   2. Receiver on UART2 (the pads labelled RX 5V G R2 T2), CRSF.
 *   3. DShot300 with bidirectional DShot on, to suit the AM32 ESC board.
 */

#pragma once

#define FC_TARGET_MCU       STM32G47X      // STM32G473CEU6, the Betaflight 2025.12 G47x target

#define BOARD_NAME          CHEAPDRONE_G473
#define MANUFACTURER_ID     OFFG

#define USE_ACC
#define USE_ACC_SPI_ICM42688P
#define USE_GYRO
#define USE_GYRO_SPI_ICM42688P
#define USE_FLASH
#define USE_FLASH_W25Q128FV

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
#define GYRO_1_ALIGN        CW0_DEG

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

#define DEFAULT_PID_PROCESS_DENOM       2
#define DEFAULT_BLACKBOX_DEVICE         BLACKBOX_DEVICE_FLASH
#define DEFAULT_VOLTAGE_METER_SOURCE    VOLTAGE_METER_ADC     // 10k / 1k divider: vbat_scale 110 (the default)
#define DEFAULT_CURRENT_METER_SOURCE    CURRENT_METER_ADC     // CUR pin on the ESC lead; reads 0 A with this stack's ESC
#define SERIALRX_UART                   SERIAL_PORT_USART2
#define SERIALRX_PROVIDER               SERIALRX_CRSF
#define DEFAULT_MOTOR_DSHOT_SPEED       MOTOR_PROTOCOL_DSHOT300
#define DEFAULT_DSHOT_TELEMETRY         DSHOT_TELEMETRY_ON
