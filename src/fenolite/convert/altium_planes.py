# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The internal planes of an Altium design carried through KiCad (change c0466; capability
design-conversion, "Altium internal planes through KiCad and back").

KiCad's file has no slot for a layer's net. A conversion to KiCad types each internal plane's row ``power``
and names it after the plane (``altium_to_kicad.copper_rows``), and writes in the board property
``PROPERTY`` (``backends.kicad.boardcarrier``) each plane's row, its ``PLANE<k>NETNAME`` text, its pull-back
and its ``Split Plane`` polygons (each a net and a straight ring in the frame of the design), with the low
corner of the board's edge. The conversion back (``restored``) gives each plane whose row is still a
``power`` row and whose nets the design holds its ``plane_net`` again and the writer its splits
(``lower.CarriedPlane``), moved by the translation of the edge's corner; every other plane is a ``plane``
loss.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping, Sequence
from typing import Any, cast

from fenolite.core.coords import Point
from fenolite.model.base import ExtBag
from fenolite.model.board import Board, Layer
from fenolite.model.design import Design

PROPERTY = "Fenolite.Altium.Planes"
"""The board property that carries the planes (``boardcarrier``)."""
SCHEMA = "fenolite.altium-planes.v0"
MULTIPLE_NETS = "(Multiple Nets)"
"""``PLANE<k>NETNAME`` of a plane split between several nets (``pcb-copper.md``, S-2250)."""
PULLBACK = 508_000
"""20 mil: the pull-back of a plane whose document holds no ``PLANE<k>PULLBACK`` (``libboard.PULLBACK``)."""
EDGE = "Edge.Cuts"

KIND = "plane"
ROW_GONE = (
    "the KiCad board no longer holds the plane's row as a power row, so it is written as a signal layer"
)
NET_GONE = "the design no longer holds a net of the plane, so it is written as a signal layer"


@dataclasses.dataclass(frozen=True, slots=True)
class Split:
    """One ``Split Plane`` polygon: its net's name and its ring, in the frame of the design."""

    net: str
    points: tuple[Point, ...]


@dataclasses.dataclass(frozen=True, slots=True)
class Plane:
    """One carried plane: its KiCad row, its ``PLANE<k>NETNAME`` text, its pull-back (nanometres) and its
    splits, in ``Polygons6`` order."""

    layer: str
    net: str
    pullback: int
    splits: tuple[Split, ...] = ()


@dataclasses.dataclass(frozen=True, slots=True)
class Carried:
    """The carried planes, in chain order, and the low corner of the board's edge when it has one."""

    planes: tuple[Plane, ...]
    corner: Point | None = None


def edge_corner(board: Board) -> Point | None:
    """The low corner of the board's edge: the least x and y of its outline and of its drawings on
    ``Edge.Cuts``; ``None`` for a board without either."""
    points = [p for g in board.graphics if g.layer == EDGE for p in g.points]
    if board.outline is not None:
        points += list(board.outline.points)
    if not points:
        return None
    return Point(min(p.x for p in points), min(p.y for p in points))


def _pair(layer: Layer, key: str) -> str | None:
    bag = layer.ext.get("altium")
    return None if bag is None else dict(bag.payload).get(key)


def _pullback(fields: Mapping[str, str], index: int) -> int:
    """The pull-back of Internal Plane ``index``: its ``PLANE<k>PULLBACK``, else the ``PULLBACKDISTANCE``
    of its row of the ``V9`` stack, else ``PULLBACK``."""
    from fenolite.backends.altium.adapter.units import text_length
    from fenolite.backends.altium.libboard import long_id

    length = text_length(fields.get(f"PLANE{index}PULLBACK"))
    if length is None:
        wanted = str(long_id(38 + index))
        for key, value in fields.items():
            if key.startswith("V9_STACK_LAYER") and key.endswith("_LAYERID") and value == wanted:
                length = text_length(fields.get(key.removesuffix("LAYERID") + "PULLBACKDISTANCE"))
                break
    return length[0] if length is not None else PULLBACK


