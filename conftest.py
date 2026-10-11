"""Configuración de pytest: asegura que la raíz del proyecto esté en sys.path."""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
