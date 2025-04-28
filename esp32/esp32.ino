#include <WiFi.h>
#include <HTTPClient.h>
#include <PZEM004Tv30.h>
#include <ArduinoJson.h>

// WiFi credentials
const char *ssid = "yousef";
const char *password = "123456788";

// Flask server IP
const char *serverURL = "http://192.168.137.1:5000/data";
const char *controlURL = "http://192.168.239.112:5000/esp_command";
const char *controllimitURL = "http://192.168.239.112:5000/esp_limit";

String deviceName = "";
String command = "";
float powerLimit = 100.0;
bool hasTripped = false;
unsigned long countdownStart = 0;
unsigned long countdownDuration = 0;
bool countdownActive = false;
bool relayOpened = false;
// تعريف متغير للتأكد من تشغيل الفصل مرة واحدة
// قيمة ابتدائية مثلاً
// <-- Move it here

// PZEM Serial pins
#define PZEM_RX_PIN 16
#define PZEM_TX_PIN 17
#define RELAY_PIN 5
#define BUZZER_PIN 13
#define LED_PIN 13

// Initialize PZEM sensor
PZEM004Tv30 pzem(Serial2, PZEM_RX_PIN, PZEM_TX_PIN);

void setup()
{
  Serial.begin(115200);
  Serial2.begin(9600, SERIAL_8N1, PZEM_RX_PIN, PZEM_TX_PIN);

  pinMode(RELAY_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);

  digitalWrite(RELAY_PIN, HIGH);
  digitalWrite(BUZZER_PIN, LOW); // إيقاف البازر
  digitalWrite(LED_PIN, LOW);    // الدائرة في وضع التشغيل في البداية

  // Connect to WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to WiFi");

  // Get device name from server
  if (WiFi.status() == WL_CONNECTED)
  {
    HTTPClient http;
    http.begin("http://192.168.137.1:5000/get_device");
    int httpCode = http.GET();

    if (httpCode == 200)
    {
      String payload = http.getString();
      int start = payload.indexOf(":\"") + 2;
      int end = payload.indexOf("\"", start);
      deviceName = payload.substring(start, end);
      Serial.print("Device Name Fetched: ");
      Serial.println(deviceName);
    }
    else
    {
      Serial.println("Failed to get device name");
      deviceName = "FallbackDevice";
    }
    http.end();
  }

  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}
void getControllimit()
{
  if (WiFi.status() == WL_CONNECTED)
  {
    HTTPClient http;
    http.begin(controllimitURL);
    int httpCode = http.GET();

    if (httpCode == 200)
    {
      String payload = http.getString();
      Serial.println("Received payload: " + payload);

      // تحليل JSON
      StaticJsonDocument<200> doc;
      DeserializationError error = deserializeJson(doc, payload);

      if (!error)
      {
        powerLimit = doc["power_limit"].as<float>();

        Serial.println("Parsed command: " + String(powerLimit));
      }
      else
      {
        Serial.println("Failed to parse JSON");
      }
    }
    else
    {
      Serial.print("HTTP error: ");
      Serial.println(httpCode);
    }

    http.end();
  }
}

void getControlCommand()
{
  if (WiFi.status() == WL_CONNECTED)
  {
    HTTPClient http;
    http.begin(controlURL);
    int httpCode = http.GET();

    if (httpCode == 200)
    {
      String payload = http.getString();
      Serial.println("Received payload: " + payload);

      // تحليل JSON
      StaticJsonDocument<200> doc;
      DeserializationError error = deserializeJson(doc, payload);

      if (!error)
      {
        command = doc["command"].as<String>();

        Serial.println("Parsed command: " + command);
      }
      else
      {
        Serial.println("Failed to parse JSON");
      }
    }
    else
    {
      Serial.print("HTTP error: ");
      Serial.println(httpCode);
    }

    http.end();
  }
}

void applyCommand()
{
  if (command == "on")
  {
    if (!hasTripped)
    {
      digitalWrite(RELAY_PIN, HIGH);
      Serial.println("Control Command: ON (Relay OFF)");
    }
    else
    {
      Serial.println("Ignored ON command: Device is tripped due to power limit.");
    }
  }
  else if (command == "off")
  {
    digitalWrite(RELAY_PIN, LOW);
    Serial.println("Control Command: OFF (Relay ON)");
  }
}

