#pragma once
#include <WiFi.h>
// Private credentials are shared by both builds and deliberately excluded from Git.
#if __has_include("network.local.h")
#include "network.local.h"
#endif
#ifndef GRASSROOT_WIFI_STATION
#define GRASSROOT_WIFI_STATION 0
#endif
#ifndef GRASSROOT_AP_SSID
#define GRASSROOT_AP_SSID "codeanywhere-robot"
#endif
#ifndef GRASSROOT_AP_PASS
#define GRASSROOT_AP_PASS "change-me-please"
#endif

inline void grassrootNetworkStart(bool robot) {
#if GRASSROOT_WIFI_STATION
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(GRASSROOT_WIFI_SSID, GRASSROOT_WIFI_PASSWORD);
#else
  // Existing AP configuration is retained when no local station configuration exists.
  if (robot) { WiFi.mode(WIFI_AP); WiFi.softAP(GRASSROOT_AP_SSID,GRASSROOT_AP_PASS); }
#endif
}

inline IPAddress grassrootNetworkAddress() {
#if GRASSROOT_WIFI_STATION
  return WiFi.localIP();
#else
  return WiFi.softAPIP();
#endif
}
