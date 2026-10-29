# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The net roles of a design script (change c0222; capability design-dsl, "Net roles in the DSL";
``docs/dsl.md``, "Net roles"; ``docs/roles.md``).

``Design.net_role``, ``hot_loop``, ``kelvin``, ``gate_loop``, ``role_limits`` and ``part_class`` record
plain data here; ``convert.to_model`` turns it into ``RuleSet.roles`` with the source ``declared``. A group
names pads as ``part.pad(<number>)``, which the model keeps as ``REF-PIN`` with the pad number. A bad kind,
key, unit or pad, or a name used twice, raises ``DslError`` at the call.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from typing import TYPE_CHECKING, cast

from fenolite.dsl.errors import DslError
from fenolite.dsl.part import Net, Part, PinHandle
from fenolite.dsl.quantity import Quantity
from fenolite.dsl.units import as_nm, as_nm2
from fenolite.model.rules import (
    PART_CLASSES,
    PART_TERMINALS,
    ROLE_KEY,
    ROLE_KINDS,
    ROLE_LIMIT_UNITS,
    GateLoop,
    HotLoop,
    KelvinPair,
    NetRole,
    PartClass,
    PartClassName,
    RoleLimit,
    RoleSet,
    Terminal,
)

if TYPE_CHECKING:
    from fenolite.dsl.design import Design
    from fenolite.dsl.intents import PadRef

_SCALE = {"ampere": ("milliamps", 1000), "volt": ("millivolts", 1000), "ohm": ("milliohms", 1000)}


@dataclass(slots=True)
class RoleRecords:
    """What the role calls of one script recorded, in call order."""

    nets: dict[str, NetRole] = field(default_factory=lambda: {})
    loops: dict[str, tuple[PadRef, ...]] = field(default_factory=lambda: {})
    kelvins: dict[str, tuple[tuple[PadRef, ...], tuple[PadRef, ...], tuple[PadRef, ...]]] = field(
        default_factory=lambda: {}
    )
    gates: dict[str, tuple[PadRef, PadRef, PadRef, PadRef, tuple[PadRef, ...]]] = field(
        default_factory=lambda: {}
    )
    limits: dict[tuple[str, str, str], RoleLimit] = field(default_factory=lambda: {})
    classes: dict[str, tuple[Part, PartClassName, tuple[tuple[str, tuple[str, ...]], ...]]] = field(
        default_factory=lambda: {}
    )


def records(design: Design) -> RoleRecords:
    """The role records of ``design``."""
    return design.role_records


def _whole(value: object, unit: str, what: str) -> int:
    """A ``Quantity`` of ``unit`` as a whole number of its thousandths (mA, mV, mΩ)."""
    if not isinstance(value, Quantity) or value.unit != unit:
        raise DslError(f"{what}: {value!r} is not a quantity in {unit}; use {unit[:3]}(...)")
    name, scale = _SCALE[unit]
    scaled = value.value * scale
    if scaled.denominator != 1 or scaled <= 0:
        raise DslError(f"{what}: {value.value} {unit} is not a whole number of {name} above 0")
    return scaled.numerator


def _name(name: object, call: str, taken: Mapping[str, object]) -> str:
    if not isinstance(name, str) or not ROLE_KEY.fullmatch(name):
        raise DslError(f"{call}: the name {name!r} must match {ROLE_KEY.pattern}")
    if name in taken:
        raise DslError(f"{call}: the name {name!r} is used twice")
    return name


def _pad(value: object, what: str) -> PadRef:
    from fenolite.dsl.intents import PadRef

    if isinstance(value, PinHandle):
        raise DslError(
            f"{what} takes pads, not the pin {value.part.ref}[{value.designator!r}]: use part.pad(<number>)"
        )
    if not isinstance(value, PadRef):
        raise DslError(f"{what} takes a part.pad(<number>), not {value!r}")
    return value


def _pads(values: object, what: str, count: int | None = None) -> tuple[PadRef, ...]:
    if not isinstance(values, (list, tuple)):
        raise DslError(f"{what} takes a list or tuple of part.pad(<number>)")
    pads = tuple(_pad(value, what) for value in cast(Sequence[object], values))
    if count is not None and len(pads) != count:
        raise DslError(f"{what} takes {count} pads, not {len(pads)}")
    return pads


def _one_part(pads: Sequence[PadRef], what: str) -> None:
    if len({id(pad.part) for pad in pads}) != 1:
        raise DslError(f"{what} must belong to one part")


