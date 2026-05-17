#define TRIG_PIN 9
#define ECHO_PIN 10
// === Threshold jarak (cm) ===
#define JARAK_LOCK 30.0          // <= ini -> LOCK
#define JARAK_MENDEKAT 50.0      // antara JARAK_LOCK dan ini -> MENDEKAT
// JARAK_MENJAUH = JARAK_LOCK    // > ini mulai MENJAUH
// JARAK_RESET = JARAK_MENDEKAT  // > ini reset ke IDLE

// === Timing ===
#define HB_MS 1000
#define MENDEKAT_BATAS 2
#define MENJAUH_BATAS 5

enum State { IDLE, MENDEKAT, LOCK, MENJAUH };
State state = IDLE;
unsigned long waktu_report = 0;
int count = 0;

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
  Serial.print("JARAK_LOCK: ");
  Serial.print(JARAK_LOCK);
  Serial.print(", MENDEKAT: ");
  Serial.print(JARAK_MENDEKAT);
  Serial.print(", HB: ");
  Serial.print(HB_MS / 1000);
  Serial.print("s, DEKAT: ");
  Serial.print(MENDEKAT_BATAS);
  Serial.print(", JAUH: ");
  Serial.println(MENJAUH_BATAS);
}

void loop() {
  float jarak = baca_jarak();
  unsigned long now = millis();

  if (jarak == 0.00) {
    unsigned long n = millis();
    if (n - waktu_report >= HB_MS) {
      waktu_report = n;
      Serial.println("ERROR | HC-SR04 tidak merespon (jarak=0)");
    }
    delay(100);
    return;
  }
  if (now - waktu_report < HB_MS) { delay(50); return; }
  waktu_report = now;

  // ─────────── LOCK zone (≤ 30 cm) ───────────
  if (jarak >= 2 && jarak <= JARAK_LOCK) {
    count = 0;
    if (state != LOCK) {
      state = LOCK;
      Serial.print("LOCK | ADA objek terdeteksi | Jarak: ");
      Serial.print(jarak);
      Serial.println(" cm");
    } else {
      Serial.print("LOCK | Objek masih ada | Jarak: ");
      Serial.print(jarak);
      Serial.println(" cm");
    }
    delay(50);
    return;
  }

  // ─────────── MENDEKAT zone (30–50 cm) ───────────
  if (jarak > JARAK_LOCK && jarak <= JARAK_MENDEKAT) {
    if (state == LOCK || state == MENJAUH) goto menjauh_or_idle;

    count++;
    if (count >= MENDEKAT_BATAS) {
      state = MENDEKAT;
      Serial.print("MENDEKAT | Ada objek mendekat | Jarak: ");
      Serial.print(jarak);
      Serial.println(" cm");
    } else {
      // Still counting, stay IDLE
      Serial.print("IDLE | TIDAK ADA objek | Jarak: ");
      Serial.print(jarak);
      Serial.println(" cm");
    }
    delay(50);
    return;
  }

  // ─────────── MENJAUH / IDLE zone (> 50 cm) ───────────
  menjauh_or_idle:
  if (state == LOCK || state == MENJAUH) {
    count++;
    if (count >= MENJAUH_BATAS) {
      state = IDLE;
      count = 0;
      Serial.println("UNLOCK | TIDAK ADA objek");
    } else {
      state = MENJAUH;
      Serial.print("MENJAUH | Objek terlihat menjauh | Jarak: ");
      Serial.print(jarak);
      Serial.print(" cm | Hitungan: ");
      Serial.print(count);
      Serial.print("/");
      Serial.println(MENJAUH_BATAS);
    }
  } else {
    state = IDLE;
    count = 0;
    Serial.print("IDLE | TIDAK ADA objek | Jarak: ");
    Serial.print(jarak);
    Serial.println(" cm");
  }

  delay(50);
}
