# -*- coding: utf-8 -*-
"""Every part on the three boards, and where it comes from.

Each entry is one orderable line: the footprint the board uses, the LCSC
part number JLCPCB assembles from, the manufacturer part number for anyone
buying elsewhere, and a description.  Stock and prices were read from
JLCPCB's catalogue on 26 Oct 2026 (tools/lcsc.py --parts; docs/parts.md
has the table and the second sources).  Read them again before ordering.

Footprints named 'lc:*' live in ../lc.pretty: the IC, connector, crystal,
LED and inductor footprints there are JLCPCB/EasyEDA's own library entries
for these exact LCSC parts (src/easyeda_raw, cleaned by footprints.py), so
the pad numbering and the 0-degree orientation are the ones the assembly
line uses.  Every pad number was checked against the EasyEDA symbol's pin
names and the maker's datasheet (docs/parts.md).  Plain two-terminal R/C
parts use KiCad's standard footprints, whose 0-degree orientation matches
JLCPCB's.

Every part is rated for at least 85 degC ambient except where a note says
otherwise: the camera lives in a printer chamber at up to 65 degC.

Parts bought separately (not on any board, docs/parts.md): the SC3336
camera module, the CLA219 IR-cut holder, the M12 lens, the Wi-Fi antenna
and the three cables.
"""

R0402 = 'Resistor_SMD:R_0402_1005Metric'
R1206 = 'Resistor_SMD:R_1206_3216Metric'
C0402 = 'Capacitor_SMD:C_0402_1005Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
L0402 = 'Inductor_SMD:L_0402_1005Metric'
UNIROYAL, SAMSUNG = 'UNI-ROYAL', 'Samsung Electro-Mechanics'


def R(value, lcsc, mpn, fp=R0402, maker=UNIROYAL, desc=None):
    return dict(fp=fp, lcsc=lcsc, mpn=mpn, value=value, maker=maker, kind='R',
                desc=desc or 'Resistor %s 1%% 0402' % value)


def C(value, fp, lcsc, mpn, rating, maker=SAMSUNG):
    return dict(fp=fp, lcsc=lcsc, mpn=mpn, value=value, maker=maker, kind='C',
                desc='Capacitor %s %s' % (value, rating))


