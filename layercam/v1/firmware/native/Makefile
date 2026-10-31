# layercam-media, cross-compiled with the Luckfox SDK's toolchain against the
# rockit MPI and rkaiq headers and libraries that luckfox_pico_rkmpi_example
# ships (include/, lib/uclibc/).  Not yet built here: check the paths
# against your SDK checkout.
#
#   make LUCKFOX_SDK_PATH=~/luckfox-pico RKMPI=~/luckfox_pico_rkmpi_example
#   make ... HAVE_LIBJPEG=1 JPEG_INC=... JPEG_LIB=...   (adds --encode-jpegs)
#   make check RKMPI=...      syntax check with the host gcc (what was done on a PC)

LUCKFOX_SDK_PATH ?= $(HOME)/luckfox-pico
RKMPI ?= $(HOME)/luckfox_pico_rkmpi_example
CROSS ?= $(LUCKFOX_SDK_PATH)/tools/linux/toolchain/arm-rockchip830-linux-uclibcgnueabihf/bin/arm-rockchip830-linux-uclibcgnueabihf-
CC = $(CROSS)gcc

INC = $(RKMPI)/include
CFLAGS += -std=gnu99 -O2 -Wall -Wextra -DISP_HW_V30 -DRKPLATFORM=ON -DARCH64=OFF -DUAPI2 \
	-I$(INC) -I$(INC)/rkaiq -I$(INC)/rkaiq/uAPI2 -I$(INC)/rkaiq/common -I$(INC)/rkaiq/xcore \
	-I$(INC)/rkaiq/algos -I$(INC)/rkaiq/iq_parser -I$(INC)/rkaiq/iq_parser_v2 -I$(INC)/rkaiq/smartIr
LDFLAGS += -L$(RKMPI)/lib/uclibc -Wl,-rpath-link,$(RKMPI)/lib/uclibc
LDLIBS = -lrockit -lrockchip_mpp -lrkaiq -lpthread -lm

ifeq ($(HAVE_LIBJPEG),1)
CFLAGS += -DHAVE_LIBJPEG $(if $(JPEG_INC),-I$(JPEG_INC))
LDFLAGS += $(if $(JPEG_LIB),-L$(JPEG_LIB))
LDLIBS += -ljpeg
endif

layercam-media: layercam-media.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS) $(LDLIBS)

check:
	gcc -fsyntax-only $(CFLAGS) layercam-media.c
	gcc -fsyntax-only -DHAVE_LIBJPEG $(if $(JPEG_INC),-I$(JPEG_INC)) $(CFLAGS) layercam-media.c

clean:
	rm -f layercam-media

.PHONY: check clean
