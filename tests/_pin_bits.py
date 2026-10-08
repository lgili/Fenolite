# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Compare two written schematic files that may differ only in the pins' ``PINCONGLOMERATE`` (change
c0148, which adds bit 0x20 to every pin the writers write).

``pin_bits_only(old, new, path)`` reads both with Fenolite's own reader and returns the problems: a record
that differs in another key or field, or a pin whose conglomerate is not the old one with 0x20 added. The
bits 0x08 and 0x10 are the same on both sides: the old pin, without 0x20, reads today as hide flags (as
Altium Designer 26 showed it), so its ``name_shown`` and ``designator_shown`` are the opposite of the new
pin's (``schematic-library.md``, "Binary pin record").
"""

from __future__ import annotations

from fenolite.backends.altium.read.sch import read_schematic
from fenolite.backends.altium.read.sch.records import Pin, SchRecord
from fenolite.backends.altium.read.schlib import read_schlib

SHOW_FLAGS = 0x20


def _records(data: bytes, path: str) -> list[SchRecord]:
    if path.lower().endswith(".schlib"):
        library = read_schlib(data, file=path)
        return [record for component in library.components for record in component.records]
    return list(read_schematic(data, file=path).records)


def _pin(pin: Pin) -> tuple[object, ...]:
    return (
        pin.owner_part,
        pin.name,
        pin.designator,
        pin.electrical,
        pin.location,
        pin.length,
        pin.direction,
        pin.hidden,
        pin.formal_type,
        pin.inner_edge,
        pin.outer_edge,
        pin.inside,
        pin.outside,
        pin.swap_group,
        pin.part_and_sequence,
    )


def pin_bits_only(old: bytes, new: bytes, path: str) -> list[str]:
    """The ways in which ``new`` differs from ``old`` beyond bit 0x20 of each pin; empty when none."""
    before, after = _records(old, path), _records(new, path)
    if len(before) != len(after):
        return [f"{path}: {len(before)} records before, {len(after)} after"]
    problems: list[str] = []
    for index, (a, b) in enumerate(zip(before, after, strict=True)):
        where = f"{path} record {index}"
        if isinstance(a, Pin) != isinstance(b, Pin):
            problems.append(f"{where}: a pin on one side only")
        elif isinstance(a, Pin) and isinstance(b, Pin):
            if _pin(a) != _pin(b):
                problems.append(f"{where}: a pin field other than PINCONGLOMERATE differs")
            if a.conglomerate & SHOW_FLAGS or b.conglomerate != a.conglomerate | SHOW_FLAGS:
                problems.append(f"{where}: PINCONGLOMERATE {a.conglomerate} became {b.conglomerate}")
            if (a.name_shown, a.designator_shown) != (not b.name_shown, not b.designator_shown):
                problems.append(f"{where}: the meant visibility changed")
        else:
            keys_a = a.props.keys() if a.props is not None else ()
            keys_b = b.props.keys() if b.props is not None else ()
            fields_a = [(k, a.props.get(k)) for k in keys_a if k != "PINCONGLOMERATE"] if a.props else []
            fields_b = [(k, b.props.get(k)) for k in keys_b if k != "PINCONGLOMERATE"] if b.props else []
            if fields_a != fields_b:
                problems.append(f"{where}: the record differs")
    return problems


__all__ = ["SHOW_FLAGS", "pin_bits_only"]
