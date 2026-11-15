# Firmware ESP32 — Clasificador de Frutas

Recibe estados desde el pipeline vía HTTP y acciona el hardware:
LEDs, servo desviador, buzzer y relé del motor.

## Contrato HTTP

| Método | Ruta | Respuesta |
|---|---|---|
| `GET` | `/estado?valor=S` | `200 {"ok":true,"estado":"S"}` |
| `GET` | `/estado?valor=A` | `200 {"ok":true,"estado":"A"}` |
| `GET` | `/estado?valor=R` | `200 {"ok":true,"estado":"R"}` |
| `GET` | `/estado` (sin valor) | `400 {"error":"falta parametro valor"}` |
| `GET` | `/estado?valor=X` | `400 {"error":"valor invalido"}` |

## Hardware (pines)

| Componente | GPIO |
|---|---|
| LED Verde (S) | 18 |
| LED Amarillo (A) | 19 |
| LED Rojo (R) | 21 |
| Buzzer | 22 |
| Servo | 23 |
| Relé motor | 27 |
| HC-SR04 TRIG | 5 |
| HC-SR04 ECHO | 4 (divisor 1kΩ/2kΩ) |
| LCD SDA | 25 |
| LCD SCL | 26 |

LCD dirección I2C: `0x27`.

## Compilar y flashear

```bash
cd firmware/esp32_clasificador
cp secrets.h.example secrets.h   # editar con SSID/password reales
pio run                          # compilar
pio run --target upload          # flashear por USB
pio device monitor -b 115200     # ver IP por serial

Comandos seriales (demo de respaldo)
Comando	Acción
0	Detener motor (modo manual)
1	Encender motor (modo manual)
a	Volver a modo automático (HTTP)
Respaldo y restauración
Backup del firmware original guardado en ~/esp32_backups/.

Restaurar (si algo sale mal):
python -m esptool --port /dev/ttyUSB0 write-flash 0x0 \
  ~/esp32_backups/esp32_backup_20261012_1457.bin
