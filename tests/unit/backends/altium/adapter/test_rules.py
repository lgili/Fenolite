# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rules of a PCB document through the mapper of c0042 (capability altium-import, "Rules where they map";
change c0043)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import _altium_records as rec
import pytest

from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.adapter.layers import LayerMap, copper_layers_of
from fenolite.backends.altium.adapter.rules import import_rules
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.rules import CopperLayer, map_rules
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


# --- More forms of a Clearance record (change c0125) ---------------------------------------------------

OUTER = "(ExistsOnLayer('Top Layer') Or ExistsOnLayer('Bottom Layer'))"
NAMES = {"LAYER1NAME": "Top Layer", "LAYER32NAME": "Bottom Layer"}
CELL = {"SOURCERULE": "2", "CELLROWNAME": "All", "CELLROWTYPE": "0", "CELLCOLNAME": "All", "CELLCOLTYPE": "0"}


def matrix_records() -> list[object]:
    """The three Clearance records of a clearance matrix with one value for the inner layers, one for the
    outer layers and one for everything else."""
    common = {"IGNOREPADTOPADCLEARANCEINFOOTPRINT": "FALSE", "OBJECTCLEARANCES": " "}
    return [
        rec.rule(
            "Clearance", "Clearance_1", GAP="5mil", GENERICCLEARANCE="5mil", **common, **CELL,
            INNERLAYERS="TRUE", SCOPE1EXPRESSION="OnMid", SCOPE2EXPRESSION="OnMid",
        ),
        rec.rule(
            "Clearance", "Clearance_2", GAP="5mil", GENERICCLEARANCE="5mil", **common, **CELL,
            OUTERLAYERS="TRUE", SCOPE1EXPRESSION=OUTER, SCOPE2EXPRESSION=OUTER, PRIORITY="2",
        ),
        rec.rule(
            "Clearance", "Clearance", GAP="10mil", GENERICCLEARANCE="10mil", **common, ISMATRIX="TRUE",
            PRIORITY="3",
        ),
    ]  # fmt: skip


def test_layer_conditions_take_the_layers_of_the_board() -> None:
    """Scenario "A clearance matrix on a two-layer board" through the import: the rule of the outer
    layers holds the neutral names of the board's two copper layers."""
    issues: list[Issue] = []
    board = rec.board(extra=NAMES)
    document = rec.document(board, rules=matrix_records())  # type: ignore[arg-type]
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA, issues=issues)
    assert design.rules is not None and design.board is not None
    assert [(r.name, r.min, r.priority, r.layers) for r in design.rules.rules] == [
        ("Clearance_2", 127_000, 2, ("F.Cu", "B.Cu")),
        ("Clearance", 254_000, 3, ()),
    ]
    assert dict(design.rules.rules[0].ext["altium"].payload)["scope1"] == OUTER
    assert [i.message for i in issues if i.code == "altium.import.rule-unmapped"] == [
        "1 rule(s) of kind Clearance are not mapped (no-layer 1)"
    ]
    layers = LayerMap.from_board(board).copper_layers()
    assert layers.layers == (CopperLayer("Top Layer", "F.Cu"), CopperLayer("Bottom Layer", "B.Cu"))
    assert copper_layers_of(design.board.layers) == layers


def test_layer_conditions_on_four_layers_stay_unmapped() -> None:
    """Scenario "Some of the copper layers" through the import: mid layer 1 is an internal signal layer
    and plane 1 is not; neither layer condition maps."""
    issues: list[Issue] = []
    board = rec.board((1, 2, 39, 32), extra=NAMES)
    document = rec.document(board, rules=matrix_records())  # type: ignore[arg-type]
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA, issues=issues)
    assert design.rules is not None and design.board is not None
    assert [r.name for r in design.rules.rules] == ["Clearance"]
    assert [i.message for i in issues if i.code == "altium.import.rule-unmapped"] == [
        "2 rule(s) of kind Clearance are not mapped (scope 2)"
    ]
    layers = copper_layers_of(design.board.layers)
    assert layers == LayerMap.from_board(board).copper_layers()
    assert layers is not None
    assert [(layer.name, layer.inner_signal) for layer in layers.layers] == [
        ("F.Cu", False),
        ("In1.Cu", True),
        ("In2.Cu", False),
        ("B.Cu", False),
    ]


