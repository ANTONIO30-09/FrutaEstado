/*
 * Clasificador de Frutas — Firmware ESP32 con WiFi + HTTP
 * Version robusta: LCD opcional, prints tempranos para diagnostico.
 */

#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <ESP32Servo.h>
#include <esp_system.h>
#include <WiFi.h>
#include <WebServer.h>
#include "secrets.h"

// Pon 1 para activar la LCD, 0 para desactivarla
#define USAR_LCD 0
#define USAR_SERVO 0   // 0 = sin servo (falta fuente 5V)
#define USAR_BUZZER 0  // 0 = sin buzzer (falta transistor)

// ===================== PINES =====================
const int LED_VERDE    = 18;
const int LED_AMARILLO = 19;
const int LED_ROJO     = 21;
const int BUZZER_PIN   = 22;
const int SERVO_PIN    = 23;
const int RELE_PIN     = 27;
const int TRIG_PIN     = 5;
const int ECHO_PIN     = 4;
const int LCD_SDA      = 25;
const int LCD_SCL      = 26;

// ===================== HARDWARE =====================
LiquidCrystal_I2C lcd(0x27, 16, 2);
Servo desviador;
WebServer server(80);

bool lcdPresente = false;
uint8_t lcdAddr = 0x27;

// ===================== AJUSTES =====================
const bool RELE_ACTIVO_EN_HIGH = true;
const int ANGULO_BUENA    = 90;
const int ANGULO_INMADURA = 30;
const int ANGULO_MALA     = 150;

const unsigned long DURACION_ALARMA_MS   = 2000;
const unsigned long INTERVALO_SENSOR_MS  = 200;
const unsigned long INTERVALO_LCD_MS     = 250;
const unsigned long TIMEOUT_ACTIVIDAD_MS = 5000;

// ===================== ESTADO GLOBAL =====================
bool modoManual = false;
String estadoActual = "-";
String textoEstado  = "Esperando...";
unsigned long ultimoComandoHttp   = 0;
unsigned long ultimoLCD           = 0;
unsigned long ultimaLecturaSensor = 0;

bool alarmaActiva = false;
unsigned long inicioAlarma = 0;
bool pitidoAnterior = false;

float distanciaCm = -1;

// ===================== HELPERS =====================
void controlarMotor(bool encender) {
  int nivel = RELE_ACTIVO_EN_HIGH ? (encender ? HIGH : LOW)
                                   : (encender ? LOW  : HIGH);
  digitalWrite(RELE_PIN, nivel);
}

void apagarIndicadores() {
  digitalWrite(LED_VERDE, LOW);
  digitalWrite(LED_AMARILLO, LOW);
  digitalWrite(LED_ROJO, LOW);
  noTone(BUZZER_PIN);
  alarmaActiva = false;
  pitidoAnterior = false;
}

void escribirLinea(int fila, const char* texto) {
#if !USAR_LCD
  return;
#else
  if (!lcdPresente) return;
  lcd.setCursor(0, fila);
  int i = 0;
  while (texto[i] != '\0' && i < 16) { lcd.print(texto[i]); i++; }
  while (i < 16) { lcd.print(' '); i++; }
#endif
}

void actualizarBuzzer(unsigned long ahora) {
#if !USAR_BUZZER
  return;
#else
  if (!alarmaActiva) return;
  unsigned long t = ahora - inicioAlarma;
  if (t >= DURACION_ALARMA_MS) {
    noTone(BUZZER_PIN);
    alarmaActiva = false;
    pitidoAnterior = false;
    return;
  }
  bool debeSonar = ((t / 200) % 2 == 0);
  if (debeSonar != pitidoAnterior) {
    pitidoAnterior = debeSonar;
    if (debeSonar) tone(BUZZER_PIN, 2000);
    else           noTone(BUZZER_PIN);
  }
#endif
}

float medirDistancia() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  unsigned long duracion = pulseIn(ECHO_PIN, HIGH, 25000);
  if (duracion == 0) return -1;
  return duracion * 0.0343f / 2.0f;
}

void actualizarSensor(unsigned long ahora) {
  if (ahora - ultimaLecturaSensor < INTERVALO_SENSOR_MS) return;
  ultimaLecturaSensor = ahora;
  distanciaCm = medirDistancia();
}

