# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rules onto the neutral model (capability altium-project-reader, "Rules onto the neutral model")."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from fenolite.backends.altium.read.proptext import parse_fields
from fenolite.backends.altium.read.rul import read_rule_file
from fenolite.backends.altium.read.rules import (
    HEADER_KEYS,
    UNMAPPED_REASONS,
    Field,
    map_rules,
    record_text,
)
from fenolite.core.ids import derived_id
from fenolite.model.base import ExtBag
from fenolite.model.rules import Rule, Selector

DATA = Path(__file__).resolve().parents[4] / "data" / "altium" / "read"
COMMON: list[Field] = [
    ("SELECTION", "FALSE"),
    ("LAYER", "TOP"),
    ("LOCKED", "FALSE"),
    ("POLYGONOUTLINE", "FALSE"),
    ("USERROUTED", "TRUE"),
    ("UNIONINDEX", "0"),
]


def record(kind: str, *keys: tuple[str, str], **header: str) -> list[Field]:
    """A field list with the common keys, every header key (defaults below, ``header`` overrides) and
    ``keys``."""
    values = {
        "RULEKIND": kind,
        "NETSCOPE": "DifferentNets" if kind == "Clearance" else "AnyNet",
        "LAYERKIND": "SameLayer",
        "SCOPE1EXPRESSION": "All",
        "SCOPE2EXPRESSION": "All",
        "NAME": kind,
        "ENABLED": "TRUE",
        "PRIORITY": "1",
        "COMMENT": "",
        "UNIQUEID": "QWERTYUI",
        "DEFINEDBYLOGICALDOCUMENT": "FALSE",
    } | header
    return [*COMMON, *((key, values[key]) for key in HEADER_KEYS), *keys]


def rule_of(rules: Sequence[Rule], kind: str) -> Rule:
    (found,) = [rule for rule in rules if rule.kind == kind]
    return found


def reasons(records: Sequence[Sequence[Field]], **options: object) -> list[str]:
    return [u.reason for u in map_rules(records, origin="x.RUL", **options).unmapped]  # type: ignore[arg-type]


# --- Clearance and Width (task 6.2) -----------------------------------------------------------------


def test_clearance_and_width() -> None:
    """Scenario "Clearance and width"."""
    records = [
        record("Clearance", ("GAP", "6mil")),
        record(
            "Width",
            ("MINLIMIT", "10mil"),
            ("PREFEREDWIDTH", "20mil"),
            ("MAXLIMIT", "100mil"),
            SCOPE1EXPRESSION="InNetClass('PWR')",
        ),
    ]
    mapping = map_rules(records, origin="board.RUL")
    assert mapping.unmapped == () and mapping.issues == () and mapping.sources == (0, 1)
    clearance, width = mapping.ruleset.rules
    assert clearance.kind == "clearance" and clearance.min == 152_400
    assert clearance.opt is None and clearance.max is None
    assert clearance.selector_a == Selector("all") and clearance.selector_b is None
    assert width.kind == "track_width"
    assert (width.min, width.opt, width.max) == (254_000, 508_000, 2_540_000)
    assert width.selector_a == Selector("netclass", "PWR") and width.selector_b is None


def test_clearance_header_of_a_mapped_rule() -> None:
    fields = record("Clearance", ("GAP", "6mil"), NAME="Gap", PRIORITY="3")
    mapping = map_rules([fields], origin="board.RUL")
    (rule,) = mapping.ruleset.rules
    assert rule.name == "Gap" and rule.priority == 3 and rule.severity == "error" and rule.layers == ()
    assert rule.native_ids == {"altium": "QWERTYUI"}
    assert rule.id == derived_id("rul", "altium", "board.RUL:0:clearance")
    assert rule.ext == {"altium": ExtBag(payload=(("record", record_text(fields)),))}
    assert mapping.ruleset.id == derived_id("rst", "altium", "board.RUL")


def test_clearance_second_scope_and_conditions() -> None:
    both = record(
        "Clearance",
        ("GAP", "8mil"),
        ("GENERICCLEARANCE", "8.0mil"),
        ("IGNOREPADTOPADCLEARANCEINFOOTPRINT", "FALSE"),
        ("OBJECTCLEARANCES", ""),
        SCOPE1EXPRESSION="InNet('A')",
        SCOPE2EXPRESSION="InNetClass('HV')",
    )
    (rule,) = map_rules([both], origin="b").ruleset.rules
    assert rule.selector_a == Selector("net", "A") and rule.selector_b == Selector("netclass", "HV")
    assert reasons([record("Clearance", ("GAP", "8mil"), ("GENERICCLEARANCE", "9mil"))]) == ["keys"]
    assert reasons(
        [record("Clearance", ("GAP", "8mil"), ("IGNOREPADTOPADCLEARANCEINFOOTPRINT", "TRUE"))]
    ) == ["keys"]


