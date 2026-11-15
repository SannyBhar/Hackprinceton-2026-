# Greenlite — Codex Structural Refactor Brief

**Companion specification:** `Greenlite_Project_Architecture.md` (authoritative product requirements)  
**Existing repository:** https://github.com/SannyBhar/Hackprinceton-2026-  
**Task type:** **Structural refactor only**. This is **not** a request to implement Greenlite's missing features.  
**Project name:** Greenlite (formerly Grassroot, originally CodeAnywhere)

## 0. Instructions to Codex (read first)

Refactor the **existing** repository incrementally. Preserve working behavior and tests. Do **not** restart the project or generate a new application from scratch. The architecture specification describes the eventual product; this brief defines the **limited restructuring work for this pass**. If the two conflict on implementation scope, **this brief wins for this pass**; the product specification still wins for eventual behavior.

**Scope fence:** Only reorganize code, separate responsibilities, define stable interfaces, move existing implementations behind those interfaces, consolidate configuration, document the architecture, and add/refine regression tests needed to prove behavior was preserved. **Do not build any new user-visible functionality yet.** Do not add AI models, OCR engines, camera pipelines, joystick trajectory inference, SQLite migrations, firmware features, new UI flows, or new maze-generation algorithms in this pass. Empty interfaces, protocols, typed contracts, and clearly marked *nonfunctional* adapters/placeholders are acceptable only where genuinely useful. Avoid large unused scaffolds and speculative abstractions.

**Hard exclusions in the child programming language:** no loops, conditionals, functions, side-strafing, arbitrary-angle turns, or additional block commands. Normal programming language `if`/`for` statements used to implement the software are fine.

**Preserve unchanged:** ordered path grading, green/red revisit history and split coloring, live projection behavior, simulator, manual scan review, safety stops, basic command semantics, existing reverse-recording demo, and all currently working instructor workflows. Existing APIs and persisted fixtures should remain compatible unless a change is unavoidable and documented.

> **Do not assume the repo's README proves the code is correct.** Inspect actual files, run tests, and document results. If tests cannot run, report the exact blocker. Never claim hardware is validated from simulator tests.

---

## 1. Source-of-truth decisions (for future compatibility, not implementation now)

The accompanying product specification fixes the eventual design:

| Area | Confirmed final requirement |
|---|---|
| Identity | Greenlite |
| Commands | `START`, `FORWARD n`, `BACKWARD n`, `LEFT`, `RIGHT`, `STOP` only |
| Card distance | Handwritten integers, OCR with mandatory instructor review when uncertain |
| Camera | **One** shared generic USB webcam for scanning and arena tracking |
| Joystick | **Continuous** driving; reconstructed code can be approximate/uncertain |
| Persistence | **SQLite**; current JSON data can remain until a later migration |
| AI | Generative *decorative maze themes* + adaptive learning/maze selection; no chatbot |
| Grading | Exact ordered observed-cell entries vs. exact ordered target entries |
| Projector | Passive external monitor/fullscreen projection; no projector-device API |
| Motor controller | ESP32-S3 on a 4WD chassis, two DRV8833 modules **subject to hardware verification** |

For this refactor, only make the design modular enough to support these later. Do not silently substitute current behavior as if a later requirement were already fulfilled.

## 2. First inspect the current repository

Before modifying code:

1. Record the current commit, working-tree status, and relevant package/firmware versions. Do not overwrite teammates' uncommitted changes. Work on a dedicated `grassroot-structural-refactor` branch if the environment permits.
2. Inventory *actual* files and dependencies. The repository README currently describes roughly:
   - `backend/app/`: `models`, `grading`, `compiler`, `tracking`, `recording`, `session`, `main`.
   - `backend/app/robot/`: base protocol, simulator, ESP32 transport.
   - `backend/app/vision/`: card readers and camera tracker.
   - `frontend/src/`: API, shared board renderer, calibration, projection, instructor screens.
   - `firmware/esp32/greenlite/`: Arduino firmware.
   - `fixtures/`, `tools/`, `docs/`.
   Treat these as **reported paths**; verify before moving or renaming anything.
3. Map imports and call sites, especially for the session class, REST/WebSocket handlers, simulator, grading reducer, recording, projector rendering, and robot transport.
4. Capture baseline outputs: backend tests, frontend tests, frontend build, and, if possible, a simulator smoke test. Record pass/fail counts, not guesses.
5. Identify architectural risks (circular imports, oversized modules, duplicate state, direct hardware access from request handlers, global camera handles, blocking operations, undocumented configuration). Make a short before/after map.

