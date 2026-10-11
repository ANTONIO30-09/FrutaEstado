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

### Probar la captura de video

Antes de cualquier clasificación, se puede verificar que la fuente de video llega bien:

~~~bash
python -m src.captura
~~~

Esto abre una ventana con los frames en vivo y muestra los FPS en la esquina superior izquierda. Se cierra con la tecla `q`.

**Dos modos de `CAM_URL` en `.env`:**

- **Desarrollo (webcam de la laptop):**
  ~~~
  CAM_URL=0
  ~~~
- **Demo (celular con DroidCam por el hotspot del iPhone):**
  ~~~
  CAM_URL=http://<IP-DEL-IPHONE>:4747/video
  ~~~

> **Nota sobre la red en la universidad:** las redes WiFi institucionales suelen aislar a los dispositivos entre sí (AP isolation), por lo que el celular y la laptop no se verán aunque estén "en la misma red". Para la demo se recomienda activar el punto de acceso personal del iPhone y conectar la laptop (y el ESP32) a ese hotspot.

### Probar la clasificación HSV

Una vez verificada la captura, se puede probar el clasificador en vivo:

~~~bash
python -m src.clasificador
~~~

Muestra la ventana con el rectángulo de la ROI, el estado detectado (S/A/R o `-`), los porcentajes de píxeles verdes/maduros/pasados y el total de píxeles de fruta. Se cierra con `q`.

**Reglas de clasificación (contrato del proyecto):**

- ROI central: 25% horizontal, 20% vertical, 50% ancho, 60% alto.
- Filtro de fruta: S >= 50 y V >= 30.
- Verde (inmadura, `A`): 35 <= H <= 85.
- Madura (`S`): H <= 35 o H >= 160, con V >= 110 y S >= 80.
- Pasada (`R`): H <= 25 y V < 110.
- Filtro de mayoría sobre los últimos 7 cuadros para evitar parpadeos.

### Ejecutar el sistema completo

Con la captura y la clasificación verificadas, se levanta el pipeline completo:

~~~bash
python -m src.main
~~~

Esto abre la ventana con la ROI, el estado clasificado en vivo, los porcentajes de píxeles y el estado del enlace con el ESP32 (contadores OK/FAIL y timestamp del último envío exitoso). Se cierra con `q`.

**Comportamiento del heartbeat:**

- El clasificador corre a la velocidad que le permita la cámara.
- El envío al ESP32 (`GET /estado?valor=S|A|R`) se dispara **exactamente cada 1 segundo**, independientemente de los FPS de captura.
- Si el ESP32 no responde (apagado, timeout, IP mal configurada), el script **no se cae**: muestra `ESP32: FAIL` en pantalla y sigue clasificando.
- Si el estado filtrado es `None` (no hay fruta en la ROI), no se envía nada al ESP32 hasta que aparezca una fruta.

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
