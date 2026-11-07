# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule kinds and their reading (capability altium-project-reader, "Rule kinds and their reading", scenario
"Every corpus kind is listed"; change c0462, design D6). The documents are those of the manifest rows of use
``altium-pcbdoc``, read from the corpus cache with Fenolite's own readers; counts only."""

from __future__ import annotations

import dataclasses
from collections import Counter
from collections.abc import Sequence
from fractions import Fraction
from pathlib import Path

import pytest
from _corpus import CorpusItem, manifest_items, require

from fenolite.backends.altium.adapter.layers import copper_layers_of
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_rule_fields
from fenolite.backends.altium.read.rules import (
    CARRIED_KINDS,
    CHECKED_KINDS,
    READ_KINDS,
    RULE_KIND_MAP,
    Field,
    map_rules,
)
from fenolite.checks.clearance import rule_precedence
from fenolite.model.rules import Rule, RuleSubject

pytestmark = pytest.mark.needs_corpus

ROWS = (
    *manifest_items("altium-pcbdoc"),
    *(row for row in manifest_items("rta") if row.id == "altium-third-party-pcbdoc-08"),
)
"""The 8 public rows of the pour census (S-2210)."""
PAGE = Path(__file__).resolve().parents[2] / "docs" / "formats" / "altium" / "rule-file.md"
HEADER = "| RULEKIND | reading | rules, part or reason |"
READINGS = {"neutral": set(RULE_KIND_MAP), "read": set(READ_KINDS), "checked": set(CHECKED_KINDS)}
READINGS["carried"] = set(CARRIED_KINDS)
REFUSED = {
    "MatchedLengths": ("delay-units", 15),
    "RoutingVias": ("template", 4),
    "Clearance": ("matrix-kind", 2),
    "BoardOutlineClearance": ("matrix-kind", 1),
}
"""Kind → the reason of change c0462 that refuses its records on the public rows, and their count."""


def page_rows() -> dict[str, str]:
    """The rows of the table "Rule kinds and their reading": kind → reading."""
    lines = PAGE.read_text(encoding="utf-8").splitlines()
    start = lines.index(HEADER) + 2
    rows: dict[str, str] = {}
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip("|").split(" | ")]
        assert cells[0].strip("`") not in rows, cells[0]
        rows[cells[0].strip("`")] = cells[1]
    return rows


def test_the_table_is_the_code() -> None:
    """The page lists exactly the kinds of the four tables, each with its reading."""
    rows = page_rows()
    assert {kind: reading for kind, reading in rows.items()} == {
        kind: reading for reading, kinds in READINGS.items() for kind in kinds
    }
    assert list(rows) == sorted(rows)


def _records(item: CorpusItem) -> list[tuple[str, str, str]]:
    path = require(item)
    design = AltiumBackend().read(path).design
    layers = copper_layers_of(design.board.layers) if design.board is not None else None
    fields = read_rule_fields(path.read_bytes(), file=path.name)
    mapping = map_rules(fields, origin=path.name, layers=layers)
    reasons = {unmapped.index: unmapped.reason for unmapped in mapping.unmapped}
    return [
        (dict(f).get("RULEKIND", ""), reasons.get(index, "mapped"), item.id) for index, f in enumerate(fields)
    ]


@pytest.mark.parametrize("item", ROWS, ids=lambda item: item.id)
def test_every_corpus_kind_is_listed(item: CorpusItem) -> None:
    """Each kind of the row is in the table, and no record of a neutral or read kind is reported with
    ``no-counterpart``; a read kind is reported ``read-elsewhere``, a checked kind ``checked``."""
    found = _records(item)
    assert found, "no rule record read"
    listed = page_rows()
    assert sorted({kind for kind, _reason, _row in found} - set(listed)) == []
    wrong = [
        kind
        for kind, reason, _row in found
        if listed[kind] in ("neutral", "read") and reason == "no-counterpart"
    ]
    assert wrong == []
    assert all(reason == "read-elsewhere" for kind, reason, _row in found if listed[kind] == "read")
    assert all(reason == "checked" for kind, reason, _row in found if listed[kind] == "checked")


