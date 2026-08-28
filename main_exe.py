"""Gera o executavel da interface grafica em Windows usando PyInstaller.

Uso:
    uv run python main_exe.py

Opcionalmente:
    uv run python main_exe.py --name MeuApp
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

DEFAULT_APP_NAME = "DracmaSort"


def build_executable(name: str) -> int:
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
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera o executavel da interface grafica.")
    parser.add_argument(
        "--name",
        default=DEFAULT_APP_NAME,
        help="Nome do executavel gerado em dist/.",
    )
    args = parser.parse_args(argv)
    return build_executable(args.name)


if __name__ == "__main__":
    raise SystemExit(main())
