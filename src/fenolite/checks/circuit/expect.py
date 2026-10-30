# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The expectations of the contract judge (change c0253; capability electrical-contracts, "Expectation
judgement" and "Unresolved expectations"; ``docs/contracts.md``, "Expectations").

An expectation is data: a tree of operations over literal ranges, exact numbers and refs to the model
(a component's ``value_range``, a device limit, a net's voltage or current bound). The judge evaluates it
by worst-case range arithmetic on the model as it is now, so an edit kept after the build is what is
judged, and gives one of three results: ``pass``, ``unsure`` (the ranges overlap without the test holding
for all of them) or ``fail`` (it holds for none). A ref that cannot be resolved or bounded makes the
expectation ``unknown``. No Python code of the script runs here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from fenolite.checks.circuit.rails import View, bounds
from fenolite.checks.circuit.ratings import Judged, to_unit
from fenolite.checks.circuit.values import Values
from fenolite.core.quantities import UNITS
from fenolite.core.requirement_table import TABLE_UNITS, Bound, Side, Status
from fenolite.model.library import DeviceDef, Rating
from fenolite.model.rules import Expectation, ExpectNode

RATIO = "ratio"
EXPECT_ROW = ".".join(("circuit", "expect"))
"""The prefix of an expectation's row id (``circuit.expect:buck1/expect#1``); not an issue code."""
SQUARED: tuple[str, ...] = ("volt_squared", "ampere_squared")
"""The units of the products V·V and A·A (c0274), which exist in the judge only."""


def _products() -> dict[tuple[str, str], str]:
    table: dict[tuple[str, str], str] = {(RATIO, RATIO): RATIO}
    for unit in (*UNITS, *SQUARED):
        table[(unit, RATIO)] = table[(RATIO, unit)] = unit
    for left, right, result in (
        ("volt", "ampere", "watt"),
        ("ampere", "ohm", "volt"),
        ("ohm", "farad", "second"),
        ("hertz", "second", RATIO),
        ("volt", "volt", "volt_squared"),
        ("ampere", "ampere", "ampere_squared"),
        ("ampere_squared", "ohm", "watt"),
    ):
        table[(left, right)] = table[(right, left)] = result
    return table


def _quotients() -> dict[tuple[str, str], str]:
    table: dict[tuple[str, str], str] = {(RATIO, RATIO): RATIO}
    for unit in (*UNITS, *SQUARED):
        table[(unit, unit)] = RATIO
        table[(unit, RATIO)] = unit
    for left, right, result in (
        ("volt", "ohm", "ampere"),
        ("volt", "ampere", "ohm"),
        ("watt", "volt", "ampere"),
        ("watt", "ampere", "volt"),
        ("henry", "ohm", "second"),
        (RATIO, "second", "hertz"),
        (RATIO, "hertz", "second"),
        ("volt_squared", "ohm", "watt"),
        ("watt", "ohm", "ampere_squared"),
    ):
        table[(left, right)] = result
    return table


PRODUCTS: Mapping[tuple[str, str], str] = _products()
"""(unit, unit) → the unit of the product: the table of ``fenolite.dsl.quantity.UNIT_PRODUCTS`` (a test keeps
the two equal; ``checks`` does not import the DSL)."""
QUOTIENTS: Mapping[tuple[str, str], str] = _quotients()
"""(dividend, divisor) → the unit of the quotient, as ``fenolite.dsl.quantity.UNIT_QUOTIENTS``."""


class Unknown(Exception):
    """A ref that cannot be resolved or bounded; the message names it."""


@dataclass(frozen=True, slots=True)
class Interval:
    """An exact interval of one unit (``None``: unbounded) and the rig supplies it reads."""

    unit: str
    low: Fraction | None
    high: Fraction | None
    rigs: frozenset[str] = frozenset()


def _side(a: Fraction | None, b: Fraction | None, how: str) -> Fraction | None:
    if a is None or b is None:
        return None
    return a + b if how == "+" else a - b


def _mul(a: Interval, b: Interval, unit: str) -> Interval:
    rigs = a.rigs | b.rigs
    if a.low is None or a.high is None or b.low is None or b.high is None:
        if a.low is None or b.low is None or a.low < 0 or b.low < 0:
            raise Unknown(f"a product of the one-sided {_text(a)} and {_text(b)}")
        high = None if a.high is None or b.high is None else a.high * b.high
        return Interval(unit, a.low * b.low, high, rigs)
    products = [x * y for x in (a.low, a.high) for y in (b.low, b.high)]
    return Interval(unit, min(products), max(products), rigs)


