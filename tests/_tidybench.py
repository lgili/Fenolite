# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper-tidy bench of change c0208: authored two-layer boards built with ``tests/_ties.py``. No file
is read, nothing comes from a library, and every value is a round invented one.

``SIG`` joins ``U1-1`` at (10, 10) mm and ``U2-1`` at (30, 20) mm by ``t1`` along y 10 mm and ``t2`` down
x 30 mm: a right angle at (30, 10) mm. Its dangling copper: ``stub``, 2 mm from (20, 10) mm into the air,
and ``lead``, 4 mm from (15, 10) mm to the via ``v1``, which nothing joins on ``B.Cu``. ``BUS`` joins
``U3-1`` at (10, 30) mm and ``U4-1`` at (18, 36) mm only through ``k``, which runs on to a free end at
(25, 30) mm. Every track is 0.25 mm wide on ``F.Cu`` and the clearance is 0.3 mm."""

from __future__ import annotations

import dataclasses

from _groundties import _p, _via
from _ties import MM, TieBoard, tie_footprint

from fenolite.model.design import Design

ONE = tie_footprint("ONE", (0,))
"""A footprint of one square pad of 1 mm."""
CLEARANCE = 3 * MM // 10
LEG = MM // 2
"""The default leg of a chamfer of the bench's tracks: twice their width."""


def bench(
    *,
    stub: bool = True,
    lead: bool = True,
    bus: bool = True,
    locked_stub: bool = False,
    intruder: bool = False,
) -> Design:
    """The bench. ``locked_stub`` adds the locked stub ``lock`` at x 25 mm; ``intruder`` adds ``V1-1`` of
    net ``OTHER`` inside the corner of ``SIG``, 0.375 mm from both tracks: a chamfer there comes within
    0.23 mm of it."""
    board = TieBoard(clearance=CLEARANCE)
    board.place("U1", ONE, _p(10, 10), nets={"1": "SIG"})
    board.place("U2", ONE, _p(30, 20), nets={"1": "SIG"})
    board.track("t1", "SIG", _p(10, 10), _p(30, 10))
    board.track("t2", "SIG", _p(30, 10), _p(30, 20))
    if stub:
        board.track("stub", "SIG", _p(20, 10), _p(20, 12))
    if lead:
        board.track("lead", "SIG", _p(15, 10), _p(15, 14))
    if bus:
        board.place("U3", ONE, _p(10, 30), nets={"1": "BUS"})
        board.place("U4", ONE, _p(18, 36), nets={"1": "BUS"})
        board.track("k", "BUS", _p(10, 30), _p(25, 30))
        board.track("m", "BUS", _p(18, 36), _p(18, 30))
    if locked_stub:
        board.track("lock", "SIG", _p(25, 10), _p(25, 8))
    if intruder:
        board.place("V1", ONE, _p(29, 11), nets={"1": "OTHER"})
    design = board.build()
    built = design.board
    assert built is not None
    tracks = tuple(
        dataclasses.replace(track, locked=True) if locked_stub and track.start == _p(25, 10) else track
        for track in built.tracks
    )
    vias = (_via(1, board.net("SIG"), _p(15, 14)),) if lead else ()
    return dataclasses.replace(design, board=dataclasses.replace(built, tracks=tracks, vias=vias))


def corner(width: int) -> Design:
    """An L of two tracks of ``width`` between ``U1-1`` at (10, 10) mm and ``U2-1`` at (30, 20) mm."""
    board = TieBoard(clearance=CLEARANCE)
    board.place("U1", ONE, _p(10, 10), nets={"1": "SIG"})
    board.place("U2", ONE, _p(30, 20), nets={"1": "SIG"})
    board.track("t1", "SIG", _p(10, 10), _p(30, 10), width=width)
    board.track("t2", "SIG", _p(30, 10), _p(30, 20), width=width)
    return board.build()


def staircase(*, net: str = "SIG", partner: str | None = None, blocker: bool = False) -> Design:
    """The staircase of change c0214: ``U1-1`` at (10, 10) mm and ``U2-1`` at (20, 14) mm of ``net``,
    joined by a track to (12, 10) mm and eight steps of 0.5 mm up and 1 mm right: 17 tracks, 16 right
    angles. ``partner`` adds a pad ``P1-1`` of that net at (40, 30) mm; ``blocker`` adds ``V1-1`` of net
    ``OTHER`` at (12, 13) mm, on the diagonal from (10, 10) mm to (14, 14) mm and clear of the steps."""
    board = TieBoard(clearance=CLEARANCE)
    board.place("U1", ONE, _p(10, 10), nets={"1": net})
    board.place("U2", ONE, _p(20, 14), nets={"1": net})
    board.track("h0", net, _p(10, 10), _p(12, 10))
    for step in range(8):
        x, y = 12 + step, 10 + step / 2
        board.track(f"v{step + 1}", net, _p(x, y), _p(x, y + 0.5))
        board.track(f"h{step + 1}", net, _p(x, y + 0.5), _p(x + 1, y + 0.5))
    if partner is not None:
        board.place("P1", ONE, _p(40, 30), nets={"1": partner})
    if blocker:
        board.place("V1", ONE, _p(12, 13), nets={"1": "OTHER"})
    return board.build()


def acute() -> Design:
    """One joint at 30° (change c0214): ``U1-1`` at (10, 10) mm and ``U2-1`` at (11.34, 15) mm of ``SIG``,
    joined by a track to (20, 10) mm and a track back at 30° to it."""
    board = TieBoard(clearance=CLEARANCE)
    board.place("U1", ONE, _p(10, 10), nets={"1": "SIG"})
    board.place("U2", ONE, _p(11.34, 15), nets={"1": "SIG"})
    board.track("a", "SIG", _p(10, 10), _p(20, 10))
    board.track("b", "SIG", _p(20, 10), _p(11.34, 15))
    return board.build()


__all__ = ["CLEARANCE", "LEG", "ONE", "acute", "bench", "corner", "staircase"]
