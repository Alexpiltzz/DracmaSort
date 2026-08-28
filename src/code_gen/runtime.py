"""Utilidades de caminho para execução em fonte e em executável empacotado."""

from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    """Retorna a raiz do app.

    Em desenvolvimento, aponta para a raiz do repositório.
    Em executável empacotado, aponta para a pasta do ``.exe``.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]
