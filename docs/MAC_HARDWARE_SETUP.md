# Local Mac setup and measured hardware acceptance

This is the physical host workflow. Codespaces is suitable for UI/simulator work, but cannot
access the Mac's USB devices or webcam. No physical measurements below have been completed.

## Install and run

Use Python **3.13** (`brew install python@3.13`) and Node **24.4.1** (`nvm install && nvm use`).
The pinned pydantic-core does not support Python 3.14; recreate an incorrectly created venv
rather than bypassing PyO3 checks. Preserve any private files before replacing a venv.
From the repository root:

```bash
./scripts/setup-mac.sh vision joystick firmware
npm --prefix frontend run build
./scripts/run-local.sh
```

Optional `ocr` installs real local TrOCR and `ai` installs image validation dependencies.
For development use `./dev.sh` after exporting settings; for the built UI use the local runner
and open http://127.0.0.1:8000. The runner loads your own ignored root `.env` shell assignments.
Keep credentials out of Vite variables, screenshots, logs, commits and PRs.

Example root `.env` (no credentials):

```bash
GRASSROOT_ROBOT=esp32
GRASSROOT_ROBOT_URL=ws://ROBOT_IP:81/
GRASSROOT_CARDS=opencv
GRASSROOT_TRACKER=camera
GRASSROOT_CAMERA=0
GRASSROOT_JOYSTICK_PORT=/dev/cu.usbmodem_YOUR_JOYSTICK
# Optional later: GRASSROOT_OCR=local, GEMINI_API_KEY (private value only)
```

Use `ls /dev/cu.usb*` to identify each board. macOS Camera permission must be granted to the
terminal/app running the backend (start it from Terminal.app). Use the webcam in Scan mode for
cards, close it, then start the Overhead camera in Setup and calibrate from the projection (no
markers needed; see CAMERA_SETUP.md). Recalibrate after moving the camera or projector.

## Wi-Fi on both XIAOs

Both boards join the existing **EeroBuddy** network in station mode. A local credential header
has been configured for this checkout only: `firmware/esp32/network.local.h` (ignored, mode 600).
The robot WebSocket remains on port 81. Read its assigned IP from the robot USB serial monitor
or the router device list and set `GRASSROOT_ROBOT_URL` accordingly. The Mac must join the same
LAN. Disable client isolation if it prevents the Mac from reaching the robot. No ESP-NOW is used.
The joystick still requires USB serial; its Wi-Fi connection does not carry robot commands.

On another checkout, create the ignored header privately with these macros (supply your own
values; no credentials are stored in this document):

```cpp
#pragma once
#define GRASSROOT_WIFI_STATION 1
#define GRASSROOT_WIFI_SSID "YOUR_NETWORK"
#define GRASSROOT_WIFI_PASSWORD "YOUR_PRIVATE_PASSWORD"
```

Both builds consume the same header. Without it the robot retains its legacy AP configuration
and the joystick has no Wi-Fi connection. Station failure does not start a fallback AP or replay
motion. Wi-Fi reconnect is automatic; physical disconnect/watchdog behavior still needs testing.
Built firmware contains local credentials; keep `.pio` output private as well.

## Verify power before calibration

- Both controllers: Seeed Studio XIAO ESP32-S3. Robot GPIO pairs LF 1/2, LR 3/4, RF 5/6, RR 43/44.
- Both driver SLP pins to 3V3; common ground; motor power separate from USB controller power.
- Joystick: X GPIO1, Y GPIO2, button GPIO3 with pull-up, VCC 3V3.
- Motor supply reported **6 V**. Confirm the motor's rated voltage, startup/stall current and
  driver capacity before energizing. A belief that the rating is 6 V is not verification.
- Physical grid cell: **22 cm**. Wheel polarity and movement timings are unmeasured.

## Calibration and firmware profiles

