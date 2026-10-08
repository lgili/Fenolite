# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The table between the neutral rule kinds and Altium's (capability altium-pcb-writer, "Rule lowering
table" and "Scoped rule records"; change c0084). Hermetic: every rule is authored here."""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

from hypothesis import given
from hypothesis import strategies as st

from fenolite.backends.altium import rulemap
from fenolite.backends.altium.read.rules import PENDING_KINDS, RULE_KIND_MAP
from fenolite.backends.altium.read.scope import parse_scope
from fenolite.backends.altium.rulemap import NOT_LOWERED_REASONS, TABLE, lift, lower, same_rules
from fenolite.model.rules import Rule, RuleKind, Selector

PAGE = Path(__file__).resolve().parents[4] / "docs" / "formats" / "altium" / "pcb-copper.md"
ALL = Selector("all")
PWR = Selector("netclass", "PWR")
MM = 1_000_000


def rule(
    kind: str,
    where: Selector = ALL,
    *,
    name: str = "",
    between: Selector | None = None,
    min: int | None = None,  # noqa: A002
    opt: int | None = None,
    max: int | None = None,  # noqa: A002
    priority: int = 0,
    layers: tuple[str, ...] = (),
    severity: str = "error",
) -> Rule:
    label = name or f"{kind}_{rulemap.selector_text(where)}_{priority}"
    return Rule(
        id=f"rul_{label}",
        name=label,
        kind=kind,  # type: ignore[arg-type]
        selector_a=where,
        selector_b=between,
        layers=layers,
        min=min,
        opt=opt,
        max=max,
        severity=severity,  # type: ignore[arg-type]
        priority=priority,
    )


def one_of_each(where: Selector = ALL) -> list[Rule]:
    """One rule of every ``exact`` kind with the limits its row takes."""
    return [
        rule("clearance", where, min=200_000),
        rule("track_width", where, min=150_000, opt=250_000, max=2 * MM),
        rule("via_diameter", where, min=500_000, opt=600_000, max=800_000),
        rule("via_drill", where, min=250_000, opt=300_000, max=400_000),
        rule("hole_size", where, min=300_000, max=6 * MM),
        rule("edge_clearance", where, min=500_000),
        rule("hole_to_hole", where, min=250_000),
        rule("annular_width", where, min=125_000),
    ]


def table_rows() -> list[list[str]]:
    text = PAGE.read_text(encoding="utf-8").split("### The lowering table", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in text.splitlines() if line.startswith("| `")]
    return [[cell.strip().strip("`") for cell in row.strip("|").split("|")] for row in rows]


def test_complete_every_kind_has_one_row() -> None:
    """Scenario "Every kind has a row": the kinds of the model, and the page's table."""
    assert [row.neutral for row in TABLE] == list(get_args(RuleKind))
    assert all(row.exact or row.status in NOT_LOWERED_REASONS for row in TABLE)
    assert all(row.note for row in TABLE if not row.exact)
    rows = table_rows()
    assert [cells[0] for cells in rows] == [row.neutral for row in TABLE]
    for cells, row in zip(rows, TABLE, strict=True):
        assert cells[6] == row.status, row.neutral
        if row.exact:
            assert (cells[1], int(cells[2])) == (row.altium, row.number)
            assert [
                name for name, cell in zip(("min", "opt", "max"), cells[3:6], strict=True) if cell != "—"
            ] == [name for name in ("min", "opt", "max") if name in row.limits]


def test_complete_exact_rows_are_cited_and_read() -> None:
    """An ``exact`` row is cited on the facts page with a source, and the reader maps its kind back."""
    text = PAGE.read_text(encoding="utf-8")
    facts = text.split("## Rule kinds lowered", 1)[1].split("### The lowering table", 1)[0]
    assert not PENDING_KINDS
    for row in TABLE:
        if not row.exact:
            continue
        entry = RULE_KIND_MAP[row.altium]
        assert row.neutral in [limits.kind for limits in entry.rules]
        assert entry.net_scope == row.net_scope
        assert ("pair" in row.scopes) == entry.binary
        limits = next(limits for limits in entry.rules if limits.kind == row.neutral)
        assert set(limits.keys) <= set(row.fields)
        # the keys of change c0125 (a matrix cell) are read and never written
        assert all(c.key in row.fields for c in entry.conditions if not c.read_only)
        assert not any(c.key in row.fields for c in entry.conditions if c.read_only)
        if row.number not in (0, 2, 11):  # the three kinds of c0038 are cited under "Rules"
            cited = [line for line in facts.splitlines() if f"`RULEKIND={row.altium}`" in line]
            assert cited and re.search(r"\| S-\d{4}", cited[0]) and f"number {row.number}" in cited[0]


