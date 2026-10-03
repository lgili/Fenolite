# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The assignment comparison (capability verification-loop, "Assignment compare stage"; change c0020)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from fakes import FakeFullOracle, FakeOracle, netlist, netlist_outcome, project, validation

from fenolite.backends.base import PadAssignment, PadNetList
from fenolite.backends.kicad.pcb import read_board
from fenolite.checks.assignment_compare import (
    NO_NET,
    assignment_stage,
    board_netlist,
    compare,
    model_netlist,
)
from fenolite.core.evidence import Level
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


def test_no_net_is_one_class() -> None:
    a = netlist("a", ("A-1", NO_NET), ("A-2", NO_NET), ("A-3", "x"))
    b = netlist("b", ("A-1", "N/C"), ("A-2", "N/C"), ("A-3", "N1"))
    assert compare(a, b).differences == ()
    lost = netlist("b", ("A-1", "N/C"), ("A-2", "N/C"), ("A-3", "N/C"))
    assert [d.element for d in compare(a, lost).differences] == ["A-3"]


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
