# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Census of the readable corpus boards (hypotheses H-K-PCB-UUID, H-K-PCB-ZONE, H-K-UNIT, H-G-ANGLE,
H-K-SEXPR-NUM-CORPUS, H-K-TOK-CONSTANTS, H-K-PCB-READ; change c0009), and of their zone settings
(H-K-ZONE-FORM; change c0031), which also covers the third-party boards upgraded in memory by KiCad 10.

Counts only, keyed by origin, manifest id and context (head chains and codes, never content). Results go
to the JSON file named by ``FENOLITE_CENSUS_OUT`` and nowhere else.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import pytest
from _boardcorpus import (
    BOARD_ITEMS,
    READABLE_ITEMS,
    Entry,
    census_fields,
    census_headers,
    census_kept_opaque,
    census_numbers,
    census_pintypes,
    census_uuids,
    census_validation,
    census_via_protection,
    census_zone_settings,
    census_zones,
    entry,
)
from _boards import census
from _corpus import require
from _resources import kicad_cli

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import parse
from fenolite.core.errors import Issue

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


def test_board_items() -> None:
    """How many dimensions of the corpus boards are modelled and how many stay opaque root children, and
    the rule areas with a name and the justified texts (change c0103). Counts only."""
    data: dict[str, dict[str, int]] = {}
    for found in entries():
        board = found.design.board
        assert board is not None
        written = sum(1 for child in found.root.nodes() if child.name == "dimension")
        counts = {
            "dimensions_modelled": len(board.dimensions),
            "dimensions_opaque": written - len(board.dimensions),
            "named_rule_areas": sum(1 for k in board.keepouts if k.name),
            "justified_texts": sum(
                1 for text in board.texts if (text.h_justify, text.v_justify) != ("center", "center")
            ),
        }
        assert counts["dimensions_opaque"] >= 0
        if any(counts.values()):
            data[found.id] = counts
    census("board_items", "native", data)
    print("board items:", data or "none")
    assert not [i for found in entries() for i in found.issues if i.code == "kicad.board.duplicate-uuid"
                and "dimension" in i.where]  # fmt: skip


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


def test_zone_settings() -> None:
    """Every zone of the native demos has modelled ``connect_pads``, ``min_thickness`` and ``fill``
    slots (``H-K-ZONE-FORM``); counts go to the census file."""
    counts, problems = census_zone_settings(entries())
    census("zone_settings", "native", counts)
    print("zone settings:", counts)
    assert sum(c.get("zones", 0) for c in counts.values()) > 0
    assert not problems, "setting children kept opaque: " + "; ".join(problems)


def test_via_protection() -> None:
    """Every protection child of a via of the readable boards is a modelled slot, and the forms are those
    of ``docs/formats/kicad/board.md``, "Via protection" (change c0112; counts go to the census file)."""
    counts, problems = census_via_protection(entries())
    census("via_protection", "native", counts)
    print("via protection:", counts)
    assert sum(c.get("vias", 0) for c in counts.values()) > 0
    assert not problems, "protection children kept opaque: " + "; ".join(problems)


@pytest.mark.needs_kicad
@pytest.mark.kicad_min_major(10)
def test_zone_settings_upgraded() -> None:
    """The same census on the third-party boards re-saved by ``pcb upgrade --force`` (in memory only)."""
    items = [i for i in BOARD_ITEMS if i.origin == "third-party" and not i.heavy and i.path.is_file()]
    if not items:
        pytest.skip("no third-party board is cached")
    path = kicad_cli()
    assert path is not None  # the needs_kicad marker skips before this is reached
    runner = KicadCli(Path(path), timeout=600)
    copies = []
    for item in items:
        text = runner.upgrade_board(item.path).decode("utf-8")
        issues: list[Issue] = []
        design = read_board(text, issues=issues)
        copies.append(Entry(item.origin, item.id, parse(text), design, tuple(issues)))
    counts, problems = census_zone_settings(copies)
    census("zone_settings", "upgraded", counts)
    print("zone settings (upgraded):", counts)
    assert sum(c.get("zones", 0) for c in counts.values()) > 0
    assert not problems, "setting children kept opaque: " + "; ".join(problems)