def test_clearance_without_record_unique_id() -> None:
    fields = [field for field in record("Clearance", ("GAP", "6mil")) if field[0] != "UNIQUEID"]
    (rule,) = map_rules([fields], origin="b").ruleset.rules
    assert rule.native_ids == {}


def test_width_with_one_limit() -> None:
    (rule,) = map_rules([record("Width", ("MAXLIMIT", "50mil"))], origin="b").ruleset.rules
    assert (rule.min, rule.opt, rule.max) == (None, None, 1_270_000)


def test_rounding_to_the_nanometre_clearance() -> None:
    """Scenario "Rounding to the nanometre"."""
    (rule,) = map_rules([record("Clearance", ("GAP", "3.937mil"))], origin="b").ruleset.rules
    assert rule.min == 100_000 and type(rule.min) is int
    assert all(not isinstance(value, float) for value in dataclasses.asdict(rule).values())


def test_every_other_kind_is_reported_reasons() -> None:
    """Scenario "Every other kind is reported"."""
    records = [
        record("ShortCircuit", ("ALLOWED", "FALSE")),
        record("PlaneConnect", ("PLANECONNECTSTYLE", "Relief")),
        record("BoardOutlineClearance", ("GAP", "10mil")),
        record("Width", ("MINLIMIT", "10mil"), ENABLED="FALSE"),
        record("Clearance", ("GAP", "10mil"), ("OBJECTCLEARANCES", "TrackTrack=10mil")),
    ]
    mapping = map_rules(records, origin="x.RUL")
    assert mapping.ruleset.rules == () and mapping.sources == ()
    assert [(u.index, u.kind, u.reason) for u in mapping.unmapped] == [
        (0, "ShortCircuit", "no-counterpart"),
        (1, "PlaneConnect", "no-counterpart"),
        (2, "BoardOutlineClearance", "no-verified-keys"),
        (3, "Width", "disabled"),
        (4, "Clearance", "keys"),
    ]
    assert [(i.code, i.severity, i.where) for i in mapping.issues] == [
        ("altium.rule.unmapped", "info", f"x.RUL#{index}") for index in range(5)
    ]
    assert "ShortCircuit" in mapping.issues[0].message and "no-counterpart" in mapping.issues[0].message


def test_reasons_in_their_order() -> None:
    """Each reason of the table, and the first one wins when several hold."""
    assert UNMAPPED_REASONS[0] == "summary-form" and UNMAPPED_REASONS[-1] == "scope"
    width = ("MINLIMIT", "10mil")
    assert reasons([[("NAME", "x"), ("PRIORITY", "1")]]) == ["malformed"]
    assert reasons([record("Width", width, NAME="")]) == ["malformed"]
    assert reasons([record("Width", width, PRIORITY="0")]) == ["malformed"]
    assert reasons([record("Width", width, PRIORITY="high")]) == ["malformed"]
    assert reasons([record("Height", width, ENABLED="FALSE")]) == ["no-counterpart"]
    assert reasons([record("BoardOutlineClearance", ENABLED="FALSE")]) == ["no-verified-keys"]
    assert reasons([record("Width", width, ENABLED="FALSE", NETSCOPE="DifferentNets")]) == ["disabled"]
    assert reasons([record("Width", width, NETSCOPE="DifferentNets", LAYERKIND="AdjacentLayers")]) == [
        "net-scope"
    ]
    assert reasons([record("Width", ("BOGUS", "1"), LAYERKIND="AdjacentLayers")]) == ["layer-kind"]
    assert reasons([record("Width", ("TOPLAYER_MINWIDTH", "1mil"), ("MINLIMIT", "x"))]) == ["keys"]
    assert reasons([record("Width", ("MINLIMIT", "10"), SCOPE1EXPRESSION="OnLayer('Top')")]) == ["value"]
    assert reasons([record("Width")]) == ["value"]
    assert reasons([record("Clearance", ("GENERICCLEARANCE", "1mil"))]) == ["keys"]
    assert reasons([record("Clearance")]) == ["value"]
    assert reasons([record("Width", width, SCOPE1EXPRESSION="OnLayer('Top')")]) == ["scope"]
    assert reasons([record("Width", width, SCOPE2EXPRESSION="InNet('A')")]) == ["scope"]
    assert reasons([[f for f in record("Width", width) if f[0] != "SCOPE2EXPRESSION"]]) == ["scope"]
    assert reasons([[f for f in record("Width", width) if f[0] != "SCOPE1EXPRESSION"]]) == ["scope"]
    assert reasons([[f for f in record("Clearance", ("GAP", "1mil")) if f[0] != "SCOPE2EXPRESSION"]]) == [
        "scope"
    ]


