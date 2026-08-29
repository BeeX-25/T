/*
 * A two-dollar Wi-Fi IR blaster for SmartTV Bridge.
 *
 * When the phone has no IR LED, this is the cheapest way to make a closed
 * device (a satellite receiver, an old TV) programmable: an ESP8266 with
 * an IR LED on D2, answering the exact pulse trains the service sends.
 *
 * Wiring:  IR LED anode -> 100R resistor -> D2 (GPIO4), cathode -> GND.
 *          (For range, drive the LED through an NPN transistor instead.)
 *
 * Libraries: IRremoteESP8266 (Sketch > Include Library > Manage Libraries)
 *
 * Then in config.json:
 *   "ir": {
 *     "enabled": true,
 *     "brand": "your_brand",
 *     "transport": "http",
 *     "url": "http://192.168.1.9/ir?freq={frequency}&pattern={pattern}"
 *   }
 */

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <IRsend.h>

const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASSWORD = "YOUR_PASSWORD";
const uint16_t IR_LED_PIN = 4;  // D2
const uint16_t MAX_PULSES = 512;

ESP8266WebServer server(80);
IRsend irsend(IR_LED_PIN);
uint16_t pulses[MAX_PULSES];

// The service sends the pattern as microsecond durations: on,off,on,off...
uint16_t parsePattern(const String& text) {
  uint16_t count = 0;
  int start = 0;
  while (start < (int)text.length() && count < MAX_PULSES) {
    int comma = text.indexOf(',', start);
    if (comma < 0) comma = text.length();
    pulses[count++] = (uint16_t)text.substring(start, comma).toInt();
    start = comma + 1;
  }
  return count;
}

void handleIr() {
  if (!server.hasArg("pattern")) {
    server.send(400, "text/plain", "pattern is required");
    return;
  }
  uint16_t frequency = server.hasArg("freq") ? server.arg("freq").toInt() : 38000;
  uint16_t count = parsePattern(server.arg("pattern"));
  if (count == 0) {
    server.send(400, "text/plain", "empty pattern");
    return;
  }
  irsend.sendRaw(pulses, count, frequency / 1000);
  server.send(200, "text/plain", "sent " + String(count));
}

void setup() {
  Serial.begin(115200);
  irsend.begin();
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print('.');
  }
  Serial.println();
  Serial.print("IR bridge ready at http://");
  Serial.println(WiFi.localIP());

  server.on("/ir", handleIr);
  server.on("/", []() { server.send(200, "text/plain", "SmartTV IR bridge"); });
  server.begin();
}

void loop() {
  server.handleClient();
}
