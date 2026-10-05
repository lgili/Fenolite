# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The document check pipeline (capability verification-loop, "Document check pipeline" and "ERC lite
stage"; change c0044), on a fake ``DocumentValidator``: no backend module is imported."""

from __future__ import annotations

import dataclasses

import pytest
from fakes import PCB, SCH, FakeDocumentValidator, document_set, passing, reading

from fenolite.backends.base import ContainerRoundTrip, Document, ModelScope
from fenolite.checks import STAGE_ORDER, erc_lite
from fenolite.checks.documents import DOCUMENT_STAGES, refused, run_document_checks
from fenolite.checks.stages import CheckReport, StageResult
from fenolite.core.coords import Point, Size
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.board import Board, FootprintInstance, Pad
from fenolite.model.circuit import Circuit, Component, Net, Pin, PinRef
from fenolite.model.design import Design

SCH_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-FAKE-SCH",))
PCB_EVIDENCE = Evidence(Level.CORPUS_VERIFIED, hypotheses=("H-FAKE-PCB",))
NETS = {"R1": ("VIN", "LED_A"), "D1": ("LED_A", "GND"), "U1": ("VIN", "GND")}


def _circuit(prefix: str, nets: dict[str, tuple[str, str]], etypes: tuple[str, str] = ("passive", "passive")):
    parts = [
        Component(
            id=f"cmp_{prefix}_{ref}",
            ref=ref,
            lib_footprint_ref="Lib:FP",
            pins=tuple(
                Pin(id=f"pin_{prefix}_{ref}_{n}", number=n, etype=t)  # type: ignore[arg-type]
                for n, t in zip(("1", "2"), etypes, strict=True)
            ),
        )
        for ref in nets
    ]
    members: dict[str, list[PinRef]] = {}
    for ref, names in nets.items():
        for number, name in zip(("1", "2"), names, strict=True):
            members.setdefault(name, []).append(PinRef(f"cmp_{prefix}_{ref}", number))
    listed = tuple(Net(id=f"net_{prefix}_{name}", name=name, members=tuple(m)) for name, m in members.items())
    return Circuit(components=tuple(parts), nets=listed)


def _schematic(nets: dict[str, tuple[str, str]] = NETS) -> Design:
    return dataclasses.replace(Design.new("sch", seed=1), circuit=_circuit("s", nets))


def _pcb(nets: dict[str, tuple[str, str]] = NETS) -> Design:
    circuit = _circuit("p", nets)
    ids = {net.name: net.id for net in circuit.nets}
    footprints = tuple(
        FootprintInstance(
            id=f"fp_{ref}",
            component_id=f"cmp_p_{ref}",
            lib_ref="Lib:FP",
            position=Point(0, 0),
            pads=tuple(
                Pad(
                    id=f"pad_{ref}_{n}",
                    number=n,
                    shape="rect",
                    size=Size(1, 1),
                    position=Point(0, 0),
                    layers=("F.Cu",),
                    net_id=ids[name],
                )
                for n, name in zip(("1", "2"), names, strict=True)
            ),
        )  # fmt: skip
        for ref, names in nets.items()
    )
    return dataclasses.replace(
        Design.new("pcb", seed=2), circuit=circuit, board=Board(id="brd_1", footprints=footprints)
    )


def _fake(**more: object) -> FakeDocumentValidator:
    values: dict[str, object] = {
        "schematic": reading(_schematic(), evidence=SCH_EVIDENCE),
        "pcb": reading(_pcb(), evidence=PCB_EVIDENCE),
    }
    return FakeDocumentValidator(**(values | more))  # type: ignore[arg-type]


def _run(
    fake: FakeDocumentValidator, stages: tuple[str, ...] = DOCUMENT_STAGES, **more: object
) -> CheckReport:
    values: dict[str, object] = {"model": None, "built": False}
    return run_document_checks(
        documents=fake.documents_result, stages=stages, validator=fake, **(values | more)  # type: ignore[arg-type]
    )  # fmt: skip


def _stage(report: CheckReport, name: str) -> StageResult:
    return next(stage for stage in report.stages if stage.name == name)