def found(source: Design, target: Design, document: Any) -> Carried:
    """The planes of the imported ``source`` to carry into ``target``, its KiCad conversion, whose rows
    ``altium_to_kicad.copper_rows`` typed: each internal plane of the chain, in order, paired with the
    ``power`` rows of ``target`` in order, whose net is a net of the design, or ``(Multiple Nets)`` with
    splits; whose splits each name a net of the design; and whose splits hold no arc vertex. ``document`` is
    the source's PCB document as read (``read.pcb.PcbDocument``), or ``None``, which carries no split."""
    from fenolite.backends.altium.adapter.arcring import record_outline
    from fenolite.backends.kicad.layers import plane_layers
    from fenolite.convert.altium_to_kicad import plane_id

    board, written = source.board, target.board
    if board is None or written is None:
        return Carried(())
    copper = sorted((x for x in board.layers if plane_id(x) is not None), key=lambda x: x.ordinal)
    rows = plane_layers(target)
    if not copper or len(rows) != len(copper):
        return Carried(())
    nets = {net.name for net in source.circuit.nets}
    names = [n.name for n in document.nets] if document is not None else []
    fields = dict(document.board.record.fields) if document is not None else {}
    polygons = document.polygons if document is not None else ()
    planes: list[Plane] = []
    for layer, row in zip(copper, rows, strict=True):
        net = _pair(layer, "plane_net")
        index = cast(int, plane_id(layer)) - 38
        pullback = _pullback(fields, index)
        splits: list[Split] = []
        whole = True
        for polygon in polygons:
            if polygon.polygon_type != "Split Plane" or (polygon.layer or "").upper() != f"PLANE{index}":
                continue
            ring = record_outline(polygon.vertices, 1) if all(v.kind == 0 for v in polygon.vertices) else ()
            name = names[polygon.net] if polygon.net is not None and 0 <= polygon.net < len(names) else None
            if len(ring) < 3 or name not in nets:
                whole = False
                break
            splits.append(Split(cast(str, name), tuple(ring)))
        if net is None or not whole or (net not in nets and not (net == MULTIPLE_NETS and splits)):
            continue
        planes.append(Plane(row, net, pullback, tuple(splits)))
    return Carried(tuple(planes), edge_corner(written))


def _point(value: object) -> Point | None:
    items = cast("list[object]", value) if isinstance(value, list) else []
    if len(items) != 2 or not all(isinstance(v, int) and not isinstance(v, bool) for v in items):
        return None
    return Point(cast(int, items[0]), cast(int, items[1]))


def carrier_text(carried: Carried) -> str:
    """The property's canonical JSON text."""
    root: dict[str, object] = {
        "schema": SCHEMA,
        "corner": None if carried.corner is None else [carried.corner.x, carried.corner.y],
        "planes": [
            {
                "layer": plane.layer,
                "net": plane.net,
                "pullback": plane.pullback,
                "splits": [
                    {"net": split.net, "points": [[p.x, p.y] for p in split.points]} for split in plane.splits
                ],
            }
            for plane in carried.planes
        ],
    }
    return json.dumps(root, sort_keys=True, separators=(",", ":"))


def read_carrier(data: bytes | None) -> Carried:
    """The carried planes; none for no property, another schema or text that is no carrier. A plane entry
    that is not well formed is left out, and so is its plane."""
    if not data:
        return Carried(())
    try:
        loaded: object = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return Carried(())
    root = cast("dict[str, object]", loaded) if isinstance(loaded, dict) else {}
    if root.get("schema") != SCHEMA:
        return Carried(())
    entries = root.get("planes")
    planes: list[Plane] = []
    for entry in cast("list[object]", entries) if isinstance(entries, list) else []:
        row = cast("dict[str, object]", entry) if isinstance(entry, dict) else {}
        layer, net, pullback, raw = row.get("layer"), row.get("net"), row.get("pullback"), row.get("splits")
        if not isinstance(layer, str) or not isinstance(net, str) or not isinstance(pullback, int):
            continue
        splits: list[Split] = []
        for item in cast("list[object]", raw) if isinstance(raw, list) else []:
            part = cast("dict[str, object]", item) if isinstance(item, dict) else {}
            name, points = part.get("net"), part.get("points")
            ring = [_point(p) for p in (cast("list[object]", points) if isinstance(points, list) else [])]
            if isinstance(name, str) and len(ring) >= 3 and all(p is not None for p in ring):
                splits.append(Split(name, tuple(cast("list[Point]", ring))))
            else:
                splits = []
                break
        if raw and not splits:
            continue
        planes.append(Plane(layer, net, pullback, tuple(splits)))
    return Carried(tuple(planes), _point(root.get("corner")))


