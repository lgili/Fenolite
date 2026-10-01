# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

import random
import uuid

import pytest

from fenolite.core.ids import FENOLITE_NS, content_hash, content_id, derived_id, is_id, new_id, parse_id


def test_new_id_is_reproducible_with_a_seed() -> None:
    a = [new_id("cmp", random.Random(7)) for _ in range(2)]
    assert a[0] == a[1]
    prefix, value = parse_id(a[0])
    assert prefix == "cmp" and value.version == 4


def test_new_ids_differ_within_one_generator() -> None:
    rng = random.Random(7)
    assert new_id("trk", rng) != new_id("trk", rng)


def test_derived_id_is_stable_and_namespaced() -> None:
    first = derived_id("fp", "kicad", "a81c0000-0000-4000-8000-000000000001")
    assert first == derived_id("fp", "kicad", "a81c0000-0000-4000-8000-000000000001")
    assert first != derived_id("fp", "other", "a81c0000-0000-4000-8000-000000000001")
    assert parse_id(first)[1] == uuid.uuid5(FENOLITE_NS, "kicad:a81c0000-0000-4000-8000-000000000001")


def test_content_id_depends_on_content_not_on_files() -> None:
    track = content_hash("track", [0, 0], [1_000_000, 0], 250_000, "F.Cu", "GND")
    moved = content_hash("track", [0, 0], [2_000_000, 0], 250_000, "F.Cu", "GND")
    a = content_id("trk", "kicad", "doc-uuid", "tracks", track)
    assert a == content_id("trk", "kicad", "doc-uuid", "tracks", track)
    assert a != content_id("trk", "kicad", "doc-uuid", "tracks", moved)


@pytest.mark.parametrize("prefix", ["foo", "", "CMP"])
def test_unknown_prefix(prefix: str) -> None:
    with pytest.raises(ValueError):
        new_id(prefix, random.Random(1))
    with pytest.raises(ValueError):
        derived_id(prefix, "kicad", "x")


def test_is_id() -> None:
    value = new_id("net", random.Random(3))
    assert is_id(value) and is_id(value, "net") and not is_id(value, "cmp")
    assert not is_id("net_not-a-uuid") and not is_id("R1")


@pytest.mark.parametrize("prefix", ["fpd", "sym"])
def test_library_definition_prefixes(prefix: str) -> None:
    value = derived_id(prefix, "kicad", "Mini:R")
    assert is_id(value, prefix) and value == derived_id(prefix, "kicad", "Mini:R")


def test_unknown_library_prefix_still_rejected() -> None:
    with pytest.raises(ValueError):
        new_id("fpx", random.Random(1))
