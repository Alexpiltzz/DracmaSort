"""Gerador de códigos de sorteio a partir de planilhas de participantes."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def _resolve_version() -> str:
    """Resolve a versão do pacote a partir do metadata instalado.

    Em builds PyInstaller ou quando o pacote não está instalado via pip/uv,
    fallback para o valor literal do pyproject.toml.
    """
    try:
        return version("giveaways-tools")
    except PackageNotFoundError:
        return "0.2.3"


__version__: str = _resolve_version()
