"""Converte a imagem PNG do projeto em um arquivo ICO."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def build_icon(input_path: Path, output_path: Path) -> Path:
    """Gera um ICO multi-resolução a partir do PNG informado."""
    image = Image.open(input_path).convert("RGBA")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(
        output_path,
        sizes=[
            (16, 16),
            (24, 24),
            (32, 32),
            (48, 48),
            (64, 64),
            (128, 128),
            (256, 256),
        ],
    )
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Converte o PNG do projeto para ICO.")
    parser.add_argument(
        "--input",
        default=str(Path(__file__).resolve().parent / "vencedora.png"),
        help="Caminho do PNG de origem.",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent / "icone.ico"),
        help="Caminho do arquivo ICO de saída.",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    output_path = Path(args.output)
    build_icon(input_path, output_path)
    print(f"Ícone gerado em: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
