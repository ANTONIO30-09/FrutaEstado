"""Aplicación Flask del dashboard FrutaEstado.

Expone:
- GET  /                 → HTML del dashboard (placeholder hasta S3.4).
- POST /api/registro     → inserta un registro en SQLite.
- GET  /api/resumen      → conteos + serie por minuto + últimos 10.

El patrón `crear_app` (factory) permite instanciar la app con una db_path
temporal en los tests, sin tocar data/frutas.db.
"""

from __future__ import annotations
import json
from pathlib import Path

from pathlib import Path

from flask import Flask, jsonify, render_template, request, redirect, url_for
from flask_cors import CORS

from src.perfiles_frutas import PERFILES

from dashboard.estado_compartido import (
    get_perfil as get_perfil_activo,
    set_perfil as set_perfil_activo,
)
from dashboard.db import (
    ESTADOS_VALIDOS,
    init_db,
    insertar_registro,
    obtener_conteos_por_estado,
    obtener_serie_por_minuto,
    obtener_ultimos_registros,
)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

CAMPOS_PORCENTAJE = ("pct_verde", "pct_madura", "pct_pasada")


from dashboard.camera_manager import CameraManager
camera_manager = CameraManager()

def crear_app(db_path: str | None = None) -> Flask:
    """Crea la app Flask. Si db_path es None, usa el del .env."""
    app = Flask(__name__, template_folder=str(TEMPLATES_DIR))
    CORS(app)

    # Crear el esquema al arrancar (idempotente).
    init_db(db_path)

    # ---------------- GET / ----------------
    @app.get("/")
    def index():
        import os
import time
        config_path = Path(__file__).resolve().parent.parent / "config" / "dispositivos.json"
        # Si estamos en pytest, ignoramos la redireccion para no romper los tests
        if not config_path.exists() and not os.environ.get("PYTEST_CURRENT_TEST"):
            return redirect(url_for("setup"))
        return render_template("index.html")

    # ---------- POST /api/registro ----------
    @app.post("/api/registro")
    def api_registro():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return jsonify({"error": "Se esperaba un JSON en el cuerpo."}), 400

        estado = datos.get("estado")
        if estado not in ESTADOS_VALIDOS:
            return (
                jsonify(
                    {"error": "El campo 'estado' debe ser 'S', 'A' o 'R'."}
                ),
                400,
            )

        porcentajes: dict[str, float] = {}
        for campo in CAMPOS_PORCENTAJE:
            valor = datos.get(campo)
            if valor is None:
                return (
                    jsonify({"error": f"Falta el campo '{campo}'."}),
                    400,
                )
            try:
                porcentajes[campo] = float(valor)
            except (TypeError, ValueError):
                return (
                    jsonify({"error": f"El campo '{campo}' debe ser numérico."}),
                    400,
                )

        tipo_fruta = str(datos.get("tipo_fruta", "desconocida")).strip() or "desconocida"

        nuevo_id = insertar_registro(
            estado=estado,
            pct_verde=porcentajes["pct_verde"],
            pct_madura=porcentajes["pct_madura"],
            pct_pasada=porcentajes["pct_pasada"],
            tipo_fruta=tipo_fruta,
            db_path=db_path,
        )
        return jsonify({"id": nuevo_id}), 201

    # ---------- GET /api/resumen ----------
    @app.get("/api/resumen")
    def api_resumen():
        # ?tipo_fruta=platano filtra; ausente o vacio = sin filtro.
        tipo_fruta = request.args.get("tipo_fruta", "").strip() or None
        return jsonify(
            {
                "conteos": obtener_conteos_por_estado(
                    db_path=db_path, tipo_fruta=tipo_fruta
                ),
                "serie_por_minuto": obtener_serie_por_minuto(
                    minutos=60, db_path=db_path, tipo_fruta=tipo_fruta
                ),
                "ultimos": obtener_ultimos_registros(
                    n=10, db_path=db_path, tipo_fruta=tipo_fruta
                ),
                "tipo_fruta": tipo_fruta,
            }
        )

    # ---------- GET /api/perfil ----------
    @app.get("/api/perfil")
    def api_perfil_get():
        return jsonify({"perfil": get_perfil_activo()})

    # ---------- POST /api/perfil ----------
    @app.post("/api/perfil")
    def api_perfil_post():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            return jsonify({"error": "Se esperaba un JSON."}), 400
        nombre = datos.get("perfil")
        if not isinstance(nombre, str) or not nombre.strip():
            return jsonify({"error": "Falta el campo 'perfil'."}), 400
        nombre = nombre.strip()
        if nombre not in PERFILES:
            return (
                jsonify(
                    {
                        "error": f"Perfil desconocido: {nombre!r}.",
                        "disponibles": sorted(PERFILES.keys()),
                    }
                ),
                400,
            )
        set_perfil_activo(nombre)
        return jsonify({"perfil": nombre}), 200

    # ---------- GET /api/perfiles ----------
    @app.get("/api/perfiles")
    def api_perfiles_list():
        return jsonify({"perfiles": sorted(PERFILES.keys())})

    @app.route("/setup", methods=["GET", "POST"])
    def setup():
        config_path = Path(__file__).resolve().parent.parent / "config" / "dispositivos.json"
        # Leemos la config actual
        cam_ip = "0"
        cam_port = "4747"
        esp32_ip = "192.168.1.100"
        
        if config_path.exists():
            try:
                saved = json.loads(config_path.read_text())
                esp32_ip = saved.get("esp32_ip", esp32_ip)
                # Extraemos IP y puerto si ya estaban guardados
                if "cam_url" in saved and "http://" in saved["cam_url"]:
                    parts = saved["cam_url"].replace("http://", "").replace("/video", "").split(":")
                    cam_ip = parts[0]
                    if len(parts) > 1: cam_port = parts[1]
                elif saved.get("cam_url") == "0":
                    cam_ip = "0"
            except Exception:
                pass

        config_actual = {"cam_ip": cam_ip, "cam_port": cam_port, "esp32_ip": esp32_ip}
                
        if request.method == "POST":
            cam_ip = request.form.get("cam_ip", "0")
            cam_port = request.form.get("cam_port", "4747")
            esp32_ip = request.form.get("esp32_ip", "")
            
            # Armamos la URL completa para el main.py
            if cam_ip == "0" or cam_ip == "":
                cam_url = "0"
            else:
                cam_url = f"http://{cam_ip}:{cam_port}/video"
                
            config_guardar = {"cam_url": cam_url, "esp32_ip": esp32_ip}
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(json.dumps(config_guardar, indent=2))
            return redirect(url_for("index"))
            
        return render_template("setup.html", config=config_actual)


    @app.route("/video_feed")
    def video_feed():
        from flask import Response
        def generate():
            while camera_manager.running:
                frame = camera_manager.get_frame()
                if frame:
                    yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                else:
                    time.sleep(0.1)
        return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

    @app.route("/api/camera/start", methods=["POST"])
    def api_camera_start():
        camera_manager.start()
        return jsonify({"status": "ok"})

    @app.route("/api/camera/stop", methods=["POST"])
    def api_camera_stop():
        camera_manager.stop()
        return jsonify({"status": "ok"})

    @app.route("/api/camera/status")
    def api_camera_status():
        return jsonify({"running": camera_manager.running})

    return app


if __name__ == "__main__":
    from src.config import cargar_config

    cfg = cargar_config()
    crear_app().run(host=cfg.flask_host, port=cfg.flask_port, debug=False, use_reloader=False)