def net_role(
    design: Design, net: object, kind: object, current: object, voltage: object, sensitive: object
) -> None:
    found = records(design)
    if not isinstance(net, Net):
        raise DslError(f"net_role(): {net!r} is not a Net")
    what = f"net_role() {net.name!r}"
    if net.name in found.nets:
        raise DslError(f"{what}: the net has a role already")
    if kind not in ROLE_KINDS:
        raise DslError(f"{what}: kind {kind!r} is not one of {', '.join(ROLE_KINDS)}")
    if not isinstance(sensitive, bool):
        raise DslError(f"{what}: sensitive must be a bool")
    if sensitive and kind != "signal":
        raise DslError(f"{what}: sensitive is a flag of a signal role")
    milliamps = None if current is None else _whole(current, "ampere", f"{what}: current")
    millivolts = None if voltage is None else _whole(voltage, "volt", f"{what}: voltage")
    found.nets[net.name] = NetRole(
        net.name,
        kind,
        "declared",
        milliamps=milliamps,
        working_mv=millivolts,
        sensitive=sensitive,
    )


def hot_loop(design: Design, name: object, pads: object) -> None:
    found = records(design)
    key = _name(name, "hot_loop()", found.loops)
    chosen = _pads(pads, f"hot_loop() {key!r}: pads")
    if len(chosen) < 3:
        raise DslError(f"hot_loop() {key!r}: pads takes at least three pads, not {len(chosen)}")
    found.loops[key] = chosen


def kelvin(design: Design, name: object, element: object, receiver: object, force: object) -> None:
    found = records(design)
    key = _name(name, "kelvin()", found.kelvins)
    what = f"kelvin() {key!r}"
    sense = _pads(element, f"{what}: element", 2)
    _one_part(sense, f"{what}: both element pads")
    inputs = _pads(receiver, f"{what}: receiver", 2)
    forced = _pads(force, f"{what}: force") if force else ()
    if forced:
        if len(forced) != 2:
            raise DslError(f"{what}: force takes 2 pads, not {len(forced)}")
        _one_part((*sense, *forced), f"{what}: the force and element pads")
    found.kelvins[key] = (sense, inputs, forced)


def gate_loop(
    design: Design, name: object, drive: object, gate: object, source: object, ret: object, resistor: object
) -> None:
    found = records(design)
    key = _name(name, "gate_loop()", found.gates)
    what = f"gate_loop() {key!r}"
    out, pin, src, back = (_pad(value, f"{what}: {part}") for value, part in
                           ((drive, "drive"), (gate, "gate"), (source, "source"), (ret, "ret")))  # fmt: skip
    _one_part((pin, src), f"{what}: the gate and source pads")
    _one_part((out, back), f"{what}: the drive and return pads")
    series = _pads(resistor, f"{what}: resistor", 2) if resistor else ()
    if series:
        _one_part(series, f"{what}: the two resistor pads")
    found.gates[key] = (out, pin, src, back, series)


def _limit(key: str, value: object, what: str) -> int:
    unit = ROLE_LIMIT_UNITS[key]
    if unit.startswith("flag"):
        if not isinstance(value, bool):
            raise DslError(f"{what}: {key} is a flag: True or False")
        return int(value)
    if unit == "per mille":
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise DslError(f"{what}: {key} is a whole number of per mille above 0, such as 2000")
        return value
    if unit == "nm²":
        return as_nm2(value, name=f"{what}: {key}")
    if unit in ("nm", "nm per ampere"):
        length = as_nm(value, name=f"{what}: {key}")
        if length <= 0:
            raise DslError(f"{what}: {key} must be above 0")
        return length
    if unit == "mA":
        return _whole(value, "ampere", f"{what}: {key}")
    if unit == "mV":
        return _whole(value, "volt", f"{what}: {key}")
    if unit == "mΩ":
        return _whole(value, "ohm", f"{what}: {key}")
    # mK: a temperature rise in kelvin, as an int, a Fraction or a decimal string
    try:
        kelvin = Fraction(str(value)) if isinstance(value, str) else Fraction(cast(int | Fraction, value))
    except (TypeError, ValueError):
        raise DslError(f"{what}: {key} is a temperature rise in kelvin, such as 10 or '12.5'") from None
    millikelvin = kelvin * 1000
    if isinstance(value, bool) or millikelvin.denominator != 1 or millikelvin <= 0:
        raise DslError(f"{what}: {key} is not a whole number of millikelvin above 0")
    return millikelvin.numerator


