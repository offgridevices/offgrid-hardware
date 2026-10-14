// Canary v1 bumper: a 3D-printable frame that protects the board's edges.
// Open top (sounder, LEDs, button, sensors) and open bottom: the board's
// underside sits flush with the frame's, so the thermal tab still lies on
// the pack. The board presses in from below and a 0.8 mm lip stops it at
// the top face. Openings for USB-C (left), the probe connector (bottom
// edge) and air vents beside the sensor head (right).
// Board coordinates: KiCad x-100, y-100 (y flipped to OpenSCAD's +y up).
$fn = 48;
BW = 60; BH = 40; BR = 2.5; BT = 1.6;   // board
CLR = 0.15;                           // fit clearance per side
WALL = 2.0; LIP = 0.8; LIPT = 0.8;    // wall, lip overhang, lip thickness
H = BT + LIPT + 2.6;                  // total height (lip tops out 2.6 mm above it)

module rrect(w, h, r, z) { translate([0, 0, 0]) linear_extrude(z) offset(r) offset(-r) square([w, h]); }
function ky(y) = BH - (y - 100);      // KiCad y -> OpenSCAD y
function kx(x) = x - 100;

difference() {
  translate([-WALL - CLR, -WALL - CLR, 0]) rrect(BW + 2 * (WALL + CLR), BH + 2 * (WALL + CLR), BR + WALL, H);
  // board pocket, through
  translate([-CLR, -CLR, -1]) rrect(BW + 2 * CLR, BH + 2 * CLR, BR + CLR, BT + 1);
  // above the board: open, less the lip
  translate([LIP - CLR, LIP - CLR, BT]) rrect(BW - 2 * LIP + 2 * CLR, BH - 2 * LIP + 2 * CLR, BR, H);
  // USB-C opening, left edge, centred on the connector (KiCad y 112), plug overmould 12 x 7
  translate([-WALL - 1, ky(112) - 6.5, -1]) cube([WALL + LIP + 2, 13, H + 2]);   // plug overmould hangs below board level
  // probe connector J3 at the bottom edge (KiCad x 124.6), 10 mm wide, above board level
  // (the wall below it keeps the frame in one piece)
  translate([kx(124.6) - 5.2, -WALL - 1, BT - 0.2]) cube([10.4, WALL + LIP + 2, H]);
  // air vents beside the sensor head (right edge, KiCad y 104..124)
  for (y = [106, 111, 116, 121]) translate([BW - 1, ky(y) - 1.6, BT + 0.2]) cube([WALL + 3, 3.2, H]);
  // thermal tab corner: no lip, so the tab can flex onto the pack
  translate([-CLR, -CLR, BT]) cube([16, 10.5, H]);   // lip only; the wall stays and joins the frame
}
