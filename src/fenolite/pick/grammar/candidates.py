# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Grammar candidates as pickable rows (change c0263, ``docs/picking.md``, "Families with ordering
codes").

A candidate becomes, in memory and never written, a c0248 device: ``id = "<family id>@<MPN>"``, the
family's manufacturer and the MPN, its datasheet, the symbol and footprint (family keys or code attributes),
the pins ``1`` and ``2`` on the family's pads, its kind, value and ratings in c0248's integer units, and the
family's evidence and sources. As a c0254 row it carries the SHA-256 of the candidate's canonical text, so an
edit of the grammar that leaves a locked candidate unchanged keeps its hash.

``grammar_rows`` gives the rows a build needs from one family: the candidates of each query of the family's
kind (a generator's part is left to the generic rows) and the locked devices of the family that still decode
inside the validity matrix.
"""

from __future__ import annotations

from collections.abc import Iterable
from fractions import Fraction
from types import MappingProxyType
from typing import cast

from fenolite.catalog.devices import DeviceFormatError
from fenolite.core.partquery import PREFIXES, VALUE_UNITS, PartQuery
from fenolite.core.quantities import MICRO_UNITS, power
from fenolite.model.library import DeviceDef, DevicePin, Rating, RatingUnit
from fenolite.pick.grammar.decode import parse_mpn
from fenolite.pick.grammar.expand import Candidate, Expansion, ExpansionLimitError, admitted
from fenolite.pick.grammar.lint import errors
from fenolite.pick.grammar.schema import GrammarFamily
from fenolite.pick.rows import Origin, Row, value_code, value_text

RATINGS: tuple[tuple[str, str], ...] = (
    ("current", "current"),
    ("power", "power"),
    ("rating", "voltage"),
    ("voltage", "voltage"),
)
"""Code attribute → the c0248 rating key it gives (its maximum, ``abs_max``)."""
_RATING_UNITS = {"current": "ampere", "power": "watt", "voltage": "volt"}


def checked(family: GrammarFamily) -> GrammarFamily:
    """``family`` when its lint finds no error; else ``DeviceFormatError`` (``FEN-3004``) naming the first
    errors, so a grammar that may parse an MPN two ways is never used to pick or decode."""
    found = errors(family)
    if found:
        shown = "; ".join(f"{item.code}: {item.message}" for item in found[:3])
        raise DeviceFormatError(
            f"the grammar {family.id} has {len(found)} lint error(s): {shown}",
            file=family.file,
            locator="fields",
        )
    return family


def _micro(unit: str, value: Fraction) -> int | None:
    scaled = value * power(MICRO_UNITS[unit][1])
    return scaled.numerator if scaled.denominator == 1 else None


def candidate_record(candidate: Candidate) -> DeviceDef:
    """The c0248 device of ``candidate`` (in memory only)."""
    family = candidate.family
    texts = candidate.code_texts()
    attributes = candidate.attributes()
    symbol = texts.get("symbol") or family.symbol
    footprint = texts.get("footprint") or family.footprint
    for name, given in (("symbol", symbol), ("footprint", footprint)):
        if not given:
            raise DeviceFormatError(
                f"{name}: the candidate {candidate.mpn} of {family.id} has no {name}; give it in the "
                "family or in a code",
                file=family.file,
                locator=name,
            )
    ratings: dict[str, Rating] = {}
    for attribute, rating_key in RATINGS:
        amount = attributes.get(attribute)
        if not isinstance(amount, Fraction) or rating_key in ratings:
            continue
        unit = _RATING_UNITS[rating_key]
        micro = _micro(unit, amount)
        if micro is not None:
            ratings[rating_key] = Rating(rating_key, cast(RatingUnit, MICRO_UNITS[unit][0]), None, micro)
    unit = VALUE_UNITS[family.kind]
    shown = value_text(unit, candidate.value)
    sources = tuple(sorted({*family.sources, *(item for ids in family.sources_by.values() for item in ids)}))
    (pin1, pad1), (pin2, pad2) = family.pins
    return DeviceDef(
        id=candidate.device,
        summary=f"{family.summary}, {shown}",
        symbol=symbol,
        footprint=footprint,
        manufacturer=family.manufacturer,
        mpn=candidate.mpn,
        datasheet=family.datasheet,
        ref_prefix=PREFIXES[family.kind],
        value=value_code(unit, candidate.value) if unit == "ohm" else shown,
        kind=family.kind,
        case=texts.get("case", ""),
        tolerance=texts.get("tolerance", ""),
        dielectric=texts.get("dielectric", ""),
        evidence=family.evidence,
        sources=sources,
        ends=("P1", "P2"),
        pins=(DevicePin("P1", ((pin1, pad1),)), DevicePin("P2", ((pin2, pad2),))),
        ratings=tuple(ratings[key] for key in sorted(ratings)),
    )


def candidate_row(candidate: Candidate, *, origin: Origin, catalog: str) -> Row:
    """The c0254 row of ``candidate``: device ``<family id>@<MPN>``, row the family id."""
    return Row(
        candidate.device,
        candidate.family.id,
        candidate.family.kind,
        candidate.value,
        MappingProxyType(candidate.attributes()),
        origin,
        catalog,
        candidate.sha256(),
        candidate.family.evidence,
        candidate_record(candidate),
    )


def expansion(family: GrammarFamily, query: PartQuery | None) -> Expansion:
    """The checked expansion of ``family`` under ``query``; above the limit, ``DeviceFormatError`` naming
    ``family.expansion-limit`` (a build cannot pick from a family it may not visit in full)."""
    found = Expansion(family, query)
    try:
        found.check()
    except ExpansionLimitError as error:
        raise DeviceFormatError(
            f"family.expansion-limit: {error.issue.message}", file=family.file, locator="valid"
        ) from None
    return found


def grammar_rows(
    family: GrammarFamily,
    *,
    queries: Iterable[PartQuery] = (),
    devices: Iterable[str] = (),
    origin: Origin,
    catalog: str,
) -> tuple[Row, ...]:
    """The rows of ``family`` a build needs: the candidates of each query of its kind, and each of
    ``devices`` (locked device ids) of the family that decodes, without a tail, inside its matrix; in device
    id order."""
    rows: dict[str, Row] = {}
    for query in queries:
        if query.kind != family.kind or query.generator is not None or query.value is None:
            continue
        for candidate in expansion(family, query):
            if candidate.device not in rows:
                rows[candidate.device] = candidate_row(candidate, origin=origin, catalog=catalog)
    prefix = f"{family.id}@"
    for device in devices:
        if not device.startswith(prefix) or device in rows:
            continue
        found = parse_mpn(family, device[len(prefix) :])
        if not isinstance(found, Candidate) or found.suffix:
            continue
        value_field = family.value_field
        assert value_field is not None
        codes = {name: code for name, code in found.codes if name != value_field.name}
        if admitted(family, codes, found.value):
            rows[device] = candidate_row(found, origin=origin, catalog=catalog)
    return tuple(rows[key] for key in sorted(rows))


__all__ = ["RATINGS", "candidate_record", "candidate_row", "checked", "expansion", "grammar_rows"]
