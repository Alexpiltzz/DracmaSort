"""Download de assets de release com progresso."""

from __future__ import annotations

import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path


def download_asset(
    url: str,
    dest: Path,
    *,
    on_progress: Callable[[int, int], None] | None = None,
    timeout: int = 30,
    chunk_size: int = 65536,
) -> Path:
    """Baixa um asset de release para um arquivo local.

    Args:
        url: URL de download do asset.
        dest: Caminho de destino (arquivo).
        on_progress: Callback ``(bytes_baixados, total_bytes)``.
            ``total_bytes`` pode ser 0 se o servidor não informar Content-Length.
        timeout: Timeout da requisição em segundos.
        chunk_size: Tamanho do chunk de leitura.

    Returns:
        O caminho do arquivo baixado (mesmo que ``dest``).

    Raises:
        ConnectionError: Se a requisição falhar.
    """
    headers = {"Accept": "application/octet-stream"}
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0

            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress:
                        on_progress(downloaded, total)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        raise ConnectionError(f"Falha ao baixar asset: {exc}") from exc

    return dest


def temp_download_path(tag: str, asset_name: str) -> Path:
    """Gera um caminho temporário para download de uma release."""
    safe_tag = tag.replace("/", "_").replace("\\", "_")
    filename = f"{asset_name.rsplit('.', 1)[0]}_{safe_tag}.exe"
    return Path(tempfile.gettempdir()) / filename
