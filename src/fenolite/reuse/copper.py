# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper of a copied block (capability layout-reuse, "Copper of a copied block"; ``docs/placement.md``,
"Layout reuse").

``copy_copper`` maps tracks, arcs and vias of the reference board through the block transform onto the
target board: each reference net goes to the target net of the pads that the fit paired with its pads,
and each copper layer to its own name, or to its mirror in the stack (``F.Cu`` ↔ ``B.Cu``, ``In<j>.Cu`` ↔
``In<n+1−j>.Cu``) when the anchor lies on the other side than its reference part. An item of a reference
net that two target nets claim, or on a layer that the target board lacks, is dropped with its reason.
Pruning the copy and checking it are the command's part (``cli.reuse_copper``): they need the copper
groups and the copper check, which this package may not import.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace

from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.geometry import BBox, convex_hull
from fenolite.geometry.transform import Transform
from fenolite.model.board import Arc, Board, Track, Via, Zone, ZoneFill
from fenolite.model.design import Design
from fenolite.reuse.fit import BlockFit, Layout

BACKEND = "fenolite.reuse"
"""The namespace of the ids of copied items."""
REBUILT = "outline rebuilt from its fill"
"""The detail of a copied zone whose reference zone had a fill and no outline."""
_INNER = re.compile(r"In([1-9][0-9]*)\.Cu")

Copper = Track | Arc | Via | Zone
"""A copied item: a track, an arc, a via or a zone."""


@dataclass(frozen=True, slots=True)
class Dropped:
    """A reference item left out of the copy: its id on the reference board, its kind (``track``,
    ``arc``, ``via`` or ``zone``), its net's name on the reference board, the reason (``net-ambiguous``,
    ``layer-unknown``, ``free-end``, ``via-under-two-layers``, ``island``, ``net-skipped``,
    ``zone-beyond-block``, ``zone-unfilled``, ``pad-lost`` or the code of a copper-check finding) and a
    detail for the reader."""

    item: str
    kind: str
    net: str
    reason: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class CopiedItem:
    """A copied item on the target board, the id of the reference item it copies, the name of that
    item's net on the reference board, for a zone the ids of the reference pads its fill joins (the copy
    must keep their images), and a detail (``REBUILT``)."""

    item: Copper
    source: str
    net: str = ""
    joins: tuple[str, ...] = ()
    detail: str = ""


@dataclass(frozen=True, slots=True)
class CopperCopy:
    """The copied items (unlocked, with new ids), the net map (reference net id → target net id, the
    unambiguous nets only) and the items left out."""

    items: tuple[CopiedItem, ...] = ()
    nets: Mapping[str, str] = field(default_factory=lambda: {})
    dropped: tuple[Dropped, ...] = ()


def _copper(board: Board) -> tuple[str, ...]:
    return tuple(layer.name for layer in board.layers if layer.kind == "copper")


def _inner(name: str) -> int | None:
    found = _INNER.fullmatch(name)
    return int(found.group(1)) if found else None


def layer_map(reference: Board, target: Board, *, flipped: bool) -> dict[str, str]:
    """Reference copper layer → target copper layer: the same name, or with ``flipped`` the layer at the
    mirrored place of the stack. A layer whose image the target board lacks is not in the map."""
    ours = set(_copper(target))
    theirs = _copper(reference)
    inner = sum(1 for name in theirs if _inner(name) is not None)
    found: dict[str, str] = {}
    for name in theirs:
        image = name
        if flipped:
            index = _inner(name)
            if name == "F.Cu":
                image = "B.Cu"
            elif name == "B.Cu":
                image = "F.Cu"
            elif index is not None:
                image = f"In{inner + 1 - index}.Cu"
            else:
                continue
        if image in ours:
            found[name] = image
    return found


def _net_map(fit: BlockFit) -> dict[str, set[str]]:
    """Reference net id → the target net ids of the pads that the fit paired with its pads, over the
    placed parts."""
    found: dict[str, set[str]] = {}
    for part in fit.placed:
        for match in part.pads:
            if match.net_id is not None and match.reference_net_id is not None:
                found.setdefault(match.reference_net_id, set()).add(match.net_id)
    return found


def _kind(item: Copper) -> str:
    if isinstance(item, Zone):
        return "zone"
    return "via" if isinstance(item, Via) else "arc" if isinstance(item, Arc) else "track"


def _ring(points: Sequence[Point], transform: Transform) -> tuple[Point, ...]:
    """The image of a ring, reversed under a mirror so that it keeps its winding."""
    moved = tuple(transform.apply(point) for point in points)
    return tuple(reversed(moved)) if transform.mirror else moved


def with_outlines(design: Design) -> Design:
    """``design`` with each zone read without an outline given the outline of its fill (``outline_of``),
    so that the copper of its net can be shaped."""
    board = design.board
    if board is None or all(zone.outline for zone in board.zones):
        return design
    zones = tuple(
        replace(zone, outline=outline_of(zone)[0]) if not zone.outline else zone for zone in board.zones
    )
    return replace(design, board=replace(board, zones=zones))


