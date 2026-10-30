# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Electrical contracts of a design script (change c0253; capability design-dsl, "Electrical contracts in
the DSL" and "Contract helpers in the DSL"; ``docs/contracts.md``).

``Design.derating``, ``operating``, ``contracts``, ``expect`` and ``rig``, and the block builder's ``expect``,
record plain data here; ``convert.to_model`` turns it into ``RuleSet.contracts``. Nothing here judges: the
stage ``circuit.rules`` (``fenolite.checks.circuit``) does, on the built model.

- ``ratio(p)`` is a derating, "at most p % of the rating", stored in whole per-mille. c0246's ``pct()`` is a
  ± tolerance and is refused as a derating. Fenolite ships no derating value: every rule is the script's.
- ``value_of``, ``rating_of``, ``voltage_of`` and ``current_of`` return handles, and ``+ - * /`` on handles,
  c0246 ranges, quantities and exact numbers builds an expression. ``within``, ``at_least`` and ``at_most``
  build a test. A handle, an expression or a test has no truth value and no order, so a script cannot branch
  on one by mistake.
- ``supply`` and ``sink`` are test-rig elements: records of the rules layer, never components, so they reach
  no netlist, schematic, board, BOM or export.
"""

from __future__ import annotations

import fnmatch
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from typing import TYPE_CHECKING, Literal, cast

from fenolite.dsl.errors import DslError
from fenolite.dsl.part import Net, Part
from fenolite.dsl.quantity import RATIO, UNIT_PRODUCTS, UNIT_QUOTIENTS, Quantity, Range, Tolerance
from fenolite.model.circuit import ValueRange
from fenolite.model.rules import (
    CONTRACT_STRICTNESS,
    DERATING_KEYS,
    ROLE_KEY,
    ContractSet,
    DeratingRule,
    Expectation,
    ExpectNode,
    OperatingRange,
    RigSink,
    RigSupply,
)

if TYPE_CHECKING:
    from fenolite.dsl.design import Design
    from fenolite.dsl.module import Module

RATING_UNITS: Mapping[str, str] = {
    "voltage": "volt",
    "current": "ampere",
    "power": "watt",
    "temperature": "kelvin",
}
"""The unit of each rating key of a device record (change c0248)."""
LIMITS: tuple[str, ...] = ("abs_max", "operating")
_NO_TRUTH = (
    "a contract handle has no truth value; record a comparison with design.expect(within(a, b), reason)"
)
_NO_ORDER = "contract handles have no order; compare them with at_least(a, b), at_most(a, b) or within(a, b)"


# ---------------------------------------------------------------------------------------- derating


@dataclass(frozen=True, slots=True)
class Derating:
    """A derating ratio: "at most ``percent`` % of the rating" (build one with ``ratio()``)."""

    percent: Fraction


def ratio(percent: int | Fraction | str) -> Derating:
    """A derating, "at most ``percent`` % of the rating": ``ratio(50)`` limits a part to half its rating. It
    lies above 0 and at most 100 (a derating never raises a rating) and is stored in whole per-mille."""
    if isinstance(percent, bool) or isinstance(percent, float):
        raise DslError(f"ratio({percent!r}) is not exact; give an int, a Fraction or a text such as '62.5'")
    if isinstance(percent, str) and re.fullmatch(r"\s*\d+(?:\.\d+)?\s*", percent):
        value = Fraction(percent.strip())
    elif isinstance(percent, int | Fraction) and not isinstance(percent, str):
        value = Fraction(percent)
    else:
        raise DslError(f"ratio({percent!r}): give a per-cent as an int, a Fraction or a decimal text")
    if not 0 < value <= 100:
        raise DslError(f"ratio({percent}): a derating lies above 0 and at most 100 % of the rating")
    return Derating(value)


# ------------------------------------------------------------------------------------- expressions


def _unit_of(value: object) -> str | None:
    return value.unit if isinstance(value, Expr) else None


class Expr:
    """An expression of a contract: a handle, a literal or an operation on them. It has no truth value and
    no order (``docs/contracts.md``, "Expectations")."""

    __slots__ = ("unit",)

    def __init__(self, unit: str | None) -> None:
        self.unit = unit

    def __bool__(self) -> bool:
        raise DslError(_NO_TRUTH)

    def _refuse(self, other: object) -> bool:
        raise DslError(_NO_ORDER)

    __lt__ = __le__ = __gt__ = __ge__ = _refuse

    def __add__(self, other: object) -> Expr:
        return Op("add", self, operand(other))

    def __radd__(self, other: object) -> Expr:
        return Op("add", operand(other), self)

    def __sub__(self, other: object) -> Expr:
        return Op("sub", self, operand(other))

    def __rsub__(self, other: object) -> Expr:
        return Op("sub", operand(other), self)

    def __mul__(self, other: object) -> Expr:
        return Op("mul", self, operand(other))

    def __rmul__(self, other: object) -> Expr:
        return Op("mul", operand(other), self)

    def __truediv__(self, other: object) -> Expr:
        return Op("div", self, operand(other))

    def __rtruediv__(self, other: object) -> Expr:
        return Op("div", operand(other), self)

    def __neg__(self) -> Expr:
        return Op("neg", self, None)


class Lit(Expr):
    """A c0246 range or a quantity of a unit."""

    __slots__ = ("range",)

    def __init__(self, value: Range) -> None:
        super().__init__(value.unit)
        self.range = value


class Num(Expr):
    """An exact number without a unit."""

    __slots__ = ("value",)

    def __init__(self, value: Fraction) -> None:
        super().__init__(RATIO)
        self.value = value


class Ref(Expr):
    """A handle: what the stage reads from the model (``value``, ``rating``, ``voltage``, ``current``)."""

    __slots__ = ("kind", "key", "limit", "pin", "target")

    def __init__(
        self, kind: str, target: object, unit: str | None, *, key: str = "", pin: str = "", limit: str = ""
    ) -> None:
        super().__init__(unit)
        self.kind = kind
        self.target = target
        self.key = key
        self.pin = pin
        self.limit = limit

    def __repr__(self) -> str:
        return f"{self.kind}_of({self.target!r})"


class Op(Expr):
    """An operation of ``+ - * /`` or a negation, with the unit c0246's tables give."""

    __slots__ = ("a", "b", "op")

    def __init__(self, op: str, a: Expr, b: Expr | None) -> None:
        left, right = a.unit, None if b is None else b.unit
        unit: str | None = left
        if b is not None and left is not None and right is not None:
            if op in ("add", "sub"):
                if left != right:
                    raise DslError(f"a contract adds or subtracts one unit, not {left} and {right}")
            else:
                table = UNIT_PRODUCTS if op == "mul" else UNIT_QUOTIENTS
                unit = table.get((left, right))
                if unit is None:
                    sign = "*" if op == "mul" else "/"
                    raise DslError(f"a contract has no unit for {left} {sign} {right}")
        elif b is not None and op in ("mul", "div"):
            unit = None
        super().__init__(unit)
        self.op = op
        self.a = a
        self.b = b


