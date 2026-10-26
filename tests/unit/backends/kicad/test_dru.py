# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Custom rules files in the full dialect (capability kicad-file-backend, "Custom rules files are read
and written"; change c0018): the front end (``-k dialect``), the reader (``-k read``) and the writer."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path
from types import MappingProxyType

import pytest

from fenolite.backends.kicad import rulemap
from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.dru import (
    EVIDENCE,
    CommentItem,
    RuleItem,
    RulesLossError,
    RulesSelfCheckError,
    VersionItem,
    parse_rules,
    print_rules,
    read_rules,
    write_rules,
)
from fenolite.backends.kicad.versions import FutureFormatError, UnsupportedFormatError
from fenolite.core.errors import FormatError, Issue
from fenolite.core.ids import derived_id
from fenolite.model.base import Modeled, Opaque
from fenolite.model.rules import Rule, RuleSet, Selector

ROOT = Path(__file__).resolve().parents[4]
RULES = ROOT / "tests" / "data" / "kicad" / "rules"


def fixture(name: str) -> str:
    return (RULES / f"{name}.kicad_dru").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def proved(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(
        rulemap, "SELECTOR_SUPPORT", MappingProxyType({k: frozenset({9, 10}) for k in rulemap.SELECTOR_KEYS})
    )
    yield


def file_slots(ruleset: RuleSet) -> list[object]:
    return list(slotlib.from_ext(ruleset.ext["kicad"]))


def plain(ruleset: RuleSet) -> RuleSet:
    return dataclasses.replace(
        ruleset, provenance=None, rules=tuple(dataclasses.replace(r, provenance=None) for r in ruleset.rules)
    )


# -- the dialect front end


def test_dialect_items_in_order() -> None:
    document = parse_rules(fixture("comments"))
    kinds = [type(i).__name__ for i in document.items]
    assert kinds == ["VersionItem", "CommentItem", "RuleItem", "CommentItem", "RuleItem", "RuleItem"]
    comment = document.items[3]
    assert isinstance(comment, CommentItem) and comment.text == "  # Comment between two rules, indented."
    inside = document.items[4]
    assert isinstance(inside, RuleItem) and inside.has_comment and "# Comment inside" in inside.text
    assert document.version == 1 and document.node.name == "kicad_dru"
    assert [c.name for c in document.node.nodes()] == ["version", "rule", "rule", "rule"]


def test_dialect_print_is_items() -> None:
    document = parse_rules(fixture("comments"))
    assert print_rules(document.items) == fixture("comments")


def test_dialect_single_quoted_name() -> None:
    with pytest.raises(FormatError) as caught:
        parse_rules(fixture("broken"), file="broken.kicad_dru")
    assert caught.value.file == "broken.kicad_dru" and caught.value.locator == "line 3"
    assert "line 3" in caught.value.message


def test_dialect_literal_inside_condition() -> None:
    assert len(parse_rules(fixture("selectors")).items) == 11


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("(rule a (constraint clearance (min 1mm)))\n", "no \\(version N\\)"),
        ("(version 1)\n(version 1)\n", "second version"),
        ("(version 1)\nstray\n", "top level"),
        ("(version 1)\n(rule a (constraint clearance (min 1mm))) # trailing\n", "top level"),
    ],
)
def test_dialect_errors(text: str, match: str) -> None:
    with pytest.raises(FormatError, match=match):
        parse_rules(text)


def test_dialect_versions() -> None:
    with pytest.raises(UnsupportedFormatError):
        parse_rules("(version 0)\n")
    assert parse_rules("(version 2)\n").version == 2


def test_dialect_offsets_kept() -> None:
    document = parse_rules("(version 1)\n# é\n(rule a (constraint clearance (min 1mm)))\n")
    rule = document.items[2]
    assert isinstance(rule, RuleItem) and rule.line == 3
    assert isinstance(document.items[0], VersionItem) and document.items[0].line == 1


# -- reading


