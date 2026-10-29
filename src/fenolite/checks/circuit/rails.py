# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rail, logic, bus, companion and port rules of the stage ``circuit.rules`` (change c0252;
``docs/cli-contract.md``, "Circuit stage").

The judge reads the model only: the parameters of interfaces and ports (exact c0246 ranges), their
directions and references, and the nets. There is no solver: a rail's voltage is the intersection of the
values set on it, loads are compared with sources, and every finding names its numbers, its ports and its
rail. A parameter that is not stated is reported as unjudged (``circuit.rail-unset``,
``circuit.logic-unknown``), never assumed.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction

from fenolite.checks.codes import issue
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level, min_level
from fenolite.core.quantities import PREFIXES, QuantityError, decimal_digits
from fenolite.core.quantities import parse as parse_quantity
from fenolite.core.requirement_table import Bound, RequirementRow, Side, Source
from fenolite.model.circuit import Circuit, Component, Interface, Port, ValueRange
from fenolite.model.design import Design
from fenolite.model.rules import RigSink, RigSupply

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-CIRCUIT-RULES",))
"""The evidence of a circuit finding before the device rows it judged lower it."""
SYMBOLS: Mapping[str, str] = {"volt": "V", "ampere": "A", "ohm": "Ω"}
LOGIC_KINDS: frozenset[str] = frozenset({"logic", "i2c", "spi", "uart", "usb2"})
SIGNAL_MEMBERS: frozenset[str] = frozenset({"vbus", "gnd"})
"""Members of a bus port that are no logic line."""
Bounds = tuple[Fraction | None, Fraction | None]


# ------------------------------------------------------------------------------------------- text


def amount(unit: str, value: Fraction) -> str:
    """One value in c0246's canonical text (``3.399V``, ``3mA``); a value that does not terminate is
    rounded to four significant digits after a ``~``."""
    size = abs(value)
    prefix, exponent = "", 0
    if size:
        prefix, exponent = PREFIXES[0]
        for name, power in PREFIXES:
            if size >= (Fraction(10) ** power):
                prefix, exponent = name, power
    scaled = size / (Fraction(10) ** exponent)
    sign = "-" if value < 0 else ""
    try:
        whole, part = decimal_digits(scaled, "a value")
        digits = f"{whole}{'.' + part if part else ''}"
    except QuantityError:
        digits = "~" + _rounded(scaled)
    return f"{sign}{digits}{prefix}{SYMBOLS.get(unit, '')}"


def _rounded(value: Fraction) -> str:
    """A positive ``value`` that does not terminate, rounded up to four significant digits, exactly."""
    exponent = 0
    while value * (Fraction(10) ** exponent) < 1000:
        exponent += 1
    while value * (Fraction(10) ** exponent) >= 10000:
        exponent -= 1
    whole = math.ceil(value * (Fraction(10) ** exponent))
    shown = Fraction(whole) / (Fraction(10) ** exponent)
    digits, part = decimal_digits(shown, "a value")
    return f"{digits}{'.' + part if part else ''}"


def span_text(unit: str, low: Fraction | None, high: Fraction | None, nominal: Fraction | None = None) -> str:
    """``3.201V..3.399V``, ``3.3V (3.201V..3.399V)`` with a nominal, ``1.3V..`` when unbounded above."""
    text = f"{'' if low is None else amount(unit, low)}..{'' if high is None else amount(unit, high)}"
    return text if nominal is None else f"{amount(unit, nominal)} ({text})"


def range_text(value: ValueRange) -> str:
    """The c0246 text of a model range."""
    return span_text(value.unit, _f(value.low), _f(value.high), _f(value.nominal))


def _f(value: object) -> Fraction | None:
    from fenolite.model.circuit import Decimal10

    return value.fraction() if isinstance(value, Decimal10) else None


def bounds(value: ValueRange) -> Bounds:
    return _f(value.low), _f(value.high)


def within(inner: Bounds, outer: Bounds) -> bool:
    """Whether every value of ``inner`` lies in ``outer`` (an unbounded side of ``outer`` holds all)."""
    if outer[0] is not None and (inner[0] is None or inner[0] < outer[0]):
        return False
    return outer[1] is None or (inner[1] is not None and inner[1] <= outer[1])


