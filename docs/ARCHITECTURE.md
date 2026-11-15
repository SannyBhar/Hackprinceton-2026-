# Greenlite — current architecture

See the [full product specification](Greenlite_Project_Architecture.md) and
[structural brief](Greenlite_Codex_Structural_Refactor.md). Implementation and acceptance status are tracked separately in
[the requirements matrix](implementation/ACCEPTANCE_MATRIX.md); software existence does not imply physical acceptance.

| Module | Responsibility |
| --- | --- |
| `backend/app/main.py` | Existing REST/WS handlers, FastAPI registration and static UI serving |
| `settings.py`, `dependencies.py` | Environment configuration and concrete adapter composition |
| `runtime.py` | Session, card-scanning webcam and board-camera startup/shutdown ownership |
| `session.py` | Single authoritative coordinator, mode exclusion, STOP, snapshots, sequenced events |
| `models.py`, `compiler.py`, `grading.py`, `tracking.py`, `recording.py` | Shared contracts and existing pure domain algorithms; unchanged paths |
| `repository.py` | Persistence protocol consumed by Session |
| `storage.py` | Existing JSON implementation, legacy imports and representation |
| `robot/base.py`, `robot/simulator.py`, `robot/esp32_ws.py` | Existing motion protocol and adapters; firmware communication unchanged |
| `vision/camera.py` | Scoped, injectable capture ownership for card scanning |
| `vision/cards.py` | Fixture/unit-block recognition; DICT_4X4_1000 IDs 0–3, no distance recognition |
| `vision/board_camera.py` | Markerless overhead tracking: test-pattern calibration, robot detection, pose stream |
| `frontend/src/api/` | Shared session types, HTTP client and sequenced WS subscription |
| `frontend/src/board/`, `calibration/` | Shared board composition and projection math |
| `frontend/src/projection/` | Passive fullscreen display and window-opening utility |
| `frontend/src/instructor/` | Existing page containers; focused useGamepad input hook |

Dependency direction: routes → Session → pure domain + adapter protocols.
Concrete adapters are assembled in dependencies/runtime, not inside domain logic.
The pure domain modules do not depend on FastAPI, OpenCV or robot transport.
The frontend displays authoritative backend tiles and shares one board renderer.

## Implemented boundaries

- `sqlite_store.py` implements the repository with idempotent JSON imports and versioned records.
- `vision/coordinator.py` owns the webcam for card scanning and preview. Robot tracking is `vision/board_camera.py`;
  the API refuses to open either while the other holds the webcam.
  Session reserves conflicting device operations synchronously before asynchronous transitions.
- `vision/markers.py` owns the physical unit-block registry; `vision/cards.py` reads repeated marker instances in spatial order. `vision/ocr.py` is retained for historical tooling, outside the active physical-card workflow.
- `joystick.py` acquires synchronized USB protocol-v2 samples independently of drive acknowledgments.
  Only latest axes are retained for control; a bounded button-edge queue preserves toggles.
- `hardware.py` validates one private measured profile. Firmware publishes readiness/profile identity
  and ledger capacity. The default target has disabled outputs; calibration and run builds are distinct.
- `ai/themes.py` serializes two-job admission and caches decorative backgrounds. No AI path controls
  geometry, grading or motors. `learning.py` owns transparent BKT/candidates, not device control.
- `history_api.py` and `intelligence_api.py` expose focused persistence/provider workflows.
- `firmware/esp32/network_config.h` shares optional private station credentials between both XIAOs;
  Wi-Fi is independent of the USB joystick protocol. Robot commands remain WebSocket JSON.

## Compatibility

Public module paths, main.build_session import, InstructorApp.openProjectionWindow export,
REST routes, WS snapshot/pose messages and sequence policy, JSON paths, fixture IDs,
robot primitives and additive acknowledgments and Arduino sketch location are retained. Display branding is Greenlite;
legacy package name, popup window name and firmware network identifiers remain unchanged.
No camera or firmware hardware validation is claimed.


See [the stabilization report](implementation/STABILIZATION.md) for additive contracts and pending hardware gates.

Current card-format override: [two-inch unit movement blocks](UNIT_BLOCKS.md). Saved numeric programs retain compatible internal counts; the student UI uses repeated one-cell blocks.