def outline_of(zone: Zone) -> tuple[tuple[Point, ...], bool]:
    """The outline of a zone and whether it was rebuilt: its own, or, when the reader gave none, the
    polygon of its one fill, else the convex hull of its fills (``()`` without a fill)."""
    if zone.outline:
        return zone.outline, False
    if len(zone.fills) == 1:
        return zone.fills[0].polygon, True
    points = [point for fill in zone.fills for point in fill.polygon]
    return (convex_hull(points), True) if points else ((), False)


def _zone(
    zone: Zone, transform: Transform, net: str, layers: Mapping[str, str], key: str
) -> tuple[Zone, bool] | None:
    """The image of ``zone`` on net ``net`` and whether its outline was rebuilt, or ``None`` when one of
    its layers has no image or it has no outline and no fill."""
    named = {*zone.layers, *(fill.layer for fill in zone.fills)}
    outline, rebuilt = outline_of(zone)
    if not named or any(layer not in layers for layer in named) or len(outline) < 3:
        return None
    image = replace(
        zone,
        id=derived_id("zon", BACKEND, key),
        native_ids={},
        provenance=None,
        outline=_ring(outline, transform),
        layers=tuple(layers[layer] for layer in zone.layers),
        net_id=net,
        fills=tuple(
            ZoneFill(layers[fill.layer], _ring(fill.polygon, transform), fill.island) for fill in zone.fills
        ),
        locked=False,
    )
    return image, rebuilt


def _moved(
    item: Track | Arc | Via, transform: Transform, net: str, layers: Mapping[str, str], key: str
) -> Track | Arc | Via | None:
    """The image of ``item`` on net ``net``, or ``None`` when one of its layers has no image."""
    if isinstance(item, Via):
        if any(layer not in layers for layer in item.layers):
            return None
        return replace(
            item,
            id=derived_id("via", BACKEND, key),
            native_ids={},
            provenance=None,
            position=transform.apply(item.position),
            layers=tuple(layers[layer] for layer in item.layers),
            net_id=net,
            locked=False,
        )
    if item.layer not in layers:
        return None
    if isinstance(item, Arc):
        return replace(
            item,
            id=derived_id("arc", BACKEND, key),
            native_ids={},
            provenance=None,
            start=transform.apply(item.start),
            mid=transform.apply(item.mid),
            end=transform.apply(item.end),
            layer=layers[item.layer],
            net_id=net,
            locked=False,
        )
    return replace(
        item,
        id=derived_id("trk", BACKEND, key),
        native_ids={},
        provenance=None,
        start=transform.apply(item.start),
        end=transform.apply(item.end),
        layer=layers[item.layer],
        net_id=net,
        locked=False,
    )


