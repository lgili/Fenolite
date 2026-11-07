# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Mask and paste expansions by the record that governs each pad and via (change c0462, design D6, task 4.4;
capability design-conversion, "Mask and paste of imported pads"). Each scope is read with the full grammar;
a pad or via takes the first record, by priority, whose scope selects it. Authored records only."""

from __future__ import annotations

from fenolite.backends.altium.read.scope import ScopeClass, ScopeDocument, ScopeLayer
from fenolite.convert import openings
from fenolite.core.coords import Point, Size
from fenolite.model.board import Pad
from fenolite.model.rules import RuleSubject, Selector

MIL = 25_400
COPPER = frozenset({"Top", "Bottom"})
DOCUMENT = ScopeDocument(
    unit="mil",
    layers=(ScopeLayer("Top Layer", "Top", False, 1), ScopeLayer("Bottom Layer", "Bottom", False, 32)),
    blind_vias=False,
    smd_plated=True,
)
"""A two-layer document in mils, whose vias span the stack and whose surface pads are plated."""
THROUGH = ("Top", "Bottom")


def _rule(kind: str, scope: str, priority: int, expansion: str, **more: str) -> dict[str, str]:
    return {
        "RULEKIND": kind,
        "ENABLED": "TRUE",
        "PRIORITY": str(priority),
        "SCOPE1EXPRESSION": scope,
        "EXPANSION": expansion,
        **more,
    }


def _mask(scope: str, priority: int, expansion: str, **more: str) -> dict[str, str]:
    return _rule(openings.MASK_RULE, scope, priority, expansion, **more)


def _paste(scope: str, priority: int, expansion: str) -> dict[str, str]:
    return _rule(openings.PASTE_RULE, scope, priority, expansion)


def _pad(kind: str = "smd", layers: tuple[str, ...] = ("Top",), drill: int | None = None) -> Pad:
    return Pad(
        id="pad-1", number="1", shape="rect", size=Size(MIL * 40, MIL * 40), position=Point(0, 0),
        kind=kind, layers=layers, drill=drill,  # type: ignore[arg-type]
    )  # fmt: skip


def _rules(
    *records: dict[str, str], document: ScopeDocument | None = DOCUMENT
) -> tuple[openings.ExpansionRule, ...]:
    return openings.expansion_rules(records, openings.MASK_RULE, document)


def _governed(
    rules: tuple[openings.ExpansionRule, ...], pad: Pad, net: str | None = None
) -> openings.Governed:
    return openings.governing_expansion(rules, openings.pad_subject(pad, COPPER, net=net))


def test_the_records_of_one_kind_by_priority() -> None:
    found = _rules(
        _mask("All", 3, "4mil"),
        _mask("InNet('GND')", 1, "1mil"),
        _mask("All", 2, "2mil", ENABLED="FALSE"),
        _paste("All", 1, "-2mil"),
        _mask("Foo(", 2, "3mil"),
    )
    assert [(rule.priority, rule.scope, rule.value) for rule in found] == [
        (1, "InNet('GND')", MIL),
        (2, "Foo(", 3 * MIL),
        (3, "All", 4 * MIL),
    ]
    assert found[0].selector is not None and found[1].selector is None


def test_a_pad_takes_the_first_record_that_selects_it() -> None:
    rules = _rules(_mask("InNet('GND')", 1, "1mil"), _mask("IsVia", 2, "5mil"), _mask("All", 3, "4mil"))
    assert _governed(rules, _pad(), "GND") == openings.Governed(MIL)
    assert _governed(rules, _pad(), "VCC") == openings.Governed(4 * MIL)
    assert _governed(rules[:2], _pad(), "VCC") == openings.Governed()


def test_a_record_outside_the_grammar_before_it_is_reported() -> None:
    """The pad takes the next record that selects it, and the scope that may govern it is kept: its
    ``pad-margin`` row (``SCOPED_REASON``)."""
    rules = _rules(_mask("Foo(", 1, "1mil"), _mask("All", 2, "4mil"))
    subject = openings.pad_subject(_pad(), COPPER, net="GND")
    assert openings.governing_expansion(rules, subject) == openings.Governed(4 * MIL, unread="Foo(")
    expansions = openings.pad_expansions(rules, (), subject)
    assert expansions == openings.RuleExpansions(openings.RuleExpansion(4 * MIL, scoped=True))
    opened, reasons = openings.open_pad(_pad(), expansions, {})
    assert opened.mask_margin == 4 * MIL and reasons == (openings.SCOPED_REASON,)


def test_the_subject_of_a_pad() -> None:
    top = openings.pad_subject(_pad(), COPPER)
    through = openings.pad_subject(_pad("thru_hole", THROUGH, 30 * MIL), COPPER)
    assert (top.item_kind, top.layer, top.hole, top.pad_type) == ("pad", "Top", None, "smd")
    assert (through.layer, through.hole, through.pad_type) == (None, 30 * MIL, "th")


def test_a_layer_scope_of_a_pad_with_a_hole() -> None:
    """A surface pad lies on one copper layer. ``OnLayer`` holds the vias and the pads with a hole by its own
    terms, so it decides them without their layer; a bare layer leaf cannot be judged for them."""
    rules = _rules(_mask("OnLayer('Bottom Layer')", 1, "1mil"), _mask("All", 2, "4mil"))
    through = _pad("thru_hole", THROUGH, 30 * MIL)
    assert _governed(rules, _pad()) == openings.Governed(4 * MIL)
    assert _governed(rules, _pad(layers=("Bottom",))) == openings.Governed(MIL)
    assert _governed(rules, through) == openings.Governed(MIL)
    scope = "IsPad and Not OnLayer('Bottom Layer')"
    only = _rules(_mask(scope, 1, "1mil"), _mask("All", 2, "4mil"))
    assert only[0].selector is not None
    assert _governed(only, _pad()) == openings.Governed(MIL)
    assert _governed(only, _pad(layers=("Bottom",))) == openings.Governed(4 * MIL)
    assert _governed(only, through) == openings.Governed(4 * MIL)
    on_bottom = Selector("and", items=(Selector("item_kind", "pad"), Selector("layer", "Bottom")))
    bare = (
        openings.ExpansionRule(1, "bare", on_bottom, MIL),
        openings.ExpansionRule(2, "All", Selector("all"), 0),
    )
    assert _governed(bare, through) == openings.Governed(0, unread="bare")
    assert _governed(bare, _pad(layers=("Bottom",))) == openings.Governed(MIL)


def test_a_hole_and_plating_scope() -> None:
    rules = _rules(
        _mask("HoleSize > 20", 1, "1mil"),
        _mask("IsPad and (PadIsPlated = False)", 2, "2mil"),
        _mask("All", 3, "4mil"),
    )
    assert all(rule.selector is not None for rule in rules)
    assert _governed(rules, _pad("thru_hole", THROUGH, 30 * MIL)) == openings.Governed(MIL)
    assert _governed(rules, _pad("thru_hole", THROUGH, 10 * MIL)) == openings.Governed(4 * MIL)
    assert _governed(rules, _pad("np_thru_hole", THROUGH, 10 * MIL)) == openings.Governed(2 * MIL)
    assert _governed(rules, _pad()) == openings.Governed(4 * MIL)


def test_a_net_in_several_classes() -> None:
    """An Altium net may be in several net classes: ``InNetClass`` selects it by each, read from the
    document's classes, not by the one class the neutral net names."""
    document = ScopeDocument(
        nets=("GND", "VCC"),
        classes=(
            ScopeClass(0, "Power", ("VCC", "GND")),
            ScopeClass(0, "Ground", ("GND",)),
            ScopeClass(0, "All Nets", (), superclass=True),
        ),
    )
    rules = _rules(_mask("InNetClass('Ground')", 1, "1mil"), _mask("All", 2, "4mil"), document=document)
    subject = openings.pad_subject(_pad(), COPPER, net="GND", netclass="Power")
    both = frozenset({"power", "ground", "all nets"})
    assert openings.governing_expansion(rules, subject, both) == openings.Governed(MIL)
    one = frozenset({"power", "all nets"})
    assert openings.governing_expansion(rules, subject, one) == openings.Governed(4 * MIL)
    assert openings.governing_expansion(rules, subject) == openings.Governed(4 * MIL)


