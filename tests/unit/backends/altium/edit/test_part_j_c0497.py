# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Phase C of Part J, the board edits of change c0497 (``docs/evidence/altium-edit.md``, cases J35 to J39):
the files of ``phase-c/``, written from the authored boards of ``board_ops`` with each gate forced on for the
kit only. ``FENOLITE_ALTIUM_PART_J=<folder outside the repository>`` writes them there; without it they are
written under the test's own folder. No file Altium wrote is in the repository."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from pathlib import Path

from fenolite.backends.altium import edit
from fenolite.backends.altium.edit import drawing
from fenolite.backends.altium.edit.state import State
from tests.unit.backends.altium.edit.board_ops import KEEPOUT, MECHANICAL_1
from tests.unit.backends.altium.edit.conftest import OPEN, mm

ROOT = Path(__file__).resolve().parents[5]
HANDOVER = os.environ.get("FENOLITE_ALTIUM_PART_J")


def _box(x: float, y: float, w: float, h: float) -> list[tuple[int, int]]:
    return [(mm(x), mm(y)), (mm(x + w), mm(y)), (mm(x + w), mm(y + h)), (mm(x), mm(y + h))]


def _tent(session: edit.Session) -> None:
    """The six ``GND`` vias tented on both sides; three ``VIN`` vias top only, open with 0.05 mm, open."""
    session.set_via_mask(edit.Vias(net="GND"), tented_top=True, tented_bottom=True, count=6)
    vin = [edit.Via((mm(x), mm(16)), "VIN") for x in (30, 32, 34)]
    session.set_via_mask(vin[0], tented_top=True, tented_bottom=False, count=1)
    session.set_via_mask(vin[1], tented_top=False, tented_bottom=False, expansion=mm(0.05), count=1)
    session.set_via_mask(vin[2], tented_top=False, tented_bottom=False, count=1)


OLD_KEEPOUT = [(mm(x), mm(y)) for x, y in KEEPOUT]
CASES: dict[str, tuple[str, Callable[[edit.Session], object]]] = {
    "text-edited": ("texts", lambda s: s.move(edit.Designator("D1"), 0, mm(1))
                    .rotate(edit.Designator("R1"), 90, old_rotation=0)),
    "cutout-inner": ("drawn", lambda s: s.add_board_cutout(_box(14, 10, 4, 2), drawing="Mechanical 1")),
    "cutout-notch": ("drawn", lambda s: s.add_board_cutout(_box(38, 10, 4, 4), notch=True)
                     .draw_board_shape("Mechanical 1", width=mm(0.1), old_count=10)),
    "polygon-cutout": ("drawn", lambda s: s.add_polygon_cutout(_box(20, 13, 2, 2), layer="Bottom Layer")),
    "tent": ("vias", lambda s: _tent(s)),
    "drawing": ("drawn", lambda s: s.draw_board_shape("Mechanical 1", width=mm(0.2), old_count=10)),
    "region": ("drawn", lambda s: s.set_outline(edit.Region("Keep-Out Layer", (mm(25), mm(20))),
                                                _box(24, 19, 5, 5), old=OLD_KEEPOUT)),
}  # fmt: skip


def phase_c(folder: Path, boards: dict[str, bytes]) -> dict[str, str]:
    """Write ``phase-c/`` into ``folder``; the SHA-256 of each file by name."""
    target = folder / "phase-c"
    target.mkdir(parents=True, exist_ok=True)
    for name, data in boards.items():
        (target / f"{name}.PcbDoc").write_bytes(data)
    for name, (source, build) in CASES.items():
        session = edit.open(target / f"{source}.PcbDoc", gates=OPEN)
        assert isinstance(session, edit.Session)
        build(session)
        receipt = session.commit(target / f"{name}.PcbDoc", backup=False)
        assert receipt.written, (name, receipt.issues)
    sums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.glob("*.PcbDoc"))}
    (target / "SHA256SUMS").write_text("".join(f"{d}  {n}\n" for n, d in sums.items()), encoding="utf-8")
    return sums


def test_phase_c_kit(board_ops: dict[str, bytes], tmp_path: Path) -> None:
    folder = Path(HANDOVER).expanduser() if HANDOVER else tmp_path / "J-edit"
    if HANDOVER:
        assert ROOT not in folder.resolve().parents, "the kit is written outside the repository"
    sums = phase_c(folder, board_ops)
    assert set(sums) == {f"{n}.PcbDoc" for n in (*board_ops, *CASES)}
    drawn = State.of((folder / "phase-c" / "drawing.PcbDoc").read_bytes())
    assert drawing.compare(drawn, MECHANICAL_1) == []