def test_read_comments_and_priorities() -> None:
    issues: list[Issue] = []
    ruleset = read_rules(fixture("comments"), file="comments.kicad_dru", issues=issues)
    assert [r.name for r in ruleset.rules] == ["comment_first", "comment_last"]
    assert [r.priority for r in ruleset.rules] == [3, 1]
    assert [i.code for i in issues] == ["rules.kept-opaque"]
    kinds = [type(s).__name__ for s in file_slots(ruleset)]
    assert kinds == ["Modeled", "Opaque", "Modeled", "Opaque", "Opaque", "Modeled"]
    first = ruleset.rules[0]
    assert first.id == derived_id("rul", "kicad", "rule:comment_first")
    assert first.provenance is not None and first.provenance.locator == "/kicad_dru/rule[0]"
    assert first.provenance.evidence == EVIDENCE
    assert ruleset.rules[1].provenance.locator == "/kicad_dru/rule[2]"  # type: ignore[union-attr]
    assert ruleset.rules[1].severity == "warning" and first.severity == "error"
    clause = [s.field for s in slotlib.from_ext(first.ext["kicad"]) if isinstance(s, Modeled)]
    assert clause == ["name", "condition", "constraint"]


def test_read_units_exactly() -> None:
    ruleset = read_rules(fixture("units"))
    assert [r.min for r in ruleset.rules] == [200_000, 203_200, 254_000]
    text = write_rules(ruleset, target=10)
    assert "(min 0.2mm)" in text and "(min 0.2032mm)" in text and "(min 0.254mm)" in text


def test_read_repeated_names() -> None:
    text = "(version 1)\n" + "(rule a (constraint clearance (min 1mm)))\n" * 2
    first, second = read_rules(text).rules
    assert first.id == derived_id("rul", "kicad", "rule:a")
    assert second.id == derived_id("rul", "kicad", "rule:a:1")


def test_read_single_quoted_name() -> None:
    with pytest.raises(FormatError) as caught:
        read_rules(fixture("broken"), file="broken.kicad_dru")
    assert caught.value.file == "broken.kicad_dru" and caught.value.locator == "line 3"


def test_read_selectors_lifted() -> None:
    ruleset = read_rules(fixture("selectors"))
    assert len(ruleset.rules) == 10
    by_name = {r.name: r for r in ruleset.rules}
    assert by_name["sel_b"].selector_b == Selector("netclass", "SEL_C")
    assert by_name["sel_layer"].layers == ("B.Cu",)
    assert by_name["sel_item_kind"].kind == "hole_size"
    assert by_name["sel_item_kind"].selector_a == Selector("item_kind", "via")
    assert by_name["sel_glob"].selector_a == Selector("net", "SEL_*")


UNREPRESENTABLE = """(version 1)
(rule first (constraint clearance (min 1mm)))
(rule spokes (constraint thermal_spoke_width (min 0.3mm)))
(rule last (constraint clearance (min 2mm)))
"""


def test_read_unrepresentable_kept_opaque() -> None:
    issues: list[Issue] = []
    ruleset = read_rules(UNREPRESENTABLE, issues=issues)
    slots = file_slots(ruleset)
    assert slots[1:] == [
        Modeled("rules"),
        Opaque("(rule spokes (constraint thermal_spoke_width (min 0.3mm)))", "1"),
        Modeled("rules"),
    ]
    assert [i.code for i in issues] == ["rules.kept-opaque"] and issues[0].where == "/kicad_dru/rule[1]"
    text = write_rules(ruleset, target=9)
    spokes = text.index("\n(rule spokes (constraint thermal_spoke_width (min 0.3mm)))\n")
    assert text.index('"first"') < spokes < text.index('"last"')


def test_read_opaque_fixture() -> None:
    issues: list[Issue] = []
    ruleset = read_rules(fixture("opaque"), issues=issues)
    assert [r.name for r in ruleset.rules] == ["opaque_lifted"]
    assert len(issues) == 3 and {i.code for i in issues} == {"rules.kept-opaque"}


def test_read_future_file() -> None:
    issues: list[Issue] = []
    ruleset = read_rules("(version 2)\n(rule a (constraint clearance (min 1mm)))\n", issues=issues)
    assert [i.code for i in issues] == ["kicad.version.future"] and ruleset.rules == ()
    assert all(isinstance(s, (Opaque, Modeled)) for s in file_slots(ruleset))
    assert [s for s in file_slots(ruleset) if isinstance(s, Opaque)] == [
        Opaque("(rule a (constraint clearance (min 1mm)))", "2")
    ]
    with pytest.raises(FutureFormatError):
        write_rules(ruleset, target=10)


# -- writing


