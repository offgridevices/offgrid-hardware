#!/usr/bin/env python3
"""Independent check of the IMU placement angle (see gyro-orientation.md).

Ports the parts of Betaflight 2026.6.2 that turn raw sensor axes into the
craft's axes, builds the chip's axes from the KiCad footprint and the
datasheet axis figures, and asserts that, for the footprint orientation
chosen, real roll/pitch/yaw motions come out with the signs Betaflight's
estimator, PID loop and mixer expect.

    python3 gyro_orientation_check.py            # checks the answer, prints a table
    python3 gyro_orientation_check.py --scan     # tries every 45 degree placement

Ported from betaflight/betaflight tag 2026.6.2 (e0b7bb01b):
  src/main/sensors/boardalignment.c   alignSensorViaRotation(), initBoardAlignment()
  src/main/common/vector.c            buildRotationMatrix(), matrixTrnVectorMul()
  src/main/common/sensor_alignment*.h SENSOR_ALIGNMENT_FROM_STD
  src/main/flight/imu.c               rMat (body -> earth, earth = North-West-Up),
                                      roll/pitch/yaw extraction
Betaflight's body frame, from imu.c: rMat maps body X/Y/Z onto North/West/Up,
so at rest and level the body axes are X = forward, Y = LEFT, Z = UP
(right-handed).  The accelerometer reads +1 g on Z when level; gyro rates
are right-handed about those axes: roll right = +X, nose up = -Y,
yaw right (clockwise from above) = -Z (rc.c negates yaw stick, mixer.c
negates yaw PID for props-in, consistent with this).
"""
import math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FP = os.path.join(HERE, '..', 'og.pretty', 'LGA-14_L3.0-W2.5-P0.50-TL.kicad_mod')

# ----------------------------------------------------------- small vector kit
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def norm(a):
    n = math.sqrt(dot(a, a)); return tuple(x / n for x in a)
def close(a, b, eps=1e-6): return all(abs(x - y) < eps for x, y in zip(a, b))

# ----------------------------------------------------------- Betaflight, ported
CW0, CW90, CW180, CW270, CW0F, CW90F, CW180F, CW270F = range(1, 9)
NAMES = {CW0: 'CW0_DEG', CW90: 'CW90_DEG', CW180: 'CW180_DEG', CW270: 'CW270_DEG',
         CW0F: 'CW0_DEG_FLIP', CW90F: 'CW90_DEG_FLIP', CW180F: 'CW180_DEG_FLIP', CW270F: 'CW270_DEG_FLIP'}

def align_via_rotation(v, rot):          # boardalignment.c alignSensorViaRotation (switch)
    x, y, z = v
    return {CW0: (x, y, z), CW90: (y, -x, z), CW180: (-x, -y, z), CW270: (-y, x, z),
            CW0F: (-x, y, -z), CW90F: (y, x, -z), CW180F: (x, -y, -z), CW270F: (-y, -x, -z)}[rot]

def build_rotation_matrix(roll, pitch, yaw):   # vector.c buildRotationMatrix, radians
    cx, sx = math.cos(roll), math.sin(roll)
    cy, sy = math.cos(pitch), math.sin(pitch)
    cz, sz = math.cos(yaw), math.sin(yaw)
    return [[cz*cy, -cy*sz, sy],
            [sz*cx + sx*cz*sy, cz*cx - sx*sz*sy, -sx*cy],
            [sx*sz - cz*cx*sy, sx*cz + sz*cx*sy, cy*cx]]

def trn_mul(m, v):                       # vector.c matrixTrnVectorMul (= applyRotationMatrix)
    return tuple(m[0][i]*v[0] + m[1][i]*v[1] + m[2][i]*v[2] for i in range(3))

def betaflight_align(raw, sensor_align=None, custom_rpy_deg=None, board_rpy_deg=(0, 0, 0)):
    """gyro.c / acceleration.c: standard alignment via the switch, ALIGN_CUSTOM via
    the matrix; then the board alignment matrix unless it is all zero."""
    if custom_rpy_deg is not None:
        v = trn_mul(build_rotation_matrix(*[math.radians(a) for a in custom_rpy_deg]), raw)
    else:
        v = align_via_rotation(raw, sensor_align)
    if any(board_rpy_deg):
        v = trn_mul(build_rotation_matrix(*[math.radians(a) for a in board_rpy_deg]), v)
    return v

