# Hardware & calibration checklist (manual)

Tick items only when actually performed. Do not report unperformed tests as passed.

Confirmed XIAO ESP32-S3 pin assignment: [motor wiring reference](ESP32_MOTOR_WIRING.md).
Constants are recorded in `firmware/esp32/codeanywhere/hardware_pins.h`; active
firmware outputs remain disabled by default. Use explicit calibration/run profiles in the
[Mac hardware runbook](MAC_HARDWARE_SETUP.md); physical acceptance below remains pending.

## Before wiring (ME-1)
- [ ] Exact motor model, rated voltage, no-load and **stall** current measured/confirmed
- [ ] Stall current within DRV8833 limits (≈1.5 A RMS / 2 A peak per channel) — else choose another driver
- [ ] 4 motors independently controllable (2× DRV8833 = 4 H-bridges)
- [ ] Battery voltage/capacity chosen; regulator for ESP32 3.3 V/5 V; **common ground**
- [ ] Motor power never routed through ESP32 pins; GPIO list checked against `hardware_pins.h`
- [ ] Fuse / power switch reachable

## Firmware bring-up
- [ ] Each motor spins the correct direction at low duty (record LF/RF/LR/RR polarity in the private hardware profile)
- [ ] `msPerCell` and `msPer90` measured on the real board surface (3 trials each), saved and acknowledged
- [ ] STOP during a move halts within ~100 ms
- [ ] Laptop disconnect / Wi-Fi off → motors stop within 1 s (watchdog)
- [ ] Same `msgId` sent twice → second returns DUPLICATE, no motion
- [ ] Command longer than 8 s is rejected before motion

## Vision
- [ ] Corner markers 0–3 detected in all lighting conditions with projector ON
- [ ] Robot marker detected anywhere on the board, incl. corners
- [ ] Pose error measured at 4 corners + centre (target < 0.15 cell); `height_correction` set
- [ ] Hand-pushed robot: exactly one entry per cell, revisits counted, no boundary jitter duplicates
- [ ] Card camera reads a 7-card row; numeric crops legible

## Projection
- [ ] Projector fixed; board inside projected footprint with margin
- [ ] Four-corner calibration aligned within ~1 cm at corners and centre (test pattern)
- [ ] Calibration survives page refresh and backend restart
- [ ] Green/red + ✓/✗ readable under room lighting from a child's eye height
- [ ] Corner dark zones keep markers readable

## End-to-end
- [ ] Correct program: all green, SUCCESS
- [ ] Wrong program: robot continues, later same-index match turns green
- [ ] Boundary approach → BOUNDARY stop; occlude marker → TRACKING_LOST stop
- [ ] Joystick recording generates the expected blocks; generated program replays the route