// ===================== DETECCION LCD =====================
bool i2cResponde(uint8_t addr) {
  Wire.beginTransmission(addr);
  return (Wire.endTransmission() == 0);
}

void detectarLCD() {
  Serial.println("[LCD] Escaneando I2C (timeout corto)...");
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    uint8_t err = Wire.endTransmission();
    if (err == 0) {
      Serial.print("[LCD] Dispositivo en 0x");
      Serial.println(a, HEX);
    }
  }
  Serial.println("[LCD] Scan terminado.");

  // Intentar 0x27, luego 0x3F
  for (uint8_t addr : {(uint8_t)0x27, (uint8_t)0x3F}) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.print("[LCD] Usando 0x");
      Serial.println(addr, HEX);
      lcd = LiquidCrystal_I2C(addr, 16, 2);
      lcd.init();
      lcd.backlight();
      lcdPresente = true;
      return;
    }
  }
  Serial.println("[LCD] No encontrada. Siguiendo sin LCD.");
  lcdPresente = false;
}

// ===================== APLICAR ESTADO =====================
void aplicarEstado(const String& v) {
  apagarIndicadores();

  if (v == "S") {
    digitalWrite(LED_VERDE, HIGH);
#if USAR_SERVO
    desviador.write(ANGULO_BUENA);
#endif
    textoEstado = "Madura / buena";
  } else if (v == "A") {
    digitalWrite(LED_AMARILLO, HIGH);
#if USAR_SERVO
    desviador.write(ANGULO_INMADURA);
#endif
    textoEstado = "Fruta inmadura";
  } else if (v == "R") {
    digitalWrite(LED_ROJO, HIGH);
#if USAR_SERVO
    desviador.write(ANGULO_MALA);
#endif
    textoEstado = "Mala / podrida";
#if USAR_BUZZER
    inicioAlarma = millis();
    alarmaActiva = true;
    pitidoAnterior = false;
#endif
  }

  estadoActual = v;
  ultimoComandoHttp = millis();
}

// ===================== HTTP =====================
void manejarEstado() {
  if (!server.hasArg("valor")) {
    server.send(400, "application/json", "{\"error\":\"falta parametro valor\"}");
    Serial.println("[HTTP] 400 - falta valor");
    return;
  }
  String v = server.arg("valor");
  v.toUpperCase();
  if (v != "S" && v != "A" && v != "R") {
    server.send(400, "application/json", "{\"error\":\"valor invalido\"}");
    Serial.println("[HTTP] 400 - valor invalido: " + v);
    return;
  }
  aplicarEstado(v);
  String resp = "{\"ok\":true,\"estado\":\"" + v + "\"}";
  server.send(200, "application/json", resp);
  Serial.println("[HTTP] 200 - estado: " + v);
}

void manejarNoEncontrado() {
  server.send(404, "application/json", "{\"error\":\"ruta no encontrada\"}");
  Serial.println("[HTTP] 404 - " + server.uri());
}

// ===================== SERIAL =====================
void revisarComandos() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '0' || c == '1') {
      modoManual = true;
      apagarIndicadores();
      bool encender = (c == '1');
      controlarMotor(encender);
      escribirLinea(0, "Prueba del rele");
      escribirLinea(1, encender ? "Motor: encendido" : "Motor: detenido");
      Serial.println(encender ? "Orden: motor encendido"
                              : "Orden: motor detenido");
    } else if (c == 'a' || c == 'A') {
      modoManual = false;
      apagarIndicadores();
      controlarMotor(true);
      estadoActual = "-";
      textoEstado = "Esperando...";
      Serial.println("Modo automatico activado.");
    }
  }
}

// ===================== LCD UPDATE =====================
void actualizarLCD(unsigned long ahora) {
#if !USAR_LCD
  return;
#else
  if (!lcdPresente) return;
  if (modoManual) return;
  if (ahora - ultimoLCD < INTERVALO_LCD_MS) return;
  ultimoLCD = ahora;

  if (estadoActual != "-" && (ahora - ultimoComandoHttp) < TIMEOUT_ACTIVIDAD_MS) {
    char l0[17];
    snprintf(l0, sizeof(l0), "Estado: %s", estadoActual.c_str());
    escribirLinea(0, l0);
    escribirLinea(1, textoEstado.c_str());
    return;
  }

  if (WiFi.status() == WL_CONNECTED) {
    escribirLinea(0, "WiFi OK");
    escribirLinea(1, WiFi.localIP().toString().c_str());
  } else {
    escribirLinea(0, "WiFi...");
    escribirLinea(1, "Desconectado");
  }
#endif
}


