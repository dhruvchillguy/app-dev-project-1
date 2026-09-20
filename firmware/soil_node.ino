#include <Arduino.h>

const int SENSOR_PIN = 34;
const int ZONE_ID = 1;
const int SAMPLES = 10;
const int INTERVAL_MS = 5000;

void setup() {
  Serial.begin(115200);
}

void loop() {
  long sum = 0;
  for (int i = 0; i < SAMPLES; i++) {
    sum += analogRead(SENSOR_PIN);
    delay(10);
  }
  int avg = sum / SAMPLES;
  Serial.print("{\"zone\":");
  Serial.print(ZONE_ID);
  Serial.print(",\"raw\":");
  Serial.print(avg);
  Serial.println("}");
  delay(INTERVAL_MS);
}
