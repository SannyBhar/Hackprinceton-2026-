# Grassroot — current architecture

See the [full product specification](Grassroot_Project_Architecture.md) and
[structural brief](Grassroot_Codex_Structural_Refactor.md). Future product requirements
in those documents are not implemented features.

| Module | Responsibility |
| --- | --- |
| `backend/app/main.py` | Existing REST/WS handlers, FastAPI registration and static UI serving |
| `settings.py`, `dependencies.py` | Environment configuration and concrete adapter composition |
| `runtime.py` | Session/tracker startup and shutdown ownership |
| `session.py` | Single authoritative coordinator, mode exclusion, STOP, snapshots, sequenced events |
| `models.py`, `compiler.py`, `grading.py`, `tracking.py`, `recording.py` | Shared contracts and existing pure domain algorithms; unchanged paths |
| `repository.py` | Persistence protocol consumed by Session |
| `storage.py` | Existing JSON implementation, legacy imports and representation |
| `robot/base.py`, `robot/simulator.py`, `robot/esp32_ws.py` | Existing motion protocol and adapters; firmware communication unchanged |
| `vision/camera.py` | Scoped, injectable capture ownership; scan/track role metadata |
| `vision/cards.py`, `vision/camera_tracker.py` | Fixture/card recognition and camera pose processing; existing OCR callable typed as OcrPort |
| `frontend/src/api/` | Shared session types, HTTP client and sequenced WS subscription |
| `frontend/src/board/`, `calibration/` | Shared board composition and projection math |
| `frontend/src/projection/` | Passive fullscreen display and window-opening utility |
| `frontend/src/instructor/` | Existing page containers; focused useGamepad input hook |

Dependency direction: routes → Session → pure domain + adapter protocols.
Concrete adapters are assembled in dependencies/runtime, not inside domain logic.
The pure domain modules do not depend on FastAPI, OpenCV or robot transport.
The frontend displays authoritative backend tiles and shares one board renderer.

## Extension seams — not implemented features

- SQLite: implement Repository's existing methods without changing Session or JSON fixtures.
  A future history query API should be designed alongside actual persistence requirements.
- OCR: inject OcrPort into OpenCvCardRecognizer; instructor review remains authoritative.
- Single camera: inject CameraSource into scanning/tracking. Only OpenCvCameraSource opens
  webcams. No locking, scheduling, handoff, repositioning or recalibration workflow is provided;
  existing scan index 0 and track index 1 defaults are deliberately preserved.
- Joystick: replace/extend the input hook independently of discrete recording compilation.
  Timestamped analog samples and continuous reconstruction require a future contract/workflow;
  current records and supported block semantics remain unchanged.
- AI: Board's decorative theme layer remains separate from geometry and grading. A future
  backend provider may supply artwork there; learning recommendations must not command motors.
  No unused AI interfaces, empty packages or runtime dependencies were added.

## Compatibility

Public module paths, main.build_session import, InstructorApp.openProjectionWindow export,
REST routes, WS snapshot/pose messages and sequence policy, JSON paths, fixture IDs,
robot primitives/acks and Arduino sketch location are retained. Display branding is Grassroot;
legacy package name, popup window name and firmware network identifiers remain unchanged.
No camera or firmware hardware validation is claimed.


## Full implementation additions

The implementation notes under `docs/implementation/` supersede the earlier extension-only
status above. CameraCoordinator owns role/calibration/preview; Session owns the control lease;
ContinuousRecorder owns timestamped input/trajectory reconstruction; SQLiteStorage implements
persistence with JSON compatibility; ThemeJobs owns bounded Gemini requests and caches;
learning.py is a pure BKT/candidate module. history_api/intelligence_api are focused routers.
Frontend History and Themes & Progress reuse the existing shared types, client and Board.
The six-command block language, ordered grader and projector geometry remain authoritative.
