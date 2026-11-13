# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Via tenting and mask set by an edit session (change c0497, D5), on the authored ``vias`` board
(``board_ops``). The gate ``tenting`` is opened by the test: ``edit.GATES`` stays off."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fenolite.backends.altium import edit
from fenolite.backends.altium.edit import records as rec
from fenolite.backends.altium.edit.state import State
from tests.unit.backends.altium.edit.conftest import OPEN, mm


def _commit(path: Path, build: Callable[[edit.Session], object]) -> tuple[edit.Receipt, bytes]:
    session = edit.open(path, gates=OPEN)
    assert isinstance(session, edit.Session)
    build(session)
    out = path.with_name("out.PcbDoc")
    receipt = session.commit(out, backup=False)
    return receipt, out.read_bytes() if receipt.written else b""


def _vias(data: bytes) -> list[tuple[int, int, int, int, int]]:
    """Per via: its net, flags byte, cache state, front and back expansion."""
    out = []
    for raw in State.of(data).get("Vias6"):
        body = rec.split(raw)[1][0]
        front, back = rec.unpack(raw, 54, "<i")[0], rec.unpack(raw, 242, "<i")[0]
        out.append((rec.prefix_of(raw)[1], body[1], body[66], int(front), int(back)))  # type: ignore[arg-type]
    return out


def test_every_via_of_a_net(ops_board: Callable[[str], Path]) -> None:
    path = ops_board("vias")
    before = _vias(path.read_bytes())
    gnd = next(n for n, *_ in before if [m for m, *_ in before].count(n) == 6)
    receipt, after_data = _commit(path, lambda s: s.set_via_mask(edit.Vias(net="GND"), tented_top=True,
                                                                 tented_bottom=True, count=6))  # fmt: skip
    assert receipt.written, receipt.issues
    after = _vias(after_data)
    for old, new in zip(before, after, strict=True):
        if old[0] != new[0]:
            raise AssertionError("the via order changed")
        if new[0] == gnd:
            assert new[1] == old[1] | 0x60 and new[2] == 2 and new[3:] == old[3:]
        else:
            assert new == old
    receipt, _ = _commit(path, lambda s: s.set_via_mask(edit.Vias(net="GND"), tented_top=True,
                                                        tented_bottom=True, count=5))  # fmt: skip
    assert [i.code for i in receipt.issues] == ["altium.edit.assertion"] and "takes 6 vias" in receipt.issues[
        0
    ].message


def test_one_via_untented_with_expansion(ops_board: Callable[[str], Path]) -> None:
    path = ops_board("vias")
    via = edit.Via((mm(20), mm(5)), "GND")
    receipt, data = _commit(path, lambda s: s.set_via_mask(via, tented_top=False, tented_bottom=False,
                                                           expansion=mm(0.05), count=1))  # fmt: skip
    assert receipt.written, receipt.issues
    changed = [v for v, w in zip(_vias(path.read_bytes()), _vias(data), strict=True) if v != w]
    [(net, flags, cache, front, back)] = [w for w in _vias(data) if w not in _vias(path.read_bytes())]
    assert len(changed) == 1 and flags & 0x60 == 0 and cache == 2 and front == back == 19685


def test_short_via_refused(ops_board: Callable[[str], Path], tmp_path: Path) -> None:
    from fenolite.backends.altium.edit import ops

    state = State.of(ops_board("vias").read_bytes())
    raw = state.get("Vias6")[0]
    kind, subs = rec.split(raw)
    state.replace("Vias6", 0, rec.join(kind, [subs[0][:200]]))
    try:
        ops.set_via_mask(state, edit.Vias(), tented_top=True, tented_bottom=True, expansion=None, count=12)
    except ops.Refused as refusal:
        assert refusal.code == "altium.edit.no-template"
    else:
        raise AssertionError("a short via was written")
