#!/usr/bin/env python3
"""Put firmware on LayerCam Pro's ESP32-C6 (the Wi-Fi module) from the camera itself.

    layercam-c6-flash --flasher-args /usr/share/layercam-c6/flasher_args.json
    layercam-c6-flash 0x0 bootloader.bin 0x8000 partition-table.bin 0x10000 network_adapter.bin

Runs on the camera (as root; Python 3 standard library only, nothing to
install: no esptool, no pyserial).  The C6's UART0 is wired to the RV1106's
UART1_M0 (/dev/ttyS1), its EN to GPIO1_A2 and its GPIO9 boot strap to
GPIO0_A2 (src/circuit.py; layercam/board.py).  The tool:

1. takes the module away from Linux: unloads esp32_sdio, unbinds the SDIO
   controller and the mmc-pwrseq that owns EN (the device tree's
   sdio-pwrseq), so both GPIOs are free;
2. holds GPIO9 low and pulses EN: the C6's ROM starts its serial download
   mode (Espressif's boot-mode straps: GPIO9 low at reset = download);
3. speaks the ROM loader's protocol (SLIP frames: SYNC, READ_REG for the
   chip, SPI_ATTACH, SPI_SET_PARAMS, CHANGE_BAUDRATE, FLASH_BEGIN /
   FLASH_DATA / FLASH_END, SPI_FLASH_MD5), the same commands esptool and
   esp-serial-flasher send to a ROM without a stub, and checks each image's
   MD5 as the C6 read it back from its flash;
4. lets GPIO9 go (10k pull-up: boot from flash), binds the SDIO controller
   again (the pwrseq pulses EN, 1.5 s) and loads esp32_sdio again.

The images are esp-hosted-linux's network_adapter built for esp32c6
(README.md, Wi-Fi firmware); flasher_args.json from its build/ folder gives
the offsets.  After the first flash, esp-hosted can also update the C6 over
SDIO (insmod esp32_sdio.ko ota_file=...).  A board whose C6 does not answer
here can still be flashed through its USB pads (TP6 D-, TP7 D+) with esptool
on a computer.

Tested against a simulated ROM over a pseudo-terminal (tests/test_c6flash.py),
not yet against a real ESP32-C6.
"""
import argparse, hashlib, json, os, select, struct, subprocess, sys, termios, time

# layercam/board.py (checked by the tests): GPIO1_A2 = 34, GPIO0_A2 = 2
EN_GPIO, BOOT_GPIO, PORT = 34, 2, '/dev/ttyS1'
# the device tree's SDIO controller (SDMMC0, mmc@ffaa0000) and its pwrseq
MMC_DRIVER, MMC_DEVICE = 'dwmmc_rockchip', 'ffaa0000.mmc'
PWRSEQ_DRIVER, PWRSEQ_DEVICE = 'pwrseq_simple', 'sdio-pwrseq'
MODULE = 'esp32_sdio'

ROM_BAUD = 115200
CHIP_MAGIC_REG, ESP32C6_MAGIC = 0x40001000, 0x2CE0806F
FLASH_SIZE = 4 * 1024 * 1024        # -H4: 4 MB of flash in the module
FLASH_BLOCK = 0x400                 # the ROM loader's write block (esptool: FLASH_WRITE_SIZE)
SECTOR = 0x1000

SYNC, READ_REG, SPI_SET_PARAMS, SPI_ATTACH, CHANGE_BAUDRATE = 0x08, 0x0A, 0x0B, 0x0D, 0x0F
FLASH_BEGIN, FLASH_DATA, FLASH_END, SPI_FLASH_MD5 = 0x02, 0x03, 0x04, 0x13
CHECKSUM_SEED = 0xEF
ERRORS = {0x05: 'invalid command or length', 0x06: 'command failed', 0x07: 'bad checksum',
          0x08: 'flash write failed (read back differs)', 0x09: 'flash read failed', 0x0a: 'read too long'}
BAUDS = {115200: termios.B115200, 230400: termios.B230400, 460800: termios.B460800,
         921600: getattr(termios, 'B921600', None)}


class FlashError(Exception):
    pass


# ---- SLIP and the ROM loader's packets ----

