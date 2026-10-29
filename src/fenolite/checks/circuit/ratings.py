# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ratings and operating checks of the contract judge (change c0253; capability electrical-contracts,
"Absolute and operating limits", "Voltage ratings", "Pin-pair limits", "Device current by class", "Resistor
power", "Temperature ratings", "Derating policy" and "Ratings without a policy"; ``docs/contracts.md``).

A device part is judged when the command gave its record (``devices``, by device id). Each limit is either
``abs_max`` (a rating: the worst case of the applied value against the limit, derated by the user's policy,
``circuit.rating-*``) or ``operating`` (the range the part needs: the applied range within it, exactly, never
derated, ``circuit.operating-range``). A rating or operating row has no ``unsure``: the worst case decides,
and a row whose input is not stated is ``unknown``. Fenolite ships no derating value: without a rule, a
rating is judged at 100 % with source ``device``.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction

from fenolite.checks.circuit.rails import View, bounds
from fenolite.checks.circuit.values import Value, Values, function_nets
from fenolite.core.requirement_table import Bound, LimitKind, Side, Status, amount_text
from fenolite.model.circuit import Component, Port
from fenolite.model.library import DeviceDef, Rating
from fenolite.model.rules import DERATING_KEYS, ContractSet, DeratingRule

DEVICE_PROPERTY = "fenolite.device"
"""The property that names the device of a built component (change c0248)."""
PATH_PROPERTY = "fenolite.path"
SCALE: Mapping[str, tuple[str, Fraction]] = {
    "uV": ("volt", Fraction(1, 10**6)),
    "uA": ("ampere", Fraction(1, 10**6)),
    "uW": ("watt", Fraction(1, 10**6)),
    "mK": ("kelvin", Fraction(1, 1000)),
}
"""The integer unit of a rating → its unit name and the value of one integer unit in it."""
CODES: Mapping[str, str] = {
    "voltage": "circuit.rating-voltage",
    "current": "circuit.rating-current",
    "power": "circuit.rating-power",
    "temperature": "circuit.rating-temperature",
}
SERIES: frozenset[str] = frozenset({"inductor", "shunt"})
"""The classes whose device current is the series current of their two nets."""
POWERED: frozenset[str] = frozenset({"resistor", "shunt"})
"""The classes whose device power is judged."""


@dataclass(frozen=True, slots=True)
class Judged:
    """A row of the judge before the stage adds its corners and its severity: the row's fields, the rig
    supplies its value reads, and what the issue says."""

    id: str
    check: str
    subject: str
    quantity: str
    unit: str
    value: Side | None
    limit: Side
    status: Status
    entities: tuple[str, ...]
    part: str = ""
    """The reference of the part the row judges, for the counts."""
    missing: str = ""
    rigs: frozenset[str] = frozenset()
    text: str = ""
    """The sentence of the finding a failing row gives (without its corners)."""
    policy: bool = False
    """Whether the row is an ``abs_max`` limit judged without a derating rule (``circuit.policy-missing``)."""
    no_rating: bool = False
    """Whether the row is a check that applies to a part whose record has no limit for it."""
    device_evidence: str = ""
    corners: tuple[tuple[str, Status, str], ...] = field(default=())


def to_unit(rating: Rating) -> tuple[str, Fraction | None, Fraction | None]:
    """A rating's unit name and bounds as exact values in it."""
    unit, scale = SCALE[rating.unit]
    low = None if rating.min is None else Fraction(rating.min) * scale
    high = None if rating.max is None else Fraction(rating.max) * scale
    return unit, low, high


def compare(
    value: tuple[Fraction | None, Fraction | None], limit: tuple[Fraction | None, Fraction | None]
) -> Status:
    """``pass`` when every value of ``value`` lies within ``limit``, ``fail`` when some does not, and
    ``unknown`` when a side the limit bounds is unbounded in ``value``."""
    low, high = value
    lower, upper = limit
    if (lower is not None and low is None) or (upper is not None and high is None):
        return "unknown"
    if lower is not None and low is not None and low < lower:
        return "fail"
    if upper is not None and high is not None and high > upper:
        return "fail"
    return "pass"


def _glob_matches(rule: DeratingRule, ref: str) -> bool:
    return bool(rule.parts) and fnmatch.fnmatchcase(ref, rule.parts)


