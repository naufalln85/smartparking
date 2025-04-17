#define trigPin1 D1
#define echoPin1 D2
#define trigPin2 D6
#define echoPin2 D7
#define trigPin3 D5
#define echoPin3 D8

void setup() {
  Serial.begin(115200);
  pinMode(trigPin1, OUTPUT); pinMode(echoPin1, INPUT);
  pinMode(trigPin2, OUTPUT); pinMode(echoPin2, INPUT);
  pinMode(trigPin3, OUTPUT); pinMode(echoPin3, INPUT);

  Serial.println("=== Monitoring Sensor Ultrasonik ===");
}

long readUltrasonic(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  long duration = pulseIn(echoPin, HIGH, 30000); // timeout 30ms
  return duration * 0.034 / 2;
}

void loop() {
  long d1 = readUltrasonic(trigPin1, echoPin1);
  long d2 = readUltrasonic(trigPin2, echoPin2);
  long d3 = readUltrasonic(trigPin3, echoPin3);

  // Tampilkan ke Serial Monitor
  Serial.print("Sensor 1 (D1-D2): "); Serial.print(d1); Serial.print(" cm | ");
  Serial.print("Sensor 2 (D6-D7): "); Serial.print(d2); Serial.print(" cm | ");
  Serial.print("Sensor 3 (D5-D8): "); Serial.print(d3); Serial.println(" cm");

  // Juga kirim data mentah ke ESP RX (jika dipakai)
  Serial.print(d1); Serial.print(",");
  Serial.print(d2); Serial.print(",");
  Serial.println(d3); // ini penting untuk RX

  delay(1000); // jeda 1 detik biar tidak terlalu cepat
}

