# LayerCam

Cameras for the inside of a Prusa CORE One, in Prusa's own Buddy3D camera
case: they feed Prusa Connect, see the bed in daylight and in infrared, and
make a per-layer timelapse that they upload to a NAS or S3. Each variant is
its own product, with its own folder, revision, tests and CI job.

| Variant | What it is | Revision | Status |
|---|---|---|---|
| [LayerCam](layercam/) | Three boards in the case (main, LED ring, USB-C), a camera module and lens bought separately, a stick-on heatsink | 1.0 | designed, not yet built |
| LayerCam Pro | LayerCam's camera on **one** board, sensor soldered on, no board-to-board cables; on its own branch, it lands in `layercam-pro/` here | 1.0 | in review, not yet merged |

## How they differ

| | LayerCam | LayerCam Pro |
|---|---|---|
| Boards | three, joined by cables | one |
| Main chip | RV1106G3 | RV1106G3, so LayerCam's software carries over |
| Camera | module and lens bought separately | sensor on the board |

Each README has the details, how to order it, and its test record.
How revisions work: [`docs/versioning.md`](../../docs/versioning.md).
