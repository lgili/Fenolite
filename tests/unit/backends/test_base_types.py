# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Neutral result types of ``fenolite.backends.base`` (capability backend-protocol)."""

from __future__ import annotations

import ast
import dataclasses
import sys
import typing
from pathlib import Path

import pytest
from _boards import created_board

from fenolite.backends import base, registry
from fenolite.backends.base import (
    BoardFrame,
    BoardPad,
    ContainerRoundTrip,
    Document,
    DocumentSet,
    DocumentValidator,
    DrcItem,
    DrcOutcome,
    DrcReport,
    DrcViolation,
    FillOutcome,
    ModelScope,
    NetlistOracle,
    PadAssignment,
    PadCopper,
    PadNetList,
    PlacedExtent,
    ProjectRead,
    ProjectSet,
    RoundTrip,
    RoundTripOracle,
    Rt2Outcome,
    SkippedFile,
    Uncovered,
    WriteResult,
    ZoneFills,
)
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.pcb import write_board
from fenolite.core.coords import Point


def test_write_result_is_immutable() -> None:
    result = WriteResult(text="(kicad_pcb)\n")
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.text = ""  # type: ignore[misc]
    assert result.issues == ()


def test_capability_default_target_among_targets() -> None:
    for backend in registry.all_backends():
        report = backend.capabilities()
        if report.write_kinds:
            assert report.default_target in report.targets, backend.name


def test_capability_write_advertised_and_implemented() -> None:
    backend = KicadBackend()
    operations = backend.capabilities().operations
    assert {"write", "lower", "validate"} <= set(operations)
    design = created_board()
    assert backend.write(design) == write_board(design, target=10)
    assert callable(backend.lower) and callable(backend.validate)
    assert backend.write(design, target=9, allow_lossy=True) == write_board(design, target=9)


def violation(kind: str) -> DrcViolation:
    item = DrcItem(uuid="u", description="d", position=Point(1, 2))
    return DrcViolation(type=kind, description=kind, severity="error", items=(item,))


def test_violations_by_type() -> None:
    clearance, mismatch = violation("clearance"), violation("lib_footprint_mismatch")
    report = DrcReport(
        source="b", date="d", kicad_version="10.0.6", coordinate_units="mm",
        violations=(clearance, mismatch, clearance), unconnected_items=(violation("unconnected_items"),),
    )  # fmt: skip
    assert report.of_type("lib_footprint_mismatch") == (mismatch,)
    assert report.of_type("clearance") == (clearance, clearance) and report.of_type("other") == ()


def test_integer_positions_only() -> None:
    with pytest.raises(TypeError):
        DrcItem(uuid="u", description="d", position=Point(1.5, 0))  # type: ignore[arg-type]


def test_drc_types_are_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        violation("x").type = "y"  # type: ignore[misc]


def test_board_outside_the_files() -> None:
    with pytest.raises(ValueError, match="a.kicad_pcb"):
        ProjectSet(root=Path("p"), board="a.kicad_pcb", files={})


@pytest.mark.parametrize("name", ["/abs.kicad_pcb", "../up.kicad_pcb", "a\\b.kicad_pcb", "a//b", ""])
def test_project_names_are_relative_posix(name: str) -> None:
    with pytest.raises(ValueError, match="relative POSIX"):
        ProjectSet(root=Path("p"), board="b.kicad_pcb", files={"b.kicad_pcb": Path("b"), name: Path("x")})


def test_project_set_is_immutable() -> None:
    project = ProjectSet(root=Path("p"), board="b.kicad_pcb", files={"b.kicad_pcb": Path("p/b.kicad_pcb")},
                         skipped=(SkippedFile("x.pretty", "missing"),))  # fmt: skip
    with pytest.raises(dataclasses.FrozenInstanceError):
        project.board = "c.kicad_pcb"  # type: ignore[misc]
    assert project.has_project is False and project.has_rules is False


def test_inconsistent_round_trip_refused() -> None:
    with pytest.raises(ValueError, match="passed"):
        RoundTrip(
            level="RT1", passed=True, tree_equal=False, model_equal=True, opaque_equal=True, opaque_count=0
        )
    with pytest.raises(ValueError):
        RoundTrip(
            level="RT1", passed=False, tree_equal=True, model_equal=True, opaque_equal=True, opaque_count=0
        )
    ok = RoundTrip(
        level="RT1", passed=True, tree_equal=True, model_equal=True, opaque_equal=True, opaque_count=3
    )
    assert ok.difference == ""


def test_outcome_is_immutable() -> None:
    outcome = DrcOutcome(report=None, tool_version="10.0.6", canary="not-applicable")
    with pytest.raises(dataclasses.FrozenInstanceError):
        outcome.canary = "fired"  # type: ignore[misc]
    assert outcome.outcome == "exit" and outcome.returncode == 0 and outcome.tool_writes == ()


