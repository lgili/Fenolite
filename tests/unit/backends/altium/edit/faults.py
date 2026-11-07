# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The planted faults of the integrity check (change c0241): each a function of a PCB document's bytes that
gives the bytes with one fault, written with the edit state and the integrity check off. The tests of the
check and the files of Part J phase B (``faults/``, cases J26 to J32) use them."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType

from fenolite.backends.altium.edit import records as rec
from fenolite.backends.altium.edit.state import State
from fenolite.backends.altium.pcbrecords import v7_layer
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RegionRecord

MECHANICAL_13, MECHANICAL_15 = 69, 71


def subpoly_gap(data: bytes) -> bytes:
    """The pieces of the first poured polygon numbered 0, 1, 3, 4 … (copies of its first piece added up to
    three pieces); without a poured piece, three copies of the free region given polygon 0."""
    state = State.of(data)
    doc = read_pcbdoc(data)
    poured = [
        n for n, r in enumerate(doc.regions) if isinstance(r, RegionRecord) and r.prefix.polygon is not None
    ]
    regions = state.get("Regions6")
    if poured:
        polygon = rec.prefix_of(regions[poured[0]])[2]
        pieces = [n for n in poured if rec.prefix_of(regions[n])[2] == polygon]
        first = regions[pieces[0]]
    else:
        pieces, first = [], rec.set_prefix(regions[0], polygon=0)
    while len(pieces) < 3:
        pieces.append(state.append("Regions6", first))
    for number, position in zip((0, 1, *range(3, len(pieces) + 1)), pieces, strict=True):
        raw = state.get("Regions6")[position]
        state.replace("Regions6", position, rec.set_region_keys(raw, {"SUBPOLYINDEX": str(number)}))
    return state.data()


def pour_index_twice(data: bytes) -> bytes:
    """The second polygon given the first one's ``POURINDEX`` 0."""
    state = State.of(data)
    state.replace("Polygons6", 1, rec.set_property(state.get("Polygons6")[1], {"POURINDEX": "0"}))
    return state.data()


def unique_id_twice(data: bytes) -> bytes:
    """The second pad's entry of ``UniqueIDPrimitiveInformation`` given the first one's unique id."""
    state = State.of(data)
    first = dict(state.properties("UniqueIDPrimitiveInformation")[0].fields)["UNIQUEID"]
    raw = state.get("UniqueIDPrimitiveInformation")[1]
    state.replace("UniqueIDPrimitiveInformation", 1, rec.set_property(raw, {"UNIQUEID": first}))
    return state.data()


def layer_fields(data: bytes) -> bytes:
    """The free region on Mechanical 13 given ``V7_LAYER`` Mechanical 15."""
    state = State.of(data)
    for number, raw in enumerate(state.get("Regions6")):
        if rec.prefix_of(raw)[0] == MECHANICAL_13 and rec.prefix_of(raw)[2] == rec.NO_INDEX:
            state.replace("Regions6", number, rec.set_region_keys(raw, {"V7_LAYER": v7_layer(MECHANICAL_15)}))
            return state.data()
    raise ValueError("the document holds no free region on Mechanical 13")


FAULTS: Mapping[str, tuple[Callable[[bytes], bytes], str]] = MappingProxyType(
    {
        "subpoly-gap": (subpoly_gap, "altium.integrity.subpoly-gap"),
        "pour-index-twice": (pour_index_twice, "altium.integrity.pour-index-twice"),
        "unique-id-twice": (unique_id_twice, "altium.integrity.unique-id-twice"),
        "layer-fields": (layer_fields, "altium.integrity.layer-fields"),
    }
)
"""Each file of ``faults/``: its planter and the one finding the check gives on it."""