def test_single_scopes_are_written_exactly() -> None:
    lowered = lower(one_of_each())
    assert lowered.not_lowered == ()
    assert [(r.kind, r.name, r.scope1, r.scope2, r.priority) for r in lowered.records] == [
        (kind, kind, "All", "All", 1) for kind in rulemap.KIND_ORDER
    ]
    keys = {record.kind: dict(record.keys) for record in lowered.records}
    assert keys["Clearance"] == {
        "GAP": "7.874mil",
        "GENERICCLEARANCE": "7.874mil",
        "IGNOREPADTOPADCLEARANCEINFOOTPRINT": "FALSE",
        "OBJECTCLEARANCES": "",
    }
    assert keys["BoardOutlineClearance"]["GAP"] == "19.685mil"
    assert list(keys["Width"]) == ["MAXLIMIT", "MINLIMIT", "PREFEREDWIDTH"]
    assert keys["Width"] == {"MAXLIMIT": "78.7402mil", "MINLIMIT": "5.9055mil", "PREFEREDWIDTH": "9.8425mil"}
    assert keys["RoutingVias"] == {
        "HOLEWIDTH": "11.811mil",
        "WIDTH": "23.622mil",
        "VIASTYLE": "Through Hole",
        "MINHOLEWIDTH": "9.8425mil",
        "MINWIDTH": "19.685mil",
        "MAXHOLEWIDTH": "15.748mil",
        "MAXWIDTH": "31.4961mil",
    }
    assert keys["HoleSize"] == {
        "ABSOLUTEVALUES": "TRUE",
        "MAXLIMIT": "236.2205mil",
        "MINLIMIT": "11.811mil",
        "MAXPERCENT": "80.000",
        "MINPERCENT": "20.000",
    }
    assert keys["HoleToHoleClearance"] == {"GAP": "9.8425mil", "ALLOWSTACKEDMICROVIAS": "FALSE"}
    assert keys["MinimumAnnularRing"] == {"MINIMUMRING": "4.9213mil"}
    assert [r.net_scope for r in lowered.records] == [
        "DifferentNets", "AnyNet", "AnyNet", "AnyNet", "DifferentNets", "AnyNet", "AnyNet"
    ]  # fmt: skip
    assert [r.number for r in lowered.records] == [0, 2, 11, 42, 63, 52, 19]


def test_roundtrip_of_one_of_each() -> None:
    """Scenario "Round trip of the table"."""
    for where in (ALL, PWR, Selector("net", "VIN")):
        lowered = lower(one_of_each(where))
        lifted, opaque = lift(lowered.records)
        assert opaque == {} and same_rules(lifted, lowered.written)
        assert [r.kind for r in lifted] == [
            "clearance", "track_width", "via_diameter", "via_drill", "hole_size", "edge_clearance",
            "hole_to_hole", "annular_width",
        ]  # fmt: skip


def test_a_rule_with_no_counterpart() -> None:
    """Scenario "A rule with no counterpart"."""
    rules = [
        rule("creepage", Selector("netclass", "HV"), between=ALL, min=4 * MM),
        rule("silk_clearance", min=150_000),
        rule("courtyard_clearance", Selector("ref", "U1"), min=250_000),
        rule("hole_clearance", min=250_000),
        rule("clearance", min=200_000),
    ]
    lowered = lower(rules)
    assert [record.kind for record in lowered.records] == ["Clearance"]
    assert [(item.kind, item.selector, item.reason) for item in lowered.not_lowered] == [
        ("creepage", "netclass HV", "no-counterpart"),
        ("silk_clearance", "all", "no-counterpart"),
        ("courtyard_clearance", "ref U1", "no-counterpart"),
        ("hole_clearance", "all", "no-counterpart"),
    ]
    assert all(item.detail for item in lowered.not_lowered)


def test_values_are_exact_or_refused() -> None:
    cases = [
        rule("track_width", min=200_000),  # the record holds three limits
        rule("hole_size", min=300_000),
        rule("clearance", min=200_000, max=MM),
        rule("clearance", min=1, name="tiny"),  # below the PCB unit
        rule("edge_clearance", min=300_000, severity="warning"),
        rule("via_diameter", min=500_000, opt=600_000, max=800_000),  # no hole rule of that selector
        rule("via_drill", PWR, min=250_000, opt=300_000, max=400_000),
        rule("annular_width", min=3 * 10**12),  # outside the 32-bit range of the unit
    ]
    lowered = lower(cases)
    assert lowered.records == ()
    assert [item.reason for item in lowered.not_lowered] == ["value-unsupported"] * len(cases)
    assert "min, opt, max" in lowered.not_lowered[0].detail and "no opt, max" in lowered.not_lowered[0].detail
    assert "via_drill" in lowered.not_lowered[5].detail and "via_diameter" in lowered.not_lowered[6].detail
    zero = lower([rule("edge_clearance", min=0)])
    assert dict(zero.records[0].keys)["GAP"] == "0mil"


