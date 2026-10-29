# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The style report of routed copper (capability copper-tidy, "Style report"; ``docs/copper.md``, "Copper
tidy"; ``fenolite tidy --report``).

It reads the design only. Per net class (the net's class, else ``Default``) and copper layer it counts:

- the joints where exactly two track ends of one net meet, by kind (``angles.joint_kind``): ``45`` (a 45°
  turn), ``90``, ``acute`` (an inner angle below 90°) and ``other``; straight joints are not counted. Where
  three or more track ends meet, each pair at an acute angle counts as an acute joint;
- the jogs: tracks shorter than three widths whose two ends are turning joints of two tracks;
- the length of tracks and arcs per width (each the floor of its exact length, an arc ``r·θ``);

and per net class the vias. Each acute joint gives ``tidy.acute`` (warning) at its point.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection
from dataclasses import dataclass
from itertools import combinations

from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.units import format_length
from fenolite.geometry import arc_length, floor_sqrt
from fenolite.model.board import Track
from fenolite.model.design import Design
from fenolite.tidy.angles import joint_kind, vector
from fenolite.tidy.codes import issue
from fenolite.tidy.graph import copper_layers
from fenolite.tidy.prune import selected_nets

DEFAULT_CLASS = "Default"
"""The class of a net without one."""
JOINT_KINDS = ("45", "90", "acute", "other")
"""The kinds of joints that the report counts."""
JOG_WIDTHS = 3
"""A jog is shorter than this many track widths."""


@dataclass(frozen=True, slots=True)
class StyleRow:
    """The counts of one net class on one copper layer; ``widths`` holds (width, length) in nm by width."""

    netclass: str
    layer: str
    joints_45: int = 0
    joints_90: int = 0
    acute: int = 0
    other: int = 0
    jogs: int = 0
    widths: tuple[tuple[int, int], ...] = ()

    def as_json(self) -> dict[str, object]:
        return {
            "netclass": self.netclass,
            "layer": self.layer,
            "joints_45": self.joints_45,
            "joints_90": self.joints_90,
            "acute": self.acute,
            "other": self.other,
            "jogs": self.jogs,
            "widths": [{"width": width, "length": length} for width, length in self.widths],
        }


@dataclass(frozen=True, slots=True)
class StyleReport:
    """The rows by net class and copper layer, the vias as (net class, count) by class, and the
    ``tidy.acute`` issues."""

    rows: tuple[StyleRow, ...] = ()
    vias: tuple[tuple[str, int], ...] = ()
    issues: tuple[Issue, ...] = ()

    def counts(self) -> dict[str, int]:
        """The sums over all rows: joints by kind, jogs and vias."""
        return {
            "joints_45": sum(row.joints_45 for row in self.rows),
            "joints_90": sum(row.joints_90 for row in self.rows),
            "acute": sum(row.acute for row in self.rows),
            "other": sum(row.other for row in self.rows),
            "jogs": sum(row.jogs for row in self.rows),
            "vias": sum(count for _, count in self.vias),
        }

    def as_json(self) -> dict[str, object]:
        return {
            "rows": [row.as_json() for row in self.rows],
            "vias": [{"netclass": name, "count": count} for name, count in self.vias],
            "counts": self.counts(),
        }


def _away(track: Track, at: Point) -> tuple[int, int]:
    return vector(at, track.end if track.start == at else track.start)


def style(design: Design, *, nets: Collection[str] | None = None) -> StyleReport:
    """The style report of the nets named by ``nets`` (every net for ``None``); see the module."""
    board = design.board
    if board is None:
        return StyleReport()
    classes = {netclass.id: netclass.name for netclass in design.circuit.netclasses}
    names = dict(selected_nets(design, nets))
    class_of = {
        net.id: classes.get(net.netclass_id or "", DEFAULT_CLASS)
        for net in design.circuit.nets
        if net.id in names
    }
    copper = copper_layers(board)
    joints: dict[tuple[str, str], Counter[str]] = {}
    widths: dict[tuple[str, str], Counter[int]] = {}
    jogs: Counter[tuple[str, str]] = Counter()
    issues: list[Issue] = []
    tracks = [
        track
        for track in board.tracks
        if track.net_id in names and track.layer in copper and track.start != track.end
    ]
    for track in tracks:
        length = floor_sqrt((track.end.x - track.start.x) ** 2 + (track.end.y - track.start.y) ** 2)
        widths.setdefault((class_of[track.net_id or ""], track.layer), Counter())[track.width] += length
    for arc in board.arcs:
        if arc.net_id in names and arc.layer in copper:
            key = (class_of[arc.net_id or ""], arc.layer)
            widths.setdefault(key, Counter())[arc.width] += arc_length(arc.start, arc.mid, arc.end)
    ends: dict[tuple[str, str, Point], list[Track]] = {}
    for track in tracks:
        for point in (track.start, track.end):
            ends.setdefault((track.net_id or "", track.layer, point), []).append(track)
    turning: set[tuple[str, str, Point]] = set()
    for key in sorted(
        ends, key=lambda found: (names[found[0]], copper.index(found[1]), found[2].x, found[2].y)
    ):
        held = sorted(ends[key], key=lambda track: track.id)
        if len(held) < 2:
            continue
        net_id, layer, at = key
        row = joints.setdefault((class_of[net_id], layer), Counter())
        for a, b in combinations(held, 2):
            kind = joint_kind(_away(a, at), _away(b, at))
            if len(held) == 2 and kind != "straight":
                row[kind] += 1
                turning.add(key)
            elif kind == "acute":
                row[kind] += 1
            if kind == "acute":
                issues.append(_acute(names[net_id], layer, at, a, b))
    for track in tracks:
        length = floor_sqrt((track.end.x - track.start.x) ** 2 + (track.end.y - track.start.y) ** 2)
        net_id = track.net_id or ""
        if length < JOG_WIDTHS * track.width and all(
            (net_id, track.layer, point) in turning for point in (track.start, track.end)
        ):
            jogs[(class_of[net_id], track.layer)] += 1
    keys = sorted({*joints, *widths}, key=lambda key: (key[0], copper.index(key[1])))
    rows = tuple(
        StyleRow(
            name,
            layer,
            joints_45=joints.get((name, layer), Counter())["45"],
            joints_90=joints.get((name, layer), Counter())["90"],
            acute=joints.get((name, layer), Counter())["acute"],
            other=joints.get((name, layer), Counter())["other"],
            jogs=jogs[(name, layer)],
            widths=tuple(sorted(widths.get((name, layer), Counter()).items())),
        )
        for name, layer in keys
    )
    vias = Counter(class_of[via.net_id] for via in board.vias if via.net_id in names)
    return StyleReport(rows, tuple(sorted(vias.items())), tuple(issues))


def _acute(net: str, layer: str, at: Point, a: Track, b: Track) -> Issue:
    return issue(
        "tidy.acute",
        f"tracks {a.id} and {b.id} of net {net} meet at an acute angle on {layer} at "
        f"({format_length(at.x)}, {format_length(at.y)})",
        where=f"{a.id}, {b.id}",
        hint="route the joint again, or straighten it with fenolite tidy --straighten",
    )


__all__ = ["DEFAULT_CLASS", "JOG_WIDTHS", "JOINT_KINDS", "StyleReport", "StyleRow", "style"]