def _div(a: Interval, b: Interval, unit: str) -> Interval:
    rigs = a.rigs | b.rigs
    if b.low is None or b.high is None or b.low <= 0 <= b.high:
        if b.low is not None and b.low > 0 and a.low is not None and a.low >= 0:
            high = None if a.high is None else a.high / b.low
            low = Fraction(0) if b.high is None else a.low / b.high
            return Interval(unit, low, high, rigs)
        raise Unknown(f"a divisor {_text(b)} that holds zero or is unbounded")
    if a.low is None or a.high is None:
        raise Unknown(f"a quotient of the one-sided {_text(a)}")
    quotients = [x / y for x in (a.low, a.high) for y in (b.low, b.high)]
    return Interval(unit, min(quotients), max(quotients), rigs)


def _text(value: Interval) -> str:
    if value.unit in TABLE_UNITS:
        return (
            Bound(value.unit, value.low, value.high).text()
            if (value.low, value.high) != (None, None)
            else "?"
        )
    return f"{value.low}..{value.high} {value.unit}"


class Evaluator:
    """Evaluates expectation trees on the model, the device records and the net bounds."""

    def __init__(self, view: View, values: Values, devices: Mapping[str, DeviceDef] | None) -> None:
        self.view = view
        self.values = values
        self.devices = devices

    def label(self, node: ExpectNode) -> str:
        """The handle a ref names, for people: ``value of R_top``, ``rating current of L1``."""
        component = self.view.components.get(node.component)
        name = component.ref if component is not None else node.component
        if node.ref == "value":
            return f"value of {name}"
        if node.ref == "rating":
            where = f" of {name}.{node.pin}" if node.pin else f" of {name}"
            return f"{node.limit} {node.key}{where}"
        return f"{node.ref} of {self.view.net_name(node.net)}"

    def describe(self, node: ExpectNode) -> str:
        """The expression for people."""
        if node.lit is not None:
            low, high = bounds(node.lit)
            return Bound(node.lit.unit, low, high).text()
        if node.num:
            return str(Fraction(node.num[0], node.num[1]))
        if node.ref:
            return self.label(node)
        signs = {"add": "+", "sub": "-", "mul": "*", "div": "/"}
        if node.op == "neg" and node.a is not None:
            return f"-({self.describe(node.a)})"
        assert node.a is not None and node.b is not None
        return f"({self.describe(node.a)} {signs.get(node.op, node.op)} {self.describe(node.b)})"

    def _rating(self, node: ExpectNode) -> Interval:
        component = self.view.components.get(node.component)
        if component is None:
            raise Unknown(f"{self.label(node)}: the part is not in the model")
        device_id = component.properties.get("fenolite.device", "")
        device = (self.devices or {}).get(device_id)
        if device is None:
            raise Unknown(f"{self.label(node)}: no device record was given for {device_id or component.ref}")
        ratings: tuple[Rating, ...] = device.ratings
        if node.pin:
            try:
                ratings = device.pin(node.pin).ratings
            except KeyError:
                raise Unknown(f"{self.label(node)}: {device.id} has no function {node.pin}") from None
        found = next((r for r in ratings if (r.key, r.limit) == (node.key, node.limit)), None)
        if found is None:
            raise Unknown(f"{self.label(node)}: {device.id} states none")
        unit, low, high = to_unit(found)
        return Interval(unit, low, high)

    def evaluate(self, node: ExpectNode) -> Interval:
        if node.lit is not None:
            low, high = bounds(node.lit)
            return Interval(node.lit.unit, low, high)
        if node.num:
            exact = Fraction(node.num[0], node.num[1])
            return Interval(RATIO, exact, exact)
        if node.ref == "value":
            component = self.view.components.get(node.component)
            if component is None or component.value_range is None:
                raise Unknown(f"{self.label(node)}: no value range in the model")
            low, high = bounds(component.value_range)
            return Interval(component.value_range.unit, low, high)
        if node.ref == "rating":
            return self._rating(node)
        if node.ref == "voltage":
            found = self.values.voltage.get(node.net)
            if found is None:
                raise Unknown(f"{self.label(node)}: no voltage is stated")
            return Interval("volt", found.low, found.high, found.rigs)
        if node.ref == "current":
            found = self.values.current.get(node.net)
            if found is None:
                raise Unknown(f"{self.label(node)}: no current is stated")
            return Interval("ampere", Fraction(0), found.high)
        assert node.a is not None
        a = self.evaluate(node.a)
        if node.op == "neg":
            return Interval(
                a.unit, None if a.high is None else -a.high, None if a.low is None else -a.low, a.rigs
            )
        assert node.b is not None
        b = self.evaluate(node.b)
        if node.op in ("add", "sub"):
            if a.unit != b.unit:
                raise Unknown(f"{self.describe(node)}: adds {a.unit} and {b.unit}")
            if node.op == "add":
                low, high = _side(a.low, b.low, "+"), _side(a.high, b.high, "+")
            else:
                low, high = _side(a.low, b.high, "-"), _side(a.high, b.low, "-")
            return Interval(a.unit, low, high, a.rigs | b.rigs)
        table = PRODUCTS if node.op == "mul" else QUOTIENTS
        unit = table.get((a.unit, b.unit))
        if unit is None:
            raise Unknown(f"{self.describe(node)}: no unit for {a.unit} {node.op} {b.unit}")
        return _mul(a, b, unit) if node.op == "mul" else _div(a, b, unit)


