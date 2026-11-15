# Grassroot — proposed XIAO ESP32-S3 motor pins

Source: supplied `esp32_motor_wiring_codex.md`. This is a proposed configuration,
not verification of the physical wiring. This change records pins only. The source's
requests for motor integration, USB bridging and pivot-turn behavior are **not applied**.

Reference constants: `firmware/esp32/codeanywhere/hardware_pins.h`.
The sketch's active `MOTOR_IN1` and `MOTOR_IN2` arrays remain `{-1, -1, -1, -1}`;
the header is intentionally not included or used to enable outputs. No upload is
required for this reference-only change.

| Position | Driver/channel | IN1: XIAO / GPIO | IN2: XIAO / GPIO | Motor output pair |
| --- | --- | --- | --- | --- |
| Left front (LF) | 1 / A | D0 / GPIO1 | D1 / GPIO2 | AOUT1, AOUT2 |
| Left rear (LR) | 1 / B | D2 / GPIO3 | D3 / GPIO4 | BOUT1, BOUT2 |
| Right front (RF) | 2 / A | D4 / GPIO5 | D5 / GPIO6 | AOUT1, AOUT2 |
| Right rear (RR) | 2 / B | D6 / GPIO43 | D7 / GPIO44 | BOUT1, BOUT2 |

D6 and D7 refer to GPIO43 and GPIO44, not GPIO6 and GPIO7.
The existing sketch orders motors **LF, RF, LR, RR**, unlike the table's **LF, LR, RF, RR**.
If integration is authorized later, its proposed arrays in sketch order would be
IN1 `{1, 5, 3, 43}` and IN2 `{2, 6, 4, 44}`. They are not activated here.

## Other connections from the supplied proposal

- Both SLP pins connect directly to XIAO 3V3; no software SLP pin is assigned.
- External motor supply positive connects to VM on both drivers; supply negative,
  both driver grounds and XIAO ground share common ground.
- XIAO is powered separately through USB-C; motor outputs connect only to their
  designated driver output pairs. Motor supply rating/current and polarity remain unverified.
- FLT remains unconnected; AS/BS retain breakout defaults.

## Scope and verification

No changes to motor direction, existing in-place turns, PWM, timing, watchdog, STOP,
command IDs, WebSocket transport, network credentials, backend, simulator or frontend.
No new Wait command, serial bridge or motor test functionality. Verify actual wiring,
motor supply, per-motor polarity and board package before any future activation.
See [hardware checklist](HARDWARE_CHECKLIST.md). No hardware was flashed or tested.

The standalone pin header was checked with the host C++ compiler; the sketch was
compared against its base with comments removed to confirm executable text is unchanged.
A complete Arduino build was not performed (board toolchain/libraries not configured).