def test_a_via_takes_the_record_that_selects_it() -> None:
    rules = _rules(
        _mask("InNet('GND')", 1, "2mil"),
        _mask("IsVia", 2, "1mil", SOLDERMASKFROMHOLE="TRUE"),
        _mask("All", 3, "4mil"),
    )
    ground = RuleSubject("via", net="GND", hole=10 * MIL)
    other = RuleSubject("via", net="VCC", hole=10 * MIL)
    assert openings.via_governing(rules, ground) == openings.ViaRule(2 * MIL, from_hole=False)
    assert openings.via_governing(rules, other) == openings.ViaRule(MIL, from_hole=True)
    assert _governed(rules, _pad(), "VCC") == openings.Governed(4 * MIL)


def test_a_room_is_not_judged() -> None:
    """The conversion places no object in a room: a record that selects one by its room is reported, as one
    outside the grammar is, unless the rest of its scope decides it."""
    room = Selector("area", "R1")
    rules = (
        openings.ExpansionRule(1, "in R1", Selector("and", items=(Selector("item_kind", "via"), room)), MIL),
        openings.ExpansionRule(2, "All", Selector("all"), 4 * MIL),
    )
    assert openings.governing_expansion(rules, RuleSubject("via")) == openings.Governed(
        4 * MIL, unread="in R1"
    )
    assert openings.governing_expansion(rules, RuleSubject("pad")) == openings.Governed(4 * MIL)


