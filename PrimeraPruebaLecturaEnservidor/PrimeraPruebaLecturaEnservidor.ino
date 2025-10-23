#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_PN532.h>
#include <ESP32Servo.h>
#include <ArduinoJson.h>

#define SDA_PIN 21
#define SCL_PIN 22

Adafruit_PN532 nfc(SDA_PIN, SCL_PIN);
Servo servoMotor;

const char* ssid = "ALVAREZ";
const char* password = "CAMILO2003";

// Servidor FastAPI
const char* serverName = "http://192.168.1.7:8000/verificar/";

void setup() {
  Serial.begin(115200);

  WiFi.begin(ssid, password);
  Serial.print("Conectando a WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ WiFi conectado");

  Wire.begin(SDA_PIN, SCL_PIN);
  nfc.begin();
  if (!nfc.getFirmwareVersion()) {
    Serial.println("❌ No se encontró PN53x");
    while (1);
  }
  nfc.SAMConfig();
  Serial.println("✅ PN532 listo");

  servoMotor.attach(27, 500, 2400);
  servoMotor.write(0);
}

void loop() {
  uint8_t uid[7]; 
  uint8_t uidLength;

  if (nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength)) {
    String uidHex = "";
    for (uint8_t i = 0; i < uidLength; i++) {
      char buf[3];
      sprintf(buf, "%02X", uid[i]);
      uidHex += buf;
    }
    Serial.println("UID leído: " + uidHex);

    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(serverName);
      http.addHeader("Content-Type", "application/json");

      // JSON de petición
      String json = "{\"uid\":\"" + uidHex + "\"}";
      int httpResponseCode = http.POST(json);

      if (httpResponseCode == 200) {
        String payload = http.getString();
        Serial.println("Respuesta: " + payload);

        StaticJsonDocument<256> doc;
        deserializeJson(doc, payload);

        bool autorizado = doc["autorizado"];
        if (autorizado) {
          String nuevoUID = doc["nuevo_uid"];
          String hash = doc["hash"];

          Serial.println("✅ Acceso autorizado");
          Serial.println("Nuevo UID: " + nuevoUID);
          Serial.println("Hash: " + hash);

          servoMotor.write(90);
          delay(2000);
          servoMotor.write(0);
        } else {
          Serial.println("❌ Acceso denegado: " + String(doc["motivo"].as<const char*>()));
        }
      } else {
        Serial.println("Error HTTP: " + String(httpResponseCode));
      }
      http.end();
    }
    delay(2000);
  }
}
