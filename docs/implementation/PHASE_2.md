> Historical phase record. Current hardware/build instructions and verification status:
> [stabilization](STABILIZATION.md) and [Mac runbook](../MAC_HARDWARE_SETUP.md).

# Phase 2 — persistence, capture and reverse coding

Phase 2 is stacked on Phase 1. Backend suite: 55 passed (includes synthetic ArUco camera
calibration, JSON import/revert/restart, normalized evidence, continuous neutral/stale stops,
reverse intent and uncertainty). Frontend suite: 8 passed; build/typecheck passed.
PlatformIO robot and joystick builds passed. No firmware was uploaded.

## Storage / UI

SQLite is now the default; set GRASSROOT_STORAGE=json for the legacy adapter. Data stays in
GRASSROOT_DATA_DIR / CA_DATA_DIR. JSON source files are never deleted. Imports are tracked
idempotently; sqlite_import_report.json records imported/skipped/errors. A schema migration
ledger and puzzle-version/attempt/visit/command tables accompany typed records for students,
calibrations, recordings, artwork and learning estimates. Interrupted runs become INTERRUPTED
on startup; no command resumes. Back up the data directory before changing adapters.
History provides local aliases, student selection, saved attempt details and exports, recording
import/export/review, and puzzle JSON import/export. Library bundled overrides/reverts persist.

## OCR

Install backend/requirements-ocr.txt, set GRASSROOT_OCR=local and use OpenCV cards. The adapter
uses microsoft/trocr-small-handwritten; configure HF_HOME to a writable local model cache,
and cache model files before joining the robot AP. Candidate confidence is conservative and
not calibrated. Every numeric value requires instructor review; missing dependencies/model
or invalid output falls back to manual entry with an issue label. Original crops/text/model
and corrected confirmed program are retained with attempts. No child handwriting benchmark
has been performed; accuracy/latency acceptance remains PENDING on actual cards.

## Continuous joystick

Install backend/requirements-joystick.txt and set GRASSROOT_JOYSTICK_PORT to the USB device.
The second ESP32 emits protocolVersion 1 NDJSON at 115200 baud: seq, timestampMs, x/y [-1,1],
button. Centre is sampled on boot: leave stick neutral. Button debounce 40ms in firmware,
600ms rising-edge toggle in backend; dead zone .18, dominant-axis with Y winning ties.
Serial loss/invalid samples stop recording; 300ms input staleness stops motors. Raw inputs,
commands/acks and observed pose segments are separate. Generated code is approximate and
requires explicit instructor review plus compiler validation. Neutral and recording-end stop
motors before reconstruction. Simulator-only browser controls exercise the same backend.

Robot firmware v2 advertises continuous capability; old firmware cannot enter continuous mode.
Drive messages expire within 250ms and require acknowledgment. Existing discrete primitives
and command IDs remain supported. Simulator supports the same expiring controls.

Build both: `PLATFORMIO_CORE_DIR=$PWD/work/platformio backend/.venv/bin/pio run -d firmware`.
Joystick target is a generic ESP32-S3 build only: confirm actual board before flashing. Supply
JOYSTICK_X_PIN, JOYSTICK_Y_PIN and JOYSTICK_BUTTON_PIN via build_flags after the wiring commit;
all default to -1 and emit an unconfigured error rather than invent input. Robot output enable
still requires verified wiring. Pending: real controller board/pins, physical stop tests,
trajectory reconstruction accuracy and real replay on the final surface.
