# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper of a board as tables (change c0275, design decision 6): tracks and arcs grouped by net,
layer, width and lock flag, vias by net, sizes, kind, span, protection and lock flag; each group is one
``track_table``, ``arc_table`` or ``via_table`` keyed ``<net>/<layer>/<n>`` (``<net>/via/<n>`` for vias),
its rows sorted by their coordinates in the frame of ``place()``.

Copper that no table can hold (no net, a segment of zero length, an arc on one line, a protection the DSL
cannot say) is counted by kind for the coverage (decision 10).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field

from fenolite.core.coords import Point
from fenolite.importer.keys import segment
from fenolite.model.board import Board, ViaProtection

ORIGIN = Point(100_000_000, 100_000_000)
"""``BOARD_ORIGIN`` of the DSL: the frame of ``place()`` starts there."""
Row = tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Table:
    """One copper table: its kind (``track``, ``arc`` or ``via``), key, net name, sorted rows and the
    shared fields (``layer`` and ``width`` of tracks and arcs; ``diameter``, ``drill``, ``via_kind``,
    ``layers`` and ``protection`` of vias)."""

    kind: str
    key: str
    net: str
    rows: tuple[Row, ...]
    locked: bool = False
    layer: str = ""
    width: int = 0
    diameter: int = 0
    drill: int = 0
    via_kind: str = "through"
    layers: tuple[str, str] | None = None
    protection: ViaProtection = field(default_factory=ViaProtection)


@dataclass(frozen=True, slots=True)
class Tables:
    """The tables of a board in key order, and the copper left out by kind."""

    tables: tuple[Table, ...] = ()
    left_out: Mapping[str, int] = field(default_factory=lambda: {})

    def count(self, kind: str) -> int:
        return sum(len(table.rows) for table in self.tables if table.kind == kind)


def _rel(point: Point) -> tuple[int, int]:
    return point.x - ORIGIN.x, point.y - ORIGIN.y


UNSAID = "unsaid"
"""What ``_sided`` gives for a pair of sides ``protect()`` cannot say."""


def _sided(front: bool | None, back: bool | None) -> bool | str | None:
    """The ``protect()`` value of a pair of sides, or ``UNSAID`` when the DSL cannot say it."""
    table: dict[tuple[bool | None, bool | None], bool | str | None] = {
        (None, None): None,
        (True, True): True,
        (False, False): False,
        (True, False): "front",
        (False, True): "back",
    }
    return table.get((front, back), UNSAID)


def protection_ok(protection: ViaProtection) -> bool:
    """Whether ``protect()`` can say ``protection`` exactly."""
    pairs = (
        (protection.tenting_front, protection.tenting_back),
        (protection.covering_front, protection.covering_back),
        (protection.plugging_front, protection.plugging_back),
    )
    return all(_sided(*pair) != UNSAID for pair in pairs)


def protect_arguments(protection: ViaProtection) -> list[tuple[str, bool | str]]:
    """The keyword arguments of ``protect()`` for ``protection``, the ``None`` ones left out."""
    out: list[tuple[str, bool | str]] = []
    for name, pair in (
        ("tenting", (protection.tenting_front, protection.tenting_back)),
        ("covering", (protection.covering_front, protection.covering_back)),
        ("plugging", (protection.plugging_front, protection.plugging_back)),
    ):
        value = _sided(*pair)
        if value is not None and value != UNSAID:
            out.append((name, value))
    for name, whole in (("capping", protection.capping), ("filling", protection.filling)):
        if whole is not None:
            out.append((name, whole))
    return out


def _protection_key(protection: ViaProtection) -> tuple[int, ...]:
    p = protection
    values = (
        p.tenting_front, p.tenting_back, p.covering_front, p.covering_back, p.plugging_front, p.plugging_back,
        p.capping, p.filling,
    )  # fmt: skip
    return tuple(-1 if v is None else int(v) for v in values)


def _collinear(a: Point, m: Point, b: Point) -> bool:
    return (m.x - a.x) * (b.y - a.y) - (m.y - a.y) * (b.x - a.x) == 0


