# PROGRESS — FrutaEstado

Bitácora del estado del proyecto. Se actualiza al cierre de cada sesión de trabajo.

**Última actualización:** Semana 2 cerrada — comenzando Semana 3

---

## Estado actual

**Fase:** Semana 3 — Dashboard Flask + SQLite + Chart.js
**Progreso global:** ~40% (pipeline de visión + envío ESP32 listo y testeado; falta dashboard)

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
- [x] Implementación de la clasificación HSV según contrato (`src/clasificador.py`)
  - [x] ROI central (25%, 20%, 50%, 60% relativos)
  - [x] Filtro de píxeles: S >= 50 y V >= 30
  - [x] Verde (inmadura): 35 <= H <= 85
  - [x] Madura: H <= 35 o H >= 160, con V >= 110 y S >= 80
  - [x] Pasada: H <= 25 y V < 110
  - [x] Filtro de mayoría sobre los últimos 7 cuadros
- [x] Cliente HTTP al ESP32 (`src/cliente_esp32.py`) con timeout 1 s y manejo silencioso de errores
- [x] Script principal (`src/main.py`) con heartbeat exacto de 1 Hz
- [x] Tests pytest: 29 pasando (config, captura, clasificador, cliente ESP32)
- [x] Demos manuales ejecutados sin errores (`src.captura`, `src.clasificador`, `src.main`)
- [x] PR de `dev` a `main` mergeado (PR #5)

---

## Pendiente

### Semana 3 — Dashboard Flask + SQLite
- [x] Modelo SQLite (tabla `registros`: id, estado, pct_verde, pct_madura, pct_pasada, timestamp)
- [x] API Flask: `GET /`, `POST /api/registro`, `GET /api/resumen`
- [x] Frontend con Chart.js (conteos por estado + serie por minuto + últimos 10 registros)
- [ ] Tests pytest de endpoints Flask
- [x] Integración desde `src/main.py`: `POST /api/registro` cuando el estado cambia

### Semana 4 — Integración ESP32 + precisión
- [x] Columna `tipo_fruta` en `registros` con migracion idempotente
- [x] Columna `tipo_fruta` en `registros` con migracion idempotente
- [ ] Prueba end-to-end con ESP32 real (compañero de hardware)
- [ ] Pruebas de precisión con frutas reales — ajustar umbrales HSV si hace falta

### Semana 5 — Cierre
- [ ] Documentación final
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

---

## Próximos pasos inmediatos

1. **S3.1** — Modelo SQLite + `init_db` idempotente.
2. **S3.2** — API Flask con los 3 endpoints del contrato.
3. **S3.3** — Integración desde `src/main.py` (POST solo cuando cambia el estado).
4. **S3.4** — Frontend Chart.js (conteos, serie por minuto, últimos 10).
5. **S3.5** — Tests de endpoints Flask.

---

## Notas operativas

- El warning `QFontDatabase: Cannot find font directory` de `opencv-python` en Linux es inofensivo; no afecta la funcionalidad.
- `python -m src.main` con el ESP32 apagado muestra `FAIL: N` creciente — comportamiento esperado y documentado.
