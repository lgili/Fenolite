# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A flip in an edit session writes the frame Altium gives a part on the other side (change c0453).

Altium places a bottom part as its footprint mirrored in Y and turned by ``ROTATION`` (S-2121: every one of
the 235 bottom parts with asymmetric pads in the public documents whose pattern is also on the top). The
session's flip mirrors the primitives in X about the origin, so the component must read ``180 − R`` and each
pad ``180 − r``. Before this change it wrote ``−R`` and ``−r``. That frame says the footprint is turned by a
half turn against its library, and after an Altium save the pads and the designator came back on the old
side (S-2120). The fixture is the authored Part J kit board; the body on ``D1`` is authored here with the
Altium writer's body record."""

from __future__ import annotations

import math
from pathlib import Path

from fenolite.backends.altium import edit
from fenolite.backends.altium.edit import integrity
from fenolite.backends.altium.edit import records as rec
from fenolite.backends.altium.edit.state import State
from fenolite.backends.altium.pcbrecords import BODY_TOP_LAYER, body_record
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.backends.altium.read.pcbprims import PadRecord
from tests.unit.backends.altium.edit.conftest import OPEN

TOLERANCE = 2
"""Units of 1/10 000 mil a mirrored and turned place may differ by rounding."""


def _session(board: Path, out: Path, steps: list[tuple[str, str, float]]) -> PcbDocument:
    """``board`` after ``steps`` (operation, reference, 0 for the top or the old rotation), written to
    ``out``."""
    session = edit.open(board, gates={name: True for name in OPEN})
    assert isinstance(session, edit.Session)
    for operation, ref, value in steps:
        part = edit.Component(ref)
        if operation == "flip":
            session = session.flip(part, old_side="TOP" if value == 0 else "BOTTOM")
        else:
            session = session.rotate(part, 90, old_rotation=value)
    receipt = session.declare_connectivity("MID", "GND", "VIN").commit(out, backup=False)
    assert receipt.written, receipt.issues
    data = out.read_bytes()
    assert integrity.check_pcbdoc(data) == ()
    return read_pcbdoc(data)


def _index(doc: PcbDocument, ref: str) -> int:
    return next(i for i, c in enumerate(doc.components) if c.source_designator == ref)


def _frame(doc: PcbDocument, ref: str) -> dict[str, tuple[float, float, float]]:
    """Pad name → its place and rotation in the footprint, as Altium reads the component's frame: turned
    back by ``ROTATION`` and, on the bottom, mirrored in Y."""
    index = _index(doc, ref)
    part = doc.components[index]
    assert part.x is not None and part.y is not None and part.rotation is not None
    turn = math.radians(-part.rotation)
    bottom = part.layer == "BOTTOM"
    found: dict[str, tuple[float, float, float]] = {}
    for pad in doc.pads:
        if not isinstance(pad, PadRecord) or pad.prefix.component != index:
            continue
        dx, dy = float(pad.x - part.x), float(pad.y - part.y)
        x = dx * math.cos(turn) - dy * math.sin(turn)
        y = dx * math.sin(turn) + dy * math.cos(turn)
        local = (pad.rotation - part.rotation) % 360
        found[pad.name] = (x, -y, (-local) % 360) if bottom else (x, y, local)
    return found


def _same(a: dict[str, tuple[float, float, float]], b: dict[str, tuple[float, float, float]]) -> bool:
    return a.keys() == b.keys() and all(
        abs(a[n][0] - b[n][0]) <= TOLERANCE
        and abs(a[n][1] - b[n][1]) <= TOLERANCE
        and math.isclose(a[n][2] % 180, b[n][2] % 180, abs_tol=1e-6)
        for n in a
    )


