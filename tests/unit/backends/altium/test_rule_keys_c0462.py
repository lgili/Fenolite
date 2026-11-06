# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule record keys read (capability altium-project-reader, "Rule record keys read"; change c0462, design
D5). Every record here is authored for Fenolite."""

from __future__ import annotations

from collections.abc import Sequence

from fenolite.backends.altium.adapter.rules import kept_indexes
from fenolite.backends.altium.read.rules import (
    HEADER_KEYS,
    MATCHED_GROUPS,
    CopperLayer,
    CopperLayers,
    Field,
    RuleMapping,
    map_rules,
)
from fenolite.checks.clearance import rule_precedence
from fenolite.model.rules import Rule, RuleKind, RuleSubject, Selector

MM = 1_000_000
MIL = 25_400
TWO = CopperLayers(
    (CopperLayer("Top Layer", "F.Cu", False, 1), CopperLayer("Bottom Layer", "B.Cu", False, 32))
)
FOUR = CopperLayers(
    (
        CopperLayer("Top Layer", "F.Cu", False, 1),
        CopperLayer("Mid 1", "In1.Cu", True, 2),
        CopperLayer("Mid 2", "In2.Cu", True, 3),
        CopperLayer("Bottom Layer", "B.Cu", False, 32),
    )
)
WIDTH = (("MINLIMIT", "0.2mm"), ("PREFEREDWIDTH", "0.25mm"), ("MAXLIMIT", "1mm"))
PAIR = (
    ("MINLIMIT", "4mil"),
    ("MOSTFREQGAP", "6mil"),
    ("MAXLIMIT", "10mil"),
    ("MAXUNCOUPLEDLENGTH", "500mil"),
)


def record(kind: str, *keys: tuple[str, str], **header: str) -> list[Field]:
    """A field list with every header key (defaults below, ``header`` overrides) and ``keys``."""
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
        "UNIQUEID": "ABCDEFGH",
        "DEFINEDBYLOGICALDOCUMENT": "FALSE",
    } | header
    return [*((key, values[key]) for key in HEADER_KEYS), *keys]


def mapped(*records: Sequence[Field], layers: CopperLayers | None = TWO) -> RuleMapping:
    return map_rules(records, origin="keys", layers=layers)


def governing(rules: Sequence[Rule], kind: RuleKind, subject: RuleSubject) -> Rule | None:
    """The rule of ``kind`` that governs ``subject``: the last one in precedence order that selects it."""
    found = [
        rule for rule in rule_precedence(rules) if rule.kind == kind and rule.selector_a.matches(subject)
    ]
    return found[-1] if found else None


def limits(rule: Rule | None) -> tuple[int | None, int | None, int | None]:
    assert rule is not None
    return rule.min, rule.opt, rule.max


# --- 4.1 per-layer values and impedance keys ----------------------------------------------------------


def test_layer_width_of_one_layer() -> None:
    """Scenario "Per-layer widths": the general rule and one rule on B.Cu, which governs there."""
    mapping = mapped(record("Width", *WIDTH, ("BOTTOMLAYER_PREFWIDTH", "0.3mm")))
    assert mapping.unmapped == () and mapping.issues == ()
    general, bottom = mapping.ruleset.rules
    assert (general.name, general.selector_a, limits(general)) == (
        "Width",
        Selector("all"),
        (200_000, 250_000, MM),
    )
    assert (bottom.name, bottom.kind, bottom.selector_a) == (
        "Width/B.Cu",
        "track_width",
        Selector("layer", "B.Cu"),
    )
    assert limits(bottom) == (200_000, 300_000, MM) and bottom.priority == general.priority
    assert mapping.rule_records == (0, 0)
    on_bottom = governing(mapping.ruleset.rules, "track_width", RuleSubject("track", layer="B.Cu"))
    on_top = governing(mapping.ruleset.rules, "track_width", RuleSubject("track", layer="F.Cu"))
    assert on_bottom is bottom and on_top is general


def test_layer_value_equal_to_the_general_one_gives_no_rule() -> None:
    mapping = mapped(record("Width", *WIDTH, ("TOPLAYER_MAXWIDTH", "1mm"), ("BOTTOMLAYER_MINWIDTH", "0.2mm")))
    assert [rule.name for rule in mapping.ruleset.rules] == ["Width"]


def test_layer_values_of_a_scoped_record_on_an_internal_layer() -> None:
    """``MIDLAYER<n>`` is the layer of Altium id ``n + 1``; the layer leaf joins the record's scope."""
    fields = record(
        "Width", *WIDTH, ("MIDLAYER2_MINWIDTH", "0.3mm"), ("MIDLAYER2_PREFWIDTH", "0.3mm"),
        SCOPE1EXPRESSION="InNetClass('PWR')",
    )  # fmt: skip
    mapping = mapped(fields, layers=FOUR)
    general, inner = mapping.ruleset.rules
    leaf = Selector("layer", "In2.Cu")
    assert inner.selector_a == Selector("and", items=(general.selector_a, leaf))
    assert (inner.name, limits(inner)) == ("Width/In2.Cu", (300_000, 300_000, MM))


