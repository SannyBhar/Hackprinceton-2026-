#pragma once

// Confirmed Seeed Studio XIAO ESP32-S3 / two Adafruit DRV8833 pin map.
// Raw ESP32 GPIO numbers, NOT XIAO D-label numbers. Physical wiring unverified.
// Active only in explicit calibration/run profiles. Default outputs remain disabled.
namespace grassroot_hardware {
constexpr int LF_IN1 = 1;   // D0 -> driver 1 AIN1
constexpr int LF_IN2 = 2;   // D1 -> driver 1 AIN2
constexpr int LR_IN1 = 3;   // D2 -> driver 1 BIN1
constexpr int LR_IN2 = 4;   // D3 -> driver 1 BIN2
constexpr int RF_IN1 = 5;   // D4 -> driver 2 AIN1
constexpr int RF_IN2 = 6;   // D5 -> driver 2 AIN2
constexpr int RR_IN1 = 43;  // D6 -> driver 2 BIN1 (NOT GPIO6)
constexpr int RR_IN2 = 44;  // D7 -> driver 2 BIN2 (NOT GPIO7)
// No SLP GPIO: both driver SLP pins are wired directly to 3V3 in the confirmed pin map.
}  // namespace grassroot_hardware
