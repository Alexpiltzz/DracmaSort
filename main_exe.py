"""Gera o executavel da interface grafica em Windows usando PyInstaller.

Uso:
    uv run python main_exe.py

Com release:
    $env:GITHUB_RELEASE_TOKEN = "ghp_..."
    uv run python main_exe.py --release

Opcionalmente:
    uv run python main_exe.py --name MeuApp
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_APP_NAME = "DracmaSort"
ASSETS_DATA = "assets" + os.pathsep + "assets"
GITHUB_REPO = "Alexpiltzz/Giveaways_Tools"
GITHUB_ASSET_NAME = "DracmaSort.exe"


def _release_token() -> str:
    """Resolve o token de publicação apenas no ambiente de desenvolvimento.

    Precedência:
        1. variável de ambiente ``GITHUB_RELEASE_TOKEN`` (shell do dev);
        2. chave ``GITHUB_RELEASE_TOKEN`` em ``.env`` local (gitignored).

    ``main_exe.py`` é ferramenta de dev/build — nunca é empacotada no
    executável. O token tem permissão de escrita (Contents: Read+Write)
    para publicar Releases e não faz parte do pacote distribuído.
    """
    token = os.environ.get("GITHUB_RELEASE_TOKEN", "")
    if token:
        return token

    env_file = Path(__file__).resolve().parent / ".env"
    if not env_file.is_file():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if key.strip() == "GITHUB_RELEASE_TOKEN":
            return value.strip()
    return ""


_REDIRECT_CODES = {301, 302, 303, 307, 308}


def _urlopen_follow_redirects(req: urllib.request.Request, timeout: int, *, max_redirects: int = 5):
    """Abre uma requisição seguindo redirecionamentos 3xx manualmente.

    A API do GitHub pode responder ``307`` apontando para a URL canônica do
    repositório (``/repositories/{id}/...``) e o ``urllib.request`` não segue
    redirecionamento de POST de forma confiável. Este helper reenvia a mesma
    requisição (método, corpo e headers) até resolver a URL.
    """
    for _ in range(max_redirects + 1):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code not in _REDIRECT_CODES:
                raise
            location = exc.headers.get("Location")
            if not location:
                raise
            req = urllib.request.Request(
                location,
                data=req.data,
                headers=dict(req.headers),
                method=req.get_method(),
            )
    raise RuntimeError("Redirecionamentos demais ao publicar a release.")


def _read_version(repo_root: Path) -> str:
    """Lê a versão do pyproject.toml."""
    pyproject = repo_root / "pyproject.toml"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def _git_log_since_last_tag(repo_root: Path, version: str) -> str:
    """Gera changelog a partir do git log desde a última tag."""
    tag = f"v{version}"
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", f"{tag}..HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return ""
        lines = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
        return "\n".join(f"- {line}" for line in lines)
    except FileNotFoundError:
        return ""


def _create_github_release(
    token: str,
    version: str,
    changelog: str,
    exe_path: Path,
) -> tuple[str, str]:
    """Cria uma release no GitHub e faz upload do executável.

    Returns:
        Tupla (release_url, asset_url).
    """
    tag = f"v{version}"
    body = f"## DracmaSort {tag}\n\n"
    if changelog:
        body += f"### Alterações\n\n{changelog}\n\n"
    body += "### Executável\n\n"
    body += f"Baixe o `{GITHUB_ASSET_NAME}` e execute diretamente no Windows.\n"

    release_payload = {
        "tag_name": tag,
        "name": tag,
        "target_commitish": "main",
        "body": body,
        "draft": False,
        "prerelease": False,
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }

    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
    req = urllib.request.Request(
        url,
        data=json.dumps(release_payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with _urlopen_follow_redirects(req, timeout=30) as resp:
            release_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Erro ao criar release: HTTP {exc.code}\n{error_body}") from exc

    release_id = release_data["id"]
    release_url = release_data["html_url"]

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"  Uploadando {GITHUB_ASSET_NAME} ({size_mb:.1f} MB)...")

    upload_url = (
        f"https://uploads.github.com/repos/{GITHUB_REPO}"
        f"/releases/{release_id}/assets?name={GITHUB_ASSET_NAME}"
    )
    upload_req = urllib.request.Request(
        upload_url,
        data=exe_path.read_bytes(),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/octet-stream",
        },
        method="POST",
    )

    try:
        with _urlopen_follow_redirects(upload_req, timeout=300) as resp:
            asset_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Erro ao uploadar asset: HTTP {exc.code}\n{error_body}") from exc

    asset_url = asset_data["browser_download_url"]
    return release_url, asset_url


def _cleanup_artifacts(repo_root: Path, name: str, icon_path: Path) -> None:
    """Remove artefatos temporários do build, preservando o ``dist/``."""
    spec_path = repo_root / f"{name}.spec"
    build_dir = repo_root / "build"

    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)
    if spec_path.exists():
        spec_path.unlink()
    if icon_path.exists():
        icon_path.unlink()


def build_executable(name: str, *, keep_artifacts: bool = False) -> int:
    """Executa o PyInstaller com a configuracao usada no build da UI."""
    repo_root = Path(__file__).resolve().parent
    icon_path = repo_root / "assets" / "icone.ico"

    icon_build = [
        "uv",
        "run",
        "--with",
        "pillow",
        "python",
        "assets/png_to_ico.py",
        "--output",
        str(icon_path),
    ]
    icon_result = subprocess.run(icon_build, cwd=repo_root, check=False)
    if icon_result.returncode != 0:
        return icon_result.returncode

    cmd = [
        "uv",
        "run",
        "--with",
        "pyinstaller",
        "pyinstaller",
        "--noconsole",
        "--onefile",
        "--clean",
        "--name",
        name,
        "--icon",
        str(icon_path),
        "--paths",
        "src",
        "--collect-all",
        "PyQt6",
        "--add-data",
        ASSETS_DATA,
        "main_ui.py",
    ]
    result = subprocess.run(cmd, cwd=repo_root, check=False)
    if result.returncode == 0 and not keep_artifacts:
        _cleanup_artifacts(repo_root, name, icon_path)
    return result.returncode


def release(name: str, *, keep_artifacts: bool = False) -> int:
    """Build + publica como release no GitHub."""
    repo_root = Path(__file__).resolve().parent
    token = _release_token()
    if not token:
        print("ERRO: GITHUB_RELEASE_TOKEN não definido.")
        print(
            "Defina a variável de ambiente GITHUB_RELEASE_TOKEN no shell "
            "ou a chave GITHUB_RELEASE_TOKEN no arquivo .env local "
            "(ambos apenas no ambiente de desenvolvimento)."
        )
        return 1

    version = _read_version(repo_root)
    print(f"Versão: {version}")

    print(f"Buildando {name}.exe...")
    rc = build_executable(name, keep_artifacts=keep_artifacts)
    if rc != 0:
        print(f"ERRO: build falhou com código {rc}")
        return rc

    exe_path = repo_root / "dist" / f"{name}.exe"
    if not exe_path.exists():
        print(f"ERRO: executável não encontrado: {exe_path}")
        return 1

    print(f"Gerando changelog para v{version}...")
    changelog = _git_log_since_last_tag(repo_root, version)
    if changelog:
        print(f"  {len(changelog.splitlines())} commit(s) desde a última tag.")

    print(f"Criando release v{version} no GitHub...")
    try:
        release_url, asset_url = _create_github_release(token, version, changelog, exe_path)
    except RuntimeError as exc:
        print(f"ERRO: {exc}")
        return 1

    print("\nRelease criada com sucesso!")
    print(f"  Release: {release_url}")
    print(f"  Asset:   {asset_url}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera o executavel da interface grafica.")
    parser.add_argument(
        "--name",
        default=DEFAULT_APP_NAME,
        help="Nome do executavel gerado em dist/.",
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Mantém build/, .spec e o .ico gerado para depuração.",
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="Build + publica como release no GitHub (requer GITHUB_RELEASE_TOKEN).",
    )
    args = parser.parse_args(argv)

    if args.release:
        return release(args.name, keep_artifacts=args.keep_artifacts)
    return build_executable(args.name, keep_artifacts=args.keep_artifacts)


if __name__ == "__main__":
    raise SystemExit(main())
