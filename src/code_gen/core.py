"""Lógica de geração e persistência dos códigos de sorteio."""

import json
import random
from pathlib import Path

MIN_CODE = 1
MAX_CODE = 9999

CODE_DOMAIN = range(MIN_CODE, MAX_CODE + 1)


class NotEnoughCodesError(Exception):
    """Quantidade solicitada excede o total de códigos disponíveis."""


class CodeRegistry:
    """Registro persistente dos códigos já sorteados entre execuções."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> set[int]:
        if not self.path.exists():
            return set()
        with self.path.open("r", encoding="utf-8") as fh:
            return {int(code) for code in json.load(fh)}

    def save(self, codes: set[int]) -> None:
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(sorted(codes), fh, indent=2)


def format_code(number: int) -> str:
    """Formata um número como código de 4 dígitos, ex.: 1 -> '0001'."""
    return f"{number:04d}"


def pool_size(used_codes: set[int]) -> int:
    in_use = len(set(used_codes).intersection(CODE_DOMAIN))
    return (MAX_CODE - MIN_CODE + 1) - in_use


def generate_codes(
    quantities: list[int],
    used_codes: set[int],
    rng: random.Random | None = None,
) -> list[list[str]]:
    """Sorta códigos únicos para cada quantidade, evitando os já usados."""
    requested = sum(quantities)
    if requested > pool_size(used_codes):
        raise NotEnoughCodesError(
            f"Pedido de {requested} códigos, mas restam apenas {pool_size(used_codes)} disponíveis."
        )
    if rng is None:
        rng = random.Random()
    available = [n for n in CODE_DOMAIN if n not in used_codes]
    chosen = rng.sample(available, requested)
    batches = []
    position = 0
    for qty in quantities:
        batches.append([format_code(n) for n in chosen[position : position + qty]])
        position += qty
    return batches
