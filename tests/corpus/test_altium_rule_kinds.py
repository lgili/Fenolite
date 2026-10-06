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
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.rules import HEADER_KEYS, RULE_KIND_MAP, map_rules
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
