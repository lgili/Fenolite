# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The one requirement table (change c0253; capability electrical-contracts, "Requirement table";
``docs/contracts.md``, "The requirement table").

Each judged limit is one ``RequirementRow``: what is judged (``subject``, ``quantity``), the applied
``value`` and the ``limit``, each an exact range with the ``source`` it comes from (``device``, ``role``,
``policy`` or ``user``) and a ``basis`` text, the ``status`` and the severity of the finding it gives. The
stages ``circuit.rules`` and ``roles.rules`` give rows, and ``fenolite roles --check`` joins them.

Standard library only, so ``checks``, ``roles`` and ``cli`` all import it. ``Bound`` writes a range in the
encoding of c0246's ``ValueRange`` (a unit name and ``Decimal10`` bounds: an integer mantissa ``m`` of at
most 15 digits and an exponent ``e``), rounded outward when the exact value does not terminate; a test keeps
the two byte-identical. No number of the table is a JSON float.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Literal

from fenolite.core.quantities import PREFIXES, UNITS, ZERO_CELSIUS

Source = Literal["device", "role", "policy", "user"]
SOURCES: tuple[Source, ...] = ("device", "role", "policy", "user")
"""Where a value or a limit comes from: a device record, a net role, a policy (the user's derating rule, or a
role profile default) or the user's own number (a rig, a rail, a requirements row, an option)."""
LimitKind = Literal["abs_max", "operating", "requirement"]
LIMIT_KINDS: tuple[LimitKind, ...] = ("abs_max", "operating", "requirement")
Status = Literal["pass", "fail", "unsure", "unknown", "deferred"]
STATUSES: tuple[Status, ...] = ("pass", "fail", "unsure", "unknown", "deferred")
"""The status of a row; ``deferred`` (change c0274) is a row whose decidable stage is not reached for its
subject and that does not fail."""
Stage = Literal["build", "place", "route"]
STAGES: tuple[Stage, ...] = ("build", "place", "route")
"""The stage at which a row can be decided (change c0274; ``docs/contracts.md``, "Decidable stages")."""
OriginKind = Literal["declared", "rig", "role", "requirements", "option", "propagated"]
ORIGINS: tuple[OriginKind, ...] = ("declared", "rig", "role", "requirements", "option", "propagated")
"""Where an applied voltage or current bound comes from (change c0274): a design rail, a ground or an
``out`` port's promise (``declared``), a rig element, a stated net role, a ``[[current]]`` row
(``requirements``), ``--current`` (``option``) or links from a stated net (``propagated``)."""
DIGEST_DIGITS = 16
"""The hexadecimal digits of a row digest (the start of a SHA-256)."""
TABLE_UNITS: tuple[str, ...] = (*UNITS, "metre", "square_metre", "ratio")
"""The unit names of a row: c0246's and c0274's, and for role rows ``metre``, ``square_metre`` and
``ratio``."""
DIGITS = 15
"""The most significant digits of a mantissa, as c0246's ``Decimal10``."""
EXPONENTS = range(-30, 31)
TEXT_DIGITS = 5
"""The significant digits of a value's text when it does not terminate (rounded outward, after ``~``)."""
_SYMBOLS: Mapping[str, str] = {**UNITS, "metre": "m", "square_metre": "m²", "ratio": ""}


def decimal10(value: Fraction, mode: str) -> dict[str, int]:
    """``value`` as c0246's ``Decimal10`` object ``{"m": ..., "e": ...}``: exact with at most 15 significant
    digits, else rounded ``down``, ``up`` or to ``near``est; ``ValueError`` outside the exponents."""
    if value == 0:
        return {"m": 0, "e": 0}
    size = abs(value)
    k = len(str(size.numerator)) - len(str(size.denominator))
    if size < Fraction(10) ** k:
        k -= 1
    if size >= Fraction(10) ** (k + 1):
        k += 1
    exponent = k - DIGITS + 1
    scaled = size / Fraction(10) ** exponent
    if value < 0:
        mode = {"down": "up", "up": "down"}.get(mode, mode)
    if scaled.denominator == 1:
        whole = scaled.numerator
    elif mode == "down":
        whole = math.floor(scaled)
    elif mode == "up":
        whole = math.ceil(scaled)
    else:
        whole = round(scaled)
    while whole % 10 == 0:
        whole //= 10
        exponent += 1
    if exponent not in EXPONENTS:
        raise ValueError(f"{value} needs the exponent {exponent}, outside -30..30")
    return {"m": -whole if value < 0 else whole, "e": exponent}


def _rounded(size: Fraction, mode: str) -> Fraction:
    """A positive ``size`` rounded ``up``, ``down`` or to ``near``est to ``TEXT_DIGITS`` significant
    digits."""
    k = len(str(size.numerator)) - len(str(size.denominator))
    if size < Fraction(10) ** k:
        k -= 1
    if size >= Fraction(10) ** (k + 1):
        k += 1
    step = Fraction(10) ** (k - TEXT_DIGITS + 1)
    count = size / step
    if mode == "near":
        return round(count) * step
    return (math.ceil(count) if mode == "up" else math.floor(count)) * step