def test_frame_of_a_flipped_part(board: Path, tmp_path: Path) -> None:
    """Scenario "The frame of a flipped part"."""
    turned = _session(board, tmp_path / "turned.PcbDoc", [("rotate", "R1", 0)])
    before = {ref: _frame(turned, ref) for ref in ("D1", "R1")}
    steps = [("flip", "D1", 0.0), ("flip", "R1", 0.0)]
    down = _session(tmp_path / "turned.PcbDoc", tmp_path / "down.PcbDoc", steps)
    rotations = {ref: down.components[_index(down, ref)].rotation for ref in ("D1", "R1")}
    assert rotations == {"D1": 180.0, "R1": 90.0}
    for ref in ("D1", "R1"):
        assert down.components[_index(down, ref)].layer == "BOTTOM"
        assert _same(_frame(down, ref), before[ref]), (ref, _frame(down, ref), before[ref])
        # Altium's own flip of D1 (case J9, S-2122) writes ROTATION 180 and pad rotations 180, from 0 and 0
        index = _index(down, ref)
        pads = {p.rotation for p in down.pads if isinstance(p, PadRecord) and p.prefix.component == index}
        assert pads == {rotations[ref]}
    up = _session(tmp_path / "down.PcbDoc", tmp_path / "up.PcbDoc", [("flip", "D1", 1), ("flip", "R1", 1)])
    for ref in ("D1", "R1"):
        index = _index(up, ref)
        assert up.components[index].record.raw == turned.components[index].record.raw
        assert [p.raw for p in up.pads if isinstance(p, PadRecord) and p.prefix.component == index] == [
            p.raw for p in turned.pads if isinstance(p, PadRecord) and p.prefix.component == index
        ]


def test_the_old_frame_is_turned_by_a_half_turn(board: Path, tmp_path: Path) -> None:
    """Negative case: the frame the flip wrote before (``ROTATION`` −R, pads −r) reads the footprint turned
    by 180° against its library, the frame from which Altium rebuilt the pads on the old side."""
    before = _frame(read_pcbdoc(board.read_bytes()), "D1")
    down = _session(board, tmp_path / "down.PcbDoc", [("flip", "D1", 0)])
    state = State.of((tmp_path / "down.PcbDoc").read_bytes())
    index = _index(down, "D1")
    record = state.properties("Components6")[index]
    state.replace("Components6", index, rec.set_property(record.raw, {"ROTATION": " 0.00000000000000E+0000"}))
    old = _frame(read_pcbdoc(state.data()), "D1")
    assert _same(_frame(down, "D1"), before)
    assert not _same(old, before)
    assert _same({n: (-x, -y, r) for n, (x, y, r) in old.items()}, before)


def _with_body(board: Path) -> Path:
    """The kit board with an extruded body on ``D1``: a square about its origin, ``BODYPROJECTION=0``."""
    state = State.of(board.read_bytes(), file=board.name)
    doc = read_pcbdoc(board.read_bytes())
    index = _index(doc, "D1")
    part = doc.components[index]
    assert part.x is not None and part.y is not None
    x, y, half = int(part.x), int(part.y), 300_000
    corners = [(x - half, y - half), (x + half, y - half), (x + half, y + half), (x - half, y + half)]
    raw = body_record(
        BODY_TOP_LAYER, corners, component=index, standoff=0, overall=500_000, bottom=False, model_id="c0453"
    )
    state.append("ComponentBodies6", raw)
    board.write_bytes(state.data())
    return board


def test_a_body_follows_the_side(board: Path, tmp_path: Path) -> None:
    """Scenario "A body follows the side"."""
    source = _with_body(board)
    keys_before = rec.region_keys(State.of(source.read_bytes()).get("ComponentBodies6")[-1])
    assert (keys_before["BODYPROJECTION"], keys_before["MODEL.3D.ROTZ"]) == ("0", "0.000")
    _session(source, tmp_path / "down.PcbDoc", [("flip", "D1", 0)])
    keys = rec.region_keys(State.of((tmp_path / "down.PcbDoc").read_bytes()).get("ComponentBodies6")[-1])
    turned = (keys["BODYPROJECTION"], keys["MODEL.3D.ROTZ"], keys["MODEL.2D.ROTATION"])
    assert turned == ("1", "180.000", "180.000")
    for key in ("MODEL.3D.ROTX", "MODEL.3D.ROTY", "MODEL.3D.DZ", "STANDOFFHEIGHT", "OVERALLHEIGHT"):
        assert keys.get(key) == keys_before.get(key), key
    _session(tmp_path / "down.PcbDoc", tmp_path / "up.PcbDoc", [("flip", "D1", 1)])
    keys_after = rec.region_keys(State.of((tmp_path / "up.PcbDoc").read_bytes()).get("ComponentBodies6")[-1])
    assert keys_after == keys_before
