#include <WiFi.h>
#include <PubSubClient.h>

// Wi-Fi dan ThingsBoard
const char* ssid = "KOS FIRDAUS";
const char* password = "NADIF354";
const char* mqtt_server = "192.168.1.7";
const int mqtt_port = 1883;
const char* client_id = "2kev19fo80ioa7sr9xdi";
const char* user_name = "481trhjkqifbe3krzau7";
const char* mqtt_password = "3h23on2t05bob6es2uoy";

// Pin sensor ultrasonik
#define TRIG_PIN1 4   // Sensor B3
#define ECHO_PIN1 34
#define TRIG_PIN2 13  // Sensor A6
#define ECHO_PIN2 12
#define TRIG_PIN3 14  // Sensor A3
#define ECHO_PIN3 27

// Pin LED
#define LED_PIN1 15   // LED untuk B3
#define LED_PIN2 2    // LED untuk A6
#define LED_PIN3 5    // LED untuk A3

// Pin Buzzer
#define BUZZER_PIN1 25 // Buzzer untuk B3
#define BUZZER_PIN2 26 // Buzzer untuk A6
#define BUZZER_PIN3 32 // Buzzer untuk A3

#define MAX_DISTANCE 400 // Maksimal jarak deteksi ultrasonik (cm)

WiFiClient espClient;
PubSubClient client(espClient);

// Variabel untuk jarak dan status
long duration;
float distance1, distance2, distance3;
bool slot1_occupied, slot2_occupied, slot3_occupied;
bool slot1_booked = false, slot2_booked = false, slot3_booked = false;
const float threshold = 5.0; // Jarak threshold (cm)

// Variabel untuk mengatur waktu pengiriman data
unsigned long lastSendTime = 0;
const unsigned long sendInterval = 1000; // Interval pengiriman data: 1 detik

void setup() {
  Serial.begin(115200);

  // Setup pin sensor
  pinMode(TRIG_PIN1, OUTPUT);
  pinMode(ECHO_PIN1, INPUT);
  pinMode(TRIG_PIN2, OUTPUT);
  pinMode(ECHO_PIN2, INPUT);
  pinMode(TRIG_PIN3, OUTPUT);
  pinMode(ECHO_PIN3, INPUT);

  // Setup pin LED
  pinMode(LED_PIN1, OUTPUT);
  pinMode(LED_PIN2, OUTPUT);
  pinMode(LED_PIN3, OUTPUT);
  // Inisialisasi lampu menyala (default)
  digitalWrite(LED_PIN1, HIGH);
  digitalWrite(LED_PIN2, HIGH);
  digitalWrite(LED_PIN3, HIGH);

  // Setup pin buzzer
  pinMode(BUZZER_PIN1, OUTPUT);
  pinMode(BUZZER_PIN2, OUTPUT);
  pinMode(BUZZER_PIN3, OUTPUT);

  // Koneksi Wi-Fi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");

  // Koneksi MQTT
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

void reconnect() {
  while (!client.connected()) {
    Serial.println("Connecting to MQTT...");
    if (client.connect(client_id, user_name, mqtt_password)) {
      Serial.println("Connected to MQTT");
      client.subscribe("v1/devices/me/attributes");
    } else {
      Serial.print("Failed, rc=");
      Serial.println(client.state());
      delay(5000);
    }
  }
}

void callback(char* topic, byte* payload, unsigned int length) {
  String message;
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.println("Message received: " + message);

  // Parsing pesan dari ThingsBoard
  if (message.indexOf("lamp1") != -1 || message.indexOf("slot1_booked") != -1) {
    slot1_booked = (message.indexOf("slot1_booked\":true") != -1);
    digitalWrite(LED_PIN1, (message.indexOf("lamp1\":true") != -1) ? HIGH : LOW);
  }
  if (message.indexOf("lamp2") != -1 || message.indexOf("slot2_booked") != -1) {
    slot2_booked = (message.indexOf("slot2_booked\":true") != -1);
    digitalWrite(LED_PIN2, (message.indexOf("lamp2\":true") != -1) ? HIGH : LOW);
  }
  if (message.indexOf("lamp3") != -1 || message.indexOf("slot3_booked") != -1) {
    slot3_booked = (message.indexOf("slot3_booked\":true") != -1);
    digitalWrite(LED_PIN3, (message.indexOf("lamp3\":true") != -1) ? HIGH : LOW);
  }
}

float readDistance(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  duration = pulseIn(echoPin, HIGH);
  float distance = duration * 0.034 / 2;
  if (distance > MAX_DISTANCE) distance = MAX_DISTANCE;
  return distance;
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // Kirim data setiap 1 detik
  unsigned long currentTime = millis();
  if (currentTime - lastSendTime >= sendInterval) {
    distance1 = readDistance(TRIG_PIN1, ECHO_PIN1);
    distance2 = readDistance(TRIG_PIN2, ECHO_PIN2);
    distance3 = readDistance(TRIG_PIN3, ECHO_PIN3);

    slot1_occupied = (distance1 < threshold);
    slot2_occupied = (distance2 < threshold);
    slot3_occupied = (distance3 < threshold);

    // Kontrol buzzer
    if (slot1_booked && slot1_occupied) {
      tone(BUZZER_PIN1, 2700, 500); // Bunyi 2700 Hz selama 500ms untuk B3
    } else {
      noTone(BUZZER_PIN1);
    }
    if (slot2_booked && slot2_occupied) {
      tone(BUZZER_PIN2, 2700, 500); // Bunyi 2700 Hz selama 500ms untuk A6
    } else {
      noTone(BUZZER_PIN2);
    }
    if (slot3_booked && slot3_occupied) {
      tone(BUZZER_PIN3, 2700, 500); // Bunyi 2700 Hz selama 500ms untuk A3
    } else {
      noTone(BUZZER_PIN3);
    }

    // Kontrol lampu
    digitalWrite(LED_PIN1, (!slot1_booked && !slot1_occupied) ? HIGH : LOW);
    digitalWrite(LED_PIN2, (!slot2_booked && !slot2_occupied) ? HIGH : LOW);
    digitalWrite(LED_PIN3, (!slot3_booked && !slot3_occupied) ? HIGH : LOW);

    // Kirim data ke ThingsBoard
    String payload = "{\"slot1_distance\":" + String(distance1) +
                     ",\"slot2_distance\":" + String(distance2) +
                     ",\"slot3_distance\":" + String(distance3) +
                     ",\"slot1_occupied\":" + String(slot1_occupied) +
                     ",\"slot2_occupied\":" + String(slot2_occupied) +
                     ",\"slot3_occupied\":" + String(slot3_occupied) +
                     ",\"slot1_booked\":" + String(slot1_booked) +
                     ",\"slot2_booked\":" + String(slot2_booked) +
                     ",\"slot3_booked\":" + String(slot3_booked) + "}";
    client.publish("v1/devices/me/telemetry", payload.c_str());

    Serial.println("Data sent: " + payload);
    lastSendTime = currentTime;
  }
}