def slip(data):
    return b'\xc0' + data.replace(b'\xdb', b'\xdb\xdd').replace(b'\xc0', b'\xdb\xdc') + b'\xc0'


def unslip(frame):
    return frame.replace(b'\xdb\xdc', b'\xc0').replace(b'\xdb\xdd', b'\xdb')


def checksum(data, seed=CHECKSUM_SEED):
    for b in data:
        seed ^= b
    return seed


def command(op, data=b'', chk=0):
    """A request: direction 0, command, length, checksum (data commands only), data."""
    return struct.pack('<BBHI', 0, op, len(data), chk) + data


def parse_response(pkt):
    """-> (op, value, data) of a response packet, or None for anything else."""
    if len(pkt) < 8 or pkt[0] != 1:
        return None
    op, size, value = struct.unpack('<xBHI', pkt[:8])
    data = pkt[8:]
    if len(data) != size:
        return None
    return op, value, data


def images_from_args(pairs, flasher_args=None):
    """[(offset, bytes, name)] from ADDR FILE pairs or an ESP-IDF flasher_args.json."""
    items = []
    if flasher_args:
        with open(flasher_args) as f:
            files = json.load(f)['flash_files']
        base = os.path.dirname(os.path.abspath(flasher_args))
        items += [(k, os.path.join(base, v)) for k, v in files.items()]
    if len(pairs) % 2:
        raise FlashError('give the images as ADDRESS FILE pairs')
    items += [(pairs[i], pairs[i + 1]) for i in range(0, len(pairs), 2)]
    if not items:
        raise FlashError('nothing to write: give --flasher-args or ADDRESS FILE pairs')
    out = []
    for addr, path in items:
        try:
            offset = int(addr, 0)
        except ValueError:
            raise FlashError('not an address: %s' % addr)
        with open(path, 'rb') as f:
            data = f.read()
        if offset % SECTOR:
            raise FlashError('%s: offset 0x%x is not on a 4 KiB sector' % (path, offset))
        if not data or offset + len(data) > FLASH_SIZE:
            raise FlashError('%s: empty, or past the end of the 4 MB flash' % path)
        out.append((offset, data, path))
    out.sort()
    for (a, da, na), (b, _, nb) in zip(out, out[1:]):
        if a + len(da) > b:
            raise FlashError('%s and %s overlap' % (na, nb))
    return out


# ---- the serial port ----

class Serial:
    def __init__(self, path, baud=ROM_BAUD):
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY)
        self.buf = b''
        self.set_baud(baud)

    def set_baud(self, baud):
        speed = BAUDS.get(baud)
        if speed is None:
            raise FlashError('baud rate %d not supported' % baud)
        a = termios.tcgetattr(self.fd)
        a[0] = 0                                                   # iflag: raw
        a[1] = 0                                                   # oflag
        a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL        # 8N1, no flow control
        a[3] = 0                                                   # lflag: no echo, no canonical mode
        a[4] = a[5] = speed
        a[6][termios.VMIN], a[6][termios.VTIME] = 0, 0
        termios.tcsetattr(self.fd, termios.TCSANOW, a)

    def write(self, data):
        while data:
            n = os.write(self.fd, data)
            data = data[n:]

    def flush_input(self):
        termios.tcflush(self.fd, termios.TCIFLUSH)
        self.buf = b''

    def packet(self, timeout):
        """The next SLIP frame's content, or None after timeout seconds.
        Anything outside frames (the ROM's boot text) is skipped."""
        end = time.monotonic() + timeout
        while True:
            start = self.buf.find(b'\xc0')
            if start >= 0:
                stop = self.buf.find(b'\xc0', start + 1)
                if stop > start:
                    frame, self.buf = self.buf[start + 1:stop], self.buf[stop:]
                    if frame:
                        return unslip(frame)
                    continue                     # two delimiters in a row: the second starts a frame
                self.buf = self.buf[start:]
            else:
                self.buf = b''
            left = end - time.monotonic()
            if left <= 0:
                return None
            r, _, _ = select.select([self.fd], [], [], left)
            if r:
                self.buf += os.read(self.fd, 4096)

    def close(self):
        os.close(self.fd)