def std_as_custom(rot):                  # SENSOR_ALIGNMENT_FROM_STD: bits -> R,P,Y multiples of 90
    bits = ((rot - CW0) & 3) | (((rot - CW0) & 4) << 1)
    return (((bits >> 4) & 3) * 90, ((bits >> 2) & 3) * 90, (bits & 3) * 90)

def attitude_from_up(up):                # imu.c, rMat row NWU_U = earth-up in body axes
    roll = math.degrees(math.atan2(up[1], up[2]))
    pitch = math.degrees(0.5 * math.pi - math.acos(-up[0]))
    return roll, pitch

# ----------------------------------------------------------- geometry
# KiCad board coordinates: x right, y DOWN the screen, viewed from the top.
# The quad's front is toward -y.  Betaflight body axes in board coordinates
# (third component = out of the top copper, i.e. up):
BODY_X = (0.0, -1.0, 0.0)   # forward
BODY_Y = (-1.0, 0.0, 0.0)   # left
BODY_Z = (0.0, 0.0, 1.0)    # up
# The board frame (x right, y down, z up) is left-handed, so in it X x Y
# comes out as -Z; in a right-handed (x right, y UP, z up) frame it is +Z.
assert close(cross(BODY_X, BODY_Y), tuple(-c for c in BODY_Z))

