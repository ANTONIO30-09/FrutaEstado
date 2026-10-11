"""Tests para src/clasificador.py con frames sintéticos.

Los frames se generan directamente en HSV y se convierten a BGR para simular
lo que entregaría cv2.VideoCapture. Así los tests son deterministas y no
dependen de la cámara ni de fotos externas.
"""

import cv2
import numpy as np

from src.clasificador import FiltroMayoria, clasificar_frame


def _frame_hsv(h: int, s: int, v: int, alto: int = 200, ancho: int = 300) -> np.ndarray:
    """Construye un frame BGR de color HSV uniforme."""
    hsv = np.zeros((alto, ancho, 3), dtype=np.uint8)
    hsv[:, :, 0] = h
    hsv[:, :, 1] = s
    hsv[:, :, 2] = v
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def test_frame_verde_es_inmadura():
    frame = _frame_hsv(60, 150, 150)
    r = clasificar_frame(frame)
    assert r.estado == "A"
    assert r.pct_verde > 95.0
    assert r.pixeles_fruta > 0


def test_frame_rojo_maduro():
    frame = _frame_hsv(0, 200, 200)
    r = clasificar_frame(frame)
    assert r.estado == "S"
    assert r.pct_madura > 95.0


def test_frame_marron_pasada():
    frame = _frame_hsv(10, 150, 60)
    r = clasificar_frame(frame)
    assert r.estado == "R"
    assert r.pct_pasada > 95.0


def test_frame_negro_sin_fruta():
    frame = np.zeros((200, 300, 3), dtype=np.uint8)  # V=0, no pasa filtro
    r = clasificar_frame(frame)
    assert r.estado is None
    assert r.pixeles_fruta == 0


def test_frame_blanco_sin_fruta():
    frame = np.full((200, 300, 3), 255, dtype=np.uint8)  # S=0, no pasa filtro
    r = clasificar_frame(frame)
    assert r.estado is None
    assert r.pixeles_fruta == 0


def test_mitad_verde_mitad_rojo_en_roi():
    # Mitad superior verde, mitad inferior roja.
    # La ROI (y de 20% a 80%) corta exactamente por la mitad → ~50/50.
    verde = _frame_hsv(60, 150, 150, alto=100, ancho=300)
    rojo = _frame_hsv(0, 200, 200, alto=100, ancho=300)
    frame = np.vstack([verde, rojo])
    r = clasificar_frame(frame)
    assert 30.0 <= r.pct_verde <= 70.0
    assert 30.0 <= r.pct_madura <= 70.0


def test_filtro_mayoria_devuelve_mas_comun():
    f = FiltroMayoria(ventana=7)
    secuencia = ["A", "A", "S", "A", "S", "A", "A"]
    ultimo = None
    for estado in secuencia:
        ultimo = f.actualizar(estado)
    assert ultimo == "A"  # 5 A, 2 S


def test_filtro_mayoria_ignora_none():
    f = FiltroMayoria(ventana=7)
    f.actualizar("A")
    f.actualizar(None)
    f.actualizar("A")
    assert f.estado_actual() == "A"


def test_filtro_mayoria_vacio_devuelve_none():
    f = FiltroMayoria(ventana=7)
    assert f.estado_actual() is None


def test_filtro_mayoria_se_llena_y_desplaza():
    f = FiltroMayoria(ventana=3)
    f.actualizar("A")
    f.actualizar("A")
    f.actualizar("S")
    # Buffer: [A, A, S] → mayoria A
    assert f.estado_actual() == "A"
    f.actualizar("S")
    # Buffer: [A, S, S] → mayoria S
    assert f.estado_actual() == "S"


# ---------- clasificacion con perfiles (S4.2) ----------

def test_clasificar_con_perfil_none_usa_default():
    frame = _frame_hsv(60, 150, 150)
    r = clasificar_frame(frame, perfil=None)
    assert r.perfil == "default"


