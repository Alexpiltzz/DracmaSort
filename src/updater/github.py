"""Consulta à API do GitHub para a última release."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class ReleaseInfo:
    """Informações de uma release do GitHub."""

    tag: str
    body: str
    asset_url: str
    asset_name: str
    asset_size: int


def check_latest_release(
    repo: str,
    asset_name: str = "DracmaSort.exe",
    *,
    timeout: int = 10,
) -> ReleaseInfo | None:
    """Consulta a release mais recente no GitHub (repositório público).

    Nenhuma autenticação é enviada — Releases públicas respondem via
    GET anônimo à API.

    Returns:
        ``ReleaseInfo`` se encontrou uma release com o asset, ou ``None``
        se não há release ou ocorreu erro de rede.
    """
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError):
        return None

    tag = data.get("tag_name", "")
    body = data.get("body", "")
    assets = data.get("assets", [])

    for asset in assets:
        if asset.get("name") == asset_name:
            return ReleaseInfo(
                tag=tag,
                body=body,
                asset_url=asset["browser_download_url"],
                asset_name=asset_name,
                asset_size=asset.get("size", 0),
            )

    return None