def _digits(value: Fraction) -> str | None:
    """The exact decimal text of a non-negative ``value``, or ``None`` when it does not terminate."""
    places, rest = 0, value.denominator
    for factor in (2, 5):
        count = 0
        while rest % factor == 0:
            rest //= factor
            count += 1
        places = max(places, count)
    if rest != 1:
        return None
    digits = str(value.numerator * 10**places // value.denominator).rjust(places + 1, "0")
    return f"{digits[:-places]}.{digits[-places:]}" if places else digits


def amount_text(unit: str, value: Fraction, mode: str = "near") -> str:
    """One value for people: ``13.2V``, ``8mA``, ``-20°C`` for a temperature (kelvin), ``~3.2315V`` when it
    does not terminate (rounded ``mode``: ``down``, ``up`` or ``near``, outward for a bound)."""
    if unit == "kelvin":
        celsius = value - ZERO_CELSIUS
        return _plain(celsius, "°C", mode, prefixed=False)
    return _plain(value, _SYMBOLS.get(unit, ""), mode, prefixed=unit not in ("ratio", "square_metre"))


def _plain(value: Fraction, symbol: str, mode: str, *, prefixed: bool) -> str:
    size = abs(value)
    prefix, power = "", 0
    if size and prefixed:
        prefix, power = PREFIXES[0]
        for name, exponent in PREFIXES:
            if size >= Fraction(10) ** exponent:
                prefix, power = name, exponent
    scaled = size / Fraction(10) ** power
    sign = "-" if value < 0 else ""
    exact = _digits(scaled)
    if exact is not None:
        return f"{sign}{exact}{prefix}{symbol}"
    if value < 0:
        mode = {"down": "up", "up": "down"}.get(mode, mode)
    shown = _rounded(scaled, mode)
    return f"~{sign}{_digits(shown)}{prefix}{symbol}"


@dataclass(frozen=True, slots=True)
class Bound:
    """An exact range of one unit (``TABLE_UNITS``): ``low`` and ``high``, each ``None`` when unbounded,
    and an optional ``nominal``."""

    unit: str
    low: Fraction | None = None
    high: Fraction | None = None
    nominal: Fraction | None = None

    def __post_init__(self) -> None:
        if self.unit not in TABLE_UNITS:
            raise ValueError(f"unknown unit {self.unit!r}; use one of: {', '.join(TABLE_UNITS)}")
        if self.low is None and self.high is None:
            raise ValueError("a bound needs a low or a high value")
        if self.low is not None and self.high is not None and self.low > self.high:
            raise ValueError(f"a bound runs from low to high, not from {self.low} to {self.high}")

    def to_json(self) -> dict[str, object]:
        """The range in c0246's encoding: ``unit``, then ``low``, ``nominal`` and ``high`` as ``Decimal10``
        objects, each left out when absent; bounds rounded outward, the nominal to nearest."""
        found: dict[str, object] = {"unit": self.unit}
        if self.low is not None:
            found["low"] = decimal10(self.low, "down")
        if self.nominal is not None:
            found["nominal"] = decimal10(self.nominal, "near")
        if self.high is not None:
            found["high"] = decimal10(self.high, "up")
        return found

    def text(self) -> str:
        """``10.8V..13.2V``, ``..8V`` when unbounded below, one value when both bounds are equal."""
        if self.low is not None and self.low == self.high:
            return amount_text(self.unit, self.low)
        low = "" if self.low is None else amount_text(self.unit, self.low, "down")
        high = "" if self.high is None else amount_text(self.unit, self.high, "up")
        return f"{low}..{high}"


@dataclass(frozen=True, slots=True)
class Origin:
    """Where an applied value comes from (change c0274): its ``kind`` (``ORIGINS``) and, for a propagated
    value, the link references it went through in order (``via``) and the stated net (``source``, ``from``
    in JSON)."""

    kind: OriginKind
    via: tuple[str, ...] = ()
    source: str = ""

    def __post_init__(self) -> None:
        if self.kind not in ORIGINS:
            raise ValueError(f"origin {self.kind!r} is not one of {', '.join(ORIGINS)}")

    def to_json(self) -> dict[str, object]:
        if self.kind != "propagated":
            return {"kind": self.kind}
        return {"from": self.source, "kind": self.kind, "via": list(self.via)}

    def text(self) -> str:
        """``rig``, ``propagated via FB1 from 3V3``."""
        if self.kind != "propagated":
            return self.kind
        return f"propagated via {', '.join(self.via)} from {self.source}"


@dataclass(frozen=True, slots=True)
class Side:
    """The value or the limit of a row: its range (``None`` when it has none, such as a value not known),
    its text for people, its source and its basis. A limit also has the evidence label of what states it
    and its kind (``abs_max``, ``operating`` or ``requirement``)."""

    range: Bound | None
    text: str
    source: Source
    basis: str
    evidence: str = ""
    kind: LimitKind | None = None
    origin: Origin | None = None
    """Where an applied value comes from (change c0274); a limit has none."""

    def __post_init__(self) -> None:
        if self.source not in SOURCES:
            raise ValueError(f"source {self.source!r} is not one of {', '.join(SOURCES)}")
        if self.kind is not None and self.kind not in LIMIT_KINDS:
            raise ValueError(f"kind {self.kind!r} is not one of {', '.join(LIMIT_KINDS)}")

    def to_json(self, *, limit: bool) -> dict[str, object]:
        found: dict[str, object] = {
            "range": None if self.range is None else self.range.to_json(),
            "text": self.text,
            "source": self.source,
            "basis": self.basis,
        }
        if limit:
            found["evidence"] = self.evidence
            found["kind"] = self.kind
        elif self.origin is not None:
            found["origin"] = self.origin.to_json()
        return found


@dataclass(frozen=True, slots=True)
class Corner:
    """A row at one corner of the rig supplies (``bench=max,aux=min``): its status and value text."""

    corner: str
    status: Status
    text: str

    def to_json(self) -> dict[str, object]:
        return {"corner": self.corner, "status": self.status, "text": self.text}


@dataclass(frozen=True, slots=True)
class RequirementRow:
    """One judged limit (``docs/contracts.md``, "The requirement table")."""

    id: str
    check: str
    subject: str
    quantity: str
    unit: str
    value: Side | None
    limit: Side
    status: Status
    severity: str | None = None
    entities: tuple[str, ...] = ()
    corners: tuple[Corner, ...] = field(default=())
    missing: str = ""
    """What is not stated when the row is ``unknown`` (``voltage of V12``, ``no rating``, ``no class``)."""
    decidable: Stage = "build"
    """The stage at which the row can be decided (change c0274): ``build`` for a ``circuit.*`` row, ``place``
    for a loop row, ``route`` for any other role row."""
    waiver: str = ""
    """The name of the waiver that accepted the row's finding (change c0274), ``""`` when none did."""

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"row {self.id}: status {self.status!r} is not one of {', '.join(STATUSES)}")
        if self.decidable not in STAGES:
            raise ValueError(f"row {self.id}: decidable {self.decidable!r} is not one of {', '.join(STAGES)}")

    @property
    def item(self) -> str:
        """The row id without its code: what a ``circuit.*`` waiver names (``C3:voltage``)."""
        return self.id.partition(":")[2] or self.id

    @property
    def digest(self) -> str:
        """The first 16 hexadecimal digits of the SHA-256 of the canonical JSON of the row's id, the ranges of
        its value and limit, the limit's kind and both sources (change c0274): what a ``circuit.*`` waiver
        accepts. The texts and bases are left out, so a reworded message is not a change."""
        return row_digest(
            {
                "id": self.id,
                "value": None
                if self.value is None or self.value.range is None
                else self.value.range.to_json(),
                "limit": None if self.limit.range is None else self.limit.range.to_json(),
                "kind": self.limit.kind,
                "value_source": None if self.value is None else self.value.source,
                "limit_source": self.limit.source,
            }
        )
        if self.unit not in TABLE_UNITS:
            raise ValueError(f"row {self.id}: unknown unit {self.unit!r}")
        if self.severity not in (None, "info", "warning", "error"):
            raise ValueError(f"row {self.id}: severity {self.severity!r} is not info, warning or error")

    def to_json(self) -> dict[str, object]:
        return {
            "id": self.id,
            "check": self.check,
            "entities": sorted(set(self.entities)),
            "subject": self.subject,
            "quantity": self.quantity,
            "unit": self.unit,
            "value": None if self.value is None else self.value.to_json(limit=False),
            "limit": self.limit.to_json(limit=True),
            "corners": [corner.to_json() for corner in self.corners],
            "status": self.status,
            "severity": self.severity,
            "missing": self.missing,
            "decidable": self.decidable,
            "digest": self.digest,
            "waiver": self.waiver or None,
        }


