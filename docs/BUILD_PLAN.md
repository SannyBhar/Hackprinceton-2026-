# CodeAnywhere — 72-hour build plan

Principle: the simulator runs the **same** tracker → grader → projection pipeline as the real
hardware. Every hardware piece replaces one adapter; nothing else changes. Integrate early,
demo from the simulator if any hardware piece slips.

## Where the scaffold stands (end of hour ~0)

| Area | Status |
| --- | --- |
| Shared contracts (Python ↔ TS) | Done — `backend/app/models.py`, `frontend/src/api/types.ts` |
| Same-index grader, tile reducer, summary | Done + tested |
| Program validation / bounds planning | Done + tested |
| Cell-entry tracker (hysteresis, revisits, skips, boundary, stale) | Done + tested |
| Session state machine, WS snapshot + seq, reconnect | Done |
| Simulator robot + fake camera + fault injection | Done + tested end-to-end |
| Projection: full-board perspective warp, on-projector 4-corner drag, nudge, test pattern, marker dark zones, size-mismatch warning, persistence | Done, verified in browser (not yet on a real projector) |
| Instructor UI: Setup, Puzzle editor, Scan review, Live attempt, Recording | Done (functional, unpolished) |
| Joystick recording → blocks (browser Gamepad + keyboard) | Done + tested with simulator |
| Card recognition | Fixture adapter done; OpenCV/ArUco adapter written, **untested**; OCR = none (manual entry) |
| Overhead camera tracker | Written, **untested** |
| ESP32 transport + firmware | Written, **untested**; GPIO/motor values are placeholders |
| AI theme generation | Not started (prepared offline themes in place) |

## Workstreams and owners

Assume 4 people: **SW-A** (backend/vision), **SW-B** (frontend/projection), **ME-1**, **ME-2**.
Adjust names as needed.

| Stream | Owner | Deliverable |
| --- | --- | --- |
| A. Projection & board | SW-B | Real projector aligned within ~1 cm at every corner; readable feedback under room light |
| B. Vision | SW-A | Card scan of a 7-card row in < 2 s; robot pose at ≥ 15 Hz with < 0.15 cell error |
| C. Robot | ME-1 + SW-A | Reliable 1-cell moves and 90° turns on the real board; STOP + watchdog verified |
| D. Physical build | ME-2 | Board + corner markers, camera & projector mounts, robot marker mast, cards + scan mat, joystick housing |
| E. Instructor UX + demo | SW-B | Polished flows, error states, rehearsed demo script |

## Timeline

### Day 1 (hours 0–24): make the physical loop real

- **SW-B / A (hrs 0–6):** take the projector + laptop, run `./dev.sh`, open `/projection` on the
  extended display, fullscreen, calibrate onto a taped grid on the floor/table. Note keystone,
  blur, brightness. Decide board size from the projector's throw (scope §7: geometry can't fix
  blur or a too-small footprint). Pick theme contrast that survives ambient light.
- **ME-2 (hrs 0–12):** build/flat board at chosen size; print markers with
  `python tools/make_cards.py`; fix corner markers (IDs 0–3) just *inside* the projected corners
  so the black dark zones cover them; rigid overhead mount for camera + projector (they must not
  move after calibration).
- **ME-1 (hrs 0–12):** chassis assembly. Complete the [hardware checklist](HARDWARE_CHECKLIST.md)
  *before* wiring. Bench-test motors with the driver off-board first.
- **SW-A (hrs 2–16):** `pip install -r requirements-vision.txt`; run `camera_tracker.py` against
  the real board; measure pose error at the 4 corners and centre; tune `height_correction` for the
  robot marker's height. Hook it via `CA_TRACKER=camera` with the **simulated** robot pushed by
  hand → cell entries should fire once per cell.
- **Checkpoint H24:** projected grid aligns with board; hand-pushed robot marker produces correct
  ordered cell entries and live green/red on the projection.

### Day 2 (hours 24–48): robot + cards

- **ME-1 + SW-A (hrs 24–36):** fill GPIO in `codeanywhere.ino`, flash, connect laptop to the
  ESP32 AP, `CA_ROBOT=esp32`. Calibrate `MS_PER_CELL` / `MS_PER_90` on the real surface.
  Verify: STOP mid-move, unplug laptop → watchdog stops within 1 s, resend same msgId → no move.
  If open-loop drift is too large, add camera-closed-loop correction between commands (heading
  re-align using pose) — keep it inside the robot adapter.
- **SW-A (hrs 30–42):** card camera + scan mat. `CA_CARDS=opencv`. Evaluate handwriting on real
  kid-style samples; add an OCR adapter only if it's ≥ 90 % on samples, otherwise ship
  "crop + instructor types number" (already works) and printed-number fallback cards.
- **SW-B (hrs 24–48):** UI polish; Program screen shows crops; big Stop button always visible;
  attempt review; projection readability tests with real artwork/lighting.
- **ME-2:** card stock + lamination, scan mat with guide rails, joystick housing.
- **Checkpoint H44:** full real run: scan → confirm → robot drives → live projection grading.

### Day 3 (hours 48–72): harden, theme, rehearse

- **hrs 48–56:** joystick recording on real robot (discrete moves); verify generated program
  replays the same route.
- **hrs 50–60 (optional, only if checkpoint H44 passed):** AI theme generation (scope §18):
  backend `theme` service + provider adapter, layout reference image, preview/accept/fallback,
  cache to disk. Replaces only Board layer 1. Keep prepared themes as fallback.
- **hrs 56–66:** failure drills — tracking occluded by a hand, robot bumped, Wi-Fi dropped,
  projector re-plugged at a different resolution (expect mismatch warning → recalibrate).
- **hrs 66–72:** rehearse demo 3× end-to-end, freeze dependencies, record a backup video of the
  simulator demo.

## Cut lines (if behind)

1. Drop AI themes (prepared themes already satisfy the board).
2. Drop OCR; instructor types numbers from the crop (still "never guess silently").
3. Single camera for cards + tracking only if handwriting crop is legible; else read cards with a
   phone/laptop webcam held over the mat.
4. Robot fallback: simulated robot + projected robot glyph + hand-pushed marker still demos the
   full grading/projection loop truthfully (label it as simulator).

## Top risks

| Risk | Mitigation |
| --- | --- |
| Projector footprint too small/dim for the board | Measure on hour 0; size board to the projector; high-contrast theme |
| Raised robot marker → pose offset | `height_correction`, keep marker low, validate at corners |
| Open-loop motion drifts across cells | Calibrate per surface; camera re-align between commands; boundary stop protects |
| Projected light washes out ArUco markers | Corner dark zones (adjustable); projection never lights the robot marker region if needed |
| Handwriting OCR unreliable | Manual confirm path is the default; printed-number cards |
| Camera/projector mount bumped | Recalibrate (both are < 1 min); lock mounts with clamps |
