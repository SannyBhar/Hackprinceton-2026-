// Separate ESP32-S3 USB joystick. Pins intentionally UNASSIGNED until wiring commit.
#include <Arduino.h>
#include <ArduinoJson.h>
#ifndef JOYSTICK_X_PIN
#define JOYSTICK_X_PIN -1
#endif
#ifndef JOYSTICK_Y_PIN
#define JOYSTICK_Y_PIN -1
#endif
#ifndef JOYSTICK_BUTTON_PIN
#define JOYSTICK_BUTTON_PIN -1
#endif
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
  if (!configured) return;
  analogReadResolution(12);
  pinMode(JOYSTICK_BUTTON_PIN, INPUT_PULLUP);
  long x=0,y=0;
  for (int i=0;i<128;i++) { x+=analogRead(JOYSTICK_X_PIN); y+=analogRead(JOYSTICK_Y_PIN); delay(2); }
  centreX=x/128; centreY=y/128;
}
void loop() {
  if (!configured) { delay(1000); Serial.println("{\"error\":\"joystick pins unconfigured\"}"); return; }
  uint32_t now=millis();
  bool raw=digitalRead(JOYSTICK_BUTTON_PIN)==LOW;
  if (raw!=previousRaw) { previousRaw=raw; buttonChanged=now; }
  if (now-buttonChanged>=40) button=raw;
  if (now-lastSample<50) return;
  lastSample=now;
  JsonDocument d;
  d["protocolVersion"]=1; d["seq"]=sampleSeq++; d["timestampMs"]=now;
  d["x"]=axis(analogRead(JOYSTICK_X_PIN),centreX);
  d["y"]=axis(analogRead(JOYSTICK_Y_PIN),centreY);
  d["button"]=button;
  serializeJson(d,Serial); Serial.println();
}