**Do not rewrite stable, tested pure functions merely to make them look more object-oriented.** Favor preserving implementation and introducing boundaries around it.

## 3. Refactor objectives

1. **One owner for session state:** the backend session coordinator controls transitions and the active puzzle/run snapshot. REST and WebSocket handlers are thin adapters.
2. **Pure logic stays independent:** program parsing/validation, ordered grading, visit-color reduction, path quantization contracts, and maze data models do not import HTTP, camera, firmware or database code.
3. **Adapters isolate I/O:** robot, joystick, camera, OCR, persistent storage, AI themes, and adaptive-learning providers expose small interfaces; the current working adapters remain available.
4. **One owner for each device:** no multiple independent camera consumers, no simultaneous joystick/manual-program command ownership, no competing authoritative robot-pose stores.
5. **Typed, validated events:** shared command/event schema separates requested movement, acknowledged movement, observed pose, grading results, and operational faults.
6. **Configurable, testable construction:** dependency injection or simple factories select simulator vs. real adapters without pervasive `if env == ...` branches.
7. **Safe future extension:** adding the selected features later should not require redesigning grading, presentation, or session coordination.

## 4. Target module boundaries (logical design; do not create empty folders gratuitously)

**Important:** This is a target responsibility map, **not a mandatory one-shot relocation**. Use actual existing filenames where practical, and move code in small tested steps.

```text
backend/app/
  main.py                   # app creation; route registration only
  api/                      # thin REST and WebSocket handlers (extract from main if needed)
  core/
    contracts.py            # typed shared commands, poses, visits, errors
    session.py              # authoritative state machine/orchestrator
    events.py               # typed event publishing + reconnect snapshot boundary
    dependencies.py         # factories/wiring; concrete dependencies assembled here
  programming/
    compiler.py             # existing parser, validation, bounds planning
    grading.py              # existing ordered grader, pure
    visits.py               # existing revisit reducer and presentation status, pure
    reverse.py              # move existing discrete recording implementation here OR keep
                              # recording/ as a focused package; DO NOT add continuous inference yet
  vision/
    camera.py               # single-camera ownership interface (no new capture behavior)
    cards.py                # existing ArUco/fixture readers via interface
    tracker.py              # existing camera/fixture pose trackers via interface
    ocr.py                  # contract only; do not implement handwriting model now
    calibration.py          # existing coordinate transforms where applicable
  devices/
    robot.py                # command transport protocol, simulator/ESP32 adapters
    joystick.py             # existing keyboard/gamepad adapter; continuous interface contract only
  storage/
    repository.py           # interface around existing JSON storage
    json_store.py           # preserved working implementation
    # SQLite implementation/migrations explicitly out of scope
  ai/
    theme_provider.py       # minimal interface only IF needed by existing theme code
    skill_provider.py       # minimal interface only IF needed; no ML code

frontend/src/
  api/                      # central typed HTTP/WS client and state subscription
  instructor/               # existing instructor pages and controls
  board/                    # canonical board rendering; no duplicated grading logic
  calibration/              # projection/camera calibration UI & math where present
  projection/               # passive fullscreen display, shared board data
  components/               # genuinely reusable presentational components

firmware/esp32/...          # retain current firmware location until build/upload paths verified
fixtures/                   # preserve IDs/format and known-good demo data
tests/                      # optional organization; preserve existing runners/locations
docs/                       # updated architecture and migration notes
```

**Avoid premature fragmentation.** If a module is already small and cohesive, leave it. If extracting `core/` or `api/` would add hundreds of lines of wrapper code, use simpler boundaries. Do not move the firmware or rename its sketch folder in this pass unless Arduino tooling and documentation are updated and tested.

### Responsibility and dependency direction

```text
HTTP / WebSocket / React clients
           ↓
Session/Application services (authoritative state, validation, orchestration)
           ↓
Pure domain logic (models, compiler, grading, visit history)
           ↓ (interfaces only, not concrete imports)
Robot / Camera / Joystick / Storage / AI provider adapters
```

In practice, application services **call adapter interfaces**; concrete adapters do not import application services to mutate them. Prefer explicit callbacks/events or return values over hidden global state. Pure domain code must never depend on React, FastAPI, hardware SDKs, or an AI provider.