def test_write_comments_stay_in_place() -> None:
    ruleset = read_rules(fixture("comments"))
    text = write_rules(ruleset, target=10)
    assert text == fixture("comments")
    again = read_rules(text)
    assert plain(again) == plain(ruleset)


@pytest.mark.parametrize("name", ["comments", "units", "selectors", "overlap", "opaque"])
def test_write_fixture_round_trip(name: str) -> None:
    ruleset = read_rules(fixture(name))
    for target in (9, 10):
        assert plain(read_rules(write_rules(ruleset, target=target))) == plain(ruleset)


def test_ten_only_refused_for_9() -> None:
    ruleset = read_rules(fixture("ten_only"))
    with pytest.raises(RulesLossError) as caught:
        write_rules(ruleset, target=9)
    assert caught.value.droppable is True and caught.value.cli_code == "FEN-7001"
    assert [i.code for i in caught.value.issues] == ["kicad.token.too-new"]
    assert "--allow-lossy" in caught.value.hint
    assert "bridged_mask" in caught.value.issues[0].message


def test_ten_only_dropped_with_allow_lossy() -> None:
    found: list[Issue] = []
    text = write_rules(read_rules(fixture("ten_only")), target=9, allow_lossy=True, issues=found)
    assert '(rule "canary"' in text and "bridged_mask" not in text
    assert [i.code for i in found] == ["rules.dropped-for-target"]
    assert "ten_only" in found[0].message and "bridged_mask" in found[0].message
    assert "bridged_mask" in write_rules(read_rules(fixture("ten_only")), target=10)


def test_ten_only_downgrade_is_a_design_loss() -> None:
    """Change c0162: with ``downgrade`` a ten-only rules row is a ``design`` edit of the resolver; it
    still needs ``allow_lossy``, and the output equals that of the lossy write without it."""
    from fenolite.backends.kicad import resolver

    ruleset = read_rules(fixture("ten_only"))
    with pytest.raises(RulesLossError):
        write_rules(ruleset, target=9, downgrade=True)
    edits: list[resolver.Edit] = []
    text = write_rules(ruleset, target=9, allow_lossy=True, downgrade=True, edits=edits)
    assert text == write_rules(ruleset, target=9, allow_lossy=True)
    assert [(e.row, e.action) for e in edits] == [("rules-type-bridged-mask", "design")]
    assert edits[0].where.startswith("rule ")


FROBNICATE = (
    "(version 1)\n"
    "(rule odd (condition \"A.NetName == 'X'\") (constraint clearance (min 1mm)) (frobnicate 1))\n"
)


def test_uninventoried_kept_for_10_refused_for_9() -> None:
    ruleset = read_rules(FROBNICATE)
    found: list[Issue] = []
    assert "(frobnicate 1)" in write_rules(ruleset, target=10, issues=found)
    assert [i.code for i in found] == ["kicad.token.uninventoried"]
    with pytest.raises(RulesLossError) as caught:
        write_rules(ruleset, target=9)
    assert caught.value.droppable is True


def test_assign_component_class_refused_for_9() -> None:
    text = '(version 1)\n(rule cc (condition "A.NetName == \'X\'") (assign_component_class "C"))\n'
    with pytest.raises(RulesLossError):
        write_rules(read_rules(text), target=9)
    found: list[Issue] = []
    write_rules(read_rules(text), target=10, issues=found)
    assert {i.code for i in found} == {"kicad.token.uninventoried"}


def test_opaque_text_that_does_not_parse() -> None:
    ruleset = RuleSet(
        id=derived_id("rst", "test", "x"),
        ext={
            "kicad": slotlib.to_ext([Modeled("version"), Opaque("(rule broken (constraint clearance", "1")])
        },
    )
    with pytest.raises(RulesSelfCheckError) as caught:
        write_rules(ruleset, target=10)
    assert caught.value.step == "parse" and caught.value.cli_code == "FEN-1001"


def test_rules_without_slots_get_severity() -> None:
    rule = Rule(
        id=derived_id("rul", "test", "a"), name="a", kind="clearance", selector_a=Selector("all"), min=10**6
    )
    text = write_rules(RuleSet(id=derived_id("rst", "test", "a"), rules=(rule,)), target=10)
    assert text == '(version 1)\n(rule "a"\n\t(constraint clearance (min 1mm))\n\t(severity error)\n)\n'


