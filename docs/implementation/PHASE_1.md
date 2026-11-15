> Historical phase record. Current hardware/build instructions and verification status:
> [stabilization](STABILIZATION.md) and [Mac runbook](../MAC_HARDWARE_SETUP.md).

# Phase 1 — physical core

Base: integrated main b33facb. Baseline: 42 backend / 6 frontend tests, build and typecheck passed.
Software validation: 49 backend / 8 frontend tests passed during core development.

Implemented repository-backed library metadata, strict distances/finite poses, scan-ID review,
start freshness, duplicate serialization, tracking-gap stop, global STOP, shared camera role
ownership/preview/calibration, asynchronous scanning and attempt persistence, firmware wiring
build gate and pinned PlatformIO build. Existing routes/simulator/renderer remain.

## Run

- Simulator: existing README commands.
- Hardware: install requirements-vision.txt; set GRASSROOT_ROBOT=esp32,
  GRASSROOT_CARDS=opencv, GRASSROOT_TRACKER=camera, GRASSROOT_CARD_CAMERA=0.
- In Setup select Scan camera, scan/review in Program, return camera to arena, select Arena
  tracking, show all markers, Validate camera calibration, confirm starting pose and Run.
- Calibration is revalidated after every role change/restart; the calibration record includes
  device index, resolution, geometry and generation. Corner displacement invalidates it.

## Firmware

From repository root: `PLATFORMIO_CORE_DIR=$PWD/work/platformio backend/.venv/bin/pio run -d firmware -e robot`.
Install platformio==6.1.18 separately for building. `pio run -d firmware -e robot -t upload`
flashes through USB-C (not performed). Robot retains existing Wi-Fi AP/WebSocket transport.
No credentials changed. Never flash until actual board/wiring/power are verified.
`GRASSROOT_WIRING_VERIFIED=0` is the default. Only set it to 1 in platformio.ini after checking
GPIOs and per-wheel polarity on supported hardware. MOTOR_POLARITY order: LF, RF, LR, RR.
Measure MS_PER_CELL/MS_PER_90 and duty on the actual surface; these are not validated constants.
SLP remains tied to 3V3 in the proposed wiring; there is no SLP GPIO.

## Physical acceptance — all PENDING

- [ ] Board/power/current limits, wiring, polarity and wheel orientation verified by teammate.
- [ ] Individual wheels, forward/backward and in-place 90-degree turns measured.
- [ ] Explicit STOP, malformed command, watchdog and Wi-Fi loss stop actual motors.
- [ ] Duplicate command does not move twice; reconnect does not replay.
- [ ] One webcam handoff/reposition/calibration, parallax and lighting tested.
- [ ] Correct/wrong-then-recover/revisit runs graded from real observations.
- [ ] Boundary and tracking loss stop verified physically.
- [ ] Projector alignment/size warning/marker masks/readability verified physically.

No physical test, firmware upload, or OCR accuracy claim is made by these software results.
A blocking native camera driver can delay acquisition teardown; STOP does not wait on it.
