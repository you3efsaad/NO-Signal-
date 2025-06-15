#include <WiFi.h>
#include <HTTPClient.h>
#include <PZEM004Tv30.h>
#include <ArduinoJson.h>
#include <WiFiManager.h> // مكتبة WiFiManager

// Base URL of the Railway server
const char *baseURL = "https://no-signal-production.up.railway.app";

// Global variables
String deviceName = "";
String command = "";
float powerLimit = 100.0;
bool hasTripped = false;
unsigned long countdownStart = 0;
unsigned long countdownDuration = 0;
bool countdownActive = false;
bool relayOpened = false;


// PZEM Serial pins
#define PZEM_RX_PIN 16
#define PZEM_TX_PIN 17
#define RELAY_PIN 5
#define BUZZER_PIN 13
#define LED_PIN 13

PZEM004Tv30 pzem(Serial2, PZEM_RX_PIN, PZEM_TX_PIN);

void setup()
{
  Serial.begin(115200);
  Serial2.begin(9600, SERIAL_8N1, PZEM_RX_PIN, PZEM_TX_PIN);

  pinMode(RELAY_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);

  digitalWrite(RELAY_PIN, HIGH);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(LED_PIN, LOW);

  // استخدام WiFiManager للاتصال بالواي فاي
  WiFiManager wm;
  bool res = wm.autoConnect("✌️ y & m ✌️");

  if (!res)
  {
    Serial.println("Failed to connect to WiFi.");
    ESP.restart();
  }
  else
  {
    Serial.println("Connected to WiFi.");
    Serial.println(WiFi.localIP());
  }

  // Fetch device name from server
  HTTPClient http;
  http.begin(String(baseURL) + "/get_device");
  int httpCode = http.GET();

  if (httpCode == 200)
  {
    String payload = http.getString();
    Serial.println("Device payload: " + payload);

    StaticJsonDocument<200> doc;
    DeserializationError error = deserializeJson(doc, payload);

    if (!error)
    {
      deviceName = doc["device"].as<String>();
      Serial.println("Device Name Fetched: " + deviceName);
    }
    else
    {
      Serial.println("Failed to parse JSON");
      deviceName = "FallbackDevice";
    }
  }
  else
  {
    Serial.println("Failed to get device name");
    deviceName = "FallbackDevice";
  }
  http.end();
}

void getControllimit()
{
  if (WiFi.status() == WL_CONNECTED)
  {
    HTTPClient http;
    http.begin(String(baseURL) + "/esp_limit");
    int httpCode = http.GET();

    if (httpCode == 200)
    {
      String payload = http.getString();
      Serial.println("Received limit: " + payload);

      StaticJsonDocument<200> doc;
      DeserializationError error = deserializeJson(doc, payload);

      if (!error)
      {
        powerLimit = doc["power_limit"].as<float>();
      }
    }
    http.end();
  }
}

void getControlCommand()
{
  if (WiFi.status() == WL_CONNECTED)
  {
    HTTPClient http;
    http.begin(String(baseURL) + "/esp_command");
    int httpCode = http.GET();

    if (httpCode == 200)
    {
      String payload = http.getString();
      Serial.println("Received command: " + payload);

      StaticJsonDocument<200> doc;
      DeserializationError error = deserializeJson(doc, payload);

      if (!error)
      {
        command = doc["command"].as<String>();
      }
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
    http.begin(String(baseURL) + "/get_timer");
    int httpCode = http.GET();

    if (httpCode == 200)
    {
      String payload = http.getString();
      Serial.println("Timer payload: " + payload);

      StaticJsonDocument<200> doc;
      DeserializationError error = deserializeJson(doc, payload);

      if (!error)
      {
        int remainingSeconds = doc["remaining_seconds"];
        if (remainingSeconds > 0)
        {
          countdownDuration = remainingSeconds * 1000UL;
          countdownStart = millis();
          countdownActive = true;
          relayOpened = false;
          digitalWrite(RELAY_PIN, HIGH);
        }
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
      digitalWrite(RELAY_PIN, LOW);
      relayOpened = true;
      countdownActive = false;
      Serial.println("Timer ended, relay off");
    }
  }
}

void loop()
{
  getControllimit();

  float voltage = pzem.voltage();
  float current = pzem.current();
  float power = pzem.power();
  float energy = pzem.energy();
  float frequency = pzem.frequency();
  float pf = pzem.pf();

  if (isnan(voltage) || isnan(current) || isnan(power))
  {
    Serial.println("Sensor read error");
    delay(2000);
    return;
  }

  if (power > powerLimit && !hasTripped)
  {
    digitalWrite(RELAY_PIN, LOW);
    digitalWrite(BUZZER_PIN, HIGH);
    digitalWrite(LED_PIN, HIGH);
    delay(3000);
    digitalWrite(BUZZER_PIN, LOW);
    digitalWrite(LED_PIN, LOW);
    hasTripped = true;

    if (WiFi.status() == WL_CONNECTED)
    {
      HTTPClient http;
      http.begin(String(baseURL) + "/esp_command");
      http.addHeader("Content-Type", "application/json");

      String cmdPayload = "{\"command\":\"off\"}";
      http.POST(cmdPayload);
      http.end();
    }
  }

  if (WiFi.status() == WL_CONNECTED)
  {
    HTTPClient http;
    http.begin(String(baseURL) + "/data");
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

    getControlCommand();
    applyCommand();

    if (!countdownActive)
    {
      getCountdownFromServer();
    }

    checkCountdown();
  }

  delay(2000);
}