def operand(value: object) -> Expr:
    """``value`` as an expression: a handle or expression, a c0246 range, a quantity, an int or a
    ``Fraction``; a float or anything else raises ``DslError``."""
    if isinstance(value, Expr):
        return value
    if isinstance(value, Range):
        return Lit(value)
    if isinstance(value, Quantity):
        return Lit(value.as_range())
    if isinstance(value, bool) or isinstance(value, float):
        raise DslError(f"{value!r} is not exact; a contract takes an int, a Fraction, a quantity or a range")
    if isinstance(value, int | Fraction):
        return Num(Fraction(value))
    raise DslError(f"a contract takes handles, ranges, quantities, ints or Fractions, not {value!r}")


def value_of(part: Part) -> Ref:
    """The handle of ``part``'s value range: what the stage reads from the built model, so an edit
    kept after the build is judged."""
    if not isinstance(part, Part):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise DslError(f"value_of() takes a Part, not {part!r}")
    unit = part.value_range.unit if part.value_range is not None else None
    return Ref("value", part, unit)


def _listed(names: Sequence[str]) -> str:
    return ", ".join(sorted(set(names))) or "none"


def rating_of(part: Part, key: str, pin: str | None = None, limit: str = "abs_max") -> Ref:
    """The handle of a limit of ``part``'s device: the device rating ``key`` (``voltage``, ``current``,
    ``power``, ``temperature``), or the pin's when ``pin`` names a function, of kind ``limit`` (``abs_max`` or
    ``operating``). A key, pin or kind the record does not state raises ``DslError`` listing what it has."""
    if not isinstance(part, Part):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise DslError(f"rating_of() takes a Part, not {part!r}")
    what = f"rating_of({part.path}, {key!r})"
    device = part.device
    if device is None:
        raise DslError(f"{what}: the part has no device, so it has no rating; place it with device=...")
    if limit not in LIMITS:
        raise DslError(f"{what}: limit {limit!r} is not one of {', '.join(LIMITS)}")
    ratings = device.ratings
    if pin is not None:
        functions = [found.function for found in device.pins]
        if pin not in functions:
            raise DslError(
                f"{what}: device {device.id} has no function {pin!r}; its functions: {_listed(functions)}"
            )
        ratings = device.pin(pin).ratings
    keys = [found.key for found in ratings]
    owner = f"the pin {pin} of device {device.id}" if pin is not None else f"device {device.id}"
    if key not in keys:
        raise DslError(f"{what}: {owner} has no {key} rating; its ratings: {_listed(keys)}")
    kinds = [found.limit for found in ratings if found.key == key]
    if limit not in kinds:
        raise DslError(f"{what}: {owner} states no {limit} {key}; it states: {_listed(kinds)}")
    return Ref("rating", part, RATING_UNITS.get(key), key=key, pin=pin or "", limit=limit)


