/*
 * Adafruit_nRF52_Bootloader board definition: OffGrid Devices Mesh Radio v1
 * (working name).  Copy this folder to src/boards/offgrid_mesh_radio_v1/ in
 * https://github.com/adafruit/Adafruit_nRF52_Bootloader (checked against tag
 * 0.11.0) and build with:  make BOARD=offgrid_mesh_radio_v1 all
 *
 * Power: nRF52840 in NORMAL-voltage mode - VDD and VDDH are both tied to the
 * board's 3.3 V rail and REG0 is unused (DCCH open).  UICR REGOUT0 only sets
 * REG0's output when the chip is supplied on VDDH alone (high-voltage mode),
 * so UICR_REGOUT0_VALUE is deliberately NOT defined: writing it would do
 * nothing useful here and costs a UICR write + reset on first boot.
 * REG1 DC/DC inductors (10 uH + 15 nH on DCC/DEC4) are fitted, so DCDC 1 is
 * enabled; DCDC 0 (REG0) has no inductor and must stay off.
 *
 * Reset: the Makefile defines CONFIG_GPIO_AS_PINRESET, so P0.18 is the reset
 * pin (the board's reset button), and CONFIG_NFCT_PINS_AS_GPIOS, so P0.09 /
 * P0.10 are GPIO (P0.09 is the charger's /CE, P0.10 an expansion pin).
 *
 * DFU: double-press reset for the UF2 drive, or hold the user button (P1.00)
 * while pressing reset.  There is no second button, so no button OTA entry
 * (Meshtastic can still request BLE OTA DFU from the app).
 */

#ifndef _OFFGRID_MESH_RADIO_V1_H
#define _OFFGRID_MESH_RADIO_V1_H

/*------------------------------------------------------------------*/
/* LED: green P1.03 and blue P1.04, active high (as RAK4631)
 *------------------------------------------------------------------*/
#define LEDS_NUMBER        2
#define LED_PRIMARY_PIN    PINNUM(1, 3) // green
#define LED_SECONDARY_PIN  PINNUM(1, 4) // blue
#define LED_STATE_ON       1

/*------------------------------------------------------------------*/
/* BUTTON: user button P1.00 to ground, internal pull-up
 *------------------------------------------------------------------*/
#define BUTTON_DFU         PINNUM(1, 0)
#define BUTTON_PULL        NRF_GPIO_PIN_PULLUP

/*------------------------------------------------------------------*/
/* Power
 *------------------------------------------------------------------*/
#define ENABLE_DCDC_0      0 // REG0 unused in normal-voltage mode (no inductor on DCCH)
#define ENABLE_DCDC_1      1 // REG1 DC/DC, inductors fitted
// No UICR_REGOUT0_VALUE: normal-voltage mode (see above)

/*
 * Nothing else needs setting in the bootloader: the amplifier power
 * (PA_PWR_EN, 1 M pull-down), amplifier control (PA_EN, 100 k pull-down),
 * GPS power (GPS_EN, 1 M pull-down) and charger /CE (100 k pull-down =
 * charging on) all default to the safe state through their resistors.
 */

//--------------------------------------------------------------------+
// BLE OTA
//--------------------------------------------------------------------+
#define BLEDIS_MANUFACTURER   "OffGrid Devices"
#define BLEDIS_MODEL          "Mesh Radio v1"

//--------------------------------------------------------------------+
// USB
// TODO before production: a VID/PID of our own (pid.codes or a vendor
// allocation).  0x1209:0x0001 is pid.codes' test PID - prototypes only.
//--------------------------------------------------------------------+
#define USB_DESC_VID           0x1209
#define USB_DESC_UF2_PID       0x0001
#define USB_DESC_CDC_ONLY_PID  0x0001

//------------- UF2 -------------//
#define UF2_PRODUCT_NAME      "OffGrid Mesh Radio v1"
#define UF2_VOLUME_LABEL      "OGMESHBOOT"
#define UF2_BOARD_ID          "nRF52840-OffGrid-MeshRadio-v1"
#define UF2_INDEX_URL         "https://flasher.meshtastic.org/"

#endif // _OFFGRID_MESH_RADIO_V1_H
