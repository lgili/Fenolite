# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project opaque KiCad copper offsets for conversion, leaving the source unchanged.

The offset is copper from the hole centre in the pad frame: kicad/frame.md,
H-G-FRAME-OFFSET. No KiCad slot is edited or discarded.
"""

from __future__ import annotations

from dataclasses import replace

from fenolite.backends.kicad._libread import Context, Loaded
from fenolite.backends.kicad.sexpr import Node, parse_fragment
from fenolite.backends.kicad.slots import Opaque, from_ext
from fenolite.backends.kicad.versions import FileKind
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence
from fenolite.core.ids import derived_id
from fenolite.geometry.transform import rotate_point
from fenolite.model.board import Pad, Padstack, PadstackLayer
from fenolite.model.design import Design


def _offset(pad: Pad) -> Point:
    bag = pad.ext.get("kicad")
    if bag is None:
        return Point(0, 0)
    for slot in from_ext(bag):
        if not isinstance(slot, Opaque):
            continue
        node = parse_fragment(slot.fragment)
        if not isinstance(node, Node) or node.name != "drill":
            continue
        offset = node.find("offset")
        if offset is None:
            continue
        provenance = pad.provenance
        loaded = Loaded(
            node,
            provenance.file_sha256 if provenance else "",
            provenance.file if provenance else "",
            None,
        )
        context = Context(loaded, FileKind.FOOTPRINT, provenance.evidence if provenance else Evidence())
        return rotate_point(context.point(offset, "pad/drill/offset"), pad.rotation)
    return Point(0, 0)


def _project(pad: Pad) -> Pad:
    offset = _offset(pad)
    if offset == Point(0, 0):
        return pad
    stack = pad.padstack or Padstack(id=derived_id("pst", "conversion", pad.id))
    layers = stack.layers or tuple(
        PadstackLayer(name, pad.shape, pad.size) for name in ("F.Cu", "In*.Cu", "B.Cu")
    )
    layers = tuple(
        replace(layer, offset=Point(layer.offset.x + offset.x, layer.offset.y + offset.y)) for layer in layers
    )
    return replace(pad, padstack=replace(stack, layers=layers))


def project(design: Design) -> Design:
    """A conversion copy with drill copper offsets expressed as model layer offsets."""
    if design.board is None:
        return design
    footprints = tuple(
        replace(footprint, pads=tuple(_project(pad) for pad in footprint.pads))
        for footprint in design.board.footprints
    )
    return replace(design, board=replace(design.board, footprints=footprints))
