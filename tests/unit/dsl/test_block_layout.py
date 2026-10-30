# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Block poses, layout strategies and block layout reuse in the DSL (change c0255; capability design-dsl,
"Block poses in the DSL", "Layout strategies in the DSL" and "Block layout reuse in the DSL")."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.dsl import Design, DslError, block, column, grid, mm, pack, row
from fenolite.dsl.relative import Pose, RelativeRequest, Reuse, Strategy, block_layouts, frames, has_layout


def _design() -> Design:
    design = Design("blk")
    design.board(mm(60), mm(40))
    return design


@block
def buck(b):  # type: ignore[no-untyped-def]
    u = b.part("U", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="1u")
    u.place(mm(0), mm(0))
    inductor = b.part("L", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="1u")
    inductor.place(right_of=u, gap=mm(1))
    b.part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1k")
    b.layout(row(gap=mm(1)))


def test_instance_strategy_wins() -> None:
    design = _design()
    design.use(buck, "buck1")
    p2 = design.use(buck, "buck2")
    p2.layout(column())
    layouts = block_layouts(design)
    assert layouts["buck1"].layout == Strategy("row", 1_000_000) and layouts["buck1"].source == "body"
    assert layouts["buck2"].layout == Strategy("column") and layouts["buck2"].source == "instance"
    assert has_layout(design)


def test_a_reference_out_of_the_block() -> None:
    design = _design()
    mcu = design.part("MCU", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="1u")

    @block
    def stray(b):  # type: ignore[no-untyped-def]
        part = b.part("L", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="1u")
        part.place(right_of=mcu)

    with pytest.raises(DslError, match="a block's parts reference only parts of the same block"):
        design.use(stray, "s1")


def test_the_board_is_out_of_a_block() -> None:
    design = _design()

    @block
    def edge(b):  # type: ignore[no-untyped-def]
        part = b.part("L", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="1u")
        part.place(left=design.board_ref.left, top=mm(0))

    with pytest.raises(DslError, match="the board is outside block"):
        design.use(edge, "e1")


def test_strategy_and_reuse_together() -> None:
    design = _design()

    @block
    def twice(b):  # type: ignore[no-untyped-def]
        b.layout(row())
        b.layout(reuse="buck.kicad_pcb")

    with pytest.raises(DslError, match="a frame has one strategy"):
        design.use(twice, "t1")


def test_reuse_is_relative_to_the_file_of_the_block() -> None:
    design = _design()

    @block
    def reused(b):  # type: ignore[no-untyped-def]
        b.layout(reuse="blocks/buck.kicad_pcb", copper=True)

    design.use(reused, "r1")
    held = block_layouts(design)["r1"].layout
    assert isinstance(held, Reuse) and held.path == "blocks/buck.kicad_pcb" and held.copper
    assert held.root == str(Path(__file__).resolve().parent)
    instance = design.use(reused, "r2")
    instance.layout(row())
    with pytest.raises(DslError, match="a frame has one strategy"):
        instance.layout(row())
    with pytest.raises(DslError, match="copper must be a bool"):
        design.use(reused, "r3").layout(reuse="x.kicad_pcb", copper="yes")


def test_poses_absolute_and_relative() -> None:
    design = _design()
    p1 = design.use(buck, "buck1")
    p1.place(mm(10), mm(8), rot=90)
    p2 = design.use(buck, "buck2")
    p2.place(below=p1, gap=mm(2), align="start")
    layouts = block_layouts(design)
    assert layouts["buck1"].pose == Pose(10_000_000, 8_000_000, 90_000_000, False)
    pose = layouts["buck2"].pose
    assert isinstance(pose, RelativeRequest) and pose.subject == "block"
    assert pose.text() == "below=buck1 gap=2mm align=start"
    with pytest.raises(DslError, match="already placed"):
        p1.place(mm(1), mm(1))
    with pytest.raises(DslError, match="needs x and y"):
        design.use(buck, "buck3").place(mm(1))


def test_strategy_arguments() -> None:
    assert grid(3, gap=mm(1)).text() == "grid(columns=3, gap=1mm)"
    assert pack(mm(10)).text() == "pack(width=10mm)"
    assert row(align="center", at=(mm(1), mm(2))).text() == "row(align=center, at=(1mm, 2mm))"
    for call in (lambda: grid(0), lambda: pack(mm(0)), lambda: row(gap=mm(-1)), lambda: column(align="up")):
        with pytest.raises(DslError):
            call()
    design = _design()
    design.layout(row())
    with pytest.raises(DslError, match="a frame has one strategy"):
        design.layout(column())
    with pytest.raises(DslError, match="reuse= belongs to a block|takes row"):
        _design().layout("row")


def test_frames_in_creation_order() -> None:
    design = _design()
    design.part("J1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1k")
    design.use(buck, "buck1")
    found = frames(design)
    assert found[""].items == (("part", "J1"), ("block", "buck1"))
    assert found["buck1"].items == (("part", "buck1/U"), ("part", "buck1/L"), ("part", "buck1/R1"))


def test_port_names_reserved_for_layout() -> None:
    design = _design()

    @block
    def bad(b):  # type: ignore[no-untyped-def]
        b.port("left")

    with pytest.raises(DslError, match="attribute of a block instance"):
        design.use(bad, "b1")