Install PlatformIO 6.1.18 in the backend venv (the setup script's `firmware` option does this).
Use `backend/.venv/bin/pio` from the repository root:

```bash
backend/.venv/bin/pio run -d firmware -e robot -e joystick
```

`robot` has disabled motor outputs. `joystick` builds the confirmed XIAO target/protocol v2.
Hold the stick neutral and button released at boot while centres are sampled. The host flushes
serial input, challenges the new lease, checks boot identity/sequence/device timestamps, and
requires neutral/released input before rearming. Old firmware is rejected with a compatibility error.

1. Copy `hardware/profile.example.json` to ignored root `hardware.local.json`. This is the single
   source for measured values, in **LF, RF, LR, RR** order. Set `wiringVerified` and
   `motorRatingVerified` true only after inspecting wiring and checking the motor specification.
2. Build and explicitly upload the calibration target through the robot's USB-C port:

   ```bash
   backend/.venv/bin/pio run -d firmware -e robot-calibration
   backend/.venv/bin/pio run -d firmware -e robot-calibration -t upload --upload-port /dev/cu.ROBOT_PORT
   backend/.venv/bin/pio run -d firmware -e joystick -t upload --upload-port /dev/cu.JOYSTICK_PORT
   ```

3. Use Setup → Instructor calibration. Lift wheels clear first. Select one wheel, signed duty
   and a one-shot duration (default **100 ms**, hard maximum **250 ms**). Confirm each pulse
   separately. STOP remains available while the pulse request is pending; heartbeat/watchdog
   and the duration bound independently stop output. No retries or repeats occur automatically.
4. Record each wheel's polarity as `1` or `-1` so positive corrected duty means forward.
   Save all four values before translation/turn trials. Then put the robot on the test floor,
   explicitly request bounded trials at selected duties, and measure displacement/rotation.
   Fit and verify `msPerCell`, `msPer90`, `driveDuty`, `turnDuty` against 22 cm and in-place 90°
   turns. Short pulses may include startup friction; verify fitted values with actual runs and
   adjust from measurements. Do not treat duty defaults or guessed durations as measured data.
5. Save the measured values and set `acknowledged:true`. Build the measured run profile:

   ```bash
   backend/.venv/bin/pio run -d firmware -e robot-calibrated
   backend/.venv/bin/pio run -d firmware -e robot-calibrated -t upload --upload-port /dev/cu.ROBOT_PORT
   ```

   This target refuses missing/unverified values. The backend compares firmware and local profile
   hashes; changed measurements require a rebuild/reflash. Never upload a synthetic build-test profile.
   `GRASSROOT_HARDWARE_PROFILE` can point both build and backend at the same alternate private file.
6. Reconnect, calibrate the overhead camera and confirm a fresh start pose. “Connected” alone is insufficient;
   Setup must show calibrated readiness. Normal program/recording movement is blocked until then.
   Commands remain bounded by 8 s, continuous drives by 250 ms, input freshness by 300 ms,
   and firmware heartbeat by 1 s. A 5-cell command can exceed the duration bound with some measured
   profiles; split the reviewed program into shorter commands rather than increasing the hard bound.

The 128-command ID ledger does not evict IDs. Snapshots/acks show remaining capacity and Run
preflights the required slots. Power-cycle only while stopped when capacity is insufficient;
reconnect alone does not reset the ledger. Calibration pulses consume slots too.

## Physical completion checklist (all pending)

- [ ] Verify motor specifications, supply, driver limits, wiring and common ground.
- [ ] Flash both XIAOs, confirm LAN reachability, USB joystick protocol and neutral rearming.
- [ ] Measure each polarity, translation and in-place turn; save/acknowledge/reflash measured profile.
- [ ] Cards → reviewed program → robot → ordered observed grading → synchronized projection → history.
- [ ] Wrong-then-correct entries, revisits and incomplete/extra grading remain correct.
- [ ] Joystick → raw recording → reviewed approximate reconstruction → validated replay → history.
- [ ] Physical STOP during program/continuous/calibration, neutral, second button, disconnect,
      heartbeat/expiry, tracking loss and boundary stops; reconnect never replays motion.
- [ ] Projector alignment, dark marker regions, camera placement/parallax and real-card OCR benchmark.

Live Nano Banana acceptance is deliberately deferred until the robot works without themes.
Static themes, simulation, fixture scans, synthetic histories and offline cached artwork remain available.
The optional later check is `PYTHONPATH=backend backend/.venv/bin/python tools/check_theme_live.py`
with a privately configured key; it makes one live request in isolated temporary simulator storage.
