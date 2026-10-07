# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board drawings in the DSL (capability design-dsl, "Board drawings in the DSL"; change c0103)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from fenolite.backends.kicad import pcb
from fenolite.backends.kicad.layers import created_layers
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, DslError, mm, to_model
from fenolite.dsl import items as itemlib
from fenolite.dsl.part import FIELD_JUSTIFY
from fenolite.model.board import Board

O = 100_000_000  # noqa: E741 - the board origin, in nanometres


def design() -> Design:
    made = Design("drawings")
    made.board(mm(50), mm(30))
    return made


def board_of(d: Design) -> Board:
    board = to_model(d).board
    assert board is not None
    return board


def test_label_and_fabrication_line_in_the_model() -> None:
    """Scenario "Label and fabrication line in the model"."""
    d = design()
    d.text("rev", "REV A", (mm(2), mm(28)), justify="left bottom")
    d.line("fab/edge", (mm(0), mm(15)), (mm(50), mm(15)), layer="F.Fab", width=mm(0.1))
    board = board_of(d)
    (text,) = board.texts
    assert text.id == derived_id("txt", "dsl", "text:rev") and text.text == "REV A"
    assert (text.position, text.layer) == (Point(O + 2_000_000, O + 28_000_000), "F.SilkS")
    assert (text.size, text.thickness, text.rotation) == (Size(1_000_000, 1_000_000), 150_000, 0)
    assert (text.h_justify, text.v_justify) == ("left", "bottom")
    (line,) = board.graphics
    assert line.id == derived_id("gfx", "dsl", "graphic:fab/edge")
    assert (line.kind, line.layer, line.width, line.filled) == ("line", "F.Fab", 100_000, False)
    assert line.points == (Point(O, O + 15_000_000), Point(O + 50_000_000, O + 15_000_000))
    assert list(d.drawings) == ["rev", "fab/edge"]


def test_dimension_in_the_model() -> None:
    """Scenario "Dimension in the model"."""
    d = design()
    d.dimension("width", (mm(0), mm(0)), (mm(50), mm(0)), offset=mm(-5))
    d.dimension("height", (mm(0), mm(0)), (mm(1), mm(30)), offset=mm(4), direction="vertical", units="in",
                precision=2, size=mm(1.5), thickness=mm(0.2), width=mm(0.12), layer="Cmts.User")  # fmt: skip
    height, width = board_of(d).dimensions
    assert width.id == derived_id("dim", "dsl", "dimension:width")
    assert (width.kind, width.layer, width.direction) == ("aligned", "Dwgs.User", None)
    assert (width.start, width.end, width.offset) == (Point(O, O), Point(O + 50_000_000, O), -5_000_000)
    assert (width.units, width.precision, width.size, width.thickness, width.width) == (
        "mm",
        4,
        None,
        None,
        None,
    )
    assert (height.kind, height.direction, height.units, height.precision) == (
        "orthogonal",
        "vertical",
        "in",
        2,
    )
    assert (height.size, height.thickness, height.width) == (Size(1_500_000, 1_500_000), 200_000, 120_000)
    assert height.layer == "Cmts.User"


def test_every_graphic_kind() -> None:
    d = design()
    d.rect("r", (mm(1), mm(1)), (mm(3), mm(2)), layer="F.Mask", width=mm(0), fill=True)
    d.circle("c", (mm(5), mm(5)), (mm(6), mm(5)), layer="B.SilkS", width=mm(0.12))
    d.arc("a", (mm(0), mm(0)), (mm(1), mm(1)), (mm(2), mm(0)), layer="Eco1.User", width=mm(0.1))
    d.polygon("p", [(mm(0), mm(0)), (mm(2), mm(0)), (mm(1), mm(2))], layer="B.Fab", width=mm(0.1))
    found = {g.id: g for g in board_of(d).graphics}
    kinds = {key: found[derived_id("gfx", "dsl", f"graphic:{key}")] for key in ("r", "c", "a", "p")}
    assert [kinds[k].kind for k in "rcap"] == ["rect", "circle", "arc", "polygon"]
    assert (kinds["r"].filled, kinds["r"].width, kinds["r"].layer) == (True, 0, "F.Mask")
    assert kinds["a"].points == (Point(O, O), Point(O + 1_000_000, O + 1_000_000), Point(O + 2_000_000, O))
    assert len(kinds["p"].points) == 3 and not kinds["p"].filled
    assert [g.id for g in board_of(d).graphics] == [
        derived_id("gfx", "dsl", f"graphic:{key}") for key in ("a", "c", "p", "r")
    ]


def test_text_values() -> None:
    d = design()
    d.text(
        "t", "X", (mm(1), mm(1)), layer="B.Fab", size=mm(2), thickness=mm(0.3), rot=90, justify=" right  top "
    )
    (text,) = board_of(d).texts
    assert (text.size, text.thickness, text.rotation) == (Size(2_000_000, 2_000_000), 300_000, 90_000_000)
    assert (text.h_justify, text.v_justify, text.layer) == ("right", "top", "B.Fab")
    for k, justify in enumerate(FIELD_JUSTIFY):
        d.text(f"j{k}", "J", (mm(1), mm(1)), justify=justify)
    words = [(t.h_justify, t.v_justify) for t in board_of(d).texts if t.text == "J"]
    assert (
        ("left", "center") in words
        and ("center", "bottom") in words
        and len(set(words)) == len(FIELD_JUSTIFY)
    )