def test_reasons_mixed_operators_give_scope() -> None:
    """Scenario "Mixed operators without parentheses": the rule is ``Unmapped`` with the reason scope."""
    fields = record("Width", ("MINLIMIT", "10mil"), SCOPE1EXPRESSION="InNet('A') Or InNet('B') And IsTrack")
    mapping = map_rules([fields], origin="x.RUL")
    assert [(u.reason, "mixes" in u.detail) for u in mapping.unmapped] == [("scope", True)]


def test_reasons_keys_before_rulekind_are_allowed() -> None:
    fields: list[Field] = [("V7_LAYER", "TOP"), ("ANYTHING", None), *record("Width", ("MINLIMIT", "1mil"))]
    assert map_rules([fields], origin="b").unmapped == ()


# --- Routing Via Style, Hole Size, summary, partition, board records (task 6.3) ------------------------


VIA_KEYS = (
    ("HOLEWIDTH", "12mil"),
    ("WIDTH", "25mil"),
    ("VIASTYLE", "Through Hole"),
    ("MINHOLEWIDTH", "12mil"),
    ("MINWIDTH", "25mil"),
    ("MAXHOLEWIDTH", "28mil"),
    ("MAXWIDTH", "50mil"),
)


def test_via_style_gives_two_rules() -> None:
    """Scenario "Via style gives two rules"."""
    mapping = map_rules([record("RoutingVias", *VIA_KEYS)], origin="v.RUL")
    diameter = rule_of(mapping.ruleset.rules, "via_diameter")
    drill = rule_of(mapping.ruleset.rules, "via_drill")
    assert (diameter.min, diameter.opt, diameter.max) == (635_000, 635_000, 1_270_000)
    assert (drill.min, drill.opt, drill.max) == (304_800, 304_800, 711_200)
    assert diameter.name == drill.name and diameter.priority == drill.priority
    assert diameter.native_ids == drill.native_ids == {"altium": "QWERTYUI"} and diameter.id != drill.id
    assert mapping.sources == (0,) and mapping.rule_records == (0, 0)


def test_via_style_with_one_group_and_other_styles() -> None:
    only_drill = record("RoutingVias", ("VIASTYLE", "Through Hole"), ("HOLEWIDTH", "12mil"))
    (rule,) = map_rules([only_drill], origin="b").ruleset.rules
    assert rule.kind == "via_drill" and (rule.min, rule.opt, rule.max) == (None, 304_800, None)
    assert reasons([record("RoutingVias", ("VIASTYLE", "Through Hole"))]) == ["value"]
    assert reasons([record("RoutingVias", ("VIASTYLE", "Blind Buried"), ("WIDTH", "1mil"))]) == ["keys"]
    assert reasons([record("RoutingVias", ("WIDTH", "1mil"))]) == ["keys"]


def test_hole_size_absolute_only() -> None:
    absolute = record(
        "HoleSize",
        ("ABSOLUTEVALUES", "TRUE"),
        ("MAXLIMIT", "100mil"),
        ("MINLIMIT", "1mil"),
        ("MAXPERCENT", "80.000"),
        ("MINPERCENT", "20.000"),
    )
    (rule,) = map_rules([absolute], origin="b").ruleset.rules
    assert rule.kind == "hole_size" and (rule.min, rule.opt, rule.max) == (25_400, None, 2_540_000)
    percent = [(k, "FALSE" if k == "ABSOLUTEVALUES" else v) for k, v in absolute]
    assert reasons([percent]) == ["keys"]
    assert reasons([[f for f in absolute if f[0] != "ABSOLUTEVALUES"]]) == ["keys"]


def test_summary_records_are_never_mapped() -> None:
    """Scenario "Summary records are never mapped"."""
    rules = read_rule_file((DATA / "rules_summary.RUL").read_bytes())
    mapping = map_rules([r.fields for r in rules.records], origin="out.RUL", summary=True)
    assert mapping.ruleset.rules == ()
    assert [(u.reason, u.kind) for u in mapping.unmapped] == [
        ("summary-form", "Width"),
        ("summary-form", "Clearance"),
        ("summary-form", "ShortCircuit"),
    ]
    assert [i.code for i in mapping.issues] == ["altium.rule.summary-form", *["altium.rule.unmapped"] * 3]