def _net_of(target: object, what: str) -> Net:
    from fenolite.dsl.interfaces import Interface
    from fenolite.dsl.portnets import PortHandle

    if isinstance(target, Net):
        return target
    if isinstance(target, Interface):
        found = target.main()
        if found is not None:
            return found
    if isinstance(target, PortHandle):
        from fenolite.dsl.portnets import MAIN_MEMBERS

        member = MAIN_MEMBERS.get(target.kind) or (
            next(iter(target.members)) if len(target.members) == 1 else None
        )
        if member is not None and member in target.members:
            return cast(Net, target.members[member])
    raise DslError(f"{what} takes a Net, a Rail, a Ground or a power port, not {target!r}")


def voltage_of(target: object) -> Ref:
    """The handle of the voltage bound of a net, a rail or a power port (``docs/contracts.md``, "Applied
    values"): from the rig, the rail or the net's declared role, never inferred."""
    _net_of(target, "voltage_of()")
    return Ref("voltage", target, "volt")


def current_of(target: object) -> Ref:
    """The handle of the current bound of a net, a rail or a power port."""
    _net_of(target, "current_of()")
    return Ref("current", target, "ampere")


@dataclass(frozen=True, slots=True, eq=False)
class Test:
    """A comparison recorded by ``design.expect``: ``within``, ``at_least`` or ``at_most`` of two
    expressions. It has no truth value."""

    op: str
    a: Expr
    b: Expr

    def __bool__(self) -> bool:
        raise DslError(_NO_TRUTH)


def _test(op: str, a: object, b: object) -> Test:
    left, right = operand(a), operand(b)
    if left.unit is not None and right.unit is not None and left.unit != right.unit:
        raise DslError(f"{op}() compares one unit, not {left.unit} and {right.unit}")
    return Test(op, left, right)


def within(a: object, b: object) -> Test:
    """The test "every value of ``a`` lies in ``b``": it passes when ``a`` is inside ``b``, fails when they do
    not overlap, and is unsure otherwise."""
    return _test("within", a, b)


def at_least(a: object, b: object) -> Test:
    """The test "``a`` is at least ``b``": it passes when ``a.min >= b.max``, fails when ``a.max < b.min``."""
    return _test("at_least", a, b)


def at_most(a: object, b: object) -> Test:
    """The test "``a`` is at most ``b``": it passes when ``a.max <= b.min``, fails when ``a.min > b.max``."""
    return _test("at_most", a, b)


# ------------------------------------------------------------------------------------------- rig


@dataclass(frozen=True, slots=True, eq=False)
class Supply:
    """A test-rig supply (``supply()``)."""

    pos: object
    neg: object
    voltage: Range
    current: Range | None
    name: str | None


@dataclass(frozen=True, slots=True, eq=False)
class Sink:
    """A test-rig sink (``sink()``)."""

    net: object
    ret: object
    current: Range
    name: str | None


def _amount(value: object, unit: str, what: str) -> Range:
    if isinstance(value, Quantity):
        value = value.as_range()
    if not isinstance(value, Range) or value.unit != unit:
        raise DslError(f"{what} is a range or a quantity in {unit}, not {value!r}")
    return value


