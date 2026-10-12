// ESP32 OTP Door Access - keypad + OLED + buzzer + SERVO (no relay)
// Libraries: Keypad, Adafruit SSD1306, Adafruit GFX, ESP32Servo
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Keypad.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ESP32Servo.h>

const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_PASS";
const char* VERIFY_URL = "https://YOUR-APP.onrender.com/api/otp/verify";
const char* DEVICE_ID  = "door-1";
const char* API_KEY    = "CHANGE_ME_DEVICE_KEY";   // same as DEVICE_KEY on Render

// ---- Pins ----
const int SERVO_PIN  = 18;
const int BUZZER_PIN = 19;
byte rowPins[4] = {13, 12, 14, 27};
byte colPins[4] = {26, 25, 33, 32};
// OLED I2C: SDA=21, SCL=22

char keys[4][4] = {{'1','2','3','A'},{'4','5','6','B'},{'7','8','9','C'},{'*','0','#','D'}};
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, 4, 4);
Adafruit_SSD1306 oled(128, 64, &Wire, -1);
Servo door;

const int LOCKED_ANGLE = 0, OPEN_ANGLE = 90;
const unsigned long WAIT_TIMEOUT = 60000;   // max time to type the OTP
const unsigned long OPEN_TIME    = 5000;    // door stays open 5 s

enum State { IDLE, WAIT, VERIFY, ACTION };
State state = IDLE;
String entry = "";
unsigned long waitStart = 0;
bool granted = false;
String reason = "";

void show(const String& l1, const String& l2 = "") {
  oled.clearDisplay(); oled.setTextColor(WHITE); oled.setTextSize(1);
  oled.setCursor(0, 0);  oled.println(l1);
  oled.setTextSize(2);   oled.setCursor(0, 24); oled.println(l2);
  oled.display();
}
void beep(int ms, int n = 1) { for (int i = 0; i < n; i++) { digitalWrite(BUZZER_PIN, HIGH); delay(ms); digitalWrite(BUZZER_PIN, LOW); delay(80); } }

bool verifyOtp(const String& otp) {
  WiFiClientSecure client; client.setInsecure();   // for school project; use a root CA in production
  HTTPClient http;
  if (!http.begin(client, VERIFY_URL)) return false;
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", API_KEY);
  int code = http.POST("{\"device_id\":\"" + String(DEVICE_ID) + "\",\"otp\":\"" + otp + "\"}");
  String body = http.getString(); http.end();
  if (code != 200) { reason = "server_error"; return false; }
  if (body.indexOf("\"access\":true") >= 0) return true;
  reason = body.indexOf("expired") >= 0 ? "expired" : "wrong_otp";
  return false;
}

void setup() {
  pinMode(BUZZER_PIN, OUTPUT);
  Wire.begin(21, 22);
  oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  door.attach(SERVO_PIN); door.write(LOCKED_ANGLE);
  show("Connecting WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) delay(300);
  show("Press # to start");
}

void loop() {
  char k = keypad.getKey();
  switch (state) {
    case IDLE:
      if (k == '#') { entry = ""; waitStart = millis(); state = WAIT; show("Enter OTP (*=clear)", ""); }
      break;

    case WAIT:   // waiting for the user to type the OTP from the app
      if (millis() - waitStart > WAIT_TIMEOUT) { show("Timed out"); beep(300, 2); delay(1500); show("Press # to start"); state = IDLE; break; }
      if (k >= '0' && k <= '9' && entry.length() < 6) { entry += k; String m = ""; for (unsigned i = 0; i < entry.length(); i++) m += '*'; show("Enter OTP", m); }
      else if (k == '*') { entry = ""; show("Enter OTP", ""); }
      if (entry.length() == 6) state = VERIFY;
      break;

    case VERIFY:
      show("Checking...");
      granted = verifyOtp(entry);
      entry = "";
      state = ACTION;
      break;

    case ACTION:
      if (granted) {
        show("ACCESS GRANTED"); beep(150, 1);
        door.write(OPEN_ANGLE); delay(OPEN_TIME); door.write(LOCKED_ANGLE);
      } else {
        show("DENIED", reason); beep(400, 3); delay(1500);
      }
      show("Press # to start");
      state = IDLE;
      break;
  }
}
