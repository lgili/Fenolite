# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Routed designs for the level-5 tests (capability design-equivalence, change c0089), built by hand.

``routed()`` is a board of three copper layers (``Top``, ``Mid``, ``Bottom``) with two connectors of two
through-hole pads (``J1``, ``J2``) and two resistors of two top pads (``R1``, ``R2``). Every value is
authored for these tests. In millimetres:

- ``A`` joins ``J1-1`` (0, 0) and ``J2-1`` (20, 0): a top track to a via at (10, 0), a bottom track on.
- ``B`` joins ``J1-2`` (0, 5) and ``J2-2`` (20, 5): one top track, and a second way round on the bottom
  layer between two vias at (5, 5) and (15, 5), so that one via or the bottom track can go and the pads
  stay joined.
- ``C`` joins ``R1-1`` (9, 10) and ``R2-1`` (9, 15) by one top track.
- ``D`` joins ``R1-2`` (11, 10) and ``R2-2`` (11, 15) by a top track with a half circle in its middle.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Sequence
from typing import Any

from _cases import design, netted, pad

from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.model.board import Arc, Board, Track, Via, Zone, ZoneFill
from fenolite.model.design import Design

MM = 1_000_000
WIDTH = 250_000
THROUGH = {"kind": "thru_hole", "shape": "circle", "size": Size(1_500_000, 1_500_000), "drill": 800_000}
ALL = ("Top", "Mid", "Bottom")


def _id(prefix: str, name: str) -> str:
    return derived_id(prefix, "test", f"route-{name}")


def mm(x: float, y: float) -> Point:
    return Point(round(x * MM), round(y * MM))


def net_id(found: Design, name: str) -> str:
    return next(net.id for net in found.circuit.nets if net.name == name)


def track(
    found: Design, key: str, net: str, a: Point, b: Point, layer: str = "Top", width: int = WIDTH
) -> Track:
    return Track(id=_id("trk", key), start=a, end=b, width=width, layer=layer, net_id=net_id(found, net))


def via(found: Design, key: str, net: str, at: Point, **fields: Any) -> Via:
    values: dict[str, Any] = {"diameter": 600_000, "drill": 300_000, "layers": ("Top", "Bottom")}
    values.update(fields)
    return Via(id=_id("via", key), position=at, net_id=net_id(found, net), **values)


def arc(found: Design, key: str, net: str, a: Point, m: Point, b: Point, layer: str = "Top") -> Arc:
    return Arc(id=_id("arc", key), start=a, mid=m, end=b, width=WIDTH, layer=layer, net_id=net_id(found, net))


def zone(found: Design, key: str, net: str, layer: str, ring: Sequence[Point], *, filled: bool) -> Zone:
    fills = (ZoneFill(layer, tuple(ring)),) if filled else ()
    return Zone(
        id=_id("zon", key), outline=tuple(ring), layers=(layer,), net_id=net_id(found, net), fills=fills,
        filled=filled,
    )  # fmt: skip


def board(found: Design) -> Board:
    assert found.board is not None
    return found.board


def with_board(found: Design, **changes: Any) -> Design:
    return dataclasses.replace(found, board=dataclasses.replace(board(found), **changes))


def parts() -> Design:
    """The four placed parts with their nets and no copper."""
    hole = {"layers": ALL, **THROUGH}
    bare = design(
        [("J1", "CONN"), ("J2", "CONN"), ("R1", "1k"), ("R2", "1k")],
        {
            "J1": (pad("1", 0, 0, **hole), pad("2", 0, 5 * MM, **hole)),
            "J2": (pad("1", 0, 0, **hole), pad("2", 0, 5 * MM, **hole)),
            "R1": (pad("1", -MM, 0), pad("2", MM, 0)),
            "R2": (pad("1", -MM, 0), pad("2", MM, 0)),
        },
        {"J1": mm(0, 0), "J2": mm(20, 0), "R1": mm(10, 10), "R2": mm(10, 15)},
        name="routed",
    )
    return netted(
        bare,
        {
            "A": (("J1", "1"), ("J2", "1")),
            "B": (("J1", "2"), ("J2", "2")),
            "C": (("R1", "1"), ("R2", "1")),
            "D": (("R1", "2"), ("R2", "2")),
        },
    )


def routed() -> Design:
    """The routed board of the module's docstring."""
    found = parts()
    tracks = (
        track(found, "a-top", "A", mm(0, 0), mm(10, 0)),
        track(found, "a-bottom", "A", mm(10, 0), mm(20, 0), "Bottom"),
        track(found, "b-top", "B", mm(0, 5), mm(20, 5)),
        track(found, "b-bottom", "B", mm(5, 5), mm(15, 5), "Bottom"),
        track(found, "c-top", "C", mm(9, 10), mm(9, 15)),
        track(found, "d-1", "D", mm(11, 10), mm(11, 12)),
        track(found, "d-2", "D", mm(11, 13), mm(11, 15)),
    )
    vias = (
        via(found, "a", "A", mm(10, 0)),
        via(found, "b-1", "B", mm(5, 5)),
        via(found, "b-2", "B", mm(15, 5)),
    )
    arcs = (arc(found, "d", "D", mm(11, 12), mm(11.5, 12.5), mm(11, 13)),)
    return with_board(found, tracks=tracks, vias=vias, arcs=arcs)


def without(found: Design, *keys: str) -> Design:
    """``found`` without the tracks, arcs and vias of those keys."""
    gone = {_id(prefix, key) for key in keys for prefix in ("trk", "via", "arc")}

    def kept(items: Sequence[Any]) -> tuple[Any, ...]:
        left = tuple(item for item in items if item.id not in gone)
        return left

    held = board(found)
    after = with_board(found, tracks=kept(held.tracks), vias=kept(held.vias), arcs=kept(held.arcs))
    count = len(held.tracks) + len(held.vias) + len(held.arcs)
    assert count - len(board(after).tracks) - len(board(after).vias) - len(board(after).arcs) == len(keys)
    return after


def with_track(found: Design, key: str, **changes: Any) -> Design:
    """``found`` with fields of the track ``key`` changed."""
    wanted = _id("trk", key)
    assert any(t.id == wanted for t in board(found).tracks)
    tracks = tuple(dataclasses.replace(t, **changes) if t.id == wanted else t for t in board(found).tracks)
    return with_board(found, tracks=tracks)


def resegmented(found: Design, choose: Callable[[Track], Sequence[Point]]) -> Design:
    """``found`` with each track cut at the points ``choose`` gives for it (points of the track, in order
    from its start)."""
    tracks: list[Track] = []
    for item in board(found).tracks:
        points = [item.start, *choose(item), item.end]
        for k, (a, b) in enumerate(zip(points, points[1:], strict=False)):
            tracks.append(dataclasses.replace(item, id=_id("trk", f"{item.id}-{k}"), start=a, end=b))
    return with_board(found, tracks=tuple(tracks))


__all__ = [
    "ALL",
    "MM",
    "WIDTH",
    "arc",
    "board",
    "mm",
    "net_id",
    "parts",
    "resegmented",
    "routed",
    "track",
    "via",
    "with_board",
    "with_track",
    "without",
    "zone",
]
