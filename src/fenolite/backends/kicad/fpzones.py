# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rule areas of a footprint in KiCad files (change c0411).

A footprint holds its keep-out zones as ``zone`` children after its pads (S-1720). A library footprint
(``.kicad_mod``) holds their points relative to its origin, but a board holds a footprint's zone in the
board's own frame: KiCad 10.0.6 neither offsets nor turns those points by the footprint's ``at``
(``docs/formats/kicad/board.md``, measured 2026-11-05). So:

- ``footprint_keepouts`` projects the keep-out zones of a footprint node into ``Keepout`` entities, each
  point through ``frame`` (the identity for a library footprint, the board-to-pad-frame map for a board
  one). A zone child stays an opaque slot: the areas are a projection, as the net-tie groups are, and a
  writer refuses a change of them on a footprint it writes as read.
- ``moved_zones`` rewrites the points of every ``zone`` child of a footprint node through ``move``: a
  library footprint placed on a board (``embed.placed_tree``) and a board footprint brought back to its
  origin (``embed.local_footprint``).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.geometry.transform import Transform
from fenolite.model.board import Keepout

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-FP-AREA",))

SETTINGS = (
    ("tracks", "no_tracks"),
    ("vias", "no_vias"),
    ("pads", "no_pads"),
    ("copperpour", "no_copper_pour"),
    ("footprints", "no_footprints"),
)
"""The ``keepout`` children and the ``Keepout`` field each sets (as ``pcb.KEEPOUT_SETTINGS``)."""
ALL_COPPER = ("F.Cu", "B.Cu", *(f"In{n}.Cu" for n in range(1, 31)))
"""The copper layers a footprint zone on every copper layer names, in the order ``fp upgrade`` 10.0.6
writes them (``docs/formats/kicad/board.md``); a definition holds them as ``*.Cu``, as a pad."""
WILDCARD = "*.Cu"
POINT_PARENTS = frozenset({"polygon", "filled_polygon"})
"""The children of a zone whose ``pts`` hold points of the zone."""


def _symbols(item: Node) -> list[str]:
    return [a.value for a in item.atoms() if a.kind != AtomKind.NUMBER]


def _point(xy: Node) -> Point | None:
    atoms = xy.atoms()
    if xy.name != "xy" or len(atoms) != 2 or any(a.kind != AtomKind.NUMBER for a in atoms):
        return None
    try:
        return Point(atoms[0].to_nm(), atoms[1].to_nm())
    except ValueError:
        return None


def keepout_of(
    zone: Node, ident: str, frame: Callable[[Point], Point], *, definition: bool = False
) -> Keepout | None:
    """The rule area a footprint's ``zone`` child stands for, or ``None`` when it is no keep-out the model
    holds: no ``keepout`` child, a setting other than ``allowed``/``not_allowed``, a net, or an outline
    that is not one polygon of plain points. In a ``definition``, a zone on every copper layer of
    ``ALL_COPPER`` is on ``*.Cu``."""
    keepout = zone.find("keepout")
    if keepout is None:
        return None
    settings = dict.fromkeys((attr for _, attr in SETTINGS), False)
    heads = dict(SETTINGS)
    for part in keepout.nodes():
        values = _symbols(part)
        if part.name not in heads or values not in (["allowed"], ["not_allowed"]):
            return None
        settings[heads[part.name]] = values == ["not_allowed"]
    net = zone.find("net")
    if net is not None and any(a.value not in ("0", "") for a in net.atoms()):
        return None  # a rule area holds no net: (net 0) or (net "")
    layers: tuple[str, ...] = ()
    for head in ("layer", "layers"):
        found = zone.find(head)
        if found is not None:
            layers = tuple(_symbols(found))
    if definition and set(layers) == set(ALL_COPPER):
        layers = (WILDCARD,)
    polygons = zone.nodes("polygon")
    if len(polygons) != 1 or not layers:
        return None
    pts = polygons[0].find("pts")
    if pts is None or pts.atoms() or len(polygons[0].children) != 1:
        return None
    points = [_point(xy) for xy in pts.nodes()]
    if len(points) < 3 or any(p is None for p in points):
        return None
    name = zone.find("name")
    return Keepout(
        id=ident,
        outline=tuple(frame(p) for p in points if p is not None),
        layers=layers,
        no_tracks=settings["no_tracks"],
        no_vias=settings["no_vias"],
        no_pads=settings["no_pads"],
        no_copper_pour=settings["no_copper_pour"],
        no_footprints=settings["no_footprints"],
        name=_symbols(name)[0] if name is not None and _symbols(name) else "",
    )


def footprint_keepouts(
    children: Iterable[Node | Atom], key: str, frame: Callable[[Point], Point], *, definition: bool = False
) -> tuple[Keepout, ...]:
    """The keep-out zones among a footprint's ``children``, in order, projected by ``keepout_of``; the
    ``n``-th zone child gets the id ``derived_id("kpo", "kicad", f"{key}:zone[n]")``."""
    zones = [child for child in children if isinstance(child, Node) and child.name == "zone"]
    found = (
        keepout_of(zone, derived_id("kpo", "kicad", f"{key}:zone[{n}]"), frame, definition=definition)
        for n, zone in enumerate(zones)
    )
    return tuple(area for area in found if area is not None)


