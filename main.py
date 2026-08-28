"""Ponto de entrada raiz do script.

Permite a execução direta simples:
    uv run python main.py
    python main.py
"""

import sys

from code_gen.main import main

if __name__ == "__main__":
    sys.exit(main())

