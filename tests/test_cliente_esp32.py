"""Tests para src/cliente_esp32.py con requests.get mockeado."""

from unittest.mock import MagicMock, patch

import requests

from src.cliente_esp32 import _construir_url, enviar_estado


def _respuesta(status_code: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    return r


def test_construir_url_con_slash():
    assert _construir_url("1.2.3.4", 80, "/estado") == "http://1.2.3.4:80/estado"


def test_construir_url_sin_slash():
    assert _construir_url("1.2.3.4", 80, "estado") == "http://1.2.3.4:80/estado"


def test_enviar_estado_200_devuelve_true():
    with patch("src.cliente_esp32.requests.get", return_value=_respuesta(200)) as m:
        assert enviar_estado("1.2.3.4", 80, "/estado", "S") is True
        args, kwargs = m.call_args
        assert args[0] == "http://1.2.3.4:80/estado"
        assert kwargs["params"] == {"valor": "S"}
        assert kwargs["timeout"] == 1.5


def test_enviar_estado_400_devuelve_false():
    with patch("src.cliente_esp32.requests.get", return_value=_respuesta(400)):
        assert enviar_estado("1.2.3.4", 80, "/estado", "A") is False


def test_enviar_estado_500_devuelve_false():
    with patch("src.cliente_esp32.requests.get", return_value=_respuesta(500)):
        assert enviar_estado("1.2.3.4", 80, "/estado", "R") is False


def test_enviar_estado_timeout_devuelve_false():
    with patch(
        "src.cliente_esp32.requests.get",
        side_effect=requests.Timeout("timeout"),
    ):
        assert enviar_estado("1.2.3.4", 80, "/estado", "S") is False


def test_enviar_estado_connection_error_devuelve_false():
    with patch(
        "src.cliente_esp32.requests.get",
        side_effect=requests.ConnectionError("no route"),
    ):
        assert enviar_estado("1.2.3.4", 80, "/estado", "S") is False


def test_enviar_estado_valor_invalido_no_hace_request():
    with patch("src.cliente_esp32.requests.get") as m:
        assert enviar_estado("1.2.3.4", 80, "/estado", "X") is False
        m.assert_not_called()


def test_enviar_estado_valor_vacio_no_hace_request():
    with patch("src.cliente_esp32.requests.get") as m:
        assert enviar_estado("1.2.3.4", 80, "/estado", "") is False
        m.assert_not_called()


def test_enviar_estado_timeout_personalizado():
    with patch(
        "src.cliente_esp32.requests.get", return_value=_respuesta(200)
    ) as m:
        enviar_estado("1.2.3.4", 80, "/estado", "S", timeout=2.5)
        _, kwargs = m.call_args
        assert kwargs["timeout"] == 2.5
