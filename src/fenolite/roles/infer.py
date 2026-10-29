# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The inference of net roles and role groups (change c0222; capability net-roles, "Inference rules" and
"Currents are never inferred"; ``docs/roles.md``, "Inference rules").

The rules form a closed table, applied in order and deterministically. Each fired rule records its id, its
confidence (the lowest of its own and of the classes it read) and the pads it read:

| rule | fires when | gives |
|---|---|---|
| ``SW-1`` | a net joins a switch's source, another switch's drain and an inductor | ``switch_node``, high |
| ``SW-2`` | a net joins a switch's drain or source (or a diode) and an inductor | ``switch_node``, medium |
| ``SW-3`` | a net joins a driver's or a controller's switching-node pin | ``switch_node``, medium |
| ``HL-1`` | the capacitor across the far nets of a switch node's two switches | ``HotLoop`` |
| ``GD-1`` | a net joins a driver output and a gate, directly or through one resistor | ``gate``, high |
| ``GD-2`` | for each gate, the Kelvin source (or source) and the driver's pin on its net | ``GateLoop`` |
| ``KS-1`` | a shunt's sense pins reach an input pair, through at most two resistors a side | ``KelvinPair`` |
| ``GND-1`` | a ground name (``GND*``, ``*GND``, ``VSS*``, ``0V``), and the most ground pins | ``ground`` |
| ``PWR-1`` | a power interface or supply pin; a switch's or inductor's far net (*) | ``power``, medium |
| ``HV-1`` | a working voltage at or above ``high_voltage_mv``, never a name | ``high_voltage`` |
| ``SIG-0`` | no other rule | ``signal``, low |

(*) A switch at no switch node (the back-to-back pair of a battery protector) gives both its drain and its
source nets.

A later rule does not replace an earlier result of a confidence at least its own; two rules that give
different kinds at one confidence leave the first and add ``roles.ambiguous``. ``PWR-1`` does not fire on a
net that ``GND-1`` gave: the far net of a low-side switch is the ground it returns to. A result of ``low``
confidence (a rule that read a class found only from a reference prefix) is not given, so the net falls to
``SIG-0``. ``KS-1`` gives ``kelvin`` to the separate sense nets of the pair (not to the power nets of a
two-pad shunt), and it also forms the pair of a four-terminal shunt whose force pads, not its sense pads,
reach the input pair, so that the check reports the shared force pad.

