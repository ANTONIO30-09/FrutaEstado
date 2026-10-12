# PROGRESS — FrutaEstado

Bitácora del estado del proyecto. Se actualiza al cierre de cada sesión de trabajo.

**Última actualización:** Sesión de rediseño visual del dashboard cerrada — listo para integrar a `dev`

---

## Estado actual

**Fase:** Semana 5 — Rediseño visual y cierre UI
**Progreso global:** ~65% (pipeline + dashboard funcionales; pendiente prueba end-to-end con ESP32 real y documentación final)

---

## Completado

### Semana 1 — Setup
- [x] Repositorio en GitHub (`ANTONIO30-09/FrutaEstado`)
- [x] Estructura de carpetas (`src/`, `dashboard/`, `tests/`, `docs/`, `data/`)
- [x] `.gitignore` robusto
- [x] `.env.example` con variables de entorno
- [x] `README.md`, `PROGRESS.md`, `requirements.txt`, `docs/decisiones.md`
- [x] Rama `dev` creada y `main` protegida en GitHub

### Semana 2 — Visión + envío ESP32
- [x] Script de captura del stream MJPEG (`src/captura.py`)
- [x] Clasificación HSV según contrato (`src/clasificador.py`)
- [x] Cliente HTTP al ESP32 (`src/cliente_esp32.py`) con timeout 1 s y manejo silencioso de errores
- [x] Script principal (`src/main.py`) con heartbeat exacto de 1 Hz
- [x] Tests pytest de config, captura, clasificador y cliente ESP32
- [x] PR de `dev` a `main` mergeado (PR #5)

### Semana 3 — Dashboard Flask + SQLite
- [x] Modelo SQLite (tabla `registros`: id, estado, pct_verde, pct_madura, pct_pasada, timestamp)
- [x] API Flask: `GET /`, `POST /api/registro`, `GET /api/resumen`
- [x] Frontend con Chart.js (conteos por estado + serie por minuto + últimos 10 registros)
- [x] Tests pytest de endpoints Flask
- [x] Integración desde `src/main.py`: `POST /api/registro` cuando el estado cambia

### Semana 4 — Integración ESP32 + precisión
- [x] Columna `tipo_fruta` en `registros` con migración idempotente
- [x] Perfiles HSV por fruta (`src/perfiles_frutas.py`) con soporte para agregar frutas via JSON
- [x] 6 perfiles calibrados desde tablas HSV públicas (`config/perfiles_custom.json`)
- [x] Reorden del clasificador: pasada -> verde -> madura
- [x] Selector de fruta en el dashboard con hot-swap del perfil en el pipeline
- [x] API: endpoints `/api/perfil` (GET/POST) y `/api/perfiles`
- [x] Filtro por `tipo_fruta` en `/api/resumen`
- [x] Mock del ESP32 (`tools/mock_esp32.py`) para desarrollo sin hardware

### Semana 5 — Rediseño visual y cierre UI (rama `feat/rediseno-visual`)
- [x] Rediseño completo del dashboard con estética "glass" (blur + transparencias)
- [x] Fondo fotográfico de pasto cargado por URL externa
- [x] Layout grid full-height con paneles estirados (resumen izquierda, gráfica derecha)
- [x] Gauge SVG circular con 3 arcos (S/A/R) sin solapamiento visual
- [x] Selector de fruta sin opción "Genérico" (evita confusión UX)
- [x] Imágenes PNG con transparencia real para 6 frutas + frutero (7 assets locales)
- [x] Iluminación tipo sol superior-izquierda + halo cálido sobre cada fruta
- [x] Sombras de dos capas (contacto + ambiental) sobre frutas y frutero
- [x] Panel flotante de "Últimos registros" con toggle desde botón inferior
- [x] Polling del perfil activo cada 2 s para hot-swap sin reiniciar `src/main.py`
- [x] Flask con `debug=False` + `use_reloader=False` en `app.py` y `run.py`
- [x] 134 tests pasando tras el rediseño

### Pendiente (Semana 5 — Cierre)
- [ ] Prueba end-to-end con ESP32 real (compañero de hardware)
- [ ] Pruebas de precisión con frutas reales — ajustar umbrales HSV si hace falta
- [ ] Documentación final (`README.md` extendido, `docs/decisiones.md`)
- [ ] Demo en vivo
- [ ] Informe .docx

---

## Decisiones técnicas tomadas

| Fecha | Decisión | Motivo |
|-------|----------|--------|
| S1 | Clasificación por HSV en lugar de YOLO/CNN | Costo computacional bajo, tiempo real en laptop común, simplicidad, sin dataset. Ver `docs/decisiones.md`. |
| S1 | Bootstrap directo a `main` en el primer commit | No existía aún rama `dev` desde la cual partir. Excepción única. |
| S1 | Registro en DB solo cuando cambia el estado | Evitar inflar la tabla con heartbeats idénticos (1 Hz). |
| S1 | IPs en `.env`, no hardcodeadas | Seguridad y portabilidad entre entornos (casa / universidad). |
| S2 | Heartbeat al ESP32 medido con `time.monotonic()` en lugar de `sleep(1)` | Garantiza cadencia exacta de 1 s incluso si el procesamiento de frames varía. |
| S2 | `enviar_estado` nunca lanza excepciones hacia arriba | El script de visión no debe caerse si el ESP32 se apaga o la red falla. Devuelve `False` y se contabiliza como FAIL. |
| S2 | Uso de webcam de laptop para desarrollo y hotspot del iPhone para demo | Las redes WiFi institucionales aíslan dispositivos (AP isolation), rompiendo la conexión celular ↔ laptop. |
| S2 | `conftest.py` en la raíz agrega el proyecto a `sys.path` | Permite importar `from src.X import Y` en los tests sin instalar el paquete. |
| S3 | Factory `crear_app(db_path=None)` en Flask | Permite inyectar una DB temporal en tests sin tocar `data/frutas.db`. |
| S3 | `POST /api/registro` valida estado y porcentajes antes de insertar | Nunca se corrompe la tabla con datos basura incluso si llega HTTP malformado. |
| S4 | Columna `tipo_fruta` con migración idempotente en `init_db` | Permite agregar la columna a DBs existentes sin perder datos. |
| S5 | Imágenes de frutas como PNG locales en `dashboard/static/img/frutas/` | Offline-ready: la demo no depende de URLs externas. Fondos procesados con remove.bg + ImageMagick. |
| S5 | Flask con `debug=False` y `use_reloader=False` en `app.py` y `run.py` | El reloader reiniciaba el server en cada guardado y perdía el perfil activo. Crítico para demos en vivo. |
| S5 | Polling de `/api/perfil` cada 2 s desde `src/main.py` | Permite hot-swap del perfil de fruta sin reiniciar el script de visión. |

---

## Próximos pasos inmediatos

1. **PR de `feat/rediseno-visual` hacia `dev`** (base = `dev`, NO `main`).
2. **Mergear el PR** una vez verificado.
3. **Borrar la rama `feat/rediseno-visual`** (local y remota) tras el merge.
4. **Prueba end-to-end con ESP32 real** cuando el compañero lo tenga listo.
5. **Ajustar umbrales HSV** si la clasificación real falla con frutas físicas.
6. **Documentación final** (`README.md` extendido + `docs/decisiones.md`).
7. **Preparar demo en vivo** e **informe .docx**.

---

## Notas operativas

- El warning `QFontDatabase: Cannot find font directory` de `opencv-python` en Linux es inofensivo; no afecta la funcionalidad.
- `python -m src.main` con el ESP32 apagado muestra `FAIL: N` creciente — comportamiento esperado y documentado.
- Los PNG de frutas fueron procesados con `remove.bg` (fondo quitado) y verificados con Pillow (canal alfa real).
- El dashboard arranca con `python run.py` (no `python -m dashboard.app` ni `flask run`) para mantener un único entry point consistente.
