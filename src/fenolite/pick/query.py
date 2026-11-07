# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Part queries on the pick side (change c0254, ``docs/picking.md``, "Queries").

The record and the closed key table live in ``fenolite.core.partquery``, so that ``fenolite.dsl`` builds
them without importing this package. ``parse_query`` reads a canonical query text back (``fenolite pick
--propose "capacitor(10uF, rating>=25V)"``): the kind, the value (a quantity, or a range in the text of a
c0246 range) and each ``<key><op><value>`` constraint.
"""

from __future__ import annotations

import re
from fractions import Fraction

from fenolite.core.errors import FormatError
from fenolite.core.partquery import KEYS, KINDS, VALUE_UNITS, Bounds, Constraint, Key, PartQuery, key
from fenolite.core.quantities import QuantityError, parse
from fenolite.pick.rows import tolerance_of

_HEAD = re.compile(r"\s*([a-z]+)\((.*)\)\s*")
_RANGE = re.compile(r"(?:(\S+)\s+\()?~?([^()\s]*?)\.\.~?([^()\s]*?)\)?")


def _amount(unit: str, text: str, what: str) -> Fraction:
    try:
        return parse(unit, text.lstrip("~"))
    except QuantityError as error:
        raise FormatError(f"{what}: {error}", locator=what) from None


def _value(kind: str, text: str) -> tuple[Bounds, bool]:
    unit = VALUE_UNITS[kind]
    if ".." not in text:
        exact = _amount(unit, text, "value")
        return Bounds(unit, exact, exact, exact), True
    found = _RANGE.fullmatch(text.strip())
    if found is None:
        raise FormatError(f"value: {text!r} is not a quantity or a range of {unit}", locator="value")
    nominal_text, low_text, high_text = found.groups()
    low = _amount(unit, low_text, "value") if low_text else None
    high = _amount(unit, high_text, "value") if high_text else None
    nominal = _amount(unit, nominal_text, "value") if nominal_text else None
    return Bounds(unit, low, high, nominal), False


def _constraint(found: Key, text: str) -> Constraint:
    if found.unit == "percent":
        return tolerance_of(text, key=found.name)
    if found.unit == "texts":
        return tuple(sorted(set(text.split("|"))))
    if found.unit == "text":
        return text
    if found.unit == "ppm":
        return Fraction(text.removesuffix("ppm/K"))
    return _amount(found.unit, text, found.name)


def _split(body: str) -> list[str]:
    """The comma-separated items of ``body``, commas inside parentheses kept."""
    items: list[str] = []
    depth, start = 0, 0
    for index, char in enumerate(body):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            items.append(body[start:index].strip())
            start = index + 1
    tail = body[start:].strip()
    if tail:
        items.append(tail)
    return items


def parse_query(text: str) -> PartQuery:
    """The query of a canonical text such as ``resistor(10kΩ, tolerance<=1%, case=0603)``; ``FormatError``
    (``FEN-3004``) for a text that is not one."""
    head = _HEAD.fullmatch(text)
    if head is None or head.group(1) not in KINDS:
        raise FormatError(
            f"{text!r} is not a query such as 'capacitor(10uF, rating>=25V)'; kinds: {', '.join(KINDS)}"
        )
    kind, body = head.group(1), head.group(2)
    items = _split(body)
    if not items:
        raise FormatError(f"{text!r} names no value")
    bounds, exact = _value(kind, items[0])
    constraints: dict[str, Constraint] = {}
    for item in items[1:]:
        match = re.fullmatch(r"([a-z]+)(>=|<=|=)(.+)", item)
        if match is None:
            raise FormatError(f"{item!r} is not a constraint <key><op><value>", locator=item)
        name, op, value = match.groups()
        try:
            found = key(kind, name)
        except KeyError:
            names = ", ".join(entry.name for entry in KEYS[kind])
            raise FormatError(f"{kind} has no key {name!r}; its keys are {names}", locator=name) from None
        if op != found.op:
            raise FormatError(f"{name} takes {found.op}, not {op}", locator=name)
        constraints[name] = _constraint(found, value.strip())
    ordered = tuple(
        (entry.name, constraints[entry.name]) for entry in KEYS[kind] if entry.name in constraints
    )
    return PartQuery(kind, bounds, exact, ordered, text.strip(), value_text=items[0])


__all__ = ["parse_query"]