class Loader:
    """The ESP32-C6 ROM loader's commands (no flasher stub)."""

    def __init__(self, port, log=print):
        self.port, self.log = port, log

    def call(self, op, data=b'', chk=0, timeout=3.0, payload=0):
        """Send one command, return (value, payload bytes).  The response
        ends in the status bytes (failed, error); payload is the number of
        data bytes before them (32 for the ROM's MD5)."""
        self.port.write(slip(command(op, data, chk)))
        end = time.monotonic() + timeout
        while True:
            pkt = self.port.packet(max(0.0, end - time.monotonic()))
            if pkt is None:
                raise FlashError('no answer to command 0x%02x' % op)
            r = parse_response(pkt)
            if r is None or r[0] != op:
                continue
            _, value, body = r
            status = body[payload:]
            if len(status) < 2:
                raise FlashError('short answer to command 0x%02x' % op)
            if status[0]:
                raise FlashError('command 0x%02x refused: %s' % (op, ERRORS.get(status[1], '0x%02x' % status[1])))
            return value, body[:payload]

    def sync(self, attempts=10):
        frame = b'\x07\x07\x12\x20' + b'\x55' * 32
        for _ in range(attempts):
            try:
                self.call(SYNC, frame, timeout=0.2)
            except FlashError:
                continue
            # the ROM answers a SYNC up to eight times: let the rest go by
            while self.port.packet(0.1) is not None:
                pass
            return True
        raise FlashError('the C6 did not answer: not in download mode (GPIO9 low at reset?) or wrong port')

    def check_chip(self):
        magic, _ = self.call(READ_REG, struct.pack('<I', CHIP_MAGIC_REG))
        if magic != ESP32C6_MAGIC:
            raise FlashError('not an ESP32-C6 (chip magic 0x%08x)' % magic)

    def attach(self):
        self.call(SPI_ATTACH, struct.pack('<II', 0, 0))
        self.call(SPI_SET_PARAMS, struct.pack('<IIIIII', 0, FLASH_SIZE, 0x10000, SECTOR, 0x100, 0xFFFF))

    def change_baud(self, baud):
        if baud == ROM_BAUD:
            return
        if BAUDS.get(baud) is None:
            raise FlashError('baud rate %d not supported' % baud)
        self.call(CHANGE_BAUDRATE, struct.pack('<II', baud, 0))
        self.port.set_baud(baud)
        time.sleep(0.05)
        self.port.flush_input()

    def write(self, offset, data, name=''):
        blocks = (len(data) + FLASH_BLOCK - 1) // FLASH_BLOCK
        mb = len(data) / 1e6
        self.call(FLASH_BEGIN, struct.pack('<IIIII', len(data), blocks, FLASH_BLOCK, offset, 0),
                  timeout=max(3.0, 30 * mb))                       # the ROM erases the region first
        for seq in range(blocks):
            block = data[seq * FLASH_BLOCK:(seq + 1) * FLASH_BLOCK]
            block += b'\xff' * (FLASH_BLOCK - len(block))
            self.call(FLASH_DATA, struct.pack('<IIII', len(block), seq, 0, 0) + block, checksum(block), timeout=5.0)
        _, md5 = self.call(SPI_FLASH_MD5, struct.pack('<IIII', offset, len(data), 0, 0),
                           timeout=max(3.0, 8 * mb), payload=32)
        if md5.decode('ascii', 'replace').lower() != hashlib.md5(data).hexdigest():
            raise FlashError('%s: the flash does not read back as written (MD5)' % (name or hex(offset)))
        self.log('  0x%06x  %7d bytes  %s  ok' % (offset, len(data), name))

    def finish(self):
        self.call(FLASH_END, struct.pack('<I', 1))                 # stay in the loader: EN restarts it


# ---- the board: GPIOs, the SDIO driver ----

