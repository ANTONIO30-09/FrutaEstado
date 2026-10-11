"""Script principal: captura -> clasificación HSV -> ESP32 + dashboard.

Pipeline completo:
1. Captura frames desde la fuente configurada (webcam o MJPEG).
2. Clasifica HSV según el contrato del proyecto.
3. Suaviza con filtro de mayoría (7 cuadros).
4. Envía heartbeat al ESP32 cada 1 s (mientras haya fruta).
5. Registra en el dashboard SOLO cuando el estado filtrado cambia.
"""

from __future__ import annotations

import sys
import time

import cv2
import numpy as np

from src.captura import CapturaVideo
from src.clasificador import (
    FiltroMayoria,
    ResultadoClasificacion,
    clasificar_frame,
)
from src.cliente_dashboard import enviar_registro
from src.cliente_esp32 import enviar_estado
from src.config import Config, cargar_config

INTERVALO_HEARTBEAT_S = 1.0

COLORES = {"S": (0, 0, 255), "A": (0, 255, 0), "R": (0, 165, 255)}


def _dibujar_overlay(
    frame: np.ndarray,
    resultado: ResultadoClasificacion,
    estado_filtrado: str | None,
    esp_ok: int,
    esp_fail: int,
    dash_ok: int,
    dash_fail: int,
    ultimo_ok_ts: float | None,
) -> None:
    alto, ancho = frame.shape[:2]
    x0, y0 = int(ancho * 0.25), int(alto * 0.20)
    x1, y1 = x0 + int(ancho * 0.50), y0 + int(alto * 0.60)
    cv2.rectangle(frame, (x0, y0), (x1, y1), (255, 255, 0), 2)

    texto_estado = estado_filtrado if estado_filtrado else "-"
    color_estado = COLORES.get(texto_estado, (255, 255, 255))

    cv2.putText(
        frame,
        f"Estado: {texto_estado}",
        (10, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        color_estado,
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

    if ultimo_ok_ts is not None:
        hace = time.time() - ultimo_ok_ts
        texto_esp = f"ESP32: OK (hace {hace:4.1f}s)"
        color_esp = (0, 255, 0)
    else:
        texto_esp = "ESP32: sin envios OK"
        color_esp = (0, 0, 255)

    cv2.putText(
        frame,
        f"{texto_esp}  OK:{esp_ok} FAIL:{esp_fail}",
        (10, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        color_esp,
        1,
    )

    if dash_ok > 0:
        texto_dash = f"DASH: OK:{dash_ok} FAIL:{dash_fail}"
        color_dash = (0, 255, 0)
    else:
        texto_dash = f"DASH: sin registros OK  FAIL:{dash_fail}"
        color_dash = (0, 200, 255)

    cv2.putText(
        frame,
        texto_dash,
        (10, 125),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        color_dash,
        1,
    )


def _loop(cfg: Config) -> int:
    try:
        captura = CapturaVideo(cfg.cam_url)
        captura.abrir()
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    filtro = FiltroMayoria()
    esp_ok = 0
    esp_fail = 0
    dash_ok = 0
    dash_fail = 0
    ultimo_ok_ts: float | None = None
    ultimo_envio_monotonic = 0.0
    estado_anterior: str | None = None

    print(
        f"Sistema iniciado. ESP32: "
        f"http://{cfg.esp32_ip}:{cfg.esp32_port}{cfg.esp32_endpoint}"
    )
    print(
        f"Dashboard: http://{cfg.flask_host}:{cfg.flask_port}/api/registro"
    )
    print("Presiona 'q' en la ventana para salir.")

    try:
        while True:
            frame = captura.leer_frame()
            ahora_monotonic = time.monotonic()

            resultado = ResultadoClasificacion(None, 0.0, 0.0, 0.0, 0)
            estado_filtrado: str | None = None

            if frame is not None:
                resultado = clasificar_frame(frame)
                estado_filtrado = filtro.actualizar(resultado.estado)

            # Heartbeat al ESP32 exactamente cada INTERVALO_HEARTBEAT_S
            if (
                estado_filtrado is not None
                and (ahora_monotonic - ultimo_envio_monotonic)
                >= INTERVALO_HEARTBEAT_S
            ):
                ok = enviar_estado(
                    cfg.esp32_ip,
                    cfg.esp32_port,
                    cfg.esp32_endpoint,
                    estado_filtrado,
                )
                if ok:
                    esp_ok += 1
                    ultimo_ok_ts = time.time()
                else:
                    esp_fail += 1
                ultimo_envio_monotonic = ahora_monotonic

            # Registro al dashboard SOLO cuando el estado cambia
            # (o es la primera vez que se detecta fruta).
            if (
                estado_filtrado is not None
                and estado_filtrado != estado_anterior
            ):
                ok = enviar_registro(
                    host=cfg.flask_host,
                    port=cfg.flask_port,
                    estado=estado_filtrado,
                    pct_verde=resultado.pct_verde,
                    pct_madura=resultado.pct_madura,
                    pct_pasada=resultado.pct_pasada,
                )
                if ok:
                    dash_ok += 1
                else:
                    dash_fail += 1
                estado_anterior = estado_filtrado

            if frame is not None:
                _dibujar_overlay(
                    frame,
                    resultado,
                    estado_filtrado,
                    esp_ok,
                    esp_fail,
                    dash_ok,
                    dash_fail,
                    ultimo_ok_ts,
                )
                cv2.imshow("FrutaEstado - Main", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        captura.cerrar()
        cv2.destroyAllWindows()

    print(f"Fin. ESP32 OK: {esp_ok} FAIL: {esp_fail}")
    print(f"Fin. Dashboard OK: {dash_ok} FAIL: {dash_fail}")
    return 0


if __name__ == "__main__":
    sys.exit(_loop(cargar_config()))
