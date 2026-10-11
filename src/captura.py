"""Captura de frames desde la fuente de video configurada (webcam o MJPEG).

Envuelve cv2.VideoCapture con reconexión básica para tolerar cortes de WiFi.
No aplica lógica de clasificación: solo entrega frames BGR crudos.
"""

from __future__ import annotations

import sys
import time

import cv2
import numpy as np

from src.config import Config, cargar_config

REINTENTOS_MAX = 3
ESPERA_RECONEXION_S = 2.0


class ErrorCaptura(Exception):
    """Se lanza cuando no se puede abrir o mantener la fuente de video."""


class CapturaVideo:
    """Envoltura de cv2.VideoCapture con reconexión automática."""

    def __init__(self, cam_url: str | int, reintentos_max: int = REINTENTOS_MAX):
        self.cam_url = cam_url
        self.reintentos_max = reintentos_max
        self._cap: cv2.VideoCapture | None = None

    def abrir(self) -> None:
        """Abre la fuente. Lanza ErrorCaptura si falla tras los reintentos."""
        if self._cap is not None and self._cap.isOpened():
            return

        for intento in range(1, self.reintentos_max + 1):
            cap = cv2.VideoCapture(self.cam_url)
            if cap.isOpened():
                self._cap = cap
                return
            cap.release()
            if intento < self.reintentos_max:
                time.sleep(ESPERA_RECONEXION_S)

        raise ErrorCaptura(
            f"No se pudo abrir la fuente de video '{self.cam_url}' "
            f"tras {self.reintentos_max} intentos."
        )

    def leer_frame(self) -> np.ndarray | None:
        """Lee un frame. Si falla, intenta reconectar una vez y reintenta.

        Devuelve None si definitivamente no hay frame disponible.
        """
        if self._cap is None:
            self.abrir()

        ok, frame = self._cap.read()  # type: ignore[union-attr]
        if ok and frame is not None:
            return frame

        # Intento de reconexión
        self.cerrar()
        try:
            self.abrir()
            ok, frame = self._cap.read()  # type: ignore[union-attr]
            if ok and frame is not None:
                return frame
        except ErrorCaptura:
            pass

        return None

    def cerrar(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> "CapturaVideo":
        self.abrir()
        return self

    def __exit__(self, *args) -> None:
        self.cerrar()


def _demo(config: Config) -> int:
    """Abre la captura, muestra los frames en ventana y reporta FPS.

    Sale con la tecla 'q'. Devuelve código de salida (0 OK, 1 error).
    """
    try:
        captura = CapturaVideo(config.cam_url)
        captura.abrir()
    except ErrorCaptura as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    print("Captura iniciada. Presiona 'q' en la ventana para salir.")
    t_inicio = time.time()
    frames = 0

    try:
        while True:
            frame = captura.leer_frame()
            if frame is None:
                print("[WARN] No se pudo leer frame. Reintentando...", file=sys.stderr)
                continue

            frames += 1
            transcurrido = time.time() - t_inicio
            fps = frames / transcurrido if transcurrido > 0 else 0.0

            cv2.putText(
                frame,
                f"FPS: {fps:.1f}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2,
            )
            cv2.imshow("FrutaEstado - Captura", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        captura.cerrar()
        cv2.destroyAllWindows()

    print(f"Captura finalizada. Frames procesados: {frames}")
    return 0


if __name__ == "__main__":
    cfg = cargar_config()
    sys.exit(_demo(cfg))
