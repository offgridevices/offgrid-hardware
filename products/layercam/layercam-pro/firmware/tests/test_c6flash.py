"""tools/layercam-c6-flash.py against a simulated ESP32-C6 ROM loader on a
pseudo-terminal, and a fake /sys: the frames, the checksums, the MD5 check,
the boot straps and the SDIO driver let go and given back."""
import hashlib, importlib.util, json, os, shutil, struct, tempfile, threading, unittest

from layercam import board

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('c6flash', os.path.join(HERE, '..', 'tools', 'layercam-c6-flash.py'))
c6 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c6)


class FakeRom(threading.Thread):
    """Answers as the C6's ROM loader does: SLIP frames, (failed, error)
    status bytes at the end of each answer, eight answers to a SYNC, boot
    text before the first frame."""

    def __init__(self, fd, magic=c6.ESP32C6_MAGIC, corrupt=False, silent=False):
        super().__init__(daemon=True)
        self.fd, self.magic, self.corrupt, self.silent = fd, magic, corrupt, silent
        self.flash = bytearray(b'\xff' * c6.FLASH_SIZE)
        self.log, self.begin, self.seq = [], None, 0
        self.stop = False

    def send(self, op, value=0, data=b'', ok=True, error=0):
        body = data + bytes([0 if ok else 1, error])
        os.write(self.fd, c6.slip(struct.pack('<BBHI', 1, op, len(body), value) + body))

    def handle(self, pkt):
        direction, op, size, chk = struct.unpack('<BBHI', pkt[:8])
        data = pkt[8:]
        assert direction == 0 and size == len(data), (direction, size, len(data))
        self.log.append(op)
        if op == c6.SYNC:
            assert data == b'\x07\x07\x12\x20' + b'\x55' * 32
            for _ in range(8):
                self.send(op)
        elif op == c6.READ_REG:
            (addr,) = struct.unpack('<I', data)
            self.send(op, self.magic if addr == c6.CHIP_MAGIC_REG else 0)
        elif op in (c6.SPI_ATTACH, c6.SPI_SET_PARAMS, c6.CHANGE_BAUDRATE, c6.FLASH_END):
            self.send(op)
        elif op == c6.FLASH_BEGIN:
            erase, blocks, bsize, offset, enc = struct.unpack('<IIIII', data)
            assert bsize == c6.FLASH_BLOCK and enc == 0 and offset % 0x1000 == 0
            self.begin, self.seq = (offset, blocks, bsize), 0
            self.send(op)
        elif op == c6.FLASH_DATA:
            n, seq, _, _ = struct.unpack('<IIII', data[:16])
            block = data[16:]
            offset, blocks, bsize = self.begin
            if c6.checksum(block) != chk:
                return self.send(op, ok=False, error=0x07)
            assert n == len(block) == bsize and seq == self.seq < blocks
            if self.corrupt and seq == 0:
                block = b'\x00' + block[1:]
            self.flash[offset + seq * bsize:offset + (seq + 1) * bsize] = block
            self.seq += 1
            self.send(op)
        elif op == c6.SPI_FLASH_MD5:
            addr, n, _, _ = struct.unpack('<IIII', data)
            self.send(op, data=hashlib.md5(bytes(self.flash[addr:addr + n])).hexdigest().encode())
        else:
            self.send(op, ok=False, error=0x05)

    def run(self):
        import select
        buf = b''
        os.write(self.fd, b'ESP-ROM:esp32c6-20220919\r\nwaiting for download\r\n')
        while not self.stop:
            r, _, _ = select.select([self.fd], [], [], 0.05)
            if not r:
                continue
            try:
                buf += os.read(self.fd, 65536)
            except OSError:
                return
            while True:
                a = buf.find(b'\xc0')
                b = buf.find(b'\xc0', a + 1) if a >= 0 else -1
                if b < 0:
                    break
                frame, buf = buf[a + 1:b], buf[b + 1:]
                if frame and not self.silent:
                    self.handle(c6.unslip(frame))