@dataclasses.dataclass(frozen=True, slots=True)
class Restored:
    """The design with each restored plane's ``plane_net`` again, the restored planes by row, and the lost
    ones as ``(layer id, reason)``."""

    design: Design
    planes: Mapping[str, Plane]
    lost: tuple[tuple[str, str], ...] = ()


def restored(design: Design, carried: Carried) -> Restored:
    """``design``, read from KiCad, with each carried plane whose row is still a copper ``power`` row and
    whose nets the design holds made a plane again: its layer's ``altium`` bag holds ``plane_net``. The
    restored planes' splits are moved by the translation of the edge's corner. Every other carried plane
    is lost with its reason."""
    from fenolite.backends.kicad.layers import plane_layers

    board = design.board
    if board is None or not carried.planes:
        return Restored(design, {})
    rows = set(plane_layers(design))
    nets = {net.name for net in design.circuit.nets}
    by_name = {layer.name: layer for layer in board.layers}
    corner = edge_corner(board)
    dx, dy = (
        (corner.x - carried.corner.x, corner.y - carried.corner.y)
        if corner is not None and carried.corner is not None
        else (0, 0)
    )
    kept: dict[str, Plane] = {}
    lost: list[tuple[str, str]] = []
    for plane in carried.planes:
        layer = by_name.get(plane.layer)
        wanted = {split.net for split in plane.splits} | ({plane.net} - {MULTIPLE_NETS})
        if layer is None or plane.layer not in rows:
            lost.append((layer.id if layer is not None else plane.layer, ROW_GONE))
            continue
        if not wanted <= nets:
            lost.append((layer.id, NET_GONE))
            continue
        moved = tuple(Split(s.net, tuple(Point(p.x + dx, p.y + dy) for p in s.points)) for s in plane.splits)
        kept[plane.layer] = dataclasses.replace(plane, splits=moved)
    layers: list[Layer] = []
    for layer in board.layers:
        plane = kept.get(layer.name)
        if plane is not None:
            bag = layer.ext.get("altium", ExtBag())
            pairs = (*(p for p in bag.payload if p[0] != "plane_net"), ("plane_net", plane.net))
            layer = dataclasses.replace(layer, ext={**layer.ext, "altium": ExtBag(bag.min_version, pairs)})
        layers.append(layer)
    board = dataclasses.replace(board, layers=tuple(layers))
    return Restored(dataclasses.replace(design, board=board), kept, tuple(lost))


def names(design: Design, planes: Sequence[str]) -> dict[str, str]:
    """The user name of each row of ``planes`` that has one (``kicad`` bag ``user_name``)."""
    board = design.board
    found_names: dict[str, str] = {}
    for layer in board.layers if board is not None else ():
        bag = layer.ext.get("kicad")
        name = dict(bag.payload).get("user_name") if bag is not None else None
        if layer.name in planes and name:
            found_names[layer.name] = name
    return found_names


__all__ = [
    "KIND",
    "MULTIPLE_NETS",
    "NET_GONE",
    "PROPERTY",
    "PULLBACK",
    "ROW_GONE",
    "SCHEMA",
    "Carried",
    "Plane",
    "Restored",
    "Split",
    "carrier_text",
    "edge_corner",
    "found",
    "names",
    "read_carrier",
    "restored",
]