def test_refusals_of_c0462_keep_their_counts() -> None:
    """Over the 8 rows, the records that change c0462 refuses by a named reason keep their counts."""
    by_kind = Counter((kind, reason) for item in ROWS for kind, reason, _row in _records(item))
    for kind, (reason, count) in REFUSED.items():
        assert by_kind[(kind, reason)] == count, (kind, reason)


# --- task 4.3: the object matrices of the public rows ---------------------------------------------------

OBJECT_KINDS = {
    "Arc": RuleSubject("track"),
    "Track": RuleSubject("track"),
    "SMDPad": RuleSubject("pad", ref="U1", pad_type="smd"),
    "THPad": RuleSubject("pad", ref="J1", hole=1_000_000, pad_type="th"),
    "NPTH": RuleSubject("pad", ref="H1", hole=3_000_000, pad_type="npth"),
    "Via": RuleSubject("via", hole=300_000),
    "Poly": RuleSubject("zone", zone="GND"),
    "Fill": RuleSubject("graphic"),
    "Region": RuleSubject("graphic"),
    "Text": RuleSubject("text"),
}
"""A subject of each object kind whose cells a neutral rule takes, as the copper check makes it; an
unplated pad is a through-hole pad of the matrix (``H-A-RULE-MATRIX-NPTH``)."""
MATRIX_REFUSED = {
    ("altium-third-party-pcbdoc-06", "Clearance"): 1,
    ("altium-third-party-pcbdoc-06", "BoardOutlineClearance"): 1,
    ("altium-third-party-pcbdoc-08", "Clearance"): 1,
}
"""Row and kind → its matrices refused ``matrix-kind`` (an arc and a track, a fill and a region, or the
outline and a cutout that differ); every other matrix of the rows is proved cell by cell."""


def _entries(text: str) -> dict[tuple[str, str], int]:
    """Each entry in nanometres by its two kinds, both ways round; read here apart from the mapper."""
    found: dict[tuple[str, str], int] = {}
    for entry in filter(None, (part.strip() for part in text.split(";"))):
        pair, count = entry.rsplit(":", 1)
        first, second = (name.removeprefix("ClearanceObj_") for name in pair.split("-"))
        found[(first, second)] = found[(second, first)] = round(Fraction(int(count) * 254, 100))
    return found


def _governing(rules: Sequence[Rule], kind: str, a: RuleSubject, b: RuleSubject | None) -> Rule | None:
    def selects(rule: Rule) -> bool:
        if b is None:
            return rule.selector_a.matches(a)
        if rule.selector_b is None:
            return rule.selector_a.matches(a) or rule.selector_a.matches(b)
        return (rule.selector_a.matches(a) and rule.selector_b.matches(b)) or (
            rule.selector_a.matches(b) and rule.selector_b.matches(a)
        )

    found = [rule for rule in rule_precedence(rules) if rule.kind == kind and selects(rule)]
    return found[-1] if found else None


def _alone(fields: Sequence[Field]) -> list[Field]:
    """The record with its matrix, gap and kind alone: scopes ``All``, enabled, no other key that could
    refuse it (the flag of the pads of one footprint, a cell's layer keys)."""
    keep = {"RULEKIND", "NETSCOPE", "LAYERKIND", "NAME", "PRIORITY", "GAP", "OBJECTCLEARANCES"}
    values = {key: value for key, value in fields if key in keep}
    values |= {"SCOPE1EXPRESSION": "All", "SCOPE2EXPRESSION": "All", "ENABLED": "TRUE"}
    return list(values.items())


