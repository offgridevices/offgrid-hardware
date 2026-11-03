"""tools/sc4336h-port.py: the SC4336H driver made from the SDK's sc4336.c,
names changed and nothing else (no register value of its own)."""
import importlib.util, os, re, subprocess, sys, tempfile, unittest

from layercam import board
from tests.test_image import SENSOR_FILES

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, '..', 'tools', 'sc4336h-port.py')
spec = importlib.util.spec_from_file_location('sc4336h_port', TOOL)
port = importlib.util.module_from_spec(spec)
spec.loader.exec_module(port)

# more of sc4336.c's shape: names in functions, structs, strings and macros,
# a register table, the ID check, and the SC4336P left alone
SOURCE = SENSOR_FILES['sc4336.c'] + '''#define SC4336_XVCLK_FREQ\t\t24000000
#define SC4336_LANES\t\t\t2
static const struct regval sc4336_linear_10_2560x1440_regs[] = {
\t{0x0103, 0x01},
\t{0x301f, 0x04},
};
struct sc4336 { struct clk *xvclk; };
static int sc4336_check_sensor_id(struct sc4336 *sc4336, struct i2c_client *client)
{
\tret = sc4336_read_reg(client, SC4336_REG_CHIP_ID, SC4336_REG_VALUE_16BIT, &id);
\tif (id != CHIP_ID) {
\t\tdev_err(dev, "Unexpected sensor id(%06x), ret(%d)\\n", id, ret);
\t\treturn -ENODEV;
\t}
}
static const struct i2c_device_id sc4336_match_id[] = { { "smartsens,sc4336", 0 }, { } };
/* see also sc4336p.c and SC4336P */
MODULE_DESCRIPTION("smartsens sc4336 sensor driver");
'''


class Port(unittest.TestCase):
    def test_names_changed_nothing_else(self):
        out = port.port_source(SOURCE)
        self.assertIn('{ .compatible = "smartsens,sc4336h" }', out)
        self.assertIn('{ "smartsens,sc4336h", 0 }', out)
        self.assertIn('#define SC4336H_NAME\t\t\t"sc4336h"', out)
        self.assertIn('static int sc4336h_check_sensor_id(struct sc4336h *sc4336h,', out)
        self.assertIn('sc4336p.c and SC4336P', out)                  # the other sensor's name untouched
        self.assertIn('TODO(SC4336H)', out)
        self.assertEqual(out.splitlines()[0], '// SPDX-License-Identifier: GPL-2.0')
        # take the header out and the names back: the SC4336's file again, but for the ID
        body = re.sub(r'/\*\n \* GENERATED.*?\*/\n', '', out, flags=re.S)
        back = re.sub(r'sc4336h', 'sc4336', re.sub(r'SC4336H', 'SC4336', body))
        self.assertEqual(back.replace('0x10000', '0xdc42'), SOURCE)
        # the register table is the SC4336's, value for value
        self.assertIn('sc4336h_linear_10_2560x1440_regs[] = {\n\t{0x0103, 0x01},\n\t{0x301f, 0x04},', out)

    def test_chip_id(self):
        self.assertIn('#define CHIP_ID\t\t\t\t0x10000\n', port.port_source(SOURCE))
        out = port.port_source(SOURCE, 0xab12)
        self.assertIn('#define CHIP_ID\t\t\t\t0xab12\n', out)
        self.assertIn('CHIP_ID: 0xab12, read from a board', out)
        self.assertEqual(board.SENSOR_CHIP_ID_REG, 0x3107)
        self.assertIn('SC4336H_REG_CHIP_ID\t\t0x3107', out)

    def test_refuses_another_file(self):
        with self.assertRaises(port.PortError):
            port.port_source(SOURCE.replace('#define CHIP_ID\t\t\t\t0xdc42\n', ''))
        with self.assertRaises(port.PortError):
            port.port_source(SOURCE.replace('"smartsens,sc4336" }', '"smartsens,sc4336p" }'))
        with self.assertRaises(port.PortError):
            port.port_source(port.port_source(SOURCE))               # already ported

    def test_tree_twice(self):
        k = tempfile.mkdtemp()
        d = os.path.join(k, 'drivers', 'media', 'i2c')
        os.makedirs(d)
        for name, text in dict(SENSOR_FILES, **{'sc4336.c': SOURCE}).items():
            with open(os.path.join(d, name), 'w') as f:
                f.write(text)
        for _ in range(2):
            r = subprocess.run([sys.executable, TOOL, k], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(d, 'Kconfig')) as f:
            kc = f.read()
        self.assertEqual(kc.count('config VIDEO_SC4336H\n'), 1)
        self.assertLess(kc.index('config VIDEO_SC4336H\n'), kc.index('config VIDEO_SC4336\n'))
        with open(os.path.join(d, 'Makefile')) as f:
            mk = f.read()
        self.assertEqual(mk.splitlines()[1:3], ['obj-$(CONFIG_VIDEO_SC4336) += sc4336.o',
                                                 'obj-$(CONFIG_VIDEO_SC4336H) += sc4336h.o'])
        with open(os.path.join(d, 'sc4336.c')) as f:
            self.assertEqual(f.read(), SOURCE)                       # the SDK's own driver left as it was
        self.assertTrue(os.path.isfile(os.path.join(d, 'sc4336h.c')))
        r = subprocess.run([sys.executable, TOOL, k, '--chip-id', '0x12345'], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        r = subprocess.run([sys.executable, TOOL, tempfile.mkdtemp()], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn('sc4336.c', r.stderr)


if __name__ == '__main__':
    unittest.main()
