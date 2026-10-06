# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Designs for the equivalence tests (capability design-equivalence): the authored two-layer board and
copies changed with ``dataclasses.replace``, and small designs built by hand."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.model.board import Board, FootprintInstance, Layer, Pad
from fenolite.model.circuit import Circuit, Component, Net, Pin, PinRef
from fenolite.model.design import Design, DesignHeader

TWO_LAYER = Path(__file__).resolve().parents[4] / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"


def two_layer() -> Design:
    """The design read from ``two_layer.kicad_pcb``: ``R1`` (two SMD pads) and ``D1`` (two round pads)."""
    return read_board(TWO_LAYER.read_text(encoding="utf-8"), file=TWO_LAYER.name)


def _id(prefix: str, name: str) -> str:
    return derived_id(prefix, "test", name)


def ref_of(design: Design, footprint: FootprintInstance) -> str:
    return next(c.ref for c in design.circuit.components if c.id == footprint.component_id)


def footprint(design: Design, ref: str) -> FootprintInstance:
    assert design.board is not None
    return next(f for f in design.board.footprints if ref_of(design, f) == ref)


def with_footprint(
    design: Design, ref: str, change: Callable[[FootprintInstance], FootprintInstance]
) -> Design:
    """``design`` with the footprint of ``ref`` replaced by ``change`` of it."""
    assert design.board is not None
    wanted = footprint(design, ref)
    footprints = tuple(change(f) if f is wanted else f for f in design.board.footprints)
    return dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=footprints))


def placed(design: Design, ref: str, **changes: Any) -> Design:
    """``design`` with fields of the footprint of ``ref`` changed."""
    return with_footprint(design, ref, lambda f: dataclasses.replace(f, **changes))


def with_pad(design: Design, ref: str, pad_number: str, /, **changes: Any) -> Design:
    """``design`` with fields of the pad ``pad_number`` of ``ref`` changed."""

    def change(found: FootprintInstance) -> FootprintInstance:
        pads = tuple(dataclasses.replace(p, **changes) if p.number == pad_number else p for p in found.pads)
        return dataclasses.replace(found, pads=pads)

    return with_footprint(design, ref, change)


def without_pad(design: Design, ref: str, number: str) -> Design:
    return with_footprint(
        design, ref, lambda f: dataclasses.replace(f, pads=tuple(p for p in f.pads if p.number != number))
    )


def with_component(design: Design, ref: str, **changes: Any) -> Design:
    components = tuple(
        dataclasses.replace(c, **changes) if c.ref == ref else c for c in design.circuit.components
    )
    return dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, components=components))


def reversed_order(design: Design) -> Design:
    """``design`` with its components, nets and footprints in reverse order."""
    assert design.board is not None
    circuit = dataclasses.replace(
        design.circuit,
        components=tuple(reversed(design.circuit.components)),
        nets=tuple(reversed(design.circuit.nets)),
    )
    board = dataclasses.replace(design.board, footprints=tuple(reversed(design.board.footprints)))
    return dataclasses.replace(design, circuit=circuit, board=board)


def renamed_nets(design: Design) -> Design:
    """``design`` with another name and another id for every net."""
    assert design.board is not None
    ids = {net.id: _id("net", f"renamed-{k}") for k, net in enumerate(design.circuit.nets)}
    nets = tuple(
        dataclasses.replace(net, id=ids[net.id], name=f"N{k}") for k, net in enumerate(design.circuit.nets)
    )
    footprints = tuple(
        dataclasses.replace(
            f,
            pads=tuple(
                dataclasses.replace(p, net_id=ids[p.net_id] if p.net_id is not None else None) for p in f.pads
            ),
        )
        for f in design.board.footprints
    )
    return dataclasses.replace(
        design,
        circuit=dataclasses.replace(design.circuit, nets=nets),
        board=dataclasses.replace(design.board, footprints=footprints),
    )