def test_stage_names() -> None:
    assert DOCUMENT_STAGES == (
        "model.validate",
        "erc.lite",
        "netlist.assignment_compare",
        "roundtrip.rta0",
        "roundtrip.rta1",
        "roundtrip.rta2",
    )
    assert "roundtrip.rta0" not in STAGE_ORDER  # the KiCad pipeline is unchanged
    assert set(DOCUMENT_STAGES) & set(STAGE_ORDER) == {
        "model.validate",
        "erc.lite",
        "netlist.assignment_compare",
    }


def test_fixed_order_with_a_fake_validator() -> None:
    fake = _fake()
    report = _run(fake, ("roundtrip.rta1", "model.validate", "netlist.assignment_compare"))
    assert [stage.name for stage in report.stages] == [
        "model.validate",
        "netlist.assignment_compare",
        "roundtrip.rta1",
    ]
    assert [stage.status for stage in report.stages] == ["ok", "ok", "ok"]
    assert len(fake.read_calls) == 1
    assert sorted(fake.roundtrip_calls) == [("a.pcb", "RT-A1"), ("a.sch", "RT-A1")]
    (pair,) = _stage(report, "netlist.assignment_compare").summary["pairs"]  # type: ignore[misc]
    assert (pair["a"], pair["b"], pair["differences"], pair["common"]) == ("schematic", "pcb", 0, 6)
    assert report.issues == () and report.read_error is None
    assert _stage(report, "model.validate").summary == {
        "schematic": {"components": 3, "nets": 3},
        "pcb": {"components": 3, "nets": 3},
    }
    assert report.evidence == Evidence(Level.INFERRED, hypotheses=("H-FAKE-PCB", "H-FAKE-RT", "H-FAKE-SCH"))


def test_no_reading_without_a_reading_stage() -> None:
    fake = _fake()
    report = _run(fake, ("roundtrip.rta0", "roundtrip.rta1"))
    assert fake.read_calls == [] and len(fake.roundtrip_calls) == 4
    assert len(set(fake.roundtrip_calls)) == 4  # once per document and level
    assert [stage.status for stage in report.stages] == ["ok", "ok"]
    assert report.evidence.level is Level.CORPUS_VERIFIED


def test_pad_on_another_net_in_the_pcb_document() -> None:
    moved = dict(NETS) | {"R1": ("VIN", "VIN")}
    report = _run(_fake(pcb=reading(_pcb(moved), evidence=PCB_EVIDENCE)), ("netlist.assignment_compare",))
    (stage,) = report.stages
    assert stage.status == "errors"
    differs = [i for i in stage.issues if i.code == "netlist.assignment-differs"]
    assert differs and "R1-2" in {i.where for i in differs}
    assert "in the schematic" in differs[0].message and "in the pcb" in differs[0].message
    assert report.issues == stage.issues


def test_schematic_alone() -> None:
    fake = _fake(documents_result=document_set(SCH), pcb=None)
    report = _run(fake)
    statuses = {stage.name: (stage.status, stage.reason) for stage in report.stages}
    assert statuses["netlist.assignment_compare"] == ("skipped", "single-source")
    assert statuses["roundtrip.rta2"] == ("skipped", "native-input")
    assert statuses["erc.lite"][0] == "ok" and statuses["model.validate"][0] == "ok"
    # neither skip counts: the envelope is the lowest of the stages that ran
    assert report.evidence.level is Level.INFERRED and "H-FAKE-PCB" not in report.evidence.hypotheses
    assert set(_stage(report, "model.validate").summary) == {"schematic"}


def test_library_alone_is_not_judged_by_the_model_stages() -> None:
    library = Document("lib.fp", "fake_fplib", "footprint-library")
    fake = FakeDocumentValidator(documents_result=document_set(library))
    report = _run(fake)
    statuses = {stage.name: (stage.status, stage.reason) for stage in report.stages}
    assert statuses == {
        "model.validate": ("skipped", "not-judged"),
        "erc.lite": ("skipped", "no-schematic"),
        "netlist.assignment_compare": ("skipped", "single-source"),
        "roundtrip.rta0": ("ok", ""),
        "roundtrip.rta1": ("ok", ""),
        "roundtrip.rta2": ("skipped", "native-input"),
    }
    assert report.issues == () and report.evidence.level is Level.CORPUS_VERIFIED


