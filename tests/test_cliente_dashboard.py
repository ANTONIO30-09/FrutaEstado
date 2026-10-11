"""Tests para src/cliente_dashboard.py con requests.post mockeado."""

from unittest.mock import MagicMock, patch

import requests

from src.cliente_dashboard import _resolver_host, enviar_registro


def _respuesta(status_code: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    return r


# ---------- _resolver_host ----------

def test_resolver_host_0_0_0_0_a_localhost():
    assert _resolver_host("0.0.0.0") == "127.0.0.1"


def test_resolver_host_vacio_a_localhost():
    assert _resolver_host("") == "127.0.0.1"


def test_resolver_host_ip_concreta_se_respeta():
    assert _resolver_host("192.168.1.10") == "192.168.1.10"


# ---------- enviar_registro ----------

def test_enviar_registro_201_devuelve_true():
    with patch(
        "src.cliente_dashboard.requests.post", return_value=_respuesta(201)
    ) as m:
        assert enviar_registro("127.0.0.1", 5000, "S", 10.0, 80.0, 10.0) is True
        args, kwargs = m.call_args
        assert args[0] == "http://127.0.0.1:5000/api/registro"
        assert kwargs["json"] == {
            "estado": "S",
            "pct_verde": 10.0,
            "pct_madura": 80.0,
            "pct_pasada": 10.0,
            "tipo_fruta": "desconocida",
        }
        assert kwargs["timeout"] == 2.0


def test_enviar_registro_usa_localhost_si_host_es_0_0_0_0():
    with patch(
        "src.cliente_dashboard.requests.post", return_value=_respuesta(201)
    ) as m:
        enviar_registro("0.0.0.0", 5000, "A", 90.0, 5.0, 5.0)
        args, _ = m.call_args
        assert args[0] == "http://127.0.0.1:5000/api/registro"


def test_enviar_registro_400_devuelve_false():
    with patch(
        "src.cliente_dashboard.requests.post", return_value=_respuesta(400)
    ):
        assert enviar_registro("127.0.0.1", 5000, "S", 0, 0, 0) is False


def test_enviar_registro_500_devuelve_false():
    with patch(
        "src.cliente_dashboard.requests.post", return_value=_respuesta(500)
    ):
        assert enviar_registro("127.0.0.1", 5000, "S", 0, 0, 0) is False


def test_enviar_registro_timeout_devuelve_false():
    with patch(
        "src.cliente_dashboard.requests.post",
        side_effect=requests.Timeout("timeout"),
    ):
        assert enviar_registro("127.0.0.1", 5000, "S", 0, 0, 0) is False


def test_enviar_registro_connection_error_devuelve_false():
    with patch(
        "src.cliente_dashboard.requests.post",
        side_effect=requests.ConnectionError("no route"),
    ):
        assert enviar_registro("127.0.0.1", 5000, "S", 0, 0, 0) is False


def test_enviar_registro_estado_invalido_no_hace_request():
    with patch("src.cliente_dashboard.requests.post") as m:
        assert enviar_registro("127.0.0.1", 5000, "X", 0, 0, 0) is False
        m.assert_not_called()


def test_enviar_registro_estado_vacio_no_hace_request():
    with patch("src.cliente_dashboard.requests.post") as m:
        assert enviar_registro("127.0.0.1", 5000, "", 0, 0, 0) is False
        m.assert_not_called()


def test_enviar_registro_timeout_personalizado():
    with patch(
        "src.cliente_dashboard.requests.post", return_value=_respuesta(201)
    ) as m:
        enviar_registro("127.0.0.1", 5000, "S", 0, 0, 0, timeout=5.0)
        _, kwargs = m.call_args
        assert kwargs["timeout"] == 5.0


# ---------- tipo_fruta (S4.2) ----------

def test_enviar_registro_con_tipo_fruta_explicito():
    from unittest.mock import patch
    with patch(
        "src.cliente_dashboard.requests.post", return_value=_respuesta(201)
    ) as m:
        enviar_registro(
            "127.0.0.1", 5000, "S", 10.0, 80.0, 10.0, tipo_fruta="platano"
        )
        _, kwargs = m.call_args
        assert kwargs["json"]["tipo_fruta"] == "platano"


def test_enviar_registro_tipo_fruta_vacio_usa_default():
    from unittest.mock import patch
    with patch(
        "src.cliente_dashboard.requests.post", return_value=_respuesta(201)
    ) as m:
        enviar_registro("127.0.0.1", 5000, "S", 10.0, 80.0, 10.0, tipo_fruta="   ")
        _, kwargs = m.call_args
        assert kwargs["json"]["tipo_fruta"] == "desconocida"


def test_enviar_registro_sin_tipo_fruta_usa_default():
    from unittest.mock import patch
    with patch(
        "src.cliente_dashboard.requests.post", return_value=_respuesta(201)
    ) as m:
        enviar_registro("127.0.0.1", 5000, "S", 10.0, 80.0, 10.0)
        _, kwargs = m.call_args
        assert kwargs["json"]["tipo_fruta"] == "desconocida"
