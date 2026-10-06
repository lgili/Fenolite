# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``parity`` stage of a document check (capability altium-verification, "Parity on Altium projects";
change c0088; ``H-A-DRC-PARITY``). No backend is imported: the validator is the fake of ``fakes.py`` with
``parity_side`` added, which builds the side from the schematic reading as a document backend does. Each of
the six planted edits of c0072 gives the finding of its kind."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

import pytest
from fakes import PCB, SCH, FakeDocumentValidator, document_set, reading

from fenolite.backends.base import DocumentParity, SchematicSide, SideComponent, SideOutcome
from fenolite.checks import parity
from fenolite.checks.documents import DOCUMENT_STAGES, run_document_checks
from fenolite.checks.stages import CheckReport, StageResult
from fenolite.core.coords import Point, Size
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level
from fenolite.model.board import Board, FootprintInstance, Pad
from fenolite.model.circuit import Circuit, Component, Net, Pin, PinRef
from fenolite.model.design import Design

SIDE_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-FAKE-SIDE",))
NETS = {"R1": ("VIN", "LED_A"), "D1": ("LED_A", "GND"), "U1": ("VIN", "GND")}


def circuit(prefix: str, nets: dict[str, tuple[str, ...]], value: str = "10k") -> Circuit:
    parts = [
        Component(
            id=f"cmp_{prefix}_{ref}",
            ref=ref,
            value=value,
            lib_footprint_ref="Lib:FP",
            pins=tuple(Pin(id=f"pin_{prefix}_{ref}_{n}", number=str(n)) for n in range(1, len(names) + 1)),
        )
        for ref, names in nets.items()
    ]
    members: dict[str, list[PinRef]] = {}
    for ref, names in nets.items():
        for number, name in enumerate(names, start=1):
            if name:
                members.setdefault(name, []).append(PinRef(f"cmp_{prefix}_{ref}", str(number)))
    listed = tuple(Net(id=f"net_{prefix}_{name}", name=name, members=tuple(m)) for name, m in members.items())
    return Circuit(components=tuple(parts), nets=listed)


def schematic(nets: dict[str, tuple[str, ...]] = NETS, value: str = "10k") -> Design:
    return dataclasses.replace(Design.new("sch", seed=1), circuit=circuit("s", nets, value))


def pcb(nets: dict[str, tuple[str, ...]] = NETS, *, lib_ref: str = "Lib:FP", twice: str = "") -> Design:
    held = circuit("p", nets)
    ids = {net.name: net.id for net in held.nets}

    def footprint(ref: str, names: tuple[str, ...], copy: str = "") -> FootprintInstance:
        return FootprintInstance(
            id=f"fp_{ref}{copy}",
            component_id=f"cmp_p_{ref}",
            lib_ref=lib_ref,
            position=Point(0, 0),
            pads=tuple(
                Pad(
                    id=f"pad_{ref}{copy}_{n}",
                    number=str(n),
                    shape="rect",
                    size=Size(1, 1),
                    position=Point(0, 0),
                    layers=("F.Cu",),
                    net_id=ids.get(name),
                )
                for n, name in enumerate(names, start=1)
            ),
        )

    footprints = [footprint(ref, names) for ref, names in nets.items()]
    if twice:
        footprints.append(footprint(twice, nets[twice], "_b"))
    board = Board(id="brd_1", footprints=tuple(footprints))
    return dataclasses.replace(Design.new("pcb", seed=2), circuit=held, board=board)


@dataclass
class ParityFake(FakeDocumentValidator):
    """The fake document validator as a ``DocumentParity``: the side is the schematic reading itself."""

    asked: list[tuple[Design, Design]] = field(default_factory=lambda: [])
    no_side: bool = False

    def parity_side(self, schematic: Design, board: Design) -> SideOutcome:
        self.asked.append((schematic, board))
        if self.no_side:
            return SideOutcome(None, message="no component")
        refs = {component.id: component.ref for component in schematic.circuit.components}
        components = {
            c.ref: SideComponent(c.value, c.lib_footprint_ref, frozenset(pin.number for pin in c.pins))
            for c in schematic.circuit.components
        }
        nodes = {
            (refs[m.component_id], m.pin): net.name for net in schematic.circuit.nets for m in net.members
        }
        return SideOutcome(SchematicSide(components, nodes), SIDE_EVIDENCE)


def check(sch: Design, board: Design, fake: FakeDocumentValidator | None = None) -> CheckReport:
    validator = fake or ParityFake()
    validator.schematic, validator.pcb = reading(sch), reading(board)
    return run_document_checks(
        documents=validator.documents_result, stages=("parity",), model=None, built=False, validator=validator
    )


def stage_of(report: CheckReport) -> StageResult:
    (stage,) = report.stages
    return stage


def found(stage: StageResult) -> list[tuple[str, str, str]]:
    return [(issue.code, issue.severity, issue.where) for issue in stage.issues]


def test_the_fake_is_a_document_parity() -> None:
    assert isinstance(ParityFake(), DocumentParity) and not isinstance(
        FakeDocumentValidator(), DocumentParity
    )
    assert DOCUMENT_STAGES.index("parity") == DOCUMENT_STAGES.index("copper.clearance") + 1


