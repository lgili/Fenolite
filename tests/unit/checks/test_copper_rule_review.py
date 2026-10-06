# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored numerical exercises; these values are not normative package distances."""

from dataclasses import replace

import pytest
from _coppercheck import Copper

from fenolite.backends.base import PadCopper
from fenolite.checks.clearance import ClearanceCandidate, ClearanceResolver
from fenolite.checks.copper import check_copper, group_findings
from fenolite.core.coords import Point
from fenolite.model.rules import Selector


def test_intrinsic_findings_survive_translation_rotation_and_review() -> None:
    made = Copper()
    made.netclass("Power", 500)
    made.net("A", "Power")
    made.net("B", "Power")
    made.pad("U1", "01", "A", PadCopper("F.Cu", (Point(0, 0),), 200))
    made.pad("U1", "EP", "B", PadCopper("F.Cu", (Point(400, 0),), 200))
    original = check_copper(made.build(), pads=made.pads)
    (found,) = original.findings
    assert found.relation == "intrinsic" and found.gap == 200
    assert found.explanation.governing.value == 500
    assert found.explanation.candidates == (ClearanceCandidate("class:Power", 500, "error"),)
    moved = tuple(
        replace(
            p,
            position=Point(5000, p.position.x + 9000),
            copper=tuple(
                replace(c, core=tuple(Point(5000 - y.y, y.x + 9000) for y in c.core)) for c in p.copper
            ),
        )
        for p in made.pads
    )
    (after,) = check_copper(made.build(), pads=moved).findings
    assert after.relation == "intrinsic" and after.gap == found.gap and after.items == found.items
    grouped = group_findings(original)
    assert grouped[0].findings == original.findings and grouped[0].source == "class:Power"


def test_selector_and_precedence_are_explained_without_weakening() -> None:
    made = Copper()
    made.pad("U1", "1", "A", PadCopper("F.Cu", (Point(0, 0),), 200))
    made.pad("U2", "2", "B", PadCopper("F.Cu", (Point(400, 0),), 200))
    made.rule("first", 800, Selector("net", "A"), Selector("net", "B"), priority=2)
    made.rule("governing", 500, Selector("net", "A"), Selector("net", "B"), priority=1)
    report = check_copper(made.build(), pads=made.pads)
    (found,) = report.findings
    assert set(report.findings) == {found}
    assert isinstance(hash(found.explanation), int)
    assert isinstance(hash(group_findings(report)[0]), int)
    assert found.relation == "inter_component" and found.clearance == 500
    assert tuple(r.source for r in found.explanation.candidates) == ("rule:first", "rule:governing")
    rows = found.explanation.candidates
    assert tuple(r.rule_id for r in rows) == tuple(r.id for r in made.rules)
    assert tuple(r.priority for r in rows) == (2, 1)
    assert rows[0].selector_a == Selector("net", "A")
    assert rows[0].selector_b == Selector("net", "B")
    assert rows[0].layers == ()
    assert found.explanation.subjects[0].netclass == "Default"
    assert found.explanation.governing.source == "rule:governing"


def test_explanation_preserves_floor_zone_switches_and_ignored_rule() -> None:
    made = Copper()
    made.netclass("Signal", 600)
    first = made.net("A", "Signal")
    second = made.net("B", "Signal")
    made.rule("selected", 300, Selector("all"))
    design = made.build()
    for classes, floor in [(False, False), (True, False), (True, True)]:
        resolver = ClearanceResolver(
            design, min_clearance=800, rules_over_classes=classes, floor_over_rules=floor
        )
        a = resolver.subject("pad", first, ref="U1", layer="F.Cu")
        b = resolver.subject("fill", second, ref=None, layer="F.Cu")
        explained = resolver.explain(a, b, zone_clearance=700)
        assert explained.governing == resolver.resolve(a, b, zone_clearance=700)
        values = {r.source: r.value for r in explained.candidates}
        assert values == {"rule:selected": 300, "class:Signal": 600, "floor": 800, "zone": 700}
        assert (explained.rules_over_classes, explained.floor_over_rules) == (classes, floor)
    assert design.rules
    design = replace(
        design, rules=replace(design.rules, rules=(replace(design.rules.rules[0], severity="ignore"),))
    )
    resolver = ClearanceResolver(design, min_clearance=800)
    explained = resolver.explain(a, b)
    assert explained.governing.value is None and explained.governing.source == "rule:selected"
    assert explained.candidates[0].severity == "ignore"


