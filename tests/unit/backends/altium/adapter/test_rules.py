# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rules of a PCB document through the mapper of c0042 (capability altium-import, "Rules where they map";
change c0043)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import _altium_records as rec

from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.adapter.rules import import_rules
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.rules import map_rules
from fenolite.core.errors import Issue
from fenolite.model.rules import RuleSet

ROUTED = Path(__file__).resolve().parents[5] / "tests" / "data" / "altium" / "routed" / "routed.PcbDoc"


def rules_of(*records: object, issues: list[Issue] | None = None) -> RuleSet:
    design = import_board(rec.document(rules=records), file="a.PcbDoc", sha256=rec.SHA, issues=issues)  # type: ignore[arg-type]
    assert design.rules is not None
    return design.rules


def test_rules_of_the_routed_sample() -> None:
    data = ROUTED.read_bytes()
    issues: list[Issue] = []
    document = read_pcbdoc(data)
    design = import_board(
        document, file="routed.PcbDoc", sha256=hashlib.sha256(data).hexdigest(), issues=issues
    )
    assert design.rules is not None
    rules = design.rules.rules
    kinds = [rule.kind for rule in rules]
    assert {"clearance", "track_width", "via_diameter", "via_drill"} <= set(kinds)
    power = [r for r in rules if r.kind == "clearance" and r.selector_a.op == "netclass"]
    assert len(power) == 1 and power[0].selector_a.value == "PWR" and power[0].priority == 1
    width = next(r for r in rules if r.kind == "track_width")
    assert None not in (width.min, width.opt, width.max)
    assert [i for i in issues if i.code == "altium.import.rule-unmapped"] == []
    assert [i for i in issues if i.code.startswith("altium.rule.")] == []
    mapped = map_rules([r.fields for r in document.rules], origin="routed.PcbDoc")
    assert len(rules) == len(mapped.ruleset.rules)
    for mine, theirs in zip(rules, mapped.ruleset.rules, strict=True):
        assert (mine.name, mine.kind, mine.min, mine.opt, mine.max) == (
            theirs.name, theirs.kind, theirs.min, theirs.opt, theirs.max,
        )  # fmt: skip
        assert (mine.selector_a, mine.selector_b, mine.priority, mine.severity, mine.layers) == (
            theirs.selector_a, theirs.selector_b, theirs.priority, theirs.severity, theirs.layers,
        )  # fmt: skip
        assert mine.id != theirs.id and mine.provenance is not None
        assert mine.provenance.locator.startswith("Rules6/Data#")
        assert [key for key, _ in mine.ext["altium"].payload] == ["scope1", "scope2", "rule_kind"]
    assert len({rule.id for rule in rules}) == len(rules)
    assert design.rules.native_ids == {"altium": "altium_pcbdoc"}


def test_rule_header_is_replaced() -> None:
    record = rec.rule("Clearance", "Clearance", GAP="10mil", SCOPE1EXPRESSION="InNetClass('PWR')")
    (rule,) = rules_of(record).rules
    assert rule.native_ids == {"altium": "rule:Clearance:Clearance:clearance"}
    assert dict(rule.ext["altium"].payload) == {
        "rule_kind": "Clearance", "scope1": "InNetClass('PWR')", "scope2": "All",
    }  # fmt: skip
    assert (rule.kind, rule.min, rule.priority, rule.selector_a.value) == ("clearance", 254_000, 1, "PWR")
    via = rec.rule(
        "RoutingVias", "Vias", VIASTYLE="Through Hole", MINWIDTH="40mil", WIDTH="50mil", MAXWIDTH="60mil",
        MINHOLEWIDTH="20mil", HOLEWIDTH="28mil", MAXHOLEWIDTH="30mil",
    )  # fmt: skip
    first, second = rules_of(via).rules
    assert [first.native_ids["altium"], second.native_ids["altium"]] == [
        "rule:RoutingVias:Vias:via_diameter",
        "rule:RoutingVias:Vias:via_drill",
    ]


def test_disabled_rule_is_counted_not_mapped() -> None:
    issues: list[Issue] = []
    record = rec.rule(
        "Width", "Width", ENABLED="FALSE", MINLIMIT="6mil", PREFEREDWIDTH="10mil", MAXLIMIT="20mil"
    )
    assert rules_of(record, issues=issues).rules == ()
    (found,) = issues
    assert (found.code, found.severity, found.where) == ("altium.import.rule-unmapped", "info", "Rules6/Data")
    assert found.message == "1 rule(s) of kind Width are not mapped (disabled 1)"


def test_scope_outside_the_grammar_and_kinds_without_a_counterpart() -> None:
    issues: list[Issue] = []
    records = [
        rec.rule("Clearance", "A", GAP="10mil", SCOPE1EXPRESSION="InPolygon"),
        rec.rule("Clearance", "B", GAP="10mil", ENABLED="FALSE"),
        rec.rule("PlaneClearance", "C"),
        rec.rule("Width", "D", MINLIMIT="6mil", PREFEREDWIDTH="10mil", MAXLIMIT="20mil"),
    ]
    found = rules_of(*records, issues=issues)
    assert [rule.name for rule in found.rules] == ["D"]
    assert [(i.code, i.message) for i in issues] == [
        ("altium.import.rule-unmapped", "2 rule(s) of kind Clearance are not mapped (disabled 1, scope 1)"),
        ("altium.import.rule-unmapped", "1 rule(s) of kind PlaneClearance are not mapped (no-counterpart 1)"),
    ]


def test_import_rules_holds_no_table_of_its_own() -> None:
    from fenolite.backends.altium.adapter import rules as module
    from fenolite.backends.altium.adapter.evidence import EVIDENCE
    from fenolite.backends.altium.adapter.ids import Ids

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "map_rules(" in source and "RULE_KIND_MAP" not in source and "GAP" not in source
    issues: list[Issue] = []
    found = import_rules([], Ids("altium_pcbdoc", EVIDENCE), file="a.PcbDoc", sha256=rec.SHA, issues=issues)
    assert found.rules == () and issues == []
