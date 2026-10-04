# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprints re-placed on a read board: ``move_footprint`` (capability kicad-file-backend, "Footprints are
re-placed on a read board"; facts: ``docs/formats/kicad/board.md``, "Moved footprints"; change c0022).

A translation changes only the footprint's position: its pads, graphics and fields are stored relative to
it. A new rotation or side re-places the footprint from its library definition with
``embed.place_footprint``, because a placed footprint stores its children in the placed frame. The copy
keeps the old footprint's id, uuid, Reference, Value, user properties, lock and pad nets.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence

from fenolite.backends.kicad import pcb
from fenolite.backends.kicad.embed import PATH_PROPERTY, place_footprint, with_property
from fenolite.core.coords import Point
from fenolite.core.errors import FenoliteError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Udeg
from fenolite.model.board import FootprintField, FootprintInstance, Side
from fenolite.model.circuit import Component
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-PLACE-MOVE",))
"""Raised to ``KICAD-VERIFIED`` when ``H-K-PLACE-MOVE`` is settled on both majors."""
BAG = "kicad"
FIELD_VALUES: tuple[str, ...] = (
    "position",
    "rotation",
    "layer",
    "size",
    "thickness",
    "visible",
    "h_justify",
    "v_justify",
    "mirrored",
)
"""What a field of a rotated footprint takes from the old one (equal to ``lens.fields.FIELD_VALUES``)."""


class PlacementError(FenoliteError):
    """A footprint that cannot be moved; ``issues`` holds one ``place.*`` error."""

    cli_code = "FEN-3001"

    def __init__(self, issues: Sequence[Issue]) -> None:
        self.issues = tuple(issues)
        super().__init__(self.issues[0].message if self.issues else "the footprint cannot be moved")


def _refuse(code: str, message: str, where: str, hint: str = "") -> PlacementError:
    return PlacementError([Issue(code, "error", message, where=where, hint=hint)])


def footprint_ref(design: Design, footprint: FootprintInstance) -> str:
    """The reference of ``footprint``: its component's, else the value of its Reference field, else its id."""
    for component in design.circuit.components:
        if component.id == footprint.component_id and component.ref:
            return component.ref
    for field in footprint.fields:
        if field.name == "Reference":
            return pcb.field_value(field) or footprint.id
    return footprint.id


def _component(design: Design, footprint: FootprintInstance) -> Component:
    for component in design.circuit.components:
        if component.id == footprint.component_id:
            return component
    values = {f.name: pcb.field_value(f) or "" for f in footprint.fields}
    return Component(
        id=footprint.component_id, ref=values.get("Reference", ""), value=values.get("Value", "")
    )


def _replaced(
    design: Design,
    old: FootprintInstance,
    definition: FootprintDef,
    at: Point,
    rotation: Udeg,
    side: Side,
) -> FootprintInstance:
    assert design.board is not None
    component = _component(design, old)
    extended = definition
    for field in old.fields:
        if field.name in extended.properties:
            continue
        value = pcb.field_value(field)
        if value is None:
            value = component.properties.get(field.name, "")
        extended = with_property(extended, name=field.name, value=value)
    key = component.properties.get(PATH_PROPERTY) or component.ref or old.id
    copper = tuple(layer.name for layer in design.board.layers if layer.kind == "copper")
    new = place_footprint(
        extended,
        component=component,
        at=at,
        rotation=rotation,
        side=side,
        locked=old.locked,
        key=key,
        copper=copper or ("F.Cu", "B.Cu"),
    )
    nets = {pad.number: pad.net_id for pad in old.pads if pad.number}
    pads = tuple(
        dataclasses.replace(pad, net_id=nets.get(pad.number)) if pad.number else pad for pad in new.pads
    )
    fields = new.fields
    if side == old.side:
        kept = {field.name: field for field in old.fields}
        carried: list[FootprintField] = []
        for field in new.fields:
            was = kept.get(field.name)
            if was is None:
                carried.append(field)
            else:
                values = {name: getattr(was, name) for name in FIELD_VALUES}
                carried.append(dataclasses.replace(field, **values))
        fields = tuple(carried)
    return dataclasses.replace(
        new,
        id=old.id,
        native_ids={**new.native_ids, **old.native_ids},
        provenance=old.provenance,
        pads=pads,
        fields=fields,
    )


def move_footprint(
    design: Design,
    footprint_id: str,
    *,
    at: Point | None = None,
    rotation: Udeg | None = None,
    side: Side | None = None,
    definitions: Mapping[str, FootprintDef] | None = None,
    force: bool = False,
) -> Design:
    """``design`` with the footprint ``footprint_id`` at the new placement and nothing else changed.

    ``None`` keeps a value. A translation changes only the position. A new rotation or side re-places the
    footprint from ``definitions[<lib_ref>]``; without that definition ``PlacementError`` carries
    ``place.no-definition``. A locked footprint is moved only with ``force`` (``place.locked``), and an
    unknown id gives ``place.unknown-ref``. The board order of the footprints is kept.
    """
    board = design.board
    footprints = board.footprints if board is not None else ()
    index = next((i for i, fp in enumerate(footprints) if fp.id == footprint_id), None)
    if board is None or index is None:
        raise _refuse("place.unknown-ref", f"the board has no footprint {footprint_id}", footprint_id)
    old = footprints[index]
    ref = footprint_ref(design, old)
    if old.locked and not force:
        raise _refuse(
            "place.locked", f"{ref} is locked on the board and is not moved", ref, "pass --force to move it"
        )
    new_at = old.position if at is None else at
    new_rotation = old.rotation if rotation is None else rotation % pcb.FULL_TURN
    new_side = old.side if side is None else side
    if (new_rotation, new_side) == (old.rotation, old.side):
        if new_at == old.position:
            return design
        new = dataclasses.replace(old, position=new_at)
    else:
        definition = (definitions or {}).get(old.lib_ref)
        if definition is None:
            raise _refuse(
                "place.no-definition",
                f"{ref}: no library definition of {old.lib_ref!r}, so its rotation and side cannot change",
                ref,
                "add the library to the project's fp-lib-table, or move the part without turning it",
            )
        new = _replaced(design, old, definition, new_at, new_rotation, new_side)
    changed = (*footprints[:index], new, *footprints[index + 1 :])
    return dataclasses.replace(design, board=dataclasses.replace(board, footprints=changed))


__all__ = ["EVIDENCE", "FIELD_VALUES", "PlacementError", "footprint_ref", "move_footprint"]
