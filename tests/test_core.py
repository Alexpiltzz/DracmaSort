import random

import pytest

from code_gen.core import (
    MAX_CODE,
    MIN_CODE,
    CodeRegistry,
    NotEnoughCodesError,
    StudentRegistry,
    draw_item,
    format_code,
    generate_codes,
    pool_size,
    smart_title_case,
)


def test_format_code_zero_padded():
    assert format_code(1) == "0001"
    assert format_code(9999) == "9999"


def test_smart_title_case_maiscula_iniciais():
    assert smart_title_case("maria silva") == "Maria Silva"
    assert smart_title_case("ANA PAULA REIS") == "Ana Paula Reis"


def test_smart_title_case_mantem_particulas_minusculas():
    assert smart_title_case("MARIA DA SILVA SANTOS") == "Maria da Silva Santos"
    assert smart_title_case("JOÃO DOS PASSOS") == "João dos Passos"


def test_smart_title_case_capitaliza_particula_inicial():
    assert smart_title_case("DA SILVA") == "Da Silva"


def test_smart_title_case_hifenizado():
    assert smart_title_case("MARIA-JOSÉ APARECIDA") == "Maria-José Aparecida"


def test_smart_title_case_mantem_abreviacoes():
    assert smart_title_case("J. P. ROBERTO") == "J. P. Roberto"


def test_smart_title_case_vazio():
    assert smart_title_case("") == ""
    assert smart_title_case("   ") == "   "


def test_generate_codes_quantities_and_range():
    batches = generate_codes([2, 1, 3], set(), rng=random.Random(42))
    assert [len(batch) for batch in batches] == [2, 1, 3]
    flat = [code for batch in batches for code in batch]
    assert all(len(code) == 4 for code in flat)
    numbers = [int(code) for code in flat]
    assert all(MIN_CODE <= number <= MAX_CODE for number in numbers)


def test_generate_codes_skips_used():
    batches = generate_codes([500], {1, 2, 3}, rng=random.Random(7))
    flat = [code for batch in batches for code in batch]
    assert len(flat) == len(set(flat))
    assert not (set(int(code) for code in flat) & {1, 2, 3})


def test_generate_codes_unique_across_runs():
    first = generate_codes([3], set(), rng=random.Random(1))
    used = {int(code) for batch in first for code in batch}
    second = generate_codes([3], used, rng=random.Random(2))
    first_flat = {code for batch in first for code in batch}
    second_flat = {code for batch in second for code in batch}
    assert not (first_flat & second_flat)


def test_generate_codes_raises_when_exhausted():
    used = set(range(1, 9999))
    with pytest.raises(NotEnoughCodesError):
        generate_codes([5], used)


def test_pool_size():
    assert pool_size(set()) == 9999
    assert pool_size({1, 2}) == 9997


def test_pool_size_ignores_out_of_range_codes():
    assert pool_size({0, 1, 2, 10000, -5}) == 9997


def test_generate_codes_ignores_out_of_range_used():
    batches = generate_codes([2], {0, 10000, -1}, rng=random.Random(13))
    flat = [code for batch in batches for code in batch]
    numbers = {int(code) for code in flat}
    assert all(MIN_CODE <= number <= MAX_CODE for number in numbers)
    assert len(numbers) == len(flat)


def test_registry_roundtrip(tmp_path):
    registry = CodeRegistry(tmp_path / "codigos_emitidos.json")
    assert registry.load() == set()
    registry.save({1, 100, 9999})
    assert registry.load() == {1, 100, 9999}


def test_registry_missing_file_is_empty(tmp_path):
    assert CodeRegistry(tmp_path / "ausente.json").load() == set()


def test_student_registry_roundtrip(tmp_path):
    registry = StudentRegistry(tmp_path / "alunos_rastreados.json")
    assert registry.load() == set()
    registry.save({"ana melo", "carlos souza"})
    assert registry.load() == {"carlos souza", "ana melo"}


def test_student_registry_missing_file_is_empty(tmp_path):
    assert StudentRegistry(tmp_path / "ausente.json").load() == set()


def test_draw_item_sem_repeticao_remove_do_pool():
    pool = ["ana melo", "carlos souza", "bia lima"]
    winner = draw_item(pool, with_repetition=False, rng=random.Random(3))
    assert winner in ("ana melo", "carlos souza", "bia lima")
    assert winner not in pool
    assert len(pool) == 2


def test_draw_item_com_repeticao_mantem_pool():
    pool = ["ana melo", "carlos souza", "bia lima"]
    winner = draw_item(pool, with_repetition=True, rng=random.Random(3))
    assert winner in pool
    assert len(pool) == 3


def test_draw_item_lista_vazia_levanta_erro():
    with pytest.raises(ValueError):
        draw_item([], with_repetition=True)


def test_draw_item_sem_repeticao_esgota_todos():
    pool = ["ana melo", "carlos souza", "bia lima"]
    sorteados = [
        draw_item(pool, with_repetition=False, rng=random.Random(seed)) for seed in range(3)
    ]
    assert pool == []
    assert set(sorteados) == {"ana melo", "carlos souza", "bia lima"}
