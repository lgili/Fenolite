# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The distance through the laminate between copper on two layers (capability board-analyses,
"Insulation between layers"; ``H-G-AN-INSUL``).

The depths of the layers come from ``Stackup.depth`` of change c0101, which the model of this base does
not have: ``layer_depths`` then returns ``None``. The tests give the depths through that one seam, as the
stack-up of the scenarios states them. Every thickness and distance here is illustrative.
"""

from __future__ import annotations

import dataclasses

import pytest
from _analysis import MM, at
from _coppercheck import Copper, ident

from fenolite.analysis import analyze_distances, distance, load_requirements
from fenolite.analysis.insulation import EVIDENCE, insulation_between, layer_depths
from fenolite.analysis.report import DistanceRow
from fenolite.analysis.requirements import SCHEMA
from fenolite.core.evidence import Level
from fenolite.model.board import StackLayer, Stackup
from fenolite.model.design import Design

STACK = (
    ("F.Cu", "copper", 35_000), ("prepreg 1", "dielectric", 200_000), ("In1.Cu", "copper", 35_000),
    ("core", "dielectric", 1_000_000), ("In2.Cu", "copper", 35_000), ("prepreg 2", "dielectric", 200_000),
    ("B.Cu", "copper", 35_000),
)  # fmt: skip
DEPTHS = {
    "F.Cu": (0, 35_000),
    "In1.Cu": (235_000, 270_000),
    "In2.Cu": (1_270_000, 1_305_000),
    "B.Cu": (1_505_000, 1_540_000),
}
"""The depths of the faces of the copper layers of ``STACK``, as ``Stackup.depth`` of c0101 defines them."""
PAIR = (("HV", "LV"),)


def required(insulation_nm: int) -> str:
    row_text = f'[[distance]]\na = {{ net = "HV" }}\nb = {{ net = "LV" }}\ninsulation_nm = {insulation_nm}\n'
    return f'schema = "{SCHEMA}"\n' + row_text


def with_stack(design: Design) -> Design:
    assert design.board is not None
    layers = tuple(
        StackLayer(id=ident("stk", n), name=name, kind=kind, thickness=thickness)  # type: ignore[arg-type]
        for n, (name, kind, thickness) in enumerate(STACK)
    )
    board = dataclasses.replace(design.board, stackup=Stackup(id=ident("stu", 1), layers=layers))
    return dataclasses.replace(design, board=board)


def over(upper: str, lower: str, offset: float = 0.0) -> Design:
    """A 1 mm track of ``HV`` on ``upper`` and one of ``LV`` on ``lower``, the second moved by ``offset``."""
    made = Copper(layers=4)
    made.track("HV", at(0, 0), at(10, 0), width=MM, layer=upper)
    made.track("LV", at(0, offset), at(10, offset), width=MM, layer=lower)
    return with_stack(made.build())


def row(report: object) -> DistanceRow:
    (found,) = report.rows  # type: ignore[attr-defined]
    assert isinstance(found, DistanceRow)
    return found


def test_overlap_copper_over_copper(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Copper over copper"."""
    monkeypatch.setattr(distance, "layer_depths", lambda board: DEPTHS)
    design = over("In1.Cu", "In2.Cu")
    report = analyze_distances(design, pads=None, boundary=None, pairs=PAIR, insulation=True)
    found = row(report)
    assert found.insulation is not None and (found.insulation.low, found.insulation.high) == (MM, MM)
    assert found.insulation.layer == "In1.Cu/In2.Cu" and found.sheets == 1
    assert "H-G-AN-INSUL" in report.evidence.hypotheses and not report.issues
    text = required(1200000)
    judged = analyze_distances(
        design, pads=None, boundary=None, requirements=load_requirements(text), insulation=True
    )
    assert [(f.code, f.severity) for f in judged.issues] == [("analysis.insulation-below", "error")]
    met = load_requirements(text.replace("1200000", "1000000"))
    assert not analyze_distances(design, pads=None, boundary=None, requirements=met, insulation=True).issues
    # without the kind the row holds no insulation
    plain = row(analyze_distances(design, pads=None, boundary=None, pairs=PAIR))
    assert plain.insulation is None and plain.sheets is None