def threshold(value: ValueRange, key: str) -> Fraction | None:
    """The value of a threshold: the lower bound of a ``*_min``, the upper bound of any other key, falling
    back on the other bound for a one-sided range."""
    low, high = bounds(value)
    return (low if low is not None else high) if key.endswith("_min") else (high if high is not None else low)


def level_of(label: str) -> Level:
    """The ``Level`` of an evidence label of a device record."""
    for level in Level:
        if label == level.value:
            return level
    if label.startswith("ORACLE-VERIFIED("):
        return Level.ORACLE_VERIFIED
    if label.startswith("ALTIUM-VERIFIED(kit"):
        return Level.ALTIUM_VERIFIED_KIT
    if label.startswith("ALTIUM-VERIFIED(author-report"):
        return Level.ALTIUM_VERIFIED_AUTHOR_REPORT
    return Level.UNVERIFIED


# ------------------------------------------------------------------------------------------- view


@dataclass
class RailInfo:
    """One rail: the ``hv`` net of a ``power`` interface or port, and what is set and stated on it."""

    net: str
    interfaces: list[Interface] = field(default_factory=lambda: [])
    ports: list[Port] = field(default_factory=lambda: [])
    voltage: Bounds | None = None
    nominal: Fraction | None = None
    sources: list[Port] = field(default_factory=lambda: [])
    rig_sources: list[RigSupply] = field(default_factory=lambda: [])
    """The test-rig supplies on the rail (change c0253): sources, their ``current`` the capacity."""
    rig_loads: list[RigSink] = field(default_factory=lambda: [])
    """The test-rig sinks on the rail (change c0253): loads."""
    load_high: Fraction | None = None
    """The upper sum of the rail's loads (change c0253), ``None`` when no load states a bounded draw."""


class View:
    """The model as the rules read it: names, owners, rails and pull-ups."""

    def __init__(self, circuit: Circuit, rig: Sequence[RigSupply | RigSink] = ()) -> None:
        self.circuit = circuit
        self.rows: list[RequirementRow] = []
        """The requirement rows of the rail and logic rules (change c0253)."""
        self.nets = {net.id: net for net in circuit.nets}
        self.modules = {module.id: module for module in circuit.modules}
        self.components = {component.id: component for component in circuit.components}
        self.ports = {port.id: port for port in circuit.ports}
        self.interfaces = {interface.id: interface for interface in circuit.interfaces}
        self.rails: dict[str, RailInfo] = {}
        for interface in circuit.interfaces:
            hv = interface.members.get("hv")
            if interface.kind == "power" and hv is not None:
                self.rails.setdefault(hv, RailInfo(hv)).interfaces.append(interface)
        for port in circuit.ports:
            hv = port.members.get("hv")
            if port.kind == "power" and hv is not None:
                self.rails.setdefault(hv, RailInfo(hv)).ports.append(port)
        for element in rig:
            if isinstance(element, RigSupply) and element.pos in self.rails:
                self.rails[element.pos].rig_sources.append(element)
            elif isinstance(element, RigSink) and element.net in self.rails:
                self.rails[element.net].rig_loads.append(element)
        self.pins: dict[str, list[str]] = {}
        """Component id → the ids of the nets its pins are on, one entry per pin."""
        for net in circuit.nets:
            for member in net.members:
                self.pins.setdefault(member.component_id, []).append(net.id)

    def net_name(self, net_id: str) -> str:
        found = self.nets.get(net_id)
        return found.name if found is not None else net_id

    def label(self, port: Port) -> str:
        """``buck/VOUT`` for a block port, ``U3.vdd`` for a device port."""
        module = self.modules.get(port.owner)
        if module is not None:
            return f"{module.path}/{port.name}"
        component = self.components.get(port.owner)
        return f"{component.ref}.{port.name}" if component is not None else port.name

    def owner_path(self, port: Port) -> str:
        module = self.modules.get(port.owner)
        if module is not None:
            return module.path
        component = self.components.get(port.owner)
        if component is None:
            return ""
        return component.properties.get("fenolite.path") or component.path or component.ref

    def reference_net(self, reference: str | None) -> str | None:
        """The ``hv`` net of the rail a reference names (a power port or interface)."""
        if reference is None:
            return None
        target = self.ports.get(reference) or self.interfaces.get(reference)
        return None if target is None else target.members.get("hv")

    def pull_ups(self, net_id: str) -> list[tuple[Component, str]]:
        """The pull-ups of ``net_id``: components of exactly two pins, one on the net and the other on a
        rail, with that rail's net id."""
        found: list[tuple[Component, str]] = []
        for component in self.circuit.components:
            on = self.pins.get(component.id, [])
            count = len(component.pins) if component.pins else len(on)
            if count != 2 or len(on) != 2 or net_id not in on:
                continue
            other = on[1] if on[0] == net_id else on[0]
            if other != net_id and other in self.rails:
                found.append((component, other))
        return found


