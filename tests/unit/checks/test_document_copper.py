# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``copper.clearance`` stage of a document check (capability altium-verification, "Copper check on
Altium boards" and "Document stage order"; change c0088). No backend is imported: the validator is the
fake of ``fakes.py`` with the three methods of a rules source and a board frame added."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from fakes import PCB, SCH, FakeDocumentValidator, document_set, reading

from fenolite.backends.base import BoardPad, DesignRules, Document, PadCopper, PlacedExtent, ProjectSet
from fenolite.checks.documents import (
    DOCUMENT_STAGES,
    project_of,
    run_document_checks,
    unjudged_copper,
)
from fenolite.checks.stages import StageResult
from fenolite.core.coords import Point, Size
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.board import Board, FootprintInstance, Layer, Pad, Track, Zone, ZoneFill, ZoneSettings
from fenolite.model.circuit import Circuit, Component, Net
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet, Selector

MM = 1_000_000
RULES_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-FAKE-RULES",))
NETS = (Net(id="net_a", name="A"), Net(id="net_b", name="B"))
SQUARE = (Point(20 * MM, 0), Point(30 * MM, 0), Point(30 * MM, 10 * MM), Point(20 * MM, 10 * MM))


def track(ident: str, net: str, y: int, x0: int = 0, x1: int = 10 * MM) -> Track:
    return Track(id=ident, start=Point(x0, y), end=Point(x1, y), width=200_000, layer="F.Cu", net_id=net)


def zone(ident: str, *, filled: bool, clearance: int = 0, net: str = "net_a") -> Zone:
    fills = (ZoneFill("F.Cu", SQUARE),) if filled else ()
    return Zone(
        id=ident,
        outline=SQUARE,
        layers=("F.Cu",),
        net_id=net,
        fills=fills,
        filled=filled,
        settings=ZoneSettings(clearance=clearance),
    )


def board(*, tracks: tuple[Track, ...] = (), zones: tuple[Zone, ...] = (), rules: tuple[Rule, ...] = ()):
    pad = Pad(id="pad_1", number="1", shape="rect", size=Size(MM, MM), position=Point(0, 0), layers=("F.Cu",))
    footprint = FootprintInstance(
        id="fp_1", component_id="cmp_1", lib_ref="L:F", position=Point(50 * MM, 50 * MM), pads=(pad,)
    )
    made = Board(
        id="brd_1",
        layers=(
            Layer(id="lyr_f", name="F.Cu", kind="copper", ordinal=0),
            Layer(id="lyr_b", name="B.Cu", kind="copper", ordinal=31),
        ),
        footprints=(footprint,),
        tracks=tracks,
        zones=zones,
    )
    circuit = Circuit(components=(Component(id="cmp_1", ref="R1"),), nets=NETS)
    held = RuleSet(id="rst_1", rules=rules) if rules else None
    return dataclasses.replace(Design.new("pcb", seed=2), circuit=circuit, board=made, rules=held)


def clearance(value: int, selector: Selector | None = None) -> Rule:
    return Rule(
        id="rul_1", name="Clearance", kind="clearance", selector_a=selector or Selector("all"), min=value
    )


@dataclass
class RulesFake(FakeDocumentValidator):
    """The fake document validator as a ``DesignRulesSource`` and a ``BoardFrame`` as well."""

    rules: DesignRules | None = None
    asked: list[ProjectSet] = field(default_factory=lambda: [])

    def design_rules(
        self, design: Design, project: ProjectSet, *, issues: list[Issue] | None = None
    ) -> DesignRules:
        self.asked.append(project)
        return self.rules or DesignRules(design, evidence=RULES_EVIDENCE)

    def board_pads(self, design: Design, *, issues: list[Issue] | None = None) -> tuple[BoardPad, ...]:
        assert design.board is not None
        (footprint,) = design.board.footprints
        (pad,) = footprint.pads
        at = footprint.position
        return (
            BoardPad(
                footprint.id, "R1", "", pad.id, "1", "smd", at, 0, "top", ("F.Cu",), None, None,
                (PadCopper("F.Cu", (at,), MM),),
            ),
        )  # fmt: skip

    def placed_extents(
        self, design: Design, *, issues: list[Issue] | None = None
    ) -> tuple[PlacedExtent, ...]:
        return ()


def run(design: Design, fake: FakeDocumentValidator | None = None, **more: object) -> StageResult:
    validator = fake or RulesFake()
    validator.pcb = reading(design)
    values: dict[str, object] = {"model": None, "built": False} | more
    report = run_document_checks(
        documents=validator.documents_result,
        stages=("copper.clearance",),
        validator=validator,
        **values,  # type: ignore[arg-type]
    )
    (stage,) = report.stages
    return stage


