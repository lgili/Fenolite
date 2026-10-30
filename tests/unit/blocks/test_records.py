# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The records of the shipped blocks (capability block-library, "Reserved block namespace", scenario
"Unregistered source of a shipped block"; change c0268): every source of a ``Fenolite:`` block is an
``S-`` id of ``docs/evidence/sources.md``."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from fenolite.cli.blocksrc import find_blocks
from fenolite.dsl.record import Header

ROOT = Path(__file__).resolve().parents[3]
SOURCES = ROOT / "docs" / "evidence" / "sources.md"


def registered() -> set[str]:
    return set(re.findall(r"^\| (S-\d{4,}) \|", SOURCES.read_text(encoding="utf-8"), re.MULTILINE))


def source_problems(headers: Iterable[Header], known: set[str]) -> list[str]:
    """``<block id>: source <S-id> is not in docs/evidence/sources.md`` for each unregistered source."""
    return [
        f"{header.id}: source {source} is not in docs/evidence/sources.md"
        for header in headers
        for source in header.sources
        if source not in known
    ]


def shipped_headers() -> list[Header]:
    return [e.definition.header for e in find_blocks() if e.source == "builtin" and e.definition.header]


def test_sources_of_shipped_blocks_are_registered() -> None:
    assert source_problems(shipped_headers(), registered()) == []


def test_sources_unregistered_source_is_named() -> None:
    """Scenario "Unregistered source of a shipped block": the check names the block and the id."""
    fake = Header("Fenolite:divider", "1.0.0", "d", sources=("S-0001", "S-9999"))
    assert source_problems([fake], registered()) == [
        "Fenolite:divider: source S-9999 is not in docs/evidence/sources.md"
    ]


def test_shipped_blocks_are_records_of_the_namespace() -> None:
    for entry in find_blocks():
        if entry.source == "builtin":
            assert entry.definition.header is not None and entry.id.startswith("Fenolite:"), entry.id