def _hidden(view: View, port: Port, peers: Sequence[Port]) -> bool:
    """Whether a block port on the same rail and of the same direction replaces ``port``: an ``out`` port of
    a block hides the ``out`` ports inside it, an ``in`` port that states ``current`` the ``in`` ports."""
    path = view.owner_path(port)
    for other in peers:
        if other is port or other.direction != port.direction or other.owner not in view.modules:
            continue
        if port.direction == "in" and "current" not in other.params:
            continue
        if path.startswith(view.modules[other.owner].path + "/"):
            return True
    return False


# ------------------------------------------------------------------------------------------ rules


def _limit(port: Port, value: ValueRange, kind: str) -> Side:
    """The limit side of a row from a port parameter: ``device`` with its label for a device port, else the
    user's (a block port or interface)."""
    source: Source = "device" if port.evidence else "user"
    return Side(
        Bound("volt" if value.unit == "volt" else value.unit, *bounds(value)),
        range_text(value),
        source,
        f"port {port.name}",
        port.evidence or "INFERRED",
        kind,  # type: ignore[arg-type]
    )


def _row(
    row_id: str,
    check: str,
    subject: str,
    quantity: str,
    unit: str,
    value: Side,
    limit: Side,
    passed: bool,
    entities: Sequence[str],
) -> RequirementRow:
    return RequirementRow(
        row_id,
        check,
        subject,
        quantity,
        unit,
        value,
        limit,
        "pass" if passed else "fail",
        None if passed else "error",
        tuple(entities),
    )


def _load_labels(view: View, loads: Sequence[Port], rail: RailInfo) -> list[str]:
    return [*(view.label(port) for port in loads), *(f"rig {element.name}" for element in rail.rig_loads)]


