# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Immutable typed views of requirement and generator summaries (change c0270)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from fenolite.core.quantities import UNITS
from fenolite.dsl.quantity import Range
from fenolite.testing.design import TestingError


def range_of(data: Mapping[str, Any] | None) -> Range | None:
    if data is None:
        return None

    def amount(key: str) -> Fraction | None:
        value = data.get(key)
        return None if value is None else Fraction(value["m"]) * Fraction(10) ** value["e"]

    return Range(data["unit"], amount("low"), amount("high"), amount("nominal"))


@dataclass(frozen=True, slots=True)
class RequirementRow:
    """A requirement with DSL ranges; expectation ids are their block paths."""

    id: str
    entities: tuple[str, ...]
    quantity: str
    value: Range | None
    limit: Range | None
    status: str
    evidence: str

    @classmethod
    def from_data(cls, row: Mapping[str, Any]) -> RequirementRow:
        value: Mapping[str, Any] | None = row.get("value")
        limit: Mapping[str, Any] = row.get("limit") or {}
        return cls(
            str(row["id"]).removeprefix("circuit.expect:"),
            tuple(row.get("entities", ())),
            str(row["quantity"]),
            range_of(value.get("range")) if value else None,
            range_of(limit.get("range")),
            str(row["status"]),
            str(limit.get("evidence", "")),
        )


def achieved_range(text: str) -> Range:
    """Decode the generator's outward-rounded micro-unit interval, preserving its exact bounds."""
    import re

    match = re.fullmatch(r"\S+ (-?\d+)u([^ .]+)\.\.(-?\d+)u([^ .]+)", text)
    if match is None or match[2] != match[4]:
        raise TestingError(f"the generator has no supported achieved range: {text!r}")
    unit = next((unit for unit, symbol in UNITS.items() if match[2] in (unit, symbol)), None)
    if unit is None:
        raise TestingError(f"unknown achieved range unit {match[2]!r}")
    return Range(unit, Fraction(int(match[1]), 10**6), Fraction(int(match[3]), 10**6))


__all__ = ["RequirementRow"]
