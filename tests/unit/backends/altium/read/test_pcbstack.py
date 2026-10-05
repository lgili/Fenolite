# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board record and layer stack of the PCB reader (capability altium-pcb-reader, "Board record and
layer stack", change c0041)."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from _altium_long import block

from fenolite.backends.altium import pcbrecords
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.pcbprops import PropertyRecord, parse_blocks
from fenolite.backends.altium.read.pcbstack import LAYER_NAMES, BoardRecord, long_layer_id, read_board
from fenolite.core.errors import Issue

ROOT = Path(__file__).resolve().parents[5]
BLINK = ROOT / "tests" / "data" / "altium" / "blink"


def _board(text: str) -> tuple[BoardRecord, list[Issue]]:
    (record,), _, _ = parse_blocks(block(text), where="Board6/Data")
    return read_board(record, where="Board6/Data#0")


def _first_block(path: Path, stream: str) -> PropertyRecord:
    data = open_compound(path.read_bytes()).read(stream)
    records, _, _ = parse_blocks(data[: 4 + (int.from_bytes(data[:4], "little") & 0xFFFFFF)], where=stream)
    return records[0]


def _layers(links: dict[int, tuple[int, int]], count: int = 54) -> str:
    text = ""
    for i in range(1, count + 1):
        prev, nxt = links.get(i, (0, 0))
        text += f"|LAYER{i}NAME=L{i}|LAYER{i}PREV={prev}|LAYER{i}NEXT={nxt}"
    return text


def test_names_equal_the_writer_table() -> None:
    assert dict(LAYER_NAMES) == dict(pcbrecords.LAYER_NAMES)
    assert sorted(LAYER_NAMES) == list(range(1, 75))


def test_names_long_layer_ids() -> None:
    assert long_layer_id(16777217) == ("signal", 1)
    assert long_layer_id(0x0100FFFF) == ("signal", 32)
    assert long_layer_id("16842753") == ("plane", 1)
    assert long_layer_id(0x01020000 + 13) == ("mechanical", 13)
    assert long_layer_id(0x01030000 + 6) == ("other", 6)
    assert long_layer_id(17039361) == ("dielectric", 1)
    assert long_layer_id(5) == ("unknown", 5)


def test_four_layers_with_a_plane_chain() -> None:
    text = (
        _layers({1: (0, 39), 39: (1, 3), 3: (39, 32), 32: (3, 0)})
        + "|PLANE1NETNAME=GND|PLANE2NETNAME=(No Net)"
    )
    board, issues = _board(text)
    assert board.copper_chain == (1, 39, 3, 32)
    assert dict(board.plane_nets) == {1: "GND"}
    assert issues == []


def test_broken_chain() -> None:
    board, issues = _board(_layers({1: (0, 2), 2: (1, 1)}))
    assert board.copper_chain == (1, 2)
    (problem,) = issues
    assert problem.code == "altium.pcb-read.bad-stack" and problem.severity == "error"
    assert problem.where == "Board6/Data#0"


def test_chain_to_a_layer_without_a_name() -> None:
    board, issues = _board(_layers({1: (0, 40)}, count=33))
    assert board.copper_chain == (1,) and [i.code for i in issues] == ["altium.pcb-read.bad-stack"]


def test_outline_vertices() -> None:
    text = "|VX0=0mil|VY0=0mil|KIND1=1|VX1=100mil|VY1=0mil|CX1=50mil|CY1=0mil"
    text += "|SA1= 1.80000000000000E+0002|R1=50mil"
    board, issues = _board(text)
    assert issues == []
    first, second = board.outline
    assert first.kind == 0 and first.radius == 0 and first.start_angle == 0.0
    assert second.kind == 1 and second.x == Fraction(1_000_000) and second.cx == Fraction(500_000)
    assert second.start_angle == 180.0 and second.end_angle == 0.0 and second.radius == Fraction(500_000)


def test_bad_value_gives_none() -> None:
    board, issues = _board("|ORIGINX=abc|ORIGINY=0mil|DISPLAYUNIT=x")
    assert board.origin is None and board.display_unit is None
    assert [i.code for i in issues] == ["altium.pcb-read.bad-value"] * 2
    assert all("abc" not in i.message for i in issues)


def test_two_layer_stack_of_fenolites_document() -> None:
    board, issues = read_board(_first_block(BLINK / "blink.PcbDoc", "Board6/Data"), where="Board6/Data#0")
    assert issues == []
    assert board.kind == "Protel_Advanced_PCB" and board.version == "5.01"
    assert board.copper_chain == (1, 32)
    assert len(board.stack) == 9
    assert board.stack[0].name == "Top Paste" and board.stack[-1].name == "Bottom Paste"
    assert [s.kind for s in board.stack if s.kind == "signal"] == ["signal", "signal"]
    assert dict(board.plane_nets) == {}
    assert board.layer_pairs == (("TOP", "BOTTOM"),)
    assert len(board.outline) == 5 and board.outline[0] == board.outline[-1]
    assert board.origin == (Fraction(10_000_000), Fraction(10_000_000))
    assert len(board.layers) == 82
    assert board.stack[3].get("layerid") == str(board.stack[3].layer_id)


def test_library_record() -> None:
    board, issues = read_board(_first_block(BLINK / "blink.PcbLib", "Library/Data"), where="Library/Data#0")
    assert issues == []
    assert board.kind == "Protel_Advanced_PCB_Library" and board.version == "3.00"
    assert board.origin is None
    assert [s.name for s in board.stack][0] == "Top Paste" and len(board.stack) == 9
    assert board.copper_chain == (1, 32)
