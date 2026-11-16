import cv2
import threading
import time
import queue
from dataclasses import replace
from pathlib import Path
import json

from src.captura import CapturaVideo
from src.detector_onnx import DetectorONNX
from src.clasificador import clasificar_bbox, FiltroMayoria
from src.perfiles_frutas import obtener_perfil
from src.config import cargar_config
from src.cliente_esp32 import enviar_estado
from dashboard.db import insertar_registro
from dashboard.estado_compartido import get_perfil

ESTADOS_ES = {"S": "Madura", "A": "Inmadura", "R": "Pasada"}

class CameraManager:
    def __init__(self):
        self.hilo_captura = None
        self.hilo_ia = None
        self.running = False
        self.frame_actual = None
        self.cola_frames = queue.Queue(maxsize=1) # Solo guarda el frame más reciente
        self._lock = threading.Lock()

    def _capturar_video(self, cam_url):
        cap = CapturaVideo(cam_url)
        try:
            cap.abrir()
            print(f"[CÁMARA] Conectada a: {cam_url}")
        except Exception as e:
            print(f"[CÁMARA] Error: {e}")
            self.running = False
            return

        while self.running:
            frame = cap.leer_frame()
            if frame is not None:
                # Si la cola está llena, quitamos el frame viejo y ponemos el nuevo
                if self.cola_frames.full():
                    try:
                        self.cola_frames.get_nowait()
                    except queue.Empty:
                        pass
                self.cola_frames.put(frame)
            time.sleep(0.05) # Leemos a ~20 FPS máximo

        cap.cerrar()
        print("[CÁMARA] Captura detenida.")

    def _procesar_ia(self):
        cfg = cargar_config()
        config_path = Path(__file__).resolve().parent.parent / "config" / "dispositivos.json"
        if config_path.exists():
            try:
                web_cfg = json.loads(config_path.read_text())
                cfg = replace(cfg, cam_url=web_cfg.get("cam_url", cfg.cam_url))
            except Exception:
                pass

        detector = DetectorONNX()
        filtro = FiltroMayoria(7)
        estado_anterior = None
        tipo_anterior = None

        while self.running:
            try:
                # Esperamos un frame nuevo (con timeout para poder cerrar el hilo)
                frame = self.cola_frames.get(timeout=0.5)
            except queue.Empty:
                continue

            perfil_forzado = get_perfil()
            bbox_para_dibujar = None
            
            # Procesamiento de IA (YOLO)
            det = detector.detectar_principal(frame)
            
            mejor_perfil = "desconocida"
            mejor_res = None
            perfiles_candidatos = []

            if perfil_forzado != "default":
                if det:
                    clase = det.clase_yolo.lower()
                    es_compatible = False
                    if "apple" in clase and "manzana" in perfil_forzado: es_compatible = True
                    elif "banana" in clase and "platano" in perfil_forzado: es_compatible = True
                    elif "orange" in clase and "mandarina" in perfil_forzado: es_compatible = True
                    elif "grape" in clase and "uva" in perfil_forzado: es_compatible = True
                    
                    if es_compatible:
                        x1, y1, x2, y2 = det.bbox
                        h, w = frame.shape[:2]
                        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
                        roi = frame[y1:y2, x1:x2]
                        bbox_para_dibujar = (x1, y1, x2, y2)
                        perfiles_candidatos = [perfil_forzado]
            else:
                if det:
                    x1, y1, x2, y2 = det.bbox
                    h, w = frame.shape[:2]
                    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
                    roi = frame[y1:y2, x1:x2]
                    bbox_para_dibujar = (x1, y1, x2, y2)
                    
                    clase = det.clase_yolo.lower()
                    if "apple" in clase: perfiles_candidatos = ["manzana_roja", "manzana_verde"]
                    elif "grape" in clase: perfiles_candidatos = ["uva_morada", "uva_verde"]
                    elif "orange" in clase: perfiles_candidatos = ["mandarina"]
                    elif "banana" in clase: perfiles_candidatos = ["platano"]

            if bbox_para_dibujar and perfiles_candidatos:
                max_score = -1
                for p_nombre in perfiles_candidatos:
                    perfil_t = obtener_perfil(p_nombre)
                    perfil_bbox = replace(perfil_t, roi_x_rel=0.0, roi_y_rel=0.0, roi_w_rel=1.0, roi_h_rel=1.0)
                    res_temp = clasificar_bbox(roi, (0,0,roi.shape[1],roi.shape[0]), perfil_bbox)
                    
                    score = res_temp.pixeles_fruta
                    if "verde" in p_nombre: score += res_temp.pct_verde
                    elif "roja" in p_nombre or "morada" in p_nombre: score += (res_temp.pct_madura + res_temp.pct_pasada)

                    if score > max_score:
                        max_score = score
                        mejor_perfil = p_nombre
                        mejor_res = res_temp

                if mejor_res:
                    estado = filtro.actualizar(mejor_res.estado)
                    if estado and (estado != estado_anterior or mejor_perfil != tipo_anterior):
                        try:
                            insertar_registro(estado=estado, pct_verde=mejor_res.pct_verde, pct_madura=mejor_res.pct_madura, pct_pasada=mejor_res.pct_pasada, tipo_fruta=mejor_perfil, db_path=cfg.db_path)
                            enviar_estado(cfg.esp32_ip, cfg.esp32_port, cfg.esp32_endpoint, estado)
                            estado_anterior = estado
                            tipo_anterior = mejor_perfil
                            print(f"[NUEVO] {mejor_perfil} | {estado}")
                        except Exception:
                            pass
                            
                    cv2.rectangle(frame, (bbox_para_dibujar[0], bbox_para_dibujar[1]), (bbox_para_dibujar[2], bbox_para_dibujar[3]), (0, 255, 0), 2)
                    cv2.putText(frame, f"{mejor_perfil} | {ESTADOS_ES.get(estado, '-')}", (bbox_para_dibujar[0], bbox_para_dibujar[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Codificamos a JPG y actualizamos la variable que lee Flask
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ret:
                with self._lock:
                    self.frame_actual = buffer.tobytes()
            
            time.sleep(0.1) # La IA procesa máximo a 10 FPS para no saturar

        print("[CÁMARA] IA detenida.")

    def start(self):
        if not self.running:
            self.running = True
            
            cfg = cargar_config()
            config_path = Path(__file__).resolve().parent.parent / "config" / "dispositivos.json"
            if config_path.exists():
                try:
                    web_cfg = json.loads(config_path.read_text())
                    cfg = replace(cfg, cam_url=web_cfg.get("cam_url", cfg.cam_url), esp32_ip=web_cfg.get("esp32_ip", cfg.esp32_ip))
                except Exception:
                    pass

            self.hilo_captura = threading.Thread(target=self._capturar_video, args=(cfg.cam_url,), daemon=True)
            self.hilo_ia = threading.Thread(target=self._procesar_ia, daemon=True)
            
            self.hilo_captura.start()
            self.hilo_ia.start()

    def stop(self):
        self.running = False
        if self.hilo_captura:
            self.hilo_captura.join(timeout=1)
        if self.hilo_ia:
            self.hilo_ia.join(timeout=1)
        
        # Vaciamos la cola
        while not self.cola_frames.empty():
            try:
                self.cola_frames.get_nowait()
            except queue.Empty:
                break
                
        self.frame_actual = None

    def get_frame(self):
        with self._lock:
            return self.frame_actual
