# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Part queries and the defaults that cascade into them (change c0254; ``docs/dsl.md``, "Part queries",
and ``docs/picking.md``).

``resistor(...)``, ``capacitor(...)`` and ``inductor(...)`` describe a passive by what it must be and return
a ``PartQuery`` of plain data (``fenolite.core.partquery``). ``design.part(device=query)`` makes a part whose
device is not known yet: the build resolves it against the design lock and the catalog (``fenolite.pick``),
never the script. ``Design.defaults`` and a block builder's ``defaults`` give, per kind, constraint keys
that apply to every query below them: the design's, then each enclosing block's from the outermost to the
innermost, then the call's; a later level replaces a key and ``None`` removes it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from fractions import Fraction
from typing import TYPE_CHECKING, cast

from fenolite.core.partquery import (
    KEYS,
    KINDS,
    PINS,
    VALUE_UNITS,
    Bounds,
    Constraint,
    Key,
    PartQuery,
    Percent,
    key,
)
from fenolite.dsl.errors import DslError
from fenolite.dsl.quantity import UNITS, Quantity, Range, Tolerance, decimal_text

if TYPE_CHECKING:
    from fenolite.dsl.devices import Origin
    from fenolite.dsl.part import Part
    from fenolite.model.library import DeviceDef

CASE = re.compile(r"[0-9]{4}")
"""An EIA inch case code (``0603``); metric codes are not read (``design.md``, open question 5)."""
SERIES_NAMES: tuple[str, ...] = ("E6", "E12", "E24", "E48", "E96", "E192")
"""The series a ``series`` key may name (``fenolite.pick.series.SERIES``)."""
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+:@-]*")
Level = dict[str, Constraint | None]
"""One defaults level of one kind: key → value, ``None`` removing the key."""


def _unit_name(unit: str) -> str:
    return {"percent": "a tolerance pct(...)", "ppm": "a number of ppm/K", "text": "a name"}.get(
        unit, f"a quantity in {unit}"
    )


def check_constraint(kind: str, name: str, value: object, where: str) -> Constraint | None:
    """``value`` of the key ``name`` of ``kind`` as a constraint (``None`` stays ``None``); ``DslError``
    naming ``where``, the key and what it takes otherwise."""
    try:
        found = key(kind, name)
    except KeyError:
        names = ", ".join(item.name for item in KEYS[kind])
        raise DslError(f"{where}: {kind}() has no key {name!r}; its keys are {names}") from None
    if value is None:
        return None
    if isinstance(value, float):
        raise DslError(f"{where}: {name}={value!r} is not exact; give {_unit_name(found.unit)}")
    return _constraint(found, value, where)


def _constraint(found: Key, value: object, where: str) -> Constraint:
    unit, name = found.unit, found.name
    if unit == "percent":
        if not isinstance(value, Tolerance):
            raise DslError(f"{where}: {name} takes a tolerance such as pct(1), not {value!r}")
        return Percent(value.lo, value.hi)
    if unit == "ppm":
        if isinstance(value, bool) or not isinstance(value, (int, Fraction, str)):
            raise DslError(
                f"{where}: {name} takes a number of ppm/K (an int, a Fraction or a text), not {value!r}"
            )
        try:
            number = Fraction(value.strip()) if isinstance(value, str) else Fraction(value)
        except ValueError:
            raise DslError(f"{where}: {name}={value!r} is not a number of ppm/K") from None
        if number < 0:
            raise DslError(f"{where}: {name} is a magnitude in ppm/K, not {value!r}")
        return number
    if unit == "text":
        if not isinstance(value, str) or not value:
            raise DslError(f"{where}: {name} takes a name, not {value!r}")
        if name == "case" and not CASE.fullmatch(value):
            raise DslError(f"{where}: case is an EIA inch code such as '0603', not {value!r}")
        if name == "series" and value not in SERIES_NAMES:
            raise DslError(f"{where}: series is one of {', '.join(SERIES_NAMES)}, not {value!r}")
        if not NAME.fullmatch(value):
            raise DslError(f"{where}: {name}={value!r} is not a name")
        return value
    if unit == "texts":
        names = cast("object", (value,) if isinstance(value, str) else value)
        if not isinstance(names, (tuple, list)) or not names:
            raise DslError(f"{where}: {name} takes a name or a tuple of names, not {value!r}")
        out: list[str] = []
        for item in tuple(cast("list[object]", names)):
            if not isinstance(item, str) or not NAME.fullmatch(item):
                raise DslError(f"{where}: {name} takes names such as 'X7R', not {item!r}")
            out.append(item)
        return tuple(sorted(set(out)))
    if not isinstance(value, Quantity):
        raise DslError(f"{where}: {name} takes a quantity in {unit}, such as {_example(unit)}, not {value!r}")
    if value.unit != unit:
        raise DslError(f"{where}: {name} takes a quantity in {unit}, not one in {value.unit}")
    if value.value < 0:
        raise DslError(f"{where}: {name} is a magnitude, not {value.text()}")
    return value.value


