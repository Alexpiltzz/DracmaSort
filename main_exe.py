"""Gera o executavel da interface grafica em Windows usando PyInstaller.

Uso:
    uv run python main_exe.py

Opcionalmente:
    uv run python main_exe.py --name MeuApp
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

DEFAULT_APP_NAME = "DracmaSort"


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
        "main_ui.py",
    ]
    result = subprocess.run(cmd, cwd=repo_root, check=False)
    if result.returncode == 0 and not keep_artifacts:
        _cleanup_artifacts(repo_root, name, icon_path)
    return result.returncode


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
    args = parser.parse_args(argv)
    return build_executable(args.name, keep_artifacts=args.keep_artifacts)


if __name__ == "__main__":
    raise SystemExit(main())
