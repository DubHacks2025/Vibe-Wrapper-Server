
#include <TM1637Display.h>

#define CLK 8
#define DIO 10
TM1637Display display(CLK, DIO);

const int buttonPin = 7;

enum State { IDLE, RECORDING, LOCKED };
State currentState = IDLE;

unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50; // 50ms is usually enough

// 7-seg segment bit definitions (TM1637Display uses these bit orders)
#define SEG_A 0x01
#define SEG_B 0x02
#define SEG_C 0x04
#define SEG_D 0x08
#define SEG_E 0x10
#define SEG_F 0x20
#define SEG_G 0x40
#define SEG_DP 0x80

void showDigitsTest() {
  // Show 0 1 2 3 to prove the display works
  display.showNumberDecEx(123, 0, true);
  delay(1000);
  display.clear();
}

void showRecording() {
  // “REC_”
  uint8_t rec[] = {
    SEG_E | SEG_G, //  'R'
    SEG_A | SEG_F | SEG_G | SEG_E | SEG_D, // 'E'
    SEG_A | SEG_F | SEG_E | SEG_D,         // 'C'
    0x00
  };
  display.setSegments(rec);
}

void showWaiting() {
  // "----"
  uint8_t dash[] = { SEG_G, SEG_G, SEG_G, SEG_G };
  display.setSegments(dash);
}

void showReady() {
  // "RDY_"
  uint8_t rdy[] = {
    SEG_E | SEG_G, // crude 'R'
    // better “D” on 7-seg is usually B C D E G (looks like lowercase 'd')
    SEG_B | SEG_C | SEG_D | SEG_E | SEG_G, // 'd'
    // “Y” approx: B C D F G can look closer to Y on many modules
    SEG_B | SEG_C | SEG_D | SEG_F | SEG_G,
    0x00
  };
  display.setSegments(rdy);
}

void setup() {
  pinMode(buttonPin, INPUT_PULLUP);  // button between pin and GND
  Serial.begin(9600);
  display.setBrightness(0x0f);

  showDigitsTest();   // prove the display works first
  showReady();        // then your intended ready state
}

void loop() {
  // Raw read so you can see the pin change in real-time
  // int raw = digitalRead(buttonPin);  // HIGH = released, LOW = pressed (with INPUT_PULLUP)
  // Serial.println(raw);

  checkButton();   // debounced edge detection
  checkSerial();   // external serial commands "DONE"
}

void checkButton() {
  static int lastStable = HIGH;   // matches INPUT_PULLUP idle
  static int lastReading = HIGH;

  int reading = digitalRead(buttonPin);
  if (reading != lastReading) {
    lastDebounceTime = millis();  // reading changed, start debounce timer
  }
  lastReading = reading;

  if ((millis() - lastDebounceTime) > debounceDelay) {
    // after stable for debounceDelay, accept as the stable state
    if (reading != lastStable) {
      lastStable = reading;

      // Falling edge: HIGH -> LOW means button pressed with INPUT_PULLUP
      if (lastStable == LOW) {
        handlePress();
      }
    }
  }
}

void handlePress() {
  if (currentState == IDLE) {
    Serial.println("START");
    showRecording();
    currentState = RECORDING;
  } else if (currentState == RECORDING) {
    Serial.println("STOP");
    showWaiting();
    currentState = LOCKED;
  } else if (currentState == LOCKED) {
    // Optional: allow press to go back to ready (or keep locked until "DONE")
    // Serial.println("RESET");
    // showReady();
    // currentState = IDLE;
  }
}

void checkSerial() {
  if (Serial.available()) {
    String msg = Serial.readStringUntil('\n');
    msg.trim();
    if (msg == "DONE") {
      showReady();
      currentState = IDLE;
      Serial.println("DONE -> IDLE");
    }
  }
}
