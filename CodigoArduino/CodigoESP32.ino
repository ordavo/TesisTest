/******************************************************
 * ESP32 + PN532 (I2C con IRQ/RESET) + Servo + FastAPI
 * Flujo: GET /api/nonce → POST /api/verify (HMAC-SHA256)
 * HMAC sobre BYTES(uid||nonce) ✅
 ******************************************************/

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_PN532.h>
#include <ESP32Servo.h>
#include <ArduinoJson.h>
#include <mbedtls/md.h>
#include <vector>

/********** WiFi **********/
const char* WIFI_SSID     = "ALVAREZ";
const char* WIFI_PASSWORD = "CAMILO2003";

/********** Servidor **********/
const char* SERVER_HOST = "192.168.1.7";
const uint16_t SERVER_PORT = 8000;
const char* URL_NONCE  = "/api/nonce";
const char* URL_VERIFY = "/api/verify";

/********** Seguridad **********/
const char* SECRET_KEY = "MiEjemplo";
const uint32_t NONCE_TTL_MS = 2500;

/********** PN532 (I2C con IRQ/RESET) **********/
#define I2C_SDA 21
#define I2C_SCL 22
#define PN532_IRQ   19
#define PN532_RESET 18
Adafruit_PN532 nfc(PN532_IRQ, PN532_RESET, &Wire);

/********** Servo **********/
#define SERVO_PIN 27
Servo servoMotor;
int SERVO_OPEN = 120;
int SERVO_CLOSE = 0;

/********** LEDs **********/
#define LED_VERDE 25
#define LED_ROJO 26

/********** HTTP **********/
HTTPClient http;

/********** Estados **********/
enum State { WIFI_CONNECT, NFC_INIT, IDLE, REQUEST_NONCE, POST_VERIFY, ACTUATE, WAIT_BACKOFF };
State state = WIFI_CONNECT;

/********** Variables **********/
String lastUIDHex;
String sessionId;
String nonceHex;
uint32_t stateDeadline = 0;
uint32_t backoffMs = 500;

/********** Utils **********/
String toHexUpper(const uint8_t* buf, size_t len) {
  static const char* hex = "0123456789ABCDEF";
  String out; out.reserve(len*2);
  for (size_t i=0;i<len;i++){ out += hex[(buf[i]>>4)&0xF]; out += hex[buf[i]&0xF]; }
  return out;
}

bool hexToBytes(const String& hex, std::vector<uint8_t>& out) {
  out.clear();
  if (hex.length() % 2 != 0) return false;
  out.reserve(hex.length()/2);
  auto val = [](char c)->int{
    if (c>='0'&&c<='9') return c-'0';
    if (c>='A'&&c<='F') return 10 + (c-'A');
    if (c>='a'&&c<='f') return 10 + (c-'a');
    return -1;
  };
  for (size_t i = 0; i < hex.length(); i += 2) {
    int hi = val(hex[i]); int lo = val(hex[i+1]);
    if (hi<0||lo<0) return false;
    out.push_back((uint8_t)((hi<<4)|lo));
  }
  return true;
}

String hmacSha256HexBytes(const uint8_t* data, size_t len) {
  const mbedtls_md_info_t* info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  unsigned char out[32];
  mbedtls_md_context_t ctx;
  mbedtls_md_init(&ctx);
  mbedtls_md_setup(&ctx, info, 1);
  mbedtls_md_hmac_starts(&ctx, (const unsigned char*)SECRET_KEY, strlen(SECRET_KEY));
  mbedtls_md_hmac_update(&ctx, data, len);
  mbedtls_md_hmac_finish(&ctx, out);
  mbedtls_md_free(&ctx);

  static const char* hex = "0123456789abcdef";
  String h; h.reserve(64);
  for (int i=0;i<32;i++){ h += hex[(out[i]>>4)&0xF]; h += hex[out[i]&0xF]; }
  return h;
}

String buildURL(const char* path) {
  String url = String("http://") + SERVER_HOST + ":" + String(SERVER_PORT) + path;
  return url;
}

/********** WiFi robusto **********/
void ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.print("Conectando a WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 8000) {
    Serial.print(".");
    delay(300);
  }
  Serial.println(WiFi.status()==WL_CONNECTED ? "\n WiFi conectado" : "\n WiFi no conectado");
}

