/* Canary v1 pin map. check_pins.py compares this file with
 * src/circuit.py (FIRMWARE_PINS) and the schematic netlist. */
#ifndef BOARD_H
#define BOARD_H

#define F_CPU_HZ        8000000UL   /* internal RC, CKDIV8 off (lfuse 0xE2) */

/* pin: NET  PORT BIT */
#define PIN_LED_GRN     PD3     /* LED_GRN   OC2B */
#define PIN_LED_AMB     PD5     /* LED_AMB   OC0B */
#define PIN_LED_RED     PD6     /* LED_RED   OC0A */
#define PIN_BUZ         PB1     /* BUZ       OC1A */
#define PIN_BTN         PD2     /* BTN       INT0 */
#define PIN_SDA         PC4     /* SDA       TWI  */
#define PIN_SCL         PC5     /* SCL       TWI  */
#define PIN_NTC_BRD     PC0     /* NTC_BRD   ADC0 */
#define PIN_NTC_PRB     PC1     /* NTC_PRB_F ADC1 */
#define PIN_TXD         PD1     /* TXD       USART */
#define PIN_RXD         PD0     /* RXD       USART */

#define ADC_CH_NTC_BRD  0
#define ADC_CH_NTC_PRB  1

/* NTCs: on-board Murata NCU18XH103F60RB (10k, B25/50 3380 K) on the
 * thermal tab; optional probe: any 10k B3950 NTC on the JST-PH. Both are
 * the low side of a divider with a 10k 0.1 % resistor from 3V3. */
#define NTC_R25         10000.0f
#define NTC_B_BRD       3380.0f
#define NTC_B_PRB       3950.0f

#define BUZ_HZ          4000    /* CMT-8504 resonance */

#define I2C_SGP40       0x59
#define I2C_SHT40       0x44
#define I2C_SCD41       0x62

#endif
