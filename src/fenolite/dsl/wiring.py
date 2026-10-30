# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Connection helpers of the DSL (``docs/dsl.md``, "Connection helpers"; change c0247).

``series``, ``decouple``, ``pull_up`` and ``pull_down`` take parts and nets the script made and lower to
what the DSL already has: ``connect`` calls, and for ``decouple`` with ``near`` one ``Design.near`` rule
per capacitor. Every check of a call runs before its first connection, so a refused call connects
nothing."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from fenolite.dsl.errors import DslError
from fenolite.dsl.interfaces import I2C, Interface
from fenolite.dsl.part import Net, Part, PinHandle, connect
from fenolite.dsl.portnets import MAIN_MEMBERS, PortHandle, as_net, same_net
from fenolite.dsl.quantity import Quantity

if TYPE_CHECKING:
    from fenolite.dsl.design import Design

Link = tuple[Net, PinHandle]


def _ends(part: Part) -> tuple[PinHandle, PinHandle]:
    """The two ends of ``part``, without marking it ``two_terminal`` (that waits for a call that succeeds)."""
    return part._end(0), part._end(1)  # pyright: ignore[reportPrivateUsage]


def _part(value: object, what: str) -> Part:
    if isinstance(value, Part):
        return value
    if isinstance(value, Quantity):
        raise DslError(
            f"{what}: {value.text()!r} is a value, and a value does not choose a part; "
            "make the part with Part(...) and pass it"
        )
    raise DslError(f"{what} takes parts made with Part(...), not {value!r}")


def _net(value: object, what: str) -> Net:
    """``value`` as a net: a ``Net``, or a net-like ``Rail``, ``Ground``, ``Logic`` or port (change c0252)."""
    if isinstance(value, Net):
        return value
    if isinstance(value, Interface | PortHandle) and value.kind in MAIN_MEMBERS:
        found = as_net(value, what=what)
        if found is not None:
            return found
    raise DslError(f"{what} must be a Net, not {value!r}")


def _join(links: Sequence[Link], call: str) -> None:
    """Connect every ``(net, pin)`` of ``links``, after checking all of them: a pin on another net, a
    marked pin, a pin given two nets in this call, or two distinct nets of one name connect nothing."""
    planned: dict[tuple[int, str], Net] = {}
    names: dict[str, Net] = {}
    for net, pin in links:
        part = pin.part
        current = part.connections.get(pin.designator)
        if current is not None and not same_net(current, net):
            raise DslError(
                f"{call}: pin {part.ref} {pin.designator} is already on net {current.name}; "
                f"cannot join {net.name}"
            )
        if pin.designator in part.no_connects:
            raise DslError(
                f"{call}: pin {part.ref} {pin.designator} is marked as not connected; cannot join {net.name}"
            )
        other = planned.setdefault((id(part), pin.designator), net)
        if other is not net:
            raise DslError(
                f"{call}: pin {part.ref} {pin.designator} would join both {other.name} and {net.name}"
            )
        known = names.setdefault(net.name, net)
        design = part.design
        registered = None if design is None else design.nets.get(net.name)
        if not same_net(known, net) or (registered is not None and not same_net(registered, net)):
            raise DslError(f"{call}: two distinct nets are named {net.name!r}")
    for net, pin in links:
        connect(net, pin)


def series(*chain: object) -> tuple[Net, ...]:
    """Connect a chain from a net through two-pin parts to a net: ``series(vin, f1, d1, vprot)``.

    An inner item is a ``Part`` (entered at ``a``, left at ``b``), a tuple ``(in_pin, out_pin)`` of two
    distinct pin handles of one part (to turn it around, as ``(d1.b, d1.a)``, or use other pins), or a
    ``Net`` that names the joint between the parts beside it. Two parts next to each other are joined by a
    new net named ``<left path>-<right path>``; the new nets are returned in chain order."""
    call = "series()"
    if len(chain) < 2 or not isinstance(chain[0], Net) or not isinstance(chain[-1], Net):
        raise DslError(f"{call}: a chain starts and ends with a Net, with at least one part between")
    first, last = chain[0], chain[-1]
    steps: list[tuple[Part, PinHandle, PinHandle] | Net] = []
    for item in chain[1:-1]:
        if isinstance(item, Net):
            steps.append(item)
        elif isinstance(item, Part):
            steps.append((item, *_ends(item)))
        elif isinstance(item, tuple):
            pair: tuple[object, ...] = item  # pyright: ignore[reportUnknownVariableType]
            if (
                len(pair) != 2
                or not isinstance(pair[0], PinHandle)
                or not isinstance(pair[1], PinHandle)
                or pair[0].part is not pair[1].part
                or pair[0].designator == pair[1].designator
            ):
                raise DslError(
                    f"{call}: a tuple in a chain is two distinct pins of one part, such as (d1.b, d1.a), "
                    f"not {item!r}"
                )
            steps.append((pair[0].part, pair[0], pair[1]))
        else:
            _part(item, call)  # raises with the message for a value or another object
    if not any(isinstance(step, tuple) for step in steps):
        raise DslError(f"{call}: the chain holds no part between {first.name} and {last.name}")
    links: list[Link] = []
    created: list[Net] = []
    left_net: Net | None = first
    left: tuple[Part, PinHandle] | None = None
    for step in (*steps, last):
        if isinstance(step, Net):
            if left_net is not None:
                raise DslError(
                    f"{call}: nets {left_net.name} and {step.name} are next to each other; "
                    "that would join them"
                )
            assert left is not None
            links.append((step, left[1]))
            left_net, left = step, None
            continue
        part, entry, exit_ = step
        if left_net is not None:
            links.append((left_net, entry))
        else:
            assert left is not None
            joint = Net(f"{left[0].path}-{part.path}")
            created.append(joint)
            links += [(joint, left[1]), (joint, entry)]
        left_net, left = None, (part, exit_)
    _join(links, call)
    for item in chain[1:-1]:
        if isinstance(item, Part):
            item.two_terminal = True
    return tuple(created)