def test_the_pads_of_an_imported_document() -> None:
    """``RuleSubjects`` and ``pad_rules`` on an authored document: the net of each pad, its classes as the
    document's classes hold them and its component's designator choose the record that governs it."""
    import _altium_records as rec

    from fenolite.backends.altium.adapter import import_board
    from fenolite.convert.altium_to_kicad import RuleSubjects, pad_rules

    document = rec.document(
        nets=("GND", "VCC"),
        components=(rec.component("U1"), rec.component("R1", x="2500mil")),
        classes=(rec.net_class("Power", ("VCC", "GND")), rec.net_class("Ground", ("GND",))),
        pads=(
            rec.pad("1", (2000 * MIL, 1500 * MIL), net=0, component=0),
            rec.pad("2", (2100 * MIL, 1500 * MIL), net=1, component=0),
            rec.pad("1", (2500 * MIL, 1500 * MIL), net=1, component=1, hole=30 * MIL, layer=74),
        ),
    )
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA)
    records = (
        _mask("InNetClass('Ground')", 1, "1mil"),
        _mask("InComponent('R1')", 2, "2mil"),
        _mask("All", 3, "4mil"),
        _paste(
            "InNet('VCC') and OnLayer('Layer 1')", 1, "-1mil"
        ),  # the authored board's name of its top layer
    )
    subjects = RuleSubjects(design, document)
    assert subjects.document is not None
    found = pad_rules(design, records, subjects)
    assert design.board is not None
    by_name = {
        (subjects.refs[fp.component_id], pad.number): found[pad.id]
        for fp in design.board.footprints
        for pad in fp.pads
    }
    assert {key: (value.mask.value, value.paste.value) for key, value in by_name.items()} == {
        ("U1", "1"): (MIL, None),
        ("U1", "2"): (4 * MIL, -MIL),
        ("R1", "1"): (2 * MIL, -MIL),
    }
    assert not any(value.mask.scoped or value.paste.scoped for value in by_name.values())


def test_level_three_takes_the_record_that_governs_the_pad() -> None:
    """``api.equivalence.mask_of`` gives a pad that follows the rules the expansion of the kept record that
    governs it, as the conversion chooses it; a record it cannot judge before that one makes no statement."""
    from fenolite.api.equivalence import mask_of
    from fenolite.backends.altium.adapter.rules import KEPT_RULE, kept_text
    from fenolite.checks.equivalence import norm
    from fenolite.model.base import ExtBag
    from fenolite.model.board import Board, FootprintInstance
    from fenolite.model.circuit import Circuit, Component, Net
    from fenolite.model.design import Design, DesignHeader

    def kept(*records: dict[str, str]) -> Board:
        texts = tuple((KEPT_RULE, kept_text(1, list(record.items()))) for record in records)
        pads = (
            _pad(),
            Pad(
                id="pad-2",
                number="2",
                shape="rect",
                size=Size(MIL, MIL),
                position=Point(0, 0),
                net_id="n-gnd",
            ),
        )
        footprint = FootprintInstance(
            id="fp-1", component_id="c-1", lib_ref="Parts:U", position=Point(0, 0), pads=pads
        )
        return Board(id="board", footprints=(footprint,), ext={"altium": ExtBag("altium", texts)})

    header = DesignHeader(id="dsn_m", name="m", schema_version="0", fenolite_version="0")
    circuit = Circuit(components=(Component(id="c-1", ref="U1"),), nets=(Net(id="n-gnd", name="GND"),))
    board = kept(_mask("InNet('GND')", 1, "1mil"), _mask("All", 2, "4mil"))
    first, ground = board.footprints[0].pads
    governs = mask_of(Design(header, circuit=circuit, board=board))
    assert (governs(first), governs(ground)) == (4 * MIL, MIL)
    unread = mask_of(
        Design(header, circuit=circuit, board=kept(_mask("Foo(", 1, "1mil"), _mask("All", 2, "4mil")))
    )
    assert unread(first) is None
    assert mask_of(Design(header, circuit=circuit, board=kept()))(first) == norm.MASK_RULES