def test_one_refused_document_among_others() -> None:
    error = FormatError("the header is cut", file="whatever.pcb", locator="header", offset=100)
    fake = _fake(
        pcb=None,
        errors={"a.pcb": error},
        verdicts={("a.pcb", "RT-A0"): error, ("a.pcb", "RT-A1"): error},
    )
    report = _run(fake)
    first = report.issues[0]
    assert (first.code, first.severity, first.where) == ("check.read-refused", "error", "a.pcb:header:@100")
    assert first.message == "FEN-3004: the header is cut" and first == refused("a.pcb", error)
    assert [i.code for i in report.issues].count("check.read-refused") == 1
    assert _stage(report, "model.validate").status == "ok"
    assert set(_stage(report, "model.validate").summary) == {"schematic"}
    for name in ("roundtrip.rta0", "roundtrip.rta1"):
        assert _stage(report, name).summary["unjudged"] == {"read-refused": 1}
    assert _stage(report, "netlist.assignment_compare").reason == "single-source"
    assert report.read_error is None


def test_only_document_refused_is_the_read_error() -> None:
    error = FormatError("cut", file="a.pcb")
    fake = FakeDocumentValidator(
        documents_result=document_set(PCB),
        errors={"a.pcb": error},
        verdicts={("a.pcb", "RT-A0"): error, ("a.pcb", "RT-A1"): error},
    )
    report = _run(fake)
    assert report.read_error is error
    statuses = {stage.name: (stage.status, stage.reason) for stage in report.stages}
    assert statuses["model.validate"] == ("skipped", "read-refused")
    assert statuses["erc.lite"] == ("skipped", "no-schematic")
    assert statuses["roundtrip.rta0"] == statuses["roundtrip.rta1"] == ("skipped", "read-refused")
    assert report.evidence == Evidence()  # read-refused skips count, as UNVERIFIED
    # found by the container stages alone, the refusal is still one input issue and the read error
    only = _run(fake, ("roundtrip.rta0", "roundtrip.rta1"))
    assert only.read_error is error and [i.code for i in only.issues] == ["check.read-refused"]
    sheet = FakeDocumentValidator(documents_result=document_set(SCH), errors={"a.sch": error})
    assert _stage(_run(sheet, ("erc.lite",)), "erc.lite").reason == "read-refused"


def test_input_issues_come_first_and_sorted() -> None:
    error = FormatError("cut", file="x")
    fake = _fake(
        documents_result=document_set(SCH, PCB, missing=("z.lib", "b.lib")),
        pcb=None,
        errors={"a.pcb": error},
        schematic=reading(_schematic({"U1": ("VIN", "GND")}), evidence=SCH_EVIDENCE),
    )
    report = _run(fake, ("erc.lite",), cache_error="ValueError: bad json")
    assert [(i.code, i.where) for i in report.issues[:4]] == [
        ("check.cache-unreadable", ""),
        ("check.document-missing", "b.lib"),
        ("check.document-missing", "z.lib"),
        ("check.read-refused", "a.pcb"),
    ]
    assert [i.severity for i in report.issues[:4]] == ["warning", "warning", "warning", "error"]


def test_erc_native_runs_on_the_schematic_reading() -> None:
    """Scenario "Rules run on a schematic reading"."""
    driver = Component(id="cmp_1", ref="U2", pins=(Pin(id="pin_0", number="1", etype="power_out"),))
    part = Component(
        id="cmp_2",
        ref="U1",
        pins=(Pin(id="pin_1", number="1", etype="input"), Pin(id="pin_2", number="2", etype="input")),
    )
    net = Net(id="net_1", name="VCC", members=(PinRef("cmp_1", "1"), PinRef("cmp_2", "1")))
    design = dataclasses.replace(
        Design.new("sch", seed=1), circuit=Circuit(components=(driver, part), nets=(net,))
    )
    added = {"erc.lite": Evidence(Level.INFERRED, hypotheses=("H-FAKE-ERC",))}
    fake = FakeDocumentValidator(
        documents_result=document_set(SCH), schematic=reading(design, evidence=SCH_EVIDENCE), added=added
    )
    report = _run(fake, ("erc.lite",))
    (stage,) = report.stages
    assert stage.status == "ok"
    assert [(i.code, i.severity, i.where) for i in stage.issues] == [
        ("erc.lite.floating-pin", "warning", "U1-2")
    ]
    assert stage.summary == {"output-conflict": 0, "power-undriven": 0, "floating-pin": 1}
    assert stage.evidence == Evidence(
        Level.INFERRED, hypotheses=("H-FAKE-ERC", "H-FAKE-SCH", "H-K-CHECK-ERC")
    )
    marked = dataclasses.replace(
        design, circuit=dataclasses.replace(design.circuit, no_connects=(PinRef("cmp_2", "2"),))
    )
    fake = FakeDocumentValidator(documents_result=document_set(SCH), schematic=reading(marked))
    assert _run(fake, ("erc.lite",)).stages[0].issues == ()


