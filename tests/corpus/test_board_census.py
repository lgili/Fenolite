# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Census of the readable corpus boards (hypotheses H-K-PCB-UUID, H-K-PCB-ZONE, H-K-UNIT, H-G-ANGLE,
H-K-SEXPR-NUM-CORPUS, H-K-TOK-CONSTANTS, H-K-PCB-READ; change c0009).

Counts only, keyed by origin, manifest id and context (head chains and codes, never content). Results go
to the JSON file named by ``FENOLITE_CENSUS_OUT`` and nowhere else.
"""

from __future__ import annotations

from functools import cache

import pytest
from _boardcorpus import (
    READABLE_ITEMS,
    Entry,
    census_fields,
    census_headers,
    census_kept_opaque,
    census_numbers,
    census_pintypes,
    census_uuids,
    census_validation,
    census_zones,
    entry,
)
from _boards import census
from _corpus import require

pytestmark = pytest.mark.needs_corpus


@cache
def entries() -> tuple[Entry, ...]:
    items = [i for i in READABLE_ITEMS if i.path.is_file() and not i.heavy]
    if not items:
        require(READABLE_ITEMS[0])  # skips, or fails in required-resource mode
    return tuple(entry(i) for i in items)


def test_inexact_numbers_by_context() -> None:
    data = census_numbers(entries())
    census("numbers", "native", data)
    print("numbers:", data)


def test_kept_opaque_reasons() -> None:
    data = census_kept_opaque(entries())
    census("kept_opaque", "native", data)
    print("kept-opaque reasons:", data)


def test_footprint_fields() -> None:
    data = census_fields(entries())
    census("fields", "native", data)
    print("footprint fields:", data)
    total = sum(counts.get("fields", 0) for counts in data["counts"].values())
    assert total > 0


def test_uuid_repeats() -> None:
    data = census_uuids(entries())
    census("uuids", "native", data)
    print("uuid repeats per board and head:", data or "none")


def test_zone_outlines() -> None:
    counts, problems = census_zones(entries())
    census("zones", "native", counts)
    assert not problems, "opaque outlines must give an empty model outline and opaque polygons: " + ", ".join(
        problems
    )


def test_validation_findings() -> None:
    data = census_validation(entries())
    census("validation", "native", data)
    print("Design.validate() findings:", data)


def test_board_headers() -> None:
    data = census_headers(entries())
    census("headers", "native", data)
    print("board headers:", {k: len(v) for k, v in data.items()})


def test_pintype_values() -> None:
    data = census_pintypes(entries())
    census("pins", "native", data)
    print("pintype values:", data)
