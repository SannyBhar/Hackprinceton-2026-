// Grassroot XIAO ESP32-S3 robot. Disabled by default; measured run profile required.
// Legacy AP and source paths are retained for compatibility.
#include <WiFi.h>
#include <WebSocketsServer.h>
#include <ArduinoJson.h>
#include "hardware_pins.h"
#ifndef GRASSROOT_HARDWARE_MODE
#define GRASSROOT_HARDWARE_MODE 0
#endif
#include "../network_config.h"

WebSocketsServer ws(81);

// Confirmed raw GPIO pairs; SLP pins tied to 3V3.
// Order: front-left, front-right, rear-left, rear-right. Each motor uses IN1/IN2 PWM.
#if GRASSROOT_HARDWARE_MODE != 0
using namespace grassroot_hardware;
const int MOTOR_IN1[4] = {LF_IN1, RF_IN1, LR_IN1, RR_IN1};
const int MOTOR_IN2[4] = {LF_IN2, RF_IN2, LR_IN2, RR_IN2};
#else
const int MOTOR_IN1[4] = {-1, -1, -1, -1};
const int MOTOR_IN2[4] = {-1, -1, -1, -1};
#endif
// Calibration pulses use raw polarity; normal control uses measured LF/RF/LR/RR values.
#if GRASSROOT_HARDWARE_MODE == 2
const int MOTOR_POLARITY[4] = {PROFILE_POLARITY_0, PROFILE_POLARITY_1, PROFILE_POLARITY_2, PROFILE_POLARITY_3};
const uint32_t MS_PER_CELL = PROFILE_MS_CELL, MS_PER_90 = PROFILE_MS_90;
const int DRIVE_DUTY = PROFILE_DRIVE_DUTY, TURN_DUTY = PROFILE_TURN_DUTY;
#else
const int MOTOR_POLARITY[4] = {1,1,1,1};
const uint32_t MS_PER_CELL = 0, MS_PER_90 = 0;
const int DRIVE_DUTY = 0, TURN_DUTY = 0;
#define PROFILE_ID "unmeasured"
#endif
const uint32_t MAX_COMMAND_MS = 8000;       // hard bound for any single command
const uint32_t HEARTBEAT_TIMEOUT_MS = 1000;

// ---------- state ----------
struct Motion { bool active; uint32_t endAt; String msgId; uint8_t client; };
Motion motion = {false, 0, "", 0};
uint32_t lastHeartbeat = 0;
String recentIds[128]; int recentCount = 0;
int controlClient = -1;

bool seen(const String& id) { for (auto& s : recentIds) if (s == id) return true; return false; }
bool remember(const String& id) { if (recentCount >= 128) return false; recentIds[recentCount++] = id; return true; }

void setMotor(int i, int duty) {   // duty -255..255
  if (MOTOR_IN1[i] < 0) return;    // pins not configured: refuse to drive
  duty = constrain(duty * MOTOR_POLARITY[i], -200, 200);
  int a = duty > 0 ? duty : 0, b = duty < 0 ? -duty : 0;
  analogWrite(MOTOR_IN1[i], a);
  analogWrite(MOTOR_IN2[i], b);
}
void drive(int left, int right) { setMotor(0, left); setMotor(2, left); setMotor(1, right); setMotor(3, right); }
void motorsOff() { drive(0, 0); }

void sendAck(uint8_t client, const String& msgId, const char* status, const char* err = nullptr) {
  JsonDocument d; d["type"] = "ack"; d["msgId"] = msgId; d["status"] = status;
  if (err) d["error"] = err;
  d["remainingCommands"] = 128-recentCount;
  String out; serializeJson(d, out); ws.sendTXT(client, out);
}

void finishMotion(const char* status, const char* reason = nullptr) {
  motorsOff();
  if (motion.active) sendAck(motion.client, motion.msgId, status, reason);
  motion.active = false;
}

