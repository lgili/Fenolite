# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The neutral placement table: where each footprint lies and how it is turned, and the rules a template
applies to it (capability assembly-outputs, "Neutral placement rows"; user guide ``docs/assembly.md``).

A row starts in the board frame, which is the KiCad file frame: X to the right, Y down, integer
nanometres, and the footprint's stored angle in microdegrees on both sides (``docs/design-model.md``).
``apply`` then subtracts the origin, turns the Y axis and applies the rotation rule of the template.
The default template gives the content of KiCad's own position file. No float is used.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import Literal

from fenolite.backends.kicad.outline import BoardOutline
from fenolite.core.coords import Point
from fenolite.core.errors import FenoliteError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm, Udeg
from fenolite.exports.assembly import (
    FULL_TURN,
    PlacementTemplate,
    footprint_name,
    format_angle,
    format_length,
    natural_key,
    property_name,
)
from fenolite.exports.bom import RESERVED_PROPERTIES
from fenolite.exports.codes import issue
from fenolite.model.board import FootprintInstance, Side
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-PCB-POS", "H-K-POS-ROWS"))
"""``INFERRED`` until ``H-K-POS-ROWS`` holds on both KiCad majors (``H-K-PCB-POS`` already does)."""
Mount = Literal["smd", "through_hole", "other"]


class NoOutlineError(FenoliteError):
    """``origin = "outline"`` on a board without a closed outline, raised when the caller passes no list
    to collect the issue in."""

    def __init__(self, found: Issue) -> None:
        self.issues = (found,)
        super().__init__(found.message)


@dataclass(frozen=True, slots=True)
class PlacementRow:
    """One footprint in the board frame: ``position`` in nm (Y down), ``rotation`` as stored, in µdeg."""

    ref: str
    value: str
    footprint: str
    position: Point
    rotation: Udeg
    side: Side
    dnp: bool = False
    mount: Mount = "other"
    properties: Mapping[str, str] = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class PlacedRow:
    """A row after the template's rules: ``x`` and ``y`` in nm from the template's origin, with its Y
    direction, and ``rotation`` in µdeg within [0°, 360°)."""

    ref: str
    value: str
    footprint: str
    x: Nm
    y: Nm
    rotation: Udeg
    side: Side
    dnp: bool = False
    mount: Mount = "other"
    properties: Mapping[str, str] = field(default_factory=lambda: {})


def _mount(footprint: FootprintInstance) -> Mount:
    if "smd" in footprint.attributes:
        return "smd"
    return "through_hole" if "through_hole" in footprint.attributes else "other"


def rows_from_model(design: Design) -> tuple[PlacementRow, ...]:
    """One row per footprint that lacks the attribute ``exclude_from_pos_files``, in natural order of the
    reference. A footprint without a component is named by its id."""
    board = design.board
    if board is None:
        return ()
    components = {component.id: component for component in design.circuit.components}
    rows: list[PlacementRow] = []
    for footprint in board.footprints:
        if "exclude_from_pos_files" in footprint.attributes:
            continue
        component = components.get(footprint.component_id)
        properties = {} if component is None else component.properties
        rows.append(
            PlacementRow(
                ref=footprint.id if component is None else component.ref,
                value="" if component is None else component.value,
                footprint=footprint.lib_ref,
                position=footprint.position,
                rotation=footprint.rotation,
                side=footprint.side,
                dnp="dnp" in footprint.attributes or (component is not None and component.dnp),
                mount=_mount(footprint),
                properties={k: v for k, v in properties.items() if k not in RESERVED_PROPERTIES},
            )
        )
    return tuple(sorted(rows, key=lambda row: (natural_key(row.ref), row.ref)))


def rotate(rotation: Udeg, side: Side, footprint: str, template: PlacementTemplate) -> Udeg:
    """``(sign × rotation + side offset + footprint offset) mod 360°`` under the template's rule: the sign
    and offset of ``side``, and the offset of the first footprint entry whose ``match`` fits the lib id."""
    rule = template.rotation
    of_side = rule.top if side == "top" else rule.bottom
    extra = next((entry.offset for entry in rule.footprint if fnmatchcase(footprint, entry.match)), 0)
    return (of_side.sign * rotation + of_side.offset + extra) % FULL_TURN


def _origin(template: PlacementTemplate, outline: BoardOutline | None) -> Point | None:
    """The point subtracted from every position, or ``None`` when the outline is needed and missing."""
    if template.origin == "page":
        return Point(0, 0)
    if outline is None or not outline.rings:
        return None
    ring = outline.rings[0]
    ys = [point.y for point in ring]
    return Point(min(point.x for point in ring), max(ys) if template.y_axis == "up" else min(ys))


def apply(
    rows: Iterable[PlacementRow],
    template: PlacementTemplate,
    *,
    outline: BoardOutline | None = None,
    issues: list[Issue] | None = None,
) -> tuple[PlacedRow, ...]:
    """``rows`` under ``template``, in this order: the DNP and ``smd_only`` filters, the origin, the Y axis
    and the rotation rule. Lengths stay in nm and angles in µdeg; ``table`` prints them.

    With ``origin = "outline"`` and no closed outline there is no row: the issue ``pnp.no-outline`` is
    appended to ``issues``, or raised as ``NoOutlineError`` when ``issues`` is ``None``.
    """
    origin = _origin(template, outline)
    if origin is None:
        problem = "" if outline is None else outline.problem
        found = issue(
            "pnp.no-outline",
            'origin = "outline" needs a closed board outline' + (f" ({problem})" if problem else ""),
            where="placement.origin",
            hint='draw a closed outline on the edge layer, or use origin = "page"',
        )
        if issues is None:
            raise NoOutlineError(found)
        issues.append(found)
        return ()
    placed: list[PlacedRow] = []
    for row in rows:
        if (template.exclude_dnp and row.dnp) or (template.smd_only and row.mount != "smd"):
            continue
        y = row.position.y - origin.y
        placed.append(
            PlacedRow(
                ref=row.ref,
                value=row.value,
                footprint=row.footprint,
                x=row.position.x - origin.x,
                y=-y if template.y_axis == "up" else y,
                rotation=rotate(row.rotation, row.side, row.footprint, template),
                side=row.side,
                dnp=row.dnp,
                mount=row.mount,
                properties=row.properties,
            )
        )
    return tuple(placed)


def cell(row: PlacedRow, field_name: str, template: PlacementTemplate) -> str:
    """The text of one field of a placed row, as the template prints it."""
    name = property_name(field_name)
    if name is not None:
        return row.properties.get(name, "")
    if field_name in ("x", "y"):
        return format_length(row.x if field_name == "x" else row.y, template.units, template.decimals)
    if field_name == "rotation":
        return format_angle(row.rotation, template.rotation_decimals)
    if field_name == "side":
        return template.sides.top if row.side == "top" else template.sides.bottom
    if field_name == "footprint_name":
        return footprint_name(row.footprint)
    if field_name in ("ref", "value", "footprint"):
        return str(getattr(row, field_name))
    raise ValueError(f"{field_name!r} is not a field of a placement row")


def table(rows: Iterable[PlacedRow], template: PlacementTemplate) -> tuple[tuple[str, ...], ...]:
    """The cells of ``rows`` as text, one row each, in the order of the template's columns."""
    return tuple(tuple(cell(row, column.field, template) for column in template.columns) for row in rows)


__all__ = [
    "EVIDENCE",
    "NoOutlineError",
    "PlacedRow",
    "PlacementRow",
    "apply",
    "cell",
    "rotate",
    "rows_from_model",
    "table",
]
