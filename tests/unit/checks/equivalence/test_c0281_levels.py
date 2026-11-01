# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The proof fixes of change c0281 (the board library's conversion report): level 2 open nets of one
element, level 6 layers paired by name, level 7 graphic widths and the lens property. Authored variants of
the two-layer test board."""

from __future__ import annotations

import dataclasses

from _cases import footprint, two_layer, with_footprint

from fenolite.checks.equivalence import compare_designs
from fenolite.model.board import Board, FootprintInstance, Layer
from fenolite.model.design import Design

OPEN = "unconnected-(D1-0-Pad0)"


def board(design: Design) -> Board:
    assert design.board is not None
    return design.board


def with_board(design: Design, **changes: object) -> Design:
    return dataclasses.replace(design, board=dataclasses.replace(board(design), **changes))


def level(a: Design, b: Design, number: int):  # noqa: ANN201
    report = compare_designs(a, b, level=number, strict=number >= 5)
    return report.levels[number - 1]


def two_zeros(design: Design, net_id: str | None, extra: str | None = None) -> Design:
    """``D1`` with both pads numbered ``0`` on ``net_id``; ``R1`` pad 1 on ``extra`` when given."""

    def shield(found: FootprintInstance) -> FootprintInstance:
        pads = tuple(dataclasses.replace(pad, number="0", net_id=net_id) for pad in found.pads)
        return dataclasses.replace(found, pads=pads)

    out = with_footprint(design, "D1", shield)
    if extra is not None:

        def moved(found: FootprintInstance) -> FootprintInstance:
            pads = tuple(
                dataclasses.replace(pad, net_id=extra) if pad.number == "1" else pad for pad in found.pads
            )
            return dataclasses.replace(found, pads=pads)

        out = with_footprint(out, "R1", moved)
    return out


def with_open_net(design: Design) -> tuple[Design, str]:
    template = design.circuit.nets[0]
    net = dataclasses.replace(template, id="net_c0281-open", name=OPEN)
    circuit = dataclasses.replace(design.circuit, nets=(*design.circuit.nets, net))
    return dataclasses.replace(design, circuit=circuit), net.id


def test_open_net_of_one_element() -> None:
    """Scenario "Two pads of one number"."""
    source = two_layer()
    a = two_zeros(source, None)
    named, open_id = with_open_net(source)
    b = two_zeros(named, open_id)
    assert level(a, b, 2).differences == ()
    joined = two_zeros(named, open_id, extra=open_id)
    a_joined = two_zeros(source, None, extra=None)
    kinds = [d.kind for d in level(a_joined, joined, 2).differences]
    assert "net" in kinds


def test_layers_paired_by_name() -> None:
    """Scenario "Two user layers missing": two layers inserted before the courtyards shift no layer."""
    source = two_layer()
    layers = list(board(source).layers)
    at = next(i for i, layer in enumerate(layers) if layer.kind == "courtyard")
    extra = [Layer(id=f"lay_c0281-{n}", name=f"Eco{n}.User", kind="user", ordinal=0) for n in (1, 2)]
    grown = layers[:at] + extra + layers[at:]
    grown = [dataclasses.replace(layer, ordinal=index) for index, layer in enumerate(grown)]
    copy = with_board(source, layers=tuple(grown))
    found = [(d.kind, d.where, d.field) for d in level(source, copy, 6).differences]
    assert found == [
        ("layer-missing", "user:Eco1.User", "layer"),
        ("layer-missing", "user:Eco2.User", "layer"),
    ]


def test_layer_kind_and_order() -> None:
    source = two_layer()
    layers = board(source).layers
    swapped = tuple(
        dataclasses.replace(layer, ordinal={0: 1, 1: 0}.get(layer.ordinal, layer.ordinal)) for layer in layers
    )
    found = [
        (d.kind, d.where, d.field) for d in level(source, with_board(source, layers=swapped), 6).differences
    ]
    assert found == [("layer-field", "layers", "order")]
    renamed = tuple(
        dataclasses.replace(layer, kind="user") if layer.name == "F.Fab" else layer for layer in layers
    )
    found = [
        (d.kind, d.where, d.field) for d in level(source, with_board(source, layers=renamed), 6).differences
    ]
    assert found == [("layer-field", "F.Fab", "kind")]


def test_outline_width() -> None:
    """Scenario "Outline drawn wider"."""
    source = two_layer()
    wide = tuple(
        dataclasses.replace(g, width=200_000) if g.layer == "Edge.Cuts" else g for g in board(source).graphics
    )
    a = with_board(source, graphics=wide)
    found = level(a, source, 7).differences
    assert [(d.kind, d.field, d.a, d.b) for d in found] == [("graphic-field", "width", "200000", "50000")] * 4


def test_lens_property_left_out() -> None:
    """Scenario "Built board against an original"."""
    source = two_layer()

    def stamped(found: FootprintInstance) -> FootprintInstance:
        reference = found.fields[0]
        lens = dataclasses.replace(reference, id=reference.id + "-lens", name="fenolite.path")
        return dataclasses.replace(found, fields=(*found.fields, lens))

    copy = with_footprint(with_footprint(source, "R1", stamped), "D1", stamped)
    assert any(f.name == "fenolite.path" for f in footprint(copy, "R1").fields)
    assert [d for d in level(source, copy, 7).differences if d.kind == "field-pose"] == []