def _rail_issues(view: View) -> list[Issue]:
    found: list[Issue] = []
    for net_id in sorted(view.rails, key=view.net_name):
        rail = view.rails[net_id]
        name = view.net_name(net_id)
        visible = [port for port in rail.ports if not _hidden(view, port, rail.ports)]
        rail.sources = [port for port in visible if port.direction == "out"]
        setters: list[tuple[str, ValueRange]] = [
            (f"rail {interface.name}", interface.params["voltage"])
            for interface in rail.interfaces
            if "voltage" in interface.params
        ]
        setters += [
            (view.label(port), port.params["voltage"]) for port in rail.sources if "voltage" in port.params
        ]
        setters += [(f"rig {element.name}", element.voltage) for element in rail.rig_sources]
        if setters:
            lows = [bounds(value)[0] for _, value in setters]
            highs = [bounds(value)[1] for _, value in setters]
            low = max((v for v in lows if v is not None), default=None)
            high = min((v for v in highs if v is not None), default=None)
            if low is not None and high is not None and low > high:
                listed = "; ".join(f"{who} sets {range_text(value)}" for who, value in setters)
                found.append(
                    issue(
                        "circuit.rail-voltage", f"{name}: the set voltages do not meet: {listed}", where=name
                    )
                )
            else:
                rail.voltage = (low, high)
                rail.nominal = _f(setters[0][1].nominal) if len(setters) == 1 else None
        bounded = [port for port in rail.ports if port.direction != "out" and "voltage" in port.params]
        if rail.voltage is not None:
            shown = span_text("volt", *rail.voltage, rail.nominal)
            for port in bounded:
                accepted = port.params["voltage"]
                passed = within(rail.voltage, bounds(accepted))
                view.rows.append(
                    _row(
                        ":".join(("circuit.rail-voltage", view.label(port))),
                        "circuit.rail-voltage",
                        view.label(port),
                        "voltage",
                        "volt",
                        Side(Bound("volt", *rail.voltage), shown, "user", f"rail {name}"),
                        _limit(port, accepted, "operating"),
                        passed,
                        (net_id, port.owner),
                    )
                )
                if not passed:
                    found.append(
                        issue(
                            "circuit.rail-voltage",
                            f"{view.label(port)} accepts {range_text(accepted)}; {name} is {shown}",
                            where=view.label(port),
                            hint="change the rail's voltage or the part, or power the port from another rail",
                        )
                    )
        elif bounded:
            needing = ", ".join(view.label(port) for port in bounded)
            found.append(
                issue(
                    "circuit.rail-unset",
                    f"{name}: no voltage is set; {needing} need"
                    f"{'s' if len(bounded) == 1 else ''} one to be judged",
                    where=name,
                    hint="give the rail a voltage (design.rail(..., voltage=...)) or its source port one",
                )
            )
        loads = [port for port in visible if port.direction == "in" and "current" in port.params]
        sources = [port for port in rail.sources if "current" in port.params]
        rig_capacity = [element for element in rail.rig_sources if element.current is not None]
        if loads or rail.rig_loads:
            draws = [bounds(port.params["current"])[1] for port in loads]
            draws += [bounds(element.current)[1] for element in rail.rig_loads]
            if all(value is not None for value in draws):
                rail.load_high = sum((v for v in draws if v is not None), Fraction(0))
        if (loads or rail.rig_loads) and not sources and not rig_capacity:
            found.append(
                issue(
                    "circuit.rail-unset",
                    f"{name}: loads state a draw "
                    f"({', '.join(_load_labels(view, loads, rail))})"
                    " and no source states a capacity",
                    where=name,
                )
            )
        elif loads or rail.rig_loads:
            highs = [bounds(port.params["current"])[1] for port in loads]
            capacity = sum(
                (bounds(port.params["current"])[0] or Fraction(0) for port in sources), Fraction(0)
            )
            capacity += sum(
                (bounds(element.current)[0] or Fraction(0) for element in rig_capacity if element.current),
                Fraction(0),
            )
            supplying = [*(view.label(p) for p in sources), *(f"rig {r.name}" for r in rig_capacity)]
            if any(value is None for value in highs):
                unbounded = ", ".join(view.label(p) for p, v in zip(loads, highs, strict=True) if v is None)
                found.append(
                    issue(
                        "circuit.rail-unset",
                        f"{name}: the draw of {unbounded} has no upper bound",
                        where=name,
                    )
                )
            elif rail.load_high is not None:
                draw = rail.load_high
                view.rows.append(
                    _row(
                        ":".join(("circuit.rail-current", name)),
                        "circuit.rail-current",
                        f"rail {name}",
                        "current",
                        "ampere",
                        Side(
                            Bound("ampere", None, draw),
                            f"..{amount('ampere', draw)}",
                            "user",
                            f"loads of {name}",
                        ),
                        Side(
                            Bound("ampere", None, capacity),
                            f"..{amount('ampere', capacity)}",
                            "device" if any(p.evidence for p in sources) else "user",
                            f"sources {', '.join(supplying)}",
                            min((p.evidence for p in sources if p.evidence), default="INFERRED"),
                            "requirement",
                        ),
                        draw <= capacity,
                        (net_id,),
                    )
                )
                if draw > capacity:
                    found.append(
                        issue(
                            "circuit.rail-current",
                            f"{name}: loads up to {amount('ampere', draw)} exceed sources "
                            f"{amount('ampere', capacity)} ({', '.join(supplying)})",
                            where=name,
                            hint="lower the loads, or choose a source of more current",
                        )
                    )
        drivers = rail.sources
        shared = any(interface.shared for interface in rail.interfaces)
        count = len(drivers) + len(rail.rig_sources)
        if count >= 2 and not shared and not (all(port.share for port in drivers) and not rail.rig_sources):
            labels = [view.label(port) for port in drivers] + [f"rig {r.name}" for r in rail.rig_sources]
            found.append(
                issue(
                    "circuit.rail-sources",
                    f"{' and '.join(labels)} both drive {name}"
                    if len(labels) == 2
                    else f"{', '.join(labels)} all drive {name}",
                    where=name,
                    hint="declare the rail shared (design.rail(..., shared=True)) if the sources share it",
                )
            )
    return found


