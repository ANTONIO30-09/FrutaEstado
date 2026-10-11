"""Tests para src/captura.py (con cv2.VideoCapture mockeado)."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.captura import CapturaVideo, ErrorCaptura


def _mock_cap_abierta(frame_valido: bool = True) -> MagicMock:
    """Devuelve un mock de cv2.VideoCapture que abre OK y entrega frames."""
    cap = MagicMock()
    cap.isOpened.return_value = True
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cap.read.return_value = (frame_valido, frame if frame_valido else None)
    return cap


def test_abrir_ok():
    with patch("src.captura.cv2.VideoCapture", return_value=_mock_cap_abierta()):
        cap = CapturaVideo(0, reintentos_max=1)
        cap.abrir()
        assert cap._cap is not None
        cap.cerrar()
        assert cap._cap is None


def test_abrir_falla_tras_reintentos():
    cap_mock = MagicMock()
    cap_mock.isOpened.return_value = False
    with patch("src.captura.cv2.VideoCapture", return_value=cap_mock), \
         patch("src.captura.time.sleep"):  # no esperar 2s en tests
        captura = CapturaVideo("http://no-existe", reintentos_max=3)
        with pytest.raises(ErrorCaptura):
            captura.abrir()


def test_leer_frame_devuelve_frame():
    with patch("src.captura.cv2.VideoCapture", return_value=_mock_cap_abierta()):
        captura = CapturaVideo(0)
        captura.abrir()
        frame = captura.leer_frame()
        assert frame is not None
        assert frame.shape == (480, 640, 3)
        captura.cerrar()


def test_leer_frame_none_si_falla_reconexion():
    cap_mock = MagicMock()
    cap_mock.isOpened.return_value = True
    cap_mock.read.return_value = (False, None)
    with patch("src.captura.cv2.VideoCapture", return_value=cap_mock), \
         patch("src.captura.time.sleep"):
        captura = CapturaVideo(0, reintentos_max=1)
        captura.abrir()
        frame = captura.leer_frame()
        assert frame is None
        captura.cerrar()


def test_context_manager():
    with patch("src.captura.cv2.VideoCapture", return_value=_mock_cap_abierta()):
        with CapturaVideo(0) as captura:
            assert captura._cap is not None
        assert captura._cap is None