def codes(stage: StageResult) -> list[str]:
    return [found.code for found in stage.issues]


def test_stage_order() -> None:
    """Scenario "Order"."""
    assert DOCUMENT_STAGES == (
        "model.validate",
        "erc.lite",
        "copper.clearance",
        "parity",
        "netlist.assignment_compare",
        "roundtrip.rta0",
        "roundtrip.rta1",
        "roundtrip.rta2",
    )


def test_a_short_between_two_nets() -> None:
    crossing = Track(
        id="trk_x",
        start=Point(5 * MM, -MM),
        end=Point(5 * MM, MM),
        width=200_000,
        layer="F.Cu",
        net_id="net_b",
    )
    fake = RulesFake()
    stage = run(board(tracks=(track("trk_a", "net_a", 0), crossing), rules=(clearance(200_000),)), fake)
    assert stage.status == "errors" and codes(stage) == ["copper.short"]
    assert "A" in stage.issues[0].message and "B" in stage.issues[0].message
    assert stage.summary["shorts"] == 1 and stage.summary["unpoured"] == 0
    assert stage.summary["zones_unjudged"] == 0
    # the rules were asked for once, with the documents as the project set and the board named
    (project,) = fake.asked
    assert project.board == PCB.name and sorted(project.files) == sorted([SCH.name, PCB.name])
    assert stage.evidence.level is Level.INFERRED and "H-FAKE-RULES" in stage.evidence.hypotheses


def test_clearance_comes_from_the_rules_of_the_source() -> None:
    near = (track("trk_a", "net_a", 0), track("trk_b", "net_b", 300_000))  # 0.1 mm between the edges
    assert codes(run(board(tracks=near, rules=(clearance(200_000),)))) == ["copper.clearance"]
    assert codes(run(board(tracks=near, rules=(clearance(100_000),)))) == []
    # without any clearance nothing is too close: pairs are judged for shorts only
    assert codes(run(board(tracks=near))) == []


def test_unpoured_zones_are_said() -> None:
    """Scenario "Unpoured polygons are said": one warning with the count, and ``UNVERIFIED``."""
    zones = (zone("zon_1", filled=False), zone("zon_2", filled=False))
    stage = run(board(zones=zones, rules=(clearance(200_000),)))
    assert stage.status == "ok" and codes(stage) == ["copper.item-unsupported"]
    (found,) = stage.issues
    assert found.severity == "warning" and found.message.startswith("2 unpoured zone(s)")
    assert stage.summary["unpoured"] == 2 and stage.evidence.level is Level.UNVERIFIED


def test_a_poured_zone_is_checked_as_a_fill() -> None:
    inside = Track(
        id="trk_in",
        start=Point(22 * MM, 5 * MM),
        end=Point(28 * MM, 5 * MM),
        width=200_000,
        layer="F.Cu",
        net_id="net_b",
    )
    stage = run(board(tracks=(inside,), zones=(zone("zon_1", filled=True),), rules=(clearance(200_000),)))
    assert codes(stage) == ["copper.short"] and stage.summary["items"]["fill"] == 1
    assert stage.summary["unpoured"] == 0 and stage.summary["zones_unjudged"] == 0


def test_a_zone_without_a_clearance_is_not_judged_against_a_default() -> None:
    """A filled zone whose clearance no rule gives is counted, never judged against an invented value: the
    track 0.3 mm from the fill is no finding, though the model's default zone clearance is 0.5 mm."""
    beside = Track(
        id="trk_out",
        start=Point(19_600_000, 0),
        end=Point(19_600_000, 10 * MM),
        width=200_000,
        layer="F.Cu",
        net_id="net_b",
    )
    design = board(tracks=(beside,), zones=(zone("zon_1", filled=True),))
    stage = run(design)
    assert codes(stage) == ["copper.rules-incomplete"]
    (unjudged,) = stage.issues
    assert unjudged.message.startswith("1 filled zone(s) judged for shorts only") and unjudged.where == "zone"
    assert stage.summary["zones_unjudged"] == 1 and stage.summary["clearance"] == 0
    assert stage.evidence.level is Level.UNVERIFIED
    # the same board with the model's default on the zone is what the stage must not report
    defaulted = board(tracks=(beside,), zones=(zone("zon_1", filled=True, clearance=500_000),))
    assert unjudged_copper(defaulted, None) == (0, 0)
    assert codes(run(defaulted)) == ["copper.clearance"]