## 5. Existing components: precise refactor policy

| Component | Structural action **now** | Do **not** do now |
|---|---|---|
| Ordered grader + revisit reducer | Preserve tested pure algorithms; isolate imports and add characterization tests if absent | Change same-index behavior or split-color rules |
| Simulator | Keep it behind the same robot contract as hardware | Replace with hardware-only behavior |
| Session coordinator | Extract I/O and handlers, make state transitions explicit; maintain legacy routes/events | Rewrite state semantics or implement new workflows |
| REST + WebSocket | Thin routes, one authoritative snapshot/event source, stable event contracts | Redesign all endpoints/UI at once |
| Robot transport | Interface for command send/ack/STOP; retain working simulator and experimental ESP32 transport | Redesign ESP32-S3 wiring/firmware or assert hardware verification |
| Vision | One camera-access ownership **interface**, distinguish scan vs. track consumers; preserve existing adapters | Implement new single-camera scheduling/calibration or OCR engine |
| Cards | Retain fixture/OpenCV path and manual review; separate reader from parser | Implement handwritten digits now |
| Joystick/recording | Isolate source events, recording store, discrete-to-block logic behind a narrow contract | Implement continuous-to-code algorithm now |
| Storage | Define repository protocol and wrap current JSON logic | Migrate database or write SQLite schema now |
| Themes | Keep current static themes; separate board geometry from artwork in APIs as needed | Call image-generation API now |
| Analytics | Expose future read-only attempt history access where low-cost | Implement skill models or adaptive selection now |
| Frontend | Reuse board renderer, share typed data/state; keep instructor/projector separate | Replace UI design or build new dashboards |
| Firmware | Leave functioning sketch intact; document contract and unknowns | Restructure pins or change power behavior without hardware |

### Explicit non-negotiable algorithm invariants

- Target is an ordered list `targetEntries` of **cell entries after leaving start**, including revisits; observed entries are stable transitions, **not** video frames or turns in place.
- For observation index `i`, correctness is `i < len(targetEntries)` **and** `actualEntries[i] == targetEntries[i]`. Increment regardless of correctness. Do not latch subsequent entries incorrect after an error.
- Additional observed entries past the target are incorrect; unobserved target entries remain incomplete.
- A wrong entry does **not** itself stop the robot. Boundary violations, stale tracking, explicit STOP and operational faults are distinct stop causes.
- Cell revisit visuals preserve per-visit history (solid green, solid red, or diagonal split according to first/second ordering). Preserve the team's documented handling of 3+ mixed visits as a labeled policy, not an unnoticed behavior change.
- Projection always uses authoritative backend state, not frontend recalculation; projector is a passive output.
- Repeated command IDs must not execute twice; run/program/puzzle versions are immutable while executing.

## 6. Stable interface contracts to define (no real feature implementation)

Use existing model types if already equivalent. Prefer Pydantic/dataclasses/TypeScript types already in the repository; avoid redundant parallel schemas.

**RobotPort**
- `send(command: RobotCommand) -> Ack/Result`
- `stop(reason: StopReason) -> Ack/Result`
- `status() -> RobotStatus`
- Simulator and ESP32 adapter implement the *same* behavioral contract; preserve idempotency and watchdog behavior.

**CameraSource / VisionPort**
- `open/close` or managed ownership; frame timestamps; scan result/pose observation with validity and source metadata.
- Distinguish scan and track roles. One camera owner should eventually arbitrate the two, but **do not implement new scheduling in this pass**.
- Camera readings are observations, never invented truths.

**CardReaderPort / OcrPort**
- Return marker ID, card order, command candidate, numeric candidate (where applicable), crop/reference, confidence/uncertainty.
- Current manual/fixture reader may return no OCR candidate; preserve instructor confirmation behavior.

**JoystickInputPort**
- Timestamped X/Y axes, button press/release, connection health and neutral/dead-zone information.
- Current keyboard/gamepad source may adapt to this; this pass must **not** convert continuous values into final block programs.

**RecordingPort / ReverseCompiler boundary**
- Keep raw timestamped input events, robot acks, pose observations, generated code, and ambiguity flags as separable records/types.
- Preserve existing discrete reverse demonstration; reserve expansion point for continuous trajectory quantization without pretending it works today.

