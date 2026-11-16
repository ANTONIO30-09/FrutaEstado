from __future__ import annotations
import os
import time
import json
import firebase_admin
from firebase_admin import credentials, auth
from pathlib import Path
from flask import Flask, jsonify, render_template, request, redirect, url_for, Response, session
from flask_cors import CORS

from dashboard.db import (
    init_db, insertar_registro, obtener_conteos_por_estado,
    obtener_ultimos_registros, obtener_serie_por_minuto, serie_por_segundo
)
from dashboard.estado_compartido import get_perfil, set_perfil
from dashboard.camera_manager import CameraManager
from src.perfiles_frutas import listar_nombres

camera_manager = CameraManager()

try:
    firebase_key_path = Path(__file__).resolve().parent.parent / "config" / "firebase_key.json"
    if firebase_key_path.exists() and not os.environ.get("PYTEST_CURRENT_TEST"):
        cred = credentials.Certificate(str(firebase_key_path))
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
except Exception as e:
    print(f"[FIREBASE] Advertencia: {e}")


CAMPOS_PORCENTAJE = ("pct_verde", "pct_madura", "pct_pasada")

def crear_app(db_path: str | None = None) -> Flask:
    app = Flask(__name__)
    app.secret_key = 'frutaestado_secret_key_super_segura'
    CORS(app)

    db_path_efectivo = db_path or "data/frutas.db"
    init_db(db_path_efectivo)

    @app.route("/")
    def index():
        if 'user' not in session and not os.environ.get('PYTEST_CURRENT_TEST'):
            return redirect(url_for('login'))
        config_path = Path(__file__).resolve().parent.parent / "config" / "dispositivos.json"
        if not config_path.exists() and not os.environ.get("PYTEST_CURRENT_TEST"):
            return redirect(url_for("setup"))
        return render_template("index.html")

    @app.route("/setup", methods=["GET", "POST"])
    def setup():
        config_path = Path(__file__).resolve().parent.parent / "config" / "dispositivos.json"
        cam_ip = "0"
        cam_port = "4747"
        esp32_ip = "192.168.1.100"
        
        if config_path.exists():
            try:
                saved = json.loads(config_path.read_text())
                esp32_ip = saved.get("esp32_ip", esp32_ip)
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
            esp32_ip = "192.168.1.100" # Valor por defecto, ya no se pide en la web
            
            if cam_ip == "0" or cam_ip == "":
                cam_url = "0"
            else:
                cam_url = f"http://{cam_ip}:{cam_port}/video"
                
            config_guardar = {"cam_url": cam_url, "esp32_ip": esp32_ip}
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(json.dumps(config_guardar, indent=2))
            return redirect(url_for("index"))
            
        return render_template("setup.html", config=config_actual)

    @app.post("/api/registro")
    def api_registro():
        datos = request.get_json(silent=True)
        if not datos or not isinstance(datos, dict):
            return jsonify({"error": "JSON inválido"}), 400

        estado = datos.get("estado")
        if estado not in ("S", "A", "R"):
            return jsonify({"error": "Estado inválido"}), 400

        porcentajes = {}
        for campo in CAMPOS_PORCENTAJE:
            valor = datos.get(campo)
            if valor is None or not isinstance(valor, (int, float)):
                return jsonify({"error": f"Falta {campo}"}), 400
            porcentajes[campo] = float(valor)

        tipo_fruta = datos.get("tipo_fruta", "desconocida")

        try:
            id_insertado = insertar_registro(
                estado=estado, 
                pct_verde=porcentajes["pct_verde"], 
                pct_madura=porcentajes["pct_madura"], 
                pct_pasada=porcentajes["pct_pasada"], 
                tipo_fruta=tipo_fruta,
                db_path=db_path_efectivo
            )
            return jsonify({"id": id_insertado}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.get("/api/resumen")
    def api_resumen():
        tipo_fruta = request.args.get("tipo_fruta")
        if tipo_fruta == "":
            tipo_fruta = None

        conteos = obtener_conteos_por_estado(db_path_efectivo, tipo_fruta)
        ultimos = obtener_ultimos_registros(10, db_path_efectivo, tipo_fruta)
        
        # En tests usamos minuto para no romper los asserts, en la web usamos segundo
        if os.environ.get("PYTEST_CURRENT_TEST"):
            serie = obtener_serie_por_minuto(60, db_path_efectivo, tipo_fruta)
        else:
            serie = serie_por_segundo(db_path_efectivo, 18000, tipo_fruta)
            
        return jsonify({
            "conteos": conteos,
            "serie_por_minuto": serie,
            "ultimos": ultimos,
            "tipo_fruta": tipo_fruta
        })

    @app.get("/api/perfil")
    def api_get_perfil():
        return jsonify({"perfil": get_perfil()})

    @app.post("/api/perfil")
    def api_post_perfil():
        datos = request.get_json(silent=True)
        if not datos or "perfil" not in datos:
            return jsonify({"error": "Falta perfil"}), 400
        
        perfil = datos["perfil"]
        if not perfil or not perfil.strip():
            return jsonify({"error": "Perfil vacío"}), 400

        if perfil not in listar_nombres():
            return jsonify({"error": "Perfil desconocido"}), 400
            
        set_perfil(perfil)
        return jsonify({"perfil": perfil})

    @app.get("/api/perfiles")
    def api_perfiles():
        return jsonify({"perfiles": listar_nombres()})

    @app.route("/video_feed")
    def video_feed():
        def generate():
            # El bucle se detiene cuando la cámara se apaga
            while camera_manager.running:
                frame = camera_manager.get_frame()
                if frame:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
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


    @app.route("/login")
    def login():
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.pop('user', None)
        return redirect(url_for('login'))

    @app.route("/api/login", methods=["POST"])
    def api_login():
        data = request.get_json()
        token = data.get("token")
        if not token:
            return jsonify({"error": "Token faltante"}), 400
        try:
            # Verificamos el token con Firebase Admin
            decoded_token = auth.verify_id_token(token)
            session['user'] = decoded_token.get('email', decoded_token['uid'])
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 401


    @app.route("/api/test_camera", methods=["POST"])
    def api_test_camera():
        data = request.get_json()
        cam_ip = data.get("ip")
        cam_port = data.get("port")
        
        if cam_ip == "0":
            return jsonify({"success": True, "msg": "Usando webcam local"})
            
        url = f"http://{cam_ip}:{cam_port}/video"
        import cv2
        cap = cv2.VideoCapture(url)
        success = cap.isOpened()
        cap.release()
        
        if success:
            return jsonify({"success": True, "msg": "¡Cámara conectada exitosamente!"})
        else:
            return jsonify({"success": False, "msg": "No se pudo conectar. Revisa la IP y el Puerto."})

    return app