def _name_or_none(name: object, what: str) -> str | None:
    if name is not None and (not isinstance(name, str) or not ROLE_KEY.fullmatch(name)):
        raise DslError(f"{what}: the name {name!r} must match {ROLE_KEY.pattern}")
    return cast(str | None, name)


def supply(
    pos: object, neg: object = None, *, voltage: object, current: object = None, name: str | None = None
) -> Supply:
    """A rig supply: the outside world holds ``pos`` at ``voltage`` against ``neg`` (the design's one ground
    when omitted) and delivers at most ``current``. It is a record of the rules layer, never a part."""
    what = f"supply({name or ''})"
    _net_of(pos, what)
    if neg is not None:
        _net_of(neg, what)
    found = _amount(voltage, "volt", f"{what}: voltage")
    amps = None if current is None else _amount(current, "ampere", f"{what}: current")
    return Supply(pos, neg, found, amps, _name_or_none(name, what))


def sink(net: object, ret: object = None, *, current: object, name: str | None = None) -> Sink:
    """A rig sink: the outside world draws ``current`` from ``net`` to ``ret`` (the design's one ground when
    omitted). It is a record of the rules layer, never a part."""
    what = f"sink({name or ''})"
    _net_of(net, what)
    if ret is not None:
        _net_of(ret, what)
    return Sink(net, ret, _amount(current, "ampere", f"{what}: current"), _name_or_none(name, what))


# --------------------------------------------------------------------------------------- records


@dataclass(slots=True)
class ContractRecords:
    """What the contract calls of one script recorded, in call order."""

    derating: list[tuple[str, int, int, object, str]] = field(default_factory=lambda: [])
    """``(key, permille, margin_mk, parts, source)``; ``parts`` is ``None``, a ``Part`` or a ref glob."""
    operating: Range | None = None
    unknown: str = "info"
    expects: list[tuple[str, str, str, Test]] = field(default_factory=lambda: [])
    """``(instance, reason, origin, test)``."""
    rig: list[Supply | Sink] = field(default_factory=lambda: [])


def records(design: Design) -> ContractRecords:
    """The contract records of ``design``."""
    return design.contract_records


def _parts(value: object, what: str) -> object:
    from fenolite.dsl.select import Select

    if value is None or isinstance(value, Part):
        return value
    if isinstance(value, Select) and value.selector.op == "ref" and value.selector.value:
        return value.selector.value
    raise DslError(f"{what}: parts is a Part or select.ref(<glob>), not {value!r}")


def derating(design: Design, parts: object, source: object, keys: Mapping[str, object]) -> None:
    found = records(design)
    what = "derating()"
    scope = _parts(parts, what)
    if not isinstance(source, str):
        raise DslError(f"{what}: source is a text naming where the rule comes from, not {source!r}")
    if not keys:
        raise DslError(f"{what} names no key; keys: {', '.join(DERATING_KEYS)}")
    for key, value in keys.items():
        if key not in DERATING_KEYS:
            raise DslError(f"{what}: unknown key {key!r}; keys: {', '.join(DERATING_KEYS)}")
        permille = margin = 0
        if key == "temperature_margin":
            if not isinstance(value, Quantity) or value.unit != "kelvin" or value.value <= 0:
                raise DslError(f"{what}: temperature_margin is a temperature difference, such as kelvin(15)")
            scaled = value.value * 1000
            if scaled.denominator != 1:
                raise DslError(
                    f"{what}: temperature_margin is stored in whole millikelvin, not {value.value} K"
                )
            margin = scaled.numerator
        elif isinstance(value, Tolerance):
            raise DslError(f"{what}: {key}=pct(...) is a ± tolerance, not a derating; write {key}=ratio(50)")
        elif not isinstance(value, Derating):
            raise DslError(f"{what}: {key} takes ratio(<per-cent>), such as ratio(50), not {value!r}")
        else:
            scaled = value.percent * 10
            if scaled.denominator != 1:
                raise DslError(
                    f"{what}: {key}=ratio({value.percent}): a derating is stored in whole per-mille, so give "
                    "a per-cent with at most one decimal"
                )
            permille = scaled.numerator
        if scope is None and any(row[0] == key and row[3] is None for row in found.derating):
            raise DslError(f"{what}: the key {key} has a design-wide rule already")
        found.derating.append((key, permille, margin, scope, source))