def test_fill_outcome_is_immutable() -> None:
    zones = (ZoneFills("zon_1", (), False),)
    outcome = FillOutcome(zones, "10.0.6")
    with pytest.raises(dataclasses.FrozenInstanceError):
        outcome.zones = None  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        zones[0].filled = True  # type: ignore[misc]
    assert outcome.supported and outcome.outcome == "exit" and outcome.returncode == 0


def test_base_imports_no_backend() -> None:
    tree = ast.parse(Path(base.__file__).read_text(encoding="utf-8"))
    names = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    names |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not {n for n in names if n.startswith("fenolite.backends.")}


def _fakes():  # type: ignore[no-untyped-def]
    folder = str(Path(__file__).resolve().parents[1] / "checks")
    if folder not in sys.path:
        sys.path.insert(0, folder)
    import fakes

    return fakes


def test_element_assigned_and_uncovered() -> None:
    with pytest.raises(ValueError, match="R1-1"):
        PadNetList(
            source="export",
            assignments=(PadAssignment("R1-1", "VIN"),),
            uncovered=(Uncovered("R1-1", "not-exported"),),
        )


def test_oracle_protocols() -> None:
    fakes = _fakes()
    drc_only, full = fakes.FakeOracle(), fakes.FakeFullOracle()
    assert not isinstance(drc_only, NetlistOracle) and not isinstance(drc_only, RoundTripOracle)
    assert isinstance(full, NetlistOracle) and isinstance(full, RoundTripOracle)


def test_new_outcomes_are_immutable() -> None:
    outcome = Rt2Outcome(before=(), after=None, normalised=False, tool_version="9.0.9")
    with pytest.raises(dataclasses.FrozenInstanceError):
        outcome.normalised = True  # type: ignore[misc]
    listed = PadNetList("board", (PadAssignment("R1-1", ""),))
    with pytest.raises(dataclasses.FrozenInstanceError):
        listed.source = "model"  # type: ignore[misc]


# -- board-frame records (backend-protocol, "Board-frame protocol"; change c0028)


def test_board_frame_protocol() -> None:
    backend = KicadBackend()
    assert isinstance(backend, BoardFrame)
    operations = backend.capabilities().operations
    assert "board_pads" not in operations and "placed_extents" not in operations
    assert not isinstance(object(), BoardFrame)


def _names(annotation: object) -> set[str]:
    """The modules of every type an annotation names."""
    found = {getattr(annotation, "__module__", "builtins")}
    for arg in typing.get_args(annotation):
        found |= _names(arg) if not isinstance(arg, (str, type(None), type(...))) else set()
    return found