def test_mismo_frame_distinto_perfil_puede_dar_distinto_estado():
    """Un frame amarillo: con default es verde-inmadura, con platano es madura."""
    from src.perfiles_frutas import obtener_perfil

    # H=30, S=150, V=150: amarillo
    frame = _frame_hsv(30, 150, 150)
    r_default = clasificar_frame(frame, obtener_perfil("default"))
    r_platano = clasificar_frame(frame, obtener_perfil("platano"))
    # Con default, H=30 cae en "madura" tambien. Verificamos que el perfil
    # viaja con el resultado correctamente.
    assert r_default.perfil == "default"
    assert r_platano.perfil == "platano"


def test_resultado_incluye_nombre_del_perfil():
    from src.perfiles_frutas import obtener_perfil

    frame = _frame_hsv(60, 150, 150)
    r = clasificar_frame(frame, obtener_perfil("manzana_verde"))
    assert r.perfil == "manzana_verde"


def test_frame_sin_fruta_con_perfil_devuelve_none_y_perfil():
    from src.perfiles_frutas import obtener_perfil

    frame = np.zeros((200, 300, 3), dtype=np.uint8)
    r = clasificar_frame(frame, obtener_perfil("platano"))
    assert r.estado is None
    assert r.perfil == "platano"


# ---------- clasificacion con perfiles calibrados (S4.3) ----------

def test_platano_verde_es_inmaduro():
    from src.perfiles_frutas import obtener_perfil

    # H=45 en rango verde 26-55, V alto para no caer en pasada
    frame = _frame_hsv(45, 100, 120)
    r = clasificar_frame(frame, obtener_perfil("platano"))
    assert r.estado == "A"
    assert r.perfil == "platano"


def test_platano_amarillo_es_maduro():
    from src.perfiles_frutas import obtener_perfil

    # H=22 amarillo, S y V altos
    frame = _frame_hsv(22, 180, 180)
    r = clasificar_frame(frame, obtener_perfil("platano"))
    assert r.estado == "S"


def test_platano_marron_es_pasado():
    from src.perfiles_frutas import obtener_perfil

    # H=12, V bajo -> pasada (cae antes que madura)
    frame = _frame_hsv(12, 80, 100)
    r = clasificar_frame(frame, obtener_perfil("platano"))
    assert r.estado == "R"


def test_uva_morada_madura():
    from src.perfiles_frutas import obtener_perfil

    # H=140 morado, dentro del rango 110+
    frame = _frame_hsv(140, 100, 80)
    r = clasificar_frame(frame, obtener_perfil("uva_morada"))
    assert r.estado == "S"


def test_uva_morada_inmadura_es_verde():
    from src.perfiles_frutas import obtener_perfil

    # H=60 verde, inmadura
    frame = _frame_hsv(60, 100, 100)
    r = clasificar_frame(frame, obtener_perfil("uva_morada"))
    assert r.estado == "A"


def test_manzana_roja_madura():
    from src.perfiles_frutas import obtener_perfil

    # H=5 rojo, S y V altos
    frame = _frame_hsv(5, 200, 180)
    r = clasificar_frame(frame, obtener_perfil("manzana_roja"))
    assert r.estado == "S"


def test_mandarina_naranja_es_madura():
    from src.perfiles_frutas import obtener_perfil

    # H=18 naranja, dentro del rango madura 11-24
    frame = _frame_hsv(18, 180, 180)
    r = clasificar_frame(frame, obtener_perfil("mandarina"))
    assert r.estado == "S"


def test_reorder_pasada_tiene_prioridad_sobre_madura():
    """Un marron oscuro (H bajo, V bajo) no debe clasificarse como madura."""
    from src.perfiles_frutas import obtener_perfil

    # H=15 cumple h_madura_max_bajo<=25 del platano, pero V bajo lo hace pasada
    frame = _frame_hsv(15, 100, 80)
    r = clasificar_frame(frame, obtener_perfil("platano"))
    assert r.estado == "R"