def decouple(
    rail: object,
    ground: object,
    *capacitors: Part,
    near: object = None,
    within: object = None,
    severity: str = "error",
) -> None:
    """Join each capacitor's ``a`` to ``rail`` and its ``b`` to ``ground``. With ``near`` and ``within``
    (given together, no default distance), each capacitor gets the placement rule
    ``design.near("decouple/<capacitor path>", capacitor, near, within=within, severity=severity)``."""
    call = "decouple()"
    rail = _net(rail, f"{call}: the rail")
    ground = _net(ground, f"{call}: the ground")
    if rail is ground or rail.name == ground.name:
        raise DslError(f"{call}: the rail and the ground are both {rail.name}")
    if not capacitors:
        raise DslError(f"{call}: give at least one capacitor")
    parts = [_part(capacitor, call) for capacitor in capacitors]
    if (near is None) != (within is None):
        raise DslError(f"{call}: near and within are given together or not at all")
    links: list[Link] = []
    for part in parts:
        first, second = _ends(part)
        links += [(rail, first), (ground, second)]
    if near is not None:
        designs: list[Design] = []
        for part in parts:
            design = part.design
            if design is None:
                raise DslError(f"{call}: add {part.ref} to a design before recording its placement rule")
            designs.append(design)
        saved = [(design, dict(design.near_rules)) for design in designs]
        try:
            for design, part in zip(designs, parts, strict=True):
                design.near(f"decouple/{part.path}", part, near, within=within, severity=severity)
            _join(links, call)
        except DslError:
            for design, rules in saved:
                design.near_rules.clear()
                design.near_rules.update(rules)
            raise
    else:
        _join(links, call)
    for part in parts:
        part.two_terminal = True


def _pull(target: object, rail: object, resistors: Sequence[object], call: str, what: str) -> None:
    signals: list[Net]
    if isinstance(target, Net):
        signals = [target]
    elif isinstance(target, I2C) or (isinstance(target, PortHandle) and target.kind == "i2c"):
        signals = [target.members["sda"], target.members["scl"]]
    elif isinstance(target, Interface | PortHandle) and target.kind == "logic":
        signals = [target.members["io"]]  # a Logic interface or a logic port (change c0252)
    elif isinstance(target, Interface | PortHandle):
        raise DslError(
            f"{call}: the target is a Net, an I2C bus or port, or a Logic line or port, not a {target.kind} "
            "interface or port"
        )
    else:
        raise DslError(f"{call}: the target is a Net, an I2C bus or port, or a Logic line, not {target!r}")
    other = _net(rail, f"{call}: the {what}")
    parts = [_part(resistor, call) for resistor in resistors]
    if len(parts) != len(signals):
        raise DslError(
            f"{call}: {len(signals)} net(s) to pull take {len(signals)} resistor(s), not {len(parts)}"
        )
    links: list[Link] = []
    for signal, part in zip(signals, parts, strict=True):
        if signal is other or signal.name == other.name:
            raise DslError(f"{call}: net {signal.name} is the {what} itself")
        first, second = _ends(part)
        links += [(signal, first), (other, second)]
    _join(links, call)
    for part in parts:
        part.two_terminal = True


def pull_up(target: object, rail: object, *resistors: Part) -> None:
    """Join each resistor's ``a`` to a net of ``target`` and its ``b`` to ``rail``. ``target`` is a ``Net``
    (one resistor), an ``I2C`` bus or ``i2c`` port (two resistors: the first on SDA, the second on SCL), or a
    ``Logic`` line or ``logic`` port (one resistor, change c0252); ``rail`` is a ``Net`` or a net-like
    ``Rail`` or power port."""
    _pull(target, rail, resistors, "pull_up()", "rail")


def pull_down(target: object, ground: object, *resistors: Part) -> None:
    """Join each resistor's ``a`` to a net of ``target`` and its ``b`` to ``ground``, as ``pull_up``."""
    _pull(target, ground, resistors, "pull_down()", "ground")


__all__ = ["decouple", "pull_down", "pull_up", "series"]
