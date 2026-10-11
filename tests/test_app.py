"""Tests para la API Flask (dashboard/app.py)."""

import pytest

from dashboard.app import crear_app


@pytest.fixture
def cliente(tmp_path):
    db = str(tmp_path / "test_app.db")
    app = crear_app(db_path=db)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------- GET / ----------

def test_get_index_devuelve_html(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    assert b"FrutaEstado" in r.data


# ---------- POST /api/registro ----------

def test_post_registro_valido(cliente):
    r = cliente.post(
        "/api/registro",
        json={"estado": "S", "pct_verde": 10, "pct_madura": 80, "pct_pasada": 10},
    )
    assert r.status_code == 201
    assert r.get_json() == {"id": 1}


def test_post_registro_estado_invalido(cliente):
    r = cliente.post(
        "/api/registro",
        json={"estado": "X", "pct_verde": 10, "pct_madura": 80, "pct_pasada": 10},
    )
    assert r.status_code == 400
    assert "estado" in r.get_json()["error"].lower()


def test_post_registro_sin_estado(cliente):
    r = cliente.post(
        "/api/registro",
        json={"pct_verde": 10, "pct_madura": 80, "pct_pasada": 10},
    )
    assert r.status_code == 400


def test_post_registro_falta_porcentaje(cliente):
    r = cliente.post(
        "/api/registro",
        json={"estado": "S", "pct_verde": 10, "pct_madura": 80},
    )
    assert r.status_code == 400
    assert "pct_pasada" in r.get_json()["error"]


def test_post_registro_porcentaje_no_numerico(cliente):
    r = cliente.post(
        "/api/registro",
        json={
            "estado": "S",
            "pct_verde": "mucho",
            "pct_madura": 80,
            "pct_pasada": 10,
        },
    )
    assert r.status_code == 400


def test_post_registro_sin_json(cliente):
    r = cliente.post("/api/registro", data="no-json", content_type="text/plain")
    assert r.status_code == 400


def test_post_registro_json_no_objeto(cliente):
    r = cliente.post("/api/registro", json=[1, 2, 3])
    assert r.status_code == 400


# ---------- GET /api/resumen ----------

def test_resumen_vacio(cliente):
    r = cliente.get("/api/resumen")
    assert r.status_code == 200
    data = r.get_json()
    assert data["conteos"] == {"S": 0, "A": 0, "R": 0}
    assert data["serie_por_minuto"] == []
    assert data["ultimos"] == []


def test_resumen_con_datos(cliente):
    for estado in ["S", "S", "A"]:
        cliente.post(
            "/api/registro",
            json={
                "estado": estado,
                "pct_verde": 10,
                "pct_madura": 80,
                "pct_pasada": 10,
            },
        )
    r = cliente.get("/api/resumen")
    data = r.get_json()
    assert data["conteos"] == {"S": 2, "A": 1, "R": 0}
    assert len(data["ultimos"]) == 3
    # El último insertado (A) es el primero de la lista (orden desc)
    assert data["ultimos"][0]["estado"] == "A"
    # Serie por minuto tiene al menos una entrada
    assert len(data["serie_por_minuto"]) >= 1