def test_native_model_findings_are_prefixed_and_reader_issues_kept() -> None:
    twice = _schematic()
    first = twice.circuit.components[0]
    clash = dataclasses.replace(twice.circuit.components[1], ref=first.ref)
    circuit = dataclasses.replace(twice.circuit, components=(first, clash, twice.circuit.components[2]))
    note = Issue("fake.reader.note", "info", "kept", where="a.sch:FileHeader#3")
    fake = _fake(schematic=reading(dataclasses.replace(twice, circuit=circuit), issues=(note,)))
    stage = _run(fake, ("model.validate",)).stages[0]
    models = [i for i in stage.issues if i.code.startswith("model.")]
    assert models and all(i.where.startswith("schematic:") for i in models)
    assert note in stage.issues
    assert not [i for i in stage.issues if i.code.startswith("check.")]  # no footprint-unresolved here
    assert stage.evidence == Evidence(Level.INFERRED, hypotheses=("H-FAKE-PCB", "H-K-PCB-READ"))


def test_built_input_compares_the_model_with_both_sides() -> None:
    model = dataclasses.replace(Design.new("model", seed=3), circuit=_circuit("m", NETS))
    fake = _fake(
        added={"netlist.assignment_compare": Evidence(Level.CORPUS_VERIFIED, hypotheses=("H-FAKE-NET",))}
    )
    report = _run(fake, ("model.validate", "erc.lite", "netlist.assignment_compare"), model=model, built=True)
    validate, erc, compare = report.stages
    assert validate.summary == {"model": {"components": 3, "nets": 3}}
    assert validate.evidence == Evidence(Level.INFERRED) and erc.evidence == erc_lite.EVIDENCE
    pairs = compare.summary["pairs"]
    assert [(p["a"], p["b"], p["differences"]) for p in pairs] == [  # type: ignore[index,union-attr]
        ("model", "schematic", 0),
        ("model", "pcb", 0),
    ]
    assert compare.evidence == Evidence(Level.INFERRED, hypotheses=("H-FAKE-NET", "H-FAKE-PCB", "H-FAKE-SCH"))
    assert len(fake.read_calls) == 1


def test_built_input_with_an_unreadable_cache() -> None:
    report = _run(_fake(), built=True, cache_error="ValueError: bad")
    statuses = {stage.name: (stage.status, stage.reason) for stage in report.stages}
    for name in ("model.validate", "erc.lite", "netlist.assignment_compare", "roundtrip.rta2"):
        assert statuses[name] == ("skipped", "cache-unreadable")
    assert statuses["roundtrip.rta0"] == ("ok", "")
    assert report.issues[0].code == "check.cache-unreadable"
    assert report.evidence.level is Level.UNVERIFIED  # the counted skips lower the envelope


def test_container_failures_reach_the_report() -> None:
    lost = ContainerRoundTrip(
        "RT-A0", True, False, streams=3, different=("Nets6/Data",), difference="Nets6/Data"
    )
    report = _run(_fake(verdicts={("a.pcb", "RT-A0"): lost}), ("roundtrip.rta0",))
    (stage,) = report.stages
    assert stage.status == "errors" and stage.evidence.level is Level.UNVERIFIED
    assert [(i.code, i.where) for i in report.issues] == [("check.rta0-failed", "a.pcb:Nets6/Data")]
    assert passing("RT-A0").passed


def test_scope_reaches_the_rta2_stage() -> None:
    model = dataclasses.replace(Design.new("model", seed=3), circuit=_circuit("m", NETS))
    fake = _fake(scope=ModelScope({"component": ("ref",)}))
    report = _run(fake, ("roundtrip.rta2",), model=model, built=True)
    assert [stage.name for stage in report.stages] == ["roundtrip.rta2"]
    assert len(fake.read_calls) == 1


@pytest.mark.parametrize("name", ["drc.kicad", "roundtrip", ""])
def test_unknown_stage_names_are_left_out(name: str) -> None:
    assert _run(_fake(), (name,)).stages == ()
