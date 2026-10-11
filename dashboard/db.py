"""Capa de acceso a datos del dashboard (SQLite).

Expone:
- init_db():        crea el esquema y migra columnas si no existen. Idempotente.
- conectar():       conexión SQLite configurada (Row factory + FK on).
- insertar_registro(): inserta una fila y devuelve el id.
- obtener_conteos_por_estado(): {S: n, A: n, R: n}.
- obtener_serie_por_minuto(): serie por minuto en la ventana (última hora por defecto).
- obtener_ultimos_registros(): últimas N filas ordenadas desc por timestamp e id.

No se usa ORM: para una sola tabla y cuatro consultas, SQL puro es suficiente
y más fácil de depurar.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from src.config import cargar_config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS registros (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    estado          TEXT NOT NULL CHECK (estado IN ('S', 'A', 'R')),
    pct_verde       REAL NOT NULL,
    pct_madura      REAL NOT NULL,
    pct_pasada      REAL NOT NULL,
    tipo_fruta      TEXT NOT NULL DEFAULT 'desconocida',
    timestamp       TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_registros_timestamp ON registros(timestamp);
CREATE INDEX IF NOT EXISTS idx_registros_estado ON registros(estado);
"""

ESTADOS_VALIDOS = frozenset({"S", "A", "R"})
TIPO_FRUTA_DEFAULT = "desconocida"


def _resolver_db_path(db_path: str | Path | None) -> str:
    """Si no se pasa db_path, lo toma de la configuración central (.env)."""
    if db_path is None:
        db_path = cargar_config().db_path
    return str(db_path)


def conectar(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Abre una conexión SQLite con Row factory y foreign_keys activado."""
    ruta = _resolver_db_path(db_path)
    if ruta != ":memory:":
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ruta)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrar_tipo_fruta(conn: sqlite3.Connection) -> None:
    """Agrega la columna tipo_fruta si no existe. Idempotente.

    Cubre bases creadas antes de S4.1. No rompe filas existentes:
    reciben el valor por defecto.
    """
    columnas = {
        fila["name"] for fila in conn.execute("PRAGMA table_info(registros)")
    }
    if "tipo_fruta" not in columnas:
        conn.execute(
            "ALTER TABLE registros "
            "ADD COLUMN tipo_fruta TEXT NOT NULL DEFAULT 'desconocida'"
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_registros_tipo_fruta "
        "ON registros(tipo_fruta)"
    )


def init_db(db_path: str | Path | None = None) -> None:
    """Crea la tabla e índices si no existen. Idempotente."""
    conn = conectar(db_path)
    try:
        conn.executescript(ESQUEMA)
        _migrar_tipo_fruta(conn)
        conn.commit()
    finally:
        conn.close()


def insertar_registro(
    estado: str,
    pct_verde: float,
    pct_madura: float,
    pct_pasada: float,
    tipo_fruta: str = TIPO_FRUTA_DEFAULT,
    db_path: str | Path | None = None,
) -> int:
    """Inserta un registro y devuelve el id generado.

    Lanza ValueError si el estado no es S, A o R.
    tipo_fruta vacío o en blanco cae al default 'desconocida'.
    """
    if estado not in ESTADOS_VALIDOS:
        raise ValueError(
            f"Estado inválido: {estado!r}. Debe ser 'S', 'A' o 'R'."
        )
    tipo = (tipo_fruta or TIPO_FRUTA_DEFAULT).strip() or TIPO_FRUTA_DEFAULT

    conn = conectar(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO registros "
            "(estado, pct_verde, pct_madura, pct_pasada, tipo_fruta) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                estado,
                float(pct_verde),
                float(pct_madura),
                float(pct_pasada),
                tipo,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def obtener_conteos_por_estado(
    db_path: str | Path | None = None,
    tipo_fruta: str | None = None,
) -> dict[str, int]:
    """Devuelve {S: n, A: n, R: n}. Siempre trae las tres claves.

    Si tipo_fruta no es None, filtra por esa fruta.
    """
    conn = conectar(db_path)
    try:
        if tipo_fruta is None:
            filas = conn.execute(
                "SELECT estado, COUNT(*) AS n FROM registros GROUP BY estado"
            ).fetchall()
        else:
            filas = conn.execute(
                "SELECT estado, COUNT(*) AS n FROM registros "
                "WHERE tipo_fruta = ? GROUP BY estado",
                (tipo_fruta,),
            ).fetchall()
    finally:
        conn.close()

    resultado = {"S": 0, "A": 0, "R": 0}
    for fila in filas:
        resultado[fila["estado"]] = int(fila["n"])
    return resultado


def obtener_serie_por_minuto(
    minutos: int = 60,
    db_path: str | Path | None = None,
    tipo_fruta: str | None = None,
) -> list[dict]:
    """Serie por minuto en la ventana indicada (por defecto, última hora).

    Si tipo_fruta no es None, filtra por esa fruta.
    """
    conn = conectar(db_path)
    try:
        if tipo_fruta is None:
            filas = conn.execute(
                """
                SELECT
                    strftime('%Y-%m-%d %H:%M', timestamp) AS minuto,
                    estado,
                    COUNT(*) AS conteo
                FROM registros
                WHERE timestamp >= datetime('now', 'localtime', ?)
                GROUP BY minuto, estado
                ORDER BY minuto ASC
                """,
                (f"-{int(minutos)} minutes",),
            ).fetchall()
        else:
            filas = conn.execute(
                """
                SELECT
                    strftime('%Y-%m-%d %H:%M', timestamp) AS minuto,
                    estado,
                    COUNT(*) AS conteo
                FROM registros
                WHERE timestamp >= datetime('now', 'localtime', ?)
                  AND tipo_fruta = ?
                GROUP BY minuto, estado
                ORDER BY minuto ASC
                """,
                (f"-{int(minutos)} minutes", tipo_fruta),
            ).fetchall()
    finally:
        conn.close()
    return [dict(fila) for fila in filas]


def obtener_ultimos_registros(
    n: int = 10,
    db_path: str | Path | None = None,
    tipo_fruta: str | None = None,
) -> list[dict]:
    """Devuelve las últimas N filas ordenadas por timestamp descendente.

    Si tipo_fruta no es None, filtra por esa fruta.
    """
    conn = conectar(db_path)
    try:
        if tipo_fruta is None:
            filas = conn.execute(
                "SELECT id, estado, pct_verde, pct_madura, pct_pasada, "
                "tipo_fruta, timestamp "
                "FROM registros ORDER BY timestamp DESC, id DESC LIMIT ?",
                (int(n),),
            ).fetchall()
        else:
            filas = conn.execute(
                "SELECT id, estado, pct_verde, pct_madura, pct_pasada, "
                "tipo_fruta, timestamp "
                "FROM registros WHERE tipo_fruta = ? "
                "ORDER BY timestamp DESC, id DESC LIMIT ?",
                (tipo_fruta, int(n)),
            ).fetchall()
    finally:
        conn.close()
    return [dict(fila) for fila in filas]
