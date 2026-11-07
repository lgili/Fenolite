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
from fenolite.core.requirement_table import Bound, LimitKind, Origin, Side, Source, Status, amount_text
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
SERIES: frozenset[str] = frozenset({"inductor", "shunt", "ferrite"})
"""The classes whose device current is the series current of their two nets (a ferrite since change c0274,
derating key ``ferrite_current``; a fuse is not judged and a jumper has no rating row)."""
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

    def scoped(rule: DeratingRule) -> bool:
        return _glob_matches(rule, ref) and applies(rule)

    def by_class(rule: DeratingRule) -> bool:
        return not rule.parts and applies(rule) and bool(DERATING_KEYS[rule.key][2])

    def generic(rule: DeratingRule) -> bool:
        return not rule.parts and applies(rule) and not DERATING_KEYS[rule.key][2]

    for level in (scoped, by_class, generic):
        found = next((rule for rule in rules if level(rule)), None)
        if found is not None:
            return found
    return None


Span = tuple[Fraction | None, Fraction | None]


@dataclass(frozen=True, slots=True)
class Applied:
    """An applied value of a row: its span (``None`` when it is not known), basis, source, the rig supplies
    it reads and, when unknown, what is missing."""

    value: Span | None
    basis: str = ""
    source: Source = "user"
    rigs: frozenset[str] = frozenset()
    missing: str = ""
    origin: Origin | None = None
    """Where the value comes from (change c0274)."""


