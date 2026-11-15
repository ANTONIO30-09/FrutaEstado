import cv2
import threading
import time
from dataclasses import replace
from pathlib import Path
import json
import logging

from src.captura import CapturaVideo
from src.detector_yolo import DetectorYOLO
from src.clasificador import clasificar_bbox, FiltroMayoria
from src.perfiles_frutas import obtener_perfil
from src.config import cargar_config
from src.cliente_esp32 import enviar_estado
# Importamos la función de la DB directamente para evitar peticiones HTTP a nosotros mismos
from dashboard.db import insertar_registro


log = logging.getLogger(__name__)

MAPEO_FRUTAS = {
    "banana": "Plátano",
    "apple": "Manzana",
    "orange": "Mandarina",
    "grape": "Uva",
    "default": "Fruta"
}

ESTADOS_ES = {"S": "Madura", "A": "Inmadura", "R": "Pasada"}


class CameraManager:
    def __init__(self):
        self.thread = None
        self.running = False
        self.frame_actual = None
        self.detector = None
        self._lock = threading.Lock()

    def generar_frames(self):
        print("[CÁMARA] Iniciando hilo de captura...")
        cfg = cargar_config()
        
        config_path = Path(__file__).resolve().parent.parent / "config" / "dispositivos.json"
        if config_path.exists():
            try:
                web_cfg = json.loads(config_path.read_text())
                cfg = replace(cfg, cam_url=web_cfg.get("cam_url", cfg.cam_url), esp32_ip=web_cfg.get("esp32_ip", cfg.esp32_ip))
                print(f"[CÁMARA] Conectando a: {cfg.cam_url}")
            except Exception as e:
                print(f"[CÁMARA] Error leyendo config: {e}")

        try:
            cap = CapturaVideo(cfg.cam_url)
            cap.abrir()
            print("[CÁMARA] ¡Conexión exitosa a la cámara!")
        except Exception as e:
            print(f"[CÁMARA] Error abriendo camara: {e}")
            self.running = False
            return

        self.detector = DetectorYOLO()
        filtro = FiltroMayoria(7)
        estado_anterior = None
        contador = 0
        ultima_deteccion = None

        while self.running:
            frame = cap.leer_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            contador += 1
            # YOLO cada 3 frames
            if contador % 3 == 0:
                det = self.detector.detectar_principal(frame)
                ultima_deteccion = det
            else:
                det = ultima_deteccion

            if det:
                x1, y1, x2, y2 = det.bbox
                h, w = frame.shape[:2]
                x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
                roi = frame[y1:y2, x1:x2]
                
                if roi.size > 0:
                    tipo_fruta = det.clase_yolo
                    perfil = obtener_perfil(tipo_fruta)
                    perfil_bbox = replace(perfil, roi_x_rel=0.0, roi_y_rel=0.0, roi_w_rel=1.0, roi_h_rel=1.0)
                    res = clasificar_bbox(roi, (0,0,roi.shape[1],roi.shape[0]), perfil_bbox)
                    
                    estado = filtro.actualizar(res.estado)
                    
                    if estado and estado != estado_anterior:
                        # Guardamos en DB directamente (sin petición HTTP)
                        try:
                            insertar_registro(estado=estado, pct_verde=res.pct_verde, pct_madura=res.pct_madura, pct_pasada=res.pct_pasada, tipo_fruta=tipo_fruta, db_path=cfg.db_path)
                            enviar_estado(cfg.esp32_ip, cfg.esp32_port, cfg.esp32_endpoint, estado)
                            estado_anterior = estado
                        except Exception as e:
                            print(f"[DB] Error: {e}")

                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    fruta_es = MAPEO_FRUTAS.get(tipo_fruta.lower(), "Fruta")
                    estado_es = ESTADOS_ES.get(estado, "-")
                    cv2.putText(frame, f"{fruta_es} | {estado_es}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                with self._lock:
                    self.frame_actual = buffer.tobytes()

        cap.cerrar()
        print("[CÁMARA] Hilo detenido.")

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.generar_frames, daemon=True)
            self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None
        self.frame_actual = None

    def get_frame(self):
        with self._lock:
            return self.frame_actual