def test_scope_forms() -> None:
    both = Selector("and", items=(Selector("net", "A"), PWR))
    lowered = lower(
        [
            rule("track_width", Selector("net", "A"), min=1, opt=MM, max=MM, name="w_net"),
            rule("track_width", both, min=MM, opt=MM, max=MM, name="w_and"),
            rule("clearance", PWR, between=Selector("net", "GND"), min=MM, name="c_pair"),
            rule("clearance", ALL, between=PWR, min=MM, name="c_second"),
        ]
    )
    assert [item.rule.name for item in lowered.not_lowered] == ["w_net"]  # 1 nm is below the unit
    found = {record.rules[0].name: record for record in lowered.records}
    assert (found["w_and"].scope1, found["w_and"].name) == (
        "InNet('A') And InNetClass('PWR')",
        "Width_net_A_and_PWR",
    )
    assert (found["c_pair"].scope1, found["c_pair"].scope2, found["c_pair"].name) == (
        "InNetClass('PWR')",
        "InNet('GND')",
        "Clearance_PWR_to_net_GND",
    )
    assert (found["c_second"].scope1, found["c_second"].scope2, found["c_second"].name) == (
        "All",
        "InNetClass('PWR')",
        "Clearance_to_PWR",
    )
    for record in lowered.records:
        assert parse_scope(record.scope1) == record.rules[0].selector_a
    lifted, _opaque = lift(lowered.records)
    assert same_rules(lifted, lowered.written)


def test_scope_outside_the_grammar_is_refused_for_that_rule_only() -> None:
    refused = [
        rule("track_width", Selector("net", "PWR_*"), min=MM, opt=MM, max=MM, name="glob"),
        rule("track_width", Selector("net", "it's"), min=MM, opt=MM, max=MM, name="quote"),
        rule("track_width", Selector("ref", "U1"), min=MM, opt=MM, max=MM, name="ref"),
        rule("track_width", Selector("not", items=(PWR,)), min=MM, opt=MM, max=MM, name="not"),
        rule(
            "track_width",
            Selector("or", items=(PWR, Selector("net", "A"))),
            min=MM,
            opt=MM,
            max=MM,
            name="or",
        ),
        rule("track_width", PWR, min=MM, opt=MM, max=MM, layers=("F.Cu",), name="layer"),
        rule("track_width", Selector("layer", "F.Cu"), min=MM, opt=MM, max=MM, name="layer_op"),
        rule("edge_clearance", PWR, between=PWR, min=MM, name="second"),
        rule("track_width", Selector("net", "a|b"), min=MM, opt=MM, max=MM, name="bar"),
    ]
    kept = rule("track_width", PWR, min=MM, opt=MM, max=MM, name="kept")
    lowered = lower([*refused, kept])
    assert [record.name for record in lowered.records] == ["Width_PWR"]
    assert [(item.rule.name, item.reason) for item in lowered.not_lowered] == [
        (item.name, "scope-unsupported") for item in refused
    ]
    assert lowered.not_lowered[5].selector == "netclass PWR on F.Cu"


def test_priority_class_rule_above_the_general_rule() -> None:
    """Scenario "Class rule above the general rule", and the order of the neutral priorities."""
    general = rule("track_width", min=150_000, opt=250_000, max=MM, priority=0, name="general")
    power = rule("track_width", PWR, min=400_000, opt=500_000, max=2 * MM, priority=1, name="power")
    second = rule("track_width", Selector("net", "A"), min=MM, opt=MM, max=MM, priority=2, name="second")
    for order in ([general, power, second], [second, power, general]):
        records = lower(order).records
        assert [(r.name, r.scope1, r.priority) for r in records] == [
            ("Width_PWR", "InNetClass('PWR')", 1),
            ("Width_net_A", "InNet('A')", 2),
            ("Width", "All", 3),
        ]
    assert [r.name for r in rulemap.governing_order([general, power, second])] == [
        "power",
        "second",
        "general",
    ]


