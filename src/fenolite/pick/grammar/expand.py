# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Lazy expansion of a grammar family into its candidates (change c0263, ``docs/picking.md``, "Families
with ordering codes").

The candidates come in the **canonical order**: fields in pattern order, codes in code-point order, values
rising. A query first cuts every field: an electrical field keeps the codes whose stated attributes meet the
query (c0254's matching), an ordering field keeps only its ``prefer``red code, and the value field keeps the
values the query admits (an exact quantity: that value; a range: the values inside it, the worst-case check
being c0254's). The product of the cut domains is known before the first step: above ``EXPANSION_LIMIT`` the
expansion is refused with ``family.expansion-limit``. Each combination is kept when some ``[[valid]]`` row
admits it and no ``[[exclude]]`` row removes it.
"""

from __future__ import annotations

import hashlib
import itertools
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType

from fenolite.core.errors import Issue
from fenolite.core.partquery import KEYS, VALUE_UNITS, Constraint, PartQuery, key
from fenolite.pick.grammar import EXPANSION_LIMIT
from fenolite.pick.grammar.codes import issue
from fenolite.pick.grammar.schema import Field, GrammarFamily, MatrixRow
from fenolite.pick.grammar.valuecodes import encode_value
from fenolite.pick.match import meets


class ExpansionLimitError(Exception):
    """A cut product above the limit: ``issue`` is the ``family.expansion-limit`` finding."""

    def __init__(self, found: Issue) -> None:
        super().__init__(found.message)
        self.issue = found


@dataclass(frozen=True, slots=True)
class Candidate:
    """One combination of a family: its MPN, the code of each field in pattern order (the value field's
    entry is the value's spelling), the exact value and an opaque ``suffix`` (decode only)."""

    family: GrammarFamily
    mpn: str
    codes: tuple[tuple[str, str], ...]
    value: Fraction
    suffix: str = ""

    @property
    def device(self) -> str:
        """``<family id>@<MPN>``: the device id a pick names."""
        return f"{self.family.id}@{self.mpn}"

    def code_texts(self) -> dict[str, str]:
        """Every attribute as the file wrote it, first stated wins, fields in pattern order."""
        out: dict[str, str] = {}
        for name, code in self.codes:
            found = self.family.fields[name].code(code)
            if found is None:
                continue
            for attribute, text in found.texts.items():
                out.setdefault(attribute, text)
        return out

    def attributes(self) -> dict[str, Constraint]:
        """The attributes by query key: every code's, and the value field's ``series`` unless a code states
        one."""
        out: dict[str, Constraint] = {}
        for name, code in self.codes:
            found = self.family.fields[name].code(code)
            if found is None:
                continue
            for attribute, value in found.attributes.items():
                out.setdefault(attribute, value)
        value_field = self.family.value_field
        if value_field is not None and value_field.series and "series" not in out:
            if any(attribute.name == "series" for attribute in KEYS[self.family.kind]):
                out["series"] = value_field.series
        return out

    def text(self) -> str:
        """The canonical text of the candidate: the family id and version, the MPN and the sorted
        attributes, one ``key = "value"`` line each; its SHA-256 is what a pick records."""
        from fenolite.pick.rows import value_text

        lines = {
            **self.code_texts(),
            "family": self.family.id,
            "version": self.family.version,
            "mpn": self.mpn,
            "manufacturer": self.family.manufacturer,
            "value": value_text(VALUE_UNITS[self.family.kind], self.value),
        }
        return "".join(f'{name} = "{lines[name]}"\n' for name in sorted(lines))

    def sha256(self) -> str:
        return hashlib.sha256(self.text().encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------ matrix


def _row_admits(
    family: GrammarFamily, row: MatrixRow, codes: Mapping[str, str], value: Fraction, *, valid: bool
) -> bool:
    for name, allowed in row.codes.items():
        if codes.get(name) not in allowed:
            return False
    if row.span is None:
        return True
    value_field = family.value_field
    series = value_field.series if value_field is not None else ""
    return row.span.admits(value, series, need_series=valid)


def admitted(family: GrammarFamily, codes: Mapping[str, str], value: Fraction) -> bool:
    """Whether the combination (field → code, and the value) is in the validity matrix: some ``[[valid]]``
    row admits it and no ``[[exclude]]`` row removes it."""
    if not any(_row_admits(family, row, codes, value, valid=True) for row in family.valid):
        return False
    return not any(_row_admits(family, row, codes, value, valid=False) for row in family.exclude)


def value_domain(
    family: GrammarFamily,
    rows: Sequence[MatrixRow] | None = None,
    *,
    low: Fraction | None = None,
    high: Fraction | None = None,
    exact: Fraction | None = None,
) -> tuple[Fraction, ...]:
    """The values of the ``[[valid]]`` rows (all of them by default), rising, cut to ``exact`` or to
    ``low``..``high``."""
    value_field = family.value_field
    if value_field is None:
        return ()
    found: set[Fraction] = set()
    for row in family.valid if rows is None else rows:
        if row.span is None:
            continue
        if exact is not None:
            if row.span.admits(exact, value_field.series, need_series=True):
                found.add(exact)
            continue
        found.update(row.span.domain(value_field.series, low, high))
    return tuple(sorted(found))


# ----------------------------------------------------------------------------------------- pruning


def _codes(family: GrammarFamily, item: Field, query: PartQuery | None) -> tuple[str, ...]:
    if query is None:
        return tuple(code.code for code in item.codes)
    pinned = query.get("row")
    if item.role == "ordering" and not (isinstance(pinned, str) and pinned.startswith(f"{family.id}@")):
        return (
            (item.prefer,) if item.code(item.prefer) is not None else tuple(code.code for code in item.codes)
        )
    kept: list[str] = []
    for code in item.codes:
        fails = False
        for name, wanted in query.constraints:
            if name == "row" or name not in code.attributes:
                continue
            if not meets(key(family.kind, name), wanted, code.attributes[name]):
                fails = True
                break
        if not fails:
            kept.append(code.code)
    return tuple(kept)


class Expansion:
    """The cut domains of a family under a query (``None``: every code and value), their product's
    ``size``, and the iteration over the valid combinations; ``visited`` counts the combinations looked at."""

    def __init__(
        self, family: GrammarFamily, query: PartQuery | None = None, *, limit: int = EXPANSION_LIMIT
    ) -> None:
        self.family = family
        self.query = query
        self.limit = limit
        self.visited = 0
        domains: dict[str, tuple[str, ...] | tuple[Fraction, ...]] = {}
        for name in family.placeholders:
            item = family.fields.get(name)
            if item is None or item.is_value:
                continue
            domains[name] = _codes(family, item, query)
        rows = [
            row
            for row in family.valid
            if all(
                any(code in domains.get(name, ()) for code in allowed) for name, allowed in row.codes.items()
            )
        ]
        value_field = family.value_field
        if value_field is not None:
            exact = low = high = None
            if query is not None and query.value is not None:
                if query.exact:
                    exact = query.value.low
                else:
                    low, high = query.value.low, query.value.high
            domains[value_field.name] = value_domain(family, rows, low=low, high=high, exact=exact)
        self.domains: Mapping[str, tuple[str, ...] | tuple[Fraction, ...]] = MappingProxyType(
            {name: domains[name] for name in family.placeholders if name in domains}
        )
        size = 1
        for values in self.domains.values():
            size *= len(values)
        self.size = size

    def sizes(self) -> dict[str, int]:
        return {name: len(values) for name, values in self.domains.items()}

    def check(self) -> None:
        """Refuse a product above the limit (``ExpansionLimitError``) before the first step."""
        if self.size > self.limit:
            shown = ", ".join(f"{name} {count}" for name, count in self.sizes().items())
            raise ExpansionLimitError(
                issue(
                    "family.expansion-limit",
                    f"{self.family.id}: {self.size} combinations to visit ({shown}) exceed the limit of "
                    f"{self.limit}",
                    self.family.id,
                    "narrow the query (an exact value, a case, a rating) so fewer combinations remain",
                )
            )

    def __iter__(self) -> Iterator[Candidate]:
        self.check()
        family = self.family
        value_field = family.value_field
        if value_field is None or len(self.domains) != len(family.placeholders):
            return
        names = list(self.domains)
        row_filter = None
        if self.query is not None:
            wanted = self.query.get("row")
            if isinstance(wanted, str) and wanted != family.id:
                if not wanted.startswith(f"{family.id}@"):
                    return
                row_filter = wanted
        for combination in itertools.product(*(self.domains[name] for name in names)):
            self.visited += 1
            chosen = dict(zip(names, combination, strict=True))
            value = chosen[value_field.name]
            assert isinstance(value, Fraction)
            codes = {name: str(code) for name, code in chosen.items() if name != value_field.name}
            if not admitted(family, codes, value):
                continue
            spelled = encode_value(value_field.scheme, value, value_field.scale)
            if spelled is None:
                continue
            codes[value_field.name] = spelled
            mpn = "".join(text if kind == "literal" else codes[text] for kind, text in family.tokens)
            candidate = Candidate(family, mpn, tuple((name, codes[name]) for name in names), value)
            if row_filter is not None and candidate.device != row_filter:
                continue
            yield candidate


def expand(
    family: GrammarFamily, query: PartQuery | None = None, *, limit: int = EXPANSION_LIMIT
) -> Iterator[Candidate]:
    """The candidates of ``family`` under ``query`` in canonical order; ``ExpansionLimitError`` when the cut
    product is above ``limit``."""
    expansion = Expansion(family, query, limit=limit)
    expansion.check()
    return iter(expansion)


__all__ = ["Candidate", "Expansion", "ExpansionLimitError", "admitted", "expand", "value_domain"]
