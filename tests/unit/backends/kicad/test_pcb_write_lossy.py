# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The emit-check gate: too-new tokens in opaque and modelled content (capability kicad-file-backend,
"Lossy writes are refused unless allowed", change c0017)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _boards import created_board, mm, square

from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import parse, walk
from fenolite.backends.kicad.versions import FileKind, LossyWriteError, check_emittable
from fenolite.core.coords import Point
from fenolite.model.base import ExtBag
from fenolite.model.board import Graphic, Outline
from fenolite.model.circuit import Circuit, Component
from fenolite.model.design import Design

TOKENS = Path(__file__).resolve().parents[4] / "tests" / "data" / "kicad" / "tokens"
MINI = Path(__file__).resolve().parents[4] / "tests" / "data" / "libs" / "Mini.pretty"
FOOTPRINT = (
    '(footprint "x:y" (layer "F.Cu") (uuid "6f1d2c3e-0000-4000-8000-0000000000c1") (at 5 5)'
    " (duplicate_pad_numbers_are_jumpers no)"
    ' (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (uuid "6f1d2c3e-0000-4000-8000-0000000000c2")))'
)


def as_created(design: Design) -> Design:
    """The design without its source header, so the writer treats it as created."""
    board = design.board
    assert board is not None
    bag = board.ext["kicad"]
    kept = tuple((k, v) for k, v in bag.payload if k not in ("version", "generator", "generator_version"))
    return dataclasses.replace(
        design, board=dataclasses.replace(board, ext={"kicad": ExtBag(bag.min_version, kept)})
    )


def ten_footprint() -> Design:
    """A design holding a footprint read from 10.0 content, whose 10-only child stays opaque."""
    text = (
        (TOKENS / "future.kicad_pcb").read_text(encoding="utf-8").rstrip().removesuffix(")") + FOOTPRINT + ")"
    )
    return as_created(read_board(text))


def test_too_new_opaque_token_is_droppable() -> None:
    with pytest.raises(LossyWriteError) as info:
        write_board(ten_footprint(), target=9)
    error = info.value
    assert error.droppable is True and "--allow-lossy" in error.hint
    assert [i.code for i in error.issues] == ["kicad.token.too-new"]
    assert "duplicate_pad_numbers_are_jumpers" in error.issues[0].message


def test_lossy_write_allowed() -> None:
    result = write_board(ten_footprint(), target=9, allow_lossy=True)
    root = parse(result.text)
    assert all(n.name != "duplicate_pad_numbers_are_jumpers" for _, n in walk(root))
    (warning,) = result.issues
    assert warning.code == "kicad.board.dropped-too-new" and warning.severity == "warning"
    assert warning.where == "/kicad_pcb/footprint[0]/duplicate_pad_numbers_are_jumpers[0]"
    assert "row " in warning.hint
    assert [i for i in check_emittable(root, FileKind.BOARD, 9) if i.severity == "error"] == []


def test_target_10_keeps_the_token() -> None:
    root = parse(write_board(ten_footprint(), target=10).text)
    assert any(n.name == "duplicate_pad_numbers_are_jumpers" for _, n in walk(root))


def test_modelled_content_is_never_dropped() -> None:
    design = created_board()
    assert design.board is not None
    via = dataclasses.replace(design.board.vias[0], via_type="buried")
    design = design.replace_entity(via)
    for allow in (False, True):
        with pytest.raises(LossyWriteError) as info:
            write_board(design, target=9, allow_lossy=allow)
        assert info.value.droppable is False and "--allow-lossy" not in info.value.hint
        assert [i.code for i in info.value.issues] == ["kicad.token.too-new"]
    assert "buried" in write_board(design, target=10).text


def test_mixed_errors_are_not_droppable() -> None:
    design = ten_footprint()
    board = design.board
    assert board is not None
    edge = Graphic(
        id="gfx_00000000-0000-4000-8000-000000000009",
        kind="line",
        layer="Edge.Cuts",
        points=(mm(0, 0), mm(1, 0)),
    )
    outline = Outline(id="out_00000000-0000-4000-8000-000000000009", points=square(0, 0, 20, 10))
    design = dataclasses.replace(design, board=dataclasses.replace(board, outline=outline, graphics=(edge,)))
    with pytest.raises(LossyWriteError) as info:
        write_board(design, target=9, allow_lossy=True)
    codes = sorted(i.code for i in info.value.issues)
    assert codes == ["kicad.board.outline-conflict", "kicad.token.too-new"] and info.value.droppable is False


def placed_resistor() -> Design:
    """A created design holding ``Mini_R_0603`` of ``Mini.pretty`` (header 20260206), placed as R1."""
    defn = read_footprint(MINI / "Mini_R_0603.kicad_mod", library="Mini")
    r1 = Component(id="cmp_00000000-0000-4000-8000-000000000001", ref="R1", value="1k")
    instance = place_footprint(defn, component=r1, at=Point(10_000_000, 10_000_000), key="R1")
    design = Design.new("lossy", seed=1)
    assert design.board is not None
    board = dataclasses.replace(design.board, layers=created_layers(2), footprints=(instance,))
    return dataclasses.replace(design, circuit=Circuit(components=(r1,)), board=board)


def test_ten_footprint_embedded_for_target_9() -> None:
    with pytest.raises(LossyWriteError) as info:
        write_board(placed_resistor(), target=9)
    assert info.value.droppable is True and "--allow-lossy" in info.value.hint
    assert any("duplicate_pad_numbers_are_jumpers" in i.message for i in info.value.issues)


def test_embedded_lossy_write_allowed() -> None:
    result = write_board(placed_resistor(), target=9, allow_lossy=True)
    assert "duplicate_pad_numbers_are_jumpers" not in result.text
    assert [i.code for i in result.issues] == ["kicad.board.dropped-too-new"]
    errors = [i for i in check_emittable(parse(result.text), FileKind.BOARD, 9) if i.severity == "error"]
    assert errors == []