def test_layer_absent_gives_an_info_and_no_rule() -> None:
    mapping = mapped(record("Width", *WIDTH, ("MIDLAYER5_MAXWIDTH", "2mm"), ("MIDLAYER1_MAXWIDTH", "2mm")))
    assert mapping.unmapped == () and [rule.name for rule in mapping.ruleset.rules] == ["Width"]
    (info,) = mapping.issues
    assert (info.code, info.severity, info.where) == ("altium.rules.layer-absent", "info", "keys#0")
    assert "2 layer(s)" in info.message and "MIDLAYER1, MIDLAYER5" in info.message


def test_layer_key_past_the_numbered_layers_is_refused() -> None:
    (refused,) = mapped(record("Width", *WIDTH, ("MIDLAYER31_MAXWIDTH", "2mm"))).unmapped
    assert (refused.reason, refused.detail) == (
        "keys",
        "MIDLAYER31_MAXWIDTH names no layer an Altium document numbers",
    )


def test_layer_value_that_is_no_length_is_refused() -> None:
    (refused,) = mapped(record("Width", *WIDTH, ("TOPLAYER_MAXWIDTH", "wide"))).unmapped
    assert refused.reason == "value"


def test_layer_values_without_the_board_layers() -> None:
    """A rule file has no board: a per-layer value that differs is refused, one that does not maps."""
    differs = mapped(record("Width", *WIDTH, ("TOPLAYER_MAXWIDTH", "2mm")), layers=None)
    assert [u.reason for u in differs.unmapped] == ["scope"]
    same = mapped(record("Width", *WIDTH, ("TOPLAYER_MAXWIDTH", "1mm")), layers=None)
    assert same.unmapped == () and len(same.ruleset.rules) == 1
    unknown = CopperLayers((CopperLayer("Top Layer", "F.Cu"), CopperLayer("Bottom Layer", "B.Cu")))
    assert [u.reason for u in mapped(differs_fields(), layers=unknown).unmapped] == ["scope"]


def differs_fields() -> list[Field]:
    return record("Width", *WIDTH, ("BOTTOMLAYER_MAXWIDTH", "2mm"))


def test_impedance_keys_are_read_and_unused() -> None:
    """``MINIMP``, ``MAXIMP`` and ``FAVIMP`` without a profile: the widths the record holds are the rule."""
    fields = record(
        "Width", *WIDTH, ("MINIMP", "50.000000"), ("MAXIMP", "50.000000"), ("FAVIMP", "50.000000")
    )
    mapping = mapped(fields)
    assert mapping.unmapped == () and [limits(rule) for rule in mapping.ruleset.rules] == [
        (200_000, 250_000, MM)
    ]


def test_impedance_profile_without_every_layer_is_refused() -> None:
    fields = record(
        "Width", *WIDTH, ("TOPLAYER_PREFWIDTH", "0.3mm"), ("BOTTOMLAYER_PREFWIDTH", "0.3mm"),
        ("IMPEDANCEPROFILEDRIVEN", "TRUE"), ("IMPEDANCEPROFILEID", "{0}"),
        ("IMPEDANCEPROFILEVALUE", "50.000000"),
    )  # fmt: skip
    (refused,) = mapped(fields, layers=FOUR).unmapped
    assert refused.reason == "impedance-profile"
    assert "no WIDTH value for In1.Cu, In2.Cu" in refused.detail
    assert [u.reason for u in mapped(fields, layers=None).unmapped] == ["scope"]


def test_impedance_profile_with_every_layer_maps() -> None:
    fields = record(
        "Width", *WIDTH, ("TOPLAYER_PREFWIDTH", "0.3mm"), ("BOTTOMLAYER_PREFWIDTH", "0.25mm"),
        ("IMPEDANCEPROFILEDRIVEN", "TRUE"),
    )  # fmt: skip
    mapping = mapped(fields)
    assert mapping.unmapped == () and [rule.name for rule in mapping.ruleset.rules] == ["Width", "Width/F.Cu"]


