# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The assignment comparison (capability verification-loop, "Assignment compare stage"; change c0020)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from fakes import (
    FakeFullOracle,
    FakeOracle,
    FakeSchematicOracle,
    netlist,
    netlist_outcome,
    project,
    validation,
)

from fenolite.backends.base import PadAssignment, PadNetList, ProjectSet
from fenolite.backends.kicad.pcb import read_board
from fenolite.checks.assignment_compare import (
    NO_NET,
    assignment_stage,
    board_netlist,
    bonded_label,
    compare,
    model_netlist,
    net_text,
    schematic_file,
)
from fenolite.core.evidence import Evidence, Level
from fenolite.model.circuit import Circuit, Component, Net, Pin, PinRef
from fenolite.model.design import Design

TWO_LAYER = Path(__file__).resolve().parents[2] / "data" / "kicad" / "board" / "two_layer.kicad_pcb"


def _design() -> Design:
    return read_board(TWO_LAYER.read_text(encoding="utf-8"), file=TWO_LAYER.name)


def _same_partition(listed: PadNetList, source: str = "export") -> PadNetList:
    """``listed`` under other labels: the same blocks, renamed."""
    names: dict[str, str] = {}
    pairs = [(a.element, names.setdefault(a.net, f"N{len(names)}")) for a in listed.assignments]
    return netlist(source, *pairs)


def test_names_do_not_matter() -> None:
    board = netlist("board", ("R1-1", "VIN"), ("R1-2", "LED_A"), ("D1-2", "LED_A"))
    export = netlist("export", ("R1-1", "N1"), ("R1-2", "N2"), ("D1-2", "N2"))
    result = compare(board, export)
    assert result.differences == () and result.common == 3
    assert (result.a, result.b, result.only_a, result.only_b) == ("board", "export", (), ())


def test_reassigned_pad_located() -> None:
    model = netlist("model", ("R1-2", "LED_A"), ("D1-2", "LED_A"), ("D1-1", "GND"), ("U1-9", "GND"))
    board = netlist("board", ("R1-2", "GND"), ("D1-2", "LED_A"), ("D1-1", "GND"), ("U1-9", "GND"))
    (difference,) = compare(model, board).differences
    assert (difference.element, difference.a, difference.b) == ("R1-2", "model", "board")
    assert (difference.net_a, difference.net_b) == ("LED_A", "GND")


def test_swapped_pairs_flagged() -> None:
    a = netlist("a", ("P1-1", "x"), ("P2-1", "x"), ("P3-1", "y"), ("P4-1", "y"))
    b = netlist("b", ("P1-1", "x"), ("P3-1", "x"), ("P2-1", "y"), ("P4-1", "y"))
    assert [d.element for d in compare(a, b).differences] == ["P1-1", "P2-1", "P3-1", "P4-1"]


def test_merged_and_split_nets() -> None:
    a = netlist("a", ("A-1", "x"), ("A-2", "x"), ("A-3", "x"), ("B-1", "y"))
    merged = netlist("b", ("A-1", "z"), ("A-2", "z"), ("A-3", "z"), ("B-1", "z"))
    assert [d.element for d in compare(a, merged).differences] == ["B-1"]
    assert [d.element for d in compare(merged, a).differences] == ["B-1"]


def test_a_pad_on_no_net_is_a_block_of_its_own() -> None:
    """c0061: two pads on no net are not connected to each other."""
    a = netlist("a", ("A-1", NO_NET), ("A-2", NO_NET), ("A-3", "x"), ("A-4", "x"))
    b = netlist("b", ("A-1", NO_NET), ("A-2", NO_NET), ("A-3", "N1"), ("A-4", "N1"))
    assert compare(a, b).differences == ()
    lost = netlist("b", ("A-1", NO_NET), ("A-2", NO_NET), ("A-3", NO_NET), ("A-4", "N1"))
    assert {d.element for d in compare(a, lost).differences} == {"A-3", "A-4"}


def test_unconnected_pins_named_on_one_side() -> None:
    model = netlist("model", ("U1-2", NO_NET), ("U1-3", NO_NET), ("U1-9", "VIN"), ("R1-1", "VIN"))
    board = netlist(
        "board",
        ("U1-2", "unconnected-(U1-PA1-Pad2)"),
        ("U1-3", "unconnected-(U1-PA2-Pad3)"),
        ("U1-9", "VIN"),
        ("R1-1", "VIN"),
    )
    assert compare(model, board).differences == () and compare(board, model).differences == ()
    assert compare(model, board).common == 4


