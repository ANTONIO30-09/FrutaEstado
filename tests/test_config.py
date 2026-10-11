"""Tests para src/config.py."""

import pytest

from src.config import ErrorConfiguracion, cargar_config


def test_cargar_config_con_cam_url_url(monkeypatch):
    monkeypatch.setenv("CAM_URL", "http://192.168.1.50:4747/video")
    monkeypatch.setenv("ESP32_IP", "10.0.0.5")
    monkeypatch.setenv("ESP32_PORT", "80")
    cfg = cargar_config()
    assert cfg.cam_url == "http://192.168.1.50:4747/video"
    assert cfg.esp32_ip == "10.0.0.5"
    assert cfg.esp32_port == 80


def test_cargar_config_con_cam_url_webcam(monkeypatch):
    monkeypatch.setenv("CAM_URL", "0")
    cfg = cargar_config()
    assert cfg.cam_url == 0


def test_cargar_config_falla_sin_cam_url(monkeypatch):
    monkeypatch.delenv("CAM_URL", raising=False)
    with pytest.raises(ErrorConfiguracion):
        cargar_config()


def test_cargar_config_falla_con_cam_url_vacia(monkeypatch):
    monkeypatch.setenv("CAM_URL", "   ")
    with pytest.raises(ErrorConfiguracion):
        cargar_config()