class FakeBoard(c6.Board):
    def __init__(self, root, loaded=True):
        os.makedirs(root + '/sys/class/gpio')
        os.makedirs(root + '/proc')
        for drv, dev in ((c6.MMC_DRIVER, c6.MMC_DEVICE), (c6.PWRSEQ_DRIVER, c6.PWRSEQ_DEVICE)):
            os.makedirs('%s/sys/bus/platform/drivers/%s/%s' % (root, drv, dev))
        with open(root + '/proc/modules', 'w') as f:
            f.write('esp32_sdio 98304 0 - Live 0x00000000\n' if loaded else 'rockit 1 0 - Live 0\n')
        os.makedirs(root + '/lib/modules')
        open(root + '/lib/modules/esp32_sdio.ko', 'w').close()
        self.writes, self.commands = [], []
        super().__init__(root, run=lambda argv, check: self.commands.append(argv), sleep=lambda s: None)

    def _write(self, path, value):
        self.writes.append((path, str(value)))
        if path.endswith('/export'):
            os.makedirs(self.sys + '/class/gpio/gpio%s' % value, exist_ok=True)
        elif path.endswith('/unexport'):
            shutil.rmtree(self.sys + '/class/gpio/gpio%s' % value)
        else:
            super()._write(path, value)


class C6Flash(unittest.TestCase):
    def setUp(self):
        self.master, self.slave = os.openpty()
        self.port = os.ttyname(self.slave)
        self.tmp = tempfile.mkdtemp()
        self.images = [(0x0, os.urandom(3000), 'bootloader.bin'), (0x8000, os.urandom(3072), 'partitions.bin'),
                       (0x10000, os.urandom(5000), 'network_adapter.bin')]

    def tearDown(self):
        os.close(self.master)
        os.close(self.slave)

    def run_flash(self, rom, brd=None, baud=460800):
        rom.start()
        brd = brd or FakeBoard(os.path.join(self.tmp, 'root'))
        lines = []
        try:
            c6.flash(self.images, self.port, baud, board=brd, log=lines.append)
        finally:
            rom.stop = True
            rom.join(2)
        return brd, lines

    def test_pins_match_the_board(self):
        self.assertEqual((c6.EN_GPIO, c6.BOOT_GPIO, c6.PORT), (board.WIFI_EN, board.WIFI_BOOT, board.WIFI_UART))
        self.assertEqual((board.gpio_number('GPIO1_A2'), board.gpio_number('GPIO0_A2')), (34, 2))

    def test_slip(self):
        raw = b'\x01\xc0\x02\xdb\x03'
        self.assertEqual(c6.slip(raw), b'\xc0\x01\xdb\xdc\x02\xdb\xdd\x03\xc0')
        self.assertEqual(c6.unslip(c6.slip(raw)[1:-1]), raw)
        self.assertEqual(c6.checksum(b''), 0xEF)
        self.assertEqual(c6.checksum(b'\xef'), 0)

    def test_flash(self):
        rom = FakeRom(self.master)
        brd, lines = self.run_flash(rom)
        for offset, data, _ in self.images:
            self.assertEqual(bytes(rom.flash[offset:offset + len(data)]), data)
            pad = (-len(data)) % c6.FLASH_BLOCK
            self.assertEqual(bytes(rom.flash[offset + len(data):offset + len(data) + pad]), b'\xff' * pad)
        ops = rom.log
        self.assertEqual(ops[:5], [c6.SYNC, c6.READ_REG, c6.SPI_ATTACH, c6.SPI_SET_PARAMS, c6.CHANGE_BAUDRATE])
        self.assertEqual(ops.count(c6.FLASH_BEGIN), 3)
        self.assertEqual(ops.count(c6.SPI_FLASH_MD5), 3)
        self.assertEqual(ops.count(c6.FLASH_DATA), 3 + 3 + 5)          # 1 KiB blocks
        self.assertEqual(ops[-1], c6.FLASH_END)
        self.assertTrue(any('done' in ln for ln in lines))
        w = brd.writes
        # driver out, controller then pwrseq unbound; GPIO9 low before EN rises; all given back
        self.assertEqual(brd.commands[0], ['rmmod', 'esp32_sdio'])
        unbind = [x for x in w if x[0].endswith('/unbind')]
        self.assertEqual([v for _, v in unbind], [c6.MMC_DEVICE, c6.PWRSEQ_DEVICE])
        boot_low = w.index(('/class/gpio/gpio2/direction', 'low'))
        en = [i for i, x in enumerate(w) if x[0] == '/class/gpio/gpio34/direction']
        self.assertEqual([w[i][1] for i in en[:2]], ['low', 'high'])
        self.assertLess(boot_low, en[0])
        self.assertIn(('/class/gpio/gpio2/direction', 'in'), w)
        bind = [v for p, v in w if p.endswith('/bind')]
        self.assertEqual(bind, [c6.PWRSEQ_DEVICE, c6.MMC_DEVICE])
        self.assertLess(max(i for i, x in enumerate(w) if x[0].endswith('/unexport')),
                        min(i for i, x in enumerate(w) if x[0].endswith('/bind')))
        self.assertEqual(brd.commands[-1][0], 'insmod')
        self.assertEqual(os.listdir(brd.sys + '/class/gpio'), [])

    def test_rom_baud_only(self):
        rom = FakeRom(self.master)
        self.run_flash(rom, baud=115200)
        self.assertNotIn(c6.CHANGE_BAUDRATE, rom.log)

    def test_bad_flash_is_reported_and_board_restored(self):
        rom = FakeRom(self.master, corrupt=True)
        brd = FakeBoard(os.path.join(self.tmp, 'root'))
        with self.assertRaisesRegex(c6.FlashError, 'MD5'):
            self.run_flash(rom, brd)
        self.assertEqual([v for p, v in brd.writes if p.endswith('/bind')], [c6.PWRSEQ_DEVICE, c6.MMC_DEVICE])

    def test_not_a_c6(self):
        with self.assertRaisesRegex(c6.FlashError, 'not an ESP32-C6'):
            self.run_flash(FakeRom(self.master, magic=0x1B31506F))

    def test_no_answer(self):
        brd = FakeBoard(os.path.join(self.tmp, 'root'), loaded=False)
        with self.assertRaisesRegex(c6.FlashError, 'did not answer'):
            self.run_flash(FakeRom(self.master, silent=True), brd)
        self.assertEqual(brd.commands, [])                       # esp32_sdio was not loaded: left alone
        self.assertIn(('/class/gpio/gpio2/direction', 'in'), brd.writes)

    def test_refused_command(self):
        loader = c6.Loader(c6.Serial(self.port))
        rom = FakeRom(self.master)
        rom.start()
        try:
            with self.assertRaisesRegex(c6.FlashError, 'refused: invalid command'):
                loader.call(0x55)
        finally:
            rom.stop = True
            rom.join(2)
            loader.port.close()

    def test_images(self):
        d = self.tmp
        for name, size in (('bootloader/bootloader.bin', 20000), ('partition_table/partition-table.bin', 3072),
                           ('network_adapter.bin', 900000)):
            os.makedirs(os.path.dirname(os.path.join(d, name)), exist_ok=True)
            with open(os.path.join(d, name), 'wb') as f:
                f.write(b'\x01' * size)
        args = os.path.join(d, 'flasher_args.json')
        with open(args, 'w') as f:
            json.dump({'flash_files': {'0x10000': 'network_adapter.bin', '0x0': 'bootloader/bootloader.bin',
                                       '0x8000': 'partition_table/partition-table.bin'},
                       'flash_settings': {'flash_size': '4MB'}}, f)
        imgs = c6.images_from_args([], args)
        self.assertEqual([o for o, _, _ in imgs], [0x0, 0x8000, 0x10000])
        self.assertEqual(len(imgs[2][1]), 900000)
        boot = os.path.join(d, 'bootloader/bootloader.bin')
        with self.assertRaisesRegex(c6.FlashError, 'overlap'):
            c6.images_from_args(['0x0', boot, '0x1000', boot])
        with self.assertRaisesRegex(c6.FlashError, 'sector'):
            c6.images_from_args(['0x100', boot])
        with self.assertRaisesRegex(c6.FlashError, '4 MB'):
            c6.images_from_args(['0x3ff000', boot])
        with self.assertRaisesRegex(c6.FlashError, 'pairs'):
            c6.images_from_args(['0x0'])
        with self.assertRaisesRegex(c6.FlashError, 'nothing to write'):
            c6.images_from_args([])
        self.assertEqual(c6.main(['0x0']), 1)


if __name__ == '__main__':
    unittest.main()