// ===================== SELF-TEST =====================
void selfTest() {
  Serial.println("[TEST] Self-test de hardware...");

  Serial.println("[TEST] Servo: sweep 0 -> 180 -> 90");
  for (int a = 0; a <= 180; a += 15) { desviador.write(a); delay(80); }
  for (int a = 180; a >= 90; a -= 15) { desviador.write(a); delay(80); }
  Serial.println("[TEST] Servo: fin (si no se movio -> falta alimentacion 5V externa)");

  Serial.println("[TEST] Buzzer metodo 1: tone(2000Hz) 600ms");
  tone(BUZZER_PIN, 2000);
  delay(600);
  noTone(BUZZER_PIN);
  delay(300);

  Serial.println("[TEST] Buzzer metodo 2: digitalWrite(HIGH) 600ms");
  digitalWrite(BUZZER_PIN, HIGH);
  delay(600);
  digitalWrite(BUZZER_PIN, LOW);
  delay(300);

  Serial.println("[TEST] Si sono con metodo 1 -> buzzer PASIVO");
  Serial.println("[TEST] Si sono con metodo 2 -> buzzer ACTIVO");
  Serial.println("[TEST] Si no sono ninguno -> revisar GPIO 22 y cableado");
}

// ===================== SETUP =====================
void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("=== Clasificador de Frutas ===");
  Serial.println("Boot OK. Inicializando...");

  Serial.println("[PINES] Configurando GPIOs...");
  pinMode(RELE_PIN, OUTPUT);
  controlarMotor(false);
  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_AMARILLO, OUTPUT);
  pinMode(LED_ROJO, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);
  apagarIndicadores();
  Serial.println("[PINES] OK");

#if USAR_LCD
  Serial.println("[LCD] Iniciando bus I2C...");
  Wire.begin(LCD_SDA, LCD_SCL);
  delay(100);
  detectarLCD();
#else
  Serial.println("[LCD] Desactivada por USAR_LCD=0");
#endif

#if USAR_SERVO
  Serial.println("[SERVO] Iniciando...");
  desviador.setPeriodHertz(50);
  desviador.attach(SERVO_PIN, 1000, 2000);
  desviador.write(ANGULO_BUENA);
  Serial.println("[SERVO] OK");
#else
  Serial.println("[SERVO] Desactivado (USAR_SERVO=0)");
#endif

#if USAR_SERVO || USAR_BUZZER
  selfTest();
#else
  Serial.println("[TEST] Self-test desactivado.");
#endif

  randomSeed(esp_random());

  Serial.println("[WIFI] Conectando...");
  Serial.print("[WIFI] SSID: ");
  Serial.println(SECRET_WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(SECRET_WIFI_SSID, SECRET_WIFI_PASS);

  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("[WIFI] OK. IP: ");
    Serial.println(WiFi.localIP());
    escribirLinea(0, "WiFi OK");
    escribirLinea(1, WiFi.localIP().toString().c_str());
  } else {
    Serial.println("[WIFI] FALLO. Modo manual (0/1/a).");
    escribirLinea(0, "WiFi FALLO");
    escribirLinea(1, "Modo manual");
  }

  server.on("/estado", HTTP_GET, manejarEstado);
  server.onNotFound(manejarNoEncontrado);
  server.begin();

  Serial.println("[HTTP] Servidor en puerto 80");
  Serial.println("[HTTP] GET /estado?valor=S|A|R");
  Serial.println("[SERIAL] 0=detener | 1=encender | a=automatico");

  controlarMotor(true);
  Serial.println("=== Listo ===");
}

// ===================== LOOP =====================
void loop() {
  server.handleClient();
  revisarComandos();
  unsigned long ahora = millis();
  actualizarBuzzer(ahora);
  actualizarSensor(ahora);
  actualizarLCD(ahora);
}
