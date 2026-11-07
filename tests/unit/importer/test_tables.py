# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper as tables (capability board-to-code, "Copper as tables"; change c0275)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from _importcode import BOARD, PROJECT, build, built_board, imported

from fenolite.api import read_board
from fenolite.importer.keys import segment
from fenolite.importer.tables import copper_tables
from fenolite.model.design import Design


def _copper(design: Design) -> Counter[tuple[object, ...]]:
    names = {net.id: net.name for net in design.circuit.nets}
    board = design.board
    assert board is not None
    found: Counter[tuple[object, ...]] = Counter()
    for t in board.tracks:
        found["track", t.start, t.end, t.width, t.layer, names[t.net_id or ""], t.locked] += 1
    for a in board.arcs:
        found["arc", a.start, a.mid, a.end, a.width, a.layer, names[a.net_id or ""], a.locked] += 1
    for v in board.vias:
        found["via", v.position, v.diameter, v.drill, v.layers, names[v.net_id or ""], v.locked] += 1
    return found


def test_every_segment_once(tmp_path: Path) -> None:
    source = read_board(BOARD).design
    assert source.board is not None
    assert (len(source.board.tracks), len(source.board.arcs), len(source.board.vias)) == (40, 3, 6)
    reply = imported(tmp_path, PROJECT, "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["counts"]["tracks"] == 40 and reply.result["counts"]["arcs"] == 3
    assert reply.result["counts"]["vias"] == 6
    text = (tmp_path / "out" / "copper.py").read_text(encoding="utf-8")
    assert 'design.track_table(\n        "GND/B.Cu/1",' in text and "locked=True" in text
    assert build(tmp_path / "out").exit_code == 0
    built = built_board(tmp_path / "out").design
    assert _copper(built) == _copper(source)


def test_tables_group_and_sort() -> None:
    source = read_board(BOARD).design
    assert source.board is not None
    names = {net.id: net.name for net in source.circuit.nets}
    tables = copper_tables(source.board, names)
    keys = [table.key for table in tables.tables]
    assert keys == sorted(keys) and len(set(keys)) == len(keys)
    for table in tables.tables:
        assert list(table.rows) == sorted(table.rows)
        assert table.key.startswith(f"{segment(table.net)}/")
    assert not tables.left_out


def test_segment_escape_is_injective() -> None:
    names = ["GND", "/a/b", "a_b", "a b", "a_0020b", "Net-(R1-Pad1)", "", "µ"]
    escaped = [segment(name) for name in names]
    assert len(set(escaped)) == len(names)
    assert segment("GND") == "GND" and segment("a_b") == "a_005fb"
