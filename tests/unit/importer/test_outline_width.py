# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Strict outline-width preservation (c0317), from Fenolite-authored CC0 data only.

Variants are constructed in tmp_path. They use arbitrary authored widths and are not reproductions
of the external corpus. No native application or reviewed corpus baseline is claimed.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _fidelity import ALL_LEVELS, roundtrip, snapshot
from _importcode import BOARD, build, imported, notched

from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse

ROOT = Path(__file__).resolve().parents[3]
SENSOR = ROOT / "tests/data/fidelity/sensor"
WIDTH = 230_000


def _strokes(source: Path, width: int, *, mixed: bool = False, arc: bool = False) -> None:
    tree = parse(source.read_text(encoding="utf-8"))
    made: list[Node | Atom] = []
    count = 0
    for graphic in tree.children:
        if isinstance(graphic, Node) and graphic.find("layer") == parse('(layer "Edge.Cuts")'):
            stroke = graphic.find("stroke")
            assert stroke is not None
            chosen = 71_000 if mixed and not count else width
            stroke = stroke.with_children(
                Node(Atom.symbol("width"), (Atom.from_nm(chosen),))
                if isinstance(c, Node) and c.name == "width"
                else c
                for c in stroke.children
            )
            graphic = graphic.with_children(
                stroke if c == graphic.find("stroke") else c for c in graphic.children
            )
            if arc and not count:
                a, b = graphic.find("start"), graphic.find("end")
                assert a is not None and b is not None
                ax, ay = (atom.to_nm() for atom in a.atoms())
                bx, by = (atom.to_nm() for atom in b.atoms())
                x = (ax + bx) // 2 + (2_000_000 if ax == bx else 0)
                y = (ay + by) // 2 + (2_000_000 if ay == by else 0)
                mid = Node(Atom.symbol("mid"), (Atom.from_nm(x), Atom.from_nm(y)))
                graphic = Node(
                    Atom.symbol("gr_arc"), (a, mid, b, *(c for c in graphic.children if c not in (a, b)))
                )
            count += 1
        made.append(graphic)
    assert count
    source.write_text(dumps(tree.with_children(made)), encoding="utf-8")


def _source(tmp: Path, width: int, *, mixed: bool = False) -> Path:
    source = tmp / "source" / "strokes.kicad_pcb"
    source.parent.mkdir(parents=True)
    shutil.copyfile(BOARD, source)
    _strokes(source, width, mixed=mixed)
    return source


@pytest.mark.parametrize("width", [WIDTH, 0])
def test_uniform_root_width_rebuilds_exactly_and_deterministically(tmp_path: Path, width: int) -> None:
    source = _source(tmp_path, width)
    first = imported(tmp_path, source, "--confirm", out="first")
    assert first.exit_code == 0, first.error
    assert first.result["unexpressed"] == []
    code = (tmp_path / "first/design.py").read_text(encoding="utf-8")
    expected = 'outline_width=mm("0.23")' if width else 'outline_width=mm("0")'
    assert expected in code
    second = imported(tmp_path, source, "--confirm", out="second")
    assert second.exit_code == 0, second.error
    assert snapshot(tmp_path / "first") == snapshot(tmp_path / "second")
    assert build(tmp_path / "first").exit_code == 0
    native = read_board(tmp_path / "first/built/strokes.kicad_pcb").board
    assert native is not None
    assert {g.width for g in native.graphics if g.layer == "Edge.Cuts"} == {width}


@pytest.mark.parametrize(("width", "mixed"), [(WIDTH, True), (-1, False)])
def test_unsupported_width_still_refuses_without_writes(tmp_path: Path, width: int, mixed: bool) -> None:
    source = _source(tmp_path, width, mixed=mixed)
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 7 and reply.error is not None
    assert reply.error["code"] == "FEN-7001"
    assert any(
        i["code"] == "import.item-unexpressed" and i["where"] == "outline-width"
        for i in (reply.envelope or {})["issues"]
    )
    assert not (tmp_path / "out").exists()


def test_uniform_width_and_supported_short_layer_table_rebuild_exactly(tmp_path: Path) -> None:
    source = _source(tmp_path, WIDTH)
    tree = parse(source.read_text(encoding="utf-8"))
    layers = tree.find("layers")
    assert layers is not None
    short = layers.with_children(
        c
        for c in layers.children
        if not isinstance(c, Node) or c.atoms()[0].value not in {"Eco1.User", "Eco2.User"}
    )
    source.write_text(
        dumps(tree.with_children(short if c == layers else c for c in tree.children)), encoding="utf-8"
    )
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["unexpressed"] == []
    assert build(tmp_path / "out").exit_code == 0
    before = read_board(source).board
    after = read_board(tmp_path / "out/built/strokes.kicad_pcb").board
    assert before is not None and after is not None
    assert [layer.name for layer in after.layers] == [layer.name for layer in before.layers]
    assert {g.width for g in after.graphics if g.layer == "Edge.Cuts"} == {WIDTH}


def test_footprint_closing_edge_keeps_its_own_width(tmp_path: Path) -> None:
    source = notched(tmp_path / "original")
    _strokes(source, WIDTH)
    original = parse(source.read_text(encoding="utf-8"))
    original_edges = [
        g
        for fp in original.nodes("footprint")
        for g in fp.nodes("fp_line")
        if g.find("layer") == parse('(layer "Edge.Cuts")')
    ]
    assert len(original_edges) == 1
    reply = imported(tmp_path, source, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["unexpressed"] == []
    assert build(tmp_path / "out").exit_code == 0
    native = read_board(tmp_path / "out/built/notched.kicad_pcb").board
    assert native is not None
    assert [g.width for g in native.graphics if g.layer == "Edge.Cuts"] == [WIDTH] * 3
    tree = parse((tmp_path / "out/built/notched.kicad_pcb").read_text(encoding="utf-8"))
    footprint_edges = [
        g
        for fp in tree.nodes("footprint")
        for g in fp.nodes("fp_line")
        if g.find("layer") == parse('(layer "Edge.Cuts")')
    ]
    assert len(footprint_edges) == 1
    assert footprint_edges[0].find("stroke") == original_edges[0].find("stroke")


def test_authored_line_arc_project_roundtrip_remains_strict_at_all_levels(tmp_path: Path) -> None:
    source = tmp_path / "original"
    shutil.copytree(SENSOR, source)
    board = next(source.glob("*.kicad_pcb"))
    _strokes(board, WIDTH, arc=True)
    reply = roundtrip(source, tmp_path / "roundtrip")
    assert reply.exit_code == 0, (reply.error, reply.result.get("differences"))
    assert reply.result["equivalent"] is True
    assert reply.result["differences"] == [] and reply.result["accepted"] == []
    assert tuple(row["level"] for row in reply.result["levels"]) == ALL_LEVELS
    assert all(row["status"] == "equal" for row in reply.result["levels"])
