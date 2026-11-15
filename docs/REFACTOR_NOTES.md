# Greenlite structural refactor notes

Branch: `refactor/grassroot-structure` (local only). Base: `805411ceb728fe98c64ba6ec597ff817b6f72b73`.
No push, merge, deployment, credentials change, dependency upgrade or new product feature.
The requested AGENTS.md was absent; the supplied specifications are preserved verbatim under docs/.
Existing documentation is retained.

## Before → after

- main.build_session implementation → dependencies.build_session (main import remains available).
- main lifespan tracker setup → runtime.running_session + dependencies.build_tracker.
- Session's concrete Storage annotation → Repository protocol; JSON adapter remains storage.Storage.
- Scattered CA_* reads → Settings; CA_* aliases and defaults remain, GRASSROOT_* wins when both exist.
  Settings are resolved on application startup; direct Storage() retains its legacy import-time default.
- cards._grab / CameraTracker.run direct capture → injectable CameraSource.open(index, role).
- RecordingTab.useGamepad → instructor/useGamepad.ts; discrete polling logic unchanged.
- InstructorApp.openProjectionWindow implementation → projection/window.ts; old export retained.
- ProgramTab validation fetch → existing api.validate with plannedEntries added to its return type.
- Display strings and OpenAPI title → Greenlite. Package, popup and firmware identifiers retained.

## Preserved behavior and deliberate limits

Compiler, grader, revisit reducer, tracker algorithm, models, recording compiler, shared Board,
homography, WS subscription and CSS are unchanged. Routes, HTTP payloads, snapshot/pose event
names, sequence policy, fixture data, JSON representation, motion primitives and firmware wire
messages remain intact. Simulator movement and fault injection are unchanged.

Session remains the single coordinator. Thin existing routes were retained rather than adding
wrappers. No cosmetic domain relocations or unused AI scaffolding were introduced. Camera capture
is scoped and releases on exceptions/cancellation; no scheduling/locking/handoff exists. Defaults
still use camera 0 for cards and 1 for tracking. Frame timestamps remain assigned by pose processing.
A blocking native camera read can outlive asyncio cancellation; physical behavior is unverified.

Lifecycle cleanup now awaits session and simulator tasks and cancels/awaits the tracker; the
ESP32 adapter gains close() for its connection task/socket. This is resource ownership cleanup,
not a motor-control or wire-protocol redesign. Existing STOP/watchdog behavior remains covered.
Concurrent duplicate-command races, transport reconnection details and camera control mode design
were not redesigned. AI calls, OCR engines, continuous joystick records, history query APIs and
SQLite migrations are absent. API validation now uses shared HTTP error handling; normal responses
are unchanged and transport/server failures clear validation state as before.

## Validation by phase

Commands run from repository root unless noted.

| Phase | Exact commands / result |
| --- | --- |
| Baseline | `cd backend && .venv/bin/python -m pytest -q`: 33 passed; `npm --prefix frontend test`: 4 passed; `npm --prefix frontend run build`: passed; `npm --prefix frontend run typecheck`: passed |
| 1 guardrails | backend pytest command above: 36 passed |
| 2 adapters | backend pytest: 36 passed initially, then 39 passed with adapter seam tests |
| 3 lifecycle | backend pytest: initial 1 failure/39 passes (simulator cancellation not awaited); fixed cleanup, then 40 passed |
| 4 frontend | `npm --prefix frontend test`: 6 passed; `npm --prefix frontend run build`: passed (49 modules); `npm --prefix frontend run typecheck`: passed |
| 5 final | backend pytest: 41 passed in 9.60 s; `cd backend && .venv/bin/python -m compileall -q app`: passed; relative-import graph inspection: no Python/TypeScript cycles; TestClient simulator startup/API/built projection SPA smoke check: passed |

The final backend suite emits one dependency deprecation warning: Starlette TestClient references
anyio.abc.BlockingPortal. No unresolved test failures. No lint script/backend type-check tool is
configured, so neither is claimed. New coverage guards HTTP/WS reconnect snapshots, explicit STOP,
JSON representation, settings precedence, camera acquisition/release and lifecycle cancellation;
frontend coverage guards validation requests/responses/errors. Existing e2e tests exercise simulator
success, wrong-then-recover, boundary/tracking stops, mode exclusion and discrete recording.
No interactive browser or physical projector alignment test was performed.

Whitespace check passes for edited code. The two verbatim supplied specifications retain
Markdown hard-break spaces, which Git reports as trailing whitespace; these are intentional.

## Existing dependency findings

Baseline lockfile install reported 8 npm vulnerabilities: 2 moderate, 4 high, 2 critical.
This records the install summary, not a fresh advisory-by-advisory security audit. No dependency
manifests/locks were changed and no audit fix/upgrade was run. Assess and remediate separately.
The default npm cache was unwritable; installation succeeded with a workspace-local cache.
Python 3.13 virtualenv and Node 24.4.1 were used.

## Hardware not tested / next phase — NOT IMPLEMENTED

- Handwriting OCR model and accuracy validation.
- Single-camera scan/track handoff, placement and recalibration.
- Timestamped continuous joystick recording and approximate trajectory reconstruction.
- SQLite adapter/migrations and history queries.
- AI artwork provider and adaptive learning recommendations.
- ESP32-S3 electrical/firmware validation, real transport/watchdog/STOP, motor calibration.
- Physical camera/ArUco tracking and projector alignment/readability.

Firmware and fixtures are untouched. No new hardware claim is made. Existing dependency
advisories and the TestClient deprecation remain unresolved intentionally in this scope.

## Changed files

- `README.md`
- `backend/app/dependencies.py`
- `backend/app/main.py`
- `backend/app/repository.py`
- `backend/app/robot/esp32_ws.py`
- `backend/app/robot/simulator.py`
- `backend/app/runtime.py`
- `backend/app/session.py`
- `backend/app/settings.py`
- `backend/app/storage.py`
- `backend/app/vision/camera.py`
- `backend/app/vision/camera_tracker.py`
- `backend/app/vision/cards.py`
- `backend/settings.env.example`
- `backend/tests/test_adapters.py`
- `backend/tests/test_boundaries.py`
- `docs/ARCHITECTURE.md`
- `docs/Greenlite_Codex_Structural_Refactor.md`
- `docs/Greenlite_Project_Architecture.md`
- `docs/REFACTOR_NOTES.md`
- `frontend/index.html`
- `frontend/src/api/client.test.ts`
- `frontend/src/api/client.ts`
- `frontend/src/instructor/InstructorApp.tsx`
- `frontend/src/instructor/ProgramTab.tsx`
- `frontend/src/instructor/RecordingTab.tsx`
- `frontend/src/instructor/SetupTab.tsx`
- `frontend/src/instructor/useGamepad.ts`
- `frontend/src/projection/ProjectionView.tsx`
- `frontend/src/projection/window.ts`
