# Hardware stabilization review

Base: integrated `main` at `dd2fef1`. Branch: `fix/hardware-stabilization`.
No merge, deployment, hardware flashing or invented measurements were performed.

## Result and compatibility

- Unexplained `STOPPED` acknowledgments now produce `ROBOT_FAULT`; a latched instructor or
  safety-stop reason is preserved. Faults remain excluded from learner evidence.
- Session reserves camera/calibration ownership before asynchronous work. Run, recording,
  scanning and conflicting state changes fail immediately while reserved. STOP always bypasses
  ownership, including pulses while the session is idle.
- Joystick snapshots contain live connection, protocol, armed, active, age/freshness and error
  fields. Transient input status is no longer written into settings.
- USB protocol v2 carries boot identity, sequence, device time and a host sync challenge.
  Reconnect flushes USB input, rejects prior-lease frames and requires neutral/released input.
  Replayed, delayed, malformed or overflowing input stops/disarms. Serial acquisition does not
  wait for drive ACKs: axes coalesce to latest, button edges use a bounded 16-entry queue.
  Neutral STOP bypasses pending drive ACKs. The 250 ms expiry and 300 ms input watchdog remain.
- Both controllers build for XIAO ESP32-S3. Robot GPIO pairs LF 1/2, LR 3/4, RF 5/6, RR 43/44;
  both SLP pins 3V3. Joystick GPIO1/2/3. The robot's USB serial does not consume the motor UART
  pins: the pinned XIAO board definition enables USB CDC on boot.
- Default robot output is disabled. Calibration firmware accepts instructor-only bounded pulses
  (100 ms default, 250 ms maximum, no automatic retry/repeat), followed by polarity-corrected
  translation/turn trials. Normal firmware builds require one privately measured profile, motor
  rating/wiring verification and acknowledgement. Backend and firmware profile hashes must match.
  The 22 cm / 6 V configuration is recorded; motor rating, polarity and timing remain unverified.
- Firmware hello publishes enabled/calibrated/mode/profile identity and remaining ID-ledger slots;
  ACKs update capacity. Run preflights capacity. IDs are never evicted to make room silently.
- Both XIAOs can join the existing EeroBuddy LAN using one ignored local credential header.
  The supplied credentials were configured in this checkout only; none are included in Git.
  Robot control stays Wi-Fi/WebSocket and joystick control stays USB serial. No ESP-NOW was added.
- Two-job artwork admission is serialized across persistence; completed task handles are removed
  and immediate cancellation is persisted. Cached/static failure paths remain.
- TrOCR outputs explicitly uncalibrated confidence; crops, uncertainty and mandatory numeric review
  remain. No false fixed accuracy is shown. Real-card benchmarking remains available.
- Mac scripts pin Python 3.13 / Node 24.4.1, opt in to vision/OCR/serial/AI/firmware dependencies,
  preserve private configuration and bind the backend to localhost. UI errors are visible and
  stale validation responses cannot overwrite newer checks.

Existing REST routes, six-command student language, ordered grading, revisits, renderer/geometry,
fixtures, simulator, fault injection, discrete recording, histories and synthetic samples are retained.
The new `/api/hardware/calibration` route is instructor-only by workflow; it is not part of the
student compiler. Snapshot/readiness/ACK fields are additive. Physical continuous input requires
updated joystick firmware; simulator browser input retains its existing explicit v1 adapter.

## Verification

| Check | Result |
| --- | --- |
| Baseline on integrated code | 64 backend, 8 frontend, 3 browser tests passed; typecheck/build and two original firmware targets passed |
| Final backend suite | 87 passed; existing Starlette/AnyIO deprecation warning |
| New regression tests | 23 passed: STOP reasons, pending camera ownership/failure cleanup, live/persisted status, serial delay/replay/boot/rearm/edges/overflow/ACK independence, calibration, readiness/ledger, profile build guards, uncalibrated OCR review and theme admission/cancel |
| Frontend unit tests | 8 passed |
| TypeScript / production build | Passed |
| Playwright workflows | 4 passed: scan review, synchronized projection/global STOP, library/history/calibration, recommendation/theme fallback, live input/error status |
| Firmware | Disabled robot, calibration robot and XIAO joystick compiled with private station configuration |
| Calibrated firmware build | Passed with an isolated **synthetic compile-only fixture**, never a measured or uploadable profile; incomplete real profile correctly rejected |
| npm audit | 0 vulnerabilities; no dependency upgrades |
| Python audit | **Unresolved:** 133 entries / 92 distinct IDs across 8 installed packages, including optional OCR and tooling; see dependency report |
| Shell / diff checks | Setup/runner shell syntax and whitespace checks passed; private credential/profile paths ignored |
| Lint / backend static types | No existing configured checker; none claimed |
| Live Nano Banana | **Deferred by user** until robot works without themes; offline/cache regression tests only |
| Physical acceptance | **Pending**, no USB hardware available to this host; no flashing, electrical or motion tests claimed |