void handleCmd(uint8_t client, JsonDocument& d) {
  String msgId = d["msgId"] | "";
  String kind = d["kind"] | "";
  int value = d["value"] | 0;
  if (kind == "STOP") { finishMotion("STOPPED","explicit host stop"); sendAck(client, msgId, "DONE"); return; }
  if (!d["value"].is<int>()) { finishMotion("STOPPED"); sendAck(client,msgId,"ERROR","value must be an integer"); return; }
  if (msgId.length() == 0 || msgId.length() > 64) {
    finishMotion("STOPPED"); sendAck(client, msgId, "ERROR", "invalid msgId"); return;
  }
  if (GRASSROOT_HARDWARE_MODE != 2) {
    sendAck(client, msgId, "ERROR", "calibrated run profile required"); return;
  }
  if (seen(msgId)) { sendAck(client, msgId, "DUPLICATE"); return; }
  if (motion.active) { sendAck(client, msgId, "ERROR", "busy"); return; }
  if ((kind == "MOVE" && (value == 0 || abs(value) > 5)) ||
      (kind == "TURN" && value != 90 && value != -90) ||
      (kind != "MOVE" && kind != "TURN")) {
    finishMotion("STOPPED"); sendAck(client, msgId, "ERROR", "invalid primitive"); return;
  }
  uint32_t planned = kind == "MOVE" ? (uint32_t)(abs(value) * MS_PER_CELL) : (uint32_t)MS_PER_90;
  if (planned > MAX_COMMAND_MS) { sendAck(client, msgId, "ERROR", "duration exceeds bound"); return; }
  if (!remember(msgId)) { sendAck(client,msgId,"ERROR","id ledger full; power-cycle only while stopped"); return; }
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

bool continuousActive = false;
uint32_t driveExpires = 0;
int driveClient = -1;
int64_t driveSeq = -1;
void handleDrive(uint8_t client, JsonDocument& d) {
  String id = d["msgId"] | "";
  int ttl = d["ttlMs"] | 0;
  float linear = d["linear"] | 0.0f, angular = d["angular"] | 0.0f;
  int64_t seq = d["seq"] | (int64_t)-1;
  if (GRASSROOT_HARDWARE_MODE != 2 || d["protocolVersion"] != 2 || ttl < 1 || ttl > 250 ||
      !isfinite(linear) || !isfinite(angular) || abs(linear)>1 || abs(angular)>1 ||
      (linear != 0 && angular != 0) || motion.active || (continuousActive && driveClient != client)) {
    continuousActive=false; motorsOff(); sendAck(client,id,"ERROR","invalid drive or unavailable control"); return;
  }
  if (seq <= driveSeq) { sendAck(client,id,"DUPLICATE"); return; }
  driveSeq=seq; driveClient=client;
  int left=(int)(linear*DRIVE_DUTY+angular*TURN_DUTY), right=(int)(linear*DRIVE_DUTY-angular*TURN_DUTY);
  drive(left,right); continuousActive=true; driveExpires=millis()+ttl;
  sendAck(client,id,"DONE");
}

// Instructor-only bounded one-shot pulse/trial; never a student command.
void handleCalibration(uint8_t client, JsonDocument& d) {
  String id=d["msgId"] | "", action=d["action"] | "";
  int duration=d["durationMs"] | 100, duty=d["duty"] | 0;
  if (GRASSROOT_HARDWARE_MODE!=1 || motion.active || continuousActive || id.length()==0 || id.length()>64 ||
      !d["durationMs"].is<int>() || !d["duty"].is<int>() || duration<1 || duration>250 || duty==0 || abs(duty)>200) {
    sendAck(client,id,"ERROR","invalid calibration pulse or calibration profile required"); return;
  }
  if (seen(id)) { sendAck(client,id,"DUPLICATE"); return; }
  if (action=="wheel") {
    int wheel=d["wheel"] | -1;
    if (!d["wheel"].is<int>() || wheel<0 || wheel>3) { sendAck(client,id,"ERROR","invalid wheel"); return; }
    if (!remember(id)) { sendAck(client,id,"ERROR","ledger full"); return; }
    motorsOff(); setMotor(wheel,duty);
  } else if (action=="translation" || action=="turn") {
    for (int i=0;i<4;i++) {
      if (!d["polarity"][i].is<int>() || abs(d["polarity"][i].as<int>())!=1) { sendAck(client,id,"ERROR","measure all wheel polarities first"); return; }
    }
    if (!remember(id)) { sendAck(client,id,"ERROR","ledger full"); return; }
    for (int i=0;i<4;i++) setMotor(i,duty*d["polarity"][i].as<int>()*(action=="turn" && (i==1 || i==3) ? -1 : 1));
  } else { sendAck(client,id,"ERROR","invalid calibration action"); return; }
  motion={true,millis()+(uint32_t)duration,id,client};
  sendAck(client,id,"ACCEPTED");
}

void onWs(uint8_t client, WStype_t type, uint8_t* payload, size_t len) {
  if (type == WStype_CONNECTED) {
    if (controlClient >= 0 && controlClient != client) { ws.disconnect(client); return; }
    controlClient = client;
    // Starting a new control connection never resumes movement.
    finishMotion("STOPPED"); continuousActive=false; driveSeq=-1;
    JsonDocument hello;
    hello["type"]="hello"; hello["protocolVersion"]=2;
    hello["outputsEnabled"]=GRASSROOT_HARDWARE_MODE!=0;
    hello["calibrated"]=GRASSROOT_HARDWARE_MODE==2;
    hello["mode"]=GRASSROOT_HARDWARE_MODE==2 ? "run" : GRASSROOT_HARDWARE_MODE==1 ? "calibration" : "disabled";
    hello["profileId"]=PROFILE_ID; hello["remainingCommands"]=128-recentCount;
    String out; serializeJson(hello,out); ws.sendTXT(client,out); return;
  }
  if (type == WStype_DISCONNECTED) { if (client==controlClient) { finishMotion("STOPPED"); continuousActive=false; controlClient=-1; } return; }
  if (type != WStype_TEXT) return;
  if (len > 4096) { finishMotion("STOPPED"); continuousActive=false; return; }
  JsonDocument d;
  if (deserializeJson(d, payload, len)) { finishMotion("STOPPED"); continuousActive=false; return; }
  String t = d["type"] | "";
  if (client != controlClient) return;
  if (t == "hb") lastHeartbeat = millis();
  else if (t == "calibration") { lastHeartbeat=millis(); handleCalibration(client,d); }
  else if (t == "drive") { lastHeartbeat = millis(); handleDrive(client,d); }
  else if (t == "cmd") {
    if (String(d["kind"] | "") == "STOP") continuousActive=false;
    else if (continuousActive) { sendAck(client,d["msgId"] | "","ERROR","continuous control active"); return; }
    lastHeartbeat = millis(); handleCmd(client, d);
  }
  else { finishMotion("STOPPED"); continuousActive=false; }
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 4; i++) {
    if (MOTOR_IN1[i] >= 0) { pinMode(MOTOR_IN1[i], OUTPUT); pinMode(MOTOR_IN2[i], OUTPUT); }
  }
  motorsOff();
  grassrootNetworkStart(true);
  Serial.println("Robot WebSocket port 81; waiting for network address");
  ws.begin();
  ws.onEvent(onWs);
}

void loop() {
  ws.loop();
  static String printedAddress;
  String address=grassrootNetworkAddress().toString();
  if (address!="0.0.0.0" && address!=printedAddress) {
    Serial.printf("Robot address %s, WebSocket port 81\n",address.c_str()); printedAddress=address;
  }
  uint32_t now = millis();
  if (continuousActive && ((int32_t)(now-driveExpires)>=0 || now-lastHeartbeat>HEARTBEAT_TIMEOUT_MS)) { motorsOff(); continuousActive=false; }
  if (motion.active && (int32_t)(now - motion.endAt) >= 0) finishMotion("DONE");
  if (motion.active && now - lastHeartbeat > HEARTBEAT_TIMEOUT_MS) {
    Serial.println("heartbeat lost -> STOP");
    finishMotion("STOPPED","heartbeat watchdog expired");
  }
}