def test_edited_rule_keeps_clause_order_and_inserts() -> None:
    ruleset = read_rules(fixture("units"))
    first = dataclasses.replace(ruleset.rules[0], severity="warning", layers=("F.Cu",))
    text = write_rules(dataclasses.replace(ruleset, rules=(first, *ruleset.rules[1:])), target=10)
    rule = text.split("(rule ")[1]
    order = [line.strip().split(" ")[0] for line in rule.splitlines()[1:-1]]
    assert order == ["(layer", "(condition", "(constraint", "(severity"]


def test_extra_and_removed_rules() -> None:
    ruleset = read_rules(fixture("comments"))
    extra = Rule(
        id=derived_id("rul", "test", "x"), name="x", kind="clearance", selector_a=Selector("all"), min=1
    )
    text = write_rules(dataclasses.replace(ruleset, rules=(ruleset.rules[0], extra)), target=10)
    assert text.index('(rule "x"') > text.index("comment_inside") and "comment_last" not in text
    text = write_rules(dataclasses.replace(ruleset, rules=()), target=10)
    assert "# Comment before" in text and "comment_inside" in text and "comment_first" not in text


def test_unsupported_selector_not_droppable() -> None:
    rule = Rule(
        id=derived_id("rul", "test", "l"),
        name="l",
        kind="clearance",
        selector_a=Selector("layer", "F.Cu"),
        min=1,
    )
    with pytest.raises(RulesLossError) as caught:
        write_rules(RuleSet(id=derived_id("rst", "test", "l"), rules=(rule,)), target=10, allow_lossy=True)
    assert caught.value.droppable is False and "--allow-lossy" not in caught.value.hint


# -- track layer rules (change c0107; the other cases are in test_rulemap_no_tracks.py)


def test_no_tracks_lift_and_opaque_forms() -> None:
    """Scenario "Lift and opaque forms" (capability kicad-file-backend, "Track layer rules in rules
    files")."""
    text = (
        "(version 1)\n"
        '(rule "a" (layer "In2.Cu") (condition "A.NetClass == \'SIG\'") (constraint disallow track))\n'
        '(rule "b" (layer inner) (condition "A.NetClass == \'SIG\'") (constraint disallow track))\n'
        '(rule "c" (layer "F.Cu") (constraint disallow via))\n'
    )
    issues: list[Issue] = []
    (a,) = read_rules(text, issues=issues).rules
    assert (a.name, a.kind, a.layers) == ("a", "no_tracks", ("In2.Cu",))
    assert a.selector_a == Selector("netclass", "SIG")
    assert [i.code for i in issues] == ["rules.kept-opaque", "rules.kept-opaque"]


# -- conditions that name an area (change c0103) --------------------------------------------------------

AREA_RULES = """(version 1)
(rule "hv"
\t(condition "A.intersectsArea('HV')")
\t(constraint clearance (min 2mm))
)
(rule "inner"
\t(condition "A.enclosedByArea('HV')")
\t(constraint clearance (min 2mm))
)
(rule "creep"
\t(condition "A.intersectsArea('HV')")
\t(constraint creepage (min 4mm))
)
"""


def test_area_condition_is_lifted_and_written_back() -> None:
    """Scenario "Enclosed area stays opaque": ``intersectsArea`` is lifted, ``enclosedByArea`` is kept as
    written, and so is an area on a kind that takes none; the text is written back as it was."""
    issues: list[Issue] = []
    ruleset = read_rules(AREA_RULES, issues=issues)
    (lifted,) = ruleset.rules
    assert (lifted.name, lifted.selector_a, lifted.min) == ("hv", Selector("area", "HV"), 2_000_000)
    assert [i.code for i in issues] == ["rules.kept-opaque", "rules.kept-opaque"]
    assert "enclosedByArea" in issues[0].message or issues[0].where.endswith("rule[1]")
    assert write_rules(ruleset, target=10) == AREA_RULES


# -- hand-written pair rules (change c0104)