def test_layers_of_a_board_that_is_no_import() -> None:
    from fenolite.model.board import Layer

    assert copper_layers_of([Layer(id="lay_1", name="F.Cu", kind="copper", ordinal=0)]) is None
    assert copper_layers_of([]) is not None


@pytest.mark.parametrize(("chain", "opaque"), [((1, 32), 0), ((1, 2, 39, 32), 2)])
def test_the_copper_check_counts_what_stays_unread(
    chain: tuple[int, ...], opaque: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rules source of the copper check maps the records with the board's layers, as the import does:
    a record that applies to nothing is no unread rule, a layer condition that stays unmapped is one."""
    from fenolite.backends.altium.read import pcb

    document = rec.document(rec.board(chain, extra=NAMES), rules=matrix_records())  # type: ignore[arg-type]
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA)
    monkeypatch.setattr(pcb, "read_rule_fields", lambda data, file: [r.fields for r in document.rules])
    rules = AltiumBackend().rules_from_bytes(design, b"document", file="a.PcbDoc")
    assert rules.opaque_clearance_rules == opaque and rules.unread == ()
    held = [r.name for r in (rules.design.rules.rules if rules.design.rules else ())]
    assert held == (["Clearance_2", "Clearance"] if not opaque else ["Clearance"])


# --- Cells of an object matrix (change c0130) ----------------------------------------------------------


def test_cell_rules_of_an_import_and_the_clearance_in_force() -> None:
    """Scenario "Cell rules in the import": the cell rule has an id and a bag of its own and governs its
    pair of item kinds above the generic rule of the same record."""
    from fenolite.checks.clearance import ClearanceResolver

    matrix = "ClearanceObj_Via-ClearanceObj_Via:35000;ClearanceObj_Track-ClearanceObj_Text:100000"
    record = rec.rule(
        "Clearance", "Clearance", GAP="4mil", GENERICCLEARANCE="4mil", OBJECTCLEARANCES=matrix,
        IGNOREPADTOPADCLEARANCEINFOOTPRINT="FALSE",
    )  # fmt: skip
    document = rec.document(nets=("A", "B"), rules=[record])
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA)
    assert design.rules is not None
    generic, cell = design.rules.rules
    assert generic.id != cell.id and generic.native_ids != cell.native_ids
    assert cell.native_ids == {"altium": "rule:Clearance:Clearance:clearance:via-via"}
    assert dict(cell.ext["altium"].payload)["cell"] == "via-via"
    assert dict(generic.ext["altium"].payload)["cells_not_lifted"] == (
        "ClearanceObj_Track-ClearanceObj_Text:100000"
    )
    assert "record" not in dict(cell.ext["altium"].payload)
    resolver = ClearanceResolver(design)
    first, second = (net.id for net in design.circuit.nets[:2])

    def between(one: str, other: str) -> tuple[int | None, str]:
        found = resolver.resolve(
            resolver.subject(one, first, ref=None, layer="F.Cu"),  # type: ignore[arg-type]
            resolver.subject(other, second, ref=None, layer="F.Cu"),  # type: ignore[arg-type]
        )
        return found.value, found.source

    assert between("via", "via") == (88_900, "rule:Clearance/via-via")
    assert between("via", "track") == (101_600, "rule:Clearance")
    assert between("arc", "pad") == (101_600, "rule:Clearance")


def test_the_copper_check_counts_the_cells(monkeypatch: pytest.MonkeyPatch) -> None:
    from fenolite.backends.altium.read import pcb

    lifted = rec.rule(
        "Clearance", "Clearance", GAP="4mil", GENERICCLEARANCE="4mil", PRIORITY="2",
        OBJECTCLEARANCES="ClearanceObj_Via-ClearanceObj_Via:35000;ClearanceObj_Via-ClearanceObj_Hole:0",
    )  # fmt: skip
    mixed = rec.rule(
        "Clearance", "Pads", GAP="4mil", GENERICCLEARANCE="4mil",
        OBJECTCLEARANCES="ClearanceObj_Track-ClearanceObj_THPad:157480",
    )  # fmt: skip
    document = rec.document(rules=[mixed, lifted])
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA)
    monkeypatch.setattr(pcb, "read_rule_fields", lambda data, file: [r.fields for r in document.rules])
    rules = AltiumBackend().rules_from_bytes(design, b"document", file="a.PcbDoc")
    assert rules.clearance_cells == (1, 2) and rules.opaque_clearance_rules == 1
    assert [r.name for r in (rules.design.rules.rules if rules.design.rules else ())] == [
        "Clearance",
        "Clearance/via-via",
    ]


# --- The slack of the unit (change c0131) and Altium's observed tolerance (change c0152) ----------------


def _two_tracks(inside_units: int):  # noqa: ANN202
    """A document with a Clearance rule of 10 mil and two parallel tracks of two nets, 10 mil wide, whose
    edges are 10 mil apart less ``inside_units`` units of the file."""
    centre = 200_000 - inside_units
    rule = rec.rule("Clearance", "Clearance", GAP="10mil", GENERICCLEARANCE="10mil", OBJECTCLEARANCES="")
    tracks = [
        rec.track((0, 0), (10_000_000, 0), 100_000, net=0),
        rec.track((0, centre), (10_000_000, centre), 100_000, net=1),
    ]
    return rec.document(nets=("A", "B"), rules=[rule], tracks=tracks)


def test_the_slack_is_derived() -> None:
    """The constants of the slack are arithmetic on the unit and on the observed tolerance, never chosen."""
    from fractions import Fraction

    from fenolite.backends.altium.backend import (
        ALTIUM_PASSED_NM,
        ALTIUM_PASSED_UNITS,
        CLEARANCE_SLACK_NM,
        FILE_UNIT_NM,
        PAIR_SLACK_NM,
        UNIT_SLACK_NM,
    )

    assert PAIR_SLACK_NM == 2 * FILE_UNIT_NM and UNIT_SLACK_NM == 5
    assert ALTIUM_PASSED_UNITS == Fraction(7, 2) and ALTIUM_PASSED_NM == Fraction(889, 100)
    assert CLEARANCE_SLACK_NM == 9
    # 9 is the least whole value that passes a model gap 8.89 nm short once that gap is rounded down
    assert CLEARANCE_SLACK_NM - 1 < ALTIUM_PASSED_NM <= CLEARANCE_SLACK_NM


@pytest.mark.parametrize(
    ("inside_units", "gap", "found"),
    [(0, 254_000, 0), (2, 253_995, 0), (3, 253_992, 0), (4, 253_990, 1)],
)
def test_the_slack_on_records(
    inside_units: int, gap: int, found: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario "At the bound, on records": copper up to 3.5 file units inside its clearance is no
    finding, and copper four units inside is one. The two tracks' grid is the unit, so no record of them
    holds a gap between the last two."""
    from fenolite.backends.altium.backend import CLEARANCE_SLACK_NM
    from fenolite.backends.altium.read import pcb
    from fenolite.checks.copper import check_copper

    document = _two_tracks(inside_units)
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA)
    assert design.board is not None
    first, second = design.board.tracks
    assert abs(second.start.y - first.start.y) - first.width == gap
    monkeypatch.setattr(pcb, "read_rule_fields", lambda data, file: [r.fields for r in document.rules])
    rules = AltiumBackend().rules_from_bytes(design, b"document", file="a.PcbDoc")
    report = check_copper(rules.design, pads=())
    assert [f.code for f in report.findings] == ["copper.clearance"] * found
    if found:
        assert (report.findings[0].gap, report.findings[0].clearance) == (gap, 254_000 - CLEARANCE_SLACK_NM)


