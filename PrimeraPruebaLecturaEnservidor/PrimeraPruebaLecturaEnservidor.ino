#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_PN532.h>
#include <ESP32Servo.h>

// --- Pines I2C (PCB)
#define SDA_PIN 21
#define SCL_PIN 22

Adafruit_PN532 nfc(SDA_PIN, SCL_PIN);
Servo servoMotor;

const char* ssid = "ALVAREZ";
const char* password = "CAMILO2003";

// Dirección del servidor FastAPI
const char* serverName = "http://192.168.1.7:8000/verificar/";

void setup() {
  Serial.begin(115200);

  // WiFi
  WiFi.begin(ssid, password);
  Serial.print("Conectando a WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ WiFi conectado");

  // PN532
  Wire.begin(SDA_PIN, SCL_PIN);
  nfc.begin();
  uint32_t versiondata = nfc.getFirmwareVersion();
  if (!versiondata) {
    Serial.println("❌ No se encontró PN53x, revise conexiones");
    while (1);
  }
  nfc.SAMConfig();
  Serial.println("✅ PN532 listo, esperando tarjeta...");

  // Servo
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
      String url = String(serverName) + uidHex;
      http.begin(url);
      int httpResponseCode = http.GET();

      if (httpResponseCode == 200) {
        String payload = http.getString();
        Serial.println("Respuesta: " + payload);

        if (payload.indexOf("\"autorizado\":true") > 0) {
          Serial.println("✅ Acceso autorizado");
          servoMotor.write(90);
          delay(2000);
          servoMotor.write(0);
        } else {
          Serial.println("❌ Acceso denegado");
        }
      } else {
        Serial.println("Error HTTP: " + String(httpResponseCode));
      }
      http.end();
    }
    delay(2000); // evitar múltiples lecturas rápidas
  }
}