def pads(path):
    s = open(path).read()
    out = {}
    for m in re.finditer(r'\(pad\s+"?(\d+)"?\s+smd\s+\S+\s*\(at\s+([-\d.]+)\s+([-\d.]+)', s):
        out[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    return out

def centroid(ps, names):
    return tuple(sum(ps[n][i] for n in names) / len(names) for i in range(2))

def chip_axes_in_footprint(ps, maker='tdk'):
    """Chip axes in footprint coordinates (x right, y down, z up), rotation 0.
    Both datasheets show the TOP view with pin 1 top-left, pins 1-4 down the
    left side, 5-7 along the bottom, 8-11 up the right side, 12-14 along the top.
      TDK ICM-42688-P fig. 4/15: +X toward pins 8-11, +Y toward pins 12-14.
      Bosch BMI270 sect. 8.2:     +X toward pins 12-14, +Y toward pins 1-4.
    """
    left = centroid(ps, ['1', '2', '3', '4']); right = centroid(ps, ['8', '9', '10', '11'])
    bottom = centroid(ps, ['5', '6', '7']); top = centroid(ps, ['12', '13', '14'])
    to_right = norm((right[0] - left[0], right[1] - left[1], 0.0))
    to_top = norm((top[0] - bottom[0], top[1] - bottom[1], 0.0))
    # numbering must run counter-clockwise seen from the top (y down => z-up cross sign flips)
    p1, p5, p8 = ps['1'], ps['5'], ps['8']
    turn = (p5[0]-p1[0])*(p8[1]-p5[1]) - (p5[1]-p1[1])*(p8[0]-p5[0])
    assert turn < 0, 'pads not numbered counter-clockwise from the top: footprint is mirrored?'
    up = (0.0, 0.0, 1.0)
    if maker == 'tdk':
        cx, cy = to_right, to_top
    else:
        cx, cy = to_top, tuple(-c for c in to_right)
    # right-handedness check in a y-down frame: x cross y must point INTO the
    # screen in maths terms, which is out of the top copper physically.
    c = cross(cx, cy)
    assert c[2] < 0, 'chip axes not right-handed with Z out of the top face'
    return cx, cy, up

def rotate_kicad(v, deg):
    """KiCad SetOrientationDegrees: counter-clockwise on screen (y down)."""
    t = math.radians(deg); c, s = math.cos(t), math.sin(t)
    return (v[0]*c + v[1]*s, -v[0]*s + v[1]*c, v[2])

def to_body(v_board):
    # board (x right, y down, z up-out-of-copper) -> Betaflight FLU body
    return (dot(v_board, BODY_X), dot(v_board, BODY_Y), v_board[2])

def chip_axes_body(fp_deg, maker='tdk'):
    cx, cy, cz = chip_axes_in_footprint(pads(FP), maker)
    return tuple(to_body(rotate_kicad(a, fp_deg)) for a in (cx, cy, cz))

def sense(axes, w):          # what the chip reports for a body-frame vector w
    return tuple(dot(a, w) for a in axes)

# ----------------------------------------------------------- the checks
MOTIONS = {                  # body-frame angular rate, and the sign Betaflight expects
    'roll right (right side down)': ((1, 0, 0), 0, +1),
    'pitch nose up':                ((0, -1, 0), 1, -1),
    'yaw right (clockwise from above)': ((0, 0, -1), 2, -1),
}

def passes(fp_deg, maker='tdk', **align):
    axes = chip_axes_body(fp_deg, maker)
    for w in [(1, 0, 0), (0, 1, 0), (0, 0, 1), (0.3, -0.7, 0.2)]:
        if not close(betaflight_align(sense(axes, w), **align), w, 1e-5):
            return False
    return True

def check(fp_deg, maker='tdk', label='', **align):
    axes = chip_axes_body(fp_deg, maker)
    print('%s  footprint %g deg, %s' % (label, fp_deg, align))
    for name, (w, axis, sign) in MOTIONS.items():
        out = betaflight_align(sense(axes, w), **align)
        print('   %-34s gyro x/y/z = %+5.2f %+5.2f %+5.2f' % (name, *out))
        assert abs(out[axis] - sign) < 1e-6 and sum(abs(o) for o in out) - 1 < 1e-6, name
    # accelerometer: level, then rolled 30 deg right, then nose up 30 deg
    acc = betaflight_align(sense(axes, (0, 0, 1)), **align)
    assert close(acc, (0, 0, 1)), 'level must read +1 g on Z'
    r = math.radians(30)
    up_roll_right = (0, math.sin(r), math.cos(r))     # earth-up seen from a right-rolled body
    up_nose_up = (math.sin(r), 0, math.cos(r))        # earth-up seen from a nose-up body
    roll, _ = attitude_from_up(betaflight_align(sense(axes, up_roll_right), **align))
    _, pitch = attitude_from_up(betaflight_align(sense(axes, up_nose_up), **align))
    print('   acc level = %+.2f %+.2f %+.2f g; roll right 30 -> roll %+.1f; nose up 30 -> pitch %+.1f'
          % (*acc, roll, pitch))
    assert abs(roll - 30) < 1e-3 and abs(pitch + 30) < 1e-3   # BF: +roll right, +pitch nose DOWN
    assert passes(fp_deg, maker, **align)
    print('   OK')

if __name__ == '__main__':
    ps = pads(FP)
    print('footprint', os.path.relpath(FP, HERE), ': pad 1 at', ps['1'],
          '(left column, top); pads run counter-clockwise seen from the top')
    stock = dict(sensor_align=CW270, board_rpy_deg=(0, 0, 45))
    if '--scan' in sys.argv:
        for deg in range(0, 360, 45):
            print('%3d deg: stock TAKERG4AIO %s' % (deg, 'CORRECT' if passes(deg, **stock) else 'wrong'))
        sys.exit(0)
    ANSWER = 135
    # the stock TAKERG4AIO defaults
    check(ANSWER, label='ICM-42688-P, TAKERG4AIO stock (CW270 + board yaw 45):', **stock)
    only = [d for d in range(0, 360, 45) if passes(d, **stock)]
    assert only == [ANSWER], only
    # the same placement with board alignment 0 (RIDGE3LITE): custom sensor yaw 315
    check(ANSWER, label='ICM-42688-P, board yaw 0, custom gyro yaw 315 (RIDGE3LITE):',
          custom_rpy_deg=(0, 0, 315))
    # and no standard 90-degree alignment works with board yaw 0
    assert not any(passes(ANSWER, sensor_align=a) for a in NAMES)
    # standard alignments expressed as custom angles agree with the switch
    for a in NAMES:
        for w in [(1, 2, 3), (-0.5, 0.25, 4)]:
            assert close(align_via_rotation(w, a),
                         trn_mul(build_rotation_matrix(*[math.radians(d) for d in std_as_custom(a)]), w), 1e-9), NAMES[a]
    # a BMI270 on the same pads, same placement
    check(ANSWER, 'bosch', label='BMI270 same placement, CW180 + board yaw 45:',
          sensor_align=CW180, board_rpy_deg=(0, 0, 45))
    check(ANSWER, 'bosch', label='BMI270 same placement, board yaw 0, custom yaw 225:',
          custom_rpy_deg=(0, 0, 225))
    assert not passes(ANSWER, 'bosch', **stock), 'BMI270 must NOT be right with CW270'
    print('\nAll checks passed: place U_IMU at KiCad orientation %d deg (top side).' % ANSWER)
