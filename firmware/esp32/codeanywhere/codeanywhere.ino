// CodeAnywhere robot firmware (ESP32, Arduino framework) — UNVERIFIED SCAFFOLD.
//
// Libraries: "WebSockets" by Markus Sattler (arduinoWebSockets), "ArduinoJson" v7.
// Protocol: see backend/app/robot/esp32_ws.py.
//
// Safety properties this sketch must keep:
//  * Every motion has a bounded duration (open-loop timing until encoders/camera close the loop).
//  * Explicit STOP preempts any motion immediately.
//  * Heartbeat watchdog: no "hb" frame for HEARTBEAT_TIMEOUT_MS -> motors off.
//  * A msgId seen before is acknowledged as DUPLICATE and never re-executed.
//
// !!! GPIO pins and motor parameters below are PLACEHOLDERS. Do not wire to these numbers until
// !!! the team confirms the chassis motor voltage/stall current vs. DRV8833 limits (1.5A/ch RMS),
// !!! power regulation, common ground, and pin assignment. See docs/HARDWARE_CHECKLIST.md.

#include <WiFi.h>
#include <WebSocketsServer.h>
#include <ArduinoJson.h>

// ---------- network (ESP32 runs its own access point; laptop joins it) ----------
const char* AP_SSID = "codeanywhere-robot";
const char* AP_PASS = "change-me-please";   // >= 8 chars
WebSocketsServer ws(81);

// ---------- motor driver pins: TODO confirm (two DRV8833 = 4 H-bridges) ----------
// Order: front-left, front-right, rear-left, rear-right. Each motor uses IN1/IN2 PWM.
const int MOTOR_IN1[4] = {-1, -1, -1, -1};  // TODO
const int MOTOR_IN2[4] = {-1, -1, -1, -1};  // TODO
const int PWM_FREQ = 20000, PWM_BITS = 8;

// ---------- movement calibration (measure on the real board!) ----------
float MS_PER_CELL = 1400;     // TODO calibrate: time to travel one cell at DRIVE_DUTY
float MS_PER_90 = 650;        // TODO calibrate: time for an in-place 90° turn at TURN_DUTY
int DRIVE_DUTY = 170, TURN_DUTY = 160;
const uint32_t MAX_COMMAND_MS = 8000;       // hard bound for any single command
const uint32_t HEARTBEAT_TIMEOUT_MS = 1000;

// ---------- state ----------
struct Motion { bool active; uint32_t endAt; String msgId; uint8_t client; };
Motion motion = {false, 0, "", 0};
uint32_t lastHeartbeat = 0;
String recentIds[16]; int recentHead = 0;

bool seen(const String& id) { for (auto& s : recentIds) if (s == id) return true; return false; }
void remember(const String& id) { recentIds[recentHead] = id; recentHead = (recentHead + 1) % 16; }

void setMotor(int i, int duty) {   // duty -255..255
  if (MOTOR_IN1[i] < 0) return;    // pins not configured: refuse to drive
  int a = duty > 0 ? duty : 0, b = duty < 0 ? -duty : 0;
  analogWrite(MOTOR_IN1[i], a);
  analogWrite(MOTOR_IN2[i], b);
}
void drive(int left, int right) { setMotor(0, left); setMotor(2, left); setMotor(1, right); setMotor(3, right); }
void motorsOff() { drive(0, 0); }

void sendAck(uint8_t client, const String& msgId, const char* status, const char* err = nullptr) {
  JsonDocument d; d["type"] = "ack"; d["msgId"] = msgId; d["status"] = status;
  if (err) d["error"] = err;
  String out; serializeJson(d, out); ws.sendTXT(client, out);
}

void finishMotion(const char* status) {
  motorsOff();
  if (motion.active) sendAck(motion.client, motion.msgId, status);
  motion.active = false;
}

void handleCmd(uint8_t client, JsonDocument& d) {
  String msgId = d["msgId"] | "";
  String kind = d["kind"] | "";
  int value = d["value"] | 0;
  if (kind == "STOP") { finishMotion("STOPPED"); sendAck(client, msgId, "DONE"); return; }
  if (seen(msgId)) { sendAck(client, msgId, "DUPLICATE"); return; }
  remember(msgId);
  if (motion.active) { sendAck(client, msgId, "ERROR", "busy"); return; }
  uint32_t dur;
  if (kind == "MOVE") {
    dur = (uint32_t)(abs(value) * MS_PER_CELL);
    int s = value > 0 ? DRIVE_DUTY : -DRIVE_DUTY; drive(s, s);
  } else if (kind == "TURN") {
    dur = (uint32_t)(abs(value) / 90.0 * MS_PER_90);
    int s = value > 0 ? TURN_DUTY : -TURN_DUTY; drive(s, -s);   // +value = right/clockwise
  } else { sendAck(client, msgId, "ERROR", "unknown kind"); return; }
  if (dur > MAX_COMMAND_MS) dur = MAX_COMMAND_MS;
  motion = {true, millis() + dur, msgId, client};
  sendAck(client, msgId, "ACCEPTED");
}

void onWs(uint8_t client, WStype_t type, uint8_t* payload, size_t len) {
  if (type == WStype_DISCONNECTED) { finishMotion("STOPPED"); return; }
  if (type != WStype_TEXT) return;
  JsonDocument d;
  if (deserializeJson(d, payload, len)) return;
  String t = d["type"] | "";
  if (t == "hb") lastHeartbeat = millis();
  else if (t == "cmd") { lastHeartbeat = millis(); handleCmd(client, d); }
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 4; i++) {
    if (MOTOR_IN1[i] >= 0) { pinMode(MOTOR_IN1[i], OUTPUT); pinMode(MOTOR_IN2[i], OUTPUT); }
  }
  motorsOff();
  WiFi.softAP(AP_SSID, AP_PASS);
  Serial.printf("AP %s at %s, ws port 81\n", AP_SSID, WiFi.softAPIP().toString().c_str());
  ws.begin();
  ws.onEvent(onWs);
}

void loop() {
  ws.loop();
  uint32_t now = millis();
  if (motion.active && (int32_t)(now - motion.endAt) >= 0) finishMotion("DONE");
  if (motion.active && now - lastHeartbeat > HEARTBEAT_TIMEOUT_MS) {
    Serial.println("heartbeat lost -> STOP");
    finishMotion("STOPPED");
  }
}