@pytest.mark.parametrize("item", ROWS, ids=lambda item: item.id)
def test_every_matrix_holds_its_cells(item: CorpusItem) -> None:
    """Design D5 on the public rows: the rules of each object matrix, read alone, give every pair of object
    kinds (every object against the outline and a cutout) exactly its entry, or the record's gap."""
    path = require(item)
    refused: Counter[str] = Counter()
    for fields in read_rule_fields(path.read_bytes(), file=path.name):
        values = dict(fields)
        text = (values.get("OBJECTCLEARANCES") or "").strip()
        if not text:
            continue
        kind = values["RULEKIND"] or ""
        mapping = map_rules([_alone(fields)], origin="matrix")
        if mapping.unmapped:
            ((reason, detail),) = [(u.reason, u.detail) for u in mapping.unmapped]
            assert reason == "matrix-kind", (item.id, kind, detail)
            refused[kind] += 1
            continue
        rules = mapping.ruleset.rules
        gap = rules[0].min
        assert gap is not None
        cells = _entries(text)
        for first, one in OBJECT_KINDS.items():
            name = first.replace("NPTH", "THPad")
            if kind == "BoardOutlineClearance":
                rule = _governing(rules, "edge_clearance", dataclasses.replace(one, net="A"), None)
                for edge in ("OutlineEdge", "CutoutEdge"):
                    assert rule is not None and rule.min == cells.get((name, edge), gap), (item.id, first)
                continue
            for second, other in OBJECT_KINDS.items():
                pair = (name, second.replace("NPTH", "THPad"))
                rule = _governing(
                    rules, "clearance", dataclasses.replace(one, net="A"), dataclasses.replace(other, net="B")
                )
                assert rule is not None and rule.min == cells.get(pair, gap), (item.id, pair)
    expected = {kind: n for (row, kind), n in MATRIX_REFUSED.items() if row == item.id}
    assert dict(refused) == expected, item.id


# --- task 5.2: the records the pour cannot read are those the design names -----------------------------

POUR_UNREAD: dict[str, Counter[str]] = {}
"""Row → the unread Clearance records that can govern a polygon of the pour, by reason (the pour's own
reading, ``pour.Clearances``). ``keys`` is ``IGNOREPADTOPADCLEARANCEINFOOTPRINT=TRUE`` alone; ``matrix-kind``
the matrices of ``MATRIX_REFUSED``. These alone may refuse a polygon ``rule-unmapped`` in the pour census
(scenario "No refusal of scope or keys in the pour census", as amended on 2026-11-06). Change c0463 (task 4.3)
reads them for the pour (``pour.pour_rule_fields``), so the pour leaves none unread: before, ``-02`` held one
``keys`` record, ``-06`` one ``keys`` and one ``matrix-kind``, ``-08`` one ``matrix-kind``."""


@pytest.mark.parametrize("item", ROWS, ids=lambda item: item.id)
def test_the_pour_refuses_only_records_the_design_names(item: CorpusItem) -> None:
    from fenolite.backends.altium.pour import pour_rule_fields, read_pour
    from fenolite.backends.altium.read.rules import NOT_APPLYING
    from fenolite.backends.altium.read.scopedoc import scope_document

    path = require(item)
    reading = read_pour(path.read_bytes(), file=path.name)
    board = reading.design.board
    layers = copper_layers_of(board.layers) if board is not None else None
    mapping = map_rules(
        pour_rule_fields(reading.document.rules)[0],
        origin="pour",
        layers=layers,
        document=scope_document(reading.document, layers),
    )
    unread = [u for u in mapping.unmapped if u.kind == "Clearance" and u.reason not in NOT_APPLYING]
    assert Counter(u.reason for u in unread) == POUR_UNREAD.get(item.id, Counter())
    keys = [u.detail for u in unread if u.reason == "keys"]
    assert all(detail.startswith("IGNOREPADTOPADCLEARANCEINFOOTPRINT=TRUE ") for detail in keys), keys