def _low(value: Fraction | None) -> tuple[int, Fraction]:
    """A low bound on the extended line: ``None`` is minus infinity."""
    return (-1, Fraction(0)) if value is None else (0, value)


def _high(value: Fraction | None) -> tuple[int, Fraction]:
    """A high bound on the extended line: ``None`` is plus infinity."""
    return (1, Fraction(0)) if value is None else (0, value)


def verdict(op: str, a: Interval, b: Interval) -> Status:
    """The three-valued judgement of ``op`` on worst-case intervals (``docs/contracts.md``):

    - ``within(a, b)``: pass when ``b.min <= a.min`` and ``a.max <= b.max``, fail when ``a.max < b.min`` or
      ``a.min > b.max``;
    - ``at_least(a, b)``: pass when ``a.min >= b.max``, fail when ``a.max < b.min``;
    - ``at_most(a, b)``: pass when ``a.max <= b.min``, fail when ``a.min > b.max``;
    - unsure otherwise, and unknown for two units."""
    if a.unit != b.unit:
        return "unknown"
    a_lo, a_hi, b_lo, b_hi = _low(a.low), _high(a.high), _low(b.low), _high(b.high)
    if op == "within":
        if b_lo <= a_lo and a_hi <= b_hi:
            return "pass"
        return "fail" if a_hi < b_lo or a_lo > b_hi else "unsure"
    if op == "at_least":
        if a_lo >= b_hi:
            return "pass"
        return "fail" if a_hi < b_lo else "unsure"
    if a_hi <= b_lo:
        return "pass"
    return "fail" if a_lo > b_hi else "unsure"


CODES: Mapping[Status, str] = {
    "pass": "circuit.expect-failed",
    "fail": "circuit.expect-failed",
    "unsure": "circuit.expect-unsure",
    "unknown": "circuit.expect-unknown",
}
"""The code a row of each status reports (a passing row names the code it would report)."""
WORDS: Mapping[str, str] = {"within": "within", "at_least": "at least", "at_most": "at most"}


def judge_expectation(evaluator: Evaluator, expectation: Expectation) -> Judged:
    """The row of one expectation; an unresolved handle makes it ``unknown`` and stops nothing else."""
    test = expectation.test
    assert test.a is not None and test.b is not None
    row_id = f"{EXPECT_ROW}:{expectation.id}"
    subject = f"{expectation.id} ({expectation.reason})"
    limit_text = evaluator.describe(test.b)
    try:
        a = evaluator.evaluate(test.a)
        b = evaluator.evaluate(test.b)
    except Unknown as error:
        return Judged(
            row_id, CODES["unknown"], subject, "expectation", RATIO, None,
            Side(None, limit_text, "user", expectation.reason, "INFERRED", "requirement"),
            "unknown", tuple(_entities(test)), missing=str(error),
            text=f"{subject}: {error}",
        )  # fmt: skip
    status = verdict(test.op, a, b)
    unit = a.unit if a.unit in TABLE_UNITS else RATIO
    bounded = a.low is not None or a.high is not None
    value = (
        Side(Bound(unit, a.low, a.high), _text(a), "user", evaluator.describe(test.a))
        if bounded and a.unit in TABLE_UNITS
        else None
    )
    limit_bound = (
        Bound(b.unit, b.low, b.high) if b.unit in TABLE_UNITS and (b.low, b.high) != (None, None) else None
    )
    limit = Side(limit_bound, _text(b), "user", expectation.reason, "INFERRED", "requirement")
    verb = {"fail": "never holds", "unsure": "holds for part of the ranges", "pass": "holds"}.get(status, "")
    text = f"{subject}: {_text(a)} {WORDS[test.op]} {_text(b)} {verb}"
    if status == "unknown":
        text = f"{subject}: {a.unit} is compared with {b.unit}"
    return Judged(
        row_id, CODES[status], subject, "expectation", unit, value, limit, status, tuple(_entities(test)),
        missing="" if status != "unknown" else f"{a.unit} against {b.unit}", rigs=a.rigs | b.rigs, text=text,
    )  # fmt: skip


def _entities(node: ExpectNode) -> list[str]:
    found = [ident for ident in (node.component, node.net) if ident]
    for child in (node.a, node.b):
        if child is not None:
            found += _entities(child)
    return found


__all__ = [
    "CODES",
    "PRODUCTS",
    "QUOTIENTS",
    "Evaluator",
    "Interval",
    "Unknown",
    "judge_expectation",
    "verdict",
]