@pytest.mark.parametrize("zone", [2000, 0])
def test_arc_fill_explains_the_call_that_judged(zone: int) -> None:
    made = Copper()
    made.netclass("Default", 1500)
    made.arc("B", Point(50000, 0), Point(0, 50000), Point(-50000, 0), width=1000)
    # Apex at 50000; copper extends by 500, then an authored gap of 2200 nm.
    ring = (Point(-30000, 52700), Point(30000, 52700), Point(30000, 82700), Point(-30000, 82700))
    made.zone("A", ring, fills=[ring], clearance=zone)
    design = made.build()
    (found,) = check_copper(design, pads=None).findings
    explained = found.explanation
    assert explained is not None
    shown_zone = next((r.value for r in explained.candidates if r.source == "zone"), None)
    assert shown_zone is None
    assert (found.clearance, found.source) == (1500, "class:Default")
    assert explained.governing.value == found.clearance
    assert explained.governing.source == found.source
    assert (
        ClearanceResolver(design).resolve(*explained.subjects, zone_clearance=shown_zone)
        == explained.governing
    )


@pytest.mark.parametrize("zone", [0, -100])
def test_nonpositive_zone_is_absent(zone: int) -> None:
    made = Copper()
    made.netclass("Default", 1500)
    resolver = ClearanceResolver(made.build())
    a = resolver.subject("arc", None, ref=None, layer="F.Cu")
    b = resolver.subject("fill", None, ref=None, layer="F.Cu")
    explained = resolver.explain(a, b, zone_clearance=zone)
    assert all(r.source != "zone" for r in explained.candidates)
    assert explained.governing == resolver.resolve(a, b)


def test_grouping_preserves_each_original_once_without_advice() -> None:
    made = Copper()
    made.netclass("Default", 500)
    made.pad("U1", "1", "A", PadCopper("F.Cu", (Point(0, 0),), 200))
    made.pad("U1", "2", "B", PadCopper("F.Cu", (Point(400, 0),), 200))
    made.pad("U2", "1", "C", PadCopper("F.Cu", (Point(800, 0),), 200))
    original = check_copper(made.build(), pads=made.pads)
    assert len(original.findings) == 2
    missing = replace(original.findings[0], explanation=None)
    routed = replace(
        original.findings[1],
        items=tuple(replace(i, footprint_id="") for i in original.findings[1].items),
        source="other",
    )
    report = replace(original, findings=(*original.findings, missing, routed))
    groups = group_findings(report)
    flattened = tuple(f for group in groups for f in group.findings)
    assert sorted(map(id, flattened)) == sorted(map(id, report.findings))
    assert len(flattened) == len(report.findings)
    assert tuple((g.relation, g.source) for g in groups) == tuple(
        sorted({(f.relation, f.source) for f in report.findings})
    )
    assert all(not hasattr(g, "review_choices") for g in groups)
    assert all(f.relation == g.relation and f.source == g.source for g in groups for f in g.findings)
    assert all(isinstance(hash(g), int) for g in groups)


@pytest.mark.parametrize("kind", ["track", "arc"])
@pytest.mark.parametrize("layer,source", [("F.Cu", "rule:R/track-via"), ("B.Cu", "rule:R")])
def test_item_kind_layer_scope_and_arc_normalization(kind: str, layer: str, source: str) -> None:
    made = Copper()
    made.rule("R", 1000, priority=1)
    scoped = made.rule(
        "R/track-via",
        2000,
        Selector("item_kind", "track"),
        Selector("item_kind", "via"),
        layers=("F.Cu",),
        priority=1,
    )
    resolver = ClearanceResolver(made.build())
    # The public subject helper performs the arc-to-track normalization used by the checker.
    a = resolver.subject("arc" if kind == "arc" else "track", None, ref=None, layer=layer)
    b = resolver.subject("via", None, ref=None, layer=layer)
    explained = resolver.explain(a, b)
    assert explained.governing == resolver.resolve(a, b)
    assert explained.governing.source == source
    assert a.item_kind == "track"
    rules = tuple(r for r in explained.candidates if r.rule_id is not None)
    assert tuple(r.source for r in rules) == (
        ("rule:R", "rule:R/track-via") if layer == "F.Cu" else ("rule:R",)
    )
    if layer == "F.Cu":
        assert rules[-1].rule_id == scoped.id
        assert rules[-1].layers == ("F.Cu",)
        assert (rules[-1].selector_a, rules[-1].selector_b) == (scoped.selector_a, scoped.selector_b)


def test_duplicate_rule_names_preserve_candidate_identity() -> None:
    made = Copper()
    first = made.rule("R", 1000)
    second = made.rule("R", 2000)
    resolver = ClearanceResolver(made.build())
    a = resolver.subject("track", None, ref=None, layer="F.Cu")
    b = resolver.subject("via", None, ref=None, layer="F.Cu")
    explained = resolver.explain(a, b)
    assert tuple(r.rule_id for r in explained.candidates) == tuple(sorted((first.id, second.id)))
    assert len(set(explained.candidates)) == 2
    assert explained.governing.value == second.min
