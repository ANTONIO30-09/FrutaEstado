"""Tests para dashboard/db.py usando bases SQLite temporales."""

from datetime import datetime

import pytest

from dashboard.db import (
    conectar,
    init_db,
    insertar_registro,
    obtener_conteos_por_estado,
    obtener_serie_por_minuto,
    obtener_ultimos_registros,
)


@pytest.fixture
def db_tmp(tmp_path):
    return str(tmp_path / "test.db")


# ---------- init_db ----------

def test_init_db_crea_tabla(db_tmp):
    init_db(db_tmp)
    conn = conectar(db_tmp)
    try:
        tablas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='registros'"
        ).fetchall()
    finally:
        conn.close()
    assert len(tablas) == 1


def test_init_db_es_idempotente(db_tmp):
    init_db(db_tmp)
    init_db(db_tmp)
    init_db(db_tmp)
    conn = conectar(db_tmp)
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='registros'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert n == 1


# ---------- insertar_registro ----------

def test_insertar_registro_devuelve_id(db_tmp):
    init_db(db_tmp)
    id1 = insertar_registro("S", 10.0, 80.0, 10.0, db_path=db_tmp)
    id2 = insertar_registro("A", 90.0, 5.0, 5.0, db_path=db_tmp)
    assert id1 == 1
    assert id2 == 2


def test_insertar_registro_estado_invalido_lanza(db_tmp):
    init_db(db_tmp)
    with pytest.raises(ValueError):
        insertar_registro("X", 0, 0, 0, db_path=db_tmp)


def test_insertar_registro_estado_vacio_lanza(db_tmp):
    init_db(db_tmp)
    with pytest.raises(ValueError):
        insertar_registro("", 0, 0, 0, db_path=db_tmp)


# ---------- obtener_conteos_por_estado ----------

def test_conteos_iniciales_en_cero(db_tmp):
    init_db(db_tmp)
    assert obtener_conteos_por_estado(db_path=db_tmp) == {"S": 0, "A": 0, "R": 0}


def test_conteos_tras_insertar(db_tmp):
    init_db(db_tmp)
    insertar_registro("S", 0, 0, 0, db_path=db_tmp)
    insertar_registro("S", 0, 0, 0, db_path=db_tmp)
    insertar_registro("A", 0, 0, 0, db_path=db_tmp)
    insertar_registro("R", 0, 0, 0, db_path=db_tmp)
    assert obtener_conteos_por_estado(db_path=db_tmp) == {"S": 2, "A": 1, "R": 1}


# ---------- obtener_serie_por_minuto ----------

def test_serie_por_minuto_vacia(db_tmp):
    init_db(db_tmp)
    assert obtener_serie_por_minuto(minutos=60, db_path=db_tmp) == []


def test_serie_por_minuto_agrupa(db_tmp):
    init_db(db_tmp)
    conn = conectar(db_tmp)
    try:
        # Timestamp fijo en el minuto actual (evita flakiness en bordes de minuto)
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:00")
        for estado in ["S", "S", "A"]:
            conn.execute(
                "INSERT INTO registros (estado, pct_verde, pct_madura, pct_pasada, timestamp) "
                "VALUES (?, 0, 0, 0, ?)",
                (estado, ahora),
            )
        conn.commit()
    finally:
        conn.close()

    serie = obtener_serie_por_minuto(minutos=60, db_path=db_tmp)
    estados = {e["estado"]: e["conteo"] for e in serie}
    assert estados.get("S") == 2
    assert estados.get("A") == 1


def test_serie_por_minuto_respeta_ventana(db_tmp):
    init_db(db_tmp)
    conn = conectar(db_tmp)
    try:
        conn.execute(
            "INSERT INTO registros "
            "(estado, pct_verde, pct_madura, pct_pasada, timestamp) "
            "VALUES (?, 0, 0, 0, datetime('now', 'localtime', '-2 hours'))",
            ("S",),
        )
        conn.commit()
    finally:
        conn.close()

    # Fuera de la ventana de 60 min
    assert obtener_serie_por_minuto(minutos=60, db_path=db_tmp) == []

    # Dentro de la ventana de 180 min
    serie = obtener_serie_por_minuto(minutos=180, db_path=db_tmp)
    assert len(serie) == 1
    assert serie[0]["estado"] == "S"


# ---------- obtener_ultimos_registros ----------

def test_ultimos_registros_vacio(db_tmp):
    init_db(db_tmp)
    assert obtener_ultimos_registros(n=10, db_path=db_tmp) == []


def test_ultimos_registros_orden_desc(db_tmp):
    init_db(db_tmp)
    insertar_registro("S", 10, 20, 30, db_path=db_tmp)
    insertar_registro("A", 40, 50, 60, db_path=db_tmp)
    insertar_registro("R", 70, 80, 90, db_path=db_tmp)
    ultimos = obtener_ultimos_registros(n=10, db_path=db_tmp)
    # Orden descendente por timestamp, luego por id → R, A, S
    assert [r["estado"] for r in ultimos] == ["R", "A", "S"]


def test_ultimos_registros_respeta_limite(db_tmp):
    init_db(db_tmp)
    for _ in range(15):
        insertar_registro("S", 0, 0, 0, db_path=db_tmp)
    assert len(obtener_ultimos_registros(n=10, db_path=db_tmp)) == 10


def test_ultimos_registros_tiene_campos_completos(db_tmp):
    init_db(db_tmp)
    insertar_registro("S", 1.5, 2.5, 3.5, db_path=db_tmp)
    r = obtener_ultimos_registros(n=1, db_path=db_tmp)[0]
    assert set(r.keys()) == {
        "id", "estado", "pct_verde", "pct_madura", "pct_pasada", "tipo_fruta", "timestamp"
    }
    assert r["pct_verde"] == 1.5
    assert r["pct_madura"] == 2.5
    assert r["pct_pasada"] == 3.5


