# Decisiones técnicas — FrutaEstado

Registro de las decisiones relevantes del proyecto, con su justificación.

---

## D-001: Clasificación por reglas HSV en lugar de YOLO/CNN

**Fecha:** Semana 1
**Estado:** Aceptada

### Contexto

El proyecto requiere clasificar frutas en tres estados (inmadura, madura, pasada) usando la cámara de un celular como fuente de video en tiempo real, con una laptop común como única unidad de procesamiento. El resultado debe enviarse a un ESP32 cada segundo.

### Opciones consideradas

1. **Red neuronal (YOLO / CNN)** entrenada sobre un dataset de frutas en distintos estados de madurez.
2. **Reglas de umbral en espacio de color HSV** aplicadas sobre una ROI central de la imagen.

### Decisión

**Opción 2 — Reglas HSV.**

### Justificación

- **Costo computacional:** las reglas HSV se ejecutan en milisegundos por frame en CPU. Un modelo CNN/YOLO requeriría GPU o un CPU potente para sostener tiempo real a 30 FPS, lo cual no está garantizado en la laptop del equipo ni en el entorno de la demo en la universidad.
- **Latencia y requisito de 1 Hz:** el sistema debe enviar un estado al ESP32 cada segundo. Con HSV esto es trivial; con una CNN habría riesgo de perder frames y no cumplir el heartbeat.
- **Sin dataset público disponible:** no existe un dataset libre etiquetado específicamente con estas tres clases y estas condiciones de iluminación. Entrenar desde cero implicaría recolectar y etiquetar cientos de imágenes — fuera del tiempo del proyecto (5 semanas).
- **Explicabilidad:** las reglas HSV son inspeccionables. Si la clasificación falla, se puede depurar mirando histogramas H/S/V; una CNN es una caja negra y consumiría tiempo del equipo en depuración.
- **Escala del problema:** tres clases, un solo objeto por frame, fondo relativamente controlado. No se justifica la complejidad de una red neuronal para un problema con esta estructura.

### Consecuencias

- El sistema será sensible a iluminación. **Mitigación:** ROI fija y umbrales calibrados en las condiciones reales de la demo (aula con luz artificial). Se documentará un procedimiento corto de recalibración.
- No se podrá generalizar a otras frutas sin recalibrar umbrales. **Aceptable:** el alcance del proyecto es una fruta objetivo (a definir con el equipo de hardware).
- El filtro de mayoría sobre los últimos 7 cuadros mitiga el parpadeo (falsos positivos puntuales por ruido).

---

## D-002: Registro en base de datos solo cuando cambia el estado

**Fecha:** Semana 1
**Estado:** Aceptada

### Contexto

El script envía un heartbeat al ESP32 cada 1 segundo, pero el estado solo cambia cuando el usuario cambia la fruta o esta madura visiblemente.

### Decisión

Al dashboard (`POST /api/registro`) solo se envía una fila **cuando el estado cambia**, no en cada heartbeat.

### Justificación

- Con 1 Hz, registrar todo generaría 3600 filas por hora de estados idénticos, inflando la DB y volviendo ilegible la gráfica.
- Las métricas del dashboard (conteos por estado, serie por minuto) pierden sentido si se cuentan heartbeats en lugar de eventos reales.
- El ESP32 **sí** recibe heartbeats cada segundo (así lo exige el contrato de hardware), pero eso es independiente de lo que se persiste.

---

## D-003: IPs del ESP32 y de la cámara en `.env`

**Fecha:** Semana 1
**Estado:** Aceptada

### Contexto

La IP del ESP32 la asigna el router por DHCP y puede cambiar entre la casa y la universidad. La URL del stream del celular también varía según la red.

### Decisión

Ambas IPs (y la URL completa del stream) se leen desde variables de entorno cargadas con `python-dotenv`, con un archivo `.env` local **fuera del control de versiones**.

### Justificación

- Evita hardcodear IPs en medio del código (regla explícita del proyecto).
- El `.env.example` versionado documenta las variables sin exponer valores reales.
- Cambiar de red no requiere tocar código, solo el `.env`.
