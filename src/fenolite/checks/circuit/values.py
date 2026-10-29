# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The applied values of the contract judge (change c0253; capability electrical-contracts, "Applied values
from stated sources", "Conflicting sources" and "Part classes for contracts"; ``docs/contracts.md``).

Each net may get a voltage bound (a range against the design's ground) and a current bound (an upper bound
on the current any copper of the net carries), only from what the user stated, in this order: a rig
element, a c0252 rail (its voltage, the upper sum of its loads), a declared or confirmed net role
(``working_mv`` read as ``-v`` to ``+v``, ``milliamps``), then for the current a ``[[current]]`` row and
``--current`` when the command has them (they come in ``currents``), and a ground (0 V). An inferred role
gives nothing, and nothing is inferred. Sources of different kinds that do not overlap give
``circuit.value-conflict``; the first in the order is used.

Part classes come from the one classifier, ``fenolite.roles.classify``, which the command runs and passes
as ``classes``; without it a part takes the class the user states in the model, else none. No module of
``checks`` holds a table of reference prefixes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from fractions import Fraction

from fenolite.checks.circuit.rails import View, bounds
from fenolite.checks.codes import issue
from fenolite.core.errors import Issue
from fenolite.core.requirement_table import Bound, Source
from fenolite.model.circuit import Component
from fenolite.model.design import Design
from fenolite.model.library import DeviceDef
from fenolite.model.rules import ContractSet, RigSink, RigSupply, RoleSet

MILLI = Fraction(1, 1000)
STATED_ROLES: frozenset[str] = frozenset({"declared", "confirmed"})
"""The role sources that give a value: an inferred role carries none (c0222)."""


@dataclass(frozen=True, slots=True)
class Value:
    """A stated bound: ``low`` and ``high`` (``None``: unbounded), where it comes from, and the names of the
    rig supplies whose voltage it reads (for the corners)."""

    low: Fraction | None
    high: Fraction | None
    source: Source
    basis: str
    kind: str
    rigs: frozenset[str] = frozenset()

    def bound(self, unit: str) -> Bound:
        return Bound(unit, self.low, self.high)


@dataclass(slots=True)
class Values:
    """The bounds of the nets (by net id) and the findings of their resolution."""

    voltage: dict[str, Value] = field(default_factory=lambda: {})
    current: dict[str, Value] = field(default_factory=lambda: {})
    issues: list[Issue] = field(default_factory=lambda: [])


def _overlap(a: Value, b: Value) -> bool:
    if a.high is not None and b.low is not None and a.high < b.low:
        return False
    return not (b.high is not None and a.low is not None and b.high < a.low)


def ground_nets(design: Design) -> dict[str, tuple[Source, str]]:
    """The nets at 0 V: c0252 grounds (``user``) and declared or confirmed ``ground`` roles (``role``)."""
    circuit = design.circuit
    found: dict[str, tuple[Source, str]] = {}
    for interface in circuit.interfaces:
        if interface.kind == "ground" and "gnd" in interface.members:
            found.setdefault(interface.members["gnd"], ("user", f"ground {interface.name}"))
    roles = design.rules.roles if design.rules is not None else None
    names = {net.name: net.id for net in circuit.nets}
    for role in roles.nets if roles is not None else ():
        if role.kind == "ground" and role.source in STATED_ROLES and role.net in names:
            found.setdefault(names[role.net], ("role", f"{role.source} ground role of {role.net}"))
    return found