def test_which_zones_count_as_unjudged() -> None:
    filled = zone("zon_1", filled=True)
    assert unjudged_copper(board(zones=(filled,)), None) == (0, 1)
    assert unjudged_copper(board(zones=(filled,), rules=(clearance(200_000),)), None) == (0, 0)
    other_net = clearance(200_000, Selector("net", value="B"))
    assert unjudged_copper(board(zones=(filled,), rules=(other_net,)), None) == (0, 1)
    own_net = clearance(200_000, Selector("net", value="A"))
    assert unjudged_copper(board(zones=(filled,), rules=(own_net,)), None) == (0, 0)
    floor = DesignRules(board(zones=(filled,)), min_clearance=100_000)
    assert unjudged_copper(floor.design, floor) == (0, 0)
    assert unjudged_copper(board(zones=(zone("zon_1", filled=False),)), None) == (1, 0)
    assert unjudged_copper(dataclasses.replace(board(), board=None), None) == (0, 0)


def test_what_the_source_left_out_is_reported() -> None:
    design = board(tracks=(track("trk_a", "net_a", 0),), rules=(clearance(200_000),))
    left = DesignRules(
        design,
        opaque_clearance_rules=2,
        left_out=(("plane", 1, "drawn in negative"),),
        evidence=RULES_EVIDENCE,
    )
    stage = run(design, RulesFake(rules=left))
    assert sorted(codes(stage)) == ["copper.item-unsupported", "copper.rules-incomplete"]
    plane = next(found for found in stage.issues if found.code == "copper.item-unsupported")
    assert plane.where == "plane" and plane.message.startswith("1 plane item(s) left out")
    assert stage.summary["rules"]["opaque_clearance_rules"] == 2
    assert stage.evidence.level is Level.UNVERIFIED
    assert stage.summary["clearance_cells"] == {"judged": 0, "unjudged": 0}


def test_cells_of_the_clearance_matrices_are_counted() -> None:
    """The cells that the rules hold and do not hold join the summary; a cell that no rule holds lowers
    nothing by itself (the record that keeps it unread is an opaque rule, which does)."""
    design = board(tracks=(track("trk_a", "net_a", 0),), rules=(clearance(200_000),))
    stage = run(design, RulesFake(rules=DesignRules(design, clearance_cells=(7, 1), evidence=RULES_EVIDENCE)))
    assert stage.summary["clearance_cells"] == {"judged": 7, "unjudged": 1}
    assert codes(stage) == [] and stage.evidence.level is not Level.UNVERIFIED


def test_without_a_rules_source_and_a_frame() -> None:
    """A document backend that gives neither: the pads are left out and the rules are the model's own."""
    stage = run(board(tracks=(track("trk_a", "net_a", 0),)), FakeDocumentValidator())
    assert sorted(codes(stage)) == ["copper.item-unsupported", "copper.rules-incomplete"]
    assert stage.summary["unsupported"] == {"pad": 1} and stage.evidence.level is Level.UNVERIFIED


def test_skips() -> None:
    """``single-source`` without a PCB document, ``read-refused`` when its reading was refused."""
    alone = FakeDocumentValidator(documents_result=document_set(SCH))
    report = run_document_checks(
        documents=alone.documents_result, stages=DOCUMENT_STAGES, model=None, built=False, validator=alone
    )
    stage = next(s for s in report.stages if s.name == "copper.clearance")
    assert (stage.status, stage.reason) == ("skipped", "single-source")
    assert project_of(alone.documents_result) is None
    library = Document("lib.fp", "fake_fplib", "footprint-library")
    assert project_of(document_set(library)) is None
    refused = RulesFake(errors={PCB.name: FormatError("cut", file=PCB.name)})
    report = run_document_checks(
        documents=refused.documents_result,
        stages=("copper.clearance",),
        model=None,
        built=False,
        validator=refused,
    )
    (stage,) = report.stages
    assert (stage.status, stage.reason) == ("skipped", "read-refused") and not refused.asked
    assert [found.code for found in report.issues] == ["check.read-refused"]


def test_built_input_judges_the_pcb_reading() -> None:
    """Built and native input alike: the board is the PCB document, not the cached model."""
    near = (track("trk_a", "net_a", 0), track("trk_b", "net_b", 300_000))
    design = board(tracks=near, rules=(clearance(200_000),))
    stage = run(design, model=board(), built=True)
    assert codes(stage) == ["copper.clearance"]