def test_fixture_export_records() -> None:
    rules = read_rule_file((DATA / "rules_export.RUL").read_bytes())
    mapping = map_rules([r.fields for r in rules.records], origin="rules_export.RUL")
    assert [r.kind for r in mapping.ruleset.rules] == ["clearance", "track_width"]
    assert [(u.index, u.reason) for u in mapping.unmapped] == [(2, "no-counterpart")]
    assert mapping.ruleset.rules[0].min == 254_000
    assert mapping.ruleset.rules[1].selector_a == Selector("netclass", "Power")


_KEYS = st.sampled_from(
    [*HEADER_KEYS, "GAP", "MINLIMIT", "MAXLIMIT", "WIDTH", "HOLEWIDTH", "VIASTYLE", "ABSOLUTEVALUES", "OTHER"]
)
_VALUES = st.sampled_from(
    ["", "TRUE", "FALSE", "1", "0", "All", "AnyNet", "DifferentNets", "SameLayer", "6mil", "x", "Clearance",
     "Width", "RoutingVias", "HoleSize", "Through Hole", "InNet('A')", "OnLayer('T')"]
)  # fmt: skip
_FIELDS = st.lists(st.tuples(_KEYS, st.one_of(st.none(), _VALUES)), max_size=14)
_KINDS = st.sampled_from(
    ["Clearance", "Width", "RoutingVias", "HoleSize", "ShortCircuit", "BoardOutlineClearance"]
)


@given(
    st.lists(st.one_of(_FIELDS, _KINDS.map(lambda kind: record(kind, ("GAP", "6mil")))), max_size=8),
    st.booleans(),
)
def test_partition_of_record_indexes(records: list[list[Field]], summary: bool) -> None:
    """Every record index is in ``sources`` or in ``unmapped``, never both, and no other index appears."""
    mapping = map_rules(records, origin="p.RUL", summary=summary)
    sources = set(mapping.sources)
    unmapped = [u.index for u in mapping.unmapped]
    assert len(unmapped) == len(set(unmapped)) and not sources & set(unmapped)
    assert sources | set(unmapped) == set(range(len(records)))
    assert len(mapping.rule_records) == len(mapping.ruleset.rules)
    infos = [i for i in mapping.issues if i.code == "altium.rule.unmapped"]
    assert len(infos) == len(unmapped)


def test_own_rules_of_a_board_record() -> None:
    """Scenario "Fenolite's own rules map": the five ``Rules6`` records that c0038's writer puts in the
    blink sample with a net class, each given as its whole field list (the 16-bit kind number left out)."""
    from _altium import blink_pcbdoc_spec
    from _altium_pcb_read import read_pcbdoc

    from fenolite.backends.altium.pcbdoc import NetClassSpec, PcbDocSpec, write_pcbdoc

    spec, _model = blink_pcbdoc_spec()
    assert isinstance(spec, PcbDocSpec)
    power = NetClassSpec("PWR", ("GND", "VIN"), clearance=200_000, track_width=500_000)
    spec = dataclasses.replace(spec, nets=(*spec.nets, "SIG"), net_classes=(power,))
    doc = read_pcbdoc(write_pcbdoc(spec, filename="blink.PcbDoc"))
    assert [r.name for r in doc.rules] == ["Clearance_PWR", "Clearance", "Width_PWR", "Width", "RoutingVias"]
    records = [list(r.fields.items()) for r in doc.rules]
    assert all("RULEKIND" in dict(fields) for fields in records)
    mapping = map_rules(records, origin="blink.PcbDoc")
    assert mapping.unmapped == () and mapping.issues == ()
    kinds = [rule.kind for rule in mapping.ruleset.rules]
    assert kinds == ["clearance", "clearance", "track_width", "track_width", "via_diameter", "via_drill"]
    clearance_pwr = mapping.ruleset.rules[0]
    assert clearance_pwr.selector_a == Selector("netclass", "PWR") and clearance_pwr.priority == 1
    assert clearance_pwr.min == 200_000  # 7.874mil, rounded half to even
    assert mapping.ruleset.rules[1].priority == 2 and mapping.ruleset.rules[1].selector_a == Selector("all")
    assert mapping.ruleset.rules[2].opt == 499_999  # 19.685mil: the writer's 2.54 nm grid, read exactly


def test_property_text_records() -> None:
    text = (
        "|RULEKIND=Width|NETSCOPE=AnyNet|LAYERKIND=SameLayer|SCOPE1EXPRESSION=All"
        "|SCOPE2EXPRESSION=All|NAME=W|ENABLED=TRUE|PRIORITY=2|MINLIMIT=0.2mm"
    )
    fields = parse_fields(text).fields
    (rule,) = map_rules([fields], origin="doc").ruleset.rules
    assert rule.min == 200_000 and rule.priority == 2 and rule.native_ids == {}
