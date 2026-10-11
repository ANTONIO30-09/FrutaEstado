"""Carga y expone la configuración del proyecto desde variables de entorno.

Todos los módulos deben importar la configuración desde aquí en lugar de
leer os.environ directamente, para centralizar validaciones y valores por
defecto.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto (un nivel arriba de src/)
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ_PROYECTO / ".env")


class ErrorConfiguracion(Exception):
    """Se lanza cuando falta una variable de entorno obligatoria."""


@dataclass(frozen=True)
class Config:
    cam_url: str | int
    esp32_ip: str
    esp32_port: int
    esp32_endpoint: str
    flask_host: str
    flask_port: int
    db_path: str


def _parsear_cam_url(valor: str) -> str | int:
    """Convierte '0' o '1' en int (índice de webcam) y deja URLs como string."""
    valor = valor.strip()
    if valor.isdigit():
        return int(valor)
    return valor


def cargar_config() -> Config:
    """Lee las variables del entorno y devuelve un objeto Config validado.

    Lanza ErrorConfiguracion si CAM_URL no está definida o está vacía.
    """
    cam_url_cruda = os.getenv("CAM_URL", "").strip()
    if not cam_url_cruda:
        raise ErrorConfiguracion(
            "Falta la variable CAM_URL en el archivo .env. "
            "Copia .env.example a .env y define CAM_URL "
            "(usa 0 para la webcam de la laptop o la URL del stream de DroidCam)."
        )

    return Config(
        cam_url=_parsear_cam_url(cam_url_cruda),
        esp32_ip=os.getenv("ESP32_IP", "192.168.1.100"),
        esp32_port=int(os.getenv("ESP32_PORT", "80")),
        esp32_endpoint=os.getenv("ESP32_ENDPOINT", "/estado"),
        flask_host=os.getenv("FLASK_HOST", "0.0.0.0"),
        flask_port=int(os.getenv("FLASK_PORT", "5000")),
        db_path=os.getenv("DB_PATH", "data/frutas.db"),
    )