def test_connected_copper_check_is_refused() -> None:
    """``CHECKCONNECTEDCOPPER=TRUE`` judges the width of connected copper, which no neutral rule says: the
    record is refused with its own reason and gives no track rule."""
    mapping = mapped(record("Width", *WIDTH, ("CHECKCONNECTEDCOPPER", "TRUE")))
    (refused,) = mapping.unmapped
    assert (refused.reason, refused.detail) == (
        "connected-copper",
        "CHECKCONNECTEDCOPPER=TRUE: Altium's connected-copper width check, which no neutral rule expresses",
    )
    assert mapping.ruleset.rules == ()
    assert mapped(record("Width", *WIDTH, ("CHECKCONNECTEDCOPPER", "FALSE"))).unmapped == ()


def test_layer_gaps_of_a_pair_record() -> None:
    """Per-layer gaps give ``diff_pair_gap`` rules on the pairs; per-layer pair widths stay unused."""
    fields = record(
        "DiffPairsRouting", *PAIR, ("TOPLAYER_MAXGAP", "5mil"), ("TOPLAYER_PREFGAP", "5mil"),
        ("TOPLAYER_MINWIDTH", "4mil"), ("BOTTOMLAYER_PREFWIDTH", "4mil"),
    )  # fmt: skip
    mapping = mapped(fields)
    assert mapping.unmapped == ()
    names = [(rule.name, rule.kind) for rule in mapping.ruleset.rules]
    assert names == [
        ("DiffPairsRouting", "diff_pair_gap"),
        ("DiffPairsRouting", "diff_pair_uncoupled"),
        ("DiffPairsRouting/F.Cu", "diff_pair_gap"),
    ]
    top = mapping.ruleset.rules[2]
    assert top.selector_a == Selector("and", items=(Selector("diff_pair", "*"), Selector("layer", "F.Cu")))
    assert limits(top) == (4 * MIL, 5 * MIL, 5 * MIL)


def test_profile_pair_record_of_the_corpus_form() -> None:
    """The form of the public profile-driven pair records: gaps on some signal layers only."""
    fields = record(
        "DiffPairsRouting", *PAIR, ("TOPLAYER_MAXGAP", "5mil"), ("MIDLAYER2_MINGAP", "6mil"),
        ("BOTTOMLAYER_MAXGAP", "5mil"), ("IMPEDANCEPROFILEDRIVEN", "TRUE"),
    )  # fmt: skip
    (refused,) = mapped(fields, layers=FOUR).unmapped
    assert refused.reason == "impedance-profile" and "no GAP value for In1.Cu:" in refused.detail


def test_a_record_with_layer_values_is_kept() -> None:
    """The lowering writes no per-layer key, so the record is written back as read (change c0424)."""
    records = [
        record("Width", *WIDTH, ("BOTTOMLAYER_PREFWIDTH", "0.3mm")),
        record("Width", *WIDTH, PRIORITY="2"),
    ]
    assert kept_indexes(records, mapped(*records)) == frozenset({0})


# --- 4.2 via templates ---------------------------------------------------------------------------------

VIA = (
    ("HOLEWIDTH", "8mil"), ("WIDTH", "16mil"), ("VIASTYLE", "Through Hole"), ("MINHOLEWIDTH", "8mil"),
    ("MINWIDTH", "16mil"), ("MAXHOLEWIDTH", "20mil"), ("MAXWIDTH", "40mil"),
)  # fmt: skip
TEMPLATE = (("VIATEMPLATEGUID#1", "{00000000-0000-0000-0000-000000000001}"), ("VIATEMPLATENAME#1", "v16h8"))


def test_template_mode_is_refused() -> None:
    """``USEVIATEMPLATES=TRUE``: no permitted source states what the check tests, so the record is refused."""
    fields = record("RoutingVias", *VIA, ("USEVIATEMPLATES", "TRUE"), *TEMPLATE)
    (refused,) = mapped(fields).unmapped
    assert refused.reason == "template" and "via templates (v16h8)" in refused.detail