def resolve(
    design: Design,
    view: View,
    contracts: ContractSet | None,
    *,
    currents: Mapping[str, tuple[Fraction, str]] | None = None,
) -> Values:
    """The bounds of every net of ``design`` from its stated sources, in the order of the module docstring.
    ``view`` has its rails judged (``rails._rail_issues``); ``currents`` maps a net *name* to an upper bound
    in amperes and its basis (``requirements.toml``, a row's ``source`` text, ``--current``)."""
    found = Values()
    circuit = design.circuit
    names = {net.id: net.name for net in circuit.nets}
    roles: RoleSet | None = design.rules.roles if design.rules is not None else None
    stated = {
        role.net: role for role in (roles.nets if roles is not None else ()) if role.source in STATED_ROLES
    }
    rig = contracts.rig if contracts is not None else ()
    grounds = ground_nets(design)
    given = currents or {}
    for net_id in sorted(names, key=lambda key: names[key]):
        name = names[net_id]
        volts: list[Value] = []
        amps: list[Value] = []
        for element in rig:
            if isinstance(element, RigSupply) and element.pos == net_id:
                low, high = bounds(element.voltage)
                volts.append(
                    Value(low, high, "user", f"rig {element.name}", "rig", frozenset({element.name}))
                )
                if element.current is not None:
                    amps.append(Value(None, bounds(element.current)[1], "user", f"rig {element.name}", "rig"))
            if isinstance(element, RigSink) and element.net == net_id:
                amps.append(Value(None, bounds(element.current)[1], "user", f"rig {element.name}", "rig"))
        rail = view.rails.get(net_id)
        if rail is not None:
            label = f"rail {name}"
            if rail.voltage is not None:
                reads = frozenset(r.name for r in rail.rig_sources)
                volts.append(Value(rail.voltage[0], rail.voltage[1], "user", label, "rail", reads))
            if rail.load_high is not None:
                amps.append(Value(None, rail.load_high, "user", label, "rail"))
        role = stated.get(name)
        if role is not None:
            what = f"{role.source} {role.kind} role of {name}"
            if role.working_mv is not None:
                volt = Fraction(role.working_mv) * MILLI
                volts.append(Value(-volt, volt, "role", what, "role"))
            if role.milliamps is not None:
                amps.append(Value(None, Fraction(role.milliamps) * MILLI, "role", what, "role"))
        if name in given:
            amount, basis = given[name]
            amps.append(Value(None, amount, "user", basis, "requirements"))
        if net_id in grounds:
            source, basis = grounds[net_id]
            volts.append(Value(Fraction(0), Fraction(0), source, basis, "ground"))
        if volts:
            first = volts[0]
            found.voltage[net_id] = first
            for other in volts[1:]:
                if other.kind != first.kind and not _overlap(first, other):
                    found.issues.append(
                        issue(
                            "circuit.value-conflict",
                            f"{name}: {first.basis} gives {first.bound('volt').text()} and {other.basis} "
                            "gives "
                            f"{other.bound('volt').text()}; the first is used",
                            where=name,
                            hint="state one voltage for the net: correct the rail, the rig or the role",
                        )
                    )
        if amps:
            found.current[net_id] = amps[0]
    return found


# ------------------------------------------------------------------------------------------- pins


def function_nets(view: View, component: Component, device: DeviceDef) -> dict[str, str | None]:
    """The net of each function of ``device`` on ``component``: the one net its designators (the function
    name and its symbol pins) are on, ``None`` when they are on none or on two nets."""
    designators: dict[str, str] = {}
    for net in view.circuit.nets:
        for member in net.members:
            if member.component_id == component.id:
                designators[member.pin] = net.id
    found: dict[str, str | None] = {}
    for pin in device.pins:
        nets = {designators[d] for d in (pin.function, *pin.pins) if d in designators}
        found[pin.function] = next(iter(nets)) if len(nets) == 1 else None
    return found


def part_classes(design: Design, classes: Mapping[str, str] | None) -> dict[str, str | None]:
    """The class of each component id: the injected mapping of ``roles.classify``, else the class the user
    states in the model (``design.part_class``), else ``None``."""
    components = design.circuit.components
    if classes is not None:
        return {component.id: classes.get(component.id) for component in components}
    roles = design.rules.roles if design.rules is not None else None
    stated = {found.ref: found.cls for found in (roles.classes if roles is not None else ())}
    return {component.id: stated.get(component.ref) for component in components}


__all__ = [
    "MILLI",
    "STATED_ROLES",
    "Value",
    "Values",
    "function_nets",
    "ground_nets",
    "part_classes",
    "resolve",
]
