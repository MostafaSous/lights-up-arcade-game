// Pins
#define PIN_BUZZER     4
#define PIN_BTN_LEFT   7
#define PIN_BTN_RIGHT  8

#define DEBOUNCE_MS 50

bool lastLeft  = HIGH;
bool lastRight = HIGH;
unsigned long lastLeftTime  = 0;
unsigned long lastRightTime = 0;

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BTN_LEFT,  INPUT_PULLUP);
  pinMode(PIN_BTN_RIGHT, INPUT_PULLUP);
  pinMode(PIN_BUZZER,    OUTPUT);
  noTone(PIN_BUZZER);
}

void buzzWin() {
  tone(PIN_BUZZER, 880, 80);
  delay(90);
  tone(PIN_BUZZER, 1200, 120);
  delay(130);
  noTone(PIN_BUZZER);
}

void buzzFail() {
  tone(PIN_BUZZER, 300, 200);
  delay(220);
  tone(PIN_BUZZER, 180, 300);
  delay(320);
  noTone(PIN_BUZZER);
}

void buzzStart() {
  tone(PIN_BUZZER, 600, 60);
  delay(80);
  noTone(PIN_BUZZER);
}

void buzzGameOver() {
  tone(PIN_BUZZER, 440, 150);
  delay(170);
  tone(PIN_BUZZER, 330, 150);
  delay(170);
  tone(PIN_BUZZER, 220, 400);
  delay(420);
  noTone(PIN_BUZZER);
}

void loop() {
  unsigned long now = millis();

  // Left button (active LOW with INPUT_PULLUP)
  bool curLeft = digitalRead(PIN_BTN_LEFT);
  if (curLeft == LOW && lastLeft == HIGH && (now - lastLeftTime) > DEBOUNCE_MS) {
    Serial.println("L");
    lastLeftTime = now;
  }
  lastLeft = curLeft;

  // Right button
  bool curRight = digitalRead(PIN_BTN_RIGHT);
  if (curRight == LOW && lastRight == HIGH && (now - lastRightTime) > DEBOUNCE_MS) {
    Serial.println("R");
    lastRightTime = now;
  }
  lastRight = curRight;

  // Commands from Python
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if      (cmd == "WIN")      buzzWin();
    else if (cmd == "FAIL")     buzzFail();
    else if (cmd == "START")    buzzStart();
    else if (cmd == "GAMEOVER") buzzGameOver();
  }
}
