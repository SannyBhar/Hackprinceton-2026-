# Overhead camera setup (markerless robot tracking)

The webcam watches the projected board and reports which cell the robot is in, so tiles light up
as it enters each one. No printed markers are needed on the board or the robot.

## Start it

1. **Run the backend from macOS Terminal.app** — processes started inside other apps may not be
   allowed to use the camera. The first time, macOS asks to let Terminal use the camera: Allow.
   ```bash
   backend/.venv/bin/uvicorn app.main:app --app-dir backend --port 8000
   ```
   (OpenCV is needed: `backend/.venv/bin/pip install -r backend/requirements-vision.txt`.)
2. Projection open and calibrated on the floor (see PROJECTION_SETUP.md).
3. **Setup → Overhead camera**: pick the camera (the USB webcam was Camera 0 on the dev laptop),
   **Start camera**, then **Calibrate from projection**. This flashes the test pattern for ~2 s,
   finds its border, and maps camera pixels to cells. Keep people off the board; dim the room.
   The yellow grid in the preview should sit on the projected tiles.
4. Set **Robot position from → Camera**. Put the robot on the start cell; the card should say
   "Robot seen in row …, column …" matching it.
5. **Run → Start hand-push test** pushes nothing to the motors: push the robot along the route by hand
   and watch tiles light up. It ends when the last route cell is entered (or press End test).

Recalibrate whenever the camera or projector moves. Calibration is saved in
`data/camera_calibration.json` and survives restarts and puzzle-size changes.

## How it detects the robot

The robot is the largest dark, colourless shape on the bright board after ignoring the board's own
dark parts (grid gaps and the corner dark zones). Its bottom-centre is taken as where it touches the
floor, which compensates for the robot's height in an angled camera view.

Measured on the real setup: robot chassis brightness ≈75, grid lines ≈124, tiles ≈211; the robot's
blob was ~4–5× larger than anything else on a clear board; ~5 ms processing per 1080p frame;
~25 fps and ~25–40 ms from frame to position.

## Limits (not yet verified or known not to work)

- **Heading** isn't visible without a marker. It's assumed to be the start heading until the robot
  moves, then the direction of travel. Turns in place are not detected.
- **Dark themes and the test pattern** make the whole board dark; detection refuses rather than guess.
  Use the Glossy white (or another bright) theme.
- **People/dark clothing on the board** can look like the robot. Keep the board clear.
- **Not yet tested**: a robot driving under its own power, timing of tile lighting during real motion,
  red/green feedback tiles under the camera, other lighting, other camera positions.
- If this isn't reliable enough, an ArUco marker on the robot (ID 4) would give exact position and heading.

Env var to start the camera automatically: `CA_TRACKER=board-camera` (with `CA_TRACK_CAMERA=0`).
