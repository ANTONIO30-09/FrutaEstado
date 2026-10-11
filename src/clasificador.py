"""Clasificación HSV de madurez de frutas.

Reglas definidas en el contrato del proyecto (NO cambiar sin justificar):
- ROI central (25%, 20%, 50%, 60% relativos).
- Filtro de fruta: S >= 50 y V >= 30.
- Verde (inmadura): 35 <= H <= 85.
- Madura: H <= 35 o H >= 160, con V >= 110 y S >= 80.
- Pasada: H <= 25 y V < 110.
- Filtro de mayoría sobre los últimos 7 cuadros.

OpenCV usa H en rango 0-179, S y V en rango 0-255.
"""

from __future__ import annotations

import sys
from collections import Counter, deque
from dataclasses import dataclass

import cv2
import numpy as np

from src.captura import CapturaVideo
from src.config import Config, cargar_config

# --- ROI central: (x_rel, y_rel, ancho_rel, alto_rel) ---
ROI_REL = (0.25, 0.20, 0.50, 0.60)

# --- Filtro de fruta ---
S_MIN_FRUTA = 50
V_MIN_FRUTA = 30

# --- Verde (inmadura) ---
H_VERDE_MIN = 35
H_VERDE_MAX = 85

# --- Madura ---
H_MADURA_MAX_BAJO = 35
H_MADURA_MIN_ALTO = 160
V_MADURA_MIN = 110
S_MADURA_MIN = 80

# --- Pasada ---
H_PASADA_MAX = 25
V_PASADA_MAX = 110

# --- Filtro de mayoría ---
VENTANA_MAYORIA = 7


@dataclass(frozen=True)
class ResultadoClasificacion:
    """Resultado de clasificar un frame.

    estado: 'S' (madura), 'A' (inmadura), 'R' (pasada) o None si no hay fruta.
    Los porcentajes están normalizados sobre los píxeles clasificados.
    """

    estado: str | None
    pct_verde: float
    pct_madura: float
    pct_pasada: float
    pixeles_fruta: int


def _extraer_roi(frame: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """Recorta la ROI central del frame.

    Devuelve (roi, (x0, y0, x1, y1)) para poder dibujar el rectángulo luego.
    """
    alto, ancho = frame.shape[:2]
    x_rel, y_rel, w_rel, h_rel = ROI_REL
    x0 = int(ancho * x_rel)
    y0 = int(alto * y_rel)
    x1 = x0 + int(ancho * w_rel)
    y1 = y0 + int(alto * h_rel)
    return frame[y0:y1, x0:x1], (x0, y0, x1, y1)


def clasificar_frame(frame: np.ndarray) -> ResultadoClasificacion:
    """Clasifica un frame BGR y devuelve el resultado por mayoría de píxeles."""
    roi, _ = _extraer_roi(frame)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    h = hsv[:, :, 0].astype(np.int16)
    s = hsv[:, :, 1].astype(np.int16)
    v = hsv[:, :, 2].astype(np.int16)

    mascara_fruta = (s >= S_MIN_FRUTA) & (v >= V_MIN_FRUTA)
    total_fruta = int(mascara_fruta.sum())

    if total_fruta == 0:
        return ResultadoClasificacion(None, 0.0, 0.0, 0.0, 0)

    # Madura (primero: es la condición más específica y con más restricciones)
    es_madura = (
        ((h <= H_MADURA_MAX_BAJO) | (h >= H_MADURA_MIN_ALTO))
        & (v >= V_MADURA_MIN)
        & (s >= S_MADURA_MIN)
        & mascara_fruta
    )

    # Verde (excluyente con madura)
    es_verde = (
        (h >= H_VERDE_MIN)
        & (h <= H_VERDE_MAX)
        & mascara_fruta
        & ~es_madura
    )

    # Pasada (excluyente con las anteriores)
    es_pasada = (
        (h <= H_PASADA_MAX)
        & (v < V_PASADA_MAX)
        & mascara_fruta
        & ~es_madura
        & ~es_verde
    )

    n_verde = int(es_verde.sum())
    n_madura = int(es_madura.sum())
    n_pasada = int(es_pasada.sum())
    total_clasificado = n_verde + n_madura + n_pasada

    if total_clasificado == 0:
        return ResultadoClasificacion(None, 0.0, 0.0, 0.0, total_fruta)

    pct_verde = 100.0 * n_verde / total_clasificado
    pct_madura = 100.0 * n_madura / total_clasificado
    pct_pasada = 100.0 * n_pasada / total_clasificado

    # Estado por mayoría. Empates: prioriza S, luego A, luego R.
    if n_madura >= n_verde and n_madura >= n_pasada:
        estado = "S"
    elif n_verde >= n_pasada:
        estado = "A"
    else:
        estado = "R"

    return ResultadoClasificacion(
        estado, pct_verde, pct_madura, pct_pasada, total_fruta
    )


class FiltroMayoria:
    """Suaviza el estado entre frames usando los últimos N resultados.

    Los valores None (sin fruta) se ignoran y no entran al buffer.
    """

    def __init__(self, ventana: int = VENTANA_MAYORIA):
        self.ventana = ventana
        self._buffer: deque[str] = deque(maxlen=ventana)

    def actualizar(self, estado: str | None) -> str | None:
        if estado is not None:
            self._buffer.append(estado)
        return self.estado_actual()

    def estado_actual(self) -> str | None:
        if not self._buffer:
            return None
        conteo = Counter(self._buffer)
        return conteo.most_common(1)[0][0]

    def reset(self) -> None:
        self._buffer.clear()


def _dibujar_overlay(
    frame: np.ndarray, resultado: ResultadoClasificacion, estado_filtrado: str | None
) -> None:
    _, (x0, y0, x1, y1) = _extraer_roi(frame)
    cv2.rectangle(frame, (x0, y0), (x1, y1), (255, 255, 0), 2)

    colores = {"S": (0, 0, 255), "A": (0, 255, 0), "R": (0, 165, 255)}
    texto_estado = estado_filtrado if estado_filtrado else "-"
    color = colores.get(texto_estado, (255, 255, 255))

    cv2.putText(
        frame,
        f"Estado: {texto_estado}",
        (10, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        color,
        2,
    )
    cv2.putText(
        frame,
        f"A:{resultado.pct_verde:5.1f}%  "
        f"S:{resultado.pct_madura:5.1f}%  "
        f"R:{resultado.pct_pasada:5.1f}%",
        (10, 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        1,
    )
    cv2.putText(
        frame,
        f"Pixeles fruta: {resultado.pixeles_fruta}",
        (10, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (200, 200, 200),
        1,
    )


def _demo(config: Config) -> int:
    """Demo: muestra la webcam/stream con el estado clasificado en pantalla."""
    try:
        captura = CapturaVideo(config.cam_url)
        captura.abrir()
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    filtro = FiltroMayoria()
    print("Clasificación iniciada. Presiona 'q' en la ventana para salir.")

    try:
        while True:
            frame = captura.leer_frame()
            if frame is None:
                continue

            resultado = clasificar_frame(frame)
            estado_filtrado = filtro.actualizar(resultado.estado)
            _dibujar_overlay(frame, resultado, estado_filtrado)

            cv2.imshow("FrutaEstado - Clasificacion", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        captura.cerrar()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    sys.exit(_demo(cargar_config()))
