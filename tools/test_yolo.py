"""Script de prueba aislado para validar YOLO con la webcam local."""
import cv2
import sys
from src.detector_yolo import DetectorYOLO

def main():
    print("Iniciando prueba de YOLO. Presiona 'q' para salir.")
    # Usamos el índice 0 para la webcam integrada de la laptop
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ No se pudo abrir la webcam.")
        return

    detector = DetectorYOLO()
    
    while True:
        ok, frame = cap.read()
        if not ok:
            break
            
        det = detector.detectar_principal(frame)
        
        if det:
            x1, y1, x2, y2 = det.bbox
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            texto = f"{det.clase_yolo} -> {det.tipo_perfil} ({det.confianza:.2f})"
            cv2.putText(frame, texto, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        cv2.imshow("Test YOLO - FrutaEstado", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