def test_two_unconnected_pads_joined_on_one_side() -> None:
    model = netlist("model", ("U1-2", NO_NET), ("U1-3", NO_NET), ("U1-9", "VIN"), ("R1-1", "VIN"))
    board = netlist("board", ("U1-2", "X"), ("U1-3", "X"), ("U1-9", "VIN"), ("R1-1", "VIN"))
    found = {d.element for d in compare(model, board).differences}
    assert found and found <= {"U1-2", "U1-3"}
    difference = compare(model, board).differences[0]
    assert (difference.net_a, difference.net_b) == (NO_NET, "X")


def test_no_net_pads_are_below_two_pins() -> None:
    a = netlist("a", ("A-1", NO_NET), ("A-2", NO_NET), ("A-3", "x"), ("A-4", "x"))
    result = compare(a, a, min_pins=2)
    assert result.common == 2 and {u.element for u in result.only_a} == {"A-1", "A-2"}
    assert {u.reason for u in result.only_a} == {"below-min-pins"}


def test_element_with_two_labels_is_a_difference() -> None:
    a = netlist("a", ("J1-1", "x"), ("J1-1", "y"), ("R1-1", "x"))
    b = netlist("b", ("J1-1", "n"), ("R1-1", "n"))
    (difference,) = compare(a, b).differences
    assert (difference.element, difference.net_a) == ("J1-1", "x|y")


def test_single_pin_nets() -> None:
    a = netlist("a", ("T1-1", "solo"), ("R1-1", "x"), ("R2-1", "x"))
    b = netlist("b", ("T1-1", "n1"), ("R1-1", "n2"), ("R2-1", "n2"))
    kept = compare(a, b, min_pins=1)
    assert kept.common == 3 and kept.only_a == () and kept.differences == ()
    dropped = compare(a, b, min_pins=2)
    assert dropped.common == 2 and dropped.differences == ()
    assert {(u.element, u.reason) for u in dropped.only_a} == {("T1-1", "below-min-pins")}
    assert {(u.element, u.reason) for u in dropped.only_b} == {("T1-1", "below-min-pins")}


def test_coverage_reasons() -> None:
    board = netlist("board", ("R1-1", "x"), ("MH1-1", NO_NET), ("U1-3", NO_NET))
    export = netlist(
        "export", ("R1-1", "n"), uncovered=(("U1-3", "net-label-ambiguous"), ("X9-7", "unmatched-record"))
    )
    result = compare(board, export)
    assert result.differences == () and result.common == 1
    assert {(u.element, u.reason) for u in result.only_a} == {
        ("MH1-1", "not-in-export"),
        ("U1-3", "net-label-ambiguous"),
        ("X9-7", "unmatched-record"),
    }
    assert {(u.element, u.reason) for u in result.only_b} == {("X9-7", "not-in-board")}


def test_board_and_model_lists() -> None:
    design = _design()
    listed, unnumbered = board_netlist(design)
    nets = {n.id: n.name for n in design.circuit.nets}
    assert {(a.element, nets.get(a.net, a.net)) for a in listed.assignments} == {
        ("R1-1", "VCC"),
        ("R1-2", "LED_A"),
        ("D1-1", "GND"),
        ("D1-2", "LED_A"),
    }
    assert (listed.source, unnumbered) == ("board", 0)
    r1 = Component(id="cmp_00000000-0000-4000-8000-000000000001", ref="R1",
                   pins=(Pin(id="pin_00000000-0000-4000-8000-000000000001", number="1"),
                         Pin(id="pin_00000000-0000-4000-8000-000000000002", number="2")))  # fmt: skip
    net = Net(id="net_00000000-0000-4000-8000-000000000001", name="VIN", members=(PinRef(r1.id, "1"),))
    model = dataclasses.replace(Design.new("m", seed=0), circuit=Circuit(components=(r1,), nets=(net,)))
    assert model_netlist(model) == PadNetList(
        "model", (PadAssignment("R1-1", net.id), PadAssignment("R1-2", NO_NET))
    )
    # a pin that the component maps to another pad is named by that pad (c0061)
    mapped = dataclasses.replace(r1, pin_pad_map=(("1", "2"), ("2", "1")))
    swapped = dataclasses.replace(model, circuit=Circuit(components=(mapped,), nets=(net,)))
    assert model_netlist(swapped) == PadNetList(
        "model", (PadAssignment("R1-2", net.id), PadAssignment("R1-1", NO_NET))
    )


def _stage(oracle: object, design: Design, **kwargs: object):  # type: ignore[no-untyped-def]
    options = {"validation": validation(design), "model": None, "built": False} | kwargs
    return assignment_stage(oracle, project(), **options)  # type: ignore[arg-type]