def copy_copper(
    fit: BlockFit,
    reference: Layout,
    target: Layout,
    *,
    items: Collection[str] | None = None,
    zones: Mapping[str, Collection[str]] | None = None,
    nets: Mapping[str, str] | None = None,
) -> CopperCopy:
    """The tracks, arcs and vias of ``reference`` on the nets of the block, mapped through the block
    transform onto ``target`` (``items``: only these reference ids). A reference net is of the block when
    a pad of a placed part paired with a pad of it lies on it. An item of a net that two target nets claim
    is dropped (``net-ambiguous``), and one on a copper layer without an image (``layer-unknown``). The
    copies are unlocked and take ids derived from the anchor's footprint and the reference item, so a
    second copy of the same block onto another channel gets other ids.

    ``zones`` gives, per reference zone with a stored fill, the ids of the reference pads its fill joins
    (the glue groups the copper as the copper check joins it). A zone of a block net whose pads are all
    paired is copied, outline and fill (``_zone``; ``REBUILT`` when the outline came from the fill); one
    that also joins an unpaired pad is ``zone-beyond-block``; a zone of a block net without a fill whose
    outline's box holds a paired pad is ``zone-unfilled``; a zone that joins no paired pad is not of the
    block.

    ``nets`` is an explicit net map (reference net id → target net id, change c0255): the nets of the
    block are its keys, and no net is inferred from the pairs of the fit."""
    board, ours = reference.design.board, target.design.board
    if fit.transform is None or board is None or ours is None:
        return CopperCopy()
    transform = fit.transform
    if nets is not None:
        claimed = {source: {image} for source, image in nets.items()}
    else:
        claimed = _net_map(fit)
    nets = {source: next(iter(images)) for source, images in claimed.items() if len(images) == 1}
    names = {net.id: net.name for net in reference.design.circuit.nets}
    target_names = {net.id: net.name for net in target.design.circuit.nets}
    layers = layer_map(board, ours, flipped=fit.flipped)
    anchor = next((part.footprint_id for part in fit.parts if part.ref == fit.anchor), fit.anchor)
    copied: list[CopiedItem] = []
    dropped: list[Dropped] = []
    for item in (*board.tracks, *board.arcs, *board.vias):
        if item.net_id is None or item.net_id not in claimed or (items is not None and item.id not in items):
            continue
        name = names.get(item.net_id, item.net_id)
        if item.net_id not in nets:
            joined = ", ".join(sorted(target_names.get(net, net) for net in claimed[item.net_id]))
            dropped.append(
                Dropped(item.id, _kind(item), name, "net-ambiguous", f"its net maps to the nets {joined}")
            )
            continue
        image = _moved(item, transform, nets[item.net_id], layers, f"{anchor}:{item.id}")
        if image is None:
            dropped.append(
                Dropped(item.id, _kind(item), name, "layer-unknown", "the target board lacks its layer")
            )
            continue
        copied.append(CopiedItem(image, item.id, name))
    paired = {match.reference_pad_id: match.reference for part in fit.placed for match in part.pads}
    joins = zones or {}
    for zone in board.zones:
        if zone.net_id is None or zone.net_id not in claimed:
            continue
        name = names.get(zone.net_id, zone.net_id)
        joined = set(joins.get(zone.id, ()))
        if zone.id not in joins:
            outline, _ = outline_of(zone)
            box = BBox.of_points(outline) if outline else None
            if not zone.fills and box is not None and any(box.contains_point(at) for at in paired.values()):
                detail = (
                    "the reference zone holds no fill to tell the pads it joins; fill the reference first"
                )
                dropped.append(Dropped(zone.id, "zone", name, "zone-unfilled", detail))
            continue
        if not joined & set(paired):
            continue
        beyond = joined - set(paired)
        if beyond:
            detail = f"its fill also joins {len(beyond)} pad(s) outside the block"
            dropped.append(Dropped(zone.id, "zone", name, "zone-beyond-block", detail))
            continue
        if zone.net_id not in nets:
            joined_nets = ", ".join(sorted(target_names.get(net, net) for net in claimed[zone.net_id]))
            dropped.append(
                Dropped(zone.id, "zone", name, "net-ambiguous", f"its net maps to the nets {joined_nets}")
            )
            continue
        shaped = _zone(zone, transform, nets[zone.net_id], layers, f"{anchor}:{zone.id}")
        if shaped is None:
            dropped.append(
                Dropped(zone.id, "zone", name, "layer-unknown", "the target board lacks its layer")
            )
            continue
        image, rebuilt = shaped
        copied.append(CopiedItem(image, zone.id, name, tuple(sorted(joined)), REBUILT if rebuilt else ""))
    return CopperCopy(tuple(copied), nets, tuple(dropped))


def copy_block(
    reference: Design,
    transform: Transform,
    nets: Mapping[str, str],
    layers: Mapping[str, str],
    *,
    key: str,
) -> CopperCopy:
    """Every track, arc, via and zone of ``reference`` (a board laid out for one block alone) on a net of
    the explicit map ``nets`` (reference net id → target net id), moved by ``transform`` onto the layers of
    ``layers`` (change c0255, a block layout reuse in a build). An item of a net outside the map is
    dropped (``net-unmapped``), one on a layer without an image ``layer-unknown``. The copies take ids
    derived from ``key`` and the reference item, unlocked; the caller locks them."""
    board = reference.board
    if board is None:
        return CopperCopy()
    names = {net.id: net.name for net in reference.circuit.nets}
    copied: list[CopiedItem] = []
    dropped: list[Dropped] = []
    for item in (*board.tracks, *board.arcs, *board.vias, *board.zones):
        if item.net_id is None:
            continue
        name = names.get(item.net_id, item.net_id)
        target = nets.get(item.net_id)
        if target is None:
            dropped.append(
                Dropped(item.id, _kind(item), name, "net-unmapped", "its net is no port of the block")
            )
            continue
        if isinstance(item, Zone):
            shaped = _zone(item, transform, target, layers, f"{key}:{item.id}")
            image = None if shaped is None else shaped[0]
        else:
            image = _moved(item, transform, target, layers, f"{key}:{item.id}")
        if image is None:
            dropped.append(
                Dropped(item.id, _kind(item), name, "layer-unknown", "the target board lacks its layer")
            )
            continue
        copied.append(CopiedItem(image, item.id, name))
    return CopperCopy(tuple(copied), dict(nets), tuple(dropped))


def with_copper(design: Design, items: Sequence[Copper]) -> Design:
    """``design`` with ``items`` added after its own tracks, arcs, vias and zones."""
    board = design.board
    if board is None or not items:
        return design
    return replace(
        design,
        board=replace(
            board,
            tracks=(*board.tracks, *(item for item in items if isinstance(item, Track))),
            arcs=(*board.arcs, *(item for item in items if isinstance(item, Arc))),
            vias=(*board.vias, *(item for item in items if isinstance(item, Via))),
            zones=(*board.zones, *(item for item in items if isinstance(item, Zone))),
        ),
    )


__all__ = [
    "BACKEND",
    "REBUILT",
    "CopiedItem",
    "Copper",
    "CopperCopy",
    "Dropped",
    "copy_block",
    "copy_copper",
    "layer_map",
    "outline_of",
    "with_copper",
    "with_outlines",
]