PARTS = {
    # ------------------------------------------------------------ main board ICs
    'RV1106G3': dict(fp='lc:QFN-128_L12.3-W12.3-P0.35-TL-EP7.0-1', lcsc='C5328706', mpn='RV1106G3',
                     value='RV1106G3', maker='Rockchip', kind='U',
                     desc='Camera SoC: Cortex-A7 1.2 GHz, 256 MB DDR3L inside, ISP, H.264/H.265, QFN-128 0.35 mm'),
    'W25N02KV': dict(fp='lc:WSON-8_L8.0-W6.0-P1.27-TL-EP-1', lcsc='C3010298', mpn='W25N02KVZEIR',
                     value='W25N02KV', maker='Winbond', kind='U',
                     desc='SPI NAND flash 2 Gbit (256 MB), 3.3 V, WSON-8 8 x 6'),
    'AP6256': dict(fp='lc:QFN-44_L12.0-W12.0-P0.90-TL_AP6256', lcsc='C5248079', mpn='AP6256', value='AP6256',
                   maker='AMPAK', kind='U',
                   desc='Wi-Fi 5 (2.4 + 5 GHz) + BT 5 module, BCM43456, SDIO; full RF to 75 degC, rated 85 degC'),
    'EA3036C': dict(fp='lc:WQFN-20_L3.0-W3.0-P0.40-BL-EP', lcsc='C570857', mpn='EA3036CQBR', value='EA3036C',
                    maker='Everanalog', kind='U', desc='Triple 1 A synchronous buck, 2.7-5.5 V in, WQFN-20 3 x 3'),
    'TLV62569': dict(fp='lc:SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR', lcsc='C141836', mpn='TLV62569DBVR',
                     value='TLV62569', maker='Texas Instruments', kind='U',
                     desc='2 A synchronous buck, 0.6 V reference, SOT-23-5, Tj to 125 degC'),
    'DRV8837': dict(fp='lc:WSON-8_L2.0-W2.0-P0.50-TL-EP', lcsc='C39159', mpn='DRV8837DSGR', value='DRV8837',
                    maker='Texas Instruments', kind='U', desc='H-bridge 1.8 A, for the IR-cut filter, WSON-8 2 x 2'),
    'AO3400A': dict(fp='lc:SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR', lcsc='C20917', mpn='AO3400A', value='AO3400A',
                    maker='Alpha & Omega', kind='Q', desc='N-MOSFET 30 V 5.7 A, logic level, SOT-23 (IR LED switch)'),
    'OSC32K': dict(fp='lc:OSC-SMD_4P-L3.2-W1.5', lcsc='C6277865', mpn='ASH7KW-32.768KHZ-L-T',
                   value='32.768kHz', maker='Abracon', kind='Y',
                   desc='32.768 kHz CMOS oscillator 1.2-5.5 V, -40..85 degC (the Wi-Fi module\'s sleep clock)'),
    'XTAL24M': dict(fp='lc:CRYSTAL-SMD_4P-L3.2-W2.5-BL', lcsc='C70590', mpn='X322524MOB4SI', value='24MHz',
                    maker='YXC', kind='Y', desc='Crystal 24 MHz 12 pF 10 ppm, 3225'),
    'XTAL37M4': dict(fp='lc:CRYSTAL-SMD_4P-L3.2-W2.5-BL_1', lcsc='C2981708', mpn='3225-37.4-12-10-10/A',
                     value='37.4MHz', maker='Shenzhen Crystal', kind='Y',
                     desc='Crystal 37.4 MHz 12 pF, 10 ppm tolerance and stability, -40..85 degC, 3225'),
    'XTAL32K': dict(fp='lc:FC-135R_L3.2-W1.5', lcsc='C32346', mpn='Q13FC13500004', value='32.768kHz',
                    maker='Epson', kind='Y', desc='Crystal 32.768 kHz 12.5 pF (the SoC\'s RTC), 3215'),
    'LED_GRN': dict(fp='lc:LED0603-RD', lcsc='C12624', mpn='KT-0603G', value='green', maker='Hubei KENTO',
                    kind='LED', desc='LED green 0603 (status)'),
    # ------------------------------------------------------------ connectors, switch
    'FPC20': dict(fp='lc:FPC-SMD_20P-P0.50_XF2M-2015-1A', lcsc='C57541', mpn='XF2M-2015-1A', value='CAM',
                  maker='Omron', kind='J',
                  desc='FFC connector 20 pin 0.5 mm, contacts top AND bottom (either cable type), flip lock'),
    'SH6V': dict(fp='lc:CONN-SMD-6P-P1.00_BM06B-SRSS-TB-LF-SN', lcsc='C160392', mpn='BM06B-SRSS-TB(LF)(SN)', value='SH 6',
                 maker='JST', kind='J', desc='JST SH 1.0 mm 6 pin, vertical, SMD'),
    'SH6R': dict(fp='lc:CONN-SMD_SM06B-SRSS-TB-LF-SN', lcsc='C160405', mpn='SM06B-SRSS-TB(LF)(SN)', value='SH 6',
                 maker='JST', kind='J', desc='JST SH 1.0 mm 6 pin, right angle, SMD'),
    'PB2R': dict(fp='lc:CONN-SMD_532610271', lcsc='C177225', mpn='53261-0271', value='IR-cut',
                 maker='Molex', kind='J', desc='PicoBlade 1.25 mm 2 pin, right angle, SMD, -40..105 degC'),
    'UFL': dict(fp='lc:RF-SMD_FRF05002-JSS103M', lcsc='C88374', mpn='U.FL-R-SMT-1(80)', value='U.FL',
                maker='Hirose', kind='J', desc='U.FL coaxial receptacle (Wi-Fi antenna), -40..90 degC'),
    'USBC': dict(fp='lc:USB-C_SMD-TYPE-C-31-M-12_1', lcsc='C165948', mpn='TYPE-C-31-M-12', value='USB-C',
                 maker='Korean Hroparts', kind='J', desc='USB-C receptacle, USB 2.0, 16 contacts (rated -30..80 degC)'),
    'USBLC6': dict(fp='lc:SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BL', lcsc='C7519', mpn='USBLC6-2SC6', value='USBLC6-2SC6',
                   maker='STMicroelectronics', kind='U', desc='USB ESD protection, SOT-23-6'),
    'SMF5V0': dict(fp='lc:SOD-123FL_L2.8-W1.8-LS3.7-BI', lcsc='C169425', mpn='SMF5.0CA', value='SMF5.0CA',
                   maker='Leiditech', kind='D', desc='TVS 5 V bidirectional 200 W, SOD-123FL'),
    # ------------------------------------------------------------ LED ring
    'IRLED': dict(fp='lc:LED-SMD_L3.5-W2.8-R-RD_RED-1', lcsc='C7500094', mpn='JNJ-LTJI0106W90/14mil-D/850NM',
                  value='850nm', maker='JNJ', kind='LED',
                  desc='IR LED 850 nm, 100 mA, 90 degrees, 2835, -40..100 degC (pad 1 anode)'),
    'TEMT6000': dict(fp='lc:SENSORS-SMD_TEMT6000X01', lcsc='C94098', mpn='TEMT6000X01', value='TEMT6000',
                     maker='Vishay', kind='Q',
                     desc='Ambient light phototransistor, eye response (blind to the 850 nm LEDs), -40..100 degC'),
    # ------------------------------------------------------------ inductors, beads
    'L1U5': dict(fp='lc:IND-SMD_L2.5-W2.0', lcsc='C29780704', mpn='FPA252012D-1R5MT0', value='1.5uH',
                 maker='Fenghua', kind='L', desc='Inductor 1.5 uH 2.9 A, 2520'),
    'L2U2': dict(fp='lc:IND-SMD_L2.5-W2.0', lcsc='C29780705', mpn='FPA252012D-2R2MT0', value='2.2uH',
                 maker='Fenghua', kind='L', desc='Inductor 2.2 uH 2.4 A, 2520'),
    'L4U7': dict(fp='lc:IND-SMD_L2.5-W2.0', lcsc='C29780707', mpn='FPA252012D-4R7MT0', value='4.7uH',
                 maker='Fenghua', kind='L', desc='Inductor 4.7 uH 1.6 A, 2520 (the Wi-Fi module\'s own buck)'),
    'BEAD': dict(fp=L0402, lcsc='C76891', mpn='BLM15PD121SN1D', value='120R@100MHz', maker='Murata', kind='L',
                 desc='Ferrite bead 120 ohm at 100 MHz, 1.3 A, 0402'),
    # ------------------------------------------------------------ resistors
    'R0R': R('0R', 'C17168', '0402WGF0000TCE'),
    'R1R': R('1R', 'C25086', '0402WGF100KTCE'),
    'R22R': R('22R', 'C25092', '0402WGF220JTCE'),
    'R100R': R('100R', 'C25076', '0402WGF1000TCE'),
    'R240R': R('240R', 'C25094', '0402WGF2400TCE'),
    'R1K': R('1k', 'C11702', '0402WGF1001TCE'),
    'R4K7': R('4.7k', 'C25900', '0402WGF4701TCE'),
    'R5K1': R('5.1k', 'C25905', '0402WGF5101TCE'),
    'R6K2': R('6.2k', 'C25915', '0402WGF6201TCE'),
    'R10K': R('10k', 'C25744', '0402WGF1002TCE'),
    'R18K': R('18k', 'C25762', '0402WGF1802TCE'),
    'R22K': R('22k', 'C25768', '0402WGF2202TCE'),
    'R47K': R('47k', 'C25792', '0402WGF4702TCE'),
    'R51K': R('51k', 'C25794', '0402WGF5102TCE'),
    'R20K': R('20k', 'C25765', '0402WGF2002TCE'),
    'R100K': R('100k', 'C25741', '0402WGF1003TCE'),
    'R127K': R('127k', 'C25751', '0402WGF1273TCE'),
    'R200K': R('200k', 'C25764', '0402WGF2003TCE'),
    'R1M': R('1M', 'C26083', '0402WGF1004TCE'),
    'R47R_1206': R('47R', 'C17969', '1206W4F470JT5E', fp=R1206, desc='Resistor 47R 1% 0.25 W 1206 (IR LED string)'),
    # ------------------------------------------------------------ capacitors
    'C12P': C('12pF', C0402, 'C1547', '0402CG120J500NT', '50V C0G 0402', 'FH (Fenghua)'),
    'C18P': C('18pF', C0402, 'C1549', '0402CG180J500NT', '50V C0G 0402', 'FH (Fenghua)'),
    'C1N': C('1nF', C0402, 'C1523', '0402B102K500NT', '50V X7R 0402', 'FH (Fenghua)'),
    'C10N': C('10nF', C0402, 'C15195', 'CL05B103KB5NNNC', '50V X7R 0402'),
    'C100N': C('100nF', C0402, 'C1525', 'CL05B104KO5NNNC', '16V X7R 0402'),
    # the 1-22 uF parts are X6S / X7S (105 / 125 C), not X5R (85 C): the
    # board runs near 85 C in a 65 C chamber (sim/thermal.md)
    'C1U': C('1uF', C0402, 'C437522', 'GRM155C71A105KE11D', '10V X7S 0402', 'Murata'),
    'C4U7': C('4.7uF', C0402, 'C464981', 'GRM155C80J475MEAAD', '6.3V X6S 0402', 'Murata'),
    'C10U': C('10uF', C0603, 'C576470', 'GRM188C81A106MA73D', '10V X6S 0603', 'Murata'),
    'C22U': C('22uF', C0603, 'C393031', 'GRM188C80J226ME15D', '6.3V X6S 0603', 'Murata'),
}

# Copper-only footprints: nothing is bought or placed for these.
#   DNP_C0402: an antenna-matching position left empty (the match is a 0 R
#   through and nothing to ground until a VNA says otherwise)
PADS = {
    'TP': dict(fp='lc:PAD_TP', kind='PAD'),
    'HOLE_M2': dict(fp='lc:MOUNT_M2', kind='H'),
    'HOLE_M1V6': dict(fp='lc:MOUNT_M1V6', kind='H'),
    'DNP_C0402': dict(fp=C0402, kind='DNP'),
}
