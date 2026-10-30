# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper of a board as tables (change c0275, design decision 6): tracks and arcs grouped by net,
layer, width and lock flag, vias by net, sizes, kind, span, protection and lock flag; each group is one
``track_table``, ``arc_table`` or ``via_table`` keyed ``<net>/<layer>/<n>`` (``<net>/via/<n>`` for vias),
its rows sorted by their coordinates in the frame of ``place()``.

Copper that no table can hold (no net, a segment of zero length, an arc on one line, a protection the DSL
cannot say) is counted by kind for the coverage (decision 10). A via keeps its teardrop settings, which the
reader leaves in the via's ``teardrops`` slot (change c0277): vias are grouped by them too, and a child the
import cannot read is counted as ``teardrop-setting`` while the via is written without it.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad import teardrops as tdlib
from fenolite.backends.kicad.copper import copper_uuid
from fenolite.backends.kicad.sexpr import Node
from fenolite.core.coords import Point
from fenolite.importer.keys import segment
from fenolite.model.base import Entity, Opaque
from fenolite.model.board import Board, Teardrop, ViaProtection

ORIGIN = Point(100_000_000, 100_000_000)
"""``BOARD_ORIGIN`` of the DSL: the frame of ``place()`` starts there."""
Row = tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Table:
    """One copper table: its kind (``track``, ``arc`` or ``via``), key, net name, sorted rows and the
    shared fields (``layer`` and ``width`` of tracks and arcs; ``diameter``, ``drill``, ``via_kind``,
    ``layers``, ``protection`` and ``teardrop`` of vias)."""

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
    teardrop: Teardrop | None = None
    free: bool = False
    """The vias are KiCad's free vias, ``(free yes)`` (change c0277)."""


@dataclass(frozen=True, slots=True)
class Tables:
    """The tables of a board in key order, and the copper left out by kind."""

    tables: tuple[Table, ...] = ()
    left_out: Mapping[str, int] = field(default_factory=lambda: {})
    teardrops_lost: int = 0
    """Vias left out that hold teardrop settings: KiCad would not draw their teardrops again."""
    built: Mapping[str, str] = field(default_factory=lambda: {})
    """The KiCad uuid of each source track, arc and via a table holds → the uuid its row takes in a build
    (``copper.copper_uuid`` of the table key and the row), so text that names copper by uuid (the
    ``members`` of a ``generated`` item) can follow it (change c0277)."""

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


def teardrop_arguments(teardrop: Teardrop) -> list[tuple[str, object]]:
    """The keyword arguments of ``teardrop()`` that state ``teardrop``: every field that is not ``None``,
    and ``enabled`` only when it is ``False``."""
    out: list[tuple[str, object]] = []
    for name in ("max_length", "max_width", "length_ratio", "width_ratio", "curved", "filter_ratio",
                 "two_segments", "prefer_zones"):  # fmt: skip
        value = getattr(teardrop, name)
        if value is not None:
            out.append((name, value))
    if not teardrop.enabled:
        out.append(("enabled", False))
    return out


def _protection_key(protection: ViaProtection) -> tuple[int, ...]:
    p = protection
    values = (
        p.tenting_front, p.tenting_back, p.covering_front, p.covering_back, p.plugging_front, p.plugging_back,
        p.capping, p.filling,
    )  # fmt: skip
    return tuple(-1 if v is None else int(v) for v in values)


def via_teardrop(item: Entity) -> tuple[Teardrop | None, bool]:
    """``(settings, understood)`` of the ``teardrops`` child the reader kept in the slots of a via or pad;
    an item without the child gives ``(None, True)``, one whose child the import cannot read
    ``(None, False)``."""
    bag = item.ext.get("kicad")
    for slot in slotlib.from_ext(bag) if bag is not None else ():
        if isinstance(slot, Opaque):
            child = slotlib.opaque_child(slot)
            if isinstance(child, Node) and child.name == tdlib.HEAD:
                found = tdlib.project(child)
                return found, found is not None
    return None, True


def via_free(via: Entity) -> bool:
    """Whether the reader kept KiCad's ``(free yes)`` in the slots of ``via`` (change c0277)."""
    bag = via.ext.get("kicad")
    for slot in slotlib.from_ext(bag) if bag is not None else ():
        if isinstance(slot, Opaque):
            child = slotlib.opaque_child(slot)
            if isinstance(child, Node) and child.name == "free":
                return [a.value for a in child.atoms()] in ([], ["yes"])
    return False


def has_teardrops(item: Entity) -> bool:
    """Whether a via or pad holds teardrop settings that are enabled, or that the import cannot read."""
    found, understood = via_teardrop(item)
    return not understood or (found is not None and found.enabled)


def _teardrop_key(teardrop: Teardrop | None) -> tuple[int, ...]:
    """A sortable key of a via's teardrop settings; ``()`` for none."""
    if teardrop is None:
        return ()
    values = (
        teardrop.enabled, teardrop.max_length, teardrop.max_width, teardrop.length_ratio,
        teardrop.width_ratio, teardrop.curved, teardrop.filter_ratio, teardrop.two_segments,
        teardrop.prefer_zones,
    )  # fmt: skip
    return tuple(-1 if v is None else int(v) for v in values)


def _collinear(a: Point, m: Point, b: Point) -> bool:
    return (m.x - a.x) * (b.y - a.y) - (m.y - a.y) * (b.x - a.x) == 0


