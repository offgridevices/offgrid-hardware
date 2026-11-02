# Gyro orientation: where U_IMU goes and why

**Answer: place U_IMU (ICM-42688-P, footprint `og:LGA-14_L3.0-W2.5-P0.50-TL`) on the top side at
KiCad orientation 135 deg** (`SetOrientationDegrees(135)`, counter-clockwise seen from the top).
With the board's front arrow pointing forward, stock TAKERG4AIO (`GYRO_1_ALIGN CW270_DEG`,
`DEFAULT_ALIGN_BOARD_YAW 45`) then reads the quad's true attitude.  It is the only multiple of 45 deg
that works (`gyro_orientation_check.py --scan`).

At 135 deg the chip's +X axis points to the front-left (motor 4), its +Y axis to the rear-left
(motor 3), and the package's pin-1 corner points to the rear (the corner nearest the back edge,
just right of the chip's centre line); pad 1 is at (+0.36, +1.42) mm from the footprint origin.

## Inputs

| What | Source | Fact used |
|---|---|---|
| Betaflight body frame | `flight/imu.c` (2026.6.2): `rMat` is body to earth with earth = North-West-Up; roll = atan2(up_y, up_z), pitch = pi/2 - acos(-up_x) | Body axes are **X forward, Y left, Z up** (right-handed). Level accelerometer reads +1 g on Z. Gyro rates are right-handed about those axes: **roll right = +X, nose up = -Y, yaw right = -Z**. Attitude: roll positive right, pitch positive nose-down. Cross-checks: `rc.c` negates the yaw stick, `mixer.c` negates yaw PID for props-in, QuadX mixer raises the rear motors for +pitch |
| Sensor alignment | `sensors/boardalignment.c` `alignSensorViaRotation` | CW270: `x' = -y, y' = x, z' = z`. That is a rotation of the vector by +90 deg about Z |
| Board alignment | `boardalignment.c` + `common/vector.c` (`buildRotationMatrix`, `matrixTrnVectorMul`) | applied after the sensor alignment as `v' = R(r,p,y)^T v`; for yaw only that rotates the vector by **-yaw** about Z |
| Custom alignment | `pg/gyrodev.c`, `gyro.c`, `acceleration_init.c` | `ALIGN_CUSTOM` uses the same `R^T` with the custom roll/pitch/yaw; CWn equals custom yaw n (the script checks all 8) |
| Chip axes | TDK DS-000347 fig. 4 (top view) and fig. 15 | Top view, pin 1 top-left, pins counter-clockwise: **+X toward pins 8-11, +Y toward pins 12-14**, +Z out of the top face |
| Footprint | `og.pretty/LGA-14_L3.0-W2.5-P0.50-TL.kicad_mod` (same as `src/easyeda_raw`) | Pad 1 at (-1.26, -0.75): left column, top. Pads 1-4 down the left, 5-7 along the bottom, 8-11 up the right, 12-14 along the top: TDK's top view, unmirrored. So at 0 deg, chip +X = KiCad +x (screen right), chip +Y = KiCad -y (screen up) |
| Board | brief | KiCad x right, y down, front of the quad = -y, viewed from the top |

## Derivation

Work in the body frame, angles about +Z (up), so "counter-clockwise seen from the top" is positive.
At footprint angle 0 the chip's +Y points forward (+X_body) and its +X points right (-Y_body):
the chip frame is the body frame turned by -90 deg.  Rotating the footprint by theta adds theta, so the
chip frame is the body frame turned by (theta - 90).  A body vector w therefore reads, in chip axes,

    raw = Rz(90 - theta) w

Betaflight then applies CW270 = Rz(+90) and board yaw 45 = Rz(-45):

    out = Rz(-45) Rz(90) Rz(90 - theta) w = Rz(135 - theta) w

`out = w` for every w requires **theta = 135 deg**.

## With board alignment 0 (custom target RIDGE3LITE)

Same placement, `align_board_yaw = 0`: the sensor alignment alone must undo Rz(90 - 135) = Rz(-45),
i.e. a custom alignment yaw of **315 deg** (`GYRO_1_ALIGN_YAW 3150` in decidegrees, roll 0, pitch 0;
Configurator shows sensor alignment CUSTOM 0/0/315 and board alignment 0/0/0).  No standard
CWn alignment works on its own (the placement is a 45-deg one), the script asserts this.

## BMI270 on the same pads

The Bosch BMI270 is pad-compatible but its axes differ: Bosch DS000 sect. 8.2 with pin 1 top-left
gives **+X toward pins 12-14, +Y toward pins 1-4**, i.e. turned +90 deg from the TDK part.  At the
same 135 deg placement it would need **CW180 with board yaw 45**, or **custom yaw 225 with board yaw 0**.
With TAKERG4AIO's CW270 it would be 90 deg off.  (Stock TAKERG4AIO does not even compile in the
BMI270 driver, so it would simply not be detected; RIDGE3LITE leaves it out on purpose for the same
reason: one alignment per gyro slot cannot serve both chips.)

## Independent check

`gyro_orientation_check.py` ports `alignSensorViaRotation`, `buildRotationMatrix`,
`matrixTrnVectorMul` and the `imu.c` attitude formulas, reads the pad positions from the footprint
file, builds the chip axes from the datasheet rule above, rotates them by the KiCad orientation and
asserts: roll right gives +gyro X and +roll, nose up gives -gyro Y and negative (nose-up) pitch,
yaw right gives -gyro Z, level gives +1 g on Z, for stock TAKERG4AIO at 135 deg, for RIDGE3LITE
(custom yaw 315), and for the BMI270 alternatives.  `--scan` shows 135 is the only working angle.

## Before the first flight (do this anyway)

Configurator Setup tab, props off: tilt the right side down - the model rolls right; lift the nose -
the model's nose lifts; turn the quad clockwise - the model turns clockwise.  If any is wrong, do not fly.