def _example(unit: str) -> str:
    return {"watt": "watt('100m')", "volt": "volt(25)", "ampere": "amp(1)", "ohm": "ohm('50m')"}.get(
        unit, unit
    )


def constraint_text(found: Key, value: Constraint) -> str:
    """``<key><op><value>`` of one constraint, as the canonical text prints it."""
    op = "=" if found.op == "=" else found.op
    if isinstance(value, Percent):
        shown = value.text()
    elif isinstance(value, tuple):
        shown = "|".join(value)
    elif isinstance(value, str):
        shown = value
    elif found.unit == "ppm":
        shown = f"{decimal_text(value, found.name)}ppm/K"
    else:
        shown = Quantity(found.unit, value).text()
    return f"{found.name}{op}{shown}"


def canonical(kind: str, head: str, constraints: Mapping[str, Constraint]) -> str:
    """``<kind>(<head>, <key><op><value>, ...)`` with the keys in the order of the kind."""
    parts = [head] if head else []
    parts += [
        constraint_text(found, constraints[found.name]) for found in KEYS[kind] if found.name in constraints
    ]
    return f"{kind}({', '.join(parts)})"


def _value(kind: str, value: object, where: str) -> tuple[Bounds, bool, str]:
    unit = VALUE_UNITS[kind]
    if isinstance(value, Quantity):
        if value.unit != unit:
            raise DslError(f"{where}: the value of {kind}() is a quantity in {unit}, not one in {value.unit}")
        exact = value.value
        return Bounds(unit, exact, exact, exact), True, value.text()
    if isinstance(value, Range):
        if value.unit != unit:
            raise DslError(f"{where}: the value of {kind}() is a range in {unit}, not one in {value.unit}")
        return Bounds(unit, value.low, value.high, value.nominal_value), False, value.text()
    raise DslError(
        f"{where}: the value of {kind}() is a quantity or a range in {unit} (such as "
        f"{'ohm' if unit == 'ohm' else unit}(...)), not {value!r}"
    )


def make_query(kind: str, value: object, constraints: Mapping[str, object]) -> PartQuery:
    """The call-level query of ``kind``: the value checked, each key checked, ``None`` recorded as a
    cleared key."""
    where = f"{kind}()"
    bounds, exact, head = _value(kind, value, where)
    given: dict[str, Constraint] = {}
    cleared: list[str] = []
    for name, item in constraints.items():
        checked = check_constraint(kind, name, item, where)
        if checked is None:
            cleared.append(name)
        else:
            given[name] = checked
    if not exact and "tolerance" in given:
        raise DslError(
            f"{where}: the value {head} already states a tolerance; give tolerance= with a plain "
            "quantity, or the range alone (two answers to one question)"
        )
    ordered = tuple((found.name, given[found.name]) for found in KEYS[kind] if found.name in given)
    return PartQuery(
        kind,
        bounds,
        exact,
        ordered,
        canonical(kind, head, dict(ordered)),
        tuple(sorted(cleared)),
        value_text=head,
    )


def resistor(value: Quantity | Range, **constraints: object) -> PartQuery:
    """A resistor by value (a quantity or a range in ohms) and constraints: ``tolerance``, ``power``,
    ``voltage``, ``case``, ``series``, ``tempco``, ``row`` (``docs/picking.md``, "Queries")."""
    return make_query("resistor", value, constraints)


def capacitor(value: Quantity | Range, **constraints: object) -> PartQuery:
    """A capacitor by value (in farads) and ``tolerance``, ``rating``, ``case``, ``dielectric``, ``series``,
    ``row``."""
    return make_query("capacitor", value, constraints)


def inductor(value: Quantity | Range, **constraints: object) -> PartQuery:
    """An inductor by value (in henries) and ``tolerance``, ``current``, ``saturation``, ``dcr``, ``case``,
    ``row``."""
    return make_query("inductor", value, constraints)


# -------------------------------------------------------------------------------------------- defaults


