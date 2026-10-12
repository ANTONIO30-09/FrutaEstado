"""Perfiles HSV por tipo de fruta.

El perfil `default` reproduce EXACTAMENTE el contrato original del proyecto
(no cambia ni un umbral). Los demas perfiles son puntos de partida que se
calibran en la fase de pruebas con frutas reales.

Extension sin tocar codigo:
- Edita `config/perfiles_custom.json` agregando una entrada nueva.
- Los campos que no especifiques toman el valor del contrato original.
- Los perfiles nuevos se fusionan con los built-in al importar este modulo.
- Los perfiles custom sobreescriben a los built-in si tienen el mismo nombre.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
ARCHIVO_CUSTOM = RAIZ_PROYECTO / "config" / "perfiles_custom.json"


@dataclass(frozen=True)
class PerfilFruta:
    """Umbrales HSV de una fruta. Todos los campos tienen default = contrato."""

    nombre: str
    # ROI central (relativo a ancho/alto del frame)
    roi_x_rel: float = 0.25
    roi_y_rel: float = 0.20
    roi_w_rel: float = 0.50
    roi_h_rel: float = 0.60
    # Filtro de fruta
    s_min_fruta: int = 50
    v_min_fruta: int = 30
    # Verde (inmadura)
    h_verde_min: int = 35
    h_verde_max: int = 85
    # Madura
    h_madura_max_bajo: int = 35
    h_madura_min_alto: int = 160
    v_madura_min: int = 110
    s_madura_min: int = 80
    # Pasada
    h_pasada_max: int = 25
    v_pasada_max: int = 110
    # Filtro de mayoria
    ventana_mayoria: int = 7


def _perfiles_builtin() -> dict[str, PerfilFruta]:
    return {
        "default": PerfilFruta(nombre="default"),
        "platano": PerfilFruta(
            nombre="platano",
            h_madura_max_bajo=35,
            h_madura_min_alto=100,   # inalcanzable: no queremos H>=160
            v_madura_min=120,
            s_madura_min=90,
        ),
        "mandarina": PerfilFruta(
            nombre="mandarina",
            h_madura_max_bajo=22,    # naranja H 8-22
            h_madura_min_alto=100,
            v_madura_min=140,
            s_madura_min=120,
        ),
        "manzana_verde": PerfilFruta(
            nombre="manzana_verde",
            h_verde_min=55,          # verde intenso = inmadura
            h_madura_max_bajo=55,    # verde-amarillento = madura
            h_madura_min_alto=100,
            v_madura_min=100,
            s_madura_min=70,
        ),
        "manzana_roja": PerfilFruta(
            nombre="manzana_roja",
            h_madura_max_bajo=10,
            h_madura_min_alto=170,
            v_madura_min=90,
            s_madura_min=100,
        ),
        "uva_verde": PerfilFruta(
            nombre="uva_verde",
            h_verde_min=55,
            h_madura_max_bajo=55,
            h_madura_min_alto=100,
            v_madura_min=90,
            s_madura_min=60,
        ),
        "uva_morada": PerfilFruta(
            nombre="uva_morada",
            h_madura_max_bajo=25,
            h_madura_min_alto=120,   # morado H 120-170
            v_madura_min=50,
            s_madura_min=50,
        ),
    }


def _cargar_perfiles_custom() -> dict[str, PerfilFruta]:
    """Lee config/perfiles_custom.json si existe. Ignora entradas invalidas."""
    if not ARCHIVO_CUSTOM.exists():
        return {}
    try:
        datos = json.loads(ARCHIVO_CUSTOM.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(datos, dict):
        return {}

    campos_validos = {f.name for f in fields(PerfilFruta)} - {"nombre"}
    resultado: dict[str, PerfilFruta] = {}
    for nombre, cfg in datos.items():
        if not isinstance(cfg, dict) or not isinstance(nombre, str):
            continue
        limpio = {k: v for k, v in cfg.items() if k in campos_validos}
        try:
            resultado[nombre] = PerfilFruta(nombre=nombre, **limpio)
        except (TypeError, ValueError):
            continue
    return resultado


PERFILES: dict[str, PerfilFruta] = {
    **_perfiles_builtin(),
    **_cargar_perfiles_custom(),
}


def obtener_perfil(nombre: str | None) -> PerfilFruta:
    """Devuelve el perfil pedido o el default si no existe o viene vacio."""
    if not nombre:
        return PERFILES["default"]
    return PERFILES.get(nombre, PERFILES["default"])


def listar_nombres() -> list[str]:
    """Devuelve los nombres de todos los perfiles disponibles, ordenados."""
    return sorted(PERFILES.keys())