The first root-directory pytest invocation failed collection because `app` was not on PYTHONPATH;
rerunning from `backend/` corrected the invocation. The watchdog test was updated to the monotonic
clock used by input freshness. New test setup initially needed an explicit app-session override;
those test harness failures were corrected. All final functional test failures are resolved.
The Python audit is an unresolved security gate; do not describe this PR as fully hardware-ready
or as having all completion gates passed.

## Acceptance gates still required

Use [the Mac hardware runbook](../MAC_HARDWARE_SETUP.md). Every physical gate is still open:

1. Confirm motor specifications/current limits, 6 V supply, grounds, wiring and LAN access.
2. Flash calibration/joystick firmware, verify each polarity with isolated pulses, then measure
   translation and in-place turns on the 22 cm grid. Save/acknowledge/reflash the run profile.
3. Demonstrate cards → review → robot → observed same-index grading → synchronized projection
   → saved history, including wrong-then-correct, revisits, extra/incomplete entries.
4. Demonstrate joystick → raw inputs/ACKs/pose recording → reviewed uncertain reconstruction
   → compiler/bounds-validated replay → saved history.
5. Verify physical STOP/neutral/second button, disconnect/expiry/watchdog, tracking loss, boundary,
   duplicate commands, full-ledger messages and reconnect without motion replay.
6. Check shared camera placement/parallax, projector geometry/readability/dark marker regions and
   actual handwritten-card OCR accuracy; complete the deferred live artwork test separately.
7. Resolve the recorded Python security findings in separately reviewed dependency maintenance.

The existing [complete specification matrix](ACCEPTANCE_MATRIX.md) remains the full-product
checklist. This report records stabilization overrides and tests, not a claim of physical completion.

## Changed files

- `.gitignore`
- `.nvmrc`
- `.python-version`
- `README.md`
- `backend/app/ai/themes.py`
- `backend/app/hardware.py`
- `backend/app/joystick.py`
- `backend/app/main.py`
- `backend/app/robot/esp32_ws.py`
- `backend/app/session.py`
- `backend/app/vision/camera.py`
- `backend/app/vision/cards.py`
- `backend/app/vision/ocr.py`
- `backend/tests/test_capture_persistence.py`
- `backend/tests/test_stabilization.py`
- `docs/ARCHITECTURE.md`
- `docs/ASSUMPTIONS.md`
- `docs/ESP32_MOTOR_WIRING.md`
- `docs/HARDWARE_CHECKLIST.md`
- `docs/MAC_HARDWARE_SETUP.md`
- `docs/implementation/ACCEPTANCE_MATRIX.md`
- `docs/implementation/DEPENDENCIES.md`
- `docs/implementation/PHASE_1.md`
- `docs/implementation/PHASE_2.md`
- `docs/implementation/PHASE_3.md`
- `docs/implementation/PYTHON_AUDIT.json`
- `docs/implementation/STABILIZATION.md`
- `firmware/esp32/codeanywhere/codeanywhere.ino`
- `firmware/esp32/codeanywhere/hardware_pins.h`
- `firmware/esp32/joystick/joystick.ino`
- `firmware/esp32/network_config.h`
- `firmware/hardware_profile.py`
- `firmware/platformio.ini`
- `frontend/e2e/workflows.pw.ts`
- `frontend/src/api/client.ts`
- `frontend/src/api/types.ts`
- `frontend/src/instructor/IntelligenceTab.tsx`
- `frontend/src/instructor/ProgramTab.tsx`
- `frontend/src/instructor/PuzzleEditor.tsx`
- `frontend/src/instructor/RecordingTab.tsx`
- `frontend/src/instructor/SetupTab.tsx`
- `frontend/src/projection/ProjectionView.tsx`
- `hardware/profile.example.json`
- `scripts/run-local.sh`
- `scripts/setup-mac.sh`
- `tools/check_theme_live.py`