def test_frame_records_are_plain_data() -> None:
    for record in (PadCopper, BoardPad, PlacedExtent):
        assert dataclasses.is_dataclass(record) and record.__dataclass_params__.frozen  # type: ignore[attr-defined]
        assert hasattr(record, "__slots__")
        for annotation in typing.get_type_hints(record).values():
            modules = _names(annotation)
            assert all(
                m in ("builtins", "typing", "types", base.__name__)  # a record may hold a sibling record
                or m.startswith(("fenolite.core", "fenolite.model"))
                for m in modules
            ), modules
    for core, width, filled in (((), 0, False), ((Point(0, 0),), -1, False), ((Point(0, 0),), 0, False)):
        with pytest.raises(ValueError):
            PadCopper("F.Cu", core, width, filled)
    with pytest.raises(ValueError):
        PadCopper("F.Cu", (Point(0, 0), Point(1, 0)), 0, filled=True)
    entry = PadCopper("F.Cu", (Point(0, 0),), 2)
    assert (entry.filled, entry.exact) == (False, True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.width = 4  # type: ignore[misc]
    assert PadCopper("F.Cu", (Point(0, 0), Point(1, 0)), 0).width == 0  # a hairline polyline is allowed


def test_own_face_by_side() -> None:
    ring = (Point(0, 0), Point(10, 0), Point(10, 10))
    bottom = PlacedExtent("fp_x", "bottom", front=(), back=(ring,))
    assert bottom.own == bottom.back == (ring,)
    top = PlacedExtent("fp_x", "top", front=(ring,))
    assert top.own == (ring,) and top.source == "none" and top.exact


def test_rules_source_protocol() -> None:
    """Scenario "KiCad backend is a rules source" (capability backend-protocol, "Design rules source";
    change c0029): the backend satisfies the protocol, and ``design_rules`` is not an operation."""
    from fenolite.backends.kicad.backend import KicadBackend

    backend = KicadBackend()
    assert isinstance(backend, base.DesignRulesSource)
    assert "design_rules" not in backend.capabilities().operations
    assert not isinstance(object(), base.DesignRulesSource)


def test_rules_source_record_defaults() -> None:
    from fenolite.model.design import Design

    design = Design.new("rules", seed=0)
    rules = base.DesignRules(design)
    assert rules.design is design and rules.min_clearance is None
    assert (rules.rules_over_classes, rules.floor_over_rules) == (True, False)
    assert rules.opaque_clearance_rules == 0 and rules.unread == ()
    assert rules.evidence == base.Evidence()
    with pytest.raises(dataclasses.FrozenInstanceError):
        rules.min_clearance = 1  # type: ignore[misc]


def test_container_verdict_consistency() -> None:
    """Scenarios "Verdict consistency enforced" and "Unjudged verdict needs a reason" (change c0044)."""
    lost = {"streams": 3, "different": ("Nets6/Data",), "difference": "Nets6/Data"}
    with pytest.raises(ValueError, match="passed"):
        ContainerRoundTrip(level="RT-A0", judged=True, passed=True, **lost)  # type: ignore[arg-type]
    verdict = ContainerRoundTrip(level="RT-A0", judged=True, passed=False, **lost)  # type: ignore[arg-type]
    assert verdict.difference == "Nets6/Data" and not verdict.reason
    with pytest.raises(ValueError, match="reason"):
        ContainerRoundTrip(level="RT-A0", judged=False, passed=False)
    assert ContainerRoundTrip(level="RT-A0", judged=False, passed=False, reason="too-large").judged is False
    with pytest.raises(ValueError, match="reason"):
        ContainerRoundTrip(level="RT-A1", judged=True, passed=True, reason="too-large")
    with pytest.raises(ValueError, match="difference"):
        ContainerRoundTrip(level="RT-A1", judged=True, passed=False, different=("FileHeader",))
    with pytest.raises(dataclasses.FrozenInstanceError):
        verdict.passed = True  # type: ignore[misc]


def test_document_names_are_relative() -> None:
    def one(name: str, **more: typing.Any) -> DocumentSet:
        documents = (Document(name, "altium_pcbdoc", "pcb"),)
        return DocumentSet(root=Path("."), project=None, board=None, documents=documents, **more)

    for bad in ("../x.PcbDoc", "/abs/x.PcbDoc", "sub\\x.PcbDoc", ""):
        with pytest.raises(ValueError, match="relative POSIX name"):
            one(bad)
    with pytest.raises(ValueError, match="../y.SchDoc"):
        one("x.PcbDoc", missing=("../y.SchDoc",))
    twice = (Document("x.PcbDoc", "altium_pcbdoc", "pcb"),) * 2
    with pytest.raises(ValueError, match="repeated: x.PcbDoc"):
        DocumentSet(Path("."), None, None, twice)
    with pytest.raises(ValueError, match="the board 'y.PcbDoc'"):
        DocumentSet(Path("."), None, "y.PcbDoc", twice[:1])
    with pytest.raises(ValueError, match="the project 'y.PrjPcb'"):
        DocumentSet(Path("."), "y.PrjPcb", None, twice[:1])
    with pytest.raises(ValueError, match="sorted"):
        DocumentSet(Path("."), None, None, (Document("b", "k", "other"), Document("a", "k", "other")))
    found = DocumentSet(Path("."), None, "sub/x.PcbDoc", (Document("sub/x.PcbDoc", "altium_pcbdoc", "pcb"),))
    assert found.named("sub/x.PcbDoc").role == "pcb" and found.of_role("schematic") == ()
    assert found.missing == ()
    with pytest.raises(dataclasses.FrozenInstanceError):
        found.board = None  # type: ignore[misc]


def test_model_scope_and_project_read() -> None:
    assert ModelScope({"component": ("ref",)}).length_tolerance == 0
    for bad in (-1, 1.0, True):
        with pytest.raises(ValueError, match="length_tolerance"):
            ModelScope({}, length_tolerance=bad)  # type: ignore[arg-type]
    read = ProjectRead(None, None)
    assert read.errors == {} and read.schematic is None and read.pcb is None
    for cls in (Document, DocumentSet, ProjectRead, ContainerRoundTrip, ModelScope):
        assert cls.__dataclass_params__.frozen  # type: ignore[attr-defined]


def test_document_validator_narrows_a_backend() -> None:
    """Scenario "Narrowing a backend": a backend that only reads is not a ``DocumentValidator``."""
    fakes = _fakes()
    assert not isinstance(fakes.FakeReader(), DocumentValidator)
    assert isinstance(fakes.FakeDocumentValidator(), DocumentValidator)
    assert not isinstance(KicadBackend(), DocumentValidator)
    assert not isinstance(fakes.FakeValidator(), DocumentValidator)
