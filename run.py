"""Punto de entrada del dashboard.

Uso:
    python run.py
"""

from dashboard.app import crear_app
from src.config import cargar_config


def main() -> None:
    cfg = cargar_config()
    app = crear_app()
    print(
        f"Dashboard escuchando en http://{cfg.flask_host}:{cfg.flask_port}/ "
        f"(abrir en el navegador)"
    )
    app.run(host=cfg.flask_host, port=cfg.flask_port, debug=True)


if __name__ == "__main__":
    main()
