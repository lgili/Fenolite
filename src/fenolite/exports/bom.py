# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The neutral bill of materials: parts, grouped lines and the difference of two bills (capability
assembly-outputs, "Neutral BOM parts and lines" and "BOM difference"; user guide ``docs/assembly.md``).

A part is one component that goes on the bill. A line is the parts that share the values of the
template's ``group_by`` fields. Nothing here reads a file or runs a tool, and no float is used.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from fenolite.backends.kicad import bom as kicad_bom
from fenolite.core.evidence import Evidence, Level
from fenolite.exports.assembly import (
    DNP_TEXT,
    PROPERTY_PREFIX,
    BomTemplate,
    TemplateError,
    footprint_name,
    natural_key,
    property_name,
)
from fenolite.exports.codes import issue
from fenolite.model.circuit import Component
from fenolite.model.design import Design

EVIDENCE_KICAD = kicad_bom.EVIDENCE
"""The evidence of parts read from ``kicad-cli`` (``H-K-BOM-CSV``); the caller adds the oracle's version."""
EVIDENCE_MODEL = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-BOM-MODEL",))
"""``KICAD-VERIFIED`` for a built project that has its schematic: there the parts of the model equal the
parts ``kicad-cli`` lists, on 9.0.9 and 10.0.6 (``H-K-BOM-MODEL``). A caller that lists any other input
lowers the level to ``INFERRED``."""
RESERVED_PROPERTIES = frozenset({"Reference", "Value", "Footprint", "Datasheet", "Description"})
"""The component properties that are fields of a part and so are left out of ``BomPart.properties``."""
LEFT_OUT_ATTRIBUTES = frozenset({"board_only", "exclude_from_bom"})
VIRTUAL_PREFIX = "#"
"""A reference that starts with ``#`` names a power flag or another virtual symbol."""
Change = Literal["added", "removed", "changed"]


@dataclass(frozen=True, slots=True)
class BomPart:
    """One part of the bill. ``footprint`` is the lib id; ``properties`` are the user properties."""

    ref: str
    value: str = ""
    footprint: str = ""
    description: str = ""
    datasheet: str = ""
    dnp: bool = False
    properties: Mapping[str, str] = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class BomLine:
    """The parts of one group: ``fields`` holds the text of every field the template names, and ``key``
    the values of its ``group_by`` fields (the reference, when ``group_by`` is empty)."""

    refs: tuple[str, ...]
    quantity: int
    fields: Mapping[str, str]
    key: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BomChange:
    """A line that differs between two bills: ``added`` (only in the second), ``removed`` (only in the
    first) or ``changed`` (in both, with different references)."""

    key: tuple[str, ...]
    change: Change
    a_refs: tuple[str, ...]
    b_refs: tuple[str, ...]


def _ref_key(ref: str) -> tuple[tuple[tuple[int, int | str], ...], str]:
    return natural_key(ref), ref


def _part(component: Component, footprint_dnp: bool) -> BomPart:
    properties = component.properties
    return BomPart(
        ref=component.ref,
        value=component.value,
        footprint=component.lib_footprint_ref,
        description=properties.get("Description", ""),
        datasheet=properties.get("Datasheet", ""),
        dnp=component.dnp or footprint_dnp,
        properties={k: v for k, v in properties.items() if k not in RESERVED_PROPERTIES},
    )


def parts_from_model(design: Design) -> tuple[BomPart, ...]:
    """One part per component that has a placed footprint, in natural order of the reference.

    Left out: a component whose footprint has the attribute ``board_only`` or ``exclude_from_bom``, and a
    reference that starts with ``#``.
    """
    board = design.board
    if board is None:
        return ()
    components = {component.id: component for component in design.circuit.components}
    parts: dict[str, BomPart] = {}
    left_out: set[str] = set()
    for footprint in board.footprints:
        component = components.get(footprint.component_id)
        if component is None:
            continue
        if LEFT_OUT_ATTRIBUTES & set(footprint.attributes) or component.ref.startswith(VIRTUAL_PREFIX):
            left_out.add(component.id)
            continue
        found = parts.get(component.id)
        dnp = "dnp" in footprint.attributes or (found is not None and found.dnp)
        parts[component.id] = _part(component, dnp)
    kept = [part for ident, part in parts.items() if ident not in left_out]
    return tuple(sorted(kept, key=lambda part: _ref_key(part.ref)))