DECLARED = Origin("declared")


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
        basis = " ".join(part for part in (device.id, label, rating.limit) if part)
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
        applied: Applied,
        *,
        key: str,
        label: str,
        rating: Rating,
        scope: str,
        quantity: str,
        entities: Sequence[str],
        what: str,
    ) -> None:
        limit_range, limit_side, no_policy = self._limit(part, rating, scope, label)
        unit = SCALE[rating.unit][0]
        code = CODES[rating.key] if rating.limit == "abs_max" else "circuit.operating-range"
        row_id = f"{code}:{part.ref}:{key}"
        if rating.limit == "operating" and key not in CODES:
            row_id = f"{code}:{part.ref}:{key}:{rating.key}"
        missing = applied.missing
        side: Side | None = None
        status: Status = "unknown"
        if applied.value is not None:
            status = compare(applied.value, limit_range)
            if status == "unknown" and not missing:
                missing = f"an unbounded {quantity}"
            low, high = applied.value
            if low is not None or high is not None:
                bound = Bound(unit, low, high)
                side = Side(bound, bound.text(), applied.source, applied.basis, origin=applied.origin)
        verb = "exceeds the" if rating.limit == "abs_max" else "is not within the operating range"
        text = (
            f"{part.subject}: {what} {'' if side is None else side.text} ({applied.basis}) {verb} "
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
                applied.rigs if status != "unknown" else frozenset(),
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
    def _merge(span: Span, *values: Value) -> Applied:
        """An applied value read from ``values``: ``user`` when any of them is the user's."""
        source: Source = "user" if any(v.source == "user" for v in values) else values[0].source
        basis = "; ".join(dict.fromkeys(v.basis for v in values))
        rigs = frozenset[str]().union(*(v.rigs for v in values))
        stated = [v for v in values if v.kind != "ground"] or list(values)
        origin = next((v.origin for v in stated if v.origin.kind == "propagated"), stated[0].origin)
        return Applied(span, basis, source, rigs, origin=origin)

    def _lacking(self, *pairs: tuple[str | None, Value | None]) -> Applied:
        names = [self._name(net) for net, value in pairs if value is None]
        return Applied(None, missing="voltage of " + " and ".join(names or ["a net"]))

    def _difference(self, first: str | None, second: str | None) -> Applied:
        """``V(first) - V(second)``, worst case at both ends."""
        a, b = self._voltage(first), self._voltage(second)
        if a is None or b is None:
            return self._lacking((first, a), (second, b))
        low = None if a.low is None or b.high is None else a.low - b.high
        high = None if a.high is None or b.low is None else a.high - b.low
        return self._merge((low, high), a, b)

    def _across(self, first: str | None, second: str | None) -> Applied:
        """``|V(first) - V(second)|``, worst case: ``max(a.max - b.min, b.max - a.min)`` above."""
        a, b = self._voltage(first), self._voltage(second)
        if a is None or b is None:
            return self._lacking((first, a), (second, b))
        if a.low is None or a.high is None or b.low is None or b.high is None:
            return Applied(None, missing=f"a bounded voltage of {self._name(first)} and {self._name(second)}")
        lo_d, hi_d = a.low - b.high, a.high - b.low
        top = max(abs(lo_d), abs(hi_d))
        bottom = Fraction(0) if lo_d <= 0 <= hi_d else min(abs(lo_d), abs(hi_d))
        return self._merge((bottom, top), a, b)

    # --------------------------------------------------------------------------------------- rows

    def judge(self, part: Part) -> None:
        device = part.device
        functions = [pin.function for pin in device.pins]
        ends = device.ends if len(device.ends) == 2 else (tuple(functions) if len(functions) == 2 else ())
        end_nets: tuple[str | None, ...] = tuple(part.nets.get(f) for f in ends)
        across = self._across(end_nets[0], end_nets[1]) if len(end_nets) == 2 else None
        nets = [n for n in end_nets if n]
        if across is not None:
            between = f"{self._name(end_nets[0])}–{self._name(end_nets[1])}"
            voltage_ratings = [r for r in device.ratings if r.key == "voltage"]
            for rating in voltage_ratings:
                self._add(
                    part, across, key="voltage", label="", rating=rating, scope="device", quantity="voltage",
                    entities=nets, what=f"the voltage across {between}",
                )  # fmt: skip
            if not voltage_ratings and across.value is not None:
                self._no_rating(part, "voltage", "voltage", "volt", nets)
        self._pins(part, functions)
        for pair in device.limits:
            if len(pair.between) != 2:
                continue
            first, second = pair.between
            pair_nets = (part.nets.get(first), part.nets.get(second))
            applied = self._difference(*pair_nets)
            for rating in pair.ratings:
                self._add(
                    part, applied, key=f"{first}-{second}", label=f"{first}-{second}", rating=rating,
                    scope="pin", quantity="voltage", entities=[n for n in pair_nets if n],
                    what=f"{first} − {second} ({self._name(pair_nets[0])} − {self._name(pair_nets[1])})",
                )  # fmt: skip
        self._current(part, end_nets)
        self._power(part, end_nets, across)
        self._temperature(part)

    def _pins(self, part: Part, functions: Sequence[str]) -> None:
        device = part.device
        ground_net = part.nets.get(device.ground) if device.ground else self.ground
        excluded = self._port_functions(part)
        origin = device.ground or "ground"
        for pin in device.pins:
            net = part.nets.get(pin.function)
            for rating in pin.ratings:
                if rating.key == "voltage":
                    if pin.function == device.ground or (
                        rating.limit == "operating" and pin.function in excluded
                    ):
                        continue
                    self._add(
                        part, self._difference(net, ground_net), key=pin.function, label=pin.function,
                        rating=rating, scope="pin", quantity="voltage",
                        entities=[n for n in (net, ground_net) if n],
                        what=f"{pin.function} on {self._name(net)} from {origin}",
                    )  # fmt: skip
                elif rating.key == "current":
                    if net is None or sum(1 for f in functions if part.nets.get(f) == net) != 1:
                        continue
                    bound = self.values.current.get(net)
                    applied = (
                        Applied(None, missing=f"current of {self._name(net)}")
                        if bound is None
                        else Applied(
                            (Fraction(0), bound.high), bound.basis, bound.source, origin=bound.origin
                        )
                    )
                    self._add(
                        part, applied, key=pin.function, label=pin.function, rating=rating, scope="pin",
                        quantity="current", entities=[net],
                        what=f"the current of {pin.function} on {self._name(net)}",
                    )  # fmt: skip

    def _port_functions(self, part: Part) -> set[str]:
        """The functions of the device ports that state ``voltage``: c0252 judges their operating voltage."""
        found: set[str] = set()
        for interface in part.device.interfaces:
            if "voltage" in interface.params:
                for functions in interface.members.values():
                    found |= set(functions)
        return found

    def _current(self, part: Part, end_nets: tuple[str | None, ...]) -> None:
        ratings = [r for r in part.device.ratings if r.key == "current"]
        out = next(
            (
                port
                for port in self.ports
                if port.owner == part.component.id and port.kind == "power" and port.direction == "out"
            ),
            None,
        )
        entities: list[str] = []
        if out is not None:
            hv = out.members.get("hv")
            rail = self.view.rails.get(hv) if hv is not None else None
            name = self._name(hv)
            what = f"the output current of {out.name} (loads of {name})"
            entities = [hv] if hv else []
            if rail is not None and rail.load_high is not None:
                applied = Applied(
                    (Fraction(0), rail.load_high), f"rail {name} loads", "user", origin=DECLARED
                )
            else:
                applied = Applied(None, missing=f"loads of {name}")
        elif part.cls is None:
            if not ratings:
                return
            applied, what = Applied(None, missing="no class"), "the series current"
        elif part.cls in SERIES and len(end_nets) == 2:
            what = f"the series current ({' and '.join(self._name(n) for n in end_nets)})"
            entities = [n for n in end_nets if n]
            found = [self.values.current.get(n) if n else None for n in end_nets]
            known = [b for b in found if b is not None and b.high is not None]
            if len(known) == 2:
                smaller = min(known, key=lambda b: b.high or Fraction(0))
                applied = Applied(
                    (Fraction(0), smaller.high), smaller.basis, smaller.source, origin=smaller.origin
                )
            else:
                lacking = [self._name(n) for n, b in zip(end_nets, found, strict=True) if b is None]
                applied = Applied(None, missing="current of " + " and ".join(lacking or ["a net"]))
        else:
            return
        if not ratings:
            if applied.value is not None:
                self._no_rating(part, "current", "current", "ampere", entities)
            return
        for rating in ratings:
            self._add(
                part, applied, key="current", label="", rating=rating, scope="device", quantity="current",
                entities=entities, what=what,
            )  # fmt: skip

    def _power(self, part: Part, end_nets: tuple[str | None, ...], across: Applied | None) -> None:
        ratings = [r for r in part.device.ratings if r.key == "power"]
        if part.cls is None:
            if not ratings:
                return
            applied = Applied(None, missing="no class")
        elif part.cls not in POWERED or across is None:
            return
        else:
            applied = self._dissipation(part, end_nets, across)
        nets = [n for n in end_nets if n]
        if not ratings:
            if applied.value is not None:
                self._no_rating(part, "power", "power", "watt", nets)
            return
        for rating in ratings:
            self._add(
                part, applied, key="power", label="", rating=rating, scope="device", quantity="power",
                entities=nets, what="the worst-case power",
            )  # fmt: skip

    def _dissipation(self, part: Part, end_nets: tuple[str | None, ...], across: Applied) -> Applied:
        """``V_across.max² / R.min``, else for a shunt ``I.max² × R.max``, with c0274's products."""
        resistance = part.component.value_range
        if resistance is None or resistance.unit != "ohm":
            return Applied(None, missing="no value range")
        r_low, r_high = bounds(resistance)
        if across.value is not None and across.value[1] is not None and r_low:
            top = across.value[1]
            basis = f"{across.basis}; V²/R with R ≥ {amount_text('ohm', r_low)}"
            return Applied((None, top * top / r_low), basis, across.source, across.rigs, origin=across.origin)
        if part.cls == "shunt" and r_high is not None:
            known = [self.values.current[n] for n in end_nets if n and n in self.values.current]
            highs = [b for b in known if b.high is not None]
            if highs:
                smaller = min(highs, key=lambda b: b.high or Fraction(0))
                amps = smaller.high or Fraction(0)
                basis = f"{smaller.basis}; I²R with R ≤ {amount_text('ohm', r_high)}"
                return Applied((None, amps * amps * r_high), basis, smaller.source, origin=smaller.origin)
            return Applied(None, missing="voltage or current of the shunt's nets")
        return Applied(None, missing=across.missing or "voltage of its nets")

    def _temperature(self, part: Part) -> None:
        ratings = [r for r in part.device.ratings if r.key == "temperature"]
        operating = self.contracts.operating if self.contracts is not None else None
        if not ratings:
            if operating is not None:
                self._no_rating(part, "temperature", "temperature", "kelvin", [])
            return
        applied = (
            Applied(None, missing="ambient range (design.operating)")
            if operating is None
            else Applied(bounds(operating.ambient), "design.operating ambient", origin=DECLARED)
        )
        for rating in ratings:
            self._add(
                part, applied, key="temperature", label="", rating=rating, scope="device",
                quantity="temperature", entities=[], what="the ambient range",
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
    "Applied",
    "Judged",
    "RatingJudge",
    "compare",
    "derating_rule",
    "judge_parts",
    "to_unit",
    "with_corners",
]
