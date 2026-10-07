# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``Design.hole()`` and its generated definitions (capability design-dsl, "Board holes in the DSL"; change
c0102)."""

from __future__ import annotations

import pytest

from fenolite.core.coords import Point, Size
from fenolite.dsl import (
    Design,
    DslError,
    Footprint,
    Net,
    Part,
    Placement,
    connect,
    holes,
    mm,
    placements,
    to_model,
)
from fenolite.model.circuit import PinRef

MM = 1_000_000


def board() -> Design:
    design = Design("holes")
    design.board(mm(50), mm(30))
    return design


def test_a_round_hole_that_is_not_plated() -> None:
    design = board()
    part = design.hole("H1", mm(3), mm(3), drill=mm(3.2))
    assert isinstance(part, Part) and design.parts["H1"] is part
    assert part.lib_id == "Fenolite_Holes:Hole" and part.footprint == "Fenolite_Holes:NPTH_3.2mm"
    assert part.value == "NPTH_3.2mm"
    assert placements(design)["H1"] == Placement(Point(103_000_000, 103_000_000), 0, "top", True)
    definition = design.footprints["Fenolite_Holes:NPTH_3.2mm"].definition
    (pad,) = definition.pads
    assert (pad.number, pad.kind, pad.shape) == ("", "np_thru_hole", "circle")
    assert pad.size == Size(3_200_000, 3_200_000) and pad.drill == 3_200_000 and pad.padstack is None
    assert pad.position == Point(0, 0) and pad.layers == ("*.Cu", "*.Mask")
    assert definition.kind == "unspecified"
    assert definition.flags == ("exclude_from_pos_files", "exclude_from_bom")
    yards = [(g.kind, g.layer, g.points, g.width) for g in definition.graphics]
    circle = (Point(0, 0), Point(1_600_000, 0))
    assert yards == [("circle", "F.CrtYd", circle, 50_000), ("circle", "B.CrtYd", circle, 50_000)]
    symbol = design.symbols["Fenolite_Holes:Hole"].definition  # type: ignore[attr-defined]
    assert symbol.pins == () and symbol.in_bom is False and symbol.on_board is True
    assert symbol.reference == "H" and symbol.lib_id == "Fenolite_Holes:Hole"


def test_a_plated_slot_on_a_net() -> None:
    design = board()
    gnd = Net("GND")
    h2 = design.hole("H2", mm(10), mm(3), drill=mm(1), length=mm(3), pad=mm(2), rot=90)
    connect(gnd, h2[1])
    assert h2.lib_id == "Fenolite_Holes:Hole_Pad"
    assert h2.footprint == "Fenolite_Holes:PTH_Slot_1x3mm_Pad_2mm"
    (pad,) = design.footprints[h2.footprint].definition.pads
    assert (pad.number, pad.kind, pad.shape) == ("1", "thru_hole", "oval")
    assert pad.size == Size(4_000_000, 2_000_000) and pad.drill == 1_000_000
    assert pad.padstack is not None
    assert (pad.padstack.hole_shape, pad.padstack.hole_length, pad.padstack.hole_rotation) == (
        "slot",
        3_000_000,
        0,
    )
    symbol = design.symbols["Fenolite_Holes:Hole_Pad"].definition  # type: ignore[attr-defined]
    assert [(pin.number, pin.etype) for pin in symbol.pins] == [("1", "passive")] and not symbol.in_bom
    model = to_model(design)
    h2_id = next(c.id for c in model.circuit.components if c.ref == "H2")
    assert model.nets_by_name["GND"].members == (PinRef(h2_id, "1"),)
    assert placements(design)["H2"].rotation == 90_000_000
    # the courtyard of a slot exceeds its copper's length by as much as it exceeds its width: nothing here
    rect = (Point(-2_000_000, -1_000_000), Point(2_000_000, 1_000_000))
    assert [g.points for g in design.footprints[h2.footprint].definition.graphics] == [rect, rect]


def test_names_hold_every_size() -> None:
    assert holes.hole_footprint(mm(3.2)).name == "NPTH_3.2mm"
    assert holes.hole_footprint(mm(1), length=mm(3)).name == "NPTH_Slot_1x3mm"
    assert holes.hole_footprint(mm(3.2), pad=mm(6)).name == "PTH_3.2mm_Pad_6mm"
    assert holes.hole_footprint(mm(1), length=mm(3), pad=mm(2)).name == "PTH_Slot_1x3mm_Pad_2mm"
    wide = holes.hole_footprint(mm(3.2), courtyard=mm(6.5))
    assert (
        wide.name == "NPTH_3.2mm_Courtyard_6.5mm" and wide.library == holes.HOLE_LIBRARY == "Fenolite_Holes"
    )
    assert wide.definition.graphics[0].points == (Point(0, 0), Point(3_250_000, 0))


def test_the_courtyard_of_a_slot_grows_on_both_axes() -> None:
    slot = holes.hole_footprint(mm(1), length=mm(3), courtyard=mm(2))
    # 1 mm more than the hole's width, so 1 mm more than its length: 4 mm × 2 mm
    assert slot.definition.graphics[0].points == (Point(-2_000_000, -1_000_000), Point(2_000_000, 1_000_000))
    assert slot.definition.graphics[0].kind == "rect" and slot.definition.graphics[1].layer == "B.CrtYd"


def test_equal_holes_share_a_definition() -> None:
    design = board()
    design.hole("H1", mm(3), mm(3), drill=mm(3.2))
    design.hole("H2", mm(47), mm(3), drill=mm(3.2))
    assert list(design.footprints) == ["Fenolite_Holes:NPTH_3.2mm"]
    assert list(design.symbols) == ["Fenolite_Holes:Hole"]
    assert sorted(design.parts) == ["H1", "H2"]


def test_refused_holes() -> None:
    design = board()
    design.hole("H1", mm(3), mm(3), drill=mm(3.2))
    for words, call in (
        ("drill", lambda: design.hole("H3", mm(1), mm(1), drill=mm(0))),
        ("pad", lambda: design.hole("H3", mm(1), mm(1), drill=mm(1), pad=mm(1))),
        ("length", lambda: design.hole("H3", mm(1), mm(1), drill=mm(1), length=mm(1))),
        ("courtyard", lambda: design.hole("H3", mm(1), mm(1), drill=mm(2), courtyard=mm(1))),
        ("'H1'", lambda: design.hole("H1", mm(9), mm(9), drill=mm(2))),
        ("drill", lambda: design.hole("H3", mm(1), mm(1), drill=3.2)),
        ("locked", lambda: design.hole("H3", mm(1), mm(1), drill=mm(1), locked="yes")),  # type: ignore[arg-type]
        ("rot", lambda: design.hole("H3", mm(1), mm(1), drill=mm(1), rot="fast")),
        ("courtyard", lambda: design.hole("H3", mm(1), mm(1), drill=mm(1), pad=mm(3), courtyard=mm(2))),
    ):
        with pytest.raises(DslError) as info:
            call()
        assert words in str(info.value), (words, str(info.value))
    assert sorted(design.parts) == ["H1"] and list(design.footprints) == ["Fenolite_Holes:NPTH_3.2mm"]


def test_another_definition_under_a_hole_lib_id_is_refused() -> None:
    design = board()
    own = Footprint("Fenolite_Holes", "NPTH_3.2mm")
    own.pad("1", at=(mm(0), mm(0)), size=(mm(1), mm(1)))
    design.add_footprint(own)
    with pytest.raises(DslError, match="Fenolite_Holes:NPTH_3.2mm"):
        design.hole("H1", mm(3), mm(3), drill=mm(3.2))
    assert "H1" not in design.parts
    other = board()
    other.hole("H1", mm(3), mm(3), drill=mm(3.2))
    with pytest.raises(DslError, match="registered twice"):
        other.add_footprint(Footprint("Fenolite_Holes", "NPTH_3.2mm"))


def test_a_hole_may_be_unlocked() -> None:
    design = board()
    design.hole("H1", mm(3), mm(3), drill=mm(3.2), locked=False)
    assert placements(design)["H1"].locked is False


def test_the_holder_gives_the_definition_and_the_lib_id() -> None:
    holder = holes.HoleSymbol(holes.hole_symbol(plated=False))
    assert holder.lib_id == "Fenolite_Holes:Hole" and holder.definition.name == "Hole"
    assert holes.hole_symbol(plated=True).name == "Hole_Pad"