@dataclass(frozen=True)
class Line:
    """A port on one net: the port, its member and its reference rail's net."""

    port: Port
    member: str
    reference: str | None


def _lines(view: View) -> dict[str, list[Line]]:
    found: dict[str, list[Line]] = {}
    for port in view.circuit.ports:
        if port.kind not in LOGIC_KINDS:
            continue
        reference = view.reference_net(port.reference)
        for member, net_id in port.members.items():
            if member not in SIGNAL_MEMBERS:
                found.setdefault(net_id, []).append(Line(port, member, reference))
    return found


def _rail_high(view: View, net_id: str | None) -> Fraction | None:
    rail = view.rails.get(net_id) if net_id is not None else None
    return None if rail is None or rail.voltage is None else rail.voltage[1]


@dataclass(frozen=True)
class Driver:
    """What drives a logic line: its label, its stated output levels and its reference rail."""

    label: str
    output_high_min: Fraction | None
    output_low_max: Fraction | None
    rail_high: Fraction | None
    rail_name: str
    comparisons: tuple[str, ...] = ("high", "low", "withstand")


def _compare(view: View, driver: Driver, reader: Line, net: str) -> list[Issue]:
    """The comparisons of ``driver`` with ``reader``, each worst case: high (``output_high_min`` against
    ``input_high_min``), low (``output_low_max`` against ``input_low_max``) and withstand (the driver's rail
    against the reader's ``abs_max``); one ``circuit.logic-unknown`` names every missing value."""
    params = reader.port.params
    target = view.label(reader.port)
    missing: list[str] = []
    found: list[Issue] = []
    rows = {
        "high": (driver.output_high_min, "output_high_min", "input_high_min"),
        "low": (driver.output_low_max, "output_low_max", "input_low_max"),
        "withstand": (driver.rail_high, "reference rail voltage", "abs_max"),
    }
    for which in driver.comparisons:
        mine, own, their = rows[which]
        if mine is None:
            missing.append(f"{driver.label} {own}")
        limit = params.get(their)
        if limit is None:
            missing.append(f"{target} {their}")
        if mine is None or limit is None:
            continue
        low, high = bounds(limit)
        if which == "high":
            theirs = threshold(limit, their)
            failed = theirs is not None and mine < theirs
            shown = "?" if theirs is None else amount("volt", theirs)
            text = f"output high {amount('volt', mine)} is below input high {shown}"
        elif which == "low":
            theirs = threshold(limit, their)
            failed = theirs is not None and mine > theirs
            shown = "?" if theirs is None else amount("volt", theirs)
            text = f"output low {amount('volt', mine)} is above input low {shown}"
        else:
            theirs = high if high is not None else low
            failed = high is not None and mine > high
            text = (
                f"its rail {driver.rail_name} reaches {amount('volt', mine)}, above the "
                f"{'?' if theirs is None else amount('volt', theirs)} that {target} withstands (abs_max)"
            )
        if failed:
            found.append(
                issue(
                    "circuit.logic-level",
                    f"{driver.label} drives {target} on {net}: {text}",
                    where=target,
                    hint="add a level shifter, or move both ports to one reference rail",
                )
            )
    if missing:
        found.append(
            issue(
                "circuit.logic-unknown",
                f"{driver.label} drives {target} on {net} across rails; not stated: {', '.join(missing)}",
                where=target,
                hint="state the threshold on the port or the device record (its datasheet value)",
            )
        )
    return found


def _level(port: Port, key: str) -> Fraction | None:
    found = port.params.get(key)
    return None if found is None else threshold(found, key)


