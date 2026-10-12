"""Tests para src/perfiles_frutas.py."""

from src.perfiles_frutas import (
    PERFILES,
    PerfilFruta,
    listar_nombres,
    obtener_perfil,
)


def test_default_existe():
    assert "default" in PERFILES


def test_listar_nombres_contiene_los_7():
    nombres = listar_nombres()
    for n in [
        "default",
        "platano",
        "mandarina",
        "manzana_verde",
        "manzana_roja",
        "uva_verde",
        "uva_morada",
    ]:
        assert n in nombres


def test_default_reproduce_contrato_original():
    p = obtener_perfil("default")
    assert p.roi_x_rel == 0.25
    assert p.roi_y_rel == 0.20
    assert p.roi_w_rel == 0.50
    assert p.roi_h_rel == 0.60
    assert p.s_min_fruta == 50
    assert p.v_min_fruta == 30
    assert p.h_verde_min == 35
    assert p.h_verde_max == 85
    assert p.h_madura_max_bajo == 35
    assert p.h_madura_min_alto == 160
    assert p.v_madura_min == 110
    assert p.s_madura_min == 80
    assert p.h_pasada_max == 25
    assert p.v_pasada_max == 110
    assert p.ventana_mayoria == 7


def test_obtener_perfil_inexistente_cae_a_default():
    p = obtener_perfil("kiwi_raro")
    assert p.nombre == "default"


def test_obtener_perfil_none_cae_a_default():
    p = obtener_perfil(None)
    assert p.nombre == "default"


def test_obtener_perfil_vacio_cae_a_default():
    p = obtener_perfil("")
    assert p.nombre == "default"


def test_perfil_es_inmutable():
    p = obtener_perfil("default")
    try:
        p.nombre = "otro"  # type: ignore[misc]
        raise AssertionError("deberia ser inmutable")
    except Exception:
        pass


def test_perfiles_son_instancias_de_dataclass():
    for nombre, p in PERFILES.items():
        assert isinstance(p, PerfilFruta)
        assert p.nombre == nombre


def test_uva_morada_tiene_h_madura_alto():
    p = obtener_perfil("uva_morada")
    assert p.h_madura_min_alto <= 130


def test_manzana_roja_madura_es_rojo():
    p = obtener_perfil("manzana_roja")
    assert p.h_madura_max_bajo <= 10
    assert p.h_madura_min_alto >= 170
