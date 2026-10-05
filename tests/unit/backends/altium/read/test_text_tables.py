# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The code tables of the text readers equal the tables of their fact pages (capability
altium-project-reader, "Text file facts are documented", scenario "Code tables follow the pages")."""

from __future__ import annotations

import re
from pathlib import Path

from fenolite.backends.altium.read.project import DOCUMENT_KINDS, HIERARCHY_MODES
from fenolite.backends.altium.read.rules import (
    HEADER_KEYS,
    PENDING_KINDS,
    RULE_KIND_MAP,
    UNMAPPED_REASONS,
)
from fenolite.backends.altium.read.scope import ITEM_KINDS, LEAF_FUNCTIONS

PAGES = Path(__file__).resolve().parents[5] / "docs" / "formats" / "altium"
DASH = "—"


def _cells(line: str) -> list[str]:
    inner = line.strip().removeprefix("|").removesuffix("|")
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", inner)]


def table(page: str, header: list[str]) -> list[list[str]]:
    """The rows of the table of ``page`` whose header is ``header``, with backticks removed."""
    rows: list[list[str]] = []
    inside = False
    found = False
    for line in (PAGES / page).read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            inside = False
            continue
        cells = _cells(line)
        if cells == header:
            inside = found = True
            continue
        if inside and not set(line.replace("|", "").strip()) <= {"-", " "}:
            rows.append([cell.replace("`", "") for cell in cells])
    assert found, f"{page}: no table {header}"
    return rows


def test_document_kinds() -> None:
    rows = table("project.md", ["extension", "kind"])
    assert dict((suffix, kind) for suffix, kind in rows) == DOCUMENT_KINDS
    assert len(rows) == len(DOCUMENT_KINDS)


def test_hierarchy_modes() -> None:
    rows = table("project.md", ["HierarchyMode", "net scope"])
    assert {int(mode): scope for mode, scope in rows} == HIERARCHY_MODES


def test_rule_kind_map() -> None:
    rows = table(
        "rule-file.md",
        ["RULEKIND", "neutral kind", "min", "opt", "max", "net scope", "further conditions"],
    )
    expected = [
        [kind, limits.kind, limits.min or DASH, limits.opt or DASH, limits.max or DASH, entry.net_scope]
        for kind, entry in RULE_KIND_MAP.items()
        for limits in entry.rules
    ]
    assert [row[:6] for row in rows] == expected
    for row in rows:
        entry = RULE_KIND_MAP[row[0]]
        keys = [condition.key for condition in entry.conditions]
        assert all(key in row[6] for key in keys), row
        assert (row[6] == DASH) == (not keys), row


def test_pending_kinds() -> None:
    rows = table("rule-file.md", ["pending RULEKIND", "neutral kind", "reason"])
    assert {kind: neutral for kind, neutral, _reason in rows} == PENDING_KINDS
    assert {reason for _kind, _neutral, reason in rows} == {"no-verified-keys"}
    assert not set(PENDING_KINDS) & set(RULE_KIND_MAP)


def test_reasons_in_order() -> None:
    rows = table("rule-file.md", ["reason", "when"])
    assert tuple(reason for reason, _when in rows) == UNMAPPED_REASONS


def test_header_keys_in_order() -> None:
    text = (PAGES / "rule-file.md").read_text(encoding="utf-8")
    section = text.split("## Header keys", 1)[1].split("\n## ", 1)[0]
    assert re.findall(r"`([A-Z0-9]+)`", section)[: len(HEADER_KEYS)] == list(HEADER_KEYS)


def test_scope_grammar() -> None:
    rows = table("rule-file.md", ["expression", "selector"])
    selectors = {expression: selector for expression, selector in rows}
    for name, op in LEAF_FUNCTIONS.items():
        assert selectors[f"{name}('v')"] == f"{op} v"
    for name, kind in ITEM_KINDS.items():
        assert selectors[name] == f"item_kind {kind}"
    assert selectors["All"] == "all"


def test_rule_kinds_seen() -> None:
    """Every kind of ``RULE_KIND_MAP`` is among the kinds the corpus holds, marked as mapping; every other
    kind seen is marked ``no`` (task 8.4)."""
    rows = table("rule-file.md", ["RULEKIND seen", "records", "source", "maps"])
    marks = {kind: maps for kind, _records, _source, maps in rows}
    assert len(marks) == len(rows)
    assert {kind for kind, maps in marks.items() if maps.startswith("yes")} == set(RULE_KIND_MAP)
    assert all(maps == "no" for kind, maps in marks.items() if kind not in RULE_KIND_MAP)
    for kind, entry in RULE_KIND_MAP.items():
        assert all(limits.kind in marks[kind] for limits in entry.rules), kind
