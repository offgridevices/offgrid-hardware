# Canary v1 firmware

AVR C for the ATmega328P-AU at 8 MHz (internal RC), 3.3 V. No Arduino core.

| File | What |
|---|---|
| `src/board.h` | pin map (checked against `src/circuit.py` and the routed board by `src/check_pins.py`) |
| `src/detect.c/.h` | the detector: evidence grading, alarm rules, hush, latching. Pure C, no hardware |
| `src/main.c` | drivers (TWI, ADC, timers, UART), Sensirion SGP40/SHT40/SCD41 commands with CRC-8, LED and sounder patterns |

Build: `make` → `build/canary.hex` (needs `gcc-avr avr-libc`).
Flash: `make flash` (USBasp on the Tag-Connect TC2030 pads; sets fuses
lfuse 0xE2, hfuse 0xD9, efuse 0xFD).

Once a second: NTCs (tab, probe), SHT40, SGP40 (humidity-compensated raw
signal), SCD41 data-ready/read (new CO₂ every 5 s), then `detect_step()`.
Telemetry on TXD at 38400 8N1. Watchdog 2 s.

Timers: Timer0 PWM (red OC0A, amber OC0B), Timer2 PWM (green OC2B) + 488 Hz
tick, Timer1 CTC toggling OC1A (PB1) at 4 kHz for the sounder.
