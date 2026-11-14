# Projection setup

The projector is a passive display: no SDK, no network, no device programming. The app renders
the board and warps it.

## How it works

1. The board (artwork → route/grid → start/goal/labels → live feedback → robot glyph →
   corner dark zones) is rendered once as SVG in canonical board pixels (`cols×100` by `rows×100`).
2. `frontend/src/calibration/homography.ts` solves the 3×3 perspective transform from that
   rectangle to the 4 corners you placed, and applies it to the **entire** layer as a CSS
   `matrix3d`. It's a true perspective map (not crop/scale), so keystone and rotation are corrected.
3. Corners are stored as fractions of the projection window size in
   `data/projector_calibration.json` along with the window size they were saved at. If the
   window size changes, the projection shows a warning to recalibrate.
4. Game logic never sees projector pixels — it only uses grid cells.

## Steps

1. Connect the projector as an **extended** display (macOS: System Settings → Displays → turn off
   mirroring). Mirroring also works, but the projected image then includes the instructor UI —
   use the fullscreen projection window on a single display as the fallback.
2. In the instructor app click **Open projection ↗**, drag the window onto the projector, press **F**.
3. **Setup → Calibrate corners** (or press **C** on the projection). Drag TL/TR/BR/BL handles onto
   the physical board corners. Fine tune: **1–4** select corner, arrows = 1 px, Shift+arrows = 10 px,
   or the nudge pad in Setup (works without touching the projector window).
4. Toggle **Test pattern** (or **T**) to check grid lines against the physical cell lines, then turn
   it off. **Esc** ends calibration.
5. Adjust **Corner-marker dark zone** until the four ArUco corner markers sit inside unlit black
   squares (the camera must read them).

Calibration is blocked while the robot is moving (scope: "calibration only while motors are stopped").

## Known limits

- Geometry correction can't fix optical blur, a beam obstructed by people/robot, or a footprint
  smaller than the board.
- A projector that's very oblique will have uneven brightness/focus across the board.
- Untested on a physical projector so far — do that in the first hours (see BUILD_PLAN Day 1).