def _logic_issues(view: View) -> list[Issue]:
    found: list[Issue] = []
    for net_id, lines in sorted(_lines(view).items(), key=lambda item: view.net_name(item[0])):
        net = view.net_name(net_id)
        i2c = [line for line in lines if line.port.kind == "i2c"]
        other = [line for line in lines if line.port.kind != "i2c"]
        for line in other:
            port = line.port
            if port.direction == "in":
                continue
            if port.direction == "inout" and not ({"output_high_min", "output_low_max"} & set(port.params)):
                continue
            driver = Driver(
                view.label(port),
                _level(port, "output_high_min"),
                _level(port, "output_low_max"),
                _rail_high(view, line.reference),
                view.net_name(line.reference) if line.reference is not None else "(no reference)",
            )
            for reader in other:
                if reader.port is port or reader.port.direction == "out":
                    continue
                if line.reference is not None and line.reference == reader.reference:
                    continue
                found += _compare(view, driver, reader, net)
        if not i2c:
            continue
        for component, rail_net in view.pull_ups(net_id):
            rail = view.rails[rail_net]
            if rail.voltage is None:
                continue
            driver = Driver(
                f"the pull-up {component.ref} to {view.net_name(rail_net)}",
                rail.voltage[0],
                None,
                rail.voltage[1],
                view.net_name(rail_net),
                ("high", "withstand"),
            )
            for reader in i2c:
                if reader.reference != rail_net:
                    found += _compare(view, driver, reader, net)
        for line in i2c:
            if "output_low_max" not in line.port.params:
                continue
            driver = Driver(
                view.label(line.port), None, _level(line.port, "output_low_max"), None, "", ("low",)
            )
            for reader in i2c:
                if reader.port is line.port or (
                    line.reference is not None and line.reference == reader.reference
                ):
                    continue
                found += _compare(view, driver, reader, net)
    return found


def _resistance(component: Component) -> Bounds | None:
    value = component.value_range
    if value is not None and value.unit == "ohm":
        return bounds(value)
    try:
        exact = parse_quantity("ohm", component.value)
    except QuantityError:
        return None
    return exact, exact


def _i2c_nets(view: View) -> dict[str, tuple[list[Interface], list[Port]]]:
    found: dict[str, tuple[list[Interface], list[Port]]] = {}
    for interface in view.circuit.interfaces:
        if interface.kind == "i2c":
            for member in ("sda", "scl"):
                if member in interface.members:
                    found.setdefault(interface.members[member], ([], []))[0].append(interface)
    for port in view.circuit.ports:
        if port.kind == "i2c":
            for member in ("sda", "scl"):
                if member in port.members:
                    found.setdefault(port.members[member], ([], []))[1].append(port)
    return found


def _bus_issues(view: View) -> list[Issue]:
    found: list[Issue] = []
    for net_id, (interfaces, ports) in sorted(
        _i2c_nets(view).items(), key=lambda item: view.net_name(item[0])
    ):
        line = view.net_name(net_id)
        references: set[str | None] = {view.reference_net(i.reference) for i in interfaces if i.reference}
        if not references:
            port_references: set[str | None] = {view.reference_net(p.reference) for p in ports}
            references = port_references if len(port_references) == 1 else set()
        references.discard(None)
        reference = next(iter(references)) if len(references) == 1 else None
        accepted: Bounds | None = None
        for holder in (*interfaces, *ports):
            if "pullup" in holder.params:
                low, high = bounds(holder.params["pullup"])
                if accepted is None:
                    accepted = (low, high)
                else:
                    lows = [v for v in (accepted[0], low) if v is not None]
                    highs = [v for v in (accepted[1], high) if v is not None]
                    accepted = (max(lows, default=None), min(highs, default=None))
        for component, rail_net in view.pull_ups(net_id):
            rail_name = view.net_name(rail_net)
            if reference is not None and rail_net != reference:
                found.append(
                    issue(
                        "circuit.bus-pullup",
                        f"{line} pulled up to {rail_name} by {component.ref}; bus reference is "
                        f"{view.net_name(reference)}",
                        where=component.ref,
                        hint="pull the bus up to its reference rail, or set the bus reference",
                    )
                )
            resistance = _resistance(component)
            if resistance is None:
                continue
            if accepted is not None and not within(resistance, accepted):
                found.append(
                    issue(
                        "circuit.bus-pullup",
                        f"{line}: the pull-up {component.ref} of {span_text('ohm', *resistance)} is outside "
                        "the "
                        f"accepted {span_text('ohm', *accepted)}",
                        where=component.ref,
                    )
                )
            rail = view.rails[rail_net]
            if rail.voltage is None or rail.voltage[1] is None or not resistance[0]:
                continue
            current = rail.voltage[1] / resistance[0]
            for port in ports:
                limit = port.params.get("output_current_max")
                value = None if limit is None else threshold(limit, "output_current_max")
                if value is not None and current > value:
                    found.append(
                        issue(
                            "circuit.bus-pullup",
                            f"{line}: the pull-up {component.ref} to {rail_name} gives up to "
                            f"{amount('ampere', current)}, more than {view.label(port)} sinks "
                            f"({amount('ampere', value)}, output_current_max)",
                            where=component.ref,
                            hint="choose a larger pull-up resistance",
                        )
                    )
    return found