# ---------- tipo_fruta (S4.1) ----------

def test_insertar_registro_tipo_fruta_default(db_tmp):
    init_db(db_tmp)
    insertar_registro("S", 1, 2, 3, db_path=db_tmp)
    r = obtener_ultimos_registros(n=1, db_path=db_tmp)[0]
    assert r["tipo_fruta"] == "desconocida"


def test_insertar_registro_tipo_fruta_explicito(db_tmp):
    init_db(db_tmp)
    insertar_registro("S", 1, 2, 3, tipo_fruta="platano", db_path=db_tmp)
    insertar_registro("A", 4, 5, 6, tipo_fruta="mandarina", db_path=db_tmp)
    ultimos = obtener_ultimos_registros(n=10, db_path=db_tmp)
    tipos = {r["tipo_fruta"] for r in ultimos}
    assert tipos == {"platano", "mandarina"}


def test_insertar_registro_tipo_vacio_usa_default(db_tmp):
    init_db(db_tmp)
    insertar_registro("S", 1, 2, 3, tipo_fruta="   ", db_path=db_tmp)
    r = obtener_ultimos_registros(n=1, db_path=db_tmp)[0]
    assert r["tipo_fruta"] == "desconocida"


def test_migracion_agrega_columna_a_db_sin_ella(tmp_path):
    """Simula una DB creada antes de S4.1: sin la columna tipo_fruta."""
    db = str(tmp_path / "viejo.db")
    conn = conectar(db)
    try:
        conn.executescript("""
            CREATE TABLE registros (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                estado          TEXT NOT NULL CHECK (estado IN ('S', 'A', 'R')),
                pct_verde       REAL NOT NULL,
                pct_madura      REAL NOT NULL,
                pct_pasada      REAL NOT NULL,
                timestamp       TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
        """)
        conn.execute(
            "INSERT INTO registros (estado, pct_verde, pct_madura, pct_pasada) "
            "VALUES ('S', 1, 2, 3)"
        )
        conn.commit()
    finally:
        conn.close()

    # init_db debe migrar sin error
    init_db(db)

    # La fila vieja recibe el default
    r = obtener_ultimos_registros(n=1, db_path=db)[0]
    assert r["tipo_fruta"] == "desconocida"


def test_init_db_idempotente_con_tipo_fruta(db_tmp):
    """Llamar init_db varias veces no falla aunque ya exista tipo_fruta."""
    init_db(db_tmp)
    init_db(db_tmp)
    init_db(db_tmp)
    insertar_registro("A", 1, 2, 3, tipo_fruta="manzana_verde", db_path=db_tmp)
    r = obtener_ultimos_registros(n=1, db_path=db_tmp)[0]
    assert r["tipo_fruta"] == "manzana_verde"


# ---------- tipo_fruta (S4.1) ----------

def test_insertar_registro_tipo_fruta_default(db_tmp):
    init_db(db_tmp)
    insertar_registro("S", 1, 2, 3, db_path=db_tmp)
    r = obtener_ultimos_registros(n=1, db_path=db_tmp)[0]
    assert r["tipo_fruta"] == "desconocida"


def test_insertar_registro_tipo_fruta_explicito(db_tmp):
    init_db(db_tmp)
    insertar_registro("S", 1, 2, 3, tipo_fruta="platano", db_path=db_tmp)
    insertar_registro("A", 4, 5, 6, tipo_fruta="mandarina", db_path=db_tmp)
    ultimos = obtener_ultimos_registros(n=10, db_path=db_tmp)
    tipos = {r["tipo_fruta"] for r in ultimos}
    assert tipos == {"platano", "mandarina"}


def test_insertar_registro_tipo_vacio_usa_default(db_tmp):
    init_db(db_tmp)
    insertar_registro("S", 1, 2, 3, tipo_fruta="   ", db_path=db_tmp)
    r = obtener_ultimos_registros(n=1, db_path=db_tmp)[0]
    assert r["tipo_fruta"] == "desconocida"


def test_migracion_agrega_columna_a_db_sin_ella(tmp_path):
    """Simula una DB creada antes de S4.1: sin la columna tipo_fruta."""
    db = str(tmp_path / "viejo.db")
    conn = conectar(db)
    try:
        conn.executescript("""
            CREATE TABLE registros (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                estado          TEXT NOT NULL CHECK (estado IN ('S', 'A', 'R')),
                pct_verde       REAL NOT NULL,
                pct_madura      REAL NOT NULL,
                pct_pasada      REAL NOT NULL,
                timestamp       TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
        """)
        conn.execute(
            "INSERT INTO registros (estado, pct_verde, pct_madura, pct_pasada) "
            "VALUES ('S', 1, 2, 3)"
        )
        conn.commit()
    finally:
        conn.close()

    # init_db debe migrar sin error
    init_db(db)

    # La fila vieja recibe el default
    r = obtener_ultimos_registros(n=1, db_path=db)[0]
    assert r["tipo_fruta"] == "desconocida"


def test_init_db_idempotente_con_tipo_fruta(db_tmp):
    """Llamar init_db varias veces no falla aunque ya exista tipo_fruta."""
    init_db(db_tmp)
    init_db(db_tmp)
    init_db(db_tmp)
    insertar_registro("A", 1, 2, 3, tipo_fruta="manzana_verde", db_path=db_tmp)
    r = obtener_ultimos_registros(n=1, db_path=db_tmp)[0]
    assert r["tipo_fruta"] == "manzana_verde"
