#define TRIG_PIN 9
#define ECHO_PIN 10
#define HB_MS 1000

unsigned long waktu_report = 0;

float baca_jarak() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  return duration * 0.0343 / 2;
}

void setup() {
  Serial.begin(9600);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);
  delay(500);
  Serial.println("ARDUINO READY | HC-SR04 Ultrasonic");
}

void loop() {
  unsigned long now = millis();
  if (now - waktu_report < HB_MS) { delay(50); return; }
  waktu_report = now;

  float jarak = baca_jarak();
  if (jarak == 0.00) {
    Serial.println("JARAK: -1.0 cm");
    return;
  }
  Serial.print("JARAK: ");
  Serial.print(jarak);
  Serial.println(" cm");
}