def test_agreeing_project() -> None:
    fake = ParityFake(added={"parity": Evidence(Level.INFERRED, hypotheses=("H-FAKE-ADDED",))})
    stage = stage_of(check(schematic(), pcb(), fake))
    assert stage.status == "ok" and stage.issues == ()
    assert stage.summary["netlist"] == "own" and stage.summary["compared"] is False
    assert stage.summary["differences"] == 0
    counts = {key: stage.summary[key] for key in parity.SUMMARY_KEYS}
    assert not any(counts.values())
    assert len(fake.asked) == 1
    names = stage.evidence.hypotheses
    assert stage.evidence.level is Level.INFERRED
    assert {"H-FAKE-SIDE", "H-FAKE-ADDED", "H-K-PARITY-OWN"} <= set(names)


RENAMED = {("R99" if ref == "R1" else ref): names for ref, names in NETS.items()}
MORE = NETS | {"C1": ("VIN", "GND")}
OPEN = NETS | {"R1": ("VIN", "")}
ELSEWHERE = NETS | {"R1": ("VIN", "GND")}
THREE = NETS | {"U1": ("VIN", "GND", "LED_A")}

EDITS = [
    # (what was planted, schematic, board, the findings it must give)
    (
        "designator renamed on the board",
        schematic(),
        pcb(RENAMED),
        [(parity.EXTRA, "error", "R99"), (parity.MISSING, "error", "R1")],
    ),
    ("footprint removed", schematic(MORE), pcb(), [(parity.MISSING, "error", "C1")]),
    ("footprint added", schematic(), pcb(MORE), [(parity.EXTRA, "error", "C1")]),
    ("reference used twice", schematic(), pcb(twice="D1"), [(parity.DUPLICATE, "error", "D1")]),
    (
        "value changed",
        schematic(value="1k"),
        pcb(),
        [(parity.MISMATCH, "warning", ref) for ref in sorted(NETS)],
    ),
    ("pad on another net", schematic(), pcb(ELSEWHERE), [(parity.NET_CONFLICT, "error", "R1-2")]),
    ("pad on no net", schematic(), pcb(OPEN), [(parity.NET_CONFLICT, "error", "R1-2")]),
    ("pin without a pad", schematic(THREE), pcb(), [(parity.PIN_WITHOUT_PAD, "error", "U1-3")]),
]


@pytest.mark.parametrize(("what", "sch", "board", "expected"), EDITS, ids=[edit[0] for edit in EDITS])
def test_planted_edits(what: str, sch: Design, board: Design, expected: list[tuple[str, str, str]]) -> None:
    """Scenario "Renamed designator" and the other planted edits of c0072: each gives its code."""
    stage = stage_of(check(sch, board))
    assert found(stage) == expected, what
    assert stage.status == ("errors" if any(severity == "error" for _, severity, _ in expected) else "ok")
    for code in {code for code, _, _ in expected}:
        assert stage.summary[code] == sum(1 for other, _, _ in expected if other == code)
    assert all(issue.message for issue in stage.issues)


def test_another_footprint_is_a_warning() -> None:
    stage = stage_of(check(schematic(), pcb(lib_ref="Lib:Other")))
    assert stage.status == "ok" and {code for code, _, _ in found(stage)} == {parity.MISMATCH}
    assert stage.summary[parity.MISMATCH] == len(NETS)


def test_skips() -> None:
    """``no-schematic`` without a schematic document, ``single-source`` without a PCB document,
    ``read-refused`` when a side was refused, ``netlist-unavailable`` when the backend gives no side."""

    def reason(fake: FakeDocumentValidator, **readings: object) -> tuple[str, str]:
        for key, value in readings.items():
            setattr(fake, key, value)
        report = run_document_checks(
            documents=fake.documents_result, stages=("parity",), model=None, built=False, validator=fake
        )
        return stage_of(report).status, stage_of(report).reason

    both = {"schematic": reading(schematic()), "pcb": reading(pcb())}
    assert reason(ParityFake(documents_result=document_set(PCB)), **both) == ("skipped", "no-schematic")
    assert reason(ParityFake(documents_result=document_set(SCH)), **both) == ("skipped", "single-source")
    refused = ParityFake(errors={PCB.name: FormatError("cut", file=PCB.name)})
    assert reason(refused, schematic=reading(schematic())) == ("skipped", "read-refused")
    assert not refused.asked
    assert reason(FakeDocumentValidator(), **both) == ("skipped", "netlist-unavailable")
    assert reason(ParityFake(no_side=True), **both) == ("skipped", "netlist-unavailable")


def test_built_input_compares_the_two_documents() -> None:
    fake = ParityFake(schematic=reading(schematic()), pcb=reading(pcb(RENAMED)))
    report = run_document_checks(
        documents=fake.documents_result, stages=("parity",), model=schematic(), built=True, validator=fake
    )
    assert [code for code, _, _ in found(stage_of(report))] == [parity.EXTRA, parity.MISSING]