def test_offset_in_plan_view(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Offset in plan view": edges 0.3 mm apart, 0.2 mm of prepreg between."""
    monkeypatch.setattr(distance, "layer_depths", lambda board: DEPTHS)
    found = row(
        analyze_distances(over("F.Cu", "In1.Cu", 1.3), pads=None, boundary=None, pairs=PAIR, insulation=True)
    )
    assert found.insulation is not None and (found.insulation.low, found.insulation.high) == (
        360_555,
        360_556,
    )
    assert found.sheets == 1 and found.insulation.layer == "F.Cu/In1.Cu"
    undecided = required(360556)
    report = analyze_distances(
        over("F.Cu", "In1.Cu", 1.3),
        pads=None,
        boundary=None,
        requirements=load_requirements(undecided),
        insulation=True,
    )
    assert [f.code for f in report.issues] == ["analysis.insulation-undecided"]
    # a search distance finds the pair through the laminate, not on a layer
    near = analyze_distances(
        over("F.Cu", "In1.Cu", 1.3), pads=None, boundary=None, within=400_000, insulation=True
    )
    assert [(r.net_a, r.net_b) for r in near.rows] == [("HV", "LV")]  # type: ignore[union-attr]
    assert not analyze_distances(over("F.Cu", "In1.Cu", 1.3), pads=None, boundary=None, within=400_000).rows


def test_no_stack_up_gives_no_value() -> None:
    """Scenario "No stack-up": on this base no layer has a depth, whatever the board holds."""
    design = over("In1.Cu", "In2.Cu")
    assert design.board is not None and layer_depths(design.board) is None
    report = analyze_distances(design, pads=None, boundary=None, pairs=PAIR, insulation=True)
    found = row(report)
    assert found.insulation is None and found.sheets is None
    (missing,) = report.issues
    assert (missing.code, missing.where) == (
        "analysis.input-missing",
        "stack-up",
    ) and "1 pair" in missing.message
    assert report.evidence.level is Level.UNVERIFIED


def test_layer_depths_reads_the_method_of_the_stack_up() -> None:
    class Stack:
        def depth(self, name: str) -> tuple[int, int]:
            return DEPTHS[name]

    class Board:
        stackup = Stack()
        layers = over("F.Cu", "B.Cu").board.layers  # type: ignore[union-attr]

    assert layer_depths(Board()) == DEPTHS  # type: ignore[arg-type]
    assert EVIDENCE.level is Level.INFERRED and EVIDENCE.hypotheses == ("H-G-AN-INSUL",)


def test_insulation_between_takes_the_smallest_over_the_layer_pairs() -> None:
    from fenolite.analysis.copper import net_copper

    made = Copper(layers=4)
    made.track("HV", at(0, 0), at(10, 0), width=MM, layer="F.Cu")
    made.track("HV", at(0, 0), at(10, 0), width=MM, layer="In1.Cu")
    made.track("LV", at(0, 5), at(10, 5), width=MM, layer="In2.Cu")
    made.track("LV", at(0, 0), at(10, 0), width=MM, layer="B.Cu")
    design = with_stack(made.build())
    assert design.board is not None
    copper = net_copper(design, pads=None)
    measure, sheets = insulation_between(
        copper.by_net["HV"], copper.by_net["LV"], depths=DEPTHS, stackup=design.board.stackup
    )
    # In1 over B: 1 235 µm straight down, against 4 mm in plan to In2
    assert measure is not None and measure.low == 1_235_000 and measure.layer == "In1.Cu/B.Cu" and sheets == 2
    assert insulation_between(copper.by_net["HV"], (), depths=DEPTHS, stackup=None) == (None, None)
