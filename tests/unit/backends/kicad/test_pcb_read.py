# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board file reading, version policy and the layer table (capability kicad-file-backend, c0009)."""

from __future__ import annotations

from pathlib import Path

import pytest
from _boards import FIXTURE, board, segment

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad import versions
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.backends.kicad.versions import FutureFormatError, UnsupportedFormatError
from fenolite.core.errors import FormatError, Issue
from fenolite.model.base import Opaque

OLD = Path(__file__).resolve().parents[3] / "data" / "kicad" / "tokens" / "old" / "old.kicad_pcb"


def test_authored_board_from_a_path() -> None:
    issues: list[Issue] = []
    design = read_board(FIXTURE, issues=issues)
    board_ = design.board
    assert board_ is not None and design.header.name == "two_layer"
    counts = [len(getattr(board_, f)) for f in ("footprints", "tracks", "arcs", "vias", "zones", "keepouts")]
    assert counts == [2, 3, 1, 1, 1, 1]
    assert len(board_.graphics) == 6 and len(board_.texts) == 1
    assert design.rules is None and design.manufacturing is None
    assert not [i for i in issues if i.severity == "error"]


def test_text_input_has_no_name() -> None:
    assert read_board(FIXTURE.read_text(encoding="utf-8")).header.name == ""


def test_foreign_root() -> None:
    with pytest.raises(FormatError) as info:
        read_board('(footprint "X" (version 20260206) (generator "t") (layer "F.Cu"))')
    assert info.value.locator == "/footprint"


def test_kicad_7_board_refused() -> None:
    with pytest.raises(UnsupportedFormatError) as info:
        read_board(board(version=20221018))
    assert "kicad-cli pcb upgrade" in info.value.hint


def test_kicad_8_board_read() -> None:
    issues: list[Issue] = []
    design = read_board(OLD, issues=issues)
    assert design.board is not None
    assert [(g.kind, g.layer) for g in design.board.graphics] == [("rect", "Edge.Cuts")]
    assert not [i for i in issues if i.severity == "error"]


def test_future_board_read_but_not_editable() -> None:
    text = FIXTURE.read_text(encoding="utf-8").replace("(version 20241229)", "(version 20990101)", 1)
    issues: list[Issue] = []
    design = read_board(text, issues=issues)
    assert [i.code for i in issues if i.severity == "warning"] == ["kicad.version.future"]
    opaque = [
        slot
        for entity in design.entities()
        if "kicad" in entity.ext
        for group in slotlib.from_ext_all(entity.ext["kicad"]).values()
        for slot in group
        if isinstance(slot, Opaque)
    ]
    assert opaque and {slot.min_version for slot in opaque} == {"20990101"}
    with pytest.raises(FutureFormatError):
        versions.require_editable(versions.inspect(parse(text)))


def test_copper_rows_of_the_authored_board() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    layers = {layer.name: layer for layer in design.board.layers}
    assert (layers["F.Cu"].kind, layers["F.Cu"].ordinal) == ("copper", 0)
    assert (layers["B.Cu"].kind, layers["B.Cu"].ordinal) == ("copper", 1)
    assert ("number", "2") in layers["B.Cu"].ext["kicad"].payload
    assert ("user_name", "F.Silkscreen") in layers["F.SilkS"].ext["kicad"].payload
    assert layers["Edge.Cuts"].kind == "edge" and layers["F.CrtYd"].kind == "courtyard"


def test_unknown_root_child_survives_in_place() -> None:
    root = parse(FIXTURE.read_text(encoding="utf-8"))
    children = list(root.children)
    children.insert(4, parse("(frobnicate 1)"))
    design = read_board(dumps(Node(root.head, tuple(children))))
    assert design.board is not None
    assert slotlib.from_ext(design.board.ext["kicad"])[4] == Opaque("(frobnicate 1)", "20241229")


def test_edge_graphics_are_authoritative() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None and design.board.outline is None and design.board.stackup is None
    edges = [g for g in design.board.graphics if g.layer == "Edge.Cuts"]
    assert len(edges) == 4 and {g.kind for g in edges} == {"line"}


def test_text_from_gr_text() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    (text,) = design.board.texts
    assert (text.text, text.layer) == ("FENOLITE", "F.SilkS")
    assert (text.size.w, text.size.h, text.thickness) == (1_500_000, 1_500_000, 300_000)


def test_header_values_in_the_board_bag() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    payload = design.board.ext["kicad"].payload
    assert ("version", "20241229") in payload and ("generator", "fenolite-tests") in payload
    assert ("generator_version", "9.0") in payload


def test_stable_ids_across_reads() -> None:
    first, second = read_board(FIXTURE), read_board(FIXTURE)
    assert [e.id for e in first.entities()] == [e.id for e in second.entities()]
    assert not [i for i in first.validate() if i.code == "model.duplicate-id"]


def test_development_header_gives_an_info() -> None:
    issues: list[Issue] = []
    read_board(board(segment(1), version=20241030), issues=issues)
    assert [i.code for i in issues] == ["kicad.version.dev"]
