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
                    # Resolvemos los subtipos usando HSV
                    perfiles_candidatos = []
                    clase_yolo = det.clase_yolo.lower()
                    
                    if clase_yolo == "apple":
                        perfiles_candidatos = ["manzana_roja", "manzana_verde"]
                    elif clase_yolo == "orange":
                        perfiles_candidatos = ["mandarina"]
                    elif clase_yolo == "banana":
                        perfiles_candidatos = ["platano"]
                    else:
                        # Si no es una fruta conocida, usamos default
                        perfiles_candidatos = ["default"]

                    mejor_perfil = "desconocida"
                    mejor_res = None
                    max_pixeles = -1

                    # Probamos los colores para ver cuál encaja mejor
                    for p_nombre in perfiles_candidatos:
                        perfil_t = obtener_perfil(p_nombre)
                        perfil_bbox = replace(perfil_t, roi_x_rel=0.0, roi_y_rel=0.0, roi_w_rel=1.0, roi_h_rel=1.0)
                        res_temp = clasificar_bbox(roi, (0,0,roi.shape[1],roi.shape[0]), perfil_bbox)
                        
                        if res_temp.pixeles_fruta > max_pixeles:
                            max_pixeles = res_temp.pixeles_fruta
                            mejor_perfil = p_nombre
                            mejor_res = res_temp

                    res = mejor_res
                    estado = filtro.actualizar(res.estado)
                    
                    if estado and estado != estado_anterior:
                        # Guardamos el nombre del perfil (ej. "manzana_roja") en la DB para que el filtro funcione
                        try:
                            insertar_registro(estado=estado, pct_verde=res.pct_verde, pct_madura=res.pct_madura, pct_pasada=res.pct_pasada, tipo_fruta=mejor_perfil, db_path=cfg.db_path)
                            enviar_estado(cfg.esp32_ip, cfg.esp32_port, cfg.esp32_endpoint, estado)
                            estado_anterior = estado
                        except Exception as e:
                            print(f"[DB] Error: {e}")

                    # Dibujamos en el video el nombre del perfil (ej. "manzana_verde")
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    estado_es = ESTADOS_ES.get(estado, "-")
                    texto = f"{mejor_perfil} | {estado_es}"
                    cv2.putText(frame, texto, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            if ret:
                with self._lock:
                    self.frame_actual = buffer.tobytes()

            # FRENO DE MANO: Dormimos el hilo para no saturar el procesador
            time.sleep(0.05) 

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
