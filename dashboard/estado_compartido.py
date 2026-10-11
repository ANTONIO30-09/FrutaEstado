"""Estado compartido del dashboard entre requests (thread-safe).

Actualmente guarda solo el perfil de fruta activo. Se usa `threading.Lock`
porque Flask en modo debug atiende en multiples hilos.

Al reiniciar Flask, el estado vuelve a 'default'. No se persiste a disco:
es estado de sesion, no configuracion.
"""

from __future__ import annotations

import threading

_lock = threading.Lock()
_perfil_actual: str = "default"


def get_perfil() -> str:
    """Devuelve el nombre del perfil activo actualmente."""
    with _lock:
        return _perfil_actual


def set_perfil(nombre: str) -> None:
    """Setea el perfil activo. No valida el nombre (lo hace el endpoint)."""
    global _perfil_actual
    with _lock:
        _perfil_actual = nombre


def reset() -> None:
    """Vuelve el perfil activo al default. Util para tests."""
    global _perfil_actual
    with _lock:
        _perfil_actual = "default"
