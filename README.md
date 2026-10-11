# FrutaEstado

Sistema de visión artificial que clasifica frutas en **inmadura**, **madura** o **pasada** usando la cámara de un celular (OpenCV + HSV), envía el resultado por HTTP a un ESP32 y muestra estadísticas en un dashboard web con Flask + SQLite + Chart.js.

Proyecto académico de la asignatura **Microprocesadores y Microcontroladores (MMI-611)** — Ingeniería de Sistemas, 6to semestre.

## Arquitectura

~~~
[Celular con DroidCam / IP Webcam]
        |  stream MJPEG por WiFi
        v
[Script Python: OpenCV + HSV]
        |
        |--> Clasifica: S (madura) / A (inmadura) / R (pasada)
        |
        |--> GET http://<ESP32_IP>/estado?valor=S|A|R
        |
        |--> POST /api/registro  (dashboard)
        v
[Dashboard Flask + SQLite + Chart.js]
~~~

## Stack

- **Visión:** Python 3, OpenCV, NumPy
- **Dashboard:** Flask, SQLite, Chart.js
- **Cliente HTTP:** Requests
- **Fuente de video:** DroidCam o IP Webcam (app móvil, stream MJPEG por WiFi)
- **Hardware (externo):** ESP32 (LEDs, buzzer, servo) — desarrollado por otro miembro del equipo

## Estructura del repositorio

~~~
.
├── src/                 # Script Python de visión y clasificación HSV
├── dashboard/           # API Flask + templates + estáticos
│   ├── templates/
│   └── static/js/
├── tests/               # Tests pytest
├── docs/                # Documentación técnica y decisiones
├── data/                # Datos locales (gitignored)
├── .env.example         # Plantilla de variables de entorno
├── requirements.txt
├── PROGRESS.md          # Estado actual del proyecto
└── README.md
~~~

## Instalación

~~~
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # editar con las IPs reales
~~~

## Uso

_(se documentará al completar los hitos de la Semana 2 y 3)_

## Hitos

1. **Semana 1** — estructura del repo, `.gitignore`, README, PROGRESS.md ✅
2. **Semana 2** — script de captura + clasificación HSV básica
3. **Semana 3** — dashboard Flask + SQLite + Chart.js
4. **Semana 4** — integración HTTP con ESP32 + pruebas de precisión
5. **Semana 5** — documentación, tests, demo final

## Documentación

- [Decisiones técnicas](docs/decisiones.md)
- Estado del proyecto: [`PROGRESS.md`](PROGRESS.md)

## Fuera de alcance

- App móvil nativa (se usa DroidCam / IP Webcam)
- Redes neuronales (YOLO / CNN) — solo HSV
- Firmware del ESP32 (responsabilidad del compañero de hardware)
- Hosting en la nube — todo local
- Autenticación de usuarios
- Bases de datos externas