PAIR_RULES = """(version 1)
(rule usb_gap
\t(layer "F.Cu")
\t(condition "A.inDiffPair('USB_')")
\t(constraint diff_pair_gap (min 0.13mm) (opt 0.15mm) (max 0.17mm)))
(rule usb_uncoupled (condition "A.inDiffPair('USB_')") (constraint diff_pair_uncoupled (max 5mm)))
(rule u_skew (condition "A.inDiffPair('*')") (constraint skew (opt 0.05mm) (max 0.15mm) (within_diff_pairs)))
(rule ddr_skew (condition "A.NetClass == 'DDR'") (constraint skew (max 1mm)))
(rule clk_length (condition "A.NetName == 'CLK'") (constraint length (min 20mm) (opt 25mm) (max 30mm)))
(rule inside (condition "A.inDiffPair('USB_') && B.inDiffPair('USB_')") (constraint clearance (min 0.1mm)))
"""
PAIR_OPAQUE = """(version 1)
(rule a (condition "A.inDiffPair('USB_')") (constraint diff_pair_uncoupled (min 1mm) (max 5mm)))
(rule b (condition "A.inDiffPair('USB_')") (constraint skew (max 0.1mm) within_diff_pairs))
(rule c (condition "A.NetName == 'CLK'") (constraint length (max 150ps)))
(rule d (layer "F.Cu") (condition "A.inDiffPair('USB_')") (constraint skew (max 0.1mm) (within_diff_pairs)))
(rule e (condition "A.inDiffPair('USB_')") (constraint skew (within_diff_pairs) (max 0.1mm)))
(rule f (condition "A.memberOfFootprint('U1')") (constraint length (max 30mm)))
(rule g (condition "AB.isCoupledDiffPair()") (constraint clearance (min 0.1mm)))
(rule h (condition "A.inDiffPair('USB_')") (constraint diff_pair_gap (min 0.1mm) (within_diff_pairs)))
(rule kept (condition "A.inDiffPair('USB_')") (constraint diff_pair_gap (min 0.13mm)))
"""


def test_read_pair_rules_lifted() -> None:
    """The five kinds, their ``opt``, the list of a skew within pairs, the pair leaf and a layer clause on
    a gap rule lift into the model."""
    issues: list[Issue] = []
    ruleset = read_rules(PAIR_RULES, issues=issues)
    assert issues == []
    by_name = {r.name: r for r in ruleset.rules}
    usb, every = Selector("diff_pair", "USB_"), Selector("diff_pair", "*")
    gap = by_name["usb_gap"]
    assert (gap.kind, gap.selector_a, gap.layers) == ("diff_pair_gap", usb, ("F.Cu",))
    assert (gap.min, gap.opt, gap.max) == (130_000, 150_000, 170_000)
    assert (by_name["usb_uncoupled"].kind, by_name["usb_uncoupled"].max) == ("diff_pair_uncoupled", 5_000_000)
    skew = by_name["u_skew"]
    assert (skew.kind, skew.selector_a, skew.opt, skew.max) == ("diff_pair_skew", every, 50_000, 150_000)
    assert (by_name["ddr_skew"].kind, by_name["ddr_skew"].selector_a) == ("skew", Selector("netclass", "DDR"))
    length = by_name["clk_length"]
    assert (length.kind, length.min, length.opt, length.max) == ("length", 20_000_000, 25_000_000, 30_000_000)
    inside = by_name["inside"]
    assert (inside.kind, inside.selector_a, inside.selector_b) == ("clearance", usb, usb)


def test_read_pair_rules_rebuilt() -> None:
    """A rules file holding hand-written pair rules is written back with its names and clause order, and
    reads back as the same rules."""
    ruleset = read_rules(PAIR_RULES)
    text = write_rules(ruleset, target=10)
    assert plain(read_rules(text)) == plain(ruleset)
    assert text.index("usb_gap") < text.index("u_skew") < text.index("inside")
    assert "(within_diff_pairs)" in text and "A.inDiffPair('*')" in text


def test_read_pair_rules_outside_the_grammar_kept_opaque() -> None:
    """A limit outside the kind's row, a bare ``within_diff_pairs`` atom, a time unit, a layer clause on a
    pair kind other than the gap, the list before the limits, a selector outside the kind's grammar and
    ``isCoupledDiffPair()`` stay opaque and are written back verbatim."""
    issues: list[Issue] = []
    ruleset = read_rules(PAIR_OPAQUE, issues=issues)
    assert [r.name for r in ruleset.rules] == ["kept"]
    assert [i.code for i in issues] == ["rules.kept-opaque"] * 8
    text = write_rules(ruleset, target=10)
    for line in PAIR_OPAQUE.splitlines()[1:9]:
        assert line in text, line