class Board:
    def __init__(self, root='', run=subprocess.run, sleep=time.sleep):
        self.root, self.sys, self.proc = root, root + '/sys', root + '/proc'
        self.run, self.sleep = run, sleep
        self.exported, self.was_loaded, self.unbound = [], False, []

    def _write(self, path, value):
        with open(self.sys + path, 'w') as f:
            f.write(str(value))

    def gpio(self, n, value=None):
        """Drive GPIO n (0/1), or with None let it go (input; the board's pull wins)."""
        g = '/class/gpio/gpio%d' % n
        if not os.path.exists(self.sys + g):
            self._write('/class/gpio/export', n)
            self.exported.append(n)
        if value is None:
            self._write(g + '/direction', 'in')
        else:
            self._write(g + '/direction', 'high' if value else 'low')

    def release_wifi(self):
        """esp32_sdio out, then the SDIO controller and the pwrseq unbound."""
        try:
            with open(self.proc + '/modules') as f:
                self.was_loaded = any(line.split()[0] == MODULE for line in f if line.strip())
        except OSError:
            self.was_loaded = False
        if self.was_loaded:
            self.run(['rmmod', MODULE], check=False)
        for drv, dev in ((MMC_DRIVER, MMC_DEVICE), (PWRSEQ_DRIVER, PWRSEQ_DEVICE)):
            if os.path.exists('%s/bus/platform/drivers/%s/%s' % (self.sys, drv, dev)):
                self._write('/bus/platform/drivers/%s/unbind' % drv, dev)
                self.unbound.append((drv, dev))

    def download_mode(self):
        self.gpio(BOOT_GPIO, 0)              # GPIO9 low: serial download at reset
        self.gpio(EN_GPIO, 0)
        self.sleep(0.02)                     # EN low well over the 50 us the C6 needs
        self.gpio(EN_GPIO, 1)
        self.sleep(0.1)                      # GPIO9 held low past the strap sampling, the ROM up

    def restore(self):
        """GPIO9 let go (pull-up: boot from flash), EN back to the pwrseq,
        the SDIO controller and esp32_sdio back."""
        errors = []
        for n, v in ((BOOT_GPIO, None), (EN_GPIO, 0)):
            try:
                self.gpio(n, v)
            except OSError as e:
                errors.append(str(e))
        for n in reversed(self.exported):
            try:
                self._write('/class/gpio/unexport', n)
            except OSError as e:
                errors.append(str(e))
        self.exported = []
        for drv, dev in reversed(self.unbound):    # the pwrseq first, then the controller that uses it
            try:
                self._write('/bus/platform/drivers/%s/bind' % drv, dev)
            except OSError as e:
                errors.append(str(e))
        self.unbound = []
        if self.was_loaded:
            for ko in ('/lib/modules/esp32_sdio.ko', '/oem/usr/ko/esp32_sdio.ko'):
                if os.path.exists(self.root + ko):
                    self.run(['insmod', self.root + ko], check=False)
                    break
        return errors


def flash(images, port_path=PORT, baud=460800, board=None, log=print, open_port=Serial):
    """Write the images to the C6; returns when it has been put back."""
    board = board or Board()
    log('releasing the Wi-Fi module from Linux')
    board.release_wifi()
    port = None
    try:
        board.download_mode()
        port = open_port(port_path, ROM_BAUD)
        port.flush_input()
        rom = Loader(port, log)
        rom.sync()
        rom.check_chip()
        log('ESP32-C6 in download mode on %s' % port_path)
        rom.attach()
        rom.change_baud(baud)
        for offset, data, name in images:
            rom.write(offset, data, name)
        rom.finish()
    finally:
        if port:
            port.close()
        problems = board.restore()
        for p in problems:
            log('warning: %s' % p)
    log('done: the C6 restarts from its flash with the SDIO driver')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('images', nargs='*', metavar='ADDRESS FILE', help='offset and image, e.g. 0x10000 app.bin')
    ap.add_argument('--flasher-args', help="ESP-IDF's build/flasher_args.json (offsets and files)")
    ap.add_argument('--port', default=PORT)
    ap.add_argument('--baud', type=int, default=460800, help='after the sync at 115200 (default 460800)')
    a = ap.parse_args(argv)
    try:
        images = images_from_args(a.images, a.flasher_args)
        flash(images, a.port, a.baud)
    except (FlashError, OSError) as e:
        print('layercam-c6-flash: %s' % e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
