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


# ---------- Estáticos y HTML del dashboard ----------

def test_static_chartjs_devuelve_200(cliente):
    r = cliente.get("/static/js/chart.umd.min.js")
    assert r.status_code == 200
    # Chart.js pesa >100 KB; verificar que se sirvio contenido real.
    assert len(r.data) > 100_000


def test_static_dashboard_js_devuelve_200(cliente):
    r = cliente.get("/static/js/dashboard.js")
    assert r.status_code == 200
    assert b"REFRESH_MS" in r.data


def test_static_dashboard_css_devuelve_200(cliente):
    r = cliente.get("/static/css/dashboard.css")
    assert r.status_code == 200


def test_index_incluye_elementos_clave(cliente):
    """El rediseno glass reemplazo el doughnut por un gauge SVG."""
    r = cliente.get("/")
    html = r.data
    # Gauge SVG (los 3 arcos)
    assert b'id="arc-s"' in html
    assert b'id="arc-a"' in html
    assert b'id="arc-r"' in html
    # Grafica de linea
    assert b'id="chart-serie"' in html
    # Tabla del panel flotante
    assert b'id="tbody-ultimos"' in html
    # Boton flotante
    assert b'id="btn-registros"' in html
    # Scripts
    assert b'chart.umd.min.js' in html
    assert b'dashboard.js' in html


# ---------- /api/perfil y filtro (S4.4) ----------

def test_get_perfil_default(cliente):
    from dashboard import estado_compartido
    estado_compartido.reset()

    r = cliente.get("/api/perfil")
    assert r.status_code == 200
    assert r.get_json() == {"perfil": "default"}


def test_post_perfil_valido(cliente):
    from dashboard import estado_compartido
    estado_compartido.reset()

    r = cliente.post("/api/perfil", json={"perfil": "platano"})
    assert r.status_code == 200
    assert r.get_json() == {"perfil": "platano"}

    r2 = cliente.get("/api/perfil")
    assert r2.get_json() == {"perfil": "platano"}

    estado_compartido.reset()


def test_post_perfil_desconocido(cliente):
    from dashboard import estado_compartido
    estado_compartido.reset()

    r = cliente.post("/api/perfil", json={"perfil": "kiwi_raro"})
    assert r.status_code == 400
    assert "perfil" in r.get_json()["error"].lower()

    # Estado no cambio
    r2 = cliente.get("/api/perfil")
    assert r2.get_json() == {"perfil": "default"}


def test_post_perfil_sin_json(cliente):
    r = cliente.post("/api/perfil", data="no-json", content_type="text/plain")
    assert r.status_code == 400


def test_post_perfil_sin_campo(cliente):
    r = cliente.post("/api/perfil", json={"otra_cosa": "x"})
    assert r.status_code == 400


def test_post_perfil_vacio(cliente):
    r = cliente.post("/api/perfil", json={"perfil": "   "})
    assert r.status_code == 400


def test_get_perfiles_lista(cliente):
    r = cliente.get("/api/perfiles")
    assert r.status_code == 200
    data = r.get_json()
    assert "perfiles" in data
    assert "default" in data["perfiles"]
    assert "platano" in data["perfiles"]


def test_resumen_filtra_por_tipo_fruta(cliente):
    # Insertar 2 platanos y 1 uva
    for _ in range(2):
        cliente.post(
            "/api/registro",
            json={
                "estado": "S", "pct_verde": 0, "pct_madura": 0,
                "pct_pasada": 0, "tipo_fruta": "platano",
            },
        )
    cliente.post(
        "/api/registro",
        json={
            "estado": "A", "pct_verde": 0, "pct_madura": 0,
            "pct_pasada": 0, "tipo_fruta": "uva_verde",
        },
    )

    r_todos = cliente.get("/api/resumen")
    assert r_todos.get_json()["conteos"]["S"] == 2
    assert r_todos.get_json()["conteos"]["A"] == 1
    assert r_todos.get_json()["tipo_fruta"] is None

    r_platano = cliente.get("/api/resumen?tipo_fruta=platano")
    assert r_platano.get_json()["conteos"]["S"] == 2
    assert r_platano.get_json()["conteos"]["A"] == 0
    assert r_platano.get_json()["tipo_fruta"] == "platano"

    r_uva = cliente.get("/api/resumen?tipo_fruta=uva_verde")
    assert r_uva.get_json()["conteos"]["S"] == 0
    assert r_uva.get_json()["conteos"]["A"] == 1


def test_resumen_tipo_fruta_vacio_es_sin_filtro(cliente):
    cliente.post(
        "/api/registro",
        json={
            "estado": "S", "pct_verde": 0, "pct_madura": 0,
            "pct_pasada": 0, "tipo_fruta": "platano",
        },
    )
    r = cliente.get("/api/resumen?tipo_fruta=")
    assert r.get_json()["tipo_fruta"] is None
    assert r.get_json()["conteos"]["S"] == 1
