# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rule kinds of change c0084 on the public PCB documents (capability altium-project-reader, "More
rule kinds onto the neutral model", scenario "Board outline clearance"; ``docs/formats/altium/pcb-copper.md``,
"Rule kinds lowered"). The documents are those of the manifest rows of use ``altium-pcbdoc``, read from the
corpus cache with Fenolite's own readers. A count here shows which keys Altium writes; it raises no row
above ``INFERRED``."""

from __future__ import annotations

from collections import Counter

import pytest
from _corpus import CorpusItem, manifest_items, require

from fenolite.backends.altium import rulemap
from fenolite.backends.altium.adapter.layers import LayerMap
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.rules import (
    HEADER_KEYS,
    MATRIX_UNIT,
    NOT_APPLYING,
    RULE_KIND_MAP,
    map_rules,
    matrix_problem,
)
from fenolite.backends.altium.read.scope import parse_layer_scope
from fenolite.model.rules import Selector

pytestmark = pytest.mark.needs_corpus

ROWS = manifest_items("altium-pcbdoc")
NEW_KINDS = {"BoardOutlineClearance": 63, "HoleToHoleClearance": 52, "MinimumAnnularRing": 19, "HoleSize": 42}
MAPPED = {
    "altium-third-party-pcbdoc-04": {"edge_clearance": 1, "annular_width": 1},
    "altium-third-party-pcbdoc-05": {"edge_clearance": 1, "annular_width": 1, "hole_to_hole": 1},
    "altium-third-party-pcbdoc-06": {"edge_clearance": 1},
    "altium-third-party-pcbdoc-07": {"edge_clearance": 1, "annular_width": 1},
}
"""Row → the rules of the three kinds of c0084 that its records give (census of 2026-10-06)."""
C0084 = ("edge_clearance", "hole_to_hole", "annular_width")


@pytest.mark.parametrize("item", ROWS, ids=lambda item: item.id)
def test_keys_and_numbers_of_the_lowered_kinds(item: CorpusItem) -> None:
    """Every record of a kind of the table has the kind number of the table and no key outside the keys the
    writer writes for it, in the written order; Clearance, Width and Routing Via Style can hold more keys
    (a matrix, per-layer widths, via templates), which the reader refuses."""
    document = read_pcbdoc(require(item).read_bytes(), file=item.path.name)
    rows = {row.altium: row for row in rulemap.TABLE if row.exact}
    for record in document.rules:
        kind = record.rule_kind or ""
        if kind not in NEW_KINDS:
            continue
        assert record.kind_number == NEW_KINDS[kind] == rows[kind].number, (item.id, kind)
        keys = [key for key, _value in record.fields]
        own = [key for key in keys[keys.index("RULEKIND") :] if key not in HEADER_KEYS]
        assert own == list(rows[kind].fields), (item.id, kind, own)
    mapping = map_rules([r.fields for r in document.rules], origin=item.id)
    assert "no-verified-keys" not in {unmapped.reason for unmapped in mapping.unmapped}
    found = Counter(rule.kind for rule in mapping.ruleset.rules if rule.kind in C0084)
    assert dict(found) == MAPPED.get(item.id, {}), item.id
    for kind in rulemap.KIND_ORDER:
        priorities = sorted(r.priority or 0 for r in document.rules if r.rule_kind == kind)
        assert priorities == list(range(1, len(priorities) + 1)), (item.id, kind)


def test_board_outline_clearance_is_imported() -> None:
    """Scenario "Board outline clearance": a document whose rules hold a board outline clearance for all
    objects gives that edge clearance, and the import lists no pending kind."""
    (item,) = [row for row in ROWS if row.id == "altium-third-party-pcbdoc-05"]
    path = require(item)
    record = next(
        r
        for r in read_pcbdoc(path.read_bytes(), file=path.name).rules
        if r.rule_kind == "BoardOutlineClearance"
    )
    assert (record.scope1, record.scope2) == ("All", "All")
    result = AltiumBackend().read(path)
    rules = result.design.rules
    assert rules is not None
    (edge,) = [rule for rule in rules.rules if rule.kind == "edge_clearance"]
    gap = dict(record.fields)["GAP"]
    assert gap.endswith("mil") and edge.min == round(float(gap[:-3]) * 25_400)
    assert edge.selector_a == Selector("all") and edge.selector_b is None and edge.priority == record.priority
    unmapped = [i.message for i in result.issues if i.code == "altium.import.rule-unmapped"]
    assert not [message for message in unmapped if "no-verified-keys" in message]
    assert not [message for message in unmapped if "BoardOutlineClearance" in message]
    assert {rule.kind for rule in rules.rules} >= {"edge_clearance", "hole_to_hole", "annular_width"}
    assert set(RULE_KIND_MAP) >= set(rulemap.KIND_ORDER)


# --- More forms of a Clearance record (change c0125) ---------------------------------------------------

DOCUMENTS = [*ROWS, *(row for row in manifest_items("rta") if row.id == "altium-third-party-pcbdoc-08")]
"""The seven rows and the heavy PCB document, which ``FENOLITE_HEAVY=1`` includes."""
CLEARANCE = {
    "altium-third-party-pcbdoc-01": (1, 0, {}),
    "altium-third-party-pcbdoc-02": (0, 0, {"keys": 1}),
    "altium-third-party-pcbdoc-03": (2, 1, {}),
    "altium-third-party-pcbdoc-04": (1, 0, {"scope": 1}),
    "altium-third-party-pcbdoc-05": (1, 0, {}),
    "altium-third-party-pcbdoc-06": (0, 0, {"keys": 2}),
    "altium-third-party-pcbdoc-07": (2, 0, {"scope": 1}),
    "altium-third-party-pcbdoc-08": (0, 0, {"keys": 2, "scope": 2}),
}
"""Row → its Clearance records that map, that apply to nothing, and that stay unread by reason (census of
2026-10-06; before change c0125 the third row had none mapped and three unread)."""
CELL = {"CELLROWNAME": "All", "CELLROWTYPE": "0", "CELLCOLNAME": "All", "CELLCOLTYPE": "0"}


@pytest.mark.parametrize("item", DOCUMENTS, ids=lambda item: item.id)
def test_clearance_forms(item: CorpusItem) -> None:
    """The Clearance records of each public PCB document, mapped with the copper layers of its board as
    the import maps them, and the facts of ``rule-file.md`` that come from these records: the cell keys of
    a clearance matrix, the two layer conditions, and the entries of an object matrix."""
    document = read_pcbdoc(require(item).read_bytes(), file=item.path.name)
    records = [record.fields for record in document.rules]
    mapping = map_rules(records, origin=item.id, layers=LayerMap.from_board(document.board).copper_layers())
    indexes = [i for i, record in enumerate(document.rules) if record.rule_kind == "Clearance"]
    unmapped = {u.index: u.reason for u in mapping.unmapped if u.index in indexes}
    unread = Counter(reason for reason in unmapped.values() if reason not in NOT_APPLYING)
    idle = sum(1 for reason in unmapped.values() if reason in NOT_APPLYING)
    assert (len(indexes) - len(unmapped), idle, dict(unread)) == CLEARANCE[item.id], item.id
    for index in indexes:
        fields = dict(records[index])
        assert fields["ENABLED"] == "TRUE" and fields["NETSCOPE"] == "DifferentNets", (item.id, index)
        scopes = (fields["SCOPE1EXPRESSION"] or "", fields["SCOPE2EXPRESSION"] or "")
        if "SOURCERULE" in fields:  # a cell of the clearance matrix: its source is the matrix's own record
            source = dict(records[int(fields["SOURCERULE"] or "")])
            assert source.get("ISMATRIX") == "TRUE" and source["RULEKIND"] == "Clearance", (item.id, index)
            assert {key: fields.get(key) for key in CELL} == CELL, (item.id, index)
            assert int(fields["PRIORITY"] or "") < int(source["PRIORITY"] or ""), (item.id, index)
            first, second = (parse_layer_scope(scope) for scope in scopes)
            assert first is not None and first == second, (item.id, index)
            assert (fields.get("INNERLAYERS") == "TRUE") == first.inner, (item.id, index)
            assert (fields.get("OUTERLAYERS") == "TRUE") == (len(first.names) == 2), (item.id, index)
        else:
            assert "INNERLAYERS" not in fields and "OUTERLAYERS" not in fields, (item.id, index)
            assert parse_layer_scope(scopes[0]) is None and parse_layer_scope(scopes[1]) is None
        matrix = fields.get("OBJECTCLEARANCES") or ""
        if matrix.strip():
            # every entry has the form of the page and none holds the generic value: the text lists the
            # cells that differ
            problem = matrix_problem(matrix, fields["GAP"])
            entries = matrix.split(";")
            assert f"{len(entries)} of its {len(entries)} entries differ" in problem, (
                item.id,
                index,
                problem,
            )
            # the counts are lengths on a grid of 0.5 mil or of 0.05 mm when a count is 0.0001 mil
            for entry in entries:
                count = int(entry.rsplit(":", 1)[1])
                nanometres = count * MATRIX_UNIT[0] / MATRIX_UNIT[1]
                assert count % 5000 == 0 or abs(nanometres / 50_000 - round(nanometres / 50_000)) < 1e-4
