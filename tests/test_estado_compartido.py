"""Tests para dashboard/estado_compartido.py."""

import threading

from dashboard import estado_compartido as ec


def setup_function():
    """Antes de cada test, resetear el estado."""
    ec.reset()


def test_default_inicial():
    assert ec.get_perfil() == "default"


def test_set_y_get():
    ec.set_perfil("platano")
    assert ec.get_perfil() == "platano"


def test_reset_vuelve_a_default():
    ec.set_perfil("uva_morada")
    ec.reset()
    assert ec.get_perfil() == "default"


def test_set_sobreescribe():
    ec.set_perfil("platano")
    ec.set_perfil("uva_verde")
    assert ec.get_perfil() == "uva_verde"


def test_set_vacio_se_guarda_tal_cual():
    """El modulo NO valida: eso lo hace el endpoint. Aqui solo guarda."""
    ec.set_perfil("")
    assert ec.get_perfil() == ""


def test_thread_safety_lecturas_y_escrituras():
    """Varios hilos leyendo/escribiendo no deben corromper el estado."""
    errores: list[Exception] = []

    def worker(nombre: str) -> None:
        try:
            for _ in range(200):
                ec.set_perfil(nombre)
                _ = ec.get_perfil()
        except Exception as exc:  # noqa: BLE001
            errores.append(exc)

    hilos = [threading.Thread(target=worker, args=(f"perfil_{i}",)) for i in range(5)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert errores == []
    # Al final debe haber algun perfil seteado (no importa cual)
    assert ec.get_perfil().startswith("perfil_")
