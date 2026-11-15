"""Script principal: captura -> YOLO (tipo) + HSV (estado) -> ESP32 + dashboard."""

from __future__ import annotations

import sys
import time
from dataclasses import replace

import cv2
import numpy as np

from src.captura import CapturaVideo
from src.clasificador import FiltroMayoria, ResultadoClasificacion, clasificar_bbox
from src.cliente_dashboard import enviar_registro, obtener_perfil_actual
from src.perfiles_frutas import PerfilFruta, obtener_perfil
from src.cliente_esp32 import enviar_estado
from src.config import Config, cargar_config
from src.detector_yolo import DetectorYOLO

INTERVALO_HEARTBEAT_S = 1.0
INTERVALO_POLLING_PERFIL_S = 2.0

COLORES = {"S": (0, 0, 255), "A": (0, 255, 0), "R": (0, 165, 255)}

def _resolver_perfil_yolo(clase_yolo: str, roi: np.ndarray) -> tuple[str, ResultadoClasificacion]:
    """Prueba los perfiles candidatos y elige el que detecte más píxeles."""
    if clase_yolo == "apple":
        candidatos = ["manzana_roja", "manzana_verde"]
    elif clase_yolo == "grape":
        candidatos = ["uva_morada", "uva_verde"]
    else:
        return clase_yolo, clasificar_bbox(None, (0,0,0,0), obtener_perfil("default")) # fallback

    mejor_perfil = "default"
    mejor_res = ResultadoClasificacion(None, 0.0, 0.0, 0.0, 0)
    max_pixeles = -1

    for p_nombre in candidatos:
        # Forzamos al clasificador a evaluar toda la caja de YOLO
        perfil_base = obtener_perfil(p_nombre)
        perfil_bbox = replace(perfil_base, roi_x_rel=0.0, roi_y_rel=0.0, roi_w_rel=1.0, roi_h_rel=1.0)
        
        # Usamos una imagen dummy para la firma, pero le pasamos la ROI directa
        res = clasificar_bbox(roi, (0, 0, roi.shape[1], roi.shape[0]), perfil_bbox)
        
        if res.pixeles_fruta > max_pixeles:
            max_pixeles = res.pixeles_fruta
            mejor_perfil = p_nombre
            mejor_res = res

    return mejor_perfil, mejor_res

def _loop(cfg: Config) -> int:
    # --- LEER CONFIGURACIÓN DESDE LA WEB ---
    import json
    from dataclasses import replace
    from pathlib import Path
    
    config_path = Path(__file__).resolve().parent.parent / "config" / "dispositivos.json"
    if config_path.exists():
        try:
            web_cfg = json.loads(config_path.read_text())
            cam_url = web_cfg.get("cam_url") or cfg.cam_url
            esp32_ip = web_cfg.get("esp32_ip") or cfg.esp32_ip
            # Al ser una dataclass frozen, usamos replace para generar una nueva
            cfg = replace(cfg, cam_url=cam_url, esp32_ip=esp32_ip)
        except Exception as e:
            print(f"[WARN] No se pudo leer la configuración web: {e}")

    try:
        captura = CapturaVideo(cfg.cam_url)
        captura.abrir()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    detector = DetectorYOLO()
    # El perfil inicial viene del dashboard/entorno
    perfil_manual = obtener_perfil(cfg.perfil_fruta)
    filtro = FiltroMayoria(perfil_manual.ventana_mayoria)
    
    ultimo_polling_monotonic = 0.0
    esp_ok, esp_fail = 0, 0
    dash_ok, dash_fail = 0, 0
    ultimo_ok_ts = None
    ultimo_envio_monotonic = 0.0
    estado_anterior = None

    print(f"Sistema iniciado con YOLO. ESP32: {cfg.esp32_ip}:{cfg.esp32_port}")
    print("Presiona 'q' para salir.")

    try:
        while True:
            frame = captura.leer_frame()
            ahora = time.monotonic()

            resultado = ResultadoClasificacion(None, 0.0, 0.0, 0.0, 0)
            estado_filtrado = None
            tipo_fruta_real = "desconocida"
            bbox = None

            if frame is not None:
                # 1. YOLO detecta qué es y dónde está
                det = detector.detectar_principal(frame)
                
                if det:
                    bbox = det.bbox
                    x1, y1, x2, y2 = bbox
                    h, w = frame.shape[:2]
                    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
                    roi = frame[y1:y2, x1:x2]
                    
                    if roi.size > 0:
                        # 2. Resolvemos si es roja/verde o morada/verde usando HSV
                        if det.clase_yolo in ("apple", "grape"):
                            tipo_fruta_real, resultado = _resolver_perfil_yolo(det.clase_yolo, roi)
                        else:
                            tipo_fruta_real = det.clase_yolo
                            perfil_t = obtener_perfil(tipo_fruta_real)
                            perfil_bbox = replace(perfil_t, roi_x_rel=0.0, roi_y_rel=0.0, roi_w_rel=1.0, roi_h_rel=1.0)
                            resultado = clasificar_bbox(roi, (0, 0, roi.shape[1], roi.shape[0]), perfil_bbox)
                        
                        # Actualizamos el filtro
                        estado_filtrado = filtro.actualizar(resultado.estado)
                        tipo_fruta_real = resultado.perfil

                # Polling por si el usuario cambia el perfil manualmente en el dashboard
                if (ahora - ultimo_polling_monotonic) >= INTERVALO_POLLING_PERFIL_S:
                    nuevo_nombre = obtener_perfil_actual(cfg.flask_host, cfg.flask_port)
                    if nuevo_nombre and nuevo_nombre != perfil_manual.nombre:
                        perfil_manual = obtener_perfil(nuevo_nombre)
                        filtro = FiltroMayoria(perfil_manual.ventana_mayoria)
                        estado_anterior = None
                    ultimo_polling_monotonic = ahora

            # Heartbeat y dashboard
            if estado_filtrado is not None:
                if (ahora - ultimo_envio_monotonic) >= INTERVALO_HEARTBEAT_S:
                    ok = enviar_estado(cfg.esp32_ip, cfg.esp32_port, cfg.esp32_endpoint, estado_filtrado)
                    if ok: esp_ok += 1; ultimo_ok_ts = time.time()
                    else: esp_fail += 1
                    ultimo_envio_monotonic = ahora

                if estado_filtrado != estado_anterior:
                    ok = enviar_registro(
                        host=cfg.flask_host, port=cfg.flask_port,
                        estado=estado_filtrado,
                        pct_verde=resultado.pct_verde, pct_madura=resultado.pct_madura, pct_pasada=resultado.pct_pasada,
                        tipo_fruta=tipo_fruta_real, # Enviamos el tipo real detectado por YOLO+HSV
                    )
                    if ok: dash_ok += 1
                    else: dash_fail += 1
                    estado_anterior = estado_filtrado

            # Overlay visual (SIEMPRE mostramos la ventana, haya o no fruta)
            if frame is not None:
                if bbox:
                    x1, y1, x2, y2 = bbox
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    texto = f"{tipo_fruta_real} | {estado_filtrado or '-'}"
                    color = COLORES.get(estado_filtrado, (255, 255, 255))
                    cv2.putText(frame, texto, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                else:
                    cv2.putText(frame, "Buscando fruta...", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                
                cv2.imshow("FrutaEstado - YOLO + HSV", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        captura.cerrar()
        cv2.destroyAllWindows()

    return 0

if __name__ == "__main__":
    sys.exit(_loop(cargar_config()))