def test_priority_counts_per_kind_and_names_are_unique() -> None:
    rules = [
        rule("clearance", min=200_000, priority=0, name="a"),
        rule("clearance", min=300_000, priority=1, name="b"),
        rule("edge_clearance", min=300_000, name="c"),
    ]
    first, again = lower(rules), lower(list(reversed(rules)))
    assert first.records == again.records
    assert [(r.kind, r.name, r.priority, dict(r.keys)["GAP"]) for r in first.records] == [
        ("Clearance", "Clearance", 1, "11.811mil"),
        ("Clearance", "Clearance_2", 2, "7.874mil"),
        ("BoardOutlineClearance", "BoardOutlineClearance", 1, "11.811mil"),
    ]
    assert len({record.name for record in first.records}) == len(first.records)


def test_two_via_pairs_of_one_selector() -> None:
    def pair(index: int) -> list[Rule]:
        return [
            rule("via_diameter", min=500_000, opt=600_000, max=800_000, priority=index, name=f"d{index}"),
            rule("via_drill", min=250_000, opt=300_000, max=400_000, priority=index, name=f"h{index}"),
        ]

    lowered = lower(
        [*pair(1), *pair(2), rule("via_diameter", min=MM, opt=MM, max=MM, priority=3, name="alone")]
    )
    assert [[r.name for r in record.rules] for record in lowered.records] == [["d1", "h1"], ["d2", "h2"]]
    assert [record.name for record in lowered.records] == ["RoutingVias", "RoutingVias_2"]
    assert [item.rule.name for item in lowered.not_lowered] == ["alone"]


def test_lift_counts_what_it_does_not_map() -> None:
    record = lower([rule("clearance", min=200_000)]).records[0]
    matrix = [(key, "x:1" if key == "OBJECTCLEARANCES" else value) for key, value in record.fields()]
    other = [(key, "ShortCircuit" if key == "RULEKIND" else value) for key, value in record.fields()]
    rules, opaque = lift([record, matrix, other, other])
    assert [r.kind for r in rules] == ["clearance"]
    assert opaque == {"Clearance": 1, "ShortCircuit": 2}


_NAMES = st.sampled_from(["A", "GND", "VIN", "PWR", "net-1", "/sheet/N1"])
_LEAVES = st.one_of(
    st.builds(Selector, st.just("net"), _NAMES), st.builds(Selector, st.just("netclass"), _NAMES)
)
_SIDES = st.one_of(
    st.just(ALL),
    _LEAVES,
    st.lists(_LEAVES, min_size=2, max_size=3).map(lambda items: Selector("and", items=tuple(items))),
    st.builds(Selector, st.just("ref"), _NAMES),
    st.builds(Selector, st.just("net"), st.just("PWR_*")),
)
_LENGTHS = st.one_of(st.none(), st.integers(min_value=0, max_value=20 * MM))


@st.composite
def _rules(draw: st.DrawFn) -> Rule:
    kind = draw(st.sampled_from(get_args(RuleKind)))
    row = rulemap.row_of(kind)
    complete = draw(st.booleans())
    limits = {
        name: draw(st.integers(min_value=0, max_value=20 * MM))
        if complete and name in row.limits
        else draw(_LENGTHS)
        for name in ("min", "opt", "max")
    }
    return Rule(
        id=f"rul_{draw(st.integers(min_value=0, max_value=10**9))}",
        name=draw(st.sampled_from(["a", "b", "c", "d"])),
        kind=kind,
        selector_a=draw(_SIDES),
        selector_b=draw(st.one_of(st.none(), _SIDES)),
        layers=draw(st.sampled_from([(), (), (), ("F.Cu",)])),
        severity=draw(st.sampled_from(["error", "error", "error", "warning"])),
        priority=draw(st.integers(min_value=0, max_value=3)),
        **limits,
    )


@given(st.lists(_rules(), max_size=10, unique_by=lambda r: r.id))
def test_roundtrip_of_generated_rule_sets(rules: list[Rule]) -> None:
    """Scenario "Round trip of the table": ``lift(lower(rules).records)`` is the lowered subset within
    2 nm; every rule is written or named with a reason; names are unique and priorities run from 1."""
    lowered = lower(rules)
    lifted, opaque = lift(lowered.records)
    assert opaque == {}
    assert same_rules(lifted, lowered.written)
    assert {r.id for r in lowered.written} | {item.rule.id for item in lowered.not_lowered} == {
        r.id for r in rules
    }
    assert not {r.id for r in lowered.written} & {item.rule.id for item in lowered.not_lowered}
    assert all(item.reason in NOT_LOWERED_REASONS for item in lowered.not_lowered)
    assert len({record.name for record in lowered.records}) == len(lowered.records)
    for kind in rulemap.KIND_ORDER:
        priorities = [record.priority for record in lowered.records if record.kind == kind]
        assert priorities == list(range(1, len(priorities) + 1))
    assert [record.kind for record in lowered.records] == sorted(
        (record.kind for record in lowered.records), key=rulemap.KIND_ORDER.index
    )
