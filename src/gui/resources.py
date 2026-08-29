"""Resolucao e leitura de recursos de interface (layout .ui e folhas de estilo .qss).

Os recursos vivem em ``assets/`` na raiz do repositorio. Em builds empacotados
(PyInstaller) eles sao colados via ``--add-data "assets;assets"`` e resolvidos a
partir de ``sys._MEIPASS``.
"""

from __future__ import annotations

import sys
from pathlib import Path


def asset_root() -> Path:
    """Diretorio onde os recursos de interface estao no ambiente atual."""
    base = getattr(sys, "_MEIPASS", None)
    if base is not None:
        return Path(base) / "assets"
    return Path(__file__).resolve().parents[2] / "assets"


def asset_path(name: str) -> Path:
    """Caminho absoluto de um recurso, com erro claro se estiver ausente."""
    path = asset_root() / name
    if not path.is_file():
        raise FileNotFoundError(
            f"Recurso de interface não encontrado: {name} (procurado em {asset_root()}). "
            "Verifique se a pasta assets/ acompanha a aplicação."
        )
    return path


def load_qss(dark: bool) -> str:
    """Carrega a folha de estilo do tema pedido."""
    theme = "style_dark.qss" if dark else "style_light.qss"
    return asset_path(theme).read_text(encoding="utf-8")
