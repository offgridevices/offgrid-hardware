# Ridge 3, revision 2: what changed, and why

Revision 1 ran through the stress simulations (`../STRESS.md`, rev 1 column)
and fell short of the brief for a heavy quad flown hard on a 50 °C day:

- the ESC's FETs could pass 175 °C in a burst before the temperature limit
  reacted;
- the switch node rang to the 40 V FETs' rating;
- the FC's 30 W did not fit through the 1 A stack lead;
- X5R capacitors, 85 °C gyro, flash and crystals sat on boards that reach
  well past 85 °C.

Revision 2 changes every one of those.  The rule for parts: rated for the
temperature the simulations give, from makers with datasheets that say so,
and actually in stock.  Where nothing qualified, the table says what was
kept and why.  `../STRESS.md` runs both revisions through the same
simulations and compares them.

Board revision labels: both boards print **REV 2.0**.

## ESC

| Rev 1 | Rev 2 | Why |
|---|---|---|
| FETs: Toshiba TPN2R304PL, 40 V (63 % of rating at 6S) | **Infineon ISZ023N06LM6**, 60 V, 2.3 mΩ max, T<sub>j</sub> 175 °C, PG-TSDSON-8 FL (Infineon's own land) | Rev 1's switch node rang to 40 V; 60 V parts at the same on-resistance class leave margin without snubbers.  Not stocked at LCSC: JLC global sourcing or PCBWay turnkey (`parts.py` marks it `source='global'`) |
| Gate drivers: TI DRV8300D (fixed peak current through 10 Ω, bootstrap high side, no protection) + TPS7A1601 gate-drive LDO | **TI DRV8320H**: gate current set by IDRIVE (60 mA source / 120 mA sink: 75 kΩ to AGND, Yageo RC0201FR-0775KL), charge-pump high side, 2 A hold-off of the idle FET, V<sub>DS</sub> overcurrent, its own 3.3 V (DVDD) | Slower, controlled edges: the half-bridge simulation keeps both FETs well under their 60 V (the DRV8300 reached 68-70 V on the same FETs).  **IDRIVE 60/120 mA is a trade, chosen for heat**: the high side's turn-off pulls SHx to -9.5 V at 30 A in the 5 nH loop (-7.8 V at 20 A), past the driver's -7 V for 200 ns (STRESS.md section 3).  30/60 mA keeps it at -6.2 V but doubles the switching energy and nearly doubles the dead time: on a 50 °C day (5 m/s) the throttle AM32's temperature limit lets the stack hold falls from 34 to 28 % (hover 27 %).  30/60 mA is one resistor (18 kΩ, Yageo RC0201FR-0718KL) away.  No gate resistors, no bootstrap capacitors, no gate-drive LDO |
| Dead time: AM32 625 ns + DRV8300 ~215 ns | DRV8320H hold-off (it turns a gate on ~100 ns after it sees the other one discharged) + AM32 `DEAD_TIME 15` (125 ns) | Less body-diode conduction, which was a large share of rev 1's hover heat |
| MCU: STM32G071GBU6 (T<sub>J</sub> 105 °C), temperature limit on its own die | **Artery AT32F421G8U7** (T<sub>A</sub> 105 °C, T<sub>J</sub> 125 °C), AM32 groups AT_B + AT_045 | 20 °C more junction headroom; AM32 reads an NTC only on Artery parts |
| – | **NTC thermistor at each channel's FETs** (Murata NCU15XH103F60RC, 10 kΩ, -40..125 °C), beside phase C's high side | AM32's temperature limit now reads the power stage itself, so it acts in a burst before the FETs overheat, not after |
| MAX15062A 3.3 V buck + 33 µH inductor on the ESC | – : **the FC's 3.3 V buck** (TPS628501, 1 A) feeds the ESC's four channels down the stack lead's pin 4 (rev 1's TLM, unused), each channel through its own ferrite bead (Murata BLM03AX601SN1D, 0201: 600 Ω at 100 MHz, 0.85 Ω, 250 mA, at the mouth of the channel's way into the middle) to 100 nF at the MCU's VDD and 1 µF at its VDDA (Murata GRM155Z71A105KE01D, X7R 0402: Artery's 100 nF + 1 µF in one case).  Each driver's DVDD keeps its 1 µF, now the same 0402 (was Murata GCM188R71E105KA64D, 0603), to leave the bead its room | The first rev 2 layout ran each channel from its DRV8320H's DVDD, a linear regulator from the battery: the ground run put 0.46 W into each driver at 6S, beside its MCU.  A switching supply wastes about a tenth of that; the ESC has no room for one, and the FC's runs at about a quarter of its 1 A with the four channels on it (86 mA at the datasheets' maxima).  The ESC's MCUs now run only with the FC connected (bench flashing: both boards on the lead).  The bead sits where the channel's lines enter the middle, its feed laid before the PWM lines (`FIRST_LINES`): by the MCU's VDDA pin its turned copies sat in the next channel's gate lines, and over the driver no via could take its feed down |
| – | Driver enable from the battery through 33 kΩ and a 4.7 V Zener (ROHM EDZVT2R4.7B) | DVDD is off while the driver sleeps, so ENABLE cannot come from it |
| External electrolytic on the battery leads (2 × 100 µF) | **3 × Murata GCJ32EC71H106KA01L**, 10 µF 50 V X7S, soft terminations, on the board | The simulated ripple (4-10 A rms) overloads electrolytics; nothing hangs on the leads |
| X5R capacitors (bootstrap, driver supply: 85 °C) | X7R / X7S everywhere (125 °C) | Board temperatures above 85 °C |
| JST-SH 8-pin stack connector (1 A per contact, 85 °C) | **Soldered stack lead** at the ESC (0.8 mm pads, 1.27 mm pitch, filled vias) | No connector at the hot end; see the FC for the other end |
| Stack lead ground on the ESC's plane at the connector | **Kelvin ground** (FC_GND): the lead's ground wire has its own pad beside the battery minus pad, joined to the plane only through that pad's tap | With the FC's video pads also wired, the motor current's drop across the planes no longer drives a ground loop through the lead.  The pad sits at the battery pad, not in the middle with the other lead pads: the wire carries the FC's own current (up to 2 A on 2S with no video wires), which from the middle took a 0.1 mm trace 25 mm long through the busiest corner of motor 1's channel |
| Battery pads | 3.0 mm, round courtyards | Clear of the mounting hole's keep-out |
| 6 layers: one VBAT plane (In4), one GND plane (In1) | **8 layers**, 1.6 mm: GND on In1 and In4, VBAT on In6 and on In3, the channels' sense returns on In5, signals on F, In2 and B, and on In3 in a window under each channel's MCU and driver | Rev 1's battery current crowded into one 1 oz plane each way; two of each halve that copper's resistance and heat.  The battery current runs from the battery pads round the board's edge to the FET rows, not under the chips, where the MCU's analog lines needed a third signal layer (with In4's ground beside it) |
| – | **The MCU's analog inputs stay in the chips' strip**: the back-EMF dividers' 20 kΩ legs sit over the driver on its switch-node sense pins, the thermistor between the MCU and phase C's high side | The FET row has room for the gate and switch-node sense lines only; with the dividers' taps and the thermistor's line crossing it as well, no routing found every line a way.  Round the MCU most of the small parts sit over its exposed pad, where no via fits, so their lines share a few ways out: the MCU's analog lines (the neutral star first, then the comparators, the thermistor and the current filter) are laid before the board's router runs, and the parts' spots were searched (`tools/mcu_cluster_search.py`) so each of those lines, and every pin's via, keeps its way |
| Copper | Return vias out from under the high-side drain tabs; bridge capacitors along the row; shunt ground pad with eight plane vias; power vias per phase | Layout fixes from the rev 1 copper simulation |
| High-side gates and charge pump at 0.1 mm, like the logic | **0.13 mm**, like the battery and the phases (netclasses GATE_HI and PUMP) | They ride up to 11 V above the battery and the phases, about 36 V from ground: IPC-2221B asks 0.13 mm for 31-50 V under solder mask (B4) |
| ESC power LED | removed | One less part on the hottest board |
| On M2 soft-mount grommets, nothing under it | **On a machined aluminium heatsink** (`../src/heatsink.py`, `../mechanical/`): 6061 black anodized, 2.3 mm base with a pocket over every part on the ESC's bottom (as deep as its maker's maximum height), 11 fins 8 mm tall along the air, feet on the frame; a T-Global TG-A6200 1.5 mm gap pad squeezed to 1.25 mm between it and the board, set by four bosses the ESC is screwed down onto.  About 14.5 g, the pad 5 g; the stack stands 11.6 mm higher | A hard flight on a 50 °C day had AM32's temperature limit cutting the motors most of the time: the board alone cannot shed the heat into hot air (STRESS.md, rev 2 against rev 1).  The ESC carries no gyro, so it gives up its grommets for a machined gap; the FC keeps its own |

## Flight controller

| Rev 1 | Rev 2 | Why |
|---|---|---|
| Gyro: TDK ICM-45686 (85 °C); BMI270 as the second source | **TDK IIM-42652**, industrial, -40..+105 °C; ICM-42688-P (85 °C) as the same-pad second source | 85 °C is passed on a 50 °C day.  Betaflight 2025.12.5 mis-scales the IIM-42652; the firmware carries a fix (`../firmware/README.md`) |
| Flash: Winbond W25Q128JVPIM (85 °C) | **Infineon S25FL128LAGNFM010**, -40..+125 °C, AEC-Q100 grade 1 | Same land and pin order; the board runs without it |
| 9 V video BEC: TI LM76003 (T<sub>J</sub> 125 °C) + Vishay IHLP2525 6.8 µH, fed from the stack lead | **TI LMR38020F** (T<sub>J</sub> 150 °C) at 455 kHz + **TDK SPM6530T-150M-HZ** 15 µH (AEC-Q200, 125 °C, 3.0 mm tall), **fed only from its own battery pads** | The video's up to 18 W no longer goes through the stack lead.  Optional (`video` group): leaving it off breaks nothing else |
| – | **Thermostat**: TI TMP390A2 + Diodes BSS138DW pull the 9 V BEC's EN low above 96 °C, back on at 76 °C | On the ground with the video on and no airflow, rev 1's FC cooked itself (29 parts past their rating at 50 °C); now the video supply switches itself off and the supplies and processor stay in their ratings up to 50 °C.  It trips above the analog OSD's 85 °C, which still passes its rating on the ground in still air in the analog build (STRESS.md); a lower trip point would cut the video in flight |
| – | TVS (Vishay SMF33A) on the video battery input | The video input has its own wires now |
| 5 V BEC: LMR38020F at 1 MHz + TDK SPM5020T 4.7 µH | LMR38020F at **455 kHz** + SPM6530T 15 µH | Lower switching loss; inductor rated 125 °C |
| 3.3 V: TI TLV76733 LDO (linear: ~0.3 W) | **TI TPS628501** buck (T<sub>J</sub> 150 °C, 2.25 MHz) + TDK TFM252012ALMAR47MTAA 0.47 µH (150 °C) | Less heat on the FC.  It also feeds the ESC's four MCUs (stack lead pin 4): 166 mA of its own load plus 86 mA, a quarter of its 1 A |
| HD video: JST BM06B-SRSS-TB 6-pin port (-25..+85 °C), SBUS solder jumper; the analog OSD on every board | **Solder pads** `9V G T1 R1` for the air unit (SBUS, if the air unit carries it, onto `R2`); the analog OSD in its own option group, fitted only in the `analog` build (`circuit.BUILDS`; production files for the default `hd` build, `-analog` files beside them) | On the ground in still air the SH header, an 85 °C part with no hotter SH-compatible replacement, passed its rating within minutes; the AT7456E (85 °C) only matters to an analog quad |
| ESC lead connector: JST-SH 8-pin (1 A, 85 °C) | **Molex Micro-Lock Plus 505567**, right angle, positive lock, 1.5 A per contact, -40..+105 °C | The lead now carries only the 5 V side, well under 1.5 A, and on pin 4 (rev 1's TLM) the FC's 3.3 V to the ESC |
| Boot button: Omron B3U-1000P | **C&K KMR223G LFG**, gold contacts, -40..+125 °C | Small and rated for the heat |
| Buzzer and its driver | removed | Betaflight beeps the motors (DShot beacon) |
| HSE crystal: ECS-80-10-33-CHN (85 °C), 12 pF load caps | **NDK NX3225GD-8MHZ-STD-CRA-3**, -40..+150 °C, AEC-Q200, two-pad; 10 pF load caps | 85 °C crystal on a hot board |
| OSD crystal: Hosonic E3SB27E00000DE (-20..70 °C) | **Abracon ABM8AIG-27.000MHZ-12-2Z-T3**, -40..+125 °C, AEC-Q200, same land | 70 °C was the board's lowest rating.  JLC stock 1: JLC global sourcing or PCBWay (DigiKey).  JLC-stocked alternative on the same land: SCTF SX3B27.000F1010G30 (105 °C) |
| LEDs: Lite-On LTST-C191KRKT (85 °C) / LTST-C191TBKT (80 °C) | **Rohm SML-D15UWT86** red / **SMLD12BN1WT86** blue, -40..+100 °C | Rohm's 110 °C AEC-Q102 LEDs had no stock |
| X5R capacitors (regulator inputs and outputs, MCU, OSD) | X7R everywhere (125 °C) | 85 °C dielectric on a hot board |

## Both boards

| Rev 1 | Rev 2 | Why |
|---|---|---|
| No copper within 3.1 mm of a mounting hole, on every layer | **2.6 mm on the outer layers; 0.5 mm from the hole's and slot's walls on the inner ones** (1.0 mm for the ESC's battery planes); parts and silkscreen as before | 3.1 mm suits an M3 nut, not the M2 grommet.  The holes stay on the 25.5 mm pattern: `MOUNTING.md` |
| Board gap and grommet unspecified; "M3 also fits" | The FC on M2 grommets (flange 4.4-4.5 mm), the ESC screwed down on its heatsink, M2 hardware, **boards at least 6 mm apart** | The FC's inductors sit over the ESC's motor joints |

### Kept, and why

| Part | Rating | Why it stays |
|---|---|---|
| STM32G473CEU6 | 105 °C junction | The 130 °C STM32G473CEU3 is a drop-in (same pads, same image) but is out of stock everywhere (JLC 0; DigiKey 0, 52 weeks on 3 October): ST quotes 52 weeks for the whole STM32G4 family since mid-2026, and DigiKey, Mouser, JLC and ST's own store have none of the -3 grade.  The simulations check the junction against 105 °C |
| AT7456E analog OSD | -40..+85 °C | The only MAX7456-compatible chip still made; only in the `analog` build.  The thermostat keeps the video side from cooking on the ground |
| GCT USB4105 USB-C | -40..+85 °C | No 16-pin USB 2.0 receptacle in this style is rated 105 °C with stock (the 105 °C ones are 24-pin, other lands).  It carries nothing in flight |

## Sourcing notes

Most parts are JLCPCB stock.  These are not, or not in quantity:

| Part | Where |
|---|---|
| Infineon ISZ023N06LM6 (ESC FETs) | JLC global sourcing / PCBWay (DigiKey, Mouser) |
| Infineon S25FL128LAGNFM010 (flash) | JLC global sourcing / PCBWay |
| Abracon ABM8AIG-27.000MHZ-12-2Z-T3 (OSD crystal) | JLC stock 1; DigiKey |
| TI TPS628501 (3.3 V buck) | JLC stock 85; DigiKey |
| TDK TFM252012ALMAR47MTAA (3.3 V inductor) | JLC stock 130 |

## Firmware

- ESC: AM32 2.21, new target `RIDGE3_F421` (thermistor, current and voltage
  scales, dead time).
- FC: Betaflight 2025.12.5 with one board config and the IIM-42652 fix.

`../firmware/README.md` has both, and how to rebuild them.
