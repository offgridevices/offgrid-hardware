# LayerCam v1: fit in the Buddy3D housing

The boards go into Prusa's own printed case for the Buddy3D camera, as
published: [Printables 1343977](https://www.printables.com/model/1343977-buddy3d-camera-for-core-one-printed-parts)
(`buddy-camera-bottom-r2`, `-top-r1`, `-lid-r1`). Nothing in the case is
changed. Every number the boards take from it is in `src/geometry.py`, with
where it came from.

## How it was measured

On 26 Oct 2026 the three STL files were downloaded, put together in their
assembled positions, and cut into sections every 0.5 mm. The STEP file was
used to check the result. The frame used throughout ("lens frame") has its
origin on the lens axis at the case's outer front face, with +Z pointing
into the case. X and Y are drawn as seen from behind the camera, +Y
towards the straight edge. Board drawings use the same X and Y, with
KiCad's y pointing down (board y = -Y).

| What | Measured | Used |
|---|---|---|
| Board seat | four printed bosses, tops at Z 19.3, pilot holes for M2 self-tappers at (+-16.07, -21.15) and (+-16.08, 20.95) | M2 clearance holes, Ø2.2, in the main board; no part within the 3.5 mm boss on the front face |
| Pocket at the seat (Z 19.4-20.9) | a 38.25 mm-wide outline, straight edge at Y +23 with a bump to Y 28.5 for \|X\| < 9.5, round edge to Y -29.4 | `POCKET`, already shrunk by 0.4 mm; the board is a simpler shape inside it (straight sides at X +-19.0, straight edge at Y 22.9 with a tab to 24.4, an arc R 31.3 about (0, 2.1)). `verify.py` checks the board lies inside the pocket |
| Free height, front (lens side) | to Z 9.5 over the whole board (9.8 mm), the LED ring at Z 2.0-3.6 | parts on the front face up to 9.8 mm |
| Free height, back | 7.7 mm everywhere; 10 mm inside X +-13.6, Y -18..15; 17.5 mm under the lid's vent window | the camera module and its cable (about 5 mm) sit in the 10 mm zone |
| Lens bore | Ø14.9 through the front face, Z 0-3.6 | the lens's front must be no wider |
| LED holes | six Ø2.4 at R 13.0, every 60 deg from +X; light window Ø5.8 at (0, -14.15) | the ring's six LEDs and its light sensor sit under them |
| Ring seat | Z 2.0-3.6, on a collar of R 9.3 with keys at +X, +Y, -X, two locating pins at (+-8.5, 0.2) | ring board: outside R 16.5, inside R 9.55 with the three key notches |
| USB-C opening | obround 9.4 x 3.8 mm in the top shell's -X facet; two grooves behind it take a board 22.0 x 1.2 mm | USB board 22 x 16 x 1.2 mm, receptacle mouth through the opening |

## The camera stack

From front to back:

1. **Lens** (Towin CCL127028MPR, M12, total track 20.9 mm). It screws into
   the IR-cut holder; its front lands about 0.2 mm behind the case's front
   face, inside the Ø14.9 bore.
2. **IR-cut holder** (Commonlands CLA219). It sits on the main board's
   front face over the board's 14.4 x 14.4 mm window. Its body and ears
   (21.2 x 19.6 mm) are kept clear of parts. Commonlands' drawing (read
   31 Oct 2026): 9.5 mm tall, under the 9.8 mm free in front of the
   board; the M12 x 0.5 lens thread is its own (no separate lens holder);
   lens back focal length 3.0 mm at most; holes 18.0 mm apart for M1.6
   self-tapping screws.
3. **Main board**, 1.6 mm, front face on the bosses at Z 19.3.
4. **Two 1.0 mm stacks of stainless washers** (three M1.6 washers,
   0.3-0.4 mm each, per screw). They keep about 1.0 mm between the
   board's back face and the sensor. Nylon softens and creeps at the
   75-85 °C the board reaches and would let the focus drift; stainless
   does not. They sit on solder mask, inside each hole's 1.9 mm keep-out. Parts under the module on the back
   face are 0.6 mm or lower (0402 resistors and capacitors only; `verify.py`
   checks this).
5. **Camera module** (Luckfox SC3336 3MP Camera (B)) with its own lens
   holder removed. Its sensor looks forward through the window. The lens
   axis is not in the module's middle: it is 8.4 mm from one edge and
   15.6 mm from the edge with the cable connector. The module covers board
   y -15.6 to +8.4 and x +-12.5.
6. **Two M1.6 x 6 thread-forming screws**, from the module's side,
   through the module, the washers and the board into the holder's
   ears (18 mm apart, on the lens axis), clamp the stack: 3.8 mm of
   stack leaves 2.2 mm of thread in the holder's 4.3 mm base.

The module's 20-way cable connector is on its back, at its +Y edge. A
short flat cable (about 15 mm, not twisted) drops 2.3 mm to J2 on the main
board's back face. J2's mouth is 2.3 mm beyond the module's edge, and its
contacts are centred on the lens axis like the module's, so contact k
meets contact k (`verify.py` checks every contact by position).

## Not checked on a printed case yet

- The stack height through the IR-cut holder and the lens's focus. A real
  lens and holder set the focus; the M12 thread gives about 2 mm of
  adjustment.
- The USB board sliding into its grooves.
- The flat cable's bend between the module and J2.
