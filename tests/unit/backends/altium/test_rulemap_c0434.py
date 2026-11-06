# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rules that a KiCad rule set gives and the Altium lowering refused before change c0434 (capability
altium-pcb-writer, "Rule lowering table"): a rule with fewer limits than its record holds, a via diameter
whose drill is a hole_size rule on vias, and the courtyard, silkscreen and differential pair kinds.
Hermetic: every rule is authored here."""

from __future__ import annotations

from fenolite.backends.altium import rulemap
from fenolite.backends.altium.read.rul import read_rule_file
from fenolite.backends.altium.read.rules import map_rules
from fenolite.backends.altium.rulemap import OPEN_MAX, PAIR_WIDTH_KEYS, lift, lower
from fenolite.model.rules import Rule, Selector

ALL = Selector("all")
PWR = Selector("netclass", "PWR")
VIA = Selector("item_kind", "via")
PAIRS = Selector("diff_pair", "*")
MM = 1_000_000
OPEN_TEXT = "3937.0079mil"


def rule(kind: str, where: Selector = ALL, *, name: str = "", **limits: int) -> Rule:
    label = name or f"{kind}_{rulemap.selector_text(where)}"
    return Rule(id=f"rul_{label}", name=label, kind=kind, selector_a=where, **limits)  # type: ignore[arg-type]


def keys_of(record: rulemap.LoweredRule) -> dict[str, str]:
    return dict(record.keys)


def test_a_missing_limit_is_written_open() -> None:
    """A board's minimum track width, via diameter and hole (KiCad gives only ``min``) is written with the
    missing limits open, and the rule is counted changed, not lost."""
    width = rule("track_width", min=150_000)
    hole = rule("hole_size", min=300_000)
    lowered = lower([width, hole])
    assert lowered.not_lowered == ()
    records = {record.kind: keys_of(record) for record in lowered.records}
    assert records["Width"] == {"MAXLIMIT": OPEN_TEXT, "MINLIMIT": "5.9055mil", "PREFEREDWIDTH": "5.9055mil"}
    assert (records["HoleSize"]["MINLIMIT"], records["HoleSize"]["MAXLIMIT"]) == ("11.811mil", OPEN_TEXT)
    assert [(item.rule.id, "written open" in item.detail) for item in lowered.changed] == [
        (width.id, True),
        (hole.id, True),
    ]
    read, opaque = lift(lowered.records)
    assert opaque == {}
    back = {item.kind: (item.min, item.opt, item.max) for item in read}
    assert back["track_width"][0] == 150_000 and back["track_width"][2] is not None
    assert abs(back["track_width"][2] - OPEN_MAX) <= rulemap.TOLERANCE_NM
    assert rulemap.OPEN_MAX == 100 * MM


def test_a_via_takes_its_hole_from_a_hole_rule_on_vias() -> None:
    """The KiCad form of a Routing Via Style (a via_diameter rule and a hole_size rule on the vias of the
    same scope) gives one record with both, and the hole_size rule keeps its own Hole Size record."""
    diameter = rule("via_diameter", PWR, min=600_000, opt=600_000, max=1_200_000)
    drill = rule("hole_size", Selector("and", items=(VIA, PWR)), min=300_000, max=500_000)
    general = rule("hole_size", VIA, min=200_000, max=400_000)
    lowered = lower([diameter, drill, general])
    assert lowered.not_lowered == ()
    (vias,) = [record for record in lowered.records if record.kind == "RoutingVias"]
    keys = keys_of(vias)
    assert vias.scope1 == "InNetClass('PWR')"
    assert (keys["MINHOLEWIDTH"], keys["HOLEWIDTH"], keys["MAXHOLEWIDTH"]) == (
        "11.811mil",
        "11.811mil",
        "19.685mil",
    )
    assert [record.kind for record in lowered.records].count("HoleSize") == 2
    (changed,) = lowered.changed
    assert (
        changed.rule.id == diameter.id
        and "hole_size rule (and(item_kind via, netclass PWR))" in changed.detail
    )
    read, opaque = lift(lowered.records)
    assert opaque == {}
    mins = {item.kind: item.min for item in read if item.kind.startswith("via_")}
    assert mins.keys() == {"via_diameter", "via_drill"}
    assert all(
        value is not None and abs(value - want) <= rulemap.TOLERANCE_NM
        for value, want in ((mins["via_diameter"], 600_000), (mins["via_drill"], 300_000))
    )


def test_a_via_falls_back_on_the_hole_rule_of_every_via() -> None:
    diameter = rule("via_diameter", PWR, min=600_000, opt=600_000, max=1_200_000)
    general = rule("hole_size", VIA, min=200_000, max=400_000)
    (vias,) = [record for record in lower([diameter, general]).records if record.kind == "RoutingVias"]
    assert keys_of(vias)["MINHOLEWIDTH"] == "7.874mil"


def test_a_via_without_any_hole_rule_is_refused() -> None:
    """Negative case: no hole rule applies to the vias, so the record would invent a hole."""
    diameter = rule("via_diameter", PWR, min=600_000, opt=600_000, max=1_200_000)
    only_pads = rule("hole_size", Selector("item_kind", "pad"), min=200_000, max=400_000)
    lowered = lower([diameter, only_pads])
    assert [(item.rule.id, item.reason) for item in lowered.not_lowered] == [
        (diameter.id, "value-unsupported")
    ]
    assert "no hole_size rule applies to its vias" in lowered.not_lowered[0].detail


def test_courtyard_and_silk_clearances_are_written() -> None:
    """Component Clearance and Silk To Silk Clearance hold the two kinds; both read back, and both are
    counted changed because Altium measures them otherwise."""
    courtyard = rule("courtyard_clearance", min=250_000)
    silk = rule("silk_clearance", min=150_000)
    lowered = lower([courtyard, silk])
    assert lowered.not_lowered == ()
    records = {record.kind: (record.number, keys_of(record)) for record in lowered.records}
    assert records["ComponentClearance"] == (
        24,
        {"GAP": "9.8425mil", "COLLISIONCHECKMODE": "3", "VERTICALGAP": "9.8425mil", "SHOWDISTANCES": "FALSE"},
    )
    assert records["SilkToSilkClearance"] == (55, {"SILKTOSILKCLEARANCE": "5.9055mil"})
    assert {item.rule.id for item in lowered.changed} == {courtyard.id, silk.id}
    read, opaque = lift(lowered.records)
    assert opaque == {}
    assert rulemap.same_rules(sorted(read, key=lambda r: r.kind), [courtyard, silk])


def test_a_differential_pair_rule_is_one_record() -> None:
    """The gap and the uncoupled length of one selector share a Differential Pairs Routing record, scoped
    ``All`` for every pair and by the other scope for the pairs of a net class; the reader narrows it to
    the pairs again."""
    gap = rule("diff_pair_gap", PAIRS, min=200_000, opt=200_000, max=250_000)
    uncoupled = rule("diff_pair_uncoupled", PAIRS, max=12 * MM)
    classed = Selector("and", items=(PAIRS, PWR))
    gap_pwr = rule("diff_pair_gap", classed, min=100_000, opt=150_000, max=200_000)
    width = rule("track_width", min=150_000, opt=200_000, max=2 * MM)
    lowered = lower([gap, uncoupled, gap_pwr, width])
    assert lowered.not_lowered == ()
    pairs = [record for record in lowered.records if record.kind == "DiffPairsRouting"]
    assert sorted((record.number, record.scope1, len(record.rules)) for record in pairs) == [
        (51, "All", 2),
        (51, "InNetClass('PWR')", 1),
    ]
    keys = keys_of(next(record for record in pairs if record.scope1 == "All"))
    assert list(keys)[:3] == ["MAXLIMIT", "MINLIMIT", "MOSTFREQGAP"]
    assert list(keys)[3:-1] == list(PAIR_WIDTH_KEYS) and len(PAIR_WIDTH_KEYS) == 96
    assert keys["TOPLAYER_PREFWIDTH"] == "7.874mil" and keys["MAXUNCOUPLEDLENGTH"] == "472.4409mil"
    alone = keys_of(next(record for record in pairs if record.scope1 != "All"))
    assert alone["MAXUNCOUPLEDLENGTH"] == OPEN_TEXT
    read, opaque = lift(lowered.records)
    assert opaque == {}
    selectors = {(item.kind, item.selector_a) for item in read if item.kind.startswith("diff_pair")}
    assert selectors == {
        ("diff_pair_gap", PAIRS),
        ("diff_pair_uncoupled", PAIRS),
        ("diff_pair_gap", classed),
        ("diff_pair_uncoupled", classed),
    }


def test_a_pair_rule_on_named_pairs_or_alone_is_refused() -> None:
    """Negative cases: a selector that names one pair is outside the record's scope, and an uncoupled
    length without a gap rule of its selector would invent a gap."""
    named = rule("diff_pair_gap", Selector("diff_pair", "USB"), min=100_000, opt=100_000, max=100_000)
    uncoupled = rule("diff_pair_uncoupled", PAIRS, max=12 * MM)
    lowered = lower([named, uncoupled])
    assert [(item.rule.id, item.reason) for item in lowered.not_lowered] == [
        (named.id, "scope-unsupported"),
        (uncoupled.id, "value-unsupported"),
    ]
    assert lowered.records == ()


def test_the_rule_file_of_the_new_records_reads_back() -> None:
    """Every record of the new forms, written to a rule file, maps again with no record left over."""
    rules = [
        rule("track_width", min=150_000),
        rule("via_diameter", min=500_000),
        rule("hole_size", VIA, min=250_000),
        rule("courtyard_clearance", min=250_000),
        rule("silk_clearance", min=150_000),
        rule("diff_pair_gap", PAIRS, opt=200_000),
        rule("diff_pair_uncoupled", PAIRS, max=12 * MM),
    ]
    data = rulemap.write_rule_file(rules, name="c0434")
    mapping = map_rules([record.fields for record in read_rule_file(data).records], origin="c0434")
    assert mapping.unmapped == ()
    kinds = sorted(item.kind for item in mapping.ruleset.rules)
    assert kinds == sorted(
        [
            "track_width",
            "via_diameter",
            "via_drill",
            "hole_size",
            "courtyard_clearance",
            "silk_clearance",
            "diff_pair_gap",
            "diff_pair_uncoupled",
        ]
    )
