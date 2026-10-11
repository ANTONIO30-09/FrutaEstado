# PROGRESS — FrutaEstado

Bitácora del estado del proyecto. Se actualiza al cierre de cada sesión de trabajo.

**Última actualización:** Semana 1 — Hito 5

---

## Estado actual

**Fase:** Semana 1 — Setup inicial del repositorio
**Progreso global:** ~10% (estructura lista, sin código funcional aún)

---

## Completado

### Semana 1
- [x] Creación del repositorio en GitHub (`ANTONIO30-09/FrutaEstado`)
- [x] Estructura de carpetas (`src/`, `dashboard/`, `tests/`, `docs/`, `data/`)
- [x] `.gitignore` robusto (Python + venv + `.env` + `*.db` + capturas + IDE)
- [x] `.env.example` con variables: ESP32, cámara, Flask, DB
- [x] `README.md` inicial con arquitectura y stack
- [x] `PROGRESS.md` (este archivo)
- [x] `requirements.txt` con dependencias base
- [x] `docs/decisiones.md` con justificación HSV vs YOLO/CNN
- [x] Rama `dev` creada y `main` protegida en GitHub

---

## Pendiente

### Semana 2 — Script de visión + clasificación HSV
- [x] Script de captura del stream MJPEG (`CAM_URL` del `.env`)
- [ ] Implementación de la clasificación HSV según contrato:
  - ROI central (25%, 20%, 50%, 60% relativos)
  - Filtro de píxeles: S >= 50 y V >= 30
  - Verde (inmadura): 35 <= H <= 85
  - Madura: H <= 35 o H >= 160, con V >= 110 y S >= 80
  - Pasada: H <= 25 y V < 110
  - Filtro de mayoría sobre los últimos 7 cuadros
- [ ] Script de envío HTTP al ESP32 (`GET /estado?valor=S|A|R`), heartbeat cada 1 s
- [ ] Registro en dashboard solo cuando cambia el estado
- [ ] Tests pytest de la función de clasificación HSV con frames de prueba

### Semana 3 — Dashboard Flask + SQLite
- [ ] API Flask: `GET /`, `POST /api/registro`, `GET /api/resumen`
- [ ] Modelo SQLite (tabla de registros: estado, pct_verde, pct_madura, pct_pasada, timestamp)
- [ ] Frontend con Chart.js (conteos por estado + serie por minuto + últimos 10 registros)
- [ ] Tests pytest de endpoints Flask

### Semana 4 — Integración ESP32
- [ ] Prueba end-to-end con ESP32 real
- [ ] Pruebas de precisión con frutas reales
- [ ] Mock de `requests` en tests del cliente HTTP

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

---

## Próximos pasos inmediatos

1. Crear `.env` real a partir de `.env.example` con las IPs del entorno de desarrollo.
2. Verificar que `python -m py_compile` corra sin errores sobre cualquier script nuevo.
3. Arrancar Semana 2: script de captura desde `CAM_URL` (validar primero que el stream MJPEG llega correctamente antes de la lógica HSV).