**RepositoryPort**
- Read/write active puzzles, calibrations, attempts and histories through backend services; preserve existing JSON representation for now.
- Future SQLite adapter must be swappable without changing grading or HTTP business logic.

**ThemeProvider / LearningModel boundaries**
- Optional, **minimal** future interfaces, not runtime-required dependencies.
- Themes can change rendering background only, not route/maze correctness. Adaptive learning can recommend but not authorize robot movement. No AI API calls during this refactor.

**Shared event invariants**
- Include stable identifiers: session/run ID, message or event ID, relevant puzzle version, timestamp, event sequence if existing.
- Distinguish `command_requested`, `command_acknowledged`, `pose_observed`, `cell_entered`, `visit_graded`, `operational_stop`, and `recording_changed`; if the existing event names differ, provide compatible translation rather than breaking clients.
- Reconnecting clients must use a snapshot and must not double-grade or replay commands.

## 7. One-camera and concurrent-control *structural* protections

- Introduce a **single** camera ownership abstraction. Nothing else may open the same webcam directly except its implementation. Preserve fixture mode.
- Document that card scanning and maze tracking may use the same camera **sequentially**; actual single-camera handoff and camera placement tests belong to a later implementation phase.
- Centralize permission to command motors. `RUNNING` and `RECORDING` control modes must be mutually exclusive; operational STOP always takes precedence.
- Keep long-running AI, vision or storage operations off the synchronous motor STOP path. In this phase, ensure the architecture permits this; no need to implement background workers.
- Pose tracking loss must not be represented as a valid or fabricated cell. Do not weaken existing stop behavior.

## 8. Configuration, naming, and dependency hygiene

1. Prefer a single typed/configured backend settings entry point and a documented example environment file. Keep old `CA_*` variables accepted as aliases temporarily if they already work; document replacements under `GRASSROOT_*` without breaking teammates' setups.
2. Use **Greenlite** for display name, README, main docs and current application identifiers. Don't change network endpoints, package names, database paths, build tools, microcontroller IDs, or imports solely for branding unless fully validated.
3. Preserve existing Python and frontend dependency management; pin or lock versions only when compatible with current toolchain. No unnecessary frameworks, event brokers, ORMs, or new services.
4. Keep secrets out of the repo. Any future image-generation provider key is backend-only; this phase does not need one.
5. Centralize logging and error labels where practical. Errors should distinguish incorrect code, bad scan, stale camera observation, hardware command failure, boundary stop and transport loss.
6. Remove dead code and duplicate wrappers **only after** tests demonstrate nothing depends on them; avoid wide automatic reformatting unrelated files.

## 9. Frontend structural requirements

- The instructor and fullscreen projection views share a **single typed board/session-state shape**, but can render it differently.
- Existing board geometry, perspective warp, and grading overlays remain unchanged.
- Avoid direct `fetch`/WebSocket setup scattered across components: use existing centralized client/hook, refactor only where necessary.
- Separate page-level container logic from reusable presentation components without a massive UI rewrite.
- Do not move grading decisions or motor validation to React; React displays backend results.
- Keep mode state and session state explicit; no duplicated local sources of authoritative puzzle/run state.
- Preserve current CSS and interactions unless a correction is essential to maintain behavior after extraction.

## 10. Testing and validation gates

**Baseline before edit** (use exact commands verified against repo):

```bash
cd backend && .venv/bin/python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run build
```

If setup is missing, install through the repository's documented steps and note the environment. Preserve a baseline test report.

**Required regression coverage after refactor:**

1. The known path grading example: target `[A,B,C,D]`, observed `[A,C,B,D]` → `green, red, red, green`.
2. Extra entries red, missing entries incomplete, turns and duplicate camera frames do not count as visits.
3. Revisit solid/split rendering consistent with existing two-visit semantics.
4. Wrong code does not trigger operational stop; boundary/stale-tracking/explicit STOP still do.
5. Robot simulator execution and duplicate command protection continue working.
6. Discrete recording demo still produces identical supported code.
7. Frontend projection warp tests and simulator UI build pass.
8. Existing REST/WebSocket integration behavior remains compatible; reconnect does not duplicate events.
9. Imports and module boundaries have no cycles; code compiles and boots in simulator mode.
10. No new hardware claim is made; if real hardware is available, keep smoke tests optional and report their status separately.

Add small unit tests at interfaces or extracted pure modules **only where those guard refactor risks**. Do not invent new feature tests for functionality not implemented.