def test_native_input_compares_board_and_export_only() -> None:
    design = _design()
    listed, _ = board_netlist(design)
    oracle = FakeFullOracle(netlist_result=netlist_outcome(_same_partition(listed)))
    result = _stage(oracle, design)
    assert result.status == "ok" and result.issues == ()
    assert result.summary == {
        "pairs": [{"a": "board", "b": "export", "common": 4, "only_a": 0, "only_b": 0, "differences": 0}],
        "min_pins": 1,
        "unnumbered": 0,
    }
    assert result.evidence.level == Level.INFERRED and result.evidence.oracle == "fake 1.0"
    assert oracle.boards == [design]


def test_uncovered_elements_are_coverage() -> None:
    design = _design()
    listed, _ = board_netlist(design)
    export = _same_partition(listed)
    kept = tuple(a for a in export.assignments if a.element != "D1-1")
    oracle = FakeFullOracle(netlist_result=netlist_outcome(PadNetList("export", kept)))
    result = _stage(oracle, design)
    (info,) = result.issues
    assert (info.code, info.severity, info.where) == ("netlist.uncovered", "info", "D1-1")
    assert "not-in-export" in info.message and "1 element(s)" in info.message
    assert result.status == "ok"


def test_built_input_compares_both_pairs_and_locates_the_pad() -> None:
    design = _design()
    listed, _ = board_netlist(design)
    refs = {c.id: c.ref for c in design.circuit.components}
    assert design.board is not None
    moved = tuple(
        dataclasses.replace(
            fp,
            pads=tuple(
                dataclasses.replace(p, net_id=next(n.id for n in design.circuit.nets if n.name == "GND"))
                if (refs[fp.component_id], p.number) == ("R1", "2")
                else p
                for p in fp.pads
            ),
        )
        for fp in design.board.footprints
    )
    board = dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=moved))
    oracle = FakeFullOracle(netlist_result=netlist_outcome(_same_partition(board_netlist(board)[0])))
    model = dataclasses.replace(
        design,
        circuit=dataclasses.replace(
            design.circuit,
            nets=tuple(
                dataclasses.replace(
                    n,
                    members=tuple(
                        PinRef(c.id, a.element.split("-")[1])
                        for a in listed.assignments
                        if a.net == n.id
                        for c in design.circuit.components
                        if c.ref == a.element.split("-")[0]
                    ),
                )
                for n in design.circuit.nets
            ),
        ),
    )
    result = _stage(oracle, board, model=model, built=True)
    assert [(p["a"], p["b"], p["differences"]) for p in result.summary["pairs"]] == [  # type: ignore[index,union-attr]
        ("model", "board", 3),
        ("board", "export", 0),
    ]
    # Every net of this board has two pads, so the moved pad splits its blocks 1 to 1: a tie on both sides
    # flags nothing, and the fallback flags every element of a block without an equal block.
    errors = {i.where: i for i in result.issues if i.severity == "error"}
    assert set(errors) == {"R1-2", "D1-1", "D1-2"}
    assert {i.code for i in errors.values()} == {"netlist.assignment-differs"}
    error = errors["R1-2"]
    assert "LED_A in the model" in error.message and "GND in the board" in error.message
    assert result.status == "errors"
    unreadable = _stage(oracle, board, model=None, built=True)
    assert [(p["a"], p["b"]) for p in unreadable.summary["pairs"]] == [("board", "export")]  # type: ignore[index,union-attr]


def test_failed_export_and_timeout() -> None:
    design = _design()
    failed = _stage(FakeFullOracle(netlist_result=netlist_outcome(None)), design)
    (issue,) = failed.issues
    assert (issue.code, issue.retryable) == ("check.oracle-failed", False)
    assert "no export" in issue.message and failed.evidence.level == Level.UNVERIFIED
    assert failed.status == "errors" and failed.summary["pairs"] == []
    timed = _stage(FakeFullOracle(netlist_result=netlist_outcome(None, timeout=True)), design)
    assert timed.issues[0].retryable and "timed out" in timed.issues[0].message


def test_skips() -> None:
    design = _design()
    refused = assignment_stage(FakeFullOracle(), project(), validation=None, model=None, built=False)
    assert (refused.status, refused.reason) == ("skipped", "read-refused")
    drc_only = _stage(FakeOracle(), design)
    assert (drc_only.status, drc_only.reason) == ("skipped", "unsupported-oracle")
    assert _stage(None, design).reason == "unsupported-oracle"


# -- the schematic's netlist as a source (change c0063)