void getCountdownFromServer()
{
  if (WiFi.status() == WL_CONNECTED)
  {
    HTTPClient http;
    http.begin("http://192.168.239.112:5000/get_timer");
    int httpCode = http.GET();

    if (httpCode == 200)
    {
      String payload = http.getString();
      Serial.println("تايمر السيرفر: " + payload);

      StaticJsonDocument<200> doc;
      DeserializationError error = deserializeJson(doc, payload);

      if (!error)
      {
        int remainingSeconds = doc["remaining_seconds"];
        if (remainingSeconds > 0)
        {
          countdownDuration = remainingSeconds * 1000UL; // بالملي ثانية
          countdownStart = millis();
          countdownActive = true;
          relayOpened = false;

          digitalWrite(RELAY_PIN, HIGH); // شغّل الدائرة
          Serial.println("بدأ التايمر العد التنازلي لثواني: " + String(remainingSeconds));
        }
        else
        {
          Serial.println("لا يوجد تايمر مفعل حاليًا");
        }
      }
      else
      {
        Serial.println("خطأ في تحليل JSON");
      }
    }
    http.end();
  }
}

void checkCountdown()
{
  if (countdownActive && !relayOpened)
  {
    if (millis() - countdownStart >= countdownDuration)
    {
      digitalWrite(RELAY_PIN, LOW); // فتح الريليه بعد العد التنازلي
      relayOpened = true;
      countdownActive = false;
      Serial.println("انتهى التايمر وتم فتح الريليه");
    }
  }
}

// Read sensor values
void loop()
{
  // Read sensor values
  getControllimit();

  float voltage = pzem.voltage();
  float current = pzem.current();
  float power = pzem.power();
  float energy = pzem.energy();
  float frequency = pzem.frequency();
  float pf = pzem.pf();

  if (isnan(voltage) || isnan(current) || isnan(power) || isnan(energy) || isnan(frequency) || isnan(pf))
  {
    Serial.println("Error reading from sensor");
    delay(2000);
    return;
  }

  // Check and act on power limit
  if (power > powerLimit && !hasTripped)
  {
    digitalWrite(RELAY_PIN, LOW);   // إغلاق الدائرة
    digitalWrite(BUZZER_PIN, HIGH); // تشغيل البازر
    digitalWrite(LED_PIN, HIGH);    // تشغيل الليد
    delay(3000);
    digitalWrite(BUZZER_PIN, LOW); // إيقاف البازر
    digitalWrite(LED_PIN, LOW);

    hasTripped = true;

    // إرسال الأمر للسيرفر لتحديث "command" إلى "off"
    if (WiFi.status() == WL_CONNECTED)
    {
      HTTPClient http;
      http.begin(controlURL); // <-- تأكد إنه يشير إلى /control
      http.addHeader("Content-Type", "application/json");

      String cmdPayload = "{\"command\":\"off\"}";
      int responseCode = http.POST(cmdPayload);

      if (responseCode > 0)
      {
        Serial.println("Command updated on server: off");
      }
      else
      {
        Serial.println("Failed to update command on server");
      }

      http.end();
    }
  }

  // Send sensor data
  if (WiFi.status() == WL_CONNECTED)
  {
    HTTPClient http;
    http.begin(serverURL);
    http.addHeader("Content-Type", "application/json");

    String payload = "{";
    payload += "\"device\":\"" + deviceName + "\",";
    payload += "\"voltage\":" + String(voltage, 1) + ",";
    payload += "\"current\":" + String(current, 2) + ",";
    payload += "\"power\":" + String(power, 1) + ",";
    payload += "\"energy_consumption\":" + String(energy, 3) + ",";
    payload += "\"active_power\":" + String(power, 1) + ",";
    payload += "\"frequency\":" + String(frequency, 1) + ",";
    payload += "\"power_factor\":" + String(pf, 2) + ",";
    payload += "\"active_energy\":" + String(energy, 3);
    payload += "}";

    int httpResponseCode = http.POST(payload);
    http.end();

    // Just get control command (no action)

    getControlCommand();
    applyCommand();
    if (!countdownActive)
    {
      getCountdownFromServer();
    }
    checkCountdown(); // يشيّك إذا خلص

    // تنفيذ الأمر بناءً على القيمة
  }
  else
  {
    Serial.println("WiFi Disconnected");
  }

  delay(2000);
}