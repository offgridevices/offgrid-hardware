# -*- coding: utf-8 -*-
"""Gate: the camera software's pins against this circuit.

run(firmware_dir) -> [(ok, description)]: layercam/board.py and the device
tree dts/rv1106g-layercam-v1.dts against main_soc()'s pin map in
circuit.py.  The checks themselves live with the firmware
(firmware/pincheck.py, also run by its own tests/test_pins.py), so the two
cannot drift apart.  Called by verify.py; standard library only.
"""
import importlib.util, os

HERE = os.path.dirname(os.path.abspath(__file__))


def run(firmware_dir):
    path = os.path.join(firmware_dir, 'pincheck.py')
    if not os.path.exists(path):
        return [(False, 'firmware pin check: %s missing' % path)]
    spec = importlib.util.spec_from_file_location('layercam_pincheck', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run(firmware_dir, os.path.join(HERE, 'circuit.py'))


if __name__ == '__main__':
    for ok, what in run(os.path.join(os.path.dirname(HERE), 'firmware')):
        print('  [%s] %s' % ('ok' if ok else 'FAIL', what))