def row_digest(data: Mapping[str, object]) -> str:
    """The first ``DIGEST_DIGITS`` hexadecimal digits of the SHA-256 of ``data`` as canonical JSON (sorted
    keys, no spaces, integers only)."""
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:DIGEST_DIGITS]


def table_json(rows: Iterable[RequirementRow]) -> list[dict[str, object]]:
    """The rows in canonical order (by ``id``), as JSON; a repeated id keeps its first row."""
    unique: dict[str, RequirementRow] = {}
    for row in rows:
        unique.setdefault(row.id, row)
    return [unique[key].to_json() for key in sorted(unique)]


def joined(*tables: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    """Tables already in JSON, joined in ``id`` order; a repeated id keeps the row of the first table."""
    unique: dict[str, Mapping[str, object]] = {}
    for table in tables:
        for row in table:
            unique.setdefault(str(row["id"]), row)
    return [unique[key] for key in sorted(unique)]


__all__ = [
    "DIGEST_DIGITS",
    "LIMIT_KINDS",
    "ORIGINS",
    "SOURCES",
    "STAGES",
    "STATUSES",
    "TABLE_UNITS",
    "Bound",
    "Corner",
    "LimitKind",
    "Origin",
    "OriginKind",
    "RequirementRow",
    "Side",
    "Source",
    "Stage",
    "Status",
    "amount_text",
    "decimal10",
    "joined",
    "row_digest",
    "table_json",
]
