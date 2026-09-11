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


class StudentRegistry:
    """Registro persistente de alunos já rastreados entre execuções."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> set[str]:
        if not self.path.exists():
            return set()
        with self.path.open("r", encoding="utf-8") as fh:
            return {str(name) for name in json.load(fh)}

    def save(self, students: set[str]) -> None:
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(sorted(students), fh, indent=2)


def format_code(number: int) -> str:
    """Formata um número como código de 4 dígitos, ex.: 1 -> '0001'."""
    return f"{number:04d}"


def smart_title_case(name: str) -> str:
    """Converte um nome para iniciais maiúsculas respeitando partículas do português.

    Palavras como "de", "da", "do", "dos", "das" e "e" caem para minúsculas quando
    não abrem o nome; abreviações como "J." são mantidas como estão. Hifenizados
    (ex.: "Maria-José") capitalizam cada parte.
    """
    if not name or not name.strip():
        return name
    words = _split_title_words(name)
    parts: list[str] = []
    for index, word in enumerate(words):
        lower = word.lower()
        if index > 0 and _is_title_particle(lower):
            parts.append(lower)
            continue
        if _is_abbreviation(word):
            parts.append(word)
            continue
        if "-" in word:
            parts.append(
                "-".join(
                    part[:1].upper() + part[1:].lower() if part else "" for part in word.split("-")
                )
            )
            continue
        parts.append(word[:1].upper() + word[1:].lower())
    return " ".join(parts)


def _is_title_particle(word: str) -> bool:
    return word in {"de", "da", "do", "das", "dos", "e", "em", "no", "na"}


def _is_abbreviation(word: str) -> bool:
    if word.endswith("."):
        core = word[:-1]
        return len(core) >= 1 and all(char.isalpha() for char in core)
    return False


def _split_title_words(name: str) -> list[str]:
    return name.replace(",", " ").split()


def pool_size(used_codes: set[int]) -> int:
    in_use = len(set(used_codes).intersection(CODE_DOMAIN))
    return (MAX_CODE - MIN_CODE + 1) - in_use


def draw_item(
    pool: list[str],
    with_repetition: bool,
    rng: random.Random | None = None,
) -> str:
    """Sorteia um item do pool.

    Com ``with_repetition=True`` o item permanece no pool; caso contrário é
    removido. O pool é mutado in-place e pode ser reutilizado entre sorteios.
    """
    if not pool:
        raise ValueError("Não há itens disponíveis para o sorteio.")
    if rng is None:
        rng = random.Random()
    index = rng.randrange(len(pool))
    winner = pool[index]
    if not with_repetition:
        del pool[index]
    return winner


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
