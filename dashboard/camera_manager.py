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
from src.cliente_dashboard import enviar_registro

log = logging.getLogger(__name__)

class CameraManager:
    def __init__(self):
        self.thread = None
        self.running = False
        self.frame_actual = None
        self.detector = None
        self._lock = threading.Lock()

    def generar_frames(self):
        cfg = cargar_config()
        
        # Leer config del JSON
        config_path = Path(__file__).resolve().parent.parent / "config" / "dispositivos.json"
        if config_path.exists():
            try:
                web_cfg = json.loads(config_path.read_text())
                cfg = replace(cfg, cam_url=web_cfg.get("cam_url", cfg.cam_url), esp32_ip=web_cfg.get("esp32_ip", cfg.esp32_ip))
            except Exception:
                pass

        try:
            cap = CapturaVideo(cfg.cam_url)
            cap.abrir()
        except Exception as e:
            log.error(f"Error abriendo camara: {e}")
            self.running = False
            return

        self.detector = DetectorYOLO()
        filtro = FiltroMayoria(7)
        estado_anterior = None

        while self.running:
            frame = cap.leer_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            # YOLO + HSV
            det = self.detector.detectar_principal(frame)
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
                        enviar_registro(
                            host=cfg.flask_host, port=cfg.flask_port,
                            estado=estado, pct_verde=res.pct_verde, pct_madura=res.pct_madura, pct_pasada=res.pct_pasada,
                            tipo_fruta=tipo_fruta
                        )
                        enviar_estado(cfg.esp32_ip, cfg.esp32_port, cfg.esp32_endpoint, estado)
                        estado_anterior = estado

                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"{tipo_fruta} | {estado or '-'}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Convertir a JPEG y guardar
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                with self._lock:
                    self.frame_actual = buffer.tobytes()

        cap.cerrar()

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