def _model_of(design: Design) -> Design:
    """``design`` as a built model: every pad of the board is a member of its net."""
    listed, _ = board_netlist(design)
    nets = tuple(
        dataclasses.replace(
            n,
            members=tuple(
                PinRef(c.id, a.element.split("-")[1])
                for a in listed.assignments
                if a.net == n.id
                for c in design.circuit.components
                if c.ref == a.element.split("-")[0]
            ),
        )
        for n in design.circuit.nets
    )
    return dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, nets=nets))


def _schematic_stage(oracle: object, design: Design, **kwargs: object):  # type: ignore[no-untyped-def]
    options = {"validation": validation(design), "model": None, "built": False} | kwargs
    return assignment_stage(oracle, project(schematic=True), **options)  # type: ignore[arg-type]


def _pairs(result: object) -> list[tuple[str, str, int]]:
    return [(p["a"], p["b"], p["differences"]) for p in result.summary["pairs"]]  # type: ignore[attr-defined]


def _oracle_with(design: Design, schematic: PadNetList | None, **kwargs: object) -> FakeSchematicOracle:
    export = netlist_outcome(_same_partition(board_netlist(design)[0]))
    found = netlist_outcome(schematic, **kwargs)  # type: ignore[arg-type]
    return FakeSchematicOracle(netlist_result=export, schematic_result=found)


def test_schematic_pair_agrees_with_the_model() -> None:
    design = _design()
    listed, _ = board_netlist(design)
    names = {n.id: n.name for n in design.circuit.nets}
    sheet = netlist(
        "schematic",
        *((a.element, names.get(a.net, f"unconnected-({a.element})")) for a in listed.assignments),
    )
    oracle = _oracle_with(design, sheet)
    result = _schematic_stage(oracle, design, model=_model_of(design), built=True)
    assert _pairs(result) == [("model", "board", 0), ("model", "schematic", 0), ("board", "export", 0)]
    assert result.status == "ok" and len(oracle.schematic_calls) == 1
    assert [i for i in result.issues if i.severity == "error"] == []


def test_two_nets_joined_on_the_sheet() -> None:
    design = _design()
    listed, _ = board_netlist(design)
    joined = netlist("schematic", *((a.element, "ONE") for a in listed.assignments))
    result = _schematic_stage(_oracle_with(design, joined), design, model=_model_of(design), built=True)
    assert _pairs(result)[0] == ("model", "board", 0) and _pairs(result)[2] == ("board", "export", 0)
    assert _pairs(result)[1][:2] == ("model", "schematic") and _pairs(result)[1][2] > 0
    errors = [i for i in result.issues if i.code == "netlist.assignment-differs"]
    assert errors and all("in the model" in i.message and "in the schematic" in i.message for i in errors)
    assert all("ONE in the schematic" in i.message for i in errors), (
        "the label of the sheet is shown as it is"
    )
    assert result.status == "errors"


def test_native_input_compares_the_schematic_with_the_board() -> None:
    design = _design()
    listed, _ = board_netlist(design)
    names = {n.id: n.name for n in design.circuit.nets}
    pairs = [(a.element, "GND" if a.element == "R1-2" else names[a.net]) for a in listed.assignments]
    result = _schematic_stage(_oracle_with(design, netlist("schematic", *pairs)), design)
    assert [(a, b) for a, b, _ in _pairs(result)] == [("schematic", "board"), ("board", "export")]
    errors = {i.where for i in result.issues if i.code == "netlist.assignment-differs"}
    assert "R1-2" in errors and _pairs(result)[1][2] == 0


def test_built_input_without_a_model_compares_the_schematic_with_the_board() -> None:
    design = _design()
    same = _same_partition(board_netlist(design)[0], "schematic")
    result = _schematic_stage(_oracle_with(design, same), design, model=None, built=True)
    assert _pairs(result) == [("schematic", "board", 0), ("board", "export", 0)]


def test_schematic_export_fails() -> None:
    design = _design()
    result = _schematic_stage(_oracle_with(design, None), design)
    (failed,) = [i for i in result.issues if i.code == "check.oracle-failed"]
    assert failed.severity == "error" and not failed.retryable and failed.where == "board.kicad_sch"
    assert "no netlist of the schematic" in failed.message and "no export" in failed.message
    assert _pairs(result) == [("board", "export", 0)] and result.status == "errors"
    timed = _schematic_stage(_oracle_with(design, None, timeout=True), design)
    (late,) = [i for i in timed.issues if i.code == "check.oracle-failed"]
    assert late.retryable and "timed out" in late.message