def derating_rule(
    contracts: ContractSet | None, *, scope: str, key: str, cls: str | None, ref: str
) -> DeratingRule | None:
    """The rule that governs a rating: a part-scoped rule first, then a class key, then a generic key; the
    first of a level in call order (the DSL refuses two that match one part)."""
    rules = contracts.derating if contracts is not None else ()

    def applies(rule: DeratingRule) -> bool:
        where, rating, owner = DERATING_KEYS[rule.key]
        return where == scope and rating == key and (not owner or owner == cls)

    for level in (
        lambda r: _glob_matches(r, ref) and applies(r),
        lambda r: not r.parts and applies(r) and bool(DERATING_KEYS[r.key][2]),
        lambda r: not r.parts and applies(r) and not DERATING_KEYS[r.key][2],
    ):
        found = next((rule for rule in rules if level(rule)), None)
        if found is not None:
            return found
    return None


@dataclass(slots=True)
class Part:
    """A device part being judged: its component, record, class, function nets and labels."""

    component: Component
    device: DeviceDef
    cls: str | None
    nets: dict[str, str | None]
    ref: str
    subject: str


class RatingJudge:
    """The rating and operating rows of the device parts of one model."""

    def __init__(
        self,
        view: View,
        values: Values,
        contracts: ContractSet | None,
        ground: str | None,
        ports: Sequence[Port],
    ) -> None:
        self.view = view
        self.values = values
        self.contracts = contracts
        self.ground = ground
        self.ports = ports
        self.rows: list[Judged] = []

    # ------------------------------------------------------------------------------------ helpers

    def _voltage(self, net: str | None) -> Value | None:
        if net is None:
            return None
        return self.values.voltage.get(net)

    def _name(self, net: str | None) -> str:
        return "(no net)" if net is None else self.view.net_name(net)

    def _limit(
        self, part: Part, rating: Rating, scope: str, label: str
    ) -> tuple[tuple[Fraction | None, Fraction | None], Side, bool]:
        """The limit of ``rating`` (derated for an ``abs_max`` rating with a rule), its side and whether it is
        judged without a rule."""
        unit, low, high = to_unit(rating)
        device = part.device
        basis = f"{device.id} {label} {rating.limit}"
        kind: LimitKind = rating.limit
        if rating.limit == "operating":
            side = Side(
                Bound(unit, low, high), Bound(unit, low, high).text(), "device", basis, device.evidence, kind
            )
            return (low, high), side, False
        rule = derating_rule(self.contracts, scope=scope, key=rating.key, cls=part.cls, ref=part.ref)
        if rule is None:
            side = Side(
                Bound(unit, low, high), Bound(unit, low, high).text(), "device", basis, device.evidence, kind
            )
            return (low, high), side, True
        if rating.key == "temperature":
            margin = Fraction(rule.margin_mk, 1000)
            new_low = None if low is None else low + margin
            new_high = None if high is None else high - margin
            what = f"temperature_margin {amount_text('ratio', margin)}K of {Bound(unit, low, high).text()}"
        else:
            share = Fraction(rule.permille, 1000)
            new_low = None if low is None else low * share
            new_high = None if high is None else high * share
            rated = (
                amount_text(unit, high) if high is not None and low is None else Bound(unit, low, high).text()
            )
            what = f"{rule.key} {rule.permille}‰ of {rated}"
        basis = f"{what} (device {device.id})" + (f"; {rule.source}" if rule.source else "")
        bound = Bound(unit, new_low, new_high)
        return (new_low, new_high), Side(bound, bound.text(), "policy", basis, device.evidence, kind), False

    def _add(
        self,
        part: Part,
        *,
        key: str,
        label: str,
        rating: Rating,
        scope: str,
        quantity: str,
        value: tuple[Fraction | None, Fraction | None] | None,
        value_basis: str,
        value_source: str,
        missing: str,
        rigs: frozenset[str],
        entities: Sequence[str],
        what: str,
    ) -> None:
        limit_range, limit_side, no_policy = self._limit(part, rating, scope, label)
        unit = SCALE[rating.unit][0]
        code = CODES[rating.key] if rating.limit == "abs_max" else "circuit.operating-range"
        row_id = f"{code}:{part.ref}:{key}"
        if rating.limit == "operating" and key not in CODES:
            row_id = f"{code}:{part.ref}:{key}:{rating.key}"
        if value is None:
            status: Status = "unknown"
            side = None
        else:
            status = compare(value, limit_range)
            if status == "unknown" and not missing:
                missing = f"an unbounded {quantity}"
            bound = Bound(unit, *value) if value[0] is not None or value[1] is not None else None
            side = (
                None if bound is None else Side(bound, bound.text(), value_source, value_basis)  # type: ignore[arg-type]
            )
        verb = "exceeds the" if rating.limit == "abs_max" else "is not within the operating range"
        text = (
            f"{part.subject}: {what} {'' if side is None else side.text} ({value_basis}) {verb} "
            f"{limit_side.text} ({limit_side.basis})"
        )
        self.rows.append(
            Judged(
                row_id,
                code,
                f"{part.subject} {label}".strip(),
                quantity,
                unit,
                side,
                limit_side,
                status,
                (part.component.id, *entities),
                part.ref,
                missing if status == "unknown" else "",
                rigs if status != "unknown" else frozenset(),
                text,
                policy=no_policy and rating.limit == "abs_max",
                device_evidence=part.device.evidence,
            )
        )

    def _no_rating(self, part: Part, key: str, quantity: str, unit: str, entities: Sequence[str]) -> None:
        code = CODES[key]
        self.rows.append(
            Judged(
                f"{code}:{part.ref}:{key}",
                code,
                part.subject,
                quantity,
                unit,
                None,
                Side(None, "", "device", f"{part.device.id}: no rating", part.device.evidence, "abs_max"),
                "unknown",
                (part.component.id, *entities),
                part.ref,
                "no rating",
                no_rating=True,
                device_evidence=part.device.evidence,
            )
        )

    @staticmethod
    def _merge(*values: Value | None) -> tuple[str, str, frozenset[str]]:
        known = [v for v in values if v is not None]
        source = "user" if any(v.source == "user" for v in known) else (known[0].source if known else "user")
        basis = "; ".join(dict.fromkeys(v.basis for v in known))
        rigs = frozenset().union(*(v.rigs for v in known)) if known else frozenset()
        return source, basis, rigs

    def _difference(
        self, first: str | None, second: str | None
    ) -> tuple[tuple[Fraction | None, Fraction | None] | None, str, str, frozenset[str], str]:
        """``V(first) - V(second)`` worst case, with source, basis, rigs and what is missing."""
        a, b = self._voltage(first), self._voltage(second)
        if a is None or b is None:
            lacking = [self._name(net) for net, v in ((first, a), (second, b)) if v is None]
            return None, "", "user", frozenset(), "voltage of " + " and ".join(lacking)
        low = None if a.low is None or b.high is None else a.low - b.high
        high = None if a.high is None or b.low is None else a.high - b.low
        source, basis, rigs = self._merge(a, b)
        return (low, high), basis, source, rigs, ""

    # --------------------------------------------------------------------------------------- rows

    def judge(self, part: Part) -> None:
        device = part.device
        functions = [pin.function for pin in device.pins]
        ends = device.ends if len(device.ends) == 2 else (tuple(functions) if len(functions) == 2 else ())
        two_pin = len(ends) == 2
        end_nets = tuple(part.nets.get(f) for f in ends) if two_pin else ()
        across = None
        if two_pin:
            a, b = self._voltage(end_nets[0]), self._voltage(end_nets[1])
            if a is not None and b is not None and None not in (a.low, a.high, b.low, b.high):
                lo_d = a.low - b.high  # type: ignore[operator]
                hi_d = a.high - b.low  # type: ignore[operator]
                top = max(abs(lo_d), abs(hi_d))
                bottom = Fraction(0) if lo_d <= 0 <= hi_d else min(abs(lo_d), abs(hi_d))
                source, basis, rigs = self._merge(a, b)
                across = ((bottom, top), basis, source, rigs, "")
            else:
                lacking = [self._name(n) for n, v in zip(end_nets, (a, b), strict=True) if v is None]
                across = (None, "", "user", frozenset(), "voltage of " + " and ".join(lacking or ["a net"]))
        between = f"{self._name(end_nets[0])}–{self._name(end_nets[1])}" if two_pin else ""
        # device voltage (two-pin parts)
        voltage_ratings = [r for r in device.ratings if r.key == "voltage"]
        if two_pin and across is not None:
            for rating in voltage_ratings:
                value, basis, source, rigs, missing = across
                self._add(
                    part, key="voltage", label="", rating=rating, scope="device", quantity="voltage",
                    value=value, value_basis=basis, value_source=source, missing=missing, rigs=rigs,
                    entities=[n for n in end_nets if n], what=f"the voltage across {between}",
                )  # fmt: skip
            if not voltage_ratings and across[0] is not None:
                self._no_rating(part, "voltage", "voltage", "volt", [n for n in end_nets if n])
        # pin voltages and currents
        ground_net = part.nets.get(device.ground) if device.ground else self.ground
        excluded = self._port_functions(part)
        for pin in device.pins:
            net = part.nets.get(pin.function)
            for rating in pin.ratings:
                if rating.key == "voltage":
                    if pin.function == device.ground:
                        continue
                    if rating.limit == "operating" and pin.function in excluded:
                        continue
                    value, basis, source, rigs, missing = self._difference(net, ground_net)
                    origin = device.ground or "ground"
                    self._add(
                        part, key=pin.function, label=pin.function, rating=rating, scope="pin",
                        quantity="voltage",
                        value=value, value_basis=basis, value_source=source, missing=missing, rigs=rigs,
                        entities=[n for n in (net, ground_net) if n],
                        what=f"{pin.function} on {self._name(net)} from {origin}",
                    )  # fmt: skip
                elif rating.key == "current":
                    alone = net is not None and sum(1 for f in functions if part.nets.get(f) == net) == 1
                    if not alone:
                        continue
                    bound = self.values.current.get(net) if net is not None else None
                    self._add(
                        part, key=pin.function, label=pin.function, rating=rating, scope="pin",
                        quantity="current",
                        value=None if bound is None else (Fraction(0), bound.high),
                        value_basis="" if bound is None else bound.basis,
                        value_source="user" if bound is None else bound.source,
                        missing="" if bound is not None else f"current of {self._name(net)}",
                        rigs=frozenset(), entities=[net] if net else [],
                        what=f"the current of {pin.function} on {self._name(net)}",
                    )  # fmt: skip
        # pin pairs
        for pair in device.limits:
            if len(pair.between) != 2:
                continue
            first, second = pair.between
            nets = (part.nets.get(first), part.nets.get(second))
            value, basis, source, rigs, missing = self._difference(*nets)
            for rating in pair.ratings:
                self._add(
                    part, key=f"{first}-{second}", label=f"{first}-{second}", rating=rating, scope="pin",
                    quantity="voltage", value=value, value_basis=basis, value_source=source, missing=missing,
                    rigs=rigs, entities=[n for n in nets if n],
                    what=f"{first} − {second} ({self._name(nets[0])} − {self._name(nets[1])})",
                )  # fmt: skip
        # device current by class
        self._current(part, two_pin, end_nets)
        # power
        self._power(part, two_pin, end_nets, across)
        # temperature
        self._temperature(part)

    def _port_functions(self, part: Part) -> set[str]:
        """The functions of the device ports that state ``voltage``: c0252 judges their operating voltage."""
        found: set[str] = set()
        for interface in part.device.interfaces:
            if "voltage" in interface.params:
                for functions in interface.members.values():
                    found |= set(functions)
        return found

    def _current(self, part: Part, two_pin: bool, end_nets: tuple[str | None, ...]) -> None:
        ratings = [r for r in part.device.ratings if r.key == "current"]
        out = next(
            (
                port
                for port in self.ports
                if port.owner == part.component.id and port.kind == "power" and port.direction == "out"
            ),
            None,
        )
        value: tuple[Fraction | None, Fraction | None] | None = None
        basis, source, missing, what, entities = "", "user", "", "", []
        if out is not None:
            hv = out.members.get("hv")
            rail = self.view.rails.get(hv) if hv is not None else None
            name = self._name(hv)
            what = f"the output current of {out.name} (loads of {name})"
            entities = [hv] if hv else []
            if rail is not None and rail.load_high is not None:
                value = (Fraction(0), rail.load_high)
                basis = f"rail {name} loads"
            else:
                missing = f"loads of {name}"
        elif part.cls is None:
            if ratings:
                missing, what = "no class", "the series current"
            else:
                return
        elif part.cls in SERIES and two_pin:
            bounds_ = [self.values.current.get(n) if n else None for n in end_nets]
            what = f"the series current ({' and '.join(self._name(n) for n in end_nets)})"
            entities = [n for n in end_nets if n]
            if all(b is not None and b.high is not None for b in bounds_):
                smaller = min((b for b in bounds_ if b is not None), key=lambda b: b.high or 0)
                value, basis, source = (Fraction(0), smaller.high), smaller.basis, smaller.source
            else:
                lacking = [self._name(n) for n, b in zip(end_nets, bounds_, strict=True) if b is None]
                missing = "current of " + " and ".join(lacking)
        else:
            return
        if not ratings:
            if value is not None:
                self._no_rating(part, "current", "current", "ampere", entities)
            return
        for rating in ratings:
            self._add(
                part, key="current", label="", rating=rating, scope="device", quantity="current", value=value,
                value_basis=basis, value_source=source, missing=missing, rigs=frozenset(), entities=entities,
                what=what,
            )  # fmt: skip

    def _power(
        self,
        part: Part,
        two_pin: bool,
        end_nets: tuple[str | None, ...],
        across: tuple[object, ...] | None,
    ) -> None:
        ratings = [r for r in part.device.ratings if r.key == "power"]
        if part.cls is None:
            if not ratings:
                return
            value, basis, source, rigs, missing = None, "", "user", frozenset[str](), "no class"
        elif part.cls not in POWERED or not two_pin:
            return
        else:
            value, basis, source, rigs, missing = None, "", "user", frozenset[str](), ""
            resistance = part.component.value_range
            if resistance is None or resistance.unit != "ohm":
                missing = "no value range"
            else:
                r_low, r_high = bounds(resistance)
                volts = across[0] if across is not None else None
                if volts is not None and r_low:
                    top = volts[1]  # type: ignore[index]
                    value = (None, top * top / r_low)
                    basis, source, rigs = across[1], across[2], across[3]  # type: ignore[index, assignment]
                    basis = f"{basis}; V²/R with R ≥ {amount_text('ohm', r_low)}"
                elif part.cls == "shunt" and r_high is not None:
                    known = [self.values.current.get(n) for n in end_nets if n and n in self.values.current]
                    if known:
                        smaller = min(known, key=lambda b: b.high or 0)  # type: ignore[union-attr]
                        if smaller is not None and smaller.high is not None:
                            value = (None, smaller.high * smaller.high * r_high)
                            basis = f"{smaller.basis}; I²R with R ≤ {amount_text('ohm', r_high)}"
                            source = smaller.source
                    if value is None:
                        missing = "voltage or current of the shunt's nets"
                else:
                    missing = str(across[4]) if across is not None and across[4] else "voltage of its nets"
        if not ratings:
            if value is not None:
                self._no_rating(part, "power", "power", "watt", [n for n in end_nets if n])
            return
        for rating in ratings:
            self._add(
                part, key="power", label="", rating=rating, scope="device", quantity="power", value=value,
                value_basis=str(basis), value_source=str(source), missing=missing, rigs=rigs,  # type: ignore[arg-type]
                entities=[n for n in end_nets if n], what="the worst-case power",
            )  # fmt: skip

    def _temperature(self, part: Part) -> None:
        ratings = [r for r in part.device.ratings if r.key == "temperature"]
        operating = self.contracts.operating if self.contracts is not None else None
        ambient = None if operating is None else bounds(operating.ambient)
        if not ratings:
            if ambient is not None:
                self._no_rating(part, "temperature", "temperature", "kelvin", [])
            return
        for rating in ratings:
            self._add(
                part, key="temperature", label="", rating=rating, scope="device", quantity="temperature",
                value=ambient, value_basis="design.operating ambient", value_source="user",
                missing="" if ambient is not None else "ambient range (design.operating)", rigs=frozenset(),
                entities=[], what="the ambient range",
            )  # fmt: skip


def judge_parts(
    view: View,
    values: Values,
    contracts: ContractSet | None,
    parts: Sequence[tuple[Component, DeviceDef, str | None]],
    ground: str | None,
) -> list[Judged]:
    """The rating and operating rows of ``parts`` (component, record, class)."""
    judge = RatingJudge(view, values, contracts, ground, view.circuit.ports)
    for component, device, cls in parts:
        path = component.properties.get(PATH_PROPERTY) or component.path
        subject = f"{component.ref} ({path})" if path and path != component.ref else component.ref
        judge.judge(
            Part(component, device, cls, function_nets(view, component, device), component.ref, subject)
        )
    return judge.rows


def with_corners(row: Judged, corners: Sequence[tuple[str, Status, str]]) -> Judged:
    return replace(row, corners=tuple(corners))


__all__ = [
    "CODES",
    "DEVICE_PROPERTY",
    "POWERED",
    "SERIES",
    "Judged",
    "RatingJudge",
    "compare",
    "derating_rule",
    "judge_parts",
    "to_unit",
    "with_corners",
]