def role_limits(design: Design, net: object, kind: object, limits: Mapping[str, object]) -> None:
    found = records(design)
    if net is not None and not isinstance(net, Net):
        raise DslError(f"role_limits(): net {net!r} is not a Net")
    if kind is not None and kind not in ROLE_KINDS:
        raise DslError(f"role_limits(): kind {kind!r} is not one of {', '.join(ROLE_KINDS)}")
    if net is not None and kind is not None:
        raise DslError("role_limits(): give net or kind, not both")
    if not limits:
        raise DslError("role_limits(): no limit given")
    name = net.name if isinstance(net, Net) else None
    what = "role_limits()" + (f" for {name!r}" if name else f" for kind {kind!r}" if kind else "")
    for key, value in limits.items():
        if key not in ROLE_LIMIT_UNITS:
            raise DslError(f"{what}: unknown key {key!r}; keys: {', '.join(ROLE_LIMIT_UNITS)}")
        order = (key, kind or "", name or "")
        if order in found.limits:
            raise DslError(f"{what}: {key} is given twice")
        found.limits[order] = RoleLimit(key, _limit(key, value, what), net=name, kind=kind)


def part_class(design: Design, part: object, cls: object, terminals: object) -> None:
    found = records(design)
    if not isinstance(part, Part):
        raise DslError(f"part_class(): {part!r} is not a Part")
    what = f"part_class() {part.ref!r}"
    if part.path in found.classes:
        raise DslError(f"{what}: the part has a class already")
    if cls not in PART_CLASSES:
        raise DslError(f"{what}: class {cls!r} is not one of {', '.join(PART_CLASSES)}")
    if terminals is not None and not isinstance(terminals, Mapping):
        raise DslError(f"{what}: terminals maps a terminal name to a pin number or a list of them")
    given: Mapping[object, object] = {} if terminals is None else cast(Mapping[object, object], terminals)
    allowed = PART_TERMINALS.get(cast(str, cls), ())
    rows: list[tuple[str, tuple[str, ...]]] = []
    for terminal, pins in given.items():
        if terminal not in allowed:
            raise DslError(
                f"{what}: {cls} has no terminal {terminal!r} (terminals: {', '.join(allowed) or 'none'})"
            )
        numbers = (pins,) if isinstance(pins, (str, int)) else tuple(cast(Sequence[object], pins))
        if not numbers or not all(
            isinstance(pin, (str, int)) and not isinstance(pin, bool) and str(pin) for pin in numbers
        ):
            raise DslError(f"{what}: terminal {terminal!r} takes a pin number or a list of them")
        rows.append((cast(str, terminal), tuple(str(pin) for pin in numbers)))
    found.classes[part.path] = (part, cls, tuple(rows))


def to_roles(design: Design) -> RoleSet | None:
    """The declared ``RoleSet`` of ``design``, or ``None`` when the script declares no role. ``DslError``
    names a group whose pad belongs to a part that is not in the design."""
    found = records(design)

    def name(pad: PadRef, what: str) -> str:
        if design.parts.get(pad.part.path) is not pad.part:
            raise DslError(f"{what}: part {pad.part.ref} is not in the design")
        return f"{pad.part.ref}-{pad.number}"

    def names(pads: Sequence[PadRef], what: str) -> tuple[str, ...]:
        return tuple(name(pad, what) for pad in pads)

    try:
        roles = RoleSet(
            nets=tuple(found.nets.values()),
            loops=tuple(
                HotLoop(key, names(pads, f"hot_loop() {key!r}")) for key, pads in found.loops.items()
            ),
            kelvins=tuple(
                KelvinPair(
                    key,
                    names(sense, f"kelvin() {key!r}"),
                    names(inputs, f"kelvin() {key!r}"),
                    names(forced, f"kelvin() {key!r}"),
                )  # fmt: skip
                for key, (sense, inputs, forced) in found.kelvins.items()
            ),
            gates=tuple(
                GateLoop(
                    key,
                    *names((out, pin, src, back), f"gate_loop() {key!r}"),
                    resistor=names(series, f"gate_loop() {key!r}"),
                )  # fmt: skip
                for key, (out, pin, src, back, series) in found.gates.items()
            ),
            limits=tuple(found.limits.values()),
            classes=tuple(
                PartClass(part.ref, cls, tuple(Terminal(terminal, pins) for terminal, pins in rows))
                for part, cls, rows in found.classes.values()
            ),
        )
    except ValueError as error:
        raise DslError(f"roles: {error}") from None
    return roles or None


__all__ = [
    "RoleRecords",
    "gate_loop",
    "hot_loop",
    "kelvin",
    "net_role",
    "part_class",
    "records",
    "role_limits",
    "to_roles",
]
