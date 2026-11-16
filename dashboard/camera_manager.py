import cv2
import threading
import time
from dataclasses import replace
from pathlib import Path
import json
import logging

from src.captura import CapturaVideo
from src.detector_onnx import DetectorONNX
from src.clasificador import clasificar_bbox, FiltroMayoria
from src.perfiles_frutas import obtener_perfil
from src.config import cargar_config
from src.cliente_esp32 import enviar_estado
from dashboard.db import insertar_registro
from dashboard.estado_compartido import get_perfil

log = logging.getLogger(__name__)
ESTADOS_ES = {"S": "Madura", "A": "Inmadura", "R": "Pasada"}

class CameraManager:
    def __init__(self):
        self.thread = None
        self.running = False
        self.frame_actual = None
        self.detector = None
        self._lock = threading.Lock()

    def generar_frames(self):
        print("[CÁMARA] Iniciando hilo...")
        cfg = cargar_config()
        
        config_path = Path(__file__).resolve().parent.parent / "config" / "dispositivos.json"
        if config_path.exists():
            try:
                web_cfg = json.loads(config_path.read_text())
                cfg = replace(cfg, cam_url=web_cfg.get("cam_url", cfg.cam_url))
            except Exception:
                pass

        try:
            cap = CapturaVideo(cfg.cam_url)
            cap.abrir()
            print(f"[CÁMARA] Conectada a: {cfg.cam_url}")
        except Exception as e:
            print(f"[CÁMARA] Error: {e}")
            self.running = False
            return

        self.detector = DetectorONNX()
        filtro = FiltroMayoria(7)
        estado_anterior = None
        tipo_anterior = None
        contador = 0
        ultima_deteccion = None

        while self.running:
            frame = cap.leer_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            contador += 1
            if contador % 5 == 0:
                det_nueva = self.detector.detectar_principal(frame)
                ultima_deteccion = det_nueva if det_nueva else None

            det = ultima_deteccion
            perfil_forzado = get_perfil()

            bbox_para_dibujar = None
            roi = None
            perfiles_candidatos = []

            # --- Lógica de selección de perfil ---
            if perfil_forzado != "default":
                # El usuario forzó una fruta en el menú
                h, w = frame.shape[:2]
                x1, y1, x2, y2 = int(w*0.25), int(h*0.25), int(w*0.75), int(h*0.75)
                roi = frame[y1:y2, x1:x2]
                bbox_para_dibujar = (x1, y1, x2, y2)
                perfiles_candidatos = [perfil_forzado]
                print(f"[DEBUG] Modo Forzado: {perfil_forzado}") if contador % 30 == 0 else None

            elif det:
                # YOLO detectó algo
                x1, y1, x2, y2 = det.bbox
                h, w = frame.shape[:2]
                x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
                roi = frame[y1:y2, x1:x2]
                bbox_para_dibujar = (x1, y1, x2, y2)

                clase_yolo = det.clase_yolo.lower()
                if "apple" in clase_yolo:
                    perfiles_candidatos = ["manzana_roja", "manzana_verde"]
                elif "grape" in clase_yolo:
                    perfiles_candidatos = ["uva_morada", "uva_verde"]
                elif "orange" in clase_yolo:
                    perfiles_candidatos = ["mandarina"]
                elif "banana" in clase_yolo:
                    perfiles_candidatos = ["platano"]
                else:
                    perfiles_candidatos = ["default"]
                print(f"[DEBUG] YOLO detectó: {clase_yolo} ({det.confianza:.2f})") if contador % 30 == 0 else None

            # --- Evaluación y guardado (AQUÍ ESTABA EL ERROR DE INDENTACIÓN) ---
            if roi is not None and roi.size > 0 and perfiles_candidatos:
                mejor_perfil = "desconocida"
                mejor_res = None
                max_score = -1

                for p_nombre in perfiles_candidatos:
                    perfil_t = obtener_perfil(p_nombre)
                    perfil_bbox = replace(perfil_t, roi_x_rel=0.0, roi_y_rel=0.0, roi_w_rel=1.0, roi_h_rel=1.0)
                    res_temp = clasificar_bbox(roi, (0,0,roi.shape[1],roi.shape[0]), perfil_bbox)
                    
                    # Damos prioridad al porcentaje de color sobre la cantidad de píxeles
                    if "verde" in p_nombre:
                        score = res_temp.pct_verde
                    elif "roja" in p_nombre or "morada" in p_nombre:
                        score = (res_temp.pct_madura + res_temp.pct_pasada)
                    else:
                        score = res_temp.pixeles_fruta

                    if score > max_score:
                        max_score = score
                        mejor_perfil = p_nombre
                        mejor_res = res_temp

                if mejor_res:
                    # VALIDACIÓN ESTRICTA UNIVERSAL (Para todas las frutas)
                    es_valido = True
                    if perfil_forzado != "default":
                        # Frutas verdes
                        if "verde" in perfil_forzado and mejor_res.pct_verde < 35:
                            es_valido = False
                        # Frutas rojas, moradas o naranjas (mandarina)
                        elif ("roja" in perfil_forzado or "morada" in perfil_forzado or "mandarina" in perfil_forzado) and (mejor_res.pct_madura + mejor_res.pct_pasada) < 35:
                            es_valido = False
                        # Plátano (puede ser verde o amarillo)
                        elif "platano" in perfil_forzado and (mejor_res.pct_madura + mejor_res.pct_verde) < 35:
                            es_valido = False

                    if es_valido:
                        res = mejor_res
                        estado = filtro.actualizar(res.estado)
                        
                        if estado:
                            print(f'[ANÁLISIS] Fruta: {mejor_perfil} | Estado: {estado} | Píxeles: {res.pixeles_fruta}')
                            if estado != estado_anterior or mejor_perfil != tipo_anterior:
                                try:
                                    insertar_registro(estado=estado, pct_verde=res.pct_verde, pct_madura=res.pct_madura, pct_pasada=res.pct_pasada, tipo_fruta=mejor_perfil, db_path=cfg.db_path)
                                    enviar_estado(cfg.esp32_ip, cfg.esp32_port, cfg.esp32_endpoint, estado)
                                    estado_anterior = estado
                                    tipo_anterior = mejor_perfil
                                    print(f"[DB] Guardado: {mejor_perfil} - {estado}")
                                except Exception as e:
                                    print(f"[DB] Error: {e}")
                    else:
                        # Si no cumple el color, no dibujamos nada
                        bbox_para_dibujar = None
                        estado = None

                    # Dibujamos
                    cv2.rectangle(frame, (bbox_para_dibujar[0], bbox_para_dibujar[1]), (bbox_para_dibujar[2], bbox_para_dibujar[3]), (0, 255, 0), 2)
                    estado_es = ESTADOS_ES.get(estado, "-")
                    texto = f"{mejor_perfil} | {estado_es}"
                    cv2.putText(frame, texto, (bbox_para_dibujar[0], bbox_para_dibujar[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ret:
                with self._lock:
                    self.frame_actual = buffer.tobytes()

            time.sleep(0.03) 

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
