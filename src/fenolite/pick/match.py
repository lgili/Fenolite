# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Matching and ranking of rows against a query (change c0254, ``docs/picking.md``, "Matching").

A row of the query's kind matches when its value meets the query's value (an exact quantity equals the
row's nominal; a range contains the row's worst-case span, nominal ± the row's tolerance) and every
constraint holds: a rating at least as large (``>=``), a value at most as large (``<=``), equality of a
name (a tuple of names: any of them). A row that does not state a constrained attribute never matches: a
missing rating is never assumed. An ``UNVERIFIED`` row (a proposal not reviewed yet) is ranked out unless
the query names it with ``row=``. Matches are ranked, fully deterministically, by the distance of their
nominal to the query's nominal, the larger tolerance, the smaller case, a project row before a shipped one,
and the device id in code-point order.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from fenolite.core.partquery import KEYS, VALUE_UNITS, Constraint, Key, PartQuery, Percent
from fenolite.core.quantities import decimal_digits
from fenolite.pick.rows import SHIPPED, Row, case_rank, value_text

Reason = Literal["failed", "unknown", "unverified"]


@dataclass(frozen=True, slots=True)
class Exclusion:
    """A row of the query's kind left out: the first constraint it fails (``key`` and its text) and why:
    ``failed`` (the row states the attribute and misses), ``unknown`` (the row does not state it) or
    ``unverified`` (an ``UNVERIFIED`` row the query does not name)."""

    row: Row
    key: str
    text: str
    reason: Reason


@dataclass(frozen=True, slots=True)
class MatchResult:
    """The matching rows, ranked, and the rows of the kind left out, in row order."""

    matches: tuple[Row, ...]
    excluded: tuple[Exclusion, ...]

    @property
    def best(self) -> Row | None:
        return self.matches[0] if self.matches else None


def _number(value: Fraction) -> str:
    whole, part = decimal_digits(value, "a number")
    return f"{whole}.{part}" if part else whole


def constraint_text(found: Key, value: Constraint) -> str:
    """``rating>=50V``: one constraint as the canonical text prints it."""
    if isinstance(value, Percent):
        shown = value.text()
    elif isinstance(value, tuple):
        shown = "|".join(value)
    elif isinstance(value, str):
        shown = value
    elif found.unit == "ppm":
        shown = f"{_number(value)}ppm/K"
    else:
        shown = value_text(found.unit, value)
    return f"{found.name}{found.op}{shown}"


def value_failure(query: PartQuery, row: Row) -> tuple[str, Reason] | None:
    """Why ``row``'s value misses ``query``'s value, as ``(text, reason)``, or ``None`` when it meets it."""
    bounds = query.value
    if bounds is None:
        return None
    unit = VALUE_UNITS[query.kind]
    if query.exact:
        if row.value == bounds.low:
            return None
        return f"value={value_text(unit, bounds.low or Fraction(0))}", "failed"
    tolerance = row.tolerance
    shown = query.value_text or "the value range"
    if tolerance is None:
        return f"value within {shown} (the row states no tolerance)", "unknown"
    low = row.value + row.value * tolerance.lo / 100
    high = row.value + row.value * tolerance.hi / 100
    if bounds.contains(low, high):
        return None
    return f"value within {shown}", "failed"


def _meets(found: Key, wanted: Constraint, have: Constraint) -> bool:
    if found.name == "tolerance":
        return isinstance(have, Percent) and isinstance(wanted, Percent) and have.within(wanted)
    if found.unit in ("text", "texts"):
        names = wanted if isinstance(wanted, tuple) else (wanted,)
        return isinstance(have, str) and have in names
    if not isinstance(have, Fraction) or not isinstance(wanted, Fraction):
        return False
    return have >= wanted if found.op == ">=" else have <= wanted


def failure(query: PartQuery, row: Row) -> Exclusion | None:
    """The first reason ``row`` does not match ``query``, or ``None`` when it does (``row`` is of the
    query's kind)."""
    missed = value_failure(query, row)
    if missed is not None:
        return Exclusion(row, "value", missed[0], missed[1])
    given = dict(query.constraints)
    named = given.get("row")
    for found in KEYS[query.kind]:
        if found.name not in given:
            continue
        wanted = given[found.name]
        if found.name == "row":
            if wanted not in (row.row, row.device):
                return Exclusion(row, "row", constraint_text(found, wanted), "failed")
            continue
        have = row.attributes.get(found.name)
        if have is None:
            return Exclusion(row, found.name, constraint_text(found, wanted), "unknown")
        if not _meets(found, wanted, have):
            return Exclusion(row, found.name, constraint_text(found, wanted), "failed")
    if row.unverified and named not in (row.row, row.device):
        return Exclusion(row, "evidence", "an UNVERIFIED row is picked only when row= names it", "unverified")
    return None


def rank_key(query: PartQuery, row: Row) -> tuple[Fraction, Fraction, int, int, str]:
    """The ranking key of a match: distance to the nominal, the larger tolerance, the smaller case, project
    before shipped, the device id."""
    nominal = query.value.center() if query.value is not None else row.value
    tolerance = row.tolerance
    return (
        abs(row.value - nominal),
        -(tolerance.size() if tolerance is not None else Fraction(0)),
        case_rank(row.attributes.get("case")),
        1 if row.origin == SHIPPED else 0,
        row.device,
    )


def match(query: PartQuery, rows: Iterable[Row]) -> MatchResult:
    """The rows of ``rows`` that match ``query``, ranked, and those of its kind left out."""
    matches: list[Row] = []
    excluded: list[Exclusion] = []
    for row in rows:
        if row.kind != query.kind:
            continue
        missed = failure(query, row)
        if missed is None:
            matches.append(row)
        else:
            excluded.append(missed)
    matches.sort(key=lambda row: rank_key(query, row))
    return MatchResult(tuple(matches), tuple(excluded))


def unknown_rows(result: MatchResult) -> tuple[Exclusion, ...]:
    """One exclusion per row id left out only because it lacks a constrained attribute."""
    seen: dict[str, Exclusion] = {}
    for found in result.excluded:
        if found.reason == "unknown" and found.key != "value":
            seen.setdefault(found.row.row, found)
    return tuple(seen[key] for key in sorted(seen))


def unverified_ahead(query: PartQuery, result: MatchResult) -> tuple[Exclusion, ...]:
    """The ``UNVERIFIED`` rows ranked out that would rank before the pick (one per row id)."""
    best = result.best
    limit = rank_key(query, best) if best is not None else None
    seen: dict[str, Exclusion] = {}
    for found in result.excluded:
        if found.reason != "unverified":
            continue
        if limit is None or rank_key(query, found.row) < limit:
            seen.setdefault(found.row.row, found)
    return tuple(seen[key] for key in sorted(seen))


def candidates(
    query: PartQuery, rows: Sequence[Row], limit: int
) -> tuple[tuple[Row, ...], tuple[Exclusion, ...]]:
    """The first ``limit`` matches of ``query`` and its exclusions (``fenolite pick --candidates``)."""
    result = match(query, rows)
    return result.matches[:limit], result.excluded


__all__ = [
    "Exclusion",
    "MatchResult",
    "candidates",
    "constraint_text",
    "failure",
    "match",
    "rank_key",
    "unknown_rows",
    "unverified_ahead",
    "value_failure",
]
