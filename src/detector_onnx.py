"""Detector de frutas basado en ONNX Runtime (ultra ligero)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np
import cv2
import onnxruntime as ort
from pathlib import Path

# Mapeo de las 10 clases del modelo a los nombres de tus perfiles
# NOTA: Ajustaremos esto cuando verifiquemos los nombres exactos.
CLASES_MODELO = [
    "apple", "banana", "grape", "orange", "pineapple", "watermelon"
]

MAPEO_YOLO_A_PERFIL = {
    "apple": "manzana_roja",
    "banana": "platano",
    "orange": "mandarina",
    "grape": "uva_morada",
    # Los demás usarán el perfil default
}

@dataclass(frozen=True)
class Deteccion:
    clase_yolo: str
    tipo_perfil: str
    confianza: float
    bbox: tuple[int, int, int, int]

class DetectorONNX:
    def __init__(self, modelo_path: str = "models/frutas.onnx", confianza_min: float = 0.25):
        self.modelo_path = str(Path(__file__).resolve().parent.parent / modelo_path)
        # Forzamos a usar 1 solo hilo de CPU para no congelar Flask
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        self.session = ort.InferenceSession(self.modelo_path, sess_options=opts, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        self.confianza_min = confianza_min

    def detectar_principal(self, frame_bgr: np.ndarray) -> Optional[Deteccion]:
        # 1. Preprocesamiento (Redimensionar a 416x416 y normalizar)
        img_h, img_w = frame_bgr.shape[:2]
        img_resized = cv2.resize(frame_bgr, (416, 416))
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
        
        # Transponer a formato CHW y añadir dimensión de lote [1, 3, 416, 416]
        img_input = np.transpose(img_rgb, (2, 0, 1)).astype(np.float32) / 255.0
        img_input = np.expand_dims(img_input, axis=0)

        # 2. Inferencia
        outputs = self.session.run(None, {self.input_name: img_input})[0]

        # 3. Postprocesamiento (Formato YOLOv8: [1, 4+clases, 3549])
        outputs = np.squeeze(outputs).T
        bboxes = []
        confidences = []
        class_ids = []

        for row in outputs:
            classes_scores = row[4:]
            class_id = np.argmax(classes_scores)
            max_score = classes_scores[class_id]

            if max_score >= self.confianza_min:
                # Convertir coordenadas de 416x416 a la imagen original
                cx, cy, w, h = row[0], row[1], row[2], row[3]
                x_scale = img_w / 416.0
                y_scale = img_h / 416.0

                x1 = int((cx - w/2) * x_scale)
                y1 = int((cy - h/2) * y_scale)
                w_scaled = int(w * x_scale)
                h_scaled = int(h * y_scale)

                bboxes.append([x1, y1, w_scaled, h_scaled])
                confidences.append(float(max_score))
                class_ids.append(class_id)

        if not bboxes:
            return None
        # print(f'[YOLO] Objetos crudos detectados: {len(bboxes)}')

        # 4. Non-Maximum Suppression (Evitar cajas duplicadas)
        indices = cv2.dnn.NMSBoxes(bboxes, confidences, self.confianza_min, 0.45)
        
        if len(indices) == 0:
            return None
            
        # Tomamos la detección con mayor confianza
        best_idx = int(indices[0])
        box = bboxes[best_idx]
        conf = confidences[best_idx]
        c_id = class_ids[best_idx]
        
        clase_yolo = CLASES_MODELO[c_id] if c_id < len(CLASES_MODELO) else "desconocida"
        tipo_perfil = MAPEO_YOLO_A_PERFIL.get(clase_yolo, "default")

        return Deteccion(
            clase_yolo=clase_yolo,
            tipo_perfil=tipo_perfil,
            confianza=conf,
            bbox=(box[0], box[1], box[0] + box[2], box[1] + box[3])
        )