def circuit_only(design: Design) -> Design:
    """A design without footprints whose circuit holds the components, pins and nets of ``design``'s
    board."""
    assert design.board is not None
    members: dict[str, list[PinRef]] = {}
    components: list[Component] = []
    for component in design.circuit.components:
        placed_one = next(f for f in design.board.footprints if f.component_id == component.id)
        numbers = sorted({p.number for p in placed_one.pads if p.number})
        pins = tuple(Pin(id=_id("pin", f"{component.ref}-{n}"), number=n) for n in numbers)
        components.append(dataclasses.replace(component, pins=pins))
        for pad in placed_one.pads:
            if pad.number and pad.net_id is not None:
                found = members.setdefault(pad.net_id, [])
                if PinRef(component.id, pad.number) not in found:
                    found.append(PinRef(component.id, pad.number))
    nets = tuple(
        dataclasses.replace(net, members=tuple(members.get(net.id, ()))) for net in design.circuit.nets
    )
    circuit = dataclasses.replace(design.circuit, components=tuple(components), nets=nets)
    return dataclasses.replace(design, circuit=circuit, board=None)


LAYERS = (
    Layer(id=_id("lay", "top"), name="Top", kind="copper", ordinal=0),
    Layer(id=_id("lay", "mid"), name="Mid", kind="copper", ordinal=1),
    Layer(id=_id("lay", "bottom"), name="Bottom", kind="copper", ordinal=2),
    Layer(id=_id("lay", "mask"), name="Mask", kind="soldermask", ordinal=3),
)


def pad(number: str, x: int = 0, y: int = 0, **fields: Any) -> Pad:
    """A hand-built pad (``rect``, 1 mm by 0.5 mm, on ``Top``) with ``fields`` changed."""
    values: dict[str, Any] = {
        "shape": "rect",
        "size": Size(1_000_000, 500_000),
        "position": Point(x, y),
        "layers": ("Top", "Mask"),
    }
    values.update(fields)
    return Pad(id=_id("pad", f"{number}@{x},{y}:{sorted(values.items())!r}"), number=number, **values)


def design(
    parts: Sequence[tuple[str, str]],
    pads: dict[str, Sequence[Pad]] | None = None,
    at: dict[str, Point] | None = None,
    name: str = "case",
) -> Design:
    """A hand-built design: ``parts`` are ``(reference, value)`` pairs (a reference may repeat), and a
    reference of ``pads`` gets a footprint ``Lib:FP_<ref>`` with those pads at ``at[ref]``."""
    components = tuple(
        Component(id=_id("cmp", f"{name}-{k}-{ref}"), ref=ref, value=value)
        for k, (ref, value) in enumerate(parts)
    )
    footprints = tuple(
        FootprintInstance(
            id=_id("fp", f"{name}-{c.id}"),
            component_id=c.id,
            lib_ref=f"Lib:FP_{c.ref}",
            position=(at or {}).get(c.ref, Point(0, 0)),
            pads=tuple((pads or {})[c.ref]),
        )
        for c in components
        if c.ref in (pads or {})
    )
    header = DesignHeader(id=_id("dsn", name), name=name, schema_version="1", fenolite_version="0")
    board = Board(id=_id("brd", name), layers=LAYERS, footprints=footprints) if pads is not None else None
    return Design(header=header, circuit=Circuit(components=components), board=board)


def netted(found: Design, nets: dict[str, Sequence[tuple[str, str]]]) -> Design:
    """``found`` with the nets ``name -> (reference, pad number)`` on its pads and in its circuit."""
    assert found.board is not None
    ids = {name: _id("net", name) for name in nets}
    where = {(ref, number): ids[name] for name, members in nets.items() for ref, number in members}
    by_ref = {c.ref: c.id for c in found.circuit.components}
    footprints = tuple(
        dataclasses.replace(
            f,
            pads=tuple(
                dataclasses.replace(p, net_id=where.get((ref_of(found, f), p.number), p.net_id))
                for p in f.pads
            ),
        )
        for f in found.board.footprints
    )
    listed = tuple(
        Net(id=ids[name], name=name, members=tuple(PinRef(by_ref[ref], number) for ref, number in members))
        for name, members in nets.items()
    )
    return dataclasses.replace(
        found,
        circuit=dataclasses.replace(found.circuit, nets=listed),
        board=dataclasses.replace(found.board, footprints=footprints),
    )