def kicad_fields(template: BomTemplate) -> tuple[str, ...]:
    """The fields to ask ``kicad-cli`` for under ``template``: the base fields, then each user property
    that a column or ``group_by`` names, sorted. A property name with a comma cannot be asked for: it
    raises ``TemplateError`` with one ``bom.field-unsupported`` issue per name."""
    names = [
        name
        for field_name in (*(column.field for column in template.columns), *template.group_by)
        if (name := property_name(field_name)) is not None
    ]
    bad = kicad_bom.unsupported_fields(names)
    if bad:
        raise TemplateError(
            tuple(
                issue(
                    "bom.field-unsupported",
                    f"the property {name!r} has a comma in its name, which kicad-cli cannot be asked for",
                    where=f"{PROPERTY_PREFIX}{name}",
                    hint="use --source model, or rename the property",
                )
                for name in bad
            )
        )
    return kicad_bom.bom_fields(names)


def parts_from_kicad(rows: Iterable[kicad_bom.BomRow]) -> tuple[BomPart, ...]:
    """The parts of the rows that ``kicad-cli`` exported, in natural order of the reference. KiCad has
    already left out what is not on the bill; a reference that starts with ``#`` is dropped all the same."""
    parts = [
        BomPart(
            ref=row.ref,
            value=row.value,
            footprint=row.footprint,
            description=row.description,
            datasheet=row.datasheet,
            dnp=row.dnp,
            properties=dict(row.properties),
        )
        for row in rows
        if not row.ref.startswith(VIRTUAL_PREFIX)
    ]
    return tuple(sorted(parts, key=lambda part: _ref_key(part.ref)))


def part_value(part: BomPart, field_name: str) -> str:
    """The text of a field of one part (the fields a part has: not ``refs``, ``quantity`` or ``item``)."""
    name = property_name(field_name)
    if name is not None:
        return part.properties.get(name, "")
    if field_name == "footprint_name":
        return footprint_name(part.footprint)
    if field_name == "dnp":
        return DNP_TEXT if part.dnp else ""
    if field_name in ("value", "footprint", "description", "datasheet"):
        return str(getattr(part, field_name))
    raise ValueError(f"{field_name!r} is not a field of a part")


def _shared(parts: Sequence[BomPart], field_name: str, separator: str) -> str:
    values: list[str] = []
    for part in parts:
        value = part_value(part, field_name)
        if value not in values:
            values.append(value)
    return values[0] if len(values) == 1 else separator.join(values)


def group(parts: Iterable[BomPart], template: BomTemplate) -> tuple[BomLine, ...]:
    """The lines of ``parts`` under ``template``: DNP parts left out first when ``exclude_dnp`` is true,
    then one line per distinct value of the ``group_by`` fields (one line per part when it is empty).

    References inside a line and lines among themselves are in natural order of the reference.
    """
    kept = sorted(
        (part for part in parts if not (template.exclude_dnp and part.dnp)),
        key=lambda part: _ref_key(part.ref),
    )
    groups: dict[tuple[str, ...], list[BomPart]] = {}
    for part in kept:
        if template.group_by:
            key = tuple(part_value(part, name) for name in template.group_by)
        else:
            key = (part.ref,)
        groups.setdefault(key, []).append(part)
    names = dict.fromkeys((*(column.field for column in template.columns), *template.group_by))
    lines: list[BomLine] = []
    for item, (key, members) in enumerate(groups.items(), start=1):  # first references are in order
        refs = tuple(part.ref for part in members)
        fields: dict[str, str] = {}
        for name in names:
            if name == "refs":
                fields[name] = template.ref_separator.join(refs)
            elif name == "quantity":
                fields[name] = str(len(refs))
            elif name == "item":
                fields[name] = str(item)
            else:
                fields[name] = _shared(members, name, template.ref_separator)
        lines.append(BomLine(refs, len(refs), fields, key))
    return tuple(lines)


def table(lines: Iterable[BomLine], template: BomTemplate) -> tuple[tuple[str, ...], ...]:
    """The cells of ``lines`` as text, one row per line, in the order of the template's columns."""
    return tuple(tuple(line.fields.get(column.field, "") for column in template.columns) for line in lines)


def difference(a: Iterable[BomLine], b: Iterable[BomLine]) -> tuple[BomChange, ...]:
    """What changed from bill ``a`` to bill ``b``, both grouped under one template, sorted by key."""
    first = {line.key: line.refs for line in a}
    second = {line.key: line.refs for line in b}
    changes: list[BomChange] = []
    for key in sorted(set(first) | set(second)):
        if key not in first:
            changes.append(BomChange(key, "added", (), second[key]))
        elif key not in second:
            changes.append(BomChange(key, "removed", first[key], ()))
        elif first[key] != second[key]:
            changes.append(BomChange(key, "changed", first[key], second[key]))
    return tuple(changes)


__all__ = [
    "EVIDENCE_KICAD",
    "EVIDENCE_MODEL",
    "LEFT_OUT_ATTRIBUTES",
    "RESERVED_PROPERTIES",
    "BomChange",
    "BomLine",
    "BomPart",
    "difference",
    "group",
    "kicad_fields",
    "part_value",
    "parts_from_kicad",
    "parts_from_model",
    "table",
]
