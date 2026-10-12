"""Cliente HTTP hacia el dashboard Flask (POST /api/registro).

Se usa cuando el estado filtrado cambia respecto del anterior. No se llama
en cada heartbeat (evita inflar la DB con estados idénticos).

Este módulo NUNCA lanza excepciones de red hacia arriba: si el dashboard
no está corriendo, devuelve False y el pipeline sigue.
"""

from __future__ import annotations

import requests

TIMEOUT_POR_DEFECTO = 2.0
RUTA_REGISTRO = "/api/registro"
ESTADOS_VALIDOS = frozenset({"S", "A", "R"})


def _resolver_host(host: str) -> str:
    """Si el host es 0.0.0.0 (bind genérico), usar 127.0.0.1 para el POST.

    Flask escucha en 0.0.0.0 para aceptar conexiones de cualquier interfaz,
    pero para hacer una petición hay que apuntar a una dirección concreta.
    """
    if host in ("0.0.0.0", "", None):  # type: ignore[comparison-overlap]
        return "127.0.0.1"
    return host


def enviar_registro(
    host: str,
    port: int,
    estado: str,
    pct_verde: float,
    pct_madura: float,
    pct_pasada: float,
    tipo_fruta: str = "desconocida",
    timeout: float = TIMEOUT_POR_DEFECTO,
) -> bool:
    """Hace POST /api/registro con el payload JSON.

    Devuelve True si el dashboard responde 201 Created, False en cualquier
    otro caso (estado inválido, 400, timeout, error de conexión, etc.).
    Nunca lanza.
    """
    if estado not in ESTADOS_VALIDOS:
        return False

    host = _resolver_host(host)
    url = f"http://{host}:{port}{RUTA_REGISTRO}"
    payload = {
        "estado": estado,
        "pct_verde": float(pct_verde),
        "pct_madura": float(pct_madura),
        "pct_pasada": float(pct_pasada),
        "tipo_fruta": (tipo_fruta or "desconocida").strip() or "desconocida",
    }

    try:
        respuesta = requests.post(url, json=payload, timeout=timeout)
    except requests.RequestException:
        return False

    return respuesta.status_code == 201


def obtener_perfil_actual(
    host: str,
    port: int,
    timeout: float = TIMEOUT_POR_DEFECTO,
) -> str | None:
    """Consulta GET /api/perfil al dashboard y devuelve el perfil activo.

    Devuelve None si el dashboard no responde, hay timeout o la respuesta
    no tiene el formato esperado. Nunca lanza.
    """
    host = _resolver_host(host)
    url = f"http://{host}:{port}/api/perfil"
    try:
        respuesta = requests.get(url, timeout=timeout)
    except requests.RequestException:
        return None
    if respuesta.status_code != 200:
        return None
    try:
        datos = respuesta.json()
    except ValueError:
        return None
    if not isinstance(datos, dict):
        return None
    perfil = datos.get("perfil")
    if isinstance(perfil, str) and perfil.strip():
        return perfil.strip()
    return None
