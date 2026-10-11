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

### Base de datos (Semana 3)

El dashboard (Semana 3) usa SQLite local. La base de datos se crea automáticamente al arrancar el dashboard en la ruta definida por `DB_PATH` en `.env` (por defecto `data/frutas.db`). Esa ruta está en `.gitignore` — la base **no se sube al repositorio**.

Esquema de la tabla `registros`:

| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | INTEGER | PK autoincremental |
| `estado` | TEXT | CHECK en ('S', 'A', 'R') |
| `pct_verde` | REAL | Porcentaje de píxeles verdes en la ROI |
| `pct_madura` | REAL | Porcentaje de píxeles maduros |
| `pct_pasada` | REAL | Porcentaje de píxeles pasados |
| `tipo_fruta` | TEXT | Tipo de fruta (default: 'desconocida') |

### Perfiles HSV por tipo de fruta

El clasificador soporta umbrales HSV especificos por fruta. El perfil activo se define en `.env` con `PERFIL_FRUTA=<nombre>` y se aplica en el pipeline.

**Perfiles incluidos:**

| Perfil | Fruta | Notas |
|--------|-------|-------|
| `default` | Generico | Contrato original del proyecto, sin cambios |
| `platano` | Platano | Amarillo maduro |
| `mandarina` | Mandarina | Naranja maduro |
| `manzana_verde` | Manzana verde | Verde-amarillento maduro |
| `manzana_roja` | Manzana roja | Rojo maduro |
| `uva_verde` | Uva verde | Verde claro maduro |
| `uva_morada` | Uva morada | Morado maduro |

**Agregar un perfil nuevo sin tocar codigo** — edita `config/perfiles_custom.json`:

~~~json
{
  "pera": {
    "h_madura_max_bajo": 30,
    "s_madura_min": 70,
    "v_madura_min": 100
  }
}
~~~

Los campos no especificados toman los valores del contrato original. El perfil queda disponible en `.env` con `PERFIL_FRUTA=pera`.

**Origen de los valores:**

Los perfiles built-in (en `src/perfiles_frutas.py`) son puntos de partida teoricos. Los perfiles de `config/perfiles_custom.json` fueron calibrados a partir de tablas HSV publicas para: platano, mandarina, manzana verde, manzana roja, uva verde, uva morada. Se recomienda recalibrar con las frutas y la iluminacion reales del entorno de la demo.

**Cambiar de perfil sin reiniciar el dashboard:**

~~~bash
# Editar .env y cambiar PERFIL_FRUTA
# Reiniciar solo el pipeline (no el dashboard)
python -m src.main
~~~
| `timestamp` | TEXT | ISO en hora local |

### Arrancar el dashboard

~~~bash
python run.py
~~~

Abre `http://localhost:5000/` en el navegador. La primera vez crea automáticamente la base `data/frutas.db` (ignorada por git) y sirve un placeholder que consulta `/api/resumen`.

**Endpoints de la API:**

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET  | `/`             | Página del dashboard (placeholder hasta S3.4) |
| POST | `/api/registro` | Inserta una fila. Body: `{estado, pct_verde, pct_madura, pct_pasada}` |
| GET  | `/api/resumen`  | Devuelve `{conteos, serie_por_minuto, ultimos}` |
| GET  | `/api/perfil`   | Devuelve el perfil activo del pipeline |
| POST | `/api/perfil`   | Cambia el perfil activo (`{"perfil":"platano"}`) |
| GET  | `/api/perfiles` | Lista todos los perfiles disponibles |

### Ejecutar el pipeline completo con dashboard

Para que `src/main.py` registre los cambios de estado en la base de datos, el dashboard debe estar corriendo en otra terminal:

~~~bash
# Terminal 1: dashboard
python run.py

# Terminal 2: pipeline de visión
python -m src.main
~~~

Cuando la fruta cambia de estado (por ejemplo, de inmadura a madura), `src/main.py` hace `POST /api/registro` con el estado y los porcentajes. La ventana del pipeline muestra los contadores `DASH: OK:X FAIL:Y` — si el dashboard no está corriendo, verás `FAIL` subir pero el pipeline sigue funcionando sin caerse.

### Panel visual (Chart.js)

El dashboard se compone de cuatro bloques:

1. **Contadores grandes** — totales por estado (S/A/R) y total general.
2. **Doughnut** — distribución de registros por estado.
3. **Línea temporal** — registros agrupados por minuto durante la última hora.
4. **Tabla** — últimos 10 registros con hora, estado y porcentajes.

Se actualiza automáticamente cada **6 segundos** consultando `GET /api/resumen` (sin recargar la página). Chart.js se incluye localmente en `dashboard/static/js/chart.umd.min.js`, sin depender de CDN.

**Abrir el dashboard desde el celular** (misma red WiFi que la laptop):

~~~
http://<IP-DE-LA-LAPTOP>:5000/
~~~

La IP la puedes ver con `hostname -I` o `ip a`.

### Cambiar de fruta desde el dashboard

El dashboard incluye un selector arriba a la derecha. Al elegir una fruta:

1. El selector filtra las gráficas y la tabla (solo muestra registros de esa fruta).
2. El dashboard hace `POST /api/perfil` para cambiar el perfil activo.
3. El pipeline (`python -m src.main`) consulta el perfil cada 2 segundos y lo aplica en caliente, **sin reiniciar el script**.

Con "Ver todos" seleccionado, se muestran todas las frutas sin filtro y el pipeline mantiene el perfil actual.

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
