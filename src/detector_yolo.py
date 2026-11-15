"""Detector de frutas basado en YOLO (Ultralytics) y mapeo a perfiles HSV."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

# Mapeo de clases COCO (inglés) a perfiles del proyecto (español)
MAPEO_YOLO_A_PERFIL = {
    "banana": "platano",
    "orange": "mandarina",
    "apple": "manzana_roja",  # Asumimos roja por defecto
    "grape": "uva_morada",    # Asumimos morada por defecto
    # Si YOLO detecta algo más, se usará el perfil "default"
}

CLASES_PERMITIDAS = {"banana", "orange", "apple", "grape"}

@dataclass(frozen=True)
class Deteccion:
    clase_yolo: str
    tipo_perfil: str
    confianza: float
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)

class DetectorYOLO:
    def __init__(self, modelo_path: str = "yolov8n.pt", confianza_min: float = 0.40):
        if YOLO is None:
            raise RuntimeError("Falta ultralytics. Ejecuta: pip install ultralytics")
        self.modelo = YOLO(modelo_path)
        self.confianza_min = confianza_min

    def detectar_principal(self, frame_bgr: np.ndarray) -> Optional[Deteccion]:
        """Devuelve la detección de fruta con mayor confianza en el frame."""
        resultados = self.modelo.predict(frame_bgr, conf=self.confianza_min, verbose=False)
        mejor_det = None
        mejor_conf = 0.0

        for r in resultados:
            nombres = r.names
            for box in r.boxes:
                clase_yolo = nombres[int(box.cls[0])].lower()
                if clase_yolo not in CLASES_PERMITIDAS:
                    continue
                
                conf = float(box.conf[0])
                if conf > mejor_conf:
                    mejor_conf = conf
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    tipo_perfil = MAPEO_YOLO_A_PERFIL.get(clase_yolo, "default")
                    mejor_det = Deteccion(
                        clase_yolo=clase_yolo,
                        tipo_perfil=tipo_perfil,
                        confianza=conf,
                        bbox=(x1, y1, x2, y2)
                    )
        return mejor_det
