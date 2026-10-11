"""Tests para tools/mock_esp32.py."""

import pytest

from tools.mock_esp32 import crear_app_mock


@pytest.fixture
def cliente():
    app = crear_app_mock(verbose=False)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_estado_s_devuelve_200(cliente):
    r = cliente.get("/estado?valor=S")
    assert r.status_code == 200


def test_estado_a_devuelve_200(cliente):
    r = cliente.get("/estado?valor=A")
    assert r.status_code == 200


def test_estado_r_devuelve_200(cliente):
    r = cliente.get("/estado?valor=R")
    assert r.status_code == 200


def test_estado_x_devuelve_400(cliente):
    r = cliente.get("/estado?valor=X")
    assert r.status_code == 400


def test_estado_sin_parametro_devuelve_400(cliente):
    r = cliente.get("/estado")
    assert r.status_code == 400


def test_estado_valor_vacio_devuelve_400(cliente):
    r = cliente.get("/estado?valor=")
    assert r.status_code == 400


def test_estado_minuscula_devuelve_400(cliente):
    """El contrato es estricto: S, A, R en mayuscula."""
    r = cliente.get("/estado?valor=s")
    assert r.status_code == 400


def test_index_responde(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