Fenolite infers no current and no voltage: ``with_currents`` takes a role's current from the role, then
from a ``[[current]]`` row of the requirements file, then from ``--current NET=AMPS``.
"""

from __future__ import annotations

import fnmatch
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import cast

from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.model.circuit import Circuit, Component
from fenolite.model.rules import (
    Confidence,
    GateLoop,
    HotLoop,
    KelvinPair,
    NetRole,
    RoleKind,
    RoleSet,
)
from fenolite.roles.classify import CONFIDENCE_ORDER, Classified, lowest
from fenolite.roles.codes import issue

RULES = ("SW-1", "SW-2", "SW-3", "HL-1", "GD-1", "GD-2", "KS-1", "GND-1", "PWR-1", "HV-1", "SIG-0")
GROUND_PATTERNS = ("GND*", "*GND", "VSS*", "0V")
"""The ground names of ``GND-1``, matched without regard to letter case."""
GROUND_PINS = frozenset({"GND", "VSS", "AGND", "DGND", "PGND", "VEE", "V-", "0V"})
"""The names of the supply pins of the negative side, for the second clause of ``GND-1``."""
_UNSAFE = re.compile(r"[^A-Za-z0-9_.+-]")


@dataclass(frozen=True, slots=True)
class _Member:
    ref: str
    pin: str
    pad: str


@dataclass(frozen=True, slots=True)
class Inferred:
    """The inferred roles and groups (source ``inferred``), the pads each role read, and the issues of the
    inference (``roles.ambiguous``)."""

    roles: RoleSet
    pads: Mapping[str, tuple[str, ...]] = field(default_factory=lambda: {})
    issues: tuple[Issue, ...] = ()


def _level(text: str) -> Confidence:
    return cast(Confidence, text)


def group_name(prefix: str, text: str) -> str:
    """A group name of the copper key pattern: ``prefix`` and ``text`` with every other character as ``_``."""
    return f"{prefix}_{_UNSAFE.sub('_', text)}"


class _Topology:
    """The circuit as nets of members, with the classes of the parts."""

    def __init__(self, circuit: Circuit, classes: Mapping[str, Classified]) -> None:
        self.classes = classes
        self.components: dict[str, Component] = {c.ref: c for c in circuit.components}
        by_id = {c.id: c for c in circuit.components}
        self.nets: dict[str, list[_Member]] = {}
        self.net_of: dict[tuple[str, str], str] = {}
        for net in sorted(circuit.nets, key=lambda n: n.name):
            members: list[_Member] = []
            for ref in net.members:
                component = by_id.get(ref.component_id)
                if component is None:
                    continue
                members.append(
                    _Member(component.ref, ref.pin, f"{component.ref}-{component.pads_of(ref.pin)[0]}")
                )
                self.net_of[component.ref, ref.pin] = net.name
            self.nets[net.name] = sorted(members, key=lambda m: (m.ref, m.pin))
        self.power_nets = {
            member
            for interface in circuit.interfaces
            if interface.kind == "power"
            for role, member_id in interface.members.items()
            if role == "hv"
            for member in [next((n.name for n in circuit.nets if n.id == member_id), None)]
            if member is not None
        }

    def cls(self, ref: str) -> str:
        found = self.classes.get(ref)
        return found.cls if found is not None else "other"

    def confidence(self, ref: str) -> str:
        found = self.classes.get(ref)
        return found.confidence if found is not None else "low"

    def terminal(self, ref: str, name: str) -> tuple[str, ...]:
        found = self.classes.get(ref)
        return found.pins(name) if found is not None else ()

    def pad(self, ref: str, pin: str) -> str:
        component = self.components.get(ref)
        return f"{ref}-{component.pads_of(pin)[0] if component is not None else pin}"

    def net(self, ref: str, pin: str) -> str | None:
        return self.net_of.get((ref, pin))

    def on(self, net: str, ref: str, terminal: str) -> list[str]:
        """The pins of terminal ``terminal`` of part ``ref`` that lie on ``net``."""
        return [pin for pin in self.terminal(ref, terminal) if self.net(ref, pin) == net]

    def nets_of(self, ref: str, terminal: str) -> list[str]:
        found = [self.net(ref, pin) for pin in self.terminal(ref, terminal)]
        return sorted({net for net in found if net is not None})

    def two_pin_other(self, ref: str, net: str) -> str | None:
        """The net of the other pin of a two-pin part that has one pin on ``net``."""
        component = self.components.get(ref)
        if component is None:
            return None
        nets = [self.net(ref, pin.number) for pin in component.pins]
        if len(nets) != 2 or net not in nets:
            return None
        other = nets[1] if nets[0] == net else nets[0]
        return other

    def refs(self, net: str, cls: str | None = None) -> list[str]:
        return sorted({m.ref for m in self.nets.get(net, ()) if cls is None or self.cls(m.ref) == cls})


@dataclass(slots=True)
class _Pick:
    kind: RoleKind
    rule: str
    confidence: str
    pads: tuple[str, ...]


class _Table:
    """The roles given so far, with the conflict rule."""

    def __init__(self) -> None:
        self.picks: dict[str, _Pick] = {}
        self.issues: list[Issue] = []

    def offer(self, net: str, kind: RoleKind, rule: str, confidence: str, pads: Sequence[str]) -> None:
        if confidence == "low" and rule != "SIG-0":
            return
        made = _Pick(kind, rule, confidence, tuple(sorted(set(pads))))
        known = self.picks.get(net)
        if known is None:
            self.picks[net] = made
            return
        if CONFIDENCE_ORDER[confidence] > CONFIDENCE_ORDER[known.confidence]:
            self.picks[net] = made
            return
        if known.kind != kind and CONFIDENCE_ORDER[confidence] == CONFIDENCE_ORDER[known.confidence]:
            self.issues.append(
                issue(
                    "roles.ambiguous",
                    f"the net {net} is {known.kind} by {known.rule} and {kind} by {rule}, both of "
                    f"{confidence} confidence; it keeps {known.kind}",
                    where=net,
                    hint=f"confirm the role: fenolite roles PATH --set {net}=KIND",
                )
            )


def _switch_nodes(top: _Topology, table: _Table) -> None:
    for net, members in top.nets.items():
        refs = {m.ref for m in members}
        sources = [r for r in refs if top.cls(r) == "transistor" and top.on(net, r, "source")]
        drains = [r for r in refs if top.cls(r) == "transistor" and top.on(net, r, "drain")]
        diodes = [r for r in refs if top.cls(r) == "diode"]
        inductors = [r for r in refs if top.cls(r) == "inductor"]
        if inductors and any(s != d for s in sources for d in drains):
            pair = next((s, d) for s in sorted(sources) for d in sorted(drains) if s != d)
            used = [*pair, *inductors]
            pads = [m.pad for m in members if m.ref in used]
            table.offer(net, "switch_node", "SW-1", lowest("high", *(top.confidence(r) for r in used)), pads)
        if inductors and (sources or drains or diodes):
            used = [*sources, *drains, *diodes, *inductors]
            pads = [m.pad for m in members if m.ref in used]
            table.offer(
                net, "switch_node", "SW-2", lowest("medium", *(top.confidence(r) for r in used)), pads
            )
    for net, members in top.nets.items():
        hits = [
            m
            for m in members
            if top.cls(m.ref) in ("driver", "controller") and m.pin in top.terminal(m.ref, "sw")
        ]
        if hits:
            table.offer(
                net,
                "switch_node",
                "SW-3",
                lowest("medium", *(top.confidence(m.ref) for m in hits)),
                [m.pad for m in hits],
            )


def _far(top: _Topology, ref: str, terminal: str) -> str | None:
    nets = top.nets_of(ref, terminal)
    return nets[0] if len(nets) == 1 else None


def _hot_loops(
    top: _Topology, nodes: Sequence[str], confidence: Mapping[str, str], positions: Mapping[str, Point]
) -> list[HotLoop]:
    loops: list[HotLoop] = []
    for node in nodes:
        refs = top.refs(node)
        highs = [r for r in refs if top.cls(r) == "transistor" and top.on(node, r, "source")]
        lows = [r for r in refs if top.cls(r) == "transistor" and top.on(node, r, "drain") and r not in highs]
        diodes = [r for r in refs if top.cls(r) == "diode" and top.on(node, r, "cathode")]
        if not highs or not (lows or diodes):
            continue
        high = highs[0]
        drain_net = _far(top, high, "drain")
        if lows:
            low = lows[0]
            low_far = _far(top, low, "source")
            low_pads = [top.pad(low, top.on(node, low, "drain")[0])]
            if low_far is not None:
                low_pads.append(top.pad(low, top.on(low_far, low, "source")[0]))
        else:
            low = diodes[0]
            low_far = _far(top, low, "anode")
            low_pads = [top.pad(low, top.on(node, low, "cathode")[0])]
            if low_far is not None:
                low_pads.append(top.pad(low, top.on(low_far, low, "anode")[0]))
        if drain_net is None or low_far is None:
            continue
        high_pads = [
            top.pad(high, top.on(drain_net, high, "drain")[0]),
            top.pad(high, top.on(node, high, "source")[0]),
        ]
        # the far source net, or the far net of a shunt on it
        candidates: list[tuple[str, list[str]]] = [(low_far, [])]
        for shunt in top.refs(low_far, "shunt"):
            other = top.two_pin_other(shunt, low_far)
            if other is not None:
                component = top.components[shunt]
                pins = {top.net(shunt, p.number): p.number for p in component.pins}
                candidates.append((other, [top.pad(shunt, pins[low_far]), top.pad(shunt, pins[other])]))
        for return_net, through in candidates:
            caps = [
                c for c in top.refs(drain_net, "capacitor") if top.two_pin_other(c, drain_net) == return_net
            ]
            if not caps:
                continue

            def distance(cap: str, around: tuple[str, ...] = (*high_pads, *low_pads)) -> tuple[int, str]:
                spots = [positions.get(p) for p in around]
                pads = [top.pad(cap, pin.number) for pin in top.components[cap].pins]
                mine = [positions.get(p) for p in pads]
                if any(s is None for s in (*spots, *mine)):
                    return (0, cap)
                total = sum(
                    (a.x - b.x) ** 2 + (a.y - b.y) ** 2
                    for a in mine
                    if a is not None
                    for b in spots
                    if b is not None
                )
                return (total, cap)

            cap = min(caps, key=distance)
            pin_plus = next(p.number for p in top.components[cap].pins if top.net(cap, p.number) == drain_net)
            pin_minus = next(
                p.number for p in top.components[cap].pins if top.net(cap, p.number) == return_net
            )
            pads = (top.pad(cap, pin_plus), *high_pads, *low_pads, *through, top.pad(cap, pin_minus))
            used = [cap, high, low, *(p.rpartition("-")[0] for p in through)]
            level = lowest(confidence[node], *(top.confidence(r) for r in used))
            if level != "low":
                loops.append(HotLoop(group_name("hot", node), pads, "inferred", "HL-1", _level(level)))
            break
    return loops


def _gates(top: _Topology, table: _Table) -> list[GateLoop]:
    loops: list[GateLoop] = []
    for driver in sorted(r for r in top.components if top.cls(r) in ("driver", "controller")):
        for out_pin in top.terminal(driver, "drive"):
            out_net = top.net(driver, out_pin)
            if out_net is None:
                continue
            routes: list[tuple[str, tuple[str, ...], str]] = [(out_net, (), out_net)]
            for resistor in top.refs(out_net, "resistor"):
                other = top.two_pin_other(resistor, out_net)
                if other is not None and other != out_net:
                    pins = {top.net(resistor, p.number): p.number for p in top.components[resistor].pins}
                    routes.append(
                        (other, (top.pad(resistor, pins[out_net]), top.pad(resistor, pins[other])), resistor)
                    )
            for gate_net, through, via in routes:
                for switch in top.refs(gate_net, "transistor"):
                    gate_pins = top.on(gate_net, switch, "gate")
                    if not gate_pins:
                        continue
                    used = [driver, switch] + ([via] if through else [])
                    level = lowest("high", *(top.confidence(r) for r in used))
                    pads = [top.pad(driver, out_pin), top.pad(switch, gate_pins[0]), *through]
                    for net in {out_net, gate_net}:
                        table.offer(net, "gate", "GD-1", level, pads)
                    kelvin = top.terminal(switch, "kelvin_source")
                    source_pins = kelvin or top.terminal(switch, "source")
                    source_net = top.net(switch, source_pins[0]) if source_pins else None
                    if source_net is None:
                        continue
                    on_net = [
                        p.number
                        for p in top.components[driver].pins
                        if top.net(driver, p.number) == source_net
                    ]
                    preferred = [
                        p for p in on_net if p in (*top.terminal(driver, "ret"), *top.terminal(driver, "sw"))
                    ]
                    ret_pins = preferred or on_net
                    if not ret_pins or level == "low":
                        continue
                    loops.append(
                        GateLoop(
                            group_name("gate", switch),
                            top.pad(driver, out_pin),
                            top.pad(switch, gate_pins[0]),
                            top.pad(switch, source_pins[0]),
                            top.pad(driver, ret_pins[0]),
                            through,
                            "inferred",
                            "GD-2",
                            _level(level),
                        )
                    )
    unique: dict[str, GateLoop] = {}
    for loop in loops:
        unique.setdefault(loop.name, loop)
    return list(unique.values())


def _reach(
    top: _Topology, start: str, receiver: str, terminal: str
) -> tuple[str, list[str], list[str]] | None:
    """The pin of ``receiver``'s ``terminal`` reached from ``start`` through at most two resistors in series,
    with the nets crossed and the resistors used."""
    frontier: list[tuple[str, list[str], list[str]]] = [(start, [start], [])]
    for _ in range(3):
        nxt: list[tuple[str, list[str], list[str]]] = []
        for net, nets, used in frontier:
            pins = top.on(net, receiver, terminal)
            if pins:
                return pins[0], nets, used
            if len(used) == 2:
                continue
            for resistor in top.refs(net, "resistor"):
                other = top.two_pin_other(resistor, net)
                if other is not None and other not in nets:
                    nxt.append((other, [*nets, other], [*used, resistor]))
        frontier = nxt
    return None


def _kelvins(top: _Topology, table: _Table) -> list[KelvinPair]:
    pairs: list[KelvinPair] = []
    receivers = sorted(r for r in top.components if top.terminal(r, "in_p") and top.terminal(r, "in_n"))
    for shunt in sorted(r for r in top.components if top.cls(r) == "shunt"):
        sense = top.terminal(shunt, "sense")
        force = top.terminal(shunt, "force")
        if len(sense) != 2:
            continue
        for attempt in (sense, force):
            if len(attempt) != 2:
                continue
            nets = [top.net(shunt, pin) for pin in attempt]
            if None in nets:
                continue
            found = None
            for receiver in receivers:
                for order in ((0, 1), (1, 0)):
                    plus = _reach(top, nets[order[0]] or "", receiver, "in_p")
                    minus = _reach(top, nets[order[1]] or "", receiver, "in_n")
                    if plus is not None and minus is not None:
                        found = (receiver, order, plus, minus)
                        break
                if found is not None:
                    break
            if found is None:
                continue
            receiver, order, plus, minus = found
            used = [shunt, receiver, *plus[2], *minus[2]]
            level = lowest("high", *(top.confidence(r) for r in used))
            if attempt is force:
                level = lowest(level, "medium")
            if level == "low":
                break
            element = (top.pad(shunt, sense[order[0]]), top.pad(shunt, sense[order[1]]))
            if attempt is force:
                # the sense pads stay the element; the force pads, which reach the receiver, show the fault
                sense_pins = sorted(sense)
                element = (top.pad(shunt, sense_pins[0]), top.pad(shunt, sense_pins[1]))
            receiver_pads = (top.pad(receiver, plus[0]), top.pad(receiver, minus[0]))
            force_pads = tuple(top.pad(shunt, pin) for pin in force) if len(force) == 2 else ()
            pairs.append(
                KelvinPair(
                    group_name("kelvin", shunt),
                    element,
                    receiver_pads,
                    force_pads,
                    "inferred",
                    "KS-1",
                    _level(level),
                )
            )
            power = {top.net(shunt, pin) for pin in force} if force else set(nets)
            for net in {*plus[1], *minus[1]} - power:
                if net in top.nets:
                    table.offer(net, "kelvin", "KS-1", level, [*element, *receiver_pads])
            break
    return pairs


def _grounds(top: _Topology, table: _Table) -> None:
    counts: dict[str, int] = {}
    for net, members in top.nets.items():
        count = 0
        for m in members:
            component = top.components[m.ref]
            pin = next((p for p in component.pins if p.number == m.pin), None)
            if pin is not None and pin.etype == "power_in" and pin.name.strip().upper() in GROUND_PINS:
                count += 1
        if count:
            counts[net] = count
    most = max(counts.values(), default=0)
    for net, members in top.nets.items():
        named = any(fnmatch.fnmatchcase(net.upper(), pattern) for pattern in GROUND_PATTERNS)
        pins = most > 0 and counts.get(net) == most
        if named or pins:
            table.offer(
                net, "ground", "GND-1", "high" if named and pins else "medium", [m.pad for m in members]
            )


def _powers(top: _Topology, table: _Table, nodes: Sequence[str]) -> None:
    far: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        for ref in top.refs(node):
            if top.cls(ref) == "transistor":
                for terminal in ("drain", "source"):
                    for net in top.nets_of(ref, terminal):
                        if net != node:
                            far[net].append(ref)
            elif top.cls(ref) == "inductor":
                other = top.two_pin_other(ref, node)
                if other is not None and other != node:
                    far[other].append(ref)
    for ref in sorted(top.components):
        if top.cls(ref) != "transistor":
            continue
        own = [net for terminal in ("drain", "source") for net in top.nets_of(ref, terminal)]
        if own and not set(own) & set(nodes):  # a switch at no switch node: both its nets are power nets
            for net in own:
                far[net].append(ref)
    for net, members in top.nets.items():
        supply = [
            m
            for m in members
            for pin in top.components[m.ref].pins
            if pin.number == m.pin and pin.etype in ("power_in", "power_out")
        ]
        refs = far.get(net, [])
        known = table.picks.get(net)
        if known is not None and known.kind == "ground":
            continue  # a ground net carries the return current: PWR-1 does not contest GND-1
        if net in top.power_nets or supply or refs:
            levels = [top.confidence(r) for r in refs]
            level = "medium" if net in top.power_nets or supply else lowest("medium", *levels)
            pads = [m.pad for m in supply] + [m.pad for m in members if m.ref in refs]
            table.offer(net, "power", "PWR-1", level, pads)


def infer(
    circuit: Circuit,
    classes: Mapping[str, Classified],
    *,
    positions: Mapping[str, Point] | None = None,
    working_mv: Mapping[str, int] | None = None,
    high_voltage_mv: int | None = None,
) -> Inferred:
    """The inferred roles of every net of ``circuit`` and the inferred groups. ``positions`` are the pad
    positions of the board (``REF-PIN`` → point), used by ``HL-1`` to take the capacitor nearest the
    switches when several qualify; ``working_mv`` the working voltages the user stated, for ``HV-1``."""
    top = _Topology(circuit, classes)
    table = _Table()
    _switch_nodes(top, table)
    nodes = sorted(net for net, pick in table.picks.items() if pick.kind == "switch_node")
    loops = _hot_loops(top, nodes, {n: table.picks[n].confidence for n in nodes}, positions or {})
    gates = _gates(top, table)
    kelvins = _kelvins(top, table)
    _grounds(top, table)
    _powers(top, table, nodes)
    for net, value in sorted((working_mv or {}).items()):
        if high_voltage_mv is not None and value >= high_voltage_mv and net in top.nets:
            table.offer(net, "high_voltage", "HV-1", "high", [m.pad for m in top.nets[net]])
    for net in top.nets:
        table.offer(net, "signal", "SIG-0", "low", [])
    roles = tuple(
        NetRole(net, pick.kind, "inferred", pick.rule, _level(pick.confidence))
        for net, pick in sorted(table.picks.items())
    )
    pads = {net: pick.pads for net, pick in table.picks.items()}
    issues = tuple(dict.fromkeys(table.issues))
    return Inferred(
        RoleSet(nets=roles, loops=tuple(loops), kelvins=tuple(kelvins), gates=tuple(gates)), pads, issues
    )


def with_currents(
    roles: RoleSet,
    *,
    requirements_current: Mapping[str, int] | None = None,
    given: Mapping[str, int] | None = None,
) -> RoleSet:
    """``roles`` with each role's ``milliamps``: the role's own, then the ``[[current]]`` row of the
    requirements file (``requirements_current``, net → mA), then ``--current`` (``given``). Nothing is
    assumed: a role that none of them gives keeps ``None``."""
    rows = requirements_current or {}
    options = given or {}
    nets: list[NetRole] = []
    for role in roles.nets:
        milliamps = role.milliamps
        if milliamps is None:
            milliamps = rows.get(role.net, options.get(role.net))
        nets.append(replace(role, milliamps=milliamps) if milliamps != role.milliamps else role)
    return replace(roles, nets=tuple(nets))


__all__ = ["GROUND_PATTERNS", "RULES", "Inferred", "group_name", "infer", "with_currents"]
