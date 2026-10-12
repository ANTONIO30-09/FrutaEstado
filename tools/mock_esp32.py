"""Mock del ESP32 para desarrollo y demo sin hardware.

Simula el contrato del companero:
- GET /estado?valor=S|A|R
- 200 OK si el valor es valido
- 400 BAD REQUEST si no

Corre en el puerto 8080 para no chocar con el dashboard (5000).
Imprime cada peticion recibida con timestamp.

Uso:
    python -m tools.mock_esp32
    python -m tools.mock_esp32 --port 8081
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from flask import Flask, request

VALORES_VALIDOS = frozenset({"S", "A", "R"})
PUERTO_DEFAULT = 8080


def crear_app_mock(verbose: bool = True) -> Flask:
    app = Flask(__name__)

    @app.get("/estado")
    def estado():
        valor = request.args.get("valor", "")
        ts = datetime.now().strftime("%H:%M:%S")
        if valor in VALORES_VALIDOS:
            if verbose:
                print(f"[{valor}] {ts} -> 200 OK", flush=True)
            return "OK", 200
        if verbose:
            mostrado = valor if valor else "(vacio)"
            print(f"[{mostrado}] {ts} -> 400 BAD REQUEST", flush=True)
        return "BAD REQUEST", 400

    @app.get("/")
    def index():
        return (
            "Mock ESP32 corriendo.\n"
            "Endpoint: GET /estado?valor=S|A|R\n",
            200,
        )

    return app


def main() -> int:
    parser = argparse.ArgumentParser(description="Mock del ESP32.")
    parser.add_argument(
        "--port", type=int, default=PUERTO_DEFAULT,
        help=f"Puerto (default: {PUERTO_DEFAULT})",
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Host (default: 127.0.0.1)",
    )
    args = parser.parse_args()

    print(f"Mock ESP32 escuchando en http://{args.host}:{args.port}/estado")
    print("Ctrl+C para detener.")
    app = crear_app_mock(verbose=True)
    app.run(host=args.host, port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
