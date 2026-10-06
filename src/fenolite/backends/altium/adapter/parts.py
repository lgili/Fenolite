# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The components of one schematic sheet, from its component records and their children (capability
altium-import, "Schematic components and pins"; change c0043).

Altium places one component record per part; the parts of one component share the designator text. A
``PartGroup`` is one component: its part records, its reference, its value, its properties, its library
references and its pin table. Plain data, without ids: a sheet may be instantiated more than once.
"""

# evidence: see import_evidence

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PureWindowsPath

from fenolite.backends.altium.read.sch import (
    Component,
    Designator,
    Implementation,
    MapDefiner,
    Parameter,
    Pin,
    SchDocument,
    SchRecord,
)

COMMENT = "Comment"
FOOTPRINT_MODEL = "PCBLIB"


def locator(record: SchRecord) -> str:
    """``FileHeader#<index>`` for a record of the main stream, ``Additional#<index>`` for the other."""
    stream = "Additional" if record.ref.stream == "additional" else "FileHeader"
    return f"{stream}#{record.ref.index}"


def order(record: SchRecord) -> tuple[int, int]:
    """A sort key in stream order: the main stream first."""
    return (1 if record.ref.stream == "additional" else 0, record.ref.index)


@dataclass(frozen=True, slots=True)
class PartGroup:
    """One component of a sheet. ``parts`` are its component records in stream order; ``pins`` its pin
    table (one record per distinct designator); ``shown`` the pins that are drawn, per placed part, and so
    take part in connectivity."""

    ref: str
    parts: tuple[Component, ...]
    value: str
    properties: tuple[tuple[str, str], ...]
    lib_symbol_ref: str
    lib_footprint_ref: str
    pins: tuple[Pin, ...]
    shown: tuple[Pin, ...]
    has_designator: bool
    pin_pads: tuple[tuple[str, tuple[str, ...]], ...] = ()
    """The pin-to-pad map of the current footprint model, for the pins it does not map to a pad of their
    own designator: ``(pin designator, pad names)``."""

    @property
    def first(self) -> Component:
        return self.parts[0]

    @property
    def lowest(self) -> Component:
        """The part with the lowest part number (the first in stream order among equals)."""
        return min(self.parts, key=lambda part: (part.current_part, part.ref.index))

    @property
    def unique_ids(self) -> tuple[str, ...]:
        """The unique ids of the parts, the lowest part first."""
        lowest = self.lowest
        rest = [part.unique_id for part in self.parts if part is not lowest]
        return tuple(dict.fromkeys(i for i in (lowest.unique_id, *rest) if i))

    @property
    def locator(self) -> str:
        return locator(self.first)


def _stem(path: str) -> str:
    return PureWindowsPath(path).stem if path else ""


def _children(document: SchDocument, component: Component) -> tuple[SchRecord, ...]:
    return tuple(document.get(ref) for ref in component.children)


def _value(parameters: list[Parameter]) -> str:
    comment = next((p.text for p in parameters if p.name.casefold() == COMMENT.casefold()), "")
    if comment.startswith("="):
        wanted = comment[1:].strip().casefold()
        named = next((p.text for p in parameters if p.name.casefold() == wanted), None)
        return comment if named is None else named
    return comment


def _footprint(document: SchDocument, component: Component) -> str:
    models = [r for r in document.walk(component) if isinstance(r, Implementation)]
    models = [m for m in models if m.model_type.upper() == FOOTPRINT_MODEL]
    current = next((m for m in models if m.is_current), None)
    if current is None:
        return ""
    files = current.data_files
    library = _stem(files[0].file) if files else ""
    return f"{library}:{current.model_name}" if library and current.model_name else current.model_name


def _pin_pads(document: SchDocument, component: Component) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """The map records of the current footprint model that name other pads than the pin's designator."""
    current = next(
        (
            r
            for r in document.walk(component)
            if isinstance(r, Implementation) and r.is_current and r.model_type.upper() == FOOTPRINT_MODEL
        ),
        None,
    )
    if current is None:
        return ()
    found: dict[str, tuple[str, ...]] = {}
    for record in document.walk(current):
        if isinstance(record, MapDefiner) and record.implementations != (record.interface,):
            found.setdefault(record.interface, record.implementations)
    return tuple(found.items())


def part_groups(document: SchDocument) -> tuple[PartGroup, ...]:
    """The components of ``document`` in stream order of their first part. Component records with one
    designator text are the parts of one component; a record without a designator record is a component of
    its own."""
    grouped: dict[str, list[Component]] = {}
    lone: list[Component] = []
    for component in document.components():
        if component.owner is not None:
            continue
        designators = [r for r in _children(document, component) if isinstance(r, Designator)]
        if designators:
            grouped.setdefault(designators[0].text, []).append(component)
        else:
            lone.append(component)
    found: list[tuple[tuple[int, int], PartGroup]] = []
    for ref, parts in [*grouped.items(), *(("", [part]) for part in lone)]:
        first = parts[0]
        parameters = [r for r in _children(document, first) if isinstance(r, Parameter)]
        properties: dict[str, str] = {}
        for parameter in parameters:
            if parameter.name and parameter.name.casefold() != COMMENT.casefold():
                properties.setdefault(parameter.name, parameter.text)
        library = _stem(first.source_library)
        symbol = (
            f"{library}:{first.lib_reference}" if library and first.lib_reference else first.lib_reference
        )
        table: dict[str, Pin] = {}
        shown: list[Pin] = []
        for part in parts:
            pins = [r for r in _children(document, part) if isinstance(r, Pin)]
            for pin in sorted(pins, key=lambda p: (p.owner_display_mode, p.ref.index)):
                table.setdefault(pin.designator, pin)
            shown += [r for r in document.shown_children(part) if isinstance(r, Pin)]
        found.append(
            (
                order(first),
                PartGroup(
                    ref=ref,
                    parts=tuple(parts),
                    value=_value(parameters),
                    properties=tuple(properties.items()),
                    lib_symbol_ref=symbol,
                    lib_footprint_ref=_footprint(document, first),
                    pins=tuple(table.values()),
                    shown=tuple(shown),
                    has_designator=bool(parts) and first not in lone,
                    pin_pads=_pin_pads(document, first),
                ),
            )
        )
    return tuple(group for _key, group in sorted(found, key=lambda pair: pair[0]))


__all__ = ["PartGroup", "locator", "order", "part_groups"]