def operating(design: Design, ambient: object) -> None:
    found = records(design)
    if found.operating is not None:
        raise DslError("operating(): the design states its operating range once")
    if (
        not isinstance(ambient, Range)
        or ambient.unit != "kelvin"
        or ambient.low is None
        or ambient.high is None
    ):
        raise DslError(
            "operating(): ambient is a range of temperatures, such as between(celsius(-20), celsius(70))"
        )
    found.operating = ambient


def contracts(design: Design, unknown: object) -> None:
    if unknown not in CONTRACT_STRICTNESS:
        raise DslError(f"contracts(): unknown is one of {', '.join(CONTRACT_STRICTNESS)}, not {unknown!r}")
    records(design).unknown = cast(str, unknown)


def _origin() -> str:
    """``module:line`` of the script line that called ``expect`` (never a path)."""
    frame = sys._getframe(4)  # pyright: ignore[reportPrivateUsage]
    module = str(frame.f_globals.get("__name__") or "script")
    if not re.fullmatch(r"[A-Za-z_][\w.]*", module):
        module = "script"
    return f"{module}:{frame.f_lineno}"


def expect(design: Design, instance: str, test: object, reason: object) -> None:
    found = records(design)
    if isinstance(test, bool):
        raise DslError(
            "expect() needs within(a, b), at_least(a, b) or at_most(a, b), so that both ranges are recorded "
            "and judged on every check; a bool such as Range.within() is fixed at script time"
        )
    if not isinstance(test, Test):
        raise DslError(f"expect() takes within(a, b), at_least(a, b) or at_most(a, b), not {test!r}")
    if not isinstance(reason, str) or not reason.strip():
        raise DslError("expect() needs a reason: a text that says why the expectation holds")
    if any(row[0] == instance and row[1] == reason for row in found.expects):
        raise DslError(f"expect(): the reason {reason!r} is used twice in {instance}; give each its own")
    found.expects.append((instance, reason, _origin(), test))


def expect_on(design: Design, test: object, reason: object) -> None:
    """``Design.expect``: an expectation of the top level, path ``design``."""
    expect(design, "design", test, reason)


def expect_in(block: Module, test: object, reason: object) -> None:
    """``b.expect``: an expectation of the block instance ``block``."""
    design = block.design
    if design is None:
        raise DslError(f"expect(): {block.describe()} is not in a design yet")
    expect(design, block.path, test, reason)


def rig(design: Design, elements: Sequence[object]) -> None:
    found = records(design)
    if not elements:
        raise DslError("rig() takes supply(...) and sink(...) elements")
    for element in elements:
        if not isinstance(element, Supply | Sink):
            raise DslError(f"rig() takes supply(...) and sink(...), not {element!r}")
        found.rig.append(element)


# -------------------------------------------------------------------------------------- to_model


def _key_id(kind: str, *parts: str) -> str:
    from fenolite.dsl.convert import key_id

    return key_id(kind, *parts)


def _range(value: Range, what: str) -> ValueRange:
    from fenolite.dsl.convert import range_to_model

    return range_to_model(value) if value.unit != RATIO else _refuse_ratio(what)


def _refuse_ratio(what: str) -> ValueRange:
    raise DslError(f"{what}: a range without a unit is recorded only as an exact number")


def _node(expr: Expr, design: Design, what: str) -> ExpectNode:
    if isinstance(expr, Num):
        return ExpectNode(num=(expr.value.numerator, expr.value.denominator))
    if isinstance(expr, Lit):
        value = expr.range
        if value.unit == RATIO:
            if value.low is not None and value.low == value.high:
                return ExpectNode(num=(value.low.numerator, value.low.denominator))
            _refuse_ratio(what)
        return ExpectNode(lit=_range(value, what))
    if isinstance(expr, Op):
        right = None if expr.b is None else _node(expr.b, design, what)
        return ExpectNode(expr.op, _node(expr.a, design, what), right)
    if isinstance(expr, Ref):
        if expr.kind in ("value", "rating"):
            part = cast(Part, expr.target)
            if design.parts.get(part.path) is not part:
                raise DslError(f"{what}: part {part.path} is not in the design")
            return ExpectNode(
                ref=expr.kind,
                component=_key_id("component", part.path),
                key=expr.key,
                pin=expr.pin,
                limit=expr.limit,
            )
        net = _net_of(expr.target, what)
        if net.name not in design.nets:
            raise DslError(f"{what}: the net {net.name} is not in the design")
        return ExpectNode(ref=expr.kind, net=_key_id("net", net.name))
    raise DslError(f"{what}: {expr!r} is not a contract expression")


