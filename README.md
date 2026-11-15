# Grassroot

Physical-card coding robot for grades 2–4. Students lay out ArUco coding cards; the instructor
webapp scans them, runs the robot on a physical grid, tracks it with an overhead camera, grades
each cell entry against an ordered target route, and projects live feedback onto the board via a
plain projector.

Architecture specification: [Grassroot](docs/Grassroot_Project_Architecture.md) ·
Structural refactor: [brief](docs/Grassroot_Codex_Structural_Refactor.md) ·
Current architecture: [module map](docs/ARCHITECTURE.md) · [refactor notes and checks](docs/REFACTOR_NOTES.md) ·
Legacy scope: [CodeAnywhere_MVP_Scope.md](CodeAnywhere_MVP_Scope.md) · Plan: [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md) ·
Defaults we chose: [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) · Projector setup: [docs/PROJECTION_SETUP.md](docs/PROJECTION_SETUP.md) ·
Hardware: [docs/HARDWARE_CHECKLIST.md](docs/HARDWARE_CHECKLIST.md)

## Quick start (simulator, no hardware)

One-time setup:

```bash
python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt
```

```bash
npm --prefix frontend install
```

Run both servers (backend :8000, frontend :5173):

```bash
./dev.sh
```

Open http://localhost:5173 (instructor) and click **Open projection ↗** (or visit
http://localhost:5173/projection on the projector display and press **F**).

Single-process alternative (serves the built UI from FastAPI on :8000):

```bash
npm --prefix frontend run build && backend/.venv/bin/uvicorn app.main:app --app-dir backend --port 8000
```

## Tests

```bash
cd backend && .venv/bin/python -m pytest -q
```

```bash
npm --prefix frontend test
```

Backend: grading/indexing (incl. the `[A,B,C,D]` vs `[A,C,B,D]` → green/red/red/green acceptance
case), tile/revisit reducer, program validation and bounds, tracker hysteresis/revisits/skips,
recording compression, duplicate-command protection, and simulator end-to-end runs (success,
wrong-then-recover, boundary stop, tracking-loss stop, recording). Frontend: projector homography.

## 2-minute demo script (simulator)

1. **Setup** → *Calibrate corners*: drag the 4 handles on the projection window; toggle *Test pattern*.
2. **Program / Scan** → *Scan cards* (plays `fixtures/scans/01_*`): one card is low-confidence and
   must be ticked; *Confirm program* → *Run ▶*. All 7 tiles go green.
3. *Scan cards* again (buggy fixture): FORWARD is unreadable — type `1` and review. Run: tiles go
   ✓ ✓ ✗ ✗ ✗ ✓ ✓ — wrong entries don't stop the robot and the later same-index match is green.
4. **Setup** → *Drift left*, run again → operational **BOUNDARY** stop, shown distinctly from mistakes.
5. **Puzzle Editor** → load *Peek and Return* for revisits/split tiles. **Joystick Recording** →
   arrows/Space or a gamepad; Stop generates `START, FORWARD 2, RIGHT, …, STOP`.

## Layout

```text
backend/app/      models · grading · compiler · tracking · recording · session · main (FastAPI + WS)
  robot/          base protocol · simulator (robot + fake camera, fault injection) · esp32_ws (unverified)
  vision/         cards (fixture + OpenCV/ArUco recognizers) · camera_tracker (unverified)
frontend/src/     api (types, REST, WS hook) · board (SVG renderer, themes) · calibration (homography)
                  projection (fullscreen warped view) · instructor (5 screens)
firmware/esp32/   Arduino sketch: WS commands, bounded moves, STOP, heartbeat watchdog, msgId dedup
fixtures/         puzzles/*.json, scans/*.json
tools/            make_cards.py (printable markers + cards)
docs/             build plan, assumptions, projection setup, hardware checklist
```

## Hardware switches (env vars for the backend)

| Var | Values | Notes |
| --- | --- | --- |
| `CA_ROBOT` | `sim` (default) / `esp32` | `CA_ROBOT_URL=ws://192.168.4.1:81/` |
| `CA_CARDS` | `fixture` (default) / `opencv` | `CA_CARD_CAMERA=0`; needs `requirements-vision.txt` |
| `CA_TRACKER` | unset / `camera` | `CA_TRACK_CAMERA=1`; pose from overhead camera |

**Status labels:** everything under "Tests" runs against the simulator. The ESP32 transport,
firmware, OpenCV card reader and camera tracker are written but **not verified on hardware**.

## Configuration and refactor status

Backend settings are assembled in `app/settings.py` and adapters in `app/dependencies.py`.
Every `CA_*` variable above (plus `CA_DATA_DIR`) remains supported. Equivalent
`GRASSROOT_*` variables take precedence; see `backend/settings.env.example`.
Existing camera indices (scan 0, tracker 1) are retained for compatibility. The injected
camera interface does **not** implement single-camera scheduling or handoff.

The current implementation uses JSON storage, discrete keyboard/gamepad recording,
manual numeric review and static themes. OCR models, continuous joystick reconstruction,
SQLite and AI providers are **not implemented** by this refactor. The supplied full product
specification includes future work; it is not a claim of current functionality.

Additional verification: `npm --prefix frontend run typecheck` and
`npm --prefix frontend run build`. No lint script or backend static type checker is configured.
The baseline npm install reported **8 vulnerabilities (2 moderate, 4 high, 2 critical)**.
Dependency upgrades are deferred; package manifests and lockfiles were not changed.
