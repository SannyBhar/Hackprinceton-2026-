// XIAO ESP32-S3 USB joystick protocol v2. Release/centre the stick at boot.
#include <Arduino.h>
#include <ArduinoJson.h>
#include "../network_config.h"
#ifndef JOYSTICK_X_PIN
#define JOYSTICK_X_PIN -1
#endif
#ifndef JOYSTICK_Y_PIN
#define JOYSTICK_Y_PIN -1
#endif
#ifndef JOYSTICK_BUTTON_PIN
#define JOYSTICK_BUTTON_PIN -1
#endif
String bootId, syncId;
uint32_t syncTimestamp = 0;
String inputLine;
uint32_t sampleSeq = 0, lastSample = 0, buttonChanged = 0;
int centreX = 2048, centreY = 2048;
bool previousRaw = false, button = false;
const bool configured = JOYSTICK_X_PIN >= 0 && JOYSTICK_Y_PIN >= 0 && JOYSTICK_BUTTON_PIN >= 0;
float axis(int raw, int centre) {
  float v = (raw-centre)/(float)(raw >= centre ? max(1,4095-centre) : max(1,centre));
  return constrain(v,-1.0f,1.0f);
}
void setup() {
  Serial.begin(115200);
  grassrootNetworkStart(false);
  bootId=String(esp_random(),HEX)+String(esp_random(),HEX);
  if (!configured) return;
  analogReadResolution(12);
  pinMode(JOYSTICK_BUTTON_PIN, INPUT_PULLUP);
  long x=0,y=0;
  for (int i=0;i<128;i++) { x+=analogRead(JOYSTICK_X_PIN); y+=analogRead(JOYSTICK_Y_PIN); delay(2); }
  centreX=x/128; centreY=y/128;
}
void loop() {
  if (!configured) { delay(1000); Serial.println("{\"error\":\"joystick pins unconfigured\"}"); return; }
  while (Serial.available()) {
    char c=Serial.read();
    if (c=='\n') {
      JsonDocument request;
      if (!deserializeJson(request,inputLine) && request["type"]=="sync" && request["protocolVersion"]==2) {
        syncId=String(request["syncId"] | "");
        syncTimestamp=millis();
      }
      inputLine="";
    } else if (inputLine.length()<256) inputLine+=c;
    else { inputLine=""; syncId=""; }
  }
  if (syncId.length()==0) return;
  uint32_t now=millis();
  bool raw=digitalRead(JOYSTICK_BUTTON_PIN)==LOW;
  if (raw!=previousRaw) { previousRaw=raw; buttonChanged=now; }
  if (now-buttonChanged>=40) button=raw;
  if (now-lastSample<50) return;
  lastSample=now;
  JsonDocument d;
  d["protocolVersion"]=2; d["bootId"]=bootId; d["syncId"]=syncId; d["syncTimestampMs"]=syncTimestamp; d["seq"]=sampleSeq++; d["timestampMs"]=now;
  d["x"]=axis(analogRead(JOYSTICK_X_PIN),centreX);
  d["y"]=axis(analogRead(JOYSTICK_Y_PIN),centreY);
  d["button"]=button;
  d["wifiConnected"]=WiFi.status()==WL_CONNECTED;
  d["wifiAddress"]=grassrootNetworkAddress().toString();
  serializeJson(d,Serial); Serial.println();
}
