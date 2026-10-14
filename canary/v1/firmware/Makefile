# Canary v1 firmware. `make` builds build/canary.hex; `make flash` programs
# a board through the Tag-Connect pads with a USBasp (avrdude).
MCU = atmega328p
CC = avr-gcc
CFLAGS = -mmcu=$(MCU) -DF_CPU=8000000UL -Os -std=gnu11 -Wall -Wextra -Werror \
         -ffunction-sections -fdata-sections
LDFLAGS = -mmcu=$(MCU) -Wl,--gc-sections -lm
SRC = src/main.c src/detect.c
# lfuse 0xE2: internal 8 MHz RC, no CKDIV8; hfuse 0xD9: SPI on, no boot;
# efuse 0xFD: brown-out at 2.7 V
FUSES = -U lfuse:w:0xE2:m -U hfuse:w:0xD9:m -U efuse:w:0xFD:m

build/canary.hex: build/canary.elf
	avr-objcopy -O ihex -R .eeprom $< $@
	avr-size --mcu=$(MCU) -C $<

build/canary.elf: $(SRC) src/*.h
	mkdir -p build
	$(CC) $(CFLAGS) $(SRC) -o $@ $(LDFLAGS)

flash: build/canary.hex
	avrdude -c usbasp -p m328p $(FUSES) -U flash:w:$<:i

clean:
	rm -rf build
.PHONY: flash clean
