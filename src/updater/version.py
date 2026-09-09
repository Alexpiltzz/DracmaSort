"""Comparação semântica de versões para o auto-updater."""

from __future__ import annotations


def parse_version(tag: str) -> tuple[int, ...]:
    """Converte uma tag de versão em tupla de inteiros.

    Aceita formatos com ou sem prefixo ``v``:
        ``"v0.2.1"`` → ``(0, 2, 1)``
        ``"0.2.1"``  → ``(0, 2, 1)``

    Suporta também versões com pre-release (``v1.0.0-beta.1``),
    mas ignora o sufixo na comparação.
    """
    cleaned = tag.strip()
    if cleaned.lower().startswith("v"):
        cleaned = cleaned[1:]
    core = cleaned.split("-", 1)[0].split("+", 1)[0]
    return tuple(int(part) for part in core.split("."))


def is_newer(remote_tag: str, local_tag: str) -> bool:
    """Verifica se ``remote_tag`` é estritamente mais nova que ``local_tag``."""
    return parse_version(remote_tag) > parse_version(local_tag)
