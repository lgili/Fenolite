# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Designator and comment texts moved and turned, and free texts narrowed (change c0497, D2), on the authored
``texts`` board (``board_ops``). The gate ``text`` is opened by the test: ``edit.GATES`` stays off."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from fenolite.backends.altium import edit
from fenolite.backends.altium.edit.state import State
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import TextRecord
from tests.unit.backends.altium.edit.conftest import OPEN, mm


def _commit(path: Path, build: Callable[[edit.Session], object]) -> tuple[edit.Receipt, Path]:
    session = edit.open(path, gates=OPEN)
    assert isinstance(session, edit.Session)
    build(session)
    out = path.with_name("out.PcbDoc")
    return session.commit(out, backup=False), out


def _texts(data: bytes) -> list[TextRecord]:
    return [t for t in read_pcbdoc(data).texts if isinstance(t, TextRecord)]


def _of(texts: list[TextRecord], component: int, designator: bool) -> TextRecord:
    return next(t for t in texts if t.prefix.component == component and t.is_designator is designator)


def _centre(t: TextRecord) -> tuple[float, float]:
    width = len(t.text) * t.height
    hx, hy = (-width if t.mirrored else width) / 2, t.height / 2
    turn = math.radians(t.rotation)
    return t.x + hx * math.cos(turn) - hy * math.sin(turn), t.y + hx * math.sin(turn) + hy * math.cos(turn)


def _index(data: bytes, ref: str) -> int:
    return next(i for i, c in enumerate(read_pcbdoc(data).components) if c.source_designator == ref)


def test_bottom_turn(ops_board: Callable[[str], Path]) -> None:
    path = ops_board("texts")
    before = path.read_bytes()
    r1 = _index(before, "R1")
    old = _of(_texts(before), r1, True)
    assert old.mirrored and old.rotation == 0
    receipt, out = _commit(path, lambda s: s.rotate(edit.Designator("R1"), 90, old_rotation=0))
    assert receipt.written, receipt.issues
    after = out.read_bytes()
    new = _of(_texts(after), r1, True)
    assert new.rotation == 90 and new.mirrored
    assert all(abs(u - v) <= 394 for u, v in zip(_centre(new), _centre(old), strict=True))  # 1 µm
    changed = Counter(State.of(before).get("Texts6")) - Counter(State.of(after).get("Texts6"))
    assert list(changed.elements()) == [old.raw]
    receipt, _ = _commit(path, lambda s: s.rotate(edit.Designator("R1"), 90, old_rotation=90))
    assert [i.code for i in receipt.issues] == ["altium.edit.assertion"]


def test_comment_moved(ops_board: Callable[[str], Path]) -> None:
    path = ops_board("texts")
    before = path.read_bytes()
    d1 = _index(before, "D1")
    receipt, out = _commit(path, lambda s: s.move(edit.Comment("D1"), 0, mm(1)))
    assert receipt.written, receipt.issues
    after = out.read_bytes()
    old, new = _of(_texts(before), d1, False), _of(_texts(after), d1, False)
    assert (new.x, new.y - old.y) == (old.x, 393_701)
    assert _of(_texts(after), d1, True) == _of(_texts(before), d1, True)
    record = dict(State.of(after).properties("Components6")[d1].fields)
    assert "COMMENTAUTOPOSITION" not in record and record["NAMEAUTOPOSITION"] == "1"
    assert record["X"] == dict(State.of(before).properties("Components6")[d1].fields)["X"]


def test_two_free_texts(ops_board: Callable[[str], Path]) -> None:
    path = ops_board("texts")
    receipt, _ = _commit(path, lambda s: s.move(edit.Text("REV A"), mm(1), 0))
    assert [i.code for i in receipt.issues] == ["altium.edit.assertion"]
    assert "2 records match" in receipt.issues[0].message
    receipt, out = _commit(path, lambda s: s.move(edit.Text("REV A", layer="Bottom Overlay"), mm(1), 0))
    assert receipt.written, receipt.issues
    moved = {t.prefix.layer: t.x for t in _texts(out.read_bytes()) if t.text == "REV A"}
    held = {t.prefix.layer: t.x for t in _texts(path.read_bytes()) if t.text == "REV A"}
    assert moved[33] == held[33] and moved[34] == held[34] + 393_701
    receipt, _ = _commit(path, lambda s: s.move(edit.Text("REV B", layer="Top Overlay"), mm(1), 0))
    assert "'REV A'" in receipt.issues[0].message and "'FENOLITE EDIT'" in receipt.issues[0].message
    receipt, _ = _commit(path, lambda s: s.move(edit.Text("REV A", at=(mm(30), mm(18))), mm(1), 0))
    assert receipt.written, receipt.issues


def test_text_gate_and_truetype(ops_board: Callable[[str], Path]) -> None:
    path = ops_board("texts")
    session = edit.open(path)
    assert isinstance(session, edit.Session)
    receipt = session.move(edit.Designator("D1"), mm(1), 0).commit(path.with_name("x.PcbDoc"))
    assert [i.code for i in receipt.issues] == ["altium.edit.gate"] and "H-A-EDIT-TEXT" in receipt.issues[
        0
    ].message
    receipt, _ = _commit(path, lambda s: s.rotate(edit.Designator("D1"), 90, old_rotation=0, about="anchor"))
    assert receipt.written, receipt.issues
