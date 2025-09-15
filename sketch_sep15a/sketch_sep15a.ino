#include <WiFi.h>
#include <HTTPClient.h>

const char* ssid = "ALVAREZ";
const char* password = "CAMILO2003";

// Dirección de tu servidor FastAPI
const char* serverName = "http://192.168.1.7:8000/test"; // cambia por tu IP local

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);

  Serial.print("Conectando a WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ Conectado a WiFi");

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverName); 
    int httpResponseCode = http.GET();

    if (httpResponseCode > 0) {
      Serial.print("Código respuesta HTTP: ");
      Serial.println(httpResponseCode);
      String payload = http.getString();
      Serial.println("Respuesta del servidor: " + payload);
    } else {
      Serial.print("Error en la conexión HTTP, código: ");
      Serial.println(httpResponseCode);
    }
    http.end();
  }
}

void loop() {
  // nada, solo prueba de conexión
}