/********** Setup **********/
void setup() {
  Serial.begin(115200);
  delay(100);

  WiFi.mode(WIFI_STA);
  ensureWiFi();

  Wire.begin(I2C_SDA, I2C_SCL);
  pinMode(PN532_IRQ, INPUT);
  pinMode(PN532_RESET, OUTPUT);
  state = NFC_INIT;

  servoMotor.attach(SERVO_PIN, 500, 2400);
  servoMotor.write(SERVO_CLOSE);

  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_ROJO, OUTPUT);
  digitalWrite(LED_VERDE, LOW);
  digitalWrite(LED_ROJO, LOW);
}

/********** Loop **********/
void loop() {
  switch (state) {

    case NFC_INIT: {
      Serial.println("Inicializando PN532...");
      nfc.begin();
      uint32_t ver = nfc.getFirmwareVersion();
      if (!ver) { Serial.println(" No se detecta PN532"); delay(1000); break; }
      Serial.println(" PN532 listo.");
      nfc.SAMConfig();
      state = IDLE;
      break;
    }

    case IDLE: {
      uint8_t uid[7]; uint8_t uidLen = 0;
      if (nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLen)) {
        lastUIDHex = toHexUpper(uid, uidLen);
        Serial.println("UID detectado: " + lastUIDHex);
        state = REQUEST_NONCE;
        stateDeadline = millis() + NONCE_TTL_MS;
      }
      delay(50);
      break;
    }

    case REQUEST_NONCE: {
      if ((int32_t)(millis() - stateDeadline) > 0) { state = WAIT_BACKOFF; break; }
      String url = buildURL(URL_NONCE);
      url += "?uid=" + lastUIDHex;

      http.setTimeout(1500);
      if (!http.begin(url)) { state = WAIT_BACKOFF; break; }

      int code = http.GET();
      if (code == 200) {
        StaticJsonDocument<256> doc;
        if (deserializeJson(doc, http.getString()) == DeserializationError::Ok) {
          sessionId = (const char*)doc["sessionId"];
          nonceHex  = (const char*)doc["nonce"];
          state = POST_VERIFY;
        } else state = WAIT_BACKOFF;
      } else state = WAIT_BACKOFF;
      http.end();
      break;
    }

    case POST_VERIFY: {
      if ((int32_t)(millis() - stateDeadline) > 0) { state = WAIT_BACKOFF; break; }

      String url = buildURL(URL_VERIFY);
      if (!http.begin(url)) { state = WAIT_BACKOFF; break; }
      http.addHeader("Content-Type", "application/json");

      std::vector<uint8_t> uidBytes, nonceBytes, msg;
      if (!hexToBytes(lastUIDHex, uidBytes) || !hexToBytes(nonceHex, nonceBytes)) { state = WAIT_BACKOFF; http.end(); break; }
      msg.insert(msg.end(), uidBytes.begin(), uidBytes.end());
      msg.insert(msg.end(), nonceBytes.begin(), nonceBytes.end());
      String hmacHex = hmacSha256HexBytes(msg.data(), msg.size());

      StaticJsonDocument<256> req;
      req["uid"] = lastUIDHex;
      req["sessionId"] = sessionId;
      req["hmac"] = hmacHex;

      String body; serializeJson(req, body);
      int code = http.POST(body);

      if (code > 0) {
        StaticJsonDocument<256> res;
        if (deserializeJson(res, http.getString()) == DeserializationError::Ok) {
          String result = res["result"] | "";
          String reason = res["reason"] | "";

          if (result == "OK") {
            Serial.println(" ACCESO PERMITIDO");
            state = ACTUATE;
          } else {
            Serial.println(" ACCESO DENEGADO");
            digitalWrite(LED_ROJO, HIGH);
            delay(2000);
            digitalWrite(LED_ROJO, LOW);
            state = WAIT_BACKOFF;
          }
        }
      }
      http.end();
      break;
    }

    case ACTUATE: {
      Serial.println("🔓 ABRIENDO SERVO 3s...");
      servoMotor.write(SERVO_OPEN);
      digitalWrite(LED_VERDE, HIGH);
      delay(3000);
      digitalWrite(LED_VERDE, LOW);
      servoMotor.write(SERVO_CLOSE);
      Serial.println("🔒 CERRADO");
      state = IDLE;
      delay(300);
      break;
    }

    case WAIT_BACKOFF: {
      delay(backoffMs);
      backoffMs = min<uint32_t>(backoffMs * 2, 4000);
      state = IDLE;
      break;
    }
  }
}