def test_template_keys_without_template_mode_are_unused() -> None:
    """Template keys without ``USEVIATEMPLATES=TRUE``: the record's own limits are the rule."""
    for fields in (
        record("RoutingVias", *VIA, *TEMPLATE),
        record("RoutingVias", *VIA, ("USEVIATEMPLATES", "FALSE")),
    ):
        mapping = mapped(fields)
        assert mapping.unmapped == ()
        assert [(rule.kind, limits(rule)) for rule in mapping.ruleset.rules] == [
            ("via_diameter", (16 * MIL, 16 * MIL, 40 * MIL)),
            ("via_drill", (8 * MIL, 8 * MIL, 20 * MIL)),
        ]


def test_template_key_of_another_form_is_refused() -> None:
    (refused,) = mapped(record("RoutingVias", *VIA, ("VIATEMPLATESIZE#1", "16mil"))).unmapped
    assert refused.reason == "keys"


# --- 4.4 Matched Lengths and checks Fenolite performs ------------------------------------------------


def matched(*groups: str, delay: str = "FALSE", **header: str) -> list[Field]:
    flags = [(key, "TRUE" if key in groups else "FALSE") for key in MATCHED_GROUPS]
    keys = (("TOLERANCE", "2mm"), *flags, ("USEDELAYUNITS", delay), ("DELAYTOLERANCE", "0.500000"))
    return record("MatchedLengths", *keys, NETSCOPE="DifferentNets", **header)


def test_matched_lengths_within_pairs_is_a_pair_skew() -> None:
    (rule,) = mapped(matched("CHECKNETSINDIFFPAIR", SCOPE1EXPRESSION="InNetClass('USB')")).ruleset.rules
    assert (rule.kind, limits(rule)) == ("diff_pair_skew", (None, None, 2 * MM))
    assert rule.selector_a == Selector("and", items=(Selector("diff_pair", "*"), Selector("netclass", "USB")))


def test_matched_lengths_of_the_scope_is_a_skew() -> None:
    (rule,) = mapped(matched("CHECKOTHERS", SCOPE1EXPRESSION="InNetClass('DDR')")).ruleset.rules
    assert (rule.kind, rule.selector_a, limits(rule)) == (
        "skew",
        Selector("netclass", "DDR"),
        (None, None, 2 * MM),
    )


def test_matched_lengths_in_delay_units_is_refused() -> None:
    (refused,) = mapped(matched("CHECKOTHERS", delay="TRUE")).unmapped
    assert refused.reason == "delay-units" and "DELAYTOLERANCE=0.500000" in refused.detail


def test_matched_lengths_of_other_groups_is_refused() -> None:
    for groups in (
        ("CHECKXSIGNALS",),
        ("CHECKDIFFPAIRVSDIFFPAIR",),
        ("CHECKOTHERS", "CHECKNETSINDIFFPAIR"),
        (),
    ):
        (refused,) = mapped(matched(*groups)).unmapped
        assert refused.reason == "keys", groups


def test_kinds_read_elsewhere_checked_and_carried() -> None:
    records = [
        record("PolygonConnect", ("CONNECTSTYLE", "Relief")),
        record("ShortCircuit", ("ALLOWED", "FALSE")),
        record("FanoutControl"),
        record("SomeFutureKind"),
    ]
    found = [(u.kind, u.reason) for u in mapped(*records).unmapped]
    assert found == [
        ("PolygonConnect", "read-elsewhere"),
        ("ShortCircuit", "checked"),
        ("FanoutControl", "no-counterpart"),
        ("SomeFutureKind", "no-counterpart"),
    ]
    assert all(issue.code == "altium.rule.unmapped" for issue in mapped(*records).issues)


def test_a_record_that_relaxes_a_check_is_reported() -> None:
    """Scenario: ``ALLOWED=TRUE`` on Short-Circuit, a tolerance on Net Antennae; a disabled one is silent."""
    records = [
        record("ShortCircuit", ("ALLOWED", "TRUE"), SCOPE2EXPRESSION="InNet('B')"),
        record("NetAntennae", ("NETANTENNAETOLERANCE", "1mil")),
        record("NetAntennae", ("NETANTENNAETOLERANCE", "0mil"), PRIORITY="2"),
        record("ShortCircuit", ("ALLOWED", "TRUE"), ENABLED="FALSE", PRIORITY="2"),
    ]
    relaxed = [i for i in mapped(*records).issues if i.code == "altium.rules.check-relaxed"]
    assert [(i.severity, i.where) for i in relaxed] == [("warning", "keys#0"), ("warning", "keys#1")]
    assert "ALLOWED=TRUE" in relaxed[0].message and "NETANTENNAETOLERANCE=1mil" in relaxed[1].message
