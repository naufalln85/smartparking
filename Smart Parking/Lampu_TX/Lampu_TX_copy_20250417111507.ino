#define BLYNK_TEMPLATE_ID "TMPL6e11RNRWe"
#define BLYNK_TEMPLATE_NAME "Parking Slot"
#define BLYNK_AUTH_TOKEN "xbC-JEuKmxpdry7iTOd8n2h_bCsaOf-I"

#include <ESP8266WiFi.h>
#include <BlynkSimpleEsp8266.h>

#define led1 D1  // Slot A6 → V1
#define led2 D2  // Slot A3 → V2
#define led3 D0  // Slot B3 → V0

char ssid[] = "POCO F4 GT";      // Ganti sesuai hotspot kamu
char pass[] = "Yuhen112233";     // Password hotspot kamu

void setup() {
  Serial.begin(115200);
  Blynk.begin(BLYNK_AUTH_TOKEN, ssid, pass);

  pinMode(led1, OUTPUT);
  pinMode(led2, OUTPUT);
  pinMode(led3, OUTPUT);
}

void loop() {
  Blynk.run();

  if (Serial.available()) {
    String data = Serial.readStringUntil('\n'); // format: d1,d2,d3
    int d1, d2, d3;

    if (sscanf(data.c_str(), "%d,%d,%d", &d1, &d2, &d3) == 3) {
      // Update LED & kirim status ke Blynk
      digitalWrite(led1, d1 <= 5 ? HIGH : LOW);
      Blynk.virtualWrite(V1, d1 <= 5 ? "Isi" : "Kosong");

      digitalWrite(led2, d2 <= 5 ? HIGH : LOW);
      Blynk.virtualWrite(V2, d2 <= 5 ? "Isi" : "Kosong");

      digitalWrite(led3, d3 <= 5 ? HIGH : LOW);
      Blynk.virtualWrite(V0, d3 <= 5 ? "Isi" : "Kosong");

      // Debug Serial
      Serial.print("LED1 (D1 / V1): "); Serial.print(d1 <= 5 ? "ON" : "OFF");
      Serial.print(" | LED2 (D2 / V2): "); Serial.print(d2 <= 5 ? "ON" : "OFF");
      Serial.print(" | LED3 (D0 / V0): "); Serial.println(d3 <= 5 ? "ON" : "OFF");
    }
  }
}