def test_refused_drawing_calls() -> None:
    """Scenario "Refused drawing calls": each names its argument and records nothing."""
    d = design()
    d.text("rev", "REV A", (mm(2), mm(2)))
    origin, right = (mm(0), mm(0)), (mm(1), mm(0))
    calls: tuple[tuple[Callable[[], None], str], ...] = (
        (lambda: d.text("t1", "CU", (mm(1), mm(1)), layer="F.Cu"), "F.Cu"),
        (lambda: d.line("l1", origin, right, layer="Edge.Cuts", width=mm(0.1)), "Edge.Cuts"),
        (lambda: d.line("rev", origin, right, layer="F.Fab", width=mm(0.1)), "rev"),
        (lambda: d.arc("a1", origin, (mm(1), mm(1)), (mm(2), mm(2)), layer="F.Fab", width=mm(0.1)), "points"),
        (
            lambda: d.dimension("d1", origin, (mm(0), mm(9)), offset=mm(2), direction="horizontal"),
            "direction",
        ),
        (lambda: d.dimension("d2", origin, right, offset=mm(2), precision=5), "precision"),
        (lambda: d.text("t2", "A\nB", (mm(1), mm(1))), "text"),
        (lambda: d.text("t3", "", (mm(1), mm(1))), "text"),
        (lambda: d.text("t4", "A", (mm(1), mm(1)), size=mm(0)), "size"),
        (lambda: d.text("t5", "A", (mm(1), mm(1)), justify="middle"), "justify"),
        (lambda: d.text("bad key", "A", (mm(1), mm(1))), "key"),
        (lambda: d.line("l2", origin, right, layer="F.CrtYd", width=mm(0.1)), "F.CrtYd"),
        (lambda: d.line("l3", origin, right, layer="F.Paste", width=mm(0.1)), "F.Paste"),
        (lambda: d.line("l4", origin, right, layer="F.Fab", width=mm(0)), "width"),
        (lambda: d.rect("r1", origin, right, layer="F.Fab", width=mm(0.1)), "start and end"),
        (lambda: d.rect("r2", origin, (mm(1), mm(1)), layer="F.Fab", width=mm(0)), "width"),
        (lambda: d.rect("r3", origin, (mm(1), mm(1)), layer="F.Fab", width=mm(0), fill=1), "fill"),  # type: ignore[arg-type]
        (lambda: d.circle("c1", origin, origin, layer="F.Fab", width=mm(0.1)), "edge"),
        (lambda: d.polygon("p1", [origin, right], layer="F.Fab", width=mm(0.1)), "points"),
        (lambda: d.dimension("d3", origin, origin, offset=mm(2)), "start and end"),
        (lambda: d.dimension("d4", origin, right, offset=mm(2), units="mil"), "units"),
        (lambda: d.dimension("d5", origin, right, offset=mm(2), direction="vertical"), "direction"),
        (lambda: d.dimension("d6", origin, right, offset=mm(2), width=mm(0)), "width"),
        (lambda: d.dimension("d7", origin, right, offset=mm(2), precision=True), "precision"),
        (lambda: d.dimension("d8", origin, right, offset=mm(2), layer="B.Cu"), "B.Cu"),
    )
    for call, word in calls:
        with pytest.raises(DslError, match=word):
            call()
    assert list(d.drawings) == ["rev"]
    with pytest.raises(DslError, match=r"board\(\)"):
        Design("bare").text("t", "A", (mm(1), mm(1)))


def test_keys_not_order() -> None:
    """Scenario "Keys, not order"."""

    def calls(d: Design) -> list[Callable[[], None]]:
        return [
            lambda: d.text("rev", "REV A", (mm(2), mm(2))),
            lambda: d.text("date", "2026", (mm(2), mm(4))),
            lambda: d.line("b", (mm(0), mm(0)), (mm(1), mm(0)), layer="F.Fab", width=mm(0.1)),
            lambda: d.line("a", (mm(0), mm(1)), (mm(1), mm(1)), layer="F.Fab", width=mm(0.1)),
            lambda: d.dimension("width", (mm(0), mm(0)), (mm(50), mm(0)), offset=mm(-5)),
        ]

    boards = []
    for reverse in (False, True):
        d = design()
        made = calls(d)
        for call in reversed(made) if reverse else made:
            call()
        boards.append(board_of(d))
    assert boards[0] == boards[1]
    assert [t.id for t in boards[0].texts] == [derived_id("txt", "dsl", f"text:{k}") for k in ("date", "rev")]
    assert [g.id for g in boards[0].graphics] == [derived_id("gfx", "dsl", f"graphic:{k}") for k in "ab"]


def test_layer_table_equals_the_created_board() -> None:
    """The DSL imports no backend: its layer table and text defaults repeat the backend's."""
    created = {layer.name: layer.kind for layer in created_layers(2) if layer.kind != "copper"}
    assert dict(itemlib.BOARD_LAYER_KINDS) == created
    allowed = [name for name, kind in created.items() if kind in itemlib.DRAWING_LAYER_KINDS]
    assert sorted(allowed) == sorted([
        "F.SilkS", "B.SilkS", "F.Mask", "B.Mask", "F.Fab", "B.Fab", "Dwgs.User", "Cmts.User", "Eco1.User",
        "Eco2.User",
    ])  # fmt: skip
    assert itemlib.DRAWING_LAYER_KINDS == ("silkscreen", "soldermask", "fabrication", "user")
    assert Size(itemlib.TEXT_SIZE, itemlib.TEXT_SIZE) == pcb.TEXT_SIZE
    assert itemlib.TEXT_THICKNESS == pcb.TEXT_THICKNESS
