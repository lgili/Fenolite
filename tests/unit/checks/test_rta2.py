# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``roundtrip.rta2`` stage (capability verification-loop, "Document check pipeline"; change c0044):
the built model against the two readings of the documents a build wrote, on authored models."""

from __future__ import annotations

import dataclasses

from fakes import FakeDocumentValidator, reading

from fenolite.backends.base import ModelScope, ProjectRead
from fenolite.checks.documents import run_document_checks
from fenolite.checks.rta2 import BOARD_KINDS, CIRCUIT_KINDS, MAX_ISSUES, held, rta2_stage
from fenolite.core.coords import Point, Size
from fenolite.core.evidence import Evidence, Level
from fenolite.model.board import Board, FootprintInstance, Pad, Track
from fenolite.model.circuit import Circuit, Component, Net, NetClass, PinRef
from fenolite.model.design import Design

SCOPE = ModelScope(
    {
        "component": ("ref", "value"),
        "net": ("name", "members"),
        "no_connect": (),
        "netclass": ("name",),
        "footprint": ("position", "side"),
        "pad": ("number", "net_id", "position"),
        "track": ("start", "end", "width", "layer", "net_id"),
    },
    length_tolerance=2,
)


def _circuit(prefix: str, value: str = "10k", classes: tuple[str, ...] = ("PWR",)) -> Circuit:
    parts = tuple(Component(id=f"cmp_{prefix}_{ref}", ref=ref, value=value) for ref in ("R1", "R2"))
    net = Net(id=f"net_{prefix}_1", name="VIN", members=(PinRef(parts[0].id, "1"), PinRef(parts[1].id, "1")))
    listed = tuple(NetClass(id=f"cls_{prefix}_{name}", name=name) for name in classes)
    return Circuit(components=parts, nets=(net,), netclasses=listed)


def _design(prefix: str, *, board: Board | None = None, **more: object) -> Design:
    circuit = _circuit(prefix, **more)  # type: ignore[arg-type]
    return dataclasses.replace(Design.new(prefix, seed=1), circuit=circuit, board=board)


def _board(prefix: str, *, shift: int = 0, tracks: int = 0) -> Board:
    footprints = tuple(
        FootprintInstance(
            id=f"fp_{prefix}_{ref}",
            component_id=f"cmp_{prefix}_{ref}",
            lib_ref="Lib:R",
            position=Point(1000 * n + shift, 0),
            pads=(
                Pad(
                    id=f"pad_{prefix}_{ref}",
                    number="1",
                    shape="rect",
                    size=Size(10, 10),
                    position=Point(0, 0),
                    net_id=f"net_{prefix}_1",
                ),
            ),
        )  # fmt: skip
        for n, ref in enumerate(("R1", "R2"))
    )
    copper = tuple(
        Track(id=f"trk_{prefix}_{n}", start=Point(0, n), end=Point(500, n), width=200, layer="F.Cu",
              net_id=f"net_{prefix}_1")
        for n in range(tracks)
    )  # fmt: skip
    return Board(id=f"brd_{prefix}", footprints=footprints, tracks=copper)


def test_difference_is_located() -> None:
    """Scenario "RT-A2 difference located"."""
    model = _design("m")
    read = ProjectRead(reading(_design("s", value="1k")), None)
    stage = rta2_stage(model, read, ModelScope({"component": ("value",)}))
    assert [(i.code, i.severity, i.where) for i in stage.issues] == [
        ("check.rta2-failed", "error", "schematic:/component/R1/value"),
        ("check.rta2-failed", "error", "schematic:/component/R2/value"),
    ]
    assert '"10k"' in stage.issues[0].message and '"1k"' in stage.issues[0].message
    assert stage.status == "errors" and stage.summary["holds"] is False
    assert stage.summary == {
        "level": "RT-A2",
        "holds": False,
        "differences": 2,
        "compared": {"schematic": ["component"]},
        "not_in_model": {},
    }


def test_circuit_kinds_go_to_the_schematic_and_the_rest_to_the_pcb() -> None:
    assert CIRCUIT_KINDS == ("component", "net", "no_connect")
    model = _design("m", board=_board("m", tracks=1))
    read = ProjectRead(
        reading(_design("s", classes=())), reading(_design("p", board=_board("p", shift=2, tracks=1)))
    )
    stage = rta2_stage(model, read, SCOPE)
    assert stage.status == "ok" and stage.issues == () and stage.summary["holds"] is True
    assert stage.summary["compared"] == {
        "schematic": ["component", "net", "no_connect"],
        "pcb": ["footprint", "netclass", "pad", "track"],
    }
    assert stage.summary["not_in_model"] == {}
    # the schematic reading holds no net class and is not asked for one; a footprint moved by 3 nm differs
    moved = ProjectRead(read.schematic, reading(_design("p", board=_board("p", shift=3, tracks=1))))
    assert [i.where for i in rta2_stage(model, moved, SCOPE).issues] == [
        "pcb:/footprint/R1/position",
        "pcb:/footprint/R2/position",
    ]
    renamed = ProjectRead(
        read.schematic, reading(_design("p", board=_board("p", tracks=1), classes=("SIG",)))
    )
    assert [i.where for i in rta2_stage(model, renamed, SCOPE).issues] == [
        "pcb:/netclass/PWR",
        "pcb:/netclass/SIG",
    ]


def test_board_kinds_the_model_does_not_hold_are_counted() -> None:
    """The built model of the script holds no footprint and no copper: the reading's are counted, and the
    level says nothing about them."""
    model = _design("m", board=Board(id="brd_m"))
    read = ProjectRead(reading(_design("s")), reading(_design("p", board=_board("p", tracks=3))))
    stage = rta2_stage(model, read, SCOPE)
    assert stage.status == "ok" and stage.summary["holds"] is True
    assert stage.summary["compared"] == {"schematic": ["component", "net", "no_connect"], "pcb": ["netclass"]}
    assert stage.summary["not_in_model"] == {"pcb": {"footprint": 2, "pad": 2, "track": 3}}
    # a kind the model holds is compared in full: a track that only the reading holds is a difference
    some = _design("m", board=dataclasses.replace(_board("m", tracks=1), footprints=()))
    stage = rta2_stage(some, read, SCOPE)
    assert stage.summary["not_in_model"] == {"pcb": {"footprint": 2, "pad": 2}}
    assert sorted(i.where for i in stage.issues) == ["pcb:/track/0", "pcb:/track/1"]
    assert "the written documents hold this" in stage.issues[0].message
    assert set(held(model)) == set(BOARD_KINDS) and held(some)["track"] == 1


def test_one_side_alone_and_the_issue_cap() -> None:
    model = _design("m")
    only_pcb = rta2_stage(model, ProjectRead(None, reading(_design("p"))), SCOPE)
    assert only_pcb.summary["compared"] == {"pcb": ["netclass"]} and only_pcb.status == "ok"
    many = tuple(Component(id=f"cmp_m_{n}", ref=f"C{n}") for n in range(MAX_ISSUES + 20))
    big = dataclasses.replace(model, circuit=dataclasses.replace(model.circuit, components=many, nets=()))
    stage = rta2_stage(big, ProjectRead(reading(_design("s")), None), ModelScope({"component": ("ref",)}))
    assert len(stage.issues) == MAX_ISSUES and stage.summary["differences"] == MAX_ISSUES + 22
    removed = next(i for i in stage.issues if i.where == "schematic:/component/C0")
    assert "the built model holds this" in removed.message


def test_stage_in_the_pipeline_takes_the_backends_scope_and_evidence() -> None:
    model = _design("m")
    added = {"roundtrip.rta2": Evidence(Level.INFERRED, hypotheses=("H-FAKE-RTA2",))}
    sheet = reading(_design("s"), evidence=Evidence(Level.CORPUS_VERIFIED, hypotheses=("H-FAKE-SCH",)))
    fake = FakeDocumentValidator(schematic=sheet, scope=ModelScope({"component": ("value",)}), added=added)

    def run(design: Design, **more: object):  # type: ignore[no-untyped-def]
        values: dict[str, object] = {"model": design, "built": True}
        return run_document_checks(
            documents=fake.documents_result, stages=("roundtrip.rta2",), validator=fake, **(values | more)  # type: ignore[arg-type]
        ).stages[0]  # fmt: skip

    stage = run(model)
    assert (stage.status, stage.summary["holds"]) == ("ok", True)
    assert stage.evidence == Evidence(Level.INFERRED, hypotheses=("H-FAKE-RTA2", "H-FAKE-SCH"))
    changed = dataclasses.replace(model, circuit=_circuit("m", value="22k"))
    assert [i.where for i in run(changed).issues][:1] == ["schematic:/component/R1/value"]
    assert run(model, built=False).reason == "native-input"
    assert run(model, cache_error="bad").reason == "cache-unreadable"
    fake.schematic = None
    assert run(model).reason == "not-judged"