def _requires_issues(view: View) -> list[Issue]:
    found: list[Issue] = []
    for port in view.circuit.ports:
        label = view.label(port)
        for entry in port.requires:
            missing = ""
            if entry == "pullup":
                lines = ("sda", "scl") if port.kind == "i2c" else ("io",)
                lacking = [
                    view.net_name(port.members[m])
                    for m in lines
                    if m in port.members and not view.pull_ups(port.members[m])
                ]
                missing = f"no pull-up on {', '.join(lacking)}" if lacking else ""
            elif entry == "supply":
                target = (
                    port.members.get("hv") if port.kind == "power" else view.reference_net(port.reference)
                )
                if target is None and (port.kind == "power" or port.reference is None):
                    missing = "no reference rail" if port.kind != "power" else ""
                elif target is not None:
                    rail = view.rails.get(target)
                    if rail is None or rail.voltage is None or not rail.sources:
                        missing = f"{view.net_name(target)} has no set voltage and source"
            elif entry == "chip_select":
                lacking = [
                    view.net_name(net_id)
                    for member, net_id in sorted(port.members.items())
                    if member.startswith("cs")
                    and sum(len(n.members) for n in view.circuit.nets if n.id == net_id) < 2
                ]
                missing = f"chip select {', '.join(lacking)} goes nowhere" if lacking else ""
            if missing:
                found.append(
                    issue(
                        "circuit.requires-missing",
                        f"{label} requires {entry}: {missing}",
                        where=label,
                        hint="connect the companion, or remove it from requires if the board needs none",
                    )
                )
    return found


def _split_issues(view: View) -> list[Issue]:
    found: list[Issue] = []
    for port in view.circuit.ports:
        component = view.components.get(port.owner)
        owner = component.ref if component is not None else view.owner_path(port)
        for member, net_ids in sorted(port.split.items()):
            names = ", ".join(view.net_name(net_id) for net_id in net_ids)
            found.append(
                issue(
                    "circuit.port-split",
                    f"{owner}: the member {member} of the port {port.name} is on the nets {names}; its "
                    "parameters are not judged",
                    where=view.label(port),
                    hint="join the pins of the member, or accept the split",
                )
            )
    return found


def has_parameters(design: Design) -> bool:
    """Whether the model holds anything this stage judges: a param, a ``ground`` or ``logic`` interface, a
    port or a ``requires``."""
    circuit = design.circuit
    return bool(
        circuit.ports
        or any(i.params or i.kind in ("ground", "logic") or i.reference for i in circuit.interfaces)
    )


def circuit_evidence(design: Design) -> Evidence:
    """``INFERRED``, lowered to the lowest evidence label of the device ports that state a parameter."""
    labels: Iterable[str] = {
        p.evidence for p in design.circuit.ports if p.evidence and (p.params or p.requires)
    }
    levels = [level_of(label) for label in labels]
    return Evidence(min_level(Level.INFERRED, *levels), hypotheses=EVIDENCE.hypotheses)


def rail_counts(design: Design) -> dict[str, int]:
    """The rails of ``design`` and how many of them have a voltage to judge against."""
    view = View(design.circuit)
    _rail_issues(view)
    return {
        "rails": len(view.rails),
        "judged": sum(1 for rail in view.rails.values() if rail.voltage is not None),
    }


__all__ = [
    "EVIDENCE",
    "amount",
    "circuit_evidence",
    "has_parameters",
    "level_of",
    "rail_counts",
    "range_text",
    "span_text",
]