def span_ok(kind: str, layers: tuple[str, ...], stack: tuple[str, ...]) -> bool:
    """Whether a via of ``kind`` between ``layers`` fits the copper ``stack`` as the build's resolver
    requires of a via table: a blind via joins one outer layer, or both (change c0277), a buried one none,
    a micro via one outer layer and the layer next to it; a through via spans the board."""
    if kind == "through":
        return True
    if len(layers) < 2 or layers[0] not in stack or layers[-1] not in stack:
        return False
    first, second = sorted((stack.index(layers[0]), stack.index(layers[-1])))
    outer = sum(1 for index in (first, second) if index in (0, len(stack) - 1))
    fits = {"blind": outer >= 1, "buried": outer == 0, "micro": outer == 1 and second - first == 1}
    return first != second and fits.get(kind, False)


_ViaGroup = tuple[
    list[tuple[Row, str]],
    int,
    int,
    str,
    "tuple[str, str] | None",
    ViaProtection,
    bool,
    "Teardrop | None",
    bool,
]
"""The rows of one via table and its shared fields, the ``free`` flag last (change c0277)."""


def copper_tables(board: Board, net_names: Mapping[str, str]) -> Tables:
    """The tables of ``board``'s tracks, arcs and vias; ``net_names`` maps net ids to names."""
    stack = tuple(
        layer.name for layer in sorted(board.layers, key=lambda la: la.ordinal) if layer.kind == "copper"
    )
    left: Counter[str] = Counter()
    lines: dict[tuple[str, str], dict[tuple[int, int, bool], list[tuple[Row, str]]]] = {}
    for track in board.tracks:
        net = net_names.get(track.net_id or "")
        if net is None:
            left["copper-without-net"] += 1
            continue
        if track.start == track.end:
            left["zero-length-track"] += 1
            continue
        groups = lines.setdefault((net, track.layer), {})
        groups.setdefault((0, track.width, track.locked), []).append(
            ((*_rel(track.start), *_rel(track.end)), track.native_ids.get("kicad", ""))
        )
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
            ((*_rel(arc.start), *_rel(arc.mid), *_rel(arc.end)), arc.native_ids.get("kicad", ""))
        )
    tables: list[Table] = []
    built: dict[str, str] = {}
    for (net, layer), groups in lines.items():
        for index, ((kind, width, locked), held) in enumerate(sorted(groups.items()), start=1):
            key = f"{segment(net)}/{segment(layer)}/{index}"
            ordered = sorted(held)
            stem = "seg" if kind == 0 else "arc"
            built.update(
                (uuid, copper_uuid(key, f"{stem}[{k}]")) for k, (_, uuid) in enumerate(ordered) if uuid
            )
            tables.append(
                Table(
                    "track" if kind == 0 else "arc",
                    key,
                    net,
                    tuple(row for row, _ in ordered),
                    locked,
                    layer=layer,
                    width=width,
                )
            )
    holes: dict[str, dict[tuple[object, ...], _ViaGroup]] = {}
    lost = 0
    for via in board.vias:
        net = net_names.get(via.net_id or "")
        reason = (
            "copper-without-net" if net is None
            else "via-protection" if not protection_ok(via.protection)
            else "via-span" if not span_ok(via.via_type, tuple(via.layers), stack)
            else ""
        )  # fmt: skip
        if reason or net is None:
            left[reason] += 1
            lost += has_teardrops(via)
            continue
        span = (via.layers[0], via.layers[-1]) if via.via_type != "through" and len(via.layers) >= 2 else None
        teardrop, understood = via_teardrop(via)
        if not understood:
            left["teardrop-setting"] += 1
        free = via_free(via)
        group = (via.diameter, via.drill, via.via_type, span or ("", ""), _protection_key(via.protection),
                 via.locked, _teardrop_key(teardrop), free)  # fmt: skip
        held = holes.setdefault(net, {})
        if group not in held:
            held[group] = (
                [],
                via.diameter,
                via.drill,
                via.via_type,
                span,
                via.protection,
                via.locked,
                teardrop,
                free,
            )
        held[group][0].append((_rel(via.position), via.native_ids.get("kicad", "")))
    for net, groups in holes.items():
        ordered = sorted(groups.items(), key=lambda item: item[0])  # type: ignore[arg-type,return-value]
        for index, (_, (rows, diameter, drill, kind, span, protection, locked, teardrop, free)) in enumerate(
            ordered, start=1
        ):
            key = f"{segment(net)}/via/{index}"
            placed = sorted(rows)
            built.update((uuid, copper_uuid(key, f"via[{k}]")) for k, (_, uuid) in enumerate(placed) if uuid)
            tables.append(
                Table(
                    "via",
                    key,
                    net,
                    tuple(row for row, _ in placed),
                    locked,
                    diameter=diameter,
                    drill=drill,
                    via_kind=kind,
                    layers=span,
                    protection=protection,
                    teardrop=teardrop,
                    free=free,
                )
            )
    return Tables(tuple(sorted(tables, key=lambda t: t.key)), dict(sorted(left.items())), lost, built)


__all__ = [
    "ORIGIN",
    "Table",
    "Tables",
    "copper_tables",
    "protect_arguments",
    "protection_ok",
    "has_teardrops",
    "via_free",
    "teardrop_arguments",
    "via_teardrop",
]