PAD_UNITS = 637_795
"""An odd size of a square pad, so that its edge lies on a half unit (authored for Fenolite)."""


@pytest.mark.parametrize(("half_units_inside", "found"), [(7, 0), (9, 1)])
def test_a_pad_and_a_track_at_the_observed_tolerance(
    half_units_inside: int, found: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario "At Altium's observed tolerance": a rectangular pad of an odd size and a track of another
    net under a Clearance of 5 mil. With the track's edge 3.5 units inside the clearance (the pair kind and
    the shortfall that Altium passes, S-0616) there is no finding; one unit nearer, 4.5 units inside, there
    is one."""
    from fractions import Fraction

    from fenolite.backends.altium.backend import ALTIUM_PASSED_UNITS, CLEARANCE_SLACK_NM
    from fenolite.backends.altium.read import pcb
    from fenolite.checks.copper import check_copper

    rule = rec.rule("Clearance", "Clearance", GAP="5mil", GENERICCLEARANCE="5mil", OBJECTCLEARANCES="")
    edge = Fraction(PAD_UNITS, 2)
    centre = edge + 50_000 - Fraction(half_units_inside, 2) + 25_000
    assert centre.denominator == 1
    x = int(centre)
    pad = rec.pad("1", (0, 0), size=(PAD_UNITS, PAD_UNITS), shape=2, layer=1, net=0)
    track = rec.track((x, -400_000), (x, 400_000), 50_000, layer=1, net=1)
    document = rec.document(nets=("A", "B"), rules=[rule], pads=[pad], tracks=[track])
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA)
    monkeypatch.setattr(pcb, "read_rule_fields", lambda data, file: [r.fields for r in document.rules])
    backend = AltiumBackend()
    rules = backend.rules_from_bytes(design, b"document", file="a.PcbDoc")
    report = check_copper(rules.design, pads=backend.board_pads(rules.design))
    assert [f.code for f in report.findings] == ["copper.clearance"] * found
    shortfall = Fraction(half_units_inside, 2)
    assert (shortfall <= ALTIUM_PASSED_UNITS) == (not found)
    if found:
        (finding,) = report.findings
        assert sorted(item.kind for item in finding.items) == ["pad", "track"]
        assert finding.clearance == 127_000 - CLEARANCE_SLACK_NM
        assert finding.gap == 126_988  # 49 995.5 units, 126 988.57 nm, read in whole nanometres


@pytest.mark.parametrize(("moved", "gap", "found"), [(1, 253_991, 0), (2, 253_990, 1)])
def test_one_nanometre_inside_the_bound(
    moved: int, gap: int, found: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario "One nanometre inside the bound": the model of the document with one track moved by one or
    two nanometres, which no file can hold. 9 nm below the rule's value is no finding, 10 nm is one."""
    import dataclasses

    from fenolite.backends.altium.read import pcb
    from fenolite.checks.copper import check_copper
    from fenolite.core.coords import Point

    document = _two_tracks(3)
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA)
    assert design.board is not None
    first, second = design.board.tracks
    sign = 1 if first.start.y > second.start.y else -1
    nearer = dataclasses.replace(
        second,
        start=Point(second.start.x, second.start.y + sign * moved),
        end=Point(second.end.x, second.end.y + sign * moved),
    )
    assert abs(nearer.start.y - first.start.y) - first.width == gap
    board = dataclasses.replace(design.board, tracks=(first, nearer))
    monkeypatch.setattr(pcb, "read_rule_fields", lambda data, file: [r.fields for r in document.rules])
    rules = AltiumBackend().rules_from_bytes(
        dataclasses.replace(design, board=board), b"document", file="a.PcbDoc"
    )
    report = check_copper(rules.design, pads=())
    assert [(f.code, f.gap) for f in report.findings] == [("copper.clearance", gap)] * found