def test_no_schematic_pairs_as_before() -> None:
    design = _design()
    oracle = _oracle_with(design, _same_partition(board_netlist(design)[0], "schematic"))
    result = _stage(oracle, design)
    assert _pairs(result) == [("board", "export", 0)] and oracle.schematic_calls == []


def test_oracle_without_schematic_netlists_keeps_the_pairs() -> None:
    design = _design()
    oracle = FakeFullOracle(netlist_result=netlist_outcome(_same_partition(board_netlist(design)[0])))
    result = _schematic_stage(oracle, design)
    assert _pairs(result) == [("board", "export", 0)] and result.issues == ()


def test_schematic_evidence_joins_the_stage() -> None:
    design = _design()
    same = _same_partition(board_netlist(design)[0], "schematic")
    weak = Evidence(Level.INFERRED, oracle="fake 1.0", hypotheses=("H-FAKE-SHEET",))
    result = _schematic_stage(_oracle_with(design, same, evidence=weak), design)
    assert "H-FAKE-SHEET" in result.evidence.hypotheses and result.evidence.oracle == "fake 1.0"


def test_schematic_file_of_a_project(tmp_path: Path) -> None:
    assert schematic_file(project()) == "" and schematic_file(project(schematic=True)) == "board.kicad_sch"
    board = tmp_path / "x.kicad_pcb"
    board.write_text("", encoding="utf-8")
    sheet = tmp_path / "x.kicad_sch"
    sheet.write_text("", encoding="utf-8")
    beside = ProjectSet(tmp_path, "x.kicad_pcb", {"x.kicad_pcb": board})
    assert schematic_file(beside) == ""  # the copy set decides (c0062 plans the schematic into it)
    listed = ProjectSet(tmp_path, "x.kicad_pcb", {"x.kicad_pcb": board, "x.kicad_sch": sheet})
    assert schematic_file(listed) == "x.kicad_sch"


def _several() -> tuple[Design, Component, Net]:
    """``U1`` with the pins 1 and 3, pin 3 bonded to the pads 3 and EP and on ``GND`` (change c0123)."""
    u1 = Component(
        id="cmp_00000000-0000-4000-8000-0000000000a1",
        ref="U1",
        pins=(
            Pin(id="pin_00000000-0000-4000-8000-0000000000a1", number="1"),
            Pin(id="pin_00000000-0000-4000-8000-0000000000a3", number="3"),
        ),
        pin_pad_map=(("3", "3"), ("3", "EP")),
    )
    gnd = Net(id="net_00000000-0000-4000-8000-0000000000a1", name="GND", members=(PinRef(u1.id, "3"),))
    model = dataclasses.replace(Design.new("m", seed=0), circuit=Circuit(components=(u1,), nets=(gnd,)))
    return model, u1, gnd


def test_several_pads_of_one_pin_are_elements() -> None:
    """Capability verification-loop, "Assignment comparison names every pad of a pin", scenario "Pin of
    two pads"."""
    model, _u1, gnd = _several()
    listed = model_netlist(model)
    assert listed == PadNetList(
        "model",
        (PadAssignment("U1-3", gnd.id), PadAssignment("U1-EP", gnd.id), PadAssignment("U1-1", NO_NET)),
    )
    board = PadNetList(
        "board", (PadAssignment("U1-1", NO_NET), PadAssignment("U1-3", "n"), PadAssignment("U1-EP", "n"))
    )
    result = compare(listed, board, min_pins=1)
    assert (result.common, result.only_a, result.only_b, result.differences) == (3, (), (), ())
    # a board that leaves the further pad off the net differs
    split = PadNetList(
        "board", (PadAssignment("U1-1", NO_NET), PadAssignment("U1-3", "n"), PadAssignment("U1-EP", NO_NET))
    )
    assert compare(listed, split, min_pins=1).differences


def test_open_pin_of_several_pads_is_one_block() -> None:
    """Scenario "Open pin of two pads": the pads of a pin are bonded, so on no net they still are one
    block, as a board that names their net (``unconnected-(…)`` or ``Net-(…)``) has them."""
    model, u1, _gnd = _several()
    opened = dataclasses.replace(model, circuit=Circuit(components=(u1,)))
    listed = model_netlist(opened)
    label = bonded_label(u1, "3")
    assert listed == PadNetList(
        "model", (PadAssignment("U1-1", NO_NET), PadAssignment("U1-3", label), PadAssignment("U1-EP", label))
    )
    assert "U1" in label and "|" not in label and net_text(label, {}) == label
    joined = PadNetList(
        "board", (PadAssignment("U1-1", NO_NET), PadAssignment("U1-3", "x"), PadAssignment("U1-EP", "x"))
    )
    assert compare(listed, joined, min_pins=1).differences == ()
