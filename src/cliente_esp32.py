"""Cliente HTTP hacia el ESP32.

Contrato con el compañero de hardware (NO cambiar):
- Endpoint: /estado
- Método: GET
- Parámetro: valor = S | A | R
- Respuesta: 200 OK si es válido, 400 si no
- El ESP32 escucha en el puerto 80

Este módulo NUNCA lanza excepciones de red hacia arriba: si el ESP32 está
apagado, desconectado o tarda demasiado, devuelve False y el loop principal
sigue funcionando.
"""

from __future__ import annotations

import requests

VALORES_VALIDOS = frozenset({"S", "A", "R"})
TIMEOUT_POR_DEFECTO = 1.0


def _construir_url(ip: str, port: int, endpoint: str) -> str:
    """Construye la URL base. Asegura '/' inicial en el endpoint."""
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    return f"http://{ip}:{port}{endpoint}"


def enviar_estado(
    ip: str,
    port: int,
    endpoint: str,
    valor: str,
    timeout: float = TIMEOUT_POR_DEFECTO,
) -> bool:
    """Envía el estado al ESP32 vía GET.

    Devuelve True si el ESP32 responde 200 OK, False en cualquier otro caso
    (valor inválido, 400, timeout, error de conexión, etc.). Nunca lanza.
    """
    if valor not in VALORES_VALIDOS:
        return False

    url = _construir_url(ip, port, endpoint)

    try:
        respuesta = requests.get(url, params={"valor": valor}, timeout=timeout)
    except requests.RequestException:
        return False

    return respuesta.status_code == 200
