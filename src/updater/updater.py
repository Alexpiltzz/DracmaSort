"""Worker QThread para verificação e download de atualizações."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from code_gen import __version__
from code_gen.runtime import app_root
from updater._build_config import GITHUB_ASSET_NAME, GITHUB_REPO
from updater.download import download_asset, temp_download_path
from updater.github import ReleaseInfo, check_latest_release
from updater.version import is_newer


def _effective_token() -> str:
    """Resolve o token do updater somente quando ele vai ser usado.

    O token NUNCA é embutido no executável e não depende do módulo SMTP
    (importar ``delivery.smtp`` não carrega nenhuma credencial do updater).
    É lido:
        1. da variável de ambiente ``GITHUB_TOKEN`` (precedência — dev/testes), ou
        2. do arquivo ``.env.updater`` ao lado do executável (distribuído junto
           com o app, contém apenas ``GITHUB_TOKEN``).

    Esta função só é chamada dentro de ``check()``/``download()``, quando o
    updater realmente vai consultar uma Release ou baixar um asset.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        return token

    env_path = app_root() / ".env.updater"
    if not env_path.is_file():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if key.strip() == "GITHUB_TOKEN":
            return value.strip()
    return ""


class UpdateWorker(QObject):
    """Verifica releases e baixa atualização em background.

    Fluxo separado em duas etapas:
        1. ``check()`` — consulta a API e emite ``update_available`` ou ``up_to_date``.
        2. ``download()`` — baixa o asset (chamado após confirmação do usuário).

    Sinais:
        update_available(tag, body, asset_url):
            Emitido quando uma versão mais nova está disponível.
        progress(current, total):
            Emitido durante o download (bytes).
        download_finished(path):
            Emitido quando o download termina com sucesso.
        error(msg):
            Emitido quando ocorre um erro (silencioso na UI).
        up_to_date:
            Emitido quando não há atualização disponível.
    """

    update_available = pyqtSignal(str, str, str)
    progress = pyqtSignal(int, int)
    download_finished = pyqtSignal(str)
    error = pyqtSignal(str)
    up_to_date = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._download_path: str | None = None
        self._pending_release: ReleaseInfo | None = None

    @property
    def pending_download(self) -> str | None:
        """Caminho do .exe baixado pendente de instalação."""
        return self._download_path

    def check(self) -> None:
        """Verifica se há uma release mais nova disponível."""
        token = _effective_token()
        if not token:
            self.error.emit("GITHUB_TOKEN não configurado. Atualização automática desabilitada.")
            return

        release = check_latest_release(token, GITHUB_REPO, GITHUB_ASSET_NAME)
        if release is None:
            self.error.emit("Não foi possível consultar releases do GitHub.")
            return

        local_version = f"v{__version__}"
        if not is_newer(release.tag, local_version):
            self.up_to_date.emit()
            return

        self._pending_release = release
        self.update_available.emit(release.tag, release.body, release.asset_url)

    def download(self) -> None:
        """Baixa o asset da release pendente.

        Deve ser chamado apenas após ``update_available`` e com
        confirmação do usuário.
        """
        if not self._pending_release:
            self.error.emit("Nenhuma release pendente para download.")
            return

        release = self._pending_release
        dest = temp_download_path(release.tag, release.asset_name)
        token = _effective_token()
        try:
            download_asset(
                release.asset_url,
                dest,
                on_progress=lambda cur, tot: self.progress.emit(cur, tot),
                token=token,
            )
        except ConnectionError as exc:
            self.error.emit(str(exc))
            return

        self._download_path = str(dest)
        self.download_finished.emit(str(dest))

    def apply_update(self) -> None:
        """Substitui o .exe atual pelo baixado e relança o app.

        Deve ser chamado apenas após ``download_finished`` e com
        confirmação do usuário. Funciona apenas em modo frozen (PyInstaller).
        """
        if not self._download_path:
            return

        new_exe = Path(self._download_path)
        if not new_exe.is_file():
            self.error.emit(f"Arquivo de atualização não encontrado: {new_exe}")
            return

        if not getattr(sys, "frozen", False):
            self.error.emit("Atualização automática só funciona no executável.")
            return

        current_exe = Path(sys.executable).resolve()
        backup_exe = current_exe.with_suffix(".exe.bak")

        try:
            if backup_exe.exists():
                backup_exe.unlink()
            current_exe.rename(backup_exe)
            new_exe.rename(current_exe)
        except OSError as exc:
            self.error.emit(f"Falha ao substituir executável: {exc}")
            return

        os.startfile(str(current_exe))
        os._exit(0)  # noqa: SLF001 — forçar saída imediata após relançar
