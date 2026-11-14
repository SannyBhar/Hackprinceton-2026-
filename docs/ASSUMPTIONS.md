# Implementation defaults (not user-confirmed)

These are the scope doc's "recommended defaults" or choices made while scaffolding. Each is
configurable; none should be presented as a confirmed product decision.

| Topic | Default | Where |
| --- | --- | --- |
| Coordinates | `{row, col}` zero-indexed, row ↓, col →; pose in cell units, centre `(col+.5,row+.5)` | `models.py` |
| Heading degrees | 0 = N, 90 = E, 180 = S, 270 = W | `models.py` |
| Step counts | integers 1–5 (`DEFAULT_MAX_STEPS`) | `compiler.py` |
| Program syntax | exactly one START first, one STOP last | `compiler.py` |
| Out-of-bounds plan | rejected at Confirm with the offending card; never clipped/wrapped | `compiler.py` |
| 3+ mixed visits | FIRST result left, LATEST right; equal → solid (`first_latest`); `first_other` alternative available; full history kept | `grading.py` |
| Success | exact ordered match + full traversal + final cell = goal + normal completion | `grading.py` |
| Cell-entry hysteresis | must be ≥ 0.18 cell inside the new cell for 2 consecutive frames | `tracking.py` |
| Boundary stop | robot centre within 0.08 cell of the board edge | `tracking.py` |
| Stale tracking stop | no valid pose for 800 ms during RUNNING/RECORDING | `tracking.py` |
| Skipped cells | logged as a tracking warning; intermediate cells are **not** fabricated | `tracking.py` |
| Start check | Run requires observed pose in start cell and heading within ±30° | `session.py` |
| Joystick | discrete: 1 cell / 90° per press; serialized (input ignored while moving); toggle debounce 600 ms; dead zone 0.5 | `session.py`, `RecordingTab.tsx` |
| Recording compression | consecutive same-direction moves merge, split at the card limit | `recording.py` |
| Card layout | single horizontal row, read left→right; marker IDs per `vision/cards.py` | `vision/cards.py` |
| OCR | none by default → instructor enters/confirms every number; low-confidence (< 0.85) needs explicit review | `vision/cards.py`, `ProgramTab.tsx` |
| Robot transport | WebSocket to ESP32 soft-AP; heartbeat 250 ms; firmware watchdog 1 s; max 8 s per command | `esp32_ws.py`, firmware |
| Marker height | linear radial correction `height_correction` (0 = off) — must be measured | `camera_tracker.py` |
| Corner markers | ArUco 4x4_100 IDs 0–3 (TL,TR,BR,BL), robot ID 4 | `vision/cards.py` |
| Persistence | local JSON in `data/` (gitignored); bundled puzzles in `fixtures/puzzles` | `storage.py` |
| Themes | 3 prepared offline themes; palettes avoid saturated green/red | `board/themes.tsx` |