def _grounds(design: Design) -> list[str]:
    names = {
        itf.members["gnd"].name
        for itf in design.interfaces.values()
        if itf.kind == "ground" and "gnd" in itf.members
    }
    names |= {name for name, role in design.role_records.nets.items() if role.kind == "ground"}
    return sorted(names)


def _rig_net(design: Design, target: object, used: set[str], name: str, side: str) -> str:
    what = f"rig {name}"
    if target is None:
        grounds = _grounds(design)
        if len(grounds) != 1:
            raise DslError(
                f"{what}: {side} is omitted and the design has {len(grounds)} grounds "
                f"({', '.join(grounds) or 'none'}); name the net"
            )
        net_name = grounds[0]
    else:
        net_name = _net_of(target, what).name
    if net_name not in used:
        raise DslError(
            f"{what}: the net {net_name} has no pin of a board part; a rig names nets of the design"
        )
    return _key_id("net", net_name)


def to_contracts(design: Design) -> ContractSet | None:
    """The ``ContractSet`` of ``design``, or ``None`` when the script states no contract; ``DslError`` for a
    rig on a net without parts, an omitted ground that is not one, or two part-scoped rules of one key that
    both match a part."""
    found = design.contract_records
    rules: list[DeratingRule] = []
    scoped: dict[str, list[str]] = {}
    for key, permille, margin, scope, source in found.derating:
        glob = scope.label if isinstance(scope, Part) else cast(str, scope or "")
        rules.append(DeratingRule(key, permille, margin, glob, source))
        if glob:
            scoped.setdefault(key, []).append(glob)
    refs = sorted(part.label for part in design.parts.values())
    for key, globs in scoped.items():
        for ref in refs:
            matching = [glob for glob in globs if fnmatch.fnmatchcase(ref, glob)]
            if len(matching) > 1:
                raise DslError(
                    f"derating(): two rules of {key} match {ref}: parts={matching[0]!r} and {matching[1]!r}"
                )
    expects: list[Expectation] = []
    counts: dict[str, int] = {}
    for instance, reason, origin, test in found.expects:
        counts[instance] = counts.get(instance, 0) + 1
        ident = f"{instance}/expect#{counts[instance]}"
        what = f"expect {ident} ({reason})"
        node = ExpectNode(test.op, _node(test.a, design, what), _node(test.b, design, what))
        expects.append(Expectation(ident, instance, reason, origin, node))
    used = {net.name for part in design.parts.values() for net in part.connections.values()}
    elements: list[RigSupply | RigSink] = []
    seen: set[str] = set()
    for index, element in enumerate(found.rig, start=1):
        kind = "supply" if isinstance(element, Supply) else "sink"
        name = element.name or f"{kind}{index}"
        if name in seen:
            raise DslError(f"rig(): the name {name!r} is used twice")
        seen.add(name)
        if isinstance(element, Supply):
            elements.append(
                RigSupply(
                    "supply",
                    name,
                    _rig_net(design, element.pos, used, name, "pos"),
                    _rig_net(design, element.neg, used, name, "neg"),
                    _range(element.voltage, f"rig {name}"),
                    None if element.current is None else _range(element.current, f"rig {name}"),
                )
            )
        else:
            elements.append(
                RigSink(
                    "sink",
                    name,
                    _rig_net(design, element.net, used, name, "net"),
                    _rig_net(design, element.ret, used, name, "ret"),
                    _range(element.current, f"rig {name}"),
                )
            )
    ambient = None if found.operating is None else OperatingRange(_range(found.operating, "operating()"))
    try:
        made = ContractSet(
            derating=tuple(rules),
            operating=ambient,
            unknown=cast(Literal["info", "warning"], found.unknown),
            expects=tuple(expects),
            rig=tuple(elements),
        )
    except ValueError as error:
        raise DslError(f"contracts: {error}") from None
    return made or None


__all__ = [
    "LIMITS",
    "RATING_UNITS",
    "ContractRecords",
    "Derating",
    "Expr",
    "Sink",
    "Supply",
    "Test",
    "at_least",
    "at_most",
    "current_of",
    "operand",
    "rating_of",
    "ratio",
    "records",
    "sink",
    "supply",
    "to_contracts",
    "value_of",
    "voltage_of",
    "within",
]
