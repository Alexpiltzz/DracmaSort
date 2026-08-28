import random

import pytest

from code_gen.core import (
    MAX_CODE,
    MIN_CODE,
    CodeRegistry,
    NotEnoughCodesError,
    format_code,
    generate_codes,
    pool_size,
)


def test_format_code_zero_padded():
    assert format_code(1) == "0001"
    assert format_code(9999) == "9999"


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


def test_registry_roundtrip(tmp_path):
    registry = CodeRegistry(tmp_path / "codigos_emitidos.json")
    assert registry.load() == set()
    registry.save({1, 100, 9999})
    assert registry.load() == {1, 100, 9999}


def test_registry_missing_file_is_empty(tmp_path):
    assert CodeRegistry(tmp_path / "ausente.json").load() == set()
