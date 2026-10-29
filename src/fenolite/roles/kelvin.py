# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The two attachment measures that no analysis of ``fenolite.analysis`` has (change c0222; capability
net-roles, "Kelvin attachment" and "Hot and gate loop checks"; ``docs/roles.md``, "Kelvin and gate-return
measures").

**Kelvin attachment.** For each sense pad ``P`` of a ``KelvinPair``:

1. the power copper of ``P``'s net is the active part of ``path_network`` between ``P`` and the other power
   pads of that net (the pads of transistors' drains and sources, inductors, connectors, shunts and hot-loop
   capacitors), with those pads;
2. the sense branch is the connected copper of the net reached from the receiver's pad (or from the pad on
   ``P``'s net of a resistor in series with it) without crossing ``P`` and without entering power copper;
3. the attachment is where the branch touches ``P``: the end of a track inside the pad, a via, or, for a
   fill, the pad's centre;
4. with ``u`` the unit vector from ``P``'s centre to the other sense pad's centre, the offset of an
   attachment point ``a`` is ``t = (a - centre(P)) · u`` in nanometres. ``t < 0`` lies on the outer half,
   where the load current's path through pad and solder is in the measurement (S-0850).

A branch that reaches power copper, or a receiver joined to a force pad's net of a four-terminal shunt, is
shared. **Gate return.** The return branch of a ``GateLoop`` is found the same way, from the driver's return
pad to the loop's source pad: a return that reaches the switch's power source copper first is shared; the
source pads of the other gate loops end the walk (a common-source pair shares its driver's return pin). When
the source pad is the power source pad itself (a package without a Kelvin pin), the copper that touches that
pad counts as reaching the pad: the return of such a switch necessarily lands in its source's copper.

The walk joins copper items of one net that touch on a layer (``fenolite.geometry.thick_touch``) and the
layers of one via or pad; the copper is ``analysis.copper.net_copper``'s. It measures no area, section,
capacity or gap.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isqrt

from fenolite.analysis.copper import ARC_TOL_NM, CopperShape, NetCopper
from fenolite.analysis.network import PathNetwork, path_network
from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.geometry import Thick, thick_bbox, thick_touch
from fenolite.model.design import Design
from fenolite.model.rules import GateLoop, KelvinPair

_Item = tuple[str, str]  # (kind, entity id)


@dataclass(frozen=True, slots=True)
class Attachment:
    """The measure of one sense pad, or of a gate loop's source pad: the pad, its net, the attachment points
    and their offsets ``t`` (nm; empty for a gate return), the power copper or force pads the branch reached
    (by ``where``), the branch's tracks, arcs and vias (by entity id), and the pads the walk started from."""

    pad: str
    net: str | None
    points: tuple[Point, ...] = ()
    offsets: tuple[int, ...] = ()
    shared: tuple[str, ...] = ()
    branch: tuple[str, ...] = ()
    starts: tuple[str, ...] = ()

    @property
    def reached(self) -> bool:
        return bool(self.points)


def pad_name(record: BoardPad) -> str:
    holder = record.ref or record.footprint_id
    return f"{holder}-{record.number}" if record.number else holder


def power_items(network: PathNetwork) -> set[_Item]:
    """The active elements of a path network as copper items: the tracks and arcs, the vias of the via
    groups, and the zones of the fills."""
    found: set[_Item] = set()
    for element in network.elements:
        if not element.active:
            continue
        kind = {"via-group": "via", "track": "track", "arc": "arc", "fill": "fill"}[element.kind]
        found.update((kind, entity) for entity in element.entity_ids)
    return found


class _Graph:
    """The copper items of one net and which of them touch."""

    def __init__(self, shapes: Sequence[CopperShape]) -> None:
        self.shapes = tuple(shapes)
        self.boxes = [thick_bbox(shape.shape) for shape in self.shapes]

    def touching(self, index: int) -> list[int]:
        shape, box = self.shapes[index], self.boxes[index]
        found: list[int] = []
        for other, candidate in enumerate(self.shapes):
            if other == index:
                continue
            if candidate.entity_id == shape.entity_id and candidate.kind == shape.kind:
                found.append(other)
                continue
            if candidate.layer != shape.layer:
                continue
            near = self.boxes[other]
            if near.x0 > box.x1 or box.x0 > near.x1 or near.y0 > box.y1 or box.y0 > near.y1:
                continue
            if thick_touch(shape.shape, candidate.shape):
                found.append(other)
        return found


def _inside(point: Point, pad: Sequence[CopperShape]) -> bool:
    probe = Thick((point,), 1)
    return any(thick_touch(probe, shape.shape) for shape in pad)


def _attachment_points(shape: CopperShape, pad: Sequence[CopperShape], centre: Point) -> list[Point]:
    if shape.kind in ("track", "arc"):
        core = shape.shape.core
        ends = [point for point in (core[0], core[-1]) if _inside(point, pad)]
        if ends:
            return ends
        return [min(core, key=lambda point: (point.x - centre.x) ** 2 + (point.y - centre.y) ** 2)]
    if shape.kind in ("via", "pad"):
        return [shape.shape.core[0]]
    return [centre]


def offset(point: Point, centre: Point, toward: Point) -> int:
    """``(point - centre) · u`` in nanometres, ``u`` the unit vector from ``centre`` to ``toward``, rounded
    toward zero."""
    dx, dy = toward.x - centre.x, toward.y - centre.y
    norm = isqrt(dx * dx + dy * dy) or 1
    dot = (point.x - centre.x) * dx + (point.y - centre.y) * dy
    return dot // norm if dot >= 0 else -((-dot) // norm)


def _walk(
    copper: NetCopper,
    net: str,
    starts: Sequence[str],
    target: str,
    power: set[_Item],
    power_pads: set[str],
    centre: Point,
    toward: Point | None,
    allowed: set[_Item],
    stops: frozenset[str] = frozenset(),
) -> Attachment:
    shapes = copper.by_net.get(net, ())
    graph = _Graph(shapes)
    pad_shapes = [shape for shape in shapes if shape.kind == "pad" and shape.where == target]
    start = [index for index, shape in enumerate(shapes) if shape.kind == "pad" and shape.where in starts]
    seen = set(start)
    queue = list(start)
    points: list[Point] = []
    shared: set[str] = set()
    branch: set[str] = set()

    def is_power(shape: CopperShape) -> bool:
        if shape.kind == "pad":
            return shape.where in power_pads
        return (shape.kind, shape.entity_id) in power

    for index in start:
        if is_power(shapes[index]):
            shared.add(shapes[index].where)
    while queue:
        index = queue.pop(0)
        shape = shapes[index]
        if shape.kind in ("track", "arc", "via"):
            branch.add(shape.entity_id)
        for other in graph.touching(index):
            candidate = shapes[other]
            if candidate.kind == "pad" and candidate.where == target:
                points += _attachment_points(shape, pad_shapes, centre)
                continue
            if (candidate.kind, candidate.entity_id) in allowed:
                points.append(centre)  # the copper of the source pad itself: the return reaches the pad
                continue
            if other in seen:
                continue
            if candidate.kind == "pad" and candidate.where in stops:
                continue  # another loop's source pad ends the branch: its own return lands there
            if is_power(candidate):
                shared.add(candidate.where)
                continue
            seen.add(other)
            queue.append(other)
    unique = tuple(dict.fromkeys(points))
    offsets = tuple(offset(point, centre, toward) for point in unique) if toward is not None else ()
    return Attachment(
        target, net, unique, offsets, tuple(sorted(shared)), tuple(sorted(branch)), tuple(starts)
    )


def _starts(records: Mapping[str, BoardPad], receiver: str, net: str, design: Design) -> tuple[str, ...]:
    """The pads the branch starts from: the receiver's pad when it lies on ``net``, else the pads on ``net``
    of two-pad parts whose other pad lies on the receiver's net (a resistor in series)."""
    record = records.get(receiver)
    if record is None:
        return ()
    if record.net == net:
        return (receiver,)
    by_part: dict[str, list[BoardPad]] = {}
    for found in records.values():
        by_part.setdefault(found.ref, []).append(found)
    starts: list[str] = []
    for held in by_part.values():
        if len(held) == 2 and {held[0].net, held[1].net} == {net, record.net}:
            starts += [pad_name(found) for found in held if found.net == net]
    del design
    return tuple(sorted(starts))


def _power(
    design: Design,
    pads: Sequence[BoardPad],
    pad: str,
    net: str,
    power_pads: Mapping[str, tuple[str, ...]],
    arc_tol: int,
) -> tuple[set[_Item], set[str]]:
    others = tuple(name for name in power_pads.get(net, ()) if name != pad)
    if not others:
        return set(), set()
    network = path_network(design, pads=pads, start=(pad,), end=others, arc_tol=arc_tol)
    return power_items(network), set(others)


def kelvin_attachments(
    design: Design,
    pads: Sequence[BoardPad],
    pair: KelvinPair,
    *,
    copper: NetCopper,
    power_pads: Mapping[str, tuple[str, ...]],
    arc_tol: int = ARC_TOL_NM,
) -> tuple[Attachment, ...]:
    """The attachment of each sense pad of ``pair``, in the order of ``element``."""
    records = {pad_name(record): record for record in pads}
    found: list[Attachment] = []
    force_nets = {records[name].net for name in pair.force if name in records} - {None}
    for index, sense in enumerate(pair.element):
        receiver = pair.receiver[index]
        record, other = records.get(sense), records.get(pair.element[1 - index])
        receiving = records.get(receiver)
        if record is None or other is None or receiving is None:
            found.append(Attachment(sense, None if record is None else record.net))
            continue
        if receiving.net is not None and receiving.net in force_nets and receiving.net != record.net:
            force = next(name for name in pair.force if records[name].net == receiving.net)
            found.append(Attachment(sense, record.net, shared=(force,), starts=(receiver,)))
            continue
        net = record.net
        if net is None:
            found.append(Attachment(sense, None, starts=(receiver,)))
            continue
        items, others = _power(design, pads, sense, net, power_pads, arc_tol)
        others |= {name for name in pair.force if name in records and records[name].net == net}
        starts = _starts(records, receiver, net, design)
        found.append(_walk(copper, net, starts, sense, items, others, record.position, other.position, set()))
    return tuple(found)


def gate_return(
    design: Design,
    pads: Sequence[BoardPad],
    loop: GateLoop,
    *,
    copper: NetCopper,
    power_pads: Mapping[str, tuple[str, ...]],
    power_source: str,
    stops: Sequence[str] = (),
    arc_tol: int = ARC_TOL_NM,
) -> Attachment:
    """The return branch of ``loop``: from the driver's return pad to the loop's source pad, against the
    power copper of the switch's power source pad ``power_source`` (the loop's own source pad when the
    package has no Kelvin pin). ``stops`` are the source pads of the other gate loops: the branch does not
    walk on through them (switches with a common source share their driver's return pin)."""
    records = {pad_name(record): record for record in pads}
    record = records.get(loop.source)
    if record is None or record.net is None:
        return Attachment(loop.source, None)
    net = record.net
    items, others = _power(design, pads, power_source, net, power_pads, arc_tol)
    others.add(power_source)
    others.discard(loop.source)
    allowed: set[_Item] = set()
    if power_source == loop.source:
        own = [
            shape
            for shape in copper.by_net.get(net, ())
            if shape.kind == "pad" and shape.where == loop.source
        ]
        for shape in copper.by_net.get(net, ()):
            if (shape.kind, shape.entity_id) in items and any(
                thick_touch(shape.shape, mine.shape) for mine in own
            ):
                allowed.add((shape.kind, shape.entity_id))
    starts = _starts(records, loop.ret, net, design)
    ends = frozenset(stops) - {loop.source}
    return _walk(copper, net, starts, loop.source, items, others, record.position, None, allowed, ends)


__all__ = ["Attachment", "gate_return", "kelvin_attachments", "offset", "pad_name", "power_items"]