def board_to_pad(position: Point, rotation: int) -> Callable[[Point], Point]:
    """A board point in the pad frame of a footprint at ``position`` turned by ``rotation``: the inverse
    of ``pad_to_board``, rounded to the nanometre."""
    return Transform.placement(position, rotation).inverse().apply


def pad_to_board(position: Point, rotation: int) -> Callable[[Point], Point]:
    """A pad-frame point of a footprint at ``position`` turned by ``rotation`` on its board, as a pad's
    position is placed (``Transform.placement``, ``model.board.placed_keepout``)."""
    return Transform.placement(position, rotation).apply


def placement_frame(children: Iterable[Node | Atom]) -> Callable[[Point], Point]:
    """The map of a footprint's zone points to its own frame: ``board_to_pad`` of its ``(at x y [angle])``
    child when it has one (a footprint of a board), else the identity (a library footprint)."""
    from fenolite.core.units import parse_angle

    at = next((c for c in children if isinstance(c, Node) and c.name == "at"), None)
    atoms: tuple[Atom, ...] = at.atoms() if at is not None else ()
    if len(atoms) < 2 or any(a.kind != AtomKind.NUMBER for a in atoms[:3]):
        return same
    angle = parse_angle(atoms[2].value + "deg") if len(atoms) >= 3 else 0
    return board_to_pad(Point(atoms[0].to_nm(), atoms[1].to_nm()), angle)


def _moved_pts(pts: Node, move: Callable[[Point], Point]) -> Node:
    children: list[Node | Atom] = []
    for child in pts.children:
        point = _point(child) if isinstance(child, Node) else None
        if isinstance(child, Node) and point is not None:
            moved = move(point)
            child = child.with_children([Atom.from_nm(moved.x), Atom.from_nm(moved.y)])
        children.append(child)
    return pts.with_children(children)


def moved_zones(footprint: Node, move: Callable[[Point], Point]) -> Node:
    """``footprint`` with the points of each ``zone`` child's polygons moved by ``move``."""

    def zone(item: Node) -> Node:
        parts: list[Node | Atom] = []
        for part in item.children:
            if isinstance(part, Node) and part.name in POINT_PARENTS:
                part = part.with_children(
                    [
                        _moved_pts(c, move) if isinstance(c, Node) and c.name == "pts" else c
                        for c in part.children
                    ]
                )
            parts.append(part)
        return item.with_children(parts)

    if not any(isinstance(c, Node) and c.name == "zone" for c in footprint.children):
        return footprint
    return footprint.with_children(
        [zone(c) if isinstance(c, Node) and c.name == "zone" else c for c in footprint.children]
    )


def placed_zone(zone: Node, area: Keepout, frame: Callable[[Point], Point]) -> Node:
    """``zone`` (a keep-out zone ``keepout_of`` projects) with its polygon's points written from
    ``area.outline``, each through ``frame``; every other child as it is."""
    points = (_node("xy", Atom.from_nm(q.x), Atom.from_nm(q.y)) for q in map(frame, area.outline))
    pts = _node("pts", *points)
    return zone.with_children(
        [c.with_children([pts]) if isinstance(c, Node) and c.name == "polygon" else c for c in zone.children]
    )


def shape(area: Keepout) -> tuple[object, ...]:
    """What a footprint's zone child holds of a rule area: outline, layers, settings and name (no ids)."""
    return (area.outline, area.layers, *(getattr(area, attr) for _, attr in SETTINGS), area.name)


def same(p: Point) -> Point:
    """The identity frame: a library footprint's points as they are."""
    return p


def _node(head: str, *children: Node | Atom) -> Node:
    return Node(Atom.symbol(head), children)


def zone_node(area: Keepout, uuid: str, frame: Callable[[Point], Point] | None = None) -> Node:
    """The ``zone`` child of a footprint for ``area``, in the form KiCad 10.0.6's ``fp upgrade`` writes a
    footprint's keep-out: layers, uuid, name, the hatch, pad connection and thickness that a rule area
    carries unused, the five settings and the outline, each point through ``frame`` (the identity by
    default)."""
    move: Callable[[Point], Point] = frame if frame is not None else same
    names = [m for n in area.layers for m in (ALL_COPPER if n == WILDCARD else (n,))]
    names = list(dict.fromkeys(names))
    layers = _node("layer" if len(names) == 1 else "layers", *(Atom.string(n) for n in names))
    settings = (
        _node(head, Atom.symbol("not_allowed" if getattr(area, attr) else "allowed"))
        for head, attr in SETTINGS
    )
    points = (_node("xy", Atom.from_nm(q.x), Atom.from_nm(q.y)) for q in map(move, area.outline))
    named = (_node("name", Atom.string(area.name)),) if area.name else ()
    return _node(
        "zone",
        layers,
        _node("uuid", Atom.string(uuid)),
        *named,
        _node("hatch", Atom.symbol("edge"), Atom.from_nm(500_000)),
        _node("connect_pads", _node("clearance", Atom.from_nm(0))),
        _node("min_thickness", Atom.from_nm(250_000)),
        _node("keepout", *settings),
        _node(
            "fill",
            _node("thermal_gap", Atom.from_nm(500_000)),
            _node("thermal_bridge_width", Atom.from_nm(500_000)),
        ),
        _node("polygon", _node("pts", *points)),
    )
