# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Route search and free channel in the API (change c0501, requirements "Route search and free channel in
the API" and "Found copper queued on a session"), on PCB documents authored for Fenolite: a slot between a
pad of class ``HV`` and a pad of another net (``_altium_pour``), and the Part J kit board."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import _altium_pour as pour
import pytest

from fenolite.api.board import read_board
from fenolite.api.route import RouteFound, find_route, free_channel
from fenolite.backends.altium import edit
from fenolite.backends.altium.pcbdoc import NetClassSpec, write_pcbdoc
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.core.coords import Point
from fenolite.model.rules import Rule, Selector

MM = 1_000_000
OPEN = dict.fromkeys(edit.OPERATIONS, True)
HV = Rule(
    id="rule_hv",
    name="hv",
    kind="clearance",
    selector_a=Selector("netclass", "HV"),
    selector_b=Selector("all"),
    min=MM,
    priority=1,
)
"""The clearance between class ``HV`` and everything, 1 mm, over the 0.2 mm default."""


def _slot(folder: Path) -> Path:
    """Pad ``H`` (class ``HV``, 1 mm) from the left edge to x = 18 mm and pad ``D`` from x = 22 mm to the
    right edge, both 2 mm high at y = 15 mm; net ``S`` has no copper; the default clearance is 0.2 mm."""
    board = pour.Board(
        zones=(),
        pads=(
            pour.pad("pad_h", "H", 9, 15, size=(18, 2)),
            pour.pad("pad_d", "D", 31, 15, size=(18, 2)),
            pour.pad("pad_s", "S", 20, 2, size=(0.5, 0.5)),
        ),
        rules=(pour.clearance(0.2), HV),
    )
    spec = dataclasses.replace(board.spec(), net_classes=(NetClassSpec("HV", ("H",)),))
    path = folder / "slot.PcbDoc"
    path.write_bytes(write_pcbdoc(spec, filename=path.name))
    return path


def _ends(path: Path) -> tuple[tuple[Point, str], tuple[Point, str], int]:
    """Two points of the slot's axis 10 mm below and above the pads, in the model frame, and the slot's
    centre x."""
    pads = {p.net: p.position for p in read_board(path).pads or () if p.net in ("H", "D")}
    x, y = (pads["H"].x + pads["D"].x) // 2, pads["H"].y
    return (Point(x, y - 10 * MM), "F.Cu"), (Point(x, y + 10 * MM), "F.Cu"), x


def test_same_answer_from_a_file_and_from_a_session(tmp_path: Path) -> None:
    """Scenario "Same answer from a file and from a session"."""
    path = _slot(tmp_path)
    a, b, _ = _ends(path)
    session = edit.open(path, gates=OPEN)
    found = [
        find_route(given, net="S", start=a, end=b, width=MM // 2, grid=500_000, max_vias=0)
        for given in (path, session)
    ]
    assert all(f.found is not None for f in found)
    assert found[0].found == found[1].found


def test_net_class_clearance_from_the_board_rules(tmp_path: Path) -> None:
    """Scenario "Net-class clearance from the board's rules": the free gap of the pinch is the 4 mm slot
    less 1 mm on the ``HV`` side and the 0.2 mm default on the other."""
    path = _slot(tmp_path)
    a, b, _ = _ends(path)
    channel = free_channel(path, net="S", start=a, end=b, grid=500_000, resolution=100_000)
    assert channel.low is not None and channel.path is not None and channel.pinch is not None
    # the document's unit (1/10 000 mil) rounds the pads and the rule by a few nanometres
    assert abs(channel.pinch.free - (4 * MM - MM - 200_000)) <= 10
    assert {channel.pinch.a.net, channel.pinch.b.net} == {"H", "D"}
    assert channel.low <= channel.pinch.free and channel.grid_limited


def test_an_unknown_end_names_the_closest(tmp_path: Path) -> None:
    from fenolite.api.route import EndpointError

    path = _slot(tmp_path)
    with pytest.raises(EndpointError) as raised:
        find_route(path, net="S", start=(Point(0, 0), "F.Cuu"), end="X9-1", width=MM)
    assert raised.value.hint is not None and "F.Cu" in raised.value.hint


def _two_sided(folder: Path) -> Path:
    """A board with a GND track on each side and a GND via of 0.6/0.3 mm (the templates of the clones)."""
    board = pour.Board(
        zones=(),
        tracks=(
            pour.track("trk_top", "GND", (2, 2), (6, 2)),
            pour.track("trk_bottom", "GND", (2, 4), (6, 4), layer="B.Cu"),
        ),
        vias=(pour.via("via_gnd", "GND", 6, 2),),
        rules=(pour.clearance(0.2),),
    )
    path = folder / "two.PcbDoc"
    path.write_bytes(write_pcbdoc(board.spec(), filename=path.name))
    return path


def test_queue_a_path_with_a_via(tmp_path: Path) -> None:
    """Scenario "A path with a via": two segments on Top, a via and one segment on Bottom. The Part J kit
    board holds no track on Bottom to clone, so the board is authored with one (decision of change c0501)."""
    path = _two_sided(tmp_path)
    design = read_board(path).design
    assert design.board is not None
    [via] = design.board.vias
    start, x, y = via.position, via.position.x, via.position.y
    bend, end, far = Point(x, y - 5 * MM), Point(x + 5 * MM, y - 5 * MM), Point(x + 5 * MM, y - 9 * MM)
    found = RouteFound(
        "GND", 250_000, (("F.Cu", (start, bend, end)), ("B.Cu", (end, far))), (end,), 600_000, 300_000
    )
    session = edit.open(path, gates=OPEN)
    assert isinstance(session, edit.Session)
    assert found.queue_on(session) == ()
    assert len(session.queued) == 4 and all(q.gate == "clone" for q in session.queued)
    out = tmp_path / "out.PcbDoc"
    receipt = session.commit(out, backup=False)
    assert receipt.written, receipt.issues
    before, after = read_pcbdoc(path.read_bytes()), read_pcbdoc(out.read_bytes())
    assert len(after.tracks) == len(before.tracks) + 3 and len(after.vias) == len(before.vias) + 1
    placed = read_board(out).design
    assert placed.board is not None
    assert any(v.position == end for v in placed.board.vias)


def _kit(tmp_path: Path) -> Path:
    from tests.unit.backends.altium.test_part_j import build_board

    build_board(tmp_path)
    return tmp_path / "edit.PcbDoc"


def test_no_via_to_copy(tmp_path: Path) -> None:
    """Scenario "No via to copy"."""
    path = _kit(tmp_path)
    end = Point(48_000_000, -27_000_000)
    found = RouteFound(
        "GND", 250_000, (("F.Cu", (Point(45_400_001, -27_000_000), end)),), (end,), MM, 500_000
    )
    session = edit.open(path, gates=OPEN)
    assert isinstance(session, edit.Session)
    assert [i.code for i in found.queue_on(session)] == ["route.via-template"] and session.queued == []
