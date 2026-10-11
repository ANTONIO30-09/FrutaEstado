"""Clasificacion HSV de madurez de frutas con perfiles por tipo.

Acepta un `PerfilFruta` opcional. Si no se pasa, usa el perfil `default`,
que reproduce EXACTAMENTE el contrato original del proyecto (mismos umbrales,
misma ROI, misma ventana de mayoria). Por eso los tests anteriores siguen
pasando sin cambios.
"""

from __future__ import annotations

import sys
from collections import Counter, deque
from dataclasses import dataclass

import cv2
import numpy as np

from src.captura import CapturaVideo
from src.config import Config, cargar_config
from src.perfiles_frutas import PerfilFruta, obtener_perfil

VENTANA_MAYORIA_DEFAULT = 7


@dataclass(frozen=True)
class ResultadoClasificacion:
    """Resultado de clasificar un frame.

    estado: 'S' (madura), 'A' (inmadura), 'R' (pasada) o None si no hay fruta.
    Los porcentajes estan normalizados sobre los pixeles clasificados.
    perfil: nombre del perfil usado.
    """

    estado: str | None
    pct_verde: float
    pct_madura: float
    pct_pasada: float
    pixeles_fruta: int
    perfil: str = "default"


def _extraer_roi(
    frame: np.ndarray, perfil: PerfilFruta
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """Recorta la ROI definida por el perfil. Devuelve (roi, (x0,y0,x1,y1))."""
    alto, ancho = frame.shape[:2]
    x0 = int(ancho * perfil.roi_x_rel)
    y0 = int(alto * perfil.roi_y_rel)
    x1 = x0 + int(ancho * perfil.roi_w_rel)
    y1 = y0 + int(alto * perfil.roi_h_rel)
    return frame[y0:y1, x0:x1], (x0, y0, x1, y1)


def clasificar_frame(
    frame: np.ndarray, perfil: PerfilFruta | None = None
) -> ResultadoClasificacion:
    """Clasifica un frame BGR segun el perfil indicado.

    Si perfil es None, usa el perfil 'default' (contrato original).
    """
    if perfil is None:
        perfil = obtener_perfil(None)

    roi, _ = _extraer_roi(frame, perfil)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    h = hsv[:, :, 0].astype(np.int16)
    s = hsv[:, :, 1].astype(np.int16)
    v = hsv[:, :, 2].astype(np.int16)

    mascara_fruta = (s >= perfil.s_min_fruta) & (v >= perfil.v_min_fruta)
    total_fruta = int(mascara_fruta.sum())

    if total_fruta == 0:
        return ResultadoClasificacion(None, 0.0, 0.0, 0.0, 0, perfil.nombre)

    # Orden: pasada -> verde -> madura.
    # Razon: en algunos perfiles (platano, mandarina) el H bajo puede ser
    # marron (pasada) o amarillo (madura). Hay que excluir pasada primero
    # para que un platano marron oscuro no caiga en "madura".
    es_pasada = (
        (h <= perfil.h_pasada_max)
        & (v < perfil.v_pasada_max)
        & mascara_fruta
    )

    es_verde = (
        (h >= perfil.h_verde_min)
        & (h <= perfil.h_verde_max)
        & mascara_fruta
        & ~es_pasada
    )

    es_madura = (
        ((h <= perfil.h_madura_max_bajo) | (h >= perfil.h_madura_min_alto))
        & (v >= perfil.v_madura_min)
        & (s >= perfil.s_madura_min)
        & mascara_fruta
        & ~es_pasada
        & ~es_verde
    )

    n_verde = int(es_verde.sum())
    n_madura = int(es_madura.sum())
    n_pasada = int(es_pasada.sum())
    total_clasificado = n_verde + n_madura + n_pasada

    if total_clasificado == 0:
        return ResultadoClasificacion(
            None, 0.0, 0.0, 0.0, total_fruta, perfil.nombre
        )

    pct_verde = 100.0 * n_verde / total_clasificado
    pct_madura = 100.0 * n_madura / total_clasificado
    pct_pasada = 100.0 * n_pasada / total_clasificado

    if n_madura >= n_verde and n_madura >= n_pasada:
        estado = "S"
    elif n_verde >= n_pasada:
        estado = "A"
    else:
        estado = "R"

    return ResultadoClasificacion(
        estado, pct_verde, pct_madura, pct_pasada, total_fruta, perfil.nombre
    )


class FiltroMayoria:
    """Suaviza el estado entre frames usando los ultimos N resultados.

    Los valores None (sin fruta) se ignoran y no entran al buffer.
    """

    def __init__(self, ventana: int | None = None):
        self.ventana = ventana or VENTANA_MAYORIA_DEFAULT
        self._buffer: deque[str] = deque(maxlen=self.ventana)

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
    frame: np.ndarray,
    resultado: ResultadoClasificacion,
    estado_filtrado: str | None,
    perfil: PerfilFruta,
) -> None:
    _, (x0, y0, x1, y1) = _extraer_roi(frame, perfil)
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
    cv2.putText(
        frame,
        f"Perfil: {perfil.nombre}",
        (10, 125),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (100, 200, 255),
        1,
    )


def _demo(config: Config) -> int:
    """Demo: clasifica con el perfil configurado en .env."""
    perfil = obtener_perfil(config.perfil_fruta)
    try:
        captura = CapturaVideo(config.cam_url)
        captura.abrir()
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    filtro = FiltroMayoria(perfil.ventana_mayoria)
    print(f"Perfil activo: {perfil.nombre}")
    print("Presiona 'q' en la ventana para salir.")

    try:
        while True:
            frame = captura.leer_frame()
            if frame is None:
                continue
            resultado = clasificar_frame(frame, perfil)
            estado_filtrado = filtro.actualizar(resultado.estado)
            _dibujar_overlay(frame, resultado, estado_filtrado, perfil)
            cv2.imshow("FrutaEstado - Clasificacion", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        captura.cerrar()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    sys.exit(_demo(cargar_config()))
