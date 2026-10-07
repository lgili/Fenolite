# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The four levels of a design comparison (capability design-equivalence, "Level 1 compares components"
to "Level 4 compares placement", and the scenarios of "Equivalence package" about ``compare_designs``)."""

from __future__ import annotations

import dataclasses

import _cases
import pytest

from fenolite.checks.equivalence import (
    LEVEL_NAMES,
    LEVELS,
    EquivalenceReport,
    Tolerances,
    compare_designs,
    difference_issues,
    max_level,
)
from fenolite.checks.equivalence.levels import level_components, level_netlist
from fenolite.core.coords import Point, Size


def _kinds(report: EquivalenceReport, level: int) -> list[tuple[str, str]]:
    return [(d.kind, d.where) for d in report.levels[level - 1].differences]


# --- level 1 ---------------------------------------------------------------------------------------


def test_level1_missing_and_changed_components() -> None:
    a = _cases.design([("R1", "10k"), ("R2", "1k"), ("C1", "")])
    b = _cases.design([("R1", "10k"), ("R2", "2k2"), ("D1", "")])
    result, refs = level_components(a, b)
    assert refs == ("R1", "R2") and result.compared == 2 and result.name == "components"
    found = {(d.kind, d.where): (d.field, d.a, d.b) for d in result.differences}
    assert found == {
        ("component-missing", "C1"): ("ref", "C1", ""),
        ("component-missing", "D1"): ("ref", "", "D1"),
        ("value", "R2"): ("value", "1k", "2k2"),
    }
    assert result.summary == {"components": {"a": 3, "b": 3}, "ignored": 0}


def test_level1_dnp_and_exact_text() -> None:
    a = _cases.design([("R1", "10k"), ("R2", "1k")])
    b = _cases.with_component(_cases.design([("R1", "10K"), ("R2", "1k ")]), "R1", dnp=True)
    result, _ = level_components(a, b)
    assert [(d.kind, d.where, d.a, d.b) for d in result.differences] == [
        ("dnp", "R1", "false", "true"),
        ("value", "R1", "10k", "10K"),
        ("value", "R2", "1k", "1k "),
    ]


def test_level1_duplicate_references_are_not_compared() -> None:
    pads = {"REF**": [_cases.pad("1")], "R1": [_cases.pad("1")]}
    a = _cases.design([("REF**", ""), ("REF**", "x"), ("R1", "")], pads, name="a")
    b = _cases.design([("REF**", ""), ("R1", "")], pads, name="b")
    report = compare_designs(a, b, level=4)
    assert [(d.level, d.kind, d.where, d.a, d.b) for d in report.differences] == [
        (1, "ref-ambiguous", "REF**", "2", "1")
    ]
    assert [level.compared for level in report.levels] == [1, 1, 1, 1]
    ignored = compare_designs(a, b, level=4, ignore_refs=("REF[*][*]",))
    assert ignored.equivalent and ignored.differences == ()
    assert ignored.levels[0].summary["ignored"] == 1


def test_level1_empty_reference_is_ambiguous() -> None:
    a = _cases.design([("", "x"), ("R1", "")])
    result, refs = level_components(a, a)
    assert [(d.kind, d.where, d.a, d.b) for d in result.differences] == [("ref-ambiguous", "", "1", "1")]
    assert refs == ("R1",)


# --- level 2 ---------------------------------------------------------------------------------------


def test_level2_reassigned_pad_is_located() -> None:
    a = _cases.two_layer()
    pads = {p.number: p for p in _cases.footprint(a, "R1").pads}
    assert pads["1"].net_id != pads["2"].net_id
    b = _cases.with_pad(a, "R1", "1", net_id=pads["2"].net_id)
    report = compare_designs(a, b, level=2)
    assert _kinds(report, 1) == [] and _kinds(report, 2) == [("net", "R1-1")]
    (difference,) = report.differences
    names = {n.id: n.name for n in a.circuit.nets}
    assert (difference.field, difference.a, difference.b) == (
        "net", names[pads["1"].net_id or ""], names[pads["2"].net_id or ""],
    )  # fmt: skip
    (issue,) = difference_issues(report)
    assert (issue.code, issue.severity, issue.where) == ("netlist.assignment-differs", "error", "R1-1")
    assert not report.equivalent


def test_level2_renamed_nets_are_equivalent() -> None:
    a = _cases.two_layer()
    b = _cases.renamed_nets(a)
    assert {n.id for n in a.circuit.nets}.isdisjoint(n.id for n in b.circuit.nets)
    result = level_netlist(a, b, ("D1", "R1"))
    assert result.differences == () and result.compared == 4
    assert result.summary["renamed"] == len(a.circuit.nets)
    assert level_netlist(a, a, ("D1", "R1")).summary["renamed"] == 0


def test_level2_circuit_against_board() -> None:
    board = _cases.two_layer()
    circuit = _cases.circuit_only(board)
    assert max_level(circuit, board) == 2
    report = compare_designs(circuit, board, level=2)
    assert report.equivalent and report.differences == ()
    assert report.levels[1].summary["sources"] == {"a": "circuit", "b": "board"}
    assert report.levels[1].compared == 4


def test_level2_pin_on_one_side_only() -> None:
    a = _cases.two_layer()
    b = _cases.without_pad(a, "D1", "2")
    result = level_netlist(a, b, ("D1", "R1"))
    assert [(d.kind, d.where, d.field, d.a, d.b) for d in result.differences] == [
        ("pin-missing", "D1-2", "pin", "2", "")
    ]
    back = level_netlist(b, a, ("D1", "R1"))
    assert [(d.kind, d.where, d.a, d.b) for d in back.differences] == [("pin-missing", "D1-2", "", "2")]


def test_level2_scope_and_unnumbered_pads() -> None:
    a = _cases.two_layer()
    pads = {p.number: p for p in _cases.footprint(a, "R1").pads}
    b = _cases.with_pad(a, "R1", "1", net_id=pads["2"].net_id)
    assert level_netlist(a, b, ("D1",)).differences == ()  # R1 is outside the compared components
    bare = _cases.with_pad(a, "D1", "2", number="")
    result = level_netlist(bare, bare, ("D1", "R1"))
    assert result.summary["unnumbered"] == {"a": 1, "b": 1} and result.compared == 3


def test_level2_single_pin_nets_and_pads_on_no_net() -> None:
    parts = [("R1", ""), ("R2", "")]
    pads = {"R1": [_cases.pad("1"), _cases.pad("2", 1)], "R2": [_cases.pad("1"), _cases.pad("2", 1)]}
    a = _cases.netted(_cases.design(parts, pads, name="a"), {"X": [("R1", "1")], "Y": [("R2", "1")]})
    b = _cases.netted(_cases.design(parts, pads, name="b"), {"X": [("R1", "1"), ("R2", "1")]})
    result = level_netlist(a, b, ("R1", "R2"))
    assert {d.kind for d in result.differences} == {"net"} and result.differences
    free = _cases.netted(_cases.design(parts, pads, name="c"), {"X": [("R1", "1")]})
    result = level_netlist(a, free, ("R1", "R2"))
    assert [(d.where, d.a, d.b) for d in result.differences] == [("R2-1", "Y", "no net")]


# --- level 3 ---------------------------------------------------------------------------------------


def test_level3_changed_pad_is_located() -> None:
    a = _cases.two_layer()
    pad = next(p for p in _cases.footprint(a, "D1").pads if p.number == "1")
    assert pad.drill is not None
    b = _cases.with_pad(a, "D1", "1", size=Size(pad.size.w + 100, pad.size.h), drill=None)
    exact = compare_designs(a, b, level=3)
    assert _kinds(exact, 3) == [("pad-drill", "D1-1"), ("pad-size", "D1-1")]
    drill, size = exact.levels[2].differences
    assert (drill.field, drill.a, drill.b) == ("drill", str(pad.drill), "")
    assert (size.field, size.a, size.b) == (
        "size", f"{pad.size.w}x{pad.size.h}", f"{pad.size.w + 100}x{pad.size.h}",
    )  # fmt: skip
    loose = compare_designs(a, b, level=3, tolerances=Tolerances(length_nm=100))
    assert _kinds(loose, 3) == [("pad-drill", "D1-1")]
    assert exact.levels[2].compared == 4 and exact.levels[2].summary == {"footprints": 2, "copper_unknown": 0}


def test_level3_placement_does_not_reach_it() -> None:
    a = _cases.two_layer()
    found = _cases.footprint(a, "R1")
    b = _cases.placed(
        a, "R1", position=Point(found.position.x + 1_000_000, found.position.y),
        rotation=found.rotation + 90_000_000, side="bottom",
    )  # fmt: skip
    report = compare_designs(a, b, level=3)
    assert report.equivalent and report.differences == ()
    assert _kinds(compare_designs(a, b, level=4), 4) == [
        ("position", "R1"),
        ("rotation", "R1"),
        ("side", "R1"),
    ]


def test_level3_two_pads_of_one_number() -> None:
    two = [_cases.pad("1", 0), _cases.pad("1", 10), _cases.pad("2", 20)]
    three = [
        _cases.pad("1", 0),
        _cases.pad("1", 10),
        _cases.pad("1", 30, shape="circle"),
        _cases.pad("2", 20),
    ]
    a = _cases.design([("U1", "")], {"U1": two}, name="a")
    b = _cases.design([("U1", "")], {"U1": three}, name="b")
    report = compare_designs(a, b, level=3)
    assert [(d.kind, d.where, d.field, d.a, d.b) for d in report.levels[2].differences] == [
        ("pad-missing", "U1-1", "pad", "2", "3")
    ]
    assert report.levels[2].compared == 1


def test_level3_pads_of_one_number_pair_by_position() -> None:
    one = [_cases.pad("1", 10, 5), _cases.pad("1", 0, 7), _cases.pad("1", 0, 3)]
    a = _cases.design([("U1", "")], {"U1": one}, name="a")
    b = _cases.design([("U1", "")], {"U1": list(reversed(one))}, name="b")
    assert compare_designs(a, b, level=3).equivalent


def test_level3_unknown_layer_name() -> None:
    a = _cases.design([("R1", "")], {"R1": [_cases.pad("1", layers=("Top", "Elsewhere"))]}, name="a")
    b = _cases.design([("R1", "")], {"R1": [_cases.pad("1", layers=("Bottom",))]}, name="b")
    result = compare_designs(a, b, level=3).levels[2]
    assert result.differences == () and result.summary["copper_unknown"] == 1
    known = _cases.design([("R1", "")], {"R1": [_cases.pad("1", layers=("Top", "Mask"))]}, name="c")
    (difference,) = compare_designs(known, b, level=3).levels[2].differences
    assert (difference.kind, difference.field, difference.a, difference.b) == (
        "pad-copper", "layers", "top", "bottom",
    )  # fmt: skip


def test_level3_footprint_name_kind_shape_position() -> None:
    a = _cases.design(
        [("R1", ""), ("R2", "")], {"R1": [_cases.pad("1")], "R2": [_cases.pad("", 3, 4)]}, name="a"
    )
    b = _cases.design(
        [("R1", ""), ("R2", "")],
        {"R1": [_cases.pad("1", 0, 2, kind="thru_hole", shape="oval")], "R2": [_cases.pad("", 3, 5)]},
        name="b",
    )
    b = _cases.placed(b, "R1", lib_ref="Other:FP_R1")
    # the library nickname is not part of the name
    assert "footprint-name" not in {d.kind for d in compare_designs(a, b, level=3).differences}
    b = _cases.placed(b, "R1", lib_ref="Other:FP_R1_alt")
    assert _kinds(compare_designs(a, b, level=3), 3) == [
        ("footprint-name", "R1"),
        ("pad-kind", "R1-1"),
        ("pad-position", "R1-1"),
        ("pad-shape", "R1-1"),
        ("pad-position", "R2-@3,4"),
    ]
    assert _kinds(compare_designs(a, b, level=3, tolerances=Tolerances(length_nm=2)), 3) == [
        ("footprint-name", "R1"),
        ("pad-kind", "R1-1"),
        ("pad-shape", "R1-1"),
    ]


def test_level3_component_placed_on_one_side_only() -> None:
    a = _cases.design([("R1", ""), ("R2", "")], {"R1": [_cases.pad("1")], "R2": [_cases.pad("1")]}, name="a")
    b = _cases.design([("R1", ""), ("R2", "")], {"R1": [_cases.pad("1")]}, name="b")
    report = compare_designs(a, b, level=4)
    assert [(d.level, d.kind, d.where, d.field, d.a, d.b) for d in report.differences] == [
        (2, "pin-missing", "R2-1", "pin", "1", ""),
        (3, "footprint-missing", "R2", "footprint", "FP_R2", ""),
    ]
    assert report.levels[3].compared == 1


# --- level 4 ---------------------------------------------------------------------------------------


def test_level4_moved_footprint_is_located() -> None:
    a = _cases.two_layer()
    found = _cases.footprint(a, "R1")
    b = _cases.placed(
        a, "R1", position=Point(found.position.x + 1, found.position.y), rotation=found.rotation + 1
    )
    exact = compare_designs(a, b, level=4)
    assert _kinds(exact, 4) == [("position", "R1"), ("rotation", "R1")] and _kinds(exact, 3) == []
    position, rotation = exact.levels[3].differences
    assert (position.a, position.b) == (
        f"{found.position.x},{found.position.y}", f"{found.position.x + 1},{found.position.y}",
    )  # fmt: skip
    assert (rotation.a, rotation.b) == (str(found.rotation), str(found.rotation + 1))
    loose = compare_designs(a, b, level=4, tolerances=Tolerances(length_nm=1, angle_udeg=1))
    assert loose.equivalent and loose.levels[3].compared == 2
    assert loose.levels[3].summary == {"frame": "absolute", "translation": [0, 0]}


def test_level4_flipped_footprint() -> None:
    a = _cases.two_layer()
    assert _cases.footprint(a, "R1").side == "top"
    b = _cases.placed(a, "R1", side="bottom")
    for tolerances in (Tolerances(), Tolerances(length_nm=10**9, angle_udeg=10**9)):
        (difference,) = compare_designs(a, b, level=4, tolerances=tolerances).differences
        assert (difference.level, difference.kind, difference.where) == (4, "side", "R1")
        assert (difference.field, difference.a, difference.b) == ("side", "top", "bottom")


def test_level4_rotation_wraps() -> None:
    a = _cases.two_layer()
    b = _cases.placed(a, "R1", rotation=_cases.footprint(a, "R1").rotation - 360_000_000)
    assert compare_designs(a, b, level=4).equivalent


# --- all levels ------------------------------------------------------------------------------------


def test_a_design_compared_with_itself() -> None:
    design = _cases.two_layer()
    report = compare_designs(design, design, level=4)
    assert [level.level for level in report.levels] == [1, 2, 3, 4]
    assert [level.name for level in report.levels] == [LEVEL_NAMES[n] for n in LEVELS[:4]]
    assert all(level.differences == () and level.excluded == () for level in report.levels)
    assert report.equivalent and report.translation == Point(0, 0) and report.frame == "absolute"
    assert [level.compared for level in report.levels] == [2, 4, 4, 2]
    assert difference_issues(report) == ()
    assert [len(compare_designs(design, design, level=n).levels) for n in LEVELS] == [1, 2, 3, 4, 5]


def test_level_above_what_both_sides_hold() -> None:
    board = _cases.two_layer()
    bare = _cases.circuit_only(board)
    assert board.board is not None
    empty = dataclasses.replace(board, board=dataclasses.replace(board.board, footprints=()))
    assert (max_level(board, board), max_level(bare, board), max_level(board, empty)) == (5, 2, 2)
    with pytest.raises(ValueError, match=r"side a holds none.*highest level available is 2"):
        compare_designs(bare, board, level=3)
    with pytest.raises(ValueError, match="side b holds none"):
        compare_designs(board, empty, level=4)
    with pytest.raises(ValueError, match="side a and b holds none"):
        compare_designs(bare, empty, level=3)
    for level in (0, 6, True, "4"):
        with pytest.raises(ValueError, match="level is one of 1, 2, 3, 4, 5"):
            compare_designs(board, board, level=level)  # type: ignore[arg-type]


def test_output_order_is_stable() -> None:
    parts = [("R2", "1k"), ("R10", "1k"), ("C1", "1n"), ("U1", "")]
    pads = {ref: [_cases.pad("1"), _cases.pad("2", 5)] for ref, _ in parts}
    a = _cases.design(parts, pads, name="a")
    b = _cases.design([(ref, value + "x") for ref, value in parts[:3]] + [parts[3]], pads, name="b")
    b = _cases.placed(b, "R2", side="bottom")
    first = compare_designs(a, b, level=4)
    second = compare_designs(_cases.reversed_order(a), _cases.reversed_order(b), level=4)
    assert first == second
    assert [d.where for d in first.levels[0].differences] == ["C1", "R10", "R2"]
    assert _kinds(first, 4) == [("side", "R2")]


def test_level2_several_pads_of_one_pin() -> None:
    """Capability design-equivalence, "Level 2 names every pad of a pin", scenario "Circuit against
    board" (change c0123)."""
    board = _cases.netted(
        _cases.design([("U1", "IC")], {"U1": [_cases.pad("1"), _cases.pad("3", 1), _cases.pad("EP", 2)]}),
        {"GND": [("U1", "3"), ("U1", "EP")]},
    )
    circuit = _cases.circuit_only(board)

    # the circuit side says the same with one pin bonded to two pads
    def bonded(component: object) -> object:
        pins = tuple(pin for pin in component.pins if pin.number != "EP")  # type: ignore[attr-defined]
        return dataclasses.replace(component, pins=pins, pin_pad_map=(("3", "3"), ("3", "EP")))  # type: ignore[type-var]

    nets = tuple(
        dataclasses.replace(net, members=tuple(m for m in net.members if m.pin != "EP"))
        for net in circuit.circuit.nets
    )
    mapped = dataclasses.replace(
        circuit,
        circuit=dataclasses.replace(
            circuit.circuit,
            components=tuple(bonded(c) for c in circuit.circuit.components),
            nets=nets,  # type: ignore[misc]
        ),
    )
    report = compare_designs(mapped, board, level=2)
    assert report.equivalent and report.differences == () and report.levels[1].compared == 3
    moved = _cases.netted(board, {"OTHER": [("U1", "EP")]})
    found = compare_designs(mapped, moved, level=2).differences
    assert [(d.kind, d.where) for d in found if d.level == 2] and all(
        "EP" in d.where or "3" in d.where for d in found
    )
    # level 3 reads no map: two boards compare alike whatever the circuit's map says
    with_map = _cases.with_component(board, "U1", pin_pad_map=(("3", "3"), ("3", "EP")))
    assert compare_designs(with_map, board, level=3).differences == ()