## 11. Incremental implementation order

**Do not run all phases as one giant rewrite.** After each phase, run relevant tests and keep the diff reviewable.

### Phase A — Inventory and guardrails
- Read actual repository source and both Markdown documents.
- Save baseline and before/after module map; add characterization tests for critical unprotected current behavior.
- Stop if the checked-out repo is radically different from this description; report and adjust the mapping rather than following fictional paths.

### Phase B — Pure domain boundaries
- Isolate existing contracts, compiler, grader, visit history and state transition rules.
- Avoid modifying algorithms; move files and imports only as necessary.
- Run backend tests.

### Phase C — Device and storage interfaces
- Wrap existing robot simulator/hardware adapter, card reader/tracker, recording input, and JSON store behind narrow ports.
- Centralize construction/config selection; preserve existing default simulator behavior.
- Add a minimal camera-ownership boundary without building new camera features.
- Run backend and simulator tests.

### Phase D — Session/API decoupling
- Extract heavyweight orchestration out of route handlers into an application service **if** it is currently mixed.
- Keep one authoritative state machine; preserve endpoint payloads and WebSocket events.
- Ensure STOP and mode exclusion remain intact.
- Run all backend tests and simulator flow.

### Phase E — Frontend separation and naming
- Consolidate typed API/state consumption and shared board renderer as needed.
- Rename user-visible project branding to Greenlite and update documentation.
- Avoid UI redesign and unintended behavior changes.
- Run frontend tests and build.

### Phase F — Verification and handoff
- Execute all tests and documented simulator demo steps.
- Record before/after module map, moved files, API/fixture compatibility, tests, known risks, and next-step feature modules.
- Commit in logical chunks if working in a branch; **do not push or open a PR without authorization**.

## 12. Deliverables

Codex should return:

1. **Refactored existing source tree** (not a brand-new app), with no broken imports.
2. **Updated `README.md`** explaining how to run the simulator and tests and identifying Greenlite by name.
3. **`docs/ARCHITECTURE.md`** with a concise module responsibility map, dependency direction and extension points; link the companion Greenlite specification.
4. **`docs/REFACTOR_NOTES.md`** listing old → new paths, preserved behavior, design tradeoffs, unresolved hardware dependencies and any intentional compatibility aliases.
5. **Test report** with exact commands and results, plus warnings for any tests not run.
6. **Short next-phase TODO list** (handwriting OCR, one-camera handoff, continuous joystick reconstruction, SQLite migration, AI themes, adaptive learning, ESP32-S3 electrical/firmware validation) clearly marked **NOT IMPLEMENTED** unless already genuinely present.

## 13. Definition of done / stop conditions

**Done only when:**

- The existing simulator and working UI run with the documented commands.
- Existing tests pass (or original failures are explicitly reproduced, not falsely attributed to the refactor).
- Public API/event behavior remains compatible or all intentional changes are documented and covered.
- Core domain logic is insulated from framework/hardware concerns; hardware/storage/vision interfaces have clean ownership.
- No duplicate state managers or circular imports were introduced.
- There is no fake or hardcoded AI/OCR/SQLite implementation disguised as completed work.
- All user-visible project branding reads **Greenlite**, while necessary legacy internal compatibility is maintained.
- The refactor has not added unsupported child-programming commands.

**Stop and report instead of guessing if:** the current repo differs substantially from the README; uncommitted teammate work would be overwritten; hardware dependencies cannot be verified; a critical baseline test fails; or a proposed extraction would require changing established grading/projection semantics.

---

## 14. Copy/paste task for Codex

> In the current repository, read `Greenlite_Project_Architecture.md` and `Greenlite_Codex_Structural_Refactor.md`. Execute **only the structural refactor** described in the refactor brief. First inspect the actual code and establish baseline tests. Keep working implementations, simulator, endpoints, grading, and projection behavior unchanged. Introduce clean ownership boundaries, typed contracts, adapter interfaces, and focused module separation where justified, without gratuitous scaffolding. Update branding to Greenlite while preserving compatibility. Do not implement handwriting OCR, continuous reverse coding, SQLite, AI generation, adaptive learning, new firmware behavior, or additional block-language features yet. Work incrementally, run tests after each phase, and report files changed, test results, compatibility risks, and explicit unimplemented next-phase items. Do not push changes without permission.