def span_ok(kind: str, layers: tuple[str, ...], stack: tuple[str, ...]) -> bool:
    """Whether a via of ``kind`` between ``layers`` fits the copper ``stack`` as the build's resolver
    requires: a blind via joins one outer layer, a buried one none, a micro via one outer layer and the
    layer next to it; a through via spans the board."""
    if kind == "through":
        return True
    if len(layers) < 2 or layers[0] not in stack or layers[-1] not in stack:
        return False
    first, second = sorted((stack.index(layers[0]), stack.index(layers[-1])))
    outer = sum(1 for index in (first, second) if index in (0, len(stack) - 1))
    fits = {"blind": outer == 1, "buried": outer == 0, "micro": outer == 1 and second - first == 1}
    return first != second and fits.get(kind, False)


def copper_tables(board: Board, net_names: Mapping[str, str]) -> Tables:
    """The tables of ``board``'s tracks, arcs and vias; ``net_names`` maps net ids to names."""
    stack = tuple(
        layer.name for layer in sorted(board.layers, key=lambda la: la.ordinal) if layer.kind == "copper"
    )
    left: Counter[str] = Counter()
    lines: dict[tuple[str, str], dict[tuple[int, int, bool], list[Row]]] = {}
    for track in board.tracks:
        net = net_names.get(track.net_id or "")
        if net is None:
            left["copper-without-net"] += 1
            continue
        if track.start == track.end:
            left["zero-length-track"] += 1
            continue
        groups = lines.setdefault((net, track.layer), {})
        groups.setdefault((0, track.width, track.locked), []).append((*_rel(track.start), *_rel(track.end)))
    for arc in board.arcs:
        net = net_names.get(arc.net_id or "")
        if net is None:
            left["copper-without-net"] += 1
            continue
        if len({arc.start, arc.mid, arc.end}) < 3 or _collinear(arc.start, arc.mid, arc.end):
            left["degenerate-arc"] += 1
            continue
        groups = lines.setdefault((net, arc.layer), {})
        groups.setdefault((1, arc.width, arc.locked), []).append(
            (*_rel(arc.start), *_rel(arc.mid), *_rel(arc.end))
        )
    tables: list[Table] = []
    for (net, layer), groups in lines.items():
        for index, ((kind, width, locked), rows) in enumerate(sorted(groups.items()), start=1):
            tables.append(
                Table(
                    "track" if kind == 0 else "arc",
                    f"{segment(net)}/{segment(layer)}/{index}",
                    net,
                    tuple(sorted(rows)),
                    locked,
                    layer=layer,
                    width=width,
                )
            )
    holes: dict[str, dict[tuple[object, ...], tuple[list[Row], int, int, str, tuple[str, str] | None,
                                                    ViaProtection, bool]]] = {}  # fmt: skip
    for via in board.vias:
        net = net_names.get(via.net_id or "")
        if net is None:
            left["copper-without-net"] += 1
            continue
        if not protection_ok(via.protection):
            left["via-protection"] += 1
            continue
        if not span_ok(via.via_type, tuple(via.layers), stack):
            left["via-span"] += 1
            continue
        span = (via.layers[0], via.layers[-1]) if via.via_type != "through" and len(via.layers) >= 2 else None
        group = (via.diameter, via.drill, via.via_type, span or ("", ""), _protection_key(via.protection),
                 via.locked)  # fmt: skip
        held = holes.setdefault(net, {})
        if group not in held:
            held[group] = ([], via.diameter, via.drill, via.via_type, span, via.protection, via.locked)
        held[group][0].append(_rel(via.position))
    for net, groups in holes.items():
        ordered = sorted(groups.items(), key=lambda item: item[0])  # type: ignore[arg-type,return-value]
        for index, (_, (rows, diameter, drill, kind, span, protection, locked)) in enumerate(
            ordered, start=1
        ):
            tables.append(
                Table(
                    "via",
                    f"{segment(net)}/via/{index}",
                    net,
                    tuple(sorted(rows)),
                    locked,
                    diameter=diameter,
                    drill=drill,
                    via_kind=kind,
                    layers=span,
                    protection=protection,
                )
            )
    return Tables(tuple(sorted(tables, key=lambda t: t.key)), dict(sorted(left.items())))


__all__ = ["ORIGIN", "Table", "Tables", "copper_tables", "protect_arguments", "protection_ok"]
