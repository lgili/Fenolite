# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The test boards of change c0497 read back strictly and hold no integrity finding (task 1.3)."""

from __future__ import annotations

import pytest

from fenolite.backends.altium.edit import drawing, integrity
from fenolite.backends.altium.edit.state import State
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import TextRecord, ViaRecord


@pytest.mark.parametrize("name", ["drawn", "vias", "texts"])
def test_board_reads_back(board_ops: dict[str, bytes], name: str) -> None:
    data = board_ops[name]
    doc = read_pcbdoc(data, strict=True)
    assert not [i for i in doc.issues if i.severity == "error"]
    assert not [i for i in integrity.check_pcbdoc(data) if i.severity in ("error", "warning")]


def test_drawn_board(board_ops: dict[str, bytes]) -> None:
    state = State.of(board_ops["drawn"])
    edges = drawing.board_shape(state)
    assert sum(e.centre is not None for e in edges) == 1 and len(edges) == 9
    assert len(drawing.drawn_edges(state, 57)) == 10
    assert drawing.compare(state, 57) == []
    assert [i.code for i in drawing.check_pcbdoc(board_ops["drawn"])] == []


def test_vias_and_texts_boards(board_ops: dict[str, bytes]) -> None:
    doc = read_pcbdoc(board_ops["vias"])
    vias = [v for v in doc.vias if isinstance(v, ViaRecord)]
    assert len(vias) == 12 and all(len(v.raw) == 326 for v in vias)
    assert (
        sorted(doc.nets[v.prefix.net].name for v in vias if v.prefix.net is not None)
        == ["GND"] * 6 + ["VIN"] * 6
    )
    texts = [t for t in read_pcbdoc(board_ops["texts"]).texts if isinstance(t, TextRecord)]
    assert sorted(t.prefix.layer for t in texts if t.text == "REV A") == [33, 34]
    assert sum(t.mirrored for t in texts if t.prefix.component is not None) == 2
