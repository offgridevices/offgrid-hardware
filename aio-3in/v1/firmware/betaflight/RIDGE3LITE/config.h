/*
 * This file is part of Betaflight.
 *
 * Betaflight is free software. You can redistribute this software
 * and/or modify this software under the terms of the GNU General
 * Public License as published by the Free Software Foundation,
 * either version 3 of the License, or (at your option) any later
 * version.
 *
 * Betaflight is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
 *
 * See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public
 * License along with this software.
 *
 * If not, see <http://www.gnu.org/licenses/>.
 */

/*
 * OffGrid Ridge 3 Lite v1: STM32G473CEU6 flight controller + 4x AM32 ESC.
 * Pin map identical to GEPR/TAKERG4AIO (betaflight/config 15d8c3f) for
 * every pin this board uses; this file only trims the parts list and sets
 * the defaults this board wants.
 *
 * No blackbox flash is fitted (PB13/PB14/PB15/PC6 unconnected): blackbox
 * needs an external serial logger (e.g. OpenLager) on UART1.
 *
 * Gyro: ICM-42688-P placed at KiCad orientation 135 deg (see
 * firmware/gyro-orientation.md).  Stock TAKERG4AIO reads that placement as
 * CW270 + board yaw 45; here the same rotation is folded into the sensor
 * alignment (custom yaw 315 deg) so Configurator shows board alignment 0/0/0.
 *
 * BMI270 is deliberately NOT enabled: on the same pads a Bosch BMI270 needs
 * custom yaw 225, not 315, and Betaflight has one alignment per gyro slot,
 * so a BMI270 fitted by mistake would be detected and fly 90 deg off.
 */

#define FC_TARGET_MCU       STM32G474     // Betaflight's G47x build; runs on the G473 (no HRTIM used)
#define BOARD_NAME          RIDGE3LITE
#define MANUFACTURER_ID     OFFG

#define USE_ACC
#define USE_ACC_SPI_ICM42688P
#define USE_GYRO
#define USE_GYRO_SPI_ICM42688P

#define BEEPER_PIN          PA15
#define MOTOR1_PIN          PA0
#define MOTOR2_PIN          PA1
#define MOTOR3_PIN          PA2
#define MOTOR4_PIN          PA3
#define LED_STRIP_PIN       PB6
#define UART1_TX_PIN        PA9
#define UART2_TX_PIN        PB3
#define UART1_RX_PIN        PA10
#define UART2_RX_PIN        PB4

#define LED0_PIN            PB7
#define SPI1_SCK_PIN        PA5
#define SPI1_SDI_PIN        PA6
#define SPI1_SDO_PIN        PA7
#define ADC_VBAT_PIN        PB2
#define ADC_CURR_PIN        PB1
#define GYRO_1_EXTI_PIN     PA4
#define GYRO_1_CS_PIN       PB0

// Same timers and DMA as TAKERG4AIO: PA0 TIM2_CH1, PA1 TIM2_CH2,
// PA2 TIM5_CH3, PA3 TIM5_CH4 (DMA1 ch2..5), LED strip PB6 TIM8_CH1 (DMA2 ch2).
#define TIMER_PIN_MAPPING   TIMER_PIN_MAP( 0, PB6 , 3,  9) \
                            TIMER_PIN_MAP( 1, PA0 , 1,  1) \
                            TIMER_PIN_MAP( 2, PA1 , 1,  2) \
                            TIMER_PIN_MAP( 3, PA2 , 2,  3) \
                            TIMER_PIN_MAP( 4, PA3 , 2,  4)

#define ADC1_DMA_OPT        10
#define ADC2_DMA_OPT        11

#define ADC_INSTANCE                 ADC2
#define DEFAULT_PID_PROCESS_DENOM    2
#define DEFAULT_BLACKBOX_DEVICE      BLACKBOX_DEVICE_NONE   // no flash; see header
#define BEEPER_INVERTED
#define SYSTEM_HSE_MHZ               8
#define DEFAULT_CURRENT_METER_SOURCE CURRENT_METER_ADC
#define DEFAULT_VOLTAGE_METER_SOURCE VOLTAGE_METER_ADC
#define DEFAULT_CURRENT_METER_SCALE  120      // 12.0 mV/A (four ESC amplifiers averaged)
#define DEFAULT_VOLTAGE_METER_SCALE  110      // 10k / 1k divider
#define GYRO_1_SPI_INSTANCE          SPI1

// Sensor alignment: custom yaw 315 deg (decidegrees), board alignment 0.
#define GYRO_1_ALIGN_YAW             3150

// Receiver: CRSF (ELRS/Crossfire) on UART2 (pads R2/T2).
#define SERIALRX_UART                SERIAL_PORT_USART2
#define SERIALRX_PROVIDER            SERIALRX_CRSF

// AM32 ESCs: DShot600 with bidirectional (RPM) telemetry on.
#define DEFAULT_MOTOR_DSHOT_SPEED    PWM_TYPE_DSHOT600
#define DEFAULT_DSHOT_TELEMETRY      DSHOT_TELEMETRY_ON