def set_defaults(store: dict[str, Level], kinds: Mapping[str, object], where: str) -> None:
    """Merge ``kinds`` (kind → mapping of keys) into ``store``, checked; a ``None`` value is kept, so that
    the key is removed at this level."""
    checked: dict[str, Level] = {}
    for kind, table in kinds.items():
        if kind not in KINDS:
            raise DslError(f"{where}: {kind!r} is no query kind; the kinds are {', '.join(KINDS)}")
        if not isinstance(table, Mapping):
            raise DslError(f"{where}: the defaults of {kind} are a mapping of its keys, not {table!r}")
        level: Level = {}
        for name, value in cast("Mapping[object, object]", table).items():
            if not isinstance(name, str):
                raise DslError(f"{where}: a key of {kind} is a name, not {name!r}")
            level[name] = check_constraint(kind, name, value, f"{where} {kind}")
        checked[kind] = level
    for kind, level in checked.items():
        store.setdefault(kind, {}).update(level)


def _levels(part: Part) -> list[Level]:
    """The defaults levels of ``part``'s kind: the design's, then each enclosing block's, outermost first."""
    query = part.call_query
    assert query is not None
    found: list[Level] = []
    parent = part.parent
    chain: list[object] = []
    while parent is not None:
        chain.append(parent)
        parent = getattr(parent, "parent", None)
    for container in reversed(chain):
        store = cast("dict[str, Level] | None", getattr(container, "query_defaults", None))
        if store is not None and query.kind in store:
            found.append(store[query.kind])
    return found


def merged(kind: str, levels: list[Level], call: PartQuery | None) -> dict[str, Constraint]:
    """The effective constraints: each level in turn, then the call's keys and cleared keys."""
    out: dict[str, Constraint] = {}
    for level in levels:
        for name, value in level.items():
            if value is None:
                out.pop(name, None)
            else:
                out[name] = value
    if call is not None:
        for name in call.cleared:
            out.pop(name, None)
        out.update(dict(call.constraints))
    return out


def effective(part: Part) -> PartQuery:
    """The effective query of a query part: the defaults merged into its call, with its canonical text."""
    call = part.call_query
    assert call is not None
    if call.generator is not None:
        return call
    constraints = merged(call.kind, _levels(part), call)
    if not call.exact:
        constraints.pop("tolerance", None)  # the range states the tolerance; a default does not add one
    ordered = tuple(
        (found.name, constraints[found.name]) for found in KEYS[call.kind] if found.name in constraints
    )
    return PartQuery(
        call.kind,
        call.value,
        call.exact,
        ordered,
        canonical(call.kind, call.value_text, dict(ordered)),
        (),
        None,
        call.value_text,
    )


def query_pin(part: Part, text: str) -> str:
    """``text`` checked as a pin of a query part that has no device yet: ``1`` or ``2``."""
    if text in PINS:
        return text
    raise DslError(
        f"part {part.label} is a query part ({cast(PartQuery, part.call_query).kind}) without a device yet; "
        f"it has the pins {PINS[0]} and {PINS[1]}, not {text!r}"
    )


def value_text(unit: str, value: Fraction) -> str:
    """The value a picked part shows (``61.9kΩ``)."""
    return Quantity(unit, value).text()


__all__ = [
    "CASE",
    "apply_device",
    "SERIES_NAMES",
    "UNITS",
    "canonical",
    "capacitor",
    "check_constraint",
    "constraint_text",
    "effective",
    "inductor",
    "make_query",
    "merged",
    "query_pin",
    "resistor",
    "set_defaults",
    "value_text",
]


def apply_device(part: Part, device: DeviceDef, origin: Origin) -> None:
    """Give the query part ``part`` the device the build picked: its symbol, footprint, pin-to-pad map,
    value and identity properties, as a part made with ``device=<id>`` has them (``fenolite build``)."""
    from types import MappingProxyType

    from fenolite.dsl.part import _device_properties  # pyright: ignore[reportPrivateUsage]

    pads: dict[str, list[str]] = {}
    for pin, pad in device.pad_map:
        pads.setdefault(pin, []).append(pad)
    part.device = device
    part.device_origin = origin
    part.device_overrides = False
    part.lib_id = device.symbol
    part.footprint = device.footprint
    part.pad_map = MappingProxyType(
        {pin: found[0] if len(found) == 1 else tuple(found) for pin, found in sorted(pads.items())}
    )
    part.value = device.value
    part.properties = _device_properties(part.label, device, part.properties)
